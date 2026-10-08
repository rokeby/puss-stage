"""Fixtures FOLLOW / SCALE / RELOCATE: the PURE (no unreal) half. Loaded with runpy.run_path on every run (never
`import`ed), so an edited copy never runs stale (memory ue58-python-stale-module-cache). Exercised offline by
test_fixtures_follow.py. Reuses meshy_common.py (MeshyFixtures_20261007) for the fixture table and its quaternion /
fit maths, loaded the same way.

Proof tiers (AGENTS.md), per claim -- file:line against the tree of 7 Oct 2026:
* declaration-proven
  - housings are derived ONLY from the Show: GatherFixturePlacements walks every Station-anchored, enabled LIGHT
    attachment of every WingPair cue at a station, LightWorld = RelativeTransform * (OccurrenceOffset * StationWorld)
    (InfinityStageStructureActor.cpp:142-180); BuildFixtures: Throw = LightWorld X axis, rotation MakeFromXY(Throw,
    StationAcross) when |Throw.Z| > 0.98 else MakeFromXZ(Throw, Up), body centre = light - Throw * BodySize.X/2,
    fitted by bounds (cpp:1920-1955, FitMeshToTimber cpp:188-199); one ISM instance per placement IN PLACEMENT ORDER
    (cpp:1941-1955, 1984-1987); housings + lines cast no shadow and have NoCollision (cpp:1979-1985, :798);
  - a stale structure is detectable: the signature hashes every placement's LightWorld location + X + Z axis
    (cpp:218-252) and IsStructureCurrent compares it (cpp:358-370); the structure test proves a moved light reads
    stale (InfinityStageTests/Private/InfinityStageStructureTests.cpp:371-373);
  - one BodyMesh / BodySizeCm / BodyMaterial per Structure (InfinityStageStructureActor.h:396-416); no lens-offset or
    per-light opt-out field exists (same lines) -> exact lens placement and "no lantern on a point light" need C++;
  - hanging line top = Gridiron.HeightCm + BeamDepthCm*1.5 above the station; line only if lateral <= GridHalfWidth
    and 1 <= drop <= MaxDropCm (cpp:1957-1975); crossbeam centre at HeightCm, rails one depth higher at
    +-GridHalfWidth (cpp:1258-1300);
  - a Bulb Body with bFollowLight whose named light is disabled or not a Light finds NO light (predicate requires
    bEnabled && Kind == Light) -> DramaScale 1 = authored glow x its own flicker (InfinityStagePassageActor.cpp:
    1976-2000); without bFollowLight the glass glows as authored (InfinityStageBulbBody.h:39-41).
* measured (offline, from files read here)
  - Meshy swap state per passage (records meshy_swap_record_P0N.json, status saved_readback_verified, runs
    20261007-0825..0829): bulb_scale 3.2 (glass on the paired light), housing_scale 1.0, Fresnel P01/03/04/05,
    ParCan P02/06; 225 bulbs; ALL bodies follow_light False; paired lights 0-40 lm except P02 PRACTICAL_R x12 at
    800 lm and one P01 PRACTICAL_DEAD at 300 lm (working practicals).
  - gridiron v3: HeightCm 1150, BeamDepthCm 180, BeamWidthCm 80 on all six Structures
    (Girders_20261007/girders_v3_originals_GV3A-20261007-024125.json).
  - PRACTICAL_GLIMMER rows: one light + one SM_Lamp_Ceiling _BODY per GAP bay; NO *GLIMMER_CAP row in any snapshot.
* inferred (the live DRY confirms or refuses each)
  - the pair frame's z = 0 is the floor plane (TOP lamps sit at z 1180-1420 against a crossbeam at 1150; the dark wet
    slabs' tops are world z +0.5, floor_dark_wet_record.json); the live DRY reads floor-actor bounds instead.
  - GridHalfWidthCm offline default 1350 (live reads grid_half_width_cm).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import runpy
import types

HERE = os.path.dirname(os.path.abspath(__file__))
CONDUCTOR = os.path.dirname(HERE)
MESHY_DIR = os.path.join(CONDUCTOR, "MeshyFixtures_20261007")
MESHY_COMMON_PATH = os.path.join(MESHY_DIR, "meshy_common.py")
PASSAGES = ("P01", "P02", "P03", "P04", "P05", "P06")


class FixturesError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise FixturesError(str(message))


def load_meshy_common():
    return types.SimpleNamespace(**runpy.run_path(MESHY_COMMON_PATH, run_name="_meshy_common_for_fixtures"))


M = load_meshy_common()
canonical = M.canonical
asset_id = M.asset_id
object_path = M.object_path
enum_name = M.enum_name
quat_rotate = M.quat_rotate
make_from_xz = M.make_from_xz
quat_from_basis = M.quat_from_basis


def sha(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


# ---- vector / quaternion / transform maths (FTransform semantics) ----------------------------------------------
def norm(v):
    n = math.sqrt(sum(c * c for c in v))
    require(n > 1.0e-12, "ZERO_VECTOR")
    return [c / n for c in v]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def mul(a, s):
    return [x * s for x in a]


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def quat_mul(a, b):
    """Hamilton product, xyzw: (a*b) applies b first, then a (FQuat operator*)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def quat_norm(q):
    n = math.sqrt(sum(c * c for c in q))
    return [c / n for c in q]


def quat_axis_angle(axis, degrees):
    a = norm(axis)
    h = math.radians(degrees) * 0.5
    s = math.sin(h)
    return [a[0] * s, a[1] * s, a[2] * s, math.cos(h)]


def quat_canonical(q):
    """Positive first non-zero component (the attachment-state convention, _infinity_attachment_state.py:70-87)."""
    for c in q:
        if abs(c) > 1.0e-12:
            return list(q) if c > 0 else [-x for x in q]
    return list(q)


def axes(q):
    return quat_rotate(q, [1.0, 0.0, 0.0]), quat_rotate(q, [0.0, 1.0, 0.0]), quat_rotate(q, [0.0, 0.0, 1.0])


def make_from_xy(x_axis, y_hint):
    """FRotationMatrix::MakeFromXY: X exact, Y as close to the hint as possible."""
    fx = norm(x_axis)
    fz = norm(cross(fx, y_hint))
    fy = cross(fz, fx)
    return quat_from_basis(fx, fy, fz)


def xf(location, rotation_xyzw, scale=(1.0, 1.0, 1.0)):
    return {"location": [float(v) for v in location], "rotation_xyzw": [float(v) for v in rotation_xyzw],
            "scale": [float(v) for v in scale]}


def xf_point(t, p):
    """FTransform::TransformPosition: loc + R * (scale * p)."""
    return add(t["location"], quat_rotate(t["rotation_xyzw"], [a * b for a, b in zip(t["scale"], p)]))


def xf_compose(child, parent):
    """FTransform child * parent (child expressed relative to parent), uniform-scale case."""
    return {"location": xf_point(parent, child["location"]),
            "rotation_xyzw": quat_norm(quat_mul(parent["rotation_xyzw"], child["rotation_xyzw"])),
            "scale": [a * b for a, b in zip(child["scale"], parent["scale"])]}


def bounds_corners(lo, hi):
    return [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def corner_gap(t_a, t_b, lo, hi):
    """Largest distance between the 8 bound corners under two transforms. Equal matrices give 0 even when the ISM
    readback re-decomposed a mirror onto X (memory ue58-ism-readback-and-test-traps)."""
    return max(dist(xf_point(t_a, c), xf_point(t_b, c)) for c in bounds_corners(lo, hi))


# ---- the C++ housing, mirrored ---------------------------------------------------------------------------------
def housing_pose(light_world, station_across, bounds_min, bounds_max, body_size):
    """BuildFixtures (cpp:1941-1953) for one placement -> transform of the housing ISM instance (world)."""
    throw = norm(quat_rotate(light_world["rotation_xyzw"], [1.0, 0.0, 0.0]))
    if abs(throw[2]) > 0.98:
        rotation = make_from_xy(throw, station_across)
    else:
        rotation = make_from_xz(throw, [0.0, 0.0, 1.0])
    centre = sub(light_world["location"], mul(throw, body_size[0] * 0.5))
    location, rotation, scale = M.fit_mesh_to_timber(bounds_min, bounds_max, centre, rotation, body_size)
    return {"location": location, "rotation_xyzw": rotation, "scale": scale, "throw": throw, "centre": centre}


def aim_error_deg(housing_rotation, throw):
    """Angle between a housing instance's X axis and the light's throw."""
    hx = norm(quat_rotate(housing_rotation, [1.0, 0.0, 0.0]))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(hx, norm(throw))))))


def lens_world(pose, fixture):
    lens = fixture.get("lens_centroid")
    return None if lens is None else xf_point(pose, lens)


# ---- oriented boxes ---------------------------------------------------------------------------------------------
def obb_from_fit(pose, bounds_min, bounds_max):
    """World OBB of a bounds-fitted mesh instance: centre, unit axes, half extents."""
    c = [(a + b) * 0.5 for a, b in zip(bounds_min, bounds_max)]
    half = [abs((b - a) * 0.5 * s) for a, b, s in zip(bounds_min, bounds_max, pose["scale"])]
    return {"centre": xf_point(pose, c), "axes": list(axes(pose["rotation_xyzw"])), "half": half}


def obb(centre, rotation_xyzw, half):
    return {"centre": list(centre), "axes": list(axes(rotation_xyzw)), "half": list(half)}


def obb_overlap(a, b, margin=0.0):
    """Separating-axis test, 15 axes. True = the boxes interpenetrate by more than margin."""
    t = sub(b["centre"], a["centre"])
    cand = list(a["axes"]) + list(b["axes"])
    for u in a["axes"]:
        for v in b["axes"]:
            c = cross(u, v)
            if math.sqrt(dot(c, c)) > 1.0e-9:
                cand.append(norm(c))
    for axis in cand:
        ra = sum(h * abs(dot(u, axis)) for h, u in zip(a["half"], a["axes"]))
        rb = sum(h * abs(dot(u, axis)) for h, u in zip(b["half"], b["axes"]))
        if abs(dot(t, axis)) > ra + rb - margin:
            return False
    return True


def grid_boxes(station_world, grid, next_station_world=None):
    """Crossbeam of one station (+ the two rails to the next station when given), as OBBs, per cpp:1258-1300.
    grid = {height_cm, beam_depth_cm, beam_width_cm, half_width_cm}. Station-frame maths, nominal section (the wear
    jitter is 0 on all six Structures: section_variation 0, twist 0, girders_v3_originals)."""
    h, d, w, hw = (float(grid[k]) for k in ("height_cm", "beam_depth_cm", "beam_width_cm", "half_width_cm"))
    q = station_world["rotation_xyzw"]
    o = station_world["location"]
    fx, fy, fz = axes(q)
    out = [{"name": "crossbeam", "box": {"centre": add(o, mul(fz, h)), "axes": [fx, fy, fz], "half": [w / 2, hw, d / 2]}}]
    if next_station_world is not None:
        o2 = next_station_world["location"]
        for side in (-1.0, 1.0):
            a = add(add(o, mul(fy, side * hw)), mul(fz, h + d))
            b = add(add(o2, mul(axes(next_station_world["rotation_xyzw"])[1], side * hw)), mul(fz, h + d))
            length = dist(a, b)
            if length < 1.0:
                continue
            along = norm(sub(b, a))
            rail_q = make_from_xz(along, fz)
            out.append({"name": "rail_%s" % ("neg" if side < 0 else "pos"),
                        "box": obb(mul(add(a, b), 0.5), rail_q, [length / 2, w / 2, d / 2])})
    return out


# ---- deterministic draws (one sha256 per (seed, guid, key); never a stream, never two draws in one expression) --
def h01(seed, guid, key):
    digest = hashlib.sha256(("FIXFOLLOW|%s|%s|%s" % (seed, str(guid).upper(), key)).encode("utf-8")).hexdigest()
    return int(digest[:13], 16) / float(16 ** 13)


def lerp(a, b, t):
    return a + (b - a) * t


# ---- rows -------------------------------------------------------------------------------------------------------
def is_kind(row, kind):
    return enum_name(row.get("kind")) == kind


def is_station(row):
    return enum_name(row.get("anchor")) == "STATION"


def is_fixture_bulb_mesh(mesh):
    mesh = asset_id(mesh) or ""
    return mesh.startswith(M.MESH_DIR + "/SM_Bulb_") or mesh.startswith(M.DERIVED_DIR + "/SM_FX_Bulb_")


def bulb_variant_of_mesh(mesh, derived_index):
    """SM_Bulb_<V> directly, or the derived SM_FX_Bulb_<V>_<hash> through the swap records' derived index."""
    mesh = asset_id(mesh) or ""
    if mesh.startswith(M.MESH_DIR + "/SM_Bulb_"):
        return mesh.rsplit("/", 1)[-1]
    spec = derived_index.get(mesh)
    if spec:
        return spec["variant"]
    tail = mesh.rsplit("/", 1)[-1]
    m = re.match(r"SM_FX_(Bulb_[A-Za-z0-9]+_[A-Za-z]+)_[0-9a-f]{8}$", tail)
    return "SM_" + m.group(1) if m else None


def light_lumens(row):
    """Paired light output in lumens, or None when not in lumens (then it is treated as WORKING: never relocated)."""
    lighting = row.get("lighting") or {}
    if enum_name(lighting.get("intensity_units")) != "LUMENS":
        return None
    return float(lighting.get("intensity", 0.0))


def glass_centre_world(row_t, fixture):
    return xf_point(row_t, fixture["glass_centre"])


# ---- snapshots (COUNT mode) ---------------------------------------------------------------------------------------
def snapshot_passage(passage, conductor=CONDUCTOR):
    """Newest on-disk rows per cue: the Meshy swap record's after_rows (7 Oct 08:2x) win, else the lighting scores
    record's after_rows. Inferred: Gary's later hand edits (e.g. P03 B10 glimmer rotated 7 Oct 23:08 UTC in the
    editor log) are NOT in any file; the live DRY re-reads every row."""
    cues, sources = {}, {}
    meshy = json.load(open(os.path.join(MESHY_DIR, "meshy_swap_record_%s.json" % passage), encoding="utf-8"))
    labels = {t["cue_guid"]: t["cue_label"] for t in meshy["plan"]["targets"]}
    scores_path = os.path.join(conductor, "lighting_scores_record_%s.json" % passage)
    scores = json.load(open(scores_path, encoding="utf-8")) if os.path.isfile(scores_path) else {"plan": {"targets": []}}
    order = []
    for t in scores["plan"]["targets"]:
        labels.setdefault(t["cue_guid"], t["cue_label"])
        order.append(t["cue_guid"])
        cues[t["cue_guid"]] = t["after_rows"]
        sources[t["cue_guid"]] = "lighting_scores_record_%s run %s" % (passage, scores.get("run"))
    for g, rows in meshy["after_rows"].items():
        if g not in cues:
            order.append(g)
        cues[g] = rows
        sources[g] = "meshy_swap_record_%s run %s" % (passage, meshy.get("run"))
    derived = {}
    for p in PASSAGES:
        path = os.path.join(MESHY_DIR, "meshy_swap_record_%s.json" % p)
        if os.path.isfile(path):
            rec = json.load(open(path, encoding="utf-8"))
            derived.update(rec["plan"].get("derived_meshes", {}))
    index = {t["cue_guid"]: t.get("show_index") for t in scores["plan"]["targets"]}
    index.update({t["cue_guid"]: t.get("show_index") for t in meshy["plan"]["targets"] if t.get("show_index") is not None})
    order = sorted(order, key=lambda g: (index.get(g) is None, index.get(g) or 0, order.index(g)))
    out = [{"guid": g, "label": labels.get(g, g), "show_index": index.get(g), "attachments": cues[g], "source": sources[g]}
           for g in order]
    return out, {"meshy_run": meshy.get("run"), "scores_run": scores.get("run"), "derived_index": derived,
                 "meshy_args": meshy.get("args", {}), "meshy_housing": meshy["plan"].get("housing", {})}


# ---- FOLLOW ---------------------------------------------------------------------------------------------------
def follow_placements(cues_in_station_order, pair_worlds, station_acrosses):
    """GatherFixturePlacements in Python: [(cue_guid, row)] in the C++ ISM order + their LightWorld."""
    out = []
    for cue in cues_in_station_order:
        pair_world = pair_worlds[cue["guid"]]
        for row in cue["attachments"]:
            if not (is_kind(row, "LIGHT") and row["enabled"]):
                continue
            if not is_station(row):
                continue
            light_world = xf_compose(row["relative_transform"], pair_world)
            out.append({"cue_guid": cue["guid"], "cue_label": cue.get("label"), "guid": row["guid"],
                        "label": row["label"], "light_world": light_world, "across": station_acrosses[cue["guid"]]})
    return out


def follow_plan(placements, ism_transforms, mesh_bounds, body_size, tol_cm=0.5):
    """Predicted housing per placement vs the live ISM instance at the same index. Returns the per-light table and
    the counts. ism_transforms may be None (offline: prediction only)."""
    lo, hi = mesh_bounds
    rows, stale = [], 0
    count_ok = ism_transforms is None or len(ism_transforms) == len(placements)
    for i, p in enumerate(placements):
        pose = housing_pose(p["light_world"], p["across"], lo, hi, body_size)
        entry = {"index": i, "cue": p["cue_label"], "guid": p["guid"], "label": p["label"],
                 "throw": [round(v, 5) for v in pose["throw"]],
                 "predicted": {"location": [round(v, 3) for v in pose["location"]],
                               "rotation_xyzw": [round(v, 6) for v in quat_canonical(pose["rotation_xyzw"])]}}
        if ism_transforms is not None and count_ok:
            live = ism_transforms[i]
            gap = corner_gap(pose, live, lo, hi)
            entry["corner_gap_cm"] = round(gap, 3)
            entry["aim_error_deg"] = round(aim_error_deg(live["rotation_xyzw"], pose["throw"]), 3)
            entry["stale"] = gap > tol_cm
            stale += entry["stale"]
        rows.append(entry)
    return {"lights": rows, "count": len(placements), "ism_count": None if ism_transforms is None else len(ism_transforms),
            "count_matches": count_ok, "stale": stale if ism_transforms is not None else None}


# ---- SCALE ----------------------------------------------------------------------------------------------------
SCALE_DEFAULTS = {
    "housing_factor": 3.0,              # x the CURRENT housing size (Gary: "about 3x")
    "expected_housing_scale": 1.0,      # current BodySizeCm / lantern bounds; refuses otherwise (no double apply)
    "bulb_factor": 3.0,                 # x the CURRENT bulb scale, about the glass centre
    "expected_bulb_scale": 3.2,         # the swap's scale; refuses any bulb not at it
    "scale_tol": 1.0e-3,
    "girder_margin_cm": 0.0,
}


def scale_plan(passage, cues, table, derived_index, housing_state, opts):
    """Pure SCALE planner. housing_state = {"lantern": SM_Lantern_*, "body_size_cm": [3]}. Bulb rows = every PROP row
    whose mesh is a Meshy bulb (SM_Bulb_* or a swap-derived SM_FX_Bulb_*), enabled or not, any label."""
    lantern = housing_state["lantern"]
    require(lantern in table, "HOUSING_NOT_A_MESHY_LANTERN|%s" % lantern)
    fixture = table[lantern]
    current = [a / b for a, b in zip(housing_state["body_size_cm"], fixture["size"])]
    require(all(abs(c - current[0]) <= opts["scale_tol"] * 10 for c in current), "HOUSING_NOT_UNIFORM|%s" % current)
    require(abs(current[0] - float(opts["expected_housing_scale"])) <= opts["scale_tol"] * 10,
            "HOUSING_SCALE_UNEXPECTED|live=%.4f|expected=%.4f (already scaled?)" % (current[0], opts["expected_housing_scale"]))
    new_scale = round(current[0] * float(opts["housing_factor"]), 4)
    housing = {"lantern": lantern, "mesh": fixture["mesh"], "scale_before": round(current[0], 4), "scale_after": new_scale,
               "body_size_before": list(housing_state["body_size_cm"]),
               "body_size_after": M.housing_size(fixture, new_scale),
               "lens_offset_before_cm": M.lens_offset_local(fixture, current[0]),
               "lens_offset_after_cm": M.lens_offset_local(fixture, new_scale)}
    targets, refused = [], []
    f = float(opts["bulb_factor"])
    for cue in cues:
        changes = []
        for row in cue["attachments"]:
            if not (is_kind(row, "PROP") and is_fixture_bulb_mesh(row.get("mesh"))):
                continue
            variant = bulb_variant_of_mesh(row.get("mesh"), derived_index)
            t = row["relative_transform"]
            s = t["scale"]
            if variant not in table or any(abs(v - float(opts["expected_bulb_scale"])) > opts["scale_tol"] for v in s):
                refused.append({"cue": cue["label"], "guid": row["guid"], "label": row["label"], "scale": s,
                                "variant": variant, "why": "VARIANT_UNKNOWN" if variant not in table else "SCALE_UNEXPECTED"})
                continue
            glass = glass_centre_world(t, table[variant])
            new_s = round(s[0] * f, 4)
            new_t = {"location": [round(v, 4) for v in sub(glass, quat_rotate(t["rotation_xyzw"],
                                                                              mul(table[variant]["glass_centre"], new_s)))],
                     "rotation_xyzw": list(t["rotation_xyzw"]), "scale": [new_s, new_s, new_s]}
            after = copy.deepcopy(row)
            after.pop("ext", None)
            after["relative_transform"] = new_t
            changes.append({"guid": row["guid"], "label": row["label"], "what": "BULB_SCALE", "variant": variant,
                            "scale_before": s[0], "scale_after": new_s, "after": after})
        if changes:
            targets.append({"cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue.get("show_index"),
                            "changes": changes})
    return {"op": "SCALE", "passage": passage, "opts": {k: opts[k] for k in sorted(SCALE_DEFAULTS)}, "housing": housing,
            "targets": targets, "refused": refused,
            "counts": {"cues": len(targets), "bulbs": sum(len(t["changes"]) for t in targets), "refused": len(refused)}}


def girder_report(placements, grid_by_cue, lo, hi, body_size, margin=0.0):
    """Housings (at body_size) that interpenetrate their own station's crossbeam or rails. grid_by_cue: {cue_guid:
    [{"name","box"}]} built with grid_boxes()."""
    hits = []
    for p in placements:
        pose = housing_pose(p["light_world"], p["across"], lo, hi, body_size)
        box = obb_from_fit(pose, lo, hi)
        for g in grid_by_cue.get(p["cue_guid"], []):
            if obb_overlap(box, g["box"], margin):
                hits.append({"cue": p["cue_label"], "label": p["label"], "guid": p["guid"], "girder": g["name"],
                             "housing_centre": [round(v, 1) for v in box["centre"]]})
    return hits


# ---- RELOCATE -------------------------------------------------------------------------------------------------
RELOCATE_DEFAULTS = {
    "seed": "20261007",
    "hang_fraction": 0.5,              # share of relocated bulbs that hang (the rest go on the ground)
    "hang_fraction_by_passage": {"P04": 0.35},   # P04: rain + wet slab -> more on the ground (Gary to confirm)
    "lane_half_width_cm": 150.0,       # the camera / cat lane kept clear
    "lateral_max_cm": 520.0,           # inside the wings (route-relative; wings sit at ~ +-600..700)
    "ground_x_range_cm": [-260.0, 220.0],
    "hang_x_range_cm": [-25.0, 25.0],  # under the bay's own crossbeam (cpp:1265-1272)
    "hang_glass_z_range_cm": [220.0, 650.0],
    "lying_fraction": 0.6,             # ground: lying on its side, else standing on its cap (glass up)
    "floor_z_cm": 0.0,                 # pair frame; the live DRY replaces it per bulb from the floor actors' bounds
    "working_lumens": 50.0,            # paired light above this = a WORKING practical: never relocated
    "paired_light": "DISABLE",         # DISABLE | KEEP (KEEP leaves a lantern + light where the bulb was)
    "cord_mm": 25.0,                   # cord section (cm x10) -- thin dark line from the structure's line material
    "glimmer": "HANG_AT_SPOT",         # HANG_AT_SPOT | GROUND_UNDER_SPOT | OFF
    "glimmer_bulb_scale": None,        # None = the passage's current Meshy bulb scale (3.2, or 9.6 after SCALE)
    "glimmer_mesh": "PASSAGE_DERIVED",  # PASSAGE_DERIVED (a tinted SM_FX bulb already in the passage) | FIXTURE
    "glow_mode": "FILAMENT_AND_POINT", # FILAMENT_AND_POINT | EMISSIVE_ONLY | OFF
    "emissive_full_intensity": 3.0,      # creative default; Gary approves from the preview / first live still
    "glow_flicker": "SLIGHT",           # STABLE | SLIGHT | FAIL
    "glow_flicker_rate_hz": 11.0,
    "glow_slight_depth": 0.08,
    "point_light_lumens": 24.0,          # dim reflection/specular helper owned by the bulb actor
    "point_light_attenuation_radius_cm": 450.0,
    "point_light_source_radius_cm": 8.0,
    "point_light_soft_source_radius_cm": 18.0,
    "point_light_temperature_kelvin": 2200.0,
    "cord_sway_mode": "DETERMINISTIC_SINE",  # DETERMINISTIC_SINE | STATIC
    "sway_yaw_amplitude_degrees": 2.5,
    "sway_pitch_amplitude_degrees": 1.5,
    "sway_period_seconds": 7.0,
    "sway_seed": 20261008,
    "grid": {"height_cm": 1150.0, "beam_depth_cm": 180.0, "beam_width_cm": 80.0, "half_width_cm": 1350.0},
}
GLIMMER_LIGHT_RE = re.compile(r"\bPRACTICAL_GLIMMER$")
GLIMMER_BODY_RE = re.compile(r"\bPRACTICAL_GLIMMER_BODY$")
GLIMMER_CAP_RE = re.compile(r"\bPRACTICAL_GLIMMER(_BODY)?_CAP$")


def cord_row_transform(bottom_z, top_z, x, y, cord_cm, cube_bounds=([-50.0] * 3, [50.0] * 3)):
    """A vertical bounds-fitted box from bottom_z to top_z (pair frame), section cord_cm."""
    require(top_z - bottom_z >= 1.0, "CORD_TOO_SHORT|%.1f..%.1f" % (bottom_z, top_z))
    lo, hi = cube_bounds
    size = [cord_cm, cord_cm, top_z - bottom_z]
    scale = [s / (b - a) for s, a, b in zip(size, lo, hi)]
    centre = [(a + b) * 0.5 for a, b in zip(lo, hi)]
    loc = [x - centre[0] * scale[0], y - centre[1] * scale[1], (bottom_z + top_z) * 0.5 - centre[2] * scale[2]]
    return {"location": [round(v, 4) for v in loc], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
            "scale": [round(v, 6) for v in scale]}


def bulb_pose_hanging(fixture, scale, glass_xyz):
    """Identity rotation (cap up, glass down, as the swap placed them); glass centre on glass_xyz."""
    rot = [0.0, 0.0, 0.0, 1.0]
    loc = sub(glass_xyz, quat_rotate(rot, mul(fixture["glass_centre"], scale)))
    cap_top = loc[2] + fixture["bounds_max"][2] * scale
    return {"location": [round(v, 4) for v in loc], "rotation_xyzw": rot, "scale": [scale] * 3}, cap_top


def bulb_pose_ground(fixture, scale, x, y, floor_z, lying, yaw_deg):
    """Lying: 90 deg about X then yaw; standing: on its cap (180 deg about X) then yaw. Rests the lowest bound corner on
    the floor (exact for the round glass lying and for the flat cap standing)."""
    tilt = quat_axis_angle([1.0, 0.0, 0.0], 90.0 if lying else 180.0)
    rot = quat_norm(quat_mul(quat_axis_angle([0.0, 0.0, 1.0], yaw_deg), tilt))
    corners = [quat_rotate(rot, mul(c, scale)) for c in bounds_corners(fixture["bounds_min"], fixture["bounds_max"])]
    min_z = min(c[2] for c in corners)
    # put the bounds' XY centre on (x, y)
    cx = sum(c[0] for c in corners) / 8.0
    cy = sum(c[1] for c in corners) / 8.0
    loc = [x - cx, y - cy, floor_z - min_z]
    return {"location": [round(v, 4) for v in loc], "rotation_xyzw": [round(v, 9) for v in rot], "scale": [scale] * 3}


def _row_after(row, keep_ext=False, **fields):
    after = copy.deepcopy(row)
    if not keep_ext:
        after.pop("ext", None)
    after.update(fields)
    return after


def _body_modes(row, fixture, opts, cord_guid=None):
    """One relocated bare bulb's complete Body settings. Glow and sway are opt-in arguments; defaults are creative
    proposals, not accepted look values. The bulb-owned point light avoids a Light attachment and therefore a can."""
    after = copy.deepcopy(row)
    ext = after.setdefault("ext", {})
    body = ext.setdefault("body", {})
    glow = opts["glow_mode"]
    if glow != "OFF":
        body.update({
            "follow_light": True,
            "light_attachment_guid": "0" * 32,
            "intensity_parameter": "Intensity",
            "full_intensity": float(opts["emissive_full_intensity"]),
            "flicker": opts["glow_flicker"],
            "seed": int(opts["sway_seed"]),
            "slight_depth": float(opts["glow_slight_depth"]),
            "flicker_rate_hz": float(opts["glow_flicker_rate_hz"]),
            "flicker_also_drives_light": False,
            "emit_point_light": glow == "FILAMENT_AND_POINT",
            "point_light_lumens": float(opts["point_light_lumens"]),
            "point_light_attenuation_radius_cm": float(opts["point_light_attenuation_radius_cm"]),
            "point_light_source_radius_cm": float(opts["point_light_source_radius_cm"]),
            "point_light_soft_source_radius_cm": float(opts["point_light_soft_source_radius_cm"]),
            "point_light_temperature_kelvin": float(opts["point_light_temperature_kelvin"]),
        })
    body.update({
        "swing_on_cord": bool(cord_guid) and opts["cord_sway_mode"] == "DETERMINISTIC_SINE",
        "cord_attachment_guid": str(cord_guid or "0" * 32),
        "swing_yaw_amplitude_degrees": float(opts["sway_yaw_amplitude_degrees"]),
        "swing_pitch_amplitude_degrees": float(opts["sway_pitch_amplitude_degrees"]),
        "swing_period_seconds": float(opts["sway_period_seconds"]),
        "sway_seed": int(opts["sway_seed"]),
    })
    return after


def _label_index(rows):
    out = {}
    for r in rows:
        out.setdefault(r["label"], []).append(r)
    return out


def relocate_plan(passage, cues, table, derived_index, opts, floor_z_by_spot=None, cord_mesh=None, cord_bounds=None):
    """Pure RELOCATE planner.
    - eligible bulb = PROP row with a Meshy bulb mesh, label *_BODY, paired by label with exactly one LIGHT row on the
      same cue whose output <= working_lumens (else WORKING, untouched);
    - each eligible bulb -> HANG (glass z in range, x under the crossbeam, cord up to the crossbeam underside) or
      GROUND (lying / standing on the floor), lateral side +-, |y| in [lane, lateral_max], all from h01 draws;
    - cord row = the bulb's own *_CAP row when it exists (P03/P05), else the retired paired LIGHT row re-kinded to PROP;
      GROUND bulbs: the paired light is disabled (paired_light DISABLE) and any cap stays as it was;
    - glimmer: each *PRACTICAL_GLIMMER_BODY row -> a bare bulb at its light's spot (HANG_AT_SPOT: cord from the
      retired glimmer LIGHT row; GROUND_UNDER_SPOT: on the floor under it, the light disabled); *GLIMMER*_CAP -> off.
    floor_z_by_spot: optional {guid: z} from the live floor read; cord_mesh: object path (live) or a placeholder."""
    floor_z_by_spot = floor_z_by_spot or {}
    seed = opts["seed"]
    hang_fraction = float(opts.get("hang_fraction_by_passage", {}).get(passage, opts["hang_fraction"]))
    grid = opts["grid"]
    cord_top = float(grid["height_cm"]) - float(grid["beam_depth_cm"]) * 0.5     # crossbeam underside (pair frame)
    cord_cm = float(opts["cord_mm"]) / 10.0
    cord_mesh = cord_mesh or "/Engine/BasicShapes/Cube.Cube"
    cord_bounds = cord_bounds or ([-50.0] * 3, [50.0] * 3)
    lane, lat_max = float(opts["lane_half_width_cm"]), float(opts["lateral_max_cm"])
    require(0.0 <= lane < lat_max, "LATERAL_RANGE_BAD")
    targets, working, skipped, glimmers = [], [], [], []
    passage_scales, passage_derived = [], []
    for cue in cues:
        for r in cue["attachments"]:
            if is_kind(r, "PROP") and is_fixture_bulb_mesh(r.get("mesh")):
                passage_scales.append(round(r["relative_transform"]["scale"][0], 4))
                if (asset_id(r.get("mesh")) or "").startswith(M.DERIVED_DIR + "/"):
                    passage_derived.append(asset_id(r.get("mesh")))
    passage_derived = sorted(set(passage_derived))
    now_scale = (max(set(passage_scales), key=passage_scales.count) if passage_scales else 3.2)
    glimmer_scale = float(opts["glimmer_bulb_scale"] or now_scale)
    for cue in cues:
        rows = cue["attachments"]
        by_label = _label_index(rows)
        changes = []
        for body in rows:
            if not (is_kind(body, "PROP") and body["label"].endswith("_BODY") and is_fixture_bulb_mesh(body.get("mesh"))):
                continue
            base = body["label"][:-len("_BODY")]
            lights = [r for r in by_label.get(base, []) if is_kind(r, "LIGHT")]
            caps = [r for r in by_label.get(base + "_CAP", []) if is_kind(r, "PROP")]
            variant = bulb_variant_of_mesh(body.get("mesh"), derived_index)
            if len(lights) != 1 or variant not in table or len(caps) > 1:
                skipped.append({"cue": cue["label"], "guid": body["guid"], "label": body["label"],
                                "why": "PAIRED_LIGHTS_%d" % len(lights) if len(lights) != 1 else
                                ("VARIANT_UNKNOWN" if variant not in table else "CAPS_%d" % len(caps))})
                continue
            light = lights[0]
            lm = light_lumens(light)
            if lm is None or (light["enabled"] and lm > float(opts["working_lumens"])):
                working.append({"cue": cue["label"], "guid": body["guid"], "label": body["label"],
                                "light_guid": light["guid"], "lumens": lm})
                continue
            fixture = table[variant]
            scale = round(body["relative_transform"]["scale"][0], 4)
            g = body["guid"]
            hang = h01(seed, g, "mode") < hang_fraction
            side = -1.0 if h01(seed, g, "side") < 0.5 else 1.0
            y = side * lerp(lane, lat_max, h01(seed, g, "lateral"))
            if hang:
                x = lerp(*opts["hang_x_range_cm"], h01(seed, g, "x"))
                z = lerp(*opts["hang_glass_z_range_cm"], h01(seed, g, "z"))
                pose, cap_top = bulb_pose_hanging(fixture, scale, [x, y, z])
                cord_source = caps[0] if caps else light
                cord = _row_after(cord_source, kind="<InfinityAttachmentKind.PROP: 0>", enabled=True,
                                  mesh=cord_mesh, relative_transform=cord_row_transform(cap_top, cord_top, x, y, cord_cm, cord_bounds))
                bulb_after = _body_modes(_row_after(body, keep_ext=True, relative_transform=pose), fixture, opts, cord_source["guid"])
                changes.append({"guid": g, "label": body["label"], "what": "BULB_HANG", "variant": variant,
                                "glass": [round(x, 2), round(y, 2), round(z, 2)],
                                "after": bulb_after, "cord_guid": cord_source["guid"]})
                changes.append({"guid": cord_source["guid"], "label": cord_source["label"],
                                "what": "CORD_FROM_CAP" if caps else "CORD_FROM_RETIRED_LIGHT", "after": cord})
                if caps and opts["paired_light"] == "DISABLE" and light["enabled"]:
                    changes.append({"guid": light["guid"], "label": light["label"], "what": "LIGHT_DISABLED",
                                    "after": _row_after(light, enabled=False)})
            else:
                x = lerp(*opts["ground_x_range_cm"], h01(seed, g, "x"))
                lying = h01(seed, g, "lying") < float(opts["lying_fraction"])
                yaw = 360.0 * h01(seed, g, "yaw")
                fz = float(floor_z_by_spot.get(g, opts["floor_z_cm"]))
                pose = bulb_pose_ground(fixture, scale, x, y, fz, lying, yaw)
                bulb_after = _body_modes(_row_after(body, keep_ext=True, relative_transform=pose), fixture, opts)
                changes.append({"guid": g, "label": body["label"], "what": "BULB_GROUND_" + ("LYING" if lying else "STANDING"),
                                "variant": variant, "glass": [round(x, 2), round(y, 2), round(fz, 2)],
                                "after": bulb_after})
                if opts["paired_light"] == "DISABLE" and light["enabled"]:
                    changes.append({"guid": light["guid"], "label": light["label"], "what": "LIGHT_DISABLED",
                                    "after": _row_after(light, enabled=False)})
        # glimmer spots
        if opts["glimmer"] != "OFF":
            for body in rows:
                if not (is_kind(body, "PROP") and GLIMMER_BODY_RE.search(body["label"])):
                    continue
                base = body["label"][:-len("_BODY")]
                lights = [r for r in by_label.get(base, []) if is_kind(r, "LIGHT")]
                if len(lights) != 1:
                    skipped.append({"cue": cue["label"], "guid": body["guid"], "label": body["label"],
                                    "why": "GLIMMER_LIGHTS_%d" % len(lights)})
                    continue
                light = lights[0]
                g = body["guid"]
                variant = M.bulb_variant(light["guid"], seed, list(M.BULBS))
                fixture = table[variant]
                mesh = fixture["mesh"]
                if opts["glimmer_mesh"] == "PASSAGE_DERIVED":
                    pool = [d for d in passage_derived if derived_index.get(d, {}).get("variant") == variant]
                    if pool:
                        mesh = pool[int(h01(seed, g, "tint") * len(pool)) % len(pool)]
                spot = list(light["relative_transform"]["location"])
                entry = {"cue": cue["label"], "light_guid": light["guid"], "light_label": light["label"],
                         "body_guid": g, "body_label": body["label"], "spot": [round(v, 2) for v in spot],
                         "variant": variant, "mesh": mesh, "light_enabled_before": light["enabled"]}
                if opts["glimmer"] == "HANG_AT_SPOT":
                    pose, cap_top = bulb_pose_hanging(fixture, glimmer_scale, spot)
                    bulb_after = _body_modes(_row_after(body, keep_ext=True, mesh=object_path(mesh), relative_transform=pose), fixture,
                                             opts, light["guid"])
                    changes.append({"guid": g, "label": body["label"], "what": "GLIMMER_TO_BULB_HANG", "variant": variant,
                                    "glass": entry["spot"],
                                    "after": bulb_after, "cord_guid": light["guid"]})
                    changes.append({"guid": light["guid"], "label": light["label"], "what": "GLIMMER_LIGHT_TO_CORD",
                                    "after": _row_after(light, kind="<InfinityAttachmentKind.PROP: 0>", enabled=True,
                                                        mesh=cord_mesh,
                                                        relative_transform=cord_row_transform(cap_top, cord_top, spot[0],
                                                                                              spot[1], cord_cm, cord_bounds))})
                    entry["mode"] = "HANG_AT_SPOT"
                else:
                    fz = float(floor_z_by_spot.get(g, opts["floor_z_cm"]))
                    lying = h01(seed, g, "lying") < float(opts["lying_fraction"])
                    pose = bulb_pose_ground(fixture, glimmer_scale, spot[0], spot[1], fz, lying, 360.0 * h01(seed, g, "yaw"))
                    bulb_after = _body_modes(_row_after(body, keep_ext=True, mesh=object_path(mesh), relative_transform=pose), fixture, opts)
                    changes.append({"guid": g, "label": body["label"], "what": "GLIMMER_TO_BULB_GROUND", "variant": variant,
                                    "glass": [round(spot[0], 2), round(spot[1], 2), fz],
                                    "after": bulb_after})
                    if light["enabled"]:
                        changes.append({"guid": light["guid"], "label": light["label"], "what": "GLIMMER_LIGHT_DISABLED",
                                        "after": _row_after(light, enabled=False)})
                    entry["mode"] = "GROUND_UNDER_SPOT"
                glimmers.append(entry)
            for cap in rows:
                if is_kind(cap, "PROP") and GLIMMER_CAP_RE.search(cap["label"]) and cap["enabled"]:
                    changes.append({"guid": cap["guid"], "label": cap["label"], "what": "GLIMMER_CAP_DISABLED",
                                    "after": _row_after(cap, enabled=False)})
        seen = [c["guid"] for c in changes]
        require(len(seen) == len(set(seen)), "ROW_PLANNED_TWICE|%s" % cue["label"])
        if changes:
            targets.append({"cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue.get("show_index"),
                            "changes": changes})
    kinds = {}
    for t in targets:
        for c in t["changes"]:
            kinds[c["what"]] = kinds.get(c["what"], 0) + 1
    return {"op": "RELOCATE", "passage": passage, "opts": copy.deepcopy(opts), "hang_fraction": hang_fraction,
            "cord_top_z_cm": cord_top, "cord_mesh": cord_mesh, "cord_bounds": [list(cord_bounds[0]), list(cord_bounds[1])], "bulb_scale_now": now_scale, "glimmer_bulb_scale": glimmer_scale,
            "targets": targets, "working_practicals": working, "skipped": skipped, "glimmers": glimmers,
            "counts": {"cues": len(targets), "rows": sum(len(t["changes"]) for t in targets), "by_kind": kinds,
                       "working": len(working), "skipped": len(skipped), "glimmer_spots": len(glimmers)}}


def relocate_checks(plan, table):
    """Invariants a plan must satisfy (also used by the harness): lane clear, inside the lateral max, ground bulbs
    rest on the floor, cords reach from the cap to the beam underside and are vertical."""
    bad = []
    lane, lat_max = plan["opts"]["lane_half_width_cm"], plan["opts"]["lateral_max_cm"]
    for t in plan["targets"]:
        for c in t["changes"]:
            if c["what"].startswith("BULB_"):
                y = c["glass"][1]
                if not (lane - 1e-6 <= abs(y) <= lat_max + 1e-6):
                    bad.append(("LATERAL", c["label"], y))
            if c["what"].startswith(("BULB_", "GLIMMER_TO_BULB_")):
                body = (c["after"].get("ext") or {}).get("body") or {}
                if plan["opts"]["glow_mode"] != "OFF":
                    if not body.get("follow_light") or bool(body.get("emit_point_light")) != (
                            plan["opts"]["glow_mode"] == "FILAMENT_AND_POINT"):
                        bad.append(("GLOW", c["label"], body.get("emit_point_light")))
                hanging = "HANG" in c["what"]
                want_sway = hanging and plan["opts"]["cord_sway_mode"] == "DETERMINISTIC_SINE"
                if bool(body.get("swing_on_cord")) != want_sway:
                    bad.append(("SWAY", c["label"], body.get("swing_on_cord")))
                if want_sway and body.get("cord_attachment_guid") != c.get("cord_guid"):
                    bad.append(("CORD_LINK", c["label"], body.get("cord_attachment_guid")))
            if c["what"].startswith(("CORD_", "GLIMMER_LIGHT_TO_CORD")):
                tr = c["after"]["relative_transform"]
                lo, hi = plan["cord_bounds"]
                top = tr["location"][2] + hi[2] * tr["scale"][2]
                if abs(top - plan["cord_top_z_cm"]) > 0.01 or tr["rotation_xyzw"] != [0.0, 0.0, 0.0, 1.0]:
                    bad.append(("CORD", c["label"], top))
    return bad


# ---- generic scope / revert (row-level, any change kind) --------------------------------------------------------
def expected_after(before_all, plan):
    result = copy.deepcopy(before_all)
    for t in plan["targets"]:
        repl = {c["guid"]: c["after"] for c in t["changes"]}
        rows = result[t["cue_guid"]]
        hit = 0
        for i, row in enumerate(rows):
            if row["guid"] in repl:
                ext = row.get("ext")
                rows[i] = copy.deepcopy(repl[row["guid"]])
                if ext is not None and "ext" not in rows[i]:
                    rows[i]["ext"] = ext
                hit += 1
        require(hit == len(repl), "PLAN_GUIDS_NOT_IN_CUE|%s|%d/%d" % (t["cue_guid"], hit, len(repl)))
    return result


def scope_problems(want_all, live_all):
    return M.scope_problems(want_all, live_all)


def check_scope(want_all, live_all, side):
    problems = scope_problems(want_all, live_all)
    require(not problems, "SCOPE_CHANGED|side=%s|count=%d|%s" % (side, len(problems), canonical(problems)[:3000]))


def revert_model(record, live_all):
    return M.revert_model(record, live_all)


def plan_sha(plan):
    return sha(plan)


# ---- scores config (glimmer removal) ---------------------------------------------------------------------------
def scores_without_glimmer(scores):
    """lighting_scores.json with the PRACTICAL_GLIMMER instrument removed from every local look (only GAP has it), the
    GAP intent re-worded, and a provenance note. A re-APPLY of the scores tool then authors no glimmer light and no
    GLIMMER_BODY. Returns (new, removed_slots_by_look)."""
    new = copy.deepcopy(scores)
    removed = {}
    for name, look in new.get("local_looks", {}).items():
        keep = [i for i in look.get("instruments", []) if i.get("slot") != "PRACTICAL_GLIMMER"]
        if len(keep) != len(look.get("instruments", [])):
            removed[name] = [i["slot"] for i in look["instruments"] if i.get("slot") == "PRACTICAL_GLIMMER"]
            look["instruments"] = keep
            look["intent"] = (look.get("intent", "") + " [7 Oct, Gary: glimmer practical REMOVED; the spot holds a bare "
                              "Meshy bulb authored by FixturesFollow RELOCATE, not by this tool]")
    new["glimmer_removed_note"] = ("Gary 7 Oct: remove every PRACTICAL_GLIMMER light + GLIMMER_BODY + GLIMMER_CAP and put "
                                   "a bare bulb in each spot. Show rows: Saved/CodexConductor/FixturesFollow "
                                   "(RELOCATE). This config edit only stops a future scores re-APPLY re-creating them.")
    return new, removed
