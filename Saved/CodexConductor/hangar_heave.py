"""HANGAR HEAVE: a heavy-heave motion profile for the hangar rise and the ceiling-rig (lattice) drop.
5 Oct, offline-written, NEVER RUN IN UNREAL.

Gary, 5 Oct (Docs/Conductor/GARY_PIE_NOTES_2026-10-05.md:126-130): "the rig currently comes up in a way that is nice but
far too smooth, same for the ceiling rig drop. It needs to have the movement curve of something hugely heavy being
wrenched up in a heave, its momentum shifting halfway through, falling forwards with a crunking thud."

Tiers per claim: [decl] declaration-proven (header/source/record we can read, cited), [prec] an in-repo precedent call
(cited), [meas] intervention + read-back, [inf] inferred (why stated).

WHAT MOVES (all in /Game/InfinityStage/RigAtmos/LS_S<n>_HangarRise):
  * root_pitch    binding "S<n> Hangar Root",        MovieScene3DTransformTrack, channel index 4 = Rotation.Y (pitch)
                  [decl InfinityStageArrival.cpp:333-345 TransformChannel(...,4,...); .cpp:88 "rotation XYZ (roll, pitch,
                  yaw)"]. Keys -90 -> 0, cubic [decl .cpp:561-565 ValidateStandardShape]; S1 measured
                  [[-5.8739,-90],[4.1261,0]] [meas Saved/CodexStructure/hangar_retime_record.json scenes.1.after_keys].
                  The Arrival's MotionBindingGuid must be this binding [decl .cpp:333-338] and it evaluates the SAME
                  channel before the Scene starts [decl InfinityStageArrival.h:104-116, .cpp:1127-1155], so the heave
                  plays across the Passage tail too.
  * lattice_fly_z binding "S<n> Hangar Lattice Fly", transform channel index 2 = Location.Z [decl .cpp:382-392];
                  keys 2800 (hold) -> 2800 -> 1200 = the "ceiling rig drop" [decl .cpp:579-580; hangar_build.py:10-11
                  "the working lattice (beams, three rails, bulbs ...) flown up at rest"; "ceiling rig" = lattice is inf].
  * roof_pitch    binding "S<n> Hangar Roof Hinge" (S6 has none), channel 4 [decl .cpp:355-380], -90,-90,0.
                  OPT-IN ONLY (params.channels): Gary named the rig and the ceiling rig, not the roof [inf].
  Timing after ATF apply 2 Oct: roof land..land+4.5, lattice land+4.5..land+8.5 [meas atf_hangar_timing_apply_record.json
  readback; S5 land 25.3].

MOTION WINDOW: the keys from the LAST key that still holds the first value to the LAST key (root: both keys; lattice:
  key 1 -> key 2; the 0 s hold before it is kept). Only keys strictly inside the window are replaced; the window's start
  and end keys keep their tick, sub-frame and value exactly, so land time, Strike After Land, roof/lattice timing, the
  Master and the drape release are unchanged [inf: they read key times, .cpp:648-674; passage_end_drape.py:230-241].

KEYS: DENSE LINEAR keys on every display frame of the rise sequence, not cubic keys with explicit tangents. Why:
  (1) the shape's point is its velocity discontinuities (the wrench, the winch catch, the thud); a cubic through sparse
  keys smooths exactly those, which is Gary's complaint; (2) linear keys need no tangent writes, and tangent setters are
  one more place UE can lie (memory "setters lie"); (3) at display rate dense-linear reproduces the profile exactly on
  every rendered frame; sub-frame (speed-dial) evaluation interpolates linearly between two frames [inf].
  The window start key becomes RCIM_LINEAR (its time/value untouched). Keys whose OUTWARD tangent the editor's
  auto-tangent pass might recompute [inf: AddKeyToChannel's body is private, memory ue58-engine-source-limits] are
  checked against the record and, if an AUTO key drifted, pinned to RCTM_USER with the recorded tangent (reported).

CONSEQUENCES (warnings in every DRY):
  * AInfinityStageArrival::ReadHangarTiming refuses non-2-key roots / non-3-key lattices [decl .cpp:654-668] and
    ApplyHangarTiming refuses non-standard shapes [decl .cpp:561-583]. After APPLY the Hangar Timing panel is LOCKED for
    that Scene (it refuses cleanly, nothing is corrupted) until REVERT. Retime first, heave last.
  * passage_end_drape.py rise_start_of() refuses a root with != 2 keys [decl passage_end_drape.py:230-233]: run the drape
    BEFORE the heave, or teach it to read the first key.
  * The visual thud (THUD_FRAME) lands land_time of the way through the window, BEFORE the last (land) key; lights strike
    StrikeAfterLand after the LAST key [decl InfinityStageArrival.h:35-42], i.e. after the bounce settles.

SHAKE (Gary, 5 Oct, second note): a seeded, deterministic tremor while wrenched up and a decaying burst from the THUD,
  added to the dense keys (params.shake, per channel; amp 0 = off). Bounds |tremor| <= tremor_amp, |burst| <= thud_amp,
  burst exactly 0 on and before the THUD key, partials under fps/2.5 are refused in DRY (check_shake).
  CAMERA SHAKE: NOT AUTHORED. At the THUD the live view is decided per Scene by its camera cuts, where nested shot cuts
  outrank root cuts [decl InfinityStageCameraPilotLibrary.h:125-129], or by the transport's Entry claim
  [decl InfinityStageTransportController.h:807-818]. Which camera is live at each Scene's THUD is unknown [inf]. Keying
  the Entry camera inside the rise would add a possessable whose transform keys are ABSOLUTE, so it would fight its
  owners. An offset needs an Additive transform section, and that is unverified in 5.8 Python [inf]. Route, if wanted: a
  read-only probe per Scene (CheckSceneCutBindings + the cut live at THUD_FRAME), then an Additive 3D-transform
  section on THAT camera in the Scene sequence, decided by Gary.

Modes (globals set by hangar_heave_run.py from hangar_heave_args.json):
  HANGAR_HEAVE_SCENE 1..6, HANGAR_HEAVE_MODE DRY|APPLY|REVERT, HANGAR_HEAVE_CONFIRM "<MODE> S<n>",
  HANGAR_HEAVE_PARAMS dict, HANGAR_HEAVE_DECIDED_BY (APPLY needs it), HANGAR_HEAVE_RUN_ID optional.
Markers: HANGAR_HEAVE_DRY_OK / HANGAR_HEAVE_APPLY_OK|run=..|scene=S<n>|channels=..|thud_frame=.. / HANGAR_HEAVE_REVERT_OK,
  or HANGAR_HEAVE_STOPPED|run=..|reason=... Touches ONLY LS_S<n>_HangarRise. Never Save All, never ends PIE, never opens
  or scrubs Sequencer, never reloads the level, no unreal objects in module globals. Importing without `unreal` runs
  nothing (test_hangar_heave.py).
"""
import copy
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


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # atf_hangar_timing_apply.py:28
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                     # passage_end_drape.py:70
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S%d_HangarRise"                       # atf_hangar_timing_apply.py:29-32
ARRIVAL_LABEL = "S%d Arrival"
SCENES = (1, 2, 3, 4, 5, 6)
RECORD_PATTERN = "hangar_heave_record_S%d.json"
DRY_PATTERN = "hangar_heave_dry_S%d.json"
TOOL = "hangar_heave"

CHANNEL_SPECS = {
    "root_pitch": {"binding": "S%d Hangar Root", "index": 4, "name": "Rotation.Y"},
    "lattice_fly_z": {"binding": "S%d Hangar Lattice Fly", "index": 2, "name": "Location.Z"},
    "roof_pitch": {"binding": "S%d Hangar Roof Hinge", "index": 4, "name": "Rotation.Y", "optional": True},
}
AUTO_MODES = ("RCTM_AUTO", "RCTM_SMART_AUTO")
VALUE_TOL = 1.0e-6          # deg / cm; doubles go in and come out as doubles
TANGENT_TOL = 1.0e-5        # tangents are float in the scripting API [decl MovieSceneScriptingDouble.h:116-151]

HEAVE = {           # the rise: hugely heavy, wrenched up, tips over the middle, falls forward onto its stop
    "dip": 0.01,            # settle/strain dip before lift (root: 0.9 deg below -90; see DRY warning DIP_BELOW_REST)
    "dip_end": 0.06,
    "heaves": 3,            # wrenched pulls, each followed by a winch-catch stall
    "heave_end": 0.40,
    "heave_gain": 0.30,     # progress reached after the heaves
    "heave_weights": [0.36, 0.34, 0.30],
    "heave_duty": 0.50,     # fraction of each heave cycle that is the steep wrench; the rest is the stall
    "hitch_creep": 0.03,    # fraction of each heave's gain crept during its stall (near-flat)
    "tip_time": 0.60,       # the balance point: the strained climb ends with almost no speed here
    "tip_progress": 0.45,
    "fall_power": 2.4,      # gravity-like ease-in past the balance point
    "land_time": 0.86,      # THUD: progress hits 1.0 at full speed
    "overshoot": 0.03,      # past the stop, then
    "bounces": 2,           # rebounds: + overshoot, - rebound, + , - ... (2*bounces lobes)
    "bounce_ratio": 0.45,   # each lobe vs the previous one
}
DROP = {            # the lattice: the brake lifts it a touch, it slips and catches, hangs, then lets go and thuds
    "dip": 0.02, "dip_end": 0.08, "heaves": 2, "heave_end": 0.34, "heave_gain": 0.22, "heave_weights": [0.5, 0.5],
    "heave_duty": 0.45, "hitch_creep": 0.03, "tip_time": 0.46, "tip_progress": 0.30, "fall_power": 2.4,
    "land_time": 0.80, "overshoot": 0.035, "bounces": 2, "bounce_ratio": 0.40,
}
# STRUCTURAL SHAKE (Gary, 5 Oct: "a little bit of shake, coming up and on landing thud"; and on the ceiling-rig drop).
# Added to the dense keys in the channel's own units (deg for pitch, cm for the lattice Z), so it is Master-time
# deterministic: keys, not runtime noise. Seeded sum of three sines (partials x1, ~x1.37, ~x1.91 of *_hz), normalised so
# |noise| <= 1. Tremor: full during each wrench, decaying through each stall (stall_decay_s), strain_level x during the
# dip and the strained climb, zero in the fall. Burst: starts at 0 ON the thud key (so the THUD key stays exactly the end
# value), thud_amp * exp(-3 dt / thud_decay_s). Both tapered to 0 over taper_s at the window ends. amp 0 = off.
SHAKE = {
    "root_pitch": {"seed": 5101, "tremor_amp": 0.10, "tremor_hz": 5.5, "stall_decay_s": 0.25, "strain_level": 0.4,
                   "thud_amp": 0.30, "thud_hz": 5.0, "thud_decay_s": 0.40, "taper_s": 0.10},
    "lattice_fly_z": {"seed": 5102, "tremor_amp": 1.5, "tremor_hz": 5.5, "stall_decay_s": 0.20, "strain_level": 0.3,
                      "thud_amp": 8.0, "thud_hz": 4.5, "thud_decay_s": 0.50, "taper_s": 0.10},
    "roof_pitch": {"seed": 5103, "tremor_amp": 0.05, "tremor_hz": 5.5, "stall_decay_s": 0.20, "strain_level": 0.3,
                   "thud_amp": 0.30, "thud_hz": 5.0, "thud_decay_s": 0.40, "taper_s": 0.10},
}
SHAKE_PARTIALS = ((1.0, 1.0), (1.37, 0.6), (1.91, 0.35))   # (frequency multiple, weight)
SHAKE_JITTER = 0.05                                       # seeded +- on each partial's multiple
SHAKE_MAX_FRACTION_OF_FPS = 1.0 / 2.5                     # highest partial must stay under fps/2.5 (no aliasing)

DEFAULTS = {
    "channels": ["root_pitch", "lattice_fly_z"],
    "profiles": {"root_pitch": "heave", "lattice_fly_z": "drop", "roof_pitch": "drop"},
    "heave": HEAVE,
    "drop": DROP,
    "thud_marker": False,           # optional "THUD hangar" marked frame in the rise at the root THUD_FRAME
    "marker_label": "THUD hangar",
    "map_dirty_policy": "stop",     # a dirty map after key edits = restore in memory and stop (nothing saved)
    "shake": SHAKE,
}
SHAPE_LIMITS = {"dip_min": 0.005, "dip_max": 0.02, "overshoot_max": 0.06, "hitch_ratio": 0.2, "tip_window": (0.4, 0.7)}


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure profile
# =====================================================================================================================

def merged_params(params):
    out = copy.deepcopy(DEFAULTS)
    for key, value in (params or {}).items():
        if key not in DEFAULTS:
            raise PlanError("UNKNOWN_PARAM: %s" % key)
        if key == "shake" and isinstance(value, dict):
            for chan, row in value.items():
                if chan not in SHAKE or not isinstance(row, dict):
                    raise PlanError("UNKNOWN_PARAM: shake.%s" % chan)
                for sub, v in row.items():
                    if sub not in SHAKE[chan]:
                        raise PlanError("UNKNOWN_PARAM: shake.%s.%s" % (chan, sub))
                    out["shake"][chan][sub] = v
            continue
        if isinstance(DEFAULTS[key], dict) and isinstance(value, dict):
            for sub, v in value.items():
                if sub not in DEFAULTS[key] and key not in ("profiles",):
                    raise PlanError("UNKNOWN_PARAM: %s.%s" % (key, sub))
                out[key][sub] = v
        else:
            out[key] = value
    for name in out["channels"]:
        if name not in CHANNEL_SPECS:
            raise PlanError("UNKNOWN_CHANNEL: %s" % name)
        if out["profiles"].get(name) not in ("heave", "drop"):
            raise PlanError("UNKNOWN_PROFILE: %s -> %r" % (name, out["profiles"].get(name)))
    if out["map_dirty_policy"] != "stop":
        raise PlanError("map_dirty_policy must be 'stop'")
    if str(out["marker_label"]).upper().startswith("GO"):
        raise PlanError("MARKER_NOT_GO_LESS: %r (a GO-prefixed marker would become a cue)" % out["marker_label"])
    return out


def params_digest(params):
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _bounce_amp(p):
    """Amplitude A so that the first lobe of A*exp(-d x) sin(w x) peaks at exactly `overshoot`."""
    w = math.pi * 2.0 * p["bounces"]
    d = -math.log(p["bounce_ratio"]) * 2.0 * p["bounces"]
    x_peak = math.atan2(w, d) / w
    return p["overshoot"] / (math.exp(-d * x_peak) * math.sin(w * x_peak)), w, d


def profile(u, p):
    """Normalised time u in [0, 1] -> progress (0 = start value, 1 = end value; may dip below 0 and overshoot 1)."""
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    if u < p["dip_end"]:                                            # strain / settle dip
        return -p["dip"] * math.sin(math.pi * u / p["dip_end"])
    if u < p["heave_end"]:                                          # wrenched heaves + winch-catch stalls
        n = int(p["heaves"])
        weights = [float(w) for w in p["heave_weights"][:n]]
        total = sum(weights)
        weights = [w / total for w in weights]
        cycle = (p["heave_end"] - p["dip_end"]) / n
        k = min(int((u - p["dip_end"]) / cycle), n - 1)
        x = (u - p["dip_end"] - k * cycle) / cycle
        base = p["heave_gain"] * sum(weights[:k])
        gain = p["heave_gain"] * weights[k]
        steep = gain * (1.0 - p["hitch_creep"])
        duty = p["heave_duty"]
        if x < duty:
            return base + steep * (1.0 - (1.0 - x / duty) ** 2)      # wrench: fast start, decelerating into the catch
        return base + steep + gain * p["hitch_creep"] * (x - duty) / (1.0 - duty)
    if u < p["tip_time"]:                                           # slow strained climb to the balance point
        x = (u - p["heave_end"]) / (p["tip_time"] - p["heave_end"])
        return p["heave_gain"] + (p["tip_progress"] - p["heave_gain"]) * math.sin(0.5 * math.pi * x)
    if u < p["land_time"]:                                          # momentum shift: falls forward under its weight
        x = (u - p["tip_time"]) / (p["land_time"] - p["tip_time"])
        return p["tip_progress"] + (1.0 - p["tip_progress"]) * x ** p["fall_power"]
    x = (u - p["land_time"]) / (1.0 - p["land_time"])               # THUD at x = 0, damped bounce, exact 1 at x = 1
    amp, w, d = _bounce_amp(p)
    return 1.0 + amp * math.exp(-d * x) * math.sin(w * x)


def smoothstep(u):
    """The current motion: two cubic AUTO keys with flat end tangents (ghost_geom.py:24 'AUTO = smoothstep' [prec])."""
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u)


def _partials(sh, base_hz, salt):
    """Deterministic (frequency Hz, weight, phase) triples from the seed. Pure; never touches global random state."""
    import random
    rng = random.Random("%s|%s" % (int(sh["seed"]), salt))
    out = []
    for mult, weight in SHAKE_PARTIALS:
        jitter = 1.0 + rng.uniform(-SHAKE_JITTER, SHAKE_JITTER) if mult != 1.0 else 1.0
        out.append((base_hz * mult * jitter, weight, rng.uniform(0.0, 2.0 * math.pi)))
    return out


def _noise(t, partials, zero_phase=False):
    """Normalised so |noise| <= 1."""
    total = sum(w for _f, w, _p in partials)
    return sum(w * math.sin(2.0 * math.pi * f * t + (0.0 if zero_phase else ph)) for f, w, ph in partials) / total


def tremor_envelope(u, p, window_s, sh):
    """0..1. Full during each wrench, exp decay through each stall, strain_level in the dip and the climb, 0 after."""
    if u <= 0.0 or u >= p["tip_time"]:
        return 0.0
    if u < p["dip_end"] or u >= p["heave_end"]:
        return float(sh["strain_level"])
    n = int(p["heaves"])
    cycle = (p["heave_end"] - p["dip_end"]) / n
    k = min(int((u - p["dip_end"]) / cycle), n - 1)
    x = (u - p["dip_end"] - k * cycle) / cycle
    if x < p["heave_duty"]:
        return 1.0
    stall_s = (x - p["heave_duty"]) * cycle * window_s
    return math.exp(-3.0 * stall_s / max(float(sh["stall_decay_s"]), 1e-6))


def shake_at(u, p, window_s, sh):
    """(tremor, burst) in channel units at normalised time u of a window lasting window_s seconds. Pure."""
    if not sh or u <= 0.0 or u >= 1.0:
        return 0.0, 0.0
    t = u * window_s
    taper = max(0.0, min(1.0, t / max(sh["taper_s"], 1e-6), (window_s - t) / max(sh["taper_s"], 1e-6)))
    tremor = 0.0
    if sh["tremor_amp"]:
        tremor = (sh["tremor_amp"] * taper * tremor_envelope(u, p, window_s, sh)
                  * _noise(t, _partials(sh, sh["tremor_hz"], "tremor")))
    burst = 0.0
    if sh["thud_amp"] and u > p["land_time"]:
        dt = (u - p["land_time"]) * window_s
        burst = (sh["thud_amp"] * taper * math.exp(-3.0 * dt / max(sh["thud_decay_s"], 1e-6))
                 * _noise(dt, _partials(sh, sh["thud_hz"], "thud"), zero_phase=True))
    return tremor, burst


def check_shake(plan, sh):
    """Failures of a planned channel's shake layer: bounds, the zero at the THUD key, presence, aliasing, decay."""
    out = []
    if not sh:
        return out
    fps = float(plan["fps"])
    for label, hz in (("tremor", sh["tremor_hz"]), ("thud", sh["thud_hz"])):
        top = max(f for f, _w, _p in _partials(sh, hz, label))
        if top > fps * SHAKE_MAX_FRACTION_OF_FPS:
            out.append("SHAKE_ALIASING: %s partial %.2f Hz > %.2f Hz at %g fps"
                       % (label, top, fps * SHAKE_MAX_FRACTION_OF_FPS, fps))
    for amp in ("tremor_amp", "thud_amp"):
        if float(sh[amp]) < 0.0:
            out.append("SHAKE_NEGATIVE_AMP: %s" % amp)
    tr = [abs(d.get("tremor", 0.0)) for d in plan["dense"]]
    bu = [abs(d.get("burst", 0.0)) for d in plan["dense"]]
    if tr and max(tr) > abs(sh["tremor_amp"]) + 1e-12:
        out.append("SHAKE_TREMOR_BOUND: %.6f > %.6f" % (max(tr), sh["tremor_amp"]))
    if bu and max(bu) > abs(sh["thud_amp"]) + 1e-12:
        out.append("SHAKE_THUD_BOUND: %.6f > %.6f" % (max(bu), sh["thud_amp"]))
    for d in plan["dense"]:
        if abs(d.get("tremor", 0.0) + d.get("burst", 0.0) - d.get("shake", 0.0)) > 1e-12 or \
                abs(d.get("base", d["value"]) + d.get("shake", 0.0) - d["value"]) > 1e-9:
            out.append("SHAKE_SUM@%d" % d["tick"])
            break
        if d["tick"] <= plan["thud_tick"] and d.get("burst", 0.0) != 0.0:
            out.append("SHAKE_BURST_BEFORE_THUD@%d" % d["tick"])
            break
        if d["tick"] == plan["thud_tick"] and d.get("shake", 0.0) != 0.0:
            out.append("SHAKE_AT_THUD_KEY: %.6f (the THUD key must be exactly the end value)" % d["shake"])
    if sh["thud_amp"] and max(bu or [0.0]) < 0.25 * sh["thud_amp"]:
        out.append("SHAKE_THUD_ABSENT: peak %.6f" % max(bu or [0.0]))
    if sh["tremor_amp"] and max(tr or [0.0]) < 0.25 * sh["tremor_amp"]:
        out.append("SHAKE_TREMOR_ABSENT: peak %.6f" % max(tr or [0.0]))
    late = [abs(d.get("burst", 0.0)) for d in plan["dense"]
            if d["tick"] > plan["thud_tick"] + 2.0 * sh["thud_decay_s"] * plan["tick_rate"]]
    if late and max(late) > 0.01 * abs(sh["thud_amp"]) + 1e-12:
        out.append("SHAKE_NOT_DECAYED: %.6f two decay times after the thud" % max(late))
    return out


def check_shape(fn, p, samples=4001):
    """Failures of a profile function against the heave contract. fn(u) -> progress; p = its parameter set."""
    out = []
    us = [i / (samples - 1.0) for i in range(samples)]
    ys = [fn(u) for u in us]
    if abs(ys[0]) > 1e-12 or abs(ys[-1] - 1.0) > 1e-12:
        out.append("ENDPOINTS: p(0)=%r p(1)=%r" % (ys[0], ys[-1]))
    lo = min(ys[: int(p["dip_end"] * samples) + 1] or [0.0])
    if not (-SHAPE_LIMITS["dip_max"] - 1e-12 <= lo <= -SHAPE_LIMITS["dip_min"] + 1e-12):
        out.append("DIP: min %.4f before lift, want -%.3f..-%.3f" % (lo, SHAPE_LIMITS["dip_max"], SHAPE_LIMITS["dip_min"]))
    mono = [(u, y) for u, y in zip(us, ys) if p["dip_end"] <= u <= p["land_time"]]
    for (u0, y0), (u1, y1) in zip(mono, mono[1:]):
        if y1 < y0 - 1e-12:
            out.append("NOT_MONOTONE: falls at u=%.4f between lift and landing" % u1)
            break
    if not 2 <= int(p["heaves"]) <= 3:
        out.append("HEAVE_COUNT: %r, want 2-3" % p["heaves"])
    # hitches: inside each heave cycle the stall's mean slope must be < hitch_ratio of the wrench's
    n = max(1, int(p["heaves"]))
    cycle = (p["heave_end"] - p["dip_end"]) / n
    stalls = 0
    for k in range(n):
        a = p["dip_end"] + k * cycle
        m = a + p["heave_duty"] * cycle
        b = a + cycle
        s_w = (fn(m) - fn(a)) / (m - a)
        s_s = (fn(b - 1e-9) - fn(m)) / (b - 1e-9 - m)
        if s_w > 0 and 0 <= s_s < SHAPE_LIMITS["hitch_ratio"] * s_w:
            stalls += 1
    if stalls < 2:
        out.append("HITCHES: %d wrench-then-stall cycles, want >= 2" % stalls)
    t0, t1 = SHAPE_LIMITS["tip_window"]
    if not t0 <= p["tip_time"] <= t1:
        out.append("TIP_NOT_MIDWAY: tip_time %.3f" % p["tip_time"])
    # momentum shift: speed just before the tip is far below the speed just before landing, and the fall accelerates
    eps = 0.004
    v_tip = (fn(p["tip_time"]) - fn(p["tip_time"] - eps)) / eps
    v_land = (fn(p["land_time"] - 1e-9) - fn(p["land_time"] - eps)) / (eps - 1e-9)
    v_mid = (fn(0.5 * (p["tip_time"] + p["land_time"])) - fn(0.5 * (p["tip_time"] + p["land_time"]) - eps)) / eps
    if not (v_tip < v_mid < v_land and v_land > 3.0 * max(v_tip, 1e-9)):
        out.append("NO_MOMENTUM_SHIFT: speed tip %.3f / mid-fall %.3f / landing %.3f" % (v_tip, v_mid, v_land))
    if abs(fn(p["land_time"]) - 1.0) > 1e-12:
        out.append("LANDING_FRAME: p(land_time)=%r, want exactly 1" % fn(p["land_time"]))
    speeds = [(y1 - y0) / (u1 - u0) for (u0, y0), (u1, y1) in zip(zip(us, ys), zip(us[1:], ys[1:]))]
    i_max = max(range(len(speeds)), key=lambda i: speeds[i])
    if abs(us[i_max + 1] - p["land_time"]) > 2.0 / samples:
        out.append("THUD_NOT_FASTEST: peak speed at u=%.4f, landing at %.4f" % (us[i_max + 1], p["land_time"]))
    hi = max(ys)
    if hi > 1.0 + min(p["overshoot"], SHAPE_LIMITS["overshoot_max"]) + 1e-9 or hi > 1.0 + SHAPE_LIMITS["overshoot_max"]:
        out.append("OVERSHOOT_BOUND: max %.4f" % hi)
    if hi < 1.0 + 0.5 * p["overshoot"] or p["overshoot"] <= 0:
        out.append("NO_OVERSHOOT: max %.4f" % hi)
    tail = [y - 1.0 for u, y in zip(us, ys) if u > p["land_time"] + 1e-9 and u < 1.0]
    flips = sum(1 for a, b in zip(tail, tail[1:]) if (a > 0) != (b > 0) and abs(a) + abs(b) > 1e-9)
    if not 1 <= flips <= 4 or not tail or min(tail) >= 0:
        out.append("REBOUNDS: %d sign changes after landing, want 1-4 with one below the stop" % flips)
    return out


# =====================================================================================================================
# Pure key planning (keys are dicts: tick, sub, value, interp, tangent_mode, arrive, leave, weight_mode, arrive_w,
# leave_w; ticks in the rise's tick resolution)
# =====================================================================================================================

KEY_FIELDS = ("tick", "sub", "value", "interp", "tangent_mode", "arrive", "leave", "weight_mode", "arrive_w", "leave_w")


def window_of(keys):
    """(i0, i1): the last key still holding the first value, and the last key."""
    if len(keys) < 2:
        raise PlanError("TOO_FEW_KEYS: %d" % len(keys))
    ticks = [k["tick"] for k in keys]
    if ticks != sorted(ticks) or len(set(ticks)) != len(ticks):
        raise PlanError("KEYS_NOT_STRICTLY_SORTED")
    v0 = keys[0]["value"]
    i0 = 0
    while i0 + 1 < len(keys) and abs(keys[i0 + 1]["value"] - v0) <= VALUE_TOL:
        i0 += 1
    i1 = len(keys) - 1
    if i0 >= i1 or abs(keys[i1]["value"] - keys[i0]["value"]) <= VALUE_TOL:
        raise PlanError("NO_MOTION_WINDOW: values %r" % [k["value"] for k in keys])
    return i0, i1


def frame_tick(frame, tick_rate, fps):
    return int(round(frame * float(tick_rate) / float(fps)))


def plan_channel(name, keys, prof, tick_rate, fps, shake=None):
    """The dense-linear rewrite of one channel's motion window. Pure."""
    keys = sorted(keys, key=lambda k: k["tick"])
    i0, i1 = window_of(keys)
    a, b = keys[i0], keys[i1]
    if a.get("sub") or b.get("sub"):
        raise PlanError("SUBFRAME_ENDPOINT: %s" % name)
    t0, t1, v0, v1 = a["tick"], b["tick"], a["value"], b["value"]
    per = float(tick_rate) / float(fps)
    f_lo = int(math.floor(t0 / per)) + 1
    f_hi = int(math.ceil(t1 / per)) - 1
    frames = [f for f in range(f_lo - 1, f_hi + 2) if t0 < frame_tick(f, tick_rate, fps) < t1]
    if len(frames) < 20:
        raise PlanError("WINDOW_TOO_SHORT: %s has %d frames" % (name, len(frames)))
    target = t0 + prof["land_time"] * (t1 - t0)
    f_thud = min(frames, key=lambda f: abs(frame_tick(f, tick_rate, fps) - target))
    p = dict(prof)
    p["land_time"] = (frame_tick(f_thud, tick_rate, fps) - t0) / float(t1 - t0)
    if not p["tip_time"] < p["land_time"] < 1.0:
        raise PlanError("THUD_OUTSIDE_FALL: %s" % name)
    window_s = (t1 - t0) / float(tick_rate)
    dense = []
    for f in frames:
        tick = frame_tick(f, tick_rate, fps)
        u = (tick - t0) / float(t1 - t0)
        tremor, burst = shake_at(u, p, window_s, shake)
        base = v0 + profile(u, p) * (v1 - v0)
        dense.append({"tick": tick, "value": base + tremor + burst, "frame": f, "base": base,
                      "tremor": tremor, "burst": burst, "shake": tremor + burst})
    return {"channel": name, "i0": i0, "i1": i1, "t0": t0, "t1": t1, "v0": v0, "v1": v1,
            "interior": [copy.deepcopy(k) for k in keys[i0 + 1:i1]], "dense": dense,
            "thud_tick": frame_tick(f_thud, tick_rate, fps), "thud_frame": f_thud,
            "thud_s": frame_tick(f_thud, tick_rate, fps) / float(tick_rate), "land_time_eff": p["land_time"],
            "profile": p, "shake": copy.deepcopy(shake) if shake else None, "fps": fps, "tick_rate": tick_rate}


def _relevant(keys, i):
    """Which tangents of keys[i] shape the curve: arrive if the previous key is cubic, leave if this key is cubic and
    a key follows."""
    arrive = i > 0 and keys[i - 1]["interp"] == "RCIM_CUBIC"
    leave = keys[i]["interp"] == "RCIM_CUBIC" and i + 1 < len(keys)
    return arrive, leave


def expected_after(before, plan):
    """The key list APPLY must produce (tangent fields only where they matter). Pure."""
    before = sorted(before, key=lambda k: k["tick"])
    out = [copy.deepcopy(k) for k in before[:plan["i0"]]]
    start = copy.deepcopy(before[plan["i0"]])
    start["interp"] = "RCIM_LINEAR"
    out.append(start)
    for d in plan["dense"]:
        out.append({"tick": d["tick"], "sub": 0.0, "value": d["value"], "interp": "RCIM_LINEAR"})
    out.extend(copy.deepcopy(k) for k in before[plan["i1"]:])
    return out


def compare_keys(live, want, check_all_tangents=False):
    """Failures between a live key list and a wanted one. Tangents are compared only where they shape the curve in
    `want` unless check_all_tangents (revert exactness)."""
    out = []
    live = sorted(live, key=lambda k: k["tick"])
    want = sorted(want, key=lambda k: k["tick"])
    if [k["tick"] for k in live] != [k["tick"] for k in want]:
        lt, wt = {k["tick"] for k in live}, {k["tick"] for k in want}
        return ["KEY_TICKS: %d live vs %d wanted; missing %r extra %r"
                % (len(live), len(want), sorted(wt - lt)[:4], sorted(lt - wt)[:4])]
    for i, (l, w) in enumerate(zip(live, want)):
        if abs(float(l.get("sub", 0.0)) - float(w.get("sub", 0.0))) > 1e-9:
            out.append("KEY_SUBFRAME@%d" % w["tick"])
        if abs(l["value"] - w["value"]) > VALUE_TOL:
            out.append("KEY_VALUE@%d: %.9f want %.9f" % (w["tick"], l["value"], w["value"]))
        if l["interp"] != w["interp"]:
            out.append("KEY_INTERP@%d: %s want %s" % (w["tick"], l["interp"], w["interp"]))
        if check_all_tangents:
            for f in ("tangent_mode", "weight_mode"):
                if w.get(f) is not None and l.get(f) != w.get(f):
                    out.append("KEY_%s@%d: %s want %s" % (f.upper(), w["tick"], l.get(f), w.get(f)))
            names = ("arrive", "leave", "arrive_w", "leave_w")
        else:
            arrive, leave = _relevant(want, i)
            names = (("arrive", "arrive_w") if arrive else ()) + (("leave", "leave_w") if leave else ())
        for f in names:
            if w.get(f) is None:
                continue
            if abs(float(l.get(f, 0.0)) - float(w[f])) > TANGENT_TOL:
                out.append("KEY_%s@%d: %.7f want %.7f" % (f.upper(), w["tick"], l.get(f, 0.0), w[f]))
    return out


def endpoint_gate(before, after, plan):
    """Window endpoints and every key outside the window must keep tick/sub/value exactly."""
    out = []
    before = sorted(before, key=lambda k: k["tick"])
    keep = before[:plan["i0"] + 1] + before[plan["i1"]:]
    live = {k["tick"]: k for k in after}
    for k in keep:
        l = live.get(k["tick"])
        if l is None:
            out.append("ENDPOINT_MOVED: key at tick %d is gone" % k["tick"])
        elif abs(l["value"] - k["value"]) > 0.0 or float(l.get("sub", 0.0)) != float(k.get("sub", 0.0)):
            out.append("ENDPOINT_VALUE: tick %d %.9f -> %.9f" % (k["tick"], k["value"], l["value"]))
    a = min(k["tick"] for k in after)
    z = max(k["tick"] for k in after)
    if a != before[0]["tick"] or z != before[-1]["tick"]:
        out.append("SPAN_CHANGED: [%d, %d] -> [%d, %d]" % (before[0]["tick"], before[-1]["tick"], a, z))
    return out


def tangent_pins(before, after_live, plan):
    """Preserved AUTO keys whose shape-relevant tangent the editor recomputed -> [(tick, fields)] to pin as USER."""
    want = expected_after(before, plan)
    by_tick = {k["tick"]: k for k in after_live}
    pins, bad = [], []
    for i, w in enumerate(want):
        if "tangent_mode" not in w:
            continue                                    # a dense key
        l = by_tick.get(w["tick"])
        if l is None:
            continue
        arrive, leave = _relevant(want, i)
        drift = [f for f, on in (("arrive", arrive), ("leave", leave)) if on and abs(l[f] - w[f]) > TANGENT_TOL]
        if not drift:
            continue
        if w["tangent_mode"] in AUTO_MODES:
            pins.append((w["tick"], {"tangent_mode": "RCTM_USER", "arrive": w["arrive"], "leave": w["leave"]}))
        else:
            bad.append("TANGENT_DRIFT_ON_%s@%d: %r" % (w["tangent_mode"], w["tick"], drift))
    return pins, bad


def range_gate(before, after):
    out = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            out.append("RANGE_CHANGED: %s %r -> %r" % (key, before.get(key), after.get(key)))
    return out


def live_gates(state):
    """Refusals from editor state: mode, scene, confirm, pie, sequencer_open, census, record_exists, record_applied,
    decided_by, problems."""
    r = []
    mode, n = str(state.get("mode")), state.get("scene")
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % mode)
    if n not in SCENES:
        r.append("SCENE_OUT_OF_SCOPE: %r" % (n,))
    if state.get("confirm") != "%s S%s" % (mode, n):
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s S%s" % (mode, n)))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode in ("DRY", "APPLY") and state.get("record_exists"):
        r.append("RECORD_EXISTS: REVERT first, or archive a stale record by hand")
    if mode == "APPLY" and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    for why in state.get("problems", []):
        r.append(why)
    return r


def plan_scene(channels, params, tick_rate, fps):
    """channels: {name: keys}. Returns (plans, refusals, warnings)."""
    plans, refusals, warnings = {}, [], []
    for name in params["channels"]:
        if name not in channels:
            if CHANNEL_SPECS[name].get("optional"):
                warnings.append("CHANNEL_ABSENT: %s (S6 has no roof hinge)" % name)
                continue
            refusals.append("CHANNEL_MISSING: %s" % name)
            continue
        prof = params[params["profiles"][name]]
        try:
            plan = plan_channel(name, channels[name], prof, tick_rate, fps, (params.get("shake") or {}).get(name))
        except PlanError as exc:
            refusals.append("PLAN_%s: %s" % (name, exc))
            continue
        for f in check_shape(lambda u, p=plan["profile"]: profile(u, p), plan["profile"]):
            refusals.append("SHAPE_%s: %s" % (name, f))
        refusals.extend("SHAKE_%s: %s" % (name, f) for f in check_shake(plan, plan["shake"]))
        bad = endpoint_gate(channels[name], expected_after(channels[name], plan), plan)
        refusals.extend("MODEL_%s: %s" % (name, f) for f in bad)
        plans[name] = plan
    root = plans.get("root_pitch")
    if root and root["v1"] > root["v0"]:
        dip_deg = params[params["profiles"]["root_pitch"]]["dip"] * (root["v1"] - root["v0"])
        warnings.append("DIP_BELOW_REST: root pitch dips %.2f deg below %.1f before lifting; at 60 m depth the far edge "
                        "moves %.0f cm (check floor clipping in the first live preview)"
                        % (dip_deg, root["v0"], 6000.0 * math.sin(math.radians(dip_deg))))
    for name, plan in plans.items():
        warnings.append("THUD_BEFORE_LAND_KEY: %s thud at %.3f s, land key at %.3f s (bounce settles in between)"
                        % (name, plan["thud_s"], plan["t1"] / float(tick_rate)))
    warnings.append("ARRIVAL_TIMING_LOCK: Read/ApplyHangarTiming refuse after APPLY (InfinityStageArrival.cpp:561-583, "
                    "654-668) until REVERT")
    warnings.append("DRAPE_TWO_KEY_GATE: passage_end_drape.py:230-233 refuses a root with != 2 keys after APPLY")
    return plans, refusals, warnings


# =====================================================================================================================
# Channel writers (adapter: read() -> keys, remove_ticks(set), add(tick, value), set_fields(tick, dict))
# =====================================================================================================================

def write_channel(adapter, before, plan):
    """APPLY one channel. Returns (live_after, pins_applied, failures)."""
    before = sorted(before, key=lambda k: k["tick"])
    adapter.remove_ticks({k["tick"] for k in plan["interior"]})
    adapter.set_fields(plan["t0"], {"interp": "RCIM_LINEAR"})
    for d in plan["dense"]:
        adapter.add(d["tick"], d["value"])
    pins, bad = tangent_pins(before, adapter.read(), plan)
    for tick, fields in pins:
        adapter.set_fields(tick, fields)
    live = adapter.read()
    want = expected_after(before, plan)
    for tick, fields in pins:
        for w in want:
            if w["tick"] == tick:
                w.update(fields)
    failures = bad + compare_keys(live, want) + endpoint_gate(before, live, plan)
    return live, pins, failures


def restore_channel(adapter, original):
    """REVERT one channel to the recorded keys exactly. Returns failures (empty = exact)."""
    original = sorted(original, key=lambda k: k["tick"])
    keep = {k["tick"] for k in original}
    live = adapter.read()
    adapter.remove_ticks({k["tick"] for k in live if k["tick"] not in keep})
    have = {k["tick"] for k in adapter.read()}
    for k in original:
        if k["tick"] not in have:
            adapter.add(k["tick"], k["value"])
    for _ in range(2):          # second pass: undo anything a later write's auto-tangent pass recomputed
        live = {k["tick"]: k for k in adapter.read()}
        for k in original:
            l = live[k["tick"]]
            if any(l.get(f) != k.get(f) if f in ("interp", "tangent_mode", "weight_mode")
                   else abs(float(l.get(f, 0.0)) - float(k[f])) > TANGENT_TOL
                   for f in ("interp", "tangent_mode", "weight_mode", "arrive", "leave", "arrive_w", "leave_w")):
                adapter.set_fields(k["tick"], {f: k[f] for f in ("interp", "tangent_mode", "weight_mode", "arrive",
                                                                  "leave", "arrive_w", "leave_w")})
    return compare_keys(adapter.read(), original, check_all_tangents=True)


def drift(live_channels, record):
    out = []
    for name, row in record["channels"].items():
        if name not in live_channels:
            out.append("CHANNEL_GONE: %s" % name)
            continue
        out.extend("%s: %s" % (name, f) for f in compare_keys(live_channels[name], row["keys_after"],
                                                               check_all_tangents=True))
    return out


def new_record(n, run, params, rise_info, channels, plans, decided_by, backup):
    return {"schema": 1, "tool": TOOL, "run": run, "scene": n, "world": EXPECTED_WORLD, "rise": RISE_PATH % n,
            "decided_by": decided_by, "params": params, "params_digest": params_digest(params), "backup": backup,
            "rise_info": rise_info, "applied": False, "marker_added": None,
            "written": datetime.datetime.now().isoformat(timespec="seconds"),
            "channels": {name: {"keys_before": channels[name], "keys_after": None, "pins": [],
                                "plan": {k: v for k, v in plans[name].items() if k != "dense"},
                                "dense_count": len(plans[name]["dense"])}
                         for name in plans}}


def write_record_exclusive(path, data):
    """Create-only (refuses if it exists), flushed and fsynced BEFORE any mutation."""
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


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _stop(run, reason):
    unreal.log_error("HANGAR_HEAVE_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():   # curtain_sleight.py:1004-1006 [prec]
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _content_file(path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ".uasset"


class _LiveChannel(object):
    """Adapter over a MovieSceneScriptingDoubleChannel [decl MovieSceneScriptingDouble.h:50-218, 245-290]."""

    def __init__(self, channel):
        self.channel = channel

    def _rows(self):
        rows = []
        for key in self.channel.get_keys():
            t = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
            rows.append((key, {"tick": int(t.frame_number.value), "sub": float(getattr(t, "sub_frame", 0.0)),
                               "value": float(key.get_value()), "interp": key.get_interpolation_mode().name,
                               "tangent_mode": key.get_tangent_mode().name, "arrive": float(key.get_arrive_tangent()),
                               "leave": float(key.get_leave_tangent()), "weight_mode": key.get_tangent_weight_mode().name,
                               "arrive_w": float(key.get_arrive_tangent_weight()),
                               "leave_w": float(key.get_leave_tangent_weight())}))
        rows.sort(key=lambda r: r[1]["tick"])
        return rows

    def read(self):
        return [r[1] for r in self._rows()]

    def remove_ticks(self, ticks):
        for key, row in self._rows():
            if row["tick"] in ticks:
                self.channel.remove_key(key)

    def add(self, tick, value):
        made = self.channel.add_key(unreal.FrameNumber(int(tick)), float(value), sub_frame=0.0,
                                    time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
                                    interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        if made is None:
            raise RuntimeError("ADD_KEY_NONE@%d" % tick)

    def set_fields(self, tick, fields):
        hits = [key for key, row in self._rows() if row["tick"] == tick]
        if len(hits) != 1:
            raise RuntimeError("SET_FIELDS_KEY_COUNT@%d: %d" % (tick, len(hits)))
        key = hits[0]
        if "interp" in fields:
            key.set_interpolation_mode(getattr(unreal.RichCurveInterpMode, fields["interp"]))
        if "tangent_mode" in fields:
            key.set_tangent_mode(getattr(unreal.RichCurveTangentMode, fields["tangent_mode"]))
        if "weight_mode" in fields:
            key.set_tangent_weight_mode(getattr(unreal.RichCurveTangentWeightMode, fields["weight_mode"]))
        for f, setter in (("arrive", "set_arrive_tangent"), ("leave", "set_leave_tangent"),
                          ("arrive_w", "set_arrive_tangent_weight"), ("leave_w", "set_leave_tangent_weight")):
            if f in fields:
                getattr(key, setter)(float(fields[f]))


def _channel_name(channel):
    return str(channel.channel_name) if hasattr(channel, "channel_name") else str(channel.get_name())


def _gather(n, run, params):
    """Live facts as plain data + local handles. Read-only."""
    problems, warnings = [], []
    rise = unreal.load_asset(RISE_PATH % n)
    if rise is None:
        _stop(run, "RISE_MISSING|%s" % (RISE_PATH % n))
    tick = rise.get_tick_resolution()
    tick_rate = tick.numerator / float(tick.denominator)
    rate = rise.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    bindings = {}
    for b in rise.get_bindings():
        bindings.setdefault(str(b.get_display_name()), []).append(b)
    channels, sections, handles, meta = {}, {}, {}, {}
    for name, spec in CHANNEL_SPECS.items():
        label = spec["binding"] % n
        rows = bindings.get(label, [])
        if not rows:
            if not spec.get("optional"):
                problems.append("BINDING_MISSING: %s" % label)
            continue
        if len(rows) != 1:
            problems.append("BINDING_COUNT: %s %d" % (label, len(rows)))
            continue
        tracks = [t for t in rows[0].get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)]
        secs = [s for t in tracks for s in t.get_sections()]
        if len(tracks) != 1 or len(secs) != 1:
            problems.append("TRANSFORM_SECTION_COUNT: %s tracks=%d sections=%d" % (label, len(tracks), len(secs)))
            continue
        chans = list(secs[0].get_all_channels())
        if len(chans) <= spec["index"]:
            problems.append("CHANNEL_INDEX: %s has %d channels" % (label, len(chans)))
            continue
        ch = chans[spec["index"]]
        cname = _channel_name(ch)
        if not (cname == spec["name"] or cname.startswith(spec["name"] + "_")):     # memory: Location.Y_183, not .Y
            problems.append("CHANNEL_NAME: %s[%d] is %r, want %s" % (label, spec["index"], cname, spec["name"]))
            continue
        channels[name] = _LiveChannel(ch).read()
        handles[name] = (secs[0], ch)
        s = secs[0]
        sections[name] = [bool(s.has_start_frame()), int(s.get_start_frame()) if s.has_start_frame() else None,
                          bool(s.has_end_frame()), int(s.get_end_frame()) if s.has_end_frame() else None]
        meta[name] = {"binding": label, "binding_guid": _guid(rows[0].get_id()), "channel_name": cname,
                      "channel_index": spec["index"]}
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    arrivals = [a for a in actors if str(a.get_actor_label()) == ARRIVAL_LABEL % n]
    scene_seq = None
    if len(arrivals) != 1:
        problems.append("ARRIVAL_COUNT: %d" % len(arrivals))
    else:
        arrival = arrivals[0]
        motion = arrival.get_editor_property("motion_sequence")
        if motion is None or motion.get_path_name().split(".")[0] != RISE_PATH % n:
            problems.append("ARRIVAL_MOTION_SEQUENCE: %r" % (motion.get_path_name() if motion else None))
        if "root_pitch" in meta and _guid(arrival.get_editor_property("motion_binding_guid")) != meta["root_pitch"]["binding_guid"]:
            problems.append("ARRIVAL_ROOT_BINDING: MotionBindingGuid is not %s" % meta["root_pitch"]["binding"])
        show = unreal.load_asset(SHOW_PATH)
        cue_guid = _guid(arrival.get_editor_property("scene_cue_guid"))
        cues = [c for c in show.get_editor_property("cues") if _guid(c.get_editor_property("cue_guid")) == cue_guid] if show else []
        if len(cues) == 1:
            scene_seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
        else:
            warnings.append("SCENE_CUE_NOT_FOUND: audio check covers the rise only")
    audio = []
    for label, seq in (("rise", rise), ("scene", scene_seq)):
        if seq is None:
            continue
        for t in seq.find_tracks_by_type(unreal.MovieSceneAudioTrack):
            audio.append({"in": label, "sequence": seq.get_path_name().split(".")[0], "track": str(t.get_display_name()),
                          "sections": len(t.get_sections())})
    markers = [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)]
               for m in rise.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)]  # curtain_sleight.py:1043
    rise_info = {"tick_rate": tick_rate, "fps": fps, "playback": [int(rise.get_playback_start()), int(rise.get_playback_end())],
                 "sections": sections, "markers": markers, "audio_tracks": audio, "channel_meta": meta}
    return channels, rise_info, problems, warnings, {"rise": rise, "chan": handles}


def _ranges(rise, handles):
    out = {"playback": [int(rise.get_playback_start()), int(rise.get_playback_end())]}
    for name, (s, _ch) in handles.items():
        out["section:" + name] = [bool(s.has_start_frame()), int(s.get_start_frame()) if s.has_start_frame() else None,
                                  bool(s.has_end_frame()), int(s.get_end_frame()) if s.has_end_frame() else None]
    return out


def _backup(run, n, suffix):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "PreHangarHeave-S%d-%s%s" % (n, run, suffix))
    os.makedirs(folder, exist_ok=False)
    src = _content_file(RISE_PATH % n)
    if not os.path.isfile(src):
        _stop(run, "BACKUP_SOURCE_MISSING|" + src)
    dst = os.path.join(folder, os.path.basename(src))
    shutil.copy2(src, dst)
    digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
    if digest[0] != digest[1]:
        _stop(run, "BACKUP_HASH_MISMATCH|" + src)
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "asset": RISE_PATH % n, "source": src, "backup": dst, "sha256": digest[1]}, handle, indent=1)
    return folder


def _report(n, run, params, channels, rise_info, problems, warnings, plans, refusals):
    return {"tool": TOOL, "run": run, "scene": n, "params": params, "params_digest": params_digest(params),
            "rise": RISE_PATH % n, "rise_info": rise_info, "refusals": problems + refusals, "warnings": warnings,
            "apply_ready": not (problems or refusals),
            "channels": {name: {"keys_before": channels.get(name),
                                "window": [plans[name]["t0"], plans[name]["t1"]] if name in plans else None,
                                "values": [plans[name]["v0"], plans[name]["v1"]] if name in plans else None,
                                "dense_count": len(plans[name]["dense"]) if name in plans else None,
                                "interior_removed": len(plans[name]["interior"]) if name in plans else None,
                                "thud_frame": plans[name]["thud_frame"] if name in plans else None,
                                "thud_s": plans[name]["thud_s"] if name in plans else None,
                                "shake_peak": [max(abs(d["tremor"]) for d in plans[name]["dense"]),
                                               max(abs(d["burst"]) for d in plans[name]["dense"])] if name in plans else None,
                                "samples": [[d["frame"], round(d["value"], 4)] for d in plans[name]["dense"]][::5]
                                if name in plans else None}
                         for name in params["channels"]}}


def _thud_summary(plans):
    return ";".join("%s@f%d(%.3fs)" % (name, p["thud_frame"], p["thud_s"]) for name, p in sorted(plans.items()))


def run_dry(n, run, params):
    channels, rise_info, problems, warnings, _h = _gather(n, run, params)
    plans, refusals, more = plan_scene(channels, params, rise_info["tick_rate"], rise_info["fps"])
    warnings += more
    if rise_info["audio_tracks"]:
        warnings.append("AUDIO_TRACKS_PRESENT (reported, none added): %s" % json.dumps(rise_info["audio_tracks"]))
    if params["thud_marker"] and any(m[0] == params["marker_label"] for m in rise_info["markers"]):
        refusals.append("MARKER_EXISTS: %s" % params["marker_label"])
    report = _report(n, run, params, channels, rise_info, problems, warnings, plans, refusals)
    out = os.path.join(_here(), DRY_PATTERN % n)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    for text in report["refusals"]:
        unreal.log_warning("HANGAR_HEAVE_REFUSAL|run=%s|%s" % (run, text))
    for text in warnings:
        unreal.log("HANGAR_HEAVE_WARNING|run=%s|%s" % (run, text))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("HANGAR_HEAVE_DRY_OK|run=%s|scene=S%d|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|channels=%s|"
               "thud=%s|audio_tracks=%d|report=%s"
               % (run, n, int(report["apply_ready"]), len(report["refusals"]), len(warnings),
                  ",".join("%s:%d" % (k, len(v["dense"])) for k, v in sorted(plans.items())), _thud_summary(plans),
                  len(rise_info["audio_tracks"]), out))


def _restore_in_memory(handles, record):
    errs = []
    for name, row in record["channels"].items():
        try:
            errs += ["%s: %s" % (name, f) for f in restore_channel(_LiveChannel(handles["chan"][name][1]), row["keys_before"])]
        except Exception as exc:   # noqa: BLE001 - reported, never swallowed silently
            errs.append("%s: %r" % (name, exc))
    return errs


def run_apply(n, run, params, decided_by):
    channels, rise_info, problems, warnings, h = _gather(n, run, params)
    plans, refusals, more = plan_scene(channels, params, rise_info["tick_rate"], rise_info["fps"])
    if params["thud_marker"] and any(m[0] == params["marker_label"] for m in rise_info["markers"]):
        refusals.append("MARKER_EXISTS: %s" % params["marker_label"])
    if problems or refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(problems + refusals))
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    if os.path.exists(record_path):
        _stop(run, "RECORD_EXISTS|" + record_path)
    rise = h["rise"]
    ranges_before = _ranges(rise, h["chan"])
    backup = _backup(run, n, "")
    unreal.log("HANGAR_HEAVE_BACKUP_OK|run=%s|backup=%s" % (run, backup))
    record = new_record(n, run, params, rise_info, channels, plans, decided_by, backup)
    record["ranges_before"] = ranges_before
    write_record_exclusive(record_path, record)                         # BEFORE any mutation
    failures = []
    try:
        rise.modify()
        for name, plan in plans.items():
            section, ch = h["chan"][name]
            section.modify()
            live, pins, bad = write_channel(_LiveChannel(ch), channels[name], plan)
            failures += ["%s: %s" % (name, f) for f in bad]
            record["channels"][name]["keys_after"] = live
            record["channels"][name]["pins"] = pins
        if params["thud_marker"] and "root_pitch" in plans:
            mf = unreal.MovieSceneMarkedFrame()                          # curtain_sleight.py:1823-1827 [prec]
            mf.set_editor_property("label", params["marker_label"])
            mf.set_editor_property("frame_number", unreal.FrameNumber(int(plans["root_pitch"]["thud_frame"])))
            rise.add_marked_frame_to_sequence(mf, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
            rise.sort_marked_frames()
            record["marker_added"] = [params["marker_label"], int(plans["root_pitch"]["thud_frame"])]
    except Exception as exc:   # noqa: BLE001
        failures.append("WRITE_RAISED: %r" % exc)
    failures += range_gate(ranges_before, _ranges(rise, h["chan"]))
    census = _census()
    if census != {"content": [RISE_PATH % n], "maps": []}:
        failures.append("TOUCHED_CENSUS: %s" % json.dumps(census))
    if failures:
        errs = _restore_in_memory(h, record)
        update_record(record_path, dict(record, applied=False, failed=failures, restore_errors=errs))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|restored_in_memory=%s|NOTHING SAVED; Don't-Save restart if the census is still dirty"
              % (failures[:12], "exact" if not errs else errs[:4]))
    if not unreal.EditorAssetLibrary.save_asset(RISE_PATH % n, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s|record=%s" % (RISE_PATH % n, record_path))
    rise2 = unreal.load_asset(RISE_PATH % n)
    final = {}
    _c, _i, _p, _w, h2 = _gather(n, run, params)
    for name in plans:
        final[name] = _LiveChannel(h2["chan"][name][1]).read()
    record["applied"] = True
    dd = drift(final, record)
    dd += range_gate(ranges_before, _ranges(rise2, h2["chan"]))
    if _census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if dd:
        record["applied"] = True
        record["post_save_readback_failed"] = dd
        update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd[:8], backup))
    update_record(record_path, record)
    unreal.log("HANGAR_HEAVE_APPLY_OK|run=%s|scene=S%d|channels=%s|thud_frame=%s|thud=%s|pins=%d|marker=%s|backup=%s|"
               "record=%s|decided_by=%s"
               % (run, n, ",".join("%s:%d" % (k, len(v["dense"])) for k, v in sorted(plans.items())),
                  plans["root_pitch"]["thud_frame"] if "root_pitch" in plans else "none", _thud_summary(plans),
                  sum(len(r["pins"]) for r in record["channels"].values()), record["marker_added"], backup,
                  record_path, decided_by))


def run_revert(n, run, params):
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = load_record(record_path)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or int(record["scene"]) != n:
        _stop(run, "REVERT_RECORD_CONTEXT")
    channels, rise_info, problems, _w, h = _gather(n, run, record["params"])
    missing = [name for name in record["channels"] if name not in h["chan"]]
    if missing:
        _stop(run, "REVERT_CHANNELS_MISSING|%r|%r" % (missing, problems))
    dd = drift(channels, record)
    dd += range_gate(record["ranges_before"], _ranges(h["rise"], h["chan"]))
    marks = [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)]
             for m in h["rise"].get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)]
    if record.get("marker_added") and record["marker_added"] not in marks:
        dd.append("MARKER_GONE: %r" % record["marker_added"])
    if dd:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r (restore from %s instead)" % (dd[:8], record["backup"]))
    backup = _backup(run, n, "-revert")
    h["rise"].modify()
    errs = []
    for name, row in record["channels"].items():
        h["chan"][name][0].modify()
        errs += ["%s: %s" % (name, f) for f in restore_channel(_LiveChannel(h["chan"][name][1]), row["keys_before"])]
    if record.get("marker_added"):
        for i in sorted([i for i, m in enumerate(marks) if m == record["marker_added"]], reverse=True):
            h["rise"].delete_marked_frame(i)                              # curtain_sleight.py:1971-1974 [prec]
    errs += range_gate(record["ranges_before"], _ranges(h["rise"], h["chan"]))
    census = _census()
    if census != {"content": [RISE_PATH % n], "maps": []}:
        errs.append("TOUCHED_CENSUS: %s" % json.dumps(census))
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8], record["backup"]))
    if not unreal.EditorAssetLibrary.save_asset(RISE_PATH % n, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s" % (RISE_PATH % n))
    _c, _i, _p, _w2, h2 = _gather(n, run, record["params"])
    final = []
    for name, row in record["channels"].items():
        final += ["%s: %s" % (name, f) for f in compare_keys(_LiveChannel(h2["chan"][name][1]).read(), row["keys_before"],
                                                             check_all_tangents=True)]
    if _census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final[:8], record["backup"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("HANGAR_HEAVE_REVERT_OK|run=%s|scene=S%d|channels=%s|backup=%s|record=%s"
               % (run, n, ",".join(sorted(record["channels"])), backup, archived))


def main():
    g = globals()
    run = str(g.get("HANGAR_HEAVE_RUN_ID") or datetime.datetime.now().strftime("HH-%Y%m%d-%H%M%S"))
    n = g.get("HANGAR_HEAVE_SCENE")
    mode = str(g.get("HANGAR_HEAVE_MODE") or "DRY").upper()
    try:
        params = merged_params(g.get("HANGAR_HEAVE_PARAMS") or {})
    except PlanError as exc:
        _stop(run, "PARAMS|" + str(exc))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    record_path = os.path.join(_here(), RECORD_PATTERN % n) if n in SCENES else ""
    applied = False
    if record_path and os.path.exists(record_path):
        applied = bool(load_record(record_path).get("applied"))
    state = {"mode": mode, "scene": n, "confirm": g.get("HANGAR_HEAVE_CONFIRM"),
             "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census(), "record_exists": bool(record_path) and os.path.exists(record_path),
             "record_applied": applied, "decided_by": g.get("HANGAR_HEAVE_DECIDED_BY")}
    early = live_gates(state)
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        if mode == "REVERT":
            run_revert(n, run, params)
        elif mode == "APPLY":
            run_apply(n, run, params, str(state["decided_by"]))
        else:
            run_dry(n, run, params)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
