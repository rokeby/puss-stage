"""Offline harness for passage_end_drape.py (system Python, no Unreal). Every gate has a failing control.

Synthetic inputs are built from records, cited per number:
  S1 landed root (29284.0135, 0, 0) yaw 0            hangar_exit_doors_record.json root_before["1"]
  S2 landed root (11104.48, 80954.39, 0) yaw -43.5725 hangar_exit_doors_record.json root_before["2"]
  dock = hinge - 500 (camera stop)                    curtain_sleight_I1_dry.json hangar.dock_local [-500, 0, 150] (live 5 Oct)
  rise root pitch [[-5.8739, -90], [4.1261, 0]]       Saved/CodexStructure/hangar_retime_record.json (1 Oct)
  cache: release 1.0 s, 11.0 s long, hold offset 23200 ticks   fit_transition_drapes_final13.json sections_planned
  hang AABB x[-41.3, 39.1] y+-940 z[20, 1020]         curtain_sleight_I1_dry.json inputs.cache (live 5 Oct)
  pile AABB from DropBake/final13_opening_a06_w188.json checkpoint 780 (y -> X, x -> +-Y outer)
  Passage end speed 2.5 m/s to a dead stop           p04_backcloth_section_apply.py:8-9 (verified 30 Sep)
Run: python test_passage_end_drape.py   -> prints PASSAGE_END_DRAPE_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("passage_end_drape", os.path.join(HERE, "passage_end_drape.py"))
ped = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ped)
assert ped.unreal is None, "harness must run without Unreal"
CS = ped.load_cs(HERE)

CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(failures, prefix):
    return any(f.startswith(prefix) or (": " in f and f.split(": ", 1)[1].startswith(prefix)) or prefix in f for f in failures)


# ------------------------------------------------------------------------------------------------- synthetic inputs

def bake_pile():
    path = os.path.join(os.path.dirname(HERE), "CodexSoftGoods", "DropBake", "final13_opening_a06_w188.json")
    with open(path, "r", encoding="utf-8") as handle:
        b = json.load(handle)["checkpoints"]["780"]["aabb_m"]
    yo = max(abs(b["x"][0]), abs(b["x"][1]))
    return {"x": [b["y"][0] * 100.0, b["y"][1] * 100.0], "y": [-yo * 100.0, yo * 100.0], "z": [b["z"][0] * 100.0, b["z"][1] * 100.0]}


PILE = bake_pile()


def inputs_for(root_loc=(29284.0135, 0.0, 0.0), yaw=0.0, rise_start=-5.8739, speed=250.0, focal=24.0, eye=150.0,
               span=14.0, stop_shift=0.0, hem_cm=2.0, slab_lift=0.0):
    """hem_cm: the HOLD sample's lowest point above the cache floor. The REAL final13 sample 479 hangs at 20 cm
    (DropBake/final13_opening_a06_w188.json checkpoints["479"].aabb_m.z[0] = 0.2); the default 2 cm is a SYNTHETIC
    floor-reaching curtain so the other gates can be tested clean. t_hem_* uses the real value."""
    root = {"loc": list(root_loc), "rot": [0.0, 0.0, yaw]}
    frame = ped.frame_of(root["loc"], root["rot"])
    stop = ped.to_world(frame, [-500.0 + stop_shift, 0.0, eye])
    samples = []
    steps = int(round(span / 0.1))
    for i in range(steps + 1):
        t = -span + i * 0.1
        loc = ped.to_world(frame, [-500.0 + stop_shift + speed * t, 0.0, eye])
        samples.append([round(t, 4), {"loc": loc, "yaw": yaw, "pitch": 0.0, "focal": focal}])
    return {
        "n": 1, "root_live": copy.deepcopy(root), "root_landed": copy.deepcopy(root),
        "hangar": {"half_w": 1000.0, "height": 3000.0, "depth": 6000.0, "hinge_z": root_loc[2]},   # world, = root z
        "route_end": {"loc": ped.to_world(frame, [-500.0, 0.0, 0.0]), "yaw": yaw},
        "floor": {"route_end_z": root_loc[2], "floor_height_cm": 0.0, "slab_lift_cm": slab_lift},
        "other_cloths": [], "entry_camera": {"loc": stop, "yaw": yaw, "pitch": 0.0, "focal_mm": focal,
                                                 "filmback_mm": [23.76, 13.365]},
        "passage_camera": samples,
        "rise": {"root_pitch_keys": [[rise_start, -90.0], [4.1261, 0.0]], "tick_rate": 24000.0, "fps": 30.0},
        "rise_sub": {"section_start_s": 0.0, "start_offset_s": 0.0, "inner_start_s": 0.0, "rate": 1.0},
        "cache": {"bake_id": "final13_opening_a06_w188", "release_in_cache_s": 1.0, "duration_s": 11.0,
                  "hang_aabb_cm": {"x": [-41.3, 39.1], "y": [-940.0, 940.0], "z": [hem_cm, 1020.0]},
                  "pile_aabb_cm": copy.deepcopy(PILE)},
        "warnings": [],
    }


def all_checks(plan, inp):
    return ped.check_pose(plan, inp) + ped.check_timing(plan, inp)


CLEAN_STATE = {"mode": "DRY", "scene": 1, "confirm": "DRY S1", "pie": False, "sequencer_open": False,
               "census": {"content": [], "maps": []}, "zz": False, "record_exists": False, "slot_actor": "",
               "label_exists": False, "binding_exists": False, "arrival_problems": []}


# ------------------------------------------------------------------------------------------------- pose + guard

@test
def t_pose_s1_clean():
    inp = inputs_for()
    plan = ped.plan_drape(inp, {})
    f = all_checks(plan, inp)
    check(f == [], "S1 clean plan passes: %r" % f)
    check(abs(plan["line_x_cm"] - -(PILE["x"][1] + 20.0)) < 1e-9, "line derived from the pile far edge")
    check(abs(plan["drape_world"]["loc"][0] - (29284.0135 + plan["line_x_cm"])) < 1e-6, "world x on the S1 axis")
    check(abs(plan["drape_world"]["loc"][2]) < 1e-9, "drape on the hinge floor")
    check(plan["boxes_landed"]["pile"][1][0] <= -20.0 + 1e-6, "pile ends 20 cm before the hinge")


@test
def t_rest_pose_control_pitched():
    inp = inputs_for()
    inp["root_live"]["rot"] = [0.0, -90.0, 0.0]          # the rise's REST key (-90) evaluated onto the root
    plan = ped.plan_drape(inp, {})
    f = ped.check_pose(plan, inp)
    check(has(f, "ROOT_NOT_LANDED"), "REST control: root not landed")
    check(has(f, "DRAPE_TILTED"), "REST control: drape tilted")
    check(has(f, "BOX_Z") and has(f, "BOX_HANG"), "REST control: drape leaves the box (%r)" % f)


@test
def t_rest_pose_control_sunk():
    inp = inputs_for()
    inp["root_live"]["loc"][2] = -3500.0                 # memory: REST-pose composition ~35 m underground
    plan = ped.plan_drape(inp, {})
    f = ped.check_pose(plan, inp)
    check(has(f, "BOX_Z") and has(f, "FLOOR_MISMATCH") and has(f, "ROOT_NOT_LANDED"), "sunk control fails: %r" % f)
    inp2 = inputs_for()
    inp2["root_live"]["loc"][2] = inp2["root_landed"]["loc"][2] = -3500.0   # record ALSO wrong: floor still catches it
    f2 = ped.check_pose(ped.plan_drape(inp2, {}), inp2)
    check(has(f2, "FLOOR_MISMATCH") and not has(f2, "ROOT_NOT_LANDED"), "independent floor catches a wrong record: %r" % f2)


@test
def t_box_hinge_and_back_limits():
    inp = inputs_for()
    f = ped.check_pose(ped.plan_drape(inp, {"line_x_cm": -100.0}), inp)
    check(has(f, "BOX_PILE") and "over the hinge" in " ".join(f), "line over the hinge refused: %r" % f)
    f = ped.check_pose(ped.plan_drape(inp, {"line_x_cm": -3000.0}), inp)
    check(has(f, "BOX_") and "not at the passage end" in " ".join(f), "line far up the passage refused: %r" % f)
    f = ped.check_pose(ped.plan_drape(inp, {"pile_lateral_allow_cm": 0.0}), inp)
    check(has(f, "BOX_PILE") and "|y|" in " ".join(f), "pile lateral bound bites at 0 allowance: %r" % f)


@test
def t_floor_site_decision():
    inp = inputs_for()
    inp["floor"]["route_end_z"] = 120.0                  # S3-like: the Passage floor 1.2 m above the hinge
    f = ped.check_pose(ped.plan_drape(inp, {}), inp)
    check(has(f, "FLOOR_MISMATCH"), "floor mismatch refused: %r" % f)
    f = ped.check_pose(ped.plan_drape(inp, {"floor_offset_cm": 120.0}), inp)
    check(not has(f, "FLOOR_MISMATCH") and not has(f, "BOX_Z"), "+control: recorded offset passes: %r" % f)
    inp = inputs_for(root_loc=(11421.97275, 160000.0, -120.0))   # S3 lowered hinge, record hinge_z -120 (world)
    inp["floor"]["route_end_z"] = -120.0
    f = ped.check_pose(ped.plan_drape(inp, {}), inp)
    check(f == [] and abs(ped.plan_drape(inp, {})["drape_world"]["loc"][2] + 120.0) < 1e-9, "S3 hinge -120: drape at -120, not -240: %r" % f)
    inp["hangar"]["hinge_z"] = 0.0
    check(has(ped.check_pose(ped.plan_drape(inp, {}), inp), "HINGE_Z_MISMATCH"), "hinge_z vs root z mismatch refused")


@test
def t_route_end_and_framing():
    inp = inputs_for()
    inp["route_end"]["loc"][1] += 200.0
    check(has(ped.check_pose(ped.plan_drape(inp, {}), inp), "ROUTE_END"), "route end off-axis refused")
    inp = inputs_for()
    inp["route_end"]["yaw"] = 3.0
    check(has(ped.check_pose(ped.plan_drape(inp, {}), inp), "FACING_ROUTE"), "route tangent mismatch refused")
    inp = inputs_for()
    inp["entry_camera"]["yaw"] = 3.0
    check(has(ped.check_pose(ped.plan_drape(inp, {}), inp), "FACING_ENTRY_CAMERA"), "entry camera yaw mismatch refused")
    inp = inputs_for()
    inp["entry_camera"]["loc"] = ped.to_world(ped.frame_of(inp["root_landed"]["loc"], [0, 0, 0]), [-500.0, 300.0, 150.0])
    check(has(ped.check_pose(ped.plan_drape(inp, {}), inp), "ENTRY_CAMERA_OFF_AXIS"), "entry camera off axis refused")


@test
def t_rotated_s2_oriented_guard():
    inp = inputs_for(root_loc=(11104.483469893386, 80954.38804069262, 0.0), yaw=-43.5725212097168)
    plan = ped.plan_drape(inp, {})
    f = all_checks(plan, inp)
    check(f == [], "S2 rotated plan passes: %r" % f)
    check(abs(plan["drape_world"]["yaw"] - -43.5725212097168) < 1e-9, "S2 drape faces the root yaw")
    local = ped.to_local(ped.frame_of(inp["root_landed"]["loc"], inp["root_landed"]["rot"]), plan["drape_world"]["loc"])
    check(abs(local[1]) < 1e-6 and abs(local[0] - plan["line_x_cm"]) < 1e-6, "S2 drape on the dock axis")
    bad = copy.deepcopy(inp)
    bad["root_live"]["rot"] = [0.0, 0.0, 0.0]            # composed in an unrotated frame
    f = ped.check_pose(ped.plan_drape(bad, {}), bad)
    check(has(f, "ROOT_NOT_LANDED") and (has(f, "BOX_") or has(f, "FACING_")), "S2 unrotated control fails: %r" % f)


# ------------------------------------------------------------------------------------------------- timing

@test
def t_release_at_rise_start():
    inp = inputs_for()
    plan = ped.plan_drape(inp, {})
    t, s = plan["timing"], plan["section"]
    check(abs(t["release_scene_s"] - -5.8739) < 1e-9 and abs(t["rise_start_scene_s"] - -5.8739) < 1e-9, "release = rise start")
    check(s["offset_ticks"] == 23200, "hold offset 23200 ticks = fit_transition_drapes final13 (got %d)" % s["offset_ticks"])
    check(abs(s["start_s"] - (-5.8739 - 1 / 30.0)) < 1e-9, "section starts one cache frame before the release")
    check(abs(s["end_s"] - (s["start_s"] + 11.0 - 23200 / 24000.0)) < 1e-9, "section length = duration - offset (no loop)")
    check(abs(ped.map_time_to_animation(s, s["start_s"] - 1.0, 11.0) - s["offset_s"]) < 1e-9, "held sample before the section")
    check(abs(ped.map_time_to_animation(s, t["release_motion_s"], 11.0) - 1.0) < 1e-9, "cache at 1.0 s on the release")
    check(abs(ped.map_time_to_animation(s, 100.0, 11.0) - 11.0) < 1e-9, "after the section: the end (KeepState)")
    check(ped.check_timing(plan, inp) == [], "timing clean")


@test
def t_release_gates_controls():
    inp = inputs_for()
    check(has(ped.check_timing(ped.plan_drape(inp, {"lead_s": -0.5}), inp), "RELEASE_AFTER_RISE"), "late release refused")
    check(has(ped.check_timing(ped.plan_drape(inp, {"lead_s": 2.0}), inp), "RELEASE_TOO_EARLY"), "early release refused")
    check(ped.check_timing(ped.plan_drape(inp, {"lead_s": 0.5}), inp) == [], "+control: 0.5 s lead allowed")
    late = inputs_for(rise_start=0.5)
    check(has(ped.check_timing(ped.plan_drape(late, {}), late), "RELEASE_NOT_PRE_SCENE"), "post-cut rise refused")


@test
def t_section_tamper_controls():
    inp = inputs_for()
    plan = ped.plan_drape(inp, {})
    p2 = copy.deepcopy(plan)
    p2["section"]["length_s"] += 1.0
    check(has(ped.check_timing(p2, inp), "SECTION_LOOPS"), "overlong section (would loop) refused")
    p3 = copy.deepcopy(plan)
    p3["section"]["start_s"] += 0.2
    check(has(ped.check_timing(p3, inp), "RELEASE_SAMPLE"), "shifted section breaks the release sample")
    p4 = copy.deepcopy(plan)
    p4["section"]["offset_s"] = 0.0
    check(has(ped.check_timing(p4, inp), "RELEASE_SAMPLE"), "zero offset breaks the release sample")


@test
def t_camera_clearance_controls():
    inp = inputs_for(rise_start=-1.5)                  # cloth still falling when the camera reaches it
    f = ped.check_timing(ped.plan_drape(inp, {"max_lead_s": 1.0}), inp)
    check(has(f, "CAMERA_THROUGH_FALLING_CLOTH"), "camera through falling cloth refused: %r" % f)
    inp = inputs_for(speed=0.0)                        # camera parked at the stop (already past the hang front)
    check(has(ped.check_timing(ped.plan_drape(inp, {}), inp), "CAMERA_NOT_BEFORE_DRAPE_AT_RELEASE"), "camera past the drape refused")
    inp = inputs_for(eye=110.0)                        # eye 11 cm over the pile top
    check(has(ped.check_timing(ped.plan_drape(inp, {}), inp), "CAMERA_IN_PILE"), "camera in the pile refused")
    inp = inputs_for(stop_shift=-300.0)                # +control: stopping 3 m earlier keeps clear of the pile footprint? (still over it)
    f = ped.check_timing(ped.plan_drape(inp, {}), inp)
    check(not has(f, "CAMERA_THROUGH_FALLING_CLOTH"), "+control: an earlier stop is not a falling-cloth fault: %r" % f)


@test
def t_rise_shape():
    inp = inputs_for()
    inp["rise"]["root_pitch_keys"] = [[-5.0, -90.0], [0.0, -45.0], [4.0, 0.0]]
    try:
        ped.plan_drape(inp, {})
        check(False, "three-key rise must refuse")
    except ped.PlanError as exc:
        check("RISE_SHAPE" in str(exc), "three-key rise refused")
    inp["rise"]["root_pitch_keys"] = [[-5.0, -80.0], [4.0, 0.0]]
    try:
        ped.plan_drape(inp, {})
        check(False, "non -90 rest must refuse")
    except ped.PlanError as exc:
        check("RISE_SHAPE" in str(exc), "non -90 rest refused")


@test
def t_scene_motion_mapping():
    sub = {"section_start_s": 2.0, "start_offset_s": 0.5, "inner_start_s": 0.0, "rate": 1.0}
    for s in (-7.0, 0.0, 3.25):
        check(abs(ped.motion_to_scene(sub, ped.scene_to_motion(sub, s)) - s) < 1e-12, "mapping round trip %s" % s)
    inp = inputs_for()
    inp["rise_sub"] = {"section_start_s": 2.0, "start_offset_s": 0.0, "inner_start_s": 0.0, "rate": 1.0}
    plan = ped.plan_drape(inp, {})
    check(abs(plan["timing"]["rise_start_scene_s"] - (-5.8739 + 2.0)) < 1e-9, "nested at +2 s moves the Scene-time rise")
    check(abs(plan["timing"]["release_motion_s"] - -5.8739) < 1e-9, "the motion-time release stays on the key")


@test
def t_retime_shifts_never_stretches():
    a = inputs_for(span=14.0)
    b = inputs_for(span=40.0)                          # a longer Passage: same tail, more before it
    pa, pb = ped.plan_drape(a, {}), ped.plan_drape(b, {})
    check(pa["section"] == pb["section"] and pa["drape_world"] == pb["drape_world"], "plan invariant to Passage length")
    check(pa["digest"] == pb["digest"], "digest invariant to Passage length")
    # -control: a release anchored to the Passage START (a Choreo key) moves when the Passage grows by 10 s
    passage_len, grow = 60.0, 10.0
    choreo_key = passage_len + pa["timing"]["release_scene_s"]
    check(abs((choreo_key - (passage_len + grow)) - pa["timing"]["release_scene_s"]) > 1.0, "Choreo anchor drifts (control)")


# ------------------------------------------------------------------------------------------------- live gates

@test
def t_live_gates():
    check(ped.live_gates(CLEAN_STATE) == [], "clean DRY S1 has no refusals")
    check(ped.live_gates(dict(CLEAN_STATE, mode="APPLY", confirm="APPLY S1")) == [], "clean APPLY S1 has no refusals")
    controls = [
        (dict(CLEAN_STATE, pie=True), "PIE_OR_SIE_ACTIVE"),
        (dict(CLEAN_STATE, sequencer_open=True), "SEQUENCER_IS_OPEN"),
        (dict(CLEAN_STATE, census={"content": ["/Game/X"], "maps": []}), "DIRTY_CENSUS"),
        (dict(CLEAN_STATE, census={"content": [], "maps": [ped.EXPECTED_WORLD]}), "DIRTY_CENSUS"),
        (dict(CLEAN_STATE, mode="APPLY", confirm="APPLY S1", record_exists=True), "RECORD_EXISTS"),
        (dict(CLEAN_STATE, mode="APPLY", confirm="APPLY S1", slot_actor="P04 Backcloth (baked)"), "BACKCLOTH_SLOT_TAKEN"),
        (dict(CLEAN_STATE, label_exists=True), "ACTOR_EXISTS"),
        (dict(CLEAN_STATE, binding_exists=True), "BINDING_EXISTS"),
        (dict(CLEAN_STATE, zz=True), "ZZ_ACTORS_PRESENT"),
        (dict(CLEAN_STATE, confirm="APPLY S1"), "CONFIRM_MISMATCH"),
        (dict(CLEAN_STATE, confirm="DRY S2"), "CONFIRM_MISMATCH"),
        (dict(CLEAN_STATE, mode="SAVE", confirm="SAVE S1"), "MODE_INVALID"),
        (dict(CLEAN_STATE, scene=6, confirm="DRY S6"), "SCENE_OUT_OF_SCOPE"),
        (dict(CLEAN_STATE, mode="REVERT", confirm="REVERT S1", record_applied=False), "NO_APPLIED_RECORD"),
        (dict(CLEAN_STATE, arrival_problems=["MAPPING_MISMATCH: x"]), "ARRIVAL: MAPPING_MISMATCH"),
    ]
    for state, want in controls:
        got = ped.live_gates(state)
        check(any(g.startswith(want) for g in got), "%s refused (got %r)" % (want, got))
    check(ped.live_gates(dict(CLEAN_STATE, mode="REVERT", confirm="REVERT S1", record_applied=True)) == [],
          "+control: REVERT with an applied record passes")


@test
def t_range_gate():
    before = {"scene": [0, 5270], "rise": [0, 930]}
    check(ped.range_gate(before, copy.deepcopy(before)) == [], "unchanged ranges pass")
    check(has(ped.range_gate(before, {"scene": [0, 5271], "rise": [0, 930]}), "RANGE_CHANGED"), "Scene range change refused")
    check(has(ped.range_gate(before, {"scene": [0, 5270], "rise": [-177, 930]}), "RANGE_CHANGED"), "rise range change refused")


@test
def t_build_report_s4_and_out_of_scope():
    inp = inputs_for()
    r = ped.build_report(inp, {}, CLEAN_STATE)
    check(r["apply_ready"] and r["refusals"] == [], "S1 report apply-ready: %r" % r["refusals"])
    r = ped.build_report(inp, {}, dict(CLEAN_STATE, slot_actor="P04 Backcloth (baked)", scene=4, confirm="DRY S4"))
    check(not r["apply_ready"] and has(r["refusals"], "BACKCLOTH_SLOT_TAKEN"), "S4 refused: slot taken")
    inp6 = dict(inputs_for(), n=6)
    r = ped.build_report(inp6, {}, dict(CLEAN_STATE, scene=6, confirm="DRY S6"))
    check(not r["apply_ready"] and has(r["refusals"], "OUT_OF_SCOPE"), "S6 refused (P06 excluded)")
    r = ped.build_report(inputs_for(focal=10.0), {}, CLEAN_STATE)
    check(has(r["warnings"], "FRAME_NOT_SPANNED_AT_RELEASE"), "wide lens: coverage warning (look metric)")
    r = ped.build_report(inputs_for(focal=24.0), {}, CLEAN_STATE)
    check(not has(r["warnings"], "FRAME_NOT_SPANNED_AT_RELEASE"), "+control: 24 mm spans the frame")
    try:
        ped.plan_drape(inputs_for(), {"bogus": 1})
        check(False, "unknown params must refuse")
    except ped.PlanError as exc:
        check("UNKNOWN_PARAMS" in str(exc), "unknown params refused")


# ------------------------------------------------------------------------------------------------- track reuse (fake sequence)

class FakeClass:
    def __init__(self, name):
        self._n = name

    def get_name(self):
        return self._n


class FakeTrack:
    def __init__(self, cls):
        self.cls = cls
        self.sections = []

    def get_class(self):
        return FakeClass(self.cls)


class FakeBinding:
    def __init__(self, auto=()):
        self.tracks = [FakeTrack(c) for c in auto]       # UE may auto-create tracks on add (5 Oct: a spawn track)

    def get_tracks(self):
        return list(self.tracks)

    def add_track(self, cls):
        t = FakeTrack(cls)
        self.tracks.append(t)
        return t

    def remove_track(self, t):
        self.tracks.remove(t)
        return None                                      # UE returns None; judge by re-listing


def tool_procedure(binding):
    """Mirror of run_apply step 2 (track_ops), on the fake."""
    tracks = binding.get_tracks()
    reuse, remove, add = ped.track_ops([t.get_class().get_name() for t in tracks], ped.GC_TRACK)
    for i in remove:
        binding.remove_track(tracks[i])
    return binding.add_track(ped.GC_TRACK) if add else tracks[reuse]


def naive_procedure(binding):
    return binding.add_track(ped.GC_TRACK)


@test
def t_track_reuse():
    for auto in ((), (ped.GC_TRACK,), (ped.GC_TRACK, ped.GC_TRACK)):
        b = FakeBinding(auto)
        tool_procedure(b)
        classes = [t.get_class().get_name() for t in b.get_tracks()]
        check(ped.track_failures(classes) == [], "tool leaves exactly one GC track from %r: %r" % (auto, classes))
    b = FakeBinding((ped.GC_TRACK,))
    naive_procedure(b)
    check(has(ped.track_failures([t.get_class().get_name() for t in b.get_tracks()]), "GC_TRACK_COUNT"),
          "duplicate control: a naive add beside an auto-created track is caught")
    check(has(ped.track_failures([ped.GC_TRACK, ped.SPAWN_TRACK]), "SPAWN_TRACK_ON_POSSESSABLE"), "spawn track on the possessable caught")
    check(has(ped.track_failures([]), "GC_TRACK_COUNT"), "no GC track caught")
    check(ped.track_ops([ped.SPAWN_TRACK, ped.GC_TRACK], ped.GC_TRACK) == (1, [], False), "reuse picks the existing GC track")


# ------------------------------------------------------------------------------------------------- snapshot model, revert, drift

def snap_before():
    return CS["normalize_snapshot"]({
        "playback": [0, 930],
        "bindings": [{"name": "S1 Hangar Root", "guid": "EE1E481E42F053162CE0E3BC0A0BFE30", "parent": "",
                      "tracks": [{"class": "MovieScene3DTransformTrack", "name": "", "sections": [[0, 930]]}]}],
        "root_tracks": [], "cuts": [], "markers": [], "level_labels": [],
        "arrival": {"backcloth_actor": "", "backcloth_guid": "0" * 32}, "drape_actors": {},
        "ranges": {"scene": [0, 5270], "rise": [0, 930]}})


@test
def t_revert_exact_and_drift():
    inp = inputs_for()
    plan = ped.plan_drape(inp, {})
    before = snap_before()
    guid = "A" * 32
    gc_row = [-178, 124, 23200, 0]
    after = ped.apply_model(before, plan, guid, gc_row, CS)
    check(CS["snapshot_diff"](after, before) != [], "apply changes the snapshot")
    record = {"binding_guid": guid, "plan": plan, "snapshot_before": before, "snapshot_after": after}
    check(CS["snapshot_diff"](ped.revert_model(after, record, CS), before) == [], "revert model is exact")
    lazy = copy.deepcopy(ped.revert_model(after, record, CS))
    lazy["arrival"] = after["arrival"]
    check(CS["snapshot_diff"](lazy, before) != [], "-control: a revert that leaves the Arrival slot set is not exact")
    lazy = copy.deepcopy(ped.revert_model(after, record, CS))
    lazy["level_labels"] = [plan["label"]]
    check(CS["snapshot_diff"](lazy, before) != [], "-control: a revert that leaves the actor is not exact")
    check(ped.drift(copy.deepcopy(after), record, CS) == [], "no drift when live == after")
    moved = copy.deepcopy(after)
    for b in moved["bindings"]:
        if b["guid"] == guid:
            b["tracks"][0]["sections"][0][0] += 25         # a hand retime of the drape section
    check(ped.drift(moved, record, CS) != [], "drift: hand-retimed section refused")
    slot = copy.deepcopy(after)
    slot["arrival"]["backcloth_actor"] = "Something Else"
    check(ped.drift(slot, record, CS) != [], "drift: Arrival slot changed refused")
    pose = copy.deepcopy(after)
    pose["drape_actors"][plan["label"]][0] += 5.0
    check(ped.drift(pose, record, CS) != [], "drift: actor moved refused")


@test
def t_exclusive_record():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rec.json")
        ped.write_record_exclusive(path, {"a": 1})
        check(json.load(open(path, encoding="utf-8")) == {"a": 1}, "record readable after fsync")
        try:
            ped.write_record_exclusive(path, {"a": 2})
            check(False, "second exclusive write must refuse")
        except FileExistsError:
            check(True, "second exclusive write refused")
        ped.update_record(path, {"a": 3})
        check(json.load(open(path, encoding="utf-8")) == {"a": 3}, "update replaces atomically")


@test
def t_cs_reuse_loaded():
    check(callable(CS["normalize_snapshot"]) and callable(CS["_track_rows"]), "curtain_sleight defs loaded (main not run)")
    check("main" in CS and CS.get("unreal") is None, "curtain_sleight loaded offline without running main()")


# ------------------------------------------------------------------------------------------------- hem + S4 (5 Oct additions)

REAL_HEM = 20.0          # final13 sample 479 z min 0.2 m


@test
def t_hem_real_final13_refuses():
    inp = inputs_for(hem_cm=REAL_HEM, slab_lift=0.5)     # P01: dark-wet slab raised to +0.5
    plan = ped.plan_drape(inp, {})
    f = ped.check_pose(plan, inp)
    check(has(f, "HEM_ABOVE_FLOOR"), "-control: the real 20 cm hem refuses: %r" % f)
    check(abs(plan["floor"]["hem_gap_cm"] - 19.5) < 1e-9, "gap reported 19.5 cm (got %r)" % plan["floor"]["hem_gap_cm"])
    check(plan["floor"]["hem_drop_window_cm"] is None, "no hem_drop satisfies hem AND pile with final13 (window %r)"
          % plan["floor"]["hem_drop_window_cm"])


@test
def t_hem_drop_option_and_pile_guard():
    inp = inputs_for(hem_cm=REAL_HEM, slab_lift=0.5)
    f = ped.check_pose(ped.plan_drape(inp, {"hem_drop_cm": 19.5}), inp)
    check(not has(f, "HEM_ABOVE_FLOOR") and has(f, "PILE_BELOW_FLOOR"), "hem_drop 19.5: hem ok, pile sunk -> refused: %r" % f)
    f = ped.check_pose(ped.plan_drape(inp, {"hem_drop_cm": 40.0}), inp)
    check(has(f, "HEM_BELOW_FLOOR"), "overdrop: hem buried refused: %r" % f)
    inp = inputs_for(hem_cm=5.8, slab_lift=0.0)          # a curtain hanging 5.8 cm off its cache floor (synthetic)
    plan = ped.plan_drape(inp, {})
    check(has(ped.check_pose(plan, inp), "HEM_ABOVE_FLOOR"), "-control: 5.8 cm gap > 5 cm refused")
    w = plan["floor"]["hem_drop_window_cm"]
    check(w == [0.8, 1.0], "window [0.8, 1.0] for a 5.8 cm hem (hem tol 5, sink tol 1): %r" % w)
    f = ped.check_pose(ped.plan_drape(inp, {"hem_drop_cm": 0.9}), inp)
    check(f == [], "+control: hem_drop inside the window passes: %r" % f)
    check(has(ped.check_pose(ped.plan_drape(inp, {"hem_drop_cm": 1.5}), inp), "PILE_BELOW_FLOOR"),
          "-control: past the window's top sinks the pile")


@test
def t_hem_clean_synthetic():
    inp = inputs_for(hem_cm=2.0)
    check(not has(ped.check_pose(ped.plan_drape(inp, {}), inp), "HEM_"), "+control: a 2 cm hem passes")
    check(abs(ped.floor_top_z({"route_end_z": 10.0, "floor_height_cm": 3.0, "slab_lift_cm": 0.5}) - 13.5) < 1e-12,
          "floor top = route z + FloorHeightCm + slab lift")


@test
def t_s4_after_backcloth_revert():
    rb = (11168.469500000001, 240000.0, 0.0)             # hangar_exit_doors_record.json root_before["4"]
    inp = dict(inputs_for(root_loc=rb), n=4)
    st = dict(CLEAN_STATE, scene=4, confirm="DRY S4")
    r = ped.build_report(inp, {}, dict(st, slot_actor="P04 Backcloth (baked)"))
    check(has(r["refusals"], "BACKCLOTH_SLOT_TAKEN"), "S4 before the revert: slot taken")
    inp["other_cloths"] = [{"label": "P04 Backcloth (baked)", "loc": [10450.0, 240000.0, 0.0]}]   # CLOTH_X, p04 apply :45
    r = ped.build_report(inp, {}, st)
    check(has(r["refusals"], "STALE_CLOTH_IN_PATH"), "S4 after the revert, actor left: refused (%r)" % r["refusals"])
    inp["other_cloths"] = []
    r = ped.build_report(inp, {}, st)
    check(r["apply_ready"], "S4 plans like the others once slot and actor are gone: %r" % r["refusals"])
    inp["other_cloths"] = [{"label": "Far cloth", "loc": [0.0, 240000.0, 0.0]}]   # 111 m up the passage: not in the path
    check(ped.build_report(inp, {}, st)["apply_ready"], "+control: a cloth far up the passage is not in the path")


def main():
    for fn in TESTS:
        before = len(CHECKS["failed"])
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            CHECKS["failed"].append("%s raised %s: %s" % (fn.__name__, type(exc).__name__, exc))
        status = "ok" if len(CHECKS["failed"]) == before else "FAIL"
        print("%-40s %s" % (fn.__name__, status))
    for f in CHECKS["failed"]:
        print("  FAILED: " + f)
    print("PASSAGE_END_DRAPE_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
