"""Rig lamp drop: DRY / APPLY / REVERT for ONE passage (Gary 5 Oct, "Hang them under the girder").

Generalises p03_housing_drop.py (live-proven 5 Oct: DRY OK, APPLY run
20261005-085813, 14 Rig Slash lamps lowered 20 cm, read-back + re-fit + both
editor tests green). That file is NOT modified or imported; its helpers are
copied here so the live-applied tool stays exactly as it ran.

Problem. Underpass Phase A gives every passage's gridiron 90 cm x 40 cm plate
girders centred at HeightCm 1150 (underpass_rig_apply.py:70), so each cross
beam occupies 1105..1195 above its station line. The lighting scores placed
TOP_L / TOP_R lamps at relative (0, +-360, 1180) on the station line, so their
housings (about 1178..1227) sit inside the cross girder. This tool lowers the
Show LIGHT ATTACHMENTS behind those housings by ONE uniform pure-Z relative
translation per passage (rotation and aim untouched) so that every target's
highest housing point (BOX convention, the base tool's default) is >= 5 cm
below its cross beam's underside.

Proof tiers (AGENTS.md), per claim:
* declaration-proven: station frames are the Passage Route spline's own frames,
  StationWorld = Route->GetTransformAtDistanceAlongSpline(Wing.DistanceCm,
  World, false) with scale forced to 1 (InfinityStageStructureActor.cpp:261-265),
  sorted by DistanceCm (.cpp:276-279); X along the route, Y across, Z up
  (InfinityStageStructureActor.h:31-36). Placement, housing fit and the
  hanging-line rule are .cpp:75-111, 118-131, 1349-1378 (as in the base tool).
  Cross beams: one on every CrossBeamEvery-th station (.cpp:666, 672),
  centred at Origin + Up*HeightCm, length HalfSpanCm*2 along Across
  (.cpp:675-683), HalfSpanCm == GridHalfWidthCm (.cpp:636-637), section
  BeamWidthCm*(1+jitter*Variation) x BeamDepthCm*(1+jitter*Variation)
  (.cpp:655-659); Phase A sets section_variation 0 (underpass_rig_apply.py:70),
  so the Phase A band is exactly 90 x 40.
* measured: the underpass DRY UPRIG-20261005-081407 read cross_beam_every=1,
  height_cm=1150 on all six structures (underpass_rig_dry_UPRIG-20261005-081407.json,
  read by underpass_rig_apply.py:309 via the same property names used here);
  the P03 housing-drop DRY measured 34 TOP housings with BOX top 1226.57 and
  route gap -36 cm (p03_housing_drop_report_DRY_20261005-085808.json,
  plan.other_housings_in_new_band); the P03 APPLY read live P03 gridiron depth
  34 at 08:58 (p03_housing_drop_report_APPLY_20261005-085813.json "structure"),
  so P03's Phase A may not be live yet: this tool always plans against the
  nominal Phase A band, and reports whether it is live (phase_state()).
* inferred (the first live DRY per passage confirms each): GatherStations'
  Python return shape (handled as in the base tool); every passage's station
  frames are vertical (FRAME_NOT_VERTICAL refuses otherwise); the live ISM
  matching this maths within 0.5 cm (check_instances) is the runtime proof that
  the frames read here are the frames the C++ used, including P02's curve.

Args (rig_lamp_drop_args.json via rig_lamp_drop_run.py):
  {"mode": "DRY"|"APPLY"|"REVERT", "passage": "P01".."P06",
   "label_regex": "TOP_[LR]$", "confirm": "<MODE> <passage>", "ack_records": [...],
   "top_convention": "BOX", "expected_targets": null|int, "expected_drop_cm": null|float}
The two "expected_*" keys are optional pins: copy them from the DRY so an APPLY
cannot silently do something other than what the DRY showed.
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
VALID_MODES = ("DRY", "APPLY", "REVERT")
TOP_CONVENTIONS = ("BOX", "AXIS")
PASSAGES = ("P01", "P02", "P03", "P04", "P05", "P06")
DEFAULT_LABEL_REGEX = "TOP_[LR]$"

STRUCTURE_LABEL_FMT = "Infinity Stage - Structure %02d"   # underpass_rig_apply.py:57
PASSAGE_ACTOR_PREFIX_FMT = "Passage %02d"                  # probe_routes.json labels "Passage 0n — ..."
SCORE_LABEL_FMT = r"^%s SCORE B\d{2} "                    # lighting_scores labels, e.g. "P02 SCORE B01 INDUSTRIAL TOP_L"
NEW_BEAM_DEPTH_CM = 90.0   # underpass_rig_apply.py:70 PHASE_A
NEW_BEAM_WIDTH_CM = 40.0   # underpass_rig_apply.py:70 PHASE_A
OLD_BEAM_DEPTH_CM = 34.0   # InfinityStageStructureActor.h:84 default; measured pre-Phase-A on all six
EXPECTED_BAND_LO_REL_CM = 1105.0   # HeightCm 1150 - 90/2, relative to the station origin
BAND_LO_TOLERANCE_CM = 2.0
CLEARANCE_CM = 5.0
INSTANCE_TOLERANCE_CM = 0.5
FRAME_VERTICAL_MIN = 0.999
DROP_QUANTUM_CM = 0.1
MAX_DROP_CM = 150.0        # expected ~127.6-127.8 cm (P03 DRY measured BOX tops up to 1227.76)
FIXTURE_TAG = "InfinityStage.Structure.Fixtures"   # InfinityStageStructureActor.cpp:24
SUCCESS_TESTS = ("run_saved_master_test_request.json", "run_scene_cut_test_request.json")


class RigLampDropError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise RigLampDropError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Passage naming and per-passage files.
# --------------------------------------------------------------------------
def passage_names(passage):
    key = str(passage or "").upper()
    require(key in PASSAGES, "PASSAGE_INVALID|" + str(passage))
    number = int(key[1:])
    return {"key": key, "number": number, "structure_label": STRUCTURE_LABEL_FMT % number,
            "actor_prefix": PASSAGE_ACTOR_PREFIX_FMT % number}


def record_path(passage, folder=None):
    return os.path.join(folder or HERE, "rig_lamp_drop_record_%s.json" % passage_names(passage)["key"])


def report_path(passage, mode, run, folder=None):
    return os.path.join(folder or HERE, "rig_lamp_drop_report_%s_%s_%s.json"
                        % (passage_names(passage)["key"], mode, run))


def backup_prefix(passage, revert=False):
    return "PreRigLampDrop%s-%s-" % ("Revert" if revert else "", passage_names(passage)["key"])


# --------------------------------------------------------------------------
# Plain transform maths (FTransform semantics, positive scale) — base tool.
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


def half_extent(geometry, direction):
    """Half the housing box's extent along a unit direction."""
    return sum(abs(_dot(geometry["axes"][k], direction)) * geometry["size"][k] * 0.5 for k in range(3))


def housing_geometry(light_world, station_world, structure):
    """Where the C++ puts this light's housing (.cpp:1349-1361); base tool + axes/size."""
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
        "axes": [list(a) for a in axes],
        "size": size,
    }


def housing_top(geometry, convention):
    require(convention in TOP_CONVENTIONS, "TOP_CONVENTION_INVALID|" + str(convention))
    return geometry["top_box"] if convention == "BOX" else geometry["top_axis"]


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


# --------------------------------------------------------------------------
# Placement replication (GatherFixturePlacements, .cpp:75-111) — base tool.
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


def vertical_factor(pair_world):
    """World displacement per cm of relative Z (pure-Z relative translation)."""
    return quat_rotate(pair_world["rotation_xyzw"], [0.0, 0.0, float(pair_world["scale"][2])])


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


def _moved_geometry(placement, plain, z_new):
    cue = next(c for c in plain["cues"] if c["guid"] == placement["cue_guid"])
    rel = copy.deepcopy(cue["attachments"][placement["attachment_index"]]["relative_transform"])
    rel["location"][2] = z_new
    light_world = compose(rel, placement["pair_world"])
    station = plain["stations"][placement["station_index"]]["world"]
    return housing_geometry(light_world, station, plain["structure"])


# --------------------------------------------------------------------------
# Cross beams (BuildGridiron, .cpp:666-683) judged per station frame.
# --------------------------------------------------------------------------
def cross_beam_stations(plain):
    every = max(1, int(plain["structure"].get("cross_beam_every", 1)))
    return [i for i in range(len(plain["stations"])) if i % every == 0]


def check_frames(plain):
    """Every station frame must be upright: the band is judged in world Z."""
    for index, station in enumerate(plain["stations"]):
        up = unit_axis(station["world"], 2)
        require(up[2] >= FRAME_VERTICAL_MIN, "FRAME_NOT_VERTICAL|station=%d|up_z=%.6f" % (index, up[2]))


def beam_box(plain, station_index):
    """The Phase A cross beam at one station: origin, axes, band (world Z)."""
    structure = plain["structure"]
    world = plain["stations"][station_index]["world"]
    origin = world["location"]
    up = unit_axis(world, 2)
    cross_z = _add(origin, _mul(up, structure["gridiron_height_cm"]))[2]
    lo = cross_z - NEW_BEAM_DEPTH_CM * 0.5
    return {"station_index": station_index, "origin": origin, "route": unit_axis(world, 0),
            "across": unit_axis(world, 1), "lo": lo, "hi": cross_z + NEW_BEAM_DEPTH_CM * 0.5,
            "lo_rel": lo - origin[2], "half_span": float(structure["grid_half_width_cm"])}


def beam_relation(geometry, beam, convention):
    """Base tool's route-gap and height maths, against ONE beam in ITS station frame."""
    d = _sub(geometry["centre"], beam["origin"])
    route_gap = abs(_dot(d, beam["route"])) - half_extent(geometry, beam["route"]) - NEW_BEAM_WIDTH_CM * 0.5
    lateral_gap = abs(_dot(d, beam["across"])) - half_extent(geometry, beam["across"]) - beam["half_span"]
    top = housing_top(geometry, convention)
    height_hit = top > beam["lo"] - CLEARANCE_CM and geometry["bottom_box"] < beam["hi"]
    return {"station_index": beam["station_index"], "route_gap_cm": route_gap, "lateral_gap_cm": lateral_gap,
            "band_lo_cm": beam["lo"], "band_lo_rel_cm": beam["lo_rel"], "top": top,
            "height_hit": bool(height_hit), "hit": bool(route_gap < 0.0 and lateral_gap < 0.0 and height_hit)}


def beam_hits(geometry, beams, convention):
    """All beams this housing's clearance envelope intersects, plus the nearest beam by route gap."""
    relations = [beam_relation(geometry, beam, convention) for beam in beams]
    hits = [r for r in relations if r["hit"]]
    nearest = min(relations, key=lambda r: (max(r["route_gap_cm"], r["lateral_gap_cm"]), r["station_index"])) \
        if relations else None
    return hits, nearest


def phase_state(structure):
    """Is the Phase A girder live on this structure? The plan always uses the Phase A band."""
    depth, width = float(structure["gridiron_depth_cm"]), float(structure["gridiron_width_cm"])
    if depth == NEW_BEAM_DEPTH_CM:
        require(width == NEW_BEAM_WIDTH_CM, "PHASE_A_PARTIAL|width=%s" % width)
        require(float(structure.get("section_variation", 0.0)) == 0.0,
                "PHASE_A_VARIATION_NONZERO|%s" % structure.get("section_variation"))
        return "PHASE_A_LIVE"
    require(depth == OLD_BEAM_DEPTH_CM, "PHASE_STATE_UNKNOWN|depth=%s|width=%s" % (depth, width))
    return "PRE_PHASE_A"


# --------------------------------------------------------------------------
# Plan.
# --------------------------------------------------------------------------
def compile_label_regex(text):
    require(isinstance(text, str) and text.strip(), "LABEL_REGEX_EMPTY")
    try:
        return re.compile(text)
    except re.error as error:
        raise RigLampDropError("LABEL_REGEX_INVALID|%s|%s" % (text, error))


def build_plan(plain, passage, options=None):
    options = dict(options or {})
    names = passage_names(passage)
    convention = str(options.get("top_convention", "BOX")).upper()
    require(convention in TOP_CONVENTIONS, "TOP_CONVENTION_INVALID|" + convention)
    regex_text = options.get("label_regex", DEFAULT_LABEL_REGEX)
    regex = compile_label_regex(regex_text)
    score_label = re.compile(SCORE_LABEL_FMT % names["key"])
    structure = plain["structure"]
    require(structure.get("fixtures_enabled", True), "FIXTURES_LAYER_DISABLED")
    require(float(structure["grid_half_width_cm"]) > 0.0, "GRID_HALF_WIDTH_ZERO")
    phase = phase_state(structure)

    bay = set(plain["bay_guids"])
    outside = [s["cue_guid"] for s in plain["stations"] if s["cue_guid"] not in bay]
    require(not outside, "STATION_OUTSIDE_PASSAGE|passage=%s|count=%d" % (names["key"], len(outside)))
    check_frames(plain)
    placements, moving = gather_placements(plain)
    worst = check_instances(placements, plain["instances"])
    beams = [beam_box(plain, i) for i in cross_beam_stations(plain)]
    require(beams, "NO_CROSS_BEAMS")
    for beam in beams:
        require(abs(beam["lo_rel"] - EXPECTED_BAND_LO_REL_CM) <= BAND_LO_TOLERANCE_CM,
                "BAND_DRIFT|station=%d|band_lo_rel=%.3f|expected=%.1f"
                % (beam["station_index"], beam["lo_rel"], EXPECTED_BAND_LO_REL_CM))

    all_guids = [row["guid"] for cue in plain["cues"] for row in cue["attachments"]]
    rows, needs, non_intersecting, others = [], [], [], []
    for placement in placements:
        matches = bool(regex.search(placement["attachment_label"]))
        hits, nearest = beam_hits(placement["geometry"], beams, convention)
        if matches and hits:
            require(all_guids.count(placement["attachment_guid"]) == 1,
                    "TARGET_GUID_NOT_UNIQUE|guid=" + placement["attachment_guid"])
            require(placement["cue_guid"] in bay, "TARGET_OUTSIDE_PASSAGE|cue=" + placement["cue_label"])
            moved = vertical_factor(placement["pair_world"])
            require(FRAME_VERTICAL_MIN <= moved[2] <= 1.0 / FRAME_VERTICAL_MIN,
                    "FRAME_NOT_VERTICAL|label=%s|k=%.6f" % (placement["attachment_label"], moved[2]))
            lo = min(h["band_lo_cm"] for h in hits)
            top = housing_top(placement["geometry"], convention)
            needs.append((top - (lo - CLEARANCE_CM)) / moved[2])
            rows.append((placement, moved, lo, top, hits))
            continue
        own = beam_relation(placement["geometry"], beam_box(plain, placement["station_index"]), convention)
        summary = {"attachment_guid": placement["attachment_guid"], "label": placement["attachment_label"],
                   "cue": placement["cue_label"], "station_index": placement["station_index"],
                   "top": round(housing_top(placement["geometry"], convention), 2),
                   "bottom_box": round(placement["geometry"]["bottom_box"], 2),
                   "nearest_beam_station": nearest["station_index"] if nearest else None,
                   "nearest_route_gap_cm": round(nearest["route_gap_cm"], 2) if nearest else None,
                   "nearest_lateral_gap_cm": round(nearest["lateral_gap_cm"], 2) if nearest else None,
                   "own_station_in_band_height": own["height_hit"],
                   "hits_new_cross_beam_box": bool(hits), "matches_regex": matches}
        if matches:
            non_intersecting.append(summary)
        elif own["height_hit"] or hits:
            others.append(summary)

    require(rows, "ZERO_TARGETS|passage=%s|regex=%s|regex_matches=%d"
            % (names["key"], regex_text, len(non_intersecting)))
    raw = max(needs)
    require(raw > 0.0, "NOTHING_TO_DROP|raw=%.3f" % raw)
    drop = round(math.ceil(raw / DROP_QUANTUM_CM - 1.0e-9) * DROP_QUANTUM_CM, 1)
    require(drop <= MAX_DROP_CM, "DROP_TOO_LARGE|drop=%.1f|max=%.1f" % (drop, MAX_DROP_CM))

    targets = []
    for placement, moved, lo, top, hits in rows:
        z_before = float(placement["relative_location"][2])
        z_after = z_before - drop
        after = _moved_geometry(placement, plain, z_after)
        top_after = housing_top(after, convention)
        require(top_after <= lo - CLEARANCE_CM + 1.0e-6,
                "DROP_INSUFFICIENT|label=%s|top_after=%.3f" % (placement["attachment_label"], top_after))
        still, unused = beam_hits(after, beams, convention)
        require(not still, "DROP_INSUFFICIENT|label=%s|still_hits=%s"
                % (placement["attachment_label"], [h["station_index"] for h in still]))
        targets.append({
            "cue_guid": placement["cue_guid"], "cue_label": placement["cue_label"],
            "show_index": placement["show_index"], "station_index": placement["station_index"],
            "attachment_guid": placement["attachment_guid"], "attachment_label": placement["attachment_label"],
            "attachment_index": placement["attachment_index"],
            "score_label": bool(score_label.search(placement["attachment_label"])),
            "x_rel": float(placement["relative_location"][0]), "y_rel": float(placement["relative_location"][1]),
            "z_before": z_before, "z_after": z_after,
            "band_lo_cm": lo, "world_dz_per_cm": moved[2], "world_dxy_per_cm": [moved[0], moved[1]],
            "beam_stations_hit": [h["station_index"] for h in hits],
            "route_gap_to_new_cross_beam_cm": min(h["route_gap_cm"] for h in hits),
            "housing_before": {"top_box": placement["geometry"]["top_box"],
                               "top_axis": placement["geometry"]["top_axis"],
                               "bottom_box": placement["geometry"]["bottom_box"],
                               "centre": placement["geometry"]["centre"]},
            "housing_after": {"top_box": after["top_box"], "top_axis": after["top_axis"],
                              "bottom_box": after["bottom_box"], "centre": after["centre"]},
            "top_before": top, "top_after": top_after,
            "line": {"current_depth_after": line_state(after, placement, plain, structure["gridiron_depth_cm"]),
                     "new_depth_after": line_state(after, placement, plain, NEW_BEAM_DEPTH_CM)},
        })

    expected = options.get("expected_targets")
    if expected is not None:
        require(int(expected) == len(targets), "EXPECTED_TARGETS|expected=%s|planned=%d" % (expected, len(targets)))
    expected_drop = options.get("expected_drop_cm")
    if expected_drop is not None:
        require(abs(float(expected_drop) - drop) < 1.0e-9,
                "EXPECTED_DROP|expected=%s|planned=%.1f" % (expected_drop, drop))

    target_ids = sorted({t["attachment_guid"] for t in targets})
    return {
        "passage": names["key"], "structure_label": names["structure_label"], "label_regex": regex_text,
        "top_convention": convention, "clearance_cm": CLEARANCE_CM, "phase_state": phase,
        "drop_cm": drop, "drop_raw_cm": raw, "placements": len(placements),
        "stations": len(plain["stations"]), "cross_beam_stations": [b["station_index"] for b in beams],
        "moving_lights_without_housing": moving, "instance_worst_error_cm": worst,
        "targets": sorted(targets, key=lambda t: (t["station_index"], t["attachment_index"])),
        "target_cue_guids": sorted({t["cue_guid"] for t in targets}),
        "target_attachment_guids": target_ids,
        "non_score_targets": sorted(t["attachment_label"] for t in targets if not t["score_label"]),
        "regex_matches_not_intersecting": non_intersecting,
        "other_housings_in_new_band": others,
    }


# --------------------------------------------------------------------------
# Scope guards, offline mutation model, revert model — base tool.
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


def check_record_passage(record, passage):
    """A record may only ever be reverted by its own passage."""
    key = passage_names(passage)["key"]
    require(record.get("passage") == key and record.get("plan", {}).get("passage") == key,
            "RECORD_PASSAGE_MISMATCH|record=%s|plan=%s|requested=%s"
            % (record.get("passage"), record.get("plan", {}).get("passage"), key))
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|" + str(record.get("status")))


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


def check_args(mode, passage, confirm, label_regex=DEFAULT_LABEL_REGEX, top_convention="BOX"):
    """Mode, passage and the '<MODE> <passage>' confirmation; regex and convention well formed."""
    mode = str(mode or "DRY").upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    key = passage_names(passage)["key"]
    if mode != "DRY":
        require(confirm == "%s %s" % (mode, key), "CONFIRM_MISSING|mode=%s|need='%s %s'" % (mode, mode, key))
    compile_label_regex(label_regex)
    convention = str(top_convention or "BOX").upper()
    require(convention in TOP_CONVENTIONS, "TOP_CONVENTION_INVALID|" + convention)
    return mode, key, convention


def check_apply_gate(passage, plan, unacked, folder=None):
    """APPLY-only refusals: this passage's own active record, unacked foreign records, non-score labels."""
    path = record_path(passage, folder)
    require(plan["passage"] == passage_names(passage)["key"], "PLAN_PASSAGE_MISMATCH|" + str(plan["passage"]))
    require(not os.path.exists(path), "ACTIVE_REVERT_RECORD_EXISTS|" + path)
    require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
    require(not plan["non_score_targets"], "NON_SCORE_TARGETS|narrow label_regex|" + ";".join(plan["non_score_targets"]))
    return path


# --------------------------------------------------------------------------
# Module loading (lighting_scores_apply.py, then its load_p04_tool()) — base tool.
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
    scores = load_without_main(SCORES_TOOL_PATH, "_lighting_scores_for_rig_lamp_drop")
    missing = [n for n in SCORES_REQUIRED if not callable(getattr(scores, n, None))]
    require(not missing, "SCORES_API_DRIFT|" + ",".join(missing))
    tool = scores.load_p04_tool()   # validates the P04 tool's API by name and parameters
    missing = [n for n in TOOL_EXTRA_REQUIRED if not hasattr(tool, n)]
    require(not missing, "P04_TOOL_API_DRIFT|" + ",".join(missing))
    return scores, tool


def scan_foreign(scores, plan, passage, saved_dir=None):
    """Active records anywhere under Saved/Codex* mentioning a target GUID, except our own."""
    saved = saved_dir or os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, plan["target_attachment_guids"], exclude=[record_path(passage)])


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


def _find_structure(show, names):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = [a for a in subsystem.get_all_level_actors()
             if a.get_class().get_name() == "InfinityStageStructureActor"
             and a.get_actor_label() == names["structure_label"]]
    require(len(found) == 1, "STRUCTURE_COUNT|label=%s|count=%d" % (names["structure_label"], len(found)))
    structure = found[0]
    passage = structure.get_editor_property("passage")
    require(passage is not None and passage.get_actor_label().startswith(names["actor_prefix"]),
            "STRUCTURE_PASSAGE_WRONG|" + names["key"])
    require(passage.get_editor_property("show_asset") == show, "STRUCTURE_SHOW_WRONG")
    return structure


def _stations(tool, structure):
    """Live station frames: the C++ GatherStations (Route spline frames, .cpp:261-265)."""
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
             "distance_cm": float(s.get_editor_property("distance_cm")),
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
            "section_variation": float(grid.get_editor_property("section_variation")),
            "cross_beam_every": int(grid.get_editor_property("cross_beam_every")),
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
    """Set the targets' relative Translation.Z to plan[field]; rotation untouched (base tool)."""
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


def live_housing_check(plain, plan):
    """After the re-fit: the ISM must match the maths again and every target clear every beam."""
    require(plain["structure"]["current"], "STRUCTURE_NOT_CURRENT_AFTER_REFIT")
    check_frames(plain)
    placements, unused = gather_placements(plain)
    worst = check_instances(placements, plain["instances"])
    beams = [beam_box(plain, i) for i in cross_beam_stations(plain)]
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
        still, unused = beam_hits(placement["geometry"], beams, plan["top_convention"])
        require(not still, "LIVE_HOUSING_STILL_HITS_BEAM|label=%s|stations=%s"
                % (target["attachment_label"], [h["station_index"] for h in still]))
        tops[target["attachment_guid"]] = round(top, 3)
    return {"instance_worst_error_cm": worst, "live_tops": tops,
            "fixture_body_count": plain["structure"]["fixture_body_count"]}


def _fail_marker(run, mode, passage, reason):
    return "RIG_LAMP_DROP_FAILED|run=%s|passage=%s|mode=%s|reason=%s" % (run, passage, mode, reason)


def _run(mode, passage, label_regex, ack_records, convention, expected_targets, expected_drop_cm):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    names = passage_names(passage)
    key = names["key"]
    own_record = record_path(key)
    report = {"ok": False, "mode": mode, "passage": key, "run": run, "label_regex": label_regex}
    tool = None
    try:
        scores, tool = load_modules()
        report["sources"] = {"scores_sha256": scores.SOURCE_SHA256, "p04_tool_sha256": tool.SCORES_SOURCE_SHA256}
        world = tool._require_context()          # P04 tool's own gate (project, world, PIE, Sequencer, census, ZZ_)
        check_context(_ctx_facts(tool, world))   # same facts through the tested pure gate
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        require(scores._count_passage_actors(show, names["actor_prefix"]) == 1, "PASSAGE_ACTOR_COUNT|" + key)
        structure = _find_structure(show, names)
        plain = _runtime_plain(tool, show, structure)
        require(plain["structure"]["current"], "STRUCTURE_NOT_CURRENT_BEFORE")
        report["structure"] = plain["structure"]
        report["station_frames"] = [{"index": i, "cue_guid": s["cue_guid"], "distance_cm": s["distance_cm"],
                                     "location": s["world"]["location"],
                                     "yaw_deg": math.degrees(math.atan2(unit_axis(s["world"], 0)[1],
                                                                       unit_axis(s["world"], 0)[0]))}
                                    for i, s in enumerate(plain["stations"])]

        if mode in ("DRY", "APPLY"):
            plan = build_plan(plain, key, {"label_regex": label_regex, "top_convention": convention,
                                           "expected_targets": expected_targets,
                                           "expected_drop_cm": expected_drop_cm})
            before_all = _all_rows(plain)
            texts_hash = export_hash(_export_texts(show), plan["target_attachment_guids"])
            foreign = scan_foreign(scores, plan, key)
            unacked = sorted({h["path"] for h in foreign} - set(ack_records or []))
            report.update({"plan": plan, "foreign_records": foreign, "unacknowledged_foreign_records": unacked,
                           "active_record": own_record if os.path.exists(own_record) else None})
            if mode == "DRY":
                for t in plan["targets"]:
                    _log("RIG_LAMP_DROP_DRY_ROW|run=%s|passage=%s|label=%s|cue=%s|guid=%s|z=%.3f->%.3f"
                         "|top_%s=%.2f->%.2f|band_lo=%.2f|beams=%s|route_gap=%.2f|bottom_after=%.2f|line_new_depth=%s"
                         % (run, key, t["attachment_label"], t["cue_label"], t["attachment_guid"], t["z_before"],
                            t["z_after"], plan["top_convention"].lower(), t["top_before"], t["top_after"],
                            t["band_lo_cm"], t["beam_stations_hit"], t["route_gap_to_new_cross_beam_cm"],
                            t["housing_after"]["bottom_box"], t["line"]["new_depth_after"]))
                for o in plan["regex_matches_not_intersecting"]:
                    _log("RIG_LAMP_DROP_DRY_MATCH_CLEAR|run=%s|passage=%s|label=%s|top=%.2f|route_gap=%s|lateral_gap=%s"
                         % (run, key, o["label"], o["top"], o["nearest_route_gap_cm"], o["nearest_lateral_gap_cm"]))
                for o in plan["other_housings_in_new_band"]:
                    _log("RIG_LAMP_DROP_DRY_OTHER_IN_BAND|run=%s|passage=%s|label=%s|top=%.2f|hits_beam=%s"
                         % (run, key, o["label"], o["top"], o["hits_new_cross_beam_box"]))
                require(tool._dirty_census() == {"content": [], "maps": []}, "DRY_DIRTIED")
                report.update({"ok": True, "mutated": False})
                tool._write_json(report_path(key, mode, run), report)
                _log("RIG_LAMP_DROP_DRY_OK|run=%s|passage=%s|targets=%d|drop_cm=%.1f|convention=%s|phase=%s"
                     "|matches_clear=%d|non_score_targets=%d|others_in_band=%d|foreign=%d|unacked=%d|mutated=0"
                     % (run, key, len(plan["targets"]), plan["drop_cm"], plan["top_convention"],
                        plan["phase_state"], len(plan["regex_matches_not_intersecting"]),
                        len(plan["non_score_targets"]), len(plan["other_housings_in_new_band"]),
                        len(foreign), len(unacked)))
                return report

            check_apply_gate(key, plan, unacked)
            backup = tool._backup(backup_prefix(key), run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "passage": key, "backup": backup,
                      "plan": plan,
                      "outside_before_hash": tool._outside_hash(before_all, plan["target_cue_guids"]),
                      "export_hash_before": texts_hash,
                      "before_target_rows": target_rows(before_all, plan),
                      "after_target_rows": target_rows(apply_plain(before_all, plan), plan),
                      "acknowledged_records": list(ack_records or [])}
            tool._write_json(own_record, record, exclusive=True)   # fsynced before any mutation
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
                tool._write_json(own_record, record)
                os.rename(own_record, own_record + ".failed-" + run)
                raise
            record["status"] = "mutated_verified"
            tool._write_json(own_record, record)
            materialized = scores._materialize_passage(show, names["actor_prefix"])
            require(materialized.get("structure") == names["structure_label"], "STRUCTURE_NOT_REFIT|%s" % materialized)
            live = live_housing_check(_runtime_plain(tool, show, structure), plan)
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
            tool._write_json(own_record, record)
            tool._queue_master_test(world, "RIG_LAMP_DROP_" + key, run)
            report.update({"ok": True, "backup": backup, "record": own_record, "materialized": materialized,
                           "live": live, "tests_required": list(SUCCESS_TESTS)})
            tool._write_json(report_path(key, mode, run), report)
            _log("RIG_LAMP_DROP_APPLY_OK|run=%s|passage=%s|targets=%d|drop_cm=%.1f|convention=%s|show_saved=1"
                 "|level_saved=1|readback=1|structure_refit=1|saved_master=queued"
                 % (run, key, len(plan["targets"]), plan["drop_cm"], plan["top_convention"]))
            return report

        # REVERT
        require(os.path.isfile(own_record), "REVERT_RECORD_ABSENT|" + own_record)
        record = tool._read_json(own_record)
        check_record_passage(record, key)
        plan = record["plan"]
        before_all = _all_rows(plain)
        reverted_model = revert_plain(before_all, record)       # drift check + exactness on plain data
        texts_hash = export_hash(_export_texts(show), plan["target_attachment_guids"])
        backup = tool._backup(backup_prefix(key, revert=True), run)
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
        materialized = scores._materialize_passage(show, names["actor_prefix"])
        require(materialized.get("structure") == names["structure_label"], "STRUCTURE_NOT_REFIT|%s" % materialized)
        tool._save_narrow()
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = _all_rows(_runtime_plain(tool, readback, structure))
        require(_canonical(target_rows(read_all, plan)) == _canonical(record["before_target_rows"]),
                "REVERT_READBACK_NOT_EXACT")
        check_scope(tool, before_all, read_all, plan, "z_before")
        archived = own_record + ".reverted-" + run
        os.rename(own_record, archived)
        tool._queue_master_test(world, "RIG_LAMP_DROP_REVERT_" + key, run)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized})
        tool._write_json(report_path(key, mode, run), report)
        _log("RIG_LAMP_DROP_REVERT_OK|run=%s|passage=%s|targets=%d|show_saved=1|level_saved=1|readback=1"
             "|saved_master=queued" % (run, key, len(plan["targets"])))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path(key, mode, run), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        unreal.log_error(_fail_marker(run, mode, key, report["error"]))
        raise


def main():
    g = globals()
    mode, passage, convention = check_args(g.get("RIG_LAMP_DROP_MODE", "DRY"), g.get("RIG_LAMP_DROP_PASSAGE"),
                                           g.get("RIG_LAMP_DROP_CONFIRM"),
                                           g.get("RIG_LAMP_DROP_LABEL_REGEX", DEFAULT_LABEL_REGEX),
                                           g.get("RIG_LAMP_DROP_TOP_CONVENTION", "BOX"))
    require(unreal is not None, "UNREAL_REQUIRED")
    return _run(mode, passage, g.get("RIG_LAMP_DROP_LABEL_REGEX", DEFAULT_LABEL_REGEX),
                list(g.get("RIG_LAMP_DROP_ACK_RECORDS", []) or []), convention,
                g.get("RIG_LAMP_DROP_EXPECTED_TARGETS"), g.get("RIG_LAMP_DROP_EXPECTED_DROP_CM"))


if unreal is not None:
    main()
