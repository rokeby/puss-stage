"""SCENE AUDIO IMPORT: import a Scene's score WAV as a SoundWave and place it in that Scene's sequence from the hangar
LANDING, with named marked frames at the landing and at analysis-chosen moments. General per Scene; first use S6.
6 Oct, offline-written, NEVER RUN IN UNREAL.

Gary 6 Oct ~17:10 (conductor questionnaire): S6 audio "Yes, from the hangar landing". S3 (Shore_People, 246.9 s) will
use this same tool later, after Gary walks the S3 beats - it is NOT planned here (no S3 row in the args).

Precedent: scene_narration_standin.py (applied 5 Oct, NARR-20261005-143408). Its land maths, inputs check, GO report and
record discipline are PORTED here (cited per function) - not imported, because that module runs its own main() when
`unreal` is present (scene_narration_standin.py:936-937).

Tiers per claim: [decl] header/source we can read, [prec] in-repo precedent (cited), [meas] an earlier read-back record,
[inf] inferred (why stated).

LAND (read live every run, never from records): the Scene's sub-section playing LS_S<n>_HangarRise [decl
InfinityStageArrival.cpp:39-57 FindMotionSection matches by sequence]; LAND = root pitch channel's LAST key [decl
InfinityStageArrival.h:55-57; prec scene_narration_standin.py:504-532]; inner->Scene time inverts MapOuterToInnerTime
[decl InfinityStageArrival.cpp:1044-1048; prec scene_narration_standin.py:158-166]; rate-1 gate because the play rate is
opaque to Python [meas NEST readback prints "{}"; prec :169-179]. start_option "land" = first Scene display frame at or
after the land key; "land_plus_strike" = + the Arrival's persisted StrikeAfterLandSeconds.

FIT: section = [start, start + ceil(duration x fps)) in display frames. If its end passes the Scene's playback end the
tool REFUSES with OVERRUN and reports the needed end (it NEVER changes the playback range). Extending is the conductor's
step: Saved/CodexSoftGoods/extend_scene_playback.py (re-matches handoffs, checks cut coverage, rebuilds the Master);
the DRY report carries a ready mode-file body for it.

EXISTING AUDIO: every audio section in the Scene (root tracks) and in its nested sub/shot sequences (depth <= 4, Choreo
tracks skipped), mapped to Scene seconds and clipped to the nesting section, is listed. One that overlaps the new span
-> REFUSED (EXISTING_AUDIO_OVERLAP, listed). Others are reported and left alone. args watch_sounds (e.g. the old
The_Void_Scene) are additionally looked up in the asset registry for referencers (read-only) and reported.

MARKERS: marked frames in the Scene sequence (TickResolution explicitly [decl MovieSceneSequenceExtensions.h:531,546;
prec choreo_song_markers_refresh.py:508-549]), snapped to the nearest Scene display frame [inf: keeps them on the
Sequencer frame grid; analysis resolution is 0.1 s, a frame is 0.04 s]. A land marker at the audio start + one per
args marker at start + track_s. Every args marker names its analysis SOURCE and is re-verified against the analysis json
(kinds: major_change = equals a majorChangeProposals time; intensity_onset = the first intensity sample >= threshold at or
after after_s); the analysis json's source sha256 must equal the WAV's. Labels must NOT parse as GO labels (a "GO <n>"
marker becomes a show cue, and a HOLD stops Sequencer audio) [prec scene_narration_standin.py:238-252 port of
InfinityStageGoCues::ParseMarkerLabel]. Duplicate labels already in the sequence -> refused. Locked markers -> refused.

WRITES (APPLY): per Scene one NEW SoundWave in args.dest_folder (AssetImportTask, automated, replace_existing False [prec
scene_narration_standin.py:735-757]); in the Scene sequence ONE root MovieSceneAudioTrack named args.track_name with ONE
section (looping/repeat/play-until-finished False, read back) + the marked frames. Nothing else. Records are per Scene
(scene_audio_import_S<n>_record.json, create-only, fsync, BEFORE any change) so S3 can be applied later independently.
REVERT removes exactly our track and markers (drift-gated), saves the Scene only; the SoundWave is kept unless
delete_assets is true and nothing references it.

Modes via scene_audio_import_args.json (or init_globals SCENEAUDIO_ARGS): DRY | APPLY | REVERT, confirm
"<MODE> SCENEAUDIO". Guards: no PIE/SIE, no Sequencer open on a target Scene / the Master / a sequence nesting it, census
CLEAN before; after the edit the dirty census must be EXACTLY the new SoundWave(s) + the Scene sequence(s), no map.
Markers: SCENEAUDIO_DRY_OK / SCENEAUDIO_APPLY_OK / SCENEAUDIO_REVERT_OK |run=.., or SCENEAUDIO_STOPPED|run=..|reason=..
Never: Save All, level save, reload, open or scrub Sequencer, load the Master, touch Choreo, end PIE; no unreal objects in
module globals. Importing without `unreal` runs nothing (test_s3_narration_and_scene_audio.py).
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


TOOL = "scene_audio_import"
CONFIRM_WORD = "SCENEAUDIO"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                     # scene_narration_standin.py:68
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"            # extend_scene_playback.py:43
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # scene_narration_standin.py:69
ROOT_BINDING = "S%d Hangar Root"
ROOT_CHANNEL_INDEX = 4                                                            # scene_narration_standin.py:71
ROOT_CHANNEL_NAME = "Rotation.Y"
ARRIVAL_LABEL = "S%d Arrival"
ARGS_NAME = "scene_audio_import_args.json"
DRY_NAME = "scene_audio_import_dry.json"
RECORD_FMT = "scene_audio_import_S%s_record.json"
CHOREO_TRACK_CLASS = "MovieSceneInfinityChoreoTrack"
START_OPTIONS = ("land", "land_plus_strike")
MARKER_KINDS = ("major_change", "intensity_onset")
FRAME_EPS = 1.0e-6
DURATION_TOL_S = 0.02
WAV_ARGS_TOL_S = 0.002
ANALYSIS_DURATION_TOL_S = 0.05
MAJOR_CHANGE_TOL_S = 1.0e-3
RATE_TOL_S = 0.5 / 24000.0 * 4


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: args, inputs, analysis, maths
# =====================================================================================================================

def parse_go_label(text):
    """Port of InfinityStageGoCues::ParseMarkerLabel [prec scene_narration_standin.py:238-252]."""
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


def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    if args.get("start_option", "land") not in START_OPTIONS:
        r.append("START_OPTION_INVALID: %r" % args.get("start_option"))
    folder = str(args.get("dest_folder") or "")
    if not folder.startswith("/Game/"):
        r.append("DEST_FOLDER_INVALID: %r" % folder)
    if not str(args.get("track_name") or "").strip():
        r.append("TRACK_NAME_EMPTY")
    scenes = args.get("scenes") or {}
    if not scenes:
        r.append("NO_SCENES")
    names = []
    for key, row in sorted(scenes.items()):
        if not str(key).isdigit():
            r.append("SCENE_KEY_NOT_A_NUMBER: %r" % key)
        for field in ("wav", "sha256", "duration_s", "asset_name", "scene_sequence", "rise", "land_marker_label"):
            if field not in row:
                r.append("SCENE_%s_MISSING_%s" % (key, field.upper()))
        names.append(row.get("asset_name"))
        target = str(row.get("scene_sequence", ""))
        if "Master" in target or "Choreo" in target:
            r.append("SCENE_%s_TARGET_NOT_A_SCENE: %r" % (key, target))
        labels = [row.get("land_marker_label")] + [m.get("label") for m in row.get("markers") or []]
        for lab in labels:
            if not str(lab or "").strip():
                r.append("SCENE_%s_MARKER_LABEL_EMPTY" % key)
            elif parse_go_label(lab) is not None:
                r.append("SCENE_%s_MARKER_IS_A_GO_LABEL: %r (it would become a show cue)" % (key, lab))
        if len(set(labels)) != len(labels):
            r.append("SCENE_%s_MARKER_LABELS_NOT_UNIQUE" % key)
        for m in row.get("markers") or []:
            ts = m.get("track_s")
            if not isinstance(ts, (int, float)) or ts < 0 or ("duration_s" in row and ts >= float(row["duration_s"])):
                r.append("SCENE_%s_MARKER_TIME_OUTSIDE_CLIP: %r %r" % (key, m.get("label"), ts))
            src = m.get("source") or {}
            if src.get("kind") not in MARKER_KINDS:
                r.append("SCENE_%s_MARKER_SOURCE_KIND: %r %r" % (key, m.get("label"), src.get("kind")))
        if row.get("markers") and not row.get("analysis"):
            r.append("SCENE_%s_MARKERS_WITHOUT_ANALYSIS" % key)
    if len(set(names)) != len(names):
        r.append("ASSET_NAMES_NOT_UNIQUE")
    return r


def wav_facts(path):
    """sha256 + header facts of a PCM WAV [prec scene_narration_standin.py:123-133]."""
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    w = wave.open(path, "rb")
    try:
        frames, rate = w.getnframes(), w.getframerate()
        return {"sha256": digest, "channels": w.getnchannels(), "rate": rate, "sample_width": w.getsampwidth(),
                "frames": frames, "duration_s": frames / float(rate)}
    finally:
        w.close()


def _abs(project_dir, rel):
    return os.path.join(project_dir, *str(rel).replace("\\", "/").split("/"))


def check_inputs(args, project_dir):
    """Per-scene WAV facts + refusals (present, sha, duration == args) [prec scene_narration_standin.py:136-151]."""
    facts, r = {}, []
    for key, row in sorted((args.get("scenes") or {}).items()):
        path = _abs(project_dir, row["wav"])
        if not os.path.isfile(path):
            r.append("WAV_MISSING_S%s: %s" % (key, path))
            continue
        try:
            f = wav_facts(path)
        except (wave.Error, EOFError) as exc:          # e.g. the f32 original: stdlib wave reads PCM only
            r.append("WAV_NOT_PCM_S%s: %s (%s)" % (key, path, exc))
            continue
        f["path"] = path
        facts[key] = f
        if f["sha256"] != str(row["sha256"]).lower():
            r.append("WAV_SHA_MISMATCH_S%s: %s != args %s" % (key, f["sha256"][:12], str(row["sha256"])[:12]))
        if abs(f["duration_s"] - float(row["duration_s"])) > WAV_ARGS_TOL_S:
            r.append("WAV_DURATION_MISMATCH_S%s: header %.4f s, args %.4f s" % (key, f["duration_s"], row["duration_s"]))
    return facts, r


def verify_markers(row, analysis, wav_sha):
    """Refusals unless every args marker is what its declared analysis source says. analysis: the parsed json."""
    r = []
    src = analysis.get("source") or {}
    if str(src.get("sha256", "")).lower() != str(wav_sha).lower():
        r.append("ANALYSIS_NOT_OF_THIS_WAV: analysis sha %s, wav %s" % (str(src.get("sha256"))[:12], str(wav_sha)[:12]))
    if abs(float(analysis.get("durationSeconds", -1)) - float(row["duration_s"])) > ANALYSIS_DURATION_TOL_S:
        r.append("ANALYSIS_DURATION: %r vs %r" % (analysis.get("durationSeconds"), row["duration_s"]))
    changes = [float(p["timeSeconds"]) for p in analysis.get("majorChangeProposals") or []]
    fc = analysis.get("featureCurves") or {}
    rate = float(fc.get("rateHz") or 0)
    intensity = (fc.get("curves") or {}).get("intensity") or []
    for m in row.get("markers") or []:
        s = m.get("source") or {}
        t = float(m["track_s"])
        if s.get("kind") == "major_change":
            if not any(abs(t - c) <= MAJOR_CHANGE_TOL_S for c in changes):
                r.append("MARKER_NOT_A_MAJOR_CHANGE: %r at %.4f s" % (m["label"], t))
        elif s.get("kind") == "intensity_onset":
            if rate <= 0 or not intensity:
                r.append("MARKER_NO_INTENSITY_CURVE: %r" % m["label"])
                continue
            i0 = int(math.ceil(float(s["after_s"]) * rate - FRAME_EPS))
            hit = next((i for i in range(max(0, i0), len(intensity)) if intensity[i] >= float(s["threshold"])), None)
            if hit is None or abs(t - hit / rate) > 0.5 / rate:
                r.append("MARKER_NOT_THE_ONSET: %r at %.4f s, curve onset %s" % (
                    m["label"], t, None if hit is None else "%.3f s" % (hit / rate)))
        else:
            r.append("MARKER_SOURCE_KIND: %r" % s.get("kind"))
    return r


def inner_to_outer_tick(inner_tick, inner_res, inner_lower_tick, start_offset_tick, section_start_outer_tick,
                        outer_res, play_rate=1.0):
    """Port [prec scene_narration_standin.py:158-166; decl InfinityStageArrival.cpp:1044-1048]."""
    if play_rate <= 0:
        raise PlanError("PLAY_RATE_NONPOSITIVE: %r" % play_rate)
    inner_offset = float(inner_tick) - float(inner_lower_tick) - float(start_offset_tick)
    return float(section_start_outer_tick) + inner_offset * (float(outer_res) / float(inner_res)) / float(play_rate)


def rate_one_gate(section_start_s, section_end_s, inner_lower_s, inner_upper_s, start_offset_s, end_offset_s):
    """Port [prec scene_narration_standin.py:169-179]."""
    if section_end_s is None or section_start_s is None:
        return "SECTION_UNBOUNDED: the rise sub-section has no start or end frame"
    outer = section_end_s - section_start_s
    inner = (inner_upper_s - end_offset_s) - (inner_lower_s + start_offset_s)
    if abs(outer - inner) > RATE_TOL_S:
        return ("PLAY_RATE_UNVERIFIED: section %.4f s vs inner span %.4f s (rate != 1 or a trimmed section; the land "
                "map assumes rate 1 - refused)" % (outer, inner))
    return None


def ceil_frame(outer_tick, outer_res, fps):
    frames = float(outer_tick) * float(fps) / float(outer_res)
    return int(math.ceil(frames - FRAME_EPS))


def plan_scene(facts, args, row):
    """facts (pure data) + args + the scene's args row -> plan. Refuses OVERRUN (never extends).
    facts keys as scene_narration_standin.plan_scene, plus optional scene_label."""
    refusals, warnings = [], []
    duration_s = float(row["duration_s"])
    sres, fps = float(facts["scene_res"]), float(facts["fps"])
    rres = float(facts["rise_res"])
    gate = rate_one_gate(
        facts["section_start_tick"] / sres if facts.get("section_start_tick") is not None else None,
        facts["section_end_tick"] / sres if facts.get("section_end_tick") is not None else None,
        facts["rise_lower_tick"] / rres, facts["rise_upper_tick"] / rres,
        facts["start_offset_tick"] / rres, facts.get("end_offset_tick", 0) / rres)
    if gate:
        return {"refusals": [gate], "warnings": warnings}
    land_outer = inner_to_outer_tick(facts["land_tick_inner"], rres, facts["rise_lower_tick"],
                                     facts["start_offset_tick"], facts["section_start_tick"], sres)
    option_ticks = {"land": land_outer}
    if facts.get("strike_after_land_s") is not None:
        option_ticks["land_plus_strike"] = land_outer + float(facts["strike_after_land_s"]) * sres
    option = args.get("start_option", "land")
    if option not in option_ticks:
        return {"refusals": ["STRIKE_AFTER_LAND_UNKNOWN"], "warnings": warnings, "land_s": land_outer / sres}
    frames = {k: ceil_frame(v, sres, fps) for k, v in option_ticks.items()}
    start = frames[option]
    pb0, pb1 = int(facts["playback"][0]), int(facts["playback"][1])
    if start < pb0:
        warnings.append("LAND_BEFORE_PLAYBACK_START: frame %d < %d; starting at the playback start" % (start, pb0))
        start = pb0
    clip_frames = int(math.ceil(duration_s * fps - FRAME_EPS))
    end = start + clip_frames
    fits = end <= pb1
    if start >= pb1:
        refusals.append("START_AFTER_SCENE_END: frame %d >= playback end %d" % (start, pb1))
    elif not fits:
        refusals.append("OVERRUN: clip %.3f s from frame %d (%.3f s) needs playback end >= frame %d (%.3f s); the Scene "
                        "ends at frame %d (%.3f s), short by %.3f s. Not extended: extend via extend_scene_playback.py "
                        "first" % (duration_s, start, start / fps, end, end / fps, pb1, pb1 / fps, (end - pb1) / fps))
    markers = [{"label": row["land_marker_label"], "track_s": 0.0, "display_frame": start,
                "tick": int(round(start * sres / fps)), "scene_s": start / fps, "source": "land (audio start)"}]
    for m in row.get("markers") or []:
        df = int(round(start + float(m["track_s"]) * fps))
        markers.append({"label": m["label"], "track_s": float(m["track_s"]), "display_frame": df,
                        "tick": int(round(df * sres / fps)), "scene_s": df / fps,
                        "snap_error_s": df / fps - (start / fps + float(m["track_s"])),
                        "source": (m.get("source") or {}).get("kind")})
    for mk in markers:
        if mk["display_frame"] >= pb1 and fits:
            refusals.append("MARKER_PAST_SCENE_END: %r frame %d" % (mk["label"], mk["display_frame"]))
    plan = {"refusals": refusals, "warnings": warnings, "land_tick_outer": land_outer, "land_s": land_outer / sres,
            "option": option, "frames_by_option": frames, "seconds_by_option": {k: v / fps for k, v in frames.items()},
            "start_frame": start, "start_s": start / fps, "end_frame": end, "end_s": end / fps,
            "clip_frames": clip_frames, "duration_s": duration_s, "fps": fps, "scene_res": sres,
            "playback": [pb0, pb1], "scene_end_s": pb1 / fps, "fits": fits,
            "overrun_s": max(0.0, (end - pb1) / fps), "headroom_s": max(0.0, (pb1 - end) / fps),
            "needed_end_frame": end, "needed_end_s": end / fps, "markers": markers}
    if not fits and facts.get("scene_label"):
        plan["extend_mode_suggestion"] = {"scene_label": facts["scene_label"], "new_end_s": round(end / fps, 4),
                                          "dry_run": True,
                                          "note": "minimum; the conductor may add a tail. Saved/CodexSoftGoods/"
                                                  "extend_scene_playback_mode.json"}
    return plan


def overlapping_audio(existing, start_s, end_s, eps=1.0e-6):
    """existing: [{scene_span: [a, b] or None, ...}] -> those overlapping [start_s, end_s). Unbounded spans overlap."""
    out = []
    for e in existing:
        span = e.get("scene_span")
        if span is None or span[0] is None or span[1] is None:
            out.append(e)
        elif span[0] < end_s - eps and span[1] > start_s + eps:
            out.append(e)
    return out


def go_report(markers, plan):
    """[prec scene_narration_standin.py:255-268]; default mode in a Scene is HOLD [prec cue_list_tool.py:62]."""
    out = []
    lo, hi = plan.get("start_s"), None
    if lo is not None:
        hi = min(plan["scene_end_s"], lo + plan["duration_s"])
    for m in markers:
        parsed = parse_go_label(m["label"])
        if parsed is None:
            continue
        hold = parsed[2] != 0
        inside = lo is not None and lo - 1e-6 <= m["scene_s"] < hi
        out.append({"label": m["label"], "hold": hold, "scene_s": round(m["scene_s"], 4), "sequence": m["sequence"],
                    "inside_audio": bool(inside), "pauses_audio": bool(inside and hold)})
    return out


def live_gates(state):
    """Refusals from editor state: mode, confirm, pie, sequencer_blocks, census, records_exist, records_applied,
    decided_by, assets_exist."""
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % state.get("mode"))
    want = "%s %s" % (mode, CONFIRM_WORD)
    if state.get("confirm") != want:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), want))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_blocks"):
        r.append("SEQUENCER_OPEN_ON_TARGET: %s" % state["sequencer_blocks"])
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode in ("DRY", "APPLY") and state.get("records_exist"):
        r.append("RECORD_EXISTS: %s (REVERT first, or archive by hand)" % state["records_exist"])
    if mode == "APPLY":
        if not str(state.get("decided_by") or "").strip():
            r.append("NOT_DECIDED: args decided_by is empty")
        if state.get("assets_exist"):
            r.append("ASSET_EXISTS: %s (create-only)" % ", ".join(state["assets_exist"]))
    if mode == "REVERT":
        missing = state.get("records_not_applied") or []
        if missing:
            r.append("NO_APPLIED_RECORD: %s" % missing)
    return r


def census_gate(census, expected_content):
    out = []
    got, want = sorted(census.get("content") or []), sorted(expected_content)
    if got != want:
        out.append("TOUCHED_CENSUS: extra=%s missing=%s" % (sorted(set(got) - set(want)), sorted(set(want) - set(got))))
    if census.get("maps"):
        out.append("MAP_DIRTY: %s" % census["maps"])
    return out


def descriptor_key(d):
    return json.dumps(d, sort_keys=True)


def track_descriptor(track_name, sound_path, start, end):
    return {"cls": "MovieSceneAudioTrack", "name": track_name,
            "sections": [{"start": int(start), "end": int(end), "sound": sound_path, "looping": False}]}


def marker_pairs(markers):
    return sorted((int(m["tick"]), str(m["label"])) for m in markers)


def apply_scene(seq, track_name, sound_path, plan):
    """Add ONE track + section + the markers via the adapter; judge by re-listing. Returns (before, failures)."""
    before = {"tracks": seq.list_tracks(), "markers": seq.list_markers()}
    if any(d["name"] == track_name for d in before["tracks"]):
        return before, ["TRACK_EXISTS: %r" % track_name]
    have = set(m["label"] for m in before["markers"])
    clash = [m["label"] for m in plan["markers"] if m["label"] in have]
    if clash:
        return before, ["MARKER_LABEL_EXISTS: %s" % clash]
    track = seq.add_audio_track(track_name)
    seq.add_audio_section(track, sound_path, plan["start_frame"], plan["end_frame"])
    for m in plan["markers"]:
        seq.add_marker(m["tick"], m["label"])
    failures = []
    want_t = sorted([descriptor_key(d) for d in before["tracks"]] +
                    [descriptor_key(track_descriptor(track_name, sound_path, plan["start_frame"], plan["end_frame"]))])
    got_t = sorted(descriptor_key(d) for d in seq.list_tracks())
    if got_t != want_t:
        failures.append("APPLY_READBACK_TRACKS: extra %s missing %s" % (
            sorted(set(got_t) - set(want_t))[:2], sorted(set(want_t) - set(got_t))[:2]))
    want_m = sorted(marker_pairs(before["markers"]) + marker_pairs(plan["markers"]))
    if sorted(marker_pairs(seq.list_markers())) != want_m:
        failures.append("APPLY_READBACK_MARKERS")
    return before, failures


def drift_since_apply(tracks, markers, row):
    """Failures unless the Scene is exactly the recorded before-state + our track + our markers."""
    out = []
    ours = descriptor_key(row["added_track"])
    keys = [descriptor_key(d) for d in tracks]
    if keys.count(ours) != 1:
        out.append("OUR_TRACK_COUNT: %d" % keys.count(ours))
    if sorted(k for k in keys if k != ours) != sorted(descriptor_key(d) for d in row["tracks_before"]):
        out.append("OTHER_TRACKS_CHANGED_SINCE_APPLY")
    if marker_pairs(markers) != sorted(marker_pairs(row["markers_before"]) + marker_pairs(row["added_markers"])):
        out.append("MARKERS_CHANGED_SINCE_APPLY")
    return out


def revert_scene(seq, row):
    """Remove our track and markers. Returns failures (empty = exactly the recorded before-state)."""
    bad = drift_since_apply(seq.list_tracks(), seq.list_markers(), row)
    if bad:
        return ["STATE_DRIFTED: " + f for f in bad]
    seq.remove_matching_track(row["added_track"])
    ours = set(marker_pairs(row["added_markers"]))
    live = seq.list_markers()
    for i in sorted((i for i, m in enumerate(live) if (int(m["tick"]), str(m["label"])) in ours), reverse=True):
        seq.delete_marker(i)
    out = []
    if sorted(descriptor_key(d) for d in seq.list_tracks()) != sorted(descriptor_key(d) for d in row["tracks_before"]):
        out.append("REVERT_TRACKS_NOT_EXACT")
    if marker_pairs(seq.list_markers()) != marker_pairs(row["markers_before"]):
        out.append("REVERT_MARKERS_NOT_EXACT")
    return out


def sound_paths(args):
    folder = args["dest_folder"].rstrip("/")
    return {k: "%s/%s" % (folder, row["asset_name"]) for k, row in sorted(args["scenes"].items())}


def write_record_exclusive(path, data):
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


def summary(plans):
    return "|".join("S%s=frame%d(%.3fs)%s" % (k, p["start_frame"], p["start_s"],
                                             "" if p["fits"] else ",OVERRUN_need_end=%.3fs_have=%.3fs"
                                             % (p["needed_end_s"], p["scene_end_s"]))
                    for k, p in sorted(plans.items()) if "start_frame" in p)


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
    unreal.log_error("SCENEAUDIO_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _content_file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


class _LiveSeq(object):
    """Adapter over one Scene LevelSequence's ROOT tracks and marked frames."""

    def __init__(self, seq):
        self.seq = seq
        self.unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION

    @staticmethod
    def _section_row(s):
        row = {"start": int(s.get_start_frame()) if s.has_start_frame() else None,
               "end": int(s.get_end_frame()) if s.has_end_frame() else None}
        if isinstance(s, unreal.MovieSceneAudioSection):
            row["sound"] = _path(s.get_sound())
            row["looping"] = bool(s.get_looping())
        return row

    def _rows(self):
        return [(t, {"cls": t.get_class().get_name(), "name": str(t.get_display_name()),
                     "sections": [self._section_row(s) for s in t.get_sections()]}) for t in self.seq.get_tracks()]

    def list_tracks(self):
        return [r[1] for r in self._rows()]

    def list_markers(self):
        return [{"tick": int(m.get_editor_property("frame_number").value), "label": str(m.get_editor_property("label"))}
                for m in unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(self.seq, self.unit)]

    def add_audio_track(self, name):
        track = self.seq.add_track(unreal.MovieSceneAudioTrack)
        if track is None:
            raise RuntimeError("ADD_TRACK_NONE")
        track.set_display_name(name)
        return track

    def add_audio_section(self, track, sound_path, start, end):     # scene_narration_standin.py:474-488 [prec]
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
        if section.get_looping() or (hasattr(section, "get_play_until_finished") and section.get_play_until_finished()):
            raise RuntimeError("LOOP_OR_PLAY_UNTIL_FINISHED_STILL_SET")   # setters lie: read back

    def add_marker(self, tick, label):     # choreo_song_markers_refresh.py:537-549 [prec]
        mf = unreal.MovieSceneMarkedFrame()
        mf.set_editor_property("frame_number", unreal.FrameNumber(int(tick)))
        mf.set_editor_property("label", label)
        unreal.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(self.seq, mf, self.unit)

    def delete_marker(self, index):
        self.seq.delete_marked_frame(int(index))

    def remove_matching_track(self, descriptor):
        key = descriptor_key(descriptor)
        for t, row in self._rows():
            if descriptor_key(row) == key:
                self.seq.remove_track(t)     # return value ignored on purpose; the caller re-lists

    def remove_new(self, before, track_name, labels):
        """Failure path: remove our-named tracks and our-labelled markers not in the before-state."""
        keep = set(descriptor_key(d) for d in before["tracks"])
        for t, row in self._rows():
            if row["name"] == track_name and descriptor_key(row) not in keep:
                self.seq.remove_track(t)
        old = set((m["tick"], m["label"]) for m in before["markers"])
        live = self.list_markers()
        for i in sorted((i for i, m in enumerate(live) if m["label"] in labels and (m["tick"], m["label"]) not in old),
                        reverse=True):
            self.delete_marker(i)


def _root_land(rise, n, problems):
    """[prec scene_narration_standin.py:504-532]"""
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
    if not (cname == ROOT_CHANNEL_NAME or cname.startswith(ROOT_CHANNEL_NAME + "_")):
        problems.append("ROOT_CHANNEL_NAME: %r" % cname)
        return None
    keys = sorted((int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                   float(k.get_value())) for k in ch.get_keys())
    if len(keys) < 2:
        problems.append("ROOT_KEYS: %d" % len(keys))
        return None
    return {"land_tick": keys[-1][0], "first": keys[0], "last": keys[-1], "count": len(keys)}


def _walk(seq, origin_s, clip, depth, visited, markers_out, audio_out):
    """Markers (GO candidates) and audio sections of a sequence + nested sub/shot sequences, in Scene seconds.
    origin_s: Scene time of this sequence's playback start; clip: [lo, hi] Scene seconds of the nesting section.
    Read-only; mirrors scene_narration_standin.py:535-557 [prec] (+ audio)."""
    if seq is None or depth > 4 or _path(seq) in visited:
        return
    visited.add(_path(seq))
    tr = _rate(seq.get_tick_resolution())
    pb0 = seq.get_playback_start_seconds()
    for m in seq.get_marked_frames():
        markers_out.append({"label": str(m.get_editor_property("label")), "sequence": _path(seq),
                            "scene_s": origin_s + (m.get_editor_property("frame_number").value / tr - pb0)})
    for t in seq.get_tracks():
        if isinstance(t, unreal.MovieSceneAudioTrack):
            for a in t.get_sections():
                lo = origin_s + (a.get_start_frame_seconds() - pb0) if a.has_start_frame() else None
                hi = origin_s + (a.get_end_frame_seconds() - pb0) if a.has_end_frame() else None
                if clip is not None:
                    lo = clip[0] if lo is None else max(lo, clip[0])
                    hi = clip[1] if hi is None else min(hi, clip[1])
                if lo is not None and hi is not None and hi <= lo:
                    continue                      # wholly outside its nesting section: never audible
                audio_out.append({"sequence": _path(seq), "depth": depth, "track": str(t.get_display_name()),
                                  "sound": _path(a.get_sound()), "active": bool(a.is_active()),
                                  "scene_span": [None if lo is None else round(lo, 4), None if hi is None else round(hi, 4)]})
            continue
        if not isinstance(t, unreal.MovieSceneSubTrack) or t.get_class().get_name() == CHOREO_TRACK_CLASS:
            continue
        for s in t.get_sections():
            child = s.get_sequence()
            if child is None or not s.has_start_frame():
                continue
            off = s.get_editor_property("parameters").get_editor_property("start_frame_offset").value
            off_s = off / _rate(child.get_tick_resolution())
            s_lo = origin_s + (s.get_start_frame_seconds() - pb0)
            s_hi = origin_s + (s.get_end_frame_seconds() - pb0) if s.has_end_frame() else None
            sub_clip = [s_lo if clip is None else max(s_lo, clip[0]),
                        s_hi if clip is None else (clip[1] if s_hi is None else min(s_hi, clip[1]))]
            _walk(child, s_lo - off_s, sub_clip, depth + 1, visited, markers_out, audio_out)


def _scene_cue(n):
    show = unreal.load_asset(SHOW_PATH)
    out = []
    if show is None:
        return out
    for cue in show.get_editor_property("cues"):
        if cue.get_editor_property("type") != unreal.InfinityCueType.SCENE:
            continue
        label = str(cue.get_editor_property("label"))
        if label == "Scene %d" % n or label.startswith("Scene %d " % n):
            scene = cue.get_editor_property("scene")
            out.append({"label": label, "sequence": _path(scene.get_editor_property("sequence")),
                        "external_sound": str(scene.get_editor_property("external_sound"))})
    return out


def _gather_scene(n, row, actors):
    """Live facts for one Scene as plain data (read-only). [prec scene_narration_standin.py:577-649]"""
    problems, warnings = [], []
    seq = unreal.load_asset(row["scene_sequence"])
    rise = unreal.load_asset(row["rise"])
    if seq is None or rise is None:
        problems.append("ASSET_MISSING: scene=%s rise=%s" % (seq is not None, rise is not None))
        return None, problems, warnings, None
    found = _scene_cue(n)
    if len(found) != 1:
        problems.append("SCENE_CUE_COUNT: %d" % len(found))
    elif found[0]["sequence"] != row["scene_sequence"]:
        problems.append("SCENE_CUE_SEQUENCE: Show plays %s, args say %s" % (found[0]["sequence"], row["scene_sequence"]))
    sres, fps = _rate(seq.get_tick_resolution()), _rate(seq.get_display_rate())
    rres, rfps = _rate(rise.get_tick_resolution()), _rate(rise.get_display_rate())
    hits = [(t, s) for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            for s in t.get_sections() if _path(s.get_sequence()) == row["rise"]]
    facts = {"scene": n, "scene_sequence": row["scene_sequence"], "rise": row["rise"], "scene_res": sres, "fps": fps,
             "rise_res": rres, "rise_fps": rfps,
             "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
             "rise_lower_tick": int(round(rise.get_playback_start() * rres / rfps)),
             "rise_upper_tick": int(round(rise.get_playback_end() * rres / rfps)),
             "scene_label": found[0]["label"] if len(found) == 1 else None,
             "external_sound": found[0]["external_sound"] if len(found) == 1 else None,
             "markers_locked": bool(seq.are_marked_frames_locked())}
    if facts["markers_locked"]:
        problems.append("MARKERS_LOCKED: %s (unlock in Sequencer first; refused rather than override)" % row["scene_sequence"])
    if len(hits) != 1:
        problems.append("RISE_SUBSECTION_COUNT: %d (FindMotionSection matches by sequence)" % len(hits))
        return facts, problems, warnings, seq
    track, s = hits[0]
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
    facts.update({"land_tick_inner": land["land_tick"], "root_keys_first_last": [land["first"], land["last"]],
                  "root_key_count": land["count"]})
    if abs(land["last"][1]) > 1e-3 or abs(land["first"][1] + 90.0) > 1e-3:
        warnings.append("ROOT_VALUES_UNEXPECTED: first %r last %r (want -90 -> 0)" % (land["first"], land["last"]))
    arrivals = [a for a in actors if str(a.get_actor_label()) == ARRIVAL_LABEL % n]
    facts["strike_after_land_s"] = None
    if len(arrivals) == 1:
        motion = arrivals[0].get_editor_property("motion_sequence")
        facts["arrival_motion"] = _path(motion) if motion else None
        if facts["arrival_motion"] != row["rise"]:
            warnings.append("ARRIVAL_MOTION_SEQUENCE: %r" % facts["arrival_motion"])
        timing = arrivals[0].get_editor_property("hangar_timing")
        facts["strike_after_land_s"] = float(timing.get_editor_property("strike_after_land_seconds"))
    else:
        warnings.append("ARRIVAL_COUNT: %d (land_plus_strike unavailable)" % len(arrivals))
    markers, audio = [], []
    _walk(seq, seq.get_playback_start_seconds(), None, 0, set(), markers, audio)
    facts["markers_all"] = markers
    facts["existing_audio"] = audio
    facts["scene_markers"] = _LiveSeq(seq).list_markers()
    facts["root_tracks"] = _LiveSeq(seq).list_tracks()
    refs = {}
    for w in row.get("watch_sounds") or []:
        exists = unreal.EditorAssetLibrary.does_asset_exist(w)
        refs[w] = {"exists": bool(exists),
                   "referencers": [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(w, False)]
                   if exists else []}
    facts["watch_sounds"] = refs
    return facts, problems, warnings, seq


def _plan_all(args):
    project = _project()
    inputs, refusals = check_inputs(args, project)
    refusals = list(refusals)
    warnings, rows, plans, handles = [], {}, {}, {}
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    for key, row in sorted(args["scenes"].items()):
        n = int(key)
        if row.get("markers"):
            if key not in inputs:
                refusals.append("S%d MARKERS_UNVERIFIED: no WAV facts" % n)
            else:
                with open(_abs(project, row["analysis"]), "r", encoding="utf-8") as handle:
                    analysis = json.load(handle)
                refusals += ["S%d %s" % (n, x) for x in verify_markers(row, analysis, inputs[key]["sha256"])]
        facts, problems, warns, seq = _gather_scene(n, row, actors)
        refusals += ["S%d %s" % (n, p) for p in problems]
        warnings += ["S%d %s" % (n, w) for w in warns]
        rows[key], handles[key] = facts, seq
        if facts is None or "land_tick_inner" not in facts:
            continue
        plan = plan_scene(facts, args, row)
        refusals += ["S%d %s" % (n, p) for p in plan["refusals"]]
        warnings += ["S%d %s" % (n, w) for w in plan["warnings"]]
        if "start_frame" not in plan:
            continue
        plan["go"] = go_report(facts["markers_all"], plan)
        if any(g["pauses_audio"] for g in plan["go"]):
            warnings.append("S%d GO_HOLD_INSIDE_AUDIO: %s (a HOLD stops Sequencer audio)"
                            % (n, [g["label"] for g in plan["go"] if g["pauses_audio"]]))
        over = overlapping_audio(facts["existing_audio"], plan["start_s"], plan["end_s"])
        plan["existing_audio_overlapping"] = over
        if over:
            refusals.append("S%d EXISTING_AUDIO_OVERLAP: %s" % (n, json.dumps(over)))
        elif facts["existing_audio"]:
            warnings.append("S%d EXISTING_AUDIO_LEFT_ALONE: %s" % (n, json.dumps(facts["existing_audio"])))
        if any(t["name"] == args["track_name"] for t in facts["root_tracks"]):
            refusals.append("S%d TRACK_EXISTS: %r" % (n, args["track_name"]))
        have = set(m["label"] for m in facts["scene_markers"])
        clash = [m["label"] for m in plan["markers"] if m["label"] in have]
        if clash:
            refusals.append("S%d MARKER_LABEL_EXISTS: %s" % (n, clash))
        plans[key] = plan
    return inputs, rows, plans, refusals, warnings, handles


def _sequencer_blocks(targets):
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    if cur is None:
        return None, None
    cp = _path(cur)
    if cp in targets or cp == MASTER:
        return cp, None

    def nests(s, depth):
        if s is None or depth > 3:
            return False
        for t in s.get_tracks():
            if isinstance(t, unreal.MovieSceneSubTrack):
                for sec in t.get_sections():
                    child = sec.get_sequence()
                    if _path(child) in targets or nests(child, depth + 1):
                        return True
        return False
    if nests(cur, 0):
        return "%s (nests a target Scene)" % cp, None
    return None, "SEQUENCER_OPEN_OTHER: %s" % cp


def _backup(run, suffix, paths):
    folder = os.path.join(_project(), "Backups", "PreSceneAudio-%s%s" % (run, suffix))
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


def _record_path(key):
    return os.path.join(_here(), RECORD_FMT % key)


def run_dry(args, run):
    inputs, rows, plans, refusals, warnings, _h = _plan_all(args)
    existing = [p for p in sound_paths(args).values() if unreal.EditorAssetLibrary.does_asset_exist(p)]
    if existing:
        refusals.append("ASSET_EXISTS: %s" % existing)
    report = {"tool": TOOL, "run": run, "args": args, "inputs": inputs, "facts": rows, "plans": plans,
              "refusals": refusals, "warnings": warnings, "apply_ready": not refusals}
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    for text in refusals:
        unreal.log_warning("SCENEAUDIO_REFUSAL|run=%s|%s" % (run, text))
    for text in warnings:
        unreal.log("SCENEAUDIO_WARNING|run=%s|%s" % (run, text))
    for key, p in sorted(plans.items()):
        unreal.log("SCENEAUDIO_ROW|run=%s|scene=S%s|land_s=%.4f|start=%d|end=%d|scene_end=%d|fits=%d|need_end_s=%.3f|"
                   "markers=%s|existing_audio=%d|overlapping=%d|ext_sound=%s"
                   % (run, key, p["land_s"], p["start_frame"], p["end_frame"], p["playback"][1], int(p["fits"]),
                      p["needed_end_s"], ";".join("%s@%d" % (m["label"], m["display_frame"]) for m in p["markers"]),
                      len(rows[key]["existing_audio"]), len(p["existing_audio_overlapping"]),
                      rows[key].get("external_sound")))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("SCENEAUDIO_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|%s|report=%s"
               % (run, int(not refusals), len(refusals), len(warnings), summary(plans), out))


def _import_sounds(args, inputs):
    tasks = []
    folder = args["dest_folder"].rstrip("/")
    for key, row in sorted(args["scenes"].items()):
        task = unreal.AssetImportTask()                     # scene_narration_standin.py:739-746 [prec]
        task.set_editor_property("filename", inputs[key]["path"])
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", row["asset_name"])
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("save", False)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    failures, facts = [], {}
    for key, path in sorted(sound_paths(args).items()):
        sound = unreal.load_asset(path)
        if not isinstance(sound, unreal.SoundWave):
            failures.append("IMPORT_NOT_SOUNDWAVE_S%s: %s -> %r" % (key, path, type(sound).__name__))
            continue
        dur = float(sound.get_editor_property("duration"))                 # SoundBase.h:200-202 [decl]
        facts[key] = {"duration_s": dur}
        if abs(dur - inputs[key]["duration_s"]) > DURATION_TOL_S:
            failures.append("IMPORT_DURATION_S%s: %.4f vs WAV %.4f" % (key, dur, inputs[key]["duration_s"]))
        try:
            ch = int(sound.get_editor_property("num_channels"))
            facts[key]["num_channels"] = ch
            if ch != inputs[key]["channels"]:
                failures.append("IMPORT_CHANNELS_S%s: %d vs WAV %d" % (key, ch, inputs[key]["channels"]))
        except Exception:  # noqa: BLE001 - property not exposed: recorded as unread, duration still gates
            facts[key]["num_channels"] = "unread"
    return failures, facts


def run_apply(args, run):
    inputs, rows, plans, refusals, warnings, handles = _plan_all(args)
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    if sorted(plans) != sorted(args["scenes"]):
        _stop(run, "PLAN_INCOMPLETE|%s" % sorted(plans))
    sounds = sound_paths(args)
    seq_paths = {k: args["scenes"][k]["scene_sequence"] for k in plans}
    rpaths = {k: _record_path(k) for k in plans}
    if any(os.path.exists(p) for p in rpaths.values()):
        _stop(run, "RECORD_EXISTS|%s" % [p for p in rpaths.values() if os.path.exists(p)])
    backup = _backup(run, "", sorted(seq_paths.values()))
    unreal.log("SCENEAUDIO_BACKUP_OK|run=%s|backup=%s" % (run, backup))
    adapters = {k: _LiveSeq(handles[k]) for k in plans}
    records = {}
    for k in plans:
        records[k] = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "scene": k,
                      "args_row": args["scenes"][k], "track_name": args["track_name"], "backup": backup,
                      "decided_by": args.get("decided_by"), "applied": False, "sound_imported": False,
                      "written": datetime.datetime.now().isoformat(timespec="seconds"),
                      "scene_sequence": seq_paths[k], "sound": sounds[k], "playback_before": rows[k]["playback"],
                      "tracks_before": adapters[k].list_tracks(), "markers_before": adapters[k].list_markers(),
                      "added_track": track_descriptor(args["track_name"], sounds[k], plans[k]["start_frame"],
                                                      plans[k]["end_frame"]),
                      "added_markers": [{"tick": m["tick"], "label": m["label"]} for m in plans[k]["markers"]],
                      "plan": {f: v for f, v in plans[k].items() if f not in ("go",)},
                      "existing_audio": rows[k]["existing_audio"], "watch_sounds": rows[k].get("watch_sounds")}
        write_record_exclusive(rpaths[k], records[k])                   # BEFORE any change (incl. the import)
    failures, sound_facts = _import_sounds(args, inputs)
    for k in plans:
        records[k].update(sound_imported=True, sound_facts=sound_facts.get(k))
        update_record(rpaths[k], records[k])
    befores, touched = {}, []
    if not failures:
        for k in sorted(plans):
            touched.append(k)
            try:
                handles[k].modify()
                befores[k], bad = apply_scene(adapters[k], args["track_name"], sounds[k], plans[k])
                failures += ["S%s %s" % (k, f) for f in bad]
            except Exception as exc:   # noqa: BLE001 - reported, never swallowed silently
                failures.append("S%s WRITE_RAISED: %r" % (k, exc))
            if [int(handles[k].get_playback_start()), int(handles[k].get_playback_end())] != rows[k]["playback"]:
                failures.append("S%s PLAYBACK_RANGE_CHANGED" % k)
    expected = sorted(list(seq_paths.values()) + list(sounds.values()))
    failures += census_gate(_census(), expected)
    if failures:
        errs = []
        for k in touched:
            before = {"tracks": records[k]["tracks_before"], "markers": records[k]["markers_before"]}
            adapters[k].remove_new(before, args["track_name"], set(m["label"] for m in plans[k]["markers"]))
            if sorted(descriptor_key(d) for d in adapters[k].list_tracks()) != \
                    sorted(descriptor_key(d) for d in before["tracks"]) or \
                    marker_pairs(adapters[k].list_markers()) != marker_pairs(before["markers"]):
                errs.append("S%s not restored" % k)
        for k in plans:
            update_record(rpaths[k], dict(records[k], applied=False, failed=failures, restore_errors=errs))
            os.rename(rpaths[k], rpaths[k] + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|scene_restored_in_memory=%s|NOTHING SAVED; imported sounds are unsaved in memory: "
              "Don't-Save restart" % (failures[:10], "exact" if not errs else errs))
    for path in expected:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            for k in plans:
                update_record(rpaths[k], dict(records[k], applied=True, save_failed=path))
            _stop(run, "SAVE_FAILED|%s|records kept (some assets may be saved; REVERT or restore %s)" % (path, backup))
    dd = []
    for k in sorted(plans):
        seq = _LiveSeq(unreal.load_asset(seq_paths[k]))
        dd += ["S%s %s" % (k, f) for f in drift_since_apply(seq.list_tracks(), seq.list_markers(), records[k])]
        if not os.path.isfile(_content_file(sounds[k])):
            dd.append("S%s SOUND_FILE_NOT_ON_DISK" % k)
    if _census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    for k in plans:
        records[k]["applied"] = True
        if dd:
            records[k]["post_save_readback_failed"] = dd
        update_record(rpaths[k], records[k])
    if dd:
        _stop(run, "POST_SAVE_READBACK|%r|records kept (REVERT or restore %s)" % (dd[:8], backup))
    unreal.log("SCENEAUDIO_APPLY_OK|run=%s|%s|track=%s|sounds=%s|markers=%s|backup=%s|records=%s|decided_by=%s"
               % (run, summary(plans), args["track_name"], ",".join(sounds[k] for k in sorted(plans)),
                  ";".join("S%s:%d" % (k, len(plans[k]["markers"])) for k in sorted(plans)), backup,
                  ",".join(rpaths[k] for k in sorted(plans)), args.get("decided_by")))


def run_revert(args, run):
    keys = sorted(args["scenes"])
    records, adapters, failures = {}, {}, []
    for k in keys:
        rec = load_record(_record_path(k))
        if rec.get("world") != EXPECTED_WORLD or not rec.get("applied"):
            _stop(run, "REVERT_RECORD_CONTEXT|S%s" % k)
        seq = unreal.load_asset(rec["scene_sequence"])
        if seq is None:
            _stop(run, "REVERT_SEQUENCE_MISSING|" + rec["scene_sequence"])
        records[k], adapters[k] = rec, (seq, _LiveSeq(seq))
        failures += ["S%s %s" % (k, f) for f in drift_since_apply(adapters[k][1].list_tracks(),
                                                                 adapters[k][1].list_markers(), rec)]
    if failures:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r (restore from the record's backup instead)" % failures[:8])
    paths = sorted(records[k]["scene_sequence"] for k in keys)
    backup = _backup(run, "-revert", paths)
    errs = []
    for k in keys:
        seq, ad = adapters[k]
        seq.modify()
        errs += ["S%s %s" % (k, f) for f in revert_scene(ad, records[k])]
        if [int(seq.get_playback_start()), int(seq.get_playback_end())] != records[k]["playback_before"]:
            errs.append("S%s PLAYBACK_RANGE_CHANGED" % k)
    errs += census_gate(_census(), paths)
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart" % errs[:8])
    for path in paths:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % path)
    final = []
    for k in keys:
        ad = _LiveSeq(unreal.load_asset(records[k]["scene_sequence"]))
        if sorted(descriptor_key(d) for d in ad.list_tracks()) != \
                sorted(descriptor_key(d) for d in records[k]["tracks_before"]):
            final.append("S%s TRACKS_NOT_AS_BEFORE" % k)
        if marker_pairs(ad.list_markers()) != marker_pairs(records[k]["markers_before"]):
            final.append("S%s MARKERS_NOT_AS_BEFORE" % k)
    if _census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if final:
        _stop(run, "REVERT_READBACK|%r" % final)
    deleted = []
    if args.get("delete_assets") is True:
        for k in keys:
            snd = records[k]["sound"]
            refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(snd, False)]
            if refs:
                _stop(run, "DELETE_REFUSED_REFERENCED|%s|%s (scenes already reverted and saved)" % (snd, refs))
            unreal.EditorAssetLibrary.delete_asset(snd)
            if unreal.EditorAssetLibrary.does_asset_exist(snd):
                _stop(run, "DELETE_FAILED|%s" % snd)
            deleted.append(snd)
    archived = []
    for k in keys:
        dst = _record_path(k) + ".reverted-" + run
        os.rename(_record_path(k), dst)
        archived.append(dst)
    unreal.log("SCENEAUDIO_REVERT_OK|run=%s|scenes=%s|sounds_deleted=%s|backup=%s|records=%s"
               % (run, ",".join("S%s" % k for k in keys), ",".join(deleted) or "kept", backup, ",".join(archived)))


def main():
    g = globals()
    args = g.get("SCENEAUDIO_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("SCENEAUDIO-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    rpaths = {k: _record_path(k) for k in args["scenes"]}
    targets = set(row["scene_sequence"] for row in args["scenes"].values())
    block, seq_warn = _sequencer_blocks(targets)
    if seq_warn:
        unreal.log("SCENEAUDIO_WARNING|run=%s|%s" % (run, seq_warn))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_blocks": block, "census": _census(),
             "records_exist": [p for p in rpaths.values() if os.path.exists(p)],
             "records_not_applied": [p for p in rpaths.values()
                                     if not (os.path.exists(p) and load_record(p).get("applied"))],
             "decided_by": args.get("decided_by"),
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
