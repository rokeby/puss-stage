"""PASSAGE RETIME TO MUSIC: retime whole Passages (default P02-P05) so each walk lasts its walking song + a short tail
(Gary 5 Oct: "P02 walk speed can also now be corrected after straightening to time of music, the prev placeholder length
made it very slow"; decided 5 Oct: retime P02-P05, target "song + short tail for the crossing", P04 keeps its padded
48.4 s song). Offline-written 5 Oct, NEVER RUN IN UNREAL. Harness: test_passage_retime_to_music.py (system Python).

Tiers per claim: [decl] declaration-proven (source/header we can read, file:line), [prec] in-repo precedent call
(cited), [meas] an earlier run's read-back record (cited), [inf] inferred (why stated).

WHAT A PASSAGE'S TIME IS
  * Length = LeadInFrames + sum(IntervalToNext of every wing pair but the last) + TailFrames; the next segment starts
    at this Passage's end [decl InfinityStageCompiler.cpp:254-288, 312]. IntervalToNext is a per-wing-pair FRAME count
    (tick time to the next pair's pass) and GapToNextCm its per-pair DISTANCE [decl InfinityStageTypes.h:709-713];
    LeadIn/Tail have the same frames + cm pair [decl :957-967]. So "intervals" are per-bay TIMES, and each bay's
    walk speed is GapToNextCm / IntervalToNext: distance(time) is piecewise linear through (start, 0), (first pass,
    LeadInDistanceCm), (each pass, cumulative gap), (end, TotalDistanceCm) [decl InfinityStageCompiler.cpp:380-411].
  * Distance never depends on time: wing layout uses distances only [inf from PassageActor.cpp:720-830, MaterializePassage
    reads TotalDistanceCm/route, no frame field] and cue attachments trigger by distance ("Distance rather than time, so
    retiming cannot desynchronise it") [decl InfinityStageTypes.h:471-476].

WHAT THIS TOOL WRITES (the passage_slow_walk.py model run in reverse; that tool slowed P02-P04 to 180 s on 2 Oct
  [meas passage_slow_walk_P0{2,3,4}_latest.json, APPLY ok])
  * Per retimed Passage: LeadInFrames, every wing pair's IntervalToNext and TailFrames, all scaled by k = target / old,
    rounded to the nearest tick, the aggregate residual absorbed in TailFrames, so the new length is EXACTLY the target
    [prec passage_slow_walk.py:35-69]. Distances, wings, GUIDs, override masks, music, Choreo: unchanged (asserted).
    Every bay keeps its share of the walk: all speeds scale by 1/k (the walk's shape is kept).
  * Target = song + tail_s, rounded UP to a whole display frame. song = the live rail's SourceOut - SourceIn (what the
    walking swap set: source_out_policy "new_duration" [meas walking_music_swap_record_P02-P03-P04-P05.json]),
    cross-checked against args song_s.
  * Then RebuildManagedMaster (unwrapped as p06_tail_extend.py:830-832) moves every later managed section; Passage
    sections are MoveSection'd when their start moves, so later Passages' absolute keys travel [decl
    InfinityStageSequenceBuilderLibrary.cpp:300-309]; Choreo sections move then SetRange [decl :418-445].

WHAT IS ABSOLUTE IN TIME INSIDE A RETIMED PASSAGE (and what this tool does about it: REFUSE, never scale)
  * Master Passage-section channel keys (Camera.* and Wing.* channels) sit at ABSOLUTE Master ticks; the rebuild only
    moves them when the section START moves [decl SequenceBuilderLibrary.cpp:300-309]. A retimed Passage's start does not
    move (or moves by the shift of earlier retimes), so its keys keep their seconds-from-start while the wings come
    earlier. A channel whose keys all carry ONE value is the same curve wherever the keys sit [inf: constant value
    everywhere; user tangents could in principle overshoot - DRY lists the key times]. Any channel with differing key
    values inside a retimed Passage -> REFUSED (TIME_KEYED_CHANNEL). SpeedMultiplier is renormalised per span [decl
    MovieSceneInfinityPassageTrack.cpp:408-441], so differing SpeedMultiplier keys re-shape the walk -> same refusal.
    Scaling keys was NOT chosen: no tested API path in this repo moves individual keys of a Passage section, and the
    rule is "scale only if a proven-safe path exists and is tested".
  * PinnedPassageFrames are RELATIVE ticks and are not scaled; the rebuild silently DELETES pins >= the new duration
    [decl SequenceBuilderLibrary.cpp:286-291]. Any relative pin in a retimed Passage -> REFUSED (RELATIVE_PIN). Wing pins
    (PinnedWingCueGuids) follow their wing's pass frame [decl MovieSceneInfinityPassageTrack.cpp:383-389]: allowed.
  * Mechanism PhaseOrigin ExplicitFrame is an ABSOLUTE Master frame [decl InfinityStagePassageActor.cpp:1381-1389]: any
    wing with it in a retimed OR later Passage -> REFUSED. PassageStart/PassFrame origins follow [decl same lines].
    CycleRateHz is per second: wings cycle at the same rate, fewer cycles per (shorter) Passage [inf] - reported.
  * Celestial temporality is in seconds [decl InfinityStageTypes.h:877-903, Compiler.cpp:446-447]: fewer days pass in a
    shorter Passage - reported per Passage, not refused.
  * Choreo (0:00 at the Passage start, keys relative [decl SequenceBuilderLibrary.cpp:366-369]): its content stays at the
    same seconds from the Passage start, i.e. WITH THE SONG (which also starts at the Passage start). Content past the
    NEW end is not played and GO markers past it are dropped (collected over [start, end) [decl
    InfinityStageTransportController.cpp:237-267, 931-940]): keys / sections starting / GO markers past the new end ->
    REFUSED; song markers ("bar ", "§ ") past the new end -> REFUSED unless allow_stale_song_markers (run
    choreo_song_markers_refresh FIRST: its old-marker identity check recomputes from the LIVE Master length + 30 s
    [decl Saved/CodexCueing/choreo_tool.py:145-148; choreo_song_markers_refresh.py:617-621], so after a retime the old
    markers stop matching -> OLD_SONG_MARKERS_UNEXPLAINED [inf]).
  * Unmanaged ("artist") Master content and Master marked frames are absolute and NOT rippled [decl
    PassageResizeLibrary.cpp:138-201; p06_tail_extend.py:34-36]: keys / sections starting / markers at or after the
    earliest retimed Passage START -> REFUSED; a section straddling that start must reach the old Show end (a whole-show
    span such as a camera-cut track) and the net change must be a shrink, else REFUSED.

THE END OF A PASSAGE (why the default tail is 2.0 s)
  * The last span is [last wing pass (or last pin), Passage end]. With CrossingSettleSeconds > 0 (rig default 1.0 s
    [decl InfinityStageCameraRig.h:195-209]) the last min(settle, span) of that span eases to a stop at the route-end
    pose the next Scene's Entry handoff is matched to; the span is renormalised so it is a little faster before the
    window [decl MovieSceneInfinityPassageTrack.cpp:420-469; smoothstep :350-364 integrates to half the window].
  * The music fade-out ENDS at the Passage end [prec walking_music_swap.py:222-247 fit(); decl
    SequenceBuilderLibrary.cpp:78-96 cited there]: with fade_out 1.0 s [meas rail_after.fade_out 24000] the song only
    "ends naturally" when the tail after it is >= 1.0 s. tail_s < fade_out_s -> REFUSED (SONG_INSIDE_FADE_OUT).
  * Recommended tail_s = 2.0 s = 1 s of walking on after the last note + the 1 s settle into the Scene docking (the
    inaudible fade-out ramps under the settle). The end pose does not move (distance unchanged) - the 2 Oct slow-walk
    rematches moved the Scene cameras 0.0 cm [meas passage_slow_walk_P0{2,3,4}_latest.json rematch.camera_deltas] -
    so no rematch is run; CheckSceneHandoffs (read-only) gates instead [prec p06_tail_extend.py:731-736].
  * tail_s is a target; the new TailFrames is whatever closes the scaled sum, and must be >= the settle frames
    (TAIL_SHORTER_THAN_SETTLE refusal) so the settle stays inside the tail.
  * settle_compensation (default true): a tail scaled with the bays is ~2.4 s long, and renormalising it around a 1 s
    settle makes the camera SURGE ~25% before easing (P02 offline: 249.5 -> 314 cm/s). With compensation the walk is
    scaled to (target - settle/2) and settle/2 is added to the tail: one speed from the first bay to the settle window
    (P02 offline ~252 cm/s, P01 v_end 251.3). Same total length either way.

MULTI-PASSAGE AND SPLIT RUNS
  * One run may retime any subset of P02-P05 (default all four). Every value is read live, so P03-P05 first and P02
    later (after p02_straighten) is equally exact: segment j moves its start by the sum of the deltas of retimed
    Passages ending at or before its start, and its end by the sum ending at or before its end (shift_at()).
  * Each APPLY writes its own record passage_retime_to_music_record_<P..>.json; APPLY refuses a passage covered by an
    applied record; REVERT is strict (state == what that APPLY left), so split runs revert LIFO.

Modes (passage_retime_to_music_run.py <- passage_retime_to_music_args.json, confirm "<MODE> RETIME"):
  DRY    read-only; passage_retime_to_music_dry.json; PASSAGE_RETIME_DRY_OK|run=..|per=..
  APPLY  guards (world, no PIE, Sequencer closed, clean census, Master in sync, decided_by, expected numbers from the
         DRY) -> refusals -> backup Show + Master to Backups/PrePassageRetime-<run> -> exclusive fsynced record ->
         write timing (read back; everything else asserted unchanged) -> RebuildManagedMaster -> gates (segments,
         managed sections, Passage keys, artist content, music fit, handoffs) -> census subset {Show, Master} -> save
         those two only -> reload read-back -> census clean -> PASSAGE_RETIME_APPLY_OK|run=..|per=..
  REVERT drift check -> backup -> recorded timing -> rebuild -> == the record's BEFORE tick-exact -> save Show + Master
         -> PASSAGE_RETIME_REVERT_OK|run=..|per=..
  Failure: PASSAGE_RETIME_STOPPED|run=..|reason=..
Never: Save All, level save, reload, open/scrub Sequencer, materialise, rematch, end PIE; no unreal objects in module
globals. Importing without `unreal` runs nothing.
"""
import datetime
import fractions
import hashlib
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "passage_retime_to_music"
MARK = "PASSAGE_RETIME"
CONFIRM_SUFFIX = "RETIME"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                 # p06_tail_extend.py:85
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"   # p06_tail_extend.py:86
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ARGS_NAME = "passage_retime_to_music_args.json"
DRY_NAME = "passage_retime_to_music_dry.json"
RECORD_PREFIX = "passage_retime_to_music_record_"
VALID_KEYS = ("2", "3", "4", "5")
SONG_MARKER_PREFIXES = ("bar ", "§ ")     # choreo_tool.py:110,117 (p06_tail_extend.py:91)
MANAGED_CLASSES = {"MovieSceneInfinityPassageTrack": "Passage", "MovieSceneInfinitySceneTrack": "Scene",
                   "MovieSceneInfinityChoreoTrack": "Choreo", "MovieSceneInfinityAudioTrack": "Music"}
INT32_MAX = 2 ** 31 - 1
SYNC_TOL_S = 0.05                              # p06_tail_extend.py:95
SONG_TOL_S = 0.002                             # args song_s vs live rail length (walking_music_swap.py:115 HEADER_TOL_S)
PLAYING_MODES = ("START", "EXPLICITCROSSFADE", "EXPLICIT_CROSSFADE")   # walking_music_swap.py:113


class PlanError(Exception):
    pass


def label_of(key):
    return "Passage %s" % key


# =====================================================================================================================
# Pure: args, maths, gates (exercised by test_passage_retime_to_music.py)
# =====================================================================================================================

def _num_ok(v, minimum=0.0):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= minimum


def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    keys = args.get("passages")
    if not isinstance(keys, list) or not keys or len(set(keys)) != len(keys) or any(k not in VALID_KEYS for k in keys):
        r.append("PASSAGES_INVALID: %r (subset of %r, no repeats)" % (keys, list(VALID_KEYS)))
        keys = []
    if not _num_ok(args.get("tail_s")):
        r.append("ARG_TAIL_S_INVALID: %r" % args.get("tail_s"))
    if not _num_ok(args.get("max_speed_cm_s"), 1.0):
        r.append("ARG_MAX_SPEED_INVALID: %r" % args.get("max_speed_cm_s"))
    per = args.get("per_passage") or {}
    for k in keys:
        row = per.get(k)
        if not isinstance(row, dict):
            r.append("PER_PASSAGE_MISSING: %s" % k)
            continue
        if not str(row.get("guid") or "").strip():
            r.append("GUID_MISSING: P%s" % k)
        if not _num_ok(row.get("song_s"), 0.001):
            r.append("SONG_S_INVALID: P%s %r" % (k, row.get("song_s")))
        if not str(row.get("sound") or "").startswith("/Game/"):
            r.append("SOUND_MISSING: P%s" % k)
        if mode == "APPLY":
            exp = row.get("expected") or {}
            for f in ("old_len_ticks", "new_len_ticks"):
                if not isinstance(exp.get(f), int) or isinstance(exp.get(f), bool) or exp.get(f) <= 0:
                    r.append("EXPECTED_%s_MISSING: P%s (copy it from the DRY)" % (f.upper(), k))
    return r


def ticks_per_display_frame(tick_rate, fps_num, fps_den):
    tick = fractions.Fraction(tick_rate)
    if tick <= 0 or tick.denominator != 1:
        raise PlanError("TICK_RATE_NOT_INTEGER: %r" % tick_rate)
    tpf = tick * int(fps_den) / int(fps_num)
    if tpf.denominator != 1 or tpf <= 0:
        raise PlanError("TICKS_PER_DISPLAY_FRAME_NOT_INTEGER: %s/%s at %s" % (fps_num, fps_den, tick_rate))
    return int(tpf)


def target_ticks(song_s, tail_s, tick_rate, fps_num, fps_den):
    """ceil((song + tail) * tick) rounded UP to a whole display frame."""
    tpf = ticks_per_display_frame(tick_rate, fps_num, fps_den)
    raw = int(math.ceil((fractions.Fraction(str(song_s)) + fractions.Fraction(str(tail_s))) * int(tick_rate)))
    return -((-raw) // tpf) * tpf


def _round_positive(value):
    """passage_slow_walk.py:27-32 verbatim: UE-style nearest-integer rounding, non-negative domain."""
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError("timing value must be finite and non-negative: %r" % value)
    return int(math.floor(number + 0.5))


def plan_scaled_timing(lead_frames, intervals, tail_frames, target):
    """passage_slow_walk.py:35-69 logic: scale every timing field, absorb the rounding residual in Tail."""
    lead, rows, tail, target = int(lead_frames), [int(v) for v in intervals], int(tail_frames), int(target)
    if not rows:
        raise PlanError("NO_WING_PAIRS")
    if lead < 0 or tail < 0 or target <= 0 or any(v <= 0 for v in rows):
        raise PlanError("INVALID_TIMING_INPUTS: lead %d tail %d target %d intervals %r" % (lead, tail, target, rows[:4]))
    old = lead + sum(rows[:-1]) + tail
    if old <= 0:
        raise PlanError("OLD_LENGTH_NONPOSITIVE")
    k = target / float(old)
    new_lead = _round_positive(lead * k)
    new_rows = [max(1, _round_positive(v * k)) for v in rows]       # IntervalToNext ClampMin 1 [decl Types.h:709]
    rounded_tail = _round_positive(tail * k)
    residual = target - (new_lead + sum(new_rows[:-1]) + rounded_tail)
    new_tail = rounded_tail + residual
    if new_tail < 0:
        raise PlanError("RESIDUAL_MAKES_TAIL_NEGATIVE")
    total = new_lead + sum(new_rows[:-1]) + new_tail
    if total != target:
        raise PlanError("PLAN_NOT_EXACT: %d != %d" % (total, target))
    if max([new_lead, new_tail, total] + new_rows) > INT32_MAX:
        raise PlanError("FRAME_NUMBER_OVERFLOW")
    return {"old_ticks": old, "target_ticks": target, "k": k, "lead_frames": new_lead, "intervals": new_rows,
            "rounded_tail_frames": rounded_tail, "rounding_residual_ticks": residual, "tail_frames": new_tail,
            "new_ticks": total, "delta_ticks": total - old}


def settle_compensation_ticks(settle_s, tick_rate):
    """Half the settle window: the smoothstep window covers only half its length's worth of distance [inf from
    PassageTrack.cpp:444-458 + envelope :350-364 integrating to 1/2], so a tail scaled like the bays must SURGE before
    the window to arrive on time. Scaling the walk to (target - settle/2) and adding settle/2 to the tail keeps the
    tail's pre-settle speed equal to the bay speed for a uniform walk."""
    return int(round(float(settle_s) * float(tick_rate) / 2.0))


def add_settle_compensation(plan, comp):
    out = dict(plan, settle_compensation_ticks=int(comp))
    out["tail_frames"] = plan["tail_frames"] + int(comp)
    out["target_ticks"] = plan["target_ticks"] + int(comp)
    out["new_ticks"] = plan["new_ticks"] + int(comp)
    out["delta_ticks"] = plan["delta_ticks"] + int(comp)
    if compiled_length(out["lead_frames"], out["intervals"], out["tail_frames"]) != out["new_ticks"]:
        raise PlanError("COMPENSATED_PLAN_NOT_EXACT")
    return out


def compiled_length(lead, intervals, tail):
    """Compiler.cpp:254-288: lead + every interval but the last wing's + tail."""
    return int(lead) + sum(int(x) for x in list(intervals)[:-1]) + int(tail)


def speeds(lead, intervals, tail, lead_cm, gaps, tail_cm, tick_rate, settle_s=0.0):
    """cm/s of each piece of the distance(time) polyline [decl Compiler.cpp:380-411] with a constant SpeedMultiplier.
    tail_pre_settle: the tail span renormalised over (span - settle/2) [inf from PassageTrack.cpp:444-458 + smoothstep
    integral 1/2]; it is the speed the camera reaches before easing into the Scene (comparable to P01 v_end)."""
    t = float(tick_rate)
    pieces = []
    if int(lead) > 0:
        pieces.append(float(lead_cm) / (int(lead) / t))
    pieces += [float(g) / (int(i) / t) for i, g in zip(list(intervals)[:-1], list(gaps)[:-1])]
    tail_v = float(tail_cm) / (int(tail) / t) if int(tail) > 0 else None
    length_s = compiled_length(lead, intervals, tail) / t
    route = float(lead_cm) + sum(float(g) for g in list(gaps)[:-1]) + float(tail_cm)
    pre = None
    if int(tail) > 0:
        span_s = int(tail) / t
        s = min(float(settle_s), span_s)
        pre = float(tail_cm) / (span_s - s / 2.0) if span_s - s / 2.0 > 0 else None
    return {"length_s": round(length_s, 6), "route_cm": round(route, 4), "mean": round(route / length_s, 4),
            "bay_min": round(min(pieces), 4) if pieces else None, "bay_max": round(max(pieces), 4) if pieces else None,
            "tail": round(tail_v, 4) if tail_v is not None else None,
            "tail_pre_settle": round(pre, 4) if pre is not None else None}


def fit(passage_s, song_s, source_in_s=0.0, offset_s=0.0, fade_in_s=0.0, fade_out_s=0.0):
    """VERBATIM copy of walking_music_swap.py:222-247 fit() (that module runs main() when imported inside Unreal, so it
    cannot be imported here). The harness asserts this copy == the original on a grid."""
    if passage_s <= 0:
        raise PlanError("PASSAGE_LENGTH_NONPOSITIVE: %r" % passage_s)
    remaining = float(song_s) - float(source_in_s) - float(offset_s)
    if remaining <= 0:
        raise PlanError("SONG_STARTS_PAST_ITS_END: song %.3f s, start %.3f s" % (song_s, source_in_s + offset_s))
    overrun = remaining - passage_s
    audible = min(remaining, passage_s)
    fade_out_from = max(0.0, passage_s - float(fade_out_s))
    if float(fade_out_s) <= 0:
        fade = "no fade-out: " + ("hard cut at the Passage end" if overrun > 0 else "song ends naturally")
    elif overrun > 0:
        fade = "song CUT at the Passage end, faded %.3f-%.3f s (Passage time)" % (fade_out_from, passage_s)
    elif remaining <= fade_out_from:
        fade = ("song ends naturally at %.3f s; fade-out %.3f-%.3f s ramps over silence (inaudible)"
                % (remaining, fade_out_from, passage_s))
    else:
        fade = "song ends at %.3f s INSIDE the fade-out window %.3f-%.3f s (partly faded)" % (
            remaining, fade_out_from, passage_s)
    return {"passage_s": round(passage_s, 6), "song_s": round(float(song_s), 6), "start_in_song_s": round(
        float(source_in_s) + float(offset_s), 6), "audible_s": round(audible, 6), "fits": overrun <= 1e-6,
        "overrun_s": round(max(0.0, overrun), 6), "silence_tail_s": round(max(0.0, -overrun), 6),
        "fade_in": ("%.3f s from the Passage start" % min(float(fade_in_s), passage_s)) if fade_in_s > 0 else "none",
        "fade_out": fade}


def music_refusals(key, music, new_len_ticks, tick_rate, args_song_s):
    """music: {"mode", "offset", "source_in", "source_out", "fade_in", "fade_out", "sound"} (ticks) + "args_sound".
    The song must still fit and end before the fade-out window starts."""
    r = []
    t = float(tick_rate)
    if music is None:
        return ["P%s MUSIC_UNREADABLE" % key], None
    if not any(m in str(music.get("mode") or "").upper() for m in PLAYING_MODES):
        r.append("P%s MUSIC_NOT_PLAYING: mode %s" % (key, music.get("mode")))
    if music.get("sound") != music.get("args_sound"):
        r.append("P%s SOUND_CHANGED: live %s, args %s (walking swap record)" % (key, music.get("sound"),
                                                                              music.get("args_sound")))
    if int(music.get("source_out") or 0) <= int(music.get("source_in") or 0):
        r.append("P%s SOURCE_OUT_UNSET: the song length is not on the rail" % key)
        return r, None
    song_s = (int(music["source_out"]) - int(music["source_in"])) / t
    if abs(song_s - float(args_song_s)) > SONG_TOL_S:
        r.append("P%s SONG_LENGTH_MISMATCH: rail %.6f s, args %.6f s" % (key, song_s, args_song_s))
    row = fit(new_len_ticks / t, song_s + int(music["source_in"]) / t, int(music["source_in"]) / t,
              int(music.get("offset") or 0) / t, int(music.get("fade_in") or 0) / t, int(music.get("fade_out") or 0) / t)
    if not row["fits"]:
        r.append("P%s SONG_OVERRUNS_NEW_PASSAGE: %.3f s" % (key, row["overrun_s"]))
    elif "ends naturally" not in row["fade_out"]:
        r.append("P%s SONG_INSIDE_FADE_OUT: %s (raise tail_s to >= the fade-out)" % (key, row["fade_out"]))
    return r, row


def channel_refusals(key, channels, start, end):
    """channels {name: [[tick_abs, value]]}. Differing values = a time-keyed curve -> refuse; one value = constant."""
    r, notes = [], []
    for name, keys in sorted((channels or {}).items()):
        values = set(v for _t, v in keys)
        if len(values) > 1:
            inside = [t for t, _v in keys if int(start) <= int(t) <= int(end)]
            r.append("P%s TIME_KEYED_CHANNEL: %s %d keys (%d inside [%d, %d]) with %d distinct values; their absolute "
                     "times would no longer match the wings (refused, not scaled)" % (
                         key, name, len(keys), len(inside), start, end, len(values)))
        elif keys:
            notes.append("P%s CONSTANT_CHANNEL: %s %d key(s) all %r (position-free)" % (key, name, len(keys),
                                                                                        keys[0][1]))
    return r, notes


def pin_refusals(key, pins_rel):
    return ["P%s RELATIVE_PIN: PinnedPassageFrames %r are not scaled (and pins >= the new length are deleted by the "
            "rebuild, SequenceBuilderLibrary.cpp:286-291)" % (key, list(pins_rel))] if pins_rel else []


def mechanism_refusals(key, origins, later=False):
    """origins: [[cue_guid, origin_text]]; ExplicitFrame is absolute (PassageActor.cpp:1386-1388)."""
    bad = [g for g, o in origins if "EXPLICIT" in str(o).upper()]
    if not bad:
        return []
    return ["P%s MECHANISM_EXPLICIT_ORIGIN%s: %d wing(s) %s use an absolute ExplicitOriginFrame" % (
        key, "_IN_LATER_PASSAGE" if later else "", len(bad), bad[:4])]


def choreo_refusals(key, choreo, new_len, allow_stale_song_markers=False):
    """choreo: None or {"path","start_offset","keys":[[where,tick_local]],"sections":[{where,start,end,keyed}],
    "markers":[[label,tick_local]],"camera_cut":bool} (local ticks, 0 = Passage start). Returns (refusals, warnings)."""
    r, w = [], []
    if not choreo:
        return r, w
    end = int(choreo.get("start_offset", 0)) + int(new_len)
    if choreo.get("camera_cut"):
        w.append("P%s CHOREO_HAS_CAMERA_CUT (not nested at all, SequenceBuilderLibrary.cpp:386-395)" % key)
    late = [k for k in choreo.get("keys") or [] if int(k[1]) >= end]
    if late:
        r.append("P%s CHOREO_KEY_PAST_NEW_END: %d key(s) at/after local %d: %s" % (key, len(late), end, late[:4]))
    inside = [k for k in choreo.get("keys") or [] if int(k[1]) < end]
    if inside:
        w.append("P%s CHOREO_KEYS_STAY_WITH_THE_SONG: %d key(s) keep their seconds from the Passage start (the song "
                 "starts there too); their relation to the wings changes" % (key, len(inside)))
    for s in choreo.get("sections") or []:
        st, en = s.get("start"), s.get("end")
        if st is not None and int(st) >= end:
            r.append("P%s CHOREO_SECTION_STARTS_PAST_NEW_END: %s [%s, %s)" % (key, s.get("where"), st, en))
        elif en is not None and int(en) > end:
            w.append("P%s CHOREO_SECTION_TRUNCATED: %s [%s, %s) by the new end %d" % (key, s.get("where"), st, en, end))
    for label, tick in choreo.get("markers") or []:
        if int(tick) < end:
            continue
        if str(label).startswith(SONG_MARKER_PREFIXES):
            msg = "P%s SONG_MARKER_PAST_NEW_END: %r at local %d" % (key, label, tick)
            (w if allow_stale_song_markers else r).append(
                msg + ("" if allow_stale_song_markers else " (run choreo_song_markers_refresh BEFORE the retime)"))
        else:
            r.append("P%s CHOREO_MARKER_PAST_NEW_END: %r at local %d (a GO marker would be dropped, "
                     "TransportController.cpp:931-940)" % (key, label, tick))
    return r, w


def shift_at(t, retimed):
    """retimed: [(old_start, old_end, delta)]. Shift of an ABSOLUTE boundary t that is not strictly inside a retimed
    Passage: the sum of the deltas of retimed Passages ending at or before t. None when t is strictly inside one."""
    total = 0
    for s, e, d in retimed:
        if int(s) < int(t) < int(e):
            return None
        if int(e) <= int(t):
            total += int(d)
    return total


def predict_segments(segments, deltas):
    """segments [{label,start,end}] in Show order; deltas {label: delta_ticks}. Returns rows with new_start/new_end."""
    labels = [s["label"] for s in segments]
    for lab in deltas:
        if labels.count(lab) != 1:
            raise PlanError("SEGMENT_LABEL_COUNT: %s %d" % (lab, labels.count(lab)))
    out, cursor = [], 0
    for s in segments:
        shift = cursor
        cursor += int(deltas.get(s["label"], 0))
        out.append({"label": s["label"], "start": int(s["start"]), "end": int(s["end"]),
                    "new_start": int(s["start"]) + shift, "new_end": int(s["end"]) + cursor, "shift": shift,
                    "old_len": int(s["end"]) - int(s["start"]),
                    "new_len": int(s["end"]) + cursor - int(s["start"]) - shift})
    return out


def retimed_spans(segments, deltas):
    return [(int(s["start"]), int(s["end"]), int(deltas[s["label"]])) for s in segments if s["label"] in deltas]


def segment_shift_gate(before, after, deltas):
    if [s["label"] for s in before] != [s["label"] for s in after]:
        return ["SEGMENT_ORDER_CHANGED"]
    out = []
    for want, got in zip(predict_segments(before, deltas), after):
        if (want["new_start"], want["new_end"]) != (int(got["start"]), int(got["end"])):
            out.append("SEGMENT_MOVED_WRONG: %s want [%d, %d) got [%d, %d)" % (
                got["label"], want["new_start"], want["new_end"], got["start"], got["end"]))
    return out


SECTION_READ_TOL_TICKS = 8


def managed_shift_gate(before, after, spans):
    """Managed sections {"Kind:GUID": [s, e]} (+ "Playback:master"): each boundary moves by shift_at(boundary)."""
    out = []
    if sorted(before) != sorted(after):
        out.append("MANAGED_SET_CHANGED: gone %r new %r" % (sorted(set(before) - set(after)),
                                                           sorted(set(after) - set(before))))
    def snap(x):
        # Section ranges are read as FLOAT seconds (get_*_frame_seconds): ~5.9 ticks per float step near 2100 s
        # (C++ build agent 6 Oct; float32 round trip reproduces every recorded offset). Snap to a retimed boundary.
        for sp in spans:
            for edge in (int(sp[0]), int(sp[1])):
                if abs(int(x) - edge) <= SECTION_READ_TOL_TICKS:
                    return edge
        return int(x)

    for key in sorted(set(before) & set(after)):
        b = [None if x is None else snap(x) for x in before[key]]
        ws = [None if x is None else (None if shift_at(x, spans) is None else int(x) + shift_at(x, spans)) for x in b]
        if any(x is not None and shift_at(x, spans) is None for x in b):
            out.append("MANAGED_STRADDLES_RETIMED: %s %r" % (key, before[key]))
            continue
        got = [None if x is None else int(x) for x in after[key]]
        if any((g is None) != (w is None) or (g is not None and abs(g - w) > SECTION_READ_TOL_TICKS)
               for g, w in zip(got, ws)):
            out.append("MANAGED_MOVED_WRONG: %s want %r got %r" % (key, ws, after[key]))
    return out


def keys_gate(before, after, spans):
    """Passage channel keys {guid: {"start", "channels", "pins_rel", "wing_pins"}}: every key moves by its section's
    start shift (MoveSection, SequenceBuilderLibrary.cpp:300-309); pins identical."""
    out = []
    if sorted(before) != sorted(after):
        return ["PASSAGE_SECTION_SET_CHANGED: %r -> %r" % (sorted(before), sorted(after))]
    for guid in sorted(before):
        b, a = before[guid], after[guid]
        shift = shift_at(b["start"], spans)
        if shift is None:
            out.append("PASSAGE_SECTION_STARTS_INSIDE_RETIMED: %s" % guid)
            continue
        want = {n: [[int(t) + shift, v] for t, v in ks] for n, ks in b["channels"].items()}
        got = {n: [[int(t), v] for t, v in ks] for n, ks in a["channels"].items()}
        if want != got:
            bad = sorted(n for n in set(want) | set(got) if want.get(n) != got.get(n))
            out.append("PASSAGE_KEYS_MOVED_WRONG: %s channels %s (expected shift %d)" % (guid, bad, shift))
        if list(b.get("pins_rel") or []) != list(a.get("pins_rel") or []):
            out.append("PASSAGE_PINS_CHANGED: %s %r -> %r" % (guid, b.get("pins_rel"), a.get("pins_rel")))
        if sorted(b.get("wing_pins") or []) != sorted(a.get("wing_pins") or []):
            out.append("PASSAGE_WING_PINS_CHANGED: %s" % guid)
    return out


def artist_refusals(artist_rows, root_markers, earliest_start, old_show_end, net_delta):
    """Unmanaged Master content is absolute and NOT rippled. rows: [{"owner","track","class","sections":[[s,e]],
    "keys":[tick]}] (None = open bound); root_markers [[label, tick]]."""
    r, w = [], []
    t0 = int(earliest_start)
    for row in artist_rows or []:
        name = "%s %s (%s)" % (row.get("owner"), row.get("track"), row.get("class"))
        late_k = [k for k in row.get("keys") or [] if int(k) >= t0]
        if late_k:
            r.append("ARTIST_KEYS_NOT_RIPPLED: %s %d key(s) at/after tick %d: %s" % (name, len(late_k), t0, late_k[:5]))
        for s, e in row.get("sections") or []:
            if s is not None and int(s) >= t0:
                r.append("ARTIST_SECTION_NOT_RIPPLED: %s [%s, %s) starts at/after %d" % (name, s, e, t0))
            elif e is None or int(e) > t0:
                whole = e is None or int(e) >= int(old_show_end)
                if whole and int(net_delta) <= 0:
                    w.append("ARTIST_WHOLE_SHOW_SECTION: %s [%s, %s) still covers the shorter Show" % (name, s, e))
                else:
                    r.append("ARTIST_SECTION_STRADDLES: %s [%s, %s) across tick %d (net delta %d)" % (
                        name, s, e, t0, net_delta))
    for label, tick in root_markers or []:
        if int(tick) >= t0:
            r.append("MASTER_MARKER_NOT_RIPPLED: %r at tick %d" % (label, tick))
    return r, w


def sync_gate(show_rows, master_rows, tol_s=SYNC_TOL_S):
    """p06_tail_extend.py:360-373 (walking_music_swap.py:283-298 logic): the Master must already match the Show."""
    out = []
    for label in sorted(show_rows):
        m = master_rows.get(label)
        if m is None:
            out.append("MASTER_SECTION_MISSING: %s" % label)
            continue
        err = max(abs(show_rows[label][0] - m[0]), abs(show_rows[label][1] - m[1]))
        if err > tol_s:
            out.append("MASTER_STALE: %s Show %r Master %r (err %.3f s)" % (label, show_rows[label], m, err))
    for label in sorted(set(master_rows) - set(show_rows)):
        out.append("MASTER_EXTRA_SECTION: %s" % label)
    return out


def handoff_gate(stale_before, stale_after):
    new = sorted(set(stale_after) - set(stale_before))
    return ["HANDOFF_NEWLY_STALE: %s" % new] if new else []


def census_gate(census, expected_content):
    out = []
    got = sorted(census.get("content") or [])
    if not set(got) <= set(expected_content):
        out.append("UNEXPECTED_DIRTY: %s" % sorted(set(got) - set(expected_content)))
    if census.get("maps"):
        out.append("MAP_DIRTY: %s" % census["maps"])
    return out


def expected_refusals(key, plan, expected, mode):
    """APPLY must carry the DRY's numbers: the live state and the plan must not have moved since the decision."""
    if mode != "APPLY":
        return []
    r = []
    if int(expected.get("old_len_ticks", -1)) != plan["old_ticks"]:
        r.append("P%s OLD_LENGTH_CHANGED_SINCE_DRY: live %d, args %r" % (key, plan["old_ticks"],
                                                                         expected.get("old_len_ticks")))
    if int(expected.get("new_len_ticks", -1)) != plan["new_ticks"]:
        r.append("P%s PLAN_CHANGED_SINCE_DRY: plan %d, args %r" % (key, plan["new_ticks"], expected.get("new_len_ticks")))
    if expected.get("route_cm") is not None and abs(float(expected["route_cm"]) - plan.get("route_cm", -1)) > 0.01:
        r.append("P%s ROUTE_CHANGED_SINCE_DRY: live %.4f, args %r" % (key, plan.get("route_cm", -1), expected["route_cm"]))
    return r


def protected_diff(before, after):
    """Everything but the planned timing fields must be identical. before/after from protected_view()."""
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def timing_view(per):
    """{key: {"lead", "intervals", "tail"}} - the only fields this tool writes."""
    return {k: {"lead": int(v["lead"]), "intervals": [int(x) for x in v["intervals"]], "tail": int(v["tail"])}
            for k, v in per.items()}


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % state.get("mode"))
    want = "%s %s" % (mode, CONFIRM_SUFFIX)
    if state.get("confirm") != want:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), want))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode == "APPLY":
        if state.get("covering_records"):
            r.append("PASSAGE_ALREADY_RETIMED: applied record(s) %s cover %s (REVERT first)" % (
                state["covering_records"], state.get("passages")))
        if state.get("record_exists"):
            r.append("RECORD_EXISTS: %s" % state.get("record_name"))
        if not str(state.get("decided_by") or "").strip():
            r.append("NOT_DECIDED: args decided_by is empty")
        for missing in state.get("prerequisites_missing") or []:
            r.append("PREREQUISITE_NOT_APPLIED: %s" % missing)
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD: %s" % state.get("record_name"))
    return r


def record_name(keys):
    return RECORD_PREFIX + "-".join("P0%s" % k for k in sorted(keys)) + ".json"


def records_covering(folder, keys):
    """Applied records (not .reverted/.failed) that retime any of keys."""
    hits = []
    for name in sorted(os.listdir(folder)):
        if not (name.startswith(RECORD_PREFIX) and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(folder, name), "r", encoding="utf-8") as handle:
                rec = json.load(handle)
        except (OSError, ValueError):
            hits.append(name + " (unreadable)")
            continue
        if rec.get("applied") and set(rec.get("passages") or []) & set(keys):
            hits.append(name)
    return hits


def prerequisites_missing(folder, keys, prereq):
    """prereq {key: record file name}: each must exist here with applied true (e.g. P02 straighten)."""
    out = []
    for k in keys:
        name = (prereq or {}).get(k)
        if not name:
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                rec = json.load(handle)
                ok = bool(rec.get("applied")) or rec.get("status") == "saved"  # p02_straighten writes status "saved"
        except (OSError, ValueError):
            ok = False
        if not ok:
            out.append("P%s needs %s (applied)" % (k, name))
    return out


def drift_refusals(live, record):
    out = []
    for field in ("timing", "segments", "managed"):
        if live.get(field) != record["after"].get(field):
            out.append("STATE_DRIFTED_SINCE_APPLY: %s (revert later retimes / tail extends first - LIFO)" % field)
    return out


def revert_exact_gate(live, record):
    return ["REVERT_NOT_EXACT: %s" % f for f in ("timing", "segments", "managed", "keys")
            if live.get(f) != record["before"].get(f)]


def write_record_exclusive(path, data):
    """Create-only, fsynced BEFORE any mutation [prec p06_tail_extend.py:449-455]."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def unwrap(result, count):
    """p06_tail_extend.py:467-476 (verify_camera_pilot_readonly.py:25-33): out-params tuple, None on false."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    if count == 1 and not isinstance(result, tuple):
        return (result,)
    return result


def plan_passage(key, live, tick, fps, args):
    """All per-Passage planning from plain live facts. live: lead, intervals, tail, lead_cm, gaps, tail_cm, music,
    segment {start,end}, channels, pins_rel, origins, choreo, settle_s. Returns (row, refusals, warnings)."""
    per = args["per_passage"][key]
    r, w = [], []
    seg = live["segment"]
    old_len = seg["end"] - seg["start"]
    c = compiled_length(live["lead"], live["intervals"], live["tail"])
    if c != old_len:
        r.append("P%s COMPILE_MODEL_MISMATCH: lead+intervals+tail %d != segment %d" % (key, c, old_len))
    tgt = target_ticks(per["song_s"], args["tail_s"], tick, fps[0], fps[1])
    settle_ticks = float(live.get("settle_s") or 0.0) * tick
    comp = settle_compensation_ticks(live.get("settle_s") or 0.0, tick) if args.get("settle_compensation", True) else 0
    plan = plan_scaled_timing(live["lead"], live["intervals"], live["tail"], tgt - comp)
    plan = add_settle_compensation(plan, comp)
    if plan["tail_frames"] < settle_ticks:
        r.append("P%s TAIL_SHORTER_THAN_SETTLE: %d < %.0f ticks" % (key, plan["tail_frames"], settle_ticks))
    if plan["lead_frames"] == 0 and float(live["lead_cm"]) != 0.0:
        r.append("P%s LEAD_FRAMES_ROUND_TO_ZERO with lead distance (Compiler.cpp:290-293)" % key)
    if plan["tail_frames"] == 0 and float(live["tail_cm"]) != 0.0:
        r.append("P%s TAIL_FRAMES_ZERO with tail distance (Compiler.cpp:294-297)" % key)
    old_v = speeds(live["lead"], live["intervals"], live["tail"], live["lead_cm"], live["gaps"], live["tail_cm"], tick,
                   live.get("settle_s") or 0.0)
    new_v = speeds(plan["lead_frames"], plan["intervals"], plan["tail_frames"], live["lead_cm"], live["gaps"],
                   live["tail_cm"], tick, live.get("settle_s") or 0.0)
    plan["route_cm"] = old_v["route_cm"]
    if new_v["bay_max"] and new_v["bay_max"] > float(args["max_speed_cm_s"]):
        r.append("P%s TOO_FAST: bay %.1f cm/s > max_speed_cm_s %.1f" % (key, new_v["bay_max"], args["max_speed_cm_s"]))
    mr, fit_row = music_refusals(key, dict(live.get("music") or {}, args_sound=per["sound"]) if live.get("music")
                                 else None, plan["new_ticks"], tick, per["song_s"])
    r += mr
    cr, notes = channel_refusals(key, live.get("channels"), seg["start"], seg["end"])
    r += cr
    w += notes
    r += pin_refusals(key, live.get("pins_rel"))
    r += mechanism_refusals(key, live.get("origins") or [])
    chr_, chw = choreo_refusals(key, live.get("choreo"), plan["new_ticks"], bool(args.get("allow_stale_song_markers")))
    r += chr_
    w += chw
    cel = live.get("celestial")
    if cel and cel.get("animate"):
        days_old = old_len / tick / max(float(cel["cycle_s"]), 1e-6) * float(cel["rate"])
        days_new = plan["new_ticks"] / tick / max(float(cel["cycle_s"]), 1e-6) * float(cel["rate"])
        w.append("P%s CELESTIAL_SECONDS_BASED: %.2f -> %.2f day/night cycles over the Passage" % (key, days_old, days_new))
    r += expected_refusals(key, plan, per.get("expected") or {}, str(args.get("mode")).upper())
    row = {"key": key, "label": label_of(key), "segment": seg, "plan": plan, "speeds_old": old_v, "speeds_new": new_v,
           "vs_p01_v_end": {"p01_v_end_cm_s": args.get("p01_v_end_cm_s"),
                            "new_tail_pre_settle_cm_s": new_v["tail_pre_settle"], "new_mean_cm_s": new_v["mean"]},
           "fit_after": fit_row, "old": {"lead": live["lead"], "intervals": live["intervals"], "tail": live["tail"],
                                         "len_ticks": old_len, "len_s": old_len / tick},
           "settle_s": live.get("settle_s")}
    return row, r, w


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local or an adapter attribute.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


_PATH_RX = re.compile(r"(/Game/[A-Za-z0-9_/\-]+)(?:\.[A-Za-z0-9_\-]+)?")


def soft_path_from_export(text, field):
    """walking_music_swap.py:499-509 verbatim (proven by its APPLY, WALK-20261005-143843 [meas])."""
    m = re.search(r"(?:^|[,(])%s=(\"[^\"]*\"|[^,)]*)" % re.escape(field), str(text))
    if not m:
        return None
    hit = _PATH_RX.search(m.group(1))
    return hit.group(1) if hit else None


def _soft(struct, field, prop):
    """walking_music_swap.py:583-594 verbatim: (path, loaded object) of a soft field."""
    obj = struct.get_editor_property(prop)
    if obj is not None and hasattr(obj, "load_synchronous"):
        obj = obj.load_synchronous()
    text = struct.export_text() if hasattr(struct, "export_text") else str(struct)
    path = soft_path_from_export(text, field)
    if obj is None and path:
        obj = unreal.load_asset(path)
    if obj is not None and path and _path(obj) != path:
        raise RuntimeError("SOFT_PATH_DISAGREES: %s %s vs %s" % (field, _path(obj), path))
    return (_path(obj) if obj is not None else path), obj


def _content_file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _ticks(seconds, tick):
    return int(round(float(seconds) * tick))


def _segments(show):
    """Compiled segments via a transient transport [prec p06_tail_extend.py:543-548]; ticks."""
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    return [{"label": str(s.get_editor_property("label")), "start": int(s.get_editor_property("start_frame").value),
             "end": int(s.get_editor_property("end_frame").value)} for s in tr.get_editor_property("segments")]


def _passage_rows(show):
    """{label: (index, settings)} for every Passage settings row; duplicates refused."""
    rows = {}
    for i, p in enumerate(show.get_editor_property("passage_settings")):
        lab = str(p.get_editor_property("label"))
        if lab in rows:
            raise PlanError("PASSAGE_LABEL_DUPLICATED: %s" % lab)
        rows[lab] = (i, p)
    return rows


def _cue_range(show, p, label):
    cues = list(show.get_editor_property("cues"))
    by_guid = {_guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
    first = by_guid.get(_guid(p.get_editor_property("first_cue_guid")))
    last = by_guid.get(_guid(p.get_editor_property("last_cue_guid")))
    if first is None or last is None or last < first:
        raise PlanError("%s CUE_RANGE_UNRESOLVED" % label)
    for i in range(first, last + 1):
        c = cues[i]
        if c.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR or not c.get_editor_property("enabled"):
            raise PlanError("%s CUE_%d_NOT_ENABLED_WINGPAIR" % (label, i))     # passage_slow_walk.py:197-201
    if last + 1 < len(cues):
        nxt = cues[last + 1]
        if nxt.get_editor_property("enabled") and nxt.get_editor_property("type") == unreal.InfinityCueType.WING_PAIR:
            raise PlanError("%s RANGE_NOT_MAXIMAL (compiler would join the next WingPair)" % label)
    return cues, first, last


def _passage_facts(show, label):
    rows = _passage_rows(show)
    if label not in rows:
        raise PlanError("PASSAGE_NOT_FOUND: %s" % label)
    index, p = rows[label]
    cues, first, last = _cue_range(show, p, label)
    intervals, gaps, wing_cues, origins = [], [], [], []
    for i in range(first, last + 1):
        wp = cues[i].get_editor_property("wing_pair")
        intervals.append(int(wp.get_editor_property("interval_to_next").value))
        gaps.append(float(wp.get_editor_property("gap_to_next_cm")))
        g = _guid(cues[i].get_editor_property("cue_guid"))
        wing_cues.append(g)
        origins.append([g, str(wp.get_editor_property("mechanism").get_editor_property("phase_origin"))])
    m = p.get_editor_property("music")
    cel = None
    try:
        cc = p.get_editor_property("celestial_cycle")
        cel = {"animate": bool(cc.get_editor_property("animate")), "cycle_s": float(cc.get_editor_property(
            "cycle_duration_seconds")), "rate": float(cc.get_editor_property("cycle_rate_multiplier"))}
    except Exception as exc:  # noqa: BLE001 - reported
        cel = {"animate": False, "unreadable": repr(exc), "cycle_s": 1.0, "rate": 0.0}
    choreo = p.get_editor_property("choreography")
    if choreo is not None and hasattr(choreo, "load_synchronous"):
        choreo = choreo.load_synchronous()
    return {"index": index, "guid": _guid(p.get_editor_property("passage_guid")), "first": first, "last": last,
            "lead": int(p.get_editor_property("lead_in_frames").value),
            "tail": int(p.get_editor_property("tail_frames").value),
            "lead_cm": float(p.get_editor_property("lead_in_distance_cm")),
            "tail_cm": float(p.get_editor_property("tail_distance_cm")), "intervals": intervals, "gaps": gaps,
            "wing_cues": wing_cues, "origins": origins, "celestial": cel, "choreo_obj": choreo,
            "fit_mode": str(p.get_editor_property("fit_mode")),
            "preferred_speed": float(p.get_editor_property("preferred_camera_speed_cm_per_second")),
            "music_binding": {"mode": str(m.get_editor_property("mode")),
                              "rail": _guid(m.get_editor_property("primary_rail_guid")),
                              "offset": int(m.get_editor_property("rail_offset_frames").value)}}


def _rail(show, rail_guid):
    for r in show.get_editor_property("music_rails"):
        if _guid(r.get_editor_property("rail_guid")) == rail_guid:
            return {"sound": _soft(r, "Sound", "sound")[0],
                    "source_in": int(r.get_editor_property("source_in_frame").value),
                    "source_out": int(r.get_editor_property("source_out_frame").value),
                    "fade_in": int(r.get_editor_property("fade_in_frames").value),
                    "fade_out": int(r.get_editor_property("fade_out_frames").value)}
    return None


def protected_view(show):
    """Every cue and Passage field this tool must NOT change, as comparable plain data. Timing fields excluded."""
    out = {}
    for i, c in enumerate(show.get_editor_property("cues")):
        row = [_guid(c.get_editor_property("cue_guid")), str(c.get_editor_property("label")),
               str(c.get_editor_property("type")), bool(c.get_editor_property("enabled"))]
        if c.get_editor_property("type") == unreal.InfinityCueType.WING_PAIR:
            wp = c.get_editor_property("wing_pair")
            mech = wp.get_editor_property("mechanism")
            row += [_guid(wp.get_editor_property("occurrence_guid")), float(wp.get_editor_property("gap_to_next_cm")),
                    int(wp.get_editor_property("local_override_mask")), str(mech.get_editor_property("phase_origin")),
                    float(mech.get_editor_property("cycle_rate_hz")), len(wp.get_editor_property("attachments")),
                    _path(wp.get_editor_property("left").get_editor_property("mesh")),     # passage_slow_walk.py:146-152
                    _path(wp.get_editor_property("right").get_editor_property("mesh"))]
        else:
            row += [int(c.get_editor_property("scene").get_editor_property("duration_frames").value)]
        out["cue%03d" % i] = row
    for i, p in enumerate(show.get_editor_property("passage_settings")):
        m = p.get_editor_property("music")
        out["passage%02d" % i] = [
            _guid(p.get_editor_property("passage_guid")), str(p.get_editor_property("label")),
            _guid(p.get_editor_property("first_cue_guid")), _guid(p.get_editor_property("last_cue_guid")),
            float(p.get_editor_property("lead_in_distance_cm")), float(p.get_editor_property("tail_distance_cm")),
            float(p.get_editor_property("preferred_camera_speed_cm_per_second")), str(p.get_editor_property("fit_mode")),
            _soft(p, "Choreography", "choreography")[0], str(m.get_editor_property("mode")),
            _guid(m.get_editor_property("primary_rail_guid")), int(m.get_editor_property("rail_offset_frames").value)]
    for i, r in enumerate(show.get_editor_property("music_rails")):
        out["rail%02d" % i] = [_guid(r.get_editor_property("rail_guid")), _soft(r, "Sound", "sound")[0],
                               int(r.get_editor_property("source_in_frame").value),
                               int(r.get_editor_property("source_out_frame").value),
                               int(r.get_editor_property("fade_in_frames").value),
                               int(r.get_editor_property("fade_out_frames").value)]
    out["display_rate"] = str(show.get_editor_property("display_rate"))
    out["tick_resolution"] = str(show.get_editor_property("tick_resolution"))
    return out


def _write_timing(show, rows_by_key, timing):
    """Write lead/tail (passage_settings) and IntervalToNext (cues); arrays of structs are copies -> write back
    [prec passage_slow_walk.py:391-407]."""
    show.modify()
    ps = list(show.get_editor_property("passage_settings"))
    for key, t in timing.items():
        idx = rows_by_key[key]["index"]
        p = ps[idx]
        p.set_editor_property("lead_in_frames", unreal.FrameNumber(int(t["lead"])))
        p.set_editor_property("tail_frames", unreal.FrameNumber(int(t["tail"])))
        ps[idx] = p
    show.set_editor_property("passage_settings", ps)
    cues = list(show.get_editor_property("cues"))
    for key, t in timing.items():
        first = rows_by_key[key]["first"]
        for j, iv in enumerate(t["intervals"]):
            c = cues[first + j]
            wp = c.get_editor_property("wing_pair")
            wp.set_editor_property("interval_to_next", unreal.FrameNumber(int(iv)))
            c.set_editor_property("wing_pair", wp)
            cues[first + j] = c
    show.set_editor_property("cues", cues)


def _read_timing(show, keys):
    out = {}
    for k in keys:
        f = _passage_facts(show, label_of(k))
        out[k] = {"lead": f["lead"], "intervals": f["intervals"], "tail": f["tail"]}
    return timing_view(out)


def _channel_keys(section):
    """p06_tail_extend.py:588-605."""
    out = {}
    for ch in section.get_all_channels():
        try:
            keys = ch.get_keys()
        except Exception:  # noqa: BLE001 - a channel type without keys
            continue
        rows = []
        for k in keys:
            t = int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value)
            try:
                v = float(k.get_value())
            except Exception:  # noqa: BLE001 - non-scalar key: compare by time only
                v = None
            rows.append([t, v])
        if rows:
            out[str(ch.get_editor_property("channel_name"))] = sorted(rows, key=lambda r: r[0])
    return out


def _all_tracks(seq):
    """p06_tail_extend.py:608-623."""
    rows, seen = [], set()
    hosts = [("root", t) for t in seq.get_tracks()]
    for b in seq.get_bindings():
        hosts += [("binding:%s" % b.get_display_name(), t) for t in b.get_tracks()]
    try:
        hosts += [("root", t) for t in seq.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)]
    except Exception:  # noqa: BLE001
        pass
    for owner, t in hosts:
        key = t.get_path_name()
        if key not in seen:
            seen.add(key)
            rows.append((owner, t))
    return rows


def _section_range(sec, tick, origin=0):
    s = _ticks(sec.get_start_frame_seconds(), tick) - origin if sec.has_start_frame() else None
    e = _ticks(sec.get_end_frame_seconds(), tick) - origin if sec.has_end_frame() else None
    return s, e


def _master_state(master, show_guid, tick):
    """p06_tail_extend.py:632-666: managed {"Kind:GUID": [s, e]} + Playback; passage keys/pins; artist; markers."""
    managed, keys, artist, dup = {}, {}, [], []
    managed["Playback:master"] = [_ticks(master.get_playback_start_seconds(), tick),
                                  _ticks(master.get_playback_end_seconds(), tick)]
    for owner, track in _all_tracks(master):
        cls = track.get_class().get_name()
        kind = MANAGED_CLASSES.get(cls)
        is_managed = False
        if kind and owner == "root":
            try:
                is_managed = _guid(track.get_editor_property("owner_guid")) == show_guid
            except Exception:  # noqa: BLE001
                is_managed = False
        if is_managed:
            for sec in track.get_sections():
                k = "%s:%s" % (kind, _guid(sec.get_editor_property("block_guid")))
                if k in managed:
                    dup.append(k)
                managed[k] = list(_section_range(sec, tick))
                if kind == "Passage":
                    keys[k.split(":", 1)[1]] = {
                        "start": managed[k][0], "channels": _channel_keys(sec),
                        "pins_rel": [int(f.value) for f in sec.get_editor_property("pinned_passage_frames")],
                        "wing_pins": sorted(_guid(g) for g in sec.get_editor_property("pinned_wing_cue_guids"))}
            continue
        row = {"owner": owner, "track": str(track.get_display_name()), "class": cls, "sections": [], "keys": []}
        for sec in track.get_sections():
            row["sections"].append(list(_section_range(sec, tick)))
            for ks in _channel_keys(sec).values():
                row["keys"] += [k[0] for k in ks]
        artist.append(row)
    markers = [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)]
               for m in master.get_marked_frames()]
    return managed, keys, artist, markers, dup


def _choreo_facts(choreo, master, guid, show_tick):
    """p06_tail_extend.py:669-702: Choreo content in local ticks (0 = Passage start)."""
    if choreo is None:
        return None
    tick = _rate(choreo.get_tick_resolution())
    if abs(tick - show_tick) > 1e-9:
        raise PlanError("CHOREO_TICK_RESOLUTION %s != Show %s" % (tick, show_tick))
    origin = _ticks(choreo.get_playback_start_seconds(), tick)
    facts = {"path": _path(choreo), "playback_ticks": [0, _ticks(choreo.get_playback_end_seconds(), tick) - origin],
             "keys": [], "sections": [], "camera_cut": False, "start_offset": 0, "time_scale": None,
             "markers": [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value) - origin]
                         for m in choreo.get_marked_frames()]}
    for owner, track in _all_tracks(choreo):
        cls = track.get_class().get_name()
        if cls == "MovieSceneCameraCutTrack":
            facts["camera_cut"] = True
        for sec in track.get_sections():
            ks = _channel_keys(sec)
            s, e = _section_range(sec, tick, origin)
            where = "%s/%s/%s" % (owner, cls, track.get_display_name())
            facts["sections"].append({"where": where, "start": s, "end": e, "keyed": bool(ks)})
            for name, rows in ks.items():
                facts["keys"] += [["%s/%s" % (where, name), k[0] - origin] for k in rows]
    for t in [t for t in master.get_tracks() if t.get_class().get_name() == "MovieSceneInfinityChoreoTrack"]:
        for sec in t.get_sections():
            if _guid(sec.get_editor_property("block_guid")) != guid:
                continue
            try:
                prm = sec.get_editor_property("parameters")
                facts["start_offset"] = int(prm.get_editor_property("start_frame_offset").value)
                facts["time_scale"] = str(prm.get_editor_property("time_scale"))
            except Exception as exc:  # noqa: BLE001 - reported
                facts["time_scale"] = "unreadable: %r" % exc
    return facts


def _label_rows(master, segments, tick, guid_by_label):
    """p06_tail_extend.py:705-723."""
    show_rows = {s["label"]: [s["start"] / tick, s["end"] / tick] for s in segments}
    secs = []
    for track in master.find_tracks_by_exact_type(unreal.MovieSceneInfinitySceneTrack):
        for sec in track.get_sections():
            secs.append([sec.get_start_frame_seconds(), sec.get_end_frame_seconds()])
    secs.sort()
    seq_labels = [s["label"] for s in sorted(segments, key=lambda x: x["start"]) if not s["label"].startswith("Passage")]
    master_rows = dict(zip(seq_labels, secs))
    for track in [t for t in master.get_tracks() if t.get_class().get_name() == "MovieSceneInfinityPassageTrack"]:
        for sec in track.get_sections():
            g = _guid(sec.get_editor_property("block_guid"))
            for label, guid in guid_by_label.items():
                if guid == g:
                    master_rows[label] = [sec.get_start_frame_seconds(), sec.get_end_frame_seconds()]
    if len(secs) != len(seq_labels):
        master_rows["<sub-section count %d vs %d sequence segments>" % (len(secs), len(seq_labels))] = [0.0, 0.0]
    return show_rows, master_rows


def _guid_by_label(show):
    return {str(p.get_editor_property("label")): _guid(p.get_editor_property("passage_guid"))
            for p in show.get_editor_property("passage_settings")}


def _handoffs(show):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    res = unwrap(unreal.InfinityStageSequenceBuilderLibrary.check_scene_handoffs(show, world), 2)  # read-only
    if res is None:
        return None, "check_scene_handoffs returned false"
    return sorted(_guid(g) for g in res[0]), str(res[1])


def _settle_seconds(default_s):
    """CrossingSettleSeconds of the level's camera rig(s), read-only; falls back to args (rig default 1.0 s)."""
    vals = []
    try:
        for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
            if isinstance(a, unreal.InfinityStageCameraRig):
                vals.append(float(a.get_editor_property("crossing_settle_seconds")))
    except Exception:  # noqa: BLE001 - reported via source
        vals = []
    if not vals:
        return float(default_s), "args (no rig read)"
    return max(vals), "rig(s) %r" % vals


def _snapshot(show, master, keys):
    tick = _rate(show.get_editor_property("tick_resolution"))
    managed, pkeys, artist, markers, dup = _master_state(master, _guid(show.get_editor_property("show_guid")), tick)
    return {"tick": tick, "segments": _segments(show), "managed": managed, "keys": pkeys, "artist": artist,
            "markers": markers, "dup": dup, "timing": _read_timing(show, keys)}


def _plain(snap):
    return {"timing": snap["timing"], "segments": snap["segments"], "managed": snap["managed"], "keys": snap["keys"]}


def _gather(args):
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    keys = sorted(args["passages"])
    snap = _snapshot(show, master, keys)
    tick = snap["tick"]
    dr = show.get_editor_property("display_rate")
    fps = (dr.numerator, dr.denominator)
    settle_s, settle_src = _settle_seconds(args.get("crossing_settle_s", 1.0))
    refusals, warnings, rows, facts_by_key = [], [], {}, {}
    if snap["dup"]:
        refusals.append("MANAGED_BLOCK_DUPLICATED: %s" % snap["dup"])
    seg_by_label = {s["label"]: s for s in snap["segments"]}
    for k in keys:
        lab = label_of(k)
        f = _passage_facts(show, lab)
        facts_by_key[k] = f
        if f["guid"] != args["per_passage"][k]["guid"]:
            refusals.append("P%s GUID: live %s != args %s" % (k, f["guid"], args["per_passage"][k]["guid"]))
        if lab not in seg_by_label:
            raise PlanError("SEGMENT_MISSING: %s" % lab)
        pk = snap["keys"].get(f["guid"]) or {"channels": {}, "pins_rel": [], "wing_pins": []}
        if f["guid"] not in snap["keys"]:
            refusals.append("P%s MASTER_SECTION_MISSING" % k)
        rail = _rail(show, f["music_binding"]["rail"])
        music = dict(rail, mode=f["music_binding"]["mode"], offset=f["music_binding"]["offset"]) if rail else None
        live = {"lead": f["lead"], "intervals": f["intervals"], "tail": f["tail"], "lead_cm": f["lead_cm"],
                "gaps": f["gaps"], "tail_cm": f["tail_cm"], "segment": seg_by_label[lab], "music": music,
                "channels": pk["channels"], "pins_rel": pk["pins_rel"], "origins": f["origins"],
                "choreo": _choreo_facts(f["choreo_obj"], master, f["guid"], tick), "settle_s": settle_s,
                "celestial": f["celestial"]}
        row, r, w = plan_passage(k, live, tick, fps, args)
        row.update({"guid": f["guid"], "fit_mode": f["fit_mode"], "preferred_speed_cm_s": f["preferred_speed"],
                    "music": music, "wing_pairs": len(f["intervals"]), "lead_cm": f["lead_cm"], "tail_cm": f["tail_cm"],
                    "gaps_distinct": sorted(set(f["gaps"])), "channels": pk["channels"], "pins_rel": pk["pins_rel"],
                    "wing_pins": pk["wing_pins"], "choreo": live["choreo"]})
        rows[k] = row
        refusals += r
        warnings += w
    deltas = {label_of(k): rows[k]["plan"]["delta_ticks"] for k in keys}
    pred = predict_segments(snap["segments"], deltas)
    spans = retimed_spans(snap["segments"], deltas)
    earliest = min(s for s, _e, _d in spans)
    old_end = snap["managed"]["Playback:master"][1]
    net = sum(deltas.values())
    # later Passages: absolute mechanism origins would not travel
    for lab, (idx, _p) in sorted(_passage_rows(show).items()):
        seg = seg_by_label.get(lab)
        if seg is None or lab in deltas or seg["start"] < earliest:
            continue
        refusals += mechanism_refusals(lab.replace("Passage ", ""), _passage_facts(show, lab)["origins"], later=True)
    ar, aw = artist_refusals(snap["artist"], snap["markers"], earliest, old_end, net)
    refusals += ar
    warnings += aw
    show_rows, master_rows = _label_rows(master, snap["segments"], tick, _guid_by_label(show))
    refusals += sync_gate(show_rows, master_rows)
    stale, handoff_report = _handoffs(show)
    if stale is None:
        warnings.append("HANDOFF_CHECK_FAILED: %s" % handoff_report)
    choreo_sections = {k: {"old": snap["managed"].get("Choreo:" + rows[k]["guid"])} for k in keys}
    report = {"tick_rate": tick, "display_rate": list(fps), "settle_s": settle_s, "settle_source": settle_src,
              "tail_s": args["tail_s"], "per": rows, "deltas": deltas, "net_delta_ticks": net,
              "net_delta_s": net / tick, "segments_predicted": pred, "earliest_retimed_start": earliest,
              "old_show_end": old_end, "new_show_end": old_end + net, "choreo_master_sections": choreo_sections,
              "artist_content": snap["artist"], "master_markers": snap["markers"],
              "handoff_stale_before": stale, "handoff_report": handoff_report,
              "p06_tail_extend_note": "p06_tail_extend args hold only P06's LENGTH (expected_old_len_ticks); it reads "
                                      "segments live, so a retime of P02-P05 leaves its args valid "
                                      "(p06_tail_extend.py:117,176-184,763-769)",
              "refusals": refusals, "warnings": warnings}
    return report, snap, show, master, facts_by_key


def _backup(run, suffix, paths):
    folder = os.path.join(_project(), "Backups", "PrePassageRetime%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path in paths:
        src = _content_file(path)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = []
        for x in (src, dst):
            with open(x, "rb") as handle:
                digest.append(hashlib.sha256(handle.read()).hexdigest())
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _rebuild(show, master):
    res = unwrap(unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master), 1)
    return (False, "rebuild returned false/None") if res is None else (True, str(res[0]))


def _per_text(report):
    return ",".join("P0%s:%.3f->%.3fs" % (k, r["old"]["len_s"], r["plan"]["new_ticks"] / report["tick_rate"])
                    for k, r in sorted(report["per"].items()))


def _log_rows(run, report):
    for k, r in sorted(report["per"].items()):
        p, o, n = r["plan"], r["speeds_old"], r["speeds_new"]
        unreal.log("%s_PLAN|run=%s|P0%s|old lead=%d tail=%d pairs=%d len=%d(%.4fs)|new lead=%d tail=%d len=%d(%.4fs)|"
                   "k=%.6f|route=%.2fcm|mean %.2f->%.2f cm/s|bay %s-%s -> %s-%s|tail_pre_settle %s->%s|p01_v_end=%s" % (
                       MARK, run, k, r["old"]["lead"], r["old"]["tail"], r["wing_pairs"], p["old_ticks"],
                       r["old"]["len_s"], p["lead_frames"], p["tail_frames"], p["new_ticks"],
                       p["new_ticks"] / report["tick_rate"], p["k"], o["route_cm"], o["mean"], n["mean"], o["bay_min"],
                       o["bay_max"], n["bay_min"], n["bay_max"], o["tail_pre_settle"], n["tail_pre_settle"],
                       r["vs_p01_v_end"]["p01_v_end_cm_s"]))
        unreal.log("%s_MUSIC|run=%s|P0%s|%s" % (MARK, run, k, json.dumps(r["fit_after"], ensure_ascii=False)))
    for row in report["segments_predicted"]:
        unreal.log("%s_SEGMENT|run=%s|%s|%d->%d|end %d->%d|shift=%d" % (
            MARK, run, row["label"], row["start"], row["new_start"], row["end"], row["new_end"], row["shift"]))
    for text in report["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, text))
    for text in report["warnings"]:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, text))


def run_dry(args, run):
    report, _snap, _s, _m, _f = _gather(args)
    out = os.path.join(_here(), DRY_NAME)
    expected = {k: {"old_len_ticks": r["plan"]["old_ticks"], "new_len_ticks": r["plan"]["new_ticks"],
                    "route_cm": r["speeds_old"]["route_cm"]} for k, r in report["per"].items()}
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(dict(report, tool=TOOL, run=run, mode="DRY", args=args, apply_ready=not report["refusals"],
                       expected_for_apply_args=expected), handle, indent=1, sort_keys=True, default=str,
                  ensure_ascii=False)
    _log_rows(run, report)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|per=%s|net_s=%.4f|report=%s" % (
        MARK, run, int(not report["refusals"]), len(report["refusals"]), len(report["warnings"]), _per_text(report),
        report["net_delta_s"], out))


def _post_gates(report, before, after, show):
    f = []
    spans = retimed_spans(before["segments"], report["deltas"])
    f += segment_shift_gate(before["segments"], after["segments"], report["deltas"])
    f += managed_shift_gate(before["managed"], after["managed"], spans)
    f += keys_gate(before["keys"], after["keys"], spans)
    if after["dup"]:
        f.append("MANAGED_BLOCK_DUPLICATED_AFTER: %s" % after["dup"])
    if after["artist"] != before["artist"] or after["markers"] != before["markers"]:
        f.append("ARTIST_CONTENT_OR_MARKERS_CHANGED")
    for k, r in report["per"].items():
        seg = [s for s in after["segments"] if s["label"] == label_of(k)]
        if len(seg) != 1 or seg[0]["end"] - seg[0]["start"] != r["plan"]["new_ticks"]:
            f.append("P%s NEW_LENGTH_WRONG: %r" % (k, seg))
        music = r["music"]
        if music:
            mr, _row = music_refusals(k, dict(music, args_sound=music["sound"]), r["plan"]["new_ticks"],
                                      report["tick_rate"], (music["source_out"] - music["source_in"]) / report["tick_rate"])
            f += mr
    if report["handoff_stale_before"] is not None:
        stale_after, rep = _handoffs(show)
        f += ["HANDOFF_CHECK_FAILED_AFTER: %s" % rep] if stale_after is None else handoff_gate(
            report["handoff_stale_before"], stale_after)
    return f


def run_apply(args, run):
    report, before, show, master, facts = _gather(args)
    if report["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(report["refusals"]))
    keys = sorted(args["passages"])
    record_path = os.path.join(_here(), record_name(keys))
    prot_before = protected_view(show)
    backup = _backup(run, "", [SHOW_PATH, MASTER_PATH])
    unreal.log("%s_BACKUP_OK|run=%s|backup=%s" % (MARK, run, backup))
    want = timing_view({k: {"lead": report["per"][k]["plan"]["lead_frames"],
                            "intervals": report["per"][k]["plan"]["intervals"],
                            "tail": report["per"][k]["plan"]["tail_frames"]} for k in keys})
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "backup": backup, "args": args,
              "passages": keys, "decided_by": args.get("decided_by"), "applied": False,
              "deltas": report["deltas"], "planned_timing": want,
              "rows_by_key": {k: {"index": facts[k]["index"], "first": facts[k]["first"], "guid": facts[k]["guid"]}
                              for k in keys},
              "written": datetime.datetime.now().isoformat(timespec="seconds"), "before": _plain(before)}
    write_record_exclusive(record_path, record)                  # BEFORE any change
    failures = []
    try:
        _write_timing(show, record["rows_by_key"], want)
        got = _read_timing(show, keys)
        if got != want:
            failures.append("READBACK_TIMING: %r != %r" % (got, want))
        diff = protected_diff(prot_before, protected_view(show))
        if diff:
            failures.append("PROTECTED_FIELDS_CHANGED: %s" % diff[:10])
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        failures.append("WRITE_RAISED: %r" % exc)
    if not failures:
        ok, text = _rebuild(show, master)
        record["rebuild_report"] = text
        if not ok:
            failures.append("REBUILD_FAILED: %s" % text)
    if not failures:
        after = _snapshot(show, master, keys)
        failures += _post_gates(report, before, after, show)
        record["after"] = _plain(after)
    failures += census_gate(_census(), [SHOW_PATH, MASTER_PATH])
    if failures:
        update_record(record_path, dict(record, applied=False, failed=failures))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|NOTHING SAVED; Don't-Save restart (Show/Master unsaved in memory); backup %s" % (
            failures[:10], backup))
    for path in (SHOW_PATH, MASTER_PATH):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s|record=%s (REVERT or restore %s)" % (path, record_path, backup))
    record["applied"] = True
    update_record(record_path, record)
    final = _plain(_snapshot(unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH), keys))
    dd = ["POST_SAVE_%s_DIFFERS" % f for f in ("timing", "segments", "managed", "keys") if final[f] != record["after"][f]]
    if _census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if dd:
        record["post_save_readback_failed"] = dd
        update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd, backup))
    unreal.log("%s_APPLY_OK|run=%s|per=%s|net_s=%.4f|backup=%s|record=%s|decided_by=%s" % (
        MARK, run, _per_text(report), report["net_delta_s"], backup, record_path, args.get("decided_by")))


def run_revert(args, run):
    keys = sorted(args["passages"])
    record_path = os.path.join(_here(), record_name(keys))
    with open(record_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or not record.get("after"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    for k in keys:
        f = _passage_facts(show, label_of(k))
        rk = record["rows_by_key"][k]
        if (f["index"], f["first"], f["guid"]) != (rk["index"], rk["first"], rk["guid"]):
            _stop(run, "REVERT_PASSAGE_ROW_MOVED|P%s" % k)
    snap = _snapshot(show, master, keys)
    drift = drift_refusals(_plain(snap), record)
    if drift:
        _stop(run, "%r (restore from %s instead)" % (drift, record["backup"]))
    show_rows, master_rows = _label_rows(master, snap["segments"], snap["tick"], _guid_by_label(show))
    stale = sync_gate(show_rows, master_rows)
    if stale:
        _stop(run, "MASTER_NOT_IN_SYNC_BEFORE_REVERT|%r" % stale[:6])
    prot_before = protected_view(show)
    backup = _backup(run, "Revert", [SHOW_PATH, MASTER_PATH])
    errs = []
    try:
        _write_timing(show, record["rows_by_key"], record["before"]["timing"])
        if _read_timing(show, keys) != record["before"]["timing"]:
            errs.append("READBACK_TIMING")
        diff = protected_diff(prot_before, protected_view(show))
        if diff:
            errs.append("PROTECTED_FIELDS_CHANGED: %s" % diff[:10])
    except Exception as exc:  # noqa: BLE001
        errs.append("WRITE_RAISED: %r" % exc)
    if not errs:
        ok, text = _rebuild(show, master)
        if not ok:
            errs.append("REBUILD_FAILED: %s" % text)
        else:
            errs += revert_exact_gate(_plain(_snapshot(show, master, keys)), record)
    errs += census_gate(_census(), [SHOW_PATH, MASTER_PATH])
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8], record["backup"]))
    for path in (SHOW_PATH, MASTER_PATH):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % path)
    final = revert_exact_gate(_plain(_snapshot(unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH), keys)),
                              record)
    if _census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final, record["backup"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|per=%s|backup=%s|record=%s" % (
        MARK, run, ",".join("P0%s" % k for k in keys), backup, archived))


def main():
    g = globals()
    args = g.get("RETIME_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("RETIME-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    keys = sorted(args["passages"])
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    here = _here()
    rp = os.path.join(here, record_name(keys))
    applied = False
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as handle:
            applied = bool(json.load(handle).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census(), "record_exists": os.path.exists(rp), "record_applied": applied,
             "record_name": os.path.basename(rp), "decided_by": args.get("decided_by"), "passages": keys,
             "covering_records": records_covering(here, keys) if mode == "APPLY" else [],
             "prerequisites_missing": prerequisites_missing(here, keys, args.get("prerequisite_records"))
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
