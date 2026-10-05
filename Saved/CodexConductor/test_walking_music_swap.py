"""Offline harness for walking_music_swap.py (system Python, no Unreal). Every gate has a failing control.

Fixture data, cited (the live DRY re-reads all of it):
  Passage lengths P1 96.336, P2-P4 180.000, P5 186.364, P6 110.561 s
      opening_sequence_report_apply.json segments_after (run OPENING-APPLY-20261004-131449) and
      Saved/CodexCueing/choreo_report_choreo-apply-3.json length_s [meas 4 Oct; NOT re-measured since Gary's 14:02 edit]
  Show tick 24000/s; fixture rails FadeIn = FadeOut = 1 s, SourceOut = song length
      InfinityStageDevFixtureBuilder.cpp:330, 352-356 [decl: the dev-fixture DEFAULTS; live fades unknown - inf]
  WAV durations/sha256: the real files (read here) == the conductor's ffprobe numbers.
Run: python test_walking_music_swap.py -> WALKING_MUSIC_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_PATH = os.path.join(HERE, "walking_music_swap.py")
spec = importlib.util.spec_from_file_location("walking_music_swap", TOOL_PATH)
wm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wm)
assert wm.unreal is None, "harness must run without Unreal"

PROJECT = os.path.dirname(os.path.dirname(HERE))
with open(os.path.join(HERE, "walking_music_swap_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)

CHECKS = {"n": 0, "failed": []}
TESTS = []
TICK = 24000.0
PASSAGE_S = {"1": 96.336, "2": 180.0, "3": 180.0, "4": 180.0, "5": 186.364, "6": 110.561}


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(items, prefix):
    return any(str(i).startswith(prefix) for i in items)


def args(**kw):
    a = copy.deepcopy(ARGS)
    a.update(kw)
    return a


# ------------------------------------------------------------------------------------------------ args + mapping
@test
def args_valid_as_shipped():
    check(wm.validate_args(args()) == [], "shipped args validate: %r" % wm.validate_args(args()))


@test
def args_controls():
    check(has(wm.validate_args(args(mode="GO")), "MODE_INVALID"), "bad mode refused")
    check(has(wm.validate_args(args(keep_passage_lengths=False)), "KEEP_LENGTHS_REQUIRED"), "retime refused")
    check(has(wm.validate_args(args(dest_folder="/Game/Other")), "DEST_FOLDER_INVALID"), "dest folder pinned")
    check(has(wm.validate_args(args(apply_passages=[])), "APPLY_PASSAGES_INVALID"), "empty targets refused")
    check(has(wm.validate_args(args(apply_passages=["7"])), "APPLY_PASSAGES_INVALID"), "P7 refused")
    check(has(wm.validate_args(args(apply_passages=["2", "2"])), "APPLY_PASSAGES_INVALID"), "dup target refused")
    check(has(wm.validate_args(args(source_out_policy="x")), "SOURCE_OUT_POLICY_INVALID"), "policy checked")
    a = args()
    del a["passages"]["6"]
    check(has(wm.validate_args(a), "PASSAGES_NOT_P01_P06"), "missing passage refused")


@test
def mapping_controls():
    a = args()
    a["passages"]["2"]["wav"], a["passages"]["3"]["wav"] = a["passages"]["3"]["wav"], a["passages"]["2"]["wav"]
    bad = wm.validate_args(a)
    check(has(bad, "P2_MAPPING") and has(bad, "P3_MAPPING"), "swapped files refused: %r" % bad)
    a = args()
    a["passages"]["5"]["asset_name"] = "SW_P06_X"
    check(has(wm.validate_args(a), "P5_ASSET_NAME"), "asset name must carry its Passage")
    a = args()
    a["passages"]["6"]["asset_name"] = a["passages"]["5"]["asset_name"]
    check(has(wm.validate_args(a), "ASSET_NAMES_NOT_UNIQUE") or has(wm.validate_args(a), "P6_ASSET_NAME"),
          "duplicate asset names refused")
    a = args()
    del a["passages"]["4"]["pad"]["unpadded_sha256"]
    check(has(wm.validate_args(a), "P4_PAD_MISSING_UNPADDED_SHA256"), "pad record must be complete")


@test
def real_inputs_match_args():
    facts, r = wm.check_inputs(args(), PROJECT)
    check(r == [], "real WAVs match args: %r" % r)
    check(sorted(facts) == list(wm.PASSAGE_KEYS), "six inputs read")
    check(abs(facts["6"]["duration_s"] - 125.0) < 1e-6, "P06 125.000 s")
    check(abs(facts["4"]["duration_s"] - 48.397664) < 1e-5, "P04 padded 48.398 s")
    check(abs(facts["4"]["unpadded"]["duration_s"] - 38.397664) < 1e-5, "P04 unpadded 38.398 s recorded")
    check(facts["1"]["sample_width"] == 3 and facts["1"]["rate"] == 44100 and facts["1"]["channels"] == 2,
          "24-bit 44.1 kHz stereo")


@test
def input_controls():
    a = args()
    a["passages"]["3"]["sha256"] = "0" * 64
    check(has(wm.check_inputs(a, PROJECT)[1], "WAV_SHA_MISMATCH_P3"), "tampered sha refused")
    a = args()
    a["passages"]["2"]["duration_s"] = 47.0
    check(has(wm.check_inputs(a, PROJECT)[1], "WAV_DURATION_MISMATCH_P2"), "wrong duration refused")
    a = args()
    a["passages"]["4"]["pad"]["pad_s"] = 9.0
    check(has(wm.check_inputs(a, PROJECT)[1], "PAD_LENGTH_P4"), "pad length must equal padded - unpadded")
    a = args()
    a["passages"]["4"]["pad"]["unpadded_sha256"] = "1" * 64
    check(has(wm.check_inputs(a, PROJECT)[1], "PAD_UNPADDED_SHA_MISMATCH_P4"), "unpadded sha checked")
    a = args()
    a["passages"]["1"]["wav"] = "DerivedAssets/Audio/WalkingMusic_Cameron_20261005/P01_missing.wav"
    check(has(wm.check_inputs(a, PROJECT)[1], "WAV_MISSING_P1"), "missing file refused")


# ------------------------------------------------------------------------------------------------ fit maths
@test
def fit_table():
    facts, _ = wm.check_inputs(args(), PROJECT)
    f6 = wm.fit(PASSAGE_S["6"], facts["6"]["duration_s"], 0, 0, 1.0, 1.0)
    check(not f6["fits"] and abs(f6["overrun_s"] - 14.439) < 1e-6, "P06 overruns 14.439 s: %r" % f6)
    check(abs(f6["audible_s"] - 110.561) < 1e-6, "P06 audible = Passage")
    check("CUT" in f6["fade_out"] and "109.561-110.561" in f6["fade_out"], "P06 cut + faded at the Passage end")
    f1 = wm.fit(PASSAGE_S["1"], facts["1"]["duration_s"], 0, 0, 1.0, 1.0)
    check(f1["fits"] and abs(f1["silence_tail_s"] - 22.819968) < 1e-5, "P01 22.820 s silence tail: %r" % f1)
    check("inaudible" in f1["fade_out"], "P01 fade-out over silence")
    f4 = wm.fit(PASSAGE_S["4"], facts["4"]["duration_s"], 0, 0, 1.0, 1.0)
    check(f4["fits"] and abs(f4["silence_tail_s"] - 131.602336) < 1e-5, "P04 padded tail 131.602 s")
    f5 = wm.fit(PASSAGE_S["5"], facts["5"]["duration_s"], 0, 0, 0, 0)
    check(abs(f5["silence_tail_s"] - 144.341528) < 1e-5 and f5["fade_out"].startswith("no fade-out"), "P05 tail")


@test
def fit_controls():
    inside = wm.fit(100.0, 99.5, 0, 0, 0, 2.0)
    check(inside["fits"] and "INSIDE" in inside["fade_out"], "song ending inside the fade window flagged")
    hard = wm.fit(100.0, 120.0, 0, 0, 0, 0)
    check(not hard["fits"] and "hard cut" in hard["fade_out"], "no fade + overrun = hard cut")
    off = wm.fit(100.0, 120.0, 10.0, 15.0, 0, 0)
    check(off["fits"] and abs(off["silence_tail_s"] - 5.0) < 1e-9, "source-in + rail offset shorten the song")
    exact = wm.fit(100.0, 100.0)
    check(exact["fits"] and exact["overrun_s"] == 0 and exact["silence_tail_s"] == 0, "exact fit")
    for bad in ((0.0, 10.0), (10.0, 0.0)):
        try:
            wm.fit(*bad)
            check(False, "fit %r must raise" % (bad,))
        except wm.PlanError:
            check(True, "")


# ------------------------------------------------------------------------------------------------ length + sync gates
SEGS = [{"label": "Opening", "start": 0, "end": 2312640}, {"label": "Passage 1", "start": 2312640, "end": 4624704},
        {"label": "Scene 1", "start": 4624704, "end": 9683904}]


@test
def length_gate_controls():
    check(wm.length_gate(SEGS, copy.deepcopy(SEGS)) == [], "unchanged passes")
    moved = copy.deepcopy(SEGS)
    moved[1]["end"] += 1
    check(has(wm.length_gate(SEGS, moved), "LENGTH_MOVED: Passage 1"), "1-tick length change refused")
    shifted = copy.deepcopy(SEGS)
    for s in shifted:
        s["start"] += 24000
        s["end"] += 24000
    out = wm.length_gate(SEGS, shifted)
    check(has(out, "START_MOVED") and not has(out, "LENGTH_MOVED"), "shift caught as START_MOVED")
    check(has(wm.length_gate(SEGS, SEGS[:2]), "SEGMENT_SET_CHANGED"), "lost segment refused")
    check(has(wm.length_gate(SEGS + [dict(SEGS[0])], SEGS + [dict(SEGS[0])]), "SEGMENT_LABELS_DUPLICATED"),
          "duplicate labels refused")


@test
def sync_and_section_gates():
    show = {"Opening": [0.0, 96.36], "Passage 1": [96.36, 192.696]}
    check(wm.sync_gate(show, dict(show)) == [], "in sync passes")
    stale = {"Opening": [0.0, 96.36], "Passage 1": [96.36, 192.696]}
    gary = {"Opening": [0.0, 104.0], "Passage 1": [104.0, 200.336]}
    out = wm.sync_gate(gary, stale)
    check(has(out, "MASTER_STALE: Opening") and has(out, "MASTER_STALE: Passage 1"), "stale Master refused")
    check(has(wm.sync_gate(show, {"Opening": [0.0, 96.36]}), "MASTER_SECTION_MISSING"), "missing section refused")
    check(has(wm.sync_gate(show, dict(show, Extra=[0, 1])), "MASTER_EXTRA_SECTION"), "extra section refused")
    check(wm.sync_gate(show, {"Opening": [0.0, 96.40], "Passage 1": [96.40, 192.70]}) == [], "0.05 s tolerance")
    check(wm.section_gate(show, dict(show)) == [], "sections unchanged pass")
    check(has(wm.section_gate(show, {"Opening": [0, 96.36], "Passage 1": [96.36, 192.7]}),
              "MASTER_PASSAGE_SECTION_MOVED"), "moved section refused")


# ------------------------------------------------------------------------------------------------ rail plan refusals
def live_fixture():
    passages = {k: {"label": "Passage %s" % k, "guid": "PG%s" % k, "mode": "<InfinityMusicBindingMode.START: 0>",
                    "rail": "R%s" % k} for k in wm.PASSAGE_KEYS}
    passages["1"]["mode"] = "<InfinityMusicBindingMode.SILENCE: 2>"
    passages["1"]["rail"] = "2E86"
    bindings = [{"owner": p["label"], "mode": p["mode"], "rail": p["rail"], "secondary": "0"} for p in passages.values()]
    bindings.append({"owner": "cue:Opening", "mode": "<InfinityMusicBindingMode.START: 0>", "rail": "2E86",
                     "secondary": "0"})
    rails = {p["rail"]: {"guid": p["rail"], "label": "Passage %s Music" % k, "sound": "/Game/Old/SW_%s" % k,
                         "source_in": 0, "source_out": int(PASSAGE_S[k] * TICK), "fade_in": 24000, "fade_out": 24000,
                         "analysis_map": "/Game/InfinityStage/MusicMaps/MM_P0%s_Analysis" % k}
             for k, p in passages.items()}
    return passages, bindings, rails


@test
def rail_plan_controls():
    passages, bindings, rails = live_fixture()
    plan, r = wm.rail_plan(passages, bindings, rails, ["2", "3", "4", "5", "6"], "refuse")
    check(r == [] and sorted(plan) == ["2", "3", "4", "5", "6"], "P2-P6 plan cleanly: %r" % r)
    plan, r = wm.rail_plan(passages, bindings, rails, ["1"], "refuse")
    check(has(r, "P1_SILENT") and not plan, "silent P01 refused under 'refuse'")
    plan, r = wm.rail_plan(passages, bindings, rails, ["1"], "set_start")
    check(has(r, "P1_RAIL_SHARED") and not plan, "P01 rail shared with the Opening refused even with set_start")
    b2 = [b for b in bindings if b["owner"] != "cue:Opening"] + [
        {"owner": "cue:Opening", "mode": "START", "rail": "R_OPEN", "secondary": "0"}]
    plan, r = wm.rail_plan(passages, b2, rails, ["1"], "set_start")
    check(r == [] and plan["1"]["set_start"], "after the Opening owns a rail, P01 plans with set_start")
    p2 = copy.deepcopy(passages)
    p2["3"]["rail"] = "R2"
    b3 = [dict(b, rail="R2") if b["owner"] == "Passage 3" else b for b in bindings]
    _plan, r = wm.rail_plan(p2, b3, rails, ["2"], "refuse")
    check(has(r, "P2_RAIL_SHARED"), "rail shared by two Passages refused")
    p3 = copy.deepcopy(passages)
    p3["5"]["mode"] = "InfinityMusicBindingMode.EXPLICIT_CROSSFADE"
    check(has(wm.rail_plan(p3, bindings, rails, ["5"], "refuse")[1], "P5_MODE_UNSUPPORTED"), "crossfade refused")
    p4 = copy.deepcopy(passages)
    p4["6"]["rail"] = "MISSING"
    check(has(wm.rail_plan(p4, bindings, rails, ["6"], "refuse")[1], "P6_RAIL_MISSING"), "missing rail refused")
    sil = [dict(b, mode="SILENCE") if b["owner"] == "Passage 4" else b for b in bindings]
    check(wm.rail_plan(passages, sil, rails, ["2", "3", "4", "5", "6"], "refuse")[1] == [],
          "a SILENT other binding on the same rail is not a share")


@test
def mode_token_forms():
    for text, want in (("<InfinityMusicBindingMode.START: 0>", "START"), ("InfinityMusicBindingMode.SILENCE", "SILENCE"),
                       ("START", "START"), ("<InfinityMusicBindingMode.EXPLICIT_CROSSFADE: 3>", "EXPLICIT_CROSSFADE")):
        check(wm.mode_token(text) == want, "mode_token %r -> %r" % (text, wm.mode_token(text)))


@test
def rail_targets_policies():
    _p, _b, rails = live_fixture()
    rb = rails["R6"]
    t = wm.rail_targets(rb, "/Game/New/SW_6", 125.0, TICK, "new_duration", "keep")
    check(t == {"sound": "/Game/New/SW_6", "source_out": 3000000}, "new_duration sets SourceOut: %r" % t)
    check(wm.rail_targets(rb, "/Game/New/SW_6", 125.0, TICK, "keep", "keep") == {"sound": "/Game/New/SW_6"}, "keep")
    t = wm.rail_targets(dict(rb, source_out=0), "/Game/New/SW_6", 125.0, TICK, "new_duration", "unlink")
    check(t == {"sound": "/Game/New/SW_6", "analysis_map": None}, "SourceOut 0 stays 0; unlink clears the map")
    try:
        wm.rail_targets(dict(rb, source_in=4000000), "/Game/N", 125.0, TICK, "new_duration", "keep")
        check(False, "SourceOut <= SourceIn must raise")
    except wm.PlanError:
        check(True, "")


# ------------------------------------------------------------------------------------------------ apply / revert exactness
class FakeShow(object):
    def __init__(self, rails, modes):
        self.rails = copy.deepcopy(rails)
        self.modes = dict(modes)
        self.lossy = None

    def read_rails(self):
        return copy.deepcopy(self.rails)

    def read_modes(self):
        return dict(self.modes)

    def write_rail(self, guid, fields):
        for k, v in fields.items():
            if k == self.lossy:
                continue
            self.rails[guid][k] = v

    def write_mode(self, key, mode):
        enum = {"START": 0, "CONTINUE": 1, "SILENCE": 2, "EXPLICIT_CROSSFADE": 3}   # InfinityStageTypes.h:28-35
        self.modes[key] = "<InfinityMusicBindingMode.%s: %d>" % (mode, enum[mode])


def make_record(show, plan, targets):
    rb, mb = show.read_rails(), show.read_modes()
    return {"passages": {k: {"rail": plan[k]["rail"], "rail_before": wm.rail_descriptor(rb[plan[k]["rail"]]),
                             "rail_after": dict(wm.rail_descriptor(rb[plan[k]["rail"]]), **targets[k]),
                             "mode_before": mb[k], "mode_after": "START" if plan[k]["set_start"] else mb[k]}
                         for k in plan}}


def scenario(keys=("2", "3", "4", "5", "6"), opening_rail="2E86", policy="refuse"):
    passages, bindings, rails = live_fixture()
    if opening_rail != "2E86":
        bindings = [b for b in bindings if b["owner"] != "cue:Opening"] + [
            {"owner": "cue:Opening", "mode": "START", "rail": opening_rail, "secondary": "0"}]
    show = FakeShow(rails, {k: p["mode"] for k, p in passages.items()})
    plan, r = wm.rail_plan(passages, bindings, show.read_rails(), list(keys), policy)
    targets = {k: wm.rail_targets(show.read_rails()[plan[k]["rail"]], "/Game/New/SW_%s" % k, 40.0 + int(k), TICK,
                                  "new_duration", "keep") for k in plan}
    return show, plan, targets, r


@test
def apply_then_revert_is_exact():
    show, plan, targets, r = scenario()
    check(r == [], "scenario plans")
    original = (show.read_rails(), show.read_modes())
    record = make_record(show, plan, targets)
    check(wm.swap_rails(show, plan, targets) == [], "swap reads back")
    check(show.read_rails()["R6"]["sound"] == "/Game/New/SW_6", "rail written")
    check(show.read_rails()["2E86"] == original[0]["2E86"], "the Opening/P01 rail untouched")
    check(wm.drift_since_apply(show, record) == [], "no drift right after apply")
    check(wm.restore_rails(show, record) == [], "revert reads back exact")
    check((show.read_rails(), show.read_modes()) == original, "revert == original, every field and mode")


@test
def revert_restores_mode_for_p01():
    show, plan, targets, r = scenario(keys=("1",), opening_rail="R_OPEN", policy="set_start")
    check(r == [], "P01 plan with set_start")
    original = (show.read_rails(), show.read_modes())
    record = make_record(show, plan, targets)
    check(wm.swap_rails(show, plan, targets) == [], "P01 swap + Start reads back")
    check(wm.mode_token(show.read_modes()["1"]) == "START", "P01 now Start")
    check(wm.restore_rails(show, record) == [] and (show.read_rails(), show.read_modes()) == original,
          "P01 revert back to Silence + old sound, exact")


@test
def revert_controls():
    show, plan, targets, _r = scenario()
    record = make_record(show, plan, targets)
    wm.swap_rails(show, plan, targets)
    show.rails["R3"]["fade_out"] = 48000                  # someone edited after apply
    out = wm.restore_rails(show, record)
    check(has(out, "STATE_DRIFTED") and show.rails["R3"]["sound"] == "/Game/New/SW_3", "drift refuses, writes nothing")
    show, plan, targets, _r = scenario()
    record = make_record(show, plan, targets)
    wm.swap_rails(show, plan, targets)
    show.lossy = "source_out"                              # a setter that silently does nothing
    check(has(wm.restore_rails(show, record), "P2 REVERT_RAIL_NOT_EXACT"), "lossy revert detected")
    show, plan, targets, _r = scenario()
    show.lossy = "sound"
    check(has(wm.swap_rails(show, plan, targets), "P2 READBACK_SOUND"), "lossy apply detected")


# ------------------------------------------------------------------------------------------------ live gates, records
@test
def live_gate_controls():
    good = {"mode": "APPLY", "confirm": "APPLY WALKING MUSIC", "pie": False, "sequencer_open": False,
            "census": {"content": [], "maps": []}, "overlapping_records": [], "decided_by": "Gary",
            "mapping_confirmed_by": "Gary", "assets_exist": []}
    check(wm.live_gates(good) == [], "clean APPLY passes")
    for field, value, prefix in (("confirm", "APPLY", "CONFIRM_MISMATCH"), ("pie", True, "PIE_OR_SIE_ACTIVE"),
                                 ("sequencer_open", True, "SEQUENCER_IS_OPEN"),
                                 ("census", {"content": ["/Game/X"], "maps": []}, "DIRTY_CENSUS"),
                                 ("overlapping_records", ["walking_music_swap_record_P02.json"], "RECORD_COVERS_TARGET"),
                                 ("decided_by", "", "NOT_DECIDED"), ("mapping_confirmed_by", " ", "MAPPING_NOT_CONFIRMED"),
                                 ("assets_exist", ["/Game/A"], "ASSET_EXISTS")):
        check(has(wm.live_gates(dict(good, **{field: value})), prefix), "control %s" % prefix)
    check(has(wm.live_gates({"mode": "REVERT", "confirm": "REVERT WALKING MUSIC", "census": {}}), "NO_APPLIED_RECORD"),
          "REVERT needs an applied record")
    check(wm.live_gates({"mode": "DRY", "confirm": "DRY WALKING MUSIC", "census": {}, "decided_by": ""}) == [],
          "DRY needs no decision")


@test
def census_gate_controls():
    exp = ["/Game/S", "/Game/M", "/Game/W1"]
    check(wm.census_gate({"content": ["/Game/S", "/Game/W1"], "maps": []}, exp) == [], "subset passes")
    check(has(wm.census_gate({"content": ["/Game/L"], "maps": []}, exp), "UNEXPECTED_DIRTY"), "stray refused")
    check(has(wm.census_gate({"content": [], "maps": ["/Game/Map"]}, exp), "MAP_DIRTY"), "map dirty refused")


@test
def records_and_names():
    check(wm.record_name(["6", "2"]) == "walking_music_swap_record_P02-P06.json", "record name sorted")
    d = tempfile.mkdtemp()
    open(os.path.join(d, "walking_music_swap_record_P02-P03.json"), "w").close()
    open(os.path.join(d, "walking_music_swap_record_P04.json.reverted-X"), "w").close()
    check(wm.records_covering(d, ["3"]) == ["walking_music_swap_record_P02-P03.json"], "overlap found")
    check(wm.records_covering(d, ["1", "4"]) == [], "archived records ignored; disjoint set free")
    p = os.path.join(d, "rec.json")
    wm.write_record_exclusive(p, {"a": 1})
    try:
        wm.write_record_exclusive(p, {"a": 2})
        check(False, "exclusive record must refuse an existing file")
    except OSError:
        check(True, "")


@test
def soft_path_parsing():
    for text, want in (('(RailGuid=1,Sound="/Script/Engine.SoundWave\'/Game/A/SW_X.SW_X\'",AnalysisMap=None)', "/Game/A/SW_X"),
                       ("(Sound=/Game/A/SW_Y.SW_Y,FadeInFrames=(Value=24000))", "/Game/A/SW_Y"),
                       ("(Sound=None,AnalysisMap=/Game/M/MM_P01_Analysis.MM_P01_Analysis)", None)):
        check(wm.soft_path_from_export(text, "Sound") == want, "Sound in %r" % text)
    check(wm.soft_path_from_export("(Sound=None,AnalysisMap=/Game/M/MM_P01_Analysis.MM_P01_Analysis)", "AnalysisMap")
          == "/Game/M/MM_P01_Analysis", "AnalysisMap parsed")
    check(wm.soft_path_from_export('(Label=NSLOCTEXT("", "k", "MySound=/Game/Fake"),Sound=None)', "Sound") is None,
          "field inside a label is not matched")


@test
def stale_report_lists_everything():
    f = wm.fit(110.561, 125.0, 0, 0, 1, 1)
    facts = {"choreo": {"path": "/Game/InfinityStage/Choreo/LS_Choreo_Passage_6", "marks": 9, "song_markers": 7},
             "analysis_map": {"path": "/Game/InfinityStage/MusicMaps/MM_P06_Analysis", "source_filename": "x.wav",
                              "duration_s": 110.561, "confirmed": 0},
             "pinned_frames": 0, "keyed_channels": {}, "rail": {"fingerprint": "abc"}, "refit_duration_s_after": 125.0}
    items = {i["item"]: i for i in wm.stale_report("6", facts, 125.0, f)}
    check(sorted(items) == sorted(["choreo_song_markers", "analysis_map", "camera_anchors_pinned_frames",
                                   "camera_channel_keys_candidates", "refit_from_music", "source_fingerprint",
                                   "light_drama_and_lighting_scores"]), "every stale category reported")
    check(items["choreo_song_markers"]["stale"] and items["analysis_map"]["stale"], "choreo + map stale")
    check(not items["camera_anchors_pinned_frames"]["stale"], "no pins -> not stale (control)")
    check(not items["refit_from_music"]["stale"] and "DO NOT REFIT" in items["refit_from_music"]["detail"], "refit")
    check(not items["light_drama_and_lighting_scores"]["stale"], "lighting is distance-driven")


@test
def module_runs_nothing_offline():
    src = open(TOOL_PATH, encoding="utf-8").read()
    check(src.rstrip().endswith("if unreal is not None:\n    main()"), "main gated on unreal")
    check("save_all" not in src.lower().replace("save all", ""), "no save_all call")
    check("refit" not in [l.split("(")[0] for l in src.split() if l.startswith("unreal.")], "no refit call")


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:   # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    facts, _ = wm.check_inputs(args(), PROJECT)
    for k in wm.PASSAGE_KEYS:
        f = wm.fit(PASSAGE_S[k], facts[k]["duration_s"], 0, 0, 1.0, 1.0)
        print("FIT P%s passage %.3f s | new %.3f s | fits=%s overrun %.3f s | silence tail %.3f s | %s"
              % (k, PASSAGE_S[k], facts[k]["duration_s"], f["fits"], f["overrun_s"], f["silence_tail_s"], f["fade_out"]))
    for f in CHECKS["failed"]:
        print("FAIL: " + f)
    print("WALKING_MUSIC_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
