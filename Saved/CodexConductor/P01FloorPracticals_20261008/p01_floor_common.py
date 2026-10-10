"""P01 FLOOR practicals: the PURE (no unreal) half. Loaded with runpy.run_path on every run (never `import`ed), so an
edited copy never runs stale (memory ue58-python-stale-module-cache). Exercised offline by test_p01_floor.py.

Gary, 8 Oct (GARY_FINISHING_NOTES_2026-10-08.md row F1): P01 practicals seen from the wings "just float there ... maybe
they can just be on the floor ... in the bottom corner". Decision (Gary, 8 Oct): "floor uplights for the domestic lamps
please". Investigation: Docs/Conductor/F1_P01_PRACTICALS_2026-10-08.md.

WHAT A PLAN CHANGES (P01 only; one row per change; nothing else, ever)
 (A) DEAD   every Meshy bulb body (*_BODY, SM_Bulb_* / SM_FX_Bulb_*) whose ONE paired light (same label minus _BODY,
            same cue) is at <= dead_lumens_max (0 lm):  light row  `enabled` -> False   (its Structure lantern goes:
            only enabled Station LIGHT rows get one, InfinityStageStructureActor.cpp:164 / :168-171)
                                                         body row   `relative_transform` -> standing on its screw cap on
            the floor at the foot of its own wing panel, tilted +-tilt_max_deg about a horizontal axis, yawed; all three
            angles from one sha256 per (seed, GUID, key) -- deterministic, no random stream.
 (B) UPLIGHT every domestic body (SM_Lamp_Wall / SM_Lamp_Ceiling) of role PRACTICAL_CLAMP / PRACTICAL_L whose paired
            light is lit:   light row `relative_transform` -> on the floor at the same wing foot, X axis (= the throw;
            the C++ lantern follows it, cpp:1941-1953) pitched pitch_range_deg up, toward +x = into the wing face, at the
            height where its lantern's lowest bound corner rests on the floor; `lighting.type` -> SPOT when
            uplight_type SPOT (a point light cannot be aimed); `lighting.drama.flash_camera_offsets_cm` -= dx on note
            lamps that moved along x (flash_timing COMPENSATE; see FLASH below). Intensity, units, colour, temperature,
            cone angles, anchor, every other field: unchanged (checked).
                            body row  `relative_transform` -> on the floor beside its lantern (outboard side, gap
            body_gap_cm), rotated "head up" (lamp_body_rotation), lowest bound face on the floor.
 (-) LEFT   PRACTICAL_GLIMMER rows (Conductor 5's glimmer -> bare-bulb plan owns them), any Meshy bulb whose light is
            lit (P01 B04 BULB_DEAD at 300 lm: Gary's decision 3), LOW_SIDE / BEAM lantern cans (separate decision; listed
            by cans_report, never changed).

Frame. Pair frame = the attachment's anchor for STATION rows (OccurrenceOffset * StationWorld, cpp:159, and
InfinityStagePassageActor.cpp:2137-2139): x along the route (camera travels +x), y lateral, z up. Every position here
is in that frame, which is exactly what RelativeTransform means for a Station row (InfinityStageTypes.h:462-467).

Proof tiers (AGENTS.md), per claim -- file:line against the tree of 8 Oct 2026:
* declaration-proven
  - lanterns: one ISM instance per ENABLED, LIGHT-kind, STATION-anchored attachment (InfinityStageStructureActor.cpp:164
    skip when !bEnabled or Kind != Light; :168-171 non-Station -> ++OutMovingLights, no lantern); pose: Throw = light X,
    MakeFromXY(Throw, Across) when |Throw.Z| > 0.98 else MakeFromXZ(Throw, Up), body centre = light - Throw*Size.X/2,
    fitted by bounds (cpp:1941-1953, FitMeshToTimber cpp:183-196); hanging line only when Lateral <= GridHalfWidth and
    1 <= Drop <= MaxDropCm with Drop = (station + (Height + Depth*1.5)) - (centre.z + Size.Z/2) (cpp:1962-1975);
  - Light Drama and Movers run only for Station-anchored LIGHT rows (InfinityStagePassageActor.cpp:1864-1866, :1916-1917);
    their lamp position is Wing.DistanceCm + RelativeTransform.X (:1879-1880 drama, :1925 mover) and the authored pose
    is RelativeTransform * OccurrenceOffset * route (:1870-1872) -> a moved Station light keeps its drama, aimed from
    its new pose; a flash fires at CameraPastLampCm - Offset (InfinityStageLightDrama.cpp:62-80), so moving the lamp by
    dx along x moves each flash by dx unless the offset is shifted by -dx;
  - a light's actor class follows Lighting.Type (InfinityStagePassageActor.cpp:964, ResolveNativeLightClass :486-498);
  - a Bulb Body with bFollowLight false glows as authored whatever its light does (InfinityStageBulbBody.h:38-40);
  - Station anchor: "Fixed at the pair's spline station; wings move past it" (InfinityStageTypes.h:154-155); panel
    anchors ride the panel "including its inward travel" (:156-157) -> P01 wings may move (mechanism, :644-700, :750).
* measured (offline, from files read here)
  - Meshy bulb pivot = screw-cap tip at the origin, cap +Z, glass hangs -Z; r_cap per variant (DerivedAssets/Lighting/
    MeshyClean/cleanup_report.json, classification.r_cap_cm, "pivot").
* inferred (each is either re-read live by the DRY, or bounded and stated)
  - the bulb's real contact: modelled as the rim of a cap-end disk of radius r_cap; the real tip is <= that, so the
    real mesh can sit at most r_cap * scale * sin|tilt| above the floor (<= 0.77 cm at 3.2x and 10 deg);
  - lantern contact: the lowest corner of the lantern's BOUNDS box rests on the floor; the real Fresnel mesh may sit a
    little above its bounds corner when pitched (not measurable offline; the first live still shows it);
  - "head up" for the StarterContent lamps (lamp_body_rotation defaults): SM_Lamp_Ceiling is a pendant hung from its top
    -> 180 deg about X puts the shade opening upward; SM_Lamp_Wall's mounting plate faces +X (the score tool placed it
    15 cm in front of the wing face with identity rotation) -> +90 deg about Y puts the plate on the floor, the shade up.
    Override per mesh in args if the first still says otherwise;
  - a SPOT light in LUMENS gives the same luminous intensity as the POINT light it replaces (UE treats spot lumens as an
    isotropic source masked by the cone; engine private .cpp is not in this tree, memory ue58-engine-source-limits).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import runpy
import struct
import types

HERE = os.path.dirname(os.path.abspath(__file__))
CONDUCTOR = os.path.dirname(HERE)
SAVED = os.path.dirname(CONDUCTOR)
PROJECT = os.path.dirname(SAVED)
FIXFOLLOW_DIR = os.path.join(CONDUCTOR, "FixturesFollow")
FC_PATH = os.path.join(FIXFOLLOW_DIR, "fixtures_common.py")
CLEANUP_REPORT = os.path.join(PROJECT, "DerivedAssets", "Lighting", "MeshyClean", "cleanup_report.json")
PASSAGE = "P01"
MARK = "P01FLOOR"


class FloorError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise FloorError(str(message))


def load_fc():
    return types.SimpleNamespace(**runpy.run_path(FC_PATH, run_name="_fixtures_common_for_p01floor"))


FC = load_fc()
M = FC.M
canonical = FC.canonical
asset_id = FC.asset_id
enum_name = FC.enum_name
quat_rotate = FC.quat_rotate
xf = FC.xf
xf_point = FC.xf_point
xf_compose = FC.xf_compose


def sha(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def f32(v):
    return struct.unpack("f", struct.pack("f", float(v)))[0]


# ---- defaults --------------------------------------------------------------------------------------------------
FLOOR_DEFAULTS = {
    "seed": "20261008",
    "dead_lumens_max": 0.0,                 # (A): paired light at or below this (0 lm) -> disabled, body to the floor
    "uplight_roles": ["PRACTICAL_CLAMP", "PRACTICAL_L"],
    "uplight_body_meshes": ["SM_Lamp_Wall", "SM_Lamp_Ceiling"],
    "leave_roles": ["PRACTICAL_GLIMMER"],   # Conductor 5's glimmer -> bare-bulb plan owns these
    "tilt_max_deg": 10.0,                   # dead bulbs: +- tilt about a horizontal axis (Gary: realism)
    "pitch_range_deg": [70.0, 80.0],        # uplights: elevation of the throw above horizontal, toward the wing
    "uplight_type": "SPOT",                 # SPOT (aimable) | KEEP_POINT (keeps POINT; the throw only aims the lantern)
    "flash_timing": "COMPENSATE",           # COMPENSATE (flash offsets -= dx, same musical moment) | NONE
    "y_mode": "NEAREST",                    # NEAREST point of the wing foot | OUTER_CORNER | INNER_CORNER
    "span_margin_cm": 30.0,                 # keep this far inside the panel's lateral span
    "wing_clearance_cm": 5.0,               # gap between any moved bounds and the panel's front-most x
    "lane_half_width_cm": 150.0,            # camera / cat lane kept clear
    "body_gap_cm": 8.0,                     # lamp body beside its lantern
    "lamp_body_rotation": {"SM_Lamp_Ceiling": [[1.0, 0.0, 0.0], 180.0], "SM_Lamp_Wall": [[0.0, 1.0, 0.0], 90.0]},
    "floor_tol_cm": 1.0,                    # every moved support point within +-1 cm of its floor
    "floor_disagree_expected_cm": 0.0,      # measured uniform floor-actor-top minus panel-foot offset (P01: 100.5, 8 Oct DRY)
    "floor_disagree_accept": {},            # {body_guid: cm} named per-item floor exceptions (P02 platform 120.5)
    "floor_disagree_max_cm": 3.0,           # floor actor top vs panel foot: larger -> that item is refused (listed)
    "floor_label_regex": r"Floor",
    # (B) what stands on the floor for a domestic uplight (Gary 8 Oct, second message: "replaced with theatre light
    # meshes"). STRUCTURE_CAN: the domestic body row is disabled and the Structure's own lantern -- generated behind
    # every enabled Station LIGHT, cpp:164-176 -- IS the theatre lantern on the floor, aimed with the light.
    # LAMP_ON_FLOOR: the earlier proposal (domestic lamp beside the lantern). BIRDIE_BODY: refused -- a separate Birdie
    # body would stand next to the Structure lantern (two lanterns), because no per-attachment housing opt-out exists
    # (GatherFixturePlacements tests only bEnabled / Kind / Anchor, cpp:164-176; FInfinityCueAttachment has no such
    # field, InfinityStageTypes.h:439-498; FInfinityStageFixtureSettings neither, InfinityStageStructureActor.h:386-416).
    "uplight_body": "STRUCTURE_CAN",
    "uplight_body_mesh": "/Game/InfinityStage/Lighting/Fixtures/Meshes/SM_Lantern_Birdie",   # BIRDIE_BODY only
    # ADD_UPLIGHTS: new floor uplights per bay side at the wing feet
    "add_per_side": 1,
    "add_skip_sides_with_uplights": True,
    "add_lumens": 800.0,
    "add_on": True,                         # False keeps an enabled 0 lm row, so its Structure lantern still exists
    "add_color": [1.0, 1.0, 1.0, 1.0],    # temperature supplies the colour; do not double-tint it warm
    "add_temperature_kelvin": 3000.0,
    "add_attenuation_radius_cm": 650.0,
    "add_inner_cone_deg": 18.0,
    "add_outer_cone_deg": 42.0,
}
VALID = {"uplight_type": ("SPOT", "KEEP_POINT"), "flash_timing": ("COMPENSATE", "NONE"),
         "y_mode": ("NEAREST", "OUTER_CORNER", "INNER_CORNER"),
         "uplight_body": ("STRUCTURE_CAN", "LAMP_ON_FLOOR", "BIRDIE_BODY")}
BIRDIE_REFUSAL = ("BIRDIE_BODY_NEEDS_CPP|a Birdie body row would stand beside the Structure lantern that every enabled "
                  "Station LIGHT gets (InfinityStageStructureActor.cpp:164-176); no per-attachment housing opt-out exists "
                  "(InfinityStageTypes.h:439-498, InfinityStageStructureActor.h:386-416). Use STRUCTURE_CAN, or the held "
                  "C++ proposal FIXTURES_FOLLOW doc D3 patch 1 (bHousePointLights) / a per-attachment opt-out.")
# Allowed field paths per change kind (scope: anything else differing on a planned row is a violation).
ALLOWED_PATHS = {
    "DEAD_LIGHT_DISABLED": ("enabled",),
    "DEAD_BULB_TO_FLOOR": ("relative_transform",),
    "UPLIGHT_LIGHT_TO_FLOOR": ("relative_transform", "lighting.type", "lighting.drama.flash_camera_offsets_cm"),
    "UPLIGHT_BODY_TO_FLOOR": ("relative_transform",),
    "UPLIGHT_BODY_HIDDEN": ("enabled",),
}
LANTERN_ROLE_PREFIXES = ("LOW_SIDE", "BEAM")


def check_opts(opts):
    out = copy.deepcopy(FLOOR_DEFAULTS)
    for k, v in (opts or {}).items():
        require(k in FLOOR_DEFAULTS, "OPT_UNKNOWN|%s" % k)
        out[k] = copy.deepcopy(v)
    for k, allowed in VALID.items():
        require(out[k] in allowed, "OPT_INVALID|%s=%s" % (k, out[k]))
    require(out["uplight_body"] != "BIRDIE_BODY", BIRDIE_REFUSAL)
    require(isinstance(out["add_per_side"], int) and 0 <= out["add_per_side"] <= 4, "ADD_PER_SIDE_INVALID")
    require(isinstance(out["add_on"], bool), "ADD_ON_INVALID")
    require(0.0 < float(out["add_lumens"]) <= 5000.0, "ADD_LUMENS_INVALID")
    require(1000.0 <= float(out["add_temperature_kelvin"]) <= 15000.0, "ADD_KELVIN_INVALID")
    require(0.0 < float(out["add_attenuation_radius_cm"]) <= 100000.0, "ADD_RADIUS_INVALID")
    inner, outer = float(out["add_inner_cone_deg"]), float(out["add_outer_cone_deg"])
    require(0.0 <= inner <= outer <= 89.0, "ADD_CONE_INVALID")
    require(isinstance(out["add_color"], (list, tuple)) and len(out["add_color"]) == 4
            and all(0.0 <= float(v) <= 1.0 for v in out["add_color"]), "ADD_COLOR_INVALID")
    p0, p1 = (float(v) for v in out["pitch_range_deg"])
    require(45.0 <= p0 <= p1 <= 89.0, "PITCH_RANGE_INVALID|%s" % out["pitch_range_deg"])
    require(0.0 <= float(out["tilt_max_deg"]) <= 20.0, "TILT_RANGE_INVALID")
    require(float(out["dead_lumens_max"]) >= 0.0, "DEAD_LUMENS_INVALID")
    for name, (axis, angle) in out["lamp_body_rotation"].items():
        require(len(axis) == 3 and abs(float(angle)) <= 360.0, "LAMP_BODY_ROTATION_INVALID|" + name)
    return out


# ---- maths -----------------------------------------------------------------------------------------------------
def h01(seed, guid, key):
    digest = hashlib.sha256(("P01FLOOR|%s|%s|%s" % (seed, str(guid).upper(), key)).encode("utf-8")).hexdigest()
    return int(digest[:13], 16) / float(16 ** 13)


def lerp(a, b, t):
    return a + (b - a) * t


def quat_conj(q):
    return [-q[0], -q[1], -q[2], q[3]]


def to_pair(pair_world, p):
    """World point -> pair frame (uniform scale)."""
    s = pair_world["scale"][0]
    require(all(abs(c - s) < 1.0e-6 for c in pair_world["scale"]) and abs(s) > 1.0e-9, "PAIR_SCALE_NOT_UNIFORM")
    d = FC.sub(p, pair_world["location"])
    return [c / s for c in quat_rotate(quat_conj(pair_world["rotation_xyzw"]), d)]


def dir_to_pair(pair_world, v):
    return quat_rotate(quat_conj(pair_world["rotation_xyzw"]), v)


def corners_of(transform, lo, hi):
    return [xf_point(transform, c) for c in FC.bounds_corners(lo, hi)]


def aabb(points):
    return [min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]


def aabb_overlap(a, b, margin=0.0):
    """Axis-aligned overlap in the pair frame (margin > 0 makes touching within margin count)."""
    return all(a[0][i] < b[1][i] + margin and b[0][i] < a[1][i] + margin for i in range(3))


def canon_q(q):
    return [round(v, 12) for v in FC.quat_canonical(FC.quat_norm(q))]


def role_of_label(label):
    return str(label).split()[-1] if str(label).split() else ""


def light_lumens(row):
    lighting = row.get("lighting") or {}
    if enum_name(lighting.get("intensity_units")) != "LUMENS":
        return None
    return float(lighting.get("intensity", 0.0))


def mesh_name(mesh):
    a = asset_id(mesh)
    return None if a is None else a.rsplit("/", 1)[-1]


def is_station(row):
    return enum_name(row.get("anchor")) == "STATION"


def is_kind(row, kind):
    return enum_name(row.get("kind")) == kind


def get_path(row, path):
    cur = row
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def set_path(row, path, value):
    cur = row
    parts = path.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


# ---- static inputs -----------------------------------------------------------------------------------------------
def load_cap_radii(path=CLEANUP_REPORT):
    """{variant: r_cap_cm, ...} plus the pivot rule text (measured: cleanup_report.json per asset)."""
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    out = {}
    for name in M.BULBS:
        rec = report["assets"][name]
        out[name] = {"r_cap_cm": float(rec["classification"]["r_cap_cm"]), "pivot": rec.get("pivot")}
    return out


# ---- panel / floor helpers -------------------------------------------------------------------------------------
def side_panel(panels, y):
    """The cue's side panel on the same side as y: pair-frame AABB not crossing the centre line (Top panels do)."""
    sign = 1.0 if y >= 0 else -1.0
    hits = [p for p in panels if (p["min"][1] > 0 and sign > 0) or (p["max"][1] < 0 and sign < 0)]
    return hits[0] if len(hits) == 1 else None, len(hits)


def lateral_range(panel, side, margin, ext_lo, ext_hi, lane=0.0):
    """Pivot y range keeping [pivot+ext_lo, pivot+ext_hi] inside the panel span shrunk by margin, and out of the
    camera lane |y| < lane."""
    lo = panel["min"][1] + margin - ext_lo
    hi = panel["max"][1] - margin - ext_hi
    if side > 0:
        lo = max(lo, lane - ext_lo)
    else:
        hi = min(hi, -lane - ext_hi)
    return lo, hi


def choose_y(pref, lo, hi, side, mode):
    if lo > hi:
        return None
    if mode == "NEAREST":
        return min(hi, max(lo, pref))
    inner_is_lo = side > 0           # right side (+y): the inner (lane) edge is the low y
    if mode == "INNER_CORNER":
        return lo if inner_is_lo else hi
    return hi if inner_is_lo else lo  # OUTER_CORNER


# ---- geometry of each moved thing (also used by the checks: recomputed from the AFTER rows) -----------------------
def bulb_geometry(t, meta):
    """Standing bulb: support = lowest point of the cap-end disk (radius r_cap*s) at the cap tip (pivot rule)."""
    s = t["scale"][0]
    tip = xf_point(t, meta["tip_local"])
    n = quat_rotate(t["rotation_xyzw"], [0.0, 0.0, 1.0])
    support = tip[2] - meta["r_cap_cm"] * abs(s) * math.sqrt(max(0.0, 1.0 - n[2] * n[2]))
    box = aabb(corners_of(t, meta["bounds"][0], meta["bounds"][1]))
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, -n[2]))))     # 0 = glass straight up
    return {"support_z": support, "aabb": box, "tilt_deg": tilt}


def box_geometry(t, meta):
    box = aabb(corners_of(t, meta["bounds"][0], meta["bounds"][1]))
    return {"support_z": box[0][2], "aabb": box}


def lantern_geometry(light_t, pair_world, across_world, lantern):
    """The C++ lantern for a light at light_t (pair-relative), as pair-frame corners."""
    lw = xf_compose(light_t, pair_world)
    pose = FC.housing_pose(lw, across_world, lantern["bounds"][0], lantern["bounds"][1], lantern["body_size"])
    pts = [to_pair(pair_world, c) for c in corners_of(pose, lantern["bounds"][0], lantern["bounds"][1])]
    throw_pair = dir_to_pair(pair_world, pose["throw"])
    box = aabb(pts)
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, throw_pair[2]))))
    return {"support_z": box[0][2], "aabb": box, "throw_pair": throw_pair, "pitch_deg": pitch,
            "body_centre_world": pose["centre"], "light_world": lw}


def line_after(light_t, enabled, ctx, lantern, grid):
    """cpp:1962-1975 for one placement: does this light's lantern get a hanging line?"""
    if not enabled or not grid or not grid.get("lines_enabled", False):
        return False
    lw = xf_compose(light_t, ctx["pair_world"])
    throw = FC.norm(quat_rotate(lw["rotation_xyzw"], [1.0, 0.0, 0.0]))
    size = lantern["body_size"]
    centre = FC.sub(lw["location"], FC.mul(throw, size[0] * 0.5))
    st = ctx["station_world"]
    origin = st["location"]
    up = quat_rotate(st["rotation_xyzw"], [0.0, 0.0, 1.0])
    across = ctx["across_world"]
    lateral = abs(FC.dot(FC.sub(centre, origin), across))
    grid_top = (FC.add(origin, FC.mul(up, grid["height_cm"] + grid["beam_depth_cm"] * 1.5)))[2]
    drop = grid_top - (centre[2] + size[2] * 0.5)
    return lateral <= grid["half_width_cm"] and 1.0 <= drop <= grid["max_drop_cm"]


# ---- the planner -----------------------------------------------------------------------------------------------
def _pairs(rows):
    by_label = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)
    return by_label


def _row_after(row, **paths):
    after = copy.deepcopy(row)
    for path, value in paths.items():
        set_path(after, path.replace("__", "."), value)
    return after


def _bulb_plan(body, light, fixture, cap, panel, floor_z, opts, side):
    t = body["relative_transform"]
    s = t["scale"]
    require(max(s) - min(s) < 1.0e-6, "BULB_SCALE_NOT_UNIFORM|" + body["guid"])
    s0 = s[0]
    g = body["guid"]
    seed = opts["seed"]
    tilt = lerp(-float(opts["tilt_max_deg"]), float(opts["tilt_max_deg"]), h01(seed, g, "tilt"))
    phi = 360.0 * h01(seed, g, "tilt_axis")
    yaw = 360.0 * h01(seed, g, "yaw")
    q_flip = FC.quat_axis_angle([1.0, 0.0, 0.0], 180.0)
    q_yaw = FC.quat_axis_angle([0.0, 0.0, 1.0], yaw)
    q_tilt = FC.quat_axis_angle([math.cos(math.radians(phi)), math.sin(math.radians(phi)), 0.0], tilt)
    q = canon_q(FC.quat_mul(q_tilt, FC.quat_mul(q_yaw, q_flip)))
    lo, hi = fixture["bounds_min"], fixture["bounds_max"]
    gc = fixture["glass_centre"]
    tip_local = [gc[0], gc[1], hi[2]]                 # screw-cap tip (pivot rule; bounds max z)
    # everything relative to the GLASS CENTRE, whose xy is the bulb's reference point before and after (so a re-plan
    # of an applied row is a no-op)
    rel = [quat_rotate(q, [s0 * (c[i] - gc[i]) for i in range(3)]) for c in FC.bounds_corners(lo, hi)]
    rmin, rmax = aabb(rel)
    tip_rel = quat_rotate(q, [s0 * (tip_local[i] - gc[i]) for i in range(3)])
    n = quat_rotate(q, [0.0, 0.0, 1.0])
    lift = cap["r_cap_cm"] * abs(s0) * math.sqrt(max(0.0, 1.0 - n[2] * n[2]))
    glass_now = xf_point(t, gc)
    # nearest wing foot: a bulb authored behind the panel's mid-plane goes to the foot BEHIND the wing (hidden from the
    # oncoming camera, which looks +x at the panel's front); the rest to the foot in FRONT of it. x is kept when it
    # already clears the panel by wing_clearance_cm.
    clear = float(opts["wing_clearance_cm"])
    behind = glass_now[0] > 0.5 * (panel["min"][0] + panel["max"][0])
    if behind:
        x_g = max(glass_now[0], panel["max"][0] + clear - rmin[0])
    else:
        x_g = min(glass_now[0], panel["min"][0] - clear - rmax[0])
    ylo, yhi = lateral_range(panel, side, float(opts["span_margin_cm"]), rmin[1], rmax[1],
                             float(opts["lane_half_width_cm"]))
    y_g = choose_y(glass_now[1], ylo, yhi, side, opts["y_mode"])
    if y_g is None:
        return None, "SPAN_TOO_NARROW"
    z_g = floor_z + lift - tip_rel[2]                 # the cap rim's lowest point on the floor
    glass = [x_g, y_g, z_g]
    loc = FC.sub(glass, quat_rotate(q, [s0 * c for c in gc]))
    new_t = {"location": [float(v) for v in loc], "rotation_xyzw": q, "scale": list(s)}
    meta = {"geom": "BULB", "bounds": [lo, hi], "tip_local": tip_local, "r_cap_cm": cap["r_cap_cm"],
            "floor_z": floor_z, "tilt_deg": round(tilt, 4), "tilt_axis_deg": round(phi, 4), "yaw_deg": round(yaw, 4),
            "x_moved_cm": round(x_g - glass_now[0], 3), "before_glass": [round(v, 3) for v in glass_now],
            "wing_side": "BEHIND_WING" if behind else "FRONT_OF_WING"}
    return {"after": _row_after(body, relative_transform=new_t), "meta": meta}, None


def _uplight_plan(light, body, body_bounds, lantern, ctx, panel, floor_z, opts, side):
    g = light["guid"]
    p0, p1 = (float(v) for v in opts["pitch_range_deg"])
    pitch = lerp(p0, p1, h01(opts["seed"], g, "pitch"))
    throw = [math.cos(math.radians(pitch)), 0.0, math.sin(math.radians(pitch))]   # +x = into the wing face
    q_light = canon_q(M.make_from_xz(throw, [0.0, 0.0, 1.0]))
    lt = light["relative_transform"]
    probe = {"location": [0.0, 0.0, 0.0], "rotation_xyzw": q_light, "scale": list(lt["scale"])}
    can = lantern_geometry(probe, ctx["pair_world"], ctx["across_world"], lantern)
    origin = to_pair(ctx["pair_world"], ctx["pair_world"]["location"])
    cmin = FC.sub(can["aabb"][0], origin)
    cmax = FC.sub(can["aabb"][1], origin)
    lamp = opts["uplight_body"] == "LAMP_ON_FLOOR"
    if lamp:      # lamp body "head up"
        name = mesh_name(body.get("mesh"))
        axis, angle = opts["lamp_body_rotation"][name]
        q_body = canon_q(FC.quat_axis_angle(axis, float(angle)))
        bs = body["relative_transform"]["scale"]
        bt0 = {"location": [0.0, 0.0, 0.0], "rotation_xyzw": q_body, "scale": list(bs)}
        bmin, bmax = aabb(corners_of(bt0, body_bounds[0], body_bounds[1]))
    else:         # STRUCTURE_CAN: no body on the floor; the group is the lantern alone
        bmin, bmax = list(cmin), list(cmax)
    gap = float(opts["body_gap_cm"])
    margin = float(opts["span_margin_cm"])
    chosen = None
    for direction in (side, -side):                  # outboard first (away from the lane), then inboard
        off = ((cmax[1] + gap - bmin[1]) if direction > 0 else (cmin[1] - gap - bmax[1])) if lamp else 0.0
        gmin, gmax = min(cmin[1], off + bmin[1]), max(cmax[1], off + bmax[1])
        ylo, yhi = lateral_range(panel, side, margin, gmin, gmax, float(opts["lane_half_width_cm"]))
        y = choose_y(lt["location"][1], ylo, yhi, side, opts["y_mode"])
        if y is not None:
            chosen = (y, off, direction)
            break
    if chosen is None:
        return None, "SPAN_TOO_NARROW"
    y_light, off, direction = chosen
    clear = panel["min"][0] - float(opts["wing_clearance_cm"])
    x_light = min(lt["location"][0], clear - cmax[0])
    z_light = floor_z - cmin[2]
    can_cx = x_light + 0.5 * (cmin[0] + cmax[0])
    # no rounding: a coordinate kept from the authored row stays bit-identical (dx == 0 exactly -> no flash edit)
    new_lt = {"location": [float(x_light), float(y_light), float(z_light)], "rotation_xyzw": q_light,
              "scale": list(lt["scale"])}
    dx = new_lt["location"][0] - float(lt["location"][0])
    paths = {"relative_transform": new_lt}
    if opts["uplight_type"] == "SPOT":
        paths["lighting__type"] = "<InfinityStageLightType.SPOT: 0>"
    drama = (light.get("lighting") or {}).get("drama") or {}
    flash = bool(drama.get("flash")) and bool(drama.get("flash_camera_offsets_cm"))
    if flash and opts["flash_timing"] == "COMPENSATE" and abs(dx) > 1.0e-9:
        paths["lighting__drama__flash_camera_offsets_cm"] = [f32(float(o) - dx) for o in drama["flash_camera_offsets_cm"]]
    light_after = _row_after(light, **paths)
    meta_l = {"geom": "UPLIGHT", "floor_z": floor_z, "pitch_deg": round(pitch, 4), "dx_cm": round(dx, 4),
              "flash_lamp": flash, "flash_compensated": "lighting__drama__flash_camera_offsets_cm" in paths,
              "body_side": ("OUTBOARD" if direction == side else "INBOARD") if lamp else "NONE(STRUCTURE_CAN)",
              "before_location": [round(v, 3) for v in lt["location"]],
              "lantern": lantern_on_floor(new_lt, ctx, lantern)}
    if not lamp:
        meta_b = {"geom": None, "before_location": [round(v, 3) for v in body["relative_transform"]["location"]],
                  "why": "STRUCTURE_CAN: the Structure lantern is the theatre lantern on the floor"}
        return {"light": {"after": light_after, "meta": meta_l},
                "body": {"after": _row_after(body, enabled=False), "meta": meta_b, "what": "UPLIGHT_BODY_HIDDEN"}}, None
    x_body = min(can_cx - 0.5 * (bmin[0] + bmax[0]), clear - bmax[0])
    z_body = floor_z - bmin[2]
    new_bt = {"location": [float(x_body), float(y_light + off), float(z_body)], "rotation_xyzw": q_body,
              "scale": list(bs)}
    meta_b = {"geom": "BOX", "bounds": [list(body_bounds[0]), list(body_bounds[1])], "floor_z": floor_z,
              "rotation_axis_angle": [axis, angle],
              "before_location": [round(v, 3) for v in body["relative_transform"]["location"]]}
    return {"light": {"after": light_after, "meta": meta_l},
            "body": {"after": _row_after(body, relative_transform=new_bt), "meta": meta_b,
                     "what": "UPLIGHT_BODY_TO_FLOOR"}}, None


def lantern_on_floor(light_t, ctx, lantern):
    """What stands on the floor for a Station light: the Structure lantern (its mesh, centre, throw, pitch and lens),
    from the C++ formula (cpp:1941-1953): housing X = the light's throw, the light on the bounds' +X front face, so the
    lens / front faces along the throw (lens: cleanup_report lens_centroid_cm, meshy_common.lens_offset_local)."""
    lw = xf_compose(light_t, ctx["pair_world"])
    lo, hi = lantern["bounds"]
    pose = FC.housing_pose(lw, ctx["across_world"], lo, hi, lantern["body_size"])
    out = {"mesh": lantern.get("name"), "centre_pair": [round(v, 2) for v in to_pair(ctx["pair_world"], pose["centre"])],
           "throw_pair": [round(v, 5) for v in dir_to_pair(ctx["pair_world"], pose["throw"])],
           "front_axis": "+X of the lantern = the light's throw (cpp:1945-1951)"}
    if lantern.get("lens_centroid") is not None:
        lens_w = xf_point({"location": pose["location"], "rotation_xyzw": pose["rotation_xyzw"], "scale": pose["scale"]},
                          lantern["lens_centroid"])
        out["lens_pair"] = [round(v, 2) for v in to_pair(ctx["pair_world"], lens_w)]
    return out


def floor_plan(cues, ctx_by_cue, mesh_bounds, table, caps, lantern, grid, opts, floor_by_guid=None, derived_index=None,
               passage=PASSAGE):
    """Pure planner. cues: [{guid,label,show_index,attachments:[rows]}] for P01 only, in route order. ctx_by_cue:
    {cue_guid: {pair_world, station_world, across_world, panels:[{side,min,max}], foot_z_by_side? }} (pair frame
    AABBs). mesh_bounds: {asset id: [lo, hi]} for the lamp bodies. lantern: {bounds:[lo,hi], body_size}. grid: {height_cm,
    beam_depth_cm, half_width_cm, max_drop_cm, lines_enabled} or None. floor_by_guid: {item guid: {"z", "source"}}."""
    opts = check_opts(opts)
    floor_by_guid = floor_by_guid or {}
    derived_index = derived_index or {}
    targets, dead, uplights, left, refused, notes = [], [], [], [], [], []
    for cue in cues:
        ctx = ctx_by_cue[cue["guid"]]
        rows = cue["attachments"]
        by_label = _pairs(rows)
        changes = []
        for body in rows:
            if not (is_kind(body, "PROP") and body["label"].endswith("_BODY")):
                continue
            base = body["label"][:-len("_BODY")]
            role = role_of_label(base)
            lights = [r for r in by_label.get(base, []) if is_kind(r, "LIGHT")]
            mesh = asset_id(body.get("mesh"))
            item = {"cue": cue["label"], "cue_guid": cue["guid"], "role": role, "body_guid": body["guid"],
                    "body_label": body["label"], "body_mesh": mesh,
                    "body_location": [round(v, 2) for v in body["relative_transform"]["location"]]}
            if not role.startswith("PRACTICAL"):
                continue
            if role in opts["leave_roles"]:
                left.append(dict(item, why="GLIMMER_PLAN_OWNS_IT", light_guid=lights[0]["guid"] if len(lights) == 1 else None))
                continue
            if len(lights) != 1:
                refused.append(dict(item, why="PAIRED_LIGHTS_%d" % len(lights)))
                continue
            light = lights[0]
            lm = light_lumens(light)
            item.update({"light_guid": light["guid"], "light_label": light["label"], "lumens": lm,
                         "light_enabled_before": bool(light["enabled"])})
            if not (is_station(light) and is_station(body)):
                refused.append(dict(item, why="NOT_STATION_ANCHORED"))
                continue
            is_bulb = FC.is_fixture_bulb_mesh(mesh)
            is_lamp = mesh_name(mesh) in opts["uplight_body_meshes"]
            if is_bulb and lm is not None and lm <= float(opts["dead_lumens_max"]):
                kind = "DEAD"
            elif is_lamp and role in opts["uplight_roles"] and lm is not None and lm > float(opts["dead_lumens_max"]) \
                    and light["enabled"]:
                kind = "UPLIGHT"
            elif is_bulb:
                left.append(dict(item, why="WORKING_BULB_LIT (Gary decision 3: B04-style working practical)"))
                continue
            else:
                refused.append(dict(item, why="NOT_A_FLOOR_TARGET"))
                continue
            y_ref = light["relative_transform"]["location"][1]
            panel, n_panels = side_panel(ctx["panels"], y_ref)
            if panel is None:
                refused.append(dict(item, why="SIDE_PANEL_%d" % n_panels))
                continue
            side = 1.0 if y_ref >= 0 else -1.0
            fl = floor_by_guid.get(body["guid"]) or {"z": panel["min"][2], "source": "PANEL_FOOT"}
            # 8 Oct live DRY: every P01 floor-actor top sat exactly 100.50 cm above the wing-panel foot (the panels reach
            # below the visible floor). floor_disagree_expected_cm (arg) is that measured, uniform offset; an item is
            # refused only when its own disagreement departs from it by more than floor_disagree_max_cm.
            # floor_disagree_accept (arg): {body_guid: cm} -- an item whose OWN floor actor is a measured, named exception
            # (P02 failing-stage/gap platform: 120.50 cm vs the uniform 100.50, live DRY 9 Oct). Exact value, same tolerance.
            expected_cm = float((opts.get("floor_disagree_accept") or {}).get(body["guid"], opts.get("floor_disagree_expected_cm", 0.0)))
            if fl.get("disagree_cm") is not None and abs(fl["disagree_cm"] - expected_cm) > float(opts["floor_disagree_max_cm"]):
                refused.append(dict(item, why="FLOOR_DISAGREES|%.2f cm" % fl["disagree_cm"]))
                continue
            floor_z = float(fl["z"])
            item.update({"panel_y_span": [round(panel["min"][1], 2), round(panel["max"][1], 2)],
                         "panel_front_x": round(panel["min"][0], 3), "floor_z": round(floor_z, 3),
                         "floor_source": fl["source"]})
            if kind == "DEAD":
                variant = FC.bulb_variant_of_mesh(mesh, derived_index)
                if variant not in table or variant not in caps:
                    refused.append(dict(item, why="BULB_VARIANT_UNKNOWN|%s" % variant))
                    continue
                res, why = _bulb_plan(body, light, table[variant], caps[variant], panel, floor_z, opts, side)
                if res is None:
                    refused.append(dict(item, why=why))
                    continue
                if light["enabled"]:
                    changes.append({"guid": light["guid"], "label": light["label"], "what": "DEAD_LIGHT_DISABLED",
                                    "after": _row_after(light, enabled=False), "meta": {"geom": None, "lumens": lm}})
                changes.append({"guid": body["guid"], "label": body["label"], "what": "DEAD_BULB_TO_FLOOR",
                                "after": res["after"], "meta": dict(res["meta"], variant=variant)})
                dead.append(dict(item, variant=variant, after=res["after"]["relative_transform"], meta=res["meta"]))
            else:
                bb = mesh_bounds.get(mesh)
                if bb is None and opts["uplight_body"] == "LAMP_ON_FLOOR":
                    refused.append(dict(item, why="BODY_BOUNDS_UNKNOWN"))
                    continue
                res, why = _uplight_plan(light, body, bb, lantern, ctx, panel, floor_z, opts, side)
                if res is None:
                    refused.append(dict(item, why=why))
                    continue
                changes.append({"guid": light["guid"], "label": light["label"], "what": "UPLIGHT_LIGHT_TO_FLOOR",
                                "after": res["light"]["after"], "meta": res["light"]["meta"]})
                changes.append({"guid": body["guid"], "label": body["label"], "what": res["body"]["what"],
                                "after": res["body"]["after"], "meta": res["body"]["meta"]})
                uplights.append(dict(item, light_after=res["light"]["after"]["relative_transform"],
                                     body_after=(res["body"]["after"]["relative_transform"]
                                                 if res["body"]["what"] == "UPLIGHT_BODY_TO_FLOOR" else None),
                                     body_hidden=res["body"]["what"] == "UPLIGHT_BODY_HIDDEN",
                                     meta=res["light"]["meta"]))
        by_guid = {r["guid"]: r for r in rows}
        noop = [c for c in changes if not M.row_differences(by_guid[c["guid"]], c["after"])]
        notes.extend({"cue": cue["label"], "label": c["label"], "note": "ALREADY_IN_PLACE"} for c in noop)
        changes = [c for c in changes if c not in noop]
        guids = [c["guid"] for c in changes]
        require(len(guids) == len(set(guids)), "ROW_PLANNED_TWICE|" + cue["label"])
        if changes:
            targets.append({"cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue.get("show_index"),
                            "changes": changes})
    kinds = {}
    for t in targets:
        for c in t["changes"]:
            kinds[c["what"]] = kinds.get(c["what"], 0) + 1
    plan = {"op": "FLOOR", "passage": passage, "opts": opts, "lantern": lantern, "grid": grid,
            "ctx": {g: {k: v for k, v in c.items() if k != "mechanism"} for g, c in ctx_by_cue.items()
                    if g in {t["cue_guid"] for t in targets}},
            "targets": targets, "dead": dead, "uplights": uplights, "left": left, "refused": refused, "notes": notes,
            "counts": {"cues": len(targets), "rows": sum(len(t["changes"]) for t in targets), "by_kind": kinds,
                       "dead_bulbs": len(dead), "uplights": len(uplights),
                       "uplight_bodies_hidden": sum(1 for u in uplights if u.get("body_hidden")),
                       "dead_behind_wing": sum(1 for d in dead if d["meta"]["wing_side"] == "BEHIND_WING"),
                       "uplight_bodies_inboard": sum(1 for u in uplights if u["meta"]["body_side"] == "INBOARD"),
                       "flash_lamps_compensated": sum(1 for u in uplights if u["meta"]["flash_compensated"]),
                       "glimmers_left": sum(1 for x in left if x["why"].startswith("GLIMMER")),
                       "working_left": sum(1 for x in left if x["why"].startswith("WORKING")),
                       "refused": len(refused), "already_in_place": len(notes)}}
    return plan


# ---- predictions: lanterns and lines -------------------------------------------------------------------------------
def housings(cues_in_order, ctx_by_cue):
    worlds = {c["guid"]: ctx_by_cue[c["guid"]]["pair_world"] for c in cues_in_order if c["guid"] in ctx_by_cue}
    across = {c["guid"]: ctx_by_cue[c["guid"]]["across_world"] for c in cues_in_order if c["guid"] in ctx_by_cue}
    return FC.follow_placements([c for c in cues_in_order if c["guid"] in worlds], worlds, across)


def predict_structure(plan, before_all):
    """Lanterns removed (= dead lights disabled that were enabled Station LIGHTs) and the hanging-line delta of every
    changed light (cpp:1962-1975)."""
    rows = {r["guid"]: r for rs in before_all.values() for r in rs}
    removed, line_delta, new_lines = 0, 0, []
    for t in plan["targets"]:
        ctx = plan["ctx"][t["cue_guid"]]
        for c in t["changes"]:
            b = rows[c["guid"]]
            a = c["after"]
            if not is_kind(b, "LIGHT"):
                continue
            was = b["enabled"] and is_station(b)
            now = a["enabled"] and is_station(a) and is_kind(a, "LIGHT")
            removed += bool(was and not now)
            if plan["grid"]:
                lb = line_after(b["relative_transform"], was, ctx, plan["lantern"], plan["grid"])
                la = line_after(a["relative_transform"], now, ctx, plan["lantern"], plan["grid"])
                line_delta += int(la) - int(lb)
                if la and not lb:
                    new_lines.append(c["label"])
    return {"housings_removed": removed, "hanging_line_delta": line_delta, "new_lines": new_lines}


# ---- checks (recomputed from the AFTER rows, so a mutated plan or a lying write is caught) ------------------------
def _diff_paths(before, after):
    diffs = M.row_differences(before, after)
    out = set()
    for d in diffs:
        p = d["path"].lstrip(".")
        p = p.split("[", 1)[0]
        out.add(p)
    return out


def path_allowed(path, allowed):
    return any(path == a or path.startswith(a + ".") for a in allowed)


def plan_checks(plan, before_all):
    """Every invariant the brief names. Returns [(code, label, detail)]; empty = pass."""
    bad = []
    opts = plan["opts"]
    tol = float(opts["floor_tol_cm"])
    rows = {r["guid"]: r for rs in before_all.values() for r in rs}
    p0, p1 = (float(v) for v in opts["pitch_range_deg"])
    planned = set()
    for t in plan["targets"]:
        ctx = plan["ctx"][t["cue_guid"]]
        boxes = []
        for c in t["changes"]:
            planned.add(c["guid"])
            before = rows.get(c["guid"])
            if before is None:
                bad.append(("ROW_NOT_IN_CUE", c["label"], c["guid"]))
                continue
            role = role_of_label(before["label"][:-len("_BODY")] if before["label"].endswith("_BODY") else before["label"])
            if role in opts["leave_roles"]:
                bad.append(("GLIMMER_TOUCHED", c["label"], role))
            for p in _diff_paths(before, c["after"]):
                if not path_allowed(p, ALLOWED_PATHS[c["what"]]):
                    bad.append(("FIELD_OUT_OF_SCOPE", c["label"], p))
            after = c["after"]
            meta = c["meta"]
            if c["what"] == "UPLIGHT_BODY_HIDDEN":
                if after["enabled"] is not False:
                    bad.append(("DOMESTIC_BODY_STILL_VISIBLE", c["label"], after["enabled"]))
                if mesh_name(before.get("mesh")) not in opts["uplight_body_meshes"]:
                    bad.append(("HID_A_NON_DOMESTIC_BODY", c["label"], before.get("mesh")))
                continue
            if c["what"] == "DEAD_LIGHT_DISABLED":
                if after["enabled"] is not False:
                    bad.append(("DEAD_LIGHT_STILL_ENABLED", c["label"], after["enabled"]))
                lm = light_lumens(before)
                if lm is None or lm > float(opts["dead_lumens_max"]):
                    bad.append(("DISABLED_A_LIT_LIGHT", c["label"], lm))
                continue
            panel = None
            if c["what"] == "UPLIGHT_LIGHT_TO_FLOOR":
                geo = lantern_geometry(after["relative_transform"], ctx["pair_world"], ctx["across_world"], plan["lantern"])
                if not (p0 - 1.0e-6 <= geo["pitch_deg"] <= p1 + 1.0e-6):
                    bad.append(("PITCH_OUT_OF_RANGE", c["label"], round(geo["pitch_deg"], 3)))
                if geo["throw_pair"][0] <= 0.0:
                    bad.append(("AIM_NOT_TOWARD_WING", c["label"], geo["throw_pair"]))
                for f in ("intensity", "intensity_units", "color", "temperature_kelvin", "use_temperature",
                          "attenuation_radius_cm", "inner_cone_angle_degrees", "outer_cone_angle_degrees"):
                    if M.row_differences({"v": (before.get("lighting") or {}).get(f)},
                                         {"v": (after.get("lighting") or {}).get(f)}):
                        bad.append(("LIGHT_SETTING_CHANGED", c["label"], f))
                if not after["enabled"]:
                    bad.append(("UPLIGHT_DISABLED", c["label"], False))
                if opts["uplight_type"] == "SPOT" and enum_name(after["lighting"]["type"]) != "SPOT":
                    bad.append(("UPLIGHT_NOT_SPOT", c["label"], after["lighting"]["type"]))
                if enum_name(after.get("anchor")) != "STATION":
                    bad.append(("UPLIGHT_NOT_STATION", c["label"], after.get("anchor")))
            elif c["what"] == "DEAD_BULB_TO_FLOOR":
                geo = bulb_geometry(after["relative_transform"], meta)
                if geo["tilt_deg"] > float(opts["tilt_max_deg"]) + 1.0e-6:
                    bad.append(("BULB_TILT_OUT_OF_RANGE", c["label"], round(geo["tilt_deg"], 3)))
            else:
                geo = box_geometry(after["relative_transform"], meta)
            gap = geo["support_z"] - float(meta["floor_z"])
            if gap > tol:
                bad.append(("FLOATING", c["label"], round(gap, 3)))
            elif gap < -tol:
                bad.append(("SUNK_IN_FLOOR", c["label"], round(gap, 3)))
            y = (geo["aabb"][0][1] + geo["aabb"][1][1]) * 0.5
            panel, _n = side_panel(ctx["panels"], y)
            if panel is None:
                bad.append(("NO_SIDE_PANEL", c["label"], y))
            else:
                wing_box = (panel["min"], panel["max"])
                if aabb_overlap(geo["aabb"], wing_box, float(opts["wing_clearance_cm"]) - 0.05):   # 0.5 mm rounding slack
                    bad.append(("INSIDE_WING_PANEL", c["label"], [round(geo["aabb"][1][0], 2), round(panel["min"][0], 2)]))
            lane = float(opts["lane_half_width_cm"])
            lo_y, hi_y = geo["aabb"][0][1], geo["aabb"][1][1]
            if lo_y < lane and hi_y > -lane:
                bad.append(("IN_CAMERA_LANE", c["label"], [round(lo_y, 1), round(hi_y, 1)]))
            boxes.append((c["label"], geo["aabb"]))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if aabb_overlap(boxes[i][1], boxes[j][1]):
                    bad.append(("MOVED_OBJECTS_OVERLAP", boxes[i][0], boxes[j][0]))
    pred = predict_structure(plan, before_all)
    if pred["new_lines"]:
        bad.append(("NEW_HANGING_LINE", ",".join(pred["new_lines"][:5]), pred["hanging_line_delta"]))
    return bad


# ---- (C) report only: the LOW_SIDE / BEAM lantern cans -------------------------------------------------------------
def cans_report(cues, ctx_by_cue, lantern):
    out = []
    for cue in cues:
        ctx = ctx_by_cue.get(cue["guid"])
        if ctx is None:
            continue
        for r in cue["attachments"]:
            if not (is_kind(r, "LIGHT") and r["enabled"] and is_station(r)):
                continue
            role = role_of_label(r["label"])
            if not role.startswith(LANTERN_ROLE_PREFIXES):
                continue
            geo = lantern_geometry(r["relative_transform"], ctx["pair_world"], ctx["across_world"], lantern)
            y = r["relative_transform"]["location"][1]
            panel, _n = side_panel(ctx["panels"], y)
            outer = None if panel is None else (panel["max"][1] if y >= 0 else panel["min"][1])
            out.append({"cue": cue["label"], "role": role, "light_guid": r["guid"], "label": r["label"],
                        "abs_y_gt_1130": abs(y) > 1130.0,
                        "light_rel": [round(v, 1) for v in r["relative_transform"]["location"]],
                        "can_z_range": [round(geo["aabb"][0][2], 1), round(geo["aabb"][1][2], 1)],
                        "can_abs_y_range": sorted([round(abs(geo["aabb"][0][1]), 1), round(abs(geo["aabb"][1][1]), 1)]),
                        "panel_outer_y": None if outer is None else round(outer, 1),
                        "outboard_of_panel": None if outer is None else abs(y) > abs(outer)})
    return out


# ---- generic scope / revert -------------------------------------------------------------------------------------
def expected_after(before_all, plan):
    return FC.expected_after(before_all, plan)


def scope_problems(want_all, live_all):
    return FC.scope_problems(want_all, live_all)


def check_scope(want_all, live_all, side):
    problems = scope_problems(want_all, live_all)
    require(not problems, "SCOPE_CHANGED|side=%s|count=%d|%s" % (side, len(problems), canonical(problems)[:3000]))


def revert_model(record, live_all):
    return FC.revert_model(record, live_all)


def plan_sha(plan):
    return sha(plan)


def item_table(plan):
    """One row per moved practical (for the CSV and the preview)."""
    rows = []
    for d in plan["dead"]:
        rows.append({"cue": d["cue"], "role": d["role"], "class": "A_DEAD", "light_guid": d["light_guid"],
                     "body_guid": d["body_guid"], "lumens": d["lumens"], "body_mesh": mesh_name(d["body_mesh"]),
                     "before_xyz": d["meta"]["before_glass"], "after_light_xyz": None,
                     "after_body_xyz": [round(v, 2) for v in d["after"]["location"]],
                     "pitch_deg": None, "tilt_deg": d["meta"]["tilt_deg"], "floor_z": d["floor_z"],
                     "floor_source": d["floor_source"], "panel_y_span": d["panel_y_span"], "dx_cm": d["meta"]["x_moved_cm"],
                     "wing_side": d["meta"]["wing_side"], "flash": None})
    for u in plan["uplights"]:
        rows.append({"cue": u["cue"], "role": u["role"], "class": "B_UPLIGHT", "light_guid": u["light_guid"],
                     "body_guid": u["body_guid"], "lumens": u["lumens"], "body_mesh": mesh_name(u["body_mesh"]),
                     "before_xyz": u["meta"]["before_location"],
                     "after_light_xyz": [round(v, 2) for v in u["light_after"]["location"]],
                     "after_body_xyz": ("HIDDEN(STRUCTURE_CAN)" if u.get("body_hidden")
                                        else [round(v, 2) for v in u["body_after"]["location"]]),
                     "pitch_deg": u["meta"]["pitch_deg"], "tilt_deg": None, "floor_z": u["floor_z"],
                     "floor_source": u["floor_source"], "panel_y_span": u["panel_y_span"], "dx_cm": u["meta"]["dx_cm"],
                     "wing_side": "FRONT_OF_WING", "flash": ("COMPENSATED" if u["meta"]["flash_compensated"] else "FLASH_LAMP") if u["meta"]["flash_lamp"]
                     else None})
    for x in plan["left"]:
        rows.append({"cue": x["cue"], "role": x["role"], "class": "LEFT", "light_guid": x.get("light_guid"),
                     "body_guid": x["body_guid"], "lumens": x.get("lumens"), "body_mesh": mesh_name(x["body_mesh"]),
                     "before_xyz": None, "after_light_xyz": None, "after_body_xyz": None, "pitch_deg": None,
                     "tilt_deg": None, "floor_z": None, "floor_source": None, "panel_y_span": None, "dx_cm": None,
                     "wing_side": None, "flash": x["why"]})
    return rows


# ---- ADD_UPLIGHTS ------------------------------------------------------------------------------------------------
def _existing_uplight_sides(rows):
    """Sides (+1/-1) of a bay that already have a floor-level, upward-thrown enabled LIGHT (or an UPLIGHT role)."""
    out = set()
    for r in rows:
        if not (is_kind(r, "LIGHT") and r["enabled"]):
            continue
        t = r["relative_transform"]
        up = quat_rotate(t["rotation_xyzw"], [1.0, 0.0, 0.0])[2]
        if "UPLIGHT" in role_of_label(r["label"]) or (t["location"][2] < 120.0 and up > 0.5):
            out.add(1.0 if t["location"][1] >= 0 else -1.0)
    return out


def add_uplights_plan(cues, ctx_by_cue, lantern, grid, opts, passage, floor_by_guid=None):
    """N new Station LIGHT rows per bay side, at the wing foot (in front of the panel, wing_clearance_cm off it), the
    lantern's lowest bounds corner on the floor, throw pitched pitch_range_deg up toward +x (into the wing face),
    evenly spread along the panel's span. Each would get the Structure's lantern (cpp:164-176): that lantern IS the
    floor uplight's body. The planner uses deterministic NEW... placeholder ids; APPLY replaces them with GUIDs minted
    by Unreal and records every resulting row id before save."""
    opts = check_opts(opts)
    floor_by_guid = floor_by_guid or {}
    n = int(opts["add_per_side"])
    targets, skipped = [], []
    for cue in cues:
        ctx = ctx_by_cue[cue["guid"]]
        have = _existing_uplight_sides(cue["attachments"])
        changes = []
        for panel in ctx["panels"]:
            if panel["min"][1] <= 0.0 <= panel["max"][1]:
                continue                                   # a Top panel spans the centre line
            side = 1.0 if panel["min"][1] > 0 else -1.0
            tag = "R" if side > 0 else "L"
            if opts["add_skip_sides_with_uplights"] and side in have:
                skipped.append({"cue": cue["label"], "side": tag, "why": "SIDE_ALREADY_HAS_AN_UPLIGHT"})
                continue
            for k in range(n):
                key = "%s|%s|%d" % (cue["guid"], tag, k)
                pitch = lerp(float(opts["pitch_range_deg"][0]), float(opts["pitch_range_deg"][1]),
                             h01(opts["seed"], key, "pitch"))
                throw = [math.cos(math.radians(pitch)), 0.0, math.sin(math.radians(pitch))]
                q = canon_q(M.make_from_xz(throw, [0.0, 0.0, 1.0]))
                probe = {"location": [0.0, 0.0, 0.0], "rotation_xyzw": q, "scale": [1.0, 1.0, 1.0]}
                can = lantern_geometry(probe, ctx["pair_world"], ctx["across_world"], lantern)
                cmin, cmax = can["aabb"]
                ylo, yhi = lateral_range(panel, side, float(opts["span_margin_cm"]), cmin[1], cmax[1],
                                         float(opts["lane_half_width_cm"]))
                if ylo > yhi:
                    skipped.append({"cue": cue["label"], "side": tag, "why": "SPAN_TOO_NARROW"})
                    continue
                y = ylo + (yhi - ylo) * (k + 1.0) / (n + 1.0)
                guid = "NEW%s" % hashlib.sha256(key.encode()).hexdigest()[:29].upper()
                fl = floor_by_guid.get(guid) or {"z": panel["min"][2], "source": "PANEL_FOOT"}
                if fl.get("disagree_cm") is not None and abs(fl["disagree_cm"] - float(opts.get("floor_disagree_expected_cm", 0.0))) > float(opts["floor_disagree_max_cm"]):
                    skipped.append({"cue": cue["label"], "side": tag, "why": "FLOOR_DISAGREES"})
                    continue
                x = panel["min"][0] - float(opts["wing_clearance_cm"]) - cmax[0]
                z = float(fl["z"]) - cmin[2]
                t = {"location": [float(x), float(y), float(z)], "rotation_xyzw": q, "scale": [1.0, 1.0, 1.0]}
                row = {"guid": guid, "label": "%s FLOOR UPLIGHT_%s%d" % (cue["label"], tag, k + 1),
                       "kind": "<InfinityAttachmentKind.LIGHT: 1>", "enabled": True,
                       "anchor": "<InfinityAttachmentAnchor.STATION: 0>", "relative_transform": t, "mesh": None,
                       "lighting": {"type": "<InfinityStageLightType.SPOT: 0>",
                                    "intensity_units": "<InfinityStageLightIntensityUnits.LUMENS: 2>",
                                    "intensity": float(opts["add_lumens"]) if opts["add_on"] else 0.0,
                                    "color": list(opts["add_color"]),
                                    "use_temperature": True, "temperature_kelvin": float(opts["add_temperature_kelvin"]),
                                    "attenuation_radius_cm": float(opts["add_attenuation_radius_cm"]),
                                    "inner_cone_angle_degrees": float(opts["add_inner_cone_deg"]),
                                    "outer_cone_angle_degrees": float(opts["add_outer_cone_deg"]),
                                    "cast_shadows": False}}
                changes.append({"guid": guid, "label": row["label"], "what": "ADD_UPLIGHT", "after": row,
                                 "meta": {"geom": "UPLIGHT", "floor_z": float(fl["z"]), "floor_source": fl["source"],
                                          "pitch_deg": round(pitch, 4), "before_location": None, "side": tag,
                                          "on": bool(opts["add_on"]), "requested_lumens": float(opts["add_lumens"]),
                                          "temperature_kelvin": float(opts["add_temperature_kelvin"]),
                                          "panel_y_span": [round(panel["min"][1], 1), round(panel["max"][1], 1)],
                                         "lantern": lantern_on_floor(t, ctx, lantern)}})
        if changes:
            targets.append({"cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue.get("show_index"),
                            "changes": changes})
    return {"op": "ADD_UPLIGHTS", "passage": passage, "opts": opts, "lantern": lantern, "grid": grid,
            "ctx": {t["cue_guid"]: ctx_by_cue[t["cue_guid"]] for t in targets}, "targets": targets,
            "skipped": skipped, "dead": [], "uplights": [], "left": [], "refused": [], "notes": [],
            "counts": {"cues": len(targets), "proposed_uplights": sum(len(t["changes"]) for t in targets),
                       "enabled_rows": sum(len(t["changes"]) for t in targets),
                       "lit_rows": sum(1 for t in targets for c in t["changes"]
                                       if float(c["after"]["lighting"]["intensity"]) > 0.0),
                       "sides_skipped": len(skipped), "rows": sum(len(t["changes"]) for t in targets)}}


def add_plan_checks(plan):
    bad = []
    opts = plan["opts"]
    tol = float(opts["floor_tol_cm"])
    p0, p1 = (float(v) for v in opts["pitch_range_deg"])
    lane = float(opts["lane_half_width_cm"])
    for t in plan["targets"]:
        ctx = plan["ctx"][t["cue_guid"]]
        boxes = []
        for c in t["changes"]:
            row = c["after"]
            lighting = row["lighting"]
            expected_lumens = float(opts["add_lumens"]) if opts["add_on"] else 0.0
            if row.get("enabled") is not True:
                bad.append(("ADD_ROW_DISABLED", c["label"], row.get("enabled")))
            if enum_name(row.get("kind")) != "LIGHT" or enum_name(row.get("anchor")) != "STATION":
                bad.append(("ADD_ROW_KIND_OR_ANCHOR", c["label"], [row.get("kind"), row.get("anchor")]))
            if enum_name(lighting.get("type")) != "SPOT" or enum_name(lighting.get("intensity_units")) != "LUMENS":
                bad.append(("ADD_LIGHT_TYPE_OR_UNITS", c["label"], [lighting.get("type"), lighting.get("intensity_units")]))
            if abs(float(lighting.get("intensity", -1.0)) - expected_lumens) > 1.0e-4:
                bad.append(("ADD_LUMENS", c["label"], lighting.get("intensity")))
            if not lighting.get("use_temperature") or abs(float(lighting.get("temperature_kelvin", 0.0))
                                                            - float(opts["add_temperature_kelvin"])) > 1.0e-4:
                bad.append(("ADD_KELVIN", c["label"], lighting.get("temperature_kelvin")))
            geo = lantern_geometry(c["after"]["relative_transform"], ctx["pair_world"], ctx["across_world"], plan["lantern"])
            if not (p0 - 1e-6 <= geo["pitch_deg"] <= p1 + 1e-6) or geo["throw_pair"][0] <= 0:
                bad.append(("PITCH_OR_AIM", c["label"], round(geo["pitch_deg"], 3)))
            gap = geo["support_z"] - c["meta"]["floor_z"]
            if abs(gap) > tol:
                bad.append(("FLOATING" if gap > 0 else "SUNK_IN_FLOOR", c["label"], round(gap, 3)))
            y = 0.5 * (geo["aabb"][0][1] + geo["aabb"][1][1])
            panel, _n = side_panel(ctx["panels"], y)
            if panel is None or aabb_overlap(geo["aabb"], (panel["min"], panel["max"]),
                                             float(opts["wing_clearance_cm"]) - 0.05):
                bad.append(("INSIDE_WING_PANEL", c["label"], y))
            if geo["aabb"][0][1] < lane and geo["aabb"][1][1] > -lane:
                bad.append(("IN_CAMERA_LANE", c["label"], y))
            if plan["grid"] and line_after(c["after"]["relative_transform"], True, ctx, plan["lantern"], plan["grid"]):
                bad.append(("NEW_HANGING_LINE", c["label"], None))
            boxes.append((c["label"], geo["aabb"]))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if aabb_overlap(boxes[i][1], boxes[j][1]):
                    bad.append(("MOVED_OBJECTS_OVERLAP", boxes[i][0], boxes[j][0]))
    return bad
