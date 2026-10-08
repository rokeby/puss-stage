"""P13 opening-lighting proposal (8 Oct 2026; authored offline, never run here).

DRY/APPLY/REVERT tool for the Show-owned opening lamps and the Opening sequence.
The first P01 WingPair cue owns every new light attachment.  The Opening sequence
drives those attachments through UInfinityStageAttachmentBinding, whose GUID tag
survives Passage materialization.  APPLY also disables (never deletes) the old
``Opening Rig - *`` spawnables, re-times the existing curtain Geometry Cache, and
places the focal-length perspective adjustment on the selected flurry.

Globals supplied by opening_lighting_p13_run.py:
  P13_MODE = DRY|APPLY|REVERT
  P13_CONFIRM = "DRY P13"|"APPLY P13"|"REVERT P13"
  P13_ARGS = dict (optional overrides)
  P13_RUN_ID = optional

Success marker: P13_OPENING_LIGHTING_<MODE>_OK|run=...
Importing this module under system Python is offline-only and never imports Unreal.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LEVEL_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OPENING_LABEL = "Opening — Curtain"
P01_LABEL = "Passage 1"
OLD_RIG_PREFIX = "Opening Rig - "
TRACK_NAME = "P13 Opening Lighting"
MARKER_PREFIX = "P13 "
RECORD_NAME = "opening_lighting_p13_record.json"
PLAN_NAME = "opening_lighting_p13_plan.json"
ANALYSIS_FALLBACK = os.path.join("Saved", "InfinityStage", "MusicAnalysis", "OpeningSketch2",
                                 "P01_Opening_Tuning_sketch2.analysis.json")
P11_GLOB_HINT = os.path.join("DerivedAssets", "MusicAnalysis")
MODES = ("DRY", "APPLY", "REVERT")

DEFAULTS = {
    # P11 had not landed in this worktree.  These are args, not claimed musical truth.
    "flurry_times_s": [36.1767, 43.8393, 59.5360],
    "curtain_flurry_index": 2,
    "lights_on_flurry_index": 2,
    "perspective_flurry_index": 3,
    "opening_end_s": 96.36,
    "fps": 25.0,
    "spot_count": 4,
    "spot_intensity_cd": 800.0,
    "spot_hold_scale": 0.55,
    "spot_fade_in_s": 0.45,
    "spot_fade_out_s": 1.25,
    "spot_outer_cone_deg": 12.0,
    "spot_inner_cone_deg": 7.0,
    "spot_falloff_exponent": 12.0,
    "spot_soft_source_radius_cm": 8.0,
    "spot_source_radius_cm": 2.0,
    "spot_temperature_kelvin": 2950.0,
    "spot_color_rgb_linear": [1.0, 0.80, 0.58],
    "spot_attenuation_cm": 4800.0,
    "spot_volumetric_scattering": 0.45,
    "spot_cast_shadows": True,
    "spot_cast_volumetric_shadows": False,
    "fixture_world_x_cm": -1600.0,
    "fixture_side_y_cm": 1050.0,
    "fixture_low_z_cm": 760.0,
    "fixture_high_z_cm": 1120.0,
    "start_aim_x_cm": 0.0,
    "start_aim_half_width_cm": 760.0,
    "start_aim_z_cm": 430.0,
    "centre_aim_x_cm": 260.0,
    "centre_aim_half_width_cm": 110.0,
    "centre_aim_z_cm": 280.0,
    "corner_intensity_cd": 1500.0,
    "corner_outer_cone_deg": 10.0,
    "corner_inner_cone_deg": 5.0,
    "corner_falloff_exponent": 12.0,
    "corner_source_radius_cm": 2.0,
    "corner_soft_source_radius_cm": 6.0,
    "corner_temperature_kelvin": 3400.0,
    "corner_color_rgb_linear": [1.0, 0.88, 0.70],
    "corner_attenuation_cm": 4300.0,
    "corner_volumetric_scattering": 0.35,
    "corner_cast_shadows": True,
    "corner_cast_volumetric_shadows": False,
    "corner_world_x_cm": -1050.0,
    "corner_world_y_cm": 920.0,
    "corner_world_z_cm": 1250.0,
    "corner_aim_x_cm": 100.0,
    "corner_aim_y_cm": 0.0,
    "corner_aim_z_cm": 430.0,
    "corner_pulse_attack_s": 0.08,
    "corner_pulse_release_s": 0.55,
    "perspective_start_mm": 15.0,
    "perspective_end_mm": 25.0,
    "perspective_duration_s": 2.4,
    "perspective_mode": "focal_only",
    "station_world_x_cm": 250.0,
    "curtain_fall_frames": 250,
    "curtain_hold_offset_ticks": 23200,
    "curtain_pile_offset_ticks": 263999,
    "curtain_cache_path": "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening",
    "analysis_path": None,
}

CLAIMS = [
    {"tier": "declaration-proven", "claim": "Show light attachments are stored on a WingPair and carry stable AttachmentGuid identity.",
     "cite": "Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:434-498"},
    {"tier": "declaration-proven", "claim": "The custom Stage Attachment binding resolves a materialized attachment by its GUID tag across respawn.",
     "cite": "Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageAttachmentBinding.h:12-66"},
    {"tier": "declaration-proven", "claim": "A Show Scene cue owns a Level Sequence and may delegate its visible curtain to that sequence.",
     "cite": "Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:817-875"},
    {"tier": "measured", "claim": "The last applied opening record used 2409 frames at 25 fps and put the current release at frame 1935.",
     "cite": "Saved/CodexConductor/opening_sequence_record.json:12122-12131"},
    {"tier": "inferred", "claim": "Four 12-degree moving pools plus two corner pulses should read tighter than the current 30-degree centre wash; rendered acceptance is pending.",
     "cite": "Docs/Conductor/codex_briefs/p13_opening_lighting.md:2-10; Saved/CodexConductor/opening_lighting_p13_args.json:6-67"},
    {"tier": "inferred", "claim": "Gary's perspective adjustment means a 15-to-25 mm focal pull; camera translation is deliberately not changed.",
     "cite": "Docs/Conductor/codex_briefs/p13_opening_lighting.md:2-3; Saved/CodexConductor/opening_lighting_p13_args.json:58-61"},
]


class P13Error(RuntimeError):
    pass


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _project_root():
    if unreal is not None:
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.abspath(os.path.join(_here(), "..", ".."))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:20]


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def merge_args(overrides=None):
    unknown = sorted(set(overrides or {}) - set(DEFAULTS))
    if unknown:
        raise P13Error("UNKNOWN_ARGS|%r" % unknown)
    p = copy.deepcopy(DEFAULTS)
    p.update(overrides or {})
    p["flurry_times_s"] = [float(v) for v in p["flurry_times_s"]]
    for name in ("fps", "opening_end_s", "spot_intensity_cd", "spot_hold_scale", "spot_fade_in_s",
                 "spot_fade_out_s", "spot_outer_cone_deg", "spot_inner_cone_deg", "spot_falloff_exponent",
                 "corner_intensity_cd", "corner_outer_cone_deg", "corner_inner_cone_deg",
                 "corner_falloff_exponent", "corner_pulse_attack_s", "corner_pulse_release_s",
                 "perspective_start_mm", "perspective_end_mm", "perspective_duration_s"):
        p[name] = float(p[name])
    for name in ("spot_count", "curtain_flurry_index", "lights_on_flurry_index",
                 "perspective_flurry_index", "curtain_fall_frames"):
        p[name] = int(p[name])
    if p["perspective_mode"] != "focal_only":
        raise P13Error("PERSPECTIVE_MODE|only focal_only is implemented; camera translation needs Gary")
    if not (2 <= p["spot_count"] <= 8):
        raise P13Error("SPOT_COUNT|must be 2..8")
    if p["flurry_times_s"] != sorted(p["flurry_times_s"]) or len(p["flurry_times_s"]) < 3:
        raise P13Error("FLURRIES|need at least three strictly ordered seconds")
    if len(set(p["flurry_times_s"])) != len(p["flurry_times_s"]):
        raise P13Error("FLURRIES|duplicate time")
    for name in ("curtain_flurry_index", "lights_on_flurry_index", "perspective_flurry_index"):
        if not 1 <= p[name] <= len(p["flurry_times_s"]):
            raise P13Error("FLURRY_INDEX|%s=%d" % (name, p[name]))
    for prefix in ("spot", "corner"):
        inner, outer = p[prefix + "_inner_cone_deg"], p[prefix + "_outer_cone_deg"]
        if not (1.0 <= inner < outer <= 45.0):
            raise P13Error("CONE|%s %.3f/%.3f" % (prefix, inner, outer))
        if not (8.0 <= p[prefix + "_falloff_exponent"] <= 16.0):
            raise P13Error("FALLOFF|%s" % prefix)
    if not (0.0 < p["spot_hold_scale"] <= 1.0):
        raise P13Error("SPOT_HOLD_SCALE")
    if p["opening_end_s"] <= p["flurry_times_s"][-1]:
        raise P13Error("OPENING_END_BEFORE_FLURRIES")
    return p


def frame(seconds, fps):
    return int(round(float(seconds) * float(fps)))


def aim_rotation(origin, target):
    dx, dy, dz = (float(target[i]) - float(origin[i]) for i in range(3))
    flat = math.hypot(dx, dy)
    return [0.0, math.degrees(math.atan2(dz, max(flat, 1.0e-9))), math.degrees(math.atan2(dy, dx))]


def _spot_origins(p):
    n = p["spot_count"]
    out = []
    for i in range(n):
        side = -1.0 if i % 2 == 0 else 1.0
        rank = i // 2
        pairs = (n + 1) // 2
        alpha = 0.0 if pairs == 1 else rank / float(pairs - 1)
        z = p["fixture_low_z_cm"] + (p["fixture_high_z_cm"] - p["fixture_low_z_cm"]) * alpha
        out.append([p["fixture_world_x_cm"], side * p["fixture_side_y_cm"], z])
    return out


def build_plan(overrides=None):
    p = merge_args(overrides)
    fps = p["fps"]
    flurries = [{"index": i + 1, "seconds": t, "frame": frame(t, fps)}
                for i, t in enumerate(p["flurry_times_s"])]
    pick = lambda key: flurries[p[key] - 1]
    curtain, lights, perspective = pick("curtain_flurry_index"), pick("lights_on_flurry_index"), pick("perspective_flurry_index")
    end = frame(p["opening_end_s"], fps)
    fade_in = max(1, frame(p["spot_fade_in_s"], fps))
    fade_out = max(1, frame(p["spot_fade_out_s"], fps))
    perspective_end = perspective["frame"] + max(1, frame(p["perspective_duration_s"], fps))
    fixtures = []
    origins = _spot_origins(p)
    n = len(origins)
    for i, origin in enumerate(origins):
        side = -1.0 if origin[1] < 0 else 1.0
        spread = 0.0 if n == 1 else -1.0 + 2.0 * i / float(n - 1)
        start_target = [p["start_aim_x_cm"], spread * p["start_aim_half_width_cm"], p["start_aim_z_cm"]]
        centre_target = [p["centre_aim_x_cm"], side * p["centre_aim_half_width_cm"], p["centre_aim_z_cm"]]
        start_rot, end_rot = aim_rotation(origin, start_target), aim_rotation(origin, centre_target)
        fixtures.append({
            "label": "P13 Opening Sweep %02d" % (i + 1), "role": "moving_spot", "type": "SPOT",
            "world_location_cm": origin,
            "relative_location_cm": [origin[0] - p["station_world_x_cm"], origin[1], origin[2]],
            "start_target_cm": start_target, "end_target_cm": centre_target,
            "start_rotation_rpy_deg": start_rot, "end_rotation_rpy_deg": end_rot,
            "rotation_keys": [[0, start_rot], [lights["frame"], start_rot], [perspective["frame"], end_rot]],
            "intensity_keys": [[0, 0.0], [lights["frame"], 0.0],
                               [lights["frame"] + fade_in, p["spot_intensity_cd"]],
                               [max(lights["frame"] + fade_in, end - fade_out), p["spot_intensity_cd"] * p["spot_hold_scale"]],
                               [end, 0.0]],
            "intensity_cd": p["spot_intensity_cd"], "inner_cone_deg": p["spot_inner_cone_deg"],
            "outer_cone_deg": p["spot_outer_cone_deg"], "falloff_exponent": p["spot_falloff_exponent"],
            "source_radius_cm": p["spot_source_radius_cm"], "soft_source_radius_cm": p["spot_soft_source_radius_cm"],
            "temperature_kelvin": p["spot_temperature_kelvin"], "color_rgb_linear": p["spot_color_rgb_linear"],
            "attenuation_cm": p["spot_attenuation_cm"], "volumetric_scattering": p["spot_volumetric_scattering"],
            "cast_shadows": p["spot_cast_shadows"], "cast_volumetric_shadows": p["spot_cast_volumetric_shadows"],
        })
    attack, release = max(1, frame(p["corner_pulse_attack_s"], fps)), max(1, frame(p["corner_pulse_release_s"], fps))
    for side, token in ((-1.0, "L"), (1.0, "R")):
        origin = [p["corner_world_x_cm"], side * p["corner_world_y_cm"], p["corner_world_z_cm"]]
        target = [p["corner_aim_x_cm"], p["corner_aim_y_cm"], p["corner_aim_z_cm"]]
        keys = [[0, 0.0]]
        for f in flurries:
            keys += [[max(0, f["frame"] - attack), 0.0], [f["frame"], p["corner_intensity_cd"]],
                     [f["frame"] + release, 0.0]]
        fixtures.append({
            "label": "P13 Opening Corner " + token, "role": "corner_pulse", "type": "SPOT",
            "world_location_cm": origin,
            "relative_location_cm": [origin[0] - p["station_world_x_cm"], origin[1], origin[2]],
            "start_target_cm": target, "end_target_cm": target,
            "start_rotation_rpy_deg": aim_rotation(origin, target), "end_rotation_rpy_deg": aim_rotation(origin, target),
            "rotation_keys": [], "intensity_keys": keys,
            "intensity_cd": p["corner_intensity_cd"], "inner_cone_deg": p["corner_inner_cone_deg"],
            "outer_cone_deg": p["corner_outer_cone_deg"], "falloff_exponent": p["corner_falloff_exponent"],
            "source_radius_cm": p["corner_source_radius_cm"], "soft_source_radius_cm": p["corner_soft_source_radius_cm"],
            "temperature_kelvin": p["corner_temperature_kelvin"], "color_rgb_linear": p["corner_color_rgb_linear"],
            "attenuation_cm": p["corner_attenuation_cm"], "volumetric_scattering": p["corner_volumetric_scattering"],
            "cast_shadows": p["corner_cast_shadows"], "cast_volumetric_shadows": p["corner_cast_volumetric_shadows"],
        })
    marker_rows = [("P13 flurry %02d" % f["index"], f["frame"]) for f in flurries]
    marker_rows += [("P13 curtain drop", curtain["frame"]), ("P13 lights on", lights["frame"]),
                    ("P13 perspective", perspective["frame"])]
    plan = {
        "schema_version": 1, "fps": fps, "opening_end_frame": end, "flurries": flurries,
        "cue_frames": {"curtain_drop": curtain["frame"], "lights_on": lights["frame"],
                       "perspective": perspective["frame"], "perspective_end": perspective_end},
        "curtain_sections": [[0, curtain["frame"], p["curtain_hold_offset_ticks"], p["curtain_hold_offset_ticks"] + 1],
                             [curtain["frame"], curtain["frame"] + p["curtain_fall_frames"],
                              p["curtain_hold_offset_ticks"], 0],
                             [curtain["frame"] + p["curtain_fall_frames"], end + 1,
                              p["curtain_pile_offset_ticks"], p["curtain_pile_offset_ticks"] + 1]],
        "perspective_keys": [[0, p["perspective_start_mm"]], [perspective["frame"], p["perspective_start_mm"]],
                             [perspective_end, p["perspective_end_mm"]], [end, p["perspective_end_mm"]]],
        "markers": marker_rows, "fixtures": fixtures,
        "disable_existing_bindings_prefix": OLD_RIG_PREFIX,
        "authority": {"show": SHOW_PATH, "attachment_owner": "first WingPair in Passage 1",
                      "sequence": "resolved from Show cue '%s'" % OPENING_LABEL},
        "params": p,
    }
    plan["digest"] = digest({k: v for k, v in plan.items() if k != "digest"})
    failures = validate_plan(plan)
    if failures:
        raise P13Error("PLAN_INVALID|" + " || ".join(failures))
    return plan


def validate_plan(plan):
    p, out = plan["params"], []
    cf = plan["cue_frames"]
    if cf["perspective_end"] >= plan["opening_end_frame"]:
        out.append("PERSPECTIVE_PAST_END")
    if cf["lights_on"] > cf["perspective"]:
        out.append("LIGHTS_AFTER_PERSPECTIVE")
    if plan["curtain_sections"][1][1] >= plan["opening_end_frame"]:
        out.append("CURTAIN_NOT_LANDED")
    labels = [f["label"] for f in plan["fixtures"]]
    if len(labels) != len(set(labels)) or len(labels) != p["spot_count"] + 2:
        out.append("FIXTURE_LABELS")
    for fx in plan["fixtures"]:
        if fx["inner_cone_deg"] >= fx["outer_cone_deg"]:
            out.append("CONE|" + fx["label"])
        if fx["falloff_exponent"] < 8.0:
            out.append("FALLOFF|" + fx["label"])
        frames = [row[0] for row in fx["intensity_keys"]]
        if frames != sorted(frames):
            out.append("INTENSITY_ORDER|" + fx["label"])
    if p["curtain_flurry_index"] == 2:
        out.append("" if p["curtain_flurry_index"] == p["lights_on_flurry_index"] else "CUE_LIST_INDEX_DRIFT")
    return [x for x in out if x]


def preflight_refusals(mode, state):
    out = []
    if mode not in MODES or state.get("confirm") != "%s P13" % mode:
        out.append("CONFIRM_MISMATCH")
    if state.get("pie"):
        out.append("PIE_OR_SIE_ACTIVE")
    if not state.get("world_ok"):
        out.append("WRONG_WORLD")
    if state.get("sequencer_open"):
        out.append("SEQUENCER_IS_OPEN")
    if state.get("census") != {"content": [], "maps": []}:
        out.append("DIRTY_CENSUS|%r" % state.get("census"))
    if state.get("zz"):
        out.append("ZZ_ACTORS_PRESENT")
    rec = state.get("record")
    if mode in ("DRY", "APPLY") and rec is not None:
        out.append("RECORD_EXISTS")
    if mode == "REVERT" and not (rec and rec.get("status") == "saved_readback_verified"):
        out.append("NOTHING_TO_REVERT")
    return out


def load_envelope(path=None):
    root = _project_root()
    candidates = []
    if path:
        candidates.append(path if os.path.isabs(path) else os.path.join(root, path))
    derived = os.path.join(root, P11_GLOB_HINT)
    if os.path.isdir(derived):
        for name in sorted(os.listdir(derived)):
            if name.lower().endswith(".json") and ("opening" in name.lower() or "p01" in name.lower()):
                candidates.append(os.path.join(derived, name))
    candidates.append(os.path.join(root, ANALYSIS_FALLBACK))
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        data = load_json(candidate)
        curves = data.get("featureCurves", {}).get("curves", {})
        values = curves.get("intensity") or data.get("rms_envelope") or data.get("envelope")
        rate = data.get("featureCurves", {}).get("rateHz") or data.get("rate_hz") or 25.0
        duration = data.get("durationSeconds") or data.get("duration_s")
        if isinstance(values, list) and values:
            return {"source": os.path.relpath(candidate, root).replace("\\", "/"), "rate_hz": float(rate),
                    "duration_s": float(duration or len(values) / float(rate)), "values": [float(v) for v in values]}
    return {"source": "none", "rate_hz": 1.0, "duration_s": DEFAULTS["opening_end_s"], "values": [0.0, 0.0]}


def _draw_arrow(draw, a, b, color, width=3):
    draw.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for d in (-0.45, 0.45):
        draw.line([b, (b[0] - 10 * math.cos(ang + d), b[1] - 10 * math.sin(ang + d))], fill=color, width=width)


def write_rig_diagram(path, plan, size=(1400, 800)):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", size, (16, 18, 22)); draw = ImageDraw.Draw(image); font = ImageFont.load_default()
    w, h = size; mid = w // 2
    draw.text((25, 18), "P13 OPENING LIGHTING - TOP / FRONT PROPOSAL", fill=(240, 220, 178), font=font)
    draw.text((25, 42), "Show-owned spots; cones schematic, creative values remain args", fill=(165, 172, 184), font=font)
    # top panel: x horizontal, y vertical
    top = (30, 80, mid - 20, h - 40); front = (mid + 20, 80, w - 30, h - 40)
    for box, title in ((top, "TOP - aims travel from edge pools into centre"), (front, "FRONT - upper-corner flurry accents")):
        draw.rectangle(box, outline=(80, 88, 100), width=2); draw.text((box[0] + 10, box[1] + 8), title, fill=(215, 218, 224), font=font)
    def top_xy(v):
        return (top[0] + 40 + (v[0] + 1900) / 2400 * (top[2] - top[0] - 80),
                (top[1] + top[3]) / 2 + v[1] / 2400 * (top[3] - top[1] - 90))
    draw.line([top_xy([-1800, 0, 0]), top_xy([500, 0, 0])], fill=(80, 80, 86), width=2)
    for fx in plan["fixtures"]:
        if fx["role"] != "moving_spot":
            continue
        o, s, e = top_xy(fx["world_location_cm"]), top_xy(fx["start_target_cm"]), top_xy(fx["end_target_cm"])
        draw.ellipse([o[0]-5,o[1]-5,o[0]+5,o[1]+5], fill=(255,190,85)); _draw_arrow(draw,o,s,(105,150,220),2); _draw_arrow(draw,o,e,(255,190,85),3)
        z_mid=(plan["params"]["fixture_low_z_cm"]+plan["params"]["fixture_high_z_cm"])/2.0
        label_dy=-18 if fx["world_location_cm"][2] <= z_mid else 7
        draw.text((o[0]+7,o[1]+label_dy), fx["label"].split()[-1], fill=(220,220,225), font=font)
    draw.text((top[0]+12,top[3]-24), "blue=start aim   amber=end/centre aim", fill=(150,160,176), font=font)
    def front_yz(v):
        return (front[0] + (v[1] + 1250) / 2500 * (front[2] - front[0]),
                front[3] - 35 - v[2] / 1450 * (front[3] - front[1] - 75))
    draw.line([front_yz([0,-900,0]), front_yz([0,900,0])], fill=(100,90,75), width=5)
    for fx in plan["fixtures"]:
        o, e = front_yz(fx["world_location_cm"]), front_yz(fx["end_target_cm"])
        col = (255,122,72) if fx["role"] == "corner_pulse" else (255,190,85)
        draw.ellipse([o[0]-6,o[1]-6,o[0]+6,o[1]+6], fill=col); _draw_arrow(draw,o,e,col,2)
        draw.text((o[0]+8,o[1]-7), fx["label"].replace("P13 Opening ", ""), fill=(225,225,228), font=font)
    draw.text((front[0]+12,front[3]-24), "orange=corner pulse   amber=tight moving pool", fill=(150,160,176), font=font)
    os.makedirs(os.path.dirname(path), exist_ok=True); image.save(path)
    return {"path": path, "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(), "size": list(size)}


def write_timeline(path, plan, envelope, size=(1600, 700)):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", size, (15, 17, 21)); draw = ImageDraw.Draw(image); font = ImageFont.load_default()
    w, h = size; x0, x1, y0, y1 = 180, w - 35, 80, 380; duration = plan["opening_end_frame"] / plan["fps"]
    draw.text((25, 18), "P13 OPENING CUE TIMELINE OVER MUSIC INTENSITY", fill=(240,220,178), font=font)
    draw.text((25, 42), "Envelope: %s (not P11 unless that path says DerivedAssets/MusicAnalysis)" % envelope["source"], fill=(165,172,184), font=font)
    vals, rate = envelope["values"], envelope["rate_hz"]
    pts=[]
    for i,v in enumerate(vals):
        t=i/rate
        if t>duration: break
        pts.append((x0+t/duration*(x1-x0), y1-max(0,min(1,v))*(y1-y0)))
    if len(pts)>1: draw.line(pts, fill=(78,145,210), width=2)
    draw.rectangle((x0,y0,x1,y1), outline=(80,88,100), width=2)
    for sec in range(0,int(duration)+1,10):
        x=x0+sec/duration*(x1-x0); draw.line((x,y1,x,y1+7),fill=(120,125,135)); draw.text((x-8,y1+10),str(sec),fill=(150,155,165),font=font)
    colors={"curtain_drop":(235,92,92),"lights_on":(255,190,85),"perspective":(177,132,255)}
    for key in ("curtain_drop","lights_on","perspective"):
        fr=plan["cue_frames"][key]; x=x0+(fr/plan["fps"])/duration*(x1-x0)
        draw.line((x,y0,x,h-55),fill=colors[key],width=3); draw.text((x+5, y0+12+22*list(colors).index(key)), key.replace("_"," "), fill=colors[key],font=font)
    for fl in plan["flurries"]:
        x=x0+fl["seconds"]/duration*(x1-x0); draw.ellipse((x-5,y1+52,x+5,y1+62),fill=(245,245,245)); draw.text((x-22,y1+68),"flurry %d"%fl["index"],fill=(210,210,215),font=font)
    lanes=[("MOVING SPOTS",(255,190,85)),("CORNER PULSES",(255,122,72)),("CURTAIN FALL",(235,92,92)),("FOCAL 15->25 mm",(177,132,255))]
    base=y1+125
    for i,(label,col) in enumerate(lanes): draw.text((25,base+i*45),label,fill=col,font=font)
    lx0=x0
    l_on=lx0+(plan["cue_frames"]["lights_on"]/plan["fps"])/duration*(x1-lx0)
    l_end=lx0+(plan["opening_end_frame"]/plan["fps"])/duration*(x1-lx0)
    draw.rectangle((l_on,base-2,l_end,base+12),fill=lanes[0][1])
    for fl in plan["flurries"]:
        x=lx0+fl["seconds"]/duration*(x1-lx0); draw.rectangle((x-3,base+43,x+7,base+57),fill=lanes[1][1])
    c=lx0+(plan["cue_frames"]["curtain_drop"]/plan["fps"])/duration*(x1-lx0); ce=lx0+((plan["cue_frames"]["curtain_drop"]+plan["params"]["curtain_fall_frames"])/plan["fps"])/duration*(x1-lx0)
    draw.rectangle((c,base+88,ce,base+102),fill=lanes[2][1])
    ps=lx0+(plan["cue_frames"]["perspective"]/plan["fps"])/duration*(x1-lx0); pe=lx0+(plan["cue_frames"]["perspective_end"]/plan["fps"])/duration*(x1-lx0)
    draw.rectangle((ps,base+133,pe,base+147),fill=lanes[3][1])
    os.makedirs(os.path.dirname(path),exist_ok=True); image.save(path)
    return {"path":path,"sha256":hashlib.sha256(open(path,"rb").read()).hexdigest(),"size":list(size),"envelope":envelope["source"]}


# ------------------------------- Unreal-only helpers -------------------------------
def _stop(run, message):
    if unreal is not None:
        unreal.log_error("P13_OPENING_LIGHTING_FAILED|run=%s|%s" % (run, message))
    raise P13Error(message)


def _guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).upper()


def _enum(enum_type, name):
    for candidate in (name, name.upper(), name.lower()):
        if hasattr(enum_type, candidate): return getattr(enum_type, candidate)
    raise P13Error("ENUM|%s.%s" % (enum_type, name))


def _census():
    return {"content": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _context(mode, confirm, run):
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); world=editor.get_editor_world()
    record=load_json(os.path.join(_here(),RECORD_NAME))
    state={"confirm":confirm,"pie":editor.get_game_world() is not None,
           "world_ok":world is not None and str(world.get_outermost().get_name())==LEVEL_PATH,
           "sequencer_open":unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
           "census":_census(),"zz":any(str(a.get_actor_label()).startswith("ZZ_") for a in _actors()),"record":record}
    refusals=preflight_refusals(mode,state)
    if refusals:_stop(run,"REFUSED|"+" || ".join(refusals))
    show=unreal.load_asset(SHOW_PATH)
    if show is None:_stop(run,"SHOW_LOAD")
    cues=list(show.get_editor_property("cues")); opening=[c for c in cues if str(c.get_editor_property("label"))==OPENING_LABEL]
    if len(opening)!=1:_stop(run,"OPENING_CUE_COUNT|%d"%len(opening))
    seq=opening[0].get_editor_property("scene").get_editor_property("sequence")
    if seq is None:_stop(run,"OPENING_SEQUENCE_NULL")
    passages=[p for p in show.get_editor_property("passages") if str(p.get_editor_property("label"))==P01_LABEL]
    if len(passages)!=1:_stop(run,"P01_PASSAGE_COUNT|%d"%len(passages))
    first=_guid(passages[0].get_editor_property("first_cue_guid")); targets=[(i,c) for i,c in enumerate(cues) if _guid(c.get_editor_property("cue_guid"))==first]
    if len(targets)!=1:_stop(run,"P01_FIRST_CUE_COUNT|%d"%len(targets))
    return show,seq,targets[0][0],targets[0][1],record


def _pair_attachments(cue):
    return list(cue.get_editor_property("wing_pair").get_editor_property("attachments"))


def _set_pair_attachments(show,index,attachments):
    cues=list(show.get_editor_property("cues")); cue=cues[index]; pair=cue.get_editor_property("wing_pair")
    pair.set_editor_property("attachments",list(attachments)); cue.set_editor_property("wing_pair",pair); cues[index]=cue
    show.modify(); show.set_editor_property("cues",cues)


def _is_light(att):
    return "LIGHT" in str(att.get_editor_property("kind")).upper()


def _transform(row):
    r=row["start_rotation_rpy_deg"]
    return unreal.Transform(location=unreal.Vector(*row["relative_location_cm"]),rotation=unreal.Rotator(roll=r[0],pitch=r[1],yaw=r[2]),scale=unreal.Vector(1,1,1))


def _blank_light():
    a=unreal.InfinityCueAttachment(); a.set_editor_property("label",unreal.Text("P13 GUID SCRATCH")); a.set_editor_property("kind",_enum(unreal.InfinityAttachmentKind,"LIGHT")); a.set_editor_property("enabled",False); a.set_editor_property("anchor",_enum(unreal.InfinityAttachmentAnchor,"STATION")); return a


def _light(row):
    a=unreal.InfinityCueAttachment(); a.set_editor_property("label",unreal.Text(row["label"])); a.set_editor_property("kind",_enum(unreal.InfinityAttachmentKind,"LIGHT")); a.set_editor_property("enabled",True); a.set_editor_property("anchor",_enum(unreal.InfinityAttachmentAnchor,"STATION")); a.set_editor_property("relative_transform",_transform(row))
    s=unreal.InfinityStageLightSettings(); s.set_editor_property("type",_enum(unreal.InfinityStageLightType,"SPOT")); s.set_editor_property("intensity_units",_enum(unreal.InfinityStageLightIntensityUnits,"CANDELAS")); s.set_editor_property("intensity",float(row["intensity_cd"])); rgb=row["color_rgb_linear"]; s.set_editor_property("color",unreal.LinearColor(rgb[0],rgb[1],rgb[2],1)); s.set_editor_property("use_temperature",True); s.set_editor_property("temperature_kelvin",float(row["temperature_kelvin"])); s.set_editor_property("attenuation_radius_cm",float(row["attenuation_cm"])); s.set_editor_property("cast_shadows",bool(row["cast_shadows"])); s.set_editor_property("cast_volumetric_shadow",bool(row["cast_volumetric_shadows"])); s.set_editor_property("volumetric_scattering_intensity",float(row["volumetric_scattering"])); s.set_editor_property("use_inverse_squared_falloff",False); s.set_editor_property("light_falloff_exponent",float(row["falloff_exponent"])); s.set_editor_property("source_radius_cm",float(row["source_radius_cm"])); s.set_editor_property("soft_source_radius_cm",float(row["soft_source_radius_cm"])); s.set_editor_property("inner_cone_angle_degrees",float(row["inner_cone_deg"])); s.set_editor_property("outer_cone_angle_degrees",float(row["outer_cone_deg"])); a.set_editor_property("lighting",s); return a


def _overwrite(vessel,template):
    gid=_guid(vessel.get_editor_property("attachment_guid"))
    for name in ("label","kind","enabled","actor_class","mesh","anchor","relative_transform","lighting","effect","trigger_distance_cm","body","mover"):
        vessel.set_editor_property(name,template.get_editor_property(name))
    if _guid(vessel.get_editor_property("attachment_guid"))!=gid:raise P13Error("GUID_CHANGED")
    return vessel


def _mint(show,target_index,plan,run):
    cues=list(show.get_editor_property("cues")); original=_pair_attachments(cues[target_index]); existing=sum(_is_light(a) for a in original)
    candidates=[(i,c) for i,c in enumerate(cues) if i!=target_index and "WING_PAIR" in str(c.get_editor_property("type")).upper()]
    if not candidates:_stop(run,"SCRATCH_CUE_MISSING")
    scratch_index,scratch=candidates[-1]; scratch_original=_pair_attachments(scratch); scratch_lights=sum(_is_light(a) for a in scratch_original); needed=existing+len(plan["fixtures"]); padding=max(0,needed-scratch_lights)
    pre={_guid(a.get_editor_property("attachment_guid")) for c in cues for a in _pair_attachments(c)}
    _set_pair_attachments(show,scratch_index,scratch_original+[_blank_light() for _ in range(padding)])
    fresh=list(show.get_editor_property("cues")); changed=show.replicate_light_attachments(fresh[scratch_index].get_editor_property("cue_guid"),[fresh[target_index].get_editor_property("cue_guid")])
    _set_pair_attachments(show,scratch_index,scratch_original)
    if int(changed)!=1:_stop(run,"REPLICATE_COUNT|%s"%changed)
    replicated=_pair_attachments(list(show.get_editor_property("cues"))[target_index]); vessels=[a for a in replicated if _is_light(a)]
    if len(vessels)<needed:_stop(run,"MINTED_SLOT_COUNT|%d<%d"%(len(vessels),needed))
    added=[]
    for vessel,row in zip(vessels[existing:needed],plan["fixtures"]):
        if _guid(vessel.get_editor_property("attachment_guid")) in pre:_stop(run,"GUID_NOT_FRESH")
        added.append(_overwrite(vessel,_light(row)))
    _set_pair_attachments(show,target_index,original+added)
    return [{"guid":_guid(a.get_editor_property("attachment_guid")),"label":str(a.get_editor_property("label"))} for a in added]


def _package_file(package):
    root=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()); base=os.path.join(root,package[len('/Game/'):].replace('/',os.sep))
    for ext in ('.uasset','.umap'):
        if os.path.isfile(base+ext):return base+ext
    raise P13Error("PACKAGE_FILE_MISSING|"+package)


def _backup(packages,run,label="PreP13OpeningLighting-"):
    root=os.path.join(_project_root(),"Backups",label+run); os.makedirs(root,exist_ok=False); rows=[]
    for package in packages:
        src=_package_file(package); dst=os.path.join(root,package[len('/Game/'):].replace('/',os.sep)+os.path.splitext(src)[1]); os.makedirs(os.path.dirname(dst),exist_ok=True); shutil.copy2(src,dst)
        a=hashlib.sha256(open(src,'rb').read()).hexdigest(); b=hashlib.sha256(open(dst,'rb').read()).hexdigest()
        if a!=b:_stop(run,"BACKUP_HASH|"+package)
        rows.append({"package":package,"source":src,"backup":dst,"sha256":a})
    return {"root":root,"packages":rows}


def _find_binding(seq,name):
    rows=[b for b in seq.get_bindings() if str(b.get_display_name())==name]
    if len(rows)!=1:raise P13Error("BINDING_COUNT|%s|%d"%(name,len(rows)))
    return rows[0]


def _channel_state(channel):
    default=channel.get_default(); return {"name":str(channel.channel_name),"default":None if default is None else float(default),"keys":[[int(k.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value),float(k.get_value())] for k in channel.get_keys()]}


def _section_state(section):
    return {"range":[section.get_start_frame(),section.get_end_frame()],"channels":[_channel_state(c) for c in section.get_all_channels()]}


def _spawn_state(binding):
    tracks=[t for t in binding.get_tracks() if t.get_class().get_name()=="MovieSceneSpawnTrack"]
    return [] if not tracks else [_section_state(s) for s in tracks[0].get_sections()]


def _gc(seq):
    rows=[]
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if t.get_class().get_name()=="MovieSceneGeometryCacheTrack":
                secs=sorted(t.get_sections(),key=lambda s:s.get_start_frame())
                if len(secs)==3:
                    asset=secs[1].get_editor_property("params").get_editor_property("geometry_cache_asset")
                    rows.append((b,secs,None if asset is None else asset.get_path_name().split('.')[0]))
    if len(rows)!=1:raise P13Error("CURTAIN_GC_COUNT|%d"%len(rows))
    return rows[0]


def _gc_state(secs):
    out=[]
    for s in secs:
        p=s.get_editor_property("params"); out.append([s.get_start_frame(),s.get_end_frame(),p.get_editor_property("start_frame_offset").value,p.get_editor_property("end_frame_offset").value])
    return out


def _set_gc(secs,rows):
    for s,(a,b,so,eo) in zip(secs,rows):
        s.set_range(int(a),int(b)); p=s.get_editor_property("params"); p.set_editor_property("start_frame_offset",unreal.FrameNumber(int(so))); p.set_editor_property("end_frame_offset",unreal.FrameNumber(int(eo))); s.set_editor_property("params",p)


def _markers(seq):
    return [{"label":str(m.label),"frame":int(m.frame_number.value)} for m in unreal.MovieSceneSequenceExtensions.get_marked_frames(seq)]


def _set_marker(seq,label,frame_value):
    ext=unreal.MovieSceneSequenceExtensions; idx=ext.find_marked_frame_by_label(seq,label)
    if idx>=0:ext.delete_marked_frame(seq,idx)  # exact internal index, per house rule
    m=unreal.MovieSceneMarkedFrame(); m.set_editor_property("label",label); m.set_editor_property("frame_number",unreal.FrameNumber(int(frame_value))); ext.add_marked_frame_to_sequence(seq,m,unreal.MovieSceneTimeUnit.DISPLAY_RATE)


def _remove_marker(seq,label):
    ext=unreal.MovieSceneSequenceExtensions; idx=ext.find_marked_frame_by_label(seq,label)
    if idx>=0:ext.delete_marked_frame(seq,idx)


def _focal_track(seq):
    rows=[]
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if t.get_class().get_name()=="MovieSceneFloatTrack" and str(t.get_property_name())=="CurrentFocalLength":rows.append((b,t))
    if len(rows)!=1:raise P13Error("FOCAL_TRACK_COUNT|%d"%len(rows))
    return rows[0]


def _write_float_track(binding,prop,path,keys,end,display=TRACK_NAME):
    track=binding.add_track(unreal.MovieSceneFloatTrack); track.set_property_name_and_path(unreal.Name(prop),path); track.set_display_name(display); sec=track.add_section(); sec.set_range(0,end+1); ch=list(sec.get_all_channels())[0]
    for f,v in keys:ch.add_key(unreal.FrameNumber(int(f)),float(v),time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    return track


def _write_transform(binding,fx,end):
    t=binding.add_track(unreal.MovieScene3DTransformTrack); t.set_display_name(TRACK_NAME); s=t.add_section(); s.set_range(0,end+1); ch={str(c.channel_name):c for c in s.get_all_channels()}
    loc=fx["relative_location_cm"]
    for name,val in zip(("Location.X","Location.Y","Location.Z"),loc):ch[name].set_default(float(val))
    for name in ("Scale.X","Scale.Y","Scale.Z"):ch[name].set_default(1.0)
    for f,rot in fx["rotation_keys"]:
        for name,val in zip(("Rotation.X","Rotation.Y","Rotation.Z"),rot):ch[name].add_key(unreal.FrameNumber(int(f)),float(val),time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,interpolation=unreal.MovieSceneKeyInterpolation.AUTO)


def _restore_track(binding,track,snapshot):
    binding.remove_track(track); new=_write_float_track(binding,"CurrentFocalLength","CurrentFocalLength",snapshot["sections"][0]["channels"][0]["keys"],snapshot["sections"][0]["range"][1]-1,str(snapshot["display"]))
    ch=list(new.get_sections()[0].get_all_channels())[0]; default=snapshot["sections"][0]["channels"][0]["default"]
    if default is not None:ch.set_default(float(default))


def _find_materialized(added,target_cue_guid):
    want={r["guid"]:r for r in added}; found={}
    prefix="InfinityStage.Attachment.%s|"%target_cue_guid
    for actor in _actors():
        for tag in actor.get_editor_property("tags"):
            text=str(tag)
            if text.startswith(prefix) and text[len(prefix):].upper() in want:found[text[len(prefix):].upper()]=actor
    if set(found)!=set(want):raise P13Error("MATERIALIZED_P13|want=%r|found=%r"%(sorted(want),sorted(found)))
    return found


def _passage_actor(show):
    rows=[a for a in _actors() if a.get_class().get_name()=="InfinityStagePassageActor" and a.get_editor_property("show_asset")==show and str(a.get_actor_label()).startswith("Passage 01")]
    if len(rows)!=1:raise P13Error("P01_ACTOR_COUNT|%d"%len(rows))
    return rows[0]


def _bind_fixture(seq,actor,fx,run):
    if not unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq):_stop(run,"OPEN_SEQUENCE_FAILED")
    sub=unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem); ordinary=seq.add_possessable(actor)
    if ordinary is None or not ordinary.is_valid():_stop(run,"ADD_ACTOR_BINDING")
    binding=sub.convert_to_custom_binding(ordinary,unreal.InfinityStageAttachmentBinding)
    if binding is None or not binding.is_valid():_stop(run,"CUSTOM_BINDING_CONVERT|"+fx["label"])
    binding.set_display_name(fx["label"]); custom=sub.get_custom_binding_objects(binding)
    if len(custom)!=1 or not str(custom[0].get_editor_property("attachment_tag")).startswith("InfinityStage.Attachment."):_stop(run,"CUSTOM_BINDING_READBACK|"+fx["label"])
    if fx["rotation_keys"]:_write_transform(binding,fx,seq.get_playback_end())
    comps=list(actor.get_components_by_class(unreal.SpotLightComponent))
    if len(comps)!=1:_stop(run,"SPOT_COMPONENT_COUNT|"+fx["label"])
    child=seq.add_possessable(comps[0]); child.set_parent(binding); child.set_display_name(fx["label"]+" SpotLightComponent")
    _write_float_track(child,"Intensity","Intensity",fx["intensity_keys"],seq.get_playback_end())
    return {"actor_binding_guid":_guid(binding.get_id()),"component_binding_guid":_guid(child.get_id()),"tag":str(custom[0].get_editor_property("attachment_tag"))}


def _snapshot_live(seq,target_cue):
    _,secs,asset=_gc(seq); fb,ft=_focal_track(seq)
    return {"target_attachments":[{"guid":_guid(a.get_editor_property("attachment_guid")),"label":str(a.get_editor_property("label")),"enabled":bool(a.get_editor_property("enabled"))} for a in _pair_attachments(target_cue)],
            "old_rig_spawn":{str(b.get_display_name()):_spawn_state(b) for b in seq.get_bindings() if str(b.get_display_name()).startswith(OLD_RIG_PREFIX)},
            "curtain_asset":asset,"curtain_sections":_gc_state(secs),
            "focal":{"binding":str(fb.get_display_name()),"display":str(ft.get_display_name()),"sections":[_section_state(s) for s in ft.get_sections()]},
            "markers":_markers(seq)}


def _focal_keys(seq):
    unused,track=_focal_track(seq); sections=list(track.get_sections())
    if len(sections)!=1 or len(list(sections[0].get_all_channels()))!=1:raise P13Error("FOCAL_SHAPE")
    return _channel_state(list(sections[0].get_all_channels())[0])["keys"]


def _verify_saved_apply(plan,record):
    show=unreal.load_asset(SHOW_PATH); seq=unreal.load_asset(record["sequence"])
    if show is None or seq is None:raise P13Error("READBACK_LOAD")
    target=list(show.get_editor_property("cues"))[int(record["target_index"])]
    rows={( _guid(a.get_editor_property("attachment_guid")),str(a.get_editor_property("label"))) for a in _pair_attachments(target)}
    want={(r["guid"],r["label"]) for r in record["added_attachments"]}
    if not want.issubset(rows):raise P13Error("READBACK_ATTACHMENTS")
    unused,secs,asset=_gc(seq)
    if asset!=plan["params"]["curtain_cache_path"] or _gc_state(secs)!=plan["curtain_sections"]:raise P13Error("READBACK_CURTAIN")
    got=[[int(f),round(float(v),4)] for f,v in _focal_keys(seq)]; want_f=[[int(f),round(float(v),4)] for f,v in plan["perspective_keys"]]
    if got!=want_f:raise P13Error("READBACK_PERSPECTIVE|%r|%r"%(got,want_f))
    marks={(m["label"],m["frame"]) for m in _markers(seq)}
    if not set(plan["markers"]).issubset(marks):raise P13Error("READBACK_MARKERS")
    names={str(b.get_display_name()) for b in seq.get_bindings()}
    if not {f["label"] for f in plan["fixtures"]}.issubset(names):raise P13Error("READBACK_BINDINGS")
    if _census()!={"content":[],"maps":[]}:raise P13Error("READBACK_DIRTY")
    return {"attachments":len(want),"curtain":_gc_state(secs),"focal_keys":got,"markers":len(plan["markers"]),"bindings":len(plan["fixtures"])}


def _verify_saved_revert(record):
    show=unreal.load_asset(SHOW_PATH); seq=unreal.load_asset(record["sequence"])
    target=list(show.get_editor_property("cues"))[int(record["target_index"])]
    snapshot=_snapshot_live(seq,target)
    rows=[{"guid":_guid(a.get_editor_property("attachment_guid")),"label":str(a.get_editor_property("label")),"enabled":bool(a.get_editor_property("enabled"))} for a in _pair_attachments(target)]
    if rows!=record["before"]["target_attachments"]:raise P13Error("REVERT_READBACK_ATTACHMENTS")
    unused,secs,asset=_gc(seq)
    if asset!=record["before"]["curtain_asset"] or _gc_state(secs)!=record["before"]["curtain_sections"]:raise P13Error("REVERT_READBACK_CURTAIN")
    if snapshot["old_rig_spawn"]!=record["before"]["old_rig_spawn"]:raise P13Error("REVERT_READBACK_OLD_RIG")
    if snapshot["focal"]!=record["before"]["focal"]:raise P13Error("REVERT_READBACK_FOCAL")
    if _markers(seq)!=record["before"]["markers"]:raise P13Error("REVERT_READBACK_MARKERS")
    if _census()!={"content":[],"maps":[]}:raise P13Error("REVERT_READBACK_DIRTY")
    return {"attachments":len(rows),"curtain":_gc_state(secs),"markers":len(_markers(seq))}


def _disable_old_rig(seq):
    changed=[]
    for b in seq.get_bindings():
        if not str(b.get_display_name()).startswith(OLD_RIG_PREFIX):continue
        tracks=[t for t in b.get_tracks() if t.get_class().get_name()=="MovieSceneSpawnTrack"]
        if not tracks:continue
        for s in tracks[0].get_sections():
            for ch in s.get_all_channels():ch.set_default(False); [k.set_value(False) for k in ch.get_keys()]
        changed.append(str(b.get_display_name()))
    return changed


def _save(show_path,seq_path):
    census=_census(); allowed_content={show_path,seq_path}; allowed_maps={LEVEL_PATH}
    if set(census["content"])-allowed_content or set(census["maps"])-allowed_maps:raise P13Error("DIRTY_SCOPE|"+canonical(census))
    if not unreal.EditorAssetLibrary.save_asset(show_path,only_if_is_dirty=False):raise P13Error("SHOW_SAVE")
    if not unreal.EditorAssetLibrary.save_asset(seq_path,only_if_is_dirty=False):raise P13Error("SEQUENCE_SAVE")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():raise P13Error("LEVEL_SAVE")
    if _census()!={"content":[],"maps":[]}:raise P13Error("DIRTY_AFTER_SAVE|"+canonical(_census()))


def _report_paths(run):
    return (os.path.join(_here(),"opening_lighting_p13_%s.json"%run),os.path.join(_here(),PLAN_NAME))


def run_dry(run,args,confirm):
    show,seq,idx,target,_=_context("DRY",confirm,run); plan=build_plan(args); before=_snapshot_live(seq,target); env=load_envelope(plan["params"].get("analysis_path")); root=os.path.join(_project_root(),"DerivedAssets","OpeningLighting")
    rig=write_rig_diagram(os.path.join(root,"P13_opening_rig_top_front.png"),plan); timeline=write_timeline(os.path.join(root,"P13_opening_cue_timeline.png"),plan,env)
    report={"schema_version":1,"mode":"DRY","run":run,"apply_ready":before["curtain_asset"]==plan["params"]["curtain_cache_path"],"mutated":False,"plan":plan,"plan_digest":plan["digest"],"live_before":before,"previews":{"rig":rig,"timeline":timeline},"claims":CLAIMS,"warnings":["APPLY_NOT_RUN","VISUAL_ACCEPTANCE_PENDING","curtain_flurry_index defaults to 2 despite the prose saying final flurry; change the arg if Gary meant 3","perspective is focal-only; camera translation is untouched"]}
    out,pf=_report_paths(run); write_json(out,report); write_json(pf,{"run":run,"plan_digest":plan["digest"],"target_cue_guid":_guid(target.get_editor_property("cue_guid")),"sequence":seq.get_path_name().split('.')[0],"args":args})
    if _census()!={"content":[],"maps":[]}:_stop(run,"DRY_DIRTIED|"+canonical(_census()))
    unreal.log("P13_OPENING_LIGHTING_DRY_OK|run=%s|mutated=0|spots=%d|curtain_frame=%d|lights_frame=%d|perspective_frame=%d|report=%s"%(run,plan["params"]["spot_count"],plan["cue_frames"]["curtain_drop"],plan["cue_frames"]["lights_on"],plan["cue_frames"]["perspective"],out))


def run_apply(run,args,confirm):
    show,seq,idx,target,_=_context("APPLY",confirm,run); plan=build_plan(args); pf=load_json(os.path.join(_here(),PLAN_NAME)) or {}; target_guid=_guid(target.get_editor_property("cue_guid")); seq_path=seq.get_path_name().split('.')[0]
    if pf.get("plan_digest")!=plan["digest"] or pf.get("target_cue_guid")!=target_guid or pf.get("sequence")!=seq_path:_stop(run,"PLAN_CHANGED_SINCE_DRY")
    before=_snapshot_live(seq,target); backup=_backup([SHOW_PATH,seq_path,LEVEL_PATH],run); record_path=os.path.join(_here(),RECORD_NAME); record={"schema_version":1,"run":run,"status":"recorded_before_mutation","plan":plan,"plan_digest":plan["digest"],"show":SHOW_PATH,"sequence":seq_path,"level":LEVEL_PATH,"target_cue_guid":target_guid,"target_index":idx,"before":before,"backup":backup,"dirty_before":_census()}; write_json(record_path,record,exclusive=True)
    try:
        added=_mint(show,idx,plan,run); record["added_attachments"]=added; record["status"]="show_mutated"; write_json(record_path,record)
        passage=_passage_actor(show)
        if not bool(passage.materialize_passage()):_stop(run,"MATERIALIZE_FAILED")
        actors=_find_materialized(added,target_guid); seq.modify(); disabled=_disable_old_rig(seq)
        _,secs,asset=_gc(seq)
        if asset!=plan["params"]["curtain_cache_path"]:_stop(run,"CURTAIN_ASSET|"+str(asset))
        _set_gc(secs,plan["curtain_sections"])
        fb,ft=_focal_track(seq); focal_before=before["focal"]; fb.remove_track(ft); _write_float_track(fb,"CurrentFocalLength","CurrentFocalLength",plan["perspective_keys"],plan["opening_end_frame"])
        bindings={}
        for fx,row in zip(plan["fixtures"],added):bindings[fx["label"]]=_bind_fixture(seq,actors[row["guid"]],fx,run)
        for label,fr in plan["markers"]:_set_marker(seq,label,fr)
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
        record.update({"status":"mutated_verified_presave","disabled_old_rig":disabled,"bindings":bindings,"focal_before":focal_before,"after":_snapshot_live(seq,list(show.get_editor_property("cues"))[idx]),"dirty_presave":_census()}); write_json(record_path,record)
        want_content={SHOW_PATH,seq_path}; want_maps={LEVEL_PATH}; census=_census()
        if set(census["content"])!=want_content or set(census["maps"])!=want_maps:_stop(run,"DIRTY_PRESAVE|"+canonical(census))
        _save(SHOW_PATH,seq_path); record["saved_readback"]=_verify_saved_apply(plan,record); record["status"]="saved_readback_verified"; record["dirty_after"]=_census(); write_json(record_path,record)
        unreal.log("P13_OPENING_LIGHTING_APPLY_OK|run=%s|attachments=%d|old_rig_disabled=%d|saved=%s,%s,%s|backup=%s|record=%s"%(run,len(added),len(disabled),SHOW_PATH,seq_path,LEVEL_PATH,backup["root"],record_path))
    finally:
        if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()


def run_revert(run,confirm):
    show,seq,idx,target,record=_context("REVERT",confirm,run); seq_path=record["sequence"]
    live=_snapshot_live(seq,target)
    if digest(live)!=digest(record["after"]):_stop(run,"STATE_DRIFTED_SINCE_APPLY")
    backup=_backup([SHOW_PATH,seq_path,LEVEL_PATH],run,"PreP13OpeningLighting-Revert-"); txn=os.path.join(_here(),"opening_lighting_p13_revert_%s.json"%run); write_json(txn,{"run":run,"status":"recorded_before_mutation","source_record":os.path.join(_here(),RECORD_NAME),"backup":backup,"dirty_before":_census()},exclusive=True)
    added={r["guid"] for r in record["added_attachments"]}; current=_pair_attachments(target); live_added={_guid(a.get_editor_property("attachment_guid")) for a in current if _guid(a.get_editor_property("attachment_guid")) in added}
    if live_added!=added:_stop(run,"REVERT_ATTACHMENT_DRIFT|%r"%sorted(live_added))
    seq.modify()
    for pair in record["bindings"].values():
        for gid in (pair["component_binding_guid"],pair["actor_binding_guid"]):
            hits=[b for b in seq.get_bindings() if _guid(b.get_id())==gid]
            if len(hits)!=1:_stop(run,"REVERT_BINDING_DRIFT|"+gid)
            hits[0].remove()
    for name,specs in record["before"]["old_rig_spawn"].items():
        b=_find_binding(seq,name); tracks=[t for t in b.get_tracks() if t.get_class().get_name()=="MovieSceneSpawnTrack"]
        if len(tracks)!=1:_stop(run,"REVERT_SPAWN_TRACK|"+name)
        if len(tracks[0].get_sections())!=len(specs):_stop(run,"REVERT_SPAWN_SECTION_COUNT|"+name)
        for s,spec in zip(tracks[0].get_sections(),specs):
            s.set_range(*spec["range"]); ch=list(s.get_all_channels())[0]
            if len(ch.get_keys())!=len(spec["channels"][0]["keys"]):_stop(run,"REVERT_SPAWN_KEY_COUNT|"+name)
            ch.set_default(bool(spec["channels"][0]["default"])); [k.set_value(bool(v)) for k,(_,v) in zip(ch.get_keys(),spec["channels"][0]["keys"])]
    _,secs,_=_gc(seq); _set_gc(secs,record["before"]["curtain_sections"])
    fb,ft=_focal_track(seq); _restore_track(fb,ft,record["before"]["focal"])
    for label,_ in record["plan"]["markers"]:_remove_marker(seq,label)
    for m in record["before"]["markers"]:
        if m["label"].startswith(MARKER_PREFIX):_set_marker(seq,m["label"],m["frame"])
    _set_pair_attachments(show,idx,[a for a in current if _guid(a.get_editor_property("attachment_guid")) not in added])
    passage=_passage_actor(show)
    if not bool(passage.materialize_passage()):_stop(run,"REVERT_MATERIALIZE_FAILED")
    census=_census()
    if set(census["content"])!={SHOW_PATH,seq_path} or set(census["maps"])!={LEVEL_PATH}:_stop(run,"REVERT_DIRTY_PRESAVE|"+canonical(census))
    _save(SHOW_PATH,seq_path); readback=_verify_saved_revert(record); archived=os.path.join(_here(),RECORD_NAME)+".reverted-"+run; os.rename(os.path.join(_here(),RECORD_NAME),archived); write_json(txn,{"run":run,"status":"saved_readback_verified","source_record_archived":archived,"backup":backup,"saved_readback":readback,"dirty_after":_census()})
    unreal.log("P13_OPENING_LIGHTING_REVERT_OK|run=%s|attachments_removed=%d|saved=%s,%s,%s|backup=%s|record=%s"%(run,len(added),SHOW_PATH,seq_path,LEVEL_PATH,backup["root"],archived))


def main():
    g=globals(); mode=str(g.get("P13_MODE","DRY")).upper(); confirm=str(g.get("P13_CONFIRM", "")); args=dict(g.get("P13_ARGS") or {}); run=str(g.get("P13_RUN_ID") or datetime.datetime.now().strftime("P13OPEN-%Y%m%d-%H%M%S"))
    if mode not in MODES:_stop(run,"MODE|"+mode)
    if confirm!="%s P13"%mode:_stop(run,"CONFIRM_MISMATCH|want '%s P13'"%mode)
    if mode=="DRY":run_dry(run,args,confirm)
    elif mode=="APPLY":run_apply(run,args,confirm)
    else:run_revert(run,confirm)


if unreal is not None:
    main()
