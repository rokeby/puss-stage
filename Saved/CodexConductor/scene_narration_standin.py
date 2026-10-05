"""SCENE NARRATION STAND-IN: import three stand-in narration WAVs and place each in its Scene sequence (S1-S3),
starting after that Scene's hangar has LANDED. 5 Oct, offline-written, NEVER RUN IN UNREAL.

Gary asked for it through his directing session (via the conductor). The file -> Scene mapping (Animals->S1,
Shrine->S2, Shore->S3) is INFERRED from the file names and NOT yet confirmed by Gary: it lives in
scene_narration_standin_args.json, and APPLY refuses until args.mapping_confirmed_by is filled in.

Tiers per claim: [decl] declaration-proven (header/source we can read, cited), [prec] in-repo precedent call (cited),
[meas] an earlier run's read-back record (cited), [inf] inferred (why stated).

LAND TIME (per Scene, read live every run, never from the records below):
  * The rise LS_S<n>_HangarRise is a sub-section of the Scene sequence; AInfinityStageArrival finds it by SEQUENCE on any
    sub-track [decl InfinityStageArrival.cpp:39-57 FindMotionSection], and so does this tool.
  * LAND = the root pitch channel's LAST key [decl InfinityStageArrival.h:55-57 "Landing time read from the root pitch
    channel's last key"; .cpp:662]. Root = binding "S<n> Hangar Root", 3D transform channel index 4 [prec
    hangar_heave.py:12-15 citing InfinityStageArrival.cpp:333-345]. The heave (if ever applied) keeps the last key
    [prec hangar_heave.py:31-34].
  * inner -> Scene time inverts the Arrival's own map: inner = innerPlaybackLower + StartFrameOffset +
    (outer - sectionStart) x playRate, across tick resolutions [decl InfinityStageArrival.cpp:1029-1049]. The play rate
    (MovieSceneTimeWarpVariant) is opaque to Python [meas NEST-S2-NEST-READBACK-20261003-A-response.json prints it as
    "{}"], so the tool REFUSES unless the section's outer length equals the inner span (rate 1) [inf: a trimmed section
    would also fail this gate - conservative].
  * Option (a) "land" (default): start = first Scene display frame at or after the land key (ceil).
    Option (b) "land_plus_strike": land + the S<n> Arrival's persisted HangarTiming.StrikeAfterLandSeconds
    [decl InfinityStageArrival.h:35-38, not Transient]. The persisted value is what ATF apply last wrote
    [meas atf_hangar_timing_apply_record.json readback 5.8667083 s]; it is NOT recomputed from the light keys here [inf:
    ReadHangarTiming would recompute it but writes actor properties, i.e. dirties the map - so never called].
  * Expected (not authoritative) from records: land 4.1333 s rise time for S1-S3 [meas atf readback land_seconds];
    Hangar Fold sub-section at Scene 0.0 s, offsets 0, rise playback 0-31 s [meas NEST-S2-NEST-READBACK 3 Oct];
    Scene playback S1 0-210.8 s @25, S2 0-31.0 s @25, S3 0-260.0 s @24 [meas same file]. The live DRY confirms.

WHAT APPLY WRITES: three NEW SoundWave assets (AssetImportTask, automated, replace_existing False [prec
hangar_exit_doors.py:749-766]) in /Game/InfinityStage/Audio/ScenesAudio/Narration, and in each Scene sequence ONE root
MovieSceneAudioTrack named "Narration (stand-in)" with ONE section [decl MovieSceneSequenceExtensions.h:79 AddTrack;
MovieSceneTrackExtensions.h:33,72 SetDisplayName/AddSection; MovieSceneAudioSection.h:38 SetSound;
MovieSceneSectionExtensions.h:145 SetRange in display frames]. Looping and Play-Until-Finished are set False and read
back [decl MovieSceneAudioSection.h:101-133]. The Scene's playback range is NEVER changed: an overrunning clip is cut by
the Scene end and reported (Gary decides). Section end policy args.section_end: "clip_length" (default, the section
spans the whole clip, so extending the Scene later plays the rest) or "scene_end" (trimmed to the playback end).

GO HOLDS: a HOLD stops Sequencer audio while the show holds [prec Saved/CodexCueing/cue_list_tool.py:10-12 lint]. DRY
lists GO markers in the Scene and its nested sequences (not Choreo tracks), mapped to Scene time, and flags holds inside
each narration window. S3 is DeclaredUnpausable (holds refused in performance mode) [prec
scene_external_sound_apply.py:5]; the Show's ExternalSound value is read and reported.

Modes via scene_narration_standin_run.py <- scene_narration_standin_args.json: DRY | APPLY | REVERT, confirm
"<MODE> NARRATION". Markers: SCENE_NARRATION_DRY_OK / SCENE_NARRATION_APPLY_OK|run=..|S1=frame..|S2=..|S3=..|
overruns=.. / SCENE_NARRATION_REVERT_OK, or SCENE_NARRATION_STOPPED|run=..|reason=...
Never: Save All, level save, reload, open or scrub Sequencer, load the Master, touch Choreo, end PIE; no unreal objects
in module globals. Importing without `unreal` runs nothing (test_scene_narration_standin.py).
"""
import datetime
import hashlib
import json
import math
import os
import shutil
import wave

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "scene_narration_standin"
TRACK_NAME = "Narration (stand-in)"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                     # scene_external_sound_apply.py:13
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # hangar_heave.py:93
ROOT_BINDING = "S%d Hangar Root"
ROOT_CHANNEL_INDEX = 4                                                            # hangar_heave.py:112
ROOT_CHANNEL_NAME = "Rotation.Y"
ARRIVAL_LABEL = "S%d Arrival"
RECORD_NAME = "scene_narration_standin_record.json"
DRY_NAME = "scene_narration_standin_dry.json"
ARGS_NAME = "scene_narration_standin_args.json"
CHOREO_TRACK_CLASS = "MovieSceneInfinityChoreoTrack"   # Plugins/.../MovieSceneInfinityChoreoTrack.h:32 - never walked
START_OPTIONS = ("land", "land_plus_strike")
SECTION_END_POLICIES = ("clip_length", "scene_end")
FRAME_EPS = 1.0e-6        # frames: ceil tolerance against float noise only (a real tick late still rounds up)
FIT_EPS_S = 1.0e-6
DURATION_TOL_S = 0.02     # imported SoundWave duration vs the WAV header
RATE_TOL_S = 0.5 / 24000.0 * 4  # section-length vs inner-span tolerance (a few ticks)


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: args, inputs, maths
# =====================================================================================================================

def validate_args(args):
    """Refusals for the args file itself (pure)."""
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    if args.get("start_option") not in START_OPTIONS:
        r.append("START_OPTION_INVALID: %r, want one of %s" % (args.get("start_option"), START_OPTIONS))
    if args.get("section_end", "clip_length") not in SECTION_END_POLICIES:
        r.append("SECTION_END_INVALID: %r" % args.get("section_end"))
    folder = str(args.get("dest_folder") or "")
    if not folder.startswith("/Game/"):
        r.append("DEST_FOLDER_INVALID: %r" % folder)
    scenes = args.get("scenes") or {}
    if sorted(scenes) != ["1", "2", "3"]:
        r.append("SCENES_NOT_S1_S3: %r" % sorted(scenes))
    names = []
    for key, row in sorted(scenes.items()):
        for field in ("wav", "sha256", "duration_s", "asset_name", "scene_sequence", "rise"):
            if field not in row:
                r.append("SCENE_%s_MISSING_%s" % (key, field.upper()))
        names.append(row.get("asset_name"))
        if "Master" in str(row.get("scene_sequence", "")) or "Choreo" in str(row.get("scene_sequence", "")):
            r.append("SCENE_%s_TARGET_NOT_A_SCENE: %r" % (key, row.get("scene_sequence")))
    if len(set(names)) != len(names):
        r.append("ASSET_NAMES_NOT_UNIQUE")
    return r


def wav_facts(path):
    """sha256 + header facts of a PCM WAV (pure; stdlib wave)."""
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    w = wave.open(path, "rb")
    try:
        frames, rate = w.getnframes(), w.getframerate()
        return {"sha256": digest, "channels": w.getnchannels(), "rate": rate, "sample_width": w.getsampwidth(),
                "frames": frames, "duration_s": frames / float(rate)}
    finally:
        w.close()


def check_inputs(args, project_dir):
    """Per-scene input facts and refusals: file present, sha256 equal, header duration equal to the args'."""
    facts, r = {}, []
    for key, row in sorted((args.get("scenes") or {}).items()):
        path = os.path.join(project_dir, *str(row["wav"]).replace("\\", "/").split("/"))
        if not os.path.isfile(path):
            r.append("WAV_MISSING_S%s: %s" % (key, path))
            continue
        f = wav_facts(path)
        f["path"] = path
        facts[key] = f
        if f["sha256"] != str(row["sha256"]).lower():
            r.append("WAV_SHA_MISMATCH_S%s: %s != args %s" % (key, f["sha256"][:12], str(row["sha256"])[:12]))
        if abs(f["duration_s"] - float(row["duration_s"])) > 0.002:
            r.append("WAV_DURATION_MISMATCH_S%s: header %.4f s, args %.4f s" % (key, f["duration_s"], row["duration_s"]))
    return facts, r


def rate_of(num, den):
    return float(num) / float(den)


def inner_to_outer_tick(inner_tick, inner_res, inner_lower_tick, start_offset_tick, section_start_outer_tick,
                        outer_res, play_rate=1.0):
    """Inverse of AInfinityStageArrival::MapOuterToInnerTime [decl InfinityStageArrival.cpp:1044-1048]:
    inner = innerLower + StartFrameOffset + T_in<-out((outer - sectionStart) x rate)
    => outer = sectionStart + T_out<-in(inner - innerLower - StartFrameOffset) / rate. Ticks; float result."""
    if play_rate <= 0:
        raise PlanError("PLAY_RATE_NONPOSITIVE: %r" % play_rate)
    inner_offset = float(inner_tick) - float(inner_lower_tick) - float(start_offset_tick)
    return float(section_start_outer_tick) + inner_offset * (float(outer_res) / float(inner_res)) / float(play_rate)


def rate_one_gate(section_start_s, section_end_s, inner_lower_s, inner_upper_s, start_offset_s, end_offset_s):
    """Refusal text or None: the section's outer length must equal its inner span (rate 1). Python cannot read
    MovieSceneTimeWarpVariant [meas NEST readback prints '{}'], so this is the only check available."""
    if section_end_s is None or section_start_s is None:
        return "SECTION_UNBOUNDED: the rise sub-section has no start or end frame"
    outer = section_end_s - section_start_s
    inner = (inner_upper_s - end_offset_s) - (inner_lower_s + start_offset_s)
    if abs(outer - inner) > RATE_TOL_S:
        return ("PLAY_RATE_UNVERIFIED: section %.4f s vs inner span %.4f s (rate != 1 or a trimmed section; the land "
                "map assumes rate 1 - refused)" % (outer, inner))
    return None


def ceil_frame(outer_tick, outer_res, fps):
    """First display frame at or after a tick time (float-noise tolerant only)."""
    frames = float(outer_tick) * float(fps) / float(outer_res)
    return int(math.ceil(frames - FRAME_EPS))


def plan_scene(facts, args, duration_s):
    """facts (pure data from _gather_scene / fixtures) -> plan dict with start/end frames and fit.
    facts keys: scene_res, fps, playback (display frames [start, end)), rise_res, rise_lower_tick, rise_upper_tick,
    section_start_tick, section_end_tick, start_offset_tick, end_offset_tick, land_tick_inner, strike_after_land_s."""
    refusals, warnings = [], []
    sres, fps = float(facts["scene_res"]), float(facts["fps"])
    rres = float(facts["rise_res"])
    gate = rate_one_gate(
        facts["section_start_tick"] / sres if facts.get("section_start_tick") is not None else None,
        facts["section_end_tick"] / sres if facts.get("section_end_tick") is not None else None,
        facts["rise_lower_tick"] / rres, facts["rise_upper_tick"] / rres,
        facts["start_offset_tick"] / rres, facts.get("end_offset_tick", 0) / rres)
    if gate:
        refusals.append(gate)
        return {"refusals": refusals, "warnings": warnings}
    land_outer = inner_to_outer_tick(facts["land_tick_inner"], rres, facts["rise_lower_tick"],
                                     facts["start_offset_tick"], facts["section_start_tick"], sres)
    land_s = land_outer / sres
    strike = facts.get("strike_after_land_s")
    option_ticks = {"land": land_outer}
    if strike is not None:
        option_ticks["land_plus_strike"] = land_outer + float(strike) * sres
    option = args["start_option"]
    if option not in option_ticks:
        refusals.append("STRIKE_AFTER_LAND_UNKNOWN: option (b) needs the S Arrival's StrikeAfterLandSeconds")
        return {"refusals": refusals, "warnings": warnings, "land_s": land_s}
    frames = {k: ceil_frame(v, sres, fps) for k, v in option_ticks.items()}
    start = frames[option]
    pb0, pb1 = int(facts["playback"][0]), int(facts["playback"][1])
    if start < pb0:
        warnings.append("LAND_BEFORE_PLAYBACK_START: frame %d < %d; starting at the playback start" % (start, pb0))
        start = pb0
    if start >= pb1:
        refusals.append("START_AFTER_SCENE_END: frame %d >= playback end %d" % (start, pb1))
    clip_frames = int(math.ceil(float(duration_s) * fps - FRAME_EPS))
    end = start + clip_frames
    if args.get("section_end", "clip_length") == "scene_end":
        end = min(end, pb1)
    start_s, end_s = start / fps, pb1 / fps
    overrun_s = start_s + float(duration_s) - end_s
    fits = overrun_s <= FIT_EPS_S
    return {"refusals": refusals, "warnings": warnings, "land_tick_outer": land_outer, "land_s": land_s,
            "option": option, "frames_by_option": frames,
            "seconds_by_option": {k: v / fps for k, v in frames.items()},
            "start_frame": start, "start_s": start_s, "end_frame": end, "clip_frames": clip_frames,
            "duration_s": float(duration_s), "scene_end_frame": pb1, "scene_end_s": end_s,
            "fits": fits, "overrun_s": max(0.0, overrun_s), "headroom_s": max(0.0, -overrun_s),
            "audible_s": max(0.0, min(float(duration_s), end_s - start_s))}


def parse_go_label(text):
    """Port of InfinityStageGoCues::ParseMarkerLabel [prec curtain_sleight.py:230-245, citing
    InfinityStageTransportController.cpp:601-645]. Returns (number, label, mode) mode -1 default/1 HOLD/0 PASS."""
    words = str(text).strip().split()
    if len(words) < 2 or words[0] != "GO":
        return None
    cand = words[1]
    if not any(ch.isdigit() for ch in cand) or any(not (ch.isdigit() or ch == ".") for ch in cand):
        return None
    mode, start = -1, 2
    if len(words) > 2 and words[2] == "HOLD":
        mode, start = 1, 3
    elif len(words) > 2 and words[2] == "PASS":
        mode, start = 0, 3
    return cand, " ".join(words[start:]), mode


def go_report(markers, plan):
    """markers: [{label, scene_s, sequence}]. Default mode in a Scene is HOLD [prec cue_list_tool.py:62]."""
    out = []
    lo = plan.get("start_s")
    hi = None if lo is None else min(plan["scene_end_s"], lo + plan["duration_s"])
    for m in markers:
        parsed = parse_go_label(m["label"])
        if parsed is None:
            continue
        hold = parsed[2] != 0
        inside = lo is not None and lo - FIT_EPS_S <= m["scene_s"] < hi
        out.append({"label": m["label"], "number": parsed[0], "hold": hold, "scene_s": round(m["scene_s"], 4),
                    "sequence": m["sequence"], "inside_narration": bool(inside), "pauses_narration": bool(inside and hold)})
    return out


def live_gates(state):
    """Refusals from editor state: mode, confirm, pie, sequencer_open, census, record_exists, record_applied,
    decided_by, mapping_confirmed_by, assets_exist."""
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % state.get("mode"))
    if state.get("confirm") != "%s NARRATION" % mode:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s NARRATION" % mode))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode in ("DRY", "APPLY") and state.get("record_exists"):
        r.append("RECORD_EXISTS: REVERT first, or archive a stale record by hand")
    if mode == "APPLY":
        if not str(state.get("decided_by") or "").strip():
            r.append("NOT_DECIDED: args decided_by is empty")
        if not str(state.get("mapping_confirmed_by") or "").strip():
            r.append("MAPPING_NOT_CONFIRMED: file->Scene mapping is inferred from names; args mapping_confirmed_by empty")
        if state.get("assets_exist"):
            r.append("ASSET_EXISTS: %s" % ", ".join(state["assets_exist"]))
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def census_gate(census, expected_content):
    """Failures unless the dirty census is EXACTLY the expected content packages and no maps."""
    out = []
    got = sorted(census.get("content") or [])
    want = sorted(expected_content)
    if got != want:
        out.append("TOUCHED_CENSUS: extra=%s missing=%s" % (sorted(set(got) - set(want)), sorted(set(want) - set(got))))
    if census.get("maps"):
        out.append("MAP_DIRTY: %s" % census["maps"])
    return out


def descriptor_key(d):
    return json.dumps(d, sort_keys=True)


def narration_descriptor(sound_path, start, end):
    return {"cls": "MovieSceneAudioTrack", "name": TRACK_NAME,
            "sections": [{"start": int(start), "end": int(end), "sound": sound_path, "looping": False}]}


def apply_scene(seq, sound_path, start, end):
    """Add ONE narration track + section via the adapter; judge by re-listing. Returns (before, after, failures)."""
    before = seq.list_tracks()
    if any(d["name"] == TRACK_NAME for d in before):
        return before, before, ["NARRATION_TRACK_EXISTS"]
    track = seq.add_audio_track(TRACK_NAME)
    seq.add_audio_section(track, sound_path, start, end)
    after = seq.list_tracks()
    want = sorted([descriptor_key(d) for d in before] + [descriptor_key(narration_descriptor(sound_path, start, end))])
    got = sorted(descriptor_key(d) for d in after)
    failures = []
    if got != want:
        failures.append("APPLY_READBACK: tracks %s, want %s" % (
            sorted(set(got) - set(want))[:3], sorted(set(want) - set(got))[:3]))
    return before, after, failures


def drift_since_apply(live, row):
    """Failures if the Scene's root tracks are not exactly the recorded before-list + our one track."""
    ours = descriptor_key(row["added"])
    keys = [descriptor_key(d) for d in live]
    out = []
    if keys.count(ours) != 1:
        out.append("NARRATION_TRACK_COUNT: %d" % keys.count(ours))
    others = sorted(k for k in keys if k != ours)
    if others != sorted(descriptor_key(d) for d in row["tracks_before"]):
        out.append("OTHER_TRACKS_CHANGED_SINCE_APPLY")
    return out


def revert_scene(seq, row):
    """Remove our track (judged by re-listing; remove_track's return value is ignored - it lies [memory
    puss-python-api-gotchas]). Returns failures (empty = the root track list equals the recorded before-list)."""
    failures = drift_since_apply(seq.list_tracks(), row)
    if failures:
        return ["STATE_DRIFTED: " + f for f in failures]
    seq.remove_matching(row["added"])
    final = sorted(descriptor_key(d) for d in seq.list_tracks())
    if final != sorted(descriptor_key(d) for d in row["tracks_before"]):
        return ["REVERT_NOT_EXACT: %d tracks, want %d" % (len(final), len(row["tracks_before"]))]
    return []


def marker_summary(plans):
    return "|".join("S%s=frame%d(%.3fs)" % (k, p["start_frame"], p["start_s"]) for k, p in sorted(plans.items()))


def overrun_summary(plans):
    bad = ["S%s:+%.3fs" % (k, p["overrun_s"]) for k, p in sorted(plans.items()) if not p["fits"]]
    return ",".join(bad) if bad else "none"


def write_record_exclusive(path, data):
    """Create-only (refuses if it exists), flushed and fsynced BEFORE any mutation [prec hangar_heave.py:702-707]."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_record(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sound_paths(args):
    folder = args["dest_folder"].rstrip("/")
    return {k: "%s/%s" % (folder, row["asset_name"]) for k, row in sorted(args["scenes"].items())}


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local or an adapter instance attribute.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    if unreal is not None:
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.dirname(os.path.dirname(_here()))


def _stop(run, reason):
    unreal.log_error("SCENE_NARRATION_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():   # hangar_heave.py:739-743 [prec]
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _content_file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


class _LiveSeq(object):
    """Adapter over one Scene LevelSequence's ROOT tracks [decl MovieSceneSequenceExtensions.h:49,79,89]."""

    def __init__(self, seq):
        self.seq = seq

    @staticmethod
    def _section_row(s):
        row = {"start": int(s.get_start_frame()) if s.has_start_frame() else None,
               "end": int(s.get_end_frame()) if s.has_end_frame() else None}
        if isinstance(s, unreal.MovieSceneAudioSection):
            row["sound"] = _path(s.get_sound())
            row["looping"] = bool(s.get_looping())
        return row

    def _rows(self):
        out = []
        for t in self.seq.get_tracks():
            out.append((t, {"cls": t.get_class().get_name(), "name": str(t.get_display_name()),
                            "sections": [self._section_row(s) for s in t.get_sections()]}))
        return out

    def list_tracks(self):
        return [r[1] for r in self._rows()]

    def add_audio_track(self, name):
        track = self.seq.add_track(unreal.MovieSceneAudioTrack)
        if track is None:
            raise RuntimeError("ADD_TRACK_NONE")
        track.set_display_name(name)
        return track

    def add_audio_section(self, track, sound_path, start, end):
        sound = unreal.load_asset(sound_path)
        if not isinstance(sound, unreal.SoundWave):
            raise RuntimeError("SOUND_NOT_LOADED: %s" % sound_path)
        section = track.add_section()
        if section is None:
            raise RuntimeError("ADD_SECTION_NONE")
        section.set_sound(sound)
        section.set_range(int(start), int(end))
        section.set_looping(False)
        for setter in ("set_repeating", "set_play_until_finished"):   # MovieSceneAudioSection.h:111-112, 132-133
            if hasattr(section, setter):
                getattr(section, setter)(False)
        if hasattr(section, "get_play_until_finished") and section.get_play_until_finished():
            raise RuntimeError("PLAY_UNTIL_FINISHED_STILL_SET")       # setters lie: read back

    def remove_matching(self, descriptor):
        key = descriptor_key(descriptor)
        for t, row in self._rows():
            if descriptor_key(row) == key:
                self.seq.remove_track(t)     # return value ignored on purpose; the caller re-lists

    def remove_new_named(self, before):
        """Failure path: remove every TRACK_NAME track not in the before-list, whatever its (possibly mis-set) shape."""
        keep = set(descriptor_key(d) for d in before)
        for t, row in self._rows():
            if row["name"] == TRACK_NAME and descriptor_key(row) not in keep:
                self.seq.remove_track(t)


def _root_land(rise, n, problems):
    """(land tick in the rise's tick resolution, first/last values) from the root pitch channel's last key."""
    rows = [b for b in rise.get_bindings() if str(b.get_display_name()) == ROOT_BINDING % n]
    if len(rows) != 1:
        problems.append("ROOT_BINDING_COUNT: %s %d" % (ROOT_BINDING % n, len(rows)))
        return None
    tracks = [t for t in rows[0].get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)]
    secs = [s for t in tracks for s in t.get_sections()]
    if len(tracks) != 1 or len(secs) != 1:
        problems.append("ROOT_TRANSFORM_SECTION_COUNT: tracks=%d sections=%d" % (len(tracks), len(secs)))
        return None
    chans = list(secs[0].get_all_channels())
    if len(chans) <= ROOT_CHANNEL_INDEX:
        problems.append("ROOT_CHANNEL_INDEX: %d channels" % len(chans))
        return None
    ch = chans[ROOT_CHANNEL_INDEX]
    cname = str(ch.channel_name) if hasattr(ch, "channel_name") else str(ch.get_name())
    if not (cname == ROOT_CHANNEL_NAME or cname.startswith(ROOT_CHANNEL_NAME + "_")):   # memory: Location.Y_183
        problems.append("ROOT_CHANNEL_NAME: %r" % cname)
        return None
    keys = []
    for key in ch.get_keys():
        t = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
        keys.append((int(t.frame_number.value), float(key.get_value())))
    keys.sort()
    if len(keys) < 2:
        problems.append("ROOT_KEYS: %d" % len(keys))
        return None
    return {"land_tick": keys[-1][0], "first": keys[0], "last": keys[-1], "count": len(keys)}


def _walk_markers(seq, outer_start_s, depth, visited, out):
    """GO-candidate markers of a sequence and its nested sub-sequences (Choreo tracks skipped), in Scene seconds.
    Read-only; mirrors cue_list_tool.py:33-89 [prec] (+ StartFrameOffset)."""
    if seq is None or depth > 4 or _path(seq) in visited:
        return
    visited.add(_path(seq))
    tick = seq.get_tick_resolution()
    tr = rate_of(tick.numerator, tick.denominator)
    pb0 = seq.get_playback_start_seconds()
    for m in seq.get_marked_frames():                                # tick resolution [decl ...Extensions.h:536]
        out.append({"label": str(m.get_editor_property("label")), "sequence": _path(seq),
                    "scene_s": outer_start_s + (m.get_editor_property("frame_number").value / tr - pb0)})
    for t in seq.get_tracks():
        if not isinstance(t, unreal.MovieSceneSubTrack) or t.get_class().get_name() == CHOREO_TRACK_CLASS:
            continue
        for s in t.get_sections():
            child = s.get_sequence()
            if child is None or not s.has_start_frame():
                continue
            ctick = child.get_tick_resolution()
            off = s.get_editor_property("parameters").get_editor_property("start_frame_offset").value
            off_s = off / rate_of(ctick.numerator, ctick.denominator)
            _walk_markers(child, outer_start_s + (s.get_start_frame_seconds() - pb0) - off_s, depth + 1, visited, out)


def _scene_cues():
    show = unreal.load_asset(SHOW_PATH)
    out = {}
    if show is None:
        return out
    for cue in show.get_editor_property("cues"):
        if cue.get_editor_property("type") != unreal.InfinityCueType.SCENE:
            continue
        label = str(cue.get_editor_property("label"))
        for n in (1, 2, 3):
            if label == "Scene %d" % n or label.startswith("Scene %d " % n):
                scene = cue.get_editor_property("scene")
                out.setdefault(n, []).append({"label": label, "sequence": _path(scene.get_editor_property("sequence")),
                                              "external_sound": str(scene.get_editor_property("external_sound"))})
    return out


def _gather_scene(n, row, cues, arrivals):
    """Live facts for one Scene as plain data (read-only)."""
    problems, warnings = [], []
    seq = unreal.load_asset(row["scene_sequence"])
    rise = unreal.load_asset(row["rise"])
    if seq is None or rise is None:
        problems.append("ASSET_MISSING: scene=%s rise=%s" % (seq is not None, rise is not None))
        return None, problems, warnings, None
    found = cues.get(n, [])
    if len(found) != 1:
        problems.append("SCENE_CUE_COUNT: %d" % len(found))
    elif found[0]["sequence"] != row["scene_sequence"]:
        problems.append("SCENE_CUE_SEQUENCE: Show plays %s, args say %s" % (found[0]["sequence"], row["scene_sequence"]))
    st, dr, rt = seq.get_tick_resolution(), seq.get_display_rate(), rise.get_tick_resolution()
    rdr = rise.get_display_rate()
    sres, fps, rres = rate_of(st.numerator, st.denominator), rate_of(dr.numerator, dr.denominator), \
        rate_of(rt.numerator, rt.denominator)
    rfps = rate_of(rdr.numerator, rdr.denominator)
    sections = []
    for t in seq.get_tracks():
        if isinstance(t, unreal.MovieSceneSubTrack):
            for s in t.get_sections():
                if _path(s.get_sequence()) == row["rise"]:
                    sections.append((t, s))
    facts = {"scene": n, "scene_sequence": row["scene_sequence"], "rise": row["rise"], "scene_res": sres, "fps": fps,
             "rise_res": rres, "rise_fps": rfps,
             "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
             "rise_lower_tick": int(round(rise.get_playback_start() * rres / rfps)),
             "rise_upper_tick": int(round(rise.get_playback_end() * rres / rfps)),
             "external_sound": found[0]["external_sound"] if len(found) == 1 else None}
    if len(sections) != 1:
        problems.append("RISE_SUBSECTION_COUNT: %d (FindMotionSection matches by sequence)" % len(sections))
        return facts, problems, warnings, seq
    track, s = sections[0]
    p = s.get_editor_property("parameters")
    facts.update({
        "rise_track": str(track.get_display_name()),
        "section_start_tick": int(round(s.get_start_frame_seconds() * sres)) if s.has_start_frame() else None,
        "section_end_tick": int(round(s.get_end_frame_seconds() * sres)) if s.has_end_frame() else None,
        "start_offset_tick": int(p.get_editor_property("start_frame_offset").value),
        "end_offset_tick": int(p.get_editor_property("end_frame_offset").value)})
    land = _root_land(rise, n, problems)
    if land is None:
        return facts, problems, warnings, seq
    facts["land_tick_inner"] = land["land_tick"]
    facts["root_keys_first_last"] = [land["first"], land["last"]]
    facts["root_key_count"] = land["count"]
    if abs(land["last"][1]) > 1e-3 or abs(land["first"][1] + 90.0) > 1e-3:
        warnings.append("ROOT_VALUES_UNEXPECTED: first %r last %r (want -90 -> 0)" % (land["first"], land["last"]))
    hits = [a for a in arrivals if str(a.get_actor_label()) == ARRIVAL_LABEL % n]
    facts["strike_after_land_s"] = None
    if len(hits) == 1:
        a = hits[0]
        motion = a.get_editor_property("motion_sequence")
        facts["arrival_motion"] = _path(motion) if motion else None
        if facts["arrival_motion"] != row["rise"]:
            warnings.append("ARRIVAL_MOTION_SEQUENCE: %r" % facts["arrival_motion"])
        timing = a.get_editor_property("hangar_timing")
        facts["strike_after_land_s"] = float(timing.get_editor_property("strike_after_land_seconds"))
        facts["arrival_land_seconds_transient"] = float(timing.get_editor_property("land_seconds"))
    else:
        warnings.append("ARRIVAL_COUNT: %d (option b unavailable)" % len(hits))
    audio = []
    for t in seq.find_tracks_by_type(unreal.MovieSceneAudioTrack):
        audio.append({"track": str(t.get_display_name()),
                      "sections": [[s2.get_start_frame() if s2.has_start_frame() else None,
                                    s2.get_end_frame() if s2.has_end_frame() else None,
                                    _path(s2.get_sound())] for s2 in t.get_sections()]})
    facts["audio_tracks"] = audio
    markers = []
    _walk_markers(seq, seq.get_playback_start_seconds(), 0, set(), markers)   # root: absolute Scene seconds
    facts["markers"] = markers
    return facts, problems, warnings, seq


def _plan_all(args, run):
    project = _project()
    inputs, input_refusals = check_inputs(args, project)
    cues = _scene_cues()
    arrivals = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    rows, plans, refusals, warnings, handles = {}, {}, list(input_refusals), [], {}
    for key, row in sorted(args["scenes"].items()):
        n = int(key)
        facts, problems, warns, seq = _gather_scene(n, row, cues, arrivals)
        refusals += ["S%d %s" % (n, p) for p in problems]
        warnings += ["S%d %s" % (n, w) for w in warns]
        rows[key] = facts
        handles[key] = seq
        if problems or facts is None:
            continue
        plan = plan_scene(facts, args, float(row["duration_s"]))
        refusals += ["S%d %s" % (n, p) for p in plan["refusals"]]
        warnings += ["S%d %s" % (n, w) for w in plan["warnings"]]
        if plan["refusals"]:
            continue
        plan["go"] = go_report(facts["markers"], plan)
        if any(g["pauses_narration"] for g in plan["go"]):
            warnings.append("S%d GO_HOLD_INSIDE_NARRATION: %s (a HOLD stops Sequencer audio)"
                            % (n, [g["label"] for g in plan["go"] if g["pauses_narration"]]))
        if facts["audio_tracks"]:
            warnings.append("S%d AUDIO_TRACKS_PRESENT: %s" % (n, json.dumps(facts["audio_tracks"])))
        if any(t["track"] == TRACK_NAME for t in facts["audio_tracks"]):
            refusals.append("S%d NARRATION_TRACK_EXISTS" % n)
        if not plan["fits"]:
            warnings.append("S%d OVERRUN: clip %.3f s from %.3f s ends %.3f s past the Scene end %.3f s (not extended)"
                            % (n, plan["duration_s"], plan["start_s"], plan["overrun_s"], plan["scene_end_s"]))
        plans[key] = plan
    return inputs, rows, plans, refusals, warnings, handles


def _backup(run, suffix, paths):
    folder = os.path.join(_project(), "Backups", "PreSceneNarration-%s%s" % (run, suffix))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path in paths:
        src = _content_file(path)
        if not os.path.isfile(src):
            _stop(run, "BACKUP_SOURCE_MISSING|" + src)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def run_dry(args, run):
    inputs, rows, plans, refusals, warnings, _h = _plan_all(args, run)
    existing = [p for p in sound_paths(args).values() if unreal.EditorAssetLibrary.does_asset_exist(p)]
    if existing:
        refusals.append("ASSET_EXISTS: %s" % existing)
    report = {"tool": TOOL, "run": run, "args": args, "inputs": inputs, "facts": rows, "plans": plans,
              "refusals": refusals, "warnings": warnings, "apply_ready": not refusals,
              "mapping_confirmed_by": args.get("mapping_confirmed_by") or None}
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    for text in refusals:
        unreal.log_warning("SCENE_NARRATION_REFUSAL|run=%s|%s" % (run, text))
    for text in warnings:
        unreal.log("SCENE_NARRATION_WARNING|run=%s|%s" % (run, text))
    for key, p in sorted(plans.items()):
        unreal.log("SCENE_NARRATION_ROW|run=%s|scene=S%s|land_s=%.4f|a=%d|b=%s|start=%d|end=%d|scene_end=%d|fits=%d|"
                   "overrun_s=%.3f|go_holds_inside=%d|ext_sound=%s"
                   % (run, key, p["land_s"], p["frames_by_option"]["land"],
                      p["frames_by_option"].get("land_plus_strike"), p["start_frame"], p["end_frame"],
                      p["scene_end_frame"], int(p["fits"]), p["overrun_s"],
                      sum(1 for g in p["go"] if g["pauses_narration"]), rows[key].get("external_sound")))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("SCENE_NARRATION_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|option=%s|%s|overruns=%s|"
               "report=%s" % (run, int(not refusals), len(refusals), len(warnings), args["start_option"],
                              marker_summary(plans), overrun_summary(plans), out))


def _import_sounds(args, inputs, run):
    tasks = []
    folder = args["dest_folder"].rstrip("/")
    for key, row in sorted(args["scenes"].items()):
        task = unreal.AssetImportTask()                                   # hangar_exit_doors.py:760-766 [prec]
        task.set_editor_property("filename", inputs[key]["path"])
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", row["asset_name"])
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("save", False)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    failures = []
    for key, path in sorted(sound_paths(args).items()):
        sound = unreal.load_asset(path)
        if not isinstance(sound, unreal.SoundWave):
            failures.append("IMPORT_NOT_SOUNDWAVE_S%s: %s -> %r" % (key, path, type(sound).__name__))
            continue
        dur = float(sound.get_editor_property("duration"))                 # SoundBase.h:200-202 [decl]
        if abs(dur - inputs[key]["duration_s"]) > DURATION_TOL_S:
            failures.append("IMPORT_DURATION_S%s: %.4f vs WAV %.4f" % (key, dur, inputs[key]["duration_s"]))
    return failures


def run_apply(args, run):
    inputs, rows, plans, refusals, warnings, handles = _plan_all(args, run)
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    if sorted(plans) != ["1", "2", "3"]:
        _stop(run, "PLAN_INCOMPLETE|%s" % sorted(plans))
    sounds = sound_paths(args)
    seq_paths = {k: args["scenes"][k]["scene_sequence"] for k in plans}
    record_path = os.path.join(_here(), RECORD_NAME)
    if os.path.exists(record_path):
        _stop(run, "RECORD_EXISTS|" + record_path)
    backup = _backup(run, "", sorted(seq_paths.values()))
    unreal.log("SCENE_NARRATION_BACKUP_OK|run=%s|backup=%s" % (run, backup))
    adapters = {k: _LiveSeq(handles[k]) for k in plans}
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "args": args, "backup": backup,
              "decided_by": args.get("decided_by"), "mapping_confirmed_by": args.get("mapping_confirmed_by"),
              "applied": False, "sounds_imported": False, "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "scenes": {k: {"scene_sequence": seq_paths[k], "sound": sounds[k],
                             "playback_before": rows[k]["playback"],
                             "tracks_before": adapters[k].list_tracks(),
                             "added": narration_descriptor(sounds[k], plans[k]["start_frame"], plans[k]["end_frame"]),
                             "plan": {f: v for f, v in plans[k].items() if f not in ("go",)}}
                         for k in plans}}
    write_record_exclusive(record_path, record)                         # BEFORE any change (incl. the import)
    failures = _import_sounds(args, inputs, run)
    record["sounds_imported"] = True
    update_record(record_path, record)
    added = []
    if not failures:
        for k in sorted(plans):
            try:
                handles[k].modify()
                _b, _a, bad = apply_scene(adapters[k], sounds[k], plans[k]["start_frame"], plans[k]["end_frame"])
                failures += ["S%s %s" % (k, f) for f in bad]
                added.append(k)
            except Exception as exc:   # noqa: BLE001 - reported, never swallowed silently
                failures.append("S%s WRITE_RAISED: %r" % (k, exc))
                added.append(k)
            if [int(handles[k].get_playback_start()), int(handles[k].get_playback_end())] != rows[k]["playback"]:
                failures.append("S%s PLAYBACK_RANGE_CHANGED" % k)
    expected = sorted(list(seq_paths.values()) + list(sounds.values()))
    failures += census_gate(_census(), expected)
    if failures:
        errs = []
        for k in added:
            seq = adapters[k]
            seq.remove_new_named(record["scenes"][k]["tracks_before"])
            if sorted(descriptor_key(d) for d in seq.list_tracks()) != \
                    sorted(descriptor_key(d) for d in record["scenes"][k]["tracks_before"]):
                errs.append("S%s not restored" % k)
        update_record(record_path, dict(record, applied=False, failed=failures, restore_errors=errs))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|tracks_restored_in_memory=%s|NOTHING SAVED; imported sounds are unsaved in memory: "
              "Don't-Save restart" % (failures[:10], "exact" if not errs else errs))
    for path in expected:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s|record=%s (some assets may be saved; REVERT or restore %s)"
                  % (path, record_path, backup))
    dd = []
    for k in sorted(plans):
        seq = _LiveSeq(unreal.load_asset(seq_paths[k]))
        live = seq.list_tracks()
        dd += ["S%s %s" % (k, f) for f in drift_since_apply(live, record["scenes"][k])]
        mine = [d for d in live if d["name"] == TRACK_NAME]
        if len(mine) != 1 or mine[0]["sections"][0]["start"] != plans[k]["start_frame"] or \
                mine[0]["sections"][0]["sound"] != sounds[k]:
            dd.append("S%s READBACK_SECTION: %r" % (k, mine))
        if not os.path.isfile(_content_file(sounds[k])):
            dd.append("S%s SOUND_FILE_NOT_ON_DISK" % k)
    if _census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    record["applied"] = True
    if dd:
        record["post_save_readback_failed"] = dd
        update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd[:8], backup))
    update_record(record_path, record)
    unreal.log("SCENE_NARRATION_APPLY_OK|run=%s|%s|overruns=%s|option=%s|section_end=%s|sounds=%s|backup=%s|record=%s|"
               "decided_by=%s|mapping_confirmed_by=%s"
               % (run, "|".join("S%s=frame%d" % (k, plans[k]["start_frame"]) for k in sorted(plans)),
                  overrun_summary(plans), args["start_option"], args.get("section_end", "clip_length"),
                  ",".join(sounds[k] for k in sorted(sounds)), backup, record_path, args.get("decided_by"),
                  args.get("mapping_confirmed_by")))


def run_revert(args, run):
    record_path = os.path.join(_here(), RECORD_NAME)
    record = load_record(record_path)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    adapters, failures = {}, []
    for k, row in sorted(record["scenes"].items()):
        seq = unreal.load_asset(row["scene_sequence"])
        if seq is None:
            _stop(run, "REVERT_SEQUENCE_MISSING|" + row["scene_sequence"])
        adapters[k] = (seq, _LiveSeq(seq))
        failures += ["S%s %s" % (k, f) for f in drift_since_apply(adapters[k][1].list_tracks(), row)]
    if failures:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r (restore from %s instead)" % (failures[:8], record["backup"]))
    paths = sorted(row["scene_sequence"] for row in record["scenes"].values())
    backup = _backup(run, "-revert", paths)
    errs = []
    for k, row in sorted(record["scenes"].items()):
        adapters[k][0].modify()
        errs += ["S%s %s" % (k, f) for f in revert_scene(adapters[k][1], row)]
        if [int(adapters[k][0].get_playback_start()), int(adapters[k][0].get_playback_end())] != row["playback_before"]:
            errs.append("S%s PLAYBACK_RANGE_CHANGED" % k)
    errs += census_gate(_census(), paths)
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8], record["backup"]))
    for path in paths:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % path)
    final = []
    for k, row in sorted(record["scenes"].items()):
        live = sorted(descriptor_key(d) for d in _LiveSeq(unreal.load_asset(row["scene_sequence"])).list_tracks())
        if live != sorted(descriptor_key(d) for d in row["tracks_before"]):
            final.append("S%s TRACKS_NOT_AS_BEFORE" % k)
    if _census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final, record["backup"]))
    deleted = []
    if args.get("delete_assets") is True:
        for k, row in sorted(record["scenes"].items()):
            refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(row["sound"], False)]
            if refs:                                                     # fx_cleanup_failed_candle_assets.py:91 [prec]
                _stop(run, "DELETE_REFUSED_REFERENCED|%s|%s (tracks already reverted and saved)" % (row["sound"], refs))
            unreal.EditorAssetLibrary.delete_asset(row["sound"])
            if unreal.EditorAssetLibrary.does_asset_exist(row["sound"]):
                _stop(run, "DELETE_FAILED|%s" % row["sound"])
            deleted.append(row["sound"])
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("SCENE_NARRATION_REVERT_OK|run=%s|scenes=%s|sounds_deleted=%s|backup=%s|record=%s"
               % (run, ",".join("S%s" % k for k in sorted(record["scenes"])), ",".join(deleted) or "kept", backup,
                  archived))


def main():
    g = globals()
    args = g.get("NARRATION_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("NARR-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    record_path = os.path.join(_here(), RECORD_NAME)
    applied = os.path.exists(record_path) and bool(load_record(record_path).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census(), "record_exists": os.path.exists(record_path), "record_applied": applied,
             "decided_by": args.get("decided_by"), "mapping_confirmed_by": args.get("mapping_confirmed_by"),
             "assets_exist": [p for p in sound_paths(args).values() if unreal.EditorAssetLibrary.does_asset_exist(p)]
             if mode == "APPLY" else []}
    early = live_gates(state)
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        if mode == "REVERT":
            run_revert(args, run)
        elif mode == "APPLY":
            run_apply(args, run)
        else:
            run_dry(args, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
