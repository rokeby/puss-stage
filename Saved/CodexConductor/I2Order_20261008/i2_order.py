"""I2 ORDER (8 Oct 2026; offline-authored, NEVER RUN IN UNREAL here).  Gary's notes F16 / F17 / F18 on Interaction 2.

F16  curtain first, then the light; the camera stops at its 12:18 pose and holds; the drape fills that frame.
     * the I2 sleight drape ("Sleight Hangar Drape") is spawned HUNG from `drape_visible_from` (I2_START = frame 0,
       DARKNESS = first frame the I2-keyed hangar lights are all dark, or an int), i.e. before the gobo spot's fade
       (live: the last dark frame of "Shadow Play Spot (Hangar)" intensity; IST record says 175->275);
     * 12:18 / cue 7 of 19 + 8.7 s is mapped to an I2 frame H from the LIVE compiled transport segments and
       cross-checked against I2's camera cuts; the live camera at H is evaluated by SEQUENCE EVALUATION
       (channel.evaluate_keys at H), never retyped; its later keys are replaced by a constant hold;
     * the other sleight camera (it cuts in at the sleight, 1250) is re-posed to the twin of the held pose relative to
       its own drape, so the sleight stays matched;
     * the drape box (curtain_sleight_I2_dry.json inputs.cache.hang_aabb_cm on the drape's live transform) is
       projected into the held camera (filmback/focal/aspect read live): coverage and margins per edge, reported, and
       RESIZE_SPOT if the drape moved vs GoboSpot DRY-2 (D = 3000).
F17  read-only LIGHTING DIFF across every sleight camera cut (+ the I2 end): lights reaching each side's framed drape,
     exposure volumes + camera PP, fog, the twin spots' keyed intensity at the cut, light events near the end; ranked;
     proposals.  OPTIONAL fixes (PPV_WEIGHT / LIGHT_HIDE / LIGHT_DIM) only under mode FIX with its own confirm.
F18  the measured curtain-fall frame (mouth drape GC FALL section end) + a hold -> N; everything past N is listed;
     the mode file for Saved/CodexSoftGoods/extend_scene_playback.py is written (dry_run true).  That tool is NOT run
     or edited here, and its own source refuses to shorten a Sequence cue (extend_scene_playback.py:345-346): the
     DRY says so.

Modes (args["mode"], args["confirm"] must equal CONFIRMS[mode]):
  DRY        read-only.  Writes i2_order_dry_<run>.json + i2_order_plan.json + extend_i2_shorten_mode.json.
  APPLY      needs a DRY plan with the same digest.  Backups/PreI2Order-<run>/ + exclusive record FIRST, then writes
             only the owned tracks of the named bindings, read-back, saves ONLY the LS, read-back again.
  REVERT     drift check against the record's after-state, backup, restores the recorded originals exactly.
  VERIFY     read-only re-check of an applied record (holds, curtain-first, guards).
  FIX        optional lighting fix steps from args["params"]["fix_steps"] (default none).  Own record.
  FIX_REVERT removes what FIX created.
Guards on every mode: no PIE, no open Sequencer, the show world, exact census, no ZZ_ actors; the gobo session's
AG-I2-TEST-004 track/LF materials and the GoboSpot template properties are hashed before and after and must be equal;
every non-owned binding/track/cut/marker of the LS must read back identical.
Visibility tracks: bHidden/bHidden, channel TRUE = VISIBLE (memory ue58-visibility-track-binding); bHiddenInGame is
refused (inert, measured by Conductor 5 on 8 Oct).
Markers: I2_ORDER_<MODE>_OK|run=<id>|... only after asserted read-back; I2_ORDER_STOPPED|run=<id>|reason=...
No unreal object at module level: `unreal` is imported inside functions only (_ue()).  Importing this file under system
Python touches nothing.  Tiers of every claim/call are in CLAIMS and API_TABLE (decl / prec / meas / inf).
"""
import copy
import datetime
import hashlib
import json
import math
import os
import shutil

MARK = "I2_ORDER"
TOOL_VERSION = "2026-10-08a"
SEQ_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CUE_LABEL = "Interaction 2 \u2014 Turnips"
GC_PATH = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
CACHE_FPS = 30.0                     # curtain_sleight.py:100
NAMES = {
    "drape": "Sleight Hangar Drape",               # curtain_sleight.py:95
    "hangar_cam": "S2 Sleight Hangar Camera",      # curtain_sleight.py:92 (S%d)
    "mouth_cam": "I2 Sleight Mouth Camera",        # curtain_sleight.py:93 (I%d)
    "mouth_drape": "Transition Drape (baked)",     # curtain_sleight.py:68
    "spot_hangar": "Shadow Play Spot (Hangar)",
    "spot_mouth": "Shadow Play Spot (Mouth)",
    "root": "S2 Hangar Root",                      # curtain_sleight.py:72
}
CAMERAS = (NAMES["hangar_cam"], NAMES["mouth_cam"])
DRAPE_OF_CAMERA = {NAMES["hangar_cam"]: NAMES["drape"], NAMES["mouth_cam"]: NAMES["mouth_drape"]}
CAM_TRACK = "CurtainSleight (Conductor)"           # curtain_sleight.py:90
SPOT_TRACK = "ShadowPlaySpot (Conductor)"
AG_TRACK = "ShadowGobo Frame (Conductor)"          # animated_gobo.py:84
FIX_TRACK = "I2Order Fix (Conductor)"
LENS_PROPS = ("CurrentFocalLength", "ManualFocusDistance")   # curtain_sleight.py:2094-2095
POSE_CH = {"Location.X": "x", "Location.Y": "y", "Location.Z": "z",
           "Rotation.X": "roll", "Rotation.Y": "pitch", "Rotation.Z": "yaw"}   # curtain_sleight.py:104-105
GOBO_PROPS = ("attenuation_radius", "cast_shadows", "disabled_brightness", "inner_cone_angle", "intensity",
              "intensity_units", "light_function_fade_distance", "light_function_material", "outer_cone_angle",
              "soft_source_radius", "source_length", "source_radius")       # gobo_spot_record originals
EXTEND_REFUSAL_TEXT = "Sequence cues can only be lengthened"            # extend_scene_playback.py:346

CONFIRMS = {"DRY": "DRY I2ORDER", "APPLY": "APPLY I2ORDER", "REVERT": "REVERT I2ORDER", "VERIFY": "VERIFY I2ORDER",
            "FIX": "FIX I2LIGHT", "FIX_REVERT": "FIX_REVERT I2LIGHT"}
FOLDER = "I2Order_20261008"
RECORD = "i2_order_record.json"
FIX_RECORD = "i2_order_fix_record.json"
PLAN_FILE = "i2_order_plan.json"
DRY_PATTERN = "i2_order_dry_%s.json"
EXTEND_MODE_OUT = "extend_i2_shorten_mode.json"
REF = {  # paths relative to Saved/CodexConductor
    "sleight_dry": "curtain_sleight_I2_dry.json",
    "sleight_record": "curtain_sleight_record_I2.json",
    "ist_record": "interaction_shadow_transition_record_I2.json",
    "gs_dry": os.path.join("GoboSpot_20261008", "gobo_spot_dry_GS-I2-DRY-2.json"),
    "gs_record": os.path.join("GoboSpot_20261008", "gobo_spot_record_LS_Interaction_02_Turnips.json"),
    "ag_record": os.path.join("animated_gobo_records", "AG-I2-TEST-004.json"),
}
EXTEND_TOOL_REL = os.path.join("CodexSoftGoods", "extend_scene_playback.py")   # relative to Saved/

DEFAULTS = {
    "seconds_into_cue": 8.7,          # Gary 8 Oct (F16): "8.7 seconds into Q7 out of 19"
    "transport_clock": "12:18",       # Gary 8 Oct (F16)
    "cue_number": 7, "cue_count": 19,
    "frame_rounding": "nearest",      # nearest | floor | ceil  (8.7 s x 25 = 217.5 exactly)
    "drape_visible_from": "I2_START",  # I2_START | DARKNESS | <int frame>
    "dark_threshold_cd": 0.0,
    "mouth_after_hold": "HOLD",       # HOLD (spec: hold to the end) | KEEP_WALK (keep the walk-in keys)
    "output_aspect": 16.0 / 9.0,      # used only when the camera does not constrain its aspect ratio [inf]
    "visible_z_tol_cm": 1.0,
    "eval_tol": 1.0e-3,
    "spot_tol_cm": 1.0,
    "f18_enabled": True,
    "f18_hold_s": 1.0,                # Conductor 5: "a small hold, default ~1.0 s"
    "f18_fall_frame": "FALL_END",     # FALL_END (curtain has fallen) | RELEASE (drop starts)
    "lighting_window_s": [49.0, 50.0],
    "fix_steps": [],
}

CLAIMS = [
    {"tier": "declaration-proven", "claim": "I2 cuts: S2 Sleight Hangar Camera [0,1250), I2 Sleight Mouth Camera [1250,2226): 1250/25 = 50.0 s = Gary's 49-50 s shift",
     "cite": "Saved/CodexConductor/interaction_shadow_transition_record_I2.json snapshot_after.cuts; curtain_sleight_record_I2.json plan.cuts"},
    {"tier": "declaration-proven", "claim": "Hangar drape spawn [[75,T],[1300,F]], GC [75,1300] offsets 23200/240799 on a 264000-tick cache = a ONE-tick hold window",
     "cite": "curtain_sleight_record_I2.json plan.hangar_drape.spawn/gc; curtain_sleight_I2_dry.json inputs.cache.duration_ticks"},
    {"tier": "declaration-proven", "claim": "Hangar camera pushes 75->275 (smoothstep, focal 28->35 log-linear) and is constant 275..1300; 8.7 s = 217.5 frames is mid-push",
     "cite": "curtain_sleight.py:487-495; curtain_sleight_record_I2.json plan.frames"},
    {"tier": "declaration-proven", "claim": "Spot fade-up 175->275 on both twins (IST-I2-APPLY-20261008)",
     "cite": "interaction_shadow_transition_record_I2.json plan.fade_up"},
    {"tier": "declaration-proven", "claim": "Equal-priority overlapping post-process volumes have an UNDEFINED order",
     "cite": "D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Engine/PostProcessVolume.h:30-35"},
    {"tier": "declaration-proven", "claim": "Hangar camera stands in TWO priority-0 volumes (unbound EV -3 histogram; 'S2 Hangar Pinned Exposure' EV 0.5); the mouth camera only in the unbound one (5 Oct DRY)",
     "cite": "curtain_sleight_I2_dry.json diagnostics.ppv_hangar_camera / ppv_mouth_camera"},
    {"tier": "declaration-proven", "claim": "extend_scene_playback.py refuses a Sequence cue new_end <= old_end, BEFORE its dry-run return",
     "cite": "Saved/CodexSoftGoods/extend_scene_playback.py:345-346 (dry return at :355)"},
    {"tier": "declaration-proven", "claim": "evaluate_keys floors the evaluation time to the display frame and evaluates the channel (default, keys, extrapolation)",
     "cite": "SequencerScripting/Public/MovieSceneScriptingChannel.h:218-243; Private/KeysAndChannels/MovieSceneScriptingDouble.h:296, MovieSceneScriptingFloat.h:467-468"},
    {"tier": "declaration-proven", "claim": "Camera basis = FRotationMatrix rows (forward, right, up)",
     "cite": "Core/Public/Math/RotationTranslationMatrix.h:72-84"},
    {"tier": "declaration-proven", "claim": "Cameras keep horizontal FOV by default (MaintainXFOV); bConstrainAspectRatio letterboxes",
     "cite": "Engine/Classes/Camera/CameraComponent.h:107-120"},
    {"tier": "inferred", "claim": "The channel evaluation equals what the camera shows: section easing/blend weights and attach-parent motion are not part of evaluate_keys; the tool composes the root (live, landed) and cross-checks against linear key interpolation",
     "cite": "no private .cpp in UE_5.8 (memory ue58-engine-source-limits)"},
    {"tier": "inferred", "claim": "A one-tick GC window plays a static sample, so moving the hangar drape's GC section start earlier does not change what it shows",
     "cite": "curtain_sleight.py:289-296 (fmod inferred there too)"},
    {"tier": "inferred", "claim": "Illuminance estimates (inverse square, UE spot cone and radius window, lumens/4pi) ignore occlusion (hangar walls) and lights keyed by OTHER sequences; ranking is a guide, the cut must be judged in PIE",
     "cite": "no LightRendering .usf/.cpp read for this; tool design"},
    {"tier": "inferred", "claim": "Camera PP settings apply after the volumes, weighted by PostProcessBlendWeight",
     "cite": "CameraComponent.h:317,353 declare the fields; the blend order is not declared there"},
]

API_TABLE = [
    ("Show.cues / cue.scene.sequence / label / type", "prec", "curtain_sleight.py:1476-1488 (APPLY_OK 5 Oct)"),
    ("InfinityStageTransportController build_segments + segments label/start_frame/end_frame", "prec",
     "Saved/CodexSoftGoods/extend_scene_playback.py:185-194 (ran 8 Oct, S2SHRINE-20261008 ok:true)"),
    ("seq.get_bindings / binding.get_tracks / track.get_sections / section.get_all_channels / channel.get_keys", "prec",
     "interaction_shadow_transition.py:363-447 (IST-I2-APPLY-20261008 applied on THIS sequence)"),
    ("track.get_property_name / get_property_path", "prec", "interaction_shadow_transition.py:475-476 (same run)"),
    ("seq.make_range(frame, 1) + channel.evaluate_keys(range, display_rate)", "decl",
     "MovieSceneSequenceExtensions.h:145; MovieSceneScriptingDouble.h:296; no run precedent in this project [inf for the Python names]"),
    ("key.get_interpolation_mode", "decl", "MovieSceneScriptingFloat.h:62-64 (Python name inferred; failure is recorded, not fatal)"),
    ("remove_section / add_section / set_range / add_key(LINEAR) on existing transform/float/spawn tracks", "prec",
     "interaction_shadow_transition.py:427-492 (IST APPLY measured on this sequence)"),
    ("GC section get/set params, set_range", "prec", "curtain_sleight.py:1302-1305, 1997-2002 (APPLY_OK 5 Oct)"),
    ("camera cut sections get_camera_binding_id().guid", "prec", "curtain_sleight.py:1338-1341"),
    ("CineCameraComponent filmback/current_focal_length", "prec", "curtain_sleight.py:1614-1615, 2061-2066"),
    ("CameraComponent constrain_aspect_ratio / aspect_ratio / post_process_blend_weight / post_process_settings", "decl",
     "CameraComponent.h:107-120, 317, 353 [Python names inferred; unreadable -> reported]"),
    ("PostProcessVolume settings auto_exposure_* + override flags, priority, unbound, enabled", "prec",
     "curtain_sleight.py:1412-1433 (DRY ran 5 Oct)"),
    ("PostProcessVolume blend_weight / blend_radius", "decl", "PostProcessVolume.h:37-43 [Python names inferred]"),
    ("LightComponent intensity/intensity_units/temperature/cones/attenuation/LF material", "prec",
     "curtain_sleight.py:1567-1576; gobo_spot record originals"),
    ("light_color / use_temperature / affects_world / hidden / visible", "decl",
     "LightComponentBase.h:36-52, LightComponent.h:56-69 [Python names inferred]"),
    ("ExponentialHeightFogComponent fog_density/fog_height_falloff/start_distance/volumetric_fog*", "decl",
     "ExponentialHeightFogComponent.h:22-175 [Python names inferred]"),
    ("seq.add_possessable + set_parent (FIX only)", "prec", "curtain_sleight.py:1918-1928 (APPLY_OK 5 Oct)"),
    ("binding.add_track(MovieSceneVisibilityTrack) + set_property_name_and_path('bHidden','bHidden') (FIX only)", "prec",
     "ClamSlime_20261008/slime_apply_ue.py:1068-1071; KlaraIngest/vis_fix.py (APPLIED S2 VISFIX-20261008-1)"),
    ("float track on PostProcessVolume BlendWeight (FIX only)", "inf", "BlendWeight is UPROPERTY(interp) PostProcessVolume.h:41-43; no project precedent"),
    ("binding.remove_track / binding.remove (FIX_REVERT only)", "prec", "curtain_sleight.py:1825; interaction_shadow_transition.py:741"),
    ("EditorAssetLibrary.save_asset(LS only)", "prec", "interaction_shadow_transition.py:822 (measured)"),
]


class PlanError(ValueError):
    pass


class Stop(RuntimeError):
    pass


# =====================================================================================================================
# small pure helpers
# =====================================================================================================================

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def wrap(deg):
    return (float(deg) + 180.0) % 360.0 - 180.0


def norm_channel(raw):
    """'Location.Y_183' -> 'Location.Y' (memory ue58-sequencer-read-traps); plain names pass through."""
    raw = str(raw)
    head, sep, tail = raw.rpartition("_")
    return head if sep and tail.isdigit() else raw


def interp(keys, frame, default=None):
    """Linear evaluation of [[frame, value]] with constant extrapolation; the default when there are no keys."""
    rows = sorted((float(f), v) for f, v in keys)
    if not rows:
        return default
    if isinstance(rows[0][1], bool):
        return bool_at(keys, frame, default)
    if frame <= rows[0][0]:
        return float(rows[0][1])
    for (a, x), (b, y) in zip(rows, rows[1:]):
        if a <= frame <= b:
            return float(y) if b == a else float(x) + (float(y) - float(x)) * (frame - a) / (b - a)
    return float(rows[-1][1])


def bool_at(keys, frame, default=False):
    value = bool(default) if default is not None else False
    for f, v in sorted(keys, key=lambda r: r[0]):
        if f <= frame:
            value = bool(v)
    return value


def rot_z(v, yaw):
    r = math.radians(float(yaw))
    c, s = math.cos(r), math.sin(r)
    return [v[0] * c - v[1] * s, v[0] * s + v[1] * c, float(v[2])]


def to_world(frame, p):
    d = rot_z(p, frame["yaw"])
    return [float(frame["loc"][i]) + d[i] for i in range(3)]


def to_local(frame, p):
    return rot_z([float(p[i]) - float(frame["loc"][i]) for i in range(3)], -float(frame["yaw"]))


def basis(pitch, yaw, roll):
    """FRotationMatrix rows [decl RotationTranslationMatrix.h:72-84]: forward, right, up."""
    sp, cp = math.sin(math.radians(pitch)), math.cos(math.radians(pitch))
    sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    sr, cr = math.sin(math.radians(roll)), math.cos(math.radians(roll))
    fwd = [cp * cy, cp * sy, sp]
    right = [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp]
    up = [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp]
    return fwd, right, up


def pose_from_values(values):
    """values keyed by POSE_CH names -> pose dict."""
    v = {POSE_CH[k]: float(values[k]) for k in POSE_CH if k in values}
    return {"loc": [v["x"], v["y"], v["z"]], "pitch": v["pitch"], "yaw": v["yaw"], "roll": v["roll"]}


def compose_attached(root, rel_pose):
    """World pose of a pose keyed relative to a yaw-only root (curtain_sleight keys the hangar camera in the root
    frame, curtain_sleight.py:476, 2014-2015).  Adding the root yaw is exact for a yaw-only parent because
    FRotator applies yaw last about world Z [decl RotationTranslationMatrix.h:72-84]."""
    return {"loc": to_world(root, rel_pose["loc"]), "pitch": rel_pose["pitch"],
            "yaw": wrap(float(root["yaw"]) + rel_pose["yaw"]), "roll": rel_pose["roll"]}


def twin_pose(world_pose, from_frame, to_frame):
    """The pose relative to `to_frame` that world_pose has relative to `from_frame` (both yaw-only)."""
    rel = to_local(from_frame, world_pose["loc"])
    return {"loc": to_world(to_frame, rel), "pitch": world_pose["pitch"],
            "yaw": wrap(world_pose["yaw"] - float(from_frame["yaw"]) + float(to_frame["yaw"])),
            "roll": world_pose["roll"]}


def merged_params(params):
    unknown = sorted(set(params or {}) - set(DEFAULTS))
    if unknown:
        raise PlanError("UNKNOWN_PARAMS: %r" % unknown)
    p = copy.deepcopy(DEFAULTS)
    p.update(copy.deepcopy(params or {}))
    if p["frame_rounding"] not in ("nearest", "floor", "ceil"):
        raise PlanError("FRAME_ROUNDING: %r" % p["frame_rounding"])
    v = p["drape_visible_from"]
    if not (v in ("I2_START", "DARKNESS") or (isinstance(v, int) and not isinstance(v, bool) and v >= 0)):
        raise PlanError("DRAPE_VISIBLE_FROM: I2_START | DARKNESS | int >= 0, got %r" % (v,))
    if p["mouth_after_hold"] not in ("HOLD", "KEEP_WALK"):
        raise PlanError("MOUTH_AFTER_HOLD: %r" % p["mouth_after_hold"])
    if p["f18_fall_frame"] not in ("FALL_END", "RELEASE"):
        raise PlanError("F18_FALL_FRAME: %r" % p["f18_fall_frame"])
    if not (0.0 <= float(p["f18_hold_s"]) <= 10.0):
        raise PlanError("F18_HOLD_S: %r" % p["f18_hold_s"])
    for step in p["fix_steps"]:
        fix_step_check(step)
    return p


# =====================================================================================================================
# F16 (b): transport mapping
# =====================================================================================================================

def parse_clock(text):
    parts = [int(x) for x in str(text).strip().split(":")]
    if not parts or len(parts) > 3 or any(x < 0 for x in parts):
        raise PlanError("TRANSPORT_CLOCK: %r" % text)
    s = 0
    for x in parts:
        s = s * 60 + x
    return float(s)


def frame_mapping(segments, p, fps, playback):
    """segments: [{"label","start","end"}] in Master seconds (live compiled order).  Returns the I2 frame H."""
    problems = []
    labels = [s["label"] for s in segments]
    if labels.count(CUE_LABEL) != 1:
        raise PlanError("CUE_SEGMENT_COUNT: %r appears %d times" % (CUE_LABEL, labels.count(CUE_LABEL)))
    idx = labels.index(CUE_LABEL)
    seg = segments[idx]
    if idx + 1 != int(p["cue_number"]):
        problems.append("CUE_NUMBER_MISMATCH: %r is cue %d, Gary said %d" % (CUE_LABEL, idx + 1, p["cue_number"]))
    if len(segments) != int(p["cue_count"]):
        problems.append("CUE_COUNT_MISMATCH: %d segments, Gary said %d" % (len(segments), p["cue_count"]))
    seg_len = float(seg["end"]) - float(seg["start"])
    seq_len = (int(playback[1]) - int(playback[0])) / float(fps)
    if abs(seg_len - seq_len) > 0.05:
        problems.append("SEGMENT_NOT_1TO1: segment %.3f s vs sequence %.3f s" % (seg_len, seq_len))
    t = float(p["seconds_into_cue"])
    exact = round(t * float(fps), 6)      # 8.7 x 25 = 217.49999999999997 in binary floating point
    if p["frame_rounding"] == "floor":
        h = int(math.floor(exact + 1.0e-9))
    elif p["frame_rounding"] == "ceil":
        h = int(math.ceil(exact - 1.0e-9))
    else:
        h = int(math.floor(exact + 0.5))
    clock = parse_clock(p["transport_clock"])
    window = [clock - float(seg["start"]), clock + 1.0 - float(seg["start"])]
    clock_ok = window[0] - 1.0e-6 <= t < window[1]
    if not clock_ok:
        problems.append("CLOCK_INCONSISTENT: %s is I2 [%.3f, %.3f) s, Gary said %.3f s" % (p["transport_clock"], window[0], window[1], t))
    if not (int(playback[0]) <= h < int(playback[1])):
        problems.append("FRAME_OUTSIDE_PLAYBACK: %d" % h)
    return {"cue_index_1based": idx + 1, "segment_count": len(segments), "segment": dict(seg),
            "seconds_into_cue": t, "exact_frame": exact, "frame": h, "rounding": p["frame_rounding"],
            "clock": p["transport_clock"], "clock_window_local_s": window,
            "clock_window_frames": [window[0] * fps, window[1] * fps], "clock_consistent": clock_ok,
            "problems": problems}


def live_camera_at(cuts, frame, guid_names):
    rows = [c for c in cuts if c[3] and c[1] <= frame < c[2]]
    if len(rows) != 1:
        raise PlanError("CUT_AT_FRAME: %d active cut sections at frame %d" % (len(rows), frame))
    return guid_names.get(rows[0][0], "?"), rows[0]


# =====================================================================================================================
# F16 (b): holds
# =====================================================================================================================

def track_key(guid, cls, name, prop):
    return "%s|%s|%s|%s" % (guid, cls, name, prop or "")


def evaluated_record(binding_guid, frame, spec, values, source="sequence_evaluation"):
    """The ONLY accepted pose input of plan_hold: values that came from the engine evaluation of `spec` at `frame`."""
    return {"source": source, "binding_guid": binding_guid, "frame": int(frame), "spec_digest": digest(spec),
            "values": dict(values)}


def _require_evaluated(ev, spec, frame):
    if not isinstance(ev, dict) or ev.get("source") != "sequence_evaluation":
        raise PlanError("POSE_NOT_EVALUATED: a hold pose must come from the live sequence evaluation, not be typed")
    if ev.get("spec_digest") != digest(spec) or int(ev.get("frame", -1)) != int(frame):
        raise PlanError("POSE_NOT_EVALUATED: evaluation does not belong to this track/frame")


def hold_spec(spec, ev, frame, hold_end):
    """Keep keys before `frame`, key the evaluated value at `frame` and `hold_end`, drop the later keys."""
    _require_evaluated(ev, spec, frame)
    out = copy.deepcopy(spec)
    sec = out["sections"][0]
    for ch in sec["channels"]:
        if not ch["keys"]:
            continue
        if ch["name"] not in ev["values"]:
            raise PlanError("EVALUATION_MISSING_CHANNEL: %s" % ch["name"])
        v = float(ev["values"][ch["name"]])
        keys = [k for k in ch["keys"] if float(k[0]) < frame]
        keys.append([int(frame), v])
        if hold_end > frame:
            keys.append([int(hold_end), v])
        ch["keys"] = keys
    return out


def constant_spec(spec, values, start, hold_end, keep_from=None):
    """Constant keys (start, hold_end) for every keyed channel; optional keep_from keeps original keys >= keep_from."""
    out = copy.deepcopy(spec)
    for ch in out["sections"][0]["channels"]:
        if not ch["keys"] and ch["name"] not in values:
            continue
        if ch["name"] not in values:
            raise PlanError("TWIN_VALUE_MISSING: %s" % ch["name"])
        v = float(values[ch["name"]])
        if keep_from is None:
            ch["keys"] = [[int(start), v], [int(hold_end), v]]
        else:
            ch["keys"] = [[int(start), v], [int(keep_from) - 1, v]] + [k for k in ch["keys"] if float(k[0]) >= keep_from]
    return out


def check_hold(before, after, ev, frame, hold_end, tol):
    """Falsifiable: (1) engine value == linear key interpolation at frame (else easing/non-linear keys: refuse);
    (2) the held curve equals the evaluated value on [frame, hold_end+50]; (3) nothing before `frame` changed."""
    fail = []
    for cb, ca in zip(before["sections"][0]["channels"], after["sections"][0]["channels"]):
        if not cb["keys"]:
            continue
        name, v = cb["name"], float(ev["values"][cb["name"]])
        pure = interp(cb["keys"], frame, cb["default"])
        if abs(pure - v) > tol * max(1.0, abs(v)):
            fail.append("EVAL_DISAGREES_WITH_KEYS|%s|engine=%.6f|keys=%.6f" % (name, v, pure))
        for f in (frame, (frame + hold_end) // 2, hold_end, hold_end + 50):
            got = interp(ca["keys"], f, ca["default"])
            if abs(got - v) > 1.0e-6 * max(1.0, abs(v)):
                fail.append("HOLD_NOT_EVALUATED_POSE|%s|f=%d|%.6f!=%.6f" % (name, f, got, v))
        probes = sorted({int(k[0]) for k in cb["keys"] if float(k[0]) < frame} |
                        {int(k[0]) + 1 for k in cb["keys"] if float(k[0]) + 1 < frame})
        for f in probes:
            a, b = interp(cb["keys"], f, cb["default"]), interp(ca["keys"], f, ca["default"])
            if abs(a - b) > 1.0e-6 * max(1.0, abs(a)):
                fail.append("HOLD_CHANGED_BEFORE_FRAME|%s|f=%d|%.6f->%.6f" % (name, f, a, b))
                break
    return fail


# =====================================================================================================================
# F16 (a): curtain first
# =====================================================================================================================

def spec_channels(spec):
    return {c["name"]: c for c in spec["sections"][0]["channels"]}


def drape_state(drape, frame, z_hung, tol):
    """Is the drape visible AND hung at `frame`?  drape: {"spawn","transform","gc","vis"} specs (plain data)."""
    sp = spec_channels(drape["spawn"])
    ch = list(sp.values())[0]
    spawned = bool_at(ch["keys"], frame, ch["default"])
    gc = any(a <= frame < b for a, b in (s["range"] for s in drape["gc"]["sections"]))
    tz = spec_channels(drape["transform"])["Location.Z"]
    z = interp(tz["keys"], frame, tz["default"])
    hung = abs(z - z_hung) <= tol
    vis_ok, inert = True, []
    for vt in drape.get("vis", []):
        if vt.get("prop") == "bHiddenInGame":
            inert.append("INERT_VIS_TRACK_bHiddenInGame")
            continue
        vc = vt["sections"][0]["channels"][0]
        if not bool_at(vc["keys"], frame, vc["default"]):
            vis_ok = False
    return {"frame": frame, "spawned": spawned, "gc": gc, "z": z, "hung": hung, "vis": vis_ok,
            "visible": spawned and gc and hung and vis_ok, "inert": inert}


def fade_start_of(intensity_rows):
    """intensity_rows: [(frame, value)] evaluated on consecutive frames.  The last dark frame before the first lit one."""
    lit = [f for f, v in intensity_rows if float(v) > 0.0]
    if not lit:
        raise PlanError("SPOT_NEVER_LIT")
    first = min(lit)
    dark = [f for f, v in intensity_rows if f < first and float(v) <= 0.0]
    if not dark:
        raise PlanError("SPOT_LIT_FROM_START")
    return max(dark)


def darkness_frame(light_specs, fade_start, threshold):
    """First frame < fade_start at which every I2-keyed hangar light evaluates <= threshold; None if never."""
    table = {}
    for label, keys, default in light_specs:
        table[label] = [interp(keys, f, default if default is not None else 0.0) for f in range(0, fade_start + 1)]
    for f in range(0, fade_start + 1):
        if all(float(v[f]) <= threshold for v in table.values()):
            return f, {k: v[f] for k, v in table.items()}
    return None, {k: {"at_0": v[0], "at_fade": v[-1]} for k, v in table.items()}


def drape_plan(drape, visible_from, fade_start, hung_values, tol):
    """New spawn/transform/GC for the hangar drape: spawned and HUNG from visible_from (constant hung pose)."""
    if visible_from >= fade_start:
        raise PlanError("VISIBLE_FROM_NOT_BEFORE_FADE: %d >= %d" % (visible_from, fade_start))
    spawn = copy.deepcopy(drape["spawn"])
    ch = spawn["sections"][0]["channels"][0]
    on = [int(f) for f, v in ch["keys"] if v]
    off_after = sorted(int(f) for f, v in ch["keys"] if not v and on and int(f) > min(on))
    if not on or not off_after:
        raise PlanError("DRAPE_SPAWN_SHAPE: keys %r" % ch["keys"])
    strike = off_after[0]
    if strike <= fade_start:
        raise PlanError("DRAPE_STRUCK_BEFORE_FADE: %d" % strike)
    ch["keys"] = [[int(visible_from), True]] + [list(k) for k in ch["keys"] if int(k[0]) > fade_start]
    transform = copy.deepcopy(drape["transform"])
    last = 0
    for c in transform["sections"][0]["channels"]:
        if c["keys"]:
            last = max(last, max(int(k[0]) for k in c["keys"]))
    for c in transform["sections"][0]["channels"]:
        if not c["keys"]:
            continue
        v = float(hung_values[c["name"]])
        c["keys"] = [[int(visible_from), v], [max(last, strike), v]]
    gc = copy.deepcopy(drape["gc"])
    hits = [s for s in gc["sections"] if s["range"][0] <= fade_start < s["range"][1]]
    if len(hits) != 1:
        raise PlanError("DRAPE_GC_AT_FADE: %d sections cover %d" % (len(hits), fade_start))
    old_range = list(hits[0]["range"])
    hits[0]["range"] = [int(visible_from), old_range[1]]
    new = {"spawn": spawn, "transform": transform, "gc": gc, "vis": copy.deepcopy(drape.get("vis", []))}
    return new, {"strike": strike, "gc_range_before": old_range, "gc_range_after": hits[0]["range"]}


def check_drape(new, visible_from, fade_start, z_hung, tol):
    fail = []
    for f in range(int(visible_from), int(fade_start) + 1):
        st = drape_state(new, f, z_hung, tol)
        if not st["visible"]:
            fail.append("DRAPE_NOT_VISIBLE_BEFORE_FADE|f=%d|%s" % (f, json.dumps(st, sort_keys=True)))
            break
    for vt in new.get("vis", []):
        if vt.get("prop") == "bHiddenInGame":
            fail.append("DRAPE_HAS_INERT_bHiddenInGame_TRACK")
    return fail


# =====================================================================================================================
# F16 (c): coverage
# =====================================================================================================================

def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def coverage(cam_pose, focal_mm, filmback_mm, constrain, cam_aspect, output_aspect, drape_frame, box, grid=(64, 36)):
    """Project the frame through the drape's FRONT face (box x_lo, facing the camera) in the drape's local frame.
    Horizontal FOV from sensor width (MaintainXFOV [decl CameraComponent.h:114]); vertical from the aspect actually
    shown (the camera's if it constrains, else output_aspect [inf])."""
    fwd, right, up = basis(cam_pose["pitch"], cam_pose["yaw"], cam_pose["roll"])
    tan_h = float(filmback_mm[0]) / (2.0 * float(focal_mm))
    aspect = float(cam_aspect) if constrain else float(output_aspect)
    tan_v = tan_h / aspect
    c_loc = to_local(drape_frame, cam_pose["loc"])
    lf, lr, lu = (rot_z(v, -float(drape_frame["yaw"])) for v in (fwd, right, up))
    x0 = float(box["x"][0])
    ylo, yhi, zlo, zhi = float(box["y"][0]), float(box["y"][1]), float(box["z"][0]), float(box["z"][1])
    out = {"camera_in_front": c_loc[0] < x0, "camera_local": c_loc, "distance_to_face_cm": x0 - c_loc[0],
           "tan_h": tan_h, "tan_v": tan_v, "aspect_used": aspect, "aspect_source": "camera" if constrain else "output_aspect_arg"}

    def hit(sx, sy):
        d = [lf[i] + sx * tan_h * lr[i] + sy * tan_v * lu[i] for i in range(3)]
        if d[0] <= 1.0e-9:
            return None
        t = (x0 - c_loc[0]) / d[0]
        if t <= 0.0:
            return None
        return [c_loc[1] + t * d[1], c_loc[2] + t * d[2]]

    def inside(h):
        return h is not None and ylo <= h[0] <= yhi and zlo <= h[1] <= zhi

    def edge_margin(points, outward):
        # outward image direction -> the box boundary it faces (local y or z, by the dominant component)
        o = [outward[i] for i in range(3)]
        axis = 1 if abs(o[1]) >= abs(o[2]) else 2
        sign = 1.0 if o[axis] > 0 else -1.0
        bound = (yhi if sign > 0 else ylo) if axis == 1 else (zhi if sign > 0 else zlo)
        worst = None
        for h in points:
            if h is None:
                return {"margin_cm": None, "boundary": ("y" if axis == 1 else "z") + ("_hi" if sign > 0 else "_lo"),
                        "note": "ray misses the face plane"}
            m = (bound - h[axis - 1]) * sign
            worst = m if worst is None else min(worst, m)
        return {"margin_cm": worst, "boundary": ("y" if axis == 1 else "z") + ("_hi" if sign > 0 else "_lo")}

    n = 21
    s = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    edges = {"left": ([hit(-1.0, y) for y in s], [-v for v in lr]),
             "right": ([hit(1.0, y) for y in s], lr),
             "top": ([hit(x, 1.0) for x in s], lu),
             "bottom": ([hit(x, -1.0) for x in s], [-v for v in lu])}
    out["margins"] = {k: edge_margin(pts, o) for k, (pts, o) in edges.items()}
    gx, gy = grid
    total = good = 0
    for i in range(gx):
        for j in range(gy):
            total += 1
            good += 1 if inside(hit(-1.0 + (2 * i + 1) / float(gx), -1.0 + (2 * j + 1) / float(gy))) else 0
    corners = {k: hit(*v) for k, v in {"top_left": (-1, 1), "top_right": (1, 1), "bottom_left": (-1, -1),
                                         "bottom_right": (1, -1)}.items()}
    out["corners_on_face"] = corners
    out["coverage_fraction"] = good / float(total)
    ms = [m["margin_cm"] for m in out["margins"].values()]
    out["fills_frame"] = bool(out["camera_in_front"] and all(m is not None and m >= 0.0 for m in ms)
                              and all(inside(h) for h in corners.values()))
    centre = hit(0.0, 0.0)
    out["footprint_cm"] = None if centre is None else {
        "width": 2.0 * (x0 - c_loc[0]) * tan_h, "height": 2.0 * (x0 - c_loc[0]) * tan_v, "centre_yz": centre}
    return out


def spot_hit(spot_pose, drape_frame, box):
    """Distance along the spot axis to the drape front face and the world hit point (GoboSpot convention)."""
    fwd, _, _ = basis(spot_pose["pitch"], spot_pose["yaw"], spot_pose.get("roll", 0.0))
    c = to_local(drape_frame, spot_pose["loc"])
    d = rot_z(fwd, -float(drape_frame["yaw"]))
    if d[0] <= 1.0e-9:
        return None
    t = (float(box["x"][0]) - c[0]) / d[0]
    local = [c[i] + t * d[i] for i in range(3)]
    return {"d_cm": t, "hit_local": local, "hit_world": to_world(drape_frame, local),
            "on_face": float(box["y"][0]) <= local[1] <= float(box["y"][1]) and float(box["z"][0]) <= local[2] <= float(box["z"][1])}


def resize_spot_check(hits, gs_twins, box, tol):
    """RESIZE_SPOT if the drape moved/resized vs GoboSpot DRY-2 for either twin."""
    flags, rows = [], {}
    w, h = float(box["y"][1]) - float(box["y"][0]), float(box["z"][1]) - float(box["z"][0])
    for label, hit in hits.items():
        ref = gs_twins.get(label)
        if ref is None or hit is None:
            flags.append("RESIZE_SPOT|%s|no reference or no hit" % label)
            continue
        dd = abs(hit["d_cm"] - float(ref["d_max_cm"]))
        dp = math.dist(hit["hit_world"], ref["hit_point"])
        dw, dh = abs(w - float(ref["curtain_width_cm"])), abs(h - float(ref["curtain_height_cm"]))
        rows[label] = {"d_now_cm": hit["d_cm"], "d_gs_cm": float(ref["d_max_cm"]), "d_delta_cm": dd,
                       "hit_moved_cm": dp, "width_delta_cm": dw, "height_delta_cm": dh}
        if max(dd, dp, dw, dh) > tol:
            flags.append("RESIZE_SPOT|%s|D %.2f->%.2f cm, hit moved %.2f cm, size delta %.2f/%.2f cm"
                         % (label, float(ref["d_max_cm"]), hit["d_cm"], dp, dw, dh))
    return flags, rows


# =====================================================================================================================
# snapshot model (plain data) + untouched / guards
# =====================================================================================================================

def owned_keys_apply(guids, twin):
    """The tracks APPLY may write (binding guid, class, display name, property)."""
    g = guids
    out = {track_key(g["drape"], "MovieSceneSpawnTrack", "", "*"),
           track_key(g["drape"], "MovieScene3DTransformTrack", CAM_TRACK, "*"),
           track_key(g["drape"], "MovieSceneGeometryCacheTrack", "", "*"),
           track_key(g["held_cam"], "MovieScene3DTransformTrack", CAM_TRACK, "*")}
    for prop in LENS_PROPS:
        out.add(track_key(g["held_cam_comp"], "MovieSceneFloatTrack", CAM_TRACK, prop))
    if twin:
        out.add(track_key(g["twin_cam"], "MovieScene3DTransformTrack", CAM_TRACK, "*"))
        for prop in LENS_PROPS:
            out.add(track_key(g["twin_cam_comp"], "MovieSceneFloatTrack", CAM_TRACK, prop))
    return out


def tracks_by_key(snapshot):
    out = {}
    for b in snapshot["bindings"]:
        for t in b["tracks"]:
            k = track_key(b["guid"], t["class"], t["name"], t.get("prop"))
            if k in out:
                k = k + "#2"
            out[k] = t
    return out


def untouched_diff(before, after, owned, created_bindings=()):
    """Everything except the owned tracks (and bindings created by FIX) must be identical."""
    fail = []
    for key in ("playback", "cuts", "markers", "root_tracks", "fps", "templates"):
        if json.dumps(before.get(key), sort_keys=True, default=str) != json.dumps(after.get(key), sort_keys=True, default=str):
            fail.append("UNTOUCHED_CHANGED|%s" % key)
    bg = {b["guid"]: b for b in before["bindings"]}
    ag = {b["guid"]: b for b in after["bindings"]}
    if set(ag) - set(bg) - set(created_bindings):
        fail.append("UNEXPECTED_NEW_BINDINGS|%r" % sorted(set(ag) - set(bg) - set(created_bindings)))
    if set(bg) - set(ag):
        fail.append("BINDINGS_REMOVED|%r" % sorted(set(bg) - set(ag)))
    for g in set(bg) & set(ag):
        if (bg[g]["name"], bg[g]["parent"]) != (ag[g]["name"], ag[g]["parent"]):
            fail.append("BINDING_RENAMED_OR_REPARENTED|%s" % g)
    tb, ta = tracks_by_key(before), tracks_by_key(after)
    for k in sorted(set(tb) | set(ta)):
        base = k.split("#")[0]
        if base in owned or base.rsplit("|", 1)[0] + "|*" in owned:
            continue
        if k.split("|")[0] in created_bindings:
            continue
        if json.dumps(tb.get(k), sort_keys=True, default=str) != json.dumps(ta.get(k), sort_keys=True, default=str):
            fail.append("UNTOUCHED_TRACK_CHANGED|%s" % k)
    return fail


def guard_view(snapshot):
    """AG-I2-TEST-004 (MPC track + LF materials) and GoboSpot (spot template properties): what must not change."""
    ag = [t for t in snapshot["root_tracks"]
          if t["class"] == "MovieSceneMaterialParameterCollectionTrack" and t["name"] == AG_TRACK]
    tmpl = snapshot.get("templates", {})
    return {"ag004": {"tracks": ag, "lf": {k: (tmpl.get(k) or {}).get("light_function_material") for k in
                                            (NAMES["spot_hangar"], NAMES["spot_mouth"])}},
            "gobospot": {k: {p: (tmpl.get(k) or {}).get(p) for p in GOBO_PROPS if p != "light_function_material"}
                         for k in (NAMES["spot_hangar"], NAMES["spot_mouth"])}}


def guard_hashes(snapshot):
    g = guard_view(snapshot)
    return {"ag004": digest(g["ag004"]), "gobospot": digest(g["gobospot"])}


def guard_vs_records(snapshot, ag_record, gs_record):
    """DRY information: live vs what the gobo session recorded (drift by others is reported, not repaired)."""
    out = []
    g = guard_view(snapshot)
    if ag_record:
        want = ag_record.get("snapshot_after", {})
        tr = g["ag004"]["tracks"]
        keys = None
        if len(tr) == 1 and tr[0]["sections"] and tr[0]["sections"][0]["channels"]:
            frames = [c for c in tr[0]["sections"][0]["channels"] if c["name"].endswith("Frame") or c["name"] == "Frame"]
            keys = (frames or tr[0]["sections"][0]["channels"])[0]["keys"]
        if keys is not None and [[int(f), float(v)] for f, v in keys] != [[int(f), float(v)] for f, v in want.get("track", {}).get("keys", [])]:
            out.append("AG004_KEYS_DIFFER_FROM_RECORD|live=%r|record=%r" % (keys, want.get("track", {}).get("keys")))
        if len(tr) != 1:
            out.append("AG004_TRACK_COUNT|%d" % len(tr))
        for label, mat in (want.get("lights") or {}).items():
            if g["ag004"]["lf"].get(label) != mat:
                out.append("AG004_LF_DIFFERS|%s|live=%r|record=%r" % (label, g["ag004"]["lf"].get(label), mat))
    if gs_record:
        for label, props in (gs_record.get("after") or {}).items():
            for p, v in props.items():
                if p in ("light_function_material", "intensity_units", "intensity"):
                    continue
                live = g["gobospot"].get(label, {}).get(p)
                if live is None or (isinstance(v, (int, float)) and abs(float(live) - float(v)) > 1.0e-3):
                    out.append("GOBOSPOT_DIFFERS_FROM_RECORD|%s|%s|live=%r|record=%r" % (label, p, live, v))
    return out


# =====================================================================================================================
# F18: shorten after the fall
# =====================================================================================================================

def f18_plan(mouth_gc_sections, markers, fps, playback_end, p):
    secs = sorted(mouth_gc_sections, key=lambda s: s["range"][0])
    if len(secs) < 2 or secs[0]["range"][0] != 0:
        raise PlanError("MOUTH_DRAPE_GC_SHAPE: %r" % [s["range"] for s in secs])
    fall = secs[1]
    release, fall_end = int(fall["range"][0]), int(fall["range"][1])
    cross = []
    drop = [f for l, f in markers if l.strip() == "CST drop"]
    if drop and int(drop[0]) != release:
        cross.append("CST_DROP_MARKER_DIFFERS|marker=%d|gc=%d" % (drop[0], release))
    go = [(l, f) for l, f in markers if l.strip().startswith("GO ")]
    base = fall_end if p["f18_fall_frame"] == "FALL_END" else release
    n = base + int(round(float(p["f18_hold_s"]) * fps))
    problems = []
    if n >= int(playback_end):
        problems.append("F18_NOT_SHORTER: N=%d >= end %d" % (n, playback_end))
    return {"release_frame": release, "fall_end_frame": fall_end, "fall_frame_used": base,
            "fall_frame_source": "GC section 2 of %s (range %r, offsets %r)" % (NAMES["mouth_drape"], fall["range"],
                                                                              [fall.get("so"), fall.get("eo")]),
            "markers_cross_check": {"CST drop": drop, "GO": go, "problems": cross},
            "hold_s": float(p["f18_hold_s"]), "new_end_frame": n, "new_end_s": n / float(fps),
            "old_end_frame": int(playback_end), "cut_frames": int(playback_end) - n,
            "cut_s": (int(playback_end) - n) / float(fps), "problems": problems}


def past_end_listing(snapshot, n, guid_names):
    """Everything in the LS at or past N (the S2 extend report lists sections/cuts; this lists keys too)."""
    rows = {"sections": [], "keys": [], "cuts": [], "markers": [], "audio": [], "root_tracks": []}

    def walk(owner, t):
        for si, s in enumerate(t["sections"]):
            r = s.get("range")
            if r and r[1] is not None and r[1] > n:
                rows["sections"].append({"owner": owner, "track": t["class"], "name": t["name"], "prop": t.get("prop"),
                                         "range": r, "crosses_N": r[0] is not None and r[0] < n})
            for c in s.get("channels", []):
                late = [k for k in c["keys"] if float(k[0]) > n]
                if late:
                    rows["keys"].append({"owner": owner, "track": t["class"], "name": t["name"], "prop": t.get("prop"),
                                         "channel": c["name"], "count": len(late), "first": late[0], "last": late[-1]})
            if "Audio" in t["class"] and r and r[1] is not None and r[1] > n:
                rows["audio"].append({"owner": owner, "range": r})

    for b in snapshot["bindings"]:
        for t in b["tracks"]:
            walk(b["name"], t)
    for t in snapshot["root_tracks"]:
        walk("<root>", t)
        if any((s.get("range") or [0, 0])[1] is not None and (s.get("range") or [0, 0])[1] > n for s in t["sections"]):
            rows["root_tracks"].append({"class": t["class"], "name": t["name"]})
    for g, a, b, act in snapshot["cuts"]:
        if b > n:
            rows["cuts"].append({"camera": guid_names.get(g, g), "range": [a, b], "active": act,
                                 "extend_tool_will_set_end_to_N": b == snapshot["playback"][1]})
    rows["markers"] = [[l, f] for l, f in snapshot["markers"] if f >= n]
    return rows


def extend_mode_file(n, run):
    return {"cue_label": CUE_LABEL, "new_end_frame": int(n), "dry_run": True, "run_id": "I2SHORTEN-%s" % run}


def extend_prediction(extend_source, n, old_end):
    """Static reading of extend_scene_playback.py (never executed here)."""
    if extend_source is None:
        return {"will_refuse": None, "why": "extend_scene_playback.py not found"}
    refuses = EXTEND_REFUSAL_TEXT in extend_source and n <= old_end
    return {"will_refuse": refuses,
            "why": ("extend_scene_playback.py:345-346 refuses Sequence cues new_end <= old_end BEFORE its dry_run "
                    "return (:355): its DRY will print PUSS_SOFTGOODS_SCENE_EXTEND_STOPPED|cue_type=SEQUENCE|refusing: "
                    "Sequence cues can only be lengthened (%d -> %d). Shortening needs that tool's owner to allow it "
                    "(this tool edits no existing file)." % (old_end, n)) if refuses else "no refusal predicted",
            "also": ["tail_cut_extensions only moves cut ends that END at the old end (:83-96): the mouth cut "
                     "[1250, old_end) would end at N", "sections/keys past N are NOT trimmed by it (listed here)",
                     "its docstring note for Sequence cues says drape sections are re-fitted by fit_transition_drapes.py; "
                     "curtain_sleight warns NEVER to run that on I2 (FIT_TOOLS_INCOMPATIBLE)"]}


# =====================================================================================================================
# F17: lighting diff (pure)
# =====================================================================================================================

def to_candela(intensity, units, kind):
    u = str(units or "").upper()
    if kind == "directional":
        return None, "directional (lux), compared separately"
    if "CANDELA" in u:
        return float(intensity), "candela"
    if "LUMEN" in u:
        return float(intensity) / (4.0 * math.pi), "lumens/4pi [inf]"
    if "EV" in u:
        return None, "EV units not converted"
    return None, "unitless/unknown units not converted (%s)" % units


def light_lux(light, point, normal):
    """Estimate of illuminance (lux) at point from one local light.  [inf] UE-like cone and radius window."""
    cd, why = to_candela(light["intensity"], light.get("units"), light.get("kind"))
    if light.get("kind") == "directional":
        return {"lux": None, "why": why}
    if cd is None:
        return {"lux": None, "why": why}
    d = [float(light["loc"][i]) - point[i] for i in range(3)]
    dist = math.sqrt(_dot(d, d))
    if dist < 1.0:
        return {"lux": None, "why": "light at the point"}
    u = [x / dist for x in d]
    r = light.get("radius")
    if r and dist >= float(r):
        return {"lux": 0.0, "why": "outside attenuation radius %.0f" % r, "dist_cm": dist}
    cos_i = max(0.0, _dot(normal, u))
    cone = 1.0
    if light.get("kind") == "spot":
        fwd, _, _ = basis(light["rot"]["pitch"], light["rot"]["yaw"], light["rot"].get("roll", 0.0))
        cos_a = _dot(fwd, [-x for x in u])
        co, ci = math.cos(math.radians(float(light["outer"]))), math.cos(math.radians(float(light.get("inner") or 0.0)))
        if ci <= co + 1.0e-9:
            cone = 1.0 if cos_a >= co else 0.0
        else:
            cone = max(0.0, min(1.0, (cos_a - co) / (ci - co))) ** 2
    window = 1.0 if not r else max(0.0, 1.0 - (dist / float(r)) ** 4) ** 2
    lux = cd * cos_i / (dist / 100.0) ** 2 * cone * window
    return {"lux": lux, "dist_cm": dist, "cos_incidence": cos_i, "cone": cone, "window": window, "why": why}


EXPOSURE_FIELDS = ("method", "min_ev", "max_ev", "bias")


def effective_exposure(volumes, camera_pp):
    """Blend override fields in ascending priority (higher wins), camera PP last [inf]; equal priorities are
    undefined [decl PostProcessVolume.h:30-33]: both orders are computed and a difference is flagged."""
    vols = [v for v in volumes if v.get("enabled", True) and float(v.get("weight", 1.0)) > 0.0]

    def run(order):
        out = {f: None for f in EXPOSURE_FIELDS}
        for v in order + ([camera_pp] if camera_pp and float(camera_pp.get("weight", 0.0)) > 0.0 else []):
            w = max(0.0, min(1.0, float(v.get("weight", 1.0))))
            for f in EXPOSURE_FIELDS:
                val = (v.get("overrides") or {}).get(f)
                if val is None:
                    continue
                if f == "method" or out[f] is None or not isinstance(val, (int, float)):
                    out[f] = val if w > 0.0 else out[f]
                else:
                    out[f] = out[f] + (float(val) - out[f]) * w
        return out

    asc = sorted(vols, key=lambda v: float(v.get("priority", 0.0)))
    groups, rev = {}, []
    for v in asc:
        groups.setdefault(float(v.get("priority", 0.0)), []).append(v)
    for pr in sorted(groups):
        rev.extend(reversed(groups[pr]))
    a, b = run(asc), run(rev)
    ties = [[x["name"] for x in g] for g in groups.values() if len(g) > 1]
    return {"effective": a, "effective_other_order": b, "tie_groups": ties,
            "tie_changes_result": a != b, "volumes": [v["name"] for v in asc],
            "camera_pp_weight": None if not camera_pp else camera_pp.get("weight")}


def ev_mid(eff):
    lo, hi = eff.get("min_ev"), eff.get("max_ev")
    if lo is None or hi is None:
        return None
    return (float(lo) + float(hi)) / 2.0 + float(eff.get("bias") or 0.0)


PAIRS = [({"label": NAMES["spot_hangar"]}, {"label": NAMES["spot_mouth"]}),
         ({"label": "S2 Sleight Twin Lantern"}, {"tag": "RigAtmos.MouthLantern.P03"})]


def side_summary(lights, point, normal):
    rows, total = [], 0.0
    for L in lights:
        r = light_lux(L, point, normal) if L.get("effective_visible", True) else {"lux": 0.0, "why": "hidden at frame"}
        row = {"label": L["label"], "kind": L.get("kind"), "intensity": L["intensity"], "units": L.get("units"),
               "intensity_source": L.get("intensity_source"), "color": L.get("color"),
               "temperature": L.get("temperature") if L.get("use_temperature") else None,
               "outer": L.get("outer"), "inner": L.get("inner"), "lf": L.get("lf"), "visible": L.get("effective_visible", True),
               "vis_note": L.get("vis_note"), "tags": L.get("tags", []), "lux": r.get("lux"), "why": r.get("why"),
               "dist_cm": r.get("dist_cm")}
        rows.append(row)
        if r.get("lux"):
            total += r["lux"]
    rows.sort(key=lambda x: -(x["lux"] or 0.0))
    return {"total_lux_est": total, "lights": rows}


def _stops(a, b):
    if a is None or b is None or a <= 0.0 or b <= 0.0:
        return None
    return math.log(b / a, 2.0)


def _match_pair(row, sel):
    if "label" in sel:
        return row["label"] == sel["label"]
    return sel["tag"] in row.get("tags", [])


def rank_cut(before, after, cut_frame, fps, spots_at_cut, fog_before, fog_after):
    """Ranked differences across one cut (largest likely visual impact first)."""
    items = []
    eb, ea = ev_mid(before["exposure"]["effective"]), ev_mid(after["exposure"]["effective"])
    if eb is not None and ea is not None:
        items.append({"kind": "EXPOSURE", "what": "effective EV100 mid (min/max + bias)", "before": before["exposure"]["effective"],
                      "after": after["exposure"]["effective"], "impact_stops": abs(ea - eb), "signed_ev_delta": ea - eb,
                      "note": "+EV100 after the cut = darker image after [inf]", "tier": "inferred (blend model), inputs live"})
    for side, ex in (("before", before["exposure"]), ("after", after["exposure"])):
        if ex["tie_changes_result"]:
            items.append({"kind": "EXPOSURE_TIE", "what": "equal-priority volumes %r at the %s camera" % (ex["tie_groups"], side),
                          "before": ex["effective"], "after": ex["effective_other_order"],
                          "impact_stops": abs((ev_mid(ex["effective"]) or 0.0) - (ev_mid(ex["effective_other_order"]) or 0.0)),
                          "note": "order undefined: PostProcessVolume.h:30-33", "tier": "declaration-proven (undefined order)"})
    tb, ta = before["light"]["total_lux_est"], after["light"]["total_lux_est"]
    st = _stops(tb, ta)
    items.append({"kind": "ILLUMINANCE_TOTAL", "what": "estimated lux on the framed drape", "before": tb, "after": ta,
                  "impact_stops": abs(st) if st is not None else None, "signed_stops": st, "tier": "inferred (no occlusion)"})
    used_b, used_a = set(), set()
    for sb, sa in PAIRS:
        rb = [r for r in before["light"]["lights"] if _match_pair(r, sb)]
        ra = [r for r in after["light"]["lights"] if _match_pair(r, sa)]
        if rb and ra:
            used_b.add(rb[0]["label"]); used_a.add(ra[0]["label"])
            st = _stops(rb[0]["lux"], ra[0]["lux"])
            diff_props = {k: [rb[0].get(k), ra[0].get(k)] for k in ("intensity", "units", "color", "temperature", "outer", "inner", "lf", "visible")
                          if json.dumps(rb[0].get(k), default=str) != json.dumps(ra[0].get(k), default=str)}
            items.append({"kind": "PAIR", "what": "%s <-> %s" % (rb[0]["label"], ra[0]["label"]),
                          "before": rb[0]["lux"], "after": ra[0]["lux"], "impact_stops": abs(st) if st is not None else None,
                          "property_differences": diff_props, "tier": "inferred lux; properties live"})
    labels_b = {r["label"] for r in before["light"]["lights"]}
    labels_a = {r["label"] for r in after["light"]["lights"]}
    for side, rows, used, total, other_labels in (("before", before["light"]["lights"], used_b, tb, labels_a),
                                                  ("after", after["light"]["lights"], used_a, ta, labels_b)):
        for r in rows:
            if r["label"] in used or not r.get("lux"):
                continue
            # a light reaching both framings (a global or a far light) is not one-sided
            twin_row = [x for x in (after if side == "before" else before)["light"]["lights"] if x["label"] == r["label"]]
            if twin_row and twin_row[0].get("lux"):
                continue
            # its share of its own side: the stops that side loses without it
            imp = _stops(max(total - r["lux"], 1.0e-9), total)
            items.append({"kind": "ONE_SIDED_LIGHT", "what": "%s only %s the cut" % (r["label"], side),
                          "before": r["lux"] if side == "before" else 0.0, "after": r["lux"] if side == "after" else 0.0,
                          "impact_stops": abs(imp) if imp is not None else None, "intensity_source": r.get("intensity_source"),
                          "tier": "inferred lux (no occlusion); keyed elsewhere = not evaluated"})
    for label, (vb, va) in spots_at_cut.items():
        st = _stops(vb, va) if vb and va else None
        items.append({"kind": "TWIN_SPOT_KEYS_AT_CUT", "what": "%s intensity at %d / %d" % (label, cut_frame - 1, cut_frame),
                      "before": vb, "after": va, "impact_stops": abs(st) if st is not None else (None if vb == va else 9.0),
                      "tier": "declaration-proven keys (evaluated)"})
    if json.dumps(fog_before, sort_keys=True, default=str) != json.dumps(fog_after, sort_keys=True, default=str):
        items.append({"kind": "FOG", "what": "height fog / local fog at the two framings", "before": fog_before, "after": fog_after,
                      "impact_stops": None, "tier": "properties live; visual impact not estimated"})
    items.sort(key=lambda x: -(x["impact_stops"] if x["impact_stops"] is not None else -1.0))
    return items


def proposals_for_cut(items, before, after, cut_frame, release, end):
    """Smallest reversible fixes, ranked as the items.  Executable ones are LS-only FIX steps (opt-in, look = Gary)."""
    props = []
    for it in items:
        if it["kind"] == "EXPOSURE" and it["impact_stops"] >= 0.25:
            vb = set(before["exposure"]["volumes"]); va = set(after["exposure"]["volumes"])
            only_b = sorted(v for v in vb - va if not (before["exposure"].get("unbound") or {}).get(v))
            for v in only_b:
                props.append({"id": "PPV-%s" % v, "executable": True, "kind": "PPV_WEIGHT", "rank_from": it["kind"],
                              "why": "volume %r covers only the pre-cut camera; weight 0 in I2 makes the hangar side expose like the mouth side" % v,
                              "fix_step": {"id": "PPV-%s" % v, "kind": "PPV_WEIGHT", "actor_label": v,
                                           "keys": [[0, 0.0], [end, 0.0]]},
                              "look_change": True, "needs": "Gary's own yes (it changes the hangar half's exposure)"})
            props.append({"id": "CAMERA_PP_MATCH", "executable": False, "kind": "CAMERA_PP",
                          "why": "match the post-cut camera's PP exposure (override min/max/bias, weight 1) to the pre-cut effective %r" % before["exposure"]["effective"],
                          "blocked_by": "a level-actor write (the cameras are level actors): this tool saves only the LS"})
        elif it["kind"] == "ONE_SIDED_LIGHT" and it["impact_stops"] and it["impact_stops"] >= 0.25:
            label = it["what"].split(" only ")[0]
            after_side = it["what"].endswith("after the cut")
            keys = [[0, True], [cut_frame, False], [release, True]] if after_side else [[0, True], [cut_frame - 25, False]]
            props.append({"id": "HIDE-%s" % label, "executable": True, "kind": "LIGHT_HIDE", "rank_from": it["kind"],
                          "why": "one-sided light (~%.2f stops on the framed drape, no occlusion modelled)" % it["impact_stops"],
                          "fix_step": {"id": "HIDE-%s" % label, "kind": "LIGHT_HIDE", "actor_label": label, "keys": keys},
                          "alternative": {"kind": "LIGHT_DIM", "actor_label": label},
                          "look_change": True, "needs": "Gary's own yes; check the light is not keyed by another sequence at this time"})
        elif it["kind"] == "TWIN_SPOT_KEYS_AT_CUT" and it["impact_stops"] and it["impact_stops"] > 0.05:
            props.append({"id": "SPOT_MATCH", "executable": False, "kind": "SPOT_KEYS",
                          "why": "twin spots differ at the cut", "blocked_by": "interaction_shadow_transition owns these keys: change its args and re-run it"})
        elif it["kind"] == "PAIR" and it["impact_stops"] and it["impact_stops"] >= 0.25:
            props.append({"id": "PAIR-%s" % it["what"], "executable": False, "kind": "PAIR_MATCH",
                          "why": "twin pair differs by %.2f stops (est.)" % it["impact_stops"],
                          "blocked_by": "the twin's own tool (curtain_sleight lantern scaling / IST spots)"})
    return props


# =====================================================================================================================
# FIX steps (pure)
# =====================================================================================================================

FIX_KINDS = ("PPV_WEIGHT", "LIGHT_HIDE", "LIGHT_DIM")


def fix_step_check(step):
    if not isinstance(step, dict) or step.get("kind") not in FIX_KINDS or not step.get("actor_label") or not step.get("id"):
        raise PlanError("FIX_STEP_SHAPE: %r" % (step,))
    keys = step.get("keys")
    if not isinstance(keys, list) or not keys:
        raise PlanError("FIX_STEP_KEYS: %r" % (step,))
    for k in keys:
        if not (isinstance(k, list) and len(k) == 2 and isinstance(k[0], int)):
            raise PlanError("FIX_STEP_KEY: %r" % (k,))
        if step["kind"] == "LIGHT_HIDE" and not isinstance(k[1], bool):
            raise PlanError("FIX_HIDE_KEYS_ARE_VISIBLE_BOOLS (true = VISIBLE): %r" % (k,))
        if step["kind"] != "LIGHT_HIDE" and (isinstance(k[1], bool) or not isinstance(k[1], (int, float))):
            raise PlanError("FIX_FLOAT_KEY: %r" % (k,))
    if step.get("property") not in (None, "bHidden") and step["kind"] == "LIGHT_HIDE":
        raise PlanError("FIX_VIS_PROPERTY: only bHidden (bHiddenInGame is inert), got %r" % step.get("property"))
    return True


def fix_track_spec(step, end):
    if step["kind"] == "LIGHT_HIDE":
        return {"class": "MovieSceneVisibilityTrack", "prop": "bHidden", "path": "bHidden", "name": FIX_TRACK,
                "range": [0, end + 1], "default": True, "keys": [[int(f), bool(v)] for f, v in step["keys"]]}
    if step["kind"] == "PPV_WEIGHT":
        return {"class": "MovieSceneFloatTrack", "prop": "BlendWeight", "path": "BlendWeight", "name": FIX_TRACK,
                "range": [0, end + 1], "default": None, "keys": [[int(f), float(v)] for f, v in step["keys"]]}
    return {"class": "MovieSceneFloatTrack", "prop": "Intensity", "path": "Intensity", "name": FIX_TRACK,
            "range": [0, end + 1], "default": None, "keys": [[int(f), float(v)] for f, v in step["keys"]]}


def check_fix_readback(spec, row):
    fail = []
    if row is None:
        return ["FIX_TRACK_MISSING"]
    if spec["class"] == "MovieSceneVisibilityTrack" and row.get("prop") != "bHidden":
        fail.append("VIS_TRACK_PROPERTY_NOT_bHidden|%r" % row.get("prop"))
    if row.get("prop") != spec["prop"]:
        fail.append("FIX_PROPERTY|%r!=%r" % (row.get("prop"), spec["prop"]))
    keys = row["sections"][0]["channels"][0]["keys"] if row.get("sections") else []
    want = spec["keys"]
    if len(keys) != len(want) or any(int(a[0]) != int(b[0]) or (a[1] != b[1] if isinstance(b[1], bool) else abs(float(a[1]) - float(b[1])) > 1e-4)
                                     for a, b in zip(keys, want)):
        fail.append("FIX_KEYS|%r!=%r" % (keys, want))
    return fail


# =====================================================================================================================
# plan (pure, from plain facts)
# =====================================================================================================================

def build_plan(facts, p):
    """facts: everything read live, as plain data (see _facts).  Returns (plan, refusals, warnings)."""
    refusals, warnings = [], []
    snap = facts["snapshot"]
    fps = float(snap["fps"])
    pb = snap["playback"]
    m = frame_mapping(facts["segments"], p, fps, pb)
    refusals += m["problems"]
    h = m["frame"]
    names = {b["guid"]: b["name"] for b in snap["bindings"]}
    held_name, cut_row = live_camera_at(snap["cuts"], h, names)
    if held_name not in CAMERAS:
        raise PlanError("LIVE_CAMERA_NOT_A_SLEIGHT_CAMERA: %s at %d" % (held_name, h))
    twin_name = [c for c in CAMERAS if c != held_name][0]
    later = [(names.get(g, g), a, b) for g, a, b, act in snap["cuts"] if act and b > h]
    twin_needed = any(n == twin_name for n, _, _ in later)

    # ---- F18 first: the hold must end at the new end when the shortening is planned
    f18 = None
    if p["f18_enabled"]:
        f18 = f18_plan(facts["mouth_drape_gc"]["sections"], snap["markers"], fps, pb[1], p)
        warnings += f18["markers_cross_check"]["problems"]
        if f18["problems"]:
            refusals += f18["problems"]
    hold_end = f18["new_end_frame"] if (f18 and not f18["problems"]) else int(pb[1])

    # ---- F16 (b) holds
    cams = facts["cameras"]
    hc = cams[held_name]
    held_tr = hold_spec(hc["transform"], hc["eval_transform"], h, hold_end)
    held_lens = {prop: hold_spec(hc["lens"][prop], hc["eval_lens"][prop], h, hold_end) for prop in LENS_PROPS}
    fails = check_hold(hc["transform"], held_tr, hc["eval_transform"], h, hold_end, p["eval_tol"])
    for prop in LENS_PROPS:
        fails += check_hold(hc["lens"][prop], held_lens[prop], hc["eval_lens"][prop], h, hold_end, p["eval_tol"])
    refusals += fails
    rel_pose = pose_from_values(hc["eval_transform"]["values"])
    held_world = compose_attached(hc["parent_frame"], rel_pose) if hc.get("parent_frame") else rel_pose
    for prop in LENS_PROPS:
        _require_evaluated(hc["eval_lens"][prop], hc["lens"][prop], h)
        if len(hc["eval_lens"][prop]["values"]) != 1:
            raise PlanError("LENS_CHANNELS|%s|%d" % (prop, len(hc["eval_lens"][prop]["values"])))
    focal = float(list(hc["eval_lens"]["CurrentFocalLength"]["values"].values())[0])
    focus = float(list(hc["eval_lens"]["ManualFocusDistance"]["values"].values())[0])
    poses_near = {}
    for f, vals in sorted(hc.get("eval_near", {}).items()):
        w = compose_attached(hc["parent_frame"], pose_from_values(vals)) if hc.get("parent_frame") else pose_from_values(vals)
        poses_near[str(f)] = w
    spread = {"max_cm": max([math.dist(w["loc"], held_world["loc"]) for w in poses_near.values()] or [0.0]),
              "max_deg": max([abs(wrap(w["yaw"] - held_world["yaw"])) + abs(w["pitch"] - held_world["pitch"]) for w in poses_near.values()] or [0.0])}

    # ---- drape frames (live, evaluated at the hold frame)
    drape = facts["drape"]
    hung_ref = drape["hung_ref_frame"]
    hung_vals = drape["eval_hung"]["values"]
    if drape["eval_hung"].get("source") != "sequence_evaluation":
        raise PlanError("DRAPE_POSE_NOT_EVALUATED")
    hung_pose = pose_from_values(hung_vals)
    if abs(hung_pose["pitch"]) > 1e-3 or abs(hung_pose["roll"]) > 1e-3:
        raise PlanError("DRAPE_TILTED")
    hangar_frame = {"loc": hung_pose["loc"], "yaw": hung_pose["yaw"]}
    mouth_frame = facts["mouth_drape_frame"]
    frames = {NAMES["drape"]: hangar_frame, NAMES["mouth_drape"]: mouth_frame}

    twin = None
    if twin_needed:
        tc = cams[twin_name]
        if tc.get("parent_frame"):
            raise PlanError("TWIN_CAMERA_ATTACHED: %s (expected a world-keyed level camera)" % twin_name)
        tw = twin_pose(held_world, frames[DRAPE_OF_CAMERA[held_name]], frames[DRAPE_OF_CAMERA[twin_name]])
        vals = {"Location.X": tw["loc"][0], "Location.Y": tw["loc"][1], "Location.Z": tw["loc"][2],
                "Rotation.X": tw["roll"], "Rotation.Y": tw["pitch"], "Rotation.Z": tw["yaw"]}
        keep = None
        walk_jump = None
        if p["mouth_after_hold"] == "KEEP_WALK":
            keep = tc["walk_start"]
            if keep is None:
                raise PlanError("KEEP_WALK_BUT_NO_WALK")
            first = pose_from_values({c["name"]: interp(c["keys"], keep, c["default"]) for c in tc["transform"]["sections"][0]["channels"] if c["name"] in POSE_CH})
            walk_jump = math.dist(first["loc"], tw["loc"])
            warnings.append("WALK_SEAT_JUMP: the kept walk-in starts %.1f cm from the new seat at frame %d" % (walk_jump, keep))
        else:
            if tc.get("walk_start") is not None:
                warnings.append("WALKIN_REMOVED: %s held to the end; its walk-in from frame %d is replaced (spec: hold to the I2 end)"
                                % (twin_name, tc["walk_start"]))
        twin_tr = constant_spec(tc["transform"], vals, 0, hold_end, keep)
        twin_lens = {"CurrentFocalLength": constant_spec(tc["lens"]["CurrentFocalLength"], {c["name"]: focal for c in tc["lens"]["CurrentFocalLength"]["sections"][0]["channels"]}, 0, hold_end, keep),
                     "ManualFocusDistance": constant_spec(tc["lens"]["ManualFocusDistance"], {c["name"]: focus for c in tc["lens"]["ManualFocusDistance"]["sections"][0]["channels"]}, 0, hold_end, keep)}
        twin = {"name": twin_name, "pose": tw, "transform": twin_tr, "lens": twin_lens, "walk_jump_cm": walk_jump,
                "cuts_in": [[a, b] for n, a, b in later if n == twin_name]}

    # ---- F16 (a) curtain first
    fade = facts["fade_start"]
    if p["drape_visible_from"] == "I2_START":
        v_from, v_src = 0, "I2_START"
    elif p["drape_visible_from"] == "DARKNESS":
        df, table = darkness_frame(facts["hangar_light_specs"], fade, float(p["dark_threshold_cd"]))
        if df is None:
            raise PlanError("DARKNESS_NOT_REACHED_BEFORE_FADE: %s" % json.dumps(table, sort_keys=True))
        v_from, v_src = df, "DARKNESS"
    else:
        v_from, v_src = int(p["drape_visible_from"]), "frame arg"
    z_hung = float(hung_vals["Location.Z"])
    now_states = [drape_state(drape["specs"], f, z_hung, p["visible_z_tol_cm"]) for f in sorted({0, max(0, fade - 100), fade - 1, fade})]
    new_drape, dmeta = drape_plan(drape["specs"], v_from, fade, hung_vals, p["visible_z_tol_cm"])
    refusals += check_drape(new_drape, v_from, fade, z_hung, p["visible_z_tol_cm"])
    darkness_info = darkness_frame(facts["hangar_light_specs"], fade, float(p["dark_threshold_cd"]))

    # ---- F16 (c) coverage + RESIZE_SPOT
    cam = facts["camera_optics"][held_name]
    box = facts["hang_aabb_cm"]
    cov = {"held": coverage(held_world, focal, cam["filmback"], cam["constrain"], cam["aspect"], p["output_aspect"],
                            frames[DRAPE_OF_CAMERA[held_name]], box)}
    if twin:
        co = facts["camera_optics"][twin_name]
        cov["twin"] = coverage(twin["pose"], focal, co["filmback"], co["constrain"], co["aspect"], p["output_aspect"],
                               frames[DRAPE_OF_CAMERA[twin_name]], box)
    flags = []
    for k, c in cov.items():
        if not c["fills_frame"]:
            flags.append("DRAPE_DOES_NOT_FILL_FRAME|%s|coverage=%.4f|margins=%s" % (
                k, c["coverage_fraction"], json.dumps({e: (None if v["margin_cm"] is None else round(v["margin_cm"], 1))
                                                     for e, v in c["margins"].items()}, sort_keys=True)))
    hits = {NAMES["spot_hangar"]: spot_hit(facts["spot_poses"][NAMES["spot_hangar"]], hangar_frame, box),
            NAMES["spot_mouth"]: spot_hit(facts["spot_poses"][NAMES["spot_mouth"]], mouth_frame, box)}
    rflags, rrows = resize_spot_check(hits, facts["gs_twins"], box, p["spot_tol_cm"])
    flags += rflags

    guids = {"drape": drape["guid"], "held_cam": hc["guid"], "held_cam_comp": hc["comp_guid"]}
    if twin:
        guids.update({"twin_cam": cams[twin_name]["guid"], "twin_cam_comp": cams[twin_name]["comp_guid"]})
    writes = {"drape": new_drape, "held": {"name": held_name, "transform": held_tr, "lens": held_lens}, "twin": twin}
    plan = {"tool_version": TOOL_VERSION, "sequence": SEQ_PATH, "fps": fps, "playback": pb, "mapping": m,
            "hold_frame": h, "hold_end": hold_end, "held_camera": held_name, "held_cut": cut_row,
            "held_world_pose": held_world, "held_rel_pose": rel_pose, "lens": {"focal_mm": focal, "focus_cm": focus},
            "poses_near_frame": poses_near, "rounding_spread": spread, "later_cuts": later, "twin_needed": twin_needed,
            "drape": {"visible_from": v_from, "visible_from_source": v_src, "fade_start": fade, "hung_ref_frame": hung_ref,
                      "hung_pose": hung_pose, "states_now": now_states, "darkness": darkness_info, **dmeta},
            "coverage": cov, "resize_spot": rrows, "flags": flags, "f18": f18, "guids": guids,
            "owned": sorted(owned_keys_apply(guids, bool(twin))), "writes": writes, "params": p}
    plan["digest"] = digest({k: v for k, v in plan.items() if k not in ("digest", "params")} | {"params": {k: v for k, v in p.items() if k != "fix_steps"}})
    return plan, refusals, warnings


# =====================================================================================================================
# Unreal side.  `unreal` is imported only inside these functions.
# =====================================================================================================================

def _ue():
    import unreal  # noqa: WPS433 - deliberately local: no unreal object at module level
    return unreal


def _here():
    ue = _ue()
    saved = ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir())
    return os.path.join(saved, "CodexConductor", FOLDER)


def _saved():
    return os.path.dirname(os.path.dirname(_here()))


def _cc():
    return os.path.dirname(_here())


def _log(text):
    _ue().log(text)


def _stop(run, reason):
    msg = "%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason)
    _ue().log_error(msg)
    raise Stop(msg)


def _load_json(path, required=False):
    if not os.path.isfile(path):
        if required:
            raise PlanError("MISSING_FILE|" + path)
        return None
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


def _write_json(path, value, exclusive=False):
    text = json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=str)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            h.write(text)
            h.flush()
            os.fsync(h.fileno())
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        h.write(text)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


def _census():
    ue = _ue()
    lib = ue.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _guid(v):
    return _ue().GuidLibrary.conv_guid_to_string(v)


def _actors():
    ue = _ue()
    return list(ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors())


def _content_file(path):
    ue = _ue()
    project = ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _plain(v):
    if isinstance(v, bool) or v is None or isinstance(v, (int, float, str)):
        return v
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return str(v)


def _prop(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:  # noqa: BLE001
        return None


def _path_of(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _preflight(mode, run, confirm):
    ue = _ue()
    if CONFIRMS.get(mode) != str(confirm or "").strip():
        _stop(run, "CONFIRM_MISMATCH|want %r|got %r" % (CONFIRMS.get(mode), confirm))
    editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    if ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")
    c = _census()
    if c != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(c))
    if any(str(a.get_actor_label()).startswith("ZZ_") for a in _actors()):
        _stop(run, "ZZ_ACTORS_PRESENT")
    return world


def _sequence(run):
    ue = _ue()
    show = ue.load_asset(SHOW_PATH)
    if show is None:
        _stop(run, "SHOW_LOAD")
    rows = [c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == CUE_LABEL
            and c.get_editor_property("enabled")]
    if len(rows) != 1:
        _stop(run, "CUE_COUNT|%d" % len(rows))
    seq = rows[0].get_editor_property("scene").get_editor_property("sequence")
    if seq is None or _path_of(seq) != SEQ_PATH:
        _stop(run, "CUE_SEQUENCE|%s" % (_path_of(seq),))
    return show, seq


def _segments(show):
    ue = _ue()
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / float(tick.denominator)
    tr = ue.new_object(ue.InfinityStageTransportController)
    tr.build_segments(show)
    out = [{"label": str(s.get_editor_property("label")), "start": s.get_editor_property("start_frame").value / rate,
            "end": s.get_editor_property("end_frame").value / rate} for s in tr.get_editor_property("segments")]
    del tr
    return out


def _channel_row(c):
    ue = _ue()
    keys, interps = [], set()
    for k in c.get_keys():
        t = k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        f, sub = int(t.frame_number.value), float(getattr(t, "sub_frame", 0.0) or 0.0)
        keys.append([f if abs(sub) < 1.0e-6 else f + sub, _plain(k.get_value())])
        try:
            interps.add(str(k.get_interpolation_mode()))
        except Exception:  # noqa: BLE001
            interps.add("unreadable")
    default = None
    try:
        if not hasattr(c, "has_default") or c.has_default():
            default = _plain(c.get_default())
    except Exception:  # noqa: BLE001
        default = None
    raw = str(c.channel_name)
    return {"name": norm_channel(raw), "raw": raw, "default": default, "keys": keys, "interp": sorted(interps)}


def _section_row(cls, s):
    r = [int(s.get_start_frame()) if s.has_start_frame() else None, int(s.get_end_frame()) if s.has_end_frame() else None]
    row = {"range": r, "channels": [_channel_row(c) for c in s.get_all_channels()]}
    if cls == "MovieSceneGeometryCacheTrack":
        prm = s.get_editor_property("params")
        row["so"] = int(prm.get_editor_property("start_frame_offset").value)
        row["eo"] = int(prm.get_editor_property("end_frame_offset").value)
        row["asset"] = _path_of(prm.get_editor_property("geometry_cache_asset"))
    return row


def _track_row(t):
    cls = t.get_class().get_name()
    prop = path = None
    try:
        prop, path = str(t.get_property_name()), str(t.get_property_path())
    except Exception:  # noqa: BLE001
        pass
    row = {"class": cls, "name": str(t.get_display_name()), "prop": prop or "", "path": path or "",
           "sections": sorted((_section_row(cls, s) for s in t.get_sections()), key=lambda r: json.dumps(r["range"]))}
    if cls == "MovieSceneMaterialParameterCollectionTrack":
        row["mpc"] = _path_of(_prop(t, "mpc"))
    return row


def _template_props(binding):
    tmpl = binding.get_object_template()
    if tmpl is None:
        return None
    comp = _prop(tmpl, "spot_light_component")
    if comp is None:
        return None
    out = {}
    for p in GOBO_PROPS:
        v = _prop(comp, p)
        out[p] = _path_of(v) if p == "light_function_material" else (str(v) if p == "intensity_units" else _plain(v))
    root = _prop(tmpl, "root_component")
    if root is not None:
        loc, rot = _prop(root, "relative_location"), _prop(root, "relative_rotation")
        out["_root"] = {"loc": [float(loc.x), float(loc.y), float(loc.z)], "pitch": float(rot.pitch), "yaw": float(rot.yaw),
                        "roll": float(rot.roll)}
    return out


def _snapshot(seq):
    ue = _ue()
    rate = seq.get_display_rate()
    bindings = []
    templates = {}
    for b in seq.get_bindings():
        parent = b.get_parent()
        name = str(b.get_display_name())
        bindings.append({"guid": _guid(b.get_id()), "name": name,
                         "parent": _guid(parent.get_id()) if parent is not None and parent.is_valid() else "",
                         "tracks": sorted((_track_row(t) for t in b.get_tracks()),
                                          key=lambda r: (r["class"], r["name"], r["prop"]))})
        if name in (NAMES["spot_hangar"], NAMES["spot_mouth"]):
            templates[name] = _template_props(b)
    bindings.sort(key=lambda r: (r["name"], r["guid"]))
    cuts = []
    for t in seq.find_tracks_by_type(ue.MovieSceneCameraCutTrack):
        for s in t.get_sections():
            cuts.append([_guid(s.get_camera_binding_id().get_editor_property("guid")),
                         int(s.get_start_frame()) if s.has_start_frame() else int(seq.get_playback_start()),
                         int(s.get_end_frame()) if s.has_end_frame() else int(seq.get_playback_end()), bool(s.is_active())])
    roots = sorted((_track_row(t) for t in seq.get_tracks() if t.get_class().get_name() != "MovieSceneCameraCutTrack"),
                   key=lambda r: (r["class"], r["name"]))
    marks = sorted([str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)]
                   for m in seq.get_marked_frames_from_sequence(ue.MovieSceneTimeUnit.DISPLAY_RATE))
    return {"fps": rate.numerator / float(rate.denominator), "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
            "bindings": bindings, "cuts": sorted(cuts), "root_tracks": roots, "markers": marks, "templates": templates}


def _bindings_named(seq, name):
    return [b for b in seq.get_bindings() if str(b.get_display_name()) == name]


def _one_binding(seq, name, run):
    rows = _bindings_named(seq, name)
    if len(rows) != 1:
        _stop(run, "BINDING_COUNT|%s|%d" % (name, len(rows)))
    return rows[0]


def _child(seq, parent, run, suffix="/CameraComponent"):
    pg = _guid(parent.get_id())
    rows = [b for b in seq.get_bindings() if b.get_parent() is not None and b.get_parent().is_valid()
            and _guid(b.get_parent().get_id()) == pg and str(b.get_display_name()).endswith(suffix)]
    if len(rows) != 1:
        _stop(run, "CHILD_BINDING_COUNT|%s%s|%d" % (parent.get_display_name(), suffix, len(rows)))
    return rows[0]


def _track(binding, cls, name, prop, run):
    rows = []
    for t in binding.get_tracks():
        if t.get_class().get_name() != cls or str(t.get_display_name()) != name:
            continue
        if prop:
            try:
                if str(t.get_property_name()) != prop:
                    continue
            except Exception:  # noqa: BLE001
                continue
        rows.append(t)
    if len(rows) != 1:
        _stop(run, "TRACK_COUNT|%s|%s|%s|%s|%d" % (binding.get_display_name(), cls, name, prop, len(rows)))
    if len(list(rows[0].get_sections())) != 1:
        _stop(run, "SECTION_COUNT|%s|%s|%d" % (binding.get_display_name(), cls, len(list(rows[0].get_sections()))))
    return rows[0]


def _evaluate(seq, track, frame):
    """Engine evaluation of every channel of the track's single section at `frame` [decl MovieSceneScriptingChannel.h:218-243]."""
    ue = _ue()
    rng = seq.make_range(int(frame), 1)
    rate = seq.get_display_rate()
    out = {}
    for c in list(track.get_sections())[0].get_all_channels():
        vals = list(c.evaluate_keys(rng, rate))
        if len(vals) != 1:
            raise PlanError("EVALUATE_KEYS_RETURNED_%d|%s" % (len(vals), c.channel_name))
        out[norm_channel(str(c.channel_name))] = _plain(vals[0])
    return out


def _evaluate_range(seq, track, start, count):
    rng = seq.make_range(int(start), int(count))
    rate = seq.get_display_rate()
    c = list(list(track.get_sections())[0].get_all_channels())[0]
    vals = list(c.evaluate_keys(rng, rate))
    return [(int(start) + i, float(v)) for i, v in enumerate(vals)]


def _spec_of(track):
    row = _track_row(track)
    return {"class": row["class"], "name": row["name"], "prop": row["prop"], "path": row["path"],
            "sections": row["sections"]}


def _camera_facts(seq, name, h, run, actors_by_label):
    b = _one_binding(seq, name, run)
    comp = _child(seq, b, run)
    tr = _track(b, "MovieScene3DTransformTrack", CAM_TRACK, "", run)
    spec = _spec_of(tr)
    lens_tracks = {p: _track(comp, "MovieSceneFloatTrack", CAM_TRACK, p, run) for p in LENS_PROPS}
    lens = {p: _spec_of(t) for p, t in lens_tracks.items()}
    ev = evaluated_record(_guid(b.get_id()), h, spec, _evaluate(seq, tr, h))
    ev_lens = {p: evaluated_record(_guid(comp.get_id()), h, lens[p], _evaluate(seq, lens_tracks[p], h)) for p in LENS_PROPS}
    near = {f: _evaluate(seq, tr, f) for f in (h - 1, h + 1) if f >= 0}
    actor = actors_by_label.get(name, [])
    if len(actor) != 1:
        _stop(run, "CAMERA_ACTOR_COUNT|%s|%d" % (name, len(actor)))
    parent = actor[0].get_attach_parent_actor()
    pframe = None
    if parent is not None:
        pl, pr = parent.get_actor_location(), parent.get_actor_rotation()
        if abs(pr.pitch) > 1e-3 or abs(pr.roll) > 1e-3:
            _stop(run, "CAMERA_PARENT_TILTED|%s" % name)
        pframe = {"label": str(parent.get_actor_label()), "loc": [float(pl.x), float(pl.y), float(pl.z)], "yaw": float(pr.yaw)}
    # walk start: first key after which the pose channels stop being constant at their first value
    walk = None
    chs = [c for c in spec["sections"][0]["channels"] if c["name"] in POSE_CH and c["keys"]]
    for c in chs:
        v0 = c["keys"][0][1]
        for f, v in c["keys"]:
            if abs(float(v) - float(v0)) > 1.0e-3:
                walk = f if walk is None else min(walk, f)
                break
    return {"guid": _guid(b.get_id()), "comp_guid": _guid(comp.get_id()), "transform": spec, "lens": lens,
            "eval_transform": ev, "eval_lens": ev_lens, "eval_near": near, "parent_frame": pframe,
            "walk_start": (int(walk) - 1) if walk is not None else None}


def _optics(actor):
    comp = actor.get_cine_camera_component()
    fb = comp.get_editor_property("filmback")
    w, hh = float(fb.get_editor_property("sensor_width")), float(fb.get_editor_property("sensor_height"))
    constrain = _prop(comp, "constrain_aspect_ratio")
    aspect = _prop(comp, "aspect_ratio")
    return {"filmback": [w, hh], "constrain": bool(constrain) if constrain is not None else False,
            "constrain_read": constrain is not None, "aspect": float(aspect) if aspect else w / hh,
            "focal_static": _plain(_prop(comp, "current_focal_length"))}


def _facts(seq, show, p, run, snap=None):
    ue = _ue()
    snap = snap or _snapshot(seq)
    actors = _actors()
    by_label = {}
    for a in actors:
        by_label.setdefault(str(a.get_actor_label()), []).append(a)
    segs = _segments(show)
    m = frame_mapping(segs, p, snap["fps"], snap["playback"])
    h = m["frame"]
    cams = {n: _camera_facts(seq, n, h, run, by_label) for n in CAMERAS}
    optics = {n: _optics(by_label[n][0]) for n in CAMERAS}
    # drape
    db = _one_binding(seq, NAMES["drape"], run)
    spawn_t = [t for t in db.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    gc_t = [t for t in db.get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
    vis_t = [t for t in db.get_tracks() if t.get_class().get_name() == "MovieSceneVisibilityTrack"]
    if len(spawn_t) != 1 or len(gc_t) != 1:
        _stop(run, "DRAPE_TRACKS|spawn=%d|gc=%d" % (len(spawn_t), len(gc_t)))
    dtr = _track(db, "MovieScene3DTransformTrack", CAM_TRACK, "", run)
    specs = {"spawn": _spec_of(spawn_t[0]), "transform": _spec_of(dtr), "gc": _spec_of(gc_t[0]),
             "vis": [_spec_of(t) for t in vis_t]}
    sp = specs["spawn"]["sections"][0]["channels"][0]
    offs = sorted(int(f) for f, v in sp["keys"] if not v and any(vv for _, vv in sp["keys"]))
    on = [int(f) for f, v in sp["keys"] if v]
    strike = [f for f in offs if on and f > min(on)]
    if not strike:
        _stop(run, "DRAPE_SPAWN_SHAPE|%r" % sp["keys"])
    hung_ref = strike[0] - 1
    eval_hung = evaluated_record(_guid(db.get_id()), hung_ref, specs["transform"], _evaluate(seq, dtr, hung_ref))
    gsec = list(gc_t[0].get_sections())
    cache = gsec[0].get_editor_property("params").get_editor_property("geometry_cache_asset") if gsec else None
    gc_window = None
    if cache is not None:
        tick = seq.get_tick_resolution()
        dur = int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / CACHE_FPS
                        * tick.numerator / float(tick.denominator)))
        gc_window = [dur - r["so"] - r["eo"] for r in specs["gc"]["sections"]]
    # mouth drape
    mb = _one_binding(seq, NAMES["mouth_drape"], run)
    mt = mb.get_object_template()
    mroot = mt.get_editor_property("root_component")
    ml, mr = mroot.get_editor_property("relative_location"), mroot.get_editor_property("relative_rotation")
    if abs(mr.pitch) > 1e-3 or abs(mr.roll) > 1e-3:
        _stop(run, "MOUTH_DRAPE_TILTED")
    mouth_frame = {"loc": [float(ml.x), float(ml.y), float(ml.z)], "yaw": float(mr.yaw)}
    mgc = [t for t in mb.get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
    if len(mgc) != 1:
        _stop(run, "MOUTH_DRAPE_GC_TRACKS|%d" % len(mgc))
    # spots
    spot_poses, spot_int = {}, {}
    for label in (NAMES["spot_hangar"], NAMES["spot_mouth"]):
        b = _one_binding(seq, label, run)
        t = _track(b, "MovieScene3DTransformTrack", SPOT_TRACK, "", run)
        spot_poses[label] = pose_from_values(_evaluate(seq, t, h))
        ft = [x for x in b.get_tracks() if x.get_class().get_name() == "MovieSceneFloatTrack"
              and str(x.get_display_name()) == SPOT_TRACK]
        if len(ft) != 1:
            _stop(run, "SPOT_FLOAT_TRACK|%s|%d" % (label, len(ft)))
        spot_int[label] = ft[0]
    fade = fade_start_of(_evaluate_range(seq, spot_int[NAMES["spot_hangar"]], 0, min(snap["playback"][1], 1000)))
    # hangar lights keyed in I2 (component float 'Intensity' on possessable children; not the spots)
    hl = []
    for b in snap["bindings"]:
        if not b["name"].endswith("/LightComponent"):
            continue
        for t in b["tracks"]:
            if t["class"] == "MovieSceneFloatTrack" and t["prop"] == "Intensity" and t["sections"]:
                c = t["sections"][0]["channels"][0]
                hl.append((b["name"].split("/")[0], c["keys"], c["default"]))
    # references (files)
    cc = _cc()
    sd = _load_json(os.path.join(cc, REF["sleight_dry"]), required=True)
    box = sd["inputs"]["cache"]["hang_aabb_cm"]
    gs = _load_json(os.path.join(cc, REF["gs_dry"]), required=True)
    gs_twins = gs["plan"]["twins"]
    return {"snapshot": snap, "segments": segs, "cameras": cams, "camera_optics": optics,
            "drape": {"guid": _guid(db.get_id()), "specs": specs, "hung_ref_frame": hung_ref, "eval_hung": eval_hung,
                      "gc_window_ticks": gc_window},
            "mouth_drape_frame": mouth_frame, "mouth_drape_gc": _spec_of(mgc[0]), "spot_poses": spot_poses,
            "fade_start": fade, "hangar_light_specs": hl, "hang_aabb_cm": box, "gs_twins": gs_twins}


# ------------------------------------------------------------------------------------------------ lighting (live)

def _light_rows(actors, snap, frame):
    ue = _ue()
    by_binding = {b["name"]: b for b in snap["bindings"]}
    rows = []
    for a in actors:
        if not isinstance(a, ue.Light):
            continue
        comp = a.get_component_by_class(ue.LightComponent)
        if comp is None:
            continue
        label = str(a.get_actor_label())
        kind = "spot" if isinstance(a, ue.SpotLight) else ("directional" if isinstance(a, ue.DirectionalLight) else "point")
        loc, rot = a.get_actor_location(), a.get_actor_rotation()
        intensity = _plain(_prop(comp, "intensity"))
        src = "static property (may be keyed by another sequence: NOT evaluated)"
        cb = by_binding.get(label + "/LightComponent")
        if cb:
            ft = [t for t in cb["tracks"] if t["class"] == "MovieSceneFloatTrack" and t["prop"] == "Intensity"]
            if len(ft) == 1:
                c = ft[0]["sections"][0]["channels"][0]
                intensity, src = interp(c["keys"], frame, c["default"] if c["default"] is not None else intensity), "I2 keyed (evaluated)"
        visible, note = True, None
        hidden = _prop(a, "hidden")
        if hidden:
            visible, note = False, "actor bHidden"
        vis_comp = _prop(comp, "visible")
        if vis_comp is False:
            visible, note = False, "component not visible"
        ab = by_binding.get(label)
        if ab:
            for t in ab["tracks"]:
                if t["class"] != "MovieSceneVisibilityTrack":
                    continue
                if t["prop"] == "bHiddenInGame":
                    note = (note or "") + " INERT bHiddenInGame track ignored"
                    continue
                c = t["sections"][0]["channels"][0]
                if not bool_at(c["keys"], frame, c["default"]):
                    visible, note = False, "I2 visibility track (bHidden) hides it"
        col = _prop(comp, "light_color")
        rows.append({"label": label, "kind": kind, "loc": [float(loc.x), float(loc.y), float(loc.z)],
                     "rot": {"pitch": float(rot.pitch), "yaw": float(rot.yaw), "roll": float(rot.roll)},
                     "intensity": float(intensity or 0.0), "intensity_source": src,
                     "units": str(_prop(comp, "intensity_units")), "radius": _plain(_prop(comp, "attenuation_radius")),
                     "outer": _plain(_prop(comp, "outer_cone_angle")), "inner": _plain(_prop(comp, "inner_cone_angle")),
                     "color": None if col is None else [int(col.r), int(col.g), int(col.b)],
                     "use_temperature": _plain(_prop(comp, "use_temperature")), "temperature": _plain(_prop(comp, "temperature")),
                     "lf": _path_of(_prop(comp, "light_function_material")), "affects_world": _plain(_prop(comp, "affects_world")),
                     "effective_visible": visible and _prop(comp, "affects_world") is not False, "vis_note": note,
                     "tags": [str(t) for t in (a.tags or [])]})
    return rows


def _spawned_spot_rows(snap, frame):
    out = []
    for label in (NAMES["spot_hangar"], NAMES["spot_mouth"]):
        b = [x for x in snap["bindings"] if x["name"] == label]
        tmpl = snap["templates"].get(label) or {}
        if len(b) != 1:
            continue
        tr = {t["class"]: t for t in b[0]["tracks"]}
        pose = {}
        for c in tr["MovieScene3DTransformTrack"]["sections"][0]["channels"]:
            if c["name"] in POSE_CH:
                pose[c["name"]] = interp(c["keys"], frame, c["default"])
        ps = pose_from_values(pose)
        ic = tr["MovieSceneFloatTrack"]["sections"][0]["channels"][0]
        sc = tr["MovieSceneSpawnTrack"]["sections"][0]["channels"][0]
        out.append({"label": label, "kind": "spot", "loc": ps["loc"], "rot": {"pitch": ps["pitch"], "yaw": ps["yaw"], "roll": ps["roll"]},
                    "intensity": interp(ic["keys"], frame, ic["default"]), "intensity_source": "I2 keyed (evaluated, IST track)",
                    "units": tmpl.get("intensity_units"), "radius": tmpl.get("attenuation_radius"),
                    "outer": tmpl.get("outer_cone_angle"), "inner": tmpl.get("inner_cone_angle"), "color": None,
                    "use_temperature": None, "temperature": None, "lf": tmpl.get("light_function_material"),
                    "effective_visible": bool_at(sc["keys"], frame, sc["default"]), "vis_note": "spawn track", "tags": []})
    return out


def _ppv_rows(actors, point):
    ue = _ue()
    rows = []
    for v in actors:
        if not isinstance(v, ue.PostProcessVolume):
            continue
        unbound = bool(_prop(v, "unbound"))
        o, e = v.get_actor_bounds(False)
        radius = float(_prop(v, "blend_radius") or 0.0)
        dx = max(abs(point[0] - o.x) - e.x, abs(point[1] - o.y) - e.y, abs(point[2] - o.z) - e.z)
        if not unbound and dx > radius:
            continue
        weight = float(_prop(v, "blend_weight") if _prop(v, "blend_weight") is not None else 1.0)
        if not unbound and dx > 0.0 and radius > 0.0:
            weight *= max(0.0, 1.0 - dx / radius)       # [inf] linear blend over BlendRadius
        st = _prop(v, "settings")
        rows.append({"name": str(v.get_actor_label()), "unbound": unbound, "priority": float(_prop(v, "priority") or 0.0),
                     "enabled": bool(_prop(v, "enabled")), "weight": weight, "overrides": _pp_overrides(st)})
    return rows


def _pp_overrides(st):
    if st is None:
        return {}
    out = {}
    for field, flag, name in (("method", "override_auto_exposure_method", "auto_exposure_method"),
                              ("bias", "override_auto_exposure_bias", "auto_exposure_bias"),
                              ("min_ev", "override_auto_exposure_min_brightness", "auto_exposure_min_brightness"),
                              ("max_ev", "override_auto_exposure_max_brightness", "auto_exposure_max_brightness")):
        if _prop(st, flag):
            v = _prop(st, name)
            out[field] = str(v) if field == "method" else _plain(v)
    return out


def _camera_pp(actor):
    comp = actor.get_cine_camera_component()
    return {"name": "camera:" + str(actor.get_actor_label()), "priority": 1.0e9,
            "weight": float(_prop(comp, "post_process_blend_weight") or 0.0),
            "overrides": _pp_overrides(_prop(comp, "post_process_settings"))}


def _fog_rows(actors, cam_loc, point):
    ue = _ue()
    out = []
    for a in actors:
        cls = a.get_class().get_name()
        if cls == "ExponentialHeightFog":
            comp = a.get_component_by_class(ue.ExponentialHeightFogComponent) if hasattr(ue, "ExponentialHeightFogComponent") else None
            row = {"label": str(a.get_actor_label()), "class": cls, "z": float(a.get_actor_location().z)}
            for p in ("fog_density", "fog_height_falloff", "fog_max_opacity", "start_distance", "volumetric_fog",
                      "volumetric_fog_extinction_scale", "volumetric_fog_distance"):
                row[p] = _plain(_prop(comp, p)) if comp is not None else None
            out.append(row)
        elif cls == "LocalFogVolume":
            o, e = a.get_actor_bounds(False)
            inside = lambda q: abs(q[0] - o.x) <= e.x and abs(q[1] - o.y) <= e.y and abs(q[2] - o.z) <= e.z  # noqa: E731
            if inside(cam_loc) or inside(point):
                out.append({"label": str(a.get_actor_label()), "class": cls, "camera_inside": inside(cam_loc), "drape_inside": inside(point)})
    return out


def _lighting(seq, snap, facts, plan, run):
    """F17 read-only diff across every sleight cut and the I2 end."""
    actors = _actors()
    by_label = {}
    for a in actors:
        by_label.setdefault(str(a.get_actor_label()), []).append(a)
    names = {b["guid"]: b["name"] for b in snap["bindings"]}
    fps, end = snap["fps"], snap["playback"][1]
    box = facts["hang_aabb_cm"]
    zc = (float(box["z"][0]) + float(box["z"][1])) / 2.0
    frames = {NAMES["drape"]: {"loc": plan["drape"]["hung_pose"]["loc"], "yaw": plan["drape"]["hung_pose"]["yaw"]},
              NAMES["mouth_drape"]: facts["mouth_drape_frame"]}
    boundaries = sorted({c[1] for c in snap["cuts"] if 0 < c[1] < end} | {c[2] for c in snap["cuts"] if 0 < c[2] < end})
    release = (plan.get("f18") or {}).get("release_frame") or end
    out = {"cuts": [], "events": [], "window_s": plan["params"]["lighting_window_s"]}

    def side(frame):
        cam, _ = live_camera_at(snap["cuts"], frame, names)
        if cam not in CAMERAS:
            return {"camera": cam, "note": "not a sleight camera"}
        cf = facts["cameras"][cam]
        vals = {c["name"]: interp(c["keys"], frame, c["default"]) for c in cf["transform"]["sections"][0]["channels"] if c["name"] in POSE_CH}
        pose = pose_from_values(vals)
        if cf.get("parent_frame"):
            pose = compose_attached(cf["parent_frame"], pose)
        df = frames[DRAPE_OF_CAMERA[cam]]
        point = to_world(df, [float(box["x"][0]), 0.0, zc])
        normal = rot_z([-1.0, 0.0, 0.0], df["yaw"])
        lights = _light_rows(actors, snap, frame) + _spawned_spot_rows(snap, frame)
        lights = [L for L in lights if L["kind"] == "directional" or not L.get("radius") or math.dist(L["loc"], point) < float(L["radius"])]
        vols = _ppv_rows(actors, pose["loc"])
        ex = effective_exposure(vols, _camera_pp(by_label[cam][0]))
        ex["unbound"] = {v["name"]: v["unbound"] for v in vols}
        return {"camera": cam, "frame": frame, "pose": pose, "drape": DRAPE_OF_CAMERA[cam], "point": point,
                "light": side_summary(lights, point, normal), "exposure": ex,
                "fog": _fog_rows(actors, pose["loc"], point)}

    for c in boundaries:
        b, a = side(c - 1), side(c)
        if "light" not in b or "light" not in a:
            out["cuts"].append({"cut_frame": c, "before": b, "after": a, "note": "not both sleight cameras"})
            continue
        spots = {}
        for label in (NAMES["spot_hangar"], NAMES["spot_mouth"]):
            rows = [r for r in _spawned_spot_rows(snap, c - 1) if r["label"] == label] + [r for r in _spawned_spot_rows(snap, c) if r["label"] == label]
            spots[label] = (rows[0]["intensity"], rows[1]["intensity"]) if len(rows) == 2 else (None, None)
        items = rank_cut(b, a, c, fps, spots, b["fog"], a["fog"])
        win = plan["params"]["lighting_window_s"]
        out["cuts"].append({"cut_frame": c, "cut_s": c / fps, "in_gary_window": win[0] - 0.5 <= c / fps <= win[1] + 0.5,
                            "before": b, "after": a, "ranked": items,
                            "proposals": proposals_for_cut(items, b, a, c, release, end)})
    # light events (any I2-keyed light value change) from 1000 to the end: what "switches again at the end"
    for bnd in snap["bindings"]:
        for t in bnd["tracks"]:
            if (t["class"] == "MovieSceneFloatTrack" and t["prop"] == "Intensity") or t["class"] in ("MovieSceneVisibilityTrack", "MovieSceneSpawnTrack"):
                if not t["sections"] or not t["sections"][0]["channels"]:
                    continue
                keys = t["sections"][0]["channels"][0]["keys"]
                ev = [k for k in keys if float(k[0]) >= 1000]
                if ev and ("Light" in bnd["name"] or "Spot" in bnd["name"] or "Lantern" in bnd["name"] or t["class"] == "MovieSceneVisibilityTrack"):
                    out["events"].append({"binding": bnd["name"], "track": t["class"], "prop": t["prop"], "keys_from_1000": ev})
    return out


# ------------------------------------------------------------------------------------------------ writers

def _write_spec(track, spec, run):
    """Rewrite the track's single section exactly (IST precedent interaction_shadow_transition.py:427-492)."""
    ue = _ue()
    for s in list(track.get_sections()):
        track.remove_section(s)
    sec = spec["sections"][0]
    s = track.add_section()
    if sec["range"][0] is None or sec["range"][1] is None:
        _stop(run, "UNBOUNDED_SECTION|NOTHING SAVED; Don't-Save restart")
    s.set_range(int(sec["range"][0]), int(sec["range"][1]))
    chans = {norm_channel(str(c.channel_name)): c for c in s.get_all_channels()}
    for row in sec["channels"]:
        c = chans.get(row["name"])
        if c is None:
            _stop(run, "CHANNEL_MISSING|%s|NOTHING SAVED; Don't-Save restart" % row["name"])
        if row["default"] is not None:
            c.set_default(row["default"])
        for f, v in row["keys"]:
            if isinstance(v, bool):
                k = c.add_key(ue.FrameNumber(int(f)), bool(v), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
            else:
                k = c.add_key(ue.FrameNumber(int(f)), float(v), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE,
                              interpolation=ue.MovieSceneKeyInterpolation.LINEAR)
            if k is None:
                _stop(run, "ADD_KEY_NONE|%s|%s|NOTHING SAVED; Don't-Save restart" % (row["name"], f))


def _set_gc_range(track, before_range, after_range, run):
    rows = [s for s in track.get_sections() if [int(s.get_start_frame()), int(s.get_end_frame())] == list(before_range)]
    if len(rows) != 1:
        _stop(run, "GC_SECTION_NOT_FOUND|%r|NOTHING SAVED; Don't-Save restart" % (before_range,))
    rows[0].set_range(int(after_range[0]), int(after_range[1]))


def _handles(seq, plan, run):
    w = plan["writes"]
    db = _one_binding(seq, NAMES["drape"], run)
    hb = _one_binding(seq, w["held"]["name"], run)
    hcomp = _child(seq, hb, run)
    out = {"drape_spawn": [t for t in db.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"][0],
           "drape_tr": _track(db, "MovieScene3DTransformTrack", CAM_TRACK, "", run),
           "drape_gc": [t for t in db.get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"][0],
           "held_tr": _track(hb, "MovieScene3DTransformTrack", CAM_TRACK, "", run),
           "held_lens": {p: _track(hcomp, "MovieSceneFloatTrack", CAM_TRACK, p, run) for p in LENS_PROPS}}
    if w["twin"]:
        tb = _one_binding(seq, w["twin"]["name"], run)
        tcomp = _child(seq, tb, run)
        out["twin_tr"] = _track(tb, "MovieScene3DTransformTrack", CAM_TRACK, "", run)
        out["twin_lens"] = {p: _track(tcomp, "MovieSceneFloatTrack", CAM_TRACK, p, run) for p in LENS_PROPS}
    return out


def _apply_writes(seq, plan, run, originals=None):
    """Write the plan's specs (or, with originals, restore them)."""
    src = originals or plan["writes"]
    hd = _handles(seq, plan, run)
    seq.modify()
    _write_spec(hd["drape_spawn"], src["drape"]["spawn"], run)
    _write_spec(hd["drape_tr"], src["drape"]["transform"], run)
    a, b = (plan["drape"]["gc_range_before"], plan["drape"]["gc_range_after"])
    if originals is None:
        _set_gc_range(hd["drape_gc"], a, b, run)
    else:
        _set_gc_range(hd["drape_gc"], b, a, run)
    _write_spec(hd["held_tr"], src["held"]["transform"], run)
    for p in LENS_PROPS:
        _write_spec(hd["held_lens"][p], src["held"]["lens"][p], run)
    if plan["writes"]["twin"]:
        _write_spec(hd["twin_tr"], src["twin"]["transform"], run)
        for p in LENS_PROPS:
            _write_spec(hd["twin_lens"][p], src["twin"]["lens"][p], run)


def _owned_specs_live(seq, plan, run):
    hd = _handles(seq, plan, run)
    out = {"drape": {"spawn": _spec_of(hd["drape_spawn"]), "transform": _spec_of(hd["drape_tr"]), "gc": _spec_of(hd["drape_gc"])},
           "held": {"name": plan["writes"]["held"]["name"], "transform": _spec_of(hd["held_tr"]),
                    "lens": {p: _spec_of(hd["held_lens"][p]) for p in LENS_PROPS}}, "twin": None}
    if plan["writes"]["twin"]:
        out["twin"] = {"name": plan["writes"]["twin"]["name"], "transform": _spec_of(hd["twin_tr"]),
                       "lens": {p: _spec_of(hd["twin_lens"][p]) for p in LENS_PROPS}}
    return out


def _cmp_specs(got, want, path="", tol=1.0e-4):
    """Key/default equality of two spec trees (ignores interp lists and raw channel names)."""
    fail = []
    if isinstance(want, dict) and isinstance(got, dict):
        for k in want:
            if k in ("interp", "raw", "pose", "cuts_in", "walk_jump_cm", "vis"):
                continue
            fail += _cmp_specs(got.get(k), want[k], path + "/" + str(k), tol)
        return fail
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            return ["SPEC_LEN%s|%d!=%d" % (path, len(got), len(want))]
        for i, (g, w) in enumerate(zip(got, want)):
            fail += _cmp_specs(g, w, "%s[%d]" % (path, i), tol)
        return fail
    if isinstance(want, bool) or isinstance(got, bool) or want is None or got is None or isinstance(want, str):
        return [] if got == want else ["SPEC%s|%r!=%r" % (path, got, want)]
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return [] if abs(float(got) - float(want)) <= tol * max(1.0, abs(float(want))) else ["SPEC%s|%r!=%r" % (path, got, want)]
    return [] if got == want else ["SPEC%s|%r!=%r" % (path, got, want)]


def _backup(run, label):
    ue = _ue()
    project = ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())
    d = os.path.join(project, "Backups", "Pre%s-%s" % (label, run))
    os.makedirs(d, exist_ok=False)
    src = _content_file(SEQ_PATH)
    dst = os.path.join(d, os.path.basename(src))
    if not os.path.isfile(src):
        _stop(run, "BACKUP_SOURCE_MISSING|" + src)
    shutil.copy2(src, dst)
    if os.path.getsize(src) != os.path.getsize(dst):
        _stop(run, "BACKUP_SIZE_MISMATCH")
    return d, dst


def _save_ls(run):
    ue = _ue()
    c = _census()
    if c != {"content": [SEQ_PATH], "maps": []}:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(c))
    if not bool(ue.EditorAssetLibrary.save_asset(SEQ_PATH, only_if_is_dirty=True)):
        _stop(run, "SAVE_FAILED|%s" % SEQ_PATH)
    c = _census()
    if c != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(c))


def _post_checks(seq, plan, run):
    """Engine re-evaluation after the write: holds equal the evaluated pose; curtain visible before the fade."""
    fail = []
    w = plan["writes"]
    hd = _handles(seq, plan, run)
    want = plan["held_values"]
    for f in (plan["hold_frame"], plan["hold_end"], min(plan["playback"][1] - 1, plan["hold_end"] + 25)):
        got = _evaluate(seq, hd["held_tr"], f)
        for k, v in want["transform"].items():
            if k in got and abs(float(got[k]) - float(v)) > 1.0e-3 * max(1.0, abs(float(v))):
                fail.append("POST_HOLD|%s|f=%d|%r!=%r" % (k, f, got[k], v))
    live = _owned_specs_live(seq, plan, run)
    d = {"spawn": live["drape"]["spawn"], "transform": live["drape"]["transform"], "gc": live["drape"]["gc"],
         "vis": w["drape"].get("vis", [])}
    fail += check_drape(d, plan["drape"]["visible_from"], plan["drape"]["fade_start"],
                        float(plan["drape"]["hung_pose"]["loc"][2]), plan["params"]["visible_z_tol_cm"])
    return fail


def _read_refs():
    cc = _cc()
    return {k: _load_json(os.path.join(cc, v)) for k, v in REF.items()}


def _extend_source():
    path = os.path.join(_saved(), EXTEND_TOOL_REL)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as h:
        return h.read()


def _report(seq, show, p, run, snap=None):
    snap = snap or _snapshot(seq)
    facts = _facts(seq, show, p, run, snap)
    plan, refusals, warnings = build_plan(facts, p)
    hc = facts["cameras"][plan["held_camera"]]
    plan["held_values"] = {"transform": hc["eval_transform"]["values"],
                           "lens": {k: hc["eval_lens"][k]["values"] for k in LENS_PROPS}}
    refs = _read_refs()
    warnings += guard_vs_records(snap, refs.get("ag_record"), refs.get("gs_record"))
    if facts["drape"].get("gc_window_ticks") and any(w > 1 for w in facts["drape"]["gc_window_ticks"]):
        warnings.append("GC_WINDOW_ANIMATES|%r: moving the section start shifts the sampled frame" % facts["drape"]["gc_window_ticks"])
    for vt in facts["drape"]["specs"]["vis"]:
        if vt["prop"] == "bHiddenInGame":
            refusals.append("DRAPE_HAS_INERT_bHiddenInGame_TRACK")
    interps = set()
    for spec in [facts["drape"]["specs"]["transform"], hc["transform"]] + list(hc["lens"].values()):
        for c in spec["sections"][0]["channels"]:
            interps.update(c.get("interp") or [])
    if interps - {"RichCurveInterpMode.RCIM_LINEAR", "unreadable", "<RichCurveInterpMode.RCIM_LINEAR: 0>"}:
        warnings.append("NONLINEAR_OR_UNKNOWN_INTERP|%r (REVERT rewrites LINEAR keys)" % sorted(interps))
    names = {b["guid"]: b["name"] for b in snap["bindings"]}
    past = past_end_listing(snap, plan["f18"]["new_end_frame"], names) if plan.get("f18") else None
    if past is not None:
        own = []
        w = plan["writes"]
        specs = [("drape.spawn", w["drape"]["spawn"]), ("drape.transform", w["drape"]["transform"]),
                 ("held.transform", w["held"]["transform"])] + [("held." + k, v) for k, v in w["held"]["lens"].items()]
        if w["twin"]:
            specs += [("twin.transform", w["twin"]["transform"])] + [("twin." + k, v) for k, v in w["twin"]["lens"].items()]
        for label, spec in specs:
            for c in spec["sections"][0]["channels"]:
                late = [k for k in c["keys"] if float(k[0]) > plan["f18"]["new_end_frame"]]
                if late:
                    own.append({"spec": label, "channel": c["name"], "keys": late})
        past["own_writes_after_apply_past_N"] = own
        past["own_hold_end"] = plan["hold_end"]
    ext = extend_prediction(_extend_source(), plan["f18"]["new_end_frame"], snap["playback"][1]) if plan.get("f18") else None
    if ext and ext["will_refuse"]:
        warnings.append("EXTEND_TOOL_WILL_REFUSE_SHORTENING|extend_scene_playback.py:345-346")
    lighting = _lighting(seq, snap, facts, plan, run)
    return {"schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "sequence": SEQ_PATH,
            "apply_ready": not refusals, "refusals": refusals, "warnings": warnings, "flags": plan["flags"],
            "plan": plan, "plan_digest": plan["digest"], "guards": guard_hashes(snap), "f18_past_end": past,
            "f18_extend_prediction": ext, "lighting": lighting, "claims": CLAIMS,
            "api_table": [{"call": a, "tier": b, "cite": c} for a, b, c in API_TABLE],
            "inputs_digest": digest(facts["snapshot"]), "drape_gc_window_ticks": facts["drape"]["gc_window_ticks"]}


def _print_dry(run, rep, out):
    pl = rep["plan"]
    m = pl["mapping"]
    _log("%s_MAPPING|run=%s|cue=%d/%d|segment=[%.3f,%.3f]|seconds=%.3f|exact=%.2f|H=%d|clock=%s->I2[%.3f,%.3f)s|consistent=%d"
         % (MARK, run, m["cue_index_1based"], m["segment_count"], m["segment"]["start"], m["segment"]["end"],
            m["seconds_into_cue"], m["exact_frame"], m["frame"], m["clock"], m["clock_window_local_s"][0],
            m["clock_window_local_s"][1], int(m["clock_consistent"])))
    hw = pl["held_world_pose"]
    _log("%s_HOLD|run=%s|camera=%s|cut=[%d,%d)|H=%d|hold_end=%d|loc=%.1f,%.1f,%.1f|pitch=%.3f|yaw=%.3f|focal=%.3f|focus=%.1f|spread_cm=%.1f|twin=%s"
         % (MARK, run, pl["held_camera"], pl["held_cut"][1], pl["held_cut"][2], pl["hold_frame"], pl["hold_end"],
            hw["loc"][0], hw["loc"][1], hw["loc"][2], hw["pitch"], hw["yaw"], pl["lens"]["focal_mm"], pl["lens"]["focus_cm"],
            pl["rounding_spread"]["max_cm"], (pl["writes"]["twin"] or {}).get("name")))
    d = pl["drape"]
    _log("%s_CURTAIN|run=%s|visible_from=%d(%s)|fade_start=%d|strike=%d|gc=%r->%r|now@fade=%s|darkness=%s"
         % (MARK, run, d["visible_from"], d["visible_from_source"], d["fade_start"], d["strike"], d["gc_range_before"],
            d["gc_range_after"], json.dumps({s["frame"]: s["visible"] for s in d["states_now"]}),
            json.dumps(d["darkness"][0])))
    for k, c in pl["coverage"].items():
        _log("%s_COVERAGE|run=%s|%s|fills=%d|coverage=%.4f|margins_cm=%s|footprint=%s|aspect=%s"
             % (MARK, run, k, int(c["fills_frame"]), c["coverage_fraction"],
                json.dumps({e: (None if v["margin_cm"] is None else round(v["margin_cm"], 1)) for e, v in c["margins"].items()}, sort_keys=True),
                json.dumps({kk: round(vv, 1) for kk, vv in (c["footprint_cm"] or {}).items() if kk != "centre_yz"}, sort_keys=True),
                c["aspect_source"]))
    for label, r in pl["resize_spot"].items():
        _log("%s_SPOT|run=%s|%s|D=%.2f(gs %.2f)|hit_moved=%.2f" % (MARK, run, label, r["d_now_cm"], r["d_gs_cm"], r["hit_moved_cm"]))
    for c in rep["lighting"]["cuts"]:
        top = [(i["kind"], i["what"], None if i["impact_stops"] is None else round(i["impact_stops"], 2)) for i in c.get("ranked", [])[:5]]
        _log("%s_LIGHT_CUT|run=%s|frame=%d|s=%.2f|in_window=%s|top=%s|proposals=%s"
             % (MARK, run, c["cut_frame"], c.get("cut_s", 0.0), c.get("in_gary_window"), json.dumps(top),
                json.dumps([x["id"] for x in c.get("proposals", [])])))
    if rep.get("plan", {}).get("f18"):
        f = rep["plan"]["f18"]
        _log("%s_F18|run=%s|release=%d|fall_end=%d|N=%d|cut_s=%.2f|past_end=%s|extend_will_refuse=%s"
             % (MARK, run, f["release_frame"], f["fall_end_frame"], f["new_end_frame"], f["cut_s"],
                json.dumps({k: len(v) for k, v in rep["f18_past_end"].items() if isinstance(v, list)}, sort_keys=True),
                (rep.get("f18_extend_prediction") or {}).get("will_refuse")))
    for g, h in rep["guards"].items():
        _log("%s_GUARD|run=%s|%s=%s" % (MARK, run, g, h))
    for t in rep["refusals"]:
        _ue().log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, t))
    for t in rep["warnings"] + rep["flags"]:
        _log("%s_WARNING|run=%s|%s" % (MARK, run, t))


def run_dry(run, p, confirm):
    _preflight("DRY", run, confirm)
    show, seq = _sequence(run)
    here = _here()
    rec = _load_json(os.path.join(here, RECORD))
    rep = _report(seq, show, p, run)
    if rec and rec.get("applied"):
        rep["warnings"].append("RECORD_APPLIED: this DRY reads the APPLIED state (use VERIFY)")
    out = os.path.join(here, DRY_PATTERN % run)
    _write_json(out, rep)
    _write_json(os.path.join(here, PLAN_FILE), {"run": run, "plan_digest": rep["plan_digest"], "params": p,
                                                "inputs_digest": rep["inputs_digest"]})
    if rep["plan"].get("f18"):
        _write_json(os.path.join(here, EXTEND_MODE_OUT), extend_mode_file(rep["plan"]["f18"]["new_end_frame"], run))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % json.dumps(_census()))
    _print_dry(run, rep, out)
    _log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|flags=%d|H=%d|visible_from=%d|fade=%d|fills=%d|N=%s|digest=%s|report=%s"
         % (MARK, run, int(rep["apply_ready"]), len(rep["refusals"]), len(rep["warnings"]), len(rep["flags"]),
            rep["plan"]["hold_frame"], rep["plan"]["drape"]["visible_from"], rep["plan"]["drape"]["fade_start"],
            int(rep["plan"]["coverage"]["held"]["fills_frame"]), (rep["plan"].get("f18") or {}).get("new_end_frame"),
            rep["plan_digest"], out))
    return rep


def run_apply(run, p, confirm):
    _preflight("APPLY", run, confirm)
    show, seq = _sequence(run)
    here = _here()
    rp = os.path.join(here, RECORD)
    if os.path.exists(rp):
        _stop(run, "RECORD_EXISTS|%s|nothing mutated (REVERT first)" % rp)
    before = _snapshot(seq)
    rep = _report(seq, show, p, run, before)
    if rep["refusals"]:
        _stop(run, "PLAN_REFUSED|%s" % json.dumps(rep["refusals"]))
    pf = _load_json(os.path.join(here, PLAN_FILE)) or {}
    if pf.get("plan_digest") != rep["plan_digest"]:
        _stop(run, "PLAN_CHANGED_SINCE_DRY|dry=%s|now=%s|rerun DRY" % (pf.get("plan_digest"), rep["plan_digest"]))
    plan = rep["plan"]
    originals = _owned_specs_live(seq, plan, run)
    backup, copied = _backup(run, "I2Order")
    record = {"schema_version": 1, "run": run, "applied": False, "sequence": SEQ_PATH, "backup": backup,
              "backup_files": [copied], "plan": plan, "plan_digest": plan["digest"], "originals": originals,
              "snapshot_before": before, "guards_before": guard_hashes(before), "census_before": _census()}
    try:
        _write_json(rp, record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|nothing mutated")
    _apply_writes(seq, plan, run)
    after = _snapshot(seq)
    owned = set(plan["owned"])
    problems = untouched_diff(before, after, owned)
    problems += _cmp_specs(_owned_specs_live(seq, plan, run), plan["writes"])
    if guard_hashes(after) != record["guards_before"]:
        problems.append("GUARD_CHANGED|before=%r|after=%r" % (record["guards_before"], guard_hashes(after)))
    problems += _post_checks(seq, plan, run)
    if problems:
        _stop(run, "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup %s" % (json.dumps(problems[:12]), backup))
    _save_ls(run)
    seq = _ue().load_asset(SEQ_PATH)
    after2 = _snapshot(seq)
    problems = untouched_diff(before, after2, owned) + _cmp_specs(_owned_specs_live(seq, plan, run), plan["writes"])
    if json.dumps(after2, sort_keys=True, default=str) != json.dumps(after, sort_keys=True, default=str):
        problems.append("POSTSAVE_SNAPSHOT_DIFFERS")
    if guard_hashes(after2) != record["guards_before"]:
        problems.append("GUARD_CHANGED_AFTER_SAVE")
    problems += _post_checks(seq, plan, run)
    if problems:
        _stop(run, "READBACK_FAILED_AFTER_SAVE|%s|restore from %s" % (json.dumps(problems[:12]), backup))
    record.update({"applied": True, "snapshot_after": after2, "guards_after": guard_hashes(after2),
                   "owned_after": _owned_specs_live(seq, plan, run), "census_after": _census()})
    _write_json(rp, record)
    _log("%s_APPLY_OK|run=%s|H=%d|hold_end=%d|held=%s|twin=%s|visible_from=%d|fade=%d|fills=%d|guards=unchanged|saved=%s|backup=%s|record=%s"
         % (MARK, run, plan["hold_frame"], plan["hold_end"], plan["held_camera"], (plan["writes"]["twin"] or {}).get("name"),
            plan["drape"]["visible_from"], plan["drape"]["fade_start"], int(plan["coverage"]["held"]["fills_frame"]),
            SEQ_PATH, backup, rp))
    return record


def run_verify(run, p, confirm):
    _preflight("VERIFY", run, confirm)
    show, seq = _sequence(run)
    rec = _load_json(os.path.join(_here(), RECORD))
    if not rec or not rec.get("applied"):
        _stop(run, "NOTHING_APPLIED")
    plan = rec["plan"]
    live = _snapshot(seq)
    problems = []
    fixrec = _load_json(os.path.join(_here(), FIX_RECORD))
    created = (fixrec or {}).get("created_bindings", []) if (fixrec or {}).get("applied") else []
    fix_owned = set((fixrec or {}).get("owned", [])) if (fixrec or {}).get("applied") else set()
    problems += untouched_diff(rec["snapshot_after"], live, fix_owned, created)
    problems += _cmp_specs(_owned_specs_live(seq, plan, run), plan["writes"])
    if guard_hashes(live) != rec["guards_before"]:
        problems.append("GUARD_CHANGED_SINCE_APPLY")
    problems += _post_checks(seq, plan, run)
    if _census() != {"content": [], "maps": []}:
        problems.append("VERIFY_DIRTIED")
    if problems:
        _stop(run, "VERIFY_FAILED|%s" % json.dumps(problems[:12]))
    _log("%s_VERIFY_OK|run=%s|applied_run=%s|mutated=0|H=%d|visible_from=%d|guards=unchanged" %
         (MARK, run, rec["run"], plan["hold_frame"], plan["drape"]["visible_from"]))


def run_revert(run, p, confirm):
    _preflight("REVERT", run, confirm)
    show, seq = _sequence(run)
    here = _here()
    rp = os.path.join(here, RECORD)
    rec = _load_json(rp)
    if not rec or not rec.get("applied"):
        _stop(run, "NOTHING_TO_REVERT")
    fixrec = _load_json(os.path.join(here, FIX_RECORD))
    if fixrec and fixrec.get("applied"):
        _stop(run, "FIX_APPLIED|run FIX_REVERT first")
    plan = rec["plan"]
    live = _snapshot(seq)
    problems = untouched_diff(rec["snapshot_after"], live, set()) + _cmp_specs(_owned_specs_live(seq, plan, run), rec["owned_after"])
    if problems:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%s|restore from %s" % (json.dumps(problems[:12]), rec["backup"]))
    backup, copied = _backup(run, "I2Order-Revert")
    txn = os.path.join(here, "i2_order_revert_%s.json" % run)
    _write_json(txn, {"run": run, "backup": backup, "backup_files": [copied], "source_record": rp,
                      "snapshot_before_revert": live}, exclusive=True)
    _apply_writes(seq, plan, run, originals=rec["originals"])
    after = _snapshot(seq)
    problems = untouched_diff(rec["snapshot_before"], after, set())
    problems += _cmp_specs(_owned_specs_live(seq, plan, run), rec["originals"])
    if guard_hashes(after) != rec["guards_before"]:
        problems.append("GUARD_CHANGED")
    if problems:
        _stop(run, "REVERT_PRESAVE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(problems[:12]))
    _save_ls(run)
    seq = _ue().load_asset(SEQ_PATH)
    after2 = _snapshot(seq)
    problems = untouched_diff(rec["snapshot_before"], after2, set()) + _cmp_specs(_owned_specs_live(seq, plan, run), rec["originals"])
    if problems:
        _stop(run, "REVERT_READBACK|%s|restore from %s" % (json.dumps(problems[:12]), backup))
    archived = rp + ".reverted-" + run
    os.rename(rp, archived)
    _write_json(txn, dict(_load_json(txn), completed=True, archived_record=archived))
    _log("%s_REVERT_OK|run=%s|saved=%s|backup=%s|record=%s" % (MARK, run, SEQ_PATH, backup, archived))


# ------------------------------------------------------------------------------------------------ FIX (optional)

def _fix_target(seq, step, run):
    ue = _ue()
    actors = [a for a in _actors() if str(a.get_actor_label()) == step["actor_label"]]
    if len(actors) != 1:
        _stop(run, "FIX_ACTOR_COUNT|%s|%d" % (step["actor_label"], len(actors)))
    a = actors[0]
    if step["kind"] == "PPV_WEIGHT" and not isinstance(a, ue.PostProcessVolume):
        _stop(run, "FIX_NOT_A_PPV|%s" % step["actor_label"])
    if step["kind"] in ("LIGHT_HIDE", "LIGHT_DIM") and not isinstance(a, ue.Light):
        _stop(run, "FIX_NOT_A_LIGHT|%s" % step["actor_label"])
    created = []
    rows = _bindings_named(seq, step["actor_label"])
    if len(rows) > 1:
        _stop(run, "FIX_BINDING_COUNT|%s|%d" % (step["actor_label"], len(rows)))
    if rows:
        b = rows[0]
    else:
        b = seq.add_possessable(a)
        if b is None or not b.is_valid():
            _stop(run, "FIX_BIND|%s|NOTHING SAVED; Don't-Save restart" % step["actor_label"])
        b.set_display_name(step["actor_label"])
        created.append(_guid(b.get_id()))
    if step["kind"] != "LIGHT_DIM":
        return b, created
    kids = _bindings_named(seq, step["actor_label"] + "/LightComponent")
    if kids:
        return kids[0], created
    kb = seq.add_possessable(a.get_component_by_class(ue.LightComponent))
    if kb is None or not kb.is_valid():
        _stop(run, "FIX_BIND_COMPONENT|%s|NOTHING SAVED; Don't-Save restart" % step["actor_label"])
    kb.set_parent(b)
    kb.set_display_name(step["actor_label"] + "/LightComponent")
    created.append(_guid(kb.get_id()))
    return kb, created


def _fix_write(binding, spec, run):
    ue = _ue()
    for t in binding.get_tracks():
        cls = t.get_class().get_name()
        try:
            prop = str(t.get_property_name())
        except Exception:  # noqa: BLE001
            prop = ""
        if cls == spec["class"] and (prop == spec["prop"] or (cls == "MovieSceneVisibilityTrack")):
            _stop(run, "FIX_TRACK_OWNED_ELSEWHERE|%s|%s|%s|NOTHING SAVED; Don't-Save restart" % (binding.get_display_name(), cls, prop))
    t = binding.add_track(getattr(ue, spec["class"]))
    if t is None:
        _stop(run, "FIX_ADD_TRACK|NOTHING SAVED; Don't-Save restart")
    t.set_property_name_and_path(spec["prop"], spec["path"])   # visibility: bHidden/bHidden, true = VISIBLE
    t.set_display_name(spec["name"])
    s = t.add_section()
    s.set_range(*spec["range"])
    c = s.get_all_channels()[0]
    if spec["default"] is not None:
        c.set_default(spec["default"])
    for f, v in spec["keys"]:
        if isinstance(v, bool):
            c.add_key(ue.FrameNumber(int(f)), bool(v), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        else:
            c.add_key(ue.FrameNumber(int(f)), float(v), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE,
                      interpolation=ue.MovieSceneKeyInterpolation.LINEAR)
    return _guid(binding.get_id()), t


def run_fix(run, p, confirm):
    _preflight("FIX", run, confirm)
    if not p["fix_steps"]:
        _stop(run, "NO_FIX_STEPS|params.fix_steps is empty (fixes never run by default)")
    show, seq = _sequence(run)
    here = _here()
    fp = os.path.join(here, FIX_RECORD)
    if os.path.exists(fp):
        _stop(run, "FIX_RECORD_EXISTS|FIX_REVERT first")
    before = _snapshot(seq)
    end = before["playback"][1]
    backup, copied = _backup(run, "I2OrderFix")
    record = {"run": run, "applied": False, "backup": backup, "backup_files": [copied], "steps": p["fix_steps"],
              "snapshot_before": before, "guards_before": guard_hashes(before)}
    _write_json(fp, record, exclusive=True)
    seq.modify()
    created, owned, specs = [], set(), {}
    for step in p["fix_steps"]:
        spec = fix_track_spec(step, end)
        b, made = _fix_target(seq, step, run)
        created += made
        g, _ = _fix_write(b, spec, run)
        owned.add(track_key(g, spec["class"], spec["name"], "*"))
        specs[step["id"]] = {"guid": g, "spec": spec}
    after = _snapshot(seq)
    problems = untouched_diff(before, after, owned, created)
    for sid, row in specs.items():
        # found by binding + class + our display name, whatever property the setter really wrote (read back)
        hits = [t for b in after["bindings"] if b["guid"] == row["guid"] for t in b["tracks"]
                if t["class"] == row["spec"]["class"] and t["name"] == FIX_TRACK]
        problems += ["%s|%s" % (sid, x) for x in check_fix_readback(row["spec"], hits[0] if len(hits) == 1 else None)]
    if guard_hashes(after) != record["guards_before"]:
        problems.append("GUARD_CHANGED")
    if problems:
        _stop(run, "FIX_PRESAVE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(problems[:12]))
    _save_ls(run)
    seq = _ue().load_asset(SEQ_PATH)
    after2 = _snapshot(seq)
    if json.dumps(after2, sort_keys=True, default=str) != json.dumps(after, sort_keys=True, default=str):
        _stop(run, "FIX_POSTSAVE_SNAPSHOT_DIFFERS|restore from %s" % backup)
    record.update({"applied": True, "created_bindings": created, "owned": sorted(owned), "specs": specs, "snapshot_after": after2})
    _write_json(fp, record)
    _log("%s_FIX_OK|run=%s|steps=%s|created_bindings=%d|guards=unchanged|saved=%s|backup=%s"
         % (MARK, run, ",".join(s["id"] for s in p["fix_steps"]), len(created), SEQ_PATH, backup))


def run_fix_revert(run, p, confirm):
    ue = _ue()
    _preflight("FIX_REVERT", run, confirm)
    show, seq = _sequence(run)
    fp = os.path.join(_here(), FIX_RECORD)
    rec = _load_json(fp)
    if not rec or not rec.get("applied"):
        _stop(run, "NOTHING_TO_FIX_REVERT")
    live = _snapshot(seq)
    if json.dumps(live, sort_keys=True, default=str) != json.dumps(rec["snapshot_after"], sort_keys=True, default=str):
        _stop(run, "FIX_STATE_DRIFTED|restore from %s" % rec["backup"])
    backup, _ = _backup(run, "I2OrderFix-Revert")
    seq.modify()
    for sid, row in rec["specs"].items():
        spec = row["spec"]
        bs = [b for b in seq.get_bindings() if _guid(b.get_id()) == row["guid"]]
        if len(bs) != 1:
            _stop(run, "FIX_REVERT_BINDING|%s|NOTHING SAVED; Don't-Save restart" % sid)
        ts = [t for t in bs[0].get_tracks() if t.get_class().get_name() == spec["class"] and str(t.get_display_name()) == FIX_TRACK]
        if len(ts) != 1:
            _stop(run, "FIX_REVERT_TRACK|%s|NOTHING SAVED; Don't-Save restart" % sid)
        bs[0].remove_track(ts[0])
    for g in reversed(rec["created_bindings"]):
        bs = [b for b in seq.get_bindings() if _guid(b.get_id()) == g]
        if len(bs) == 1:
            bs[0].remove()
    after = _snapshot(seq)
    if json.dumps(after, sort_keys=True, default=str) != json.dumps(rec["snapshot_before"], sort_keys=True, default=str):
        _stop(run, "FIX_REVERT_PRESAVE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(untouched_diff(rec["snapshot_before"], after, set())[:8]))
    _save_ls(run)
    os.rename(fp, fp + ".reverted-" + run)
    _log("%s_FIX_REVERT_OK|run=%s|saved=%s|backup=%s" % (MARK, run, SEQ_PATH, backup))


def main(args):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("I2ORDER-%Y%m%d-%H%M%S"))
    confirm = args.get("confirm")
    try:
        p = merged_params(args.get("params") or {})
        fn = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert, "VERIFY": run_verify,
              "FIX": run_fix, "FIX_REVERT": run_fix_revert}.get(mode)
        if fn is None:
            _stop(run, "MODE|%r" % mode)
        return fn(run, p, confirm)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|%s" % exc)
