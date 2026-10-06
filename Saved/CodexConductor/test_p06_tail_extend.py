"""Offline harness for p06_tail_extend.py (system Python, no Unreal). Every gate has a failing control.

Fixture data, cited (the live DRY re-reads all of it):
  Compiled segments (ticks, 24000/s): walking_music_swap_dry.json "segments", run WALK-20261005-143830 [meas 5 Oct].
  Passage 6 = [47128792, 49782259) = 2653467 ticks = 110.561125 s [meas, same record].
  Display rate 25 fps = Show default [decl InfinityStageShowAsset.cpp:86]; 24/30/60 fps also exercised.
  P06's lead-in / intervals / tail split is INVENTED (only their sum is measured); the live DRY reads the real ones.
Run: python test_p06_tail_extend.py -> P06_TAIL_EXTEND_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_PATH = os.path.join(HERE, "p06_tail_extend.py")
spec = importlib.util.spec_from_file_location("p06_tail_extend", TOOL_PATH)
pt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt)
assert pt.unreal is None, "harness must run without Unreal"

with open(os.path.join(HERE, "p06_tail_extend_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
with open(os.path.join(HERE, "walking_music_swap_dry.json"), encoding="utf-8") as _h:
    MEASURED = json.load(_h)["segments"]

CHECKS = {"n": 0, "failed": []}
TESTS = []
TICK = 24000
P06 = "9BFC29C45D47911FF7836BB8537230D2"


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def refused(rows, token):
    return any(token in r for r in rows)


def p06_seg():
    return [s for s in MEASURED if s["label"] == "Passage 6"][0]


def plan(fps=(25, 1), song=125.0, head=1.0, maxd=16.0, seg=None, tail=533467):
    s = seg or p06_seg()
    return pt.tail_plan(s["start"], s["end"], tail, TICK, fps[0], fps[1], song, head, maxd)


# --------------------------------------------------------------------------------------------- fake Show + Master
class FakeWorld(object):
    """Compiles segments like Compiler.cpp:200-312 and rebuilds managed rows like SequenceBuilderLibrary.cpp:196-601.
    P06 (and an invented later Passage 'P07' in some fixtures) carries keys at ABSOLUTE ticks; MoveSection on start
    change (patch K) unless broken=True."""

    def __init__(self, later_passage=False):
        self.blocks = []
        for s in MEASURED:
            if s["label"] == "Passage 6":
                self.blocks.append({"label": s["label"], "kind": "Passage", "guid": P06, "lead": 120000,
                                    "intervals": [400000] * 6, "tail": 533467, "tail_cm": 600.0})
            elif s["label"].startswith("Passage"):
                self.blocks.append({"label": s["label"], "kind": "Passage", "guid": "G-" + s["label"],
                                    "lead": 0, "intervals": [s["end"] - s["start"]], "tail": 0, "tail_cm": 0.0})
            else:
                self.blocks.append({"label": s["label"], "kind": "Scene", "guid": "G-" + s["label"],
                                    "len": s["end"] - s["start"]})
        if later_passage:
            self.blocks.insert(len(self.blocks) - 1, {"label": "Passage 7", "kind": "Passage", "guid": "G-P07",
                                                      "lead": 0, "intervals": [240000], "tail": 0, "tail_cm": 0.0})
        self.broken_move = False
        self.lying_setter = False
        self.sections = None
        self.keys = {}
        self.rebuild()
        p06s = self.seg("Passage 6")
        self.keys[P06] = {"start": p06s["start"], "pins_rel": [480000], "wing_pins": [],
                          "channels": {"Camera.SpeedMultiplier": [[p06s["start"] + 24000, 1.0]],
                                       "Camera.HeightOffsetCm": [[p06s["start"] + 24000, 0.0], [p06s["end"], 12.5]]}}
        for b in self.blocks:
            if b["kind"] == "Passage" and b["guid"] != P06:
                s = self.seg(b["label"])
                self.keys[b["guid"]] = {"start": s["start"], "pins_rel": [], "wing_pins": [],
                                        "channels": {"Wing.CycleRateScale": [[s["start"] + 100, 1.0], [s["end"] - 100, 2.0]]}}

    def segments(self):
        out, cur = [], 0
        for b in self.blocks:
            n = b["len"] if b["kind"] == "Scene" else pt.compiled_length(b["lead"], b["intervals"], b["tail"])
            out.append({"label": b["label"], "start": cur, "end": cur + n})
            cur += n
        return out

    def seg(self, label):
        return [s for s in self.segments() if s["label"] == label][0]

    def rebuild(self):
        segs = self.segments()
        rows = {"Playback:master": [0, segs[-1]["end"]]}
        for b, s in zip(self.blocks, segs):
            rows["%s:%s" % (b["kind"], b["guid"])] = [s["start"], s["end"]]
            if b["guid"] == P06:
                rows["Choreo:" + P06] = [s["start"], s["end"]]
                rows["Music:" + P06] = [s["start"], s["end"]]
            if b["label"].startswith("Scene 6"):
                rows["Music:" + b["guid"]] = [s["start"], s["end"]]
            k = self.keys.get(b["guid"])
            if k is not None and k["start"] != s["start"] and not self.broken_move:
                d = s["start"] - k["start"]
                k["channels"] = {n: [[t + d, v] for t, v in ks] for n, ks in k["channels"].items()}
                k["start"] = s["start"]
        self.sections = rows
        return True

    def p06(self):
        return [b for b in self.blocks if b.get("guid") == P06][0]

    def read_tail(self):
        b = self.p06()
        return b["tail"], b["tail_cm"]

    def write_tail(self, frames):
        if not self.lying_setter:
            self.p06()["tail"] = int(frames)

    def plain(self):
        t, cm = self.read_tail()
        return json.loads(json.dumps({"tail_frames": t, "tail_distance_cm": cm, "segments": self.segments(),
                                      "managed": self.sections, "keys": self.keys}))


# --------------------------------------------------------------------------------------------- tests
@test
def t_args():
    check(pt.validate_args(ARGS) == [], "shipped args validate: %r" % pt.validate_args(ARGS))
    check(ARGS["confirm"] == "%s %s" % (ARGS["mode"], pt.CONFIRM_SUFFIX), "shipped confirm matches its mode")
    bad = dict(ARGS, passage_label="Passage 5", song_s=-1, expected_old_len_ticks=0, passage_guid="")
    r = pt.validate_args(bad)
    for token in ("PASSAGE_LABEL_NOT_P06", "ARG_SONG_S_INVALID", "EXPECTED_OLD_LEN_TICKS_INVALID", "PASSAGE_GUID_MISSING"):
        check(refused(r, token), "control: bad args refused " + token)
    check(ARGS["expected_old_len_ticks"] == p06_seg()["end"] - p06_seg()["start"], "args old length = measured segment")


@test
def t_delta_maths():
    p = plan()
    check(p["old_len"] == 2653467, "old len 2653467")
    check(p["target_ticks"] == 3024000, "target 126.0 s = 3024000 ticks")
    check(p["raw_delta_ticks"] == 370533, "raw delta 370533")
    check(p["ticks_per_display_frame"] == 960 and p["delta_frames"] == 386 and p["delta_ticks"] == 370560,
          "25 fps: 386 frames = 370560 ticks (%r)" % p)
    check(abs(p["delta_s"] - 15.44) < 1e-12, "delta 15.440 s")
    check(p["new_len"] == 3024027 and p["new_len"] >= 3024000, "new len 3024027 >= target")
    check(p["new_tail"] == 533467 + 370560, "new tail = old + delta")
    check(p["new_end"] == p06_seg()["end"] + 370560, "new end")
    check(p["delta_ticks"] % 960 == 0 and p["delta_ticks"] - p["raw_delta_ticks"] < 960, "round UP by < 1 frame")
    check(plan((30, 1))["delta_ticks"] == 371200, "30 fps -> 464 frames 371200")
    check(plan((24, 1))["delta_ticks"] == 371000, "24 fps -> 371 frames 371000")
    check(plan((60, 1))["delta_ticks"] == 370800, "60 fps -> 927 frames 370800")
    # exact multiple: no extra frame
    seg = {"start": 0, "end": 3024000 - 960 * 10}
    check(plan(seg=seg, tail=0)["delta_ticks"] == 9600, "exact multiple: no round-up")
    # failing controls
    for kw, token in ((dict(seg={"start": 0, "end": 3024000}, tail=0), "ALREADY_FITS"),
                      (dict(maxd=15.0), "DELTA_TOO_LARGE"),
                      (dict(fps=(30000, 1001)), "TICKS_PER_DISPLAY_FRAME_NOT_INTEGER"),
                      (dict(fps=(7, 1)), "TICKS_PER_DISPLAY_FRAME_NOT_INTEGER")):
        try:
            plan(**kw)
            check(False, "control: %s must raise" % token)
        except pt.PlanError as exc:
            check(token in str(exc), "control raised %s (%s)" % (token, exc))
    check(pt.tail_speed(533467, 600.0, TICK) > pt.tail_speed(533467 + 370560, 600.0, TICK), "tail drift slows")


@test
def t_consistency():
    check(pt.consistency_refusals(2653467, 120000, [400000] * 6, 533467, 2653467) == [], "model = compiled")
    check(refused(pt.consistency_refusals(2653467, 120000, [400000] * 6, 533466, 2653467), "COMPILE_MODEL_MISMATCH"),
          "control: one tick off -> mismatch")
    check(refused(pt.consistency_refusals(2653467, 120000, [400000] * 6, 533467, 2653000), "P06_LENGTH_CHANGED"),
          "control: live length differs from the decision")
    check(pt.wing_pass_frames(100, 10, [5, 7, 9]) == [110, 115, 122], "wing pass frames")


def _p06_facts(start, end):
    return {"channels": {"Camera.SpeedMultiplier": [[start + 10, 1.0]], "Camera.YawDegrees": [[end, 3.0]]},
            "pins_rel": [1000], "wing_pin_frames": [start + 5000]}


def _choreo(old_len, new_len):
    return {"path": "/Game/InfinityStage/Choreo/LS_Choreo_Passage_6", "start_offset": 0,
            "playback_ticks": [0, old_len + 30 * TICK], "keys": [["a/k", old_len - 1], ["a/k", old_len]],
            "sections": [{"where": "light", "start": 0, "end": old_len, "keyed": True}],
            "markers": [["§ Intro", 0], ["bar 3", 1000]], "camera_cut": False}


@test
def t_beyond_end():
    p = plan()
    s, e, nl = p["old_start"], p["old_end"], p["new_len"]
    r, w = pt.beyond_end_refusals(_p06_facts(s, e), _choreo(p["old_len"], nl), s, e, nl)
    check(r == [], "clean fixture passes (keys AT the old end are allowed): %r" % r)
    controls = []
    f = _p06_facts(s, e)
    f["channels"]["Camera.YawDegrees"].append([e + 1, 4.0])
    controls.append((f, _choreo(p["old_len"], nl), "P06_KEY_BEYOND_OLD_END"))
    f = _p06_facts(s, e)
    f["pins_rel"].append(p["old_len"])
    controls.append((f, _choreo(p["old_len"], nl), "P06_PIN_BEYOND_OLD_END"))
    f = _p06_facts(s, e)
    f["wing_pin_frames"].append(e + 10)
    controls.append((f, _choreo(p["old_len"], nl), "P06_WING_PIN_BEYOND_OLD_END"))
    c = _choreo(p["old_len"], nl)
    c["keys"].append(["a/k", p["old_len"] + 1])
    controls.append((_p06_facts(s, e), c, "CHOREO_KEY_BEYOND_OLD_END"))
    c = _choreo(p["old_len"], nl)
    c["sections"].append({"where": "audio", "start": 0, "end": p["old_len"] + 30 * TICK, "keyed": False})
    controls.append((_p06_facts(s, e), c, "CHOREO_UNKEYED_SECTION_PAST_OLD_END"))
    c = _choreo(p["old_len"], nl)
    c["sections"].append({"where": "late", "start": p["old_len"] + 5, "end": None, "keyed": True})
    controls.append((_p06_facts(s, e), c, "CHOREO_SECTION_STARTS_AFTER_OLD_END"))
    c = _choreo(p["old_len"], nl)
    c["markers"].append(["GO 12 Blackout", p["old_len"] + 24000])
    controls.append((_p06_facts(s, e), c, "CHOREO_MARKER_PAST_OLD_END"))
    c = _choreo(p["old_len"], nl)
    c["playback_ticks"] = [0, nl - 1]
    controls.append((_p06_facts(s, e), c, "CHOREO_SHORT"))
    c = _choreo(p["old_len"], nl)
    c["start_offset"] = 48000
    c["keys"].append(["a/k", p["old_len"] + 24000])            # inside old end once the offset is applied
    r2, _w = pt.beyond_end_refusals(_p06_facts(s, e), c, s, e, nl)
    check(not refused(r2, "CHOREO_KEY_BEYOND_OLD_END"), "start offset shifts the local end")
    for facts, choreo, token in controls:
        r, _w = pt.beyond_end_refusals(facts, choreo, s, e, nl)
        check(refused(r, token), "control refused: " + token)
    c = _choreo(p["old_len"], nl)
    c["markers"].append(["bar 99", p["old_len"] + 24000])
    c["sections"].append({"where": "light2", "start": 0, "end": None, "keyed": True})
    r, w = pt.beyond_end_refusals(_p06_facts(s, e), c, s, e, nl)
    check(r == [] and refused(w, "CHOREO_SONG_MARKER_PAST_OLD_END") and refused(w, "CHOREO_SECTION_HOLDS_PAST_OLD_END"),
          "song marker / keyed hold past end = warnings only")
    r, _w = pt.beyond_end_refusals(_p06_facts(s, e), None, s, e, nl)
    check(r == [], "no Choreo: nothing to refuse")


@test
def t_speed_renorm():
    s, e, ne = 1000, 5000, 6000
    check(pt.last_span_start(s, e, [100, 3000, 9000], [2500]) == 4000, "last span starts at the last pin (start+3000)")
    check(pt.last_span_start(s, e, [], []) == s, "no pins: span starts at the Passage start")
    check(pt.speed_renorm_refusals([], s, ne) == [], "no keys")
    check(pt.speed_renorm_refusals([[1500, 1.0], [4500, 1.0]], s, ne) == [], "constant keys")
    check(pt.speed_renorm_refusals([[100, 0.5], [800, 1.0]], s, ne) == [], "varying only before the span, held after")
    check(refused(pt.speed_renorm_refusals([[1500, 1.0], [4500, 2.0]], s, ne), "SPEED_RENORMALISED"),
          "control: varying keys inside the last span")
    check(refused(pt.speed_renorm_refusals([[900, 1.0], [7000, 2.0]], s, ne), "SPEED_RENORMALISED"),
          "control: interpolation across the span")


@test
def t_artist():
    e = p06_seg()["end"]
    rows = [{"owner": "root", "track": "FOH", "class": "MovieSceneFloatTrack", "sections": [[0, e - 1]], "keys": [5, e - 1]}]
    check(pt.artist_refusals(rows, [["note", e - 1]], e) == [], "artist content before the old end is fine")
    check(refused(pt.artist_refusals([dict(rows[0], keys=[e])], [], e), "ARTIST_CONTENT_NOT_RIPPLED"), "control: key at end")
    check(refused(pt.artist_refusals([dict(rows[0], sections=[[0, None]])], [], e), "ARTIST_CONTENT_NOT_RIPPLED"),
          "control: open-ended section")
    check(refused(pt.artist_refusals([dict(rows[0], sections=[[0, 50886259]])], [], e), "ARTIST_CONTENT_NOT_RIPPLED"),
          "control: whole-show section ending at the old show end")
    check(refused(pt.artist_refusals([], [["GO 30", e + 5]], e), "MASTER_MARKER_NOT_RIPPLED"), "control: root marker")


@test
def t_segment_shift_gate():
    d = plan()["delta_ticks"]
    after = [dict(r, start=r["new_start"], end=r["new_end"]) for r in pt.predict_segments(MEASURED, "Passage 6", d)]
    after = [{"label": a["label"], "start": a["start"], "end": a["end"]} for a in after]
    check(pt.segment_shift_gate(MEASURED, after, "Passage 6", d) == [], "exact predicted shift passes")
    later = [r for r in pt.predict_segments(MEASURED, "Passage 6", d) if r["shift"]]
    check([r["label"] for r in later] == ["Scene 6 — External Sound", "Closing — Sweeping Up"],
          "downstream = Scene 6, Closing (%r)" % [r["label"] for r in later])
    for i, field, by, what in ((0, "end", 1, "earlier segment moved 1 tick"),
                               (16, "end", -1, "P06 end off by one"),
                               (16, "start", 960, "P06 start moved"),
                               (17, "start", 1, "later shift off by one"),
                               (18, "end", -d, "later end not shifted")):
        bad = copy.deepcopy(after)
        bad[i][field] += by
        check(refused(pt.segment_shift_gate(MEASURED, bad, "Passage 6", d), "SEGMENT_MOVED_WRONG"), "control: " + what)
    check(refused(pt.segment_shift_gate(MEASURED, after[:-1], "Passage 6", d), "SEGMENT_ORDER_CHANGED"),
          "control: segment set changed")


@test
def t_world_apply_and_gates():
    for later in (False, True):
        w = FakeWorld(later_passage=later)
        before = w.plain()
        seg = w.seg("Passage 6")
        p = pt.tail_plan(seg["start"], seg["end"], w.p06()["tail"], TICK, 25, 1, 125.0, 1.0, 16.0)
        check(pt.write_tail_checked(w, p["new_tail"], 600.0) == [], "tail write reads back")
        w.rebuild()
        after = w.plain()
        tag = " (later passage=%s)" % later
        check(pt.segment_shift_gate(before["segments"], after["segments"], "Passage 6", p["delta_ticks"]) == [],
              "segments gate" + tag)
        check(pt.managed_shift_gate(before["managed"], after["managed"], P06, p["old_start"], p["old_end"],
                                    p["delta_ticks"]) == [], "managed gate" + tag)
        check(pt.keys_gate(before["keys"], after["keys"], p["old_end"], p["delta_ticks"]) == [], "keys gate" + tag)
        check(after["segments"][-1]["end"] - before["segments"][-1]["end"] == p["delta_ticks"], "show end +delta" + tag)
        # failing controls
        bad = copy.deepcopy(after["managed"])
        bad["Choreo:" + P06][1] -= p["delta_ticks"]                          # Choreo section did not grow
        check(refused(pt.managed_shift_gate(before["managed"], bad, P06, p["old_start"], p["old_end"], p["delta_ticks"]),
                      "MANAGED_MOVED_WRONG"), "control: Choreo section not grown" + tag)
        bad = copy.deepcopy(after["managed"])
        bad["Playback:master"][1] -= pt.MASTER_ROUNDING_TICKS + 1     # beyond the measured 2-tick rebuild rounding (6 Oct)
        check(refused(pt.managed_shift_gate(before["managed"], bad, P06, p["old_start"], p["old_end"], p["delta_ticks"]),
                      "MANAGED_MOVED_WRONG"), "control: playback range" + tag)
        ok_round = copy.deepcopy(after["managed"])
        ok_round["Playback:master"][1] += 2                                # measured 6 Oct: rebuild rounding is accepted
        check(pt.managed_shift_gate(before["managed"], ok_round, P06, p["old_start"], p["old_end"], p["delta_ticks"]) == [],
              "rounding: +2 ticks on a boundary passes" + tag)
        b2 = copy.deepcopy(before["managed"]); a2 = copy.deepcopy(after["managed"])
        k = [x for x in b2 if x.startswith("Scene:") and int(b2[x][0]) >= p["old_end"]][0]
        b2[k] = [b2[k][0] - 2, b2[k][1] - 2]; a2[k] = [a2[k][0] - 2, a2[k][1] - 2]   # measured 6 Oct: Master 2 ticks early
        check(pt.managed_shift_gate(b2, a2, P06, p["old_start"], p["old_end"], p["delta_ticks"]) == [],
              "rounding: a later Scene starting 2 ticks before old_end is not a straddle" + tag)
        b3 = copy.deepcopy(b2); b3[k] = [b3[k][0] - 100, b3[k][1]]
        check(refused(pt.managed_shift_gate(b3, a2, P06, p["old_start"], p["old_end"], p["delta_ticks"]),
                      "MANAGED_STRADDLES_P06"), "control: 100 ticks early IS a straddle" + tag)
        bad = copy.deepcopy(after["managed"])
        bad["Scene:G-Passage 1"] = [1, 2]
        check(refused(pt.managed_shift_gate(before["managed"], bad, P06, p["old_start"], p["old_end"], p["delta_ticks"]),
                      "MANAGED_SET_CHANGED"), "control: new managed block" + tag)
        bad = copy.deepcopy(before["managed"])
        bad["Scene:straddle"] = [p["old_start"] - 50, p["old_start"] + 50]
        bad2 = dict(after["managed"], **{"Scene:straddle": [p["old_start"] - 50, p["old_start"] + 50]})
        check(refused(pt.managed_shift_gate(bad, bad2, P06, p["old_start"], p["old_end"], p["delta_ticks"]),
                      "MANAGED_STRADDLES_P06"), "control: straddling block" + tag)
        bad = copy.deepcopy(after["keys"])
        bad[P06]["channels"]["Camera.HeightOffsetCm"][0][0] += 1
        check(refused(pt.keys_gate(before["keys"], bad, p["old_end"], p["delta_ticks"]), "PASSAGE_KEYS_MOVED"),
              "control: P06 key moved" + tag)
        bad = copy.deepcopy(after["keys"])
        bad[P06]["pins_rel"] = []
        check(refused(pt.keys_gate(before["keys"], bad, p["old_end"], p["delta_ticks"]), "PASSAGE_PINS_CHANGED"),
              "control: pin dropped" + tag)
    # later Passage whose keys did NOT travel (patch K missing) must fail
    w = FakeWorld(later_passage=True)
    w.broken_move = True
    before = w.plain()
    seg = w.seg("Passage 6")
    p = pt.tail_plan(seg["start"], seg["end"], w.p06()["tail"], TICK, 25, 1, 125.0, 1.0, 16.0)
    w.write_tail(p["new_tail"])
    w.rebuild()
    check(refused(pt.keys_gate(before["keys"], w.plain()["keys"], p["old_end"], p["delta_ticks"]), "PASSAGE_KEYS_MOVED"),
          "control: later Passage keys stranded (no MoveSection)")
    # lying setter
    w = FakeWorld()
    w.lying_setter = True
    check(refused(pt.write_tail_checked(w, 999, 600.0), "READBACK_TAIL_FRAMES"), "control: setter lies")
    check(refused(pt.write_tail_checked(FakeWorld(), 999, 601.0), "READBACK_TAIL_DISTANCE_CHANGED"),
          "control: tail distance changed")


@test
def t_revert_exact():
    w = FakeWorld()
    before = w.plain()
    seg = w.seg("Passage 6")
    p = pt.tail_plan(seg["start"], seg["end"], w.p06()["tail"], TICK, 25, 1, 125.0, 1.0, 16.0)
    w.write_tail(p["new_tail"])
    w.rebuild()
    record = json.loads(json.dumps({"before": before, "after": w.plain(), "plan": p}))   # through the record file
    check(pt.drift_refusals(w.plain(), record) == [], "no drift right after APPLY")
    ok = copy.deepcopy(w)
    ok.write_tail(record["before"]["tail_frames"])
    ok.rebuild()
    check(pt.revert_exact_gate(ok.plain(), record) == [], "REVERT is tick-exact (segments, managed, keys, tail)")
    check(ok.plain() == before, "REVERT == before, whole state")
    bad = copy.deepcopy(w)
    bad.write_tail(record["before"]["tail_frames"] + 1)
    bad.rebuild()
    check(refused(pt.revert_exact_gate(bad.plain(), record), "REVERT_NOT_EXACT"), "control: revert one tick off")
    nr = copy.deepcopy(w)
    nr.write_tail(record["before"]["tail_frames"])
    check(refused(pt.revert_exact_gate(nr.plain(), record), "REVERT_NOT_EXACT: managed"), "control: revert w/o rebuild")
    dr = copy.deepcopy(w)
    dr.p06()["tail"] += 960
    dr.rebuild()
    check(refused(pt.drift_refusals(dr.plain(), record), "STATE_DRIFTED_SINCE_APPLY"), "control: edited after APPLY")
    dk = copy.deepcopy(w)
    dk.sections["Music:" + P06][1] += 1
    check(refused(pt.drift_refusals(dk.plain(), record), "STATE_DRIFTED_SINCE_APPLY: managed"), "control: Master drift")


@test
def t_live_and_misc_gates():
    base = {"mode": "APPLY", "confirm": "APPLY P06TAIL", "census": {"content": [], "maps": []}, "decided_by": "Gary"}
    check(pt.live_gates(base) == [], "clean APPLY state passes")
    for kw, token in ((dict(confirm="APPLY WALKING MUSIC"), "CONFIRM_MISMATCH"), (dict(pie=True), "PIE_OR_SIE_ACTIVE"),
                      (dict(sequencer_open=True), "SEQUENCER_IS_OPEN"),
                      (dict(census={"content": ["/Game/X"], "maps": []}), "DIRTY_CENSUS"),
                      (dict(record_exists=True), "RECORD_EXISTS"), (dict(decided_by=""), "NOT_DECIDED")):
        check(refused(pt.live_gates(dict(base, **kw)), token), "control live gate " + token)
    check(refused(pt.live_gates({"mode": "REVERT", "confirm": "REVERT P06TAIL", "census": {}}), "NO_APPLIED_RECORD"),
          "control: REVERT without record")
    check(pt.sync_gate({"A": [0.0, 1.0]}, {"A": [0.0, 1.04]}) == [], "sync within 0.05 s")
    check(refused(pt.sync_gate({"A": [0.0, 1.0]}, {"A": [0.0, 1.2]}), "MASTER_STALE"), "control: stale Master")
    check(pt.handoff_gate(["a"], ["a"]) == [], "no new stale handoff")
    check(refused(pt.handoff_gate(["a"], ["a", "b"]), "HANDOFF_NEWLY_STALE"), "control: new stale handoff")
    check(pt.census_gate({"content": [pt.SHOW_PATH]}, [pt.SHOW_PATH, pt.MASTER_PATH]) == [], "census subset")
    check(refused(pt.census_gate({"content": ["/Game/L"], "maps": []}, [pt.SHOW_PATH]), "UNEXPECTED_DIRTY"),
          "control: unexpected dirty")
    check(refused(pt.census_gate({"content": [], "maps": ["/Game/M"]}, [pt.SHOW_PATH]), "MAP_DIRTY"), "control: map")
    check(pt.unwrap((True, "rep"), 1) == ("rep",) and pt.unwrap(None, 1) is None and pt.unwrap("rep", 1) == ("rep",),
          "unwrap shapes")
    p = os.path.join(HERE, "_p06_tail_extend_harness_record.tmp")
    try:
        pt.write_record_exclusive(p, {"a": 1})
        try:
            pt.write_record_exclusive(p, {"a": 2})
            check(False, "control: exclusive record must refuse an existing file")
        except FileExistsError:
            check(True, "exclusive record refuses an existing file")
    finally:
        if os.path.exists(p):
            os.remove(p)
    src = open(TOOL_PATH, encoding="utf-8").read()
    check(src.rstrip().endswith("if unreal is not None:\n    main()"), "main gated on unreal")
    check("save_all" not in src and "save_current_level" not in src and "materialize" not in src.replace(
        "materialisation", "").replace("materialise", ""), "no Save All / level save / materialise call")
    check("run_path" not in src and "exec(" not in src and "subprocess" not in src,
          "never runs another script (the guarded rebuild mis-pairs Choreo sub-tracks)")


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:   # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    p = plan()
    print("PLAN 25 fps: old %d ticks (%.6f s) -> new %d (%.6f s); delta %d ticks = %d frames = %.6f s; tail %d -> %d"
          % (p["old_len"], p["old_len_s"], p["new_len"], p["new_len_s"], p["delta_ticks"], p["delta_frames"],
             p["delta_s"], p["old_tail"], p["new_tail"]))
    for r in pt.predict_segments(MEASURED, "Passage 6", p["delta_ticks"])[-3:]:
        print("SEG %-30s start %d -> %d  end %d -> %d" % (r["label"], r["start"], r["new_start"], r["end"], r["new_end"]))
    for f in CHECKS["failed"]:
        print("FAIL: " + f)
    print("P06_TAIL_EXTEND_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
