"""Floor cloths laid over the stage boards: a short Blender cloth settle per piece, exported as FBX.

Run headless:

    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --factory-startup --python Scripts/build_floor_cloth.py

Brief from Rig & atmosphere (25 Sep): 3-5 nearly flat canvas pieces with slight rumple and
edge curl (<= 3 cm relief), some torn or frayed at the edges, pivot at the centre, length along
+X (the route), width along Y, nominal 1200 x 500 cm. The structure pass lays one per bay.
Holes and frays that let the boards show through are alpha-cut by the material
(Scripts/build_floor_cloth_masks.py); this script makes the geometry.

The rumples are earned, not drawn: each piece starts a few percent compressed (low-frequency,
aperiodic), and its rest shape is the full flat canvas, so the solver has to buckle the excess
into ridges as it settles on the floor. The hem curl is a rest-shape set (canvas edges
curl because the hem is stiffer), which the solver then honours. No per-vertex noise anywhere.

Outputs: DerivedAssets/FloorCloth/SM_FloorCloth_<A..D>.fbx, <piece>.png previews, floor_cloth_report.json.
"""

from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def _project_root() -> Path:
    override = os.environ.get("PUSS_PROJECT_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1]


OUTPUT_DIR = _project_root() / "DerivedAssets" / "FloorCloth"
LENGTH = 12.0          # m, along +X
WIDTH = 5.0            # m, along Y
QUAD = float(os.environ.get("FLOOR_CLOTH_QUAD_M", "0.08"))
RELIEF_MAX = 0.03      # m, the brief's cap on rumple height
LIFT = 0.003           # m, lowest point sits this far above the boards (no z-fighting)
HEM = 0.12             # m, curled hem band
HEM_CURL = 0.015       # m, rise of the hem edge in the rest shape (3.5 cm alone used up the relief budget)
FRAMES = 110
SEED = int(os.environ.get("FLOOR_CLOTH_SEED", "20260925"))

# One entry per piece: whether its ends are torn in the geometry, and how much slack it carries.
PIECES = {
    "A": {"torn_ends": False, "slack_x": 0.028, "slack_y": 0.012},
    "B": {"torn_ends": True, "slack_x": 0.024, "slack_y": 0.015},
    "C": {"torn_ends": False, "slack_x": 0.035, "slack_y": 0.008},
    "D": {"torn_ends": True, "slack_x": 0.02, "slack_y": 0.018},
}


def value_noise(rng: random.Random, start: float, end: float, spacing: float):
    """Seeded aperiodic 1D noise in [0, 1] (random knots, smoothstep); see build_curtain_chaos_pattern.py."""
    knots = [start - spacing]
    while knots[-1] < end + spacing:
        knots.append(knots[-1] + spacing * rng.uniform(0.55, 1.45))
    values = [rng.random() for _ in knots]

    def f(s: float) -> float:
        lo, hi = 0, len(knots) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if knots[mid] <= s:
                lo = mid
            else:
                hi = mid
        t = min(1.0, max(0.0, (s - knots[lo]) / (knots[hi] - knots[lo])))
        t = t * t * (3.0 - 2.0 * t)
        return values[lo] * (1.0 - t) + values[hi] * t

    return f


def field_2d(rng: random.Random, spacing: float):
    """Low-frequency aperiodic 2D field in [0, 1]: product-free sum of two rotated 1D noises."""
    a, b = rng.uniform(0, math.pi), rng.uniform(0, math.pi)
    n1 = value_noise(rng, -10.0, 10.0, spacing)
    n2 = value_noise(rng, -10.0, 10.0, spacing * 1.3)

    def f(x: float, y: float) -> float:
        return 0.5 * (n1(x * math.cos(a) + y * math.sin(a)) + n2(x * math.cos(b) + y * math.sin(b)))

    return f


def hem_curl(d_edge: float) -> float:
    """Rest-shape lift of the hem: zero inboard of the band, rising to HEM_CURL at the very edge."""
    if d_edge >= HEM:
        return 0.0
    t = 1.0 - d_edge / HEM
    return HEM_CURL * t * t


def build_piece(name: str, spec: dict, rng: random.Random) -> tuple[bpy.types.Object, dict]:
    cols = int(round(LENGTH / QUAD))
    rows = int(round(WIDTH / QUAD))
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    grid = []
    for j in range(rows + 1):
        y = (j / rows - 0.5) * WIDTH
        grid.append([bm.verts.new(((i / cols - 0.5) * LENGTH, y, 0.0)) for i in range(cols + 1)])
    for j in range(rows):
        for i in range(cols):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            f.smooth = True
            for loop in f.loops:
                co = loop.vert.co
                loop[uv_layer].uv = (co.x / LENGTH + 0.5, co.y / WIDTH + 0.5)

    report = {"torn_ends": spec["torn_ends"], "slack": [spec["slack_x"], spec["slack_y"]]}
    if spec["torn_ends"]:
        # Torn ends: each end worn back 0-0.7 m along a ragged, non-repeating line.
        ends = [value_noise(rng, -WIDTH, WIDTH, 0.8), value_noise(rng, -WIDTH, WIDTH, 0.8)]
        detail = [value_noise(rng, -WIDTH, WIDTH, 0.25), value_noise(rng, -WIDTH, WIDTH, 0.25)]
        doomed = []
        for f in bm.faces:
            c = f.calc_center_median()
            for side, sign in ((0, -1.0), (1, 1.0)):
                depth = 0.7 * ends[side](c.y) ** 1.5 + 0.12 * detail[side](c.y)
                if sign * c.x > 0.5 * LENGTH - depth:
                    doomed.append(f)
                    break
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        # Relax the stair-stepped cut toward a smooth ragged outline (boundary verts only, <= 0.45 quad).
        boundary = [v for v in bm.verts if v.is_boundary and abs(abs(v.co.y) - 0.5 * WIDTH) > 1e-6]
        origin = {v: v.co.copy() for v in boundary}
        for _ in range(4):
            targets = {}
            for v in boundary:
                nbrs = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
                if len(nbrs) == 2:
                    targets[v] = v.co.lerp((nbrs[0].co + nbrs[1].co) * 0.5, 0.5)
            for v, t in targets.items():
                d = t - origin[v]
                if d.length > 0.45 * QUAD:
                    d = d.normalized() * 0.45 * QUAD
                v.co = origin[v] + d
        for f in bm.faces:
            for loop in f.loops:
                co = loop.vert.co
                loop[uv_layer].uv = (co.x / LENGTH + 0.5, co.y / WIDTH + 0.5)
        report["cut_faces"] = len(doomed)

    mesh = bpy.data.meshes.new(f"FloorCloth_{name}")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"SM_FloorCloth_{name}", mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Rest shape: the full flat canvas with the hem curled up. Basis (start pose): compressed.
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    x_min, x_max, y_min, y_max = min(xs), max(xs), min(ys), max(ys)
    obj.shape_key_add(name="Basis", from_mix=False)
    rest = obj.shape_key_add(name="Rest", from_mix=False)
    for v, rk in zip(mesh.vertices, rest.data):
        d_edge = min(v.co.x - x_min, x_max - v.co.x, v.co.y - y_min, y_max - v.co.y)
        rk.co = Vector((v.co.x, v.co.y, hem_curl(d_edge)))

    # Start pose: squeeze the canvas by a low-frequency, aperiodic amount so it carries slack.
    squeeze = field_2d(rng, 2.2)
    lift = field_2d(rng, 1.6)
    basis = obj.data.shape_keys.key_blocks["Basis"]
    for v, bk in zip(mesh.vertices, basis.data):
        sx = 1.0 - spec["slack_x"] * (0.5 + squeeze(v.co.x, v.co.y))
        sy = 1.0 - spec["slack_y"] * (0.5 + squeeze(v.co.y + 7.0, v.co.x))
        # A few mm of low-frequency lift so the buckles choose "up" (the floor is below).
        bk.co = Vector((v.co.x * sx, v.co.y * sy, 0.004 + 0.004 * lift(v.co.x, v.co.y)))
    return obj, report


def add_floor() -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "Boards"
    floor.modifiers.new(name="Collision", type="COLLISION")
    floor.collision.thickness_outer = 0.002
    floor.collision.cloth_friction = 12.0
    return floor


def settle(obj: bpy.types.Object) -> None:
    cloth = obj.modifiers.new(name="Cloth", type="CLOTH")
    s = cloth.settings
    s.quality = 6
    s.mass = 0.45 * QUAD * QUAD          # ~0.45 kg/m2 canvas, per vertex
    s.tension_stiffness = 80.0
    s.compression_stiffness = 4.0        # will not stretch, buckles freely (the curtain's lesson)
    s.shear_stiffness = 20.0
    s.bending_stiffness = 0.35           # canvas: stiffer than velvet, but soft enough not to tent
    s.bending_model = "ANGULAR"
    s.tension_damping = 5.0
    s.compression_damping = 2.0
    s.bending_damping = 0.5
    s.air_damping = 2.0
    s.rest_shape_key = obj.data.shape_keys.key_blocks["Rest"]
    c = cloth.collision_settings
    c.use_collision = True
    c.distance_min = 0.002
    c.use_self_collision = False
    c.collision_quality = 3
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = FRAMES
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, FRAMES
    scene.frame_set(1)
    with bpy.context.temp_override(scene=scene, active_object=obj, object=obj, point_cache=cloth.point_cache):
        bpy.ops.ptcache.bake(bake=True)
    scene.frame_set(FRAMES)


def freeze_and_cap(obj: bpy.types.Object) -> dict:
    """Apply the settled frame as the mesh, then cap relief to the brief and lift off the boards."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    settled = obj.evaluated_get(depsgraph).to_mesh()
    cos = [v.co.copy() for v in settled.vertices]
    obj.evaluated_get(depsgraph).to_mesh_clear()
    obj.shape_key_clear()
    obj.modifiers.clear()
    zs = sorted(c.z for c in cos)
    z0 = zs[0]
    relief = zs[-1] - z0
    p99 = zs[int(0.99 * (len(zs) - 1))] - z0
    # Soft cap: small rumples pass nearly unchanged, tall folds are pressed down toward the cap
    # (as if trodden flat). A linear scale let one tall fold flatten a whole piece to ~9%.
    cap = RELIEF_MAX
    for v, c in zip(obj.data.vertices, cos):
        v.co = Vector((c.x, c.y, LIFT + cap * math.tanh((c.z - z0) / cap)))
    # Recentre in XY so the pivot is the piece's centre after the settle drew it in.
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    cx, cy = 0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys))
    for v in obj.data.vertices:
        v.co.x -= cx
        v.co.y -= cy
    obj.data.update()
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return {"relief_raw_m": round(relief, 4), "relief_raw_p99_m": round(p99, 4),
            "size_m": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3), round(max(zs) - min(zs), 4)],
            "z_range_m": [round(min(zs), 4), round(max(zs), 4)],
            "vertices": len(obj.data.vertices), "faces": len(obj.data.polygons)}


def preview(obj: bpy.types.Object, path: Path) -> None:
    """Raking-light workbench render of the piece, so the rumples and curl can be judged."""
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = LENGTH * 1.05
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.0, -6.0, 3.0)
    cam.rotation_euler = (math.radians(63.0), 0.0, 0.0)
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    obj.color = (0.62, 0.55, 0.43, 1.0)
    if "Boards" in bpy.data.objects:
        bpy.data.objects["Boards"].color = (0.16, 0.11, 0.08, 1.0)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 2.0
    scene.render.resolution_x, scene.render.resolution_y = 1800, 900
    scene.render.filepath = str(path)
    for o in scene.objects:
        o.hide_render = o not in (obj, cam) and o.name != "Boards"
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)


def export(obj: bpy.types.Object, path: Path) -> None:
    for o in bpy.context.scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH"}, global_scale=1.0,
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", use_space_transform=True,
        bake_space_transform=False, axis_forward="-Y", axis_up="Z", use_mesh_modifiers=False,
        mesh_smooth_type="FACE", use_tspace=False, add_leaf_bones=False, bake_anim=False,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for index, (name, spec) in enumerate(PIECES.items()):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.system = "METRIC"
        rng = random.Random(SEED + 101 * index)
        add_floor()
        obj, report = build_piece(name, spec, rng)
        mat = bpy.data.materials.new("M_FloorCloth")
        obj.data.materials.append(mat)
        settle(obj)
        report.update(freeze_and_cap(obj))
        fbx = OUTPUT_DIR / f"SM_FloorCloth_{name}.fbx"
        export(obj, fbx)
        png = OUTPUT_DIR / f"SM_FloorCloth_{name}_preview.png"
        preview(obj, png)
        report.update({"fbx": str(fbx), "preview": str(png)})
        results[name] = report
        print(f"FLOOR_CLOTH_PIECE|{name}|{json.dumps(report)}")
    (OUTPUT_DIR / "floor_cloth_report.json").write_text(json.dumps(
        {"seed": SEED, "quad_m": QUAD, "nominal_m": [LENGTH, WIDTH], "relief_max_m": RELIEF_MAX, "lift_m": LIFT,
         "pieces": results}, indent=1), encoding="utf-8")
    print(f"FLOOR_CLOTH_SUCCESS|pieces={len(results)}")


if __name__ == "__main__":
    main()
