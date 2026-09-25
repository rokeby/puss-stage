"""Cut a heavy, ragged stage-curtain pattern for Chaos Cloth and export it as a static-mesh FBX.

Blender is the pattern cutter here, not the simulator: Unreal's Chaos Cloth simulates
it live in the editor. Run headless:

    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --python Scripts/build_curtain_chaos_pattern.py

What goes in the file, and why (see Docs/Conductor/BRIEF_SOFT_GOODS_2026-09-25.md):
- UV0 is the flat 2D pattern: a drop FULLNESS times wider than the track, normalised
  0-1. Chaos imports it with UVScale = (pattern width, drop) in cm, so the rest lengths
  are the flat fabric's. Nothing is pleated at rest; every fold is the solver's.
- The 3D positions are the start pose: the same fabric gathered onto the track in
  pleats (pleat-scale variation only). The pleated arc length equals the flat width,
  so the start pose is unstretched.
- Raggedness is boundary topology, never surface noise: a torn hem, frayed sides,
  tears that run up from the hem (split edges, opened a few mm) and holes. The rule
  from the Blender bakes carries over: any wrinkle finer than the pleats must be
  earned by the solver.
- Columns are sized so a seam line falls on a grid line every SEAM_WIDTH_M of flat
  fabric (the width of a bolt of cloth). The material draws the seams from UV0.
- The top row is the heading tied to the batten. Its vertex indices are written to
  the sidecar JSON; Unreal makes them kinematic.

Outputs go to DerivedAssets/CurtainCloth/Chaos/.
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
    try:
        return Path(__file__).resolve().parents[1]
    except NameError as exc:  # pragma: no cover - Blender text editor only
        raise SystemExit("Set PUSS_PROJECT_ROOT to the PussStage folder.") from exc


PROJECT_ROOT = _project_root()
OUTPUT_DIR = PROJECT_ROOT / "DerivedAssets" / "CurtainCloth" / "Chaos"

# Stage geometry (metres). Matches SM_FireSafetyCurtain_01.
TRACK_WIDTH = 17.77
DROP = 10.0
FULLNESS = float(os.environ.get("CURTAIN_FULLNESS", "2.0"))
SEAM_WIDTH_M = 1.37                     # one bolt of cloth
# Grid spacing: quads per bolt width. 9 per bolt = 15.2 cm (interactive), 15 = 9.1 cm (the bake resolution).
QUADS_PER_BOLT = int(os.environ.get("CURTAIN_QUADS_PER_BOLT", "9"))
FOLD_WAVELENGTH = 0.85                  # pleat spacing along the track
SEED = int(os.environ.get("CURTAIN_SEED", "20260925"))
RAGGED = os.environ.get("CURTAIN_RAGGED", "1") != "0"

QUAD_X = SEAM_WIDTH_M / QUADS_PER_BOLT
PATTERN_WIDTH = TRACK_WIDTH * FULLNESS
COLS = int(round(PATTERN_WIDTH / QUAD_X))
PATTERN_WIDTH = COLS * QUAD_X           # snap to whole quads so seams stay on grid lines
ROWS = int(round(DROP / QUAD_X))
QUAD_Z = DROP / ROWS

STEM = f"CurtainChaos_Ragged_Q{int(round(QUAD_X * 100)):02d}" if RAGGED else f"CurtainChaos_Plain_Q{int(round(QUAD_X * 100)):02d}"
FBX_OUTPUT = OUTPUT_DIR / f"SM_{STEM}.fbx"
BLEND_OUTPUT = OUTPUT_DIR / f"{STEM}.blend"
SIDECAR_OUTPUT = OUTPUT_DIR / f"{STEM}.json"
PREVIEW_OUTPUT = OUTPUT_DIR / f"{STEM}_pattern.png"


def sine_amplitude_for_fullness(wavelength: float, fullness: float) -> float:
    """Amplitude A such that the arc length of A*sin(2*pi*x/wavelength) is `fullness` x the chord."""
    lo, hi = 0.0, wavelength
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        n = 400
        length = 0.0
        prev = Vector((0.0, 0.0))
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


class Pleats:
    """The start pose: flat pattern x -> gathered track position, pleated in depth.

    The gather is done by arc length so the pleated line is exactly as long as the
    flat fabric, i.e. the start pose carries no stretch. Pleat depth and phase vary per
    pleat (pleat-scale, not per vertex)."""

    def __init__(self, rng: random.Random) -> None:
        self.amplitude = sine_amplitude_for_fullness(FOLD_WAVELENGTH, FULLNESS)
        count = int(math.ceil(TRACK_WIDTH / FOLD_WAVELENGTH)) + 2
        self.gain = [rng.uniform(0.6, 1.25) for _ in range(count)]
        # Tabulate arc length along the pleated track so flat x maps to track x exactly.
        self.samples = 20000
        self.track = []
        self.arc = []
        total = 0.0
        prev = None
        for i in range(self.samples + 1):
            xt = (i / self.samples - 0.5) * TRACK_WIDTH
            y = self.depth(xt)
            if prev is not None:
                total += math.hypot(xt - prev[0], y - prev[1])
            self.track.append(xt)
            self.arc.append(total)
            prev = (xt, y)
        self.total = total

    def depth(self, x_track: float) -> float:
        k = (x_track + 0.5 * TRACK_WIDTH) / FOLD_WAVELENGTH
        i = min(int(k), len(self.gain) - 1)
        j = min(i + 1, len(self.gain) - 1)
        t = k - int(k)
        gain = self.gain[i] * (1.0 - t) + self.gain[j] * t
        return self.amplitude * gain * math.sin(2.0 * math.pi * x_track / FOLD_WAVELENGTH)

    def position(self, x_flat: float) -> tuple[float, float]:
        s = (x_flat / PATTERN_WIDTH + 0.5) * self.total
        lo, hi = 0, self.samples
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.arc[mid] < s:
                lo = mid
            else:
                hi = mid
        span = self.arc[hi] - self.arc[lo]
        t = 0.0 if span <= 0.0 else (s - self.arc[lo]) / span
        xt = self.track[lo] + (self.track[hi] - self.track[lo]) * t
        return xt, self.depth(xt)


def value_noise(rng: random.Random, start: float, end: float, spacing: float) -> callable:
    """Seeded, aperiodic 1D noise in [0, 1]: random values at jittered knots, smoothstep between.

    Sine sums repeat visibly across a 35 m drop (the "stamped pattern" failure); this does not."""
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
        t = (s - knots[lo]) / (knots[hi] - knots[lo])
        t = min(1.0, max(0.0, t))
        t = t * t * (3.0 - 2.0 * t)
        return values[lo] * (1.0 - t) + values[hi] * t

    return f


def layered_noise(rng: random.Random, start: float, end: float, spacings: tuple[float, ...], weights: tuple[float, ...]) -> callable:
    layers = [value_noise(rng, start, end, s) for s in spacings]
    total = sum(weights)

    def f(s: float) -> float:
        return sum(w * layer(s) for w, layer in zip(weights, layers)) / total

    return f


def build_grid() -> bmesh.types.BMesh:
    bm = bmesh.new()
    grid = []
    for r in range(ROWS + 1):
        z = DROP * (1.0 - r / ROWS)
        row = []
        for c in range(COLS + 1):
            x = (c / COLS - 0.5) * PATTERN_WIDTH
            v = bm.verts.new((x, 0.0, z))
            row.append(v)
        grid.append(row)
    uv_layer = bm.loops.layers.uv.new("UVMap")
    for r in range(ROWS):
        for c in range(COLS):
            face = bm.faces.new((grid[r][c], grid[r + 1][c], grid[r + 1][c + 1], grid[r][c + 1]))
            face.smooth = True
            for loop in face.loops:
                co = loop.vert.co
                loop[uv_layer].uv = (co.x / PATTERN_WIDTH + 0.5, co.z / DROP)
    return bm


def cut_rags(bm: bmesh.types.BMesh, rng: random.Random) -> dict:
    """Tear the hem, fray the sides, rip tears up from the hem and punch holes. All in the flat pattern."""
    report = {"hem": {}, "sides": {}, "tongues": [], "tears": [], "holes": []}
    half = 0.5 * PATTERN_WIDTH
    # Hem: worn back unevenly, from intact to the floor to ~1 m, rougher at small scale.
    hem_noise = layered_noise(rng, -half, half, (2.8, 0.9, 0.33), (1.0, 0.45, 0.2))
    # Tongues: a few places where a strip has torn away well up into the drop.
    tongues = []
    for _ in range(rng.randint(3, 5)):
        tongues.append((rng.uniform(-0.46, 0.46) * PATTERN_WIDTH, rng.uniform(0.25, 0.7), rng.uniform(1.2, 2.6)))
    report["tongues"] = [{"x_flat_m": round(x, 2), "half_width_m": round(w, 2), "height_m": round(h, 2)} for x, w, h in tongues]

    def hem_height(x: float) -> float:
        h = -0.05 + 1.15 * hem_noise(x) ** 1.6
        for tx, tw, th in tongues:
            d = abs(x - tx) / tw
            if d < 1.0:
                h = max(h, th * (1.0 - d) ** 1.4)   # a ragged V, narrowing as it climbs
        return h

    side_noise = [layered_noise(rng, 0.0, DROP, (1.6, 0.5), (1.0, 0.4)) for _ in range(2)]

    def side_inset(z: float, side: int) -> float:
        return 0.55 * side_noise[side](z) ** 1.8

    doomed = set()
    for face in bm.faces:
        centre = face.calc_center_median()
        x_rel = centre.x + 0.5 * PATTERN_WIDTH
        if centre.z < hem_height(centre.x):
            doomed.add(face)
        elif x_rel < side_inset(centre.z, 0) or (PATTERN_WIDTH - x_rel) < side_inset(centre.z, 1):
            # Keep the heading intact: the top 0.4 m is taped and tied to the batten.
            if centre.z < DROP - 0.4:
                doomed.add(face)

    # Holes: worn-through patches, mostly in the lower half where the cloth has dragged.
    hole_count = rng.randint(5, 8)
    for _ in range(hole_count):
        cx = rng.uniform(-0.45, 0.45) * PATTERN_WIDTH
        cz = rng.uniform(0.9, DROP * 0.6) if rng.random() < 0.8 else rng.uniform(DROP * 0.6, DROP - 1.2)
        radius = rng.uniform(0.2, 0.6)
        wobble = value_noise(rng, -math.pi, math.pi, 0.9)
        stretch = rng.uniform(0.6, 1.6)
        for face in bm.faces:
            c = face.calc_center_median()
            dx, dz = (c.x - cx) / stretch, (c.z - cz) * stretch
            ang = math.atan2(dz, dx)
            if math.hypot(dx, dz) < radius * (0.65 + 0.7 * wobble(ang)):
                doomed.add(face)
        report["holes"].append({"x_flat_m": round(cx, 2), "z_m": round(cz, 2), "radius_m": round(radius, 2)})

    bmesh.ops.delete(bm, geom=list(doomed), context="FACES")
    # Drop anything the cuts disconnected from the heading so no loose scraps fall away.
    keep_islands_attached_to_top(bm)

    # Tears: rip upward from the hem along grid lines, jogging sideways now and then.
    tear_count = rng.randint(4, 7)
    bm.verts.ensure_lookup_table()
    for _ in range(tear_count):
        col = rng.randint(int(COLS * 0.05), int(COLS * 0.95))
        length = rng.uniform(0.6, 2.8)
        tear_edges = rip_path(bm, col, length, rng)
        if tear_edges:
            opened = open_tear(bm, tear_edges)
            report["tears"].append({"col": col, "length_m": round(length, 2), "edges": len(tear_edges), "opened_verts": opened})
    keep_islands_attached_to_top(bm)
    moved = smooth_cut_edges(bm)
    samples = [hem_height((i / 400 - 0.5) * PATTERN_WIDTH) for i in range(401)]
    report["hem"] = {"min_m": round(min(samples), 2), "max_m": round(max(samples), 2), "mean_m": round(sum(samples) / len(samples), 2)}
    report["sides"] = {"max_inset_m": 0.55}
    report["smoothed_boundary_verts"] = moved
    return report


def smooth_cut_edges(bm, iterations: int = 4, factor: float = 0.5) -> int:
    """Relax the stair-stepped cut boundaries toward smooth ragged outlines.

    Only boundary vertices below the heading move, each by at most 0.45 of a quad, so
    the cut outline loses its grid steps without distorting the fabric. UVs are rebuilt
    from the flat positions afterwards, so the 2D pattern stays exact."""
    limit = 0.45 * QUAD_X
    boundary = [v for v in bm.verts if v.is_boundary and v.co.z < DROP - 1e-6]
    origin = {v: v.co.copy() for v in boundary}
    for _ in range(iterations):
        targets = {}
        for v in boundary:
            nbrs = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nbrs) != 2:
                continue
            avg = (nbrs[0].co + nbrs[1].co) * 0.5
            targets[v] = v.co.lerp(avg, factor)
        for v, target in targets.items():
            delta = target - origin[v]
            if delta.length > limit:
                delta = delta.normalized() * limit
            v.co = origin[v] + delta
            v.co.y = 0.0
    uv_layer = bm.loops.layers.uv.active
    for face in bm.faces:
        for loop in face.loops:
            co = loop.vert.co
            loop[uv_layer].uv = (co.x / PATTERN_WIDTH + 0.5, co.z / DROP)
    return sum(1 for v in boundary if (v.co - origin[v]).length > 1e-6)


def column_x(col: int) -> float:
    return (col / COLS - 0.5) * PATTERN_WIDTH


def rip_path(bm, col: int, length: float, rng: random.Random) -> list:
    """Collect interior edges along grid column `col`, from the hem upward for `length` metres."""
    tol = 0.25 * QUAD_X
    verts_by_key = {}
    for v in bm.verts:
        c = int(round((v.co.x / PATTERN_WIDTH + 0.5) * COLS))
        r = int(round((1.0 - v.co.z / DROP) * ROWS))
        if abs(column_x(c) - v.co.x) < tol:
            verts_by_key[(c, r)] = v
    # Start at the lowest surviving vertex on this column.
    rows_on_col = sorted((r for (c, r) in verts_by_key if c == col), reverse=True)
    if not rows_on_col:
        return []
    r = rows_on_col[0]
    edges = []
    climbed = 0.0
    c = col
    # Climb past the ragged hem until the edge above is interior; the tear starts on
    # the boundary there, so splitting it opens the tear to the hem.
    while r > int(0.1 * ROWS):
        a, b = verts_by_key.get((c, r)), verts_by_key.get((c, r - 1))
        edge = bm.edges.get((a, b)) if a and b else None
        if edge is not None and len(edge.link_faces) == 2:
            break
        r -= 1
    jogged = False
    while climbed < length and r > int(0.1 * ROWS):
        a = verts_by_key.get((c, r))
        # Jog sideways now and then, but never twice running (that would retrace an edge).
        if edges and not jogged and rng.random() < 0.18:
            step = rng.choice((-1, 1))
            b = verts_by_key.get((c + step, r))
            nc, nr = c + step, r
            jogged = True
        else:
            b = verts_by_key.get((c, r - 1))
            nc, nr = c, r - 1
            climbed += QUAD_Z
            jogged = False
        if a is None or b is None:
            break
        edge = bm.edges.get((a, b))
        if edge is None or len(edge.link_faces) != 2 or edge in edges:
            break
        edges.append(edge)
        c, r = nc, nr
    return edges


def open_tear(bm, edges: list) -> int:
    """Split the tear edges into two boundaries and part them a few millimetres, in 3D and in UV."""
    result = bmesh.ops.split_edges(bm, edges=edges)
    # Nudge each side of the split away from the tear line along the local face direction.
    uv_layer = bm.loops.layers.uv.active
    moved = 0
    for edge in result["edges"]:
        if not edge.is_boundary:
            continue
        face = edge.link_faces[0]
        mid = (edge.verts[0].co + edge.verts[1].co) * 0.5
        away = face.calc_center_median() - mid
        away.z = 0.0
        if away.length < 1e-9:
            continue
        away.normalize()
        for v in edge.verts:
            v.co += away * 0.004
            moved += 1
    for face in bm.faces:
        for loop in face.loops:
            co = loop.vert.co
            loop[uv_layer].uv = (co.x / PATTERN_WIDTH + 0.5, co.z / DROP)
    return moved


def keep_islands_attached_to_top(bm) -> None:
    bm.verts.ensure_lookup_table()
    top = [v for v in bm.verts if abs(v.co.z - DROP) < 1e-6]
    seen = set(top)
    stack = list(top)
    while stack:
        v = stack.pop()
        for e in v.link_edges:
            if not e.link_faces:
                continue
            o = e.other_vert(v)
            if o not in seen:
                seen.add(o)
                stack.append(o)
    loose_faces = [f for f in bm.faces if any(v not in seen for v in f.verts)]
    if loose_faces:
        bmesh.ops.delete(bm, geom=loose_faces, context="FACES")
    orphans = [v for v in bm.verts if not v.link_faces]
    if orphans:
        bmesh.ops.delete(bm, geom=orphans, context="VERTS")


def apply_start_pose(bm, pleats: Pleats) -> None:
    """Move every vertex from its flat pattern position to the pleated start pose. UVs keep the flat pattern."""
    for v in bm.verts:
        xt, y = pleats.position(v.co.x)
        v.co = Vector((xt, y, v.co.z))


def write_preview_png(obj) -> str:
    """The flat pattern as it will be cut (UV space), with the seam lines, so the rags can be judged."""
    import numpy as np

    width = 2400
    height = int(width * DROP / PATTERN_WIDTH)
    img = np.ones((height, width, 4), dtype=np.float32)
    img[..., :3] = 0.08
    mesh = obj.data
    uv = mesh.uv_layers.active.data

    def px(p):
        return p.x * (width - 1), (1.0 - p.y) * (height - 1)

    for poly in mesh.polygons:
        pts = [px(uv[li].uv) for li in poly.loop_indices]
        for i in range(1, len(pts) - 1):   # fan-triangulate and fill each triangle exactly
            (ax, ay), (bx, by), (cx, cy) = pts[0], pts[i], pts[i + 1]
            x0, x1 = int(min(ax, bx, cx)), int(math.ceil(max(ax, bx, cx)))
            y0, y1 = int(min(ay, by, cy)), int(math.ceil(max(ay, by, cy)))
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            if abs(d) < 1e-12:
                continue
            w0 = ((bx - gx) * (cy - gy) - (by - gy) * (cx - gx)) / d
            w1 = ((cx - gx) * (ay - gy) - (cy - gy) * (ax - gx)) / d
            inside = (w0 >= -1e-3) & (w1 >= -1e-3) & (1.0 - w0 - w1 >= -1e-3)
            region = img[y0:y1 + 1, x0:x1 + 1, :3]
            region[inside] = (0.55, 0.14, 0.12)
    # Seam lines every bolt width, only where there is fabric.
    for k in range(1, int(PATTERN_WIDTH / SEAM_WIDTH_M) + 1):
        x = int(k * SEAM_WIDTH_M / PATTERN_WIDTH * (width - 1))
        col = img[:, x, :3]
        col[col[:, 0] > 0.3] = (0.8, 0.45, 0.4)
    # Every cut edge (hem, sides, holes, tears) in pale yellow.
    loop_uv = {}
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            loop_uv[mesh.loops[li].vertex_index] = uv[li].uv
    edge_faces = {}
    for poly in mesh.polygons:
        for ek in poly.edge_keys:
            edge_faces[ek] = edge_faces.get(ek, 0) + 1
    for (a, b), n in edge_faces.items():
        if n != 1:
            continue
        (ax, ay), (bx, by) = px(loop_uv[a]), px(loop_uv[b])
        steps = int(max(abs(bx - ax), abs(by - ay))) + 2
        xs = np.clip(np.round(np.linspace(ax, bx, steps)).astype(int), 0, width - 1)
        ys = np.clip(np.round(np.linspace(ay, by, steps)).astype(int), 0, height - 1)
        img[ys, xs, :3] = (0.95, 0.85, 0.45)
    image = bpy.data.images.new("PatternPreview", width=width, height=height, alpha=True)
    image.pixels.foreach_set(np.flipud(img).ravel())
    image.filepath_raw = str(PREVIEW_OUTPUT)
    image.file_format = "PNG"
    image.save()
    return str(PREVIEW_OUTPUT)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    rng = random.Random(SEED)
    bm = build_grid()
    rag_report = cut_rags(bm, rng) if RAGGED else {}
    pleats = Pleats(random.Random(SEED + 1))
    apply_start_pose(bm, pleats)

    mesh = bpy.data.meshes.new(STEM)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"SM_{STEM}", mesh)
    scene.collection.objects.link(obj)

    # Material slot name the Unreal side assigns its cloth material to.
    mat = bpy.data.materials.new("M_CurtainChaos")
    obj.data.materials.append(mat)

    mesh.validate()
    top_indices = [v.index for v in mesh.vertices if abs(v.co.z - DROP) < 1e-6]

    preview = write_preview_png(obj)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=str(FBX_OUTPUT),
        use_selection=True,
        object_types={"MESH"},
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        use_space_transform=True,
        bake_space_transform=False,
        axis_forward="-Y",
        axis_up="Z",
        use_mesh_modifiers=False,
        mesh_smooth_type="FACE",
        use_tspace=False,
        add_leaf_bones=False,
        bake_anim=False,
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT))

    sidecar = {
        "stem": STEM,
        "fbx": str(FBX_OUTPUT),
        "blend": str(BLEND_OUTPUT),
        "pattern_preview": preview,
        "seed": SEED,
        "ragged": RAGGED,
        "track_width_m": TRACK_WIDTH,
        "drop_m": DROP,
        "fullness": FULLNESS,
        "pattern_width_m": PATTERN_WIDTH,
        "seam_width_m": SEAM_WIDTH_M,
        "quad_x_m": QUAD_X,
        "quad_z_m": QUAD_Z,
        "grid_cols_rows": [COLS, ROWS],
        "vertices": len(mesh.vertices),
        "faces": len(mesh.polygons),
        # Chaos Static Mesh Import: UVChannel 0, UVScale in cm.
        "uv_scale_cm": [PATTERN_WIDTH * 100.0, DROP * 100.0],
        "heading_vertex_indices": top_indices,
        "heading_vertex_count": len(top_indices),
        "rags": rag_report,
    }
    SIDECAR_OUTPUT.write_text(json.dumps(sidecar, indent=1), encoding="utf-8")
    print(
        f"CURTAIN_CHAOS_PATTERN_SUCCESS|stem={STEM}|vertices={len(mesh.vertices)}|faces={len(mesh.polygons)}"
        f"|heading={len(top_indices)}|fbx={FBX_OUTPUT}"
    )


if __name__ == "__main__":
    main()
