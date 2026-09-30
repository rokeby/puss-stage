"""Bake a TRAVELLER (side-opening) stage curtain with Blender cloth and MEASURE it (headless Blender 4.4).

30 Sep, Gary (via the Conductor): "a version that doesn't fall, but like a normal curtain, opens slowly to the sides
(so this would be in two left right pieces)", sized for the Opening line. For every bake: "The main thing I need to get
right is the first part of the bake - a still acceptable curtain that can be extended in its stillness for as long as
I need". So this uses the SAME fabric as the Opening drape: mass, bending, damping, fullness, solver, colliders,
materials, renders and Alembic export all come from Scripts/bake_curtain_drop.py, which is imported, not copied. It
gets the same long settle and stillness metric, then the opening, then a second settle, so the OPEN stacks can be
held too.

THE HEADING IS A RIPPLEFOLD TRACK. Each half hangs from carriers at its pleat nodes, one every half fold wavelength of
track. Between two carriers the heading bows alternately upstage and downstage, carrying a fixed length of fabric.
  - The bow is a stadium: a semicircle whose diameter is the carrier spacing, plus straight flanks. When there is too
    little fabric for a semicircle, it is a circular arc instead.
  - A row of semicircles is the smooth S-wave of a closed ripplefold. Bunched carriers give a comb of U-loops, whose
    flanks stay one carrier pitch apart, so the stack never pinches the fabric tighter than the self-collision
    distance.
  - Opening moves the lead carrier offstage with a cosine ease. Each carrier stays put until the compressed stack
    behind the lead reaches it (the compression front), then travels with it at STACK_PITCH spacing, as carriers on
    a real track bunch from the leading edge.
  - The fabric between two carriers is fixed, so the stack's depth follows from the pleat. It is not chosen.

  closed: each half covers its side of the TRAVELLER_TRACK_M track, and the halves overlap by OVERLAP at the centre.
          They ride on tracks TRACK_GAP apart, the left half downstage. A flat LEAD-wide leading panel carries the
          overlap.
  open:   each half is a stack n x STACK_PITCH + LEAD wide at its own track end. The clear opening between the leading
          edges is TRACK - 2 x that.

The heading vertices are pinned KINEMATICALLY (weight 1.0), so the heading follows the carriers exactly and nothing
is released. Its path is animated by shape keys relative to the flat basis, which is the cloth's rest shape:
  - "Gathered" is the closed pose, gathered from the flat sheet over GATHER_FRAMES, as on the drape.
  - There is one "Open_###" key every KEY_STEP frames of the opening. The keys are cross-faded LINEARLY, so the
    heading moves piecewise-linearly between exact poses. The weights are checked to sum to 1 at every frame and half
    frame.

THE FLAT SHEETS are laid out from each half's LEADING edge outward: the left half to the left, the right half to the
right. The gather pulls each outer end in, and the two halves never cross. Only their flat lead panels overlap,
TRACK_GAP apart.

Env, besides bake_curtain_drop.py's:
  RELEASE_FRAME            the frame the opening starts
  TRAVELLER_OPEN_FRAMES    360 (12 s)
  TRAVELLER_KEY_STEP       2
  TRAVELLER_TRACK_M        17.77, as the drape
  TRAVELLER_OVERLAP_M      0.4
  TRAVELLER_LEAD_M         0.4
  TRAVELLER_TRACK_GAP_M    0.15
  TRAVELLER_STACK_PITCH_M  0.07
  END_PROBE                60 frames of end stillness
Outputs are named as the drop bake's: <DROP_ID>.json and .abc; <DROP_ID>_{stalls,hangstalls,midstalls,front,hangfront,34,side}.png;
and clips in <DROP_ID>_clip_{stalls,front}/. The stalls view is the Opening's stalls camera.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(os.environ.get("PUSS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
os.environ["RELEASE_METHOD"] = "kinematic"       # finish_cloth: pin stiffness 1 and no release keys; nothing falls
_spec = importlib.util.spec_from_file_location("curtain_drop", ROOT / "Scripts" / "bake_curtain_drop.py")
drop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drop)                   # reads the shared env (fabric, solver, colliders); its main() does not run
pattern = drop.pattern

OPEN_START = drop.RELEASE_FRAME
KEY_STEP = int(os.environ.get("TRAVELLER_KEY_STEP", "2"))
OPEN_FRAMES = int(os.environ.get("TRAVELLER_OPEN_FRAMES", "360"))
OPEN_FRAMES += (-OPEN_FRAMES) % KEY_STEP
OPEN_END = OPEN_START + OPEN_FRAMES
TRACK = float(os.environ.get("TRAVELLER_TRACK_M", str(pattern.TRACK_WIDTH)))
OVERLAP = float(os.environ.get("TRAVELLER_OVERLAP_M", "0.4"))
LEAD = float(os.environ.get("TRAVELLER_LEAD_M", "0.4"))
GAP = float(os.environ.get("TRAVELLER_TRACK_GAP_M", "0.15"))
PITCH = float(os.environ.get("TRAVELLER_STACK_PITCH_M", "0.07"))
END_PROBE = int(os.environ.get("END_PROBE", "60"))
# 30 Sep, Gary on the first smoke: "it should begin in a dignified and stable still set of nicely sculptural pleats"
# (with photos of a ripplefold: round waves running unbroken from heading to floor). A flat sheet gathered at the
# heading can only settle into a FLARE, and takes seconds of swinging to get there. "pleated" (default) builds every
# row in the closed ripplefold, which is then also the cloth's rest shape, as fabric that has hung in its folds holds
# them. So it starts at rest, and the settle only takes up gravity's stretch. "gather" is the first version.
START = os.environ.get("TRAVELLER_START", "pleated")
# DYNAMIC REST (30 Sep, final5_traveller). A pleated rest shape made the STACK restless: fabric that remembers the closed
# S-wave keeps pushing to re-expand against its bunched carriers. It measured 20-24 mm/frame at every height of both
# stacks, even at the heading, and never settled. The Open_ keys already carry the WHOLE curtain in each carrier pose,
# so with Dynamic Mesh the cloth's rest shape follows the carriers: the stack becomes the fabric's rest state, as a
# ripplefold's folds stack by design. Only the pleated start supports this (the gather start's input rows are flat).
DYNAMIC_REST = os.environ.get("TRAVELLER_DYNAMIC_REST", "0") == "1"
# SETTLE DAMPING (30 Sep). final5's open stacks kept moving at 20-24 mm/frame for 10 s. A stack is a dense self-colliding
# bundle, and the opening leaves it swinging. Air damping is multiplied by this over the second after the opening
# ENDS, so the opening's motion (Gary: "the motion we see when it moves is good") is untouched. Damping only removes
# energy; the 28 Sep blow-up was a BENDING damping step mid-collapse. 1 = off.
SETTLE_AIR_DAMPING = float(os.environ.get("TRAVELLER_SETTLE_AIR_DAMPING", "1"))
PLEATED = 0.5 * TRACK + 0.5 * OVERLAP - LEAD     # pleated track per half, outer end to the lead carrier
N = max(1, round(PLEATED / (0.5 * pattern.FOLD_WAVELENGTH)))
S_C = PLEATED / N                                 # closed carrier spacing (half a fold wavelength)
POST_INNER_X = 9.5                                # Rig's posts, inner faces (Docs/StageFrontColliders_2026-09-28.json)
# The Opening's stalls camera (UE (-1400, 0, 150), pitch +14, 15 mm on Super 35 = 24.89 mm wide) in Blender terms:
# 14 m downstage, 1.5 m up, and the same horizontal field on Blender's 36 mm sensor. The audience's view of the bake.
STALLS_LOC, STALLS_ROT, STALLS_LENS = Vector((0.0, -14.0, 1.5)), (math.radians(90 + 14), 0.0, 0.0), 15.0 * 36.0 / 24.89


def check_config():
    problems = []
    if OPEN_END >= drop.FRAMES:
        problems.append(f"the opening ends at {OPEN_END}, not before FRAMES={drop.FRAMES}")
    if drop.SHOW_START and not drop.SHOW_START < OPEN_START:
        problems.append("SHOW_START must come before the opening (RELEASE_FRAME)")
    if PITCH >= S_C:
        problems.append(f"stack pitch {PITCH} m is not below the closed carrier spacing {S_C:.3f} m")
    if LEAD < OVERLAP:
        problems.append(f"the lead panel ({LEAD} m) must cover the overlap ({OVERLAP} m), or the pleats of one half cross the other")
    if PITCH < 2.0 * drop.SELF_DIST:
        problems.append(f"stack pitch {PITCH} m is under twice the self-collision distance {drop.SELF_DIST} m")
    if problems:
        raise SystemExit("TRAVELLER_CONFIG_REFUSED|" + "; ".join(problems))


def arc_half_angle(r):
    """Half-angle a of the circular arc whose length is r x its chord: sin(a)/a = 1/r, 1 < r < pi/2."""
    lo, hi = 1e-9, 0.5 * math.pi
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if math.sin(mid) / mid > 1.0 / r:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def bow(sigma, fabric, chord):
    """Along-track offset and depth of the point `sigma` metres of fabric along a bow of `fabric` metres on `chord`."""
    r = fabric / chord
    if r >= 0.5 * math.pi:                        # a stadium: straight flank, semicircle, straight flank
        rad = 0.5 * chord
        flank = 0.5 * (fabric - math.pi * rad)
        theta = np.clip((sigma - flank) / rad, 0.0, math.pi)
        x = np.where(sigma <= flank, 0.0, np.where(sigma >= flank + math.pi * rad, chord, rad - rad * np.cos(theta)))
        y = np.where(sigma <= flank, sigma, np.where(sigma >= flank + math.pi * rad, fabric - sigma, flank + rad * np.sin(theta)))
        return x, y
    if r <= 1.0 + 1e-9:
        return sigma.copy(), np.zeros_like(sigma)
    a = arc_half_angle(r)                         # a circular arc through both carriers
    rho = fabric / (2.0 * a)
    psi = 0.5 * math.pi + a - sigma / rho
    return 0.5 * chord + rho * np.cos(psi), -rho * math.cos(a) + rho * np.sin(psi)


class Half:
    """One half of the traveller: side -1 = stage left of centre (downstage track), +1 = right (upstage track)."""

    def __init__(self, side, rng):
        self.side = side
        self.track_y = 0.5 * GAP * side
        # Fabric per carrier interval: fullness on average, with the pleat-to-pleat variation of the drape's gains
        # (0.6-1.25) applied to the EXCESS fabric, so every bow keeps at least its chord of fabric.
        gains = np.array([rng.uniform(0.6, 1.25) for _ in range(N)])
        self.fabric = S_C * (1.0 + (pattern.FULLNESS - 1.0) * gains / gains.mean())
        self.nodes = np.concatenate(([0.0], np.cumsum(self.fabric)))     # carriers' distance along the flat fabric
        self.width = self.nodes[-1] + LEAD
        self.cols = max(2, int(round(self.width / pattern.QUAD_X)))
        self.w = np.linspace(0.0, self.width, self.cols + 1)             # columns, from the outer end to the lead edge
        self.sign = np.array([1.0 if k % 2 == 0 else -1.0 for k in range(N)])
        self.interval = np.clip(np.searchsorted(self.nodes, self.w, side="right") - 1, 0, N - 1)
        self.lead = self.w >= self.nodes[-1] - 1e-12

    def carriers(self, e):
        """Carrier distances from the outer track end at opening fraction e: the compression front."""
        d_lead = N * S_C + e * N * (PITCH - S_C)
        k = np.arange(N + 1)
        return np.minimum(k * S_C, d_lead - (N - k) * PITCH)

    def pose(self, e):
        dk = self.carriers(e)
        d = np.empty_like(self.w)
        y = np.zeros_like(self.w)
        d[self.lead] = dk[-1] + (self.w[self.lead] - self.nodes[-1])
        for k in range(N):
            m = (self.interval == k) & ~self.lead
            if m.any():
                bx, by = bow(self.w[m] - self.nodes[k], self.fabric[k], dk[k + 1] - dk[k])
                d[m] = dk[k] + bx
                y[m] = self.sign[k] * by
        return self.world_x(d), self.track_y + y

    def world_x(self, d):
        return self.side * (0.5 * TRACK - d)

    def flat_x(self):
        return self.world_x(0.5 * TRACK + 0.5 * OVERLAP - (self.width - self.w))


def coords_for(halves, e, zs):
    parts = []
    for h in halves:
        x, y = h.pose(e)
        parts.append(np.stack([np.tile(x, len(zs)), np.tile(y, len(zs)), np.repeat(zs, h.cols + 1)], axis=1))
    return np.concatenate(parts).astype(np.float32).ravel()


def ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * u)


def build_traveller():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, drop.FRAMES
    halves = [Half(-1, random.Random(pattern.SEED + 11)), Half(+1, random.Random(pattern.SEED + 12))]
    zs = np.array([pattern.DROP * (1.0 - r / pattern.ROWS) for r in range(pattern.ROWS + 1)])
    total_w = sum(h.width for h in halves)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    top, hem, spans = [], [], []
    for h in halves:
        first = len(bm.verts)
        if START == "pleated":                # every row in the closed ripplefold: columns from heading to hem
            xs, ys = h.pose(0.0)
        else:                                 # "gather": the flat sheet, laid out from the leading edge outward
            xs, ys = h.flat_x(), np.full(h.cols + 1, h.track_y)
        grid = [[bm.verts.new((xs[c], ys[c], zs[r])) for c in range(h.cols + 1)] for r in range(pattern.ROWS + 1)]
        # One pattern across both halves (outer left edge u = 0, outer right edge u = 1), so texel density matches the drape.
        u = h.w / total_w if h.side < 0 else 1.0 - h.w / total_w
        for r in range(pattern.ROWS):
            for c in range(h.cols):
                quad = (grid[r][c], grid[r + 1][c], grid[r + 1][c + 1], grid[r][c + 1])
                cols = (c, c, c + 1, c + 1)
                if h.side > 0:                    # x runs right-to-left on this half: keep the front face downstage
                    quad, cols = quad[::-1], cols[::-1]
                face = bm.faces.new(quad)
                face.smooth = True
                for loop, cc in zip(face.loops, cols):
                    loop[uv].uv = (u[cc], loop.vert.co.z / pattern.DROP)
        bm.verts.index_update()
        top += [v.index for v in grid[0]]
        hem += [v.index for v in grid[-1]]
        spans.append((first, len(bm.verts)))
    mesh = bpy.data.meshes.new(f"Curtain_{drop.DROP_ID}")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"Curtain_{drop.DROP_ID}", mesh)
    scene.collection.objects.link(obj)
    obj.location.z = drop.LIFT_M
    obj.shape_key_add(name="Basis", from_mix=False)                      # the cloth's rest shape (pleated or flat)
    prefs = bpy.context.preferences.edit
    if START == "gather":
        gathered = obj.shape_key_add(name="Gathered", from_mix=False)
        gathered.data.foreach_set("co", coords_for(halves, 0.0, zs))
        gathered.value = 0.0
        gathered.keyframe_insert("value", frame=1)
        gathered.value = 1.0
        gathered.keyframe_insert("value", frame=1 + drop.GATHER_FRAMES)
        prefs.keyframe_new_interpolation_type = "LINEAR"                # the open cross-fades must sum to exactly 1
        gathered.keyframe_insert("value", frame=OPEN_START)
        gathered.value = 0.0
        gathered.keyframe_insert("value", frame=OPEN_START + KEY_STEP)
    prefs.keyframe_new_interpolation_type = "LINEAR"
    steps = OPEN_FRAMES // KEY_STEP
    for j in range(1, steps + 1):
        kb = obj.shape_key_add(name=f"Open_{j:03d}", from_mix=False)
        kb.data.foreach_set("co", coords_for(halves, ease(j / steps), zs))
        f = OPEN_START + j * KEY_STEP
        kb.value = 0.0
        kb.keyframe_insert("value", frame=f - KEY_STEP)
        kb.value = 1.0
        kb.keyframe_insert("value", frame=f)
        if j < steps:
            kb.value = 0.0
            kb.keyframe_insert("value", frame=f + KEY_STEP)
    pin = obj.vertex_groups.new(name="Pin")
    pin.add(top, 1.0, "REPLACE")                                         # kinematic: the heading rides the carriers
    guided = []
    if drop.HEM_GUIDE_WEIGHT > 0:
        # The HEM GUIDE (see bake_curtain_drop.py): the lowest rows spring toward the columns under their heading pleats
        # while the curtain hangs still, and let go as the opening starts, so the flat cloth moves as freely as the smoke
        # Gary liked ("the motion we see when it moves is good"). The heading (weight 1.0) is kinematic and ignores pin
        # stiffness, so keying the stiffness to 0 releases only the guide.
        for (first, last), h in zip(spans, halves):
            per_row = h.cols + 1
            guided += list(range(last - drop.HEM_GUIDE_ROWS * per_row, last))
        pin.add(guided, drop.HEM_GUIDE_WEIGHT, "REPLACE")
    cloth = obj.modifiers.new("Cloth", "CLOTH")
    if DYNAMIC_REST:
        if START != "pleated":
            raise SystemExit("TRAVELLER_CONFIG_REFUSED|dynamic rest needs the pleated start")
        cloth.settings.use_dynamic_mesh = True
    scene, obj, top, floor = drop.finish_cloth(scene, obj, mesh, top, cloth)
    if SETTLE_AIR_DAMPING != 1.0:
        cs = obj.modifiers["Cloth"].settings
        base = cs.air_damping
        cs.keyframe_insert("air_damping", frame=OPEN_END)
        cs.air_damping = base * SETTLE_AIR_DAMPING
        cs.keyframe_insert("air_damping", frame=OPEN_END + 30)
        cs.air_damping = base
    if guided:
        s = obj.modifiers["Cloth"].settings
        s.pin_stiffness = drop.PIN_STIFFNESS
        s.keyframe_insert("pin_stiffness", frame=OPEN_START - 1)
        s.pin_stiffness = 0.0
        s.keyframe_insert("pin_stiffness", frame=OPEN_START)
        s.pin_stiffness = drop.PIN_STIFFNESS
    scene["hem_guided"] = len(guided)
    return scene, obj, top, hem, floor, halves, spans


def key_weight_error(obj):
    """The heading must always be a CONVEX blend of at most two exact poses. The closed pose's weight is the Gathered
    key ("gather") or the basis' implicit 1 - sum ("pleated"). Returns the worst violation over the opening, at whole
    and half frames: a weight outside [0, 1], a total off 1, or more than two poses in play."""
    action = obj.data.shape_keys.animation_data.action
    opens = [fc for fc in action.fcurves if "Open_" in fc.data_path]
    gathered = [fc for fc in action.fcurves if "Gathered" in fc.data_path]
    worst = 0.0
    for f in range(OPEN_START - 2, OPEN_END + 3):
        for sub in (0.0, 0.5):
            w = [fc.evaluate(f + sub) for fc in opens]
            closed = gathered[0].evaluate(f + sub) if gathered else 1.0 - sum(w)
            allw = [closed] + w
            worst = max(worst, abs(sum(allw) - 1.0), max(0.0, -min(allw)), max(0.0, max(allw) - 1.0),
                        1.0 if sum(1 for x in allw if abs(x) > 1e-6) > 2 else 0.0)
    return worst


def coords_np(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    n = len(ev.data.vertices)
    a = np.empty(n * 3, dtype=np.float32)
    ev.data.vertices.foreach_get("co", a)
    m = np.array(ev.matrix_world)
    return a.reshape(n, 3).astype(np.float64) @ m[:3, :3].T + m[:3, 3]


def pcts(v, lo=0.02, hi=0.98):
    return [round(float(np.quantile(v, lo)), 3), round(float(np.quantile(v, hi)), 3)]


def traveller_hang_profile(co, spans, halves):
    """The Conductor's hang test for the closed traveller, per half: its OUTER edge's spread from heading to hem (the
    flare, converted to the whole track), and the folds kept at 75/50/25% of the height against the heading's."""
    out, spread, ok = {"halves": []}, 0.0, True
    for (first, last), h in zip(spans, halves):
        a = co[first:last].reshape(pattern.ROWS + 1, h.cols + 1, 3)
        head, hemrow = a[0], a[-1]
        outer = float(head[:, 0].min() - hemrow[:, 0].min()) if h.side < 0 else float(hemrow[:, 0].max() - head[:, 0].max())
        spread += max(0.0, outer)
        rows = {label: drop.row_folds(a[int(round(frac * pattern.ROWS))])
                for label, frac in (("heading", 0.0), ("75%", 0.25), ("50%", 0.5), ("25%", 0.75), ("hem", 1.0))}
        for label in ("75%", "50%", "25%"):
            r, hd = rows[label], rows["heading"]
            r["count_kept"] = round(r["folds"] / hd["folds"], 2) if hd["folds"] else None
            r["depth_kept"] = round(r["mean_depth_m"] / hd["mean_depth_m"], 2) if hd["mean_depth_m"] else None
            ok = ok and (r["count_kept"] or 0) >= drop.FOLD_COUNT_MIN and (r["depth_kept"] or 0) >= drop.FOLD_DEPTH_MIN
        out["halves"].append({"side": h.side, "outer_edge_spread_m": round(outer, 3), "rows": rows})
    out["flare_ratio"] = round((TRACK + spread) / TRACK, 3)
    out["pass"] = bool(ok and out["flare_ratio"] <= drop.FLARE_MAX)
    out["targets"] = {"flare_max": drop.FLARE_MAX, "fold_count_kept_min": drop.FOLD_COUNT_MIN,
                      "fold_depth_kept_min": drop.FOLD_DEPTH_MIN}
    return out


def traveller_metrics(co, spans, top, hem):
    left, right = co[spans[0][0]:spans[0][1]], co[spans[1][0]:spans[1][1]]
    head = co[top]
    head_l, head_r = head[head[:, 0] < 0.0], head[head[:, 0] >= 0.0]
    out = {"clear_opening_all_m": round(float(right[:, 0].min() - left[:, 0].max()), 3),
           "clear_opening_heading_m": round(float(head_r[:, 0].min() - head_l[:, 0].max()), 3) if len(head_l) and len(head_r) else None,
           "hem_min_z_m": round(float(co[hem][:, 2].min()), 3), "top_max_z_m": round(float(co[:, 2].max()), 3)}
    for tag, part in (("left", left), ("right", right)):
        out[tag] = {"x_m": [round(float(part[:, 0].min()), 3), round(float(part[:, 0].max()), 3)],
                    "width_m": round(float(part[:, 0].max() - part[:, 0].min()), 3),
                    "y_p2_p98_m": pcts(part[:, 1]), "depth_p2_p98_m": round(float(np.diff(pcts(part[:, 1]))[0]), 3),
                    "y_m": [round(float(part[:, 1].min()), 3), round(float(part[:, 1].max()), 3)]}
    return out


def main():
    check_config()
    drop.OUT_DIR.mkdir(parents=True, exist_ok=True)
    t_build = time.perf_counter()
    scene, obj, top, hem, floor, halves, spans = build_traveller()
    stack_w = N * PITCH + LEAD
    report = {"id": drop.DROP_ID, "kind": "traveller", "colliders": drop.COLLIDERS, "posts_from": drop.POSTS_FROM,
              "show_start": drop.SHOW_START, "open_start": OPEN_START, "open_frames": OPEN_FRAMES, "open_end": OPEN_END,
              "frames": drop.FRAMES, "gather_frames": drop.GATHER_FRAMES, "key_step": KEY_STEP,
              "track_m": TRACK, "overlap_m": OVERLAP, "lead_m": LEAD, "track_gap_m": GAP, "stack_pitch_m": PITCH,
              "carrier_intervals_per_half": N, "closed_carrier_spacing_m": round(S_C, 4),
              "fold_wavelength_m": pattern.FOLD_WAVELENGTH, "fullness": pattern.FULLNESS,
              "fabric_width_per_half_m": [round(float(h.width), 3) for h in halves],
              "design_stack_width_per_side_m": round(stack_w, 3),
              "design_clear_opening_m": round(TRACK - 2.0 * stack_w, 3),
              "design_stack_depth_m": round(float(max(0.5 * (h.fabric.max() - 0.5 * math.pi * PITCH) + 0.5 * PITCH
                                                      for h in halves)), 3),
              "quad_m": round(pattern.QUAD_X, 3), "vertices": len(obj.data.vertices), "lift_m": drop.LIFT_M,
              "bend": drop.BEND, "tension": drop.TENSION, "compression": drop.COMPRESSION, "self_dist_m": drop.SELF_DIST,
              "floor_friction": drop.FLOOR_FRICTION, "self_friction": drop.SELF_FRICTION, "air_damping": drop.AIR_DAMPING,
              "quality": drop.QUALITY, "collision_quality": drop.COLLISION_QUALITY,
              "mass_per_vertex": round(obj.modifiers["Cloth"].settings.mass, 4),
              "air_damping_applied": round(obj.modifiers["Cloth"].settings.air_damping, 4),
              "pin": "kinematic (weight 1.0)", "start": START, "dynamic_rest": DYNAMIC_REST,
              "settle_air_damping": SETTLE_AIR_DAMPING, "key_weight_max_error": None,
              "hem_guide_weight": drop.HEM_GUIDE_WEIGHT, "hem_guide_rows": drop.HEM_GUIDE_ROWS, "hem_guided_vertices": None,
              "hang_profile": None,
              "build_seconds": None, "frame_seconds": [], "move_mm": [], "hem_min_z": [], "checkpoints": {}}
    report["key_weight_max_error"] = key_weight_error(obj)
    report["hem_guided_vertices"] = scene.get("hem_guided")
    if report["key_weight_max_error"] > 1e-4:
        raise SystemExit(f"TRAVELLER_KEY_WEIGHTS_BAD|{report['key_weight_max_error']}")
    report["build_seconds"] = round(time.perf_counter() - t_build, 1)
    print(f"CURTAIN_TRAVELLER_BUILT|{drop.DROP_ID}|verts={report['vertices']}|n={N}|stack={stack_w:.2f}|"
          f"clear={TRACK - 2 * stack_w:.2f}|keys_err={report['key_weight_max_error']:.2e}", flush=True)
    probe_from = max(2, (drop.SHOW_START or OPEN_START) - drop.SETTLE_PROBE)
    prev, extents = None, []
    for f in range(1, drop.FRAMES + 1):
        t0 = time.perf_counter()
        scene.frame_set(f)
        report["frame_seconds"].append(round(time.perf_counter() - t0, 3))
        if f < probe_from - 1:
            continue
        co = coords_np(obj)
        if prev is not None:
            # STILLNESS: the largest single-vertex move from the previous frame (mm per frame), every frame from the probe
            # on, so the pre-open hold, the opening and the end hold are all read from one series.
            report["move_mm"].append([f, round(float(np.sqrt(((co - prev) ** 2).sum(axis=1)).max()) * 1000.0, 2)])
        prev = co
        if f >= (drop.SHOW_START or 1):
            report["hem_min_z"].append([f, round(float(co[hem][:, 2].min()), 4)])
            band = co[np.abs(co[:, 1]) <= 0.2]                           # the portal band, UE X -20..+20 cm
            extents.append([f, float(co[:, 1].min()), float(co[:, 1].max()), float(co[:, 0].min()), float(co[:, 0].max()),
                            float(np.abs(band[:, 0]).max()) if len(band) else 0.0])
        if f == OPEN_START - 1:
            report["hang_profile"] = traveller_hang_profile(co, spans, halves)
        if f in (OPEN_START - 1, OPEN_START + OPEN_FRAMES // 2, OPEN_END, drop.FRAMES):
            cp = drop.metrics(drop.world_coords(obj), top)
            cp["traveller"] = traveller_metrics(co, spans, top, hem)
            report["checkpoints"][f] = cp
        if f % 60 == 0:
            print(f"CURTAIN_TRAVELLER_FRAME|{f}/{drop.FRAMES}|{report['frame_seconds'][-1]}s", flush=True)
    moves = report["move_mm"]
    window = [m for f_, m in moves if (drop.SHOW_START or OPEN_START) <= f_ < OPEN_START]
    end = [m for f_, m in moves if f_ > drop.FRAMES - END_PROBE]
    opening = [m for f_, m in moves if OPEN_START <= f_ <= OPEN_END]
    report["still_window_max_mm"] = max(window) if window else None
    report["still_window_mean_mm"] = round(sum(window) / len(window), 2) if window else None
    report["end_still_max_mm"] = max(end) if end else None
    report["end_still_mean_mm"] = round(sum(end) / len(end), 2) if end else None
    report["opening_max_move_mm"] = max(opening) if opening else None
    pre = [(f_, m) for f_, m in moves if f_ < OPEN_START]
    last_bad = max((f_ for f_, m in pre if m >= 2.0), default=None)
    start_s = (drop.GATHER_FRAMES + 1) if START == "gather" else 1
    report["settle_to_2mm_s"] = round((((last_bad + 1) if last_bad is not None else pre[0][0]) - start_s) / 30.0, 1) if pre else None
    report["settle_to_2mm_reached"] = bool(pre) and (last_bad is None or last_bad < pre[-1][0])
    if extents:
        def worst(col, fn):
            row = fn(extents, key=lambda r: r[col])
            phase = "hold" if row[0] < OPEN_START else ("opening" if row[0] <= OPEN_END else "open")
            return {"value_m": round(row[col], 3), "frame": row[0], "phase": phase}
        report["rig_limits"] = {"downstage_min_y": worst(1, min), "upstage_max_y": worst(2, max),
                                "x_min": worst(3, min), "x_max": worst(4, max), "portal_abs_x_max": worst(5, max),
                                "post_clearance_min_m": round(POST_INNER_X - max(r[5] for r in extents), 3),
                                "unreal_cm": {"X_min": round(100 * min(r[1] for r in extents)),
                                              "X_max": round(100 * max(r[2] for r in extents)),
                                              "Y_min": round(100 * min(r[3] for r in extents)),
                                              "Y_max": round(100 * max(r[4] for r in extents))}}
    report["hem_floor_contact_frames"] = sum(1 for _, z in report["hem_min_z"] if z < 0.02)
    report["solve_seconds_total"] = round(sum(report["frame_seconds"]), 1)
    final = report["checkpoints"][drop.FRAMES]
    # Renders: the open state FIRST, while the sim sits on its last frame; stepping back is a cache read, and comes last.
    drop.render(obj, floor, "34", Vector((-13.0, -19.0, 11.0)), None)
    drop.render(obj, floor, "side", Vector((-30.0, 0.0, 5.0)), (math.radians(90), 0.0, math.radians(-90)), ortho=12.0)
    camfront = drop.render(obj, floor, "front", Vector((0.0, -40.0, 5.0)), (math.radians(90), 0.0, 0.0), ortho=24.0)
    camstalls = drop.render(obj, floor, "stalls", STALLS_LOC, STALLS_ROT)
    camstalls.data.lens = STALLS_LENS
    bpy.context.scene.render.filepath = str(drop.OUT_DIR / f"{drop.DROP_ID}_stalls.png")
    bpy.ops.render.render(write_still=True)                             # again, at the stalls lens
    scene.camera = camstalls
    for f, name in ((OPEN_START + OPEN_FRAMES // 2, "midstalls"), (OPEN_START - 1, "hangstalls")):
        scene.frame_set(f)
        scene.render.filepath = str(drop.OUT_DIR / f"{drop.DROP_ID}_{name}.png")
        bpy.ops.render.render(write_still=True)
    drop.render(obj, floor, "hangfront", Vector((0.0, -40.0, 5.0)), (math.radians(90), 0.0, 0.0), ortho=24.0)
    if drop.CLIP_STEP > 0:
        for tag, cam in (("stalls", camstalls), ("front", camfront)):
            clip_dir = drop.OUT_DIR / f"{drop.DROP_ID}_clip_{tag}"
            clip_dir.mkdir(parents=True, exist_ok=True)
            scene.camera = cam
            drop.set_side_hide(False)
            for n, f in enumerate(range(drop.CLIP_START, drop.FRAMES + 1, drop.CLIP_STEP)):
                scene.frame_set(f)
                scene.render.filepath = str(clip_dir / f"f{n:04d}.png")
                bpy.ops.render.render(write_still=True)
    if drop.EXPORT_ABC:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        # VIEWPORT evaluation: the simulated cloth only (the render-only subdivision and solidify are not exported).
        bpy.ops.wm.alembic_export(filepath=str(drop.OUT_DIR / f"{drop.DROP_ID}.abc"), start=drop.ABC_START, end=drop.FRAMES,
                                  selected=True, uvs=True, normals=True, face_sets=True, apply_subdiv=False,
                                  evaluation_mode="VIEWPORT")
    (drop.OUT_DIR / f"{drop.DROP_ID}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    t = final["traveller"]
    print(f"CURTAIN_TRAVELLER_BAKE_DONE|{drop.DROP_ID}|still_window_max_mm={report['still_window_max_mm']}"
          f"|end_still_max_mm={report['end_still_max_mm']}|clear_opening_heading_m={t['clear_opening_heading_m']}"
          f"|stack_widths_m={t['left']['width_m']},{t['right']['width_m']}|solve_s={report['solve_seconds_total']}", flush=True)


if __name__ == "__main__":
    main()
