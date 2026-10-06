"""P06 TAIL EXTEND: lengthen Passage 6 by adding TAIL only, so Cameron's 125 s P06 track fits (Gary 5 Oct: "Lengthen P06
to fit"). Offline-written 5 Oct, NEVER RUN IN UNREAL. Harness: test_p06_tail_extend.py (system Python, no Unreal).

Tiers per claim: [decl] declaration-proven (source/header we can read, file:line), [bin] binary-proven (installed DLL
strings), [prec] in-repo precedent call (cited), [meas] an earlier run's read-back record (cited), [inf] inferred (why).

WHAT CHANGES
  * Passage length = LeadIn + sum(IntervalToNext of all but the last wing) + Tail; SegmentEnd = LastPass + TailFrames;
    TotalDistance += TailDistanceCm; the next segment starts at this Passage's end [decl InfinityStageCompiler.cpp:
    254-288, 312]. "Tail distance requires positive tail frames" only fires when TailFrames == 0 with a non-zero
    TailDistanceCm [decl :294-297]; this tool only ADDS frames, so it cannot trigger it.
  * The ONLY Show field written: PassageSettings[Passage 6].TailFrames += delta. TailDistanceCm, LeadIn, intervals,
    wings, route: unchanged [decl InfinityStageTypes.h:957-967 fields]. Wing pass frames and distances are therefore
    unchanged [decl Compiler.cpp:262-285]; only the tail drift (TailDistanceCm over the tail) slows.
  * delta = ceil((song_s + headroom_s) * tick - old_len) rounded UP to a whole display frame (ticks per display frame =
    tick / Show.DisplayRate, must be an integer). Show.DisplayRate defaults to 25 fps [decl InfinityStageShowAsset.cpp:86];
    the live value is read and printed by DRY. With 25 fps and the measured P06 (2653467 ticks, walking_music_swap_dry.json
    run WALK-20261005-143830 [meas]) delta = 386 frames = 370560 ticks = 15.440 s, new P06 = 3024027 ticks = 126.0011 s.

WHAT FOLLOWS AUTOMATICALLY (RebuildManagedMaster, called in-process as walking_music_swap.py:973 [prec])
  * Master playback range = [0, ShowEnd) [decl InfinityStageSequenceBuilderLibrary.cpp:229].
  * Passage sections: SetRange to the compiled segment; keys are moved (MoveSection) ONLY when the section START moves
    [decl :300-309, patch K]. P06's start does not move, so its absolute keys stay put; its range grows. Relative pins
    (PinnedPassageFrames) are filtered to (0, duration) [decl :287-298] - a longer duration removes none.
  * Choreo: nested per Passage over [SegmentStart, SegmentEnd), 0:00 at the Passage start; a reused section is moved
    then SetRange'd, verified, recreated as last resort (A2c) [decl :367-458; bin: "INFINITY_CHOREO_PLACED",
    "move_then_set_range", "INFINITY_CHOREO_SHORT" are UTF-16 strings in Binaries/Win64/UnrealEditor-InfinityStageEditor
    .dll of 5 Oct 11:25]. So the Master Choreo SECTION grows with P06 without any action here. The Choreo ASSET is never
    edited: if its playback range is shorter than the new P06 the builder only warns [decl :460-476]; this tool REFUSES
    then (CHOREO_SHORT). choreo_tool made it Passage + 30 s = 140.56 s [decl Saved/CodexCueing/choreo_tool.py:15,186;
    meas choreo_report_choreo-apply-3.json P6 length_s 110.561] - so no Choreo write is expected [inf until DRY reads it].
  * Scene / Sequence sections and music sections re-derive from the compiled cursor [decl :311-362, 503-599], so Scene 6
    and Closing shift by delta.
  * NOT followed: artist (unmanaged) Master tracks and Master root marked frames - absolute, the rebuild never touches
    them [decl: builder has no MarkedFrame code (grep); PassageResizeLibrary.cpp:116-200 lists them as "not rippled";
    RETIME_ROBUSTNESS_AUDIT_2026-10-04.md row 14]. DRY lists them; any at/after the old P06 end is a REFUSAL.

WHAT COULD CHANGE BEFORE THE OLD END (gated)
  * Camera progress is renormalised over the span between the last pin and the Passage END [decl
    MovieSceneInfinityPassageTrack.cpp:377-471, PinnedFrames.Add(PassageEnd) :398]. With a constant SpeedMultiplier the
    map is the identity (DistanceMasterFrame = MasterFrame) whatever the span end [inf: alpha = (t-s)/(E-s), lerp(s,E,alpha)
    = t]; a varying SpeedMultiplier inside the last span would re-shape the walk BEFORE the old end -> REFUSED
    (SPEED_RENORMALISED). P06 had 1 SpeedMultiplier key and 0 PinnedPassageFrames [meas walking_music_swap_dry.json row 6].
  * Crossing settle eases the last SettleFrames of the span that ends at the Passage end [decl :421-468]: the settle
    window moves with the end (old [E-1s, E) is no longer settling; new [E'-1s, E') is). Intended.
  * Keys/pins/Choreo content past the old end would become live -> REFUSED (KEY/PIN/CHOREO_*_BEYOND_OLD_END). Choreo GO
    markers are collected over the Passage segment [decl InfinityStageTransportController.cpp:931-940], so a non-song
    Choreo marker past the old end is refused; song markers ("bar ", "§ ") are warnings.
  * Scene handoffs: CheckSceneHandoffs (read-only [decl InfinityStageSequenceBuilderLibrary.h:17-23]) before and after
    the rebuild; any NEW stale Scene fails the APPLY. The Passage end pose should not move (same TotalDistance, no keys
    past the old end, constant extrapolation) [inf].
  * No Passage actor materialisation: wing layout depends on distances only, which do not change [inf from
    PassageActor.cpp:768-818 using TotalDistanceCm]; the level is not saved and the census must stay map-clean.

Modes (p06_tail_extend_run.py <- p06_tail_extend_args.json, confirm "<MODE> P06TAIL"):
  DRY    read-only; p06_tail_extend_dry.json; P06_TAIL_EXTEND_DRY_OK|run=..
  APPLY  guards (no PIE, Sequencer closed, clean census, Master in sync, no live record) -> plan refusals -> backup Show
         + Master -> exclusive fsynced record -> TailFrames += delta (read back) -> RebuildManagedMaster -> gates (P06 +delta
         exactly; earlier tick-identical; later +delta exactly; all Passage keys + pins unmoved; Choreo/music sections;
         playback range; no new stale handoff) -> census subset {Show, Master} -> save those two only -> read back ->
         census clean -> P06_TAIL_EXTEND_APPLY_OK|run=..|delta_s=..|p06_s=..
  REVERT drift check (tail, segments, managed sections == what APPLY left) -> backup -> TailFrames = recorded old ->
         rebuild -> everything == the record's BEFORE, tick-exact -> save Show + Master -> P06_TAIL_EXTEND_REVERT_OK|run=..
  Failure: P06_TAIL_EXTEND_STOPPED|run=..|reason=..
Never: Save All, level save, reload, open/scrub Sequencer, materialise, refit, end PIE; no unreal objects in module
globals. Importing without `unreal` runs nothing.
"""
import datetime
import fractions
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "p06_tail_extend"
MARK = "P06_TAIL_EXTEND"
CONFIRM_SUFFIX = "P06TAIL"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                 # walking_music_swap.py:102
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"   # walking_music_swap.py:103
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ARGS_NAME = "p06_tail_extend_args.json"
DRY_NAME = "p06_tail_extend_dry.json"
RECORD_NAME = "p06_tail_extend_record.json"
SONG_MARKER_PREFIXES = ("bar ", "§ ")     # choreo_tool.py:110,117 (walking_music_swap.py:117)
MANAGED_CLASSES = {"MovieSceneInfinityPassageTrack": "Passage", "MovieSceneInfinitySceneTrack": "Scene",
                   "MovieSceneInfinityChoreoTrack": "Choreo", "MovieSceneInfinityAudioTrack": "Music"}
INT32_MAX = 2 ** 31 - 1
SYNC_TOL_S = 0.05                              # rebuild_managed_master_guarded.py:56-58 (walking_music_swap.py:283)


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: args, maths, gates (exercised by test_p06_tail_extend.py)
# =====================================================================================================================

def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    if args.get("passage_label") != "Passage 6":
        r.append("PASSAGE_LABEL_NOT_P06: %r" % args.get("passage_label"))
    for field in ("song_s", "headroom_s", "max_delta_s"):
        v = args.get(field)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0:
            r.append("ARG_%s_INVALID: %r" % (field.upper(), v))
    if not isinstance(args.get("expected_old_len_ticks"), int) or args.get("expected_old_len_ticks") <= 0:
        r.append("EXPECTED_OLD_LEN_TICKS_INVALID: %r" % args.get("expected_old_len_ticks"))
    if not str(args.get("passage_guid") or "").strip():
        r.append("PASSAGE_GUID_MISSING")
    return r


def _ceil_div(a, b):
    return -((-a) // b)


def tail_plan(old_start, old_end, old_tail, tick_rate, fps_num, fps_den, song_s, headroom_s, max_delta_s):
    """New TailFrames so the Passage is >= song_s + headroom_s, delta rounded UP to a whole display frame. All ticks."""
    tick = fractions.Fraction(tick_rate)
    if tick <= 0 or tick.denominator != 1:
        raise PlanError("TICK_RATE_NOT_INTEGER: %r" % tick_rate)
    tpf = tick * int(fps_den) / int(fps_num)
    if tpf.denominator != 1 or tpf <= 0:
        raise PlanError("TICKS_PER_DISPLAY_FRAME_NOT_INTEGER: %s/%s at %s" % (fps_num, fps_den, tick_rate))
    tpf = int(tpf)
    old_len = int(old_end) - int(old_start)
    if old_len <= 0 or int(old_tail) < 0:
        raise PlanError("OLD_PASSAGE_INVALID: len %d tail %d" % (old_len, old_tail))
    target = fractions.Fraction(str(song_s)) + fractions.Fraction(str(headroom_s))
    target_ticks = int(math.ceil(target * tick))
    raw = target_ticks - old_len
    if raw <= 0:
        raise PlanError("ALREADY_FITS: P06 %d ticks >= target %d ticks; nothing to do" % (old_len, target_ticks))
    frames = _ceil_div(raw, tpf)
    delta = frames * tpf
    if fractions.Fraction(delta) / tick > fractions.Fraction(str(max_delta_s)):
        raise PlanError("DELTA_TOO_LARGE: %.4f s > max_delta_s %.4f" % (float(delta / tick), max_delta_s))
    new_tail = int(old_tail) + delta
    if new_tail > INT32_MAX or int(old_end) + delta > INT32_MAX:
        raise PlanError("FRAME_NUMBER_OVERFLOW")
    return {"old_start": int(old_start), "old_end": int(old_end), "old_len": old_len, "old_tail": int(old_tail),
            "target_ticks": target_ticks, "raw_delta_ticks": raw, "ticks_per_display_frame": tpf,
            "delta_frames": frames, "delta_ticks": delta, "new_tail": new_tail, "new_end": int(old_end) + delta,
            "new_len": old_len + delta, "delta_s": float(fractions.Fraction(delta) / tick),
            "old_len_s": float(fractions.Fraction(old_len) / tick),
            "new_len_s": float(fractions.Fraction(old_len + delta) / tick),
            "headroom_after_s": float(fractions.Fraction(old_len + delta) / tick - fractions.Fraction(str(song_s)))}


def compiled_length(lead, intervals, tail):
    """Compiler.cpp:254-288: lead + every interval but the last wing's + tail."""
    return int(lead) + sum(int(x) for x in list(intervals)[:-1]) + int(tail)


def wing_pass_frames(start, lead, intervals):
    """Absolute pass frames of each wing [decl Compiler.cpp:259-285]."""
    out, f = [], int(start) + int(lead)
    for i, iv in enumerate(intervals):
        out.append(f)
        if i < len(intervals) - 1:
            f += int(iv)
    return out


def consistency_refusals(plan_old_len, lead, intervals, tail, expected_old_len):
    r = []
    c = compiled_length(lead, intervals, tail)
    if c != plan_old_len:
        r.append("COMPILE_MODEL_MISMATCH: lead+intervals+tail = %d, compiled segment %d" % (c, plan_old_len))
    if plan_old_len != int(expected_old_len):
        r.append("P06_LENGTH_CHANGED_SINCE_DECISION: live %d ticks, args expected %d (re-decide the delta)" % (
            plan_old_len, expected_old_len))
    return r


def tail_speed(tail_ticks, tail_cm, tick_rate):
    return round(float(tail_cm) / (float(tail_ticks) / float(tick_rate)), 4) if tail_ticks > 0 else None


def beyond_end_refusals(p06, choreo, old_start, old_end, new_len):
    """Content that would become LIVE when the Passage runs past old_end. Returns (refusals, warnings).
    p06: {"channels": {name: [[tick_abs, value], ...]}, "pins_rel": [int], "wing_pin_frames": [tick_abs]}
    choreo: None or {"path", "start_offset", "playback_ticks": [s, e] (local), "keys": [[where, tick_local]],
             "sections": [{"where", "start", "end", "keyed"}] (local; None = open), "markers": [[label, tick_local]],
             "camera_cut": bool}"""
    r, w = [], []
    old_len = int(old_end) - int(old_start)
    for name, keys in sorted((p06.get("channels") or {}).items()):
        late = [k[0] for k in keys if int(k[0]) > int(old_end)]
        if late:
            r.append("P06_KEY_BEYOND_OLD_END: %s %d key(s) after tick %d: %s" % (name, len(late), old_end, late[:5]))
    late_pins = [p for p in p06.get("pins_rel") or [] if int(p) >= old_len]
    if late_pins:
        r.append("P06_PIN_BEYOND_OLD_END: relative %s >= %d" % (late_pins, old_len))
    late_wing = [p for p in p06.get("wing_pin_frames") or [] if int(p) > int(old_end)]
    if late_wing:
        r.append("P06_WING_PIN_BEYOND_OLD_END: %s" % late_wing)
    if not choreo:
        return r, w
    if choreo.get("camera_cut"):
        w.append("CHOREO_HAS_CAMERA_CUT: the builder does not nest it at all (SequenceBuilderLibrary.cpp:388-395)")
    local_end = int(choreo.get("start_offset", 0)) + old_len
    local_new_end = int(choreo.get("start_offset", 0)) + int(new_len)
    late_keys = [k for k in choreo.get("keys") or [] if int(k[1]) > local_end]
    if late_keys:
        r.append("CHOREO_KEY_BEYOND_OLD_END: %d key(s) after local %d: %s" % (len(late_keys), local_end, late_keys[:5]))
    for s in choreo.get("sections") or []:
        start, end = s.get("start"), s.get("end")
        if start is not None and int(start) >= local_end:
            r.append("CHOREO_SECTION_STARTS_AFTER_OLD_END: %s [%s, %s)" % (s.get("where"), start, end))
        elif end is None or int(end) > local_end:
            if s.get("keyed"):
                w.append("CHOREO_SECTION_HOLDS_PAST_OLD_END: %s [%s, %s) keyed, no key past the end: last values hold"
                         % (s.get("where"), start, end))
            else:
                r.append("CHOREO_UNKEYED_SECTION_PAST_OLD_END: %s [%s, %s) would start playing more content" % (
                    s.get("where"), start, end))
    for label, tick in choreo.get("markers") or []:
        if int(tick) > local_end:
            if str(label).startswith(SONG_MARKER_PREFIXES):
                w.append("CHOREO_SONG_MARKER_PAST_OLD_END: %r at %d (stale analysis; not a GO cue)" % (label, tick))
            else:
                r.append("CHOREO_MARKER_PAST_OLD_END: %r at %d (a GO marker would become live, "
                         "TransportController.cpp:931-940)" % (label, tick))
    pb = choreo.get("playback_ticks")
    if not pb or int(pb[1]) < local_new_end:
        r.append("CHOREO_SHORT: %s playback %r < new Passage end local %d; this tool never edits the Choreo" % (
            choreo.get("path"), pb, local_new_end))
    return r, w


def last_span_start(old_start, old_end, pins_rel, wing_pin_frames):
    """Start of the camera span that ends at the Passage end [decl MovieSceneInfinityPassageTrack.cpp:377-418]."""
    cands = [int(old_start)] + [int(old_start) + int(p) for p in pins_rel or [] if 0 < int(p) < int(old_end) - int(old_start)]
    cands += [int(f) for f in wing_pin_frames or [] if int(f) < int(old_end)]
    return max(cands)


def speed_renorm_refusals(speed_keys, span_start, new_end):
    """The last span [span_start, END) is renormalised over a longer END; only a constant SpeedMultiplier across
    [span_start, new_end] keeps every earlier frame's camera position identical [inf, see module doc]."""
    keys = sorted([int(t), float(v)] for t, v in speed_keys or [])
    if len(set(v for _t, v in keys)) <= 1:
        return []
    inside = [k for k in keys if int(span_start) < k[0] < int(new_end)]
    if inside:
        return ["SPEED_RENORMALISED: %d SpeedMultiplier key(s) with differing values inside the last span (%d, %d): "
                "the walk before the old end would change" % (len(inside), span_start, new_end)]
    left = [k for k in keys if k[0] <= int(span_start)]
    right = [k for k in keys if k[0] >= int(new_end)]
    if left and right and left[-1][1] != right[0][1]:
        return ["SPEED_RENORMALISED: SpeedMultiplier interpolates %r -> %r across the last span" % (left[-1], right[0])]
    return []


def artist_refusals(artist_rows, root_markers, old_end):
    """Unmanaged Master content is absolute and is NOT rippled [decl PassageResizeLibrary.cpp:116-200]. Anything at or
    after the old P06 end would strand. artist_rows: [{"owner","track","class","sections":[[s,e]] (None=open),
    "keys": [tick]}]; root_markers: [[label, tick]]."""
    r = []
    for row in artist_rows or []:
        hit_s = [s for s in row.get("sections") or [] if s[1] is None or int(s[1]) >= int(old_end)]
        hit_k = [k for k in row.get("keys") or [] if int(k) >= int(old_end)]
        if hit_s or hit_k:
            r.append("ARTIST_CONTENT_NOT_RIPPLED: %s %s (%s) sections %s keys %s at/after tick %d" % (
                row.get("owner"), row.get("track"), row.get("class"), hit_s[:3], hit_k[:5], old_end))
    for label, tick in root_markers or []:
        if int(tick) >= int(old_end):
            r.append("MASTER_MARKER_NOT_RIPPLED: %r at tick %d" % (label, tick))
    return r


def predict_segments(segments, label, delta):
    """[{label,start,end}] -> predicted rows with old/new start/end (DRY print and APPLY gate)."""
    idx = [i for i, s in enumerate(segments) if s["label"] == label]
    if len(idx) != 1:
        raise PlanError("SEGMENT_LABEL_COUNT: %s %d" % (label, len(idx)))
    out = []
    for i, s in enumerate(segments):
        if i < idx[0]:
            ns, ne = s["start"], s["end"]
        elif i == idx[0]:
            ns, ne = s["start"], s["end"] + delta
        else:
            ns, ne = s["start"] + delta, s["end"] + delta
        out.append({"label": s["label"], "start": int(s["start"]), "end": int(s["end"]), "new_start": int(ns),
                    "new_end": int(ne), "shift": int(ns - s["start"])})
    return out


def segment_shift_gate(before, after, label, delta):
    """Earlier segments tick-identical; P06 start same, end +delta; later segments both ends +delta. Same order."""
    out = []
    if [s["label"] for s in before] != [s["label"] for s in after]:
        return ["SEGMENT_ORDER_CHANGED: %r -> %r" % ([s["label"] for s in before], [s["label"] for s in after])]
    for want, got in zip(predict_segments(before, label, delta), after):
        if (want["new_start"], want["new_end"]) != (int(got["start"]), int(got["end"])):
            out.append("SEGMENT_MOVED_WRONG: %s want [%d, %d) got [%d, %d)" % (
                got["label"], want["new_start"], want["new_end"], got["start"], got["end"]))
    return out


MASTER_ROUNDING_TICKS = 4


def managed_shift_gate(before, after, p06_guid, p06_start, old_end, delta):
    """Managed Master sections {"Kind:GUID": [start, end]} plus "Playback:master". P06 blocks (any kind keyed by the
    P06 GUID): start same, end +delta. Blocks starting at/after old_end: +delta. Blocks ending at/before P06's start:
    identical. Anything else (straddling P06) is a failure."""
    out = []
    if sorted(before) != sorted(after):
        out.append("MANAGED_SET_CHANGED: gone %r new %r" % (sorted(set(before) - set(after)),
                                                           sorted(set(after) - set(before))))
    for key in sorted(set(before) & set(after)):
        b, a = [int(x) for x in before[key]], [int(x) for x in after[key]]
        if key == "Playback:master" or key.endswith(":" + p06_guid):
            want = [b[0], b[1] + delta]
        elif b[0] >= int(old_end) - MASTER_ROUNDING_TICKS:
            want = [b[0] + delta, b[1] + delta]
        elif b[1] <= int(p06_start) + MASTER_ROUNDING_TICKS:
            want = b
        else:
            out.append("MANAGED_STRADDLES_P06: %s %r" % (key, b))
            continue
        # Master section boundaries are rounded by the rebuild: measured 6 Oct, P06 end was 2 ticks SHORT of the compiled
        # segment before and 2 ticks LONG after (0.08 ms each). Allow MASTER_ROUNDING_TICKS per boundary; segments stay exact.
        if any(abs(x - y) > MASTER_ROUNDING_TICKS for x, y in zip(a, want)):
            out.append("MANAGED_MOVED_WRONG: %s want %r got %r" % (key, want, a))
    return out


def keys_gate(before, after, old_end, delta):
    """Passage channel keys {passage_guid: {"start": tick, "channels": {name: [[tick, value]]}, "pins_rel": [...],
    "wing_pins": [...]}}. Passages starting at/after old_end must carry every key +delta (patch K MoveSection); every
    other Passage (P06 included) must be bit-identical. Relative pins and wing pins identical everywhere."""
    out = []
    if sorted(before) != sorted(after):
        return ["PASSAGE_SECTION_SET_CHANGED: %r -> %r" % (sorted(before), sorted(after))]
    for guid in sorted(before):
        b, a = before[guid], after[guid]
        shift = delta if int(b["start"]) >= int(old_end) else 0
        want = {n: [[int(t) + shift, v] for t, v in ks] for n, ks in b["channels"].items()}
        got = {n: [[int(t), v] for t, v in ks] for n, ks in a["channels"].items()}
        if want != got:
            bad = sorted(n for n in set(want) | set(got) if want.get(n) != got.get(n))
            out.append("PASSAGE_KEYS_MOVED: %s channels %s (expected shift %d)" % (guid, bad, shift))
        if list(b.get("pins_rel") or []) != list(a.get("pins_rel") or []):
            out.append("PASSAGE_PINS_CHANGED: %s %r -> %r" % (guid, b.get("pins_rel"), a.get("pins_rel")))
        if sorted(b.get("wing_pins") or []) != sorted(a.get("wing_pins") or []):
            out.append("PASSAGE_WING_PINS_CHANGED: %s" % guid)
    return out


def sync_gate(show_rows, master_rows, tol_s=SYNC_TOL_S):
    """walking_music_swap.py:283-298 verbatim logic: the Master must already match the Show."""
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
        if state.get("record_exists"):
            r.append("RECORD_EXISTS: %s (REVERT it first)" % RECORD_NAME)
        if not str(state.get("decided_by") or "").strip():
            r.append("NOT_DECIDED: args decided_by is empty")
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def write_tail_checked(adapter, new_tail, tail_cm_before):
    """Write TailFrames; judge by re-reading (setters lie, memory). TailDistanceCm must be unchanged."""
    adapter.write_tail(int(new_tail))
    frames, cm = adapter.read_tail()
    out = []
    if frames != int(new_tail):
        out.append("READBACK_TAIL_FRAMES: %r != %r" % (frames, new_tail))
    if cm != tail_cm_before:
        out.append("READBACK_TAIL_DISTANCE_CHANGED: %r != %r" % (cm, tail_cm_before))
    return out


def drift_refusals(live, record):
    """REVERT precondition: the live state is exactly what APPLY left. live/record['after']: tail_frames,
    tail_distance_cm, segments, managed."""
    out = []
    after = record["after"]
    for field in ("tail_frames", "tail_distance_cm", "segments", "managed"):
        if live.get(field) != after.get(field):
            out.append("STATE_DRIFTED_SINCE_APPLY: %s" % field)
    return out


def revert_exact_gate(live, record):
    """REVERT postcondition: the live state is exactly the record's BEFORE (tick-exact), keys included."""
    out = []
    before = record["before"]
    for field in ("tail_frames", "tail_distance_cm", "segments", "managed", "keys"):
        if live.get(field) != before.get(field):
            out.append("REVERT_NOT_EXACT: %s" % field)
    return out


def write_record_exclusive(path, data):
    """Create-only, fsynced BEFORE any mutation [prec walking_music_swap.py:476-482]."""
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


def unwrap(result, count):
    """UE Python returns out-params as a tuple, or None when a bool UFUNCTION returns false
    [prec Saved/CodexCameraPilot/verify_camera_pilot_readonly.py:25-33]."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    if count == 1 and not isinstance(result, tuple):
        return (result,)
    return result


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


def _content_file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _ticks(seconds, tick):
    return int(round(float(seconds) * tick))


class _LiveShow(object):
    """TailFrames / TailDistanceCm of one Passage row (same interface as the harness fake)."""

    def __init__(self, show, index):
        self.show, self.index = show, index

    def read_tail(self):
        p = list(self.show.get_editor_property("passage_settings"))[self.index]
        return int(p.get_editor_property("tail_frames").value), float(p.get_editor_property("tail_distance_cm"))

    def write_tail(self, frames):
        ps = list(self.show.get_editor_property("passage_settings"))
        p = ps[self.index]
        p.set_editor_property("tail_frames", unreal.FrameNumber(int(frames)))
        ps[self.index] = p
        self.show.set_editor_property("passage_settings", ps)    # struct arrays are copies [prec passage_slow_walk.py:392-399]


def _segments(show):
    """Compiled segments via a transient transport [prec walking_music_swap.py:657-662]; ticks."""
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    return [{"label": str(s.get_editor_property("label")), "start": int(s.get_editor_property("start_frame").value),
             "end": int(s.get_editor_property("end_frame").value)} for s in tr.get_editor_property("segments")]


def _p06(show, args):
    """Index, settings facts and wing timing of Passage 6 (read-only)."""
    psets = list(show.get_editor_property("passage_settings"))
    hits = [i for i, p in enumerate(psets) if str(p.get_editor_property("label")) == args["passage_label"]]
    if len(hits) != 1:
        raise PlanError("P06_LABEL_COUNT: %d" % len(hits))
    p = psets[hits[0]]
    guid = _guid(p.get_editor_property("passage_guid"))
    if guid != args["passage_guid"]:
        raise PlanError("P06_GUID: live %s != args %s" % (guid, args["passage_guid"]))
    cues = list(show.get_editor_property("cues"))
    by_guid = {_guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
    first = by_guid.get(_guid(p.get_editor_property("first_cue_guid")))
    last = by_guid.get(_guid(p.get_editor_property("last_cue_guid")))
    if first is None or last is None or last < first:
        raise PlanError("P06_CUE_RANGE_UNRESOLVED")
    intervals, wing_cues = [], []
    for i in range(first, last + 1):
        c = cues[i]
        if c.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR or not c.get_editor_property("enabled"):
            raise PlanError("P06_CUE_%d_NOT_ENABLED_WINGPAIR" % i)    # passage_slow_walk.py:197-201
        intervals.append(int(c.get_editor_property("wing_pair").get_editor_property("interval_to_next").value))
        wing_cues.append(_guid(c.get_editor_property("cue_guid")))
    if last + 1 < len(cues):
        nxt = cues[last + 1]
        if nxt.get_editor_property("enabled") and nxt.get_editor_property("type") == unreal.InfinityCueType.WING_PAIR:
            raise PlanError("P06_RANGE_NOT_MAXIMAL: the cue after LastCue is an enabled WingPair (compiler would join it)")
    choreo = p.get_editor_property("choreography")
    if choreo is not None and hasattr(choreo, "load_synchronous"):
        choreo = choreo.load_synchronous()
    return {"index": hits[0], "guid": guid, "lead": int(p.get_editor_property("lead_in_frames").value),
            "tail": int(p.get_editor_property("tail_frames").value),
            "lead_cm": float(p.get_editor_property("lead_in_distance_cm")),
            "tail_cm": float(p.get_editor_property("tail_distance_cm")), "intervals": intervals,
            "wing_cues": wing_cues, "choreo": choreo}


def _channel_keys(section):
    out = {}
    for ch in section.get_all_channels():
        try:
            keys = ch.get_keys()
        except Exception:  # noqa: BLE001 - a channel type without keys
            continue
        rows = []
        for k in keys:
            t = int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value)  # hangar_heave.py:763
            try:
                v = float(k.get_value())
            except Exception:  # noqa: BLE001 - non-scalar key: compare by time only
                v = None
            rows.append([t, v])
        if rows:
            out[str(ch.get_editor_property("channel_name"))] = sorted(rows, key=lambda r: r[0])
    return out


def _all_tracks(seq):
    """Root, binding and camera-cut tracks, deduplicated by path."""
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
    """managed {"Kind:GUID": [s, e]} + "Playback:master"; passage keys/pins by GUID; artist rows; root markers."""
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


def _choreo_facts(choreo, master, p06_guid, show_tick):
    """P06 Choreo content in Choreo-local ticks (0 = Passage start [decl SequenceBuilderLibrary.cpp:367-369])."""
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
            if _guid(sec.get_editor_property("block_guid")) != p06_guid:
                continue
            try:
                prm = sec.get_editor_property("parameters")
                facts["start_offset"] = int(prm.get_editor_property("start_frame_offset").value)
                facts["time_scale"] = str(prm.get_editor_property("time_scale"))
            except Exception as exc:  # noqa: BLE001 - reported
                facts["time_scale"] = "unreadable: %r" % exc
    return facts


def _label_rows(master, segments, tick, guid_by_label):
    """Show vs Master rows in seconds [prec walking_music_swap.py:708-731, EXACT Scene-track type]."""
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
    res = unwrap(unreal.InfinityStageSequenceBuilderLibrary.check_scene_handoffs(show, world), 2)  # read-only [decl .h:17-23]
    if res is None:
        return None, "check_scene_handoffs returned false"
    return sorted(_guid(g) for g in res[0]), str(res[1])


def _snapshot(show, master, args):
    """Everything the gates compare, as plain data."""
    tick = _rate(show.get_editor_property("tick_resolution"))
    p = _p06(show, args)
    managed, keys, artist, markers, dup = _master_state(master, _guid(show.get_editor_property("show_guid")), tick)
    return {"tick": tick, "p06": p, "segments": _segments(show), "managed": managed, "keys": keys, "artist": artist,
            "markers": markers, "dup": dup, "tail_frames": p["tail"], "tail_distance_cm": p["tail_cm"]}


def _plain(snap):
    return {"tail_frames": snap["tail_frames"], "tail_distance_cm": snap["tail_distance_cm"],
            "segments": snap["segments"], "managed": snap["managed"], "keys": snap["keys"]}


def _gather(args):
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    snap = _snapshot(show, master, args)
    tick, p = snap["tick"], snap["p06"]
    dr = show.get_editor_property("display_rate")
    refusals, warnings = [], []
    if snap["dup"]:
        refusals.append("MANAGED_BLOCK_DUPLICATED: %s" % snap["dup"])
    segs = [s for s in snap["segments"] if s["label"] == args["passage_label"]]
    if len(segs) != 1:
        raise PlanError("P06_SEGMENT_COUNT: %d" % len(segs))
    seg = segs[0]
    plan = tail_plan(seg["start"], seg["end"], p["tail"], int(round(tick)), dr.numerator, dr.denominator,
                     args["song_s"], args["headroom_s"], args["max_delta_s"])
    refusals += consistency_refusals(plan["old_len"], p["lead"], p["intervals"], p["tail"], args["expected_old_len_ticks"])
    if p["tail"] == 0 and p["tail_cm"] != 0.0:
        refusals.append("TAIL_ALREADY_INVALID: TailFrames 0 with TailDistanceCm %r (Compiler.cpp:294-297)" % p["tail_cm"])
    passes = wing_pass_frames(seg["start"], p["lead"], p["intervals"])
    pkeys = snap["keys"].get(p["guid"])
    if pkeys is None:
        refusals.append("P06_MASTER_SECTION_MISSING")
        pkeys = {"start": seg["start"], "channels": {}, "pins_rel": [], "wing_pins": []}
    wing_pin_frames = [passes[p["wing_cues"].index(g)] for g in pkeys["wing_pins"] if g in p["wing_cues"]]
    choreo = _choreo_facts(p["choreo"], master, p["guid"], tick)
    if choreo and choreo.get("start_offset"):
        warnings.append("CHOREO_START_OFFSET: %d ticks (local end computed with it)" % choreo["start_offset"])
    if choreo and choreo.get("time_scale") and "1.0" not in str(choreo["time_scale"]):
        warnings.append("CHOREO_TIME_SCALE_UNVERIFIED: %s" % choreo["time_scale"])
    r, w = beyond_end_refusals({"channels": pkeys["channels"], "pins_rel": pkeys["pins_rel"],
                                "wing_pin_frames": wing_pin_frames}, choreo, seg["start"], seg["end"], plan["new_len"])
    refusals += r
    warnings += w
    span = last_span_start(seg["start"], seg["end"], pkeys["pins_rel"], wing_pin_frames)
    refusals += speed_renorm_refusals(pkeys["channels"].get("Camera.SpeedMultiplier", []), span, plan["new_end"])
    refusals += artist_refusals(snap["artist"], snap["markers"], seg["end"])
    show_rows, master_rows = _label_rows(master, snap["segments"], tick, _guid_by_label(show))
    refusals += sync_gate(show_rows, master_rows)
    stale, handoff_report = _handoffs(show)
    if stale is None:
        warnings.append("HANDOFF_CHECK_FAILED: %s (APPLY compares before/after only if it runs)" % handoff_report)
    pred = predict_segments(snap["segments"], args["passage_label"], plan["delta_ticks"])
    music = {k: v for k, v in snap["managed"].items() if k == "Music:" + p["guid"]}
    choreo_section = snap["managed"].get("Choreo:" + p["guid"])
    report = {"plan": plan, "tick_rate": tick, "display_rate": [dr.numerator, dr.denominator],
              "p06": {k: v for k, v in p.items() if k != "choreo"}, "wing_pass_frames": passes,
              "last_pass_frame": passes[-1] if passes else None,
              "tail_speed_cm_s": {"old": tail_speed(p["tail"], p["tail_cm"], tick),
                                  "new": tail_speed(plan["new_tail"], p["tail_cm"], tick)},
              "p06_keys": pkeys, "last_span_start": span, "choreo": choreo,
              "choreo_master_section": {"old": choreo_section,
                                        "new": [choreo_section[0], choreo_section[1] + plan["delta_ticks"]]
                                        if choreo_section else None},
              "p06_music_section": music, "segments_predicted": pred, "artist_content": snap["artist"],
              "master_markers": snap["markers"], "handoff_stale_before": stale, "handoff_report": handoff_report,
              "refusals": refusals, "warnings": warnings}
    return report, snap, show, master


def _backup(run, suffix, paths):
    folder = os.path.join(_project(), "Backups", "PreP06TailExtend%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path in paths:
        src = _content_file(path)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _rebuild(show, master):
    res = unwrap(unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master), 1)
    return (False, "rebuild returned false/None") if res is None else (True, str(res[0]))


def _log_rows(run, report):
    plan = report["plan"]
    unreal.log("%s_PLAN|run=%s|old_len=%d(%.4fs)|tail=%d->%d|delta=%d ticks=%d frames=%.4fs|new_len=%d(%.4fs)|"
               "tail_cm=%.3f|tail_speed=%s->%s cm/s|fps=%s" % (
                   MARK, run, plan["old_len"], plan["old_len_s"], plan["old_tail"], plan["new_tail"],
                   plan["delta_ticks"], plan["delta_frames"], plan["delta_s"], plan["new_len"], plan["new_len_s"],
                   report["p06"]["tail_cm"], report["tail_speed_cm_s"]["old"], report["tail_speed_cm_s"]["new"],
                   "%d/%d" % tuple(report["display_rate"])))
    for row in report["segments_predicted"]:
        unreal.log("%s_SEGMENT|run=%s|%s|%d->%d|end %d->%d|shift=%d" % (
            MARK, run, row["label"], row["start"], row["new_start"], row["end"], row["new_end"], row["shift"]))
    c = report["choreo"] or {}
    unreal.log("%s_CHOREO|run=%s|asset=%s|playback_local=%s|master_section=%s->%s|offset=%s|scale=%s|keys=%d|sections=%d|"
               "markers=%d" % (MARK, run, c.get("path"), c.get("playback_ticks"), report["choreo_master_section"]["old"],
                               report["choreo_master_section"]["new"], c.get("start_offset"), c.get("time_scale"),
                               len(c.get("keys") or []), len(c.get("sections") or []), len(c.get("markers") or [])))
    for text in report["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, text))
    for text in report["warnings"]:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, text))


def run_dry(args, run):
    report, _snap, _s, _m = _gather(args)
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(dict(report, tool=TOOL, run=run, mode="DRY", args=args, apply_ready=not report["refusals"]),
                  handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
    _log_rows(run, report)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|delta_s=%.4f|p06_s=%.4f|report=%s" % (
        MARK, run, int(not report["refusals"]), len(report["refusals"]), len(report["warnings"]),
        report["plan"]["delta_s"], report["plan"]["new_len_s"], out))


def _post_gates(args, before, after, plan, p06_guid, stale_before, show):
    f = []
    f += segment_shift_gate(before["segments"], after["segments"], args["passage_label"], plan["delta_ticks"])
    f += managed_shift_gate(before["managed"], after["managed"], p06_guid, plan["old_start"], plan["old_end"],
                            plan["delta_ticks"])
    f += keys_gate(before["keys"], after["keys"], plan["old_end"], plan["delta_ticks"])
    if after["dup"]:
        f.append("MANAGED_BLOCK_DUPLICATED_AFTER: %s" % after["dup"])
    if after["artist"] != before["artist"] or after["markers"] != before["markers"]:
        f.append("ARTIST_CONTENT_OR_MARKERS_CHANGED")
    if stale_before is not None:
        stale_after, rep = _handoffs(show)
        f += ["HANDOFF_CHECK_FAILED_AFTER: %s" % rep] if stale_after is None else handoff_gate(stale_before, stale_after)
    return f


def run_apply(args, run):
    report, before, show, master = _gather(args)
    if report["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(report["refusals"]))
    plan, p = report["plan"], before["p06"]
    record_path = os.path.join(_here(), RECORD_NAME)
    backup = _backup(run, "", [SHOW_PATH, MASTER_PATH])
    unreal.log("%s_BACKUP_OK|run=%s|backup=%s" % (MARK, run, backup))
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "backup": backup, "args": args,
              "decided_by": args.get("decided_by"), "applied": False, "passage_guid": p["guid"],
              "passage_index": p["index"], "plan": plan,
              "written": datetime.datetime.now().isoformat(timespec="seconds"), "before": _plain(before)}
    write_record_exclusive(record_path, record)                  # BEFORE any change
    adapter = _LiveShow(show, p["index"])
    show.modify()
    failures = []
    try:
        failures += write_tail_checked(adapter, plan["new_tail"], p["tail_cm"])
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        failures.append("WRITE_RAISED: %r" % exc)
    if not failures:
        ok, text = _rebuild(show, master)
        record["rebuild_report"] = text
        if not ok:
            failures.append("REBUILD_FAILED: %s" % text)
    if not failures:
        after = _snapshot(show, master, args)
        failures += _post_gates(args, before, after, plan, p["guid"], report["handoff_stale_before"], show)
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
    show2, master2 = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    final = _plain(_snapshot(show2, master2, args))
    dd = ["POST_SAVE_%s_DIFFERS" % k for k in ("tail_frames", "tail_distance_cm", "segments", "managed", "keys")
          if final[k] != record["after"][k]]
    if _census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if dd:
        record["post_save_readback_failed"] = dd
        update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd, backup))
    unreal.log("%s_APPLY_OK|run=%s|delta_s=%.4f|p06_s=%.4f|delta_ticks=%d|tail=%d->%d|tail_cm=%.3f|backup=%s|record=%s|"
               "decided_by=%s" % (MARK, run, plan["delta_s"], plan["new_len_s"], plan["delta_ticks"], plan["old_tail"],
                                  plan["new_tail"], p["tail_cm"], backup, record_path, args.get("decided_by")))


def run_revert(args, run):
    record_path = os.path.join(_here(), RECORD_NAME)
    with open(record_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or not record.get("after"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    snap = _snapshot(show, master, args)
    if snap["p06"]["index"] != record["passage_index"] or snap["p06"]["guid"] != record["passage_guid"]:
        _stop(run, "REVERT_PASSAGE_ROW_MOVED")
    drift = drift_refusals(_plain(snap), record)
    if drift:
        _stop(run, "%r (restore from %s instead)" % (drift, record["backup"]))
    show_rows, master_rows = _label_rows(master, snap["segments"], snap["tick"], _guid_by_label(show))
    stale = sync_gate(show_rows, master_rows)
    if stale:
        _stop(run, "MASTER_NOT_IN_SYNC_BEFORE_REVERT|%r" % stale[:6])
    backup = _backup(run, "Revert", [SHOW_PATH, MASTER_PATH])
    show.modify()
    errs = write_tail_checked(_LiveShow(show, record["passage_index"]), record["before"]["tail_frames"],
                              record["before"]["tail_distance_cm"])
    if not errs:
        ok, text = _rebuild(show, master)
        if not ok:
            errs.append("REBUILD_FAILED: %s" % text)
        else:
            errs += revert_exact_gate(_plain(_snapshot(show, master, args)), record)
    errs += census_gate(_census(), [SHOW_PATH, MASTER_PATH])
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8], record["backup"]))
    for path in (SHOW_PATH, MASTER_PATH):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % path)
    final = revert_exact_gate(_plain(_snapshot(unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH), args)),
                              record)
    if _census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final, record["backup"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|tail=%d|p06_s=%.4f|backup=%s|record=%s" % (
        MARK, run, record["before"]["tail_frames"], record["plan"]["old_len_s"], backup, archived))


def main():
    g = globals()
    args = g.get("P06TAIL_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P06TAIL-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    rp = os.path.join(_here(), RECORD_NAME)
    applied = False
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as handle:
            applied = bool(json.load(handle).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census(), "record_exists": os.path.exists(rp), "record_applied": applied,
             "decided_by": args.get("decided_by")}
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
