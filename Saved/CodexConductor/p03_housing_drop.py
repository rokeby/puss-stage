"""P03 housing drop: DRY / APPLY / REVERT (Gary 5 Oct, "Move P03 housings down").

The underpass Phase A swap gives the gridiron 90 cm plate girders (BeamDepthCm
34 -> 90 at HeightCm 1150; underpass_rig_apply.py:70). Its DRY run
(underpass_rig_dry_UPRIG-20261005-081407.json) found 13 P03 lamp housings that
the new band reaches and the old band did not (clearance(),
underpass_rig_apply.py:445-456). This tool lowers the Show LIGHT ATTACHMENTS
those housings sit behind, by one uniform pure-Z relative translation, so the
re-fitted housings clear the band.

Proof tiers (AGENTS.md):
* declaration-proven: one housing per enabled, Light-kind, Station-anchored
  attachment of every WingPair cue at a structure station, placed at
  LightWorld = RelativeTransform * (OccurrenceOffset * StationWorld)
  (InfinityStageStructureActor.cpp:75-111); the body centre is
  LightWorld.Location - Throw * BodySize.X/2, rotated MakeFromXZ(Throw, Up)
  (MakeFromXY(Throw, Across) when |Throw.Z| > 0.98) and fitted by bounds
  (.cpp:1349-1361, FitMeshToTimber .cpp:118-131). Instances are added in
  placement order (.cpp:1349-1396). The structure signature hashes every
  LightWorld (.cpp:165-185) so a moved light makes IsStructureCurrent() false
  until MaterializeStructure() re-fits (.h:685-703). Cross beams are centred
  at StationOrigin + Up*HeightCm, BeamWidthCm along the route (.cpp:666-683).
  Fixture settings: .h:384-402 (BodySizeCm 45x32x32 default).
* inferred (the first live DRY confirms each): GatherStations' Python return
  shape (handled for None / (stations, error) / (ok, stations, error));
  StructBase.export_text() on FInfinityShowCue (used by light_guid_audit.py on
  attachments, so measured there for attachments, not for whole cues);
  FTransform translation round-trips doubles exactly through Python.

Modes via runpy init_globals (see p03_housing_drop_run.py):
  P03_HOUSING_DROP_MODE            DRY (default) | APPLY | REVERT
  P03_HOUSING_DROP_CONFIRM         "APPLY P03" / "REVERT P03" (required for writes)
  P03_HOUSING_DROP_ACK_RECORDS     foreign active record paths the operator accepts
  P03_HOUSING_DROP_EXTRA_LIGHT_GUIDS  extra attachment GUIDs to drop with the live set
  P03_HOUSING_DROP_TOP_CONVENTION  BOX (default: highest corner of the rotated
                                   housing box) | AXIS (centre + BodySize.Z/2,
                                   the convention clearance() and the C++ line
                                   maths use; lower than BOX for a pitched lamp)

Write pattern follows lighting_scores_apply.py: it loads the P04 tool module
(``tool``) through lighting_scores_apply.load_p04_tool(), never via import.

6 Oct: LIVE SOURCE. The housing points used to come from the underpass DRY
file above, which pinned the live gridiron at the pre-Phase-A depth 34; once
Phase A went live on P03 (underpass_rig_applied_index.json run
UPRIG-20261005-085951) every re-apply refused DRY_SOURCE_STALE|beam_depth_cm
(report p03_housing_drop_report_DRY_20261006-023555.json). A fresh underpass
DRY cannot replace it: clearance() keeps only housings the new band reaches
AND the old band did not, with old depth = the live depth (underpass_rig_apply.py
:445-456, :486), so with 90 live it returns []. live_points() now selects the
housings from the live structure with this tool's own in-band rule (the
other_housings_in_new_band test below), refuses unless Phase A is live and the
fixture count matches the ISM, and check_approved_set() refuses unless the
targets are exactly the 14 Rig Slash attachments applied on 5 Oct (13 DRY
points + extra Wing 010, run 20261005-085813). Every downstream gate (mapping,
ambiguity, instance fit, band drift, frame, drop limits, scope, export,
revert) is unchanged.
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import math
import os
import re
import sys
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
SCORES_TOOL_PATH = os.path.join(HERE, "lighting_scores_apply.py")
RECORD_PATH = os.path.join(HERE, "p03_housing_drop_record.json")
VALID_MODES = ("DRY", "APPLY", "REVERT")
TOP_CONVENTIONS = ("BOX", "AXIS")

PASSAGE_KEY = "P03"
PASSAGE_ACTOR_PREFIX = "Passage 03"
STRUCTURE_LABEL = "Infinity Stage - Structure 03"
EXPECTED_HOUSINGS = 14   # live in-band set (BOX); was 13 DRY points + 1 extra on 5 Oct
# The 14 Rig Slash attachments Gary's 5 Oct drop moved (p03_housing_drop_record.json
# .reverted-20261006-023409, plan.target_attachment_guids). A different live set is a
# new decision, so it refuses rather than silently dropping other lamps.
APPROVED_TARGET_GUIDS = frozenset((
    "02C239D14E23CD5512F451B69C617737", "0F3FD3F846A35A2F05D4B7A32F5D7F01", "3A786C61439BB242E0E1D58B42391832",
    "3FACD8E44D4FDFD87CF919AEE2CDC4AB", "4E63D1B24A36ACF14A2C36B32A70B8C0", "52D41212415A6CF53800968117895B89",
    "681420B0499A9FA5BDF4118939AE527C", "6B830737426981679115C5A0D8B5D984", "80282D394589898793525A8F3EBA9013",
    "9DA65BFE497AE1CE97A41B9C7938F84C", "A9ED0FFA4491A6425BF5E19918B43F13", "C6D207F34C97DD2F19259DB9BB7BE04E",
    "D2E6323C4C87C7AC728829BE579DC6ED", "E709499949DB55D6CB6EF1A0A2A46948"))
NEW_BEAM_DEPTH_CM = 90.0   # underpass_rig_apply.py:70 PHASE_A
NEW_BEAM_WIDTH_CM = 40.0   # underpass_rig_apply.py:70 PHASE_A
EXPECTED_BAND_LO_CM = 1105.0
BAND_LO_TOLERANCE_CM = 2.0
CLEARANCE_CM = 5.0
MATCH_TOLERANCE_CM = 1.0      # DRY rounds each axis to 1 cm: worst case 0.87 cm
AMBIGUITY_RADIUS_CM = 5.0
INSTANCE_TOLERANCE_CM = 0.5
FRAME_VERTICAL_MIN = 0.999
DROP_QUANTUM_CM = 0.1
MAX_DROP_CM = 60.0
FIXTURE_TAG = "InfinityStage.Structure.Fixtures"   # InfinityStageStructureActor.cpp:24
SUCCESS_TESTS = ("run_saved_master_test_request.json", "run_scene_cut_test_request.json")


class HousingDropError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise HousingDropError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Plain transform maths (FTransform semantics, positive scale).
# --------------------------------------------------------------------------
def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _mul(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    length = math.sqrt(_dot(a, a))
    require(length > 1.0e-9, "ZERO_VECTOR")
    return [a[0] / length, a[1] / length, a[2] / length]


def _dist(a, b):
    return math.sqrt(_dot(_sub(a, b), _sub(a, b)))


def quat_rotate(q, v):
    x, y, z, w = (float(c) for c in q)
    tx = 2.0 * (y * v[2] - z * v[1])
    ty = 2.0 * (z * v[0] - x * v[2])
    tz = 2.0 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx)]


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def compose(child, parent):
    """FTransform child * parent (child expressed in parent's frame)."""
    scaled = [child["location"][i] * parent["scale"][i] for i in range(3)]
    return {
        "location": _add(quat_rotate(parent["rotation_xyzw"], scaled), parent["location"]),
        "rotation_xyzw": quat_mul(parent["rotation_xyzw"], child["rotation_xyzw"]),
        "scale": [child["scale"][i] * parent["scale"][i] for i in range(3)],
    }


def unit_axis(transform, index):
    axis = [0.0, 0.0, 0.0]
    axis[index] = float(transform["scale"][index])
    return _norm(quat_rotate(transform["rotation_xyzw"], axis))


def housing_axes(throw, across):
    """FRotationMatrix::MakeFromXZ(Throw, Up) / MakeFromXY(Throw, Across), .cpp:1355-1357."""
    x_axis = _norm(throw)
    if abs(x_axis[2]) > 0.98:
        z_axis = _norm(_cross(x_axis, _norm(across)))
        y_axis = _cross(z_axis, x_axis)
    else:
        y_axis = _norm(_cross([0.0, 0.0, 1.0], x_axis))
        z_axis = _cross(x_axis, y_axis)
    return x_axis, y_axis, z_axis


def housing_geometry(light_world, station_world, structure):
    """Where the C++ puts this light's housing (.cpp:1349-1376)."""
    size = [max(1.0, float(v)) for v in structure["body_size_cm"]]
    bounds_min = structure["body_mesh_bounds"]["min"]
    bounds_max = structure["body_mesh_bounds"]["max"]
    mesh_size = [float(bounds_max[i]) - float(bounds_min[i]) for i in range(3)]
    bounds_centre = [(float(bounds_max[i]) + float(bounds_min[i])) * 0.5 for i in range(3)]
    throw = unit_axis(light_world, 0)
    across = unit_axis(station_world, 1)
    axes = housing_axes(throw, across)
    centre = _sub(light_world["location"], _mul(throw, size[0] * 0.5))
    scale = [size[i] / mesh_size[i] if mesh_size[i] > 1.0e-8 else 1.0 for i in range(3)]
    pivot_local = [bounds_centre[i] * scale[i] for i in range(3)]
    pivot = _add(_add(_mul(axes[0], pivot_local[0]), _mul(axes[1], pivot_local[1])),
                 _mul(axes[2], pivot_local[2]))
    half_z = sum(abs(axes[k][2]) * size[k] * 0.5 for k in range(3))
    route = unit_axis(station_world, 0)
    half_route = sum(abs(_dot(axes[k], route)) * size[k] * 0.5 for k in range(3))
    origin = station_world["location"]
    return {
        "centre": centre,
        "instance_location": _sub(centre, pivot),
        "top_axis": centre[2] + size[2] * 0.5,
        "top_box": centre[2] + half_z,
        "bottom_box": centre[2] - half_z,
        "route_offset_cm": _dot(_sub(centre, origin), route),
        "route_half_extent_cm": half_route,
        "lateral_cm": abs(_dot(_sub(centre, origin), across)),
        "throw": throw,
    }


def housing_top(geometry, convention):
    require(convention in TOP_CONVENTIONS, "TOP_CONVENTION_INVALID|" + str(convention))
    return geometry["top_box"] if convention == "BOX" else geometry["top_axis"]


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


# --------------------------------------------------------------------------
# Placement replication (GatherFixturePlacements, .cpp:75-111).
# --------------------------------------------------------------------------
def gather_placements(plain):
    guids = [cue["guid"] for cue in plain["cues"]]
    require(len(guids) == len(set(guids)), "DUPLICATE_CUE_GUID")
    by_guid = {cue["guid"]: cue for cue in plain["cues"]}
    placements, moving = [], 0
    for station_index, station in enumerate(plain["stations"]):
        cue = by_guid.get(station["cue_guid"])
        if cue is None or _enum_name(cue["type"]) not in ("WING_PAIR", "WINGPAIR"):
            continue
        pair_world = compose(cue["occurrence_offset"], station["world"])
        for attachment_index, row in enumerate(cue["attachments"]):
            if not row["enabled"] or _enum_name(row["kind"]) != "LIGHT":
                continue
            if _enum_name(row["anchor"]) != "STATION":
                moving += 1
                continue
            light_world = compose(row["relative_transform"], pair_world)
            placements.append({
                "placement_index": len(placements),
                "station_index": station_index,
                "cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue["show_index"],
                "attachment_guid": row["guid"], "attachment_label": row["label"],
                "attachment_index": attachment_index,
                "relative_location": list(row["relative_transform"]["location"]),
                "pair_world": pair_world, "light_world": light_world,
                "geometry": housing_geometry(light_world, station["world"], plain["structure"]),
            })
    return placements, moving


def check_instances(placements, instances):
    """The live ISM must be exactly the placements the maths predicts, in order."""
    require(len(instances) == len(placements), "INSTANCE_COUNT_MISMATCH|live=%d|predicted=%d"
            % (len(instances), len(placements)))
    worst = 0.0
    for placement, live in zip(placements, instances):
        error = _dist(placement["geometry"]["instance_location"], [float(v) for v in live])
        worst = max(worst, error)
        require(error <= INSTANCE_TOLERANCE_CM, "INSTANCE_GEOMETRY_MISMATCH|placement=%d|label=%s|error_cm=%.3f"
                % (placement["placement_index"], placement["attachment_label"], error))
    return worst


def map_points(points, placements):
    """Each DRY housing point -> exactly one placement; no placement twice."""
    mapping = []
    for point in points:
        distances = sorted((_dist(p["geometry"]["instance_location"], point), p["placement_index"])
                           for p in placements)
        near = [d for d in distances if d[0] <= AMBIGUITY_RADIUS_CM]
        require(distances and distances[0][0] <= MATCH_TOLERANCE_CM,
                "HOUSING_NO_MATCH|point=%s|nearest_cm=%s" % (point, distances[0][0] if distances else None))
        require(len(near) == 1, "HOUSING_AMBIGUOUS|point=%s|candidates=%d" % (point, len(near)))
        mapping.append(distances[0][1])
    require(len(set(mapping)) == len(mapping), "HOUSING_MAPPED_TWICE|indices=%s" % mapping)
    return mapping


def live_points(plain, convention="BOX"):
    """Housing points read from the LIVE structure (replaces the stale underpass DRY file).

    Gates carried over from the old load_dry_points: Phase A must be what the band
    maths assumes (was DRY_SOURCE_PHASE_A_CHANGED); the source must describe the
    current fixtures (was DRY_SOURCE_STALE|fixture_body_count); points are 3-vectors.
    Selection = the in-band test build_plan() already uses for
    other_housings_in_new_band: BOX/AXIS top above band_lo - clearance and the box
    bottom below band_lo + depth, against the housing's own station's Phase A band."""
    convention = str(convention or "BOX").upper()
    require(convention in TOP_CONVENTIONS, "TOP_CONVENTION_INVALID|" + convention)
    structure = plain["structure"]
    depth, width = float(structure["gridiron_depth_cm"]), float(structure["gridiron_width_cm"])
    require(depth == NEW_BEAM_DEPTH_CM and width == NEW_BEAM_WIDTH_CM,
            "PHASE_A_NOT_LIVE|depth=%s|width=%s|need=%s/%s" % (depth, width, NEW_BEAM_DEPTH_CM, NEW_BEAM_WIDTH_CM))
    require(int(structure["fixture_body_count"]) == len(plain["instances"]),
            "FIXTURE_COUNT_STALE|fixture_body_count=%s|ism_instances=%d"
            % (structure["fixture_body_count"], len(plain["instances"])))
    placements, unused = gather_placements(plain)
    points = []
    for placement in placements:
        geometry = placement["geometry"]
        lo = band_lo(placement, structure, plain)
        if housing_top(geometry, convention) > lo - CLEARANCE_CM and geometry["bottom_box"] < lo + NEW_BEAM_DEPTH_CM:
            points.append([float(v) for v in geometry["instance_location"]])
    require(all(len(p) == 3 for p in points), "LIVE_POINT_SHAPE")
    return points


def check_approved_set(plan, approved=APPROVED_TARGET_GUIDS):
    """The planned targets must be exactly the approved attachments: no more, no fewer."""
    planned, approved = set(plan["target_attachment_guids"]), set(approved)
    require(planned == approved, "TARGET_SET_NOT_APPROVED|missing=%s|unapproved=%s"
            % (sorted(approved - planned), sorted(planned - approved)))
    return sorted(planned)


def band_lo(placement, structure, plain):
    station = plain["stations"][placement["station_index"]]["world"]
    up = unit_axis(station, 2)
    cross = _add(station["location"], _mul(up, structure["gridiron_height_cm"]))
    return cross[2] - NEW_BEAM_DEPTH_CM * 0.5


def vertical_factor(pair_world):
    """World Z moved per cm of relative Z (pure-Z relative translation)."""
    moved = quat_rotate(pair_world["rotation_xyzw"], [0.0, 0.0, float(pair_world["scale"][2])])
    return moved


def line_state(geometry, placement, plain, depth):
    """C++ hanging-line rule (.cpp:1368-1378), axis-convention top."""
    structure = plain["structure"]
    station = plain["stations"][placement["station_index"]]["world"]
    up = unit_axis(station, 2)
    grid_top = _add(station["location"], _mul(up, structure["gridiron_height_cm"] + depth * 1.5))[2]
    drop = grid_top - geometry["top_axis"]
    hangs = (structure["hang_from_grid"] and structure["gridiron_enabled"]
             and structure["grid_half_width_cm"] > 0.0
             and geometry["lateral_cm"] <= structure["grid_half_width_cm"]
             and 1.0 <= drop <= structure["max_drop_cm"])
    return {"drop_cm": round(drop, 2), "hangs": bool(hangs)}


def _moved_placement(placement, plain, z_new):
    cue = next(c for c in plain["cues"] if c["guid"] == placement["cue_guid"])
    rel = copy.deepcopy(cue["attachments"][placement["attachment_index"]]["relative_transform"])
    rel["location"][2] = z_new
    light_world = compose(rel, placement["pair_world"])
    station = plain["stations"][placement["station_index"]]["world"]
    return housing_geometry(light_world, station, plain["structure"])


def build_plan(plain, dry_points, options=None):
    options = dict(options or {})
    convention = str(options.get("top_convention", "BOX")).upper()
    require(convention in TOP_CONVENTIONS, "TOP_CONVENTION_INVALID|" + convention)
    extras = [str(g).replace("-", "").upper() for g in options.get("extra_light_guids", []) or []]
    expected = int(options.get("expected_housings", EXPECTED_HOUSINGS))
    structure = plain["structure"]
    require(structure.get("fixtures_enabled", True), "FIXTURES_LAYER_DISABLED")
    require(len(dry_points) == expected, "HOUSING_COUNT|dry=%d|expected=%d" % (len(dry_points), expected))

    bay = set(plain["bay_guids"])
    outside = [s["cue_guid"] for s in plain["stations"] if s["cue_guid"] not in bay]
    require(not outside, "STATION_OUTSIDE_P03|count=%d" % len(outside))
    placements, moving = gather_placements(plain)
    worst = check_instances(placements, plain["instances"])
    mapped = map_points(dry_points, placements)
    for guid in extras:
        hits = [p["placement_index"] for p in placements if p["attachment_guid"] == guid]
        require(len(hits) == 1, "EXTRA_LIGHT_NOT_A_HOUSING|guid=%s|count=%d" % (guid, len(hits)))
        require(hits[0] not in mapped, "EXTRA_LIGHT_ALREADY_MAPPED|guid=" + guid)
        mapped.append(hits[0])
    targets_src = [placements[i] for i in mapped]
    require(len(targets_src) == expected + len(extras), "TARGET_COUNT")

    all_guids = [row["guid"] for cue in plain["cues"] for row in cue["attachments"]]
    for placement in targets_src:
        require(all_guids.count(placement["attachment_guid"]) == 1,
                "TARGET_GUID_NOT_UNIQUE|guid=" + placement["attachment_guid"])
        require(placement["cue_guid"] in bay, "TARGET_OUTSIDE_P03|cue=" + placement["cue_label"])

    rows, needs = [], []
    for placement in targets_src:
        moved = vertical_factor(placement["pair_world"])
        require(FRAME_VERTICAL_MIN <= moved[2] <= 1.0 / FRAME_VERTICAL_MIN,
                "FRAME_NOT_VERTICAL|label=%s|k=%.6f" % (placement["attachment_label"], moved[2]))
        lo = band_lo(placement, structure, plain)
        require(abs(lo - EXPECTED_BAND_LO_CM) <= BAND_LO_TOLERANCE_CM,
                "BAND_DRIFT|label=%s|band_lo=%.3f|expected=%.1f" % (placement["attachment_label"], lo,
                                                                     EXPECTED_BAND_LO_CM))
        top = housing_top(placement["geometry"], convention)
        needs.append((top - (lo - CLEARANCE_CM)) / moved[2])
        rows.append((placement, moved, lo, top))
    raw = max(needs)
    require(raw > 0.0, "NOTHING_TO_DROP|raw=%.3f" % raw)
    drop = round(math.ceil(raw / DROP_QUANTUM_CM - 1.0e-9) * DROP_QUANTUM_CM, 1)
    require(drop <= MAX_DROP_CM, "DROP_TOO_LARGE|drop=%.1f" % drop)

    targets = []
    for placement, moved, lo, top in rows:
        z_before = float(placement["relative_location"][2])
        z_after = z_before - drop
        after = _moved_placement(placement, plain, z_after)
        top_after = housing_top(after, convention)
        require(top_after <= lo - CLEARANCE_CM + 1.0e-6,
                "DROP_INSUFFICIENT|label=%s|top_after=%.3f" % (placement["attachment_label"], top_after))
        targets.append({
            "cue_guid": placement["cue_guid"], "cue_label": placement["cue_label"],
            "show_index": placement["show_index"], "station_index": placement["station_index"],
            "attachment_guid": placement["attachment_guid"], "attachment_label": placement["attachment_label"],
            "attachment_index": placement["attachment_index"],
            "x_rel": float(placement["relative_location"][0]), "y_rel": float(placement["relative_location"][1]),
            "z_before": z_before, "z_after": z_after,
            "band_lo_cm": lo, "world_dz_per_cm": moved[2], "world_dxy_per_cm": [moved[0], moved[1]],
            "housing_before": {"top_box": placement["geometry"]["top_box"],
                               "top_axis": placement["geometry"]["top_axis"],
                               "centre": placement["geometry"]["centre"]},
            "housing_after": {"top_box": after["top_box"], "top_axis": after["top_axis"],
                              "centre": after["centre"]},
            "top_before": top, "top_after": top_after,
            "route_gap_to_new_cross_beam_cm": (abs(placement["geometry"]["route_offset_cm"])
                                               - placement["geometry"]["route_half_extent_cm"]
                                               - NEW_BEAM_WIDTH_CM * 0.5),
            "line": {"current_depth_before": line_state(placement["geometry"], placement, plain,
                                                        structure["gridiron_depth_cm"]),
                     "current_depth_after": line_state(after, placement, plain, structure["gridiron_depth_cm"]),
                     "new_depth_after": line_state(after, placement, plain, NEW_BEAM_DEPTH_CM)},
            "mapped_from": "extra" if placement["attachment_guid"] in extras else "dry_point",
        })

    target_ids = {t["attachment_guid"] for t in targets}
    others = []
    for placement in placements:
        if placement["attachment_guid"] in target_ids:
            continue
        geometry = placement["geometry"]
        lo = band_lo(placement, structure, plain)
        hi = lo + NEW_BEAM_DEPTH_CM
        in_band = housing_top(geometry, convention) > lo - CLEARANCE_CM and geometry["bottom_box"] < hi
        gap = abs(geometry["route_offset_cm"]) - geometry["route_half_extent_cm"] - NEW_BEAM_WIDTH_CM * 0.5
        if in_band:
            others.append({"attachment_guid": placement["attachment_guid"], "label": placement["attachment_label"],
                           "cue": placement["cue_label"], "top": round(housing_top(geometry, convention), 2),
                           "bottom_box": round(geometry["bottom_box"], 2),
                           "route_gap_to_new_cross_beam_cm": round(gap, 2),
                           "hits_new_cross_beam_box": gap < 0.0})
    return {
        "passage": PASSAGE_KEY, "top_convention": convention, "clearance_cm": CLEARANCE_CM,
        "drop_cm": drop, "drop_raw_cm": raw, "placements": len(placements),
        "moving_lights_without_housing": moving, "instance_worst_error_cm": worst,
        "targets": sorted(targets, key=lambda t: (t["station_index"], t["attachment_index"])),
        "target_cue_guids": sorted({t["cue_guid"] for t in targets}),
        "target_attachment_guids": sorted(target_ids),
        "other_housings_in_new_band": others,
    }


# --------------------------------------------------------------------------
# Scope guards, offline mutation model, revert model.
# --------------------------------------------------------------------------
def expected_rows(before_rows, plan, field):
    rows = copy.deepcopy(before_rows)
    by_guid = {t["attachment_guid"]: t for t in plan["targets"]}
    for row in rows:
        if row["guid"] in by_guid:
            row["relative_transform"]["location"][2] = by_guid[row["guid"]][field]
    return rows


def check_scope(tool, before_all, after_all, plan, field="z_after"):
    """Outside-target hash guard + target cues equal except the planned Z."""
    require(set(before_all) == set(after_all), "CUE_SET_CHANGED")
    require(tool._outside_hash(before_all, plan["target_cue_guids"])
            == tool._outside_hash(after_all, plan["target_cue_guids"]), "OUTSIDE_TARGET_SCOPE_CHANGED")
    for cue_guid in plan["target_cue_guids"]:
        want = expected_rows(before_all[cue_guid], plan, field)
        require(_canonical(after_all[cue_guid]) == _canonical(want),
                "TARGET_CUE_SCOPE_CHANGED|cue=%s|differences=%s"
                % (cue_guid, _canonical(tool._state_differences(want, after_all[cue_guid]))[:2000]))


def apply_plain(all_rows, plan):
    result = copy.deepcopy(all_rows)
    for cue_guid in plan["target_cue_guids"]:
        result[cue_guid] = expected_rows(all_rows[cue_guid], plan, "z_after")
    return result


def target_rows(all_rows, plan):
    out = {}
    for target in plan["targets"]:
        hits = [row for row in all_rows[target["cue_guid"]] if row["guid"] == target["attachment_guid"]]
        require(len(hits) == 1, "TARGET_ROW_RESOLVE|guid=" + target["attachment_guid"])
        out[target["attachment_guid"]] = copy.deepcopy(hits[0])
    return out


def check_revert_drift(all_rows, record):
    """Every target attachment must still be exactly the recorded after-state."""
    current = target_rows(all_rows, record["plan"])
    for guid, row in current.items():
        require(_canonical(row) == _canonical(record["after_target_rows"][guid]),
                "REVERT_DRIFT|guid=%s|label=%s" % (guid, row.get("label")))


def revert_plain(all_rows, record):
    check_revert_drift(all_rows, record)
    result = copy.deepcopy(all_rows)
    for cue_guid in record["plan"]["target_cue_guids"]:
        result[cue_guid] = expected_rows(all_rows[cue_guid], record["plan"], "z_before")
    restored = target_rows(result, record["plan"])
    for guid, row in restored.items():
        require(_canonical(row) == _canonical(record["before_target_rows"][guid]), "REVERT_NOT_EXACT|guid=" + guid)
    return result


_OWN_GUID = re.compile(r"[(,]AttachmentGuid=([0-9A-Fa-f]{32})")
_TRANSLATION_Z = re.compile(r"(Translation=\(X=[^,()]*,Y=[^,()]*,Z=)([^,()]*)(\))")


def normalize_export(texts, target_guids):
    """Mask exactly the relative Translation.Z of each target attachment."""
    wanted = {g.upper() for g in target_guids}
    seen = {g: 0 for g in wanted}
    out = []
    for text in texts:
        marks = list(_OWN_GUID.finditer(text))
        pieces, cursor = [], 0
        for index, match in enumerate(marks):
            guid = match.group(1).upper()
            if guid not in wanted:
                continue
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            segment = text[match.start():end]
            anchor = segment.find("RelativeTransform=(")
            require(anchor >= 0, "EXPORT_NO_RELATIVE_TRANSFORM|guid=" + guid)
            found = _TRANSLATION_Z.search(segment, anchor)
            require(found is not None, "EXPORT_NO_TRANSLATION|guid=" + guid)
            start = match.start() + found.start(2)
            pieces.append(text[cursor:start])
            pieces.append("<Z>")
            cursor = match.start() + found.end(2)
            seen[guid] += 1
        pieces.append(text[cursor:])
        out.append("".join(pieces))
    require(all(count == 1 for count in seen.values()), "EXPORT_TARGET_COUNT|%s" % _canonical(seen))
    return out


def export_hash(texts, target_guids):
    return _sha256_text("\n".join(normalize_export(texts, target_guids)))


def check_context(ctx):
    """Pure gate over facts read from the editor (no PIE, no Sequencer, clean, no ZZ_)."""
    require(not ctx.get("pie"), "PIE_OR_SIE_ACTIVE")
    require(not ctx.get("sequencer_open"), "SEQUENCER_IS_OPEN")
    census = ctx.get("census") or {}
    require(not census.get("content") and not census.get("maps"), "DIRTY_BEFORE|census=" + _canonical(census))
    require(not ctx.get("zz_actors"), "STRAY_ZZ_ACTORS|" + ",".join(ctx.get("zz_actors") or []))


def check_mode_args(mode, confirm):
    mode = str(mode or "DRY").upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(confirm == "%s %s" % (mode, PASSAGE_KEY), "CONFIRM_MISSING|mode=%s|need='%s %s'"
                % (mode, mode, PASSAGE_KEY))
    return mode


# --------------------------------------------------------------------------
# Module loading (lighting_scores_apply.py, then its load_p04_tool()).
# --------------------------------------------------------------------------
_SAFE_CALLS = {"os.path.join", "os.path.dirname", "os.path.abspath", "os.path.normcase",
               "os.path.normpath", "re.compile", "tuple", "frozenset", "set", "dict", "list",
               "_load_attachment_state"}


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return None if inner is None else inner + "." + node.attr
    return None


def _is_main_guard(node):
    return (isinstance(node, ast.If) and not node.orelse and len(node.body) == 1
            and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "unreal" and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value is None
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call)
            and _dotted(node.body[0].value.func) == "main"
            and not node.body[0].value.args and not node.body[0].value.keywords)


def _top_level_ok(node, index):
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
        return True
    if isinstance(node, ast.Expr):
        return index == 0 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return node.value is None or all(_dotted(c.func) in _SAFE_CALLS
                                         for c in ast.walk(node.value) if isinstance(c, ast.Call))
    if isinstance(node, ast.Try):
        inner = list(node.body) + [s for h in node.handlers for s in h.body] + list(node.orelse) + list(node.finalbody)
        return all(isinstance(s, (ast.Import, ast.ImportFrom))
                   or (isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)) for s in inner)
    return False


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1])
            and sum(1 for n in tree.body if _is_main_guard(n)) == 1, "MAIN_GUARD_SHAPE|" + path)
    for index, node in enumerate(tree.body[:-1]):
        require(_top_level_ok(node, index), "TOP_LEVEL_SIDE_EFFECT|%s|line=%d" % (path, getattr(node, "lineno", -1)))
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


SCORES_REQUIRED = ("load_p04_tool", "_materialize_passage", "_count_passage_actors", "scan_foreign_records")
TOOL_EXTRA_REQUIRED = ("S", "_state_differences")


def load_modules():
    scores = load_without_main(SCORES_TOOL_PATH, "_lighting_scores_for_p03_housing_drop")
    missing = [n for n in SCORES_REQUIRED if not callable(getattr(scores, n, None))]
    require(not missing, "SCORES_API_DRIFT|" + ",".join(missing))
    tool = scores.load_p04_tool()   # validates the P04 tool's API by name and parameters
    missing = [n for n in TOOL_EXTRA_REQUIRED if not hasattr(tool, n)]
    require(not missing, "P04_TOOL_API_DRIFT|" + ",".join(missing))
    return scores, tool


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# --------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _ctx_facts(tool, world):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    return {"pie": editor.get_game_world() is not None,
            "sequencer_open": library is not None and library.get_current_level_sequence() is not None,
            "census": tool._dirty_census(),
            "zz_actors": sorted(a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_"))}


def _find_structure(show):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = [a for a in subsystem.get_all_level_actors()
             if a.get_class().get_name() == "InfinityStageStructureActor" and a.get_actor_label() == STRUCTURE_LABEL]
    require(len(found) == 1, "STRUCTURE_COUNT|label=%s|count=%d" % (STRUCTURE_LABEL, len(found)))
    structure = found[0]
    passage = structure.get_editor_property("passage")
    require(passage is not None and passage.get_actor_label().startswith(PASSAGE_ACTOR_PREFIX),
            "STRUCTURE_PASSAGE_WRONG")
    require(passage.get_editor_property("show_asset") == show, "STRUCTURE_SHOW_WRONG")
    return structure


def _stations(tool, structure):
    result = structure.gather_stations()
    if isinstance(result, tuple) and len(result) == 3:
        ok, stations, error = result
        require(bool(ok), "GATHER_STATIONS_FAILED|" + str(error))
    elif isinstance(result, tuple) and len(result) == 2:
        stations, error = result
    else:
        stations, error = result, ""
    require(stations is not None and len(list(stations)) > 0, "GATHER_STATIONS_EMPTY|" + str(error))
    return [{"cue_guid": tool._guid_text(s.get_editor_property("cue_guid")),
             "world": tool.S._transform_state(s.get_editor_property("station_world"))} for s in stations]


def _fixture_component(structure):
    comps = [c for c in structure.get_editor_property("managed_components")
             if c and FIXTURE_TAG in [str(t) for t in c.get_editor_property("component_tags")]]
    require(len(comps) == 1, "FIXTURE_COMPONENT_COUNT|%d" % len(comps))
    return comps[0]


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _runtime_plain(tool, show, structure):
    cues = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        pair = cue.get_editor_property("wing_pair")
        cues.append({"show_index": index, "guid": tool._guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")), "type": str(cue.get_editor_property("type")),
                     "occurrence_offset": tool.S._transform_state(pair.get_editor_property("occurrence_offset")),
                     "attachments": tool._attachment_rows(tool._pair_attachments(cue))})
    passage = structure.get_editor_property("passage")
    bay = [tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(
        passage.get_editor_property("passage_guid"))]
    fixtures = structure.get_editor_property("fixtures")
    grid = structure.get_editor_property("gridiron")
    comp = _fixture_component(structure)
    box = comp.get_editor_property("static_mesh").get_bounding_box()
    instances = []
    for i in range(int(comp.get_instance_count())):
        xf = comp.get_instance_transform(i, True)
        require(xf is not None, "INSTANCE_READ_FAILED|%d" % i)
        instances.append(_vec(xf.translation))
    return {
        "cues": cues, "stations": _stations(tool, structure), "bay_guids": bay, "instances": instances,
        "structure": {
            "label": structure.get_actor_label(),
            "fixtures_enabled": bool(fixtures.get_editor_property("enabled")),
            "body_size_cm": _vec(fixtures.get_editor_property("body_size_cm")),
            "body_mesh_bounds": {"min": _vec(box.min), "max": _vec(box.max)},
            "hang_from_grid": bool(fixtures.get_editor_property("hang_from_grid")),
            "max_drop_cm": float(fixtures.get_editor_property("max_drop_cm")),
            "gridiron_enabled": bool(grid.get_editor_property("enabled")),
            "gridiron_height_cm": float(grid.get_editor_property("height_cm")),
            "gridiron_depth_cm": float(grid.get_editor_property("beam_depth_cm")),
            "gridiron_width_cm": float(grid.get_editor_property("beam_width_cm")),
            "grid_half_width_cm": float(structure.get_editor_property("grid_half_width_cm")),
            "fixture_body_count": int(structure.get_editor_property("fixture_body_count")),
            "current": bool(structure.is_structure_current()),
        },
    }


def _all_rows(plain):
    return {cue["guid"]: cue["attachments"] for cue in plain["cues"]}


def _export_texts(show):
    texts = []
    for value in list(show.get_editor_property("cues")) + list(show.get_editor_property("passage_settings")):
        exporter = getattr(value, "export_text", None)
        require(callable(exporter), "EXPORT_TEXT_MISSING|" + type(value).__name__)
        texts.append(str(exporter()))
    return texts


def _write_z(tool, show, plan, field, check_field=None):
    """Set the targets' relative Translation.Z to plan[field]; rotation untouched."""
    cues = list(show.get_editor_property("cues"))
    by_cue = {}
    for target in plan["targets"]:
        by_cue.setdefault(target["cue_guid"], []).append(target)
    for cue_guid, items in sorted(by_cue.items()):
        matches = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == cue_guid]
        require(len(matches) == 1 and matches[0] == items[0]["show_index"], "TARGET_CUE_RESOLVE|cue=" + cue_guid)
        index = matches[0]
        require(str(cues[index].get_editor_property("label")) == items[0]["cue_label"], "TARGET_LABEL_DRIFT|" + cue_guid)
        attachments = tool._pair_attachments(cues[index])
        for item in items:
            hits = [a for a in attachments if tool._guid_text(a.get_editor_property("attachment_guid"))
                    == item["attachment_guid"]]
            require(len(hits) == 1, "TARGET_ATTACHMENT_RESOLVE|guid=" + item["attachment_guid"])
            attachment = hits[0]
            transform = attachment.get_editor_property("relative_transform")
            location = transform.translation
            if check_field is not None:
                require(float(location.x) == item["x_rel"] and float(location.y) == item["y_rel"]
                        and float(location.z) == item[check_field],
                        "TARGET_POSITION_DRIFT|guid=%s|z=%r" % (item["attachment_guid"], float(location.z)))
            transform.set_editor_property("translation", unreal.Vector(float(location.x), float(location.y),
                                                                        float(item[field])))
            attachment.set_editor_property("relative_transform", transform)
        tool._set_pair_attachments(show, index, attachments)


def _live_housing_check(tool, show, structure, plan):
    """After the re-fit: the ISM must match the maths again and every target clear the band."""
    plain = _runtime_plain(tool, show, structure)
    require(plain["structure"]["current"], "STRUCTURE_NOT_CURRENT_AFTER_REFIT")
    placements, unused = gather_placements(plain)
    worst = check_instances(placements, plain["instances"])
    by_guid = {p["attachment_guid"]: p for p in placements}
    tops = {}
    for target in plan["targets"]:
        placement = by_guid.get(target["attachment_guid"])
        require(placement is not None, "TARGET_HOUSING_GONE|" + target["attachment_label"])
        live = plain["instances"][placement["placement_index"]]
        offset = placement["geometry"]["instance_location"][2] - live[2]
        top = housing_top(placement["geometry"], plan["top_convention"]) - offset
        require(top <= target["band_lo_cm"] - CLEARANCE_CM + 1.0e-3,
                "LIVE_HOUSING_STILL_IN_BAND|label=%s|top=%.3f" % (target["attachment_label"], top))
        tops[target["attachment_guid"]] = round(top, 3)
    return {"instance_worst_error_cm": worst, "live_tops": tops,
            "fixture_body_count": plain["structure"]["fixture_body_count"]}


def _scan_foreign(scores, plan, extra_exclude=()):
    saved = os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in os.listdir(saved) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, plan["target_attachment_guids"],
                                       exclude=[RECORD_PATH] + list(extra_exclude))


def _report_path(run, mode):
    return os.path.join(HERE, "p03_housing_drop_report_%s_%s.json" % (mode, run))


def _run(mode, ack_records, extras, convention):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"ok": False, "mode": mode, "run": run}
    tool = None
    try:
        scores, tool = load_modules()
        report["sources"] = {"scores_sha256": scores.SOURCE_SHA256, "p04_tool_sha256": tool.SCORES_SOURCE_SHA256}
        world = tool._require_context()          # P04 tool's own gate (project, world, PIE, Sequencer, census, ZZ_)
        check_context(_ctx_facts(tool, world))   # same facts through the tested pure gate
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        require(scores._count_passage_actors(show, PASSAGE_ACTOR_PREFIX) == 1, "PASSAGE_ACTOR_COUNT")
        structure = _find_structure(show)
        plain = _runtime_plain(tool, show, structure)
        report["structure"] = plain["structure"]

        if mode in ("DRY", "APPLY"):
            points = live_points(plain, convention)
            plan = build_plan(plain, points, {"extra_light_guids": extras, "top_convention": convention})
            check_approved_set(plan)
            before_all = _all_rows(plain)
            texts_hash = export_hash(_export_texts(show), plan["target_attachment_guids"])
            foreign = _scan_foreign(scores, plan)
            unacked = sorted({h["path"] for h in foreign} - set(ack_records or []))
            report.update({"plan": plan, "housing_source": {"kind": "live_structure", "points": len(points)},
                           "foreign_records": foreign, "unacknowledged_foreign_records": unacked,
                           "active_record": RECORD_PATH if os.path.exists(RECORD_PATH) else None})
            if mode == "DRY":
                for t in plan["targets"]:
                    _log("P03_HOUSING_DROP_DRY_ROW|run=%s|label=%s|cue=%s|guid=%s|z=%.3f->%.3f|top_%s=%.2f->%.2f"
                         "|band_lo=%.2f|top_axis=%.2f->%.2f|route_gap=%.2f|line_new_depth=%s"
                         % (run, t["attachment_label"], t["cue_label"], t["attachment_guid"], t["z_before"],
                            t["z_after"], plan["top_convention"].lower(), t["top_before"], t["top_after"],
                            t["band_lo_cm"], t["housing_before"]["top_axis"], t["housing_after"]["top_axis"],
                            t["route_gap_to_new_cross_beam_cm"], t["line"]["new_depth_after"]))
                require(tool._dirty_census() == {"content": [], "maps": []}, "DRY_DIRTIED")
                report.update({"ok": True, "mutated": False})
                tool._write_json(_report_path(run, mode), report)
                _log("P03_HOUSING_DROP_DRY_OK|run=%s|targets=%d|drop_cm=%.1f|convention=%s|others_in_band=%d"
                     "|foreign=%d|unacked=%d|mutated=0" % (run, len(plan["targets"]), plan["drop_cm"],
                                                           plan["top_convention"],
                                                           len(plan["other_housings_in_new_band"]),
                                                           len(foreign), len(unacked)))
                return report

            require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS|" + RECORD_PATH)
            require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
            backup = tool._backup("PreP03HousingDrop-", run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "backup": backup, "plan": plan,
                      "outside_before_hash": tool._outside_hash(before_all, plan["target_cue_guids"]),
                      "export_hash_before": texts_hash,
                      "before_target_rows": target_rows(before_all, plan),
                      "after_target_rows": target_rows(apply_plain(before_all, plan), plan),
                      "acknowledged_records": list(ack_records or [])}
            tool._write_json(RECORD_PATH, record, exclusive=True)   # fsynced before any mutation
            try:
                _write_z(tool, show, plan, "z_after", check_field="z_before")
                after_all = _all_rows(_runtime_plain(tool, show, structure))
                check_scope(tool, before_all, after_all, plan, "z_after")
                require(export_hash(_export_texts(show), plan["target_attachment_guids"]) == texts_hash,
                        "EXPORT_OUTSIDE_SCOPE_CHANGED")
            except Exception:
                _write_z(tool, show, plan, "z_before")
                restored = _all_rows(_runtime_plain(tool, show, structure))
                check_scope(tool, before_all, restored, plan, "z_before")
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
                raise
            record["status"] = "mutated_verified"
            tool._write_json(RECORD_PATH, record)
            materialized = scores._materialize_passage(show, PASSAGE_ACTOR_PREFIX)
            require(materialized.get("structure") == STRUCTURE_LABEL, "STRUCTURE_NOT_REFIT|%s" % materialized)
            live = _live_housing_check(tool, show, structure, plan)
            tool._save_narrow()
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            read_all = _all_rows(_runtime_plain(tool, readback, structure))
            check_scope(tool, before_all, read_all, plan, "z_after")
            require(_canonical(target_rows(read_all, plan)) == _canonical(record["after_target_rows"]),
                    "READBACK_TARGET_ROWS")
            require(export_hash(_export_texts(readback), plan["target_attachment_guids"]) == texts_hash,
                    "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
            record.update({"status": "saved_readback_verified", "materialized": materialized, "live": live,
                           "saved_census": tool._dirty_census()})
            tool._write_json(RECORD_PATH, record)
            tool._queue_master_test(world, "P03_HOUSING_DROP", run)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized,
                           "live": live, "tests_required": list(SUCCESS_TESTS)})
            tool._write_json(_report_path(run, mode), report)
            _log("P03_HOUSING_DROP_APPLY_OK|run=%s|targets=%d|drop_cm=%.1f|convention=%s|show_saved=1|level_saved=1"
                 "|readback=1|structure_refit=1|saved_master=queued" % (run, len(plan["targets"]), plan["drop_cm"],
                                                                        plan["top_convention"]))
            return report

        # REVERT
        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
        record = tool._read_json(RECORD_PATH)
        require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|" + str(record.get("status")))
        plan = record["plan"]
        before_all = _all_rows(plain)
        reverted_model = revert_plain(before_all, record)       # drift check + exactness on plain data
        texts_hash = export_hash(_export_texts(show), plan["target_attachment_guids"])
        backup = tool._backup("PreP03HousingDropRevert-", run)
        try:
            _write_z(tool, show, plan, "z_before", check_field="z_after")
            after_all = _all_rows(_runtime_plain(tool, show, structure))
            check_scope(tool, before_all, after_all, plan, "z_before")
            require(_canonical(after_all) == _canonical(reverted_model), "REVERT_MODEL_MISMATCH")
            require(export_hash(_export_texts(show), plan["target_attachment_guids"]) == texts_hash,
                    "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            _write_z(tool, show, plan, "z_after")
            raise
        materialized = scores._materialize_passage(show, PASSAGE_ACTOR_PREFIX)
        require(materialized.get("structure") == STRUCTURE_LABEL, "STRUCTURE_NOT_REFIT|%s" % materialized)
        tool._save_narrow()
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = _all_rows(_runtime_plain(tool, readback, structure))
        require(_canonical(target_rows(read_all, plan)) == _canonical(record["before_target_rows"]),
                "REVERT_READBACK_NOT_EXACT")
        check_scope(tool, before_all, read_all, plan, "z_before")
        archived = RECORD_PATH + ".reverted-" + run
        os.rename(RECORD_PATH, archived)
        tool._queue_master_test(world, "P03_HOUSING_DROP_REVERT", run)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized})
        tool._write_json(_report_path(run, mode), report)
        _log("P03_HOUSING_DROP_REVERT_OK|run=%s|targets=%d|show_saved=1|level_saved=1|readback=1|saved_master=queued"
             % (run, len(plan["targets"])))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(_report_path(run, mode), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        unreal.log_error("P03_HOUSING_DROP_FAILED|run=%s|mode=%s|%s" % (run, mode, report["error"]))
        raise


def main():
    mode = check_mode_args(globals().get("P03_HOUSING_DROP_MODE", "DRY"), globals().get("P03_HOUSING_DROP_CONFIRM"))
    require(unreal is not None, "UNREAL_REQUIRED")
    return _run(mode, list(globals().get("P03_HOUSING_DROP_ACK_RECORDS", []) or []),
                list(globals().get("P03_HOUSING_DROP_EXTRA_LIGHT_GUIDS", []) or []),
                str(globals().get("P03_HOUSING_DROP_TOP_CONVENTION", "BOX") or "BOX").upper())


if unreal is not None:
    main()
