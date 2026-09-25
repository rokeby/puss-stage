"""Bake a heavy, loosely gathered theatre curtain with Blender cloth and export it as Alembic.

Run headless:

    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --python Scripts/build_curtain_cloth_bake.py

Design (see Docs/InfinityStageSessionHandover.md, 21 September):
- Full stage scale, matching the fire-safety curtain: TRACK_WIDTH x DROP metres.
- The pattern is FULLNESS times wider than the track and is pre-pleated (a sine
  fold across the width). Like a dressed stage drape the pleated pose is the rest
  state: the folds persist and the fullness shows in the swags when lifted. (A
  flat rest shape was tried first: the hem relaxed sideways into a wide splay.)
- Top row pinned to the track. Five hem lift points ride animated hook empties:
  the hem rises and the fabric between the lines bunches into swags, the way a
  festoon curtain does. Sides are free and gather into wavy edges.
- One timeline: settle, rise, hold, lower, settle. Unreal plays sub-ranges.

Outputs go to DerivedAssets/CurtainCloth/.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
import random

from mathutils import Matrix, Vector


def _project_root() -> Path:
    override = os.environ.get("PUSS_PROJECT_ROOT")
    if override:
        return Path(override)
    try:
        return Path(__file__).resolve().parents[1]
    except NameError as exc:  # pragma: no cover - Blender text editor only
        raise SystemExit("Set PUSS_PROJECT_ROOT to the PussStage folder.") from exc


PROJECT_ROOT = _project_root()
OUTPUT_DIR = PROJECT_ROOT / "DerivedAssets" / "CurtainCloth"
# "fly": one batten lifts the whole drop straight up (fabric trails and sways).
# "festoon": hem lift lines gather it into swags.
MODE = os.environ.get("CURTAIN_MODE", "fly")
STEM = "CurtainCloth_Fly_V1" if MODE == "fly" else "CurtainCloth_Festoon_V1"
ALEMBIC_OUTPUT = OUTPUT_DIR / f"{STEM}.abc"
BLEND_OUTPUT = OUTPUT_DIR / f"{STEM}.blend"
REPORT_OUTPUT = OUTPUT_DIR / f"{STEM}_report.json"

# Stage geometry (metres). Matches SM_FireSafetyCurtain_01.
TRACK_WIDTH = 17.77
DROP = 10.0
FULLNESS = float(os.environ.get("CURTAIN_FULLNESS", "2.0" if MODE == "fly" else "1.6"))
FOLD_WAVELENGTH = float(os.environ.get("CURTAIN_FOLD_M", "0.85" if MODE == "fly" else "0.9"))   # fold spacing along the track: fewer, looser folds for the plain drop
QUAD_SIZE = float(os.environ.get("CURTAIN_QUAD_M", "0.12" if MODE == "festoon" else "0.09"))
LIFT_LINES = 5
LIFT_CLUSTER_RADIUS = 0.35     # hem vertices within this radius of a lift line ride its hook
RAISED_HEM_HEIGHT = DROP - 1.1  # festoon: hem stops this far up, bunched under the track
FLY_HEIGHT = DROP + 1.0          # fly: the batten rises until the hem clears the top of the opening

FPS = 30
F_SETTLE_END = 90
F_RISE_END = F_SETTLE_END + 120   # 4 s rise
F_HOLD_END = F_RISE_END + 60
F_LOWER_END = F_HOLD_END + 90     # 3 s lower
F_END = F_LOWER_END + 45

# Cloth: heavy velvet, no flutter.
CLOTH = dict(
    quality=int(os.environ.get("CURTAIN_SUBSTEPS", "8" if MODE == "festoon" else "12")),
    # Blender mass is per vertex: ~95 verts/m2 here, so 0.08 is a heavy 7 kg/m2 hang
    # (1.2 was 200 kg/m2 and wobbled like jelly).
    mass=1.0 if MODE == "festoon" else 0.05,
    # Fabric: will not stretch, folds for free. Compression far below tension is
    # what lets it crease and crumple instead of bulging like a plate.
    tension_stiffness=40.0 if MODE == "festoon" else 200.0,
    compression_stiffness=40.0 if MODE == "festoon" else 3.0,
    shear_stiffness=15.0 if MODE == "festoon" else 60.0,
    bending_stiffness=1.5 if MODE == "festoon" else 0.1,
    tension_damping=8.0 if MODE == "festoon" else 3.0,
    compression_damping=8.0 if MODE == "festoon" else 0.5,
    shear_damping=8.0 if MODE == "festoon" else 3.0,
    bending_damping=0.8 if MODE == "festoon" else 0.15,
    air_damping=1.5 if MODE == "festoon" else 0.8,
    pin_stiffness=1.0,
)
SELF_COLLISION_DISTANCE = 0.012 if MODE == "festoon" else 0.009
COLLISION_QUALITY = 4


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = F_END
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def sine_amplitude_for_fullness(wavelength: float, fullness: float) -> float:
    """Amplitude A such that the arc length of A*sin(2*pi*x/wavelength) is `fullness` x the chord."""
    lo, hi = 0.0, wavelength
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        n = 400
        length = 0.0
        prev = Vector((0.0, mid * math.sin(0.0)))
        for i in range(1, n + 1):
            x = wavelength * i / n
            cur = Vector((x, mid * math.sin(2.0 * math.pi * x / wavelength)))
            length += (cur - prev).length
            prev = cur
        if length / wavelength < fullness:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def build_curtain() -> tuple[bpy.types.Object, list[int], list[list[int]]]:
    """Grid in the XZ plane, hanging from z=DROP to z=0, facing -Y. Returns (object, top_row, lift_clusters)."""
    pattern_width = TRACK_WIDTH * FULLNESS
    cols = max(8, int(round(pattern_width / QUAD_SIZE)))
    rows = max(8, int(round(DROP / QUAD_SIZE)))
    amplitude = sine_amplitude_for_fullness(FOLD_WAVELENGTH, FULLNESS)
    # Loosely bunched, not a radiator: each pleat gets its own depth and a slight
    # phase drift, seeded so the bake is repeatable.
    rng = random.Random(20260921)
    pleat_count = int(round(TRACK_WIDTH / FOLD_WAVELENGTH)) + 2
    pleat_gain = [rng.uniform(0.7, 1.3) for _ in range(pleat_count)]
    pleat_phase = [rng.uniform(-0.35, 0.35) for _ in range(pleat_count)]
    if MODE == "fly":
        # Fabric, not an accordion: every fold gets its own depth, sharpness and
        # drift, and the ridge sharpness varies down the drop.
        pleat_gain = [rng.uniform(0.45, 1.6) for _ in range(pleat_count)]
        pleat_phase = [rng.uniform(-0.9, 0.9) for _ in range(pleat_count)]
        pleat_sharp = [rng.uniform(0.15, 0.7) for _ in range(pleat_count)]

    flat = []
    pleated = []
    for r in range(rows + 1):
        z = DROP * (1.0 - r / rows)
        for c in range(cols + 1):
            u = c / cols
            x_flat = (u - 0.5) * pattern_width
            x_track = (u - 0.5) * TRACK_WIDTH
            # Fold depth fades slightly toward the hem so the bottom hangs a little looser.
            pleat_index = int((x_track + 0.5 * TRACK_WIDTH) / FOLD_WAVELENGTH)
            gain = pleat_gain[min(pleat_index, pleat_count - 1)]
            phase = pleat_phase[min(pleat_index, pleat_count - 1)] * (1.0 - z / DROP)
            if MODE == "fly":
                phase += 0.6 * math.sin(2.0 * math.pi * z / 6.5 + pleat_index * 1.7) * (1.0 - z / DROP)
            depth = amplitude * gain * (0.85 + 0.15 * (z / DROP))
            arg = 2.0 * math.pi * x_track / FOLD_WAVELENGTH + phase
            if MODE == "fly":
                # Triangle-wave heading: sharp ridges that the sim inherits as creases,
                # blended with a little sine so it is not a saw blade; per-vertex noise
                # seeds irregular buckling lower down.
                tri = 2.0 / math.pi * math.asin(math.sin(arg))
                sharp = pleat_sharp[min(pleat_index, pleat_count - 1)] * (0.6 + 0.4 * z / DROP)
                # No artificial noise: any wrinkle finer than the pleats must be earned
                # by the solver, or it reads as a stamped pattern.
                y = depth * (sharp * tri + (1.0 - sharp) * math.sin(arg)) * 1.1
            else:
                y = depth * math.sin(arg)
            flat.append((x_flat, 0.0, z))
            pleated.append((x_track, y, z))
    faces = []
    for r in range(rows):
        for c in range(cols):
            a = r * (cols + 1) + c
            faces.append((a, a + 1, a + cols + 2, a + cols + 1))

    mesh = bpy.data.meshes.new("CurtainCloth")
    mesh.from_pydata(pleated, [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    uv = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            r, c = divmod(vi, cols + 1)
            uv.data[li].uv = (c / cols, 1.0 - r / rows)
    obj = bpy.data.objects.new("Curtain", mesh)
    bpy.context.collection.objects.link(obj)

    # Rest shape = the flat pattern; basis = the pleated start pose.
    obj.shape_key_add(name="Basis", from_mix=False)
    flat_key = obj.shape_key_add(name="Flat", from_mix=False)
    for i, co in enumerate(flat):
        flat_key.data[i].co = Vector(co)

    top_row = [c for c in range(cols + 1)]
    hem_rows = [rows * (cols + 1) + c for c in range(cols + 1)] + [(rows - 1) * (cols + 1) + c for c in range(cols + 1)]
    clusters = []
    for k in range(LIFT_LINES):
        x_line = (k / (LIFT_LINES - 1) - 0.5) * TRACK_WIDTH * 0.92
        cluster = [vi for vi in hem_rows if abs(pleated[vi][0] - x_line) <= LIFT_CLUSTER_RADIUS]
        clusters.append(cluster)
    return obj, top_row, clusters


def add_hooks_and_pins(obj: bpy.types.Object, top_row: list[int], clusters: list[list[int]]) -> list[bpy.types.Object]:
    pins = obj.vertex_groups.new(name="Pins")
    pins.add(top_row, 1.0, "REPLACE")
    empties = []
    if MODE == "fly":
        # One batten carries the whole top edge; the fabric below is free.
        centre = sum((obj.data.vertices[vi].co for vi in top_row), Vector()) / len(top_row)
        batten = bpy.data.objects.new("Batten", None)
        batten.empty_display_type = "CUBE"
        batten.empty_display_size = 0.3
        batten.location = obj.matrix_world @ centre
        bpy.context.collection.objects.link(batten)
        hook = obj.modifiers.new(name="Hook_Batten", type="HOOK")
        hook.object = batten
        hook.vertex_indices_set(top_row)
        hook.center = centre
        hook.matrix_inverse = Matrix.Translation(obj.matrix_world @ centre).inverted()
        return [batten]
    for k, cluster in enumerate(clusters):
        if not cluster:
            continue
        centre = sum((obj.data.vertices[vi].co for vi in cluster), Vector()) / len(cluster)
        empty = bpy.data.objects.new(f"Lift_{k:02d}", None)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = 0.2
        empty.location = obj.matrix_world @ centre
        bpy.context.collection.objects.link(empty)
        hook = obj.modifiers.new(name=f"Hook_{k:02d}", type="HOOK")
        hook.object = empty
        hook.vertex_indices_set(cluster)
        hook.center = centre
        # The empty's world matrix is not evaluated yet at this point; build the
        # inverse from its intended location or the hooked verts get offset by it.
        hook.matrix_inverse = Matrix.Translation(obj.matrix_world @ centre).inverted()
        hook.strength = 1.0
        pins.add(cluster, 1.0, "REPLACE")
        empties.append(empty)
    return empties


def key_lift(empties: list[bpy.types.Object]) -> None:
    for i, empty in enumerate(empties):
        z0 = empty.location.z
        if MODE == "fly":
            keys = [(1, z0), (F_SETTLE_END, z0), (F_RISE_END, z0 + FLY_HEIGHT), (F_HOLD_END, z0 + FLY_HEIGHT), (F_LOWER_END, z0), (F_END, z0)]
            for frame, z in keys:
                empty.location.z = z
                empty.keyframe_insert(data_path="location", index=2, frame=frame)
            for fc in empty.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "QUAD"
                    kp.easing = "EASE_IN_OUT"
            continue
        # Stagger the lines a few frames so the swags do not move as one block.
        stagger = int(round((i - (len(empties) - 1) / 2.0) * 3))
        keys = [
            (1, z0),
            (F_SETTLE_END + stagger, z0),
            (F_RISE_END + stagger, z0 + RAISED_HEM_HEIGHT),
            (F_HOLD_END - stagger, z0 + RAISED_HEM_HEIGHT),
            (F_LOWER_END - stagger, z0),
            (F_END, z0),
        ]
        for frame, z in keys:
            empty.location.z = z
            empty.keyframe_insert(data_path="location", index=2, frame=frame)
        for fc in empty.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def add_gentle_air() -> None:
    bpy.ops.object.effector_add(type="TURBULENCE", location=(0.0, -3.0, DROP * 0.5))
    field = bpy.context.object
    field.name = "GentleAir"
    field.field.strength = 0.5
    field.field.size = 4.0
    field.field.flow = 0.3
    field.field.noise = 0.2
    field.field.seed = 7


def add_cloth(obj: bpy.types.Object) -> bpy.types.ClothModifier:
    cloth = obj.modifiers.new(name="Cloth", type="CLOTH")
    s = cloth.settings
    for key, value in CLOTH.items():
        setattr(s, key, value)
    s.bending_model = "ANGULAR"      # separate compression stiffness needs the angular model
    s.vertex_group_mass = "Pins"
    # Dressed drape: the pleated pose is the rest state, so folds persist instead of
    # the fabric relaxing sideways toward the flat pattern width.
    # Fly mode: the flat pattern is the rest state (real fullness that buckles into
    # irregular folds); festoon keeps the dressed pleats.
    s.rest_shape_key = obj.data.shape_keys.key_blocks["Flat"] if MODE == "fly" else None
    s.use_dynamic_mesh = False
    c = cloth.collision_settings
    c.use_collision = False           # nothing else to hit; self-collision only
    c.use_self_collision = True
    c.self_distance_min = SELF_COLLISION_DISTANCE
    c.collision_quality = COLLISION_QUALITY
    c.self_friction = 8.0 if MODE == "festoon" else 30.0   # folds hold their structure instead of sliding flat
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = F_END
    return cloth


def bake(obj: bpy.types.Object, cloth: bpy.types.ClothModifier) -> None:
    scene = bpy.context.scene
    scene.frame_set(1)
    with bpy.context.temp_override(scene=scene, active_object=obj, object=obj, point_cache=cloth.point_cache):
        bpy.ops.ptcache.bake(bake=True)


def setup_preview_camera() -> bpy.types.Object:
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 24.0 if MODE == "festoon" else 16.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = Vector((0.0, -22.0, DROP * 0.5 if MODE == "festoon" else DROP * 0.95))
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    bpy.context.scene.camera = cam
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.55, 0.12, 0.12)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.film_transparent = False
    return cam


def render_previews() -> dict[str, str]:
    scene = bpy.context.scene
    out = {}
    for name, frame in (("settled", F_SETTLE_END), ("mid_rise", F_SETTLE_END + 60), ("raised", F_HOLD_END - 5), ("mid_lower", F_HOLD_END + 45), ("relowered", F_END)):
        scene.frame_set(frame)
        path = OUTPUT_DIR / f"{STEM}_preview_{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        out[name] = str(path)
    return out


def export_alembic(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.alembic_export(
        filepath=str(ALEMBIC_OUTPUT),
        start=1,
        end=F_END,
        selected=True,
        visible_objects_only=False,
        flatten=True,
        uvs=True,
        normals=True,
        apply_subdiv=False,
        export_hair=False,
        export_particles=False,
        evaluation_mode="VIEWPORT",
        global_scale=1.0,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clear_scene()
    obj, top_row, clusters = build_curtain()
    empties = add_hooks_and_pins(obj, top_row, clusters)
    key_lift(empties)
    cloth = add_cloth(obj)
    if MODE == "fly":
        add_gentle_air()
    setup_preview_camera()
    bake(obj, cloth)
    previews = render_previews()
    export_alembic(obj)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT))
    report = {
        "mode": MODE,
        "alembic": str(ALEMBIC_OUTPUT),
        "blend": str(BLEND_OUTPUT),
        "previews": previews,
        "fps": FPS,
        "frames": {"settle_end": F_SETTLE_END, "rise_end": F_RISE_END, "hold_end": F_HOLD_END, "lower_end": F_LOWER_END, "end": F_END},
        "vertices": len(obj.data.vertices),
        "track_width_m": TRACK_WIDTH,
        "drop_m": DROP,
        "fullness": FULLNESS,
        "quad_m": QUAD_SIZE,
        "lift_lines": len(empties),
        "cloth": CLOTH,
    }
    REPORT_OUTPUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"CURTAIN_CLOTH_BAKE_SUCCESS|vertices={len(obj.data.vertices)}|frames={F_END}|abc={ALEMBIC_OUTPUT}")


if __name__ == "__main__":
    main()
