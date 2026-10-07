"""Offline harness for passage_retime_to_music.py (system Python, no Unreal). Every gate has a failing control.

Fixture data, cited (the live DRY re-reads all of it):
  Compiled segments (ticks, 24000/s): walking_music_swap_dry.json "segments", run WALK-20261005-144953 [meas 5 Oct].
  P02/P03/P04 timing (lead, intervals, tail) and distances: passage_slow_walk_P0{2,3,4}_latest.json plan +
    protected_before, APPLY 2 Oct [meas]; their sums equal the 180 s segments above (asserted below).
  P05: only its length (4472727 ticks = 186.363625 s) is measured; its lead/interval/tail split and distances are
    INVENTED here (marked); the live DRY reads the real ones.
  Songs: walking_music_swap_record_P02-P03-P04-P05.json (import duration_s, rail_after) [meas].
  Display rate 25 fps = Show default [decl InfinityStageShowAsset.cpp:86, as p06_tail_extend.py:16].
Run: python test_passage_retime_to_music.py -> PASSAGE_RETIME_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rt = _load("passage_retime_to_music")
assert rt.unreal is None, "harness must run without Unreal"
wms = _load("walking_music_swap")          # guarded import: main() does not run without unreal
assert wms.unreal is None
psw = _load("passage_slow_walk")           # imports unreal only inside run_unreal

with open(os.path.join(HERE, "passage_retime_to_music_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
with open(os.path.join(HERE, "walking_music_swap_dry.json"), encoding="utf-8") as _h:
    SEGMENTS = json.load(_h)["segments"]
SEGMENTS = [{"label": s["label"], "start": int(s["start"]), "end": int(s["end"])} for s in SEGMENTS]

TICK = 24000
FPS = (25, 1)
GUID = {k: ARGS["per_passage"][k]["guid"] for k in ("2", "3", "4", "5")}
GUID["6"] = "9BFC29C45D47911FF7836BB8537230D2"
GUID["1"] = "P01GUID"


def _slow(short):
    with open(os.path.join(HERE, "passage_slow_walk_%s_latest.json" % short), encoding="utf-8") as h:
        r = json.load(h)
    p, pr = r["plan"], r["protected_before"]
    return {"lead": p["lead_frames"], "intervals": p["intervals"], "tail": p["tail_frames"],
            "lead_cm": pr["lead_in_distance_cm"], "gaps": pr["gap_to_next_cm"], "tail_cm": pr["tail_distance_cm"],
            "slow_new_speed": r["new_speed_cm_s"], "slow_route": r["route_cm"]}


FIX = {"2": _slow("P02"), "3": _slow("P03"), "4": _slow("P04"),
       # P05 INVENTED split summing to the measured 4472727 ticks: 21 pairs, uniform walk (lead/tail at bay speed).
       "5": {"lead": 105000, "intervals": [210000] * 21, "tail": 4472727 - 105000 - 20 * 210000,
             "lead_cm": 250.0, "gaps": [500.0] * 21, "tail_cm": (4472727 - 105000 - 20 * 210000) / 420.0}}
with open(os.path.join(HERE, "walking_music_swap_record_P02-P03-P04-P05.json"), encoding="utf-8") as _h:
    WREC = json.load(_h)
RAIL = {k: dict(WREC["passages"][k]["rail_after"], mode="<InfinityMusicBindingMode.START: 0>", offset=0)
        for k in ("2", "3", "4", "5")}

CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def raises(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except (rt.PlanError, ValueError):
        return True
    return False


def seg(label):
    return [s for s in SEGMENTS if s["label"] == label][0]


def live_for(key, **over):
    f = FIX[key]
    live = {"lead": f["lead"], "intervals": list(f["intervals"]), "tail": f["tail"], "lead_cm": f["lead_cm"],
            "gaps": list(f["gaps"]), "tail_cm": f["tail_cm"], "segment": dict(seg(rt.label_of(key))),
            "music": dict(RAIL[key]), "channels": {"Camera.SpeedMultiplier": [[seg(rt.label_of(key))["start"], 1.0]]},
            "pins_rel": [], "origins": [["c%d" % i, "InfinityMotionPhaseOrigin.PASSAGE_START"] for i in range(3)],
            "choreo": {"path": "/Game/Choreo/P%s" % key, "start_offset": 0, "keys": [], "sections": [],
                       "markers": [["bar 1", 0], ["bar 2", 48000]], "camera_cut": False},
            "settle_s": 1.0, "celestial": {"animate": True, "cycle_s": 20.0, "rate": 1.0}}
    live.update(over)
    return live


def args_with(**over):
    a = copy.deepcopy(ARGS)
    a.update(over)
    return a


# ---------------------------------------------------------------------------------------------------------------------
@test
def t_fixture_consistency():
    for k in ("2", "3", "4", "5"):
        f = FIX[k]
        s = seg(rt.label_of(k))
        check(rt.compiled_length(f["lead"], f["intervals"], f["tail"]) == s["end"] - s["start"],
              "fixture P%s sums to its measured segment" % k)


@test
def t_validate_args():
    check(rt.validate_args(ARGS) == [], "shipped args valid: %r" % rt.validate_args(ARGS))
    # 7 Oct: the shipped args file is edited between runs (it held ["3", "4"] after RETIME-20261006-014626), so the old
    # "== P02-P05" check failed on a correct file; check a valid non-empty subset instead.
    check(bool(ARGS["passages"]) and set(ARGS["passages"]) <= set(rt.VALID_KEYS), "shipped passages a valid subset")
    check(any("MODE" in x for x in rt.validate_args(args_with(mode="GO"))), "control: bad mode")
    check(any("PASSAGES" in x for x in rt.validate_args(args_with(passages=["6"]))), "control: P06 refused")
    check(any("PASSAGES" in x for x in rt.validate_args(args_with(passages=["2", "2"]))), "control: repeat")
    check(any("PASSAGES" in x for x in rt.validate_args(args_with(passages=[]))), "control: empty")
    check(any("TAIL" in x for x in rt.validate_args(args_with(tail_s=-1))), "control: negative tail")
    a = args_with(mode="APPLY", passages=["2", "3", "4", "5"])
    for k in a["passages"]:
        a["per_passage"][k]["expected"] = None
    check(any("EXPECTED_OLD_LEN" in x for x in rt.validate_args(a)), "control: APPLY without DRY numbers")
    a = args_with(mode="APPLY")
    for k in a["passages"]:
        a["per_passage"][k]["expected"] = {"old_len_ticks": 1, "new_len_ticks": 2}
    check(rt.validate_args(a) == [], "APPLY with expected numbers valid")
    a = args_with()
    a["per_passage"]["3"]["guid"] = ""
    check(any("GUID_MISSING" in x for x in rt.validate_args(a)), "control: guid missing")


@test
def t_target_ticks():
    t = rt.target_ticks(45.51424, 2.0, TICK, *FPS)
    check(t % 960 == 0, "target on a display frame")
    check(t >= 47.51424 * TICK and t - 47.51424 * TICK < 960, "target is the next display frame up: %d" % t)
    check(rt.target_ticks(1.0, 0.0, TICK, *FPS) == 24000, "exact second stays exact")
    check(raises(rt.target_ticks, 1.0, 0.0, TICK, 7, 1), "control: 24000/7 ticks per frame refused")
    check(rt.target_ticks(1.0, 0.0, TICK, 24000, 1001) % 1001 == 0, "23.976 fps: 1001-tick frames")


@test
def t_plan_matches_slow_walk_and_record():
    for k in ("2", "3", "4", "5"):
        f = FIX[k]
        tgt = rt.target_ticks(WREC["passages"][k]["import"]["duration_s"], 2.0, TICK, *FPS)
        mine = rt.plan_scaled_timing(f["lead"], f["intervals"], f["tail"], tgt)
        theirs = psw.plan_scaled_timing(f["lead"], f["intervals"], f["tail"], tgt)
        check(all(mine[x] == theirs[x] for x in ("lead_frames", "intervals", "tail_frames", "new_ticks")),
              "P%s plan == passage_slow_walk.plan_scaled_timing" % k)
        check(mine["new_ticks"] == tgt and rt.compiled_length(mine["lead_frames"], mine["intervals"],
                                                              mine["tail_frames"]) == tgt, "P%s exact" % k)
    # The 2 Oct slow walk, replayed from its own record, gives the 180 s values it wrote [meas anchor].
    with open(os.path.join(HERE, "passage_slow_walk_record_P02.json"), encoding="utf-8") as h:
        rec = json.load(h)
    b, a = rec["before"], rec["after"]
    p = rt.plan_scaled_timing(b["lead_frames"], b["intervals"], b["tail_frames"], 180 * TICK)
    check([p["lead_frames"], p["intervals"], p["tail_frames"]] == [a["lead_frames"], a["intervals"], a["tail_frames"]],
          "replays the recorded 2 Oct P02 slow walk exactly")
    check(raises(rt.plan_scaled_timing, 1, [1, 1], 0, 1), "control: residual makes tail negative")
    check(raises(rt.plan_scaled_timing, 10, [], 10, 100), "control: no wing pairs")


@test
def t_settle_compensation():
    f = FIX["2"]
    tgt = rt.target_ticks(ARGS["per_passage"]["2"]["song_s"], 2.0, TICK, *FPS)
    comp = rt.settle_compensation_ticks(1.0, TICK)
    plain = rt.plan_scaled_timing(f["lead"], f["intervals"], f["tail"], tgt)
    comp_plan = rt.add_settle_compensation(rt.plan_scaled_timing(f["lead"], f["intervals"], f["tail"], tgt - comp), comp)
    check(comp_plan["new_ticks"] == plain["new_ticks"] == tgt, "same total either way")
    sp = rt.speeds(plain["lead_frames"], plain["intervals"], plain["tail_frames"], f["lead_cm"], f["gaps"],
                   f["tail_cm"], TICK, 1.0)
    sc = rt.speeds(comp_plan["lead_frames"], comp_plan["intervals"], comp_plan["tail_frames"], f["lead_cm"], f["gaps"],
                   f["tail_cm"], TICK, 1.0)
    check(abs(sc["tail_pre_settle"] - sc["bay_max"]) < 1.0, "compensated: no surge before the settle (%.2f vs %.2f)" % (
        sc["tail_pre_settle"], sc["bay_max"]))
    check(sp["tail_pre_settle"] > 1.2 * sp["bay_max"], "control: uncompensated surges >20%% (%.2f vs %.2f)" % (
        sp["tail_pre_settle"], sp["bay_max"]))
    row, r, _ = rt.plan_passage("2", live_for("2"), TICK, FPS, args_with())
    check(row["plan"]["settle_compensation_ticks"] == 12000 and r == [], "plan_passage compensates by default")
    row0, _r, _ = rt.plan_passage("2", live_for("2"), TICK, FPS, args_with(settle_compensation=False))
    check(row0["plan"]["settle_compensation_ticks"] == 0, "control: compensation can be switched off")
    check(row0["plan"]["new_ticks"] == row["plan"]["new_ticks"], "switching it off keeps the length")


@test
def t_speeds():
    f = FIX["2"]
    v = rt.speeds(f["lead"], f["intervals"], f["tail"], f["lead_cm"], f["gaps"], f["tail_cm"], TICK, 0.0)
    check(abs(v["mean"] - f["slow_new_speed"]) < 1e-3, "P02 mean == slow-walk report %.4f vs %.4f" % (
        v["mean"], f["slow_new_speed"]))
    check(abs(v["route_cm"] - f["slow_route"]) < 1e-3, "P02 route == slow-walk route")
    check(abs(v["bay_min"] - v["bay_max"]) < 0.01 and abs(v["tail"] - v["mean"]) < 0.01, "P02 walk is uniform")
    vs = rt.speeds(f["lead"], f["intervals"], f["tail"], f["lead_cm"], f["gaps"], f["tail_cm"], TICK, 1.0)
    check(vs["tail_pre_settle"] > vs["tail"], "settle makes the tail faster before the window")
    check(vs["tail_pre_settle"] != v["tail_pre_settle"], "control: settle changes the pre-settle speed")


@test
def t_fit_is_verbatim():
    for p in (10.0, 45.5, 47.52, 180.0):
        for s in (5.0, 45.51424, 47.0, 200.0):
            for fo in (0.0, 1.0, 3.0):
                for off in (0.0, 0.5):
                    check(rt.fit(p, s, 0.0, off, 1.0, fo) == wms.fit(p, s, 0.0, off, 1.0, fo),
                          "fit copy == walking_music_swap.fit (%s %s %s %s)" % (p, s, fo, off))
    for text in ('(Sound=/Game/A/B.B,X=1)', '(Sound="/Script/Engine.SoundWave\'/Game/A/B.B\'")', '(Sound=None)'):
        check(rt.soft_path_from_export(text, "Sound") == wms.soft_path_from_export(text, "Sound"),
              "soft_path_from_export copy == original: %s" % text)


@test
def t_music_refusals():
    k = "2"
    song = ARGS["per_passage"][k]["song_s"]
    m = dict(RAIL[k], args_sound=ARGS["per_passage"][k]["sound"])
    tgt = rt.target_ticks(song, 2.0, TICK, *FPS)
    r, row = rt.music_refusals(k, m, tgt, TICK, song)
    check(r == [] and "ends naturally" in row["fade_out"], "P02 song fits and ends before the fade: %r" % r)
    r, _ = rt.music_refusals(k, m, rt.target_ticks(song, 0.5, TICK, *FPS), TICK, song)
    check(any("INSIDE_FADE_OUT" in x for x in r), "control: tail 0.5 s puts the song in the fade-out")
    r, _ = rt.music_refusals(k, m, int((song - 1.0) * TICK), TICK, song)
    check(any("OVERRUNS" in x for x in r), "control: Passage shorter than the song")
    r, _ = rt.music_refusals(k, dict(m, args_sound="/Game/Other"), tgt, TICK, song)
    check(any("SOUND_CHANGED" in x for x in r), "control: sound changed")
    r, _ = rt.music_refusals(k, m, tgt, TICK, song + 0.1)
    check(any("SONG_LENGTH_MISMATCH" in x for x in r), "control: args song length differs from the rail")
    r, _ = rt.music_refusals(k, dict(m, mode="<InfinityMusicBindingMode.SILENCE: 2>"), tgt, TICK, song)
    check(any("NOT_PLAYING" in x for x in r), "control: Silence mode")
    r, _ = rt.music_refusals(k, dict(m, source_out=0), tgt, TICK, song)
    check(any("SOURCE_OUT_UNSET" in x for x in r), "control: no source out")
    for kk in ("3", "4", "5"):
        mm = dict(RAIL[kk], args_sound=ARGS["per_passage"][kk]["sound"])
        s = ARGS["per_passage"][kk]["song_s"]
        r, _ = rt.music_refusals(kk, mm, rt.target_ticks(s, 2.0, TICK, *FPS), TICK, s)
        check(r == [], "P%s rail length == args song_s and fits: %r" % (kk, r))


@test
def t_channel_pin_mechanism():
    r, notes = rt.channel_refusals("2", {"Camera.SpeedMultiplier": [[5, 1.0], [900, 1.0]]}, 0, 1000)
    check(r == [] and notes, "constant channel allowed (noted)")
    r, _ = rt.channel_refusals("2", {"Camera.HeightOffsetCm": [[5, 0.0], [900, 20.0]]}, 0, 1000)
    check(r and "TIME_KEYED_CHANNEL" in r[0], "control: differing values refused")
    r, _ = rt.channel_refusals("2", {"Camera.SpeedMultiplier": [[5, 1.0], [900, 0.5]]}, 0, 1000)
    check(r, "control: varying SpeedMultiplier refused")
    check(rt.pin_refusals("2", []) == [], "no pins ok")
    check(rt.pin_refusals("2", [24000]), "control: relative pin refused")
    check(rt.mechanism_refusals("2", [["a", "InfinityMotionPhaseOrigin.PASS_FRAME"]]) == [], "PassFrame ok")
    check(rt.mechanism_refusals("2", [["a", "InfinityMotionPhaseOrigin.EXPLICIT_FRAME"]]),
          "control: ExplicitFrame refused")


@test
def t_choreo():
    c = {"start_offset": 0, "keys": [["root/x", 100]], "sections": [], "markers": [["bar 1", 10]], "camera_cut": False}
    r, w = rt.choreo_refusals("2", c, 1000)
    check(r == [] and any("STAY_WITH_THE_SONG" in x for x in w), "keys inside: warning only")
    r, w = rt.choreo_refusals("2", dict(c, markers=[["bar 90", 5000]]), 1000)
    check(any("SONG_MARKER_PAST_NEW_END" in x for x in r), "control: stale song marker refused by default")
    r, w = rt.choreo_refusals("2", dict(c, markers=[["bar 90", 5000]]), 1000, allow_stale_song_markers=True)
    check(r == [] and w, "stale song marker allowed with the flag (warning)")
    r, _ = rt.choreo_refusals("2", dict(c, markers=[["GO 12 crossing", 5000]]), 1000)
    check(any("CHOREO_MARKER_PAST_NEW_END" in x for x in r), "control: GO marker past end refused")
    r, _ = rt.choreo_refusals("2", dict(c, keys=[["root/x", 1000]]), 1000)
    check(any("KEY_PAST_NEW_END" in x for x in r), "control: key at the new end refused")
    r, _ = rt.choreo_refusals("2", dict(c, sections=[{"where": "s", "start": 1200, "end": None, "keyed": False}]), 1000)
    check(any("STARTS_PAST_NEW_END" in x for x in r), "control: section starting past the end refused")
    r, w = rt.choreo_refusals("2", dict(c, sections=[{"where": "s", "start": 0, "end": 5000, "keyed": True}]), 1000)
    check(r == [] and any("TRUNCATED" in x for x in w), "overlapping section: truncation warning")
    check(rt.choreo_refusals("2", None, 1000) == ([], []), "no Choreo: nothing")


def _deltas(keys, tail=2.0):
    out = {}
    for k in keys:
        f = FIX[k]
        tgt = rt.target_ticks(ARGS["per_passage"][k]["song_s"], tail, TICK, *FPS)
        comp = rt.settle_compensation_ticks(1.0, TICK)
        out[rt.label_of(k)] = rt.add_settle_compensation(
            rt.plan_scaled_timing(f["lead"], f["intervals"], f["tail"], tgt - comp), comp)["delta_ticks"]
    return out


def _apply(segments, deltas):
    return [{"label": r["label"], "start": r["new_start"], "end": r["new_end"]}
            for r in rt.predict_segments(segments, deltas)]


@test
def t_downstream_maths_one_run_and_split():
    d_all = _deltas(["2", "3", "4", "5"])
    one = _apply(SEGMENTS, d_all)
    split = _apply(_apply(SEGMENTS, _deltas(["3", "4", "5"])), _deltas(["2"]))
    check(one == split, "P03-P05 then P02 == all four in one run, tick-exact")
    other = _apply(_apply(SEGMENTS, _deltas(["2"])), _deltas(["3", "4", "5"]))
    check(one == other, "P02 then P03-P05 == one run")
    net = sum(d_all.values())
    p6 = [s for s in one if s["label"] == "Passage 6"][0]
    check(p6["start"] == seg("Passage 6")["start"] + net, "P06 moves by the net delta")
    check(p6["end"] - p6["start"] == seg("Passage 6")["end"] - seg("Passage 6")["start"], "P06 length unchanged")
    check([s for s in one if s["label"] == "Passage 1"][0] == seg("Passage 1"), "P01 untouched")
    for i in range(1, len(one)):
        check(one[i]["start"] == one[i - 1]["end"], "contiguous after retime at %d" % i)
    for k in ("2", "3", "4", "5"):
        s = [x for x in one if x["label"] == rt.label_of(k)][0]
        check(s["end"] - s["start"] == seg(rt.label_of(k))["end"] - seg(rt.label_of(k))["start"]
              + d_all[rt.label_of(k)], "P%s new length" % k)
    check(raises(rt.predict_segments, SEGMENTS, {"Passage 9": 5}), "control: unknown label refused")
    check(rt.segment_shift_gate(SEGMENTS, one, d_all) == [], "segment gate passes the predicted result")
    bad = copy.deepcopy(one)
    bad[-1]["end"] += 1
    check(rt.segment_shift_gate(SEGMENTS, bad, d_all), "control: one tick off fails")
    check(rt.segment_shift_gate(SEGMENTS, SEGMENTS, d_all), "control: no rebuild fails")


def _managed(segments):
    out = {"Playback:master": [0, segments[-1]["end"]]}
    for s in segments:
        key = s["label"].replace(" ", "_")
        if s["label"].startswith("Passage"):
            g = GUID[s["label"][-1]]
            out["Passage:" + g] = [s["start"], s["end"]]
            out["Music:" + g] = [s["start"], s["end"]]
            if s["label"] != "Passage 1":
                out["Choreo:" + g] = [s["start"], s["end"]]
        else:
            out["Scene:" + key] = [s["start"], s["end"]]
    return out


@test
def t_managed_and_keys_gates():
    d = _deltas(["2", "3", "4", "5"])
    after = _apply(SEGMENTS, d)
    spans = rt.retimed_spans(SEGMENTS, d)
    check(rt.managed_shift_gate(_managed(SEGMENTS), _managed(after), spans) == [], "managed gate passes")
    bad = _managed(after)
    bad["Choreo:" + GUID["6"]][0] += 960
    check(rt.managed_shift_gate(_managed(SEGMENTS), bad, spans), "control: misplaced Choreo fails")
    strad = _managed(SEGMENTS)
    p2 = seg("Passage 2")
    strad["Music:extra"] = [p2["start"] + 100, p2["end"]]
    strad_after = _managed(after)
    strad_after["Music:extra"] = [p2["start"] + 100, p2["end"]]
    check(any("STRADDLES" in x for x in rt.managed_shift_gate(strad, strad_after, spans)),
          "control: a section starting inside a retimed Passage fails")
    miss = _managed(after)
    miss.pop("Music:" + GUID["3"])
    check(any("MANAGED_SET_CHANGED" in x for x in rt.managed_shift_gate(_managed(SEGMENTS), miss, spans)),
          "control: a vanished section fails")
    net = sum(d.values())
    kb = {GUID["6"]: {"start": seg("Passage 6")["start"], "channels": {"Camera.SpeedMultiplier":
                                                                         [[seg("Passage 6")["start"] + 5, 1.0]]},
                      "pins_rel": [], "wing_pins": []},
          GUID["3"]: {"start": seg("Passage 3")["start"], "channels": {"Camera.FocalLengthMm":
                                                                         [[seg("Passage 3")["start"], 35.0]]},
                      "pins_rel": [], "wing_pins": ["w"]}}
    ka = copy.deepcopy(kb)
    ka[GUID["6"]]["channels"]["Camera.SpeedMultiplier"][0][0] += net
    ka[GUID["3"]]["channels"]["Camera.FocalLengthMm"][0][0] += d["Passage 2"]
    check(rt.keys_gate(kb, ka, spans) == [], "keys travel with their section start (P03 by P02's delta, P06 by net)")
    check(rt.keys_gate(kb, kb, spans), "control: keys left behind fail")
    kp = copy.deepcopy(ka)
    kp[GUID["3"]]["pins_rel"] = [5]
    check(rt.keys_gate(kb, kp, spans), "control: pins changed fail")


@test
def t_shift_at():
    spans = [(100, 200, -50), (300, 400, -10)]
    check(rt.shift_at(100, spans) == 0 and rt.shift_at(200, spans) == -50, "own start 0, own end includes delta")
    check(rt.shift_at(300, spans) == -50 and rt.shift_at(400, spans) == -60, "later boundaries accumulate")
    check(rt.shift_at(150, spans) is None, "control: inside a retimed span is None")


@test
def t_artist():
    end = SEGMENTS[-1]["end"]
    t0 = seg("Passage 2")["start"]
    r, w = rt.artist_refusals([{"owner": "root", "track": "Cuts", "class": "MovieSceneCameraCutTrack",
                                "sections": [[0, end]], "keys": []}], [], t0, end, -1000)
    check(r == [] and w, "whole-show cut track on a shrink: warning only")
    r, _ = rt.artist_refusals([{"owner": "root", "track": "Cuts", "class": "MovieSceneCameraCutTrack",
                                "sections": [[0, end]], "keys": []}], [], t0, end, +1000)
    check(r, "control: whole-show section on a growth refused")
    r, _ = rt.artist_refusals([{"owner": "root", "track": "L", "class": "X", "sections": [[0, t0 + 5]], "keys": []}],
                              [], t0, end, -1000)
    check(any("STRADDLES" in x for x in r), "control: section ending mid-show refused")
    r, _ = rt.artist_refusals([{"owner": "root", "track": "L", "class": "X", "sections": [[0, None]],
                                "keys": [t0 + 10]}], [], t0, end, -1000)
    check(any("KEYS_NOT_RIPPLED" in x for x in r), "control: key after the earliest start refused")
    r, _ = rt.artist_refusals([{"owner": "root", "track": "L", "class": "X", "sections": [[0, t0]], "keys": [5]}],
                              [["cue", t0 - 1]], t0, end, -1000)
    check(r == [], "content wholly before the retime is fine")
    r, _ = rt.artist_refusals([], [["note", t0]], t0, end, -1000)
    check(r, "control: marker at the earliest start refused")


@test
def t_plan_passage():
    a = args_with()
    for k in ("2", "3", "4", "5"):
        row, r, w = rt.plan_passage(k, live_for(k), TICK, FPS, a)
        check(r == [], "P%s plans clean: %r" % (k, r))
        check(row["plan"]["new_ticks"] % 960 == 0, "P%s new length on a display frame" % k)
        check(row["fit_after"]["fits"], "P%s song fits" % k)
    row, r, _ = rt.plan_passage("2", live_for("2"), TICK, FPS, args_with(max_speed_cm_s=100.0))
    check(any("TOO_FAST" in x for x in r), "control: speed ceiling")
    bad_seg = dict(seg("Passage 2"), end=seg("Passage 2")["end"] + 1)
    _row, r, _ = rt.plan_passage("2", live_for("2", segment=bad_seg), TICK, FPS, a)
    check(any("COMPILE_MODEL_MISMATCH" in x for x in r), "control: compile model mismatch")
    _row, r, _ = rt.plan_passage("2", live_for("2", settle_s=6.0), TICK, FPS, a)
    check(any("TAIL_SHORTER_THAN_SETTLE" in x for x in r), "control: settle longer than the new tail")
    _row, r, _ = rt.plan_passage("2", live_for("2", pins_rel=[48000]), TICK, FPS, a)
    check(any("RELATIVE_PIN" in x for x in r), "control: pins refused through plan_passage")
    ap = args_with(mode="APPLY")
    ap["per_passage"]["2"]["expected"] = {"old_len_ticks": row["plan"]["old_ticks"],
                                          "new_len_ticks": row["plan"]["new_ticks"],
                                          "route_cm": row["speeds_old"]["route_cm"]}
    _row, r, _ = rt.plan_passage("2", live_for("2"), TICK, FPS, ap)
    check(r == [], "APPLY with matching DRY numbers: %r" % r)
    ap["per_passage"]["2"]["expected"]["old_len_ticks"] += 1
    _row, r, _ = rt.plan_passage("2", live_for("2"), TICK, FPS, ap)
    check(any("OLD_LENGTH_CHANGED" in x for x in r), "control: straightened/changed since the DRY")
    ap["per_passage"]["2"]["expected"] = {"old_len_ticks": row["plan"]["old_ticks"],
                                          "new_len_ticks": row["plan"]["new_ticks"], "route_cm": 1.0}
    _row, r, _ = rt.plan_passage("2", live_for("2"), TICK, FPS, ap)
    check(any("ROUTE_CHANGED" in x for x in r), "control: route distance changed since the DRY")


@test
def t_live_gates_records():
    ok = {"mode": "APPLY", "confirm": "APPLY RETIME", "census": {}, "decided_by": "Gary 5 Oct", "passages": ["2"]}
    check(rt.live_gates(ok) == [], "clean APPLY state passes")
    for field, val, what in (("confirm", "APPLY P06TAIL", "CONFIRM"), ("pie", True, "PIE"),
                             ("sequencer_open", True, "SEQUENCER"), ("census", {"maps": ["/Game/M"]}, "DIRTY"),
                             ("decided_by", "", "NOT_DECIDED"), ("covering_records", ["x.json"], "ALREADY"),
                             ("record_exists", True, "RECORD_EXISTS"),
                             ("prerequisites_missing", ["P2 needs x"], "PREREQUISITE")):
        st = dict(ok)
        st[field] = val
        check(any(what in x for x in rt.live_gates(st)), "control: %s" % field)
    check(any("NO_APPLIED_RECORD" in x for x in rt.live_gates({"mode": "REVERT", "confirm": "REVERT RETIME"})),
          "control: REVERT without record")
    check(rt.record_name(["5", "3", "4"]) == "passage_retime_to_music_record_P03-P04-P05.json", "record name")
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, rt.record_name(["3", "4", "5"])), "w", encoding="utf-8") as h:
            json.dump({"applied": True, "passages": ["3", "4", "5"]}, h)
        with open(os.path.join(tmp, rt.record_name(["2"]) + ".reverted-X"), "w", encoding="utf-8") as h:
            json.dump({"applied": True, "passages": ["2"]}, h)
        check(rt.records_covering(tmp, ["2"]) == [], "reverted record does not cover")
        check(rt.records_covering(tmp, ["4"]) == [rt.record_name(["3", "4", "5"])], "control: applied record covers")
        check(rt.prerequisites_missing(tmp, ["2", "3"], {"2": "p02_straighten_record.json"}),
              "control: P02 straighten missing")
        with open(os.path.join(tmp, "p02_straighten_record.json"), "w", encoding="utf-8") as h:
            json.dump({"applied": True}, h)
        check(rt.prerequisites_missing(tmp, ["2", "3"], {"2": "p02_straighten_record.json"}) == [],
              "P02 straighten applied: ok")
        check(rt.prerequisites_missing(tmp, ["3"], {"2": "nope.json"}) == [], "prerequisite only for listed passages")
        p = os.path.join(tmp, "rec.json")
        rt.write_record_exclusive(p, {"a": 1})
        check(raises_os(rt.write_record_exclusive, p, {"a": 2}), "control: record is create-only")
    finally:
        shutil.rmtree(tmp)


def raises_os(fn, *a):
    try:
        fn(*a)
    except OSError:
        return True
    return False


@test
def t_drift_revert_census_handoff():
    rec = {"before": {"timing": {"2": 1}, "segments": [1], "managed": {"a": 1}, "keys": {}},
           "after": {"timing": {"2": 2}, "segments": [2], "managed": {"a": 2}, "keys": {}}}
    check(rt.drift_refusals(rec["after"], rec) == [], "no drift")
    check(rt.drift_refusals(dict(rec["after"], segments=[3]), rec), "control: segments drifted (later tool ran)")
    check(rt.revert_exact_gate(rec["before"], rec) == [], "exact revert")
    check(rt.revert_exact_gate(dict(rec["before"], keys={"x": 1}), rec), "control: keys not restored")
    check(rt.census_gate({"content": [rt.SHOW_PATH, rt.MASTER_PATH]}, [rt.SHOW_PATH, rt.MASTER_PATH]) == [],
          "Show+Master dirty allowed")
    check(rt.census_gate({"content": ["/Game/Choreo/X"]}, [rt.SHOW_PATH, rt.MASTER_PATH]), "control: Choreo dirty")
    check(rt.census_gate({"content": [], "maps": ["/Game/M"]}, [rt.SHOW_PATH]), "control: map dirty")
    check(rt.handoff_gate(["a"], ["a"]) == [] and rt.handoff_gate([], ["b"]), "handoff gate + control")
    check(rt.protected_diff({"a": 1}, {"a": 1}) == [] and rt.protected_diff({"a": 1}, {"a": 2}) == ["a"],
          "protected diff + control")
    check(rt.sync_gate({"S": [0, 1]}, {"S": [0, 1]}) == [] and rt.sync_gate({"S": [0, 1]}, {"S": [0, 2]}),
          "sync gate + control")
    check(rt.unwrap((True, "x"), 1) == ("x",) and rt.unwrap((False, "x"), 1) is None and rt.unwrap(None, 1) is None,
          "unwrap")


# ---------------------------------------------------------------------------------------------------------------------
# P01 (key "1", added 7 Oct with p01_shorten.py). INFERRED fixture - the live DRY reads the real values:
#   segment 2312640..4624705 (2312065 ticks = 96.336 s) [meas walking_music_swap_record_P01.json segments_before];
#   48 pairs at 48000 ticks / 600 cm [inf: 300.0 cm/s measured between PSTILLS-P01-20261005-070532 stills at 9.634 s and
#   86.702 s; 600 cm = p456_baseline_plan.json p01_spacing]; lead 19008 ticks / 198 cm [inf: ~250 cm/s at the P01 start,
#   opening_walkin_probe.json next_frame_pose 10 cm in 1/25 s, + the stills' intercept]; tail closes the measured length
#   and the measured route 28784.0135 cm [meas probe_routes.json, hangar_s1_record.json dock].
P01_SEG = {"label": "Passage 1", "start": 2312640, "end": 4624705}
P01_FIX = {"lead": 19008, "intervals": [48000] * 48, "tail": 2312065 - 19008 - 47 * 48000,
           "lead_cm": 198.0, "gaps": [600.0] * 48, "tail_cm": 28784.0135 - 198.0 - 47 * 600.0}
with open(os.path.join(HERE, "walking_music_swap_record_P01.json"), encoding="utf-8") as _h:
    P01_RAIL = dict(json.load(_h)["passages"]["1"]["rail_after"], mode="<InfinityMusicBindingMode.START: 0>", offset=0)
P01_PER = {"guid": "659D5386D64DA7742A351B9499ECCE4C", "song_s": 73.516032, "expected": None,
           "sound": "/Game/InfinityStage/Audio/PassageMusic/Cameron_20261005/SW_P01_Walking1_Cameron"}


def p01_live(drop=6, **over):
    kept = 48 - drop
    f = P01_FIX
    length = rt.compiled_length(f["lead"], f["intervals"][:kept], f["tail"])
    live = {"lead": f["lead"], "intervals": f["intervals"][:kept], "tail": f["tail"], "lead_cm": f["lead_cm"],
            "gaps": f["gaps"][:kept], "tail_cm": f["tail_cm"],
            "segment": {"label": "Passage 1", "start": P01_SEG["start"], "end": P01_SEG["start"] + length},
            "music": dict(P01_RAIL), "channels": {}, "pins_rel": [], "origins": [], "choreo": None, "settle_s": 1.0,
            "celestial": None}
    live.update(over)
    return live


def p01_args(**over):
    a = args_with(passages=["1"])
    a["per_passage"]["1"] = dict(P01_PER)
    a.update(over)
    return a


@test
def t_p01_key_and_fixture():
    check("1" in rt.VALID_KEYS and rt.label_of("1") == "Passage 1", "P01 key accepted, label Passage 1")
    check(rt.validate_args(p01_args()) == [], "P01-only args valid: %r" % rt.validate_args(p01_args()))
    check(any("PASSAGES" in x for x in rt.validate_args(args_with(passages=["0"]))), "control: key 0 refused")
    check(any("PASSAGES" in x for x in rt.validate_args(args_with(passages=["6"]))), "control: key 6 still refused")
    f = P01_FIX
    check(rt.compiled_length(f["lead"], f["intervals"], f["tail"]) == P01_SEG["end"] - P01_SEG["start"],
          "P01 fixture sums to the measured 96.336 s")
    v = rt.speeds(f["lead"], f["intervals"], f["tail"], f["lead_cm"], f["gaps"], f["tail_cm"], TICK, 1.0)
    check(abs(v["route_cm"] - 28784.0135) < 1e-6 and abs(v["bay_max"] - 300.0) < 1e-9, "P01 fixture route/speed")
    check(rt.record_name(["1"]) == "passage_retime_to_music_record_P01.json", "P01 record name")


@test
def t_p01_plan_after_shorten():
    row, r, w = rt.plan_passage("1", p01_live(6), TICK, FPS, p01_args())
    check(r == [], "P01 (42 bays) retime has no refusals: %r" % r)
    tgt = rt.target_ticks(73.516032, 2.0, TICK, *FPS)
    check(tgt == 1812480 and row["plan"]["new_ticks"] == tgt, "P01 new length = song + 2 s on a 25 fps frame")
    check(abs(row["speeds_new"]["bay_max"] - 337.25) < 0.05, "P01 bays ~337 cm/s after drop 6: %r" % row["speeds_new"])
    check(any("ENTRY_SPEED_STEP" in x for x in w), "P01 reports the walk-in speed step")
    _r2, _r, w2 = rt.plan_passage("2", live_for("2"), TICK, FPS, args_with())
    check(not any("ENTRY_SPEED_STEP" in x for x in w2), "control: P02 has no entry-speed warning")
    check(rt.entry_speed_warnings("1", 198.0, 19008, 16000, TICK, None) == [], "control: no v_end -> no warning")
    check(rt.entry_speed_warnings("1", 0.0, 0, 0, TICK, 251.3) == [], "control: no lead-in -> no warning")
    check(rt.entry_speed_warnings("2", 198.0, 19008, 16000, TICK, 251.3) == [], "control: other key -> no warning")
    row0, r0, _w = rt.plan_passage("1", p01_live(0), TICK, FPS, p01_args())
    check(r0 == [] and row0["speeds_new"]["bay_max"] > 380.0, "control: no drop -> ~385 cm/s (+28%)")
    _row, rf, _w = rt.plan_passage("1", p01_live(6), TICK, FPS, p01_args(max_speed_cm_s=330.0))
    check(any("TOO_FAST" in x for x in rf), "control: max_speed_cm_s below the new speed refuses")
    _row, rs, _w = rt.plan_passage("1", p01_live(30), TICK, FPS, p01_args())
    check(any("SONG_OVERRUNS" in x for x in rs) is False and rs == [], "drop 30 still retimes (it slows the walk)")


@test
def t_p01_prerequisite():
    tmp = tempfile.mkdtemp()
    try:
        pre = {"1": "p01_shorten_record.json"}
        check(rt.prerequisites_missing(tmp, ["1"], pre), "control: P01 refused without the shorten record")
        with open(os.path.join(tmp, "p01_shorten_record.json"), "w", encoding="utf-8") as h:
            json.dump({"applied": False}, h)
        check(rt.prerequisites_missing(tmp, ["1"], pre), "control: unapplied shorten record refused")
        with open(os.path.join(tmp, "p01_shorten_record.json"), "w", encoding="utf-8") as h:
            json.dump({"applied": True}, h)
        check(rt.prerequisites_missing(tmp, ["1"], pre) == [], "applied shorten record satisfies P01")
        check(ARGS["prerequisite_records"].get("1") == "p01_shorten_record.json", "shipped args gate P01 on the shorten")
    finally:
        shutil.rmtree(tmp)


@test
def t_import_only_guard():
    """With a stand-in `unreal` importable, the module runs main() unless RETIME_IMPORT_ONLY is set."""
    import types

    class Boom(Exception):
        pass

    def _boom(*_a, **_k):
        raise Boom()

    fake = types.ModuleType("unreal")
    fake.__getattr__ = lambda name: _boom
    saved = sys.modules.get("unreal")
    sys.modules["unreal"] = fake
    try:
        path = os.path.join(HERE, "passage_retime_to_music.py")
        spec = importlib.util.spec_from_file_location("rt_guard", path)
        mod = importlib.util.module_from_spec(spec)
        mod.RETIME_IMPORT_ONLY = True
        mod.RETIME_ARGS = {"mode": "BAD"}
        ok = True
        try:
            spec.loader.exec_module(mod)
        except Exception:  # noqa: BLE001 - anything raised means main() ran
            ok = False
        check(ok and mod.unreal is fake, "RETIME_IMPORT_ONLY loads without running main()")
        spec2 = importlib.util.spec_from_file_location("rt_guard2", path)
        mod2 = importlib.util.module_from_spec(spec2)
        mod2.RETIME_ARGS = {"mode": "BAD"}
        ran = False
        try:
            spec2.loader.exec_module(mod2)
        except Exception:  # noqa: BLE001 - any failure inside main() proves it ran
            ran = True
        check(ran, "control: without the flag main() runs on import inside Unreal (unchanged behaviour)")
    finally:
        if saved is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = saved


def offline_table():
    print("OFFLINE_PLAN (tail_s=2.0, 25 fps, settle 1.0 s; P05 split/route INVENTED - time numbers only)")
    d = _deltas(["2", "3", "4", "5"])
    for k in ("2", "3", "4", "5"):
        f = FIX[k]
        song = ARGS["per_passage"][k]["song_s"]
        tgt = rt.target_ticks(song, 2.0, TICK, *FPS)
        comp = rt.settle_compensation_ticks(1.0, TICK)
        p = rt.add_settle_compensation(rt.plan_scaled_timing(f["lead"], f["intervals"], f["tail"], tgt - comp), comp)
        o = rt.speeds(f["lead"], f["intervals"], f["tail"], f["lead_cm"], f["gaps"], f["tail_cm"], TICK, 1.0)
        n = rt.speeds(p["lead_frames"], p["intervals"], p["tail_frames"], f["lead_cm"], f["gaps"], f["tail_cm"], TICK, 1.0)
        print(" P0%s old lead=%d iv=%s x%d tail=%d len=%d (%.3f s) route=%.2f cm mean=%.2f tailpre=%.2f | new lead=%d "
              "iv=%s tail=%d (%.3f s) len=%d (%.3f s) k=%.6f mean=%.2f bay=%.2f tailpre=%.2f | delta=%d (%.3f s)" % (
                  k, f["lead"], sorted(set(f["intervals"])), len(f["intervals"]), f["tail"], p["old_ticks"],
                  p["old_ticks"] / TICK, o["route_cm"], o["mean"], o["tail_pre_settle"], p["lead_frames"],
                  sorted(set(p["intervals"])), p["tail_frames"], p["tail_frames"] / TICK, p["new_ticks"],
                  p["new_ticks"] / TICK, p["k"], n["mean"], n["bay_max"], n["tail_pre_settle"], p["delta_ticks"],
                  p["delta_ticks"] / TICK))
    for row in rt.predict_segments(SEGMENTS, d):
        print("  %-40s [%d, %d) -> [%d, %d) shift %d (%.3f s)" % (row["label"], row["start"], row["end"],
                                                                 row["new_start"], row["new_end"], row["shift"],
                                                                 row["shift"] / TICK))
    print(" net %d ticks = %.3f s" % (sum(d.values()), sum(d.values()) / TICK))


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - counted as a failure
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    if "--table" in sys.argv:
        offline_table()
    for f in CHECKS["failed"]:
        print("FAIL:", f)
    print("PASSAGE_RETIME_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
