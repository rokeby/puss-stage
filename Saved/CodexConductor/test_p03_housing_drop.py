"""Offline harness for p03_housing_drop.py (plain-data fake Show; no Unreal).

Every gate is exercised twice: a passing case and a failing control that must
raise with the named reason. Run: python test_p03_housing_drop.py
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p03_housing_drop", os.path.join(HERE, "p03_housing_drop.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SCORES, TOOL = M.load_modules()

RESULTS = []


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
# Real P03 Rig Slash rotations (light_guid_audit_20261004-102539.json export text).
SLASH_Q = [[0.125472, 0.257312, -0.419949, 0.861214], [-0.148423, 0.291990, 0.428138, 0.842265],
           [0.135901, 0.274011, -0.423029, 0.852933], [-0.135063, 0.260340, 0.440258, 0.848619],
           [0.150034, 0.325001, -0.391362, 0.847762], [-0.135063, 0.260340, 0.440258, 0.848619]]
TOP_Q = [0.46962279248725575, 0.46962279248725586, -0.5286344982844688, 0.5286344982844688]


def _row(guid, label, kind="LIGHT", anchor="STATION", enabled=True, loc=(0.0, 0.0, 0.0), q=(0, 0, 0, 1),
         intensity=100.0):
    norm = math.sqrt(sum(c * c for c in q))
    return {"guid": guid, "label": label, "kind": "<InfinityAttachmentKind.%s: 1>" % kind, "enabled": enabled,
            "actor_class": None, "mesh": None, "anchor": "<InfinityAttachmentAnchor.%s: 0>" % anchor,
            "relative_transform": {"location": [float(v) for v in loc], "rotation_xyzw": [c / norm for c in q],
                                   "scale": [1.0, 1.0, 1.0]},
            "lighting": {"intensity": intensity, "cast_shadows": True, "drama": {"strike_distance_cm": 2200.0}},
            "effect": {"output": 0.5}, "trigger_distance_cm": 800.0}


def _guid(prefix, n):
    return (prefix + "%030d" % n)[:32].upper()


def make_show(n=6, slash_z=1078.0, station_tilt_q=None, height=1150.0, depth=34.0):
    cues, stations = [], []
    for k in range(n):
        cue_guid = _guid("C1", k)
        side = 1.0 if k % 2 == 0 else -1.0
        attachments = [
            _row(_guid("A1", k), "P03 Wing %03d Rig Slash" % (k + 1), loc=(-40.0, side * 180.0, slash_z),
                 q=SLASH_Q[k % len(SLASH_Q)]),
            _row(_guid("A2", k), "P03 SCORE B%02d TOP_L" % (k + 1), loc=(0.0, -360.0, 1180.0), q=TOP_Q),
            _row(_guid("A3", k), "disabled lamp", enabled=False, loc=(-40.0, 0.0, 1078.0), q=SLASH_Q[0]),
            _row(_guid("A4", k), "prop", kind="PROP", loc=(0.0, 0.0, 0.0)),
            _row(_guid("A5", k), "panel lamp", anchor="LEFT_PANEL", loc=(0.0, -500.0, 900.0)),
        ]
        cues.append({"show_index": 10 + k, "guid": cue_guid, "label": "P03 Wing %03d" % (k + 1),
                     "type": "<InfinityCueType.WING_PAIR: 0>", "occurrence_offset": copy.deepcopy(IDENTITY),
                     "attachments": attachments})
        world = {"location": [250.0 + 500.0 * k, 160000.0, 0.0],
                 "rotation_xyzw": list(station_tilt_q or [0.0, 0.0, 0.0, 1.0]), "scale": [1.0, 1.0, 1.0]}
        stations.append({"cue_guid": cue_guid, "world": world})
    foreign = {"show_index": 99, "guid": _guid("F9", 1), "label": "P04 Wing 001",
               "type": "<InfinityCueType.WING_PAIR: 0>", "occurrence_offset": copy.deepcopy(IDENTITY),
               "attachments": [_row(_guid("F8", 1), "P04 lamp", loc=(-40.0, 180.0, 1078.0), q=SLASH_Q[0])]}
    cues.append(foreign)
    plain = {"cues": cues, "stations": stations, "bay_guids": [s["cue_guid"] for s in stations],
             "structure": {"label": M.STRUCTURE_LABEL, "fixtures_enabled": True, "body_size_cm": [45.0, 32.0, 32.0],
                           "body_mesh_bounds": {"min": [-50.0, -50.0, -50.0], "max": [50.0, 50.0, 50.0]},
                           "hang_from_grid": True, "max_drop_cm": 600.0, "gridiron_enabled": True,
                           "gridiron_height_cm": height, "gridiron_depth_cm": depth, "gridiron_width_cm": 26.0,
                           "grid_half_width_cm": 1128.0, "fixture_body_count": 0, "current": True}}
    placements, unused = M.gather_placements(plain)
    plain["instances"] = [list(p["geometry"]["instance_location"]) for p in placements]
    plain["structure"]["fixture_body_count"] = len(placements)
    return plain


def slash_points(plain):
    placements, unused = M.gather_placements(plain)
    return [[float(round(v)) for v in p["geometry"]["instance_location"]]
            for p in placements if p["attachment_label"].endswith("Rig Slash")]


OPTS = {"expected_housings": 6}


def all_rows(plain):
    return {c["guid"]: copy.deepcopy(c["attachments"]) for c in plain["cues"]}


# ---------------------------------------------------------------- mapping
@case("mapping: 6 DRY points -> the 6 Rig Slash attachments by GUID")
def _():
    plain = make_show()
    plan = M.build_plan(plain, slash_points(plain), OPTS)
    assert sorted(t["attachment_guid"] for t in plan["targets"]) == sorted(_guid("A1", k) for k in range(6))
    assert plan["placements"] == 12 and plan["moving_lights_without_housing"] == 6
    assert plan["target_cue_guids"] == sorted(_guid("C1", k) for k in range(6))


@case("mapping control: a DRY point 3 cm off matches nothing")
def _():
    plain = make_show()
    points = slash_points(plain)
    points[2][0] += 3.0
    refuses("HOUSING_NO_MATCH", M.build_plan, plain, points, OPTS)


@case("mapping control: disabled lamps, props and panel lamps get no housing")
def _():
    plain = make_show()
    placements, moving = M.gather_placements(plain)
    labels = {p["attachment_label"] for p in placements}
    assert labels == {"P03 Wing %03d Rig Slash" % (k + 1) for k in range(6)} | {
        "P03 SCORE B%02d TOP_L" % (k + 1) for k in range(6)}
    plain["cues"][0]["attachments"][2]["enabled"] = True     # control: enabling it adds a housing
    placements2, unused = M.gather_placements(plain)
    assert len(placements2) == len(placements) + 1


@case("mapping: placements follow the C++ order (station, then attachment)")
def _():
    plain = make_show()
    placements, unused = M.gather_placements(plain)
    assert [(p["station_index"], p["attachment_index"]) for p in placements] == sorted(
        (p["station_index"], p["attachment_index"]) for p in placements)


@case("wrong count: 5 points for 6 expected refuses; default expects 14")
def _():
    plain = make_show()
    points = slash_points(plain)
    refuses("HOUSING_COUNT", M.build_plan, plain, points[:5], OPTS)
    refuses("HOUSING_COUNT", M.build_plan, plain, points, {})     # 6 != 14
    M.build_plan(plain, points, OPTS)                              # control passes


@case("ambiguity: a second lamp within 5 cm of a target refuses")
def _():
    plain = make_show()
    points = slash_points(plain)
    twin = copy.deepcopy(plain["cues"][1]["attachments"][0])
    twin["guid"] = _guid("A9", 1)
    twin["relative_transform"]["location"][0] += 2.0
    plain["cues"][1]["attachments"].append(twin)
    placements, unused = M.gather_placements(plain)
    plain["instances"] = [list(p["geometry"]["instance_location"]) for p in placements]
    refuses("HOUSING_AMBIGUOUS", M.build_plan, plain, points, OPTS)
    plain["cues"][1]["attachments"][-1]["relative_transform"]["location"][0] += 30.0   # control: far away
    placements, unused = M.gather_placements(plain)
    plain["instances"] = [list(p["geometry"]["instance_location"]) for p in placements]
    M.build_plan(plain, points, OPTS)


@case("ambiguity: the same DRY point twice refuses (mapped twice)")
def _():
    plain = make_show()
    points = slash_points(plain)
    points[1] = list(points[0])
    refuses("HOUSING_MAPPED_TWICE", M.build_plan, plain, points, OPTS)


@case("instance gate: live ISM 1 cm off the C++ maths refuses; count mismatch refuses")
def _():
    plain = make_show()
    points = slash_points(plain)
    bad = copy.deepcopy(plain)
    bad["instances"][3][2] += 1.0
    refuses("INSTANCE_GEOMETRY_MISMATCH", M.build_plan, bad, points, OPTS)
    bad = copy.deepcopy(plain)
    bad["instances"].pop()
    refuses("INSTANCE_COUNT_MISMATCH", M.build_plan, bad, points, OPTS)
    M.build_plan(plain, points, OPTS)


@case("target GUID duplicated elsewhere in the Show refuses")
def _():
    plain = make_show()
    points = slash_points(plain)
    plain["cues"][-1]["attachments"][0]["guid"] = _guid("A1", 0)
    refuses("TARGET_GUID_NOT_UNIQUE", M.build_plan, plain, points, OPTS)


@case("station outside the P03 bay list refuses")
def _():
    plain = make_show()
    points = slash_points(plain)
    plain["bay_guids"] = plain["bay_guids"][1:]
    refuses("STATION_OUTSIDE_P03", M.build_plan, plain, points, OPTS)


# ---------------------------------------------------------------- drop maths
def _flat_show(z_values, pitch_deg):
    """One lamp per station, throw along +X pitched down, hand-checkable."""
    plain = make_show(n=len(z_values))
    half = math.radians(pitch_deg) / 2.0
    q = [0.0, math.sin(half), 0.0, math.cos(half)]          # rotate X down by pitch_deg about Y
    for k, z in enumerate(z_values):
        cue = plain["cues"][k]
        cue["attachments"] = [_row(_guid("H1", k), "lamp %d" % k, loc=(-60.0, 0.0, z), q=q)]
    placements, unused = M.gather_placements(plain)
    plain["instances"] = [list(p["geometry"]["instance_location"]) for p in placements]
    plain["structure"]["fixture_body_count"] = len(placements)
    return plain, [[float(round(v)) for v in p] for p in plain["instances"]]


@case("drop maths: horizontal lamps, AXIS == BOX, drop = max(top) - 1100 exactly")
def _():
    plain, points = _flat_show([1095.0, 1092.0, 1090.5], 0.0)
    for convention in ("AXIS", "BOX"):
        plan = M.build_plan(plain, points, {"expected_housings": 3, "top_convention": convention})
        # centre z = lamp z (horizontal throw); top = z + 16; need = 1111 - 1100 = 11.0
        assert plan["drop_cm"] == 11.0, plan["drop_cm"]
        assert [t["z_after"] for t in plan["targets"]] == [1084.0, 1081.0, 1079.5]
        assert all(abs(t["band_lo_cm"] - 1105.0) < 1e-9 for t in plan["targets"])


@case("drop maths: 30 deg pitch, BOX top = c + sin*22.5 + cos*16, quantised up to 0.1 cm, minimal")
def _():
    z = 1078.0
    plain, points = _flat_show([z, z - 2.0], 30.0)
    s, c = math.sin(math.radians(30.0)), math.cos(math.radians(30.0))
    centre = z + s * 22.5
    box_top, axis_top = centre + s * 22.5 + c * 16.0, centre + 16.0
    for convention, top in (("BOX", box_top), ("AXIS", axis_top)):
        plan = M.build_plan(plain, points, {"expected_housings": 2, "top_convention": convention})
        want = math.ceil((top - 1100.0) * 10.0 - 1e-9) / 10.0
        assert abs(plan["drop_cm"] - round(want, 1)) < 1e-9, (convention, plan["drop_cm"], want)
        first = plan["targets"][0]
        assert abs(first["top_before"] - top) < 1e-6
        assert first["top_after"] <= 1100.0 + 1e-6
        # minimality: 0.1 cm less leaves the highest housing above 1100
        assert top - (plan["drop_cm"] - 0.1) > 1100.0
    assert box_top > axis_top


@case("drop maths: pure Z — rotation untouched, centre moves exactly -drop in Z only")
def _():
    plain = make_show()
    plan = M.build_plan(plain, slash_points(plain), OPTS)
    for t in plan["targets"]:
        before, after = t["housing_before"]["centre"], t["housing_after"]["centre"]
        assert abs(before[0] - after[0]) < 1e-9 and abs(before[1] - after[1]) < 1e-9
        assert abs((before[2] - after[2]) - plan["drop_cm"]) < 1e-9
        assert t["z_before"] - t["z_after"] == plan["drop_cm"] or abs(t["z_before"] - t["z_after"] - plan["drop_cm"]) < 1e-12
    after_rows = M.apply_plain(all_rows(plain), plan)
    for t in plan["targets"]:
        row = [r for r in after_rows[t["cue_guid"]] if r["guid"] == t["attachment_guid"]][0]
        src = [r for r in all_rows(plain)[t["cue_guid"]] if r["guid"] == t["attachment_guid"]][0]
        assert row["relative_transform"]["rotation_xyzw"] == src["relative_transform"]["rotation_xyzw"]


@case("drop control: already clear refuses (NOTHING_TO_DROP)")
def _():
    plain, points = _flat_show([1060.0], 0.0)
    refuses("NOTHING_TO_DROP", M.build_plan, plain, points, {"expected_housings": 1})


@case("frame gate: a 10 deg tilted station refuses (pure relative Z would not be world Z)")
def _():
    half = math.radians(10.0) / 2.0
    plain = make_show(station_tilt_q=[math.sin(half), 0.0, 0.0, math.cos(half)])
    refuses("FRAME_NOT_VERTICAL", M.build_plan, plain, slash_points(plain), OPTS)


@case("band gate: gridiron at 1200 cm drifts the band off 1105 and refuses")
def _():
    plain = make_show(height=1200.0)
    refuses("BAND_DRIFT", M.build_plan, plain, slash_points(plain), OPTS)


@case("extra lights: adding a GUID drops it too; unknown GUID refuses")
def _():
    plain = make_show()
    five = slash_points(plain)[:5]
    plan = M.build_plan(plain, five, {"expected_housings": 5, "extra_light_guids": [_guid("A1", 5)]})
    assert len(plan["targets"]) == 6 and _guid("A1", 5) in plan["target_attachment_guids"]
    assert [t["mapped_from"] for t in plan["targets"]].count("extra") == 1
    refuses("EXTRA_LIGHT_NOT_A_HOUSING", M.build_plan, plain, slash_points(plain),
            dict(OPTS, extra_light_guids=["0" * 31 + "1"]))
    refuses("EXTRA_LIGHT_ALREADY_MAPPED", M.build_plan, plain, slash_points(plain),
            dict(OPTS, extra_light_guids=[_guid("A1", 0)]))


# ---------------------------------------------------------------- live source (6 Oct)
def phase_a_show(top_z=1180.0, **kwargs):
    """make_show() with Phase A live (90 x 40); TOP lamps at top_z (1052.2 = rig_lamp_drop P03 applied)."""
    plain = make_show(depth=90.0, **kwargs)
    plain["structure"]["gridiron_width_cm"] = 40.0
    for cue in plain["cues"][:-1]:
        cue["attachments"][1]["relative_transform"]["location"][2] = top_z
    placements, unused = M.gather_placements(plain)
    plain["instances"] = [list(p["geometry"]["instance_location"]) for p in placements]
    plain["structure"]["fixture_body_count"] = len(placements)
    return plain


SLASH_GUIDS = sorted(_guid("A1", k) for k in range(6))


@case("live source: Phase A live + TOP lamps dropped -> exactly the 6 Rig Slash, same plan as the DRY points")
def _():
    plain = phase_a_show(top_z=1052.2)
    points = M.live_points(plain)
    assert len(points) == 6
    plan = M.build_plan(plain, points, OPTS)
    assert plan["target_attachment_guids"] == SLASH_GUIDS
    assert M.check_approved_set(plan, SLASH_GUIDS) == SLASH_GUIDS
    legacy = M.build_plan(plain, slash_points(plain), OPTS)      # the old DRY-point route, same housings
    assert legacy["drop_cm"] == plan["drop_cm"] and legacy["target_attachment_guids"] == SLASH_GUIDS


@case("stale-source control: last night's state (live depth 90) passes; pre-Phase-A depth 34 refuses")
def _():
    plain = phase_a_show(top_z=1052.2)
    M.live_points(plain)                                          # depth 90 / width 40: the state that refused
    stale = copy.deepcopy(plain)
    stale["structure"]["gridiron_depth_cm"], stale["structure"]["gridiron_width_cm"] = 34.0, 26.0
    refuses("PHASE_A_NOT_LIVE", M.live_points, stale)
    partial = copy.deepcopy(plain)
    partial["structure"]["gridiron_width_cm"] = 26.0
    refuses("PHASE_A_NOT_LIVE", M.live_points, partial)


@case("stale-source control: fixture_body_count disagreeing with the ISM refuses")
def _():
    plain = phase_a_show(top_z=1052.2)
    bad = copy.deepcopy(plain)
    bad["structure"]["fixture_body_count"] += 1
    refuses("FIXTURE_COUNT_STALE", M.live_points, bad)


@case("approved-set control: TOP lamps NOT dropped (rig_lamp_drop reverted) -> unapproved targets refuse")
def _():
    plain = phase_a_show(top_z=1180.0)
    points = M.live_points(plain)
    assert len(points) == 12
    refuses("HOUSING_COUNT", M.build_plan, plain, points, OPTS)
    refuses("DROP_TOO_LARGE", M.build_plan, plain, points, {"expected_housings": 12})   # TOP needs ~127 cm
    placements, unused = M.gather_placements(plain)
    twelve = {"target_attachment_guids": sorted(p["attachment_guid"] for p in placements)}
    refuses("TARGET_SET_NOT_APPROVED", M.check_approved_set, twelve, SLASH_GUIDS)
    refuses("TARGET_SET_NOT_APPROVED", M.check_approved_set,
            {"target_attachment_guids": SLASH_GUIDS[:5]}, SLASH_GUIDS)                  # one missing
    refuses("TARGET_SET_NOT_APPROVED", M.check_approved_set, {"target_attachment_guids": SLASH_GUIDS})  # vs real 14


@case("live source: housings already below the band are not selected (nothing to drop twice)")
def _():
    plain = phase_a_show(top_z=1052.2, slash_z=1058.0)           # the 5 Oct after-state
    assert M.live_points(plain) == []
    refuses("HOUSING_COUNT", M.build_plan, plain, [], OPTS)


@case("default approved set is the 14 GUIDs of the 5 Oct applied record")
def _():
    path = os.path.join(HERE, "p03_housing_drop_record.json.reverted-20261006-023409")
    assert len(M.APPROVED_TARGET_GUIDS) == M.EXPECTED_HOUSINGS == 14
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            assert set(json.load(handle)["plan"]["target_attachment_guids"]) == M.APPROVED_TARGET_GUIDS


# ---------------------------------------------------------------- context gates
CLEAN = {"pie": False, "sequencer_open": False, "census": {"content": [], "maps": []}, "zz_actors": []}


@case("context gate: clean passes; PIE, Sequencer, dirty census, ZZ_ each refuse")
def _():
    M.check_context(CLEAN)
    refuses("PIE_OR_SIE_ACTIVE", M.check_context, dict(CLEAN, pie=True))
    refuses("SEQUENCER_IS_OPEN", M.check_context, dict(CLEAN, sequencer_open=True))
    refuses("DIRTY_BEFORE", M.check_context, dict(CLEAN, census={"content": ["/Game/X"], "maps": []}))
    refuses("DIRTY_BEFORE", M.check_context, dict(CLEAN, census={"content": [], "maps": ["/Game/M"]}))
    refuses("STRAY_ZZ_ACTORS", M.check_context, dict(CLEAN, zz_actors=["ZZ_bench"]))


@case("mode gate: writes need '<MODE> P03'")
def _():
    assert M.check_mode_args("dry", None) == "DRY"
    assert M.check_mode_args("APPLY", "APPLY P03") == "APPLY"
    assert M.check_mode_args("REVERT", "REVERT P03") == "REVERT"
    refuses("CONFIRM_MISSING", M.check_mode_args, "APPLY", None)
    refuses("CONFIRM_MISSING", M.check_mode_args, "REVERT", "APPLY P03")
    refuses("CONFIRM_MISSING", M.check_mode_args, "APPLY", "APPLY P04")
    refuses("MODE_INVALID", M.check_mode_args, "FINISH", "FINISH P03")


# ---------------------------------------------------------------- outside guard
@case("outside guard: the planned change passes")
def _():
    plain = make_show()
    plan = M.build_plan(plain, slash_points(plain), OPTS)
    before = all_rows(plain)
    M.check_scope(TOOL, before, M.apply_plain(before, plan), plan)


@case("outside guard controls: non-target cue, sibling field, target rotation, wrong Z all refuse")
def _():
    plain = make_show()
    plan = M.build_plan(plain, slash_points(plain), OPTS)
    before = all_rows(plain)
    after = M.apply_plain(before, plan)
    bad = copy.deepcopy(after)
    bad[_guid("F9", 1)][0]["lighting"]["intensity"] += 1.0
    refuses("OUTSIDE_TARGET_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C1", 0)][1]["lighting"]["intensity"] += 1.0          # TOP lamp in a target cue
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C1", 0)][0]["relative_transform"]["rotation_xyzw"][0] += 1e-6
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C1", 0)][0]["relative_transform"]["location"][2] += 1e-9
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    bad = copy.deepcopy(after)
    bad[_guid("C1", 0)][0]["relative_transform"]["location"][0] += 1.0
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan)
    refuses("TARGET_CUE_SCOPE_CHANGED", M.check_scope, TOOL, before, before, plan)   # nothing applied


EXPORT = ('(CueGuid=C1,Label=INVTEXT("P03 Wing 001"),WingPair=(Attachments=('
          '(AttachmentGuid=%s,Label=INVTEXT("Rig Slash"),Kind=Light,Anchor=Station,'
          'RelativeTransform=(Rotation=(X=0.1,Y=0.2,Z=-0.4,W=0.8),Translation=(X=-40.000000,Y=159.600000,Z=%s),'
          'Scale3D=(X=1.000000,Y=1.000000,Z=1.000000)),Effect=(LinkedLightAttachmentGuid=%s)),'
          '(AttachmentGuid=%s,Label=INVTEXT("TOP"),RelativeTransform=(Rotation=(X=0,Y=0,Z=0,W=1),'
          'Translation=(X=0.000000,Y=-360.000000,Z=1180.000000),Scale3D=(X=1,Y=1,Z=1))))))')
TG, OG = "D2E6323C4C87C7AC728829BE579DC6ED", "3FACD8E44D4FDFD87CF919AEE2CDC4AB"


@case("export guard: only the target Translation.Z is masked")
def _():
    before = EXPORT % (TG, "1078.000000", OG, OG)
    after = EXPORT % (TG, "1058.000000", OG, OG)
    assert M.export_hash([before], [TG]) == M.export_hash([after], [TG])
    other = (EXPORT % (TG, "1058.000000", OG, OG)).replace("Z=1180.000000", "Z=1179.000000")
    assert M.export_hash([before], [TG]) != M.export_hash([other], [TG])      # control: sibling Z moved
    rot = after.replace("Z=-0.4", "Z=-0.41")
    assert M.export_hash([before], [TG]) != M.export_hash([rot], [TG])        # control: rotation moved


@case("export guard controls: a target missing or present twice refuses; Linked GUID is not an owner")
def _():
    refuses("EXPORT_TARGET_COUNT", M.export_hash, [EXPORT % (OG, "1", TG, TG)], ["0" * 31 + "1"])
    text = EXPORT % (TG, "1078.000000", OG, OG)
    refuses("EXPORT_TARGET_COUNT", M.export_hash, [text, text], [TG])
    linked_only = EXPORT % (OG, "1078.000000", TG, OG)    # TG appears only as LinkedLightAttachmentGuid
    refuses("EXPORT_TARGET_COUNT", M.export_hash, [linked_only], [TG])


# ---------------------------------------------------------------- revert
def _record(plain, plan):
    before = all_rows(plain)
    after = M.apply_plain(before, plan)
    return before, after, {"plan": plan, "before_target_rows": M.target_rows(before, plan),
                           "after_target_rows": M.target_rows(after, plan)}


@case("revert exactness: apply then revert is bit-identical (awkward Z 1077.3000000001)")
def _():
    plain = make_show(slash_z=1077.3000000001)
    plan = M.build_plan(plain, slash_points(plain), OPTS)
    before, after, record = _record(plain, plan)
    record = json.loads(json.dumps(record))          # through JSON, as the record file is
    restored = M.revert_plain(after, record)
    assert json.dumps(restored, sort_keys=True) == json.dumps(before, sort_keys=True)
    for t in record["plan"]["targets"]:
        row = [r for r in restored[t["cue_guid"]] if r["guid"] == t["attachment_guid"]][0]
        assert repr(row["relative_transform"]["location"][2]) == repr(1077.3000000001)


@case("revert drift: target Z nudged 0.001, or a target field changed, refuses")
def _():
    plain = make_show()
    plan = M.build_plan(plain, slash_points(plain), OPTS)
    before, after, record = _record(plain, plan)
    M.revert_plain(after, record)                                     # control passes
    bad = copy.deepcopy(after)
    bad[_guid("C1", 2)][0]["relative_transform"]["location"][2] += 0.001
    refuses("REVERT_DRIFT", M.revert_plain, bad, record)
    bad = copy.deepcopy(after)
    bad[_guid("C1", 4)][0]["enabled"] = False
    refuses("REVERT_DRIFT", M.revert_plain, bad, record)
    refuses("REVERT_DRIFT", M.revert_plain, before, record)          # never applied


@case("revert exactness control: a corrupted before-record refuses")
def _():
    plain = make_show()
    plan = M.build_plan(plain, slash_points(plain), OPTS)
    before, after, record = _record(plain, plan)
    guid = plan["targets"][0]["attachment_guid"]
    record["before_target_rows"][guid]["relative_transform"]["location"][2] += 0.5
    refuses("REVERT_NOT_EXACT", M.revert_plain, after, record)


# ---------------------------------------------------------------- loader
@case("loader: scores module + P04 tool load offline with the API the tool calls")
def _():
    for name in M.SCORES_REQUIRED:
        assert callable(getattr(SCORES, name))
    for name in ("_require_context", "_backup", "_save_narrow", "_outside_hash", "_set_pair_attachments",
                 "_pair_attachments", "_attachment_rows", "_write_json", "_queue_master_test", "S"):
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
    os.remove(bad)
    os.rmdir(folder)


# ---------------------------------------------------------------- evidence (inferred)
EVIDENCE = {}


def _yaw_q(deg):
    half = math.radians(float(deg)) / 2.0
    return [0.0, 0.0, math.sin(half), math.cos(half)]


@case("evidence: current P03 (new score + rig_lamp_drop P03 applied, Phase A) -> the 14 approved, drop 20.0")
def _():
    """Offline rebuild of the state the 6 Oct DRY will read. MEASURED inputs: the active scores record's
    after_rows, rig_lamp_drop P03's station frames (its DRY 20261006-023525) and its applied TOP rows.
    ASSUMED: identity occurrence offsets; the instance fit is self-consistent here, the live DRY proves it."""
    names = {"scores": "lighting_scores_record_P03.json", "rld": "rig_lamp_drop_record_P03.json",
             "frames": "rig_lamp_drop_report_P03_DRY_20261006-023525.json"}
    paths = {k: os.path.join(HERE, v) for k, v in names.items()}
    if not all(os.path.isfile(v) for v in paths.values()):
        EVIDENCE["skipped"] = True
        return
    loaded = {}
    for key, path in paths.items():
        with open(path, encoding="utf-8") as handle:
            loaded[key] = json.load(handle)
    rec, rld, frames = loaded["scores"], loaded["rld"], loaded["frames"]
    top_after = rld["after_target_rows"]
    cues, by_cue = [], {}
    for target in rec["plan"]["targets"]:
        rows = [copy.deepcopy(top_after.get(row["guid"], row)) for row in target["after_rows"]]
        cues.append({"show_index": target["show_index"], "guid": target["cue_guid"], "label": target["cue_label"],
                     "type": "<InfinityCueType.WING_PAIR: 0>", "occurrence_offset": copy.deepcopy(IDENTITY),
                     "attachments": rows})
        by_cue[target["cue_guid"]] = target
    stations = [{"cue_guid": f["cue_guid"], "world": {"location": list(f["location"]),
                                                       "rotation_xyzw": _yaw_q(f["yaw_deg"]),
                                                       "scale": [1.0, 1.0, 1.0]}}
                for f in sorted(frames["station_frames"], key=lambda f: f["index"])]
    structure = dict(make_show()["structure"], gridiron_depth_cm=90.0, gridiron_width_cm=40.0)
    plain = {"cues": cues, "stations": stations, "bay_guids": rec["plan"]["bay_guids"], "structure": structure}
    placements, unused = M.gather_placements(plain)
    plain["instances"] = [list(p["geometry"]["instance_location"]) for p in placements]
    structure["fixture_body_count"] = len(placements)
    assert len(placements) == frames["structure"]["fixture_body_count"] == 103, len(placements)
    for convention in ("BOX", "AXIS"):
        points = M.live_points(plain, convention)
        # Wing 010 (5 Oct's "extra") is selected live under both conventions: AXIS top 1104.8 > 1100.
        plan = M.build_plan(plain, points, {"top_convention": convention})
        M.check_approved_set(plan)
        EVIDENCE[convention] = plan
    box = EVIDENCE["BOX"]
    assert box["drop_cm"] == 20.0 and all(t["z_before"] == 1078.0 and t["z_after"] == 1058.0 for t in box["targets"])
    applied = os.path.join(HERE, "p03_housing_drop_record.json.reverted-20261006-023409")
    if os.path.isfile(applied):
        with open(applied, encoding="utf-8") as handle:
            old = json.load(handle)
        assert M.target_rows({c["guid"]: c["attachments"] for c in cues}, box) == old["before_target_rows"]
        assert box["drop_cm"] == old["plan"]["drop_cm"]
        EVIDENCE["matches_5oct"] = True


def main():
    passed = sum(1 for r in RESULTS if r[1])
    for name, ok, detail in RESULTS:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
        if not ok:
            print(detail)
    if EVIDENCE.get("BOX"):
        for convention in ("BOX", "AXIS"):
            plan = EVIDENCE[convention]
            print("EVIDENCE %s drop_cm=%.1f raw=%.3f targets=%d others_in_band=%d" % (
                convention, plan["drop_cm"], plan["drop_raw_cm"], len(plan["targets"]),
                len(plan["other_housings_in_new_band"])))
        print("  rows + drop identical to the 5 Oct applied record: %s" % bool(EVIDENCE.get("matches_5oct")))
        for t in EVIDENCE["BOX"]["targets"]:
            print("  %-24s %-14s %s z %.1f->%.1f box_top %.1f->%.1f axis_top %.1f route_gap %.1f line_new_depth %s"
                  % (t["attachment_label"], t["cue_label"], t["attachment_guid"], t["z_before"], t["z_after"],
                     t["top_before"], t["top_after"], t["housing_before"]["top_axis"],
                     t["route_gap_to_new_cross_beam_cm"], t["line"]["new_depth_after"]))
        others = EVIDENCE["BOX"]["other_housings_in_new_band"]
        slash = [o for o in others if o["label"].endswith("Rig Slash")]
        hits = [o for o in others if o["hits_new_cross_beam_box"]]
        print("  others in new band (BOX): %d; Rig Slash among them: %s; overlapping new cross-beam footprint: %d"
              % (len(others), [o["label"] for o in slash], len(hits)))
        if hits:
            print("  e.g. %s" % hits[0])
    print("RESULT %d/%d passed" % (passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
