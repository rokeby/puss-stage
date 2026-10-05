"""Offline harness for scene_narration_standin.py (system Python, no Unreal). Every gate has a failing control.

Fixture rise/Scene data, cited (the live DRY re-reads all of it):
  rise tick 24000/s, playback 0..31 s; Hangar Fold sub-section at Scene 0.0..31.0 s, offsets 0
      NEST-S2-NEST-READBACK-20261003-A-response.json (S1-S3 rows) [meas 3 Oct]
  rise display 30 fps        test_hangar_heave.py:9 [inf there too]; only used for the rise playback ticks
  root land key 4.1333 s (99200 ticks), StrikeAfterLand 5.8667083 s
      atf_hangar_timing_apply_record.json readback S1-S3 land_seconds / strike_after_land_seconds [meas 2 Oct]
  Scene playback S1 0..210.8 s @25, S2 0..31.0 s @25, S3 0..260.0 s @24, Scene tick 24000   same NEST readback [meas]
  WAV durations: the real files' headers (read here) == conductor's ffprobe numbers.
Run: python test_scene_narration_standin.py -> SCENE_NARRATION_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_PATH = os.path.join(HERE, "scene_narration_standin.py")
spec = importlib.util.spec_from_file_location("scene_narration_standin", TOOL_PATH)
sn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sn)
assert sn.unreal is None, "harness must run without Unreal"

PROJECT = os.path.dirname(os.path.dirname(HERE))
with open(os.path.join(HERE, "scene_narration_standin_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)

CHECKS = {"n": 0, "failed": []}
TESTS = []
TICK = 24000.0
LAND_TICK = 99200                       # 4.1333 s x 24000
STRIKE = 5.8667083333333325


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(items, prefix):
    return any(prefix in x for x in items)


def facts(fps, end_s, **over):
    f = {"scene_res": TICK, "fps": fps, "playback": [0, int(round(end_s * fps))], "rise_res": TICK,
         "rise_lower_tick": 0, "rise_upper_tick": int(31 * TICK), "section_start_tick": 0,
         "section_end_tick": int(31 * TICK), "start_offset_tick": 0, "end_offset_tick": 0,
         "land_tick_inner": LAND_TICK, "strike_after_land_s": STRIKE}
    f.update(over)
    return f


FIX = {"1": facts(25.0, 210.8), "2": facts(25.0, 31.0), "3": facts(24.0, 260.0)}
DUR = {"1": 34.986667, "2": 74.752, "3": 34.304}


def args(**over):
    a = copy.deepcopy(ARGS)
    a.update(over)
    return a


# ------------------------------------------------------------------------------------------------------ land maths

@test
def landing_frames():
    p1 = sn.plan_scene(FIX["1"], args(), DUR["1"])
    p3 = sn.plan_scene(FIX["3"], args(), DUR["3"])
    check(abs(p1["land_s"] - 4.133333) < 1e-5, "S1 land_s %r" % p1.get("land_s"))
    check(p1["start_frame"] == 104, "S1 (a) ceil(103.33)=104, got %r" % p1["start_frame"])
    check(p3["start_frame"] == 100, "S3 (a) @24 ceil(99.2)=100, got %r" % p3["start_frame"])
    check(p1["frames_by_option"]["land_plus_strike"] == 251, "S1 (b) 10.0000417 s -> 251 (one tick past 250)")
    check(p3["frames_by_option"]["land_plus_strike"] == 241, "S3 (b) @24 240.001 -> 241")
    # exact-frame land is NOT bumped (float tolerance) - control: one tick later IS bumped
    exact = sn.plan_scene(facts(25.0, 210.8, land_tick_inner=960 * 103), args(), 1.0)
    late = sn.plan_scene(facts(25.0, 210.8, land_tick_inner=960 * 103 + 1), args(), 1.0)
    check(exact["start_frame"] == 103 and late["start_frame"] == 104, "ceil boundary %r/%r"
          % (exact["start_frame"], late["start_frame"]))


@test
def landing_placement_maths():
    # section moved to Scene 2.0 s -> +50 frames @25
    moved = sn.plan_scene(facts(25.0, 210.8, section_start_tick=48000, section_end_tick=48000 + 31 * 24000), args(), 1.0)
    check(moved["start_frame"] == 154, "section start shift: %r" % moved["start_frame"])
    # StartFrameOffset -960 inner ticks (one frame) -> land 960 ticks LATER in the Scene (inner = lower+off+(o-s))
    off = sn.plan_scene(facts(25.0, 210.8, start_offset_tick=-960, rise_upper_tick=31 * 24000 - 960), args(), 1.0)
    check(abs(off["land_tick_outer"] - (LAND_TICK + 960)) < 1e-6, "offset sign: %r" % off.get("land_tick_outer"))
    # failing control: a sign-flipped map would put it 960 earlier - the check above must distinguish them
    flipped = sn.inner_to_outer_tick(LAND_TICK, TICK, 0, +960, 0, TICK)
    check(abs(flipped - (LAND_TICK + 960)) > 1, "control: sign-flipped offset must differ")
    # tick resolutions differ: inner 30000/s, outer 24000/s
    t = sn.inner_to_outer_tick(30000 * 4, 30000.0, 0, 0, 0, 24000.0)
    check(abs(t - 96000) < 1e-9, "tick-res transform %r" % t)
    # rise playback lower bound not zero: inner lower 1 s -> land 1 s earlier in the Scene
    low = sn.inner_to_outer_tick(LAND_TICK, TICK, 24000, 0, 0, TICK)
    check(abs(low - (LAND_TICK - 24000)) < 1e-9, "inner lower bound %r" % low)
    # round trip with the Arrival's forward map (InfinityStageArrival.cpp:1044-1048)
    for outer in (0, 12345, 99200, -5000):
        inner = 24000 + (-960) + (outer - 4800) * 1.0 * (30000.0 / 24000.0)
        back = sn.inner_to_outer_tick(inner, 30000.0, 24000, -960, 4800, 24000.0)
        check(abs(back - outer) < 1e-6, "round trip %d -> %r" % (outer, back))


@test
def play_rate_gate():
    ok = sn.plan_scene(FIX["1"], args(), DUR["1"])
    check(not ok["refusals"], "rate 1 fixture refused: %r" % ok["refusals"])
    bad = sn.plan_scene(facts(25.0, 210.8, section_end_tick=62 * 24000), args(), DUR["1"])   # 62 s for 31 s inner
    check(has(bad["refusals"], "PLAY_RATE_UNVERIFIED"), "control: rate 0.5 must refuse")
    unb = sn.plan_scene(facts(25.0, 210.8, section_end_tick=None), args(), DUR["1"])
    check(has(unb["refusals"], "SECTION_UNBOUNDED"), "control: unbounded section must refuse")


# ------------------------------------------------------------------------------------------------------ fit / overrun

@test
def fit_and_overrun():
    p = {k: sn.plan_scene(FIX[k], args(), DUR[k]) for k in FIX}
    check(p["1"]["fits"] and abs(p["1"]["headroom_s"] - (210.8 - 4.16 - 34.986667)) < 1e-6, "S1 fits %r" % p["1"])
    check(p["3"]["fits"], "S3 fits")
    check(not p["2"]["fits"] and abs(p["2"]["overrun_s"] - (4.16 + 74.752 - 31.0)) < 1e-6,
          "S2 overrun %r" % p["2"].get("overrun_s"))
    check(p["2"]["end_frame"] == 104 + 1869, "S2 clip_length end = start + ceil(74.752*25)=1869: %r" % p["2"]["end_frame"])
    check(abs(p["2"]["audible_s"] - (31.0 - 4.16)) < 1e-9, "S2 audible %r" % p["2"]["audible_s"])
    trim = sn.plan_scene(FIX["2"], args(section_end="scene_end"), DUR["2"])
    check(trim["end_frame"] == 775 and not trim["fits"], "scene_end policy trims to 775: %r" % trim["end_frame"])
    # control: S1 with a 30 s Scene must overrun
    short = sn.plan_scene(facts(25.0, 30.0), args(), DUR["1"])
    check(not short["fits"], "control: S1 in a 30 s Scene must overrun")
    # boundary: exactly-fitting clip fits
    exact = sn.plan_scene(facts(25.0, 4.16 + 10.0), args(), 10.0)
    check(exact["fits"], "exact fit must fit: %r" % exact.get("overrun_s"))
    check(sn.overrun_summary(p).startswith("S2:+47.912"), "overrun summary %r" % sn.overrun_summary(p))
    # option (b) with no Arrival strike value refuses
    nob = sn.plan_scene(facts(25.0, 210.8, strike_after_land_s=None), args(start_option="land_plus_strike"), 1.0)
    check(has(nob["refusals"], "STRIKE_AFTER_LAND_UNKNOWN"), "option b without strike must refuse")
    b = sn.plan_scene(FIX["1"], args(start_option="land_plus_strike"), DUR["1"])
    check(b["start_frame"] == 251 and not b["refusals"], "option b plan %r" % b.get("start_frame"))
    after = sn.plan_scene(facts(25.0, 3.0), args(), 1.0)
    check(has(after["refusals"], "START_AFTER_SCENE_END"), "control: land after the Scene end refuses")


# ------------------------------------------------------------------------------------------------------ GO markers

@test
def go_markers():
    plan = sn.plan_scene(FIX["1"], args(), DUR["1"])
    rows = sn.go_report([{"label": "GO 12 wait for cat", "scene_s": 20.0, "sequence": "s"},
                         {"label": "GO 13 PASS lights", "scene_s": 21.0, "sequence": "s"},
                         {"label": "go 14 lower", "scene_s": 22.0, "sequence": "s"},
                         {"label": "GO 15 HOLD late", "scene_s": 100.0, "sequence": "s"},
                         {"label": "GO 16 HOLD early", "scene_s": 1.0, "sequence": "s"}], plan)
    by = {r["number"]: r for r in rows}
    check(by["12"]["pauses_narration"], "default GO in a Scene = HOLD inside the window")
    check(not by["13"]["pauses_narration"] and by["13"]["inside_narration"], "PASS does not pause")
    check("14" not in by, "control: lower-case go is not a cue")
    check(not by["15"]["inside_narration"] and not by["16"]["inside_narration"], "outside window")
    check(sn.parse_go_label("GO HOLD") is None and sn.parse_go_label("GO 1.2 HOLD x")[2] == 1, "parser")


# ------------------------------------------------------------------------------------------------------ refusals

def clean_state(mode):
    return {"mode": mode, "confirm": "%s NARRATION" % mode, "pie": False, "sequencer_open": False,
            "census": {"content": [], "maps": []}, "record_exists": mode == "REVERT",
            "record_applied": mode == "REVERT", "decided_by": "Gary", "mapping_confirmed_by": "Gary", "assets_exist": []}


@test
def refusals():
    for mode in ("DRY", "APPLY", "REVERT"):
        check(sn.live_gates(clean_state(mode)) == [], "clean %s refused: %r" % (mode, sn.live_gates(clean_state(mode))))
    cases = [
        ("APPLY", {"confirm": "APPLY S1"}, "CONFIRM_MISMATCH"),
        ("DRY", {"mode": "PLAY", "confirm": "PLAY NARRATION"}, "MODE_INVALID"),
        ("APPLY", {"pie": True}, "PIE_OR_SIE_ACTIVE"),
        ("APPLY", {"sequencer_open": True}, "SEQUENCER_IS_OPEN"),
        ("APPLY", {"census": {"content": ["/Game/X"], "maps": []}}, "DIRTY_CENSUS"),
        ("DRY", {"census": {"content": [], "maps": ["/Game/M"]}}, "DIRTY_CENSUS"),
        ("APPLY", {"record_exists": True}, "RECORD_EXISTS"),
        ("APPLY", {"decided_by": ""}, "NOT_DECIDED"),
        ("APPLY", {"mapping_confirmed_by": " "}, "MAPPING_NOT_CONFIRMED"),
        ("APPLY", {"assets_exist": ["/Game/A/SW"]}, "ASSET_EXISTS"),
        ("REVERT", {"record_applied": False}, "NO_APPLIED_RECORD"),
    ]
    for mode, over, want in cases:
        st = clean_state(mode)
        st.update(over)
        check(has(sn.live_gates(st), want), "refusal %s missing for %s %r" % (want, mode, over))
    check(sn.validate_args(ARGS) == [], "shipped args invalid: %r" % sn.validate_args(ARGS))
    check(ARGS["start_option"] == "land" and ARGS["mode"] == "DRY" and ARGS["delete_assets"] is False,
          "shipped args defaults: option (a), DRY, keep assets")
    for over, want in (({"start_option": "b"}, "START_OPTION_INVALID"), ({"section_end": "x"}, "SECTION_END_INVALID"),
                       ({"dest_folder": "Narration"}, "DEST_FOLDER_INVALID")):
        check(has(sn.validate_args(args(**over)), want), "args control %s" % want)
    bad = args()
    bad["scenes"]["2"]["scene_sequence"] = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
    check(has(sn.validate_args(bad), "TARGET_NOT_A_SCENE"), "control: Master as a target must refuse")
    bad = args()
    bad["scenes"]["3"]["asset_name"] = bad["scenes"]["1"]["asset_name"]
    check(has(sn.validate_args(bad), "ASSET_NAMES_NOT_UNIQUE"), "control: duplicate asset names")
    bad = args()
    del bad["scenes"]["3"]
    check(has(sn.validate_args(bad), "SCENES_NOT_S1_S3"), "control: missing scene")


@test
def inputs():
    facts_, r = sn.check_inputs(ARGS, PROJECT)
    check(r == [], "real WAV inputs refused: %r" % r)
    for k, want in DUR.items():
        check(abs(facts_[k]["duration_s"] - want) < 1e-3 and facts_[k]["rate"] == 48000 and facts_[k]["channels"] == 1,
              "S%s WAV header %r" % (k, {f: facts_[k][f] for f in ("duration_s", "rate", "channels")}))
    bad = args()
    bad["scenes"]["2"]["sha256"] = "0" * 64
    check(has(sn.check_inputs(bad, PROJECT)[1], "WAV_SHA_MISMATCH_S2"), "control: wrong sha must refuse")
    bad = args()
    bad["scenes"]["1"]["duration_s"] = 30.0
    check(has(sn.check_inputs(bad, PROJECT)[1], "WAV_DURATION_MISMATCH_S1"), "control: wrong duration must refuse")
    bad = args()
    bad["scenes"]["3"]["wav"] = "DerivedAssets/Audio/Narration_Standin/Nope.wav"
    check(has(sn.check_inputs(bad, PROJECT)[1], "WAV_MISSING_S3"), "control: missing wav must refuse")


@test
def census():
    want = sorted([ARGS["scenes"][k]["scene_sequence"] for k in "123"] + list(sn.sound_paths(ARGS).values()))
    check(len(want) == 6, "six expected packages")
    check(sn.census_gate({"content": list(reversed(want)), "maps": []}, want) == [], "exact six must pass")
    check(has(sn.census_gate({"content": want + ["/Game/Other"], "maps": []}, want), "TOUCHED_CENSUS"), "extra pkg")
    check(has(sn.census_gate({"content": want[1:], "maps": []}, want), "TOUCHED_CENSUS"), "missing pkg")
    check(has(sn.census_gate({"content": want, "maps": ["/Game/Map"]}, want), "MAP_DIRTY"), "map dirty")
    check(sn.sound_paths(ARGS)["2"] == "/Game/InfinityStage/Audio/ScenesAudio/Narration/SW_S2_Shrine_Narration_Standin",
          "sound path naming")


# ------------------------------------------------------------------------------------------------------ source scan

FORBIDDEN = [
    (r"LS_InfinityStage_V1Master|V1Master", "Master path"),
    (r"load_asset\([^)]*[Cc]horeo", "Choreo load"),
    (r"save_packages|save_dirty|save_directory|save_all|SaveAll|save_current_level|save_map", "broad/level save"),
    (r"load_level|reload|unload_package|load_map", "level/package reload"),
    (r"open_level_sequence|set_current_time|set_global_time|play_to|force_update", "opens/scrubs Sequencer"),
    (r"set_playback_start|set_playback_end|set_playback_range|set_work_range|set_view_range", "playback range write"),
    (r"end_play_map|request_end_play|quit_editor", "ends PIE / quits"),
    (r"read_hangar_timing|apply_hangar_timing", "Arrival Read/Apply (dirties the map)"),
]


def scan(source):
    hits = []
    code = "\n".join(l for l in source.splitlines() if not l.lstrip().startswith("#"))
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    for pat, what in FORBIDDEN:
        if re.search(pat, code):
            hits.append(what)
    saves = re.findall(r"save_asset\(([^,]+),", code)
    if any(s.strip() not in ("path",) for s in saves):
        hits.append("save_asset on a non-plan path: %r" % saves)
    # module globals: no unreal.<Call>( at column 0
    for line in code.splitlines():
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=\s*unreal\.", line):
            hits.append("unreal object in module globals: %s" % line.strip())
    return hits


@test
def source_scan():
    src = open(TOOL_PATH, encoding="utf-8").read()
    check(scan(src) == [], "tool source scan: %r" % scan(src))
    check("CHOREO_TRACK_CLASS" in src and "!= CHOREO_TRACK_CLASS" not in src and
          "== CHOREO_TRACK_CLASS" in src, "marker walk skips Choreo tracks")
    run_src = open(os.path.join(HERE, "scene_narration_standin_run.py"), encoding="utf-8").read()
    check(scan(run_src) == [], "runner scan %r" % scan(run_src))
    for doctored, what in ((src + "\nx = '/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master'\n", "Master"),
                           (src + "\nunreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)\n", "save"),
                           (src + "\nSEQ = unreal.load_asset('x')\n", "globals"),
                           (src + "\nseq.set_playback_end(5)\n", "playback"),
                           (src + "\nunreal.EditorAssetLibrary.save_asset('/Game/Show', False)\n", "save_asset")):
        check(scan(doctored) != [], "control: doctored source (%s) must be flagged" % what)


# ------------------------------------------------------------------------------------------------------ apply/revert

class FakeSeq(object):
    """Root-track list. lie_remove: remove_track returns False but removes; noop_remove: returns True, removes nothing;
    lie_range: set_range ignored (a lying setter)."""

    def __init__(self, tracks, lie_remove=False, noop_remove=False, lie_range=False):
        self.tracks = copy.deepcopy(tracks)
        self.lie_remove, self.noop_remove, self.lie_range = lie_remove, noop_remove, lie_range

    def list_tracks(self):
        return copy.deepcopy(self.tracks)

    def add_audio_track(self, name):
        self.tracks.append({"cls": "MovieSceneAudioTrack", "name": name, "sections": []})
        return len(self.tracks) - 1

    def add_audio_section(self, track, sound_path, start, end):
        sec = {"start": 0, "end": 1} if self.lie_range else {"start": int(start), "end": int(end)}
        sec.update({"sound": sound_path, "looping": False})
        self.tracks[track]["sections"].append(sec)

    def _remove(self, pred):
        if self.noop_remove:
            return True
        self.tracks = [t for t in self.tracks if not pred(t)]
        return False if self.lie_remove else True

    def remove_matching(self, descriptor):
        key = sn.descriptor_key(descriptor)
        return self._remove(lambda t: sn.descriptor_key(t) == key)

    def remove_new_named(self, before):
        keep = set(sn.descriptor_key(d) for d in before)
        return self._remove(lambda t: t["name"] == sn.TRACK_NAME and sn.descriptor_key(t) not in keep)


BEFORE = [{"cls": "MovieSceneCinematicShotTrack", "name": "Shots", "sections": [{"start": -1, "end": 5270}]},
          {"cls": "MovieSceneSubTrack", "name": "Hangar Fold", "sections": [{"start": 0, "end": 775}]},
          {"cls": "MovieSceneAudioTrack", "name": "Cello", "sections": [{"start": 0, "end": 99, "sound": "/Game/C",
                                                                          "looping": False}]}]
SOUND = "/Game/InfinityStage/Audio/ScenesAudio/Narration/SW_S1_Animals_Narration_Standin"


def row_for(seq_before, start=104, end=979):
    return {"tracks_before": seq_before, "added": sn.narration_descriptor(SOUND, start, end)}


@test
def apply_and_revert_exact():
    for liar in (False, True):
        seq = FakeSeq(BEFORE, lie_remove=liar)
        before, after, bad = sn.apply_scene(seq, SOUND, 104, 979)
        check(bad == [] and len(after) == 4, "apply clean (lie_remove=%s): %r" % (liar, bad))
        row = row_for(before)
        check(sn.drift_since_apply(seq.list_tracks(), row) == [], "no drift right after apply")
        check(sn.revert_scene(seq, row) == [], "revert exact even when remove_track lies (%s)" % liar)
        check(seq.list_tracks() == BEFORE, "revert restores the exact before-list")
    # control: a remove that reports success but removes nothing must be caught by re-listing
    seq = FakeSeq(BEFORE, noop_remove=True)
    before, _a, _b = sn.apply_scene(seq, SOUND, 104, 979)
    check(has(sn.revert_scene(seq, row_for(before)), "REVERT_NOT_EXACT"), "control: no-op remove must fail")
    # control: lying set_range caught at apply read-back; failure-path removal still restores
    seq = FakeSeq(BEFORE, lie_range=True)
    before, _a, bad = sn.apply_scene(seq, SOUND, 104, 979)
    check(has(bad, "APPLY_READBACK"), "control: lying set_range must fail the read-back")
    seq.remove_new_named(before)
    check(seq.list_tracks() == BEFORE, "failure-path removal restores despite the mis-set section")
    # control: drift since apply (someone edited the Cello track) refuses REVERT, touching nothing
    seq = FakeSeq(BEFORE)
    before, _a, _b = sn.apply_scene(seq, SOUND, 104, 979)
    seq.tracks[2]["sections"][0]["end"] = 120
    snapshot = seq.list_tracks()
    check(has(sn.revert_scene(seq, row_for(before)), "STATE_DRIFTED"), "control: drift must refuse revert")
    check(seq.list_tracks() == snapshot, "refused revert touched nothing")
    # control: an existing narration track refuses apply
    seq = FakeSeq(BEFORE + [sn.narration_descriptor(SOUND, 1, 2)])
    _b, _a, bad = sn.apply_scene(seq, SOUND, 104, 979)
    check(has(bad, "NARRATION_TRACK_EXISTS") and len(seq.list_tracks()) == 4, "control: existing narration track")


@test
def record_is_exclusive():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "r.json")
    sn.write_record_exclusive(p, {"a": 1})
    try:
        sn.write_record_exclusive(p, {"a": 2})
        check(False, "control: second exclusive write must raise")
    except FileExistsError:
        check(True, "exclusive")
    check(sn.load_record(p) == {"a": 1}, "first record kept")
    sn.update_record(p, {"a": 3})
    check(sn.load_record(p) == {"a": 3}, "update replaces")


@test
def module_runs_nothing_offline():
    src = open(TOOL_PATH, encoding="utf-8").read()
    check(src.rstrip().endswith("if unreal is not None:\n    main()"), "main gated on unreal")
    check(sn.marker_summary({"1": {"start_frame": 104, "start_s": 4.16}}) == "S1=frame104(4.160s)", "marker summary")


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:   # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    plans = {k: sn.plan_scene(FIX[k], args(), DUR[k]) for k in FIX}
    for k, p in sorted(plans.items()):
        print("FIXTURE S%s land %.4f s -> (a) frame %d (%.3f s) | (b) frame %d | end %d / scene %d | fits=%s overrun %.3f s"
              % (k, p["land_s"], p["frames_by_option"]["land"], p["start_s"], p["frames_by_option"]["land_plus_strike"],
                 p["end_frame"], p["scene_end_frame"], p["fits"], p["overrun_s"]))
    for f in CHECKS["failed"]:
        print("FAIL: " + f)
    print("SCENE_NARRATION_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
