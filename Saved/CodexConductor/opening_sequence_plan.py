"""Pure planner for the long Opening (Gary, 4 Oct ~01:00). NO Unreal import: the offline harness
test_opening_sequence.py exercises every rule here with the system Python.

The new Opening is the whole of 'Intro_WalkingMusic_1.wav' (96.336 s) played BEFORE Passage 1:
  phase 0  unactivated   0 .. music_start            curtain unlit, every rig lamp at 0
  phase 1  flicker       flicker_start .. flicker_end lamps stutter on, staggered, to an idle level
  phase 2  swivel        swivel_start .. swivel_end   the two FOH movers swing from a parked aim to their place
  phase 3  envelope      swivel_end .. walkin_start   intensity follows the music (smoothed, with headroom)
  phase 4  drop + in     curtain_release (after the last swell, inside the final quarter), landed, walk-in
                         ending exactly at opening_end = the new Passage 1 start

Everything is planned on the Opening's DISPLAY-FRAME grid (25 fps), because Sequencer marked frames and
keys live there. Moments are frames; seconds are derived (frame / fps).

Manual tuning: each named moment can be 'auto' (derived from the music analysis by the rules below) or
an explicit number of seconds in opening_timing.json, AND each one is mirrored as a marked frame
'OPN <name>' on the Opening sequence. reconcile_moments() decides which wins when they disagree:
  - first run (no record of what was last applied): the JSON wins, markers are (re)written;
  - the marker moved since the last apply and the JSON did not: the MARKER wins (Gary dragged it in
    Sequencer) and the value is written back into the JSON as explicit seconds, source 'sequencer';
  - the JSON changed and the marker did not: the JSON wins;
  - both changed to different frames: CONFLICT, the tool refuses and names the moment;
  - a marker that was deleted is recreated from the JSON;
  - derived/informational markers (final_quarter, curtain_landed, swell_NN) cannot be moved: a moved
    one is reported and put back.
"""

import hashlib
import json
import math
import os

FPS_DEFAULT = 25.0
MARKER_PREFIX = "OPN "

# Moments Gary may move (inputs) and moments that are only shown (derived). Order = timeline order.
INPUT_MOMENTS = (
    "music_start", "flicker_start", "flicker_end", "swivel_start", "swivel_end",
    "last_swell", "curtain_release", "walkin_start", "opening_end",
)
DERIVED_MOMENTS = ("final_quarter", "curtain_landed")

# The two Show house warmers (cue "P01 Wing 001", Saved/CodexStructure/p01_warmer_plan.json).
# Gary, 4 Oct: OFF FOR THE OPENING ONLY, ON in P01. This tool OWNS that decision; lighting_scores_apply.py
# retains (never touches) them (lighting_scores.json foreign_owned_lights). Two facts make it unbuildable
# today without a new mechanism (Docs/Conductor/OPENING_SEQUENCE_PLAN_2026-10-04.md section 4b):
#   - the attachment's Enabled flag is not time-varying: disabling it removes the lamp from P01 too
#     (InfinityStagePassageActor.cpp:905, a disabled attachment is not spawned) - so this tool must never
#     write it;
#   - Light Drama cannot dark them before P01: drama runs only inside the Passage's own segment
#     (InfinityStagePassageActor.cpp:1267-1270 returns before the drama block at :1620-1662;
#     InfinityStageCameraRig.cpp:775-779), so during the Opening the lamp keeps its level state (authored, lit).
HOUSE_WARMER_LABELS = ("P01 Wing 001 House L", "P01 Wing 001 House R")
HOUSE_WARMER_RULE = "off_for_opening_only"
HOUSE_WARMER_OWNER = "opening_sequence_apply.py"
# None = the warmers are left lit (they burn through the Opening). "disable_show_attachment" = rig takeover
# (Gary 5 Oct ~16:25, 'let the rig FOH spots do it'): the Show attachments' Enabled flag goes False. Enabled is
# NOT time-varying (InfinityStagePassageActor.cpp:905-908), so that also removes them from P01; the planner
# refuses it until house_warmers.p01_without_warmers_confirmed_by names who accepted that.
HOUSE_WARMER_MECHANISMS = (None, "disable_show_attachment")
# The only attachment fields this tool may change on the warmers (record + REVERT cover exactly these).
WARMER_WRITE_PATHS = (("enabled",), ("lighting", "inner_cone_angle_degrees"))


def house_warmer_check(cfg):
    """(failures, warnings) for the house_warmers block. Failures refuse the plan; nothing here writes."""
    ws = cfg.get("house_warmers") or {}
    fails, warns = [], []
    if ws.get("disable"):
        fails.append("house-warmers-disable: the legacy 'disable' key is refused; use mechanism "
                     "'disable_show_attachment' with p01_without_warmers_confirmed_by (it kills them in P01 too)")
    if ws.get("mechanism") == "disable_show_attachment" and not ws.get("p01_without_warmers_confirmed_by"):
        fails.append("house-warmers-p01: disabling the Show warmers removes them from P01 too (Enabled is not "
                     "time-varying; Gary 4 Oct wanted them ON in P01). Set p01_without_warmers_confirmed_by first")
    cone = ws.get("cone")
    if cone is not None:
        d = float(cone.get("inner_equals_outer_minus_deg", -1))
        if not 0.0 <= d < float(cone.get("expect_outer_deg", 0)):
            fails.append("house-warmers-cone: inner_equals_outer_minus_deg %r outside [0, expect_outer_deg)" % d)
    if ws.get("rule") != HOUSE_WARMER_RULE:
        fails.append("house-warmers-rule: %r != %r (Gary 4 Oct)" % (ws.get("rule"), HOUSE_WARMER_RULE))
    if ws.get("owner") != HOUSE_WARMER_OWNER:
        fails.append("house-warmers-owner: %r != %r" % (ws.get("owner"), HOUSE_WARMER_OWNER))
    if tuple(ws.get("labels") or ()) != HOUSE_WARMER_LABELS:
        fails.append("house-warmers-labels: %r != %r" % (ws.get("labels"), list(HOUSE_WARMER_LABELS)))
    mech = ws.get("mechanism")
    if mech not in HOUSE_WARMER_MECHANISMS:
        fails.append("house-warmers-mechanism: %r is not implemented (Light Drama cannot dark a lamp before its "
                     "Passage segment; plan section 4b)" % (mech,))
    elif mech is None:
        warns.append("house warmers stay ON through the Opening (Gary's 'off for the Opening only' has no "
                     "mechanism yet; plan section 4b): phase 0 is NOT dark")
    elif mech == "disable_show_attachment":
        warns.append("house warmers DISABLED in the Show: dark through the Opening AND absent from P01 "
                     "(confirmed by %s)" % ws.get("p01_without_warmers_confirmed_by"))
    return fails, warns


def warmer_targets(cfg, live):
    """What APPLY writes on the two warmers. live: {label: {'enabled', 'inner', 'outer'}} read from the Show.
    Returns (targets {label: {'enabled': bool, 'inner_cone_angle_degrees': float}}, failures). Only the two
    WARMER_WRITE_PATHS fields are ever targeted; a field equal to live is a no-op."""
    ws = cfg.get("house_warmers") or {}
    fails, targets = [], {}
    labels = tuple(ws.get("labels") or ())
    if sorted(live) != sorted(labels):
        return {}, ["warmers-live: found %r, expected %r" % (sorted(live), list(labels))]
    cone = ws.get("cone")
    for label in labels:
        row = live[label]
        inner = float(row["inner"])
        if cone is not None:
            if abs(float(row["outer"]) - float(cone["expect_outer_deg"])) > 1e-4:
                fails.append("warmers-outer: %s outer %.3f != expected %.3f (re-read before changing the cone)"
                             % (label, float(row["outer"]), float(cone["expect_outer_deg"])))
                continue
            inner = float(row["outer"]) - float(cone["inner_equals_outer_minus_deg"])
        enabled = bool(row["enabled"])
        if ws.get("mechanism") == "disable_show_attachment":
            enabled = False
        targets[label] = {"enabled": enabled, "inner_cone_angle_degrees": inner}
    return targets, fails


def _get_path(state, path):
    for p in path:
        state = state[p]
    return state


def _set_path(state, path, value):
    for p in path[:-1]:
        state = state[p]
    state[path[-1]] = value


def warmers_apply_state(states, targets):
    """Pure model of the warmer write on attachment_state() dicts {label: state}: only WARMER_WRITE_PATHS change."""
    new = json.loads(json.dumps(states))
    for label, t in targets.items():
        _set_path(new[label], ("enabled",), bool(t["enabled"]))
        _set_path(new[label], ("lighting", "inner_cone_angle_degrees"), float(t["inner_cone_angle_degrees"]))
    return new


def warmers_revert_state(states, original):
    """Pure model of REVERT: the WARMER_WRITE_PATHS fields back to the first-write snapshot; nothing else touched."""
    new = json.loads(json.dumps(states))
    for label, orig in original.items():
        for path in WARMER_WRITE_PATHS:
            _set_path(new[label], path, _get_path(orig, path))
    return new


def warmers_changed_paths(before, after):
    """Field paths that differ between two {label: state} snapshots, as 'label:a.b'."""
    out = []

    def walk(label, a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                walk(label, a.get(k), b.get(k), path + (k,))
        elif a != b:
            out.append("%s:%s" % (label, ".".join(path)))
    for label in sorted(set(before) | set(after)):
        walk(label, before.get(label), after.get(label), ())
    return out


def cone_check(cfg):
    """Gary 5 Oct ~16:25: inner cone = outer - cone_rule.inner_equals_outer_minus_deg for every enabled spot fixture."""
    rule = cfg.get("cone_rule")
    if not rule:
        return []
    d = float(rule["inner_equals_outer_minus_deg"])
    return ["cone-rule: %s inner %.2f != outer %.2f - %.2f" % (fx["name"], float(fx["inner_cone_deg"]),
                                                                float(fx["outer_cone_deg"]), d)
            for fx in cfg["fixtures"] if fx.get("enabled", True) and fx.get("kind") == "spot"
            and abs(float(fx["inner_cone_deg"]) - (float(fx["outer_cone_deg"]) - d)) > 1e-6]


# --------------------------------------------------------------------------------------------- small utils
def frame_of(seconds, fps):
    return int(round(float(seconds) * fps))


def seconds_of(frame, fps):
    return frame / float(fps)


def smooth(values, window_samples, passes=2):
    """Centred moving average, repeated (2 passes = triangular kernel). Deterministic, edge-shrinking."""
    radius = max(0, int(window_samples) // 2)
    out = list(values)
    for _ in range(max(1, int(passes))):
        prefix = [0.0]
        for v in out:
            prefix.append(prefix[-1] + v)
        n = len(out)
        nxt = []
        for i in range(n):
            a, b = max(0, i - radius), min(n, i + radius + 1)
            nxt.append((prefix[b] - prefix[a]) / (b - a))
        out = nxt
    return out


def unit_hash(*parts):
    """Uniform [0,1) from a stable hash: NOT random.Random, so no draw-order dependence (puss-random-draw-order)."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:13], 16) / float(16 ** 13)


def pearson(a, b):
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


# --------------------------------------------------------------------------------------------- analysis
def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def music_curves(analysis):
    """Return (rate_hz, intensity[], rms[] resampled to the same rate, duration_s)."""
    fc = analysis["featureCurves"]
    rate = float(fc["rateHz"])
    intensity = [float(v) for v in fc["curves"]["intensity"]]
    duration = float(analysis["durationSeconds"])
    wave = analysis["waveform"]
    bins = len(wave)
    rms = []
    for i in range(len(intensity)):
        t = i / rate
        j = min(bins - 1, int(t / duration * bins))
        rms.append(float(wave[j]["rms"]))
    return rate, intensity, rms, duration


def envelope_series(analysis, env_cfg):
    """Normalized 0..1 music envelope on the feature-curve grid: weighted blend of the smoothed
    'intensity' feature curve and the smoothed waveform RMS, each normalized to its own peak."""
    rate, intensity, rms, _ = music_curves(analysis)
    window = max(1, int(round(float(env_cfg["smoothing_s"]) * rate)))
    passes = int(env_cfg.get("smoothing_passes", 2))
    si = smooth(intensity, window, passes)
    sr = smooth(rms, window, passes)
    pi, pr = max(si) or 1.0, max(sr) or 1.0
    wi = float(env_cfg["weights"].get("intensity", 0.5))
    wr = float(env_cfg["weights"].get("rms", 0.5))
    total = (wi + wr) or 1.0
    blend = [(wi * a / pi + wr * b / pr) / total for a, b in zip(si, sr)]
    peak = max(blend) or 1.0
    return rate, [v / peak for v in blend]


def detect_swells(analysis, rules):
    """Peaks of the smoothed 'intensity' curve with prominence, merged within a minimum separation.
    Returns [{"t": s, "level": 0..1 of the global smoothed peak, "prominence": 0..1}] in time order."""
    rate, intensity, _, _ = music_curves(analysis)
    window = max(1, int(round(float(rules["swell_smoothing_s"]) * rate)))
    s = smooth(intensity, window, 2)
    peak = max(s) or 1.0
    s = [v / peak for v in s]
    n = len(s)
    reach = int(round(float(rules["swell_prominence_window_s"]) * rate))
    cands = []
    for i in range(1, n - 1):
        if s[i] >= s[i - 1] and s[i] > s[i + 1]:
            left = min(s[max(0, i - reach):i + 1])
            right = min(s[i:min(n, i + reach + 1)])
            prom = s[i] - max(left, right)
            if prom >= float(rules["swell_min_prominence"]):
                cands.append({"t": round(i / rate, 3), "level": round(s[i], 4), "prominence": round(prom, 4)})
    # merge: within min separation keep the highest
    merged = []
    sep = float(rules["swell_min_separation_s"])
    for c in cands:
        if merged and c["t"] - merged[-1]["t"] < sep:
            if c["level"] > merged[-1]["level"]:
                merged[-1] = c
        else:
            merged.append(c)
    return merged


def detect_music_start(analysis, rules):
    wave = analysis["waveform"]
    duration = float(analysis["durationSeconds"])
    peak = max(float(w["rms"]) for w in wave) or 1.0
    threshold = float(rules["music_start_rms_fraction"]) * peak
    for i, w in enumerate(wave):
        if float(w["rms"]) >= threshold:
            return i * duration / len(wave)
    return 0.0


def major_changes(analysis):
    return sorted(float(m["timeSeconds"]) for m in analysis.get("majorChangeProposals", []))


# --------------------------------------------------------------------------------------------- curtain + walk
def curtain_facts(cfg):
    c = cfg["curtain"]
    return {
        "cache_fps": float(c["cache_fps"]),
        "release_in_cache_s": float(c["release_in_cache_s"]),
        "landed_after_release_s": (float(c["landed_bake_frame"]) - float(c["release_frame"])) / float(c["cache_fps"]),
        "dur_ticks": int(c["cache_duration_ticks"]),
        "fall_frames": int(c["fall_frames"]),
        "ticks_per_second": float(c["ticks_per_second"]),
    }


def curtain_sections(release_frame_target_s, end_frame, cfg, fps):
    """Three GC sections: HOLD one-tick window just before the release, FALL from that offset for a fixed
    250 frames (the bake is unchanged; only the section START moves), PILE one-tick window at the last
    sample. Mirrors Saved/CodexSoftGoods/opening_hold_at_release.py's plan rule exactly.
    Returns (sections [[start, end, start_off_ticks, end_off_ticks] x3], actual_release_s, landed_s)."""
    f = curtain_facts(cfg)
    tps = f["ticks_per_second"]
    hold_off = int(round((f["release_in_cache_s"] - 1.0 / f["cache_fps"]) * tps))
    lead_s = f["release_in_cache_s"] - hold_off / tps          # cache time from FALL start to the release
    fall_start = int(round((release_frame_target_s - lead_s) * fps))
    fall_end = fall_start + f["fall_frames"]
    if hold_off + int(round(f["fall_frames"] / fps * tps)) > f["dur_ticks"]:
        raise ValueError("FALL would overrun the cache and loop")
    if fall_start < 1:
        raise ValueError("release too early: FALL would start before frame 1")
    if fall_end > end_frame:
        raise ValueError("FALL (%d..%d) runs past the Opening end %d" % (fall_start, fall_end, end_frame))
    sections = [
        [0, fall_start, hold_off, f["dur_ticks"] - hold_off - 1],
        [fall_start, fall_end, hold_off, 0],
        [fall_end, end_frame, f["dur_ticks"] - 1, 0],
    ]
    release_s = fall_start / fps + lead_s
    return sections, release_s, release_s + f["landed_after_release_s"]


def walk_bounds(cfg):
    """A walk-in from rest with constant acceleration over ease_s then constant v_end covers the distance
    d in D = ease_s/2 + d/v. ease_s in [0, 2d/v] => D in [d/v, 2d/v]."""
    w = cfg["walkin"]
    d = math.dist([w["seat"][k] for k in ("x", "y", "z")], [w["target"][k] for k in ("x", "y", "z")])
    v = float(w["v_end_cm_s"])
    return d, v, d / v, 2.0 * d / v


def ease_for_duration(duration_s, cfg):
    d, v, lo, hi = walk_bounds(cfg)
    if duration_s < lo - 1e-9 or duration_s > hi + 1e-9:
        raise ValueError("walk-in duration %.3f s outside [%.3f, %.3f] for %.0f cm at %.0f cm/s"
                         % (duration_s, lo, hi, d, v))
    return min(2.0 * d / v, max(0.0, 2.0 * (duration_s - d / v)))


def load_walkin_planner(path):
    scope = {"__name__": "puss_walkin_plan", "__file__": path}
    with open(path, "r", encoding="utf-8") as handle:
        exec(compile(handle.read(), path, "exec"), scope)
    return scope["plan_walk"], scope["check_plan"]


def compress_walk_keys(keys):
    """Drop the constant hold keys between frame 0 and the frame before the walk starts: with LINEAR
    interpolation the evaluated values are identical, and Gary can slide one block of keys."""
    if len(keys) < 3:
        return list(keys)
    first_move = None
    for i in range(1, len(keys)):
        if keys[i][1:] != keys[0][1:]:
            first_move = i
            break
    if first_move is None or first_move <= 1:
        return list(keys)
    return [keys[0]] + list(keys[first_move - 1:])


# --------------------------------------------------------------------------------------------- moments
def resolve_moments(cfg, analysis, fps):
    """JSON moments -> frames. 'auto' values follow the rules; explicit values are seconds."""
    rules = cfg["rules"]
    m = cfg["moments"]
    track = float(analysis["durationSeconds"])
    swells = detect_swells(analysis, rules)
    changes = major_changes(analysis)
    out, why = {}, {}

    def explicit(name):
        v = m.get(name, {}).get("value", "auto")
        return None if v == "auto" else float(v)

    def put(name, seconds, reason):
        out[name] = frame_of(seconds, fps)
        why[name] = reason

    v = explicit("opening_end")
    put("opening_end", v if v is not None else math.ceil(track * fps - 1e-9) / fps,
        "json" if v is not None else "auto: the track length rounded UP to a frame")
    v = explicit("music_start")
    put("music_start", v if v is not None else detect_music_start(analysis, rules),
        "json" if v is not None else "auto: first waveform bin >= %.2f x peak RMS" % rules["music_start_rms_fraction"])
    v = explicit("flicker_start")
    put("flicker_start", v if v is not None else seconds_of(out["music_start"], fps),
        "json" if v is not None else "auto: = music_start")
    v = explicit("flicker_end")
    put("flicker_end", v if v is not None else seconds_of(out["flicker_start"], fps) + float(rules["flicker_s"]),
        "json" if v is not None else "auto: flicker_start + flicker_s")
    v = explicit("swivel_start")
    if v is None:
        after = [c for c in changes if c >= seconds_of(out["flicker_end"], fps) - 1e-6]
        v_auto = after[0] if after else seconds_of(out["flicker_end"], fps)
        put("swivel_start", v_auto, "auto: first major change at/after flicker_end")
    else:
        put("swivel_start", v, "json")
    v = explicit("swivel_end")
    if v is None:
        after = [c for c in changes if c > seconds_of(out["swivel_start"], fps) + float(rules["swivel_min_s"])]
        v_auto = after[0] if after else seconds_of(out["swivel_start"], fps) + float(rules["swivel_min_s"])
        put("swivel_end", v_auto, "auto: next major change >= swivel_min_s after swivel_start")
    else:
        put("swivel_end", v, "json")
    fq = float(rules["final_quarter_fraction"]) * track
    put("final_quarter", fq, "derived: %.2f x track length" % rules["final_quarter_fraction"])
    v = explicit("last_swell")
    if v is None:
        big = [s for s in swells if s["level"] >= float(rules["swell_min_level"])]
        if not big:
            raise ValueError("no swell reaches swell_min_level")
        put("last_swell", big[-1]["t"], "auto: last swell with level >= %.2f" % rules["swell_min_level"])
    else:
        put("last_swell", v, "json")
    v = explicit("curtain_release")
    if v is None:
        floor_s = max(seconds_of(out["last_swell"], fps) + float(rules["release_after_swell_min_s"]), fq)
        after = [c for c in changes if c >= floor_s - 1e-6]
        v_auto = after[0] if after and after[0] <= floor_s + float(rules["release_snap_max_s"]) else floor_s
        put("curtain_release", v_auto,
            "auto: first major change at/after max(last_swell + %.1f s, final_quarter) (snap <= %.1f s)"
            % (rules["release_after_swell_min_s"], rules["release_snap_max_s"]))
    else:
        put("curtain_release", v, "json")
    v = explicit("walkin_start")
    if v is None:
        d, vv, lo, hi = walk_bounds(cfg)
        duration = float(cfg["walkin"]["ease_s"]) / 2.0 + d / vv
        put("walkin_start", seconds_of(out["opening_end"], fps) - duration,
            "auto: opening_end - walk duration (ease_s %.2f)" % cfg["walkin"]["ease_s"])
    else:
        put("walkin_start", v, "json")
    return out, why, swells


def reconcile_moments(json_frames, marker_frames, last_applied):
    """Decide JSON vs Sequencer marker per input moment. Returns (frames, sources, conflicts, writeback).
    json_frames: resolved JSON frames; marker_frames: {name: frame} read from the sequence now (missing
    = no marker); last_applied: {name: frame} recorded by the previous APPLY (None on a first run)."""
    frames, sources, conflicts, writeback = {}, {}, [], {}
    for name in INPUT_MOMENTS:
        j = json_frames[name]
        mk = marker_frames.get(name)
        if last_applied is None or name not in last_applied:
            frames[name], sources[name] = j, "json (first apply)"
            continue
        last = last_applied[name]
        marker_moved = mk is not None and mk != last
        json_moved = j != last
        if mk is None:
            frames[name], sources[name] = j, "json (marker missing: recreated)"
        elif marker_moved and not json_moved:
            frames[name], sources[name] = mk, "sequencer"
            writeback[name] = mk
        elif json_moved and not marker_moved:
            frames[name], sources[name] = j, "json"
        elif marker_moved and json_moved:
            if mk == j:
                frames[name], sources[name] = j, "json+sequencer (agree)"
            else:
                conflicts.append("%s: marker moved %d->%d AND json moved %d->%d" % (name, last, mk, last, j))
                frames[name], sources[name] = j, "CONFLICT"
        else:
            frames[name], sources[name] = j, "unchanged"
    return frames, sources, conflicts, writeback


# --------------------------------------------------------------------------------------------- lamp keys
def flicker_steps(fixture, start_frame, end_frame, cfg, seed):
    """Deterministic stutter, [(frame, scale)] for CONSTANT interpolation, ending ON at the idle level at
    end_frame. Two styles, chosen by the keys present in cfg["flicker"]:
      - "peak_max" present -> strobe_flicker_steps (Gary 5 Oct ~15:15, 'brutal with a bit of strobe falloff');
      - absent -> the original stutter below, byte-for-byte unchanged (backward compatible)."""
    fl = cfg["flicker"]
    if "peak_max" in fl:
        return strobe_flicker_steps(fixture, start_frame, end_frame, fl, seed)
    # ---- original stutter: on/off steps of 1..max_step frames whose ON probability ramps 0.2 -> 1.0

    idle = float(fl["idle_level"])
    lo_on = float(fl.get("on_level_min", 0.55))
    max_step = int(fl["max_step_frames"])
    keys = [(start_frame, 0.0)]
    f, i = start_frame, 0
    span = max(1, end_frame - start_frame)
    while True:
        u = unit_hash(seed, fixture, "step", i)
        f += 1 + int(u * max_step)
        if f >= end_frame:
            break
        p_on = 0.2 + 0.8 * (f - start_frame) / span
        on = unit_hash(seed, fixture, "on", i) < p_on
        level = idle * (lo_on + (1.0 - lo_on) * unit_hash(seed, fixture, "lvl", i)) if on else 0.0
        if keys[-1][1] != level:
            keys.append((f, level))
        i += 1
    keys.append((end_frame, idle))
    return keys


# Safety ceiling for the strobe peaks (x nominal). Gary 5 Oct asked for ~3x; anything above this is refused
# by validate() as 'flicker-peak-cap' rather than keyed. Applies ONLY inside each lamp's flicker window;
# outside it the envelope cap (envelope.peak) still holds (validate 'intensity-cap').
FLICKER_PEAK_HARD_CAP = 4.0


def strobe_flicker_steps(fixture, start_frame, end_frame, fl, seed):
    """Strobe stutter (Gary 5 Oct ~15:15: 'brutal with a bit of that strobe falloff'). Scales are x nominal.
    Each flash: a pop at peak in [peak_min, peak_max] (mostly ONE frame; double_pop_chance holds it a second
    frame), then a falloff of falloff_frames_min..max frames at peak x falloff[k] (each x (1 +/- falloff_jitter)),
    then BLACK (0.0) for a gap. Gaps are drawn in [gap_early_frames] at the start and shrink towards
    [gap_late_frames] at the end (progress ** gap_curve), always >= 1 frame, so every flash is separated by
    at least one fully black frame. No flash starts unless its pop + falloff_frames_min fit before end_frame; a
    longer falloff (or a double pop) that would cross end_frame is clipped by the landing. The last key is
    (end_frame, idle_level): the lamp LANDS ON at the level the post-flicker hold/envelope starts from.
    Deterministic: every draw is unit_hash(seed, fixture, tag, index) - no draw-order dependence."""
    idle = float(fl["idle_level"])
    pmin, pmax = float(fl["peak_min"]), float(fl["peak_max"])
    falloff = [float(x) for x in fl.get("falloff", [0.34, 0.11, 0.035])]
    fmax = max(0, min(len(falloff), int(fl.get("falloff_frames_max", len(falloff)))))
    fmin = max(0, min(fmax, int(fl.get("falloff_frames_min", fmax))))
    jitter = float(fl.get("falloff_jitter", 0.0))
    hold2 = float(fl.get("double_pop_chance", 0.0))
    g_early = [float(x) for x in fl.get("gap_early_frames", [10, 20])]
    g_late = [float(x) for x in fl.get("gap_late_frames", [1, 3])]
    curve = float(fl.get("gap_curve", 1.0))
    span = max(1, end_frame - start_frame)

    def h(*tag):
        return unit_hash(seed, fixture, "strobe", *tag)

    def gap(i, at):
        t = min(1.0, max(0.0, (at - start_frame) / float(span))) ** curve
        lo = g_early[0] + (g_late[0] - g_early[0]) * t
        hi = g_early[1] + (g_late[1] - g_early[1]) * t
        return max(1, int(round(lo + (hi - lo) * h("gap", i))))

    raw = [(start_frame, 0.0)]
    f, i = start_frame, 0
    if not fl.get("first_flash_at_start", True):
        f += gap(-1, start_frame)
    while f + 1 + fmin <= end_frame:                   # a flash starts only if its pop + minimum falloff fit
        peak = pmin + (pmax - pmin) * h("peak", i)
        seq = [peak]
        if h("hold", i) < hold2:
            seq.append(peak)
        n = fmin + int(h("tail", i) * (fmax - fmin + 1))
        for k in range(min(n, fmax)):
            seq.append(peak * falloff[k] * (1.0 + jitter * (2.0 * h("fall", i, k) - 1.0)))
        for j, v in enumerate(seq):
            if f + j >= end_frame:
                break
            raw.append((f + j, v))
        f += len(seq)
        if f < end_frame:
            raw.append((f, 0.0))                       # fully black between flashes
        f += gap(i, f)
        i += 1
    raw.append((end_frame, idle))
    keys = {}
    for fr_, v in raw:                                 # a later key at the same frame wins
        keys[fr_] = v
    out = []
    for fr_ in sorted(keys):
        if not out or out[-1][1] != keys[fr_]:
            out.append((fr_, keys[fr_]))
    return out


def envelope_scale(env_value, env_cfg):
    floor = float(env_cfg["floor"])
    peak = float(env_cfg["peak"])
    usable = (1.0 - float(env_cfg["headroom"])) * float(env_cfg["gain"]) * env_value
    return floor + (peak - floor) * min(1.0, max(0.0, usable))


def env_at(t, rate, series):
    x = t * rate
    i = int(math.floor(x))
    if i <= 0:
        return series[0]
    if i >= len(series) - 1:
        return series[-1]
    a = x - i
    return series[i] * (1 - a) + series[i + 1] * a


def fixture_keys(fixture, frames, cfg, env_rate, env, fps):
    """Intensity keys [(frame, candela, interp)] and, for movers, rotation keys [(frame, pitch, yaw, roll)]."""
    name = fixture["name"]
    nominal = float(fixture["nominal_cd"])
    weight = float(fixture.get("envelope_weight", 1.0))
    idle = float(cfg["flicker"]["idle_level"])
    seed = cfg["flicker"]["seed"]
    stagger = int(round(float(fixture.get("flicker_stagger_s", 0.0)) * fps))
    f_start = frames["flicker_start"] + stagger
    f_end = frames["flicker_end"] + stagger
    keys = [(0, 0.0, "constant")]
    if f_start > 0:
        keys.append((f_start - 1, 0.0, "constant"))
    for f, s in flicker_steps(name, f_start, f_end, cfg, seed):
        keys.append((f, s * nominal, "constant"))
    # idle hold through the swivel, then rise into the envelope over env rise
    env_cfg = cfg["envelope"]
    step = int(env_cfg["key_step_frames"])
    env_start = frames["swivel_end"]
    walk = frames["walkin_start"]
    end = frames["opening_end"]
    fade_before_release = fixture.get("fade_out_before_release_s")
    out_frame = None
    if fade_before_release is not None:
        out_frame = frames["curtain_release"] - int(round(float(fade_before_release) * fps))

    trend = env_cfg.get("trend")

    def trend_at(frame):
        """Gary 5 Oct ~16:25: the FOH carry a RISE to the curtain. A linear multiplier on the envelope scale,
        trend.start at frames[trend.from] -> trend.end at frames[trend.to], held outside. Absent = 1.0 (old)."""
        if not trend:
            return 1.0
        a, b = frames[trend["from"]], frames[trend["to"]]
        u = min(1.0, max(0.0, (frame - a) / float(max(1, b - a))))
        return float(trend["start"]) + (float(trend["end"]) - float(trend["start"])) * u

    def level(frame):
        s = envelope_scale(env_at(frame / fps, env_rate, env), env_cfg) * trend_at(frame)
        return nominal * (idle + (s - idle) * weight)       # weight 1 = the full envelope, 0 = idle hold

    rise_from = env_cfg.get("rise_from")
    if rise_from:
        # Gary 5 Oct ~15:45: 'land dim, rise slowly with the swivel'. The lamp holds its landing level (idle) from
        # flicker_end until rise_from (e.g. swivel_start), then eases (smoothstep, zero slope at both ends) up to
        # the envelope's own level AT swivel_end, so the envelope continues from there with no step.
        r0 = max(frames[rise_from], f_end)
        lo, hi = idle * nominal, level(env_start)
        keys.append((r0, lo, "linear"))
        span = max(1, env_start - r0)
        rstep = max(1, int(env_cfg.get("rise_key_step_frames", step)))
        f = r0 + rstep
        while f < env_start:
            u = (f - r0) / float(span)
            keys.append((f, lo + (hi - lo) * u * u * (3.0 - 2.0 * u), "linear"))
            f += rstep
        keys.append((env_start, hi, "linear"))
    else:
        keys.append((env_start, idle * nominal, "linear"))
    f = env_start + step
    stop = walk if out_frame is None else min(walk, out_frame)
    while f < stop:
        keys.append((f, level(f), "linear"))
        f += step
    if out_frame is not None and out_frame < walk:
        keys.append((out_frame, level(out_frame), "linear"))
        keys.append((min(end, out_frame + int(round(float(fixture.get("fade_out_s", 1.0)) * fps))), 0.0, "linear"))
    else:
        keys.append((walk, level(walk), "linear"))
        keys.append((end, nominal * float(cfg["walkin"]["end_light_level"]), "linear"))
    # strictly increasing frames (a later key at an equal frame replaces the earlier one)
    dedup = {}
    for f, v, interp in keys:
        dedup[f] = (f, v, interp)
    keys = [dedup[k] for k in sorted(dedup)]
    rot = []
    if fixture.get("mover"):
        fin = fixture["final_aim"]
        off = fixture["park_offset"]
        park = (fin["pitch"] + off["pitch"], fin["yaw"] + off["yaw"], fin.get("roll", 0.0))
        rot = [(0, park[0], park[1], park[2]),
               (frames["swivel_start"], park[0], park[1], park[2]),
               (frames["swivel_end"], fin["pitch"], fin["yaw"], fin.get("roll", 0.0))]
    return keys, rot


# --------------------------------------------------------------------------------------------- the plan
def build_plan(cfg, analysis, walk_planner_path, marker_frames=None, last_applied=None):
    fps = float(cfg.get("fps", FPS_DEFAULT))
    json_frames, why, swells = resolve_moments(cfg, analysis, fps)
    frames, sources, conflicts, writeback = reconcile_moments(json_frames, marker_frames or {}, last_applied)
    frames["final_quarter"] = json_frames["final_quarter"]
    end = frames["opening_end"]
    sections, release_s, landed_s = curtain_sections(seconds_of(frames["curtain_release"], fps), end, cfg, fps)
    frames["curtain_landed"] = int(math.ceil(landed_s * fps - 1e-9))
    # walk-in: ends exactly at opening_end; ease solved from walkin_start
    duration = seconds_of(end - frames["walkin_start"], fps)
    ease = ease_for_duration(duration, cfg)
    plan_walk, check_plan = load_walkin_planner(walk_planner_path)
    w = cfg["walkin"]
    keys, report = plan_walk(w["seat"], w["target"], w["v_end_cm_s"], ease, seconds_of(end, fps), fps,
                             w["focal0_mm"], w["focal1_mm"], w["focus0_cm"], w["focus1_cm"], landed_s,
                             w["pile_edge_cm"])
    walk_failures = check_plan(keys, report, w["target"], w["v_end_cm_s"], landed_s, w["pile_edge_cm"])
    env_rate, env = envelope_series(analysis, cfg["envelope"])
    lamps = {}
    for fx in cfg["fixtures"]:
        if not fx.get("enabled", True):
            continue
        ik, rk = fixture_keys(fx, frames, cfg, env_rate, env, fps)
        stagger = int(round(float(fx.get("flicker_stagger_s", 0.0)) * fps))
        lamps[fx["name"]] = {"intensity": ik, "rotation": rk, "nominal_cd": float(fx["nominal_cd"]),
                             "flicker_start": frames["flicker_start"] + stagger,
                             "flicker_end": frames["flicker_end"] + stagger}
    plan = {
        "fps": fps,
        "frames": frames,
        "seconds": {k: round(seconds_of(v, fps), 4) for k, v in frames.items()},
        "sources": sources,
        "reasons": why,
        "conflicts": conflicts,
        "writeback": writeback,
        "swells": swells,
        "curtain": {"sections": sections, "release_s": release_s, "landed_s": landed_s},
        "walkin": {"ease_s": ease, "start_s": report["start_s"], "end_s": report["end_s"],
                   "keys": compress_walk_keys(keys), "full_key_count": len(keys), "failures": walk_failures},
        "lamps": lamps,
        "track_s": float(analysis["durationSeconds"]),
        "master_delta_s": seconds_of(end, fps) - float(cfg["baseline"]["opening_end_s"]),
        "envelope": {"rate": env_rate, "series": env},
    }
    hw_fails, hw_warns = house_warmer_check(cfg)
    ws = cfg.get("house_warmers") or {}
    plan["house_warmers"] = {"write": bool(ws.get("mechanism") or ws.get("cone")), "rule": ws.get("rule"),
                             "mechanism": ws.get("mechanism"), "cone": ws.get("cone"),
                             "write_paths": [".".join(p) for p in WARMER_WRITE_PATHS],
                             "warnings": hw_warns}
    plan["failures"] = validate(plan, cfg)
    return plan


def validate(plan, cfg):
    """Named failures; [] means the plan is good. Every rule here has a negative control in the harness."""
    fr, fps = plan["frames"], plan["fps"]
    s = plan["seconds"]
    fail = []
    fl_cfg = cfg["flicker"]
    order = ["music_start", "flicker_start", "flicker_end", "swivel_start", "swivel_end"]
    for a, b in zip(order, order[1:]):
        if fr[b] < fr[a] or (a == "flicker_start" and fr[b] <= fr[a]) or (a == "swivel_start" and fr[b] <= fr[a]):
            fail.append("order: %s (%d) must not come after %s (%d)" % (a, fr[a], b, fr[b]))
    if fr["flicker_end"] > fr["swivel_start"]:
        fail.append("flicker-before-swivel: flicker_end %d > swivel_start %d" % (fr["flicker_end"], fr["swivel_start"]))
    if fr["music_start"] < 1:
        fail.append("unactivated: music_start at frame %d leaves no unlit opening frame" % fr["music_start"])
    if plan["curtain"]["release_s"] <= s["last_swell"]:
        fail.append("release-after-last-swell: release %.3f <= last_swell %.3f" % (plan["curtain"]["release_s"], s["last_swell"]))
    fq = float(cfg["rules"]["final_quarter_fraction"]) * plan["track_s"]
    if plan["curtain"]["release_s"] < fq - 1e-6:
        fail.append("release-in-final-quarter: release %.3f < final quarter %.3f" % (plan["curtain"]["release_s"], fq))
    if fr["swivel_end"] > fr["curtain_release"]:
        fail.append("swivel-before-release: swivel_end after curtain_release")
    if plan["curtain"]["landed_s"] > s["walkin_start"] + 1e-6:
        fail.append("landed-before-walkin: curtain lands %.3f after walk-in start %.3f" % (plan["curtain"]["landed_s"], s["walkin_start"]))
    wk = plan["walkin"]["keys"]
    end_s = fr["opening_end"] / fps
    if not wk or abs(wk[-1][0] - end_s) > 1e-9:
        fail.append("walkin-ends-at-p01-start: last key %.6f != opening_end %.6f" % (wk[-1][0] if wk else -1, end_s))
    if abs(plan["walkin"]["end_s"] - end_s) > 1e-9:
        fail.append("walkin-ends-at-p01-start: planner end %.6f != %.6f" % (plan["walkin"]["end_s"], end_s))
    for f in plan["walkin"]["failures"]:
        fail.append("walkin-check: " + f)
    if fr["opening_end"] < int(cfg["baseline"]["opening_end_frame"]):
        fail.append("shorter-than-today: opening_end %d < %d" % (fr["opening_end"], cfg["baseline"]["opening_end_frame"]))
    if plan["track_s"] > end_s + 1e-6:
        fail.append("music-fits: track %.3f s longer than the Opening %.3f s" % (plan["track_s"], end_s))
    for name, lamp in plan["lamps"].items():
        ik = lamp["intensity"]
        if any(v != 0.0 for f, v, _ in ik if f < fr["flicker_start"]):
            fail.append("unlit-before-music: %s is lit before flicker_start" % name)
        if any(b[0] <= a[0] for a, b in zip(ik, ik[1:])):
            fail.append("key-order: %s intensity frames not increasing" % name)
        if any(v < 0 for _, v, _ in ik):
            fail.append("negative-intensity: %s" % name)
        rot = lamp["rotation"]
        if rot:
            if rot[1][0] < lamp.get("flicker_end", fr["flicker_end"]):
                fail.append("flicker-before-swivel: %s swivels before its flicker ends" % name)
        lf_start = lamp.get("flicker_start", fr["flicker_start"])
        lf_end = lamp.get("flicker_end", fr["flicker_end"])
        if lf_end >= fr["swivel_end"]:
            fail.append("flicker-before-envelope: %s flicker_end %d >= swivel_end %d (flicker keys would interleave "
                        "with the envelope keys)" % (name, lf_end, fr["swivel_end"]))
        # Intensity cap (5 Oct). Outside the flicker window nothing may exceed the envelope peak (x nominal).
        # INSIDE the flicker window the cap is raised ONLY for the strobe style (flicker.peak_max present):
        # Gary 5 Oct ~15:15 asked for ~3x nominal pops there. The old stutter never exceeds idle_level.
        nominal = lamp.get("nominal_cd")
        if nominal:
            env_cap = max(float(cfg["envelope"]["peak"]), float(fl_cfg["idle_level"]))
            win_cap = float(fl_cfg["peak_max"]) if "peak_max" in fl_cfg else float(fl_cfg["idle_level"])
            for f, v, _ in ik:
                cap = win_cap if lf_start <= f < lf_end else env_cap
                if v > cap * nominal + 1e-6:
                    fail.append("intensity-cap: %s %.1f cd at frame %d > %.2f x nominal (%s)"
                                % (name, v, f, cap, "flicker window" if lf_start <= f < lf_end else "outside flicker"))
                    break
    if "peak_max" in fl_cfg and float(fl_cfg["peak_max"]) > FLICKER_PEAK_HARD_CAP:
        fail.append("flicker-peak-cap: peak_max %.2f > hard cap %.2f x nominal" % (float(fl_cfg["peak_max"]), FLICKER_PEAK_HARD_CAP))
    if "peak_max" in fl_cfg and float(fl_cfg["peak_min"]) > float(fl_cfg["peak_max"]):
        fail.append("flicker-peak-order: peak_min %.2f > peak_max %.2f" % (float(fl_cfg["peak_min"]), float(fl_cfg["peak_max"])))
    if plan["conflicts"]:
        fail.extend("marker-conflict: " + c for c in plan["conflicts"])
    tr = cfg["envelope"].get("trend")
    if tr:
        if fr[tr["from"]] >= fr[tr["to"]]:
            fail.append("trend-order: trend.from %s (%d) not before trend.to %s (%d)"
                        % (tr["from"], fr[tr["from"]], tr["to"], fr[tr["to"]]))
        if not 0.0 < float(tr["start"]) <= float(tr["end"]):
            fail.append("trend-rises: trend start %.3f / end %.3f must satisfy 0 < start <= end" % (tr["start"], tr["end"]))
    fail.extend(cone_check(cfg))
    fail.extend(house_warmer_check(cfg)[0])
    return fail


# --------------------------------------------------------------------------------------------- state algebra
def owned_state(plan, cfg):
    """The parts of the Opening the tool owns, as plain data (what APPLY writes; what read-back compares)."""
    return {
        "playback_end": plan["frames"]["opening_end"],
        "cut_end": plan["frames"]["opening_end"],
        "drape_spawn_end": plan["frames"]["opening_end"],
        "gc_sections": [list(x) for x in plan["curtain"]["sections"]],
        "walkin_keys": [list(k) for k in plan["walkin"]["keys"]],
        "markers": marker_list(plan),
        "rig": {n: {"intensity": [[f, round(v, 4), i] for f, v, i in l["intensity"]],
                    "rotation": [list(r) for r in l["rotation"]]} for n, l in plan["lamps"].items()},
        "music_on_opening": bool(cfg["music"]["move_p01_track_to_opening"]),
    }


def marker_list(plan):
    out = [[MARKER_PREFIX + n, plan["frames"][n]] for n in INPUT_MOMENTS + DERIVED_MOMENTS]
    for i, sw in enumerate(plan["swells"], 1):
        out.append([MARKER_PREFIX + "swell_%02d" % i, frame_of(sw["t"], plan["fps"])])
    return sorted(out, key=lambda x: (x[1], x[0]))


def apply_to_state(state, plan, cfg):
    """Pure model of APPLY on a snapshot dict (the live tool writes the same fields). Keeps non-OPN markers."""
    new = json.loads(json.dumps(state))
    target = owned_state(plan, cfg)
    for k in ("playback_end", "cut_end", "drape_spawn_end", "gc_sections", "walkin_keys", "rig", "music_on_opening"):
        new[k] = target[k]
    new["markers"] = sorted([m for m in state["markers"] if not m[0].startswith(MARKER_PREFIX)] + target["markers"],
                            key=lambda x: (x[1], x[0]))
    return new


def revert_state(state, original):
    """Pure model of REVERT: every owned field back to the first-apply snapshot; foreign markers kept."""
    new = json.loads(json.dumps(state))
    for k in ("playback_end", "cut_end", "drape_spawn_end", "gc_sections", "walkin_keys", "rig", "music_on_opening"):
        new[k] = json.loads(json.dumps(original[k]))
    foreign = [m for m in state["markers"] if not m[0].startswith(MARKER_PREFIX)]
    orig_opn = [m for m in original["markers"] if m[0].startswith(MARKER_PREFIX)]
    new["markers"] = sorted(foreign + orig_opn, key=lambda x: (x[1], x[0]))
    return new


def markers_to_moments(markers):
    out = {}
    for label, frame in markers:
        if label.startswith(MARKER_PREFIX):
            out[label[len(MARKER_PREFIX):]] = int(frame)
    return out


def track_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def default_paths(saved_dir):
    return {
        "timing": os.path.join(saved_dir, "CodexConductor", "opening_timing.json"),
        "record": os.path.join(saved_dir, "CodexConductor", "opening_sequence_record.json"),
        "walk_planner": os.path.join(saved_dir, "CodexCameraPilot", "walkin_plan.py"),
    }
