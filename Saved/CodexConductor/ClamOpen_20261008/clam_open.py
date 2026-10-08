"""CLAM OPEN (Gary 8 Oct, his words: "the slow opening of the upper part of the clam").  Offline-written 8 Oct, NOT RUN.

Keys the hinge of "S3 PearlClam Lid" (attached to "S3 PearlClam") in LS_DevScene_03 so the lid opens slowly after the
clam has risen.  Writes ONLY the Rotation.X (ROLL) channel of the existing 3D-transform section on the binding
"S3 Hangar Float Hold: S3 PearlClam Lid".  Saves ONLY LS_DevScene_03; the level is never saved and must not need saving.

Tiers: [decl] declaration-proven (header / source / record we can read, cited), [prec] an in-repo call that ran (cited),
[meas] intervention + read-back, [inf] inferred (why stated).

FACTS
  * Hinge = the lid's RELATIVE roll.  Open roll = -front_sign * deg, front_sign = +1 for this lid -> -80 deg at 80
    [decl S3Millstone/s3_props_ue.py:1532-1540 lid_front_sign/lid_open_roll, :241 lid_open_deg 80;
     S3Millstone/s3_pearlclam_apply_record.json:434-442 plan.lid front_sign 1, open_relative_rotation_rpy [-80,0,0],
     tip_closed_z 170 -> tip_open_z 250, keyed false].
  * Rotation.X of a transform section is ROLL [decl Plugins/InfinityStage/Source/InfinityStage/Private/
    InfinityStageArrival.cpp:88 "rotation XYZ (roll, pitch, yaw)"].  Channel names carry suffixes (Rotation.X_84 in
    probe_s3_clam_anim.json:85, Rotation.X_196 in s3_retime_record.json) -> matched by BASE name (suffix stripped).
  * LS_DevScene_03 runs at 24 fps [meas probe_s3_clam_anim.json:4].
  * The lid's 9 transform channels carry a constant 2-key pattern.  Originally at 3593/4170 [meas probe_s3_clam_anim.json];
    moved to 1080/1440 by S3RETIME-20261008-020659 [meas s3_retime_record.json moves "clam|S3 Hangar Float Hold: S3
    PearlClam Lid|Transform|..."; S3RETIME_APPLY_OK in Saved/Logs/PussStage.log].  The guard takes the expected frames
    from args (default [1080, 1440]); expected_key_frames null accepts any 2-key constant pattern and records it.

KEYS (pure plan_keys): keep the two existing keys; add LINEAR keys sampled every sample_step frames from an ease curve
(cubic-in-out = smoothstep 3u^2-2u^3, or smootherstep 6u^5-15u^4+10u^3, or linear) from open_start (0 deg) to open_end
(-open_deg), optional 3-6 deg "crack" then a pause first, optional explicit closed key at hold_closed_until_frame, and
(hold_open_to_end) one key at the Scene playback end holding the open angle.  WHY SAMPLED LINEAR, NOT AUTO/CUBIC
TANGENTS: LINEAR add_key + exact read-back is what the project's tools have RUN [prec s3_drama_lights.py:153-158
(S3DRAMA_APPLY_OK 01:49:05 in PussStage.log)].  AUTO keys were added by the same run (shimmer, :172) but never
evaluated; UE's auto-tangent rule lives in the absent private .cpp, so the overshoot of a 2-key cubic is unprovable
[inf].  A LINEAR curve between keys is monotone by construction, and the evaluated value is checkable offline.

TIME/VALUE APIs (all on the double channel of a transform section):
  get_keys / add_key(FrameNumber, value, time_unit=DISPLAY_RATE, interpolation=LINEAR) / remove_key / key.get_time /
  get_value [prec s3_drama_lights.py:153-158, :184-187; decl MovieSceneScriptingDouble.h:245,254,265 (SequencerScripting
  Private/KeysAndChannels)];  get_interpolation_mode / get_tangent_mode / get_arrive_tangent / get_leave_tangent /
  get_tangent_weight_mode / weights  [decl MovieSceneScriptingDouble.h:72-210; read pattern prec klara_reveal.py:1728-1729
  (ran)];  the tangent SETTERS used only by REVERT [decl MovieSceneScriptingDouble.h:104,126,149,172,195,218; precedent
  hangar_heave.py:788-802 was NEVER RUN -> behaviour inf];  get_pre/post_infinity_extrapolation [decl
  MovieSceneScriptingDouble.h:316,349; read prec klara_hookin_s6.py:670].
  evaluate_keys(range, frame_rate) on compute_effective_range() [decl MovieSceneScriptingDouble.h:296-309; body
  Public/MovieSceneScriptingChannel.h:218-243: evaluates every display frame of the range, from its inclusive start to
  its exclusive end].  NOT USED by any project tool before -> [inf] that compute_effective_range() spans exactly the
  key extents (Channel->ComputeEffectiveRange is in the private .cpp) and that the Python marshalling works.  The tool
  checks the length of what comes back and that sample 0 equals the first key, and DRY probes the call on the
  UNMODIFIED channel first.  It never evaluates through the Master (memory: opening/scrubbing the Master dirties the map).

GUARDS (APPLY): args valid; no PIE; editor world is L_InfinityStage_V1VerticalSlice; NO Level Sequence editor open
[prec s3_retime.py:44, atf_hangar_timing_apply.py:114, close_sequencer.py closes it]; census clean (drama pattern
s3_drama_lights.py:84-89); 24 fps; playback end as expected; binding name exactly once; it resolves
(locate_bound_objects, prec s4_hangar_hold.py:978) to exactly ONE actor labelled "S3 PearlClam Lid"; exactly one
transform track, one section, 9 channels; the 2-key constant pattern with roll 0; no record already present; the eval
probe works (require_eval).  RECORD FIRST: every key field of all 9 channels + defaults + extrapolation, written
exclusive + fsync + read back, then Backups/PreClamOpen-<run>/LS_DevScene_03.uasset (sha256 checked).  After the
writes: read back every channel (the 8 others bit-identical to the record, roll = original + planned), evaluate the
roll curve and compare every frame to the planned piecewise-linear curve, census must be exactly the Scene, save the
Scene only, census must be 0+0, read back again.  Only then CLAMOPEN_APPLY_OK.

AT 4560 AND AFTER: the guard proves Rotation.X has no key past the rise (exactly 2 keys), the section is unbounded
[meas probe_s3_clam_anim.json range [null, null]], so the lid stays open to the end: by the explicit hold key at the
playback end (hold_open_to_end, default) and by constant post-extrapolation [inf; recorded per channel].

TRAPS
  * FLOAT-HOLD RE-RUN (s4_hangar_hold.py, hold FLOAT, scene 3, record s3_hangar_float_hold_record.json, run
    S3FLOATHOLD-20261007-184155 applied).  That tool CREATED this binding (record created_bindings guid
    0A71635C4DCC686A899ECD8B873FA60B "S3 PearlClam Lid") and owns only its Visibility track.  It never writes or removes
    keys on the Transform track [decl s4_hangar_hold.py:1126-1140 adds only the target's class (Visibility for the lid,
    record rows) and sets a channel DEFAULT, no keys; :1205-1209 removes only _our_nt_tracks of that class].  BUT its
    REVERT removes the Visibility track and then REFUSES to remove the binding because the Transform track (Gary's keys,
    and now the opening) is still on it: CREATED_BINDING_NOT_EMPTY [decl s4_hangar_hold.py:1215-1216] -> FAILED with
    the Visibility track already removed in memory ("NOTHING SAVED; Don't-Save restart").  Never "fix" that by removing
    the binding: it carries the rise and the opening.  A float-hold re-APPLY refuses while its record exists
    (RECORD_EXISTS, :1067-1068).
  * S3RETIME has no in-editor REVERT; its revert is a file restore of Backups/PreS3Retime-<run> [decl s3_retime.py:177-179].
    That restore would silently wipe these opening keys (and everything else saved to LS_DevScene_03 since 02:07).
    REVERT CLAMOPEN first.
  * Adding keys next to an AUTO-tangent key may recompute that key's tangents [inf]; the original 2 keys' time, value and
    interpolation are asserted unchanged, tangent changes are reported (apply) and restored + asserted (REVERT).

Args clam_open_args.json; confirm "APPLY CLAMOPEN" / "REVERT CLAMOPEN"; run from args or fresh CLAMOPEN-<stamp>.
Record ClamOpen_20261008/clam_open_record.json.  Markers CLAMOPEN_<MODE>_OK|run=<id>|... / CLAMOPEN_FAILED|run=<id>|<reason>.
No UE object at module level (memory puss-mcp-python-crashes-the-editor): every unreal access is inside a function.
"""
import datetime
import hashlib
import json
import os
import re
import shutil

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/ClamOpen_20261008/"
ARGS_FILE = "clam_open_args.json"
RECORD_FILE = "clam_open_record.json"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
SCENE_FILE = "Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
WORLD_NAME = "L_InfinityStage_V1VerticalSlice"
BINDING = "S3 Hangar Float Hold: S3 PearlClam Lid"
LID_LABEL = "S3 PearlClam Lid"
TRANSFORM_TRACK = "MovieScene3DTransformTrack"
FRONT_SIGN = 1                     # s3_pearlclam_apply_record.json plan.lid.front_sign
ROLL = "Rotation.X"
CHANNELS = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
            "Scale.X", "Scale.Y", "Scale.Z")
EASES = ("cubic-in-out", "smootherstep", "linear")
VALUE_TOL = 1e-6                   # read-back of a written double
READBACK_TOL = 1e-4               # channel storage rounds (measured 8 Oct: |err| up to ~2e-6 deg on 1620-1656) - 1e-4 deg is invisible
EVAL_TOL = 1e-3                    # deg, evaluated curve vs plan
NS = "NOTHING SAVED; Don't-Save restart"
RUN = {"run": "?"}                 # plain str in a dict (no UE wrapper at module level)

DEFAULTS = {
    "mode": "DRY", "confirm": "", "run": None,
    "open_start_frame": 1446, "open_end_frame": 1746, "open_deg": 80.0, "ease": "cubic-in-out", "sample_step": 6,
    "hold_closed_until_frame": None,
    "crack": {"enabled": False, "deg": 4.0, "start_frame": None, "duration_frames": 36, "pause_frames": 60},
    "hold_open_to_end": True, "expected_key_frames": [1080, 1440], "expected_fps": 24.0,
    "expected_playback_end": 6240, "require_eval": True,
}


class Fail(Exception):
    pass


# =====================================================================================================================
# Pure (offline-testable)
# =====================================================================================================================

def channel_base(name):
    """'Rotation.X_84' -> 'Rotation.X'."""
    return re.sub(r"_\d+$", "", str(name))


def fresh_run(now=None):
    return "CLAMOPEN-" + (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")


def merged_args(raw):
    a = json.loads(json.dumps(DEFAULTS))
    for k, v in (raw or {}).items():
        if k == "crack" and isinstance(v, dict):
            a["crack"].update(v)
        else:
            a[k] = v
    return a


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def crack_frames(a):
    """-> (crack_start, crack_end, main_start) or None when the crack is off."""
    c = a["crack"]
    if not c.get("enabled"):
        return None
    s = int(c["start_frame"]) if c.get("start_frame") is not None else int(a["open_start_frame"])
    e = s + int(c["duration_frames"])
    return s, e, e + int(c["pause_frames"])


def validate_args(a):
    """-> list of named errors (empty = valid)."""
    e = []
    mode = a.get("mode")
    if mode not in ("DRY", "APPLY", "REVERT"):
        e.append("MODE|%s" % mode)
    elif mode in ("APPLY", "REVERT") and a.get("confirm") != "%s CLAMOPEN" % mode:
        e.append("CONFIRM|%s" % a.get("confirm"))
    s, f = a.get("open_start_frame"), a.get("open_end_frame")
    if not (_is_int(s) and _is_int(f)):
        e.append("FRAMES_NOT_INT|%s|%s" % (s, f))
    elif f <= s:
        e.append("END_NOT_AFTER_START|%s|%s" % (s, f))
    d = a.get("open_deg")
    if not _is_num(d) or not (10.0 <= float(d) <= 100.0):
        e.append("OPEN_DEG_RANGE|%s (10..100)" % d)
    if a.get("ease") not in EASES:
        e.append("EASE|%s" % a.get("ease"))
    st = a.get("sample_step")
    if not _is_int(st) or not (1 <= st <= 48):
        e.append("SAMPLE_STEP|%s (1..48)" % st)
    h = a.get("hold_closed_until_frame")
    if h is not None and (not _is_int(h) or (_is_int(s) and h > s)):
        e.append("HOLD_CLOSED_AFTER_START|%s" % h)
    c = a.get("crack") or {}
    if c.get("enabled"):
        if not _is_num(c.get("deg")) or not (3.0 <= float(c["deg"]) <= 6.0):
            e.append("CRACK_DEG|%s (3..6)" % c.get("deg"))
        elif _is_num(d) and float(c["deg"]) >= float(d):
            e.append("CRACK_GE_OPEN")
        if not (_is_int(c.get("duration_frames")) and c["duration_frames"] > 0 and _is_int(c.get("pause_frames"))
                and c["pause_frames"] >= 0):
            e.append("CRACK_DURATIONS|%s|%s" % (c.get("duration_frames"), c.get("pause_frames")))
        elif c.get("start_frame") is not None and not _is_int(c.get("start_frame")):
            e.append("CRACK_START|%s" % c.get("start_frame"))
        elif _is_int(s) and _is_int(f):
            cs, ce, ms = crack_frames(a)
            if cs < s:
                e.append("CRACK_BEFORE_OPEN_START|%d<%d" % (cs, s))
            if ms >= f:
                e.append("CRACK_LEAVES_NO_MAIN_OPENING|main_start=%d>=open_end=%d" % (ms, f))
    k = a.get("expected_key_frames")
    if k is not None and not (isinstance(k, list) and len(k) == 2 and all(_is_int(x) for x in k) and k[0] < k[1]):
        e.append("EXPECTED_KEY_FRAMES|%s" % k)
    if not isinstance(a.get("hold_open_to_end"), bool):
        e.append("HOLD_OPEN_TO_END|%s" % a.get("hold_open_to_end"))
    return e


def ease(kind, u):
    u = min(1.0, max(0.0, float(u)))
    if kind == "cubic-in-out":
        return u * u * (3.0 - 2.0 * u)
    if kind == "smootherstep":
        return u * u * u * (u * (6.0 * u - 15.0) + 10.0)
    return u


def ramp(f0, f1, v0, v1, kind, step):
    """[(frame, value)] from f0 to f1 inclusive, every `step` frames, end always included."""
    fr = list(range(int(f0), int(f1), int(step))) + [int(f1)]
    return [(x, round(v0 + (v1 - v0) * ease(kind, (x - f0) / float(f1 - f0)), 6)) for x in fr]


def open_roll(deg):
    return -float(FRONT_SIGN) * float(deg)


def plan_keys(a, existing_frames, playback_end, section_range=(None, None)):
    """-> sorted [(frame, roll)] NEW keys.  Raises Fail on a plan that cannot sit after the existing keys."""
    errs = validate_args(dict(a, mode="DRY"))
    if errs:
        raise Fail("ARGS|%s" % errs)
    s, f = int(a["open_start_frame"]), int(a["open_end_frame"])
    last = max(existing_frames) if existing_frames else None
    target = open_roll(a["open_deg"])
    keys = []
    h = a.get("hold_closed_until_frame")
    if h is not None and h < s:
        keys.append((int(h), 0.0))
    ck = crack_frames(a)
    if ck:
        cs, ce, ms = ck
        crack = open_roll(a["crack"]["deg"])
        if cs > s:
            keys.append((s, 0.0))
        keys += ramp(cs, ce, 0.0, crack, a["ease"], a["sample_step"])
        keys += ramp(ms, f, crack, target, a["ease"], a["sample_step"])
    else:
        keys += ramp(s, f, 0.0, target, a["ease"], a["sample_step"])
    if a.get("hold_open_to_end") and playback_end is not None and int(playback_end) > f:
        keys.append((int(playback_end), round(target, 6)))
    keys = sorted(dict(keys).items())
    first = keys[0][0]
    if last is not None and first <= last:
        raise Fail("PLAN_NOT_AFTER_EXISTING|first_new=%d|last_existing=%d" % (first, last))
    if set(k for k, _ in keys) & set(existing_frames or []):
        raise Fail("PLAN_FRAME_CLASH")
    if playback_end is not None and f > int(playback_end):
        raise Fail("OPEN_END_PAST_PLAYBACK|%d>%s" % (f, playback_end))
    lo, hi = section_range
    if (lo is not None and first < int(lo)) or (hi is not None and keys[-1][0] >= int(hi)):
        raise Fail("PLAN_OUTSIDE_SECTION|%s|%d..%d" % (list(section_range), first, keys[-1][0]))
    return [(int(x), float(v)) for x, v in keys]


def check_plan(keys, open_deg):
    """-> errors: must start at 0, end at -open_deg, never rise (monotone non-increasing roll)."""
    e = []
    if not keys:
        return ["EMPTY"]
    if abs(keys[0][1]) > VALUE_TOL:
        e.append("START_NOT_ZERO|%s" % keys[0][1])
    if abs(keys[-1][1] - open_roll(open_deg)) > VALUE_TOL:
        e.append("END_NOT_OPEN|%s" % keys[-1][1])
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f1 <= f0:
            e.append("FRAMES_NOT_INCREASING|%d|%d" % (f0, f1))
        if v1 > v0 + VALUE_TOL:
            e.append("NOT_MONOTONE|%d|%d" % (f0, f1))
    return e


def curve_at(keys, frame):
    """Piecewise-linear value with constant extrapolation (every key we evaluate is LINEAR or flanked by equal values)."""
    ks = sorted(keys)
    if frame <= ks[0][0]:
        return ks[0][1]
    for (f0, v0), (f1, v1) in zip(ks, ks[1:]):
        if f0 <= frame <= f1:
            return v0 + (v1 - v0) * (frame - f0) / float(f1 - f0)
    return ks[-1][1]


def check_pattern(chans, expected_frames):
    """chans {base: {"keys": [{"frame", "value", ...}]}} -> errors for anything but the constant 2-key pattern."""
    e = []
    if sorted(chans) != sorted(CHANNELS):
        return ["CHANNEL_SET|%s" % sorted(chans)]
    frames0 = None
    for b in CHANNELS:
        ks = chans[b]["keys"]
        fr = [k["frame"] for k in ks]
        if len(ks) != 2:
            e.append("KEY_COUNT|%s|%d" % (b, len(ks)))
            continue
        if expected_frames is not None and fr != list(expected_frames):
            e.append("KEY_FRAMES|%s|%s" % (b, fr))
        if frames0 is None:
            frames0 = fr
        elif fr != frames0:
            e.append("FRAMES_DIFFER|%s|%s" % (b, fr))
        if ks[0]["value"] != ks[1]["value"]:
            e.append("NOT_CONSTANT|%s" % b)
        if any(k.get("sub", 0.0) for k in ks):
            e.append("SUBFRAME|%s" % b)
    if not any(x.startswith("KEY_COUNT|" + ROLL) for x in e) and \
            any(abs(k["value"]) > VALUE_TOL for k in chans[ROLL]["keys"]):
        e.append("ROLL_NOT_ZERO|%s" % [k["value"] for k in chans[ROLL]["keys"]])
    return e


KEY_FIELDS = ("frame", "sub", "value", "interp", "tmode", "arrive", "leave", "wmode", "arrive_w", "leave_w")


def channel_diff(want, got):
    """Exact (bit-identical) comparison of two channel reads."""
    d = []
    for f in ("default", "has_default", "pre", "post"):
        if want.get(f) != got.get(f):
            d.append("%s:%s->%s" % (f, want.get(f), got.get(f)))
    if len(want["keys"]) != len(got["keys"]):
        return d + ["count:%d->%d" % (len(want["keys"]), len(got["keys"]))]
    for kw, kg in zip(want["keys"], got["keys"]):
        for f in KEY_FIELDS:
            if kw.get(f) != kg.get(f):
                d.append("%s@%s:%s->%s" % (f, kw["frame"], kw.get(f), kg.get(f)))
    return d


def roll_after_diff(orig_keys, planned, got_keys):
    """Applied roll = original (frame, value, interp exact) + planned (frame exact, value within VALUE_TOL, LINEAR).
    -> (errors, tangent_changes)."""
    e, tang = [], []
    want = sorted([(k["frame"], k["value"], "orig", k) for k in orig_keys] + [(f, v, "new", None) for f, v in planned])
    if [w[0] for w in want] != [k["frame"] for k in got_keys]:
        return ["ROLL_FRAMES|want=%d|got=%s" % (len(want), [k["frame"] for k in got_keys][:8])], tang
    for (f, v, kind, ok), g in zip(want, got_keys):
        if kind == "orig":
            if g["value"] != v or g["interp"] != ok["interp"] or g.get("sub") != ok.get("sub"):
                e.append("ORIG_KEY_CHANGED|%d" % f)
            for fld in ("tmode", "arrive", "leave", "wmode", "arrive_w", "leave_w"):
                if g.get(fld) != ok.get(fld):
                    tang.append("%d:%s %s->%s" % (f, fld, ok.get(fld), g.get(fld)))
        else:
            if abs(g["value"] - v) > READBACK_TOL:
                e.append("NEW_KEY_VALUE|%d|%s|%s" % (f, v, g["value"]))
            if g["interp"] != "RCIM_LINEAR":
                e.append("NEW_KEY_INTERP|%d|%s" % (f, g["interp"]))
    return e, tang


def eval_diff(values, first_frame, all_keys, tol=EVAL_TOL):
    """values[i] = evaluated roll at first_frame + i.  -> errors."""
    e = []
    ks = sorted(all_keys)
    span = ks[-1][0] - ks[0][0]
    if first_frame != ks[0][0] or len(values) not in (span, span + 1):
        return ["EVAL_SHAPE|first=%s|n=%d|span=%d" % (first_frame, len(values), span)]
    for i, v in enumerate(values):
        w = curve_at(ks, first_frame + i)
        if abs(float(v) - w) > tol:
            e.append("EVAL|%d|%.5f|want %.5f" % (first_frame + i, float(v), w))
            if len(e) > 5:
                break
    return e


def sample_frames(a, playback_end):
    s, f = int(a["open_start_frame"]), int(a["open_end_frame"])
    out = [s - 6, s, (s + f) // 2, f, 4560]
    if playback_end is not None:
        out.append(int(playback_end) - 1)
    return out


# =====================================================================================================================
# Unreal side (every UE access inside a function)
# =====================================================================================================================

def _ue():
    import unreal
    return unreal


def _en(v):
    return str(getattr(v, "name", v)).split(".")[-1]


def _census(ue):
    lib = ue.EditorLoadingAndSavingUtils           # pattern s3_drama_lights.py:84-89 (ran)
    return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            sorted(p.get_name() for p in lib.get_dirty_map_packages()))


def _read_channel(ue, ch):
    rows = []
    for k in ch.get_keys():
        t = k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        rows.append({"frame": int(t.frame_number.value), "sub": float(getattr(t, "sub_frame", 0.0)),
                     "value": float(k.get_value()), "interp": _en(k.get_interpolation_mode()),
                     "tmode": _en(k.get_tangent_mode()), "arrive": float(k.get_arrive_tangent()),
                     "leave": float(k.get_leave_tangent()), "wmode": _en(k.get_tangent_weight_mode()),
                     "arrive_w": float(k.get_arrive_tangent_weight()), "leave_w": float(k.get_leave_tangent_weight())})
    rows.sort(key=lambda r: (r["frame"], r["sub"]))
    hd = bool(ch.has_default())
    return {"name": str(ch.get_name()), "keys": rows, "has_default": hd,
            "default": float(ch.get_default()) if hd else None,
            "pre": _en(ch.get_pre_infinity_extrapolation()), "post": _en(ch.get_post_infinity_extrapolation())}


def _read_section(ue, s):
    out, handles = {}, {}
    for ch in s.get_all_channels():
        b = channel_base(ch.get_name())
        if b in out:
            raise Fail("DUPLICATE_CHANNEL|%s" % b)
        out[b] = _read_channel(ue, ch)
        handles[b] = ch
    return out, handles


def _section_range(s):
    return (s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None)


def _evaluate(ue, seq, ch):
    """[inf] see docstring.  -> (first_frame, values) or raises."""
    rng = ch.compute_effective_range()
    vals = [float(v) for v in ch.evaluate_keys(rng, seq.get_display_rate())]
    first = min(k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value for k in ch.get_keys())
    return int(first), vals


def _find_keys(ue, ch, frame):
    return [k for k in ch.get_keys()
            if int(k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value) == frame]


def _gather(ue):
    """Guards shared by every mode; read-only.  -> facts dict with live handles under '_h'."""
    ed = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise Fail("PIE_RUNNING")
    world = ed.get_editor_world()
    if world is None or WORLD_NAME not in str(world.get_name()):
        raise Fail("WRONG_WORLD|%s" % (world.get_name() if world is not None else None))
    if ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise Fail("SEQUENCER_OPEN (run close_sequencer.py first)")
    c0 = _census(ue)
    if c0 != ([], []):
        raise Fail("DIRTY_AT_START|%s" % (c0,))
    seq = ue.load_asset(SCENE)
    if seq is None:
        raise Fail("NO_SCENE")
    dr = seq.get_display_rate()
    fps = float(dr.numerator) / float(dr.denominator)
    end = int(seq.get_playback_end())
    bs = [b for b in seq.get_bindings() if str(b.get_display_name()) == BINDING]
    if len(bs) != 1:
        raise Fail("BINDING_COUNT|%d" % len(bs))
    b = bs[0]
    objs = list(seq.locate_bound_objects(b, world))               # prec s4_hangar_hold.py:978
    if len(objs) != 1:
        raise Fail("BINDING_RESOLVES|%d" % len(objs))
    lab = str(objs[0].get_actor_label()) if hasattr(objs[0], "get_actor_label") else None
    if lab != LID_LABEL:
        raise Fail("BINDING_ACTOR|%s" % lab)
    ts = [t for t in b.get_tracks() if t.get_class().get_name() == TRANSFORM_TRACK]
    if len(ts) != 1:
        raise Fail("TRANSFORM_TRACKS|%d" % len(ts))
    secs = list(ts[0].get_sections())
    if len(secs) != 1:
        raise Fail("TRANSFORM_SECTIONS|%d" % len(secs))
    chans, handles = _read_section(ue, secs[0])
    return {"fps": fps, "playback_end": end, "lid_path": objs[0].get_path_name(), "section_range": _section_range(secs[0]),
            "chans": chans, "_h": {"seq": seq, "section": secs[0], "ch": handles}}


def _write_record_exclusive(path, rec):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1)
        h.flush()
        os.fsync(h.fileno())
    with open(path, encoding="utf-8") as h:
        if json.load(h) != json.loads(json.dumps(rec)):
            raise Fail("RECORD_READBACK")


def _rewrite_record(path, rec):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _plan_for(a, g):
    pat = check_pattern(g["chans"], a.get("expected_key_frames"))
    existing = [k["frame"] for k in g["chans"][ROLL]["keys"]] if ROLL in g["chans"] else []
    planned = plan_keys(a, existing, g["playback_end"], g["section_range"])
    bad = check_plan(planned, a["open_deg"])
    if bad:
        raise Fail("PLAN_CHECK|%s" % bad)
    return pat, planned


def _eval_probe(ue, g, expect_keys):
    try:
        first, vals = _evaluate(ue, g["_h"]["seq"], g["_h"]["ch"][ROLL])
    except Exception as exc:  # noqa: BLE001
        return "UNAVAILABLE|%r" % (exc,), None
    d = eval_diff(vals, first, expect_keys)
    return ("OK" if not d else "MISMATCH|%s" % d[:3]), (first, vals)


def run_dry(ue, a, run):
    g = _gather(ue)
    rec_exists = os.path.exists(HERE + RECORD_FILE)
    pat, planned, plan_err = check_pattern(g["chans"], a.get("expected_key_frames")), [], None
    try:
        _, planned = _plan_for(a, g)
    except Fail as exc:
        plan_err = str(exc)
    orig = [(k["frame"], k["value"]) for k in g["chans"][ROLL]["keys"]]
    probe, _ = _eval_probe(ue, g, orig) if orig else ("NO_KEYS", None)
    allk = orig + planned
    samples = {f: round(curve_at(allk, f), 3) for f in sample_frames(a, g["playback_end"])} if allk else {}
    c1 = _census(ue)
    out = {"run": run, "args": a, "fps": g["fps"], "playback_end": g["playback_end"], "lid": g["lid_path"],
           "section_range": list(g["section_range"]), "channels": g["chans"], "pattern_errors": pat,
           "plan_error": plan_err, "planned": planned, "samples": samples, "eval_probe": probe,
           "record_exists": rec_exists, "census_after": c1}
    with open(HERE + "clam_open_dry_%s.json" % run, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    if c1 != ([], []):
        raise Fail("DRY_DIRTIED|%s" % (c1,))
    ready = not pat and plan_err is None and not rec_exists and g["fps"] == float(a["expected_fps"]) and \
        (a.get("expected_playback_end") is None or g["playback_end"] == a["expected_playback_end"]) and \
        (probe == "OK" or not a.get("require_eval"))
    return "CLAMOPEN_DRY_OK|run=%s|apply_ready=%d|keys=%d|first=%s|last=%s|pattern=%s|eval=%s|record=%d|samples=%s" % (
        run, int(ready), len(planned), planned[0] if planned else None, planned[-1] if planned else None,
        "OK" if not pat else pat[:3], probe.split("|")[0], int(rec_exists), json.dumps(samples))


def run_apply(ue, a, run):
    rec_path = HERE + RECORD_FILE
    if os.path.exists(rec_path):
        raise Fail("RECORD_EXISTS (REVERT first)")
    g = _gather(ue)
    if g["fps"] != float(a["expected_fps"]):
        raise Fail("FPS|%s" % g["fps"])
    if a.get("expected_playback_end") is not None and g["playback_end"] != int(a["expected_playback_end"]):
        raise Fail("PLAYBACK_END|%s" % g["playback_end"])
    pat = check_pattern(g["chans"], a.get("expected_key_frames"))
    if pat:
        raise Fail("UNEXPECTED_PATTERN|%s" % pat[:4])
    _, planned = _plan_for(a, g)
    orig_roll = g["chans"][ROLL]["keys"]
    probe, _ = _eval_probe(ue, g, [(k["frame"], k["value"]) for k in orig_roll])
    if probe != "OK" and a.get("require_eval"):
        raise Fail("EVAL_PROBE|%s" % probe)
    src = os.path.join(PROJECT, SCENE_FILE)
    folder = os.path.join(PROJECT, "Backups", "PreClamOpen-" + run)
    rec = {"schema": 1, "tool": "clam_open", "run": run, "state": "applying", "args": a, "scene": SCENE,
           "binding": BINDING, "lid": g["lid_path"], "section_range": list(g["section_range"]),
           "channels": g["chans"], "planned": planned, "backup": folder, "source_sha256": _sha(src),
           "written": datetime.datetime.now().isoformat()}
    _write_record_exclusive(rec_path, rec)                         # RECORD FIRST
    os.makedirs(folder, exist_ok=False)
    dst = os.path.join(folder, os.path.basename(src))
    shutil.copy2(src, dst)
    if _sha(dst) != rec["source_sha256"]:
        raise Fail("BACKUP_HASH")
    shutil.copy2(rec_path, folder)
    seq, ch = g["_h"]["seq"], g["_h"]["ch"][ROLL]
    seq.modify()
    for f, v in planned:
        ch.add_key(ue.FrameNumber(f), float(v), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE,
                   interpolation=ue.MovieSceneKeyInterpolation.LINEAR)   # prec s3_drama_lights.py:157-158
    after, _ = _read_section(ue, g["_h"]["section"])
    errs, tang = roll_after_diff(orig_roll, planned, after[ROLL]["keys"])
    for b in CHANNELS:
        if b != ROLL:
            d = channel_diff(g["chans"][b], after[b])
            if d:
                errs.append("OTHER_CHANNEL|%s|%s" % (b, d[:3]))
    if errs:
        raise Fail("READBACK|%s|%s" % (errs[:4], NS))
    allk = [(k["frame"], k["value"]) for k in orig_roll] + planned
    try:
        first, vals = _evaluate(ue, seq, ch)
        ev = eval_diff(vals, first, allk)
    except Exception as exc:  # noqa: BLE001
        ev = ["EVAL_UNAVAILABLE|%r" % (exc,)] if a.get("require_eval") else []
        first, vals = None, None
    if ev:
        raise Fail("EVAL_READBACK|%s|%s" % (ev[:3], NS))
    c1 = _census(ue)
    if c1 != ([SCENE], []):
        raise Fail("CENSUS|%s|%s" % (c1, NS))
    if not ue.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False):
        raise Fail("SAVE_SCENE_FAILED")
    rec["state"] = "saved"
    _rewrite_record(rec_path, rec)
    c2 = _census(ue)
    if c2 != ([], []):
        raise Fail("DIRTY_AFTER_SAVE|%s (scene saved; REVERT CLAMOPEN available)" % (c2,))
    post, _ = _read_section(ue, g["_h"]["section"])
    perr, _ = roll_after_diff(orig_roll, planned, post[ROLL]["keys"])
    perr += [b for b in CHANNELS if b != ROLL and channel_diff(g["chans"][b], post[b])]
    if perr:
        raise Fail("POST_SAVE_READBACK|%s" % perr[:4])
    samples = {f: (round(vals[f - first], 3) if vals is not None and 0 <= f - first < len(vals) else
                   round(curve_at(allk, f), 3)) for f in sample_frames(a, g["playback_end"])}
    rec.update({"state": "applied", "after_roll": post[ROLL], "tangent_changes": tang, "eval_samples": samples,
                "applied_at": datetime.datetime.now().isoformat(), "saved_sha256": _sha(src)})
    _rewrite_record(rec_path, rec)
    return "CLAMOPEN_APPLY_OK|run=%s|keys_added=%d|open=%s->%s|deg=%s|samples=%s|tangent_changes=%d|saved=scene" % (
        run, len(planned), a["open_start_frame"], a["open_end_frame"], a["open_deg"], json.dumps(samples), len(tang))


def run_revert(ue, a, run):
    rec_path = HERE + RECORD_FILE
    if not os.path.exists(rec_path):
        raise Fail("NO_RECORD")
    with open(rec_path, encoding="utf-8") as h:
        rec = json.load(h)
    if rec.get("state") not in ("applied", "saved"):
        raise Fail("RECORD_STATE|%s (partial APPLY: restore %s with the editor closed)" % (rec.get("state"),
                                                                                         rec.get("backup")))
    g = _gather(ue)
    if g["lid_path"] != rec["lid"]:
        raise Fail("LID_MOVED|%s" % g["lid_path"])
    orig = rec["channels"]
    planned = [tuple(x) for x in rec["planned"]]
    drift, _ = roll_after_diff(orig[ROLL]["keys"], planned, g["chans"][ROLL]["keys"])
    for b in CHANNELS:
        if b != ROLL and channel_diff(orig[b], g["chans"][b]):
            drift.append("OTHER_CHANNEL|%s" % b)
    if drift:
        raise Fail("DRIFT|%s" % drift[:4])
    seq, ch = g["_h"]["seq"], g["_h"]["ch"][ROLL]
    keep = set(k["frame"] for k in orig[ROLL]["keys"])
    seq.modify()
    for k in list(ch.get_keys()):
        if int(k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value) not in keep:
            ch.remove_key(k)                                       # prec s3_drama_lights.py:184-185
    for ok in orig[ROLL]["keys"]:                                  # tangents: restore only what differs
        hits = _find_keys(ue, ch, ok["frame"])
        if len(hits) != 1:
            raise Fail("ORIG_KEY_COUNT|%d|%d|%s" % (ok["frame"], len(hits), NS))
        cur = _read_channel(ue, ch)
        now = next(k for k in cur["keys"] if k["frame"] == ok["frame"])
        k = hits[0]
        if now["tmode"] != ok["tmode"]:
            k.set_tangent_mode(getattr(ue.RichCurveTangentMode, ok["tmode"]))
        if now["wmode"] != ok["wmode"]:
            k.set_tangent_weight_mode(getattr(ue.RichCurveTangentWeightMode, ok["wmode"]))
        for fld, setter in (("arrive", "set_arrive_tangent"), ("leave", "set_leave_tangent"),
                            ("arrive_w", "set_arrive_tangent_weight"), ("leave_w", "set_leave_tangent_weight")):
            if now[fld] != ok[fld]:
                getattr(k, setter)(float(ok[fld]))
    after, _ = _read_section(ue, g["_h"]["section"])
    bad = [b for b in CHANNELS if channel_diff(orig[b], after[b])]
    if bad:
        raise Fail("REVERT_READBACK|%s|%s|%s" % (bad, channel_diff(orig[bad[0]], after[bad[0]])[:3], NS))
    c1 = _census(ue)
    if c1 != ([SCENE], []):
        raise Fail("CENSUS|%s|%s" % (c1, NS))
    if not ue.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False):
        raise Fail("SAVE_SCENE_FAILED")
    c2 = _census(ue)
    if c2 != ([], []):
        raise Fail("DIRTY_AFTER_SAVE|%s" % (c2,))
    post, _ = _read_section(ue, g["_h"]["section"])
    if any(channel_diff(orig[b], post[b]) for b in CHANNELS):
        raise Fail("POST_SAVE_READBACK")
    os.replace(rec_path, rec_path + ".reverted-" + run)
    return "CLAMOPEN_REVERT_OK|run=%s|removed=%d|restored=%s|saved=scene" % (run, len(planned), ROLL)


def main(args_path=None):
    """-> the marker string (also logged).  Never raises."""
    ue = None
    try:
        ue = _ue()
        with open(args_path or (HERE + ARGS_FILE), encoding="utf-8") as h:
            a = merged_args(json.load(h))
        RUN["run"] = str(a.get("run") or fresh_run())
        errs = validate_args(a)
        if errs:
            raise Fail("ARGS|%s" % errs)
        fn = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[a["mode"]]
        marker = fn(ue, a, RUN["run"])
        ue.log(marker)
        return marker
    except Exception as exc:  # noqa: BLE001
        marker = "CLAMOPEN_FAILED|run=%s|%s" % (RUN["run"], exc if isinstance(exc, Fail) else repr(exc))
        try:
            (ue or _ue()).log_error(marker)
        except Exception:  # noqa: BLE001
            print(marker)
        return marker


if __name__ != "clam_open_offline":
    main()
