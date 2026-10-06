"""Offline harness for s3_narration_remove.py and scene_audio_import.py (system Python, no Unreal).
Every gate has a failing control: a verifier that cannot fail is not counted as a pass.

Fixtures, cited (the live DRYs re-read all of it):
  S3 root tracks before the 5 Oct narration + the narration track 100-924, sound SW_S3_Shore_Narration_Standin
      scene_narration_standin_record.json scenes.3 [meas 5 Oct, NARR-20261005-143408]
  S6: Scene tick 24000, display 25 fps, playback 0..31.0 s; Hangar Fold sub-section 0..31 s offsets 0; rise 0..31 s
      NEST-S6-NEST-READBACK-20261003-A-response.json key "6" [meas 3 Oct]; Master section still 31 s on 6 Oct
      (Saved/CodexSoftGoods/extend_scene_playback.json segments, "Scene 6" 2074.261-2105.261) [meas]
  S6 land 4.1333 s = 99200 ticks, StrikeAfterLand 5.8667 s: atf_hangar_timing_apply_record.json readback S6 [meas 2 Oct]
  rise display 30 fps: test_scene_narration_standin.py fixture [inf there too]; only feeds the rise playback ticks
  WAV + analysis: the real files on disk (read here).
Run: python test_s3_narration_and_scene_audio.py -> S3NARR_SCENEAUDIO_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.unreal is None, "harness must run without Unreal"
    return mod


sr = _load("s3_narration_remove")
sa = _load("scene_audio_import")
with open(os.path.join(HERE, "scene_audio_import_args.json"), encoding="utf-8") as _h:
    SA_ARGS = json.load(_h)
with open(os.path.join(HERE, "scene_narration_standin_record.json"), encoding="utf-8") as _h:
    NARR_REC = json.load(_h)

CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(items, prefix):
    return any(prefix in x for x in items)


# =====================================================================================================================
# S3 narration remove
# =====================================================================================================================

def section_state(start=100, end=924, sound=sr.EXPECT_SOUND, **over):
    s = {"start": start, "end": end, "cls": "MovieSceneAudioSection", "row_index": 0, "is_active": True,
         "is_locked": False, "pre_roll": 0, "post_roll": 0, "overlap_priority": 0, "completion_mode": "KEEP_STATE",
         "color_tint": [0, 0, 0, 0],
         "channels": [{"name": "PitchMultiplier", "has_default": True, "default": 1.0, "keys": []},
                      {"name": "Volume", "has_default": True, "default": 1.0, "keys": []}],
         "sound": sound, "start_offset": 0, "looping": False, "play_until_finished": False, "suppress_subtitles": False,
         "override_attenuation": False, "attenuation": None}
    s.update(over)
    return s


def s3_states(narration=True, **over):
    """S3 root tracks: the 5 Oct record's tracks_before (+ the narration track last)."""
    out = []
    for i, d in enumerate(NARR_REC["scenes"]["3"]["tracks_before"]):
        out.append({"index": i, "cls": d["cls"], "name": d["name"], "sorting_order": i, "color_tint": [0, 0, 0, 0],
                    "sections": [{"start": s["start"], "end": s["end"], "cls": "X"} for s in d["sections"]]})
    if narration:
        t = {"index": len(out), "cls": "MovieSceneAudioTrack", "name": sr.TRACK_NAME, "sorting_order": len(out),
             "color_tint": [0, 0, 0, 0], "sections": [section_state(**over)]}
        out.append(t)
    return out


class FakeS3(object):
    """In-memory stand-in for s3_narration_remove._LiveSeq. lossy_restore drops a field (a lying setter)."""

    def __init__(self, states, lossy_restore=False):
        self.states = copy.deepcopy(states)
        self.lossy = lossy_restore

    def _reindex(self):
        for i, s in enumerate(self.states):
            s["index"] = i

    def list_states(self):
        return copy.deepcopy(self.states)

    def remove_named(self, name):
        hits = [s for s in self.states if s["name"] == name]
        if len(hits) != 1:
            raise RuntimeError("REMOVE_TARGET_COUNT")
        self.states.remove(hits[0])
        self._reindex()

    def restore(self, target):
        t = copy.deepcopy(target)
        if self.lossy:
            t["sections"][0]["play_until_finished"] = True
        self.states.append(t)
        self._reindex()


def s3_state(mode, **over):
    st = {"mode": mode, "confirm": "%s S3NARR" % mode, "pie": False, "sequencer_blocks": None,
          "census": {"content": [], "maps": []}, "record_exists": False, "record_applied": mode == "REVERT",
          "decided_by": "Gary 6 Oct"}
    st.update(over)
    return st


@test
def s3_gates():
    for m in ("DRY", "APPLY", "REVERT"):
        check(sr.gates(s3_state(m)) == [], "%s clean state passes: %r" % (m, sr.gates(s3_state(m))))
    check(has(sr.gates(s3_state("APPLY", confirm="APPLY NARRATION")), "CONFIRM_MISMATCH"), "control: wrong confirm word")
    check(has(sr.gates(s3_state("APPLY", confirm="DRY S3NARR")), "CONFIRM_MISMATCH"), "control: confirm of another mode")
    check(has(sr.gates(s3_state("DRY", pie=True)), "PIE_OR_SIE_ACTIVE"), "control: PIE")
    check(has(sr.gates(s3_state("APPLY", sequencer_blocks="/Game/.../LS_DevScene_03")), "SEQUENCER_OPEN_ON_TARGET"),
          "control: Sequencer open on S3")
    check(has(sr.gates(s3_state("APPLY", census={"content": ["/Game/X"], "maps": []})), "DIRTY_CENSUS"),
          "control: dirty content")
    check(has(sr.gates(s3_state("APPLY", census={"content": [], "maps": ["/Game/M"]})), "DIRTY_CENSUS"),
          "control: dirty map")
    check(has(sr.gates(s3_state("APPLY", record_exists=True)), "RECORD_EXISTS"), "control: record exists on APPLY")
    check(has(sr.gates(s3_state("APPLY", decided_by="  ")), "NOT_DECIDED"), "control: no decided_by")
    check(has(sr.gates(s3_state("REVERT", record_applied=False)), "NO_APPLIED_RECORD"), "control: REVERT w/o record")
    check(has(sr.gates(s3_state("NUKE")), "MODE_INVALID"), "control: bad mode")


@test
def s3_plan():
    states = s3_states()
    target, ref, warn = sr.plan_remove(states)
    check(ref == [] and warn == [], "S3 as recorded 5 Oct: no refusals/warnings (%r %r)" % (ref, warn))
    check(target is states[-1], "target is the narration track")
    after = sr.expected_after(states, target)
    check([s["name"] for s in after] == [d["name"] for d in NARR_REC["scenes"]["3"]["tracks_before"]],
          "after = the 5 Oct before-list")
    check(has(sr.plan_remove(s3_states(narration=False))[1], "NARRATION_TRACK_COUNT: 0"), "control: no track")
    two = s3_states() + [copy.deepcopy(s3_states()[-1])]
    check(has(sr.plan_remove(two)[1], "NARRATION_TRACK_COUNT: 2"), "control: two tracks")
    check(has(sr.plan_remove(s3_states(sound="/Game/Other/SW_X"))[1], "NARRATION_SOUND"), "control: other sound")
    wrong_cls = s3_states()
    wrong_cls[-1]["cls"] = "MovieSceneEventTrack"
    check(has(sr.plan_remove(wrong_cls)[1], "NARRATION_TRACK_CLASS"), "control: wrong class")
    two_sec = s3_states()
    two_sec[-1]["sections"].append(section_state())
    check(has(sr.plan_remove(two_sec)[1], "NARRATION_SECTION_COUNT"), "control: two sections")
    t, ref, warn = sr.plan_remove(s3_states(start=200, end=1024))
    check(ref == [] and has(warn, "NARRATION_RANGE_MOVED"), "moved range = warning only")
    t, ref, warn = sr.plan_remove(s3_states(start_offset=sr.UNREADABLE))
    check(has(warn, "FIELDS_UNREADABLE") and sr.revert_supported(t) is not None, "unreadable field -> revert unsupported")
    keyed = s3_states()
    keyed[-1]["sections"][0]["channels"][1]["keys"] = [[0, 0.5]]
    check(has(sr.plan_remove(keyed)[2], "CHANNEL_KEYS_PRESENT") and sr.revert_supported(keyed[-1]) is not None,
          "channel keys -> revert unsupported")
    unread_ch = s3_states(channels=sr.UNREADABLE)
    check(sr.revert_supported(unread_ch[-1]) is not None, "unreadable channels -> revert unsupported")


def s3_record(states):
    target, _r, _w = sr.plan_remove(states)
    return {"target": target, "before": states, "after": sr.expected_after(states, target), "backup": "B"}


@test
def s3_remove_and_restore_exact():
    states = s3_states()
    rec = s3_record(states)
    seq = FakeS3(states)
    check(sr.remove_exact(seq, rec) == [], "remove exact")
    check(not any(s["name"] == sr.TRACK_NAME for s in seq.list_states()), "track gone")
    check(len(seq.list_states()) == len(states) - 1, "only one track removed")
    fails, warns = sr.restore_exact(seq, rec)
    check(fails == [] and warns == [], "restore exact, same index (%r %r)" % (fails, warns))
    check(sr.list_keys(seq.list_states()) == sr.list_keys(states), "restored list == before")
    # controls
    seq2 = FakeS3(states)
    seq2.states.append({"index": 99, "cls": "MovieSceneAudioTrack", "name": "Someone else", "sections": []})
    check(sr.remove_exact(seq2, rec) == ["STATE_CHANGED_SINCE_PLAN"], "control: state changed between plan and remove")
    seq3 = FakeS3(rec["after"])
    seq3.states.append({"index": 5, "cls": "MovieSceneAudioTrack", "name": "Scene Score", "sections": []})
    f, _w = sr.restore_exact(seq3, rec)
    check(has(f, "STATE_DRIFTED_SINCE_APPLY"), "control: drift since apply refuses restore")
    seq4 = FakeS3(rec["after"], lossy_restore=True)
    f, _w = sr.restore_exact(seq4, rec)
    check(has(f, "RESTORE_NOT_EXACT"), "control: a lying setter is caught by the re-read")
    keyed = s3_states()
    keyed[-1]["sections"][0]["channels"][1]["keys"] = [[0, 0.5]]
    rk = s3_record(keyed)
    f, _w = sr.restore_exact(FakeS3(rk["after"]), rk)
    check(has(f, "CHANNEL_KEYS_RECORDED"), "control: keyed channels refuse REVERT")
    # order-only difference is reported, not failed
    mid = s3_states()
    mid.insert(1, mid.pop())                      # narration was NOT last
    for i, s in enumerate(mid):
        s["index"] = i
    rm = s3_record(mid)
    sq = FakeS3(mid)
    check(sr.remove_exact(sq, rm) == [], "remove from the middle")
    f, w = sr.restore_exact(sq, rm)
    check(f == [] and has(w, "TRACK_ORDER"), "restore appends: order warning, not failure (%r %r)" % (f, w))


@test
def s3_census_and_records():
    check(sr.census_gate({"content": [sr.SEQ], "maps": []}, [sr.SEQ]) == [], "census exactly S3")
    check(has(sr.census_gate({"content": [sr.SEQ, "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"], "maps": []},
                             [sr.SEQ]), "TOUCHED_CENSUS"), "control: S1 dirtied too")
    check(has(sr.census_gate({"content": [], "maps": []}, [sr.SEQ]), "TOUCHED_CENSUS"), "control: S3 not dirtied")
    check(has(sr.census_gate({"content": [sr.SEQ], "maps": ["/Game/M"]}, [sr.SEQ]), "MAP_DIRTY"), "control: map dirty")
    d = tempfile.mkdtemp()
    p = os.path.join(d, "r.json")
    sr.write_record_exclusive(p, {"a": 1})
    try:
        sr.write_record_exclusive(p, {"a": 2})
        check(False, "control: second exclusive write must raise")
    except FileExistsError:
        check(True, "exclusive")
    check(sr.load_record(p) == {"a": 1}, "first record kept")


# =====================================================================================================================
# Scene audio import
# =====================================================================================================================

TICK = 24000.0
S6_FACTS = {"scene_res": TICK, "fps": 25.0, "playback": [0, 775], "rise_res": TICK, "rise_lower_tick": 0,
            "rise_upper_tick": int(31 * TICK), "section_start_tick": 0, "section_end_tick": int(31 * TICK),
            "start_offset_tick": 0, "end_offset_tick": 0, "land_tick_inner": 99200, "strike_after_land_s": 5.8667,
            "scene_label": "Scene 6 — External Sound"}
S6_ROW = SA_ARGS["scenes"]["6"]


def sa_args(**over):
    a = copy.deepcopy(SA_ARGS)
    a.update(over)
    return a


def s6_facts(**over):
    f = copy.deepcopy(S6_FACTS)
    f.update(over)
    return f


@test
def sa_validate_args():
    check(sa.validate_args(SA_ARGS) == [], "real args valid: %r" % sa.validate_args(SA_ARGS))
    a = sa_args()
    a["scenes"]["6"]["markers"][0]["label"] = "GO 12 HOLD swell"
    check(has(sa.validate_args(a), "MARKER_IS_A_GO_LABEL"), "control: a GO-parsable label")
    a = sa_args()
    a["scenes"]["6"]["markers"][1]["label"] = a["scenes"]["6"]["markers"][0]["label"]
    check(has(sa.validate_args(a), "LABELS_NOT_UNIQUE"), "control: duplicate labels")
    a = sa_args()
    a["scenes"]["6"]["markers"][3]["track_s"] = 188.0
    check(has(sa.validate_args(a), "MARKER_TIME_OUTSIDE_CLIP"), "control: marker at clip end")
    a = sa_args()
    a["scenes"]["6"]["markers"][2]["source"] = {"kind": "vibes"}
    check(has(sa.validate_args(a), "MARKER_SOURCE_KIND"), "control: unknown source kind")
    a = sa_args()
    del a["scenes"]["6"]["rise"]
    check(has(a and sa.validate_args(a), "MISSING_RISE"), "control: missing rise")
    a = sa_args()
    a["scenes"]["6"]["scene_sequence"] = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
    check(has(sa.validate_args(a), "TARGET_NOT_A_SCENE"), "control: Master as target")
    check(has(sa.validate_args(sa_args(dest_folder="Score")), "DEST_FOLDER_INVALID"), "control: bad folder")
    check(has(sa.validate_args(sa_args(scenes={})), "NO_SCENES"), "control: no scenes")
    check(SA_ARGS["dest_folder"] == "/Game/InfinityStage/Audio/ScenesAudio/Score", "dest folder per brief")
    check(SA_ARGS["track_name"] == "Scene Score", "track name per brief")
    check(sorted(SA_ARGS["scenes"]) == ["6"], "S3 NOT planned in the args (Gary walks S3 first)")
    check([m["label"] for m in S6_ROW["markers"]] == ["S6 swell 0:50", "S6 trough 2:00", "S6 climax 2:35",
                                                      "S6 drop 2:54"], "marker labels per brief")


@test
def sa_inputs_real_wav():
    facts, ref = sa.check_inputs(SA_ARGS, PROJECT)
    check(ref == [], "real S6 WAV passes: %r" % ref)
    f = facts.get("6", {})
    check(f.get("channels") == 2 and f.get("rate") == 44100 and f.get("sample_width") == 2,
          "16-bit 44.1 kHz stereo: %r" % {k: f.get(k) for k in ("channels", "rate", "sample_width")})
    check(abs(f.get("duration_s", 0) - 188.0) < 1e-6, "188.0 s")
    a = sa_args()
    a["scenes"]["6"]["sha256"] = "0" * 64
    check(has(sa.check_inputs(a, PROJECT)[1], "WAV_SHA_MISMATCH"), "control: sha")
    a = sa_args()
    a["scenes"]["6"]["duration_s"] = 187.9
    check(has(sa.check_inputs(a, PROJECT)[1], "WAV_DURATION_MISMATCH"), "control: duration")
    a = sa_args()
    a["scenes"]["6"]["wav"] = "DerivedAssets/Audio/Scenes_20261006/f32/S06_The_Void_Live_Stereo_f32.wav"
    check(has(sa.check_inputs(a, PROJECT)[1], "WAV_NOT_PCM") or has(sa.check_inputs(a, PROJECT)[1], "WAV_SHA_MISMATCH"),
          "control: the f32 original is refused")
    a = sa_args()
    a["scenes"]["6"]["wav"] = "DerivedAssets/Audio/Scenes_20261006/nope.wav"
    check(has(sa.check_inputs(a, PROJECT)[1], "WAV_MISSING"), "control: missing file")


def analysis():
    with open(os.path.join(PROJECT, *S6_ROW["analysis"].split("/")), encoding="utf-8") as h:
        return json.load(h)


@test
def sa_markers_from_analysis():
    an = analysis()
    check(sa.verify_markers(S6_ROW, an, S6_ROW["sha256"]) == [], "chosen markers verify: %r"
          % sa.verify_markers(S6_ROW, an, S6_ROW["sha256"]))
    row = copy.deepcopy(S6_ROW)
    row["markers"][2]["track_s"] = 155.0                        # the nominal 2:35, not an analysis event
    check(has(sa.verify_markers(row, an, S6_ROW["sha256"]), "MARKER_NOT_A_MAJOR_CHANGE"), "control: nominal time")
    row = copy.deepcopy(S6_ROW)
    row["markers"][0]["track_s"] = 45.604                       # a major change, but not the intensity onset
    check(has(sa.verify_markers(row, an, S6_ROW["sha256"]), "MARKER_NOT_THE_ONSET"), "control: onset kind")
    row = copy.deepcopy(S6_ROW)
    row["markers"][0]["source"]["threshold"] = 0.01           # the 46.4 s blip would then be the onset
    check(has(sa.verify_markers(row, an, S6_ROW["sha256"]), "MARKER_NOT_THE_ONSET"), "control: onset threshold")
    s3sha = "46cc34c76e14934a4ca2fde375da1e6f1c99d9d62c75526d17658b13a7aba63e"
    check(has(sa.verify_markers(S6_ROW, an, s3sha), "ANALYSIS_NOT_OF_THIS_WAV"), "control: analysis of another WAV")
    row = copy.deepcopy(S6_ROW)
    row["duration_s"] = 246.9
    check(has(sa.verify_markers(row, an, S6_ROW["sha256"]), "ANALYSIS_DURATION"), "control: duration")
    changes = sorted(round(p["timeSeconds"], 4) for p in an["majorChangeProposals"])
    for t in (115.9605, 155.8523, 173.7781):
        check(t in changes, "%.4f is a major change" % t)


@test
def sa_plan_s6_as_recorded_overruns():
    p = sa.plan_scene(s6_facts(), sa_args(), S6_ROW)
    check(abs(p["land_s"] - 4.133333) < 1e-5, "land 4.1333 s")
    check(p["start_frame"] == 104 and abs(p["start_s"] - 4.16) < 1e-9, "start frame 104 (4.16 s)")
    check(p["clip_frames"] == 4700 and p["end_frame"] == 4804, "188 s = 4700 frames -> end 4804")
    check(not p["fits"] and has(p["refusals"], "OVERRUN"), "S6 at 31 s refuses OVERRUN")
    check(abs(p["needed_end_s"] - 192.16) < 1e-9 and abs(p["overrun_s"] - 161.16) < 1e-6,
          "needs 192.16 s, short by 161.16 s (%r %r)" % (p["needed_end_s"], p["overrun_s"]))
    sug = p.get("extend_mode_suggestion") or {}
    check(sug.get("scene_label") == "Scene 6 — External Sound" and sug.get("new_end_s") == 192.16
          and sug.get("dry_run") is True, "extend suggestion: %r" % sug)


@test
def sa_plan_fit_boundary_and_markers():
    exact = sa.plan_scene(s6_facts(playback=[0, 4804]), sa_args(), S6_ROW)
    check(exact["fits"] and exact["refusals"] == [], "exactly 4804 fits: %r" % exact["refusals"])
    short = sa.plan_scene(s6_facts(playback=[0, 4803]), sa_args(), S6_ROW)
    check(not short["fits"] and has(short["refusals"], "OVERRUN"), "control: one frame short refuses")
    got = [(m["label"], m["display_frame"], m["tick"]) for m in exact["markers"]]
    want = [("S6 score in (land)", 104, 99840), ("S6 swell 0:50", 1374, 1319040), ("S6 trough 2:00", 3003, 2882880),
            ("S6 climax 2:35", 4000, 3840000), ("S6 drop 2:54", 4448, 4270080)]
    check(got == want, "marker frames %r" % got)
    check(all(abs(m.get("snap_error_s", 0)) <= 0.02 + 1e-9 for m in exact["markers"]), "snap <= half a frame")
    strike = sa.plan_scene(s6_facts(playback=[0, 6000]), sa_args(start_option="land_plus_strike"), S6_ROW)
    check(strike["start_frame"] == 251, "option b frame 251 (10.0 s): %r" % strike["start_frame"])
    nostrike = sa.plan_scene(s6_facts(strike_after_land_s=None), sa_args(start_option="land_plus_strike"), S6_ROW)
    check(has(nostrike["refusals"], "STRIKE_AFTER_LAND_UNKNOWN"), "control: option b without the Arrival")
    rate = sa.plan_scene(s6_facts(section_end_tick=int(15.5 * TICK)), sa_args(), S6_ROW)
    check(has(rate["refusals"], "PLAY_RATE_UNVERIFIED"), "control: half-length rise section (rate 2?)")
    late = sa.plan_scene(s6_facts(playback=[0, 100]), sa_args(), S6_ROW)
    check(has(late["refusals"], "START_AFTER_SCENE_END"), "control: land after the Scene end")


@test
def sa_existing_audio():
    void_nested = {"sequence": "/Game/.../LS_Void", "depth": 1, "track": "Audio",
                   "sound": "/Game/InfinityStage/Audio/ScenesAudio/The_Void_Scene", "scene_span": [0.0, 15.0]}
    before_land = dict(void_nested, scene_span=[0.0, 4.0])
    after_end = dict(void_nested, scene_span=[192.16, 300.0])
    unbounded = dict(void_nested, scene_span=[None, None])
    check(sa.overlapping_audio([void_nested], 4.16, 192.16) == [void_nested], "nested Void over the span -> listed")
    check(sa.overlapping_audio([before_land, after_end], 4.16, 192.16) == [], "touching/outside spans: not overlapping")
    check(sa.overlapping_audio([unbounded], 4.16, 192.16) == [unbounded], "control: unbounded counts as overlapping")


class FakeScene(object):
    """In-memory stand-in for scene_audio_import._LiveSeq. drop_marker: a lying add_marker."""

    def __init__(self, tracks, markers, drop_marker=False):
        self.tracks = copy.deepcopy(tracks)
        self.markers = copy.deepcopy(markers)
        self.drop = drop_marker

    def list_tracks(self):
        return copy.deepcopy(self.tracks)

    def list_markers(self):
        return copy.deepcopy(self.markers)

    def add_audio_track(self, name):
        t = {"cls": "MovieSceneAudioTrack", "name": name, "sections": []}
        self.tracks.append(t)
        return t

    def add_audio_section(self, track, sound, start, end):
        track["sections"].append({"start": int(start), "end": int(end), "sound": sound, "looping": False})

    def add_marker(self, tick, label):
        if not self.drop:
            self.markers.append({"tick": int(tick), "label": label})

    def delete_marker(self, i):
        del self.markers[i]

    def remove_matching_track(self, d):
        k = sa.descriptor_key(d)
        self.tracks = [t for t in self.tracks if sa.descriptor_key(t) != k]


S6_TRACKS = [{"cls": "MovieSceneCinematicShotTrack", "name": "Shots", "sections": [{"start": 0, "end": 375}]},
             {"cls": "MovieSceneSubTrack", "name": "Hangar Fold", "sections": [{"start": 0, "end": 775}]}]
S6_MARKERS = [{"tick": 0, "label": "GO 60 HOLD Void"}]          # fixture: an existing marker must survive


def s6_row_record(plan, sound):
    return {"tracks_before": S6_TRACKS, "markers_before": S6_MARKERS,
            "added_track": sa.track_descriptor("Scene Score", sound, plan["start_frame"], plan["end_frame"]),
            "added_markers": [{"tick": m["tick"], "label": m["label"]} for m in plan["markers"]]}


@test
def sa_apply_and_revert_exact():
    plan = sa.plan_scene(s6_facts(playback=[0, 4900]), sa_args(), S6_ROW)
    sound = sa.sound_paths(SA_ARGS)["6"]
    check(sound == "/Game/InfinityStage/Audio/ScenesAudio/Score/SW_S6_The_Void_Live", "sound path %r" % sound)
    seq = FakeScene(S6_TRACKS, S6_MARKERS)
    before, bad = sa.apply_scene(seq, "Scene Score", sound, plan)
    check(bad == [], "apply exact: %r" % bad)
    check(len(seq.tracks) == 3 and len(seq.markers) == 6, "one track + five markers added")
    row = s6_row_record(plan, sound)
    check(sa.drift_since_apply(seq.list_tracks(), seq.list_markers(), row) == [], "no drift right after apply")
    check(sa.revert_scene(seq, row) == [], "revert exact")
    check(seq.tracks == S6_TRACKS and seq.markers == S6_MARKERS, "back to the before-state, GO marker kept")
    # controls
    lying = FakeScene(S6_TRACKS, S6_MARKERS, drop_marker=True)
    check(has(sa.apply_scene(lying, "Scene Score", sound, plan)[1], "APPLY_READBACK_MARKERS"),
          "control: a dropped marker is caught")
    exists = FakeScene(S6_TRACKS + [{"cls": "MovieSceneAudioTrack", "name": "Scene Score", "sections": []}], S6_MARKERS)
    check(has(sa.apply_scene(exists, "Scene Score", sound, plan)[1], "TRACK_EXISTS"), "control: track exists")
    clash = FakeScene(S6_TRACKS, S6_MARKERS + [{"tick": 5, "label": "S6 drop 2:54"}])
    check(has(sa.apply_scene(clash, "Scene Score", sound, plan)[1], "MARKER_LABEL_EXISTS"), "control: label clash")
    seq2 = FakeScene(S6_TRACKS, S6_MARKERS)
    sa.apply_scene(seq2, "Scene Score", sound, plan)
    seq2.markers.append({"tick": 1, "label": "someone's note"})
    check(has(sa.revert_scene(seq2, row), "MARKERS_CHANGED_SINCE_APPLY"), "control: marker added since apply")
    seq3 = FakeScene(S6_TRACKS, S6_MARKERS)
    sa.apply_scene(seq3, "Scene Score", sound, plan)
    seq3.tracks[0]["sections"][0]["end"] = 400
    check(has(sa.revert_scene(seq3, row), "OTHER_TRACKS_CHANGED_SINCE_APPLY"), "control: other track moved")
    seq4 = FakeScene(S6_TRACKS, S6_MARKERS)
    sa.apply_scene(seq4, "Scene Score", sound, plan)
    seq4.tracks[-1]["sections"][0]["start"] = 105
    check(has(sa.revert_scene(seq4, row), "OUR_TRACK_COUNT: 0"), "control: our section moved since apply")


def sa_state(mode, **over):
    st = {"mode": mode, "confirm": "%s SCENEAUDIO" % mode, "pie": False, "sequencer_blocks": None,
          "census": {"content": [], "maps": []}, "records_exist": [], "records_not_applied": [],
          "decided_by": "Gary", "assets_exist": []}
    st.update(over)
    return st


@test
def sa_gates_and_census():
    for m in ("DRY", "APPLY", "REVERT"):
        check(sa.live_gates(sa_state(m)) == [], "%s clean passes" % m)
    check(has(sa.live_gates(sa_state("APPLY", confirm="APPLY NARRATION")), "CONFIRM_MISMATCH"), "control: confirm")
    check(has(sa.live_gates(sa_state("DRY", pie=True)), "PIE_OR_SIE"), "control: PIE")
    check(has(sa.live_gates(sa_state("APPLY", sequencer_blocks="LS_DevScene_06")), "SEQUENCER_OPEN"), "control: seq")
    check(has(sa.live_gates(sa_state("APPLY", census={"content": ["/Game/A"], "maps": []})), "DIRTY_CENSUS"),
          "control: dirty")
    check(has(sa.live_gates(sa_state("APPLY", records_exist=["r"])), "RECORD_EXISTS"), "control: record")
    check(has(sa.live_gates(sa_state("APPLY", assets_exist=["/Game/x"])), "ASSET_EXISTS"), "control: asset exists")
    check(has(sa.live_gates(sa_state("APPLY", decided_by="")), "NOT_DECIDED"), "control: decided_by")
    check(has(sa.live_gates(sa_state("REVERT", records_not_applied=["r"])), "NO_APPLIED_RECORD"), "control: revert")
    want = sorted(["/Game/InfinityStage/Audio/ScenesAudio/Score/SW_S6_The_Void_Live",
                   "/Game/InfinityStage/Dev/Sequences/LS_DevScene_06"])
    check(sa.census_gate({"content": want, "maps": []}, want) == [], "census = sound + S6 exactly")
    check(has(sa.census_gate({"content": want + [sa.SHOW_PATH], "maps": []}, want), "TOUCHED_CENSUS"),
          "control: Show dirtied")
    check(has(sa.census_gate({"content": want[1:], "maps": []}, want), "TOUCHED_CENSUS"), "control: sound not dirty")
    check(has(sa.census_gate({"content": want, "maps": ["/Game/L"]}, want), "MAP_DIRTY"), "control: map")


@test
def sa_go_report():
    plan = sa.plan_scene(s6_facts(playback=[0, 4900]), sa_args(), S6_ROW)
    marks = [{"label": "GO 61 HOLD", "scene_s": 50.0, "sequence": "S6"},
             {"label": "GO 62 PASS", "scene_s": 60.0, "sequence": "S6"},
             {"label": "GO 63", "scene_s": 1.0, "sequence": "S6"},
             {"label": "S6 swell 0:50", "scene_s": 54.96, "sequence": "S6"}]
    g = sa.go_report(marks, plan)
    check([x["label"] for x in g] == ["GO 61 HOLD", "GO 62 PASS", "GO 63"], "only GO labels parsed")
    check([x["pauses_audio"] for x in g] == [True, False, False], "HOLD inside pauses; PASS and before-start don't")
    for m in plan["markers"]:
        check(sa.parse_go_label(m["label"]) is None, "our marker %r is not a GO label" % m["label"])


FORBIDDEN = [r"save_dirty_packages", r"save_current_level", r"save_map", r"load_map", r"load_level",
             r"\.reload\(", r"end_play_map", r"request_end_play", r"quit_editor", r"set_playback_end",
             r"set_playback_start", r"open_level_sequence", r"set_current_time", r"LS_InfinityStage_V1Master\"\)",
             r"save_packages", r"delete_marked_frames\("]


def scan(path):
    src = open(path, encoding="utf-8").read()
    return src, [p for p in FORBIDDEN if re.search(p, src)]


@test
def source_scans():
    for path, stop_word in ((os.path.join(HERE, "s3_narration_remove.py"), "S3NARR_STOPPED"),
                            (os.path.join(HERE, "scene_audio_import.py"), "SCENEAUDIO_STOPPED")):
        src, hits = scan(path)
        check(hits == [], "%s forbidden calls: %r" % (os.path.basename(path), hits))
        check(src.rstrip().endswith("if unreal is not None:\n    main()"), "%s main gated on unreal" % path)
        check(stop_word in src, "%s stop marker" % path)
        check("save_asset(" in src, "%s saves by asset" % path)
        top = [l for l in src.splitlines() if re.match(r"^[A-Z_]+ = unreal\.", l)]
        check(top == [], "%s no unreal objects in module globals: %r" % (path, top))
    src = open(os.path.join(HERE, "s3_narration_remove.py"), encoding="utf-8").read()
    check(src.count("save_asset(") == 1 and "save_asset(SEQ" in src, "S3 tool saves only LS_DevScene_03")
    check("Narration/SW_S3_Shore_Narration_Standin" in src and "delete_asset" not in src,
          "S3 tool never deletes the SoundWave")
    # the scanner itself can fail
    d = tempfile.mkdtemp()
    bad = os.path.join(d, "bad.py")
    open(bad, "w").write("unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)\n")
    check(scan(bad)[1] != [], "control: scanner catches save_dirty_packages")


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:   # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    p = sa.plan_scene(s6_facts(), sa_args(), S6_ROW)
    print("FIXTURE S6 land %.4f s -> frame %d (%.3f s) | end %d (%.3f s) | scene end %d (%.3f s) | fits=%s | "
          "needs >= %.3f s" % (p["land_s"], p["start_frame"], p["start_s"], p["end_frame"], p["end_s"],
                               p["playback"][1], p["scene_end_s"], p["fits"], p["needed_end_s"]))
    for m in p["markers"]:
        print("  marker %-20s track %8.4f s -> frame %5d  scene %8.3f s" % (m["label"], m["track_s"],
                                                                           m["display_frame"], m["scene_s"]))
    for f in CHECKS["failed"]:
        print("FAIL: " + f)
    print("S3NARR_SCENEAUDIO_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
