"""Offline harness for rig_lamp_drop.py (plain-data fake Show, several passages; no Unreal).

Ports test_p03_housing_drop.py's coverage to multi-passage and adds: a curved
route (P02-like, yaw 22.9 -> 0 deg), regex matches that do not intersect, zero
targets refused, CrossBeamEvery, span, non-score (look) labels, and per-passage
record isolation. Every gate has a passing case and a failing control that must
raise with the named reason. Run: python test_rig_lamp_drop.py
"""
from __future__ import annotations

import copy
import glob
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("rig_lamp_drop", os.path.join(HERE, "rig_lamp_drop.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SCORES, TOOL = M.load_modules()

RESULTS = []
FOUND = {}


def case(name):
    def wrap(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
        except Exception as error:  # noqa: BLE001
            RESULTS.append((name, False, "%s: %s\n%s" % (type(error).__name__, error, traceback.format_exc())))
        return fn
    return wrap


def refuses(reason, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as error:  # noqa: BLE001
        assert reason in str(error), "expected %s, got %s" % (reason, error)
        return str(error)
    raise AssertionError("expected refusal %s, but it passed" % reason)


# ---------------------------------------------------------------- fake Show
IDENTITY = {"location": [0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]}
SLASH_Q = [0.125472, 0.257312, -0.419949, 0.861214]
# Real score TOP aims (lighting_scores_record_P02.json, "P02 SCORE B01 INDUSTRIAL TOP_L/TOP_R").
TOP_L_Q = [0.3568374474759053, 0.35683744747590534, -0.6104646067372624, 0.6104646067372625]
TOP_R_Q = [0.3770015943287691, -0.3770015943287692, -0.5982221977439204, -0.5982221977439204]


def _row(guid, label, kind="LIGHT", anchor="STATION", enabled=True, loc=(0.0, 0.0, 0.0), q=(0, 0, 0, 1)):
    norm = math.sqrt(sum(c * c for c in q))
    return {"guid": guid, "label": label, "kind": "<InfinityAttachmentKind.%s: 1>" % kind, "enabled": enabled,
            "actor_class": None, "mesh": None, "anchor": "<InfinityAttachmentAnchor.%s: 0>" % anchor,
            "relative_transform": {"location": [float(v) for v in loc], "rotation_xyzw": [c / norm for c in q],
                                   "scale": [1.0, 1.0, 1.0]},
            "lighting": {"intensity": 100.0, "cast_shadows": True}, "effect": {"output": 0.5},
            "trigger_distance_cm": 800.0}


def _guid(prefix, n):
    return (prefix + str(n).zfill(32 - len(prefix))).upper()


def _yaw_q(deg):
    half = math.radians(deg) / 2.0
    return [0.0, 0.0, math.sin(half), math.cos(half)]


def station_frames(n, yaw0=0.0, z=0.0, origin=(0.0, 0.0), spacing=500.0):
    """Stations along the route. yaw0 != 0: a curve turning linearly from yaw0 to 0 (P02-like)."""
    frames, x, y = [], float(origin[0]), float(origin[1])
    for k in range(n):
        yaw = yaw0 * (1.0 - k / float(max(1, n - 1)))
        frames.append({"location": [x, y, z], "rotation_xyzw": _yaw_q(yaw), "scale": [1.0, 1.0, 1.0]})
        x += spacing * math.cos(math.radians(yaw))
        y += spacing * math.sin(math.radians(yaw))
    return frames


def _structure(passage, every=1, half_width=1128.0, height=1150.0, depth=90.0, width=40.0, variation=0.0,
               body=(45.0, 32.0, 32.0)):
    return {"label": M.STRUCTURE_LABEL_FMT % int(passage[1:]), "fixtures_enabled": True,
            "body_size_cm": list(body), "body_mesh_bounds": {"min": [-50.0] * 3, "max": [50.0] * 3},
            "hang_from_grid": True, "max_drop_cm": 900.0, "gridiron_enabled": True,
            "gridiron_height_cm": height, "gridiron_depth_cm": depth, "gridiron_width_cm": width,
            "section_variation": variation, "cross_beam_every": every, "grid_half_width_cm": half_width,
            "fixture_body_count": 0, "current": True}


PASSAGE_ORIGINS = {"P01": (0.0, 0.0), "P02": (40000.0, 0.0), "P03": (80000.0, 0.0), "P04": (120000.0, 0.0),
                   "P05": (160000.0, 0.0), "P06": (200000.0, 0.0)}


def make_world(specs):
    """specs: [{"passage", "n", "yaw0", "z", "every", "half_width", "look_bays"}]. One Show, one plain per passage."""
    cues, plains = [], {}
    show_index = 0
    for spec in specs:
        key = spec["passage"]
        tag = key[1:]
        frames = station_frames(spec.get("n", 6), spec.get("yaw0", 0.0), spec.get("z", 0.0), PASSAGE_ORIGINS[key])
        stations = []
        for k, frame in enumerate(frames):
            cue_guid = _guid("C" + tag, k)
            look = "MOODY%d" % (k % 3)
            attachments = [
                _row(_guid("S" + tag, k), "%s Wing %03d Rig Slash" % (key, k + 1), loc=(-40.0, 180.0, 1058.0), q=SLASH_Q),
                _row(_guid("L" + tag, k), "%s SCORE B%02d %s TOP_L" % (key, k + 1, look), loc=(0.0, -360.0, 1180.0), q=TOP_L_Q),
                _row(_guid("R" + tag, k), "%s SCORE B%02d %s TOP_R" % (key, k + 1, look), loc=(0.0, 360.0, 1180.0), q=TOP_R_Q),
                _row(_guid("D" + tag, k), "%s SCORE B%02d %s TOP_X disabled" % (key, k + 1, look), enabled=False,
                     loc=(0.0, 0.0, 1180.0), q=TOP_L_Q),
                _row(_guid("P" + tag, k), "prop TOP_L", kind="PROP", loc=(0.0, 0.0, 1180.0)),
                _row(_guid("M" + tag, k), "panel lamp TOP_L", anchor="LEFT_PANEL", loc=(0.0, -500.0, 1180.0)),
            ]
            if k < spec.get("look_bays", 0):
                attachments.append(_row(_guid("K" + tag, k), "%s LOOK B%02d INDUSTRIAL TOP_L" % (key, k + 1),
                                        loc=(0.0, -200.0, 1180.0), q=TOP_L_Q))
            cues.append({"show_index": show_index, "guid": cue_guid, "label": "%s Wing %03d" % (key, k + 1),
                         "type": "<InfinityCueType.WING_PAIR: 0>", "occurrence_offset": copy.deepcopy(IDENTITY),
                         "attachments": attachments})
            show_index += 1
            stations.append({"cue_guid": cue_guid, "world": frame})
        plains[key] = {"cues": cues, "stations": stations, "bay_guids": [s["cue_guid"] for s in stations],
                       "structure": _structure(key, every=spec.get("every", 1),
                                               half_width=spec.get("half_width", 1128.0),
                                               body=spec.get("body", (45.0, 32.0, 32.0)))}
    for plain in plains.values():
        refit(plain)
    return plains


def refit(plain):
    placements, unused = M.gather_placements(plain)
    plain["instances"] = [list(p["geometry"]["instance_location"]) for p in placements]
    plain["structure"]["fixture_body_count"] = len(placements)
    return plain


def world1(passage="P03", **spec):
    spec = dict(spec, passage=passage)
    return make_world([spec])[passage]


def all_rows(plain):
    return {c["guid"]: copy.deepcopy(c["attachments"]) for c in plain["cues"]}


def find_row(plain, guid):
    for cue in plain["cues"]:
        for row in cue["attachments"]:
            if row["guid"] == guid:
                return row
    raise KeyError(guid)


def box_top_identity(loc, q):
    """BOX top of a housing on an upright identity station (hand formula through the module maths)."""
    plain = {"structure": _structure("P01")}
    light = M.compose({"location": list(loc), "rotation_xyzw": list(q), "scale": [1.0, 1.0, 1.0]}, IDENTITY)
    return M.housing_geometry(light, IDENTITY, plain["structure"])["top_box"]


# ---------------------------------------------------------------- args / names
@case("args gate: '<MODE> <passage>' required for writes; passage, regex, convention validated")
def _():
    assert M.check_args("dry", "p02", None) == ("DRY", "P02", "BOX")
    assert M.check_args("APPLY", "P04", "APPLY P04")[0] == "APPLY"
    assert M.check_args("REVERT", "P01", "REVERT P01", "SCORE .*TOP_[LR]$", "axis")[2] == "AXIS"
    refuses("CONFIRM_MISSING", M.check_args, "APPLY", "P04", None)
    refuses("CONFIRM_MISSING", M.check_args, "APPLY", "P04", "APPLY P01")      # other passage
    refuses("CONFIRM_MISSING", M.check_args, "REVERT", "P04", "APPLY P04")     # other mode
    refuses("MODE_INVALID", M.check_args, "FINISH", "P04", "FINISH P04")
    refuses("PASSAGE_INVALID", M.check_args, "DRY", "P07", None)
    refuses("PASSAGE_INVALID", M.check_args, "DRY", None, None)
    refuses("LABEL_REGEX_INVALID", M.check_args, "DRY", "P01", None, "TOP_[LR")
    refuses("LABEL_REGEX_EMPTY", M.check_args, "DRY", "P01", None, "  ")
    refuses("TOP_CONVENTION_INVALID", M.check_args, "DRY", "P01", None, "TOP_[LR]$", "MIDDLE")


@case("names: per-passage structure label, actor prefix, record, report and backup prefix")
def _():
    names = M.passage_names("P02")
    assert names["structure_label"] == "Infinity Stage - Structure 02" and names["actor_prefix"] == "Passage 02"
    paths = {M.record_path(p) for p in M.PASSAGES}
    assert len(paths) == 6 and M.record_path("P04").endswith("rig_lamp_drop_record_P04.json")
    assert M.backup_prefix("P04") == "PreRigLampDrop-P04-" and M.backup_prefix("P04", True) == "PreRigLampDropRevert-P04-"
    assert M.report_path("P01", "DRY", "R") != M.report_path("P04", "DRY", "R")
    refuses("PASSAGE_INVALID", M.record_path, "P00")


# ---------------------------------------------------------------- selection
@case("selection: regex AND intersects; Rig Slash, disabled, prop and panel lamps excluded")
def _():
    plain = world1("P03")
    plan = M.build_plan(plain, "P03")
    labels = [t["attachment_label"] for t in plan["targets"]]
    assert len(labels) == 12 and all(l.endswith(("TOP_L", "TOP_R")) and " SCORE " in l for l in labels), labels
    assert plan["placements"] == 18 and plan["moving_lights_without_housing"] == 6     # 6 slash + 12 TOP
    assert not plan["regex_matches_not_intersecting"] and not plan["non_score_targets"]
    assert all(t["beam_stations_hit"] == [t["station_index"]] for t in plan["targets"])
    # control: enabling the disabled TOP_X lamp adds a housing (it does not match TOP_[LR]$, so not a target)
    find_row(plain, _guid("D03", 0))["enabled"] = True
    refit(plain)
    plan2 = M.build_plan(plain, "P03")
    assert plan2["placements"] == 19 and len(plan2["targets"]) == 12
    assert any(o["label"].endswith("TOP_X disabled") for o in plan2["other_housings_in_new_band"])


@case("selection: matches that do not intersect are reported, not targeted (between beams, below band)")
def _():
    plain = world1("P05")
    find_row(plain, _guid("L05", 1))["relative_transform"]["location"][0] = 250.0     # midway between beams
    find_row(plain, _guid("R05", 2))["relative_transform"]["location"][2] = 900.0     # well below the band
    refit(plain)
    plan = M.build_plan(plain, "P05")
    assert len(plan["targets"]) == 10
    clear = {o["label"]: o for o in plan["regex_matches_not_intersecting"]}
    assert len(clear) == 2, clear
    mid = [o for o in clear.values() if "B02" in o["label"]][0]
    low = [o for o in clear.values() if "B03" in o["label"]][0]
    assert mid["nearest_route_gap_cm"] > 0.0 and mid["own_station_in_band_height"]
    assert low["nearest_route_gap_cm"] < 0.0 and not low["own_station_in_band_height"]
    assert not any(o["hits_new_cross_beam_box"] for o in clear.values())
    # control: put them back -> all 12 are targets again
    find_row(plain, _guid("L05", 1))["relative_transform"]["location"][0] = 0.0
    find_row(plain, _guid("R05", 2))["relative_transform"]["location"][2] = 1180.0
    refit(plain)
    assert len(M.build_plan(plain, "P05")["targets"]) == 12


@case("selection: 2 cm route gap is clear, 2 cm overlap is a target (route-gap maths)")
def _():
    plain = world1("P05")
    probe = M.gather_placements(plain)[0]
    half = [p for p in probe if p["attachment_guid"] == _guid("L05", 0)][0]["geometry"]["route_half_extent_cm"]
    edge = half + M.NEW_BEAM_WIDTH_CM * 0.5
    row = find_row(plain, _guid("L05", 0))
    centre_shift = M.gather_placements(plain)[0][1]["geometry"]["centre"][0] - plain["stations"][0]["world"]["location"][0]
    row["relative_transform"]["location"][0] = edge + 2.0 - centre_shift
    refit(plain)
    plan = M.build_plan(plain, "P05")
    assert _guid("L05", 0) not in plan["target_attachment_guids"]
    gap = [o for o in plan["regex_matches_not_intersecting"] if o["attachment_guid"] == _guid("L05", 0)][0]
    assert abs(gap["nearest_route_gap_cm"] - 2.0) < 1e-6, gap
    row["relative_transform"]["location"][0] = edge - 2.0 - centre_shift               # control
    refit(plain)
    assert _guid("L05", 0) in M.build_plan(plain, "P05")["target_attachment_guids"]


@case("selection: CrossBeamEvery=2 -> lamps on beamless stations are not targets; every=1 control")
def _():
    plain = world1("P06", every=2)
    plan = M.build_plan(plain, "P06")
    assert plan["cross_beam_stations"] == [0, 2, 4]
    assert sorted({t["station_index"] for t in plan["targets"]}) == [0, 2, 4] and len(plan["targets"]) == 6
    assert len(plan["regex_matches_not_intersecting"]) == 6
    plain["structure"]["cross_beam_every"] = 1
    assert len(M.build_plan(plain, "P06")["targets"]) == 12


@case("selection: lamps beyond the cross beam's span are not targets; wide-span control")
def _():
    plain = world1("P05", half_width=300.0)
    refuses("ZERO_TARGETS", M.build_plan, plain, "P05")
    plain["structure"]["grid_half_width_cm"] = 470.0
    assert len(M.build_plan(plain, "P05")["targets"]) == 12


@case("zero targets refused: all TOP lamps already under the band, or a regex matching nothing")
def _():
    plain = world1("P01")
    refuses("ZERO_TARGETS", M.build_plan, plain, "P01", {"label_regex": "NOPE$"})
    for cue in plain["cues"]:
        for row in cue["attachments"]:
            if row["label"].endswith(("TOP_L", "TOP_R")):
                row["relative_transform"]["location"][2] = 1040.0
    refit(plain)
    error = refuses("ZERO_TARGETS", M.build_plan, plain, "P01")
    assert "regex_matches=12" in error, error
    find_row(plain, _guid("L01", 3))["relative_transform"]["location"][2] = 1180.0     # control: one back up
    refit(plain)
    assert len(M.build_plan(plain, "P01")["targets"]) == 1


@case("5 Oct: explicit non-score approval + tagged record (P04 LOOK lamps); controls")
def _():
    plain = world1("P04", look_bays=6)
    looks_only = M.build_plan(plain, "P04", {"label_regex": "LOOK .*TOP_[LR]$"})
    assert len(looks_only["targets"]) == 6 and len(looks_only["non_score_targets"]) == 6
    folder = tempfile.mkdtemp()
    try:
        M.ALLOW_NON_SCORE_BECAUSE, M.RECORD_TAG = "", ""
        refuses("NON_SCORE_TARGETS", M.check_apply_gate, "P04", looks_only, [], folder)   # control: no approval
        M.ALLOW_NON_SCORE_BECAUSE = "Gary 5 Oct: rehang to correct physical position on girders"
        untagged = M.record_path("P04", folder)
        M.RECORD_TAG = "LOOKS"
        tagged = M.check_apply_gate("P04", looks_only, [], folder)                         # approved: passes
        assert tagged.endswith("rig_lamp_drop_record_P04_LOOKS.json") and tagged != untagged
        open(untagged, "w").write("{}")                                                    # score batch's record
        M.check_apply_gate("P04", looks_only, [], folder)                                  # does not block the tag
        open(tagged, "w").write("{}")
        refuses("ACTIVE_REVERT_RECORD_EXISTS", M.check_apply_gate, "P04", looks_only, [], folder)  # control
    finally:
        M.ALLOW_NON_SCORE_BECAUSE, M.RECORD_TAG = "", ""
        shutil.rmtree(folder)


@case("non-score labels (P04 looks) match TOP_[LR]$: listed, APPLY refuses; narrowed regex control")
def _():
    plain = world1("P04", look_bays=6)
    plan = M.build_plan(plain, "P04")
    assert len(plan["non_score_targets"]) == 6 and len(plan["targets"]) == 18
    folder = tempfile.mkdtemp()
    try:
        refuses("NON_SCORE_TARGETS", M.check_apply_gate, "P04", plan, [], folder)
        narrow = M.build_plan(plain, "P04", {"label_regex": "SCORE .*TOP_[LR]$"})
        assert len(narrow["targets"]) == 12 and not narrow["non_score_targets"]
        looks = [o for o in narrow["other_housings_in_new_band"] if " LOOK " in o["label"]]
        assert len(looks) == 6 and all(o["hits_new_cross_beam_box"] and not o["matches_regex"] for o in looks)
        M.check_apply_gate("P04", narrow, [], folder)
    finally:
        shutil.rmtree(folder)


# ---------------------------------------------------------------- curved route
@case("curved route (P02-like 22.9 -> 0 deg): frames from stations, every TOP lamp judged in its own frame")
def _():
    curved = world1("P02", n=8, yaw0=22.9)
    straight = world1("P02", n=8, yaw0=0.0)
    yaws = [math.degrees(math.atan2(M.unit_axis(s["world"], 0)[1], M.unit_axis(s["world"], 0)[0]))
            for s in curved["stations"]]
    assert abs(yaws[0] - 22.9) < 1e-9 and abs(yaws[-1]) < 1e-9
    plan_c, plan_s = M.build_plan(curved, "P02"), M.build_plan(straight, "P02")
    assert len(plan_c["targets"]) == 16 and len(plan_s["targets"]) == 16
    assert plan_c["drop_cm"] == plan_s["drop_cm"]                       # yaw-invariant for upright frames
    for tc, ts in zip(plan_c["targets"], plan_s["targets"]):
        assert abs(tc["route_gap_to_new_cross_beam_cm"] - ts["route_gap_to_new_cross_beam_cm"]) < 1e-6
        assert tc["beam_stations_hit"] == [tc["station_index"]]
    # the moved housing centre stays in the station's own frame: pure world Z
    for t in plan_c["targets"]:
        b, a = t["housing_before"]["centre"], t["housing_after"]["centre"]
        assert abs(b[0] - a[0]) < 1e-9 and abs(b[1] - a[1]) < 1e-9 and abs(b[2] - a[2] - plan_c["drop_cm"]) < 1e-9


@case("curved route control: frames ASSUMED straight along the chord do not match the live ISM -> refuse")
def _():
    curved = world1("P02", n=8, yaw0=22.9)
    first, last = curved["stations"][0]["world"]["location"], curved["stations"][-1]["world"]["location"]
    chord_yaw = math.degrees(math.atan2(last[1] - first[1], last[0] - first[0]))
    assumed = copy.deepcopy(curved)
    for k, station in enumerate(assumed["stations"]):
        f = k / 7.0
        station["world"] = {"location": [first[0] + f * (last[0] - first[0]), first[1] + f * (last[1] - first[1]), 0.0],
                            "rotation_xyzw": _yaw_q(chord_yaw), "scale": [1.0, 1.0, 1.0]}
    refuses("INSTANCE_GEOMETRY_MISMATCH", M.build_plan, assumed, "P02")       # instances are the curved C++ ones
    M.build_plan(curved, "P02")                                               # control


@case("curved route: a neighbour's beam converging on the inside of a tight curve is detected")
def _():
    def hits_at(yaw0, x_rel):
        plain = world1("P02", n=4, yaw0=yaw0)       # 90 deg over 3 gaps: 30 deg per 5 m station, an extreme bend
        find_row(plain, _guid("L02", 1))["relative_transform"]["location"][0] = float(x_rel)
        refit(plain)
        beams = [M.beam_box(plain, i) for i in M.cross_beam_stations(plain)]
        placement = [p for p in M.gather_placements(plain)[0] if p["attachment_guid"] == _guid("L02", 1)][0]
        hits = M.beam_hits(placement["geometry"], beams, "BOX")[0]
        plan = M.build_plan(plain, "P02")
        return sorted(h["station_index"] for h in hits), plan
    found = None
    for x_rel in range(0, 500, 2):
        curved, plan = hits_at(90.0, x_rel)
        straight, unused = hits_at(0.0, x_rel)
        if curved and 1 not in curved and not straight:
            found = (x_rel, curved, plan)
            break
    assert found is not None, "no offset where only the converging neighbour beam is hit"
    x_rel, curved, plan = found
    target = [t for t in plan["targets"] if t["attachment_guid"] == _guid("L02", 1)][0]
    assert target["beam_stations_hit"] == curved and target["station_index"] == 1
    # control: on the straight route the same offset clears every beam (asserted in the search) and is not a target
    unused, straight_plan = hits_at(0.0, x_rel)
    assert _guid("L02", 1) not in straight_plan["target_attachment_guids"]
    FOUND["curve_x_rel"] = (x_rel, curved)


# ---------------------------------------------------------------- drop maths
@case("drop maths: uniform per passage, ceil to 0.1 cm, minimal, every target >= 5 cm under 1105")
def _():
    plain = world1("P03")
    find_row(plain, _guid("L03", 4))["relative_transform"]["location"][2] = 1170.0   # a lower one
    refit(plain)
    for convention in ("BOX", "AXIS"):
        plan = M.build_plan(plain, "P03", {"top_convention": convention})
        top = max(t["top_before"] for t in plan["targets"])
        want = round(math.ceil((top - 1100.0) * 10.0 - 1e-9) / 10.0, 1)
        assert plan["drop_cm"] == want, (convention, plan["drop_cm"], want)
        assert all(abs(t["z_before"] - t["z_after"] - plan["drop_cm"]) < 1e-9 for t in plan["targets"])
        assert all(t["top_after"] <= 1100.0 + 1e-6 for t in plan["targets"])
        assert top - (plan["drop_cm"] - 0.1) > 1100.0                     # control: 0.1 cm less is not enough
    box = M.build_plan(plain, "P03", {"top_convention": "BOX"})
    axis = M.build_plan(plain, "P03", {"top_convention": "AXIS"})
    assert box["drop_cm"] >= axis["drop_cm"]


@case("drop maths: BOX top of a TOP lamp equals the hand formula; rotation untouched by apply")
def _():
    plain = world1("P01")
    plan = M.build_plan(plain, "P01")
    t = [t for t in plan["targets"] if t["attachment_guid"] == _guid("L01", 0)][0]
    assert abs(t["top_before"] - box_top_identity((0.0, -360.0, 1180.0), TOP_L_Q)) < 1e-9
    after_rows = M.apply_plain(all_rows(plain), plan)
    for t in plan["targets"]:
        row = [r for r in after_rows[t["cue_guid"]] if r["guid"] == t["attachment_guid"]][0]
        src = find_row(plain, t["attachment_guid"])
        assert row["relative_transform"]["rotation_xyzw"] == src["relative_transform"]["rotation_xyzw"]
        assert row["relative_transform"]["location"][:2] == src["relative_transform"]["location"][:2]


@case("drop gate: a housing needing more than 150 cm refuses (DROP_TOO_LARGE); normal body control")
def _():
    plain = world1("P05", body=(45.0, 32.0, 120.0))
    for cue in plain["cues"]:
        for row in cue["attachments"]:
            if row["label"].endswith(("TOP_L", "TOP_R")):
                row["relative_transform"]["location"][2] = 1220.0   # top ~1288.7, bottom ~1190.6 < 1195
    refit(plain)
    refuses("DROP_TOO_LARGE", M.build_plan, plain, "P05")
    assert M.build_plan(world1("P05"), "P05")["drop_cm"] <= M.MAX_DROP_CM


@case("expected pins: expected_targets / expected_drop_cm must equal the plan")
def _():
    plain = world1("P01")
    plan = M.build_plan(plain, "P01")
    M.build_plan(plain, "P01", {"expected_targets": 12, "expected_drop_cm": plan["drop_cm"]})
    refuses("EXPECTED_TARGETS", M.build_plan, plain, "P01", {"expected_targets": 11})
    refuses("EXPECTED_DROP", M.build_plan, plain, "P01", {"expected_drop_cm": plan["drop_cm"] + 0.1})


# ---------------------------------------------------------------- structure gates
@case("frame gate: a 10 deg tilted station refuses; upright control")
def _():
    plain = world1("P01")
    half = math.radians(10.0) / 2.0
    plain["stations"][2]["world"]["rotation_xyzw"] = [math.sin(half), 0.0, 0.0, math.cos(half)]
    refit(plain)
    refuses("FRAME_NOT_VERTICAL", M.build_plan, plain, "P01")
    M.build_plan(world1("P01"), "P01")


@case("band gate: band judged relative to the station (route at z=500 passes); 1200 cm grid refuses")
def _():
    high = world1("P06", z=500.0)
    plan = M.build_plan(high, "P06")
    assert len(plan["targets"]) == 12 and all(abs(t["band_lo_cm"] - 1605.0) < 1e-9 for t in plan["targets"])
    plain = world1("P06")
    plain["structure"]["gridiron_height_cm"] = 1200.0
    refuses("BAND_DRIFT", M.build_plan, plain, "P06")


@case("phase gate: Phase A live or pre-Phase-A both plan the 90 cm band; anything else refuses")
def _():
    plain = world1("P03")
    assert M.build_plan(plain, "P03")["phase_state"] == "PHASE_A_LIVE"
    plain["structure"].update(gridiron_depth_cm=34.0, gridiron_width_cm=26.0, section_variation=0.06)
    pre = M.build_plan(plain, "P03")
    assert pre["phase_state"] == "PRE_PHASE_A" and len(pre["targets"]) == 12
    for update, reason in (({"gridiron_depth_cm": 60.0}, "PHASE_STATE_UNKNOWN"),
                           ({"gridiron_depth_cm": 90.0, "gridiron_width_cm": 26.0}, "PHASE_A_PARTIAL"),
                           ({"gridiron_depth_cm": 90.0, "gridiron_width_cm": 40.0, "section_variation": 0.06},
                            "PHASE_A_VARIATION_NONZERO")):
        bad = copy.deepcopy(plain)
        bad["structure"].update(update)
        refuses(reason, M.build_plan, bad, "P03")


@case("instance gate: live ISM 1 cm off refuses; count mismatch refuses")
def _():
    plain = world1("P04")
    bad = copy.deepcopy(plain)
    bad["instances"][3][2] += 1.0
    refuses("INSTANCE_GEOMETRY_MISMATCH", M.build_plan, bad, "P04")
    bad = copy.deepcopy(plain)
    bad["instances"].pop()
    refuses("INSTANCE_COUNT_MISMATCH", M.build_plan, bad, "P04")
    M.build_plan(plain, "P04")


@case("bay gate: a station outside the passage's bay list refuses")
def _():
    plain = world1("P04")
    plain["bay_guids"] = plain["bay_guids"][1:]
    refuses("STATION_OUTSIDE_PASSAGE", M.build_plan, plain, "P04")


@case("GUID gate: a target GUID duplicated elsewhere in the Show refuses")
def _():
    plains = make_world([{"passage": "P01"}, {"passage": "P04"}])
    find_row(plains["P01"], _guid("S01", 0))["guid"] = _guid("L04", 0)     # P01 slash reuses a P04 target GUID
    refuses("TARGET_GUID_NOT_UNIQUE", M.build_plan, plains["P04"], "P04")
    M.build_plan(make_world([{"passage": "P01"}, {"passage": "P04"}])["P04"], "P04")


# ---------------------------------------------------------------- per-passage isolation
@case("isolation: P04 plan touches only P04 cues; P01 rows and P01's record stay valid after P04 applies")
def _():
    plains = make_world([{"passage": "P01"}, {"passage": "P04"}])
    p01, p04 = M.build_plan(plains["P01"], "P01"), M.build_plan(plains["P04"], "P04")
    assert set(p04["target_cue_guids"]) <= set(plains["P04"]["bay_guids"])
    assert not set(p04["target_cue_guids"]) & set(plains["P01"]["bay_guids"])
    before = all_rows(plains["P01"])
    after_p01 = M.apply_plain(before, p01)
    record_p01 = {"plan": p01, "before_target_rows": M.target_rows(before, p01),
                  "after_target_rows": M.target_rows(after_p01, p01)}
    after_both = M.apply_plain(after_p01, p04)
    for guid in plains["P01"]["bay_guids"]:
        assert json.dumps(after_both[guid], sort_keys=True) == json.dumps(after_p01[guid], sort_keys=True)
    M.check_revert_drift(after_both, record_p01)                       # P01 revert still possible
    M.check_scope(TOOL, after_p01, after_both, p04)                    # P04's change is in P04 scope
    refuses("OUTSIDE_TARGET_SCOPE_CHANGED", M.check_scope, TOOL, before, after_both, p04)   # control: P01 moved too


@case("isolation: own record blocks APPLY of that passage only; record passage must match on REVERT")
def _():
    plains = make_world([{"passage": "P01"}, {"passage": "P04"}])
    p01, p04 = M.build_plan(plains["P01"], "P01"), M.build_plan(plains["P04"], "P04")
    folder = tempfile.mkdtemp()
    try:
        with open(M.record_path("P01", folder), "w", encoding="utf-8") as handle:
            json.dump({"status": "saved_readback_verified", "passage": "P01", "plan": p01}, handle)
        M.check_apply_gate("P04", p04, [], folder)                                       # P04 unaffected
        refuses("ACTIVE_REVERT_RECORD_EXISTS", M.check_apply_gate, "P01", p01, [], folder)
        refuses("PLAN_PASSAGE_MISMATCH", M.check_apply_gate, "P04", p01, [], folder)
        refuses("FOREIGN_ACTIVE_RECORDS_OVERLAP", M.check_apply_gate, "P04", p04, ["x_record.json"], folder)
        rec = {"status": "saved_readback_verified", "passage": "P01", "plan": p01}
        M.check_record_passage(rec, "P01")
        refuses("RECORD_PASSAGE_MISMATCH", M.check_record_passage, rec, "P04")
        refuses("REVERT_RECORD_STATUS", M.check_record_passage, dict(rec, status="prepared"), "P01")
    finally:
        shutil.rmtree(folder)


@case("isolation: foreign-record scan of P04 GUIDs ignores P01's record; P01 GUIDs find it (control)")
def _():
    plains = make_world([{"passage": "P01"}, {"passage": "P04"}])
    p01, p04 = M.build_plan(plains["P01"], "P01"), M.build_plan(plains["P04"], "P04")
    saved = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(saved, "CodexConductor"))
        with open(os.path.join(saved, "CodexConductor", "rig_lamp_drop_record_P01.json"), "w", encoding="utf-8") as h:
            json.dump({"status": "saved_readback_verified", "passage": "P01", "plan": p01}, h)
        assert M.scan_foreign(SCORES, p04, "P04", saved) == []
        hits = M.scan_foreign(SCORES, p01, "P04", saved)     # P01 GUIDs, seen from another passage's run
        assert len(hits) == 1 and hits[0]["path"].endswith("rig_lamp_drop_record_P01.json")
    finally:
        shutil.rmtree(saved)


# ---------------------------------------------------------------- outside guard (base ports)
@case("outside guard: the planned change passes")
def _():
    plain = world1("P02", yaw0=22.9)
    plan = M.build_plan(plain, "P02")
    before = all_rows(plain)
    M.check_scope(TOOL, before, M.apply_plain(before, plan), plan)


@case("outside guard controls: non-target cue, sibling field, target rotation, wrong Z, X all refuse")
def _():
    plains = make_world([{"passage": "P01"}, {"passage": "P02", "yaw0": 22.9}])
    plain = plains["P02"]
    plan = M.build_plan(plain, "P02")
    before = all_rows(plain)
    after = M.apply_plain(before, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C01", 0)][0]["lighting"]["intensity"] += 1.0                   # another passage's cue
    refuses("OUTSIDE_TARGET_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C02", 0)][0]["lighting"]["intensity"] += 1.0                   # Rig Slash in a target cue
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C02", 0)][1]["relative_transform"]["rotation_xyzw"][0] += 1e-6
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C02", 0)][1]["relative_transform"]["location"][2] += 1e-9
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C02", 0)][1]["relative_transform"]["location"][0] += 1.0
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, before, plan)   # nothing applied


EXPORT = ('(CueGuid=C1,Label=INVTEXT("P02 Wing 001"),WingPair=(Attachments=('
          '(AttachmentGuid=%s,Label=INVTEXT("P02 SCORE B01 X TOP_L"),Kind=Light,Anchor=Station,'
          'RelativeTransform=(Rotation=(X=0.35,Y=0.35,Z=-0.61,W=0.61),Translation=(X=0.000000,Y=-360.000000,Z=%s),'
          'Scale3D=(X=1.000000,Y=1.000000,Z=1.000000)),Effect=(LinkedLightAttachmentGuid=%s)),'
          '(AttachmentGuid=%s,Label=INVTEXT("Rig Slash"),RelativeTransform=(Rotation=(X=0,Y=0,Z=0,W=1),'
          'Translation=(X=-40.000000,Y=180.000000,Z=1058.000000),Scale3D=(X=1,Y=1,Z=1))))))')
TG, OG = "D2E6323C4C87C7AC728829BE579DC6ED", "3FACD8E44D4FDFD87CF919AEE2CDC4AB"


@case("export guard: only the target Translation.Z is masked")
def _():
    before = EXPORT % (TG, "1180.000000", OG, OG)
    after = EXPORT % (TG, "1053.400000", OG, OG)
    assert M.export_hash([before], [TG]) == M.export_hash([after], [TG])
    other = after.replace("Z=1058.000000", "Z=1057.000000")
    assert M.export_hash([before], [TG]) != M.export_hash([other], [TG])      # control: sibling Z moved
    rot = after.replace("Z=-0.61", "Z=-0.62")
    assert M.export_hash([before], [TG]) != M.export_hash([rot], [TG])        # control: rotation moved


@case("export guard controls: a target missing or present twice refuses; Linked GUID is not an owner")
def _():
    refuses("EXPORT_TARGET_COUNT", M.export_hash, [EXPORT % (OG, "1", TG, TG)], ["0" * 31 + "1"])
    text = EXPORT % (TG, "1180.000000", OG, OG)
    refuses("EXPORT_TARGET_COUNT", M.export_hash, [text, text], [TG])
    refuses("EXPORT_TARGET_COUNT", M.export_hash, [EXPORT % (OG, "1180.000000", TG, OG)], [TG])


# ---------------------------------------------------------------- revert (base ports)
def _record(plain, plan):
    before = all_rows(plain)
    after = M.apply_plain(before, plan)
    return before, after, {"plan": plan, "before_target_rows": M.target_rows(before, plan),
                           "after_target_rows": M.target_rows(after, plan)}


@case("revert exactness: apply then revert is bit-identical through JSON (awkward Z 1180.0000000001)")
def _():
    plain = world1("P02", yaw0=22.9)
    for cue in plain["cues"]:
        for row in cue["attachments"]:
            if row["label"].endswith(("TOP_L", "TOP_R")):
                row["relative_transform"]["location"][2] = 1180.0000000001
    refit(plain)
    plan = M.build_plan(plain, "P02")
    before, after, record = _record(plain, plan)
    record = json.loads(json.dumps(record))
    restored = M.revert_plain(after, record)
    assert json.dumps(restored, sort_keys=True) == json.dumps(before, sort_keys=True)
    for t in record["plan"]["targets"]:
        row = [r for r in restored[t["cue_guid"]] if r["guid"] == t["attachment_guid"]][0]
        assert repr(row["relative_transform"]["location"][2]) == repr(1180.0000000001)


@case("revert drift: target Z nudged 0.001, a target field changed, or never applied, refuses")
def _():
    plain = world1("P04")
    plan = M.build_plan(plain, "P04")
    before, after, record = _record(plain, plan)
    M.revert_plain(after, record)
    bad = copy.deepcopy(after)
    bad[_guid("C04", 2)][1]["relative_transform"]["location"][2] += 0.001
    refuses("REVERT_DRIFT", M.revert_plain, bad, record)
    bad = copy.deepcopy(after)
    bad[_guid("C04", 4)][2]["enabled"] = False
    refuses("REVERT_DRIFT", M.revert_plain, bad, record)
    refuses("REVERT_DRIFT", M.revert_plain, before, record)


@case("revert exactness control: a corrupted before-record refuses")
def _():
    plain = world1("P04")
    plan = M.build_plan(plain, "P04")
    before, after, record = _record(plain, plan)
    guid = plan["targets"][0]["attachment_guid"]
    record["before_target_rows"][guid]["relative_transform"]["location"][2] += 0.5
    refuses("REVERT_NOT_EXACT", M.revert_plain, after, record)


# ---------------------------------------------------------------- post-refit live check
@case("live check: after apply + re-fit the targets clear every beam; stale ISM / not current / undropped refuse")
def _():
    plain = world1("P02", yaw0=22.9)
    plan = M.build_plan(plain, "P02")
    moved = copy.deepcopy(plain)
    rows = M.apply_plain(all_rows(plain), plan)
    for cue in moved["cues"]:
        cue["attachments"] = rows[cue["guid"]]
    stale = copy.deepcopy(moved)                       # Show moved, ISM not re-fitted
    refit(moved)
    live = M.live_housing_check(moved, plan)
    assert len(live["live_tops"]) == 12 and all(v <= 1100.0 + 1e-3 for v in live["live_tops"].values())
    refuses("INSTANCE_GEOMETRY_MISMATCH", M.live_housing_check, stale, plan)
    not_current = copy.deepcopy(moved)
    not_current["structure"]["current"] = False
    refuses("STRUCTURE_NOT_CURRENT_AFTER_REFIT", M.live_housing_check, not_current, plan)
    refuses("LIVE_HOUSING_STILL_IN_BAND", M.live_housing_check, refit(copy.deepcopy(plain)), plan)


# ---------------------------------------------------------------- context / loader (base ports)
CLEAN = {"pie": False, "sequencer_open": False, "census": {"content": [], "maps": []}, "zz_actors": []}


@case("context gate: clean passes; PIE, Sequencer, dirty census, ZZ_ each refuse")
def _():
    M.check_context(CLEAN)
    refuses("PIE_OR_SIE_ACTIVE", M.check_context, dict(CLEAN, pie=True))
    refuses("SEQUENCER_IS_OPEN", M.check_context, dict(CLEAN, sequencer_open=True))
    refuses("DIRTY_BEFORE", M.check_context, dict(CLEAN, census={"content": ["/Game/X"], "maps": []}))
    refuses("DIRTY_BEFORE", M.check_context, dict(CLEAN, census={"content": [], "maps": ["/Game/M"]}))
    refuses("STRAY_ZZ_ACTORS", M.check_context, dict(CLEAN, zz_actors=["ZZ_bench"]))


@case("loader: scores module + P04 tool load offline with the API the tool calls")
def _():
    for name in M.SCORES_REQUIRED:
        assert callable(getattr(SCORES, name))
    for name in ("_require_context", "_backup", "_save_narrow", "_outside_hash", "_set_pair_attachments",
                 "_pair_attachments", "_attachment_rows", "_write_json", "_read_json", "_queue_master_test",
                 "_dirty_census", "_guid_text", "S"):
        assert hasattr(TOOL, name), name


@case("loader control: a file with a top-level side effect or no main guard refuses")
def _():
    folder = tempfile.mkdtemp()
    bad = os.path.join(folder, "bad.py")
    with open(bad, "w", encoding="utf-8") as handle:
        handle.write("import os\nos.remove('x')\ndef main():\n    pass\nif unreal is not None:\n    main()\n")
    refuses("TOP_LEVEL_SIDE_EFFECT", M.load_without_main, bad, "_bad")
    with open(bad, "w", encoding="utf-8") as handle:
        handle.write("def main():\n    pass\nmain()\n")
    refuses("MAIN_GUARD_SHAPE", M.load_without_main, bad, "_bad")
    shutil.rmtree(folder)


@case("self-load: rig_lamp_drop.py itself has the main-guard shape and no top-level side effects")
def _():
    module = M.load_without_main(os.path.join(HERE, "rig_lamp_drop.py"), "_rig_lamp_drop_selfcheck")
    assert callable(module.build_plan)


# ---------------------------------------------------------------- evidence (inferred: records may be stale vs live)
EVIDENCE = {}


@case("evidence: the P03 score TOP aim reproduces all 34 measured DRY BOX tops (1226.57..1227.76)")
def _():
    path = os.path.join(HERE, "lighting_scores_record_P03.json")
    dry = os.path.join(HERE, "p03_housing_drop_report_DRY_20261005-085808.json")
    if not (os.path.isfile(path) and os.path.isfile(dry)):
        EVIDENCE["skipped"] = True
        return
    with open(dry, encoding="utf-8") as handle:
        measured = {o["attachment_guid"]: o["top"] for o in json.load(handle)["plan"]["other_housings_in_new_band"]}
    with open(path, encoding="utf-8") as handle:
        rec = json.load(handle)
    compared = 0
    for target in rec["plan"]["targets"]:
        for row in target["after_rows"]:
            if row["guid"] in measured:
                loc, q = row["relative_transform"]["location"], row["relative_transform"]["rotation_xyzw"]
                assert abs(box_top_identity(loc, q) - measured[row["guid"]]) < 0.01, (row["label"], measured[row["guid"]])
                compared += 1
    assert compared == 34, compared
    EVIDENCE["p03_compared"] = compared


@case("evidence: predicted drop per passage from the score records (upright frames, station z 0)")
def _():
    for path in sorted(glob.glob(os.path.join(HERE, "lighting_scores_record_P0?.json"))):
        with open(path, encoding="utf-8") as handle:
            rec = json.load(handle)
        key = rec["passage"]
        tops = []
        for target in rec["plan"]["targets"]:
            for row in target["after_rows"]:
                kind = M._enum_name(row["kind"])
                if (row["enabled"] and kind == "LIGHT" and M._enum_name(row["anchor"]) == "STATION"
                        and row["label"].endswith(("TOP_L", "TOP_R"))):
                    loc, q = row["relative_transform"]["location"], row["relative_transform"]["rotation_xyzw"]
                    tops.append((box_top_identity(loc, q), loc[2], row["label"]))
        if tops:
            top = max(t[0] for t in tops)
            EVIDENCE[key] = {"top_lamps": len(tops), "max_box_top": round(top, 2),
                             "drop_cm": round(math.ceil((top - 1100.0) * 10.0 - 1e-9) / 10.0, 1),
                             "z_rel": sorted({round(t[1], 3) for t in tops})}
    if not EVIDENCE:
        EVIDENCE["skipped"] = True


def main():
    passed = sum(1 for r in RESULTS if r[1])
    for name, ok, detail in RESULTS:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
        if not ok:
            print(detail)
    for key in sorted(FOUND):
        print("FOUND %s %s" % (key, FOUND[key]))
    for key in sorted(EVIDENCE):
        print("EVIDENCE %s %s" % (key, EVIDENCE[key]))
    print("RESULT %d/%d passed" % (passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
