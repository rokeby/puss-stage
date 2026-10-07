"""P03 ATMOS: DRY / APPLY / REVERT. Less fog in P03, the benched beam look made persistent, and a first smoke test.

Gary, 7 Oct: "P03 is also ridiculously foggy which may also be ruining all the other lighting effects. we should make
good use of the nice lighting beams we made just now here ... Reduce fog and we should try and bring in smoke machine
effects here." He chose "All of it tonight": fog cut + the soft-slat gobo + the patchy-fog look on P03's beam lights +
a first smoke-puff test.

WHAT IT CHANGES (APPLY; every before value is written to p03_atmos_record.json, fsynced, BEFORE the first change)
 1. FOG CUT, P03-local only. The global ExponentialHeightFog is NEVER written (it is one actor for the whole show;
    DRY reads and reports it). Scaled instead:
    a. Show attachments of P03's cues: lighting.volumetric_scattering_intensity x vs_scale (0.5) on every ENABLED
       LIGHT, x beam_vs_scale (1.0 = unchanged) on the score BEAM lights ("P03 SCORE B## <look> BEAM_R"), so the
       beams stay the hero. Disabled lights are left alone (they emit nothing) and listed.
    b. Show attachments of P03's cues: effect.medium_density x medium_scale (0.35) on EFFECT rows that feed a local
       medium (InfinityStageEffectSource.cpp:270-277 turns medium_density into the LFV's extinction).
    c. Level LocalFogVolume actors whose centre lies inside P03's footprint (the bbox of P03's materialized
       attachment actors + bbox_margin_cm): radial and height fog extinction x lfv_extinction_scale (0.35).
 2. BEAM LOOK (production, persistent). CREATE-ONLY assets under /Game/InfinityStage/Lighting/BeamLook, built with
    the graphs of beam_texture_bench.py (its CODE_GOBO_SLATS / CODE_GOBO_SOFT / CODE_NOISE3 strings are imported, not
    copied; flags set before the domain, bForceCompatibleWithLightFunctionAtlas on the light functions), SAVED:
      M_LF_SoftSlats, M_LF_SoftGobo (light functions, the good run's g_* values baked as parameter defaults),
      M_Vol_BeamNoise (Volume domain, the good run's b_* values).
    The score BEAM lights get lighting.light_function_material (+ light_function_disabled_brightness, + scale only
    if lf_scale is given) through the Show attachment, the same write path as p01_rig_pattern.py
    (_set_pair_attachments + materialize + _save_narrow). THREE of P03's four beams already carry the score's breath
    flicker (MI_LF_Flicker_Breath, lighting_scores_record_P03.json after_rows B08/B13/B18). A light has ONE light
    function, so lf_conflict decides: "carry_flicker" (default) builds M_LF_SoftSlatsFlicker = the slats x the
    M_LF_StageFlicker term (the graph of Saved/CodexLighting/rebuild_flicker_master.py:16-39, in HLSL, mirrored by
    lighting_scores_apply.lf_level) and one MaterialInstanceConstant per flicker profile (MI_LF_SoftSlats_Breath)
    whose six parameters are READ LIVE from the beam's current flicker instance; "replace" drops the flicker;
    "skip" leaves those beams alone.
    One noise-volume box per beam (StaticMeshActor, engine Cube, M_Vol_BeamNoise, collision off, no shadow, tag
    InfinityStage.BeamLook + P03ATMOS, label "P03 BeamLook Noise B##"), aligned to the beam from noise_start_cm to
    noise_end_cm (default 60 .. 1200 cm, i.e. the first ~12 m), side = 2 x (cone radius at the far end + margin)
    (beam_texture_bench.noisebox_spec, with a fixed span instead of the camera-route crossing).
 3. SMOKE TEST (placeholder for a real Niagara smoke; Niagara is not authorable from Python here:
    P04RainBench/p04_rain_bench_probe.json, cited by beam_texture_bench.py:68-72). smoke_count (3) floor-hugging
    noise boxes 1.2 m tall, smoke_size_cm, centred under each chosen beam smoke_along_cm along it, bottom
    smoke_sink_cm below the floor. Material M_Vol_SmokeLow = CODE_NOISE3 with its last line replaced by a height fade
    (density x (1 - (z - FloorZ)/HeightCm)^FadePow), and MI_Vol_SmokeTest_P03 with drift > 0, higher contrast, P03's
    FloorZ. Label "P03 Smoke Test N", tags InfinityStage.SmokeTest + P03ATMOS.
 Every spawned actor is Movable and ATTACHED to the Passage 03 actor (KeepWorld), so it moves with the passage
 like the materialized lights; ClearMaterializedPassage destroys only actors with an InfinityStage.Attachment.
 identity tag (InfinityStagePassageActor.cpp:66-77, :683-706), which these never carry.

REVERT: drift check first (every written Show field, LFV field and spawned actor must still read the record's after
value, else REVERT_DRIFT names them all), then writes the before values, destroys the spawned actors, materializes P03
and saves the Show + level only. Assets stay (create-only, harmless) unless args remove_assets is true, which deletes
only assets this record created, after the Show no longer references them.

Proof tiers (AGENTS.md), per claim:
* declaration-proven: attachment light fields incl. LightFunctionMaterial/Scale/DisabledBrightness and
  VolumetricScatteringIntensity (InfinityStageTypes.h:224, :349-359); the passage pushes them onto the spawned light
  (InfinityStagePassageActor.cpp:472, :491-494); spawned attachment actors carry the identity tag
  "InfinityStage.Attachment.<cue>|<attachment>" and are attached to the Passage (:964-986); Effect medium_density ->
  LFV extinction (InfinityStageEffectSource.cpp:270-277); Haze/Smoke medium defaults (InfinityStageEffectLibrary.cpp:
  35-46); the height fog is owned by the Celestial rig (InfinityStageCelestialRig.h:51, :66); P03 look values
  (lighting_scores.json variants P03_*: BEAM_R volumetric_scattering 4.0 in _SIDES, MI_LF_Flicker_Breath on the pyre
  beam); the flicker graph (rebuild_flicker_master.py:16-39); write helpers (lighting_looks_apply.py:1287-1300
  _set_pair_attachments, :1616-1633 _backup, :1657-1676 _save_narrow).
* measured (files read 7 Oct, offline): lighting_scores_record_P03.json (run 20261006-023449, saved_readback_verified):
  21 bays, 352 LIGHT + 64 PROP rows, NO Effect rows; 4 BEAM_R (B04 VS 4.0 no LF; B08/B13/B18 VS 6.0 + Breath);
  enabled non-beam VS: TOP 0.35, practicals 0.02-0.3, Rig Slash 2.0 (14), Blink Spot 0.6; 228 pre-score lights
  disabled. Height fog in PIE 6 Oct (beam bench originals BEAMTEX-20261007-003747): density 0.022, second 0.04484,
  scattering distribution 0.55; r.LightFunctionAtlas 1 and r.VolumetricFog.UsesLightFunctionAtlas 1 already (so the
  gobo needs no cvar write); bench materials built and read back (domain, blend, atlas flag True), Substrate 0.
* inferred (the first live DRY/APPLY confirms; listed in the DRY report "inferred"): that a soft-object light function
  can be set to None by set_editor_property (REVERT of B04); that MaterialInstanceConstant scalar overrides reach a
  Custom-node graph in the light-function atlas; that a Volume-domain static mesh is voxelised in the show (the bench
  saw it in PIE); the smoke height fade; that panel base z is the floor (fallback when the floor trace misses);
  that P03's footprint bbox catches every P03-local LFV and nothing of a neighbour passage.

Args (p03_atmos_args.json via p03_atmos_run.py): {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> P03ATMOS",
"params": {...DEFAULTS overrides}, "ack_records": [...], "allow_dirty": [], "expected": {"vs": n, "lf": n, ...},
"reuse_existing_assets": false, "remove_assets": false}.
Markers: P03ATMOS_DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|...; any stop P03ATMOS_STOPPED|run=<id>|<reason>.
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
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None

import beam_texture_bench as btb
import _infinity_attachment_state as S


HERE = os.path.dirname(os.path.abspath(__file__))
RIG_PATTERN_PATH = os.path.join(HERE, "p01_rig_pattern.py")
RECORD_PATH = os.path.join(HERE, "p03_atmos_record.json")
LOG_PATH = os.path.join(os.path.dirname(HERE), "Logs", "PussStage.log")
MARK = "P03ATMOS"
CONFIRM_TOKEN = "P03ATMOS"
VALID_MODES = ("DRY", "APPLY", "REVERT")
PASSAGE = "P03"
ACTOR_TAG = "P03ATMOS"
BEAMLOOK_TAG = "InfinityStage.BeamLook"
SMOKE_TAG = "InfinityStage.SmokeTest"
ATTACHMENT_TAG_PREFIX = "InfinityStage.Attachment."       # InfinityStagePassageActor.cpp:49, :971-974
CUBE = "/Engine/BasicShapes/Cube.Cube"                     # 100 cm cube, pivot at centre (look_bench.py:107)

ASSET_DIR = "/Game/InfinityStage/Lighting/BeamLook"
MAT_SLATS = ASSET_DIR + "/M_LF_SoftSlats"
MAT_GOBO = ASSET_DIR + "/M_LF_SoftGobo"
MAT_SLATS_FLK = ASSET_DIR + "/M_LF_SoftSlatsFlicker"
MAT_GOBO_FLK = ASSET_DIR + "/M_LF_SoftGoboFlicker"
MAT_NOISE = ASSET_DIR + "/M_Vol_BeamNoise"
MAT_SMOKE = ASSET_DIR + "/M_Vol_SmokeLow"
MI_SMOKE = ASSET_DIR + "/MI_Vol_SmokeTest_P03"
FLICKER_PARENT = "/Game/InfinityStage/Lighting/M_LF_StageFlicker"     # lighting_scores_apply.py:1114
FLICKER_PARAMS = ("Speed", "SpeedRatio", "Depth", "Phase", "Hardness", "OnBias")   # lighting_scores_apply.py:1115
FLICKER_STEADY = {"Speed": 0.0, "SpeedRatio": 1.0, "Depth": 0.0, "Phase": 0.0, "Hardness": 0.0, "OnBias": 0.5}
FLICKER_PIN = {"FSpeed": "Speed", "FRatio": "SpeedRatio", "FDepth": "Depth", "FPhase": "Phase",
               "FHard": "Hardness", "FOnBias": "OnBias"}

F_VS = "lighting.volumetric_scattering_intensity"
F_LF = "lighting.light_function_material"
F_LF_SCALE = "lighting.light_function_scale"
F_LF_DB = "lighting.light_function_disabled_brightness"
F_MEDIUM = "effect.medium_density"
WRITABLE = (F_VS, F_LF, F_LF_SCALE, F_LF_DB, F_MEDIUM)
FLOAT_TOL = 1.0e-5

DEFAULTS = {
    # 1. fog cut (P03-local only)
    "vs_scale": 0.5,
    "beam_vs_scale": 1.0,
    "beam_tokens": ["BEAM_R"],
    "vs_enabled_only": True,
    "medium_scale": 0.35,
    "lfv_extinction_scale": 0.35,
    "bbox_margin_cm": 1500.0,
    # 2. beam look: light function (the good run BEAMTEX-20261007-003747 GSB / GB values)
    "beam_look": True,
    "gobo": "slats",                    # "slats" (GSB, default) | "soft" (GB)
    "lf_conflict": "carry_flicker",     # "carry_flicker" | "replace" | "skip"
    "lf_disabled_brightness": 0.6,      # beam_texture_bench g_disabled_brightness
    "lf_scale": None,                   # None = leave the attachment's light_function_scale
    "g_floor": 0.2,
    "g_contrast": 3.5,
    "g_scale": 3.0,
    "g_blur_cells": 0.35,
    "g_slat_count": 3.0,
    "g_slat_soft": 0.2,
    "g_slat_threshold": 0.5,
    "g_slat_axis": "u",
    "g_pan_speed": 0.0,
    "g_disabled_brightness": 0.6,       # only so btb.validate_gobo_params sees a full set
    "g_lf_scale": None,
    "g_fade_distance_cm": None,
    "g_atlas_slot_resolution": None,
    # 2. beam look: noise volume (good run)
    "noise_boxes": True,
    "b_noise_cm": 60.0,
    "b_extinction_peak": 0.12,
    "b_noise_contrast": 3.0,
    "b_noise_floor": 0.05,
    "b_albedo": 0.9,
    "b_drift_cm_s": 0.0,
    "noise_start_cm": 60.0,
    "noise_end_cm": 1200.0,
    "b_box_margin_cm": 80.0,
    # 3. smoke test
    "smoke": True,
    "smoke_count": 3,
    "smoke_bays": None,                 # None = the first smoke_count beam bays in show order; else [4, 8, ...]
    "smoke_along_cm": 600.0,
    "smoke_size_cm": [400.0, 400.0, 120.0],
    "smoke_sink_cm": 10.0,
    "smoke_noise_cm": 45.0,
    "smoke_contrast": 4.5,
    "smoke_floor": 0.0,
    "smoke_peak": 0.25,
    "smoke_drift_cm_s": 25.0,
    "smoke_albedo": 0.85,
    "smoke_fade_pow": 1.5,
    "floor_trace_up_cm": 300.0,
    "floor_trace_down_cm": 600.0,
    "floor_max_dev_cm": 150.0,
    "smoke_floor_spread_max_cm": 30.0,
    "attach_to_passage": True,
}


class P03AtmosError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise P03AtmosError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def report_path(mode, run, folder=None):
    return os.path.join(folder or HERE, "p03_atmos_report_%s_%s.json" % (mode, run))


def backup_prefix(revert=False):
    return "PreP03Atmos%s-" % ("Revert" if revert else "")


# --------------------------------------------------------------------------
# Args + params (pure).
# --------------------------------------------------------------------------
def check_params(raw):
    p = dict(DEFAULTS)
    unknown = sorted(set(raw or {}) - set(DEFAULTS))
    require(not unknown, "PARAMS_UNKNOWN|%s" % ",".join(unknown))
    p.update(raw or {})
    for k in ("vs_scale", "beam_vs_scale", "medium_scale", "lfv_extinction_scale"):
        require(_num(p[k]) and 0.0 <= float(p[k]) <= 1.0, "PARAM_SCALE|%s=%r (0..1: this tool only REDUCES)" % (k, p[k]))
    require(isinstance(p["beam_tokens"], list) and p["beam_tokens"]
            and all(isinstance(t, str) and re.match(r"^[A-Z0-9_]+$", t) for t in p["beam_tokens"]),
            "PARAM_BEAM_TOKENS|%r" % (p["beam_tokens"],))
    require(p["gobo"] in ("slats", "soft"), "PARAM_GOBO|%r" % (p["gobo"],))
    require(p["lf_conflict"] in ("carry_flicker", "replace", "skip"), "PARAM_LF_CONFLICT|%r" % (p["lf_conflict"],))
    require(_num(p["lf_disabled_brightness"]) and 0.0 <= float(p["lf_disabled_brightness"]) <= 1.0,
            "PARAM_LF_DB|%r" % (p["lf_disabled_brightness"],))
    s = p["lf_scale"]
    require(s is None or (isinstance(s, list) and len(s) == 3 and all(_num(x) and float(x) > 0.0 for x in s)),
            "PARAM_LF_SCALE|%r" % (s,))
    bad = btb.validate_gobo_params(p)
    require(not bad, "PARAM_GOBO_VALUES|%s" % ";".join(bad))
    for k in ("b_noise_cm", "smoke_noise_cm"):
        require(_num(p[k]) and 1.0 <= float(p[k]) <= 5000.0, "PARAM|%s=%r" % (k, p[k]))
    for k in ("b_extinction_peak", "smoke_peak"):
        require(_num(p[k]) and 0.0 < float(p[k]) <= 2.0, "PARAM_PEAK|%s=%r (1/m)" % (k, p[k]))
    for k in ("b_noise_contrast", "smoke_contrast"):
        require(_num(p[k]) and 0.0 < float(p[k]) <= 50.0, "PARAM|%s=%r" % (k, p[k]))
    for k in ("b_noise_floor", "smoke_floor", "b_albedo", "smoke_albedo"):
        require(_num(p[k]) and 0.0 <= float(p[k]) <= 1.0, "PARAM|%s=%r" % (k, p[k]))
    require(_num(p["b_drift_cm_s"]) and abs(float(p["b_drift_cm_s"])) <= 500.0, "PARAM|b_drift_cm_s")
    require(_num(p["smoke_drift_cm_s"]) and 0.0 < abs(float(p["smoke_drift_cm_s"])) <= 500.0,
            "PARAM_SMOKE_DRIFT|%r (a smoke test drifts: must be non-zero)" % (p["smoke_drift_cm_s"],))
    require(_num(p["noise_start_cm"]) and _num(p["noise_end_cm"])
            and 0.0 <= float(p["noise_start_cm"]) < float(p["noise_end_cm"]) <= 5000.0, "PARAM_NOISE_SPAN")
    require(_num(p["b_box_margin_cm"]) and 0.0 <= float(p["b_box_margin_cm"]) <= 1000.0, "PARAM|b_box_margin_cm")
    require(isinstance(p["smoke_count"], int) and not isinstance(p["smoke_count"], bool)
            and 0 <= p["smoke_count"] <= 6, "PARAM_SMOKE_COUNT|%r" % (p["smoke_count"],))
    sb = p["smoke_bays"]
    require(sb is None or (isinstance(sb, list) and all(isinstance(b, int) and not isinstance(b, bool) for b in sb)
                           and len(set(sb)) == len(sb)), "PARAM_SMOKE_BAYS|%r" % (sb,))
    sz = p["smoke_size_cm"]
    require(isinstance(sz, list) and len(sz) == 3 and all(_num(x) and 10.0 <= float(x) <= 3000.0 for x in sz),
            "PARAM_SMOKE_SIZE|%r" % (sz,))
    for k in ("smoke_along_cm", "smoke_sink_cm", "floor_trace_up_cm", "floor_trace_down_cm", "floor_max_dev_cm",
              "smoke_floor_spread_max_cm", "bbox_margin_cm"):
        require(_num(p[k]) and 0.0 <= float(p[k]) <= 20000.0, "PARAM|%s=%r" % (k, p[k]))
    require(_num(p["smoke_fade_pow"]) and 0.05 <= float(p["smoke_fade_pow"]) <= 8.0, "PARAM|smoke_fade_pow")
    for k in ("vs_enabled_only", "beam_look", "noise_boxes", "smoke", "attach_to_passage"):
        require(isinstance(p[k], bool), "PARAM_BOOL|%s=%r" % (k, p[k]))
    return p


def check_args(args):
    args = dict(args or {})
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(args.get("confirm") == "%s %s" % (mode, CONFIRM_TOKEN),
                "CONFIRM_MISSING|mode=%s|need='%s %s'" % (mode, mode, CONFIRM_TOKEN))
    expected = dict(args.get("expected") or {})
    require(set(expected) <= {"vs", "lf", "medium", "lfv", "noise", "smoke"} and all(
        isinstance(v, int) and not isinstance(v, bool) for v in expected.values()), "EXPECTED_INVALID|%r" % expected)
    for k in ("reuse_existing_assets", "remove_assets"):
        require(isinstance(args.get(k, False), bool), "ARG_BOOL|%s" % k)
    return {"mode": mode, "confirm": args.get("confirm"), "params": check_params(args.get("params")),
            "ack_records": list(args.get("ack_records", []) or []),
            "allow_dirty": list(args.get("allow_dirty", []) or []), "expected": expected,
            "reuse_existing_assets": bool(args.get("reuse_existing_assets", False)),
            "remove_assets": bool(args.get("remove_assets", False))}


# --------------------------------------------------------------------------
# Material code (pure). The bench strings are IMPORTED so the graphs are the bench's; the two derived codes are
# built by replacing the final return line, which the harness asserts.
# --------------------------------------------------------------------------
FLICKER_HLSL = r"""
float fs = 0.5 + 0.25 * sin(6.2831853 * (FSpeed * T + FPhase)) + 0.25 * sin(6.2831853 * (FSpeed * FRatio * T + 1.7 * FPhase));
float fw = 0.5 * (1.0 - FHard) + 0.002;
float fx = saturate((fs - (FOnBias - fw)) / (2.0 * fw));
float fl = 1.0 - FDepth * (1.0 - fx * fx * (3.0 - 2.0 * fx));
"""
GOBO_RETURN = "return lerp(FloorV, 1.0, d);"
NOISE_RETURN = "return Peak * lerp(FloorFrac, 1.0, d);"
SMOKE_TAIL = r"""
float hgt = saturate((WP.z - FloorZ) / max(HeightCm, 1.0));
return Peak * lerp(FloorFrac, 1.0, d) * pow(1.0 - hgt, max(FadePow, 0.01));
"""


def _replace_return(code, old, new):
    body = code.rstrip()
    require(body.endswith(old) and body.count(old) == 1, "CODE_RETURN_SHAPE|%s" % old)
    return body[:-len(old)] + new


def with_flicker(code):
    """Gobo code x the M_LF_StageFlicker term (rebuild_flicker_master.py:16-39, lighting_scores_apply.lf_level)."""
    return _replace_return(code, GOBO_RETURN, "float g = lerp(FloorV, 1.0, d);\n" + FLICKER_HLSL + "return g * fl;\n")


def smoke_code():
    return _replace_return(btb.CODE_NOISE3, NOISE_RETURN, SMOKE_TAIL)


def flicker_level(t, params):
    """Python mirror of FLICKER_HLSL (= lighting_scores_apply.lf_level)."""
    sp, ra, de, ph, ha, ob = [float(params[n]) for n in FLICKER_PARAMS]
    s = 0.5 + 0.25 * math.sin(6.2831853 * (sp * t + ph)) + 0.25 * math.sin(6.2831853 * (sp * ra * t + 1.7 * ph))
    w = 0.5 * (1.0 - ha) + 0.002
    x = min(1.0, max(0.0, (s - (ob - w)) / (2.0 * w)))
    return 1.0 - de * (1.0 - x * x * (3.0 - 2.0 * x))


def smoke_reference(wp, t, sp):
    """Python mirror of smoke_code(): btb.noise3_reference x the height fade. sp: smoke material params."""
    mapped = {"b_drift_cm_s": sp["Drift"], "b_noise_cm": sp["NoiseCm"], "b_noise_contrast": sp["Contrast"],
              "b_extinction_peak": sp["Peak"], "b_noise_floor": sp["FloorFrac"]}
    hgt = min(1.0, max(0.0, (float(wp[2]) - float(sp["FloorZ"])) / max(float(sp["HeightCm"]), 1.0)))
    return btb.noise3_reference(wp, t, mapped) * (1.0 - hgt) ** max(float(sp["FadePow"]), 0.01)


def graph_spec(kind, p):
    """-> {"code", "inputs", "params": {pin: (scalar_name, value)}, "domain"}. Pins wired from TextureCoordinate /
    WorldPosition and Time are not in params."""
    if kind in ("gobo_slats", "gobo_slats_flicker"):
        code, inputs = btb.CODE_GOBO_SLATS, list(btb.GOBO_SLATS_INPUTS)
        params = {pin: (pin, float(p[k])) for pin, k in btb.GOBO_SLATS_PARAMS.items()}
        params["Axis"] = ("Axis", 1.0 if p["g_slat_axis"] == "v" else 0.0)
    elif kind in ("gobo_soft", "gobo_soft_flicker"):
        code, inputs = btb.CODE_GOBO_SOFT, list(btb.GOBO_SOFT_INPUTS)
        params = {pin: (pin, float(p[k])) for pin, k in btb.GOBO_SOFT_PARAMS.items()}
    elif kind == "noise":
        return {"code": btb.CODE_NOISE3, "inputs": list(btb.NOISE_INPUTS), "domain": "VOLUME",
                "params": {pin: (pin, float(p[k])) for pin, k in btb.NOISE_PARAMS.items()},
                "albedo": float(p["b_albedo"])}
    elif kind == "smoke":
        sp = smoke_material_params(p, 0.0)
        return {"code": smoke_code(), "inputs": list(btb.NOISE_INPUTS) + ["FloorZ", "HeightCm", "FadePow"],
                "domain": "VOLUME", "params": {pin: (pin, float(v)) for pin, v in sp.items()},
                "albedo": float(p["smoke_albedo"])}
    else:
        raise P03AtmosError("GRAPH_KIND|%s" % kind)
    if kind.endswith("_flicker"):
        code = with_flicker(code)
        inputs = inputs + list(FLICKER_PIN)
        for pin, name in FLICKER_PIN.items():
            params[pin] = (name, float(FLICKER_STEADY[name]))
    return {"code": code, "inputs": inputs, "domain": "LIGHT_FUNCTION", "params": params}


def smoke_material_params(p, floor_z):
    return {"NoiseCm": float(p["smoke_noise_cm"]), "Contrast": float(p["smoke_contrast"]),
            "FloorFrac": float(p["smoke_floor"]), "Peak": float(p["smoke_peak"]), "Drift": float(p["smoke_drift_cm_s"]),
            "FloorZ": float(floor_z), "HeightCm": float(p["smoke_size_cm"][2]) - float(p["smoke_sink_cm"]),
            "FadePow": float(p["smoke_fade_pow"])}


def obj_path(asset_path):
    return btb.obj_path(asset_path)


def asset_of(object_path):
    return None if object_path is None else str(object_path).split(".", 1)[0]


# --------------------------------------------------------------------------
# Show plan (pure): which attachment fields change.
# --------------------------------------------------------------------------
def beam_regex(p):
    return re.compile(r"^%s SCORE B(\d{2}) \S+ (%s)$" % (PASSAGE, "|".join(re.escape(t) for t in p["beam_tokens"])))


def field_target(cue, row, index, path, before, after, kind):
    return {"cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue["show_index"],
            "attachment_guid": row["guid"], "attachment_label": row["label"], "attachment_index": index,
            "path": path, "before": before, "after": after, "kind": kind}


def passage_cues(plain):
    by = {c["guid"]: c for c in plain["cues"]}
    missing = [g for g in plain["bay_guids"] if g not in by]
    require(not missing, "BAY_GUID_UNRESOLVED|%s" % missing)
    cues = sorted((by[g] for g in plain["bay_guids"]), key=lambda c: c["show_index"])
    wrong = [c["label"] for c in cues if not str(c["label"]).startswith(PASSAGE + " ")]
    require(not wrong, "BAY_NOT_%s|%s" % (PASSAGE, wrong))
    return cues


def beam_rows(plain, p):
    rx = beam_regex(p)
    out = []
    for cue in passage_cues(plain):
        for index, row in enumerate(cue["attachments"]):
            m = rx.match(str(row["label"]))
            if m and _enum_name(row["kind"]) == "LIGHT":
                out.append({"cue": cue, "row": row, "index": index, "bay": int(m.group(1)), "token": m.group(2)})
    return out


def plan_fog(plain, p):
    """1a + 1b: VS on enabled lights (beams x beam_vs_scale), effect medium density."""
    rx = beam_regex(p)
    targets, untouched = [], []
    for cue in passage_cues(plain):
        for index, row in enumerate(cue["attachments"]):
            kind = _enum_name(row["kind"])
            if kind == "LIGHT":
                vs = float(row["lighting"]["volumetric_scattering_intensity"])
                beam = bool(rx.match(str(row["label"])))
                k = float(p["beam_vs_scale"] if beam else p["vs_scale"])
                why = None
                if p["vs_enabled_only"] and not bool(row.get("enabled", True)):
                    why = "DISABLED"
                elif vs == 0.0:
                    why = "ZERO"
                elif k == 1.0:
                    why = "BEAM_KEPT" if beam else "SCALE_ONE"
                if why:
                    untouched.append({"label": row["label"], "guid": row["guid"], "why": why, "vs": vs, "beam": beam})
                    continue
                targets.append(dict(field_target(cue, row, index, F_VS, vs, vs * k, "vs"), beam=beam))
            elif kind == "EFFECT":
                eff = row.get("effect") or {}
                dens = float(eff.get("medium_density", 0.0))
                if bool(eff.get("feeds_local_medium")) and dens > 0.0 and float(p["medium_scale"]) != 1.0:
                    targets.append(field_target(cue, row, index, F_MEDIUM, dens, dens * float(p["medium_scale"]),
                                                "medium"))
                else:
                    untouched.append({"label": row["label"], "guid": row["guid"], "why": "EFFECT_NO_MEDIUM",
                                      "medium_density": dens})
    return targets, untouched


def lf_materials(p):
    if p["gobo"] == "slats":
        return MAT_SLATS, MAT_SLATS_FLK, "Slats"
    return MAT_GOBO, MAT_GOBO_FLK, "Gobo"


def produced_lf_paths(p):
    base, flk, word = lf_materials(p)
    return {obj_path(base)}, ASSET_DIR + "/MI_LF_Soft%s_" % word


def flicker_profile_name(lf_object_path):
    name = asset_of(lf_object_path).rsplit("/", 1)[-1]
    m = re.match(r"^MI_LF_Flicker_([A-Za-z0-9]+)$", name)
    return m.group(1) if m else None


def plan_lf(beams, flicker_live, p):
    """2: the beams' light function. flicker_live: {lf object path: {"parent": asset id, "params": {...}} | {"error"}}
    read LIVE. -> (targets, mi_specs {mi asset: {"parent", "params"}}, rows, warnings)."""
    base, flk, word = lf_materials(p)
    produced, mi_prefix = produced_lf_paths(p)
    targets, mi_specs, rows, warnings = [], {}, [], []
    for b in beams:
        cue, row, index = b["cue"], b["row"], b["index"]
        lit = row["lighting"]
        cur = lit.get("light_function_material")
        info = {"label": row["label"], "bay": b["bay"], "current_lf": cur}
        new = None
        if cur is None:
            new, info["how"] = obj_path(base), "NEW"
        elif cur in produced or asset_of(cur).startswith(mi_prefix):
            info["how"] = "ALREADY_BEAMLOOK"
        elif p["lf_conflict"] == "skip":
            info["how"] = "SKIPPED_HAS_LF"
            warnings.append("LF_SKIPPED|%s|has=%s" % (row["label"], cur))
        elif p["lf_conflict"] == "replace":
            new, info["how"] = obj_path(base), "REPLACED_FLICKER_DROPPED"
            warnings.append("LF_FLICKER_DROPPED|%s|was=%s" % (row["label"], cur))
        else:
            live = flicker_live.get(cur) or {"error": "not read"}
            profile = flicker_profile_name(cur)
            if "error" in live or live.get("parent") != FLICKER_PARENT or profile is None:
                info["how"] = "SKIPPED_LF_NOT_STAGEFLICKER"
                warnings.append("LF_NOT_STAGEFLICKER|%s|has=%s|live=%s" % (row["label"], cur, _canonical(live)))
            else:
                params = {k: float(live["params"][k]) for k in FLICKER_PARAMS}
                mi = "%s%s" % (mi_prefix, profile)
                spec = {"parent": flk, "params": params, "source": asset_of(cur)}
                if mi in mi_specs:
                    require(all(abs(mi_specs[mi]["params"][k] - params[k]) <= 1.0e-6 for k in FLICKER_PARAMS),
                            "FLICKER_PROFILE_CONFLICT|%s|%s" % (mi, row["label"]))
                else:
                    mi_specs[mi] = spec
                new, info["how"], info["carried"] = obj_path(mi), "CARRY_FLICKER", profile
        info["new_lf"] = new
        rows.append(info)
        if new is None:
            continue
        targets.append(dict(field_target(cue, row, index, F_LF, cur, new, "lf"), bay=b["bay"]))
        db = float(lit.get("light_function_disabled_brightness", 0.0))
        if abs(db - float(p["lf_disabled_brightness"])) > FLOAT_TOL:
            targets.append(dict(field_target(cue, row, index, F_LF_DB, db, float(p["lf_disabled_brightness"]), "lf"),
                                bay=b["bay"]))
        if p["lf_scale"] is not None:
            sc = [float(x) for x in lit.get("light_function_scale", [1.0, 1.0, 1.0])]
            want = [float(x) for x in p["lf_scale"]]
            if not same_value(sc, want):
                targets.append(dict(field_target(cue, row, index, F_LF_SCALE, sc, want, "lf"), bay=b["bay"]))
    return targets, mi_specs, rows, warnings


def asset_plan(p, mi_specs, need_flicker_parent, floor_z=None):
    """Ordered create list: materials before the instances that need them."""
    out = []
    if p["beam_look"]:
        out.append({"path": MAT_SLATS, "type": "material", "graph": "gobo_slats"})
        out.append({"path": MAT_GOBO, "type": "material", "graph": "gobo_soft"})
        if need_flicker_parent:
            _base, flk, _w = lf_materials(p)
            out.append({"path": flk, "type": "material",
                        "graph": "gobo_slats_flicker" if p["gobo"] == "slats" else "gobo_soft_flicker"})
        for mi, spec in sorted(mi_specs.items()):
            out.append({"path": mi, "type": "mi", "parent": spec["parent"], "params": dict(spec["params"])})
    if p["noise_boxes"]:
        out.append({"path": MAT_NOISE, "type": "material", "graph": "noise"})
    if p["smoke"] and int(p["smoke_count"]) > 0:
        out.append({"path": MAT_SMOKE, "type": "material", "graph": "smoke"})
        out.append({"path": MI_SMOKE, "type": "mi", "parent": MAT_SMOKE,
                    "params": smoke_material_params(p, 0.0 if floor_z is None else floor_z)})
    paths = [a["path"] for a in out]
    require(len(set(paths)) == len(paths), "ASSET_PLAN_DUPLICATE")
    require(all(x.startswith(ASSET_DIR + "/") for x in paths), "ASSET_OUTSIDE_DIR")
    made = set()
    for a in out:
        if a["type"] == "mi":
            require(a["parent"] in made, "ASSET_ORDER|%s before %s" % (a["path"], a["parent"]))
        made.add(a["path"])
    return out


# --------------------------------------------------------------------------
# Values, rows model, scope, drift (pure).
# --------------------------------------------------------------------------
def same_value(a, b, tol=FLOAT_TOL):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same_value(x, y, tol) for x, y in zip(a, b))
    if _num(a) and _num(b):
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))
    return a == b


def get_path(row, path):
    cur = row
    for part in path.split("."):
        cur = cur[part]
    return cur


def set_path(row, path, value):
    parts = path.split(".")
    cur = row
    for part in parts[:-1]:
        cur = cur[part]
    require(parts[-1] in cur, "FIELD_MISSING|%s" % path)
    cur[parts[-1]] = copy.deepcopy(value)


def check_targets(targets):
    keys = [(t["attachment_guid"], t["path"]) for t in targets]
    require(len(set(keys)) == len(keys), "TARGET_FIELD_DUPLICATE")
    require(all(t["path"] in WRITABLE for t in targets), "TARGET_FIELD_NOT_WRITABLE")
    return keys


def apply_rows(all_rows, targets, side):
    """{cue_guid: rows} with each target's field set to its side value."""
    require(side in ("before", "after"), "SIDE_INVALID|%s" % side)
    out = copy.deepcopy(all_rows)
    for t in targets:
        hits = [r for r in out.get(t["cue_guid"], []) if r["guid"] == t["attachment_guid"]]
        require(len(hits) == 1, "TARGET_ROW_RESOLVE|%s" % t["attachment_guid"])
        set_path(hits[0], t["path"], t[side])
    return out


def scope_problems(base_all, live_all, targets, side, diff=S.state_differences):
    """[] iff live == base with exactly the targets' fields at their side value (floats within FLOAT_TOL)."""
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    want_all = apply_rows(base_all, targets, side)
    by_row = {}
    for t in targets:
        by_row.setdefault((t["cue_guid"], t["attachment_guid"]), []).append(t)
    problems = []
    for cue_guid in sorted(base_all):
        want, got = want_all[cue_guid], live_all[cue_guid]
        if [r["guid"] for r in want] != [r["guid"] for r in got]:
            problems.append({"cue": cue_guid, "problem": "ROW_SET_OR_ORDER_CHANGED"})
            continue
        for w, g in zip(want, got):
            w2, g2 = copy.deepcopy(w), copy.deepcopy(g)
            for t in by_row.get((cue_guid, w["guid"]), []):
                if not same_value(get_path(g2, t["path"]), get_path(w2, t["path"])):
                    problems.append({"cue": cue_guid, "guid": w["guid"], "path": t["path"],
                                     "want": get_path(w2, t["path"]), "got": get_path(g2, t["path"])})
                set_path(g2, t["path"], None)
                set_path(w2, t["path"], None)
            d = diff(w2, g2)
            if d:
                problems.append({"cue": cue_guid, "guid": w["guid"], "label": w["label"], "differences": d})
    return problems


def field_drifts(all_rows, targets, side="after"):
    """Every target field whose live value != its side value (REVERT: side after)."""
    out = []
    for t in targets:
        hits = [r for r in all_rows.get(t["cue_guid"], []) if r["guid"] == t["attachment_guid"]]
        if len(hits) != 1:
            out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "path": "<row>",
                        "live": "count=%d" % len(hits)})
            continue
        live = get_path(hits[0], t["path"])
        if not same_value(live, t[side]):
            out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "path": t["path"],
                        "record": t[side], "live": live})
    return out


# --------------------------------------------------------------------------
# Level plan (pure): LFVs, footprint, boxes.
# --------------------------------------------------------------------------
def footprint(points, margin):
    require(points, "FOOTPRINT_EMPTY")
    xs, ys, zs = [p[0] for p in points], [p[1] for p in points], [p[2] for p in points]
    m = float(margin)
    return {"min": [min(xs) - m, min(ys) - m, min(zs) - m - 2000.0],
            "max": [max(xs) + m, max(ys) + m, max(zs) + m + 2000.0]}


def inside(box, pt):
    return all(box["min"][i] <= float(pt[i]) <= box["max"][i] for i in range(3))


def plan_lfv(lfvs, box, p):
    """1c: LocalFogVolume actors with their centre inside P03's footprint. ZZ_ bench actors are never targets."""
    k = float(p["lfv_extinction_scale"])
    targets, outside = [], []
    for f in sorted(lfvs, key=lambda f: f["id"]):
        if str(f["label"]).startswith("ZZ_") or not inside(box, f["loc"]):
            outside.append({"label": f["label"], "why": "ZZ_BENCH" if str(f["label"]).startswith("ZZ_") else "OUTSIDE"})
            continue
        for field in ("radial_fog_extinction", "height_fog_extinction"):
            v = float(f[field])
            if v > 0.0 and k != 1.0:
                targets.append({"id": f["id"], "label": f["label"], "field": field, "before": v, "after": v * k})
    return targets, outside


def lfv_drifts(live, targets, side="after"):
    """live: {(id, field): value}."""
    out = []
    for t in targets:
        v = live.get((t["id"], t["field"]))
        if v is None or not same_value(v, t[side]):
            out.append({"id": t["id"], "label": t["label"], "field": t["field"], "record": t[side], "live": v})
    return out


def heading_unit(u):
    h = (float(u[0]), float(u[1]), 0.0)
    n = math.hypot(h[0], h[1])
    require(n > 1.0e-6, "BEAM_VERTICAL")
    return (h[0] / n, h[1] / n, 0.0)


def noise_box_spec(beam, p):
    """2: beam-aligned box over [noise_start_cm, min(noise_end_cm, attenuation)] (btb.noisebox_spec with a fixed span)."""
    u = btb.beam_axis(beam["rotation"])
    s0 = float(p["noise_start_cm"])
    s1 = min(float(p["noise_end_cm"]), float(beam["attenuation_cm"]))
    require(s1 > s0 + 1.0, "NOISE_SPAN_EMPTY|%s" % beam["label"])
    r1 = s1 * math.tan(math.radians(float(beam["outer_cone_deg"])))
    side = 2.0 * (r1 + float(p["b_box_margin_cm"]))
    mid = btb.vadd(beam["location"], btb.vmul(u, 0.5 * (s0 + s1)))
    return {"label": "%s BeamLook Noise B%02d" % (PASSAGE, int(beam["bay"])), "kind": "noise",
            "loc": [round(x, 3) for x in mid], "rot": btb.rot_from_axis(u),
            "scale": [(s1 - s0) / 100.0, side / 100.0, side / 100.0], "material": MAT_NOISE,
            "tags": [BEAMLOOK_TAG, ACTOR_TAG], "beam": beam["label"], "s0": s0, "s1": s1, "side_cm": side}


def choose_floor(trace_z, station_z, p):
    """(floor_z, source). Trace hit wins when it is within floor_max_dev_cm of the station (panel base) z."""
    dev = float(p["floor_max_dev_cm"])
    if trace_z is not None and station_z is not None and abs(float(trace_z) - float(station_z)) <= dev:
        return float(trace_z), "trace"
    if station_z is not None:
        return float(station_z), "station_fallback" if trace_z is None else "station_trace_rejected"
    require(trace_z is not None, "FLOOR_UNKNOWN")
    return float(trace_z), "trace_no_station"


def smoke_point(beam, p):
    u = btb.beam_axis(beam["rotation"])
    pt = btb.vadd(beam["location"], btb.vmul(u, float(p["smoke_along_cm"])))
    return [pt[0], pt[1]], heading_unit(u)


def smoke_box_spec(n, beam, floor_z, p):
    xy, h = smoke_point(beam, p)
    L, W, H = [float(x) for x in p["smoke_size_cm"]]
    z = float(floor_z) - float(p["smoke_sink_cm"]) + H / 2.0
    return {"label": "%s Smoke Test %d" % (PASSAGE, n), "kind": "smoke", "loc": [xy[0], xy[1], z],
            "rot": {"roll": 0.0, "pitch": 0.0, "yaw": math.degrees(math.atan2(h[1], h[0]))},
            "scale": [L / 100.0, W / 100.0, H / 100.0], "material": MI_SMOKE, "tags": [SMOKE_TAG, ACTOR_TAG],
            "beam": beam["label"], "floor_z": float(floor_z), "bottom_z": z - H / 2.0, "top_z": z + H / 2.0}


def smoke_beams(beams_world, p):
    beams = sorted(beams_world, key=lambda b: (b["show_index"], b["bay"]))
    if p["smoke_bays"] is not None:
        want = [int(b) for b in p["smoke_bays"]]
        have = {b["bay"] for b in beams}
        missing = [b for b in want if b not in have]
        require(not missing, "SMOKE_BAY_HAS_NO_BEAM|%s" % missing)
        beams = [b for b in beams if b["bay"] in want]
    return beams[:int(p["smoke_count"])]


def smoke_floor(floors, p):
    """One FloorZ for the shared smoke instance: the median, every box within smoke_floor_spread_max_cm of it."""
    require(floors, "SMOKE_NO_FLOOR")
    s = sorted(float(f) for f in floors)
    med = s[len(s) // 2] if len(s) % 2 else 0.5 * (s[len(s) // 2 - 1] + s[len(s) // 2])
    spread = max(abs(f - med) for f in s)
    require(spread <= float(p["smoke_floor_spread_max_cm"]), "SMOKE_FLOOR_SPREAD|%.1f cm" % spread)
    return med


def check_inside(specs, box):
    """Frame-trap guard (memory puss-level-saved-landed-frame-trap): every box centre inside P03's footprint."""
    bad = [s["label"] for s in specs if not inside(box, s["loc"])]
    require(not bad, "SPAWN_OUTSIDE_P03|%s" % bad)


def plan_spawns(beams_world, floors, box, p):
    """-> (noise specs, smoke specs, smoke floor z)."""
    noise = [noise_box_spec(b, p) for b in beams_world] if p["noise_boxes"] and p["beam_look"] else []
    smoke, fz = [], None
    if p["smoke"] and int(p["smoke_count"]) > 0:
        chosen = smoke_beams(beams_world, p)
        fz = smoke_floor([floors[b["label"]][0] for b in chosen], p)
        smoke = [smoke_box_spec(i + 1, b, fz, p) for i, b in enumerate(chosen)]
    labels = [s["label"] for s in noise + smoke]
    require(len(set(labels)) == len(labels), "SPAWN_LABEL_DUPLICATE")
    check_inside(noise + smoke, box)
    return noise, smoke, fz


def spawn_drifts(live, specs, tol_cm=1.0):
    """live: {label: {"loc": [...], "count": n}}. A moved / missing / duplicated spawned actor is drift."""
    out = []
    for s in specs:
        row = live.get(s["label"])
        if row is None or row.get("count") != 1:
            out.append({"label": s["label"], "problem": "count=%s" % (None if row is None else row.get("count"))})
        elif math.dist(row["loc"], s["loc"]) > tol_cm:
            out.append({"label": s["label"], "problem": "moved", "record": s["loc"], "live": row["loc"]})
    return out


def check_expected(expected, counts):
    bad = {k: (v, counts.get(k)) for k, v in expected.items() if counts.get(k) != v}
    require(not bad, "EXPECTED_COUNTS|%s" % _canonical(bad))


def fog_source_table(live):
    """The candidates Gary's 'ridiculously foggy' can come from, each with its evidence and this tool's action."""
    return [
        {"source": "ExponentialHeightFog (global, Celestial rig tag InfinityStage.CelestialFog)", "scope": "GLOBAL",
         "action": "report only (never written)", "live": live.get("height_fogs"),
         "evidence": "InfinityStageCelestialRig.h:51,66; PIE 6 Oct density 0.022 / second 0.04484 / dist 0.55 "
                     "(BeamTextureBench/BEAMTEX-20261007-003747 originals)"},
        {"source": "P03 Show lights' volumetric_scattering_intensity", "scope": "P03",
         "action": "x vs_scale on enabled non-beam lights; beams x beam_vs_scale", "live": live.get("vs_summary"),
         "evidence": "InfinityStageTypes.h:224; PassageActor.cpp:472; lighting_scores_record_P03.json after_rows"},
        {"source": "P03 Effect attachments feeding a local medium (Haze/Smoke pots)", "scope": "P03",
         "action": "effect.medium_density x medium_scale", "live": live.get("medium_summary"),
         "evidence": "InfinityStageEffectSource.cpp:270-277; record 6 Oct: no EFFECT rows in P03"},
        {"source": "Level LocalFogVolume actors inside P03's footprint", "scope": "P03",
         "action": "radial/height extinction x lfv_extinction_scale", "live": live.get("lfv_summary"),
         "evidence": "LocalFogVolumeComponent setters (beam_texture_bench PIE_API); none placed by any saving tool "
                     "found in Saved/ (look_bench, p02_fog_bench, beam bench pools are ZZ_ and unsaved)"},
        {"source": "Non-Show lights in P03 (Structure fixtures etc.)", "scope": "P03",
         "action": "report only (owned by the Structure / other tools)", "live": live.get("other_lights"),
         "evidence": "InfinityStageStructureActor.cpp:2430 (tube light functions)"},
        {"source": "Renderer: volumetric fog cvars + light-function atlas", "scope": "GLOBAL",
         "action": "report only", "live": live.get("cvars"),
         "evidence": "beam_texture_bench.py:59-67, :83-99"},
    ]


# --------------------------------------------------------------------------
# Module loading (rig_lamp_drop / p01_rig_pattern pattern; p01_rig_pattern.py must not run its main()).
# --------------------------------------------------------------------------
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
            and node.test.left.id == "unreal" and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value is None
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call)
            and _dotted(node.body[0].value.func) == "main")


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1]) and sum(1 for n in tree.body if _is_main_guard(n)) == 1,
            "MAIN_GUARD_SHAPE|" + path)
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


def load_rig_pattern():
    rp = load_without_main(RIG_PATTERN_PATH, "_p01_rig_pattern_for_p03_atmos")
    for name in ("load_modules", "passage_config", "load_aims", "_runtime_plain", "_all_rows", "_ctx_facts",
                 "check_context", "_materialize"):
        require(callable(getattr(rp, name, None)), "RIG_PATTERN_API_DRIFT|" + name)
    return rp


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a module global.
# --------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rot(r):
    return {"roll": float(r.roll), "pitch": float(r.pitch), "yaw": float(r.yaw)}


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _level_actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _tag_strings(actor):
    return [str(t) for t in actor.get_editor_property("tags")]


def _identity(actor):
    """(cue_guid, attachment_guid) from the materialization identity tag, else None."""
    for t in _tag_strings(actor):
        if t.startswith(ATTACHMENT_TAG_PREFIX):
            cue, att = t[len(ATTACHMENT_TAG_PREFIX):].split("|", 1)
            return cue.upper(), att.upper()
    return None


def _passage_actor(cfg):
    hits = [a for a in _level_actors() if a.get_class().get_name() == "InfinityStagePassageActor"
            and a.get_actor_label().startswith(cfg["actor_prefix"])]
    require(len(hits) == 1, "PASSAGE_ACTOR_COUNT|%s|%d" % (cfg["actor_prefix"], len(hits)))
    return hits[0]


def _station_z(passage, tool):
    """{cue_guid: mean base z of the cue's materialized panels} (p03_nofog_capture.py:24-35)."""
    acc = {}
    for ref in passage.get_editor_property("materialized_panels"):
        g = tool._guid_text(ref.get_editor_property("cue_guid"))
        acc.setdefault(g, []).append(float(ref.get_editor_property("base_world_transform").translation.z))
    return {g: sum(v) / len(v) for g, v in acc.items() if v}


def _materialized(bay_guids):
    """{attachment_guid: actor} for actors materialized from P03's cues."""
    want = set(bay_guids)
    out = {}
    for actor in _level_actors():
        ident = _identity(actor)
        if ident and ident[0] in want:
            require(ident[1] not in out, "DUPLICATE_MATERIALIZED|%s" % ident[1])
            out[ident[1]] = actor
    return out


def _light_comp(actor):
    comps = list(actor.get_components_by_class(unreal.LocalLightComponent))
    return comps[0] if len(comps) == 1 else None


def _light_live(actor):
    comp = _light_comp(actor)
    if comp is None:
        return None
    m = comp.get_editor_property("light_function_material")
    is_spot = isinstance(comp, unreal.SpotLightComponent)
    return {"location": _vec(comp.get_world_location()), "rotation": _rot(comp.get_world_rotation()),
            "outer_cone_deg": float(comp.get_editor_property("outer_cone_angle")) if is_spot else 80.0,
            "attenuation_cm": float(comp.get_editor_property("attenuation_radius")),
            "vs": float(comp.get_editor_property("volumetric_scattering_intensity")),
            "lf": m.get_path_name() if m else None, "visible": bool(comp.is_visible()), "spot": is_spot}


def _flicker_live(paths):
    mel = unreal.MaterialEditingLibrary
    out = {}
    for path in sorted(set(x for x in paths if x)):
        try:
            mi = unreal.load_asset(asset_of(path))
            parent = mi.get_editor_property("parent") if isinstance(mi, unreal.MaterialInstance) else None
            out[path] = {"parent": asset_of(parent.get_path_name()) if parent else None,
                         "params": {k: float(mel.get_material_instance_scalar_parameter_value(mi, k))
                                    for k in FLICKER_PARAMS}}
        except Exception as error:  # noqa: BLE001 - reported per material, judged by plan_lf
            out[path] = {"error": "%s: %s" % (type(error).__name__, error)}
    return out


def _lfvs():
    rows = []
    for actor in _level_actors():
        if not isinstance(actor, unreal.LocalFogVolume):
            continue
        comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        rows.append({"id": actor.get_path_name(), "label": actor.get_actor_label(), "loc": _vec(actor.get_actor_location()),
                     "scale": _vec(actor.get_actor_scale3d()), "tags": _tag_strings(actor),
                     "radial_fog_extinction": float(comp.get_editor_property("radial_fog_extinction")),
                     "height_fog_extinction": float(comp.get_editor_property("height_fog_extinction"))})
    return rows


def _lfv_comp(actor_id):
    actor = unreal.find_object(None, actor_id)
    require(actor is not None, "LFV_UNRESOLVED|%s" % actor_id)
    return actor.get_component_by_class(unreal.LocalFogVolumeComponent)


def _lfv_live(targets):
    return {(t["id"], t["field"]): float(_lfv_comp(t["id"]).get_editor_property(t["field"])) for t in targets}


def _lfv_write(targets, side):
    for t in targets:
        comp = _lfv_comp(t["id"])
        if t["field"] == "radial_fog_extinction":
            comp.set_radial_fog_extinction(float(t[side]))        # LocalFogVolumeComponent.h:55-64 (bench PIE_API)
        else:
            comp.set_height_fog_extinction(float(t[side]))


def _height_fogs():
    rows = []
    for actor in _level_actors():
        if not isinstance(actor, unreal.ExponentialHeightFog):
            continue
        c = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
        row = {"label": actor.get_actor_label(), "tags": _tag_strings(actor)}
        for f in ("fog_density", "volumetric_fog", "volumetric_fog_scattering_distribution",
                  "volumetric_fog_extinction_scale", "fog_height_falloff"):
            try:
                v = c.get_editor_property(f)
                row[f] = bool(v) if isinstance(v, bool) else float(v)
            except Exception as error:  # noqa: BLE001
                row[f] = "unreadable: %s" % error
        try:
            row["second_fog_density"] = float(c.get_editor_property("second_fog_data").get_editor_property("fog_density"))
        except Exception as error:  # noqa: BLE001
            row["second_fog_density"] = "unreadable: %s" % error
        rows.append(row)
    return rows


def _effect_sources(box):
    rows = []
    cls = getattr(unreal, "InfinityStageEffectSource", None)
    for actor in _level_actors():
        if cls is None or not isinstance(actor, cls) or not inside(box, _vec(actor.get_actor_location())):
            continue
        comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        rows.append({"label": actor.get_actor_label(), "identity": _identity(actor),
                     "medium_radial": float(comp.get_editor_property("radial_fog_extinction")) if comp else None})
    return rows


def _other_lights(box, materialized_ids):
    rows = []
    for actor in _level_actors():
        if actor.get_path_name() in materialized_ids:
            continue
        for comp in actor.get_components_by_class(unreal.LightComponent):
            loc = _vec(comp.get_world_location())
            if not inside(box, loc):
                continue
            rows.append({"actor": actor.get_actor_label(), "component": comp.get_name(),
                         "class": comp.get_class().get_name(), "visible": bool(comp.is_visible()),
                         "intensity": float(comp.get_editor_property("intensity")),
                         "vs": float(comp.get_editor_property("volumetric_scattering_intensity"))})
    rows.sort(key=lambda r: (-r["vs"] * (1.0 if r["visible"] else 0.0), r["actor"]))
    return rows


def _cvars():
    out = {}
    for name in ("r.LightFunctionAtlas", "r.VolumetricFog.UsesLightFunctionAtlas", "r.VolumetricFog.LightFunction",
                 "r.LightFunctionQuality", "r.VolumetricFog", "r.VolumetricFog.GridPixelSize",
                 "r.VolumetricFog.GridSizeZ", "r.Substrate"):
        try:
            out[name] = float(unreal.SystemLibrary.get_console_variable_float_value(name))
        except Exception:  # noqa: BLE001
            out[name] = None
    return out


def _trace_floor(xy, station_z, p):
    world = _world()
    start = unreal.Vector(float(xy[0]), float(xy[1]), float(station_z) + float(p["floor_trace_up_cm"]))
    end = unreal.Vector(float(xy[0]), float(xy[1]), float(station_z) - float(p["floor_trace_down_cm"]))
    res = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True,
                                                 [], unreal.DrawDebugTrace.NONE, True)
    hit = res[1] if isinstance(res, tuple) else res          # capture_settle_options.py:108-128 (bench first_hit)
    if hit is None:
        return None, None
    fields = hit.to_tuple()
    if not fields[0]:
        return None, None
    label = None
    for f in fields:
        if isinstance(f, unreal.Actor):
            label = f.get_actor_label()
            break
    return float(fields[5].z), label


def _spawned_live(specs_or_labels):
    labels = [s["label"] if isinstance(s, dict) else s for s in specs_or_labels]
    out = {}
    for actor in _level_actors():
        lab = actor.get_actor_label()
        if lab in labels and ACTOR_TAG in _tag_strings(actor):
            row = out.setdefault(lab, {"count": 0, "loc": None, "paths": []})
            row["count"] += 1
            row["loc"] = _vec(actor.get_actor_location())
            row["paths"].append(actor.get_path_name())
    return out


def _tagged_leftovers():
    return sorted(a.get_actor_label() for a in _level_actors()
                  if ACTOR_TAG in _tag_strings(a) or BEAMLOOK_TAG in _tag_strings(a) or SMOKE_TAG in _tag_strings(a))


# ---- assets (CREATE-ONLY; the beam_texture_bench make_editor_adapter builders, path-parameterised)
def _material_builder():
    mel = unreal.MaterialEditingLibrary
    eal = unreal.EditorAssetLibrary

    def create_material(path):
        require(not eal.does_asset_exist(path), "ASSET_EXISTS|%s" % path)
        d, name = path.rsplit("/", 1)
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, d, unreal.Material,
                                                                      unreal.MaterialFactoryNew())
        require(mat is not None, "ASSET_CREATE_FAILED|%s" % path)
        return mat

    def node(mat, cls, x, y, **props):
        n = mel.create_material_expression(mat, cls, x, y)
        require(n is not None, "CREATE_NODE|%s" % cls)
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def link(a, a_out, b, b_in):
        ok = mel.connect_material_expressions(a, a_out, b, b_in)
        if not ok and len(mel.get_material_expression_input_names(b)) == 1:
            ok = mel.connect_material_expressions(a, a_out, b, "")
        require(ok, "LINK|%s.%s->%s.%s" % (a.get_name(), a_out, b.get_name(), b_in))

    def custom(mat, x, y, desc, code, inputs):
        n = node(mat, unreal.MaterialExpressionCustom, x, y, description=desc, code=code,
                 output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        ins = []
        for name in inputs:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", name)
            ins.append(ci)
        n.set_editor_property("inputs", ins)
        return n

    def prop(src, mp):
        require(mel.connect_material_property(src, "", mp), "PROP|%s" % mp)

    def readback(mat, want):
        rb = {"domain": str(mat.get_editor_property("material_domain")),
              "blend_mode": str(mat.get_editor_property("blend_mode")),
              "shading_model": str(mat.get_editor_property("shading_model")),
              "expressions": len(mel.get_material_expressions(mat))}
        rb["ok"] = all(tok in rb[k] for k, tok in want.items()) and rb["expressions"] > 0
        rb["want"] = want
        return rb

    def build(spec, p):
        g = graph_spec(spec["graph"], p)
        mat = create_material(spec["path"])
        if g["domain"] == "VOLUME":
            # blend BEFORE domain (beam_texture_bench.py:2205-2208, measured 6 Oct beamtex_b_probe2.py)
            mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
            mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
            mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)   # :2209-2211
            wp = node(mat, unreal.MaterialExpressionWorldPosition, -1200, 0,
                      world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
            src = node(mat, unreal.MaterialExpressionTruncateLWC, -1000, 0)
            link(wp, "", src, "")
            src_pin = "WP"
        else:
            mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
            mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
            flag_err = None
            try:                                  # Material.h:921-927 bForceCompatibleWithLightFunctionAtlas
                mat.set_editor_property("force_compatible_with_light_function_atlas", True)
            except Exception as exc:  # noqa: BLE001 - judged by the read-back below
                flag_err = "%s: %s" % (type(exc).__name__, exc)
            mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_LIGHT_FUNCTION)   # LAST
            src = node(mat, unreal.MaterialExpressionTextureCoordinate, -1100, 0)
            src_pin = "UV"
        tm = node(mat, unreal.MaterialExpressionTime, -1100, 120)
        cus = custom(mat, -600, 100, "BeamLook %s" % spec["graph"], g["code"], g["inputs"])
        link(src, "", cus, src_pin)
        link(tm, "", cus, "T")
        for k, (pin, (name, value)) in enumerate(sorted(g["params"].items())):
            sc = node(mat, unreal.MaterialExpressionScalarParameter, -1100, 250 + 100 * k, parameter_name=name,
                      default_value=float(value), group="BeamLook")
            link(sc, "", cus, pin)
        if g["domain"] == "VOLUME":
            a = float(g["albedo"])
            alb = node(mat, unreal.MaterialExpressionConstant3Vector, -600, -150,
                       constant=unreal.LinearColor(a, a, a, 1.0))
            prop(alb, unreal.MaterialProperty.MP_BASE_COLOR)                # Albedo (VolumetricFogVoxelization.usf)
            prop(cus, unreal.MaterialProperty.MP_SUBSURFACE_COLOR)           # Extinction
            mel.recompile_material(mat)
            return readback(mat, {"domain": "VOLUME", "blend_mode": "ADDITIVE"})
        prop(cus, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        mel.recompile_material(mat)
        out = readback(mat, {"domain": "LIGHT_FUNCTION"})
        try:
            out["atlas_compatible_flag"] = bool(mat.get_editor_property("force_compatible_with_light_function_atlas"))
        except Exception as exc:  # noqa: BLE001
            out["atlas_compatible_flag"] = None
            flag_err = flag_err or "%s: %s" % (type(exc).__name__, exc)
        out["atlas_flag_error"] = flag_err
        out["ok"] = out["ok"] and out["atlas_compatible_flag"] is True
        return out

    def read_mi(path):
        mi = unreal.load_asset(path)
        parent = mi.get_editor_property("parent")
        return {"parent": asset_of(parent.get_path_name()) if parent else None, "class": mi.get_class().get_name()}

    def build_mi(spec):
        require(not eal.does_asset_exist(spec["path"]), "ASSET_EXISTS|%s" % spec["path"])
        folder, name = spec["path"].rsplit("/", 1)
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "MI_CREATE_FAILED|%s" % spec["path"])
        mel.set_material_instance_parent(mi, unreal.load_asset(spec["parent"]))     # lighting_scores_apply.py:1481-1487
        for key, value in sorted(spec["params"].items()):
            mel.set_material_instance_scalar_parameter_value(mi, key, float(value))
        mel.update_material_instance(mi)
        got = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in spec["params"]}
        rb = read_mi(spec["path"])
        rb["params"] = got
        rb["ok"] = rb["parent"] == spec["parent"] and all(same_value(got[k], v) for k, v in spec["params"].items())
        return rb

    def existing_ok(spec):
        if spec["type"] == "mi":
            rb = read_mi(spec["path"])
            mi = unreal.load_asset(spec["path"])
            rb["params"] = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in spec["params"]}
            rb["ok"] = rb["parent"] == spec["parent"] and all(
                same_value(rb["params"][k], v) for k, v in spec["params"].items())
            return rb
        mat = unreal.load_asset(spec["path"])
        dom = "VOLUME" if spec["graph"] in ("noise", "smoke") else "LIGHT_FUNCTION"
        return readback(mat, {"domain": dom})

    return build, build_mi, existing_ok


def _ensure_assets(plan_assets, p, reuse, record, write_record):
    """CREATE-ONLY. Each new package is saved on its own (never Save All); returns created paths."""
    eal = unreal.EditorAssetLibrary
    build, build_mi, existing_ok = _material_builder()
    marker = "%s_ASSETS_BEGIN|run=%s" % (MARK, record["run"])
    _log(marker)                                                      # compile-error scan starts after this line
    for spec in plan_assets:
        if eal.does_asset_exist(spec["path"]):
            require(reuse, "ASSET_EXISTS|%s|set reuse_existing_assets after checking it" % spec["path"])
            rb = existing_ok(spec)
            require(rb.get("ok"), "ASSET_EXISTS_DIFFERENT|%s|%s" % (spec["path"], _canonical(rb)))
            record["assets"][spec["path"]] = dict(rb, created=False)
            continue
        rb = build(spec, p) if spec["type"] == "material" else build_mi(spec)
        record["assets"][spec["path"]] = dict(rb, created=True)
        record["created_assets"].append(spec["path"])
        write_record()
        require(rb.get("ok"), "ASSET_READBACK|%s|%s" % (spec["path"], _canonical(rb)))
        require(eal.save_asset(spec["path"], only_if_is_dirty=False), "ASSET_SAVE_FAILED|%s" % spec["path"])
        _log("%s_ASSET|run=%s|path=%s|%s" % (MARK, record["run"], spec["path"], _canonical(rb)))
    return marker


def _compile_errors(marker):
    try:
        with open(LOG_PATH, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return None
    names = [ASSET_DIR + "/" + n for n in ("M_LF_SoftSlats", "M_LF_SoftGobo", "M_LF_SoftSlatsFlicker",
                                           "M_LF_SoftGoboFlicker", "M_Vol_BeamNoise", "M_Vol_SmokeLow")]
    lines = btb.compile_errors_since(text, marker, names)
    return None if lines is None else [ln for ln in lines if MARK + "_" not in ln]


# ---- Show writes
def _to_unreal(path, value):
    if path == F_LF:
        if value is None:
            return None
        obj = unreal.load_asset(asset_of(value))
        require(obj is not None, "LF_MATERIAL_MISSING|%s" % value)
        return obj
    if path == F_LF_SCALE:
        return unreal.Vector(*[float(x) for x in value])
    return float(value)


def _write_fields(tool, show, targets, side, check_side=None):
    cues = list(show.get_editor_property("cues"))
    by_cue = {}
    for t in targets:
        by_cue.setdefault(t["cue_guid"], []).append(t)
    for cue_guid, items in sorted(by_cue.items()):
        matches = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == cue_guid]
        require(len(matches) == 1 and matches[0] == items[0]["show_index"], "TARGET_CUE_RESOLVE|" + cue_guid)
        index = matches[0]
        require(str(cues[index].get_editor_property("label")) == items[0]["cue_label"], "TARGET_LABEL_DRIFT|" + cue_guid)
        attachments = tool._pair_attachments(cues[index])
        for t in items:
            hits = [a for a in attachments if tool._guid_text(a.get_editor_property("attachment_guid"))
                    == t["attachment_guid"]]
            require(len(hits) == 1, "TARGET_ATTACHMENT_RESOLVE|" + t["attachment_guid"])
            attachment = hits[0]
            struct_name, field = t["path"].split(".", 1)
            if check_side is not None:
                live = get_path(S.attachment_state(attachment, tool._guid_text), t["path"])
                require(same_value(live, t[check_side]), "TARGET_FIELD_DRIFT|%s|%s|live=%r|want=%r"
                        % (t["attachment_label"], t["path"], live, t[check_side]))
            st = attachment.get_editor_property(struct_name)
            st.set_editor_property(field, _to_unreal(t["path"], t[side]))
            attachment.set_editor_property(struct_name, st)
        tool._set_pair_attachments(show, index, attachments)


def _spawn(spec, passage, p):
    """Editor world only. Movable before the attach (a Static child cannot attach to the Passage's movable root:
    InfinityStagePassageActor.cpp:976-981)."""
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    r = spec["rot"]
    actor = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*spec["loc"]),
                                       unreal.Rotator(roll=float(r["roll"]), pitch=float(r["pitch"]),
                                                      yaw=float(r["yaw"])))
    require(actor is not None, "SPAWN_FAILED|%s" % spec["label"])
    actor.set_actor_label(spec["label"], False)
    actor.set_editor_property("tags", [unreal.Name(t) for t in spec["tags"]])
    actor.set_actor_enable_collision(False)
    comp = actor.static_mesh_component
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.set_static_mesh(unreal.load_object(None, CUBE))
    mat = unreal.load_asset(spec["material"])
    require(mat is not None, "SPAWN_MATERIAL_MISSING|%s" % spec["material"])
    comp.set_material(0, mat)
    comp.set_cast_shadow(False)
    actor.set_actor_scale3d(unreal.Vector(*spec["scale"]))
    if p["attach_to_passage"]:
        actor.attach_to_actor(passage, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, False)
        require(actor.get_attach_parent_actor() == passage, "ATTACH_FAILED|%s" % spec["label"])
    got = _vec(actor.get_actor_location())
    require(math.dist(got, spec["loc"]) <= 1.0, "SPAWN_MOVED|%s|%s" % (spec["label"], got))
    m0 = comp.get_material(0)
    require(m0 is not None and asset_of(m0.get_path_name()) == spec["material"], "SPAWN_MATERIAL_READBACK|%s"
            % spec["label"])
    return actor.get_path_name()


def _destroy_spawned(labels):
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in _level_actors():
        if actor.get_actor_label() in labels and ACTOR_TAG in _tag_strings(actor):
            require(sub.destroy_actor(actor), "DESTROY_FAILED|%s" % actor.get_actor_label())


def _verify_lights(targets, bay_guids, side):
    """Post-materialize: the spawned light components carry the written VS / light function."""
    live = _materialized(bay_guids)
    bad = []
    for t in targets:
        if t["path"] not in (F_VS, F_LF):
            continue
        actor = live.get(t["attachment_guid"])
        row = _light_live(actor) if actor is not None else None
        if row is None:
            bad.append({"label": t["attachment_label"], "problem": "no materialized light"})
            continue
        got = row["vs"] if t["path"] == F_VS else row["lf"]
        if not same_value(got, t[side]):
            bad.append({"label": t["attachment_label"], "path": t["path"], "want": t[side], "got": got})
    require(not bad, "MATERIALIZED_LIGHT_MISMATCH|side=%s|%s" % (side, _canonical(bad)[:2500]))


def _gather(rp, scores, tool, cfg, p):
    """Everything DRY/APPLY plan from, read LIVE."""
    aims, record_passage_guid = rp.load_aims(cfg["scores_record"])
    show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
    require(show is not None, "SHOW_ASSET_MISSING")
    plain = rp._runtime_plain(tool, show, record_passage_guid, cfg)
    passage = _passage_actor(cfg)
    stations = _station_z(passage, tool)
    mats = _materialized(plain["bay_guids"])
    require(mats, "NO_MATERIALIZED_P03_ACTORS")
    box = footprint([_vec(a.get_actor_location()) for a in mats.values()], p["bbox_margin_cm"])
    beams = beam_rows(plain, p)
    beams_world, floors, warnings = [], {}, []
    for b in beams:
        actor = mats.get(b["row"]["guid"])
        live = _light_live(actor) if actor is not None else None
        require(live is not None, "BEAM_NOT_MATERIALIZED|%s" % b["row"]["label"])
        bw = dict(live, label=b["row"]["label"], bay=b["bay"], show_index=b["cue"]["show_index"],
                  cue_guid=b["cue"]["guid"], guid=b["row"]["guid"])
        beams_world.append(bw)
        st_z = stations.get(b["cue"]["guid"])
        xy, _h = smoke_point(bw, p)
        tz, tlabel = _trace_floor(xy, st_z if st_z is not None else bw["location"][2] - 450.0, p)
        fz, src = choose_floor(tz, st_z, p)
        floors[bw["label"]] = (fz, src, tz, tlabel, st_z)
        if src != "trace":
            warnings.append("FLOOR_%s|%s|trace=%s|station=%s" % (src.upper(), bw["label"], tz, st_z))
    return {"show": show, "plain": plain, "passage": passage, "stations": stations, "mats": mats, "box": box,
            "beams": beams, "beams_world": beams_world, "floors": floors, "warnings": warnings,
            "record_passage_guid": record_passage_guid}


def _plan(g, p):
    fog_targets, fog_untouched = plan_fog(g["plain"], p)
    lf_targets, mi_specs, lf_rows, lf_warn = ([], {}, [], [])
    flicker = {}
    if p["beam_look"]:
        flicker = _flicker_live([b["row"]["lighting"]["light_function_material"] for b in g["beams"]])
        lf_targets, mi_specs, lf_rows, lf_warn = plan_lf(g["beams"], flicker, p)
    show_targets = fog_targets + lf_targets
    check_targets(show_targets)
    lfv_rows = _lfvs()
    lfv_targets, lfv_outside = plan_lfv(lfv_rows, g["box"], p)
    noise, smoke, smoke_fz = plan_spawns(g["beams_world"], g["floors"], g["box"], p)
    need_flk = any(a["parent"] in (MAT_SLATS_FLK, MAT_GOBO_FLK) for a in mi_specs.values())
    assets = asset_plan(p, mi_specs, need_flk, smoke_fz)
    counts = {"vs": sum(1 for t in show_targets if t["kind"] == "vs"),
              "lf": len({t["attachment_guid"] for t in lf_targets}),
              "medium": sum(1 for t in show_targets if t["kind"] == "medium"),
              "lfv": len({t["id"] for t in lfv_targets}), "noise": len(noise), "smoke": len(smoke)}
    return {"show_targets": show_targets, "fog_untouched": fog_untouched, "lf_rows": lf_rows, "flicker_live": flicker,
            "mi_specs": mi_specs, "lfv_targets": lfv_targets, "lfv_rows": lfv_rows, "lfv_outside": lfv_outside,
            "noise": noise, "smoke": smoke, "smoke_floor_z": smoke_fz, "assets": assets, "counts": counts,
            "warnings": g["warnings"] + lf_warn,
            "target_cue_guids": sorted({t["cue_guid"] for t in show_targets}),
            "target_attachment_guids": sorted({t["attachment_guid"] for t in show_targets})}


INFERRED = [
    "set_editor_property(light_function_material, None) clears the soft pointer (REVERT of B04)",
    "MaterialInstanceConstant scalar overrides reach the Custom-node graph in the light-function atlas",
    "a Volume-domain StaticMesh box is voxelised in the show as in the bench's PIE",
    "smoke height fade (WP.z vs FloorZ) reads as floor-hugging",
    "panel base z = floor when the floor trace misses (FLOOR_* warnings)",
    "P03 footprint bbox catches every P03-local LFV and nothing of a neighbour passage",
    "a later lighting_scores APPLY/REVERT of P03 sees these fields as drift (the scores record is a foreign record)",
]


def _dry_live_summary(g, plan):
    lights = [r for c in passage_cues(g["plain"]) for r in c["attachments"] if _enum_name(r["kind"]) == "LIGHT"]
    en = [r for r in lights if r.get("enabled", True)]
    effects = [r for c in passage_cues(g["plain"]) for r in c["attachments"] if _enum_name(r["kind"]) == "EFFECT"]
    other = _other_lights(g["box"], {a.get_path_name() for a in g["mats"].values()})
    return {
        "height_fogs": _height_fogs(),
        "vs_summary": {"lights": len(lights), "enabled": len(en), "sum_vs_enabled": round(sum(
            float(r["lighting"]["volumetric_scattering_intensity"]) for r in en), 4),
            "sum_vs_enabled_after": round(sum(float(r["lighting"]["volumetric_scattering_intensity"]) for r in en)
                                          + sum(t["after"] - t["before"] for t in plan["show_targets"]
                                                if t["kind"] == "vs"), 4),
            "beams": [{"label": b["row"]["label"], "vs": b["row"]["lighting"]["volumetric_scattering_intensity"],
                       "lf": b["row"]["lighting"]["light_function_material"]} for b in g["beams"]]},
        "medium_summary": {"effect_rows": len(effects), "targets": plan["counts"]["medium"],
                           "effect_sources_in_box": _effect_sources(g["box"])},
        "lfv_summary": {"all_level_lfvs": plan["lfv_rows"], "targets": plan["lfv_targets"],
                        "outside": plan["lfv_outside"]},
        "other_lights": {"count": len(other), "visible_vs_sum": round(sum(r["vs"] for r in other if r["visible"]), 4),
                         "top": other[:30]},
        "cvars": _cvars(),
    }


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode, p = args["mode"], args["params"]
    report = {"ok": False, "mode": mode, "run": run, "args": args, "saved": False, "inferred": INFERRED}
    tool = None
    try:
        rp = load_rig_pattern()
        scores, tool = rp.load_modules()
        cfg = rp.passage_config(PASSAGE)
        report["sources"] = {"rig_pattern_sha256": rp.SOURCE_SHA256, "scores_sha256": scores.SOURCE_SHA256}
        ctx = rp._ctx_facts(tool)
        report["context"] = ctx
        rp.check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]

        if mode == "REVERT":
            return _revert(args, run, report, rp, scores, tool, cfg)

        g = _gather(rp, scores, tool, cfg, p)
        plan = _plan(g, p)
        before_all = rp._all_rows(g["plain"])
        problems = scope_problems(before_all, apply_rows(before_all, plan["show_targets"], "after"),
                                  plan["show_targets"], "after")
        require(not problems, "MODEL_SELF_CHECK|%s" % _canonical(problems)[:2000])   # model self-check
        roots = [os.path.join(os.path.dirname(HERE), n) for n in sorted(os.listdir(os.path.dirname(HERE)))
                 if n.startswith("Codex")]
        foreign = scores.scan_foreign_records(roots, plan["target_attachment_guids"], exclude=[RECORD_PATH])
        unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
        eal = unreal.EditorAssetLibrary
        existing = {a["path"]: bool(eal.does_asset_exist(a["path"])) for a in plan["assets"]}
        leftovers = _tagged_leftovers()
        report.update({"plan": {k: v for k, v in plan.items() if k not in ("lfv_rows",)},
                       "passage_guid": g["plain"]["passage_guid"], "footprint": g["box"],
                       "beams_world": g["beams_world"],
                       "floors": {k: {"z": v[0], "source": v[1], "trace_z": v[2], "trace_hit": v[3], "station_z": v[4]}
                                  for k, v in g["floors"].items()},
                       "foreign_records": foreign, "unacknowledged_foreign_records": unacked,
                       "assets_existing": existing, "tagged_leftovers": leftovers,
                       "active_record": RECORD_PATH if os.path.exists(RECORD_PATH) else None})
        if mode == "DRY":
            live = _dry_live_summary(g, plan)
            report["fog_sources"] = fog_source_table(live)
            for t in plan["show_targets"]:
                _log("%s_DRY_ROW|run=%s|%s|%s|%s->%s" % (MARK, run, t["attachment_label"], t["path"], t["before"],
                                                        t["after"]))
            for w in plan["warnings"]:
                _log("%s_WARNING|run=%s|%s" % (MARK, run, w))
            census_after = tool._dirty_census()
            require(census_after == census_before, "DRY_CENSUS_CHANGED|before=%s|after=%s"
                    % (_canonical(census_before), _canonical(census_after)))
            again = rp._all_rows(rp._runtime_plain(tool, g["show"], g["record_passage_guid"], cfg))
            require(tool._outside_hash(again, []) == tool._outside_hash(before_all, []), "DRY_SHOW_ROWS_CHANGED")
            report.update({"ok": True, "mutated": False, "census_after": census_after})
            path = report_path(mode, run)
            tool._write_json(path, report)
            _log("%s_DRY_OK|run=%s|counts=%s|assets=%d|existing=%d|warnings=%d|foreign=%d|unacked=%d|leftovers=%d"
                 "|census_equal=1|mutated=0|report=%s"
                 % (MARK, run, _canonical(plan["counts"]), len(plan["assets"]), sum(existing.values()),
                    len(plan["warnings"]), len(foreign), len(unacked), len(leftovers), path))
            return report

        # APPLY
        check_expected(args["expected"], plan["counts"])
        require(not os.path.exists(RECORD_PATH), "ACTIVE_RECORD_EXISTS|" + RECORD_PATH)
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        require(not leftovers, "TAGGED_LEFTOVERS|%s" % leftovers)
        backup = tool._backup(backup_prefix(), run)
        record = {"schema_version": 1, "status": "prepared", "run": run, "passage": PASSAGE, "backup": backup,
                  "args": args, "params": p, "plan": {k: v for k, v in plan.items() if k not in ("lfv_rows",)},
                  "outside_before_hash": tool._outside_hash(before_all, plan["target_cue_guids"]),
                  "before_cue_rows": {c: before_all[c] for c in plan["target_cue_guids"]},
                  "assets": {}, "created_assets": [], "spawned": {}, "acknowledged_records": list(args["ack_records"])}
        tool._write_json(RECORD_PATH, record, exclusive=True)            # fsynced before any change
        _log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run, RECORD_PATH))

        def write_record():
            tool._write_json(RECORD_PATH, record)

        marker = _ensure_assets(plan["assets"], p, args["reuse_existing_assets"], record, write_record)
        require(tool._dirty_census() == census_before, "DIRTY_AFTER_ASSETS|%s" % _canonical(tool._dirty_census()))
        record["status"] = "assets_saved"
        write_record()
        try:
            _write_fields(tool, g["show"], plan["show_targets"], "after", check_side="before")
            after_all = rp._all_rows(rp._runtime_plain(tool, g["show"], g["record_passage_guid"], cfg))
            problems = scope_problems(before_all, after_all, plan["show_targets"], "after", tool._state_differences)
            require(not problems, "SCOPE_CHANGED|%s" % _canonical(problems)[:3000])
            _lfv_write(plan["lfv_targets"], "after")
            require(not lfv_drifts(_lfv_live(plan["lfv_targets"]), plan["lfv_targets"], "after"), "LFV_WRITE_READBACK")
            for spec in plan["noise"] + plan["smoke"]:
                record["spawned"][spec["label"]] = _spawn(spec, g["passage"], p)
                write_record()
        except Exception:
            _destroy_spawned(list(record["spawned"]))
            _lfv_write(plan["lfv_targets"], "before")
            _write_fields(tool, g["show"], plan["show_targets"], "before")
            restored = rp._all_rows(rp._runtime_plain(tool, g["show"], g["record_passage_guid"], cfg))
            require(not scope_problems(before_all, restored, plan["show_targets"], "before", tool._state_differences),
                    "ROLLBACK_SCOPE")
            record["status"] = "failed_rolled_back_in_memory"
            write_record()
            os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
            raise
        record["status"] = "mutated_verified"
        write_record()
        materialized = rp._materialize(scores, g["show"], cfg)
        _verify_lights(plan["show_targets"], g["plain"]["bay_guids"], "after")
        require(not spawn_drifts(_spawned_live(plan["noise"] + plan["smoke"]), plan["noise"] + plan["smoke"]),
                "SPAWN_READBACK")
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = rp._all_rows(rp._runtime_plain(tool, readback, g["record_passage_guid"], cfg))
        problems = scope_problems(before_all, read_all, plan["show_targets"], "after", tool._state_differences)
        require(not problems, "READBACK_SCOPE|%s" % _canonical(problems)[:3000])
        require(not lfv_drifts(_lfv_live(plan["lfv_targets"]), plan["lfv_targets"], "after"), "LFV_READBACK")
        errors = _compile_errors(marker)
        record.update({"status": "saved_readback_verified", "materialized": materialized,
                       "compile_errors_at_save": errors, "saved_census": tool._dirty_census()})
        write_record()
        report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized,
                       "created_assets": record["created_assets"], "spawned": record["spawned"],
                       "compile_errors_at_save": errors})
        tool._write_json(report_path(mode, run), report)
        _log("%s_APPLY_OK|run=%s|counts=%s|assets_created=%d|show_saved=1|level_saved=1|readback=1|compile_errors=%s"
             "|record=%s" % (MARK, run, _canonical(plan["counts"]), len(record["created_assets"]),
                             "unknown" if errors is None else len(errors), RECORD_PATH))
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
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s" % (
            MARK, run, mode, int(report["saved"]), report["error"][:1500], "" if report["saved"] else "|NOTHING SAVED"))
        raise


def _revert(args, run, report, rp, scores, tool, cfg):
    require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
    record = tool._read_json(RECORD_PATH)
    require(record.get("passage") == PASSAGE and record.get("status") == "saved_readback_verified",
            "REVERT_RECORD_STATUS|%s" % record.get("status"))
    plan = record["plan"]
    aims, record_passage_guid = rp.load_aims(cfg["scores_record"])
    show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
    plain = rp._runtime_plain(tool, show, record_passage_guid, cfg)
    live_all = rp._all_rows(plain)
    spawned_specs = plan["noise"] + plan["smoke"]
    drifts = {"show": field_drifts(live_all, plan["show_targets"], "after"),
              "lfv": lfv_drifts(_lfv_live(plan["lfv_targets"]), plan["lfv_targets"], "after"),
              "spawned": spawn_drifts(_spawned_live(spawned_specs), spawned_specs)}
    report["revert_drifts"] = drifts
    require(not any(drifts.values()), "REVERT_DRIFT|%s" % _canonical(drifts)[:4000])
    model = apply_rows(live_all, plan["show_targets"], "before")
    backup = tool._backup(backup_prefix(revert=True), run)
    try:
        _write_fields(tool, show, plan["show_targets"], "before", check_side="after")
        after_all = rp._all_rows(rp._runtime_plain(tool, show, record_passage_guid, cfg))
        problems = scope_problems(live_all, after_all, plan["show_targets"], "before", tool._state_differences)
        require(not problems, "REVERT_SCOPE|%s" % _canonical(problems)[:3000])
        require(not scope_problems(model, after_all, [], "before", tool._state_differences), "REVERT_MODEL_MISMATCH")
        _lfv_write(plan["lfv_targets"], "before")
        require(not lfv_drifts(_lfv_live(plan["lfv_targets"]), plan["lfv_targets"], "before"), "REVERT_LFV_READBACK")
    except Exception:
        _write_fields(tool, show, plan["show_targets"], "after")
        _lfv_write(plan["lfv_targets"], "after")
        raise
    _destroy_spawned([s["label"] for s in spawned_specs])
    left = _spawned_live(spawned_specs)
    require(not left, "REVERT_SPAWNED_LEFT|%s" % sorted(left))
    materialized = rp._materialize(scores, show, cfg)
    _verify_lights(plan["show_targets"], plain["bay_guids"], "before")
    tool._save_narrow()
    report["saved"] = True
    readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
    read_all = rp._all_rows(rp._runtime_plain(tool, readback, record_passage_guid, cfg))
    require(not field_drifts(read_all, plan["show_targets"], "before"), "REVERT_READBACK")
    removed = []
    if args["remove_assets"]:
        refs = [r["label"] for c in passage_cues(rp._runtime_plain(tool, readback, record_passage_guid, cfg))
                for r in c["attachments"] if str(r["lighting"].get("light_function_material") or "").startswith(ASSET_DIR)]
        require(not refs, "ASSETS_STILL_REFERENCED|%s" % refs)
        for path in reversed(record.get("created_assets", [])):        # instances before their parents
            require(unreal.EditorAssetLibrary.delete_asset(path), "ASSET_DELETE_FAILED|%s" % path)
            removed.append(path)
        require(tool._dirty_census() == {"content": [], "maps": []}, "DIRTY_AFTER_ASSET_REMOVE")
    archived = RECORD_PATH + ".reverted-" + run
    record.update({"status": "reverted", "revert_run": run, "assets_removed": removed})
    tool._write_json(RECORD_PATH, record)
    os.rename(RECORD_PATH, archived)
    report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized,
                   "assets_removed": removed})
    tool._write_json(report_path("REVERT", run), report)
    _log("%s_REVERT_OK|run=%s|show_fields=%d|lfv_fields=%d|destroyed=%d|assets_removed=%d|show_saved=1|level_saved=1"
         "|readback=1|archived=%s" % (MARK, run, len(plan["show_targets"]), len(plan["lfv_targets"]),
                                      len(spawned_specs), len(removed), archived))
    return report


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    raw = globals().get("P03ATMOS_ARGS")
    try:
        args = check_args(raw)
    except Exception as error:  # noqa: BLE001 - args refusals get the same stop marker
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


if unreal is not None and "P03ATMOS_ARGS" in globals():
    main()
