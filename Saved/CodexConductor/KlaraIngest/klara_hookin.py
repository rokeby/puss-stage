"""KLARA HOOK-IN: swap Klara's Scene sequences into our Scenes (S1 / S2 / S4).
6 Oct, offline-written, NEVER RUN IN UNREAL. Plan and evidence: HOOKIN_PLAN.md (same folder).

Gary 6 Oct: S1 = /Game/KK_S1_Animals/LS_Animals_1, S2 = /Game/KK_S2_Shrine/LS_NEW_SHRINE, S4 = /Game/LS_Children.
Her LS lengths DEFINE our Scene lengths (relengthing approved). Audio "as she set it". Narration rule D57:
S1 re-places the stand-in narration on the first frame after her Animal_Voices end (and sizes S1 to cover it),
else REPORT; S2's narration (frame 104) must fit inside LS_NEW_SHRINE.

Tiers per claim: [decl] header/source we can read, [prec] in-repo precedent (cited), [meas] read from bytes or an
earlier record, [inf] inferred (why stated). Every API marked [inf] is probed by DRY into report["api_table"].

MECHANISM (recommendation (a), HOOKIN_PLAN.md section 2): her bindings are FULL soft paths into her maps
([meas] e.g. /Game/KK_S1_Animals/L_Animals.L_Animals:PersistentLevel.CineCameraActor_7, decoded from the
LS soft-object-path table), so her levels are added to OUR show world as plain (non-instanced) streaming
sublevels at IDENTITY, and each Scene's existing nested section is RETARGETED to her LS.

STAGES (args "mode"):
  DRY            read-only. Live Show/Scene/her-LS facts, streaming levels, cut-binding verdicts per cue, the API
                 table, and the pure plan per Scene. Writes klara_hookin_dry.json. Marker KLARAHOOK_DRY_OK.
  APPLY_STREAM   add her levels as LevelStreamingDynamic at identity (initially loaded, initially hidden [inf]);
                 saves ONLY the show map. Record klara_hookin_stream_record.json + .umap backup BEFORE the change.
  REVERT_STREAM  removes exactly the recorded streaming levels; saves only the map.
  APPLY_SEQ      per Scene: retarget the nested section (sequence, range, start offset 0), narration re-place
                 (S1 voices rule), optional Level Visibility track; saves ONLY LS_DevScene_0N.
                 Record klara_hookin_seq_record.json + .uasset backups BEFORE any change.
                 It does NOT change playback ranges: the DRY/APPLY report carries a ready mode body for
                 Saved/CodexSoftGoods/extend_scene_playback.py per Scene (end + rematch + cut coverage + Master
                 rebuild + exact saves), which is the house route for any Scene length change
                 (Docs/SceneImportCameras_2026-09-30.md section 3.3 [decl]).
  REVERT_SEQ     drift-gated restore of the recorded before-state; saves only the Scene sequences.
Confirm: "<MODE> KLARAHOOK" for every mode but DRY. Guards: no PIE/SIE, show world open, census CLEAN before,
Sequencer not open, after the edit the census must be EXACTLY the expected packages.
Never: Save All, reload a level, open/scrub Sequencer, touch Show/Master (the extend tool does that), end PIE;
no unreal objects in module globals. Importing without `unreal` runs nothing (test_klara_hookin_offline.py).
"""
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "klara_hookin"
CONFIRM_WORD = "KLARAHOOK"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                     # extend_scene_playback.py:44
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"            # extend_scene_playback.py:45
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # extend_scene_playback.py:46
ARGS_NAME = "klara_hookin_args.json"
DRY_NAME = "klara_hookin_dry.json"
STREAM_RECORD = "klara_hookin_stream_record.json"
SEQ_RECORD = "klara_hookin_seq_record.json"
MODES = ("DRY", "APPLY_STREAM", "REVERT_STREAM", "APPLY_SEQ", "REVERT_SEQ")
START_OPTIONS = ("keep", "land", "land_plus_strike", "at_s")
NARRATION_RULES = ("after_voices", "inside_shot", "none")
VIS_TRACK_NAME = "Klara Levels (hookin)"
CHOREO_TRACK_CLASS = "MovieSceneInfinityChoreoTrack"
ROOT_BINDING = "S%s Hangar Root"          # scene_audio_import.py:74 [prec]
ROOT_CHANNEL_INDEX = 4                    # scene_audio_import.py:75 [prec]
ROOT_CHANNEL_NAME = "Rotation.Y"          # scene_audio_import.py:76 [prec]
ARRIVAL_LABEL = "S%s Arrival"             # scene_audio_import.py:77 [prec]
FRAME_EPS = 1.0e-6
RATE_TOL_S = 0.5 / 24000.0 * 4            # scene_audio_import.py:89 [prec]


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: time maths (harnessed with +/- controls in test_klara_hookin_offline.py)
# =====================================================================================================================

def ceil_frames(seconds, fps):
    """First display frame at or after `seconds` (tolerant of float noise: 208.64 s x 25 is frame 5216, not 5217)."""
    return int(math.ceil(float(seconds) * float(fps) - FRAME_EPS))


def her_span(lower_frame, upper_frame, her_fps, her_tick):
    """Her playback range [lower, upper) in her display frames -> ticks and seconds. Ticks per frame must be whole
    (24000/30 = 800 [meas census: tick 24000, display 30]); a fractional ratio means her frames are not on her tick
    grid and the plan refuses."""
    tpf = float(her_tick) / float(her_fps)
    if abs(tpf - round(tpf)) > 1e-9:
        raise PlanError("HER_TICKS_PER_FRAME_NOT_WHOLE: %r" % tpf)
    tpf = int(round(tpf))
    lo, hi = int(lower_frame) * tpf, int(upper_frame) * tpf
    if hi <= lo:
        raise PlanError("HER_RANGE_EMPTY: [%d, %d)" % (lower_frame, upper_frame))
    return {"lower_tick": lo, "upper_tick": hi, "len_tick": hi - lo, "len_s": (hi - lo) / float(her_tick),
            "lower_s": lo / float(her_tick), "upper_s": hi / float(her_tick), "ticks_per_frame": tpf}


def outer_frames(len_s, outer_fps):
    """Her length in OUR display frames. exact = len_s x fps; frames = ceil. Off-grid lengths (e.g. 210.6 s at 24 fps =
    5054.4) are ceiled so her last frame is never cut, and the hold is reported."""
    exact = float(len_s) * float(outer_fps)
    frames = int(math.ceil(exact - FRAME_EPS))
    on_grid = abs(exact - round(exact)) <= 1e-6
    return {"exact": exact, "frames": frames, "on_grid": on_grid, "hold_s": (frames - exact) / float(outer_fps)}


def inner_to_scene_s(inner_tick, her_tick, section_start_s, her_lower_tick, start_offset_tick=0, play_rate=1.0):
    """Her inner time -> Scene seconds for a rate-1 sub-section. Same mapping as scene_audio_import.inner_to_outer_tick
    [prec :235-241; decl InfinityStageArrival.cpp:1044-1048 per that tool]: the section start plays her playback
    START (lower bound) + StartFrameOffset, so her NEGATIVE start (S1: -10.333 s) needs no special handling."""
    if play_rate <= 0:
        raise PlanError("PLAY_RATE_NONPOSITIVE: %r" % play_rate)
    return float(section_start_s) + (float(inner_tick) - float(her_lower_tick) - float(start_offset_tick)) / \
        float(her_tick) / float(play_rate)


def choose_start(option, facts, row):
    """Section start frame in the Scene. keep = where the current nested section starts (live); land / land_plus_strike
    = the hangar land (+ strike) frames (live, scene_audio_import port); at_s = explicit seconds in args."""
    if option == "keep":
        tgt = facts.get("target") or {}
        return tgt.get("start"), "current nested section start"
    if option == "land":
        return facts.get("land_frame"), "hangar land key"
    if option == "land_plus_strike":
        return facts.get("strike_frame"), "hangar land + StrikeAfterLandSeconds"
    if option == "at_s":
        if not isinstance(row.get("at_s"), (int, float)):
            return None, "at_s missing"
        return ceil_frames(row["at_s"], facts["fps"]), "args at_s"
    return None, "unknown option"


def plan_narration(rule, facts, row, section, her, fps):
    """-> dict(action, frames, reason, refusals, covers_end). action: move | keep | report | none."""
    out = {"rule": rule, "refusals": [], "warnings": []}
    narr = facts.get("narration")
    if rule == "none":
        out.update(action="none", reason="no narration rule for this Scene")
        return out
    if not narr:
        out.update(action="report", reason="no narration track %r in the Scene" % row.get("narration_track"))
        out["warnings"].append("NARRATION_TRACK_ABSENT")
        return out
    length = int(narr["end"]) - int(narr["start"])
    out["current"] = [int(narr["start"]), int(narr["end"])]
    out["current_s"] = [narr["start"] / fps, narr["end"] / fps]
    if rule == "after_voices":
        pat = str(row.get("voices_pattern") or "Animal_Voices")
        voices = [a for a in her.get("audio") or [] if pat in str(a.get("sound"))]
        out["voices_found"] = voices
        override = row.get("narration_override_start_s")
        if voices:
            v_end_s = max(a["scene_end_s"] for a in voices)
            start = ceil_frames(v_end_s, fps)
            out.update(action="move", voices_end_s=v_end_s, frames=[start, start + length],
                       reason="first frame after her %s ends" % pat, covers_end=True)
        elif isinstance(override, (int, float)):
            start = ceil_frames(override, fps)
            out.update(action="move", frames=[start, start + length], reason="args narration_override_start_s",
                       covers_end=True)
        else:
            out.update(action="report", frames=out["current"], covers_end=False,
                       reason="her LS has no audio matching %r: rule D57 says REPORT (narration left where it is)" % pat)
            out["warnings"].append("NO_VOICES_IN_HER_LS: her audio = %s" % [a.get("sound") for a in her.get("audio") or []])
            if narr["end"] > section[1]:
                out["refusals"].append(
                    "NARRATION_PAST_HER_END: narration [%.3f, %.3f) s ends after her shot ends %.3f s; with no voices "
                    "the rule only reports - decide (Directing): set narration_override_start_s, or accept a longer "
                    "Scene via tail_s" % (narr["start"] / fps, narr["end"] / fps, section[1] / fps))
        return out
    if rule == "inside_shot":
        inside = section[0] <= narr["start"] and narr["end"] <= section[1]
        out.update(action="keep", frames=out["current"], covers_end=False, inside=inside,
                   reason="narration must lie inside her shot")
        if not inside:
            out["refusals"].append(
                "NARRATION_NOT_INSIDE_SHOT: narration [%d, %d) = %.3f s long at %.3f s; her shot [%d, %d) = %.3f s. "
                "It cannot fit unless the narration is shortened/moved or the shot is held/looped (Gary/Directing)"
                % (narr["start"], narr["end"], length / fps, narr["start"] / fps, section[0], section[1],
                   (section[1] - section[0]) / fps))
        return out
    out.update(action="report", reason="unknown rule %r" % rule)
    out["refusals"].append("NARRATION_RULE_UNKNOWN: %r" % rule)
    return out


def plan_scene(facts, row):
    """facts (plain data, see HOOKIN_PLAN.md section 6) + args row -> plan. Never raises for content problems; they are
    refusals. Planned end = max(her section end, narration end when the rule moves it) + tail_s, in Scene frames."""
    refusals, warnings = [], []
    fps = float(facts["fps"])
    tick = float(facts["tick"])
    her = facts.get("her") or {}
    plan = {"scene": facts.get("scene"), "label": facts.get("label"), "fps": fps, "refusals": refusals,
            "warnings": warnings}
    if not her.get("exists"):
        refusals.append("HER_LS_MISSING: %s" % row.get("her_sequence"))
        return plan
    tgt = facts.get("target")
    if not tgt:
        refusals.append("TARGET_SECTION_NOT_FOUND: no root sub-section plays %s" % row.get("current_nested"))
        return plan
    if tgt.get("count", 1) != 1:
        refusals.append("TARGET_SECTION_COUNT: %d sections play %s" % (tgt["count"], row.get("current_nested")))
    try:
        span = her_span(her["lower_frame"], her["upper_frame"], her["fps"], her["tick"])
    except PlanError as exc:
        refusals.append(str(exc))
        return plan
    if abs(float(her["tick"]) - tick) > 1e-9:
        warnings.append("TICK_RESOLUTIONS_DIFFER: hers %r ours %r (Sequencer converts; harness covers the maths)"
                        % (her["tick"], tick))
    length = outer_frames(span["len_s"], fps)
    if not length["on_grid"]:
        warnings.append("LENGTH_OFF_GRID: %.4f s x %g fps = %.3f frames; ceiled to %d (holds %.4f s past her end)"
                        % (span["len_s"], fps, length["exact"], length["frames"], length["hold_s"]))
    option = row.get("start_option", "keep")
    start, why = choose_start(option, facts, row)
    cands = {}
    for opt in START_OPTIONS:
        f, _w = choose_start(opt, facts, row)
        if f is not None:
            cands[opt] = {"start": f, "start_s": f / fps, "end": f + length["frames"],
                          "end_s": (f + length["frames"]) / fps}
    plan.update({"her_span": span, "her_fps": her["fps"], "length": length, "start_option": option,
                 "start_why": why, "start_candidates": cands})
    if start is None:
        refusals.append("START_UNKNOWN: option %r (%s)" % (option, why))
        return plan
    pb0, pb1 = int(facts["playback"][0]), int(facts["playback"][1])
    if start < pb0:
        refusals.append("START_BEFORE_PLAYBACK: %d < %d" % (start, pb0))
    section = [int(start), int(start) + length["frames"]]
    plan["section"] = section
    plan["section_s"] = [section[0] / fps, section[1] / fps]
    plan["start_offset_tick"] = 0
    # Her audio, mapped into the Scene (audio "as she set it": nothing moves, we only report where it lands).
    audio = []
    for a in her.get("audio") or []:
        tpf = span["ticks_per_frame"]
        s = inner_to_scene_s(a["start_frame"] * tpf, her["tick"], section[0] / fps, span["lower_tick"])
        e = inner_to_scene_s(a["end_frame"] * tpf, her["tick"], section[0] / fps, span["lower_tick"])
        audio.append(dict(a, scene_start_s=s, scene_end_s=e))
        if e > section[1] / fps + 1e-6 or s < section[0] / fps - 1e-6:
            warnings.append("HER_AUDIO_OUTSIDE_HER_RANGE: %s [%.3f, %.3f) s (clipped by the section)" % (a["sound"], s, e))
    her = dict(her, audio=audio)
    plan["her_audio_in_scene"] = audio
    narr = plan_narration(row.get("narration_rule", "none"), facts, row, section, her, fps)
    plan["narration"] = narr
    refusals += narr["refusals"]
    warnings += narr["warnings"]
    end = section[1]
    if narr.get("covers_end") and narr.get("frames"):
        end = max(end, int(narr["frames"][1]))
    tail = row.get("tail_s", 0.0)
    if not isinstance(tail, (int, float)) or tail < 0:
        refusals.append("TAIL_INVALID: %r" % tail)
        tail = 0.0
    end += ceil_frames(tail, fps) if tail else 0
    plan["planned_end"] = end
    plan["planned_end_s"] = end / fps
    plan["end_change_s"] = (end - pb1) / fps
    allow = set(row.get("allow_truncate") or [])
    rows = []
    for s in facts.get("root_sections") or []:
        if s.get("is_target") or s.get("is_narration") or s.get("track") == VIS_TRACK_NAME:
            continue
        if s.get("end") is not None and s["end"] > end:
            rows.append(s)
            msg = "SECTION_PAST_PLANNED_END: %s %r [%s, %s) > %d (%.3f s)" % (
                s.get("cls"), s.get("track"), s.get("start"), s.get("end"), end, end / fps)
            if s.get("track") in allow:
                warnings.append(msg + " (allowed by args)")
            else:
                refusals.append(msg)
    plan["sections_past_end"] = rows
    if facts.get("land_frame") is not None and section[0] < facts["land_frame"]:
        warnings.append("SHOT_STARTS_BEFORE_LAND: frame %d < land %d - her cuts outrank our root cuts (memory, measured "
                        "30 Sep S3), so the hangar rise is NOT seen from frame %d" % (section[0], facts["land_frame"],
                                                                                      section[0]))
    plan["extend_mode"] = {"scene_label": facts.get("label"), "new_end_s": round(end / fps, 6), "dry_run": True}
    return plan


# =====================================================================================================================
# Pure: args, gates, records
# =====================================================================================================================

def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in MODES:
        r.append("MODE_INVALID: %r" % args.get("mode"))
    scenes = args.get("scenes") or {}
    if not scenes:
        r.append("NO_SCENES")
    for key, row in sorted(scenes.items()):
        if not str(key).isdigit():
            r.append("SCENE_KEY_NOT_A_NUMBER: %r" % key)
        for field in ("scene_sequence", "current_nested", "her_sequence", "start_option", "narration_rule"):
            if field not in row:
                r.append("S%s_MISSING_%s" % (key, field.upper()))
        if row.get("start_option") not in START_OPTIONS:
            r.append("S%s_START_OPTION_INVALID: %r" % (key, row.get("start_option")))
        if row.get("narration_rule") not in NARRATION_RULES:
            r.append("S%s_NARRATION_RULE_INVALID: %r" % (key, row.get("narration_rule")))
        for f in ("scene_sequence", "current_nested", "her_sequence"):
            if f in row and not str(row[f]).startswith("/Game/"):
                r.append("S%s_%s_NOT_GAME_PATH" % (key, f.upper()))
        if "Master" in str(row.get("scene_sequence", "")):
            r.append("S%s_TARGET_IS_THE_MASTER" % key)
    for lv in args.get("levels") or []:
        if not str(lv).startswith("/Game/"):
            r.append("LEVEL_NOT_GAME_PATH: %r" % lv)
    return r


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode != "DRY" and state.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s %s" % (mode, CONFIRM_WORD)))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("wrong_world"):
        r.append("WRONG_WORLD: %s" % state["wrong_world"])
    if state.get("sequencer_open"):
        r.append("SEQUENCER_OPEN: %s (close it; opening/scrubbing dirties the map)" % state["sequencer_open"])
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode.startswith("APPLY") and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode in ("APPLY_STREAM", "APPLY_SEQ") and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
    if mode in ("REVERT_STREAM", "REVERT_SEQ") and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def census_gate(census, expected_content, expected_maps):
    out = []
    if sorted(census.get("content") or []) != sorted(expected_content):
        out.append("CONTENT_CENSUS: got %s want %s" % (sorted(census.get("content") or []), sorted(expected_content)))
    if sorted(census.get("maps") or []) != sorted(expected_maps):
        out.append("MAP_CENSUS: got %s want %s" % (sorted(census.get("maps") or []), sorted(expected_maps)))
    return out


def seq_drift(live, rec):
    """Failures unless the Scene is exactly the recorded AFTER state (what APPLY_SEQ wrote)."""
    out = []
    for k in ("sequence", "start", "end", "start_offset_tick"):
        if live["target"].get(k) != rec["after"]["target"].get(k):
            out.append("TARGET_%s: live %r recorded %r" % (k.upper(), live["target"].get(k), rec["after"]["target"].get(k)))
    if rec["after"].get("narration") != live.get("narration"):
        out.append("NARRATION: live %r recorded %r" % (live.get("narration"), rec["after"].get("narration")))
    if bool(rec["after"].get("vis_track")) != bool(live.get("vis_track")):
        out.append("VIS_TRACK: live %r recorded %r" % (live.get("vis_track"), rec["after"].get("vis_track")))
    return out


def write_record_exclusive(path, data):           # scene_audio_import.py:470-475 [prec]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):                     # scene_audio_import.py:478-484 [prec]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_record(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraIngest")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    if unreal is not None:
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.dirname(os.path.dirname(os.path.dirname(_here())))


def _stop(run, reason):
    unreal.log_error("KLARAHOOK_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _file(path, ext):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ext


def _api_table():
    """[inf] APIs, probed without mutating. Each row: api, tier, how, result."""
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001 - a probe failure is a finding
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("MovieSceneSubSection.set_sequence", "decl MovieSceneSubSection.h:161-162",
          lambda: hasattr(u.MovieSceneSubSection, "set_sequence"))
    probe("MovieSceneSection.set_range (display frames of the owning sequence)",
          "decl MovieSceneSectionExtensions.h:145; frames-unit inf, prec s1_narration_after_voices record 5216 = 208.64 s",
          lambda: hasattr(u.MovieSceneSection, "set_range"))
    probe("MovieSceneSectionExtensions.get_parent_sequence_frame", "decl MovieSceneSectionExtensions.h:255",
          lambda: hasattr(u.MovieSceneSectionExtensions, "get_parent_sequence_frame"))
    probe("MovieSceneSectionParameters.start_frame_offset / time_scale", "decl MovieSceneSectionParameters.h:76,92",
          lambda: [hasattr(u.MovieSceneSectionParameters(), "get_editor_property"),
                   repr(u.MovieSceneSectionParameters().get_editor_property("start_frame_offset")),
                   repr(u.MovieSceneSectionParameters().get_editor_property("time_scale"))])
    probe("MovieSceneLevelVisibilityTrack class", "inf (track class name)",
          lambda: hasattr(u, "MovieSceneLevelVisibilityTrack"))
    probe("MovieSceneLevelVisibilitySection.set_level_names/set_visibility", "decl MovieSceneLevelVisibilitySection.h:43,49",
          lambda: [hasattr(u.MovieSceneLevelVisibilitySection, "set_level_names"),
                   hasattr(u.MovieSceneLevelVisibilitySection, "set_visibility")])
    probe("ELevelVisibility.VISIBLE", "inf (Python enum spelling)", lambda: repr(u.ELevelVisibility.VISIBLE))
    probe("EditorLevelUtils.add_level_to_world / remove_level_from_world / get_levels",
          "decl EditorLevelUtils.h:243-244, 260-261, 419-420",
          lambda: [hasattr(u.EditorLevelUtils, n) for n in ("add_level_to_world", "remove_level_from_world", "get_levels")])
    probe("LevelStreamingDynamic initially_loaded / initially_visible", "inf (property names)",
          lambda: [u.LevelStreamingDynamic.get_default_object().get_editor_property(n)
                   for n in ("initially_loaded", "initially_visible")])
    probe("LevelStreaming.get_world_asset_package_name", "inf",
          lambda: hasattr(u.LevelStreaming, "get_world_asset_package_name"))
    probe("InfinityStageCameraPilotLibrary.check_scene_cut_bindings", "decl InfinityStageCameraPilotLibrary.h:141-146; "
          "Python return shape inf (out-params -> tuple)",
          lambda: hasattr(u.InfinityStageCameraPilotLibrary, "check_scene_cut_bindings"))
    probe("MovieSceneSequence.get_possessables / get_spawnables", "inf",
          lambda: [hasattr(u.MovieSceneSequence, "get_possessables"), hasattr(u.MovieSceneSequence, "get_spawnables")])
    probe("LevelSequenceEditorBlueprintLibrary.get_current_level_sequence", "prec scene_audio_import.py:821",
          lambda: hasattr(u.LevelSequenceEditorBlueprintLibrary, "get_current_level_sequence"))
    return rows


def _cut_bindings(show, cue_guid):
    """Live verdict lines (C++ CheckSceneCutBindings, LocateBoundObjects in the EDITOR world [decl
    InfinityStageCameraPilotLibrary.cpp:767-790]). Return shape normalised; raw type recorded."""
    res = unreal.InfinityStageCameraPilotLibrary.check_scene_cut_bindings(show, cue_guid)
    if isinstance(res, tuple):
        vals = list(res)
        ok = bool(vals[0]) if vals else False
        lines = [str(x) for x in (vals[1] if len(vals) > 1 else [])]
        count = int(vals[2]) if len(vals) > 2 else None
    else:
        ok, lines, count = bool(res), [], None
    return {"ok": ok, "unresolved": count, "lines": lines, "raw_type": type(res).__name__}


def _section_row(track, s, seq_tick, fps):
    row = {"track": str(track.get_display_name()), "cls": track.get_class().get_name(),
           "start": int(s.get_start_frame()) if s.has_start_frame() else None,
           "end": int(s.get_end_frame()) if s.has_end_frame() else None}
    if isinstance(s, unreal.MovieSceneSubSection):
        row["sequence"] = _path(s.get_sequence())
        p = s.get_editor_property("parameters")
        row["start_offset_tick"] = int(p.get_editor_property("start_frame_offset").value)
        row["time_scale_repr"] = repr(p.get_editor_property("time_scale"))[:120]
    if isinstance(s, unreal.MovieSceneAudioSection):
        row["sound"] = _path(s.get_sound())
    return row


def _land_frames(seq, scene_key, problems):
    """Land (+strike) Scene frames. Port of scene_audio_import._root_land/plan_scene [prec :617-642, :261-283]:
    land = the hangar root pitch channel's LAST key in LS_S<n>_HangarRise, mapped out of its sub-section."""
    fps, sres = _rate(seq.get_display_rate()), _rate(seq.get_tick_resolution())
    hits = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            for s in t.get_sections() if s.get_sequence() is not None and "HangarRise" in _path(s.get_sequence())]
    if len(hits) != 1:
        problems.append("RISE_SUBSECTION_COUNT: %d" % len(hits))
        return None, None
    s = hits[0]
    rise = s.get_sequence()
    rres, rfps = _rate(rise.get_tick_resolution()), _rate(rise.get_display_rate())
    rows = [b for b in rise.get_bindings() if str(b.get_display_name()) == ROOT_BINDING % scene_key]
    if len(rows) != 1:
        problems.append("ROOT_BINDING_COUNT: %d" % len(rows))
        return None, None
    secs = [x for t in rows[0].get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack) for x in t.get_sections()]
    if len(secs) != 1:
        problems.append("ROOT_TRANSFORM_SECTIONS: %d" % len(secs))
        return None, None
    chans = list(secs[0].get_all_channels())
    if len(chans) <= ROOT_CHANNEL_INDEX:
        problems.append("ROOT_CHANNELS: %d" % len(chans))
        return None, None
    ch = chans[ROOT_CHANNEL_INDEX]
    name = str(ch.channel_name) if hasattr(ch, "channel_name") else str(ch.get_name())
    if not (name == ROOT_CHANNEL_NAME or name.startswith(ROOT_CHANNEL_NAME + "_")):
        problems.append("ROOT_CHANNEL_NAME: %r" % name)
        return None, None
    keys = sorted(int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value)
                  for k in ch.get_keys())
    if len(keys) < 2:
        problems.append("ROOT_KEYS: %d" % len(keys))
        return None, None
    p = s.get_editor_property("parameters")
    lower = int(round(rise.get_playback_start() * rres / rfps))
    land_outer_s = s.get_start_frame_seconds() + (keys[-1] - lower - int(p.get_editor_property("start_frame_offset").value)) / rres
    land = ceil_frames(land_outer_s, fps)
    strike = None
    actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if str(a.get_actor_label()) == ARRIVAL_LABEL % scene_key]
    if len(actors) == 1:
        timing = actors[0].get_editor_property("hangar_timing")
        strike = ceil_frames(land_outer_s + float(timing.get_editor_property("strike_after_land_seconds")), fps)
    else:
        problems.append("ARRIVAL_COUNT: %d (land_plus_strike unavailable)" % len(actors))
    return land, strike


def _her_facts(path):
    her = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if her is None:
        return {"exists": False, "path": path}
    fps, tick = _rate(her.get_display_rate()), _rate(her.get_tick_resolution())
    out = {"exists": True, "path": path, "fps": fps, "tick": tick,
           "lower_frame": int(her.get_playback_start()), "upper_frame": int(her.get_playback_end()),
           "audio": [], "cuts": [], "bindings": [], "sub_tracks": 0}
    for t in her.get_tracks():
        if isinstance(t, unreal.MovieSceneAudioTrack):
            for a in t.get_sections():
                out["audio"].append({"sound": _path(a.get_sound()), "track": str(t.get_display_name()),
                                     "active": bool(a.is_active()),
                                     "start_frame": int(a.get_start_frame()) if a.has_start_frame() else out["lower_frame"],
                                     "end_frame": int(a.get_end_frame()) if a.has_end_frame() else out["upper_frame"]})
        elif isinstance(t, unreal.MovieSceneCameraCutTrack):
            for c in t.get_sections():
                out["cuts"].append([int(c.get_start_frame()) if c.has_start_frame() else None,
                                    int(c.get_end_frame()) if c.has_end_frame() else None])
        elif isinstance(t, unreal.MovieSceneSubTrack):
            out["sub_tracks"] += 1
    for b in her.get_bindings():
        out["bindings"].append({"name": str(b.get_display_name()),
                                "tracks": sorted(t.get_class().get_name() for t in b.get_tracks())})
    for n in ("get_possessables", "get_spawnables"):
        try:
            out[n.split("_")[1]] = len(getattr(her, n)())
        except Exception as exc:  # noqa: BLE001
            out[n.split("_")[1]] = "unread: %s" % type(exc).__name__
    return out


def _scene_facts(key, row):
    problems = []
    seq = unreal.load_asset(row["scene_sequence"])
    if seq is None:
        return None, ["SCENE_SEQUENCE_MISSING: %s" % row["scene_sequence"]], None
    fps, tick = _rate(seq.get_display_rate()), _rate(seq.get_tick_resolution())
    facts = {"scene": key, "scene_sequence": row["scene_sequence"], "fps": fps, "tick": tick,
             "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())], "root_sections": []}
    targets, narr = [], []
    for t in seq.get_tracks():
        if t.get_class().get_name() == CHOREO_TRACK_CLASS:
            continue
        for s in t.get_sections():
            r = _section_row(t, s, tick, fps)
            if r.get("sequence") == row["current_nested"] or r.get("sequence") == row["her_sequence"]:
                r["is_target"] = True
                targets.append(r)
            if r["track"] == row.get("narration_track") and r["cls"] == "MovieSceneAudioTrack":
                r["is_narration"] = True
                narr.append(r)
            facts["root_sections"].append(r)
    facts["target"] = dict(targets[0], count=len(targets)) if targets else None
    if len(narr) > 1:
        problems.append("NARRATION_SECTIONS: %d" % len(narr))
    facts["narration"] = narr[0] if len(narr) == 1 else None
    facts["vis_track"] = any(t.get_display_name() == VIS_TRACK_NAME for t in seq.get_tracks())
    land_problems = []          # only fatal when the chosen start option needs them (plan -> START_UNKNOWN)
    land, strike = _land_frames(seq, key, land_problems)
    facts["land_frame"], facts["strike_frame"], facts["land_problems"] = land, strike, land_problems
    facts["her"] = _her_facts(row["her_sequence"])
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if c.get_editor_property("type") == unreal.InfinityCueType.SCENE
            and _path(c.get_editor_property("scene").get_editor_property("sequence")) == row["scene_sequence"]]
    if len(cues) != 1:
        problems.append("SCENE_CUE_COUNT: %d play %s" % (len(cues), row["scene_sequence"]))
        facts["label"] = None
    else:
        facts["label"] = str(cues[0].get_editor_property("label"))
        facts["cue_guid"] = unreal.GuidLibrary.conv_guid_to_string(cues[0].get_editor_property("cue_guid"))
        try:
            facts["cut_bindings"] = _cut_bindings(show, cues[0].get_editor_property("cue_guid"))
        except Exception as exc:  # noqa: BLE001 - recorded, not fatal in DRY
            facts["cut_bindings"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    if facts["target"] is not None:
        try:
            # [decl MovieSceneSectionExtensions.h:255] measured mapping of the CURRENT section's inner start.
            sec = _find_target_section(seq, row)
            child = sec.get_sequence()
            facts["target"]["parent_frame_of_inner_start"] = int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(
                sec, int(child.get_playback_start()), seq))
        except Exception as exc:  # noqa: BLE001
            facts["target"]["parent_frame_of_inner_start"] = "unread: %s" % type(exc).__name__
    return facts, problems, seq


def _find_target_section(seq, row, which=("current_nested", "her_sequence")):
    hits = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            and t.get_class().get_name() != CHOREO_TRACK_CLASS for s in t.get_sections()
            if _path(s.get_sequence()) in [row[w] for w in which]]
    if len(hits) != 1:
        raise PlanError("TARGET_SECTION_COUNT: %d" % len(hits))
    return hits[0]


def _streaming_levels(world):
    """Package names of the world's loaded sublevels [decl EditorLevelUtils.h:419-420 get_levels]."""
    out = []
    for lv in unreal.EditorLevelUtils.get_levels(world):
        out.append(_path(lv.get_outer()) if lv.get_outer() is not None else None)
    return out


def _sequencer_open():
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    return _path(cur) if cur is not None else None


def _backup(run, tag, files):
    folder = os.path.join(_project(), "Backups", "PreKlaraHookin-%s-%s" % (tag, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for src in files:
        if not os.path.isfile(src):
            _stop(run, "BACKUP_SOURCE_MISSING|" + src)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _plan_all(args):
    facts, plans, refusals, warnings, handles = {}, {}, [], [], {}
    for key, row in sorted(args["scenes"].items()):
        f, problems, seq = _scene_facts(key, row)
        refusals += ["S%s %s" % (key, p) for p in problems]
        facts[key], handles[key] = f, seq
        if f is None:
            continue
        p = plan_scene(f, row)
        refusals += ["S%s %s" % (key, x) for x in p["refusals"]]
        warnings += ["S%s %s" % (key, x) for x in p["warnings"]]
        plans[key] = p
    return facts, plans, refusals, warnings, handles


def run_dry(args, run, world):
    facts, plans, refusals, warnings, _h = _plan_all(args)
    have = _streaming_levels(world)
    report = {"tool": TOOL, "run": run, "args": args, "api_table": _api_table(), "facts": facts, "plans": plans,
              "streaming_levels_now": have, "levels_missing_from_world": [l for l in args.get("levels") or [] if l not in have],
              "levels_missing_from_content": [l for l in args.get("levels") or []
                                              if not unreal.EditorAssetLibrary.does_asset_exist(l)],
              "refusals": refusals, "warnings": warnings, "seq_apply_ready": not refusals,
              "extend_modes": {k: p.get("extend_mode") for k, p in plans.items()}}
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    for row in report["api_table"]:
        unreal.log("KLARAHOOK_API|run=%s|ok=%d|%s|%s|%s" % (run, int(row["ok"]), row["api"], row["tier"], row["result"]))
    for t in refusals:
        unreal.log_warning("KLARAHOOK_REFUSAL|run=%s|%s" % (run, t))
    for t in warnings:
        unreal.log("KLARAHOOK_WARNING|run=%s|%s" % (run, t))
    for k, p in sorted(plans.items()):
        cb = (facts[k] or {}).get("cut_bindings") or {}
        unreal.log("KLARAHOOK_ROW|run=%s|S%s|section=%s|planned_end_s=%s|narration=%s|cuts_ok=%s|unresolved=%s"
                   % (run, k, p.get("section"), p.get("planned_end_s"), (p.get("narration") or {}).get("action"),
                      cb.get("ok"), cb.get("unresolved")))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("KLARAHOOK_DRY_OK|run=%s|mutated=0|seq_apply_ready=%d|refusals=%d|warnings=%d|report=%s"
               % (run, int(not refusals), len(refusals), len(warnings), out))


def run_apply_stream(args, run, world):
    levels = list(args.get("levels") or [])
    have = _streaming_levels(world)
    missing = [l for l in levels if not unreal.EditorAssetLibrary.does_asset_exist(l)]
    if missing:
        _stop(run, "LEVEL_ASSET_MISSING|%s" % missing)
    already = [l for l in levels if l in have]
    if already:
        _stop(run, "ALREADY_STREAMED|%s" % already)
    rpath = os.path.join(_here(), STREAM_RECORD)
    backup = _backup(run, "Stream", [_file(EXPECTED_WORLD, ".umap")])
    rec = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY_STREAM", "world": EXPECTED_WORLD, "levels": levels,
           "levels_before": have, "backup": backup, "decided_by": args.get("decided_by"), "applied": False,
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    write_record_exclusive(rpath, rec)
    added = []
    for lv in levels:
        ls = unreal.EditorLevelUtils.add_level_to_world(world, lv, unreal.LevelStreamingDynamic)  # decl :243-244
        if ls is None:
            _stop(run, "ADD_LEVEL_NONE|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (lv, backup))
        ls.set_editor_property("initially_loaded", True)                       # [inf] probed in DRY
        ls.set_editor_property("initially_visible", bool(args.get("initially_visible", False)))
        got = [ls.get_editor_property("initially_loaded"), ls.get_editor_property("initially_visible")]
        if got != [True, bool(args.get("initially_visible", False))]:
            _stop(run, "STREAM_FLAGS_READBACK|%s|%s|NOTHING SAVED" % (lv, got))
        added.append({"level": lv, "flags": got})
    now = _streaming_levels(world)
    if sorted(now) != sorted(have + levels):
        _stop(run, "LEVELS_READBACK|%s|NOTHING SAVED; Don't-Save restart" % now)
    gate = census_gate(_census(), [], [EXPECTED_WORLD])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):      # prec extend_scene_playback.py:406
        _stop(run, "SAVE_MAP_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    show = unreal.load_asset(SHOW_PATH)
    verdicts = {}
    for key, row in sorted(args["scenes"].items()):
        cues = [c for c in show.get_editor_property("cues")
                if c.get_editor_property("type") == unreal.InfinityCueType.SCENE
                and _path(c.get_editor_property("scene").get_editor_property("sequence")) == row["scene_sequence"]]
        if len(cues) == 1:
            verdicts[key] = _cut_bindings(show, cues[0].get_editor_property("cue_guid"))
    rec.update(applied=True, added=added, levels_after=now, cut_bindings_after=verdicts)
    update_record(rpath, rec)
    unreal.log("KLARAHOOK_APPLY_STREAM_OK|run=%s|levels=%s|cut_ok=%s|backup=%s|record=%s"
               % (run, ",".join(levels), {k: v.get("ok") for k, v in verdicts.items()}, backup, rpath))


def run_revert_stream(args, run, world):
    rpath = os.path.join(_here(), STREAM_RECORD)
    rec = load_record(rpath)
    targets = []
    for lv in unreal.EditorLevelUtils.get_levels(world):
        if lv.get_outer() is not None and _path(lv.get_outer()) in rec["levels"]:
            targets.append(lv)
    if len(targets) != len(rec["levels"]):
        _stop(run, "REVERT_LEVEL_COUNT|%d of %d" % (len(targets), len(rec["levels"])))
    for lv in targets:
        if not unreal.EditorLevelUtils.remove_level_from_world(lv, True, False):     # decl :260-261; keep undo
            _stop(run, "REMOVE_LEVEL_FAILED|NOTHING SAVED; Don't-Save restart")
    now = _streaming_levels(world)
    if sorted(now) != sorted(rec["levels_before"]):
        _stop(run, "REVERT_READBACK|%s|NOTHING SAVED" % now)
    gate = census_gate(_census(), [], [EXPECTED_WORLD])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        _stop(run, "SAVE_MAP_FAILED")
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAHOOK_REVERT_STREAM_OK|run=%s|levels_now=%s" % (run, now))


def _live_seq_state(seq, row):
    sec = _find_target_section(seq, row)
    p = sec.get_editor_property("parameters")
    narr = [s for t in seq.get_tracks() if str(t.get_display_name()) == row.get("narration_track")
            and isinstance(t, unreal.MovieSceneAudioTrack) for s in t.get_sections()]
    vis = [t for t in seq.get_tracks() if str(t.get_display_name()) == VIS_TRACK_NAME]
    return {"target": {"sequence": _path(sec.get_sequence()), "start": int(sec.get_start_frame()),
                       "end": int(sec.get_end_frame()),
                       "start_offset_tick": int(p.get_editor_property("start_frame_offset").value)},
            "narration": [int(narr[0].get_start_frame()), int(narr[0].get_end_frame())] if len(narr) == 1 else None,
            "vis_track": [{"levels": [str(n) for n in s.get_level_names()], "range": [int(s.get_start_frame()),
                                                                                   int(s.get_end_frame())]}
                          for t in vis for s in t.get_sections()] or None}


def _set_target(seq, row, sequence_path, start, end, offset_tick):
    sec = _find_target_section(seq, row)
    child = unreal.load_asset(sequence_path)
    if child is None:
        raise PlanError("SEQUENCE_NOT_LOADED: %s" % sequence_path)
    sec.set_sequence(child)                                   # decl MovieSceneSubSection.h:161-162
    sec.set_range(int(start), int(end))                       # decl MovieSceneSectionExtensions.h:145
    p = sec.get_editor_property("parameters")                 # struct copy: set back [inf]
    p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(offset_tick)))
    sec.set_editor_property("parameters", p)
    return sec


def run_apply_seq(args, run, world):
    facts, plans, refusals, warnings, handles = _plan_all(args)
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    rpath = os.path.join(_here(), SEQ_RECORD)
    if os.path.exists(rpath):
        _stop(run, "RECORD_EXISTS|%s" % rpath)
    keys = sorted(plans)
    paths = {k: args["scenes"][k]["scene_sequence"] for k in keys}
    backup = _backup(run, "Seq", [_file(p, ".uasset") for p in paths.values()])
    rec = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY_SEQ", "backup": backup, "applied": False,
           "decided_by": args.get("decided_by"), "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "scenes": {k: {"row": args["scenes"][k], "scene_sequence": paths[k], "playback_before": facts[k]["playback"],
                          "label": facts[k]["label"], "plan": plans[k],
                          "before": _live_seq_state(handles[k], args["scenes"][k])} for k in keys}}
    write_record_exclusive(rpath, rec)
    unreal.log("KLARAHOOK_BACKUP_OK|run=%s|backup=%s|record=%s" % (run, backup, rpath))
    for k in keys:
        row, plan, seq = args["scenes"][k], plans[k], handles[k]
        sec = _set_target(seq, row, row["her_sequence"], plan["section"][0], plan["section"][1], 0)
        her = sec.get_sequence()
        mapped = [int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(sec, int(her.get_playback_start()), seq)),
                  int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(sec, int(her.get_playback_end()), seq))]
        if mapped != plan["section"]:
            _stop(run, "S%s MAPPING_READBACK|inner [start,end] -> %s, plan %s (time scale or offset not 1/0?)|NOTHING SAVED;"
                  " Don't-Save restart (backup %s)" % (k, mapped, plan["section"], backup))
        narr = plan["narration"]
        if narr.get("action") == "move":
            ns = [s for t in seq.get_tracks() if str(t.get_display_name()) == row["narration_track"]
                  and isinstance(t, unreal.MovieSceneAudioTrack) for s in t.get_sections()]
            if len(ns) != 1:
                _stop(run, "S%s NARRATION_SHAPE|NOTHING SAVED" % k)
            ns[0].set_range(int(narr["frames"][0]), int(narr["frames"][1]))
        vis_levels = row.get("visible_levels") or []
        if vis_levels:
            track = seq.add_track(unreal.MovieSceneLevelVisibilityTrack)              # [inf] probed in DRY
            if track is None:
                _stop(run, "S%s VIS_TRACK_NONE|NOTHING SAVED" % k)
            track.set_display_name(VIS_TRACK_NAME)
            vs = track.add_section()
            vs.set_range(int(plan["section"][0]), int(plan["section"][1]))
            vs.set_visibility(unreal.ELevelVisibility.VISIBLE)                         # decl :43
            vs.set_level_names([unreal.Name(n) for n in vis_levels])                   # decl :49
        after = _live_seq_state(seq, row)
        want = {"sequence": row["her_sequence"], "start": plan["section"][0], "end": plan["section"][1],
                "start_offset_tick": 0}
        bad = [x for x in want if after["target"][x] != want[x]]
        if narr.get("action") == "move" and after["narration"] != list(narr["frames"]):
            bad.append("narration %s" % after["narration"])
        if vis_levels and not (after["vis_track"] and after["vis_track"][0]["levels"] == vis_levels):
            bad.append("vis %s" % after["vis_track"])
        if bad:
            _stop(run, "S%s APPLY_READBACK|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (k, bad, backup))
        rec["scenes"][k]["after"] = after
        rec["scenes"][k]["mapped_inner_range"] = mapped
    gate = census_gate(_census(), list(paths.values()), [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    for k in keys:
        if not unreal.EditorAssetLibrary.save_asset(paths[k], only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % paths[k])
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    for k in keys:
        if _live_seq_state(unreal.load_asset(paths[k]), args["scenes"][k]) != rec["scenes"][k]["after"]:
            _stop(run, "S%s POST_SAVE_READBACK" % k)
    rec["applied"] = True
    update_record(rpath, rec)
    for k in keys:
        unreal.log("KLARAHOOK_EXTEND_NEXT|run=%s|S%s|extend_scene_playback_mode=%s"
                   % (run, k, json.dumps(plans[k]["extend_mode"], ensure_ascii=False)))
    unreal.log("KLARAHOOK_APPLY_SEQ_OK|run=%s|scenes=%s|backup=%s|record=%s|NEXT=extend_scene_playback per Scene"
               % (run, ",".join("S" + k for k in keys), backup, rpath))


def run_revert_seq(args, run, world):
    rpath = os.path.join(_here(), SEQ_RECORD)
    rec = load_record(rpath)
    keys = sorted(rec["scenes"])
    for k in keys:
        r = rec["scenes"][k]
        seq = unreal.load_asset(r["scene_sequence"])
        live = _live_seq_state(seq, r["row"])
        drift = seq_drift(live, r)
        if drift:
            _stop(run, "S%s STATE_DRIFTED|%s|nothing changed in this Scene" % (k, drift))
        b = r["before"]["target"]
        _set_target(seq, r["row"], b["sequence"], b["start"], b["end"], b["start_offset_tick"])
        if r["before"]["narration"] and live["narration"] != r["before"]["narration"]:
            ns = [s for t in seq.get_tracks() if str(t.get_display_name()) == r["row"]["narration_track"]
                  and isinstance(t, unreal.MovieSceneAudioTrack) for s in t.get_sections()]
            ns[0].set_range(*r["before"]["narration"])
        if not r["before"]["vis_track"]:
            for t in [t for t in seq.get_tracks() if str(t.get_display_name()) == VIS_TRACK_NAME]:
                seq.remove_track(t)        # return value ignored (memory: return values lie); re-listed below
        if _live_seq_state(seq, r["row"]) != r["before"]:
            _stop(run, "S%s REVERT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % (k, _live_seq_state(seq, r["row"])))
    gate = census_gate(_census(), [rec["scenes"][k]["scene_sequence"] for k in keys], [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    for k in keys:
        if not unreal.EditorAssetLibrary.save_asset(rec["scenes"][k]["scene_sequence"], only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % rec["scenes"][k]["scene_sequence"])
    os.rename(rpath, rpath + ".reverted-" + run)
    for k in keys:
        pb = rec["scenes"][k]["playback_before"]
        unreal.log("KLARAHOOK_EXTEND_NEXT|run=%s|S%s|restore with extend_scene_playback new_end_frame=%d (was before APPLY)"
                   % (run, k, pb[1]))
    unreal.log("KLARAHOOK_REVERT_SEQ_OK|run=%s|scenes=%s" % (run, ",".join("S" + k for k in keys)))


def main():
    g = globals()
    args = g.get("KLARAHOOK_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAHOOK-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = editor.get_game_world() is not None
    world = None if pie else editor.get_editor_world()
    wname = str(world.get_outermost().get_name()) if world is not None else None
    rpath = os.path.join(_here(), STREAM_RECORD if "STREAM" in mode else SEQ_RECORD)
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie,
             "wrong_world": None if wname == EXPECTED_WORLD else str(wname),
             "sequencer_open": None if pie else _sequencer_open(), "census": _census(),
             "decided_by": args.get("decided_by"),
             "record_exists": rpath if os.path.exists(rpath) else None,
             "record_applied": os.path.exists(rpath) and bool(load_record(rpath).get("applied"))}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        {"DRY": run_dry, "APPLY_STREAM": run_apply_stream, "REVERT_STREAM": run_revert_stream,
         "APPLY_SEQ": run_apply_seq, "REVERT_SEQ": run_revert_seq}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None:
    main()
