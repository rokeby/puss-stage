"""Offline harness for shadow_play_spot.py (system Python, no Unreal).

Fixture: the REAL applied sleight record curtain_sleight_record_I1.json (plan, snapshot_after, CST markers) and
hangar_exit_doors_record.json (S1 landed root + box). Every gate has a failing control; positives must pass.
The spawn-track tests run curtain_sleight.py's OWN _spawn_track (loaded by shadow_play_spot) against a stub `unreal`.
Run:  python test_shadow_play_spot.py   -> SHADOW_PLAY_SPOT_TESTS|pass=N|fail=0
"""
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import shadow_play_spot as sps  # noqa: E402

CS = sps.CS
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def has(failures, prefix):
    return any(prefix in text for text in failures)


def load(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


REC = load("curtain_sleight_record_I1.json")
DOORS = load("hangar_exit_doors_record.json")
INP = sps.inputs_from_record(REC, DOORS)
PLAN = sps.plan_spot(INP, {})


def fails(plan=None, inputs=None):
    return sps.check_spot(plan or PLAN, inputs or INP)


def replan(params=None, inputs=None):
    inputs = inputs or INP
    return sps.plan_spot(inputs, params or {}), inputs


# ----------------------------------------------------------------------------------------------- A. aim maths
check("A0 positive: I1 plan passes every check", fails() == [], fails())
P, B = PLAN, PLAN["beats"]
check("A1 beats from the live-shape markers = record frames", B == INP["record_frames"]
      == {"play0": 175, "sleight": 1250, "strike": 1300, "release": 1675}, B)
check("A2 aim point = front fold (-41.3) at eye 510 on the centre line", [round(v, 3) for v in P["aim_rel"]] == [-41.3, 0.0, 510.0], P["aim_rel"])
want_rel = [-41.3 - 3000 * math.cos(math.radians(20)), 0.0, 510 + 3000 * math.sin(math.radians(20))]
check("A3 spot drape-frame position (throw 30 m, 20 deg up)", max(abs(P["loc_rel"][i] - want_rel[i]) for i in range(3)) < 1e-6, P["loc_rel"])
hw = P["spots"]["hangar"]["world"]
check("A4 hangar spot world = hung drape (34883.96, 0, 0) + rel", abs(hw["loc"][0] - (34883.9635 + want_rel[0])) < 1e-3
      and abs(hw["loc"][2] - want_rel[2]) < 1e-3 and abs(hw["pitch"] + 20.0) < 1e-9, hw)
for side in sps.SIDES:
    sp = P["spots"][side]
    d, t = sps._line_distance(sp["aim_world"], sp["world"]["loc"], CS["direction"](sp["world"]["pitch"], sp["world"]["yaw"]))
    check("A5 %s beam axis hits its aim point at the throw" % side, d < 1e-6 and abs(t - 3000.0) < 1e-6, (d, t))
mw = P["spots"]["mouth"]["world"]
check("A6 mouth spot yaw = mouth drape yaw 22.908", abs(mw["yaw"] - 22.908000946044922) < 1e-9, mw)
lp = sps.to_local(INP["root_live"], hw["loc"])
check("A7 hangar spot inside the landed box (root frame)", not CS["inside_hangar"](lp, lp, INP["hangar"], INP["box_margin"]), lp)

# REST-pose controls (memory: level saved LANDED; REST = root pitch -90 about its origin)
rest_root = dict(INP["root_live"], pitch=-90.0)
rest_drape = sps.compose(rest_root, INP["drape_local"])
bad_in = copy.deepcopy(INP)
for key in ("play0", "sleight", "strike"):
    bad_in["hangar_drape_at"][key] = {"loc": rest_drape["loc"], "pitch": -90.0, "yaw": rest_drape["yaw"], "roll": 0.0}
f = fails(sps.plan_spot(bad_in, {}), bad_in)
check("A8 -control REST-composed drape: BOX fails", has(f, "BOX:"), f)
check("A9 -control REST-composed drape: DRAPE_NOT_ON_LIVE_ROOT + DRAPE_TILTED", has(f, "DRAPE_NOT_ON_LIVE_ROOT") and has(f, "DRAPE_TILTED"), f)
check("A10 REST-composed spot is underground (z < -2000)", sps.plan_spot(bad_in, {})["spots"]["hangar"]["world"]["loc"][2] < -2000.0)
bad_root = copy.deepcopy(INP)
bad_root["root_live"] = rest_root
f = fails(sps.plan_spot(bad_root, {}), bad_root)
check("A11 -control live root read in REST pose: guard fails", has(f, "DRAPE_NOT_ON_LIVE_ROOT") and has(f, "BOX:"), f)
check("A12 -control REST root: compare_live refuses ROOT_NOT_LANDED", has(sps.compare_live(INP, bad_root), "ROOT_NOT_LANDED"))
off = copy.deepcopy(INP)
for key in off["hangar_drape_at"]:
    off["hangar_drape_at"][key]["loc"][0] += 5.0
check("A13 -control drape 5 cm off the live root", has(fails(sps.plan_spot(off, {}), off), "DRAPE_NOT_ON_LIVE_ROOT"))
check("A14 -control drape keys drifted from the record", has(sps.compare_live(INP, off), "DRAPE_KEYS_DRIFTED"))
mm = copy.deepcopy(PLAN)
mm["spots"]["mouth"]["world"]["loc"][2] += 1.0
check("A15 -control mouth spot 1 cm off its twin: MATCH_POSE", has(fails(mm), "MATCH_POSE"))
mm = copy.deepcopy(PLAN)
mm["spots"]["mouth"]["world"]["pitch"] += 0.2
check("A16 -control mouth spot tilted 0.2 deg: MATCH_POSE + AIM", has(fails(mm), "MATCH_POSE") and has(fails(mm), "AIM_MOUTH"))
check("A17 -control throw 70 m leaves the box", has(fails(*replan({"throw_cm": 7000.0})), "BOX:"))
check("A18 -control circle 6 m spills out of the frame", has(fails(*replan({"circle_diameter_cm": 600.0})), "CIRCLE_OUTSIDE_FRAME"))
check("A19 -control attenuation radius shorter than the throw", has(fails(*replan({"radius_factor": 0.9})), "RADIUS_SHORT"))
ri = copy.deepcopy(INP)
ri["card_front_x"] += 1.0
check("A20 -control record lens/card disagree on the front fold", has(fails(PLAN, ri), "AIM_RECORD_INCONSISTENT"))
nh = copy.deepcopy(INP)
nh["hangar_drape_at"]["play0"]["loc"][2] += 300.0
check("A21 -control drape still flying at play start: DRAPE_NOT_HUNG", has(fails(sps.plan_spot(nh, {}), nh), "DRAPE_NOT_HUNG"))
check("A22 -control mouth drape moved: compare_live refuses", has(sps.compare_live(INP, dict(copy.deepcopy(INP), mouth_drape={"loc": [0.0, 80010.0, 0.0], "yaw": 22.908000946044922, "pitch": 0.0})), "MOUTH_DRAPE_DRIFTED"))

# photometry (justification numbers)
ph = PLAN["photometry"]
check("A23 lantern illuminance at the aim = 116.97 cd / 15.477 m^2 = 0.4883 lux", abs(ph["lantern_lux"] - 0.48830) < 1e-4, ph)
check("A24 mouth lantern gives the same lux (210 cd / 20.738 m^2)", abs(210.0 / (REC["plan"]["lantern"]["throw_mouth_cm"] / 100.0) ** 2 - ph["lantern_lux"]) < 1e-4)
check("A25 peak = 16 x 0.4883 lux x 30^2 / cos20 = 7483 cd", abs(ph["peak_cd"] - 16 * ph["lantern_lux"] * 900 / math.cos(math.radians(20))) < 1e-6 and round(ph["peak_cd"]) == 7483, ph["peak_cd"])
check("A26 cone: outer = atan(180/3000) = 3.434 deg, inner 0.6x", abs(PLAN["cone"]["outer_deg"] - math.degrees(math.atan(0.06))) < 1e-9 and abs(PLAN["cone"]["inner_deg"] / PLAN["cone"]["outer_deg"] - 0.6) < 1e-12)
p2, _ = replan({"hangar_gain": 2.0})
check("A27 hangar_gain scales only the hangar spot and still matches", fails(p2) == [] and abs(p2["spots"]["hangar"]["peak_cd"] - 2 * p2["spots"]["mouth"]["peak_cd"]) < 1e-6, fails(p2))
mi = copy.deepcopy(PLAN)
mi["spots"]["hangar"]["intensity_keys"] = [(f_, v * 1.5) for f_, v in mi["spots"]["hangar"]["intensity_keys"]]
mi["spots"]["hangar"]["peak_cd"] *= 1.5
check("A28 -control hangar spot 1.5x without gain: MATCH_INTENSITY", has(fails(mi), "MATCH_INTENSITY"))

# ----------------------------------------------------------------------------------------------- B. key timing
pk = PLAN["photometry"]["peak_cd"]
check("B1 hangar keys: 0 to play start 175, up by 187, hold to strike 1300, off 1301",
      PLAN["spots"]["hangar"]["intensity_keys"] == [(0, 0.0), (175, 0.0), (187, pk), (1300, pk), (1301, 0.0)], PLAN["spots"]["hangar"]["intensity_keys"])
check("B2 mouth keys: up by 187, hold through GO 10 HOLD 1675, fade to 0 at 1700",
      PLAN["spots"]["mouth"]["intensity_keys"] == [(0, 0.0), (175, 0.0), (187, pk), (1675, pk), (1700, 0.0)], PLAN["spots"]["mouth"]["intensity_keys"])
check("B3 spawn windows: hangar [150, 1302), mouth [150, 1701)", PLAN["spots"]["hangar"]["spawn"] == [(150, True), (1302, False)]
      and PLAN["spots"]["mouth"]["spawn"] == [(150, True), (1701, False)])
ka = CS["key_at"]
for side in sps.SIDES:
    k = PLAN["spots"][side]["intensity_keys"]
    check("B4 %s steady at peak over the cut 1225..1275" % side, all(abs(ka(k, fr, 1) - pk) < 1e-9 for fr in range(1225, 1276)))
check("B5 mouth at peak on the HOLD frame 1674 (transport rests one frame before GO)", abs(ka(PLAN["spots"]["mouth"]["intensity_keys"], 1674, 1) - pk) < 1e-9)
check("B6 required end 1701 <= length 2183, range unchanged", PLAN["required_end"] == 1701 and PLAN["end"] == 2183)
check("B7 GO 10 curtain at the drop parsed as HOLD", PLAN["go"] == ["GO 10 curtain", 1675] and CS["parse_go_label"]("GO 10 curtain")[2] != 0)
ps, _ = replan({"fade_up_s": 0.0})
check("B8 snap mode: (174, 0) -> (175, peak) and passes", ps["spots"]["mouth"]["intensity_keys"][1:3] == [(174, 0.0), (175, pk)] and fails(ps) == [], fails(ps))
fb = copy.deepcopy(PLAN)
fb["spots"]["mouth"]["intensity_keys"][3] = (1660, pk)
check("B9 -control fade starts before the GO: FADE_BEFORE_GO", has(fails(fb), "FADE_BEFORE_GO"))
lc = copy.deepcopy(PLAN)
lc["spots"]["hangar"]["intensity_keys"].insert(3, (1260, pk * 0.5))
check("B10 -control a key inside the ready window: STATE_CHANGES_ACROSS_CUT", has(fails(lc), "STATE_CHANGES_ACROSS_CUT"))
si = copy.deepcopy(INP)
si["beats"] = dict(si["beats"], strike=1260)
f = fails(sps.plan_spot(si, {}), si)
check("B11 -control hangar strike 10 frames after the cut: READY", has(f, "READY"), f)
check("B12 -control fade_out 30 s: RANGE_WOULD_CHANGE", has(fails(*replan({"fade_out_s": 30.0})), "RANGE_WOULD_CHANGE"))
ue = copy.deepcopy(PLAN)
ue["spots"]["hangar"]["intensity_keys"][1] = (170, 100.0)
check("B13 -control lit before play start: TIMING_HANGAR", has(fails(ue), "TIMING_HANGAR"))
sw = copy.deepcopy(PLAN)
sw["spots"]["mouth"]["spawn"] = [(150, True), (1690, False)]
check("B14 -control despawned mid-fade: SPAWN_MOUTH", has(fails(sw), "SPAWN_MOUTH"))
marks = [m for m in INP["markers"] if m[0] != "CST sleight"]
try:
    sps.beats_from_markers(marks)
    check("B15 -control missing CST sleight marker refused", False)
except sps.PlanError as exc:
    check("B15 -control missing CST sleight marker refused", "BEATS_MISSING" in str(exc), str(exc))
marks = [m if m[0] != "GO 10 curtain" else ["GO 10 PASS curtain", m[1]] for m in INP["markers"]]
try:
    sps.beats_from_markers(marks)
    check("B16 -control GO at the drop is PASS: refused", False)
except sps.PlanError as exc:
    check("B16 -control GO at the drop is PASS: refused", "GO_IS_PASS" in str(exc), str(exc))
dr = copy.deepcopy(INP)
dr["beats"] = dict(dr["beats"], sleight=1251)
check("B17 -control live beats drifted from the record: BEATS_DRIFTED", has(sps.compare_live(INP, dr), "BEATS_DRIFTED"))
check("B18 legacy BoyCatStart 75 reported, not used", has(sps.build_report(REC, DOORS, {})["warnings"], "LEGACY_MARKERS"))


# ----------------------------------------------------------------------------------------------- C. spawn-track reuse
class _Cls:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class _Chan:
    def __init__(self):
        self.default, self.keys = None, []

    def set_default(self, v):
        self.default = v

    def add_key(self, frame, value, time_unit=None):
        self.keys.append((frame, value))


class _Sec:
    def __init__(self):
        self.range, self.chan = None, _Chan()

    def set_range(self, a, b):
        self.range = (a, b)

    def get_all_channels(self):
        return [self.chan]


class _Track:
    def __init__(self, cls):
        self.cls, self.sections = _Cls(cls), [_Sec()]

    def get_class(self):
        return self.cls

    def get_sections(self):
        return list(self.sections)

    def remove_section(self, s):
        self.sections.remove(s)

    def add_section(self):
        s = _Sec()
        self.sections.append(s)
        return s


class _Binding:
    def __init__(self, n_spawn, remove_works=True):
        self.tracks = [_Track("MovieSceneSpawnTrack") for _ in range(n_spawn)]
        self.added, self.remove_works = 0, remove_works

    def get_tracks(self):
        return list(self.tracks)

    def add_track(self, cls):
        self.added += 1
        t = _Track("MovieSceneSpawnTrack")
        self.tracks.append(t)
        return t

    def remove_track(self, t):
        if self.remove_works:
            self.tracks.remove(t)
        return None                                  # memory: remove_track returns None - read back


class _Unreal:
    class MovieSceneTimeUnit:
        DISPLAY_RATE = "display"

    MovieSceneSpawnTrack = "MovieSceneSpawnTrack"

    @staticmethod
    def FrameNumber(v):
        return int(v)


CS["unreal"] = _Unreal                               # stub ONLY inside the loaded curtain_sleight namespace
sp = PLAN["spots"]["mouth"]
b1 = _Binding(1)
CS["_spawn_track"](b1, sp["spawn"], PLAN["end"])
check("C1 UE's auto spawn track is REUSED (no add_track), exactly one", b1.added == 0 and sps.spawn_track_count_failures(b1.get_tracks(), "m") == [])
check("C2 reused track: one section [0, end+1], default False, keys = plan", b1.tracks[0].sections[0].range == (0, 2184)
      and b1.tracks[0].sections[0].chan.default is False and b1.tracks[0].sections[0].chan.keys == [(150, True), (1701, False)])
b0 = _Binding(0)
CS["_spawn_track"](b0, sp["spawn"], PLAN["end"])
check("C3 no auto track: one added, exactly one", b0.added == 1 and sps.spawn_track_count_failures(b0.get_tracks(), "m") == [])
b2 = _Binding(2, remove_works=False)
CS["_spawn_track"](b2, sp["spawn"], PLAN["end"])
check("C4 -control duplicate spawn track whose remove_track lies: SPAWN_TRACK_COUNT",
      has(sps.spawn_track_count_failures(b2.get_tracks(), "m"), "SPAWN_TRACK_COUNT"))
b3 = _Binding(1)
b3.tracks[0].sections.append(_Sec())
check("C5 -control two spawn sections: SPAWN_SECTION_COUNT", has(sps.spawn_track_count_failures(b3.get_tracks(), "m"), "SPAWN_SECTION_COUNT"))
GUIDS = {sps.SPOT_NAMES["hangar"]: "AAAA0000000000000000000000000001", sps.SPOT_NAMES["mouth"]: "AAAA0000000000000000000000000002"}
before = CS["normalize_snapshot"](REC["snapshot_after"])
exp = sps.apply_model(before, PLAN, GUIDS)
dup = copy.deepcopy(exp)
for b in dup["bindings"]:
    if b["guid"] in GUIDS.values():
        b["tracks"].append({"class": "MovieSceneSpawnTrack", "name": "", "sections": [[0, 2184]]})
        break
check("C6 -control live snapshot with a second spawn track differs from the model", CS["snapshot_diff"](CS["normalize_snapshot"](dup), exp) != [])
check("C7 model: each spot = spawn + transform + Intensity float, no parent, range unchanged",
      all(len(b["tracks"]) == 3 and b["parent"] == "" for b in exp["bindings"] if b["guid"] in GUIDS.values())
      and exp["playback"] == [0, 2183])

# ----------------------------------------------------------------------------------------------- D. refusals
CLEAN = {"pie": False, "world_ok": True, "sequencer_open": False, "census": {"content": [], "maps": []}, "zz": False,
         "sleight_record": REC, "sleight_drift": [], "spot_record": None, "confirm": "APPLY I1"}
check("D0 positive: clean APPLY I1 state has no refusals", sps.preflight_refusals("APPLY", 1, CLEAN) == [], sps.preflight_refusals("APPLY", 1, CLEAN))
cases = [("PIE", {"pie": True}, "PIE_OR_SIE_ACTIVE"),
         ("dirty census", {"census": {"content": ["/Game/X"], "maps": []}}, "DIRTY_CENSUS"),
         ("dirty map", {"census": {"content": [], "maps": ["/Game/M"]}}, "DIRTY_CENSUS"),
         ("Sequencer open", {"sequencer_open": True}, "SEQUENCER_IS_OPEN"),
         ("existing record", {"spot_record": {"applied": False}}, "RECORD_EXISTS"),
         ("sleight not applied (no record)", {"sleight_record": None}, "SLEIGHT_NOT_APPLIED"),
         ("sleight record applied=false", {"sleight_record": dict(REC, applied=False)}, "SLEIGHT_NOT_APPLIED"),
         ("sleight record for I2 used on I1", {"sleight_record": dict(REC, interaction=2)}, "SLEIGHT_NOT_APPLIED"),
         ("sleight drifted", {"sleight_drift": ["bindings differs"]}, "SLEIGHT_DRIFTED"),
         ("confirm mismatch", {"confirm": "APPLY I2"}, "CONFIRM_MISMATCH"),
         ("wrong world", {"world_ok": False}, "WRONG_WORLD"),
         ("ZZ actors", {"zz": True}, "ZZ_ACTORS_PRESENT")]
for name, delta, code in cases:
    st = dict(CLEAN, **delta)
    check("D -control %s -> %s" % (name, code), has(sps.preflight_refusals("APPLY", 1, st), code), sps.preflight_refusals("APPLY", 1, st))
for n in (2, 3, 4, 5):
    rec = None
    path = os.path.join(HERE, sps.SLEIGHT_RECORD % n)
    if os.path.isfile(path):
        rec = load(sps.SLEIGHT_RECORD % n)
    st = dict(CLEAN, sleight_record=rec, confirm="DRY I%d" % n)
    check("D I%d today (record on disk: %s) -> SLEIGHT_NOT_APPLIED" % (n, rec is not None),
          has(sps.preflight_refusals("DRY", n, st), "SLEIGHT_NOT_APPLIED") == (not (rec and rec.get("applied"))))
check("D REVERT with no record -> NOTHING_TO_REVERT", has(sps.preflight_refusals("REVERT", 1, dict(CLEAN, confirm="REVERT I1")), "NOTHING_TO_REVERT"))
check("D REVERT with an applied record passes the preflight", sps.preflight_refusals("REVERT", 1, dict(CLEAN, confirm="REVERT I1", spot_record={"applied": True, "interaction": 1})) == [])
check("D range change read-back -> RANGE_CHANGED", has(sps.range_readback([0, 2183], [0, 2184]), "RANGE_CHANGED") and sps.range_readback([0, 2183], [0, 2183]) == [])
check("D confirm strings", sps.confirm_ok("DRY", 1, "DRY I1") and not sps.confirm_ok("DRY", 1, "APPLY I1") and not sps.confirm_ok("DRY", 1, None))
try:
    sps.merged_params({"intensity": 5})
    check("D unknown param refused", False)
except sps.PlanError:
    check("D unknown param refused", True)

# ----------------------------------------------------------------------------------------------- E. revert
record = {"snapshot_before": before, "snapshot_after": exp, "created_binding_guids": sorted(GUIDS.values()), "backup": "B"}
rev = sps.revert_model(exp, record["created_binding_guids"])
check("E1 revert model is EXACT (== snapshot_before)", sps.revert_exact(rev, record) == [])
check("E2 revert gate passes on the saved state", sps.revert_gate(exp, record) == [])
drift = copy.deepcopy(exp)
for b in drift["bindings"]:
    if b["guid"] == GUIDS[sps.SPOT_NAMES["mouth"]]:
        b["tracks"].append({"class": "MovieSceneFloatTrack", "name": "hand edit", "sections": [[0, 2184]]})
check("E3 -control hand-added track: revert refuses STATE_DRIFTED_SINCE_APPLY", has(sps.revert_gate(drift, record), "STATE_DRIFTED"))
drift2 = copy.deepcopy(exp)
drift2["markers"].append(["GO 11 extra", 1800])
check("E4 -control extra marker: revert refuses", has(sps.revert_gate(drift2, record), "STATE_DRIFTED"))
partial = sps.revert_model(exp, record["created_binding_guids"][:1])
check("E5 -control one binding survives remove(): REVERT_NOT_EXACT", has(sps.revert_exact(partial, record), "REVERT_NOT_EXACT"))
check("E6 stack order: after APPLY the SLEIGHT's own drift gate sees a difference (revert spots first)",
      CS["snapshot_diff"](exp, CS["normalize_snapshot"](REC["snapshot_after"])) != [])

# ----------------------------------------------------------------------------------------------- F. misc
check("F1 plan is deterministic", sps.plan_spot(INP, {})["digest"] == PLAN["digest"])
check("F2 keys_match: exact frames pass, -control shifted frame fails",
      sps.keys_match([(0, 0.0), (187, pk)], [(0, 0.0), (187, pk)]) == [] and sps.keys_match([(0, 0.0), (188, pk)], [(0, 0.0), (187, pk)]) != [])
check("F3 keys_match: -control value off 1 % fails", sps.keys_match([(187, pk * 1.01)], [(187, pk)]) != [])
expo, w = sps.exposure_summary({"hangar": [{"ppv": "U", "enabled": True, "min_ev": -3.0, "max_ev": -3.0},
                                           {"ppv": "S1 Hangar Pinned Exposure", "enabled": True, "min_ev": 0.5, "max_ev": 0.5}],
                                "mouth": [{"ppv": "U", "enabled": True, "min_ev": -3.0, "max_ev": -3.0}]})
check("F4 exposure: the 5 Oct DRY PPV rows -> AE_PINNED both + EXPOSURE_MISMATCH (gain 11.31 candidate)",
      has(w, "AE_PINNED_HANGAR") and has(w, "AE_PINNED_MOUTH") and has(w, "EXPOSURE_MISMATCH") and "11.3137" in " ".join(w), w)
_, w2 = sps.exposure_summary({"hangar": [{"ppv": "U", "enabled": True, "min_ev": -3.0, "max_ev": 2.0}],
                              "mouth": [{"ppv": "U", "enabled": True, "min_ev": -3.0, "max_ev": 2.0}]})
check("F5 -control unpinned exposure: no AE_PINNED / mismatch warning", w2 == [], w2)
dry = load("curtain_sleight_I1_dry.json")["diagnostics"]
expo3, w3 = sps.exposure_summary({"hangar": dry["ppv_hangar_camera"], "mouth": dry["ppv_mouth_camera"]})
check("F6 the REAL 5 Oct DRY rows: hangar pinned [-3, 0.5], mouth [-3]", expo3["hangar"]["pinned_ev100"] == [-3.0, 0.5]
      and expo3["mouth"]["pinned_ev100"] == [-3.0], expo3)

passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [(n, d) for n, ok, d in RESULTS if not ok]
for name, detail in failed:
    print("FAIL", name, str(detail)[:400])
print("SHADOW_PLAY_SPOT_TESTS|pass=%d|fail=%d" % (passed, len(failed)))
sys.exit(1 if failed else 0)
