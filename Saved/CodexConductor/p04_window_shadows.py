"""P04 window shadows: PLAN (offline) / DRY / APPLY / REVERT (editor). N cold spot lights BEHIND the LEFT wings of
Passage 4, each aimed through one large window of its wing so the window lands as a shaft / floor patch on the
corridor floor in front of that wing, struck on approach so they come and go after the right strobe has had its say.

Gary 7 Oct (P04): "the dramatic lighting (distant moonlight cast, earlier strobe) are very good. But the left side still
needs some lighting ... make good use of the large 'windows' in many of its wings to cast dramatic shadows that come and
go, especially on the left side as the right strobes". He is repointing the strobe by hand: this tool NEVER touches the
strobe, the moonlight or any existing light. It only APPENDS new rows labelled "P04 WINDOW SHADOW W0NN" (NN = wing).

MODES
  PLAN   offline only (python p04_window_shadows.py, or p04_window_shadows_run.py outside Unreal). Reads the wing
         records + cut masks, finds windows (Tools/WindowShadows/find_windows.py), places lights, projects patches,
         computes camera visibility vs the strobe, writes p04_window_shadows_plan.json + p04_window_shadows_preview.png.
  DRY    editor, read-only: resolves cues / station frames / the cloned source row against the plan; prints the plan
         sha256 that APPLY must quote; no write (census + rows compared before/after).
  APPLY  editor: backup, record (exclusive), mint GUIDs by the scratch-pair pattern (one cycle per target cue),
         author, scope check, materialize, narrow save, read-back. confirm "APPLY P04WINSHADOW" + plan_sha256.
  REVERT editor: removes exactly the recorded GUIDs, result must equal the recorded before rows; confirm
         "REVERT P04WINSHADOW".
Markers: P04WINSHADOW_<MODE>_OK|run=<id>|... ; any stop P04WINSHADOW_STOPPED|run=<id>|...

Proof tiers (AGENTS.md), per claim:
* declaration-proven
  - light fields: Type/IntensityUnits/Intensity/Color/bUseTemperature/AttenuationRadiusCm/VolumetricScatteringIntensity/
    bCastShadows/bCastVolumetricShadow/SourceRadiusCm/SoftSourceRadiusCm/Inner+OuterConeAngleDegrees/
    LightFunctionMaterial/Drama (Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:196-364);
  - strike: bStrikeOnApproach, StrikeDistanceCm, StrikeRampCm, IgnitionStutter, UnstruckIntensityScale, AfterPass
    {Hold,Decay,Extinguish}, AfterPassDistanceCm, DecayDistanceCm (InfinityStageLightDrama.h:10-76); unstruck lamps
    are switched OFF, no shadow cost (InfinityStageLightDrama.h:30-31); strike level vs AheadCm
    (InfinityStageLightDrama.cpp:24-59);
  - the lamp's route distance = its cue's wing DistanceCm + RelativeTransform.X (InfinityStagePassageActor.cpp:1651-1665);
  - spot axis = local +X, rotator->quat (roll 0) X=sp*sy, Y=-sp*cy, Z=cp*sy, W=cp*cy -- cross-checked against the
    live-proven B09 TOP_L row (quat (.380,.380,-.596,.596) = yaw -90 pitch -65, lighting_scores_record_P04.json);
  - flash fields (variant B only) exist only once Scripts/patches/2026-10-04_LD_flash_events.draft.patch is BUILT
    (patch lines 79-102: bFlash, FlashCameraOffsetsCm = camera-past-lamp at each peak, FlashAttackCm, FlashDecayCm,
    FlashRestScale); APPLY refuses variant B when unreal has no flash property;
  - strobe timing = master frame / tick resolution, LevelAt(ShowSeconds/Period + PhaseCycles)
    (InfinityStageStrobeLight.cpp:97-121, :12-18);
  - wing openings are GEOMETRY from the cut mask (Docs/FlatV3Spec_2026-09-30.md:103; build_v3_flat.py:185-196,322-376);
    image handedness L = exterior left (Docs/WingGenerationConventions.md:50-53).
* measured (records written by editor runs; offline read here)
  - P04 passage-local == world (x, y-240000, z) (gloss4_glint_pie_spawn.py:4 via p04_glint_practical.py:5-6);
  - Wing N station x = 250 + 500(N-1) cm (p04_glint_practical.py:21-23; checked live per light by FRAME_DISAGREES);
  - inner/outer edges: coventry = Saved/CodexFlatV3/swapkit/shift_verify_FV3S4-20261002-01.json placed_panels (2 Oct);
    gallery = edge_probe_FV3CVFIXPROBE-20261006-01.json rows (6 Oct 01:56, the latest; the 5 Oct TK audit differs by
    up to 35 cm and is superseded); panel x span -16..+4 cm about the station (S4 bounds_pair_cm);
  - designs per cue: Saved/CodexFlatV3/p04rough/p04rough_inventory.json:13-17 (the plan cross-checks the record mesh);
  - deployed cut masks: the build json inputs.mask of each deployed mesh (Review_2026-10-05 holes/hf + gallery_curved);
  - camera x = 215.94 t, y 0, z 180, HFOV 37.497 deg, 1600x900 (gloss4_glint.py:7-8, PSTILLS-P04-20261006-063907);
    the retime gives 2.3387 s per 500 cm wing pitch = 213.8 cm/s (passage_retime_to_music_record_P03-P04.json
    planned_timing "4": 56128 ticks @24000); P04 length 50.40 s (new_len_ticks 1209600);
  - strobe: label "P04 Strobe (default, Gary to place)", placed local (2000, 650, 60), period 1 s, flash .04, decay .33
    (place_default_strobe_p04_record.json:6-14), halo 3500 cd / 450 cm (p04_strobe_halo_applied_HALO-...022349.json)
    -- Gary is MOVING it now: args strobe_local_cm must be re-read (the DRY prints the live strobe, read-only);
  - moon colour: P04_MOODY_WINGS TOP_L/TOP_R "cold moon" [0.55, 0.68, 1.0], 7600 K (lighting_scores.json:2461-2497).
* inferred (each listed again in the plan json "inferred")
  - the camera pitch is 0 (frustum maths); darkness/fog limits floor-patch legibility beyond vis_max_cm (2500);
  - route distance == passage-local x (camera x = route distance) -- the wing pins say so, not a probe;
  - the strike timings assume the 215.94 cm/s still-measured speed;
  - variant B's antiphase needs the P04 master start 30403585 ticks (retime record after.keys, 6 Oct) to still hold and
    the strobe PhaseCycles 0 -- a later retime or Gary's hand edits move it;
  - the cloned source row ("P04 SCORE B09 MOODY TOP_L" by default) exists live with the 5 Oct shape (DRY checks);
  - panel z scale 1 (bounds 0..1000 cm in S4 say so for coventry; gallery inferred).
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import math
import os
import re
import sys
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline PLAN / harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCORES_TOOL_PATH = os.path.join(HERE, "lighting_scores_apply.py")
RECORD_PATH = os.path.join(HERE, "p04_window_shadows_record.json")
PLAN_PATH = os.path.join(HERE, "p04_window_shadows_plan.json")
PREVIEW_PATH = os.path.join(HERE, "p04_window_shadows_preview.png")
VALID_MODES = ("PLAN", "DRY", "APPLY", "REVERT")
CONFIRM_TOKEN = "P04WINSHADOW"
MARK = "P04WINSHADOW"
PASSAGE_KEY = "P04"
PASSAGE_LABEL = "Passage 4"
PASSAGE_ACTOR_PREFIX = "Passage 04"
STRUCTURE_LABEL = "Infinity Stage - Structure 04"
LABEL_FMT = "P04 WINDOW SHADOW W%03d"
LABEL_RE = re.compile(r"^P04 WINDOW SHADOW W\d{3}$")
ZERO_GUID = "0" * 32
CLONE_FIELDS = ("label", "kind", "enabled", "actor_class", "mesh", "anchor", "relative_transform",
                "lighting", "effect", "trigger_distance_cm", "body", "mover")   # InfinityStageTypes.h:429-492
EFFECT_GUID_FIELDS = ("linked_light_attachment_guid", "replicated_from_attachment_guid")
LOC_TOL_CM = 1.0e-3
ROT_TOL = 1.0e-5
REL_TOL = 1.0e-5
FLASH_FIELDS = ("flash", "flash_camera_offsets_cm", "flash_attack_cm", "flash_decay_cm", "flash_rest_scale")

SAVED = os.path.join(PROJECT, "Saved")
REVIEW = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Review_2026-10-05")
SOURCES = {
    "s4_panels": os.path.join(SAVED, "CodexFlatV3", "swapkit", "shift_verify_FV3S4-20261002-01.json"),
    "cvfix_probe": os.path.join(SAVED, "CodexFlatV3", "swapkit", "edge_probe_FV3CVFIXPROBE-20261006-01.json"),
    "inventory": os.path.join(SAVED, "CodexFlatV3", "p04rough", "p04rough_inventory.json"),
}
# design -> (deployed cut mask, deployed build json); build json inputs.mask names the mask (measured: read in PLAN).
DESIGNS = {
    "coventry_ruin_L_v1": ("holes/hf/builds/P04/P04_coventry_ruin_L_v1_t5p/P04_coventry_ruin_L_v1_t5p_L_build.json", "L"),
    "coventry_ruin_L_v2": ("holes/hf/builds/P04/P04_coventry_ruin_L_v2_t5p/P04_coventry_ruin_L_v2_t5p_L_build.json", "L"),
    "coventry_interior_L_v1": ("holes/hf/builds/P04/P04_coventry_interior_L_v1_t5p/"
                               "P04_coventry_interior_L_v1_t5p_L_build.json", "L"),
    "ruined_gallery_L_v1": ("gallery_curved/builds_cv12b/P04_ruined_gallery_L_v1_cv12b_t5j/"
                            "P04_ruined_gallery_L_v1_cv12b_t5j_L_build.json", "L"),
    "coventry_ruin_R_v1": ("holes/hf/builds/P04/P04_coventry_ruin_R_v1_t5p/P04_coventry_ruin_R_v1_t5p_R_build.json", "R"),
    "ruined_gallery_R_v1": ("gallery_curved/builds_cv12b/P04_ruined_gallery_R_v1_cv12b_t5j/"
                            "P04_ruined_gallery_R_v1_cv12b_t5j_R_build.json", "R"),
    "ruined_gallery_R_v2": ("gallery_curved/builds_cv12b/P04_ruined_gallery_R_v2_cv12b_t5j/"
                            "P04_ruined_gallery_R_v2_cv12b_t5j_R_build.json", "R"),
    "ruined_gallery_R_v3": ("gallery_curved/builds_cv12b/P04_ruined_gallery_R_v3_cv12b_t5j/"
                            "P04_ruined_gallery_R_v3_cv12b_t5j_R_build.json", "R"),
}
# p04rough_inventory.json:13-17 (+ the R rows): wing number -> design, per side.
DESIGN_BY_WING = {
    "L": {**{n: "coventry_ruin_L_v1" for n in (1, 5, 9, 13, 17, 21)},
          **{n: "coventry_ruin_L_v2" for n in (2, 6, 10, 14, 18)},
          **{n: "coventry_interior_L_v1" for n in (3, 7, 11, 15, 19)},
          **{n: "ruined_gallery_L_v1" for n in (4, 8, 12, 16, 20)}},
    "R": {**{n: "coventry_ruin_R_v1" for n in (1, 5, 9, 13, 17, 21)},
          **{n: "ruined_gallery_R_v1" for n in (2, 6, 10, 14, 18)},
          **{n: "ruined_gallery_R_v2" for n in (3, 7, 11, 15, 19)},
          **{n: "ruined_gallery_R_v3" for n in (4, 8, 12, 16, 20)}},
}
MOON_RGB = [0.55, 0.68, 1.0]          # lighting_scores.json:2461-2497 P04_MOODY_WINGS TOP_L/TOP_R "cold moon"
LF_ASSETS = ["/Game/InfinityStage/Lighting/MI_LF_Flicker_%s" % n
             for n in ("Breath", "Buzz", "Fault", "Hum", "Slow", "Steady")]   # Content/InfinityStage/Lighting *.uasset

DEFAULTS = {
    "wings": None,                      # None = every LEFT wing with a window; else a list of wing numbers
    "min_window_m2": 0.5,
    "max_lights_per_wing": 1,
    "station_x0_cm": 250.0,
    "station_pitch_cm": 500.0,
    "wing_count": 21,
    "wing_plane_dx_cm": -7.5,            # board mid-plane: S4 bounds_pair_cm x -16..+4 (front face -15)
    "panel_height_cm": 1000.0,
    "passage_world_offset_cm": [0.0, 240000.0, 0.0],
    "floor_setback_cm": 320.0,           # aim point on the floor this far in FRONT of the wing (camera side)
    "floor_target_y_cm": -120.0,         # ... and this far across (+y = right wall): left half of the corridor
    "light_setback_cm": 400.0,           # light this far BEHIND the wing plane (camera-far side)
    "light_above_window_cm": 150.0,      # light z >= window top + this (no near-horizontal smear)
    "max_cone_leak": 0.05,               # max fraction of cone rays passing OUTSIDE the wing silhouette
    "max_patch_length_cm": 700.0,        # floor patch extent along x (longer = a smear, rejected)
    "max_light_setback_cm": 440.0,       # next station is 500 cm on; keep 60 cm off it
    "max_light_z_cm": 1150.0,
    "min_light_y_cm": -1350.0,           # the left fence bays sit at y ~ -1418 (run_fence_p04_plan.json)
    "cone_margin_deg": 1.0,
    "intensity_cd": 220.0,               # "dimmed for now": ~1.5x the 150 cd moon tops (lighting_scores.json:2461+)
    "attenuation_pad": 1.35,
    "source_radius_cm": 2.0,
    "soft_source_radius_cm": 0.0,        # crisp window edges
    "volumetric_scattering": 0.6,
    "color_rgb": list(MOON_RGB),
    "light_function": None,              # e.g. "/Game/InfinityStage/Lighting/MI_LF_Flicker_Breath" (variant C)
    "camera_speed_cm_s": 215.94,
    "camera_z_cm": 180.0,
    "camera_hfov_deg": 37.497,
    "camera_aspect": 16.0 / 9.0,
    "passage_seconds": 50.4,
    "vis_max_cm": 2500.0,
    "vis_min_fraction": 0.3,
    "strike_ramp_cm": 260.0,
    "strike_lead_cm": 150.0,             # strike this much camera travel BEFORE the patch first reads ...
    "strike_patch_ahead_cm": 1500.0,     # ... but no earlier than the camera being this far short of the patch
                                         # (the patch fades up mid-frame = "come"; the camera passing it = "go")
    "strike_stutter": 0.0,
    "after_pass": "EXTINGUISH",
    "after_pass_distance_cm": 0.0,
    "max_lit_together": 3,
    "variant": "A",                      # A = strike/extinguish (works today); B = A + antiphase flashes (patch)
    "strobe_local_cm": [2000.0, 650.0, 60.0],
    "strobe_radius_cm": 450.0,
    "strobe_period_s": 1.0,
    "strobe_flash_s": 0.04,
    "strobe_decay_s": 0.33,
    "strobe_phase_cycles": 0.0,
    "passage_start_ticks": 30403585,
    "tick_rate": 24000.0,
    "flash_attack_cm": 15.0,
    "flash_decay_cm": 70.0,
    "flash_rest_scale": 0.0,
    "flash_every_n_strobes": 2,
    "source_light_label": "P04 SCORE B09 MOODY TOP_L",
    "max_frame_disagreement_cm": 5.0,
    "plan_path": None,
    "plan_sha256": None,
    "avoid_scratch_cues": [],
    "ack_records": [],
    "allow_dirty": [],
}


class P04WindowShadowError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise P04WindowShadowError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


def report_path(mode, run, folder=None):
    return os.path.join(folder or HERE, "p04_window_shadows_report_%s_%s.json" % (mode, run))


# --------------------------------------------------------------------------
# Vector / transform maths (copied from p04_glint_practical.py:136-221, FTransform semantics).
# --------------------------------------------------------------------------
def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _scale(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _dist(a, b):
    return _norm(_sub(a, b))


def quat_rotate(q, v):
    x, y, z, w = (float(c) for c in q)
    tx = 2.0 * (y * v[2] - z * v[1])
    ty = 2.0 * (z * v[0] - x * v[2])
    tz = 2.0 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx)]


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def compose(child, parent):
    scaled = [child["location"][i] * parent["scale"][i] for i in range(3)]
    return {"location": _add(quat_rotate(parent["rotation_xyzw"], scaled), parent["location"]),
            "rotation_xyzw": quat_mul(parent["rotation_xyzw"], child["rotation_xyzw"]),
            "scale": [child["scale"][i] * parent["scale"][i] for i in range(3)]}


def inverse_point(frame, world_point):
    q = [float(c) for c in frame["rotation_xyzw"]]
    norm = math.sqrt(sum(c * c for c in q))
    require(norm > 1.0e-9, "FRAME_QUAT_ZERO")
    conj = [-q[0] / norm, -q[1] / norm, -q[2] / norm, q[3] / norm]
    local = quat_rotate(conj, _sub(world_point, frame["location"]))
    require(all(abs(float(s)) > 1.0e-9 for s in frame["scale"]), "FRAME_SCALE_ZERO")
    return [local[i] / float(frame["scale"][i]) for i in range(3)]


def canonical_quat(q):
    out = [float(c) for c in q]
    for c in out:
        if c == 0.0:
            continue
        if c < 0.0:
            out = [-v for v in out]
        break
    return out


def quat_close(a, b, tol=ROT_TOL):
    d1 = max(abs(float(x) - float(y)) for x, y in zip(a, b))
    d2 = max(abs(float(x) + float(y)) for x, y in zip(a, b))
    return min(d1, d2) <= tol


def aim_quat(direction):
    """UE FRotator(pitch, yaw, roll 0) -> FQuat, so the spot's local +X points along `direction`."""
    d = _scale(direction, 1.0 / _norm(direction))
    yaw = math.atan2(d[1], d[0])
    pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    sp, cp = math.sin(pitch / 2.0), math.cos(pitch / 2.0)
    sy, cy = math.sin(yaw / 2.0), math.cos(yaw / 2.0)
    return canonical_quat([sp * sy, -sp * cy, cp * sy, cp * cy]), math.degrees(pitch), math.degrees(yaw)


def quat_forward(q):
    return quat_rotate(q, [1.0, 0.0, 0.0])


# --------------------------------------------------------------------------
# Args.
# --------------------------------------------------------------------------
def _finite(value, label):
    require(not isinstance(value, bool), "%s_NOT_NUMBER|%r" % (label, value))
    number = float(value)
    require(math.isfinite(number), "%s_NOT_FINITE|%r" % (label, value))
    return number


def _vector(value, n, label):
    require(isinstance(value, (list, tuple)) and len(value) == n, "%s_SHAPE|%r" % (label, value))
    return [_finite(v, label) for v in value]


NUMERIC_RANGES = {
    "min_window_m2": (0.01, 50.0), "station_x0_cm": (-1e6, 1e6), "station_pitch_cm": (1.0, 1e5),
    "wing_plane_dx_cm": (-50.0, 50.0), "panel_height_cm": (100.0, 3000.0), "floor_setback_cm": (50.0, 480.0),
    "floor_target_y_cm": (-600.0, 600.0), "light_setback_cm": (40.0, 480.0), "max_light_setback_cm": (40.0, 480.0),
    "max_light_z_cm": (100.0, 2500.0), "light_above_window_cm": (0.0, 1000.0), "max_cone_leak": (0.0, 1.0),
    "max_patch_length_cm": (50.0, 5000.0), "min_light_y_cm": (-3000.0, 0.0), "cone_margin_deg": (0.0, 20.0),
    "intensity_cd": (0.0, 5000.0), "attenuation_pad": (1.0, 3.0), "source_radius_cm": (0.0, 100.0),
    "soft_source_radius_cm": (0.0, 100.0), "volumetric_scattering": (0.0, 10.0), "camera_speed_cm_s": (10.0, 2000.0),
    "camera_z_cm": (0.0, 1000.0), "camera_hfov_deg": (5.0, 170.0), "camera_aspect": (0.2, 5.0),
    "passage_seconds": (1.0, 600.0), "vis_max_cm": (500.0, 20000.0), "vis_min_fraction": (0.0, 1.0),
    "strike_ramp_cm": (1.0, 5000.0), "strike_lead_cm": (0.0, 5000.0), "strike_patch_ahead_cm": (0.0, 5000.0), "strike_stutter": (0.0, 1.0),
    "after_pass_distance_cm": (0.0, 5000.0), "strobe_radius_cm": (1.0, 5000.0), "strobe_period_s": (0.05, 60.0),
    "strobe_flash_s": (0.0, 10.0), "strobe_decay_s": (0.0, 10.0), "strobe_phase_cycles": (0.0, 1.0),
    "tick_rate": (1.0, 1e6), "flash_attack_cm": (0.1, 1000.0), "flash_decay_cm": (0.1, 2000.0),
    "flash_rest_scale": (0.0, 1.0), "max_frame_disagreement_cm": (0.0, 50.0),
}


def check_args(args):
    raw = dict(args or {})
    unknown = sorted(set(raw) - set(DEFAULTS) - {"mode", "confirm"})
    require(not unknown, "ARGS_UNKNOWN|%s" % unknown)
    mode = str(raw.get("mode", "PLAN")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode in ("APPLY", "REVERT"):
        require(raw.get("confirm") == "%s %s" % (mode, CONFIRM_TOKEN),
                "CONFIRM_MISSING|mode=%s|need='%s %s'" % (mode, mode, CONFIRM_TOKEN))
    out = copy.deepcopy(DEFAULTS)
    out.update({k: copy.deepcopy(v) for k, v in raw.items() if k in DEFAULTS})
    out["mode"], out["confirm"] = mode, raw.get("confirm")
    for key, (low, high) in NUMERIC_RANGES.items():
        out[key] = _finite(out[key], key.upper())
        require(low <= out[key] <= high, "%s_RANGE|%r" % (key.upper(), out[key]))
    require(out["light_setback_cm"] <= out["max_light_setback_cm"] < out["station_pitch_cm"],
            "LIGHT_SETBACK_ORDER")
    out["passage_world_offset_cm"] = _vector(out["passage_world_offset_cm"], 3, "PASSAGE_OFFSET")
    out["strobe_local_cm"] = _vector(out["strobe_local_cm"], 3, "STROBE_LOCAL")
    out["color_rgb"] = _vector(out["color_rgb"], 3, "COLOR")
    require(all(0.0 <= c <= 1.0 for c in out["color_rgb"]), "COLOR_RANGE")
    for key in ("max_lights_per_wing", "wing_count", "max_lit_together", "flash_every_n_strobes", "passage_start_ticks"):
        require(isinstance(out[key], int) and not isinstance(out[key], bool) and out[key] >= 1, key.upper() + "_INVALID")
    if out["wings"] is not None:
        require(isinstance(out["wings"], list) and out["wings"]
                and all(isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= out["wing_count"]
                        for n in out["wings"]) and len(set(out["wings"])) == len(out["wings"]), "WINGS_INVALID")
    require(out["after_pass"] in ("HOLD", "DECAY", "EXTINGUISH"), "AFTER_PASS_INVALID")
    require(out["variant"] in ("A", "B"), "VARIANT_INVALID")
    require(out["light_function"] is None or out["light_function"] in LF_ASSETS, "LIGHT_FUNCTION_NOT_LISTED")
    require(isinstance(out["source_light_label"], str) and out["source_light_label"], "SOURCE_LABEL_INVALID")
    require(out["plan_sha256"] is None or (isinstance(out["plan_sha256"], str) and len(out["plan_sha256"]) == 64),
            "PLAN_SHA_INVALID")
    if mode == "APPLY":
        require(out["plan_sha256"], "APPLY_NEEDS_PLAN_SHA256 (copy it from the DRY report)")
    for key in ("avoid_scratch_cues", "ack_records", "allow_dirty"):
        require(isinstance(out[key], list) and all(isinstance(v, str) for v in out[key]), key.upper() + "_INVALID")
    return out


# --------------------------------------------------------------------------
# Wing table (PLAN, offline).
# --------------------------------------------------------------------------
def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _design_of(mesh):
    match = re.search(r"P04_((?:coventry_ruin|coventry_interior|ruined_gallery)_[LR]_v\d)", str(mesh or ""))
    return match.group(1) if match else None


def wing_table(opts, sources=None):
    """{(side, wing): {inner, outer, design, source, tier}}; gallery rows from the 6 Oct CVFIX probe override S4."""
    src = dict(SOURCES)
    src.update(sources or {})
    s4 = _read_json(src["s4_panels"])
    require(s4.get("status") == "PASS" and s4.get("passage") == "P04", "S4_RECORD_NOT_PASS")
    table = {}
    for row in s4["placed_panels"]:
        match = re.match(r"^P04 Wing (\d{3})$", row["cue_label"])
        require(match, "S4_LABEL|" + row["cue_label"])
        side = "L" if row["side"] == "left" else "R"
        wing = int(match.group(1))
        table[(side, wing)] = {"inner_cm": float(row["inner_edge_cm"]), "outer_cm": float(row["outer_edge_cm"]),
                               "design_record": _design_of(row["mesh"]), "cue_guid": row["cue_guid"],
                               "source": "shift_verify_FV3S4-20261002-01 placed_panels", "tier": "measured 2 Oct"}
    probe = _read_json(src["cvfix_probe"])
    require(probe.get("status") == "PASS", "CVFIX_PROBE_NOT_PASS")
    for row in probe["rows"]:
        wing = int(re.match(r"^P04 Wing (\d{3})$", row["cue"]).group(1))
        side = "L" if row["side"] == "left" else "R"
        table[(side, wing)] = {"inner_cm": float(row["inner_cm"]), "outer_cm": float(row["outer_cm"]),
                               "design_record": _design_of(row["mesh"]), "cue_guid": row["cue_guid"],
                               "source": "edge_probe_FV3CVFIXPROBE-20261006-01", "tier": "measured 6 Oct"}
    for (side, wing), row in table.items():
        want = DESIGN_BY_WING[side].get(wing)
        row["design"] = want
        row["design_agrees"] = row["design_record"] == want
    return table


def load_design(design, review_root=REVIEW, height_cm=1000.0, min_area_m2=0.5):
    """find_windows on the deployed cut mask of a design (mask path from its build json)."""
    sys.path.insert(0, os.path.join(PROJECT, "Tools", "WindowShadows"))
    import find_windows as fw  # noqa: E402
    build_rel, side = DESIGNS[design]
    build = _read_json(os.path.join(review_root, build_rel))
    mask = build["inputs"]["mask"]
    width_cm = float(build["dimensions_m"]["width"]) * 100.0
    require(abs(float(build["dimensions_m"]["height"]) * 100.0 - height_cm) < 1.0, "BUILD_HEIGHT|" + design)
    opacity, channel = fw.load_opacity(mask)
    result = fw.find_windows(opacity, height_cm, width_cm, min_area_m2)
    result["mask"] = mask
    result["mask_sha256"] = _sha256_file(mask)
    result["build_json"] = os.path.join(review_root, build_rel)
    result["side"] = side
    result["channel"] = channel
    result["build_hole_count"] = build["mask"]["hole_count"]
    return result, opacity, fw


# --------------------------------------------------------------------------
# Geometry (pure).
# --------------------------------------------------------------------------
def station_x(opts, wing):
    return opts["station_x0_cm"] + opts["station_pitch_cm"] * (wing - 1)


def panel_point(u_cm, z_cm, width_cm, side, inner, outer, x_plane):
    f = float(u_cm) / float(width_cm)
    y = outer + f * (inner - outer) if side == "L" else inner + f * (outer - inner)
    return [x_plane, y, float(z_cm)]


def place_light(centroid, opts, wing, window_top_z=None):
    """Light on the line floor-target -> window centroid, extended BEHIND the wing; returns (P, F, notes).

    The light must clear the window's top by light_above_window_cm, else rays through the top of the window run
    near-horizontal and the 'patch' smears down the corridor: the floor target is pulled toward the wing until it
    does (fs <= setback * zc / (top + margin - zc))."""
    xw = centroid[0]
    notes = []
    setback_fs = opts["floor_setback_cm"]
    if window_top_z is not None:
        need = window_top_z + opts["light_above_window_cm"] - centroid[2]
        if need > 0:
            limit = opts["light_setback_cm"] * centroid[2] / need
            if limit < setback_fs:
                setback_fs = max(60.0, limit)
                notes.append("FLOOR_TARGET_PULLED_IN|%.0f" % setback_fs)
    floor = [xw - setback_fs, opts["floor_target_y_cm"], 0.0]
    d = _sub(centroid, floor)
    require(d[0] > 0.0 and d[2] > 0.0, "AIM_DEGENERATE|wing=%d" % wing)
    setback = opts["light_setback_cm"]
    k = setback / d[0]
    light = _add(centroid, _scale(d, k))
    if light[2] > opts["max_light_z_cm"]:
        k = (opts["max_light_z_cm"] - centroid[2]) / d[2]
        light = _add(centroid, _scale(d, k))
        notes.append("SETBACK_CUT_BY_MAX_Z")
    if light[1] < opts["min_light_y_cm"]:
        k2 = (opts["min_light_y_cm"] - centroid[1]) / d[1] if d[1] < 0 else k
        k = min(k, k2)
        light = _add(centroid, _scale(d, k))
        notes.append("SETBACK_CUT_BY_FENCE")
    require(light[0] - xw <= opts["max_light_setback_cm"] + 1e-6, "LIGHT_TOO_DEEP|wing=%d" % wing)
    require(light[0] - xw >= 20.0, "LIGHT_TOO_SHALLOW|wing=%d|dx=%.1f" % (wing, light[0] - xw))
    return light, floor, notes


def cone_for(light, axis, points, margin_deg):
    a = _scale(axis, 1.0 / _norm(axis))
    worst = 0.0
    for p in points:
        v = _sub(p, light)
        c = max(-1.0, min(1.0, _dot(v, a) / _norm(v)))
        worst = max(worst, math.degrees(math.acos(c)))
    outer = min(89.0, worst + margin_deg)
    return round(max(0.0, outer * 0.85), 3), round(outer, 3), round(worst, 3)


def project_to_floor(light, point):
    if point[2] >= light[2] - 1e-6:
        return None
    s = light[2] / (light[2] - point[2])
    return [light[0] + s * (point[0] - light[0]), light[1] + s * (point[1] - light[1]), 0.0]


def blocked_by_wing(start, end, plane_x, left_span, right_span, height_cm):
    """Segment start->end crosses plane x = plane_x inside a wing's y span (holes ignored -> conservative)."""
    if not (min(start[0], end[0]) < plane_x < max(start[0], end[0])):
        return False
    t = (plane_x - start[0]) / (end[0] - start[0])
    y = start[1] + t * (end[1] - start[1])
    z = start[2] + t * (end[2] - start[2])
    if not (0.0 <= z <= height_cm):
        return False
    return (left_span[0] <= y <= left_span[1]) or (right_span[0] <= y <= right_span[1])


def spans_at(table, wing):
    left = table.get(("L", wing))
    right = table.get(("R", wing))
    ls = (min(left["inner_cm"], left["outer_cm"]), max(left["inner_cm"], left["outer_cm"])) if left else (1, 0)
    rs = (min(right["inner_cm"], right["outer_cm"]), max(right["inner_cm"], right["outer_cm"])) if right else (1, 0)
    return ls, rs


def camera_at(opts, t):
    return [opts["camera_speed_cm_s"] * t, 0.0, opts["camera_z_cm"]]


def in_frustum(opts, cam, p):
    dx = p[0] - cam[0]
    if dx <= 1.0:
        return False
    th = math.tan(math.radians(opts["camera_hfov_deg"] / 2.0))
    tv = th / opts["camera_aspect"]
    return abs(p[1] - cam[1]) / dx <= th and abs(p[2] - cam[2]) / dx <= tv and dx <= opts["vis_max_cm"]


def visible_fraction(opts, table, cam, points, ignore_wings=()):
    if not points:
        return 0.0
    seen = 0
    for p in points:
        if not in_frustum(opts, cam, p):
            continue
        ok = True
        for wing in range(1, opts["wing_count"] + 1):
            if wing in ignore_wings:
                continue
            x = station_x(opts, wing) + opts["wing_plane_dx_cm"]
            if not (cam[0] < x < p[0]):
                continue
            ls, rs = spans_at(table, wing)
            if blocked_by_wing(cam, p, x, ls, rs, opts["panel_height_cm"]):
                ok = False
                break
        seen += ok
    return seen / float(len(points))


def intervals(times, flags):
    out, start = [], None
    for t, f in zip(times, flags):
        if f and start is None:
            start = t
        if not f and start is not None:
            out.append([round(start, 2), round(prev, 2)])
            start = None
        prev = t
    if start is not None:
        out.append([round(start, 2), round(times[-1], 2)])
    return out


def time_grid(opts, step=0.1):
    n = int(opts["passage_seconds"] / step) + 1
    return [round(i * step, 4) for i in range(n)]


def strobe_flash_times(opts):
    """Passage-local seconds of each strobe peak: Cycle = frac(ShowSeconds/Period + Phase) == 0."""
    start_s = opts["passage_start_ticks"] / opts["tick_rate"]
    period = opts["strobe_period_s"]
    first = math.ceil((start_s / period + opts["strobe_phase_cycles"]) - 1e-9)
    out, k = [], first
    while True:
        t = (k - opts["strobe_phase_cycles"]) * period - start_s
        if t > opts["passage_seconds"]:
            break
        if t >= 0.0:
            out.append(round(t, 4))
        k += 1
    return out


def strobe_points(opts, n=10):
    c = opts["strobe_local_cm"]
    r = opts["strobe_radius_cm"]
    pts = [list(c)]
    for i in range(n):
        for j in range(n):
            th = math.pi * (i + 0.5) / n
            ph = 2 * math.pi * j / n
            p = [c[0] + r * math.sin(th) * math.cos(ph), c[1] + r * math.sin(th) * math.sin(ph),
                 max(0.0, c[2] + r * math.cos(th))]
            pts.append(p)
    return pts


# --------------------------------------------------------------------------
# PLAN (pure given loaded designs).
# --------------------------------------------------------------------------
def plan_window_light(opts, table, wing, design_result, opacity, fw, window):
    """One light for one window of the LEFT wing `wing`."""
    row = table[("L", wing)]
    panel = design_result["panel"]
    width = panel["width_cm"]
    xw = station_x(opts, wing) + opts["wing_plane_dx_cm"]
    inner, outer = row["inner_cm"], row["outer_cm"]
    centroid = panel_point(window["centroid_cm"][0], window["centroid_cm"][1], width, "L", inner, outer, xw)
    light, floor, notes = place_light(centroid, opts, wing, window["bbox_cm"][3])
    axis = _sub(floor, light)
    quat, pitch, yaw = aim_quat(axis)
    outline = [panel_point(u, z, width, "L", inner, outer, xw) for u, z in window["outline_cm"]]
    inner_cone, outer_cone, cover = cone_for(light, axis, outline, opts["cone_margin_deg"])
    # leak: cone rays at the wing plane that miss paper AND miss the window (= outside the silhouette or other holes)
    leak = cone_leak(opts, light, axis, outer_cone, xw, width, inner, outer, design_result, opacity, fw, window)
    # floor patch from the window interior sample
    interior = [panel_point(u, z, width, "L", inner, outer, xw) for u, z in window["interior_sample_cm"]]
    px_area = panel["cm_per_texel_u"] * panel["cm_per_texel_z"] * window["sample_stride"]
    hits, blocked, area = [], 0, 0.0
    prev_x = station_x(opts, wing - 1) + opts["wing_plane_dx_cm"] if wing > 1 else -1.0e9
    ls, rs = spans_at(table, wing - 1) if wing > 1 else ((1, 0), (1, 0))
    for p in interior:
        g = project_to_floor(light, p)
        if g is None:
            continue
        if wing > 1 and blocked_by_wing(p, g, prev_x, ls, rs, opts["panel_height_cm"]):
            blocked += 1
            continue
        hits.append(g)
        du = project_to_floor(light, _add(p, [0.0, 1.0, 0.0]))
        dz = project_to_floor(light, _add(p, [0.0, 0.0, 1.0]))
        if du and dz:
            a = _sub(du, g)
            b = _sub(dz, g)
            area += abs(a[0] * b[1] - a[1] * b[0]) * px_area
    require(hits, "PATCH_EMPTY|wing=%d" % wing)
    require(leak["outside_silhouette_fraction"] <= opts["max_cone_leak"],
            "CONE_LEAKS_PAST_SILHOUETTE|wing=%d|%.3f" % (wing, leak["outside_silhouette_fraction"]))
    require(max(g[0] for g in hits) - min(g[0] for g in hits) <= opts["max_patch_length_cm"],
            "PATCH_SMEARS|wing=%d|length=%.0f" % (wing, max(g[0] for g in hits) - min(g[0] for g in hits)))
    xs = [g[0] for g in hits]
    ys = [g[1] for g in hits]
    patch = {"centroid_cm": [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1), 0.0],
             "bbox_cm": [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)],
             "area_m2": round(area / 1e4, 3), "blocked_by_prev_wing_fraction": round(blocked / len(interior), 3),
             "samples": len(hits)}
    # camera visibility of the patch (corridor floor), and direct lamp glare through the window
    sample = hits[:: max(1, len(hits) // 60)]
    grid = time_grid(opts)
    fractions = [visible_fraction(opts, table, camera_at(opts, t), sample) for t in grid]
    vis = intervals(grid, [f >= opts["vis_min_fraction"] for f in fractions])
    glare = []
    for t in grid:
        cam = camera_at(opts, t)
        if cam[0] >= xw:
            break
        v = _sub(cam, light)
        ang = math.degrees(math.acos(max(-1.0, min(1.0, _dot(v, axis) / (_norm(v) * _norm(axis))))))
        if ang > outer_cone:
            glare.append(False)
            continue
        s = (xw - light[0]) / (cam[0] - light[0])
        y = light[1] + s * (cam[1] - light[1])
        z = light[2] + s * (cam[2] - light[2])
        u = (y - outer) / (inner - outer) * width
        glare.append(bool(0.0 <= u <= width and not fw.mask_inside(opacity, panel, [u], [z])[0]))
    glare_iv = intervals(grid[:len(glare)], glare)
    station = station_x(opts, wing)
    rel = [light[0] - station, light[1], light[2]]
    distance = _norm(_sub(floor, light))
    return {
        "wing": wing, "label": LABEL_FMT % wing, "cue_label": "P04 Wing %03d" % wing, "cue_guid_record": row["cue_guid"],
        "design": row["design"], "edges": {"inner_cm": inner, "outer_cm": outer, "source": row["source"],
                                           "tier": row["tier"]},
        "window": {k: window[k] for k in ("rank", "area_m2", "centroid_cm", "bbox_cm", "pixels")},
        "window_centroid_local_cm": [round(c, 2) for c in centroid],
        "light_local_cm": [round(c, 2) for c in light],
        "light_world_cm": [round(c, 2) for c in _add(light, opts["passage_world_offset_cm"])],
        "light_relative_cm": [round(c, 3) for c in rel],
        "station_x_cm": station,
        "aim_floor_local_cm": [round(c, 2) for c in floor],
        "rotation_xyzw": [round(c, 9) for c in quat], "pitch_deg": round(pitch, 3), "yaw_deg": round(yaw, 3),
        "inner_cone_deg": inner_cone, "outer_cone_deg": outer_cone, "window_cover_deg": cover,
        "cone_leak": leak, "attenuation_cm": round(distance * opts["attenuation_pad"], 1),
        "throw_cm": round(distance, 1), "patch": patch, "patch_visible_s": vis,
        "patch_visible_peak_fraction": round(max(fractions), 3), "glare_s": glare_iv, "notes": notes,
        "_patch_points": [[round(g[0], 1), round(g[1], 1)] for g in hits[:: max(1, len(hits) // 400)]],
        "_window_outline_local": [[round(p[1], 1), round(p[2], 1)] for p in outline[:: max(1, len(outline) // 200)]],
    }


def cone_leak(opts, light, axis, outer_cone, xw, width, inner, outer, design_result, opacity, fw, window, n=24):
    """Fraction of rays inside the outer cone that pass the wing plane OUTSIDE paper and OUTSIDE this window."""
    a = _scale(axis, 1.0 / _norm(axis))
    helper = [0.0, 0.0, 1.0] if abs(a[2]) < 0.9 else [0.0, 1.0, 0.0]
    e1 = [a[1] * helper[2] - a[2] * helper[1], a[2] * helper[0] - a[0] * helper[2], a[0] * helper[1] - a[1] * helper[0]]
    e1 = _scale(e1, 1.0 / _norm(e1))
    e2 = [a[1] * e1[2] - a[2] * e1[1], a[2] * e1[0] - a[0] * e1[2], a[0] * e1[1] - a[1] * e1[0]]
    tan_o = math.tan(math.radians(outer_cone))
    bbox = window["bbox_cm"]
    total = leak_outline = leak_other = 0
    for i in range(n):
        for j in range(n):
            x = (i + 0.5) / n * 2 - 1
            y = (j + 0.5) / n * 2 - 1
            if x * x + y * y > 1.0:
                continue
            d = _add(a, _add(_scale(e1, x * tan_o), _scale(e2, y * tan_o)))
            if d[0] >= 0:
                continue
            s = (xw - light[0]) / d[0]
            py, pz = light[1] + s * d[1], light[2] + s * d[2]
            u = (py - outer) / (inner - outer) * width
            total += 1
            paper = bool(fw.mask_inside(opacity, design_result["panel"], [u], [pz])[0])
            if paper:
                continue
            in_window = bbox[0] <= u <= bbox[2] and bbox[1] <= pz <= bbox[3]
            if in_window:
                continue
            if 0.0 <= u <= width and 0.0 <= pz <= opts["panel_height_cm"]:
                leak_other += 1
            else:
                leak_outline += 1
    return {"rays": total, "outside_silhouette_fraction": round(leak_outline / max(1, total), 3),
            "other_holes_fraction": round(leak_other / max(1, total), 3)}


def strobe_visibility(opts, table):
    grid = time_grid(opts)
    pts = strobe_points(opts)
    flags = [visible_fraction(opts, table, camera_at(opts, t), pts) >= 0.05 for t in grid]
    return intervals(grid, flags)


def schedule(opts, lights, strobe_iv):
    """Variant A: strike just before the patch first reads, extinguish at the lamp (AfterPass at AfterPassDistance).
    Lamps whose patch only reads while the strobe owns the view are deferred (variant B flashes them)."""
    strobe_end = max([iv[1] for iv in strobe_iv], default=0.0)
    v = opts["camera_speed_cm_s"]
    for light in lights:
        lamp_route = light["station_x_cm"] + light["light_relative_cm"][0]   # InfinityStagePassageActor.cpp:1665
        light["lamp_route_cm"] = round(lamp_route, 2)
        vis = light["patch_visible_s"]
        if not vis:
            light["timing"] = {"state": "NOT_VISIBLE", "enabled": False}
            continue
        first = vis[0][0]
        last = vis[-1][1]
        after = [iv for iv in vis if iv[1] > strobe_end + 0.5]
        owned = not after
        reads_from = max(after[0][0], strobe_end) if after else first
        strike_cam_x = max(0.0, reads_from * v - opts["strike_lead_cm"],
                           light["patch"]["bbox_cm"][0] - opts["strike_patch_ahead_cm"])
        strike_distance = lamp_route - strike_cam_x
        timing = {
            "state": "STROBE_OWNED" if owned else "AFTER_STROBE",
            "strike_on_approach": True,
            "strike_distance_cm": round(max(0.0, strike_distance), 1),
            "strike_ramp_cm": opts["strike_ramp_cm"],
            "ignition_stutter": opts["strike_stutter"],
            "unstruck_intensity_scale": 0.0,
            "after_pass": opts["after_pass"],
            "after_pass_distance_cm": opts["after_pass_distance_cm"],
            "decay_distance_cm": 600.0,
            "patch_first_s": first, "patch_last_s": last,
            "strike_s": round(strike_cam_x / v, 2),
            "full_s": round(min(lamp_route, strike_cam_x + opts["strike_ramp_cm"]) / v, 2),
            "off_s": round((lamp_route + opts["after_pass_distance_cm"]) / v, 2),
        }
        timing["enabled"] = not owned or opts["variant"] == "B"
        if owned and opts["variant"] == "B":
            timing.update(flash_plan(opts, lamp_route, vis))
        light["timing"] = timing
    # cap simultaneous lit lamps
    events = []
    for light in lights:
        t = light.get("timing") or {}
        if t.get("enabled") and t.get("state") == "AFTER_STROBE":
            events.append((t["strike_s"], t["off_s"], light["wing"]))
    peak = 0
    for s, unused_e, unused_w in events:
        peak = max(peak, sum(1 for a, b, unused in events if a <= s < b))
    return {"strobe_visible_s": strobe_iv, "strobe_end_s": strobe_end, "peak_lit_together": peak,
            "cap_ok": peak <= opts["max_lit_together"]}


def flash_plan(opts, lamp_route, vis):
    """Variant B: flashes keyed to camera distance at the strobe's ANTIPHASE (half a period after each strobe peak),
    every Nth strobe, while the patch reads. FlashCameraOffsetsCm = camera route - lamp route at each peak (patch
    lines 82-87)."""
    v = opts["camera_speed_cm_s"]
    peaks = strobe_flash_times(opts)
    anti = [round(t + 0.5 * opts["strobe_period_s"], 4) for t in peaks]
    keep = []
    for index, t in enumerate(anti):
        if index % opts["flash_every_n_strobes"]:
            continue
        if any(a <= t <= b for a, b in vis):
            keep.append(t)
    return {"strike_on_approach": False, "flash": True, "flash_times_s": keep,
            "flash_camera_offsets_cm": [round(t * v - lamp_route, 1) for t in keep],
            "flash_attack_cm": opts["flash_attack_cm"], "flash_decay_cm": opts["flash_decay_cm"],
            "flash_rest_scale": opts["flash_rest_scale"], "strobe_peaks_s": peaks}


def build_plan(opts, sources=None, review_root=REVIEW):
    table = wing_table(opts, sources)
    designs, opacities = {}, {}
    fw = None
    for design in sorted(DESIGNS):
        result, opacity, fw = load_design(design, review_root, opts["panel_height_cm"], opts["min_window_m2"])
        designs[design], opacities[design] = result, opacity
    windows_by_wing = []
    for side in ("L", "R"):
        for wing in range(1, opts["wing_count"] + 1):
            row = table.get((side, wing))
            if not row:
                continue
            res = designs[row["design"]]
            win = [h for h in res["holes"] if h["is_window"]]
            entry = {"side": side, "wing": wing, "design": row["design"], "design_agrees_record": row["design_agrees"],
                     "inner_cm": round(row["inner_cm"], 2), "outer_cm": round(row["outer_cm"], 2),
                     "edge_source": row["source"], "windows": []}
            xw = station_x(opts, wing) + opts["wing_plane_dx_cm"]
            for h in win:
                c = panel_point(h["centroid_cm"][0], h["centroid_cm"][1], res["panel"]["width_cm"], side,
                                row["inner_cm"], row["outer_cm"], xw)
                entry["windows"].append({"rank": h["rank"], "area_m2": h["area_m2"], "centroid_panel_cm": h["centroid_cm"],
                                         "bbox_panel_cm": h["bbox_cm"],
                                         "centroid_local_cm": [round(v, 1) for v in c]})
            windows_by_wing.append(entry)
    wanted = opts["wings"] or [w["wing"] for w in windows_by_wing if w["side"] == "L" and w["windows"]]
    lights = []
    for wing in wanted:
        row = table[("L", wing)]
        require(row["design_agrees"], "DESIGN_DISAGREES|wing=%d|record=%s|inventory=%s"
                % (wing, row["design_record"], row["design"]))
        res = designs[row["design"]]
        candidates = []
        for h in [h for h in res["holes"] if h["is_window"]]:
            try:
                cand = plan_window_light(opts, table, wing, res, opacities[row["design"]], fw, h)
            except P04WindowShadowError as error:
                candidates.append({"wing": wing, "rejected": str(error), "rank": h["rank"]})
                continue
            score = sum(b - a for a, b in cand["patch_visible_s"]) * (1.0 - cand["cone_leak"]["outside_silhouette_fraction"])
            cand["score"] = round(score, 3)
            candidates.append(cand)
        good = sorted([c for c in candidates if "score" in c], key=lambda c: -c["score"])
        for cand in good[: opts["max_lights_per_wing"]]:
            lights.append(cand)
    labels = [l["label"] for l in lights]
    require(len(labels) == len(set(labels)), "PLAN_LABELS_NOT_UNIQUE")   # max_lights_per_wing > 1 needs suffixes
    strobe_iv = strobe_visibility(opts, table)
    timeline = schedule(opts, lights, strobe_iv)
    public_opts = {k: v for k, v in opts.items() if k not in ("mode", "confirm", "plan_sha256", "ack_records",
                                                              "allow_dirty")}
    plan = {
        "schema_version": 1, "passage": PASSAGE_KEY, "tool": "p04_window_shadows.py",
        "opts": public_opts,
        "axis_convention": ("pair/station-local: X along the route (camera travels +X), Y across (+Y = right wall, "
                            "left wings at -Y), Z up; panel u from the image-LEFT edge of the paper bbox, final image "
                            "handedness: *_L image-left = exterior/outer edge (WingGenerationConventions.md:50-53, "
                            "builder build_v3_flat.py:363-366), mapped with the MEASURED inner/outer edges so no mesh "
                            "axis sign or mirrored ISM readback is trusted"),
        "designs": {d: {"mask": r["mask"], "mask_sha256": r["mask_sha256"], "build_json": r["build_json"],
                        "channel": r["channel"], "panel": {k: r["panel"][k] for k in ("width_cm", "height_cm",
                                                                                       "cm_per_texel_u", "cm_per_texel_z")},
                        "builder_hole_count": r["build_hole_count"], "enclosed_holes": len(r["holes"]),
                        "windows": [{k: h[k] for k in ("rank", "area_m2", "centroid_cm", "bbox_cm")}
                                    for h in r["holes"] if h["is_window"]],
                        "near_misses": [{k: h[k] for k in ("rank", "area_m2", "centroid_cm")}
                                        for h in r["holes"] if not h["is_window"] and h["area_m2"] >= 0.25]}
                    for d, r in designs.items()},
        "wings": windows_by_wing,
        "lights": lights,
        "timeline": timeline,
        "light_functions_available": LF_ASSETS,
        "inferred": [
            "camera pitch 0 and vis_max_cm=%d (fog/darkness) bound the floor-patch visibility" % opts["vis_max_cm"],
            "route distance == passage-local x for camera and lamps",
            "camera speed %.2f cm/s (stills-measured; retime nominal 213.8)" % opts["camera_speed_cm_s"],
            "edges: coventry from 2 Oct S4 (meshes since swapped to _t5p by HF 5 Oct; widths agree within 1 cm), "
            "gallery from 6 Oct CVFIX probe",
            "strobe position/period as placed 5 Oct -- Gary is moving it: re-plan with the DRY's live strobe",
            "variant B antiphase needs P04 master start %d ticks @%d and strobe phase %.2f"
            % (opts["passage_start_ticks"], opts["tick_rate"], opts["strobe_phase_cycles"]),
            "beam shafts read in the P04 fog (volumetric %.2f) -- stills decide" % opts["volumetric_scattering"],
            "the cloned source row '%s' still exists with the 5 Oct shape (DRY checks)" % opts["source_light_label"],
        ],
    }
    return plan, designs, opacities, table


def write_plan(plan, path=PLAN_PATH):
    text = json.dumps(plan, indent=1, sort_keys=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return _sha256_text(text)


# --------------------------------------------------------------------------
# Preview (offline).
# --------------------------------------------------------------------------
def render_preview(plan, designs, opacities, table, opts, path=PREVIEW_PATH):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    fig = plt.figure(figsize=(18, 13), dpi=110)
    gs = fig.add_gridspec(3, 4, height_ratios=[1.35, 0.8, 1.0], hspace=0.35, wspace=0.18)
    ax = fig.add_subplot(gs[0, :])
    ax.set_title("P04 window shadows (PLAN, top-down, passage-local cm; camera travels +x on y=0)", fontsize=11)
    for (side, wing), row in sorted(table.items()):
        x = station_x(opts, wing)
        ax.plot([x, x], [row["inner_cm"], row["outer_cm"]], color="#8a6d3b" if side == "L" else "#6b7a8f", lw=2.2)
        if side == "L":
            ax.text(x, row["outer_cm"] - 90, "W%d" % wing, ha="center", fontsize=7, color="#555")
    for entry in plan["wings"]:
        for w in entry["windows"]:
            b = w["bbox_panel_cm"]
            row = table[(entry["side"], entry["wing"])]
            width = designs[entry["design"]]["panel"]["width_cm"]
            y0 = panel_point(b[0], 0, width, entry["side"], row["inner_cm"], row["outer_cm"], 0)[1]
            y1 = panel_point(b[2], 0, width, entry["side"], row["inner_cm"], row["outer_cm"], 0)[1]
            ax.plot([station_x(opts, entry["wing"])] * 2, [y0, y1], color="#2aa1d8", lw=5, solid_capstyle="butt")
    for light in plan["lights"]:
        L = light["light_local_cm"]
        C = light["window_centroid_local_cm"]
        F = light["aim_floor_local_cm"]
        on = (light.get("timing") or {}).get("enabled")
        col = "#1f4fd1" if on else "#9aa5b8"
        pts = light["_patch_points"]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=2, color=col, alpha=0.35, lw=0)
        ax.plot([L[0], C[0], F[0]], [L[1], C[1], F[1]], color=col, lw=0.8, ls="--")
        ax.scatter([L[0]], [L[1]], marker="*", s=90, color=col, zorder=5)
        ax.text(L[0] + 30, L[1] - 60, "W%03d z%d" % (light["wing"], L[2]), fontsize=7, color=col)
    s = opts["strobe_local_cm"]
    ax.add_patch(Circle((s[0], s[1]), opts["strobe_radius_cm"], color="#e04040", alpha=0.18))
    ax.scatter([s[0]], [s[1]], marker="x", color="#e04040")
    ax.text(s[0], s[1] + opts["strobe_radius_cm"] + 40, "strobe (Gary moving it)", color="#c03030", fontsize=8,
            ha="center")
    ax.axhline(0, color="#999", lw=0.6, ls=":")
    ax.set_xlim(-200, 10900)
    ax.set_ylim(-1500, 1450)
    ax.set_aspect("equal")
    ax.set_xlabel("x (cm, route)")
    ax.set_ylabel("y (cm; left wings at -y)")

    tl = fig.add_subplot(gs[1, :])
    tl.set_title("timeline vs the strobe (s): red = strobe effect in view, ticks = strobe peaks; blue bar = lamp lit "
                 "(strike -> extinguish), black line = its floor patch in frame, orange = lamp seen through window",
                 fontsize=9)
    peaks = strobe_flash_times(opts)
    for a, b in plan["timeline"]["strobe_visible_s"]:
        tl.axvspan(a, b, color="#e04040", alpha=0.15)
    tl.vlines(peaks, -1.2, -0.7, color="#e04040", lw=0.6)
    for i, light in enumerate(plan["lights"]):
        t = light.get("timing") or {}
        y = i
        if t.get("enabled") and t.get("strike_on_approach"):
            tl.barh(y, t["off_s"] - t["strike_s"], left=t["strike_s"], height=0.5, color="#1f4fd1", alpha=0.55)
        for ft in t.get("flash_times_s", []):
            tl.vlines(ft, y - 0.3, y + 0.3, color="#1f4fd1", lw=1.2)
        for a, b in light["patch_visible_s"]:
            tl.plot([a, b], [y, y], color="black", lw=1.6)
        for a, b in light["glare_s"]:
            tl.plot([a, b], [y + 0.32, y + 0.32], color="#f08a00", lw=2.5)
        tl.text(-0.5, y, "W%03d %s" % (light["wing"], t.get("state", "")), ha="right", va="center", fontsize=7)
    tl.set_xlim(0, opts["passage_seconds"])
    tl.set_ylim(-1.5, max(1, len(plan["lights"])))
    tl.set_yticks([])
    tl.set_xlabel("passage seconds (camera x = %.2f t)" % opts["camera_speed_cm_s"])

    left_designs = [d for d in sorted(designs) if d.endswith(("L_v1", "L_v2"))]
    for k, design in enumerate(left_designs[:4]):
        a = fig.add_subplot(gs[2, k])
        res = designs[design]
        op = opacities[design]
        r0, r1, c0, c1 = res["panel"]["bbox_px_rows_cols"]
        a.imshow(op[r0:r1 + 1, c0:c1 + 1], cmap="gray", vmin=0, vmax=1,
                 extent=[0, res["panel"]["width_cm"], 0, res["panel"]["height_cm"]], aspect="equal")
        for h in res["holes"]:
            if h["area_m2"] < 0.15:
                continue
            o = h["outline_cm"]
            a.scatter([p[0] for p in o], [p[1] for p in o], s=0.4, color="#2aa1d8" if h["is_window"] else "#d8a02a")
            a.text(h["centroid_cm"][0], h["centroid_cm"][1], "%.2f" % h["area_m2"], fontsize=7,
                   color="#2aa1d8" if h["is_window"] else "#d8a02a", ha="center")
        a.set_title("%s (image L = outer edge)" % design, fontsize=8)
        a.tick_params(labelsize=6)
    fig.suptitle("P04 WINDOW SHADOW plan -- %d lights, variant %s, intensity %.0f cd, moon %s" % (
        len([l for l in plan["lights"] if (l.get("timing") or {}).get("enabled")]), opts["variant"],
        opts["intensity_cd"], opts["color_rgb"]), fontsize=12)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def run_plan(args, out_plan=PLAN_PATH, out_preview=PREVIEW_PATH, sources=None, review_root=REVIEW):
    opts = check_args(dict(args, mode="PLAN"))
    plan, designs, opacities, table = build_plan(opts, sources, review_root)
    render_preview(plan, designs, opacities, table, opts, out_preview)
    plan["preview"] = os.path.basename(out_preview)     # basename: the plan sha must not depend on the folder
    sha = write_plan(plan, out_plan)
    return plan, sha


# --------------------------------------------------------------------------
# Editor plan -> rows (pure).
# --------------------------------------------------------------------------
def enabled_lights(plan):
    return [l for l in plan["lights"] if (l.get("timing") or {}).get("enabled")]


def lights_by_cue(plan):
    out = {}
    for light in enabled_lights(plan):
        out.setdefault(light["cue_label"], []).append(light)
    return out


def planned_row(source_row, light, opts):
    """Plain row for one planned light: a clone of the source spot with only the named overrides."""
    t = light["timing"]
    row = copy.deepcopy(source_row)
    row.update({"guid": "<MINT:%s>" % light["label"], "label": light["label"], "enabled": True})
    row["relative_transform"]["location"] = list(light["light_relative_cm"])
    row["relative_transform"]["rotation_xyzw"] = list(light["rotation_xyzw"])
    lg = row["lighting"]
    lg.update({"intensity": float(opts["intensity_cd"]), "intensity_units": "CANDELAS",
               "attenuation_radius_cm": float(light["attenuation_cm"]),
               "source_radius_cm": float(opts["source_radius_cm"]),
               "soft_source_radius_cm": float(opts["soft_source_radius_cm"]),
               "cast_shadows": True, "cast_volumetric_shadow": True,
               "color": [float(c) for c in opts["color_rgb"]] + [1.0], "use_temperature": False,
               "inner_cone_angle_degrees": float(light["inner_cone_deg"]),
               "outer_cone_angle_degrees": float(light["outer_cone_deg"]),
               "volumetric_scattering_intensity": float(opts["volumetric_scattering"]),
               "light_function_material": opts["light_function"]})
    drama = lg.setdefault("drama", {})
    drama.update({"strike_on_approach": bool(t.get("strike_on_approach")),
                  "strike_distance_cm": float(t.get("strike_distance_cm", 0.0)),
                  "strike_ramp_cm": float(t.get("strike_ramp_cm", opts["strike_ramp_cm"])),
                  "ignition_stutter": float(t.get("ignition_stutter", 0.0)),
                  "unstruck_intensity_scale": float(t.get("unstruck_intensity_scale", 0.0)),
                  "after_pass": t.get("after_pass", opts["after_pass"]),
                  "after_pass_distance_cm": float(t.get("after_pass_distance_cm", 0.0)),
                  "decay_distance_cm": float(t.get("decay_distance_cm", 600.0)),
                  "slow_move": False})
    if t.get("flash"):
        drama.update({"flash": True, "flash_camera_offsets_cm": list(t["flash_camera_offsets_cm"]),
                      "flash_attack_cm": float(t["flash_attack_cm"]), "flash_decay_cm": float(t["flash_decay_cm"]),
                      "flash_rest_scale": float(t["flash_rest_scale"])})
    return row


LIGHT_OVERRIDE_PATHS = [("label",), ("enabled",), ("relative_transform", "location"),
                        ("relative_transform", "rotation_xyzw")] + [
    ("lighting", k) for k in ("intensity", "intensity_units", "attenuation_radius_cm", "source_radius_cm",
                              "soft_source_radius_cm", "cast_shadows", "cast_volumetric_shadow", "color",
                              "use_temperature", "inner_cone_angle_degrees", "outer_cone_angle_degrees",
                              "volumetric_scattering_intensity", "light_function_material")] + [
    ("lighting", "drama", k) for k in ("strike_on_approach", "strike_distance_cm", "strike_ramp_cm", "ignition_stutter",
                                       "unstruck_intensity_scale", "after_pass", "after_pass_distance_cm",
                                       "decay_distance_cm", "slow_move") + FLASH_FIELDS]
ENUM_KEYS = ("intensity_units", "after_pass", "type")


def find_source_row(plain, opts):
    hits = [(c, r) for c in plain["cues"] if c["guid"] in set(plain["bay_guids"]) for r in c["attachments"]
            if r["label"] == opts["source_light_label"]]
    require(len(hits) == 1, "SOURCE_ROW_COUNT|label=%s|count=%d" % (opts["source_light_label"], len(hits)))
    cue, row = hits[0]
    require(_enum_name(row["kind"]) == "LIGHT", "SOURCE_NOT_LIGHT")
    require(_enum_name(row["lighting"]["type"]) == "SPOT", "SOURCE_NOT_SPOT|" + str(row["lighting"]["type"]))
    require(_enum_name(row["anchor"]) == "STATION", "SOURCE_ANCHOR_NOT_STATION")
    for name in EFFECT_GUID_FIELDS:
        require(str(row["effect"].get(name, ZERO_GUID)) == ZERO_GUID, "SOURCE_EFFECT_GUID_LINK|" + name)
    require(not ((row.get("ext") or {}).get("mover") or {}).get("enabled"), "SOURCE_MOVER_ENABLED")
    return cue, row


def editor_plan(plain, plan, opts):
    """Resolve the offline plan against the live Show: target cues, frames, source row, planned rows."""
    by_cue = lights_by_cue(plan)
    require(by_cue, "PLAN_HAS_NO_ENABLED_LIGHTS")
    bays = set(plain["bay_guids"])
    labels = [l["label"] for ls in by_cue.values() for l in ls]
    require(len(labels) == len(set(labels)) and all(LABEL_RE.match(x) for x in labels), "LABELS_INVALID|%s" % labels)
    for c in plain["cues"]:
        for row in c["attachments"]:
            require(row["label"] not in labels and not LABEL_RE.match(str(row["label"])),
                    "LABEL_ALREADY_EXISTS|cue=%s|label=%s" % (c["label"], row["label"]))
    source_cue, source = find_source_row(plain, opts)
    targets = []
    for cue_label, lights in sorted(by_cue.items()):
        hits = [c for c in plain["cues"] if c["guid"] in bays and c["label"] == cue_label]
        require(len(hits) == 1, "TARGET_CUE_COUNT|%s|%d" % (cue_label, len(hits)))
        cue = hits[0]
        require(_enum_name(cue.get("type", "WING_PAIR")) in ("WING_PAIR", "WINGPAIR"), "TARGET_NOT_WING_PAIR")
        stations = [s for s in plain["stations"] if s["cue_guid"] == cue["guid"]]
        require(len(stations) == 1, "STATION_COUNT|%s|%d" % (cue_label, len(stations)))
        pair_world = compose(cue["occurrence_offset"], stations[0]["world"])
        rows, frames = [], []
        for light in lights:
            if light.get("cue_guid_record"):
                require(cue["guid"] == light["cue_guid_record"], "CUE_GUID_DRIFT|%s" % cue_label)
            world = _add(light["light_local_cm"], opts["passage_world_offset_cm"])
            computed = inverse_point(pair_world, world)
            dis = _dist(computed, light["light_relative_cm"])
            require(dis <= opts["max_frame_disagreement_cm"], "FRAME_DISAGREES|%s|computed=%s|nominal=%s|dist=%.3f"
                    % (light["label"], [round(v, 2) for v in computed], light["light_relative_cm"], dis))
            frames.append({"label": light["label"], "computed_cm": computed, "nominal_cm": light["light_relative_cm"],
                           "disagreement_cm": dis})
            lit = dict(light, light_relative_cm=computed)
            # the station frame may be rotated; keep the aim in world terms
            q_inv = [-pair_world["rotation_xyzw"][0], -pair_world["rotation_xyzw"][1],
                     -pair_world["rotation_xyzw"][2], pair_world["rotation_xyzw"][3]]
            lit["rotation_xyzw"] = canonical_quat(quat_mul(q_inv, light["rotation_xyzw"]))
            rows.append(planned_row(source, lit, opts))
        targets.append({"cue_guid": cue["guid"], "cue_label": cue_label, "show_index": cue["show_index"],
                        "before_count": len(cue["attachments"]),
                        "light_count": sum(1 for r in cue["attachments"] if _enum_name(r["kind"]) == "LIGHT"),
                        "planned_rows": rows, "frames": frames})
    target_guids = {t["cue_guid"] for t in targets}
    scratch = choose_scratch(plain, target_guids, opts.get("avoid_scratch_cues") or ())
    scratch_lights = sum(1 for r in scratch["attachments"] if _enum_name(r["kind"]) == "LIGHT")
    return {"source": {"cue_guid": source_cue["guid"], "cue_label": source_cue["label"], "guid": source["guid"],
                       "label": source["label"]},
            "targets": targets,
            "scratch": {"cue_guid": scratch["guid"], "cue_label": scratch["label"], "show_index": scratch["show_index"],
                        "light_count": scratch_lights}}


def choose_scratch(plain, target_guids, avoid=()):
    skip = set(avoid) | set(target_guids)
    ref = min(c["show_index"] for c in plain["cues"] if c["guid"] in target_guids)
    candidates = [(abs(c["show_index"] - ref), c["show_index"], c) for c in plain["cues"]
                  if c["guid"] not in skip and _enum_name(c.get("type", "")) in ("WING_PAIR", "WINGPAIR")]
    require(candidates, "SCRATCH_CUE_MISSING")
    candidates.sort(key=lambda t: (t[0], t[1]))
    return candidates[0][2]


def padding_needed(target_lights, scratch_lights, new_count):
    return max(0, target_lights + new_count - scratch_lights)


def realize(rows, minted):
    """Planned rows with "<MINT:label>" replaced by the minted GUIDs (same order)."""
    out = []
    for row, guid in zip(rows, minted):
        text = _canonical(row).replace("<MINT:%s>" % row["label"], guid)
        out.append(json.loads(text))
    return out


def _valid_guid(text):
    return isinstance(text, str) and re.fullmatch(r"[0-9A-F]{32}", text) is not None and text != ZERO_GUID


def check_minted(minted, preexisting, count):
    require(len(minted) == count, "MINTED_COUNT|%d|%d" % (len(minted), count))
    require(all(_valid_guid(g) for g in minted), "MINTED_GUID_INVALID|%s" % minted)
    require(len(set(minted)) == len(minted), "MINTED_GUID_DUPLICATE")
    clash = [g for g in minted if g in set(preexisting)]
    require(not clash, "MINTED_GUID_NOT_FRESH|%s" % clash)


def _pop_path(row, path):
    node = row
    for key in path[:-1]:
        node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            return None, False
    if not isinstance(node, dict) or path[-1] not in node:
        return None, False
    return node.pop(path[-1]), True


def _value_close(path, want, got):
    if path[-1] == "rotation_xyzw":
        return isinstance(got, list) and len(got) == 4 and quat_close(want, got)
    if path[-1] in ENUM_KEYS:
        return _enum_name(want) == _enum_name(got)
    if path[-1] == "light_function_material":
        return (want or None) == (str(got).split(".")[0] if got else None) or want == got
    if isinstance(want, bool) or isinstance(got, bool) or isinstance(want, str) or want is None:
        return want == got
    if isinstance(want, (list, tuple)):
        return (isinstance(got, (list, tuple)) and len(got) == len(want)
                and all(_value_close(path, a, b) for a, b in zip(want, got)))
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        tol = LOC_TOL_CM if path[-1] == "location" else REL_TOL * max(1.0, abs(float(want)))
        return abs(float(want) - float(got)) <= tol
    return want == got


def state_differences(a, b):
    """Field-level diff for plain rows (fallback when the editor tool's _state_differences is absent)."""
    out = []

    def walk(x, y, path):
        if isinstance(x, dict) and isinstance(y, dict):
            for key in sorted(set(x) | set(y)):
                if key not in x or key not in y:
                    out.append({"path": path + "." + str(key), "before": x.get(key), "after": y.get(key)})
                else:
                    walk(x[key], y[key], path + "." + str(key))
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            for i, (p, q) in enumerate(zip(x, y)):
                walk(p, q, "%s[%d]" % (path, i))
        elif x != y:
            out.append({"path": path, "before": x, "after": y})

    walk(a, b, "")
    return out


def planned_differences(diff, planned, got, paths):
    a, b = copy.deepcopy(planned), copy.deepcopy(got)
    out = []
    for path in paths:
        want, has_want = _pop_path(a, path)
        have, has_have = _pop_path(b, path)
        if not has_want and not has_have:
            continue
        if has_want != has_have or not _value_close(path, want, have):
            out.append({"path": ".".join(path), "before": want, "after": have})
    return out + diff(a, b)


def scope_differences(diff, base_all, live_all, targets, minted_by_cue, side):
    """after: each target cue == before + its planned rows (minted), every other cue identical.
    before: every cue identical to base_all."""
    require(side in ("before", "after"), "SIDE_INVALID")
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    by_guid = {t["cue_guid"]: t for t in targets}
    problems = []
    for cue_guid in sorted(base_all):
        before, live = base_all[cue_guid], live_all[cue_guid]
        if side == "after" and cue_guid in by_guid:
            t = by_guid[cue_guid]
            n, k = len(before), len(t["planned_rows"])
            if len(live) != n + k:
                problems.append({"cue": cue_guid, "problem": "ROW_COUNT", "want": n + k, "got": len(live)})
                continue
            for index, (want, got) in enumerate(zip(before, live[:n])):
                d = diff(want, got)
                if d:
                    problems.append({"cue": cue_guid, "index": index, "differences": d[:10]})
            for want, got in zip(realize(t["planned_rows"], minted_by_cue[cue_guid]), live[n:]):
                d = planned_differences(diff, want, got, LIGHT_OVERRIDE_PATHS)
                if d:
                    problems.append({"cue": cue_guid, "label": want["label"], "differences": d[:20]})
            continue
        d = diff(before, live)
        if d:
            problems.append({"cue": cue_guid, "differences": d[:20]})
    return problems


def check_scope(diff, base_all, live_all, targets, minted_by_cue, side):
    problems = scope_differences(diff, base_all, live_all, targets, minted_by_cue, side)
    require(not problems, "SCOPE_CHANGED|side=%s|count=%d|%s" % (side, len(problems), _canonical(problems)[:3000]))


def add_plain(all_rows, targets, minted_by_cue):
    result = copy.deepcopy(all_rows)
    for t in targets:
        result[t["cue_guid"]] = copy.deepcopy(all_rows[t["cue_guid"]]) + realize(t["planned_rows"],
                                                                                 minted_by_cue[t["cue_guid"]])
    return result


def check_record(record):
    require(record.get("passage") == PASSAGE_KEY, "RECORD_PASSAGE_MISMATCH")
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|" + str(record.get("status")))
    for key in ("targets", "before_rows", "after_rows", "minted_by_cue"):
        require(key in record, "REVERT_RECORD_FIELD_MISSING|" + key)
    for cue_guid, minted in record["minted_by_cue"].items():
        require(minted and all(_valid_guid(g) for g in minted), "REVERT_RECORD_GUIDS|" + cue_guid)


def revert_plain(diff, all_rows, record):
    result = copy.deepcopy(all_rows)
    for cue_guid, minted in record["minted_by_cue"].items():
        live = all_rows.get(cue_guid)
        require(live is not None, "CUE_GONE|" + cue_guid)
        drift = diff(record["after_rows"][cue_guid], live)
        require(not drift, "REVERT_DRIFT|%s|%s" % (cue_guid, _canonical(drift)[:2000]))
        kept = [r for r in live if r["guid"] not in set(minted)]
        require(len(kept) == len(live) - len(minted), "REVERT_GUID_COUNT|" + cue_guid)
        require(not diff(record["before_rows"][cue_guid], kept), "REVERT_NOT_EXACT|" + cue_guid)
        result[cue_guid] = kept
    return result


def check_context(ctx, mode, allow_dirty=(), show_path=None, world_path=None):
    """p04_glint_practical.py:407-420."""
    require(ctx.get("project_ok", True), "WRONG_PROJECT")
    require(ctx.get("world_ok", True), "WRONG_WORLD|" + str(ctx.get("world")))
    census = ctx.get("census") or {}
    if mode == "DRY":
        return
    require(not ctx.get("pie"), "PIE_OR_SIE_ACTIVE")
    require(not ctx.get("sequencer_open"), "SEQUENCER_IS_OPEN")
    require(not ctx.get("zz_actors"), "STRAY_ZZ_ACTORS|" + ",".join(ctx.get("zz_actors") or []))
    allowed = set(allow_dirty or [])
    if show_path or world_path:
        require(allowed <= {show_path, world_path}, "ALLOW_DIRTY_OUT_OF_SCOPE|%s" % sorted(allowed))
    dirty = set(census.get("content") or []) | set(census.get("maps") or [])
    require(dirty <= allowed, "DIRTY_BEFORE|census=" + _canonical(census))


def check_apply_gate(unacked, record_file=RECORD_PATH):
    require(not os.path.exists(record_file), "ACTIVE_RECORD_EXISTS|" + record_file)
    require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))


def load_plan_checked(opts):
    path = opts["plan_path"] or PLAN_PATH
    require(os.path.isfile(path), "PLAN_MISSING|" + path)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    sha = _sha256_text(text)
    if opts["mode"] == "APPLY":
        require(sha == opts["plan_sha256"], "PLAN_SHA_MISMATCH|file=%s|args=%s" % (sha, opts["plan_sha256"]))
    plan = json.loads(text)
    require(plan.get("passage") == PASSAGE_KEY, "PLAN_PASSAGE")
    if any((l.get("timing") or {}).get("flash") for l in enabled_lights(plan)):
        require(unreal is None or _has_flash_fields(), "VARIANT_B_NEEDS_FLASH_PATCH_BUILT")
    return plan, sha, path


def _has_flash_fields():
    try:
        drama = unreal.InfinityStageLightDrama()
        drama.get_editor_property("flash_camera_offsets_cm")
        return True
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# Module loading -- copied from p04_glint_practical.py:444-521.
# --------------------------------------------------------------------------
_SAFE_CALLS = {"os.path.join", "os.path.dirname", "os.path.abspath", "os.path.normcase",
               "os.path.normpath", "re.compile", "tuple", "frozenset", "set", "dict", "list",
               "_load_attachment_state"}


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return None if inner is None else inner + "." + node.attr
    return None


def _is_main_guard(node):
    return (isinstance(node, ast.If) and not node.orelse and len(node.body) == 1
            and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "unreal" and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value is None
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call)
            and _dotted(node.body[0].value.func) == "main"
            and not node.body[0].value.args and not node.body[0].value.keywords)


def _top_level_ok(node, index):
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
        return True
    if isinstance(node, ast.Expr):
        return index == 0 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return node.value is None or all(_dotted(c.func) in _SAFE_CALLS
                                         for c in ast.walk(node.value) if isinstance(c, ast.Call))
    if isinstance(node, ast.Try):
        inner = list(node.body) + [s for h in node.handlers for s in h.body] + list(node.orelse) + list(node.finalbody)
        return all(isinstance(s, (ast.Import, ast.ImportFrom))
                   or (isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)) for s in inner)
    return False


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1])
            and sum(1 for n in tree.body if _is_main_guard(n)) == 1, "MAIN_GUARD_SHAPE|" + path)
    for index, node in enumerate(tree.body[:-1]):
        require(_top_level_ok(node, index), "TOP_LEVEL_SIDE_EFFECT|%s|line=%d" % (path, getattr(node, "lineno", -1)))
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


SCORES_REQUIRED = ("load_p04_tool", "_materialize_passage", "_count_passage_actors", "scan_foreign_records",
                   "read_extensions")
TOOL_EXTRA_REQUIRED = ("S", "_state_differences", "_guid_text", "_write_json", "_read_json", "_dirty_census",
                       "_backup", "_save_narrow", "_pair_attachments", "_set_pair_attachments", "_attachment_rows",
                       "_make_blank_light", "_is_light", "_enum_member", "SHOW_PATH", "EXPECTED_WORLD",
                       "EXPECTED_PROJECT", "_asset_id")


def load_modules():
    scores = load_without_main(SCORES_TOOL_PATH, "_lighting_scores_for_p04_winshadow")
    missing = [n for n in SCORES_REQUIRED if not callable(getattr(scores, n, None))]
    require(not missing, "SCORES_API_DRIFT|" + ",".join(missing))
    tool = scores.load_p04_tool()
    missing = [n for n in TOOL_EXTRA_REQUIRED if not hasattr(tool, n)]
    require(not missing, "P04_TOOL_API_DRIFT|" + ",".join(missing))
    return scores, tool


def scan_foreign(scores, guids, saved_dir=None):
    saved = saved_dir or os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, guids, exclude=[RECORD_PATH])


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# Helpers copied from p04_glint_practical.py:527-731 (multi-cue where noted).
# --------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _ctx_facts(tool):
    project = os.path.normcase(os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))).rstrip("\\/")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if world is not None else []
    return {"project_ok": project == tool.EXPECTED_PROJECT.rstrip("\\/"),
            "world": tool._asset_id(world) if world is not None else None,
            "world_ok": world is not None and tool._asset_id(world) == tool.EXPECTED_WORLD,
            "pie": editor.get_game_world() is not None,
            "sequencer_open": library is not None and library.get_current_level_sequence() is not None,
            "census": tool._dirty_census(),
            "zz_actors": sorted(a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_"))}


def _strobe_readout():
    """READ-ONLY: the live strobe's location/period/phase so the offline plan can be re-run (never written)."""
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    hits = [a for a in subsystem.get_all_level_actors() if a.get_class().get_name() == "InfinityStageStrobeLight"]
    out = []
    for actor in hits:
        loc = actor.get_actor_location()
        row = {"label": str(actor.get_actor_label()), "world_cm": [loc.x, loc.y, loc.z]}
        for name in ("period_seconds", "flash_seconds", "decay_seconds", "phase_cycles", "peak_intensity",
                     "attenuation_radius_cm"):
            try:
                row[name] = float(actor.get_editor_property(name))
            except Exception:  # noqa: BLE001
                row[name] = None
        out.append(row)
    return out


def _rows(scores, tool, attachments):
    out = []
    for attachment, row in zip(attachments, tool._attachment_rows(attachments)):
        row["ext"] = scores.read_extensions(tool, attachment)
        out.append(row)
    return out


def _find_structure(show):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = [a for a in subsystem.get_all_level_actors()
             if a.get_class().get_name() == "InfinityStageStructureActor" and a.get_actor_label() == STRUCTURE_LABEL]
    require(len(found) == 1, "STRUCTURE_COUNT|label=%s|count=%d" % (STRUCTURE_LABEL, len(found)))
    passage = found[0].get_editor_property("passage")
    require(passage is not None and passage.get_actor_label().startswith(PASSAGE_ACTOR_PREFIX), "STRUCTURE_PASSAGE_WRONG")
    require(passage.get_editor_property("show_asset") == show, "STRUCTURE_SHOW_WRONG")
    return found[0]


def _stations(tool, structure):
    result = structure.gather_stations()
    if isinstance(result, tuple) and len(result) == 3:
        ok, stations, error = result
        require(bool(ok), "GATHER_STATIONS_FAILED|" + str(error))
    elif isinstance(result, tuple) and len(result) == 2:
        stations, error = result
    else:
        stations, error = result, ""
    require(stations is not None and len(list(stations)) > 0, "GATHER_STATIONS_EMPTY|" + str(error))
    return [{"cue_guid": tool._guid_text(s.get_editor_property("cue_guid")),
             "distance_cm": float(s.get_editor_property("distance_cm")),
             "world": tool.S._transform_state(s.get_editor_property("station_world"))} for s in stations]


def _passage_guid(tool, show):
    rows = [s for s in show.get_editor_property("passage_settings")
            if str(s.get_editor_property("label")) == PASSAGE_LABEL]
    require(len(rows) == 1, "PASSAGE_ROW_COUNT|label=%s|count=%d" % (PASSAGE_LABEL, len(rows)))
    value = rows[0].get_editor_property("passage_guid")
    return value, tool._guid_text(value)


def _runtime_plain(scores, tool, show, structure=None):
    cues = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        pair = cue.get_editor_property("wing_pair")
        cues.append({"show_index": index, "guid": tool._guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")), "type": str(cue.get_editor_property("type")),
                     "occurrence_offset": tool.S._transform_state(pair.get_editor_property("occurrence_offset")),
                     "attachments": _rows(scores, tool, tool._pair_attachments(cue))})
    value, guid = _passage_guid(tool, show)
    bays = [tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(value)]
    return {"cues": cues, "bay_guids": bays, "passage_guid": guid,
            "stations": _stations(tool, structure) if structure is not None else []}


def _all_rows(plain):
    return {cue["guid"]: cue["attachments"] for cue in plain["cues"]}


def _export_hash(show, skip_guids, tool):
    texts = []
    for cue in show.get_editor_property("cues"):
        if tool._guid_text(cue.get_editor_property("cue_guid")) in skip_guids:
            continue
        texts.append(str(cue.export_text()))
    for row in show.get_editor_property("passage_settings"):
        texts.append(str(row.export_text()))
    return _sha256_text("\n".join(texts))


def _cue_index(tool, show, cue_guid, label):
    cues = list(show.get_editor_property("cues"))
    hits = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == cue_guid]
    require(len(hits) == 1, "CUE_RESOLVE|guid=%s|count=%d" % (cue_guid, len(hits)))
    require(str(cues[hits[0]].get_editor_property("label")) == label, "CUE_LABEL_DRIFT|" + cue_guid)
    return hits[0], cues


def _source_object(tool, show, ep):
    index, cues = _cue_index(tool, show, ep["source"]["cue_guid"], ep["source"]["cue_label"])
    hits = [a for a in tool._pair_attachments(cues[index])
            if tool._guid_text(a.get_editor_property("attachment_guid")) == ep["source"]["guid"]]
    require(len(hits) == 1, "SOURCE_OBJECT_GONE")
    return hits[0]


def _author(tool, vessel, source, row):
    """Copy every field but the GUID from the source spot, then exactly the planned overrides."""
    minted = tool._guid_text(vessel.get_editor_property("attachment_guid"))
    for name in CLONE_FIELDS:
        vessel.set_editor_property(name, source.get_editor_property(name))
    vessel.set_editor_property("label", unreal.Text(row["label"]))
    vessel.set_editor_property("enabled", True)
    loc = row["relative_transform"]["location"]
    rot = row["relative_transform"]["rotation_xyzw"]
    transform = vessel.get_editor_property("relative_transform")
    transform.set_editor_property("translation", unreal.Vector(float(loc[0]), float(loc[1]), float(loc[2])))
    transform.set_editor_property("rotation", unreal.Quat(float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])))
    vessel.set_editor_property("relative_transform", transform)
    lg = row["lighting"]
    settings = vessel.get_editor_property("lighting")
    settings.set_editor_property("intensity_units", tool._enum_member(unreal.InfinityStageLightIntensityUnits,
                                                                      _enum_name(lg["intensity_units"])))
    for name in ("intensity", "attenuation_radius_cm", "source_radius_cm", "soft_source_radius_cm",
                 "inner_cone_angle_degrees", "outer_cone_angle_degrees", "volumetric_scattering_intensity"):
        settings.set_editor_property(name, float(lg[name]))
    for name in ("cast_shadows", "cast_volumetric_shadow", "use_temperature"):
        settings.set_editor_property(name, bool(lg[name]))
    c = lg["color"]
    settings.set_editor_property("color", unreal.LinearColor(float(c[0]), float(c[1]), float(c[2]), 1.0))
    lf = lg.get("light_function_material")
    settings.set_editor_property("light_function_material", unreal.load_asset(lf) if lf else None)
    dr = lg["drama"]
    drama = settings.get_editor_property("drama")
    for name in ("strike_on_approach", "slow_move"):
        drama.set_editor_property(name, bool(dr[name]))
    for name in ("strike_distance_cm", "strike_ramp_cm", "ignition_stutter", "unstruck_intensity_scale",
                 "after_pass_distance_cm", "decay_distance_cm"):
        drama.set_editor_property(name, float(dr[name]))
    drama.set_editor_property("after_pass", tool._enum_member(unreal.InfinityLightAfterPass, _enum_name(dr["after_pass"])))
    if dr.get("flash"):
        drama.set_editor_property("flash", True)
        drama.set_editor_property("flash_camera_offsets_cm", [float(v) for v in dr["flash_camera_offsets_cm"]])
        for name in ("flash_attack_cm", "flash_decay_cm", "flash_rest_scale"):
            drama.set_editor_property(name, float(dr[name]))
    settings.set_editor_property("drama", drama)
    vessel.set_editor_property("lighting", settings)
    require(tool._guid_text(vessel.get_editor_property("attachment_guid")) == minted, "MINTED_GUID_CHANGED")
    return vessel


def _snapshot(tool, show, ep):
    snap = {"targets": {}, "scratch": None}
    for t in ep["targets"]:
        index, cues = _cue_index(tool, show, t["cue_guid"], t["cue_label"])
        require(index == t["show_index"], "SHOW_INDEX_DRIFT|" + t["cue_label"])
        snap["targets"][t["cue_guid"]] = (index, tool._pair_attachments(cues[index]))
    index, cues = _cue_index(tool, show, ep["scratch"]["cue_guid"], ep["scratch"]["cue_label"])
    snap["scratch"] = (index, tool._pair_attachments(cues[index]))
    return snap


def _rollback(tool, show, snap):
    tool._set_pair_attachments(show, snap["scratch"][0], snap["scratch"][1])
    for index, rows in snap["targets"].values():
        tool._set_pair_attachments(show, index, rows)


def _mint_cue(scores, tool, show, ep, snap, target, source):
    """One scratch-pair minting cycle for one target cue (lighting_scores_apply.py:2738-2814 pattern)."""
    ti, target_original = snap["targets"][target["cue_guid"]]
    si, scratch_original = snap["scratch"]
    n = len(target["planned_rows"])
    scratch_before = _rows(scores, tool, scratch_original)
    cues = list(show.get_editor_property("cues"))
    target_lights = [tool._guid_text(a.get_editor_property("attachment_guid")) for a in target_original
                     if tool._is_light(a)]
    k, m = len(target_lights), sum(1 for a in scratch_original if tool._is_light(a))
    require(k == target["light_count"] and m == ep["scratch"]["light_count"], "LIGHT_COUNT_DRIFT|" + target["cue_label"])
    preexisting = {tool._guid_text(a.get_editor_property("attachment_guid"))
                   for cue in cues for a in tool._pair_attachments(cue)}
    tool._set_pair_attachments(show, si, scratch_original + [tool._make_blank_light()
                                                             for _ in range(padding_needed(k, m, n))])
    fresh = list(show.get_editor_property("cues"))
    changed = show.replicate_light_attachments(fresh[si].get_editor_property("cue_guid"),
                                               [fresh[ti].get_editor_property("cue_guid")])
    require(int(changed) == 1, "REPLICATION_TARGET_COUNT|%s" % changed)
    tool._set_pair_attachments(show, si, scratch_original)
    restored = _rows(scores, tool, tool._pair_attachments(list(show.get_editor_property("cues"))[si]))
    require(not tool._state_differences(scratch_before, restored), "SCRATCH_NOT_RESTORED_EXACTLY")
    replicated = tool._pair_attachments(list(show.get_editor_property("cues"))[ti])
    vessels = [a for a in replicated if tool._is_light(a)]
    require(len(vessels) >= k + n, "MINTED_SLOT_COUNT|need=%d|actual=%d" % (k + n, len(vessels)))
    require([tool._guid_text(v.get_editor_property("attachment_guid")) for v in vessels[:k]] == target_lights,
            "REPLICATE_DID_NOT_KEEP_LIGHT_GUIDS")
    fresh_vessels = vessels[k:k + n]
    minted = [tool._guid_text(v.get_editor_property("attachment_guid")) for v in fresh_vessels]
    check_minted(minted, preexisting, n)
    for vessel, row in zip(fresh_vessels, target["planned_rows"]):
        _author(tool, vessel, source, row)
    tool._set_pair_attachments(show, ti, target_original + fresh_vessels)
    return minted


def _materialize(scores, show):
    require(scores._count_passage_actors(show, PASSAGE_ACTOR_PREFIX) == 1, "PASSAGE_ACTOR_COUNT")
    materialized = scores._materialize_passage(show, PASSAGE_ACTOR_PREFIX)
    require(materialized.get("structure") == STRUCTURE_LABEL, "STRUCTURE_NOT_REFIT|%s" % materialized)
    return materialized


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = args["mode"]
    report = {"ok": False, "mode": mode, "run": run, "args": args, "saved": False}
    tool = None
    try:
        require(mode != "PLAN", "PLAN_IS_OFFLINE_ONLY (run python p04_window_shadows.py outside Unreal)")
        scores, tool = load_modules()
        diff = tool._state_differences
        ctx = _ctx_facts(tool)
        report["context"] = ctx
        check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")

        if mode in ("DRY", "APPLY"):
            plan, plan_sha, plan_path = load_plan_checked(args)
            report.update({"plan_path": plan_path, "plan_sha256": plan_sha, "strobe_readonly": _strobe_readout()})
            structure = _find_structure(show)
            plain = _runtime_plain(scores, tool, show, structure)
            before_all = _all_rows(plain)
            ep = editor_plan(plain, plan, dict(plan["opts"], **{k: args[k] for k in ("source_light_label",
                                                                                     "max_frame_disagreement_cm",
                                                                                     "avoid_scratch_cues")}))
            fake = {t["cue_guid"]: ["%032X" % (0xF00 + i) for i in range(len(t["planned_rows"]))] for t in ep["targets"]}
            check_scope(diff, before_all, add_plain(before_all, ep["targets"], fake), ep["targets"], fake, "after")
            skip = {t["cue_guid"] for t in ep["targets"]}
            texts_hash = _export_hash(show, skip, tool)
            foreign = scan_foreign(scores, sorted(skip))
            unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
            report.update({"editor_plan": ep, "foreign_records": foreign, "unacknowledged_foreign_records": unacked,
                           "active_record": RECORD_PATH if os.path.exists(RECORD_PATH) else None})
            if mode == "DRY":
                require(tool._dirty_census() == census_before, "DRY_CENSUS_CHANGED")
                require(_canonical(_all_rows(_runtime_plain(scores, tool, show))) == _canonical(before_all),
                        "DRY_SHOW_ROWS_CHANGED")
                report.update({"ok": True, "mutated": False})
                path = report_path(mode, run)
                tool._write_json(path, report)
                _log("%s_DRY_OK|run=%s|plan_sha256=%s|lights=%d|cues=%d|source=%s|scratch=%s|max_disagree_cm=%.3f"
                     "|strobes=%s|foreign=%d|unacked=%d|mutated=0|report=%s"
                     % (MARK, run, plan_sha, sum(len(t["planned_rows"]) for t in ep["targets"]), len(ep["targets"]),
                        ep["source"]["label"], ep["scratch"]["cue_label"],
                        max(f["disagreement_cm"] for t in ep["targets"] for f in t["frames"]),
                        [(s["label"], [round(v) for v in s["world_cm"]]) for s in report["strobe_readonly"]],
                        len(foreign), len(unacked), path))
                return report

            check_apply_gate(unacked)
            backup = tool._backup("PreP04WindowShadowApply-", run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "passage": PASSAGE_KEY, "backup": backup,
                      "args": args, "plan_sha256": plan_sha, "editor_plan": ep, "targets": ep["targets"],
                      "export_hash_before": texts_hash,
                      "before_rows": {g: before_all[g] for g in skip}, "minted_by_cue": {},
                      "acknowledged_records": list(args["ack_records"])}
            tool._write_json(RECORD_PATH, record, exclusive=True)
            _log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run, RECORD_PATH))
            snap = _snapshot(tool, show, ep)
            try:
                source = _source_object(tool, show, ep)
                for target in ep["targets"]:
                    record["minted_by_cue"][target["cue_guid"]] = _mint_cue(scores, tool, show, ep, snap, target, source)
                after_all = _all_rows(_runtime_plain(scores, tool, show))
                check_scope(diff, before_all, after_all, ep["targets"], record["minted_by_cue"], "after")
                require(_export_hash(show, skip, tool) == texts_hash, "EXPORT_OUTSIDE_SCOPE_CHANGED")
            except Exception:
                _rollback(tool, show, snap)
                check_scope(diff, before_all, _all_rows(_runtime_plain(scores, tool, show)), ep["targets"], {}, "before")
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
                raise
            record.update({"status": "mutated_verified", "after_rows": {g: after_all[g] for g in skip}})
            tool._write_json(RECORD_PATH, record)
            materialized = _materialize(scores, show)
            tool._save_narrow()
            report["saved"] = True
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            read_all = _all_rows(_runtime_plain(scores, tool, readback))
            check_scope(diff, before_all, read_all, ep["targets"], record["minted_by_cue"], "after")
            require(_export_hash(readback, skip, tool) == texts_hash, "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
            record.update({"status": "saved_readback_verified", "materialized": materialized,
                           "after_rows": {g: read_all[g] for g in skip}, "saved_census": tool._dirty_census()})
            tool._write_json(RECORD_PATH, record)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "minted_by_cue": record["minted_by_cue"]})
            tool._write_json(report_path(mode, run), report)
            _log("%s_APPLY_OK|run=%s|plan_sha256=%s|cues=%d|lights=%d|show_saved=1|level_saved=1|readback=1|record=%s"
                 % (MARK, run, plan_sha, len(ep["targets"]), sum(len(v) for v in record["minted_by_cue"].values()),
                    RECORD_PATH))
            return report

        # REVERT
        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
        record = tool._read_json(RECORD_PATH)
        check_record(record)
        before_all = _all_rows(_runtime_plain(scores, tool, show))
        model = revert_plain(diff, before_all, record)
        skip = set(record["minted_by_cue"])
        all_minted = [g for v in record["minted_by_cue"].values() for g in v]
        foreign = scan_foreign(scores, sorted(skip) + all_minted)
        unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
        report.update({"foreign_records": foreign, "unacknowledged_foreign_records": unacked})
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        texts_hash = _export_hash(show, skip, tool)
        backup = tool._backup("PreP04WindowShadowRevert-", run)
        originals = {}
        try:
            for target in record["targets"]:
                index, cues = _cue_index(tool, show, target["cue_guid"], target["cue_label"])
                original = tool._pair_attachments(cues[index])
                originals[target["cue_guid"]] = (index, original)
                minted = set(record["minted_by_cue"][target["cue_guid"]])
                kept = [a for a in original if tool._guid_text(a.get_editor_property("attachment_guid")) not in minted]
                require(len(kept) == len(original) - len(minted), "REVERT_GUID_COUNT|" + target["cue_label"])
                tool._set_pair_attachments(show, index, kept)
            after_all = _all_rows(_runtime_plain(scores, tool, show))
            require(not diff(model, after_all), "REVERT_MODEL_MISMATCH")
            require(_export_hash(show, skip, tool) == texts_hash, "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            for index, original in originals.values():
                tool._set_pair_attachments(show, index, original)
            raise
        materialized = _materialize(scores, show)
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = _all_rows(_runtime_plain(scores, tool, readback))
        require(not diff(model, read_all), "REVERT_READBACK_MISMATCH")
        require(_export_hash(readback, skip, tool) == texts_hash, "REVERT_READBACK_EXPORT_CHANGED")
        archived = RECORD_PATH + ".reverted-" + run
        record["status"] = "reverted"
        tool._write_json(RECORD_PATH, record)
        os.rename(RECORD_PATH, archived)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized})
        tool._write_json(report_path(mode, run), report)
        _log("%s_REVERT_OK|run=%s|removed=%d|show_saved=1|level_saved=1|readback=1|archived=%s"
             % (MARK, run, len(all_minted), archived))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path(mode, run), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s"
                         % (MARK, run, mode, int(report["saved"]), report["error"][:1500],
                            "" if report["saved"] else "|NOTHING SAVED"))
        raise


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    try:
        args = check_args(globals().get("P04WINSHADOW_ARGS"))
    except Exception as error:  # noqa: BLE001
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


def plan_cli(argv=None):
    """Offline PLAN: python p04_window_shadows.py [args.json]."""
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else os.path.join(HERE, "p04_window_shadows_args.json")
    args = _read_json(path) if os.path.isfile(path) else {"mode": "PLAN"}
    require(str(args.get("mode", "PLAN")).upper() == "PLAN", "OFFLINE_RUNS_PLAN_ONLY")
    plan, sha = run_plan(args)
    on = enabled_lights(plan)
    print("%s_PLAN_OK|plan=%s|sha256=%s|lights=%d|enabled=%d|wings=%s|peak_lit=%d|strobe_visible_s=%s|preview=%s"
          % (MARK, PLAN_PATH, sha, len(plan["lights"]), len(on), [l["wing"] for l in on],
             plan["timeline"]["peak_lit_together"], plan["timeline"]["strobe_visible_s"], PREVIEW_PATH))
    return plan, sha


if __name__ == "__main__" and unreal is None:
    plan_cli()


if unreal is not None:
    main()
