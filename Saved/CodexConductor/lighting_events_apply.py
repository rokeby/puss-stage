"""Guarded lighting EVENTS tool: polaroid flashes, rare blinkers, black passage.

Modes: DRY (default), APPLY, REVERT. Set ``LIGHTING_EVENTS_MODE`` through
``runpy.run_path(..., init_globals={...})`` when executing in Unreal.

Mechanism (read from source, 4 Oct; see Docs/Conductor/LIGHTING_EVENTS_2026-10-04.md):

* PHASE A (built engine): a flash is ONE Show light attachment whose
  ``FInfinityStageLightDrama`` strikes over ``attack`` cm and decays at once
  (StrikeDistance = StrikeRamp = attack, AfterPass DECAY, AfterPassDistance 0,
  DecayDistance = decay). EvaluateStrike (InfinityStageLightDrama.cpp:24-60)
  peaks when the camera's route distance equals the lamp's route distance,
  Wing.DistanceCm + RelativeTransform.X (InfinityStagePassageActor.cpp:1648-1660).
  So in Phase A every flash fires from the camera's own X: lateral, high or
  floor sources at that X, never "deeper in the bay", and decay is linear.
* PHASE B (HELD patch Scripts/patches/2026-10-04_LD_flash_events.draft.patch,
  unbuilt): ``bFlash`` + ``FlashCameraOffsetsCm`` decouple the trigger from the
  lamp's X, so deep fixtures and far-visible BLINKERS become possible. The tool
  probes for the field and only emits Phase-B rows when the engine has it.

Identity: target cues are resolved ONCE by label to (index, CueGuid) from a fresh
Show read, then every check and write is keyed by GUID; added attachments are
recorded by their minted GUID. The looks tool is NOT imported in Unreal because
importing it runs its main() (lighting_looks_apply.py:1276-1277); attachment
state and differences come from _infinity_attachment_state.py (loaded fresh by
path, so a stale editor module cache cannot be used).
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness import.
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))


def _load_attachment_state():
    path = os.path.join(HERE, "_infinity_attachment_state.py")
    spec = importlib.util.spec_from_file_location("_infinity_attachment_state_events", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = _load_attachment_state()

EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
VALID_MODES = ("DRY", "APPLY", "REVERT")
CONFIG_PATH = os.path.join(HERE, "lighting_events.json")
REPORT_PATH = os.path.join(HERE, "lighting_events_report.json")
RECORD_PATH = os.path.join(HERE, "lighting_events_revert_record.json")
LOOKS_RECORD_PATH = os.path.join(HERE, "lighting_looks_revert_record.json")
LOOKS_LABEL_PREFIX = "P04 LOOK "
SOURCE_KINDS = ("CAMERA", "HIGH_L", "HIGH_R", "FLOOR_L", "FLOOR_R", "BACK_L", "BACK_R")
PHASE_B_FIELDS = ("flash", "flash_camera_offsets_cm", "flash_attack_cm",
                  "flash_decay_cm", "flash_rest_scale")


class LightingEventsError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise LightingEventsError(str(message))


def _finite(value, label):
    number = float(value)
    require(math.isfinite(number), "%s_NOT_FINITE|value=%r" % (label, value))
    return number


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _state_hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# Seeded draws. ONE draw per expression: every call below is its own statement
# whose result is bound to a name before use (memory: puss-random-draw-order).
# Draws are keyed by (seed, stream, index), so adding a stream never re-rolls
# another stream.
# --------------------------------------------------------------------------

def draw01(seed, stream, index):
    digest = hashlib.sha256(("%d|%s|%d" % (int(seed), stream, int(index))).encode("utf-8")).digest()
    return int.from_bytes(digest[:7], "big") / float(1 << 56)


def draw_range(seed, stream, index, low_high):
    u = draw01(seed, stream, index)
    low, high = float(low_high[0]), float(low_high[1])
    return low + (high - low) * u


def draw_int(seed, stream, index, low_high):
    u = draw01(seed, stream, index)
    low, high = int(low_high[0]), int(low_high[1])
    return min(high, low + int(u * (high - low + 1)))


# --------------------------------------------------------------------------
# Python mirrors of the C++ evaluation, for the harness.
# --------------------------------------------------------------------------

def _smoothstep(a, b, x):
    # FMath::SmoothStep (UE): 0 below A, 1 at/above B.
    if x < a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3.0 - 2.0 * t)


def eval_strike(drama, ahead_cm):
    """Exact port of EvaluateStrike (InfinityStageLightDrama.cpp:24-60) with
    IgnitionStutter 0 (the stutter noise needs the engine's GUID hash; every
    event lamp authors 0 and the port refuses anything else)."""
    require(float(drama.get("ignition_stutter", 0.0)) == 0.0, "PORT_NEEDS_ZERO_STUTTER")
    unstruck = min(1.0, max(0.0, float(drama["unstruck_intensity_scale"])))
    start = max(0.0, float(drama["strike_distance_cm"]))
    level = unstruck
    if ahead_cm <= start:
        progress = min(1.0, max(0.0, (start - ahead_cm) / max(1.0, float(drama["strike_ramp_cm"]))))
        level = unstruck + (1.0 - unstruck) * _smoothstep(0.0, 1.0, progress)
    past = -ahead_cm - max(0.0, float(drama["after_pass_distance_cm"]))
    if past > 0.0:
        if drama["after_pass"] == "EXTINGUISH":
            level = unstruck
        elif drama["after_pass"] == "DECAY":
            faded = min(1.0, max(0.0, past / max(1.0, float(drama["decay_distance_cm"]))))
            level = level + (unstruck - level) * faded
    return level


def eval_flash(drama, camera_past_lamp_cm):
    """Port of the HELD patch's EvaluateFlash (Phase B)."""
    rest = min(1.0, max(0.0, float(drama.get("flash_rest_scale", 0.0))))
    attack = max(0.1, float(drama["flash_attack_cm"]))
    decay = max(0.1, float(drama["flash_decay_cm"]))
    level = rest
    for offset in drama["flash_camera_offsets_cm"]:
        d = camera_past_lamp_cm - float(offset)
        pulse = 0.0
        if -attack <= d < 0.0:
            pulse = (d + attack) / attack
        elif 0.0 <= d <= decay:
            pulse = (1.0 - d / decay) ** 3
        level = max(level, pulse)
    return level


def eval_drama(drama, lamp_route_cm, camera_route_cm):
    """Port of InfinityStageLightDrama::Evaluate's intensity scale (+ patch)."""
    scale = 1.0
    if drama.get("strike_on_approach"):
        scale = eval_strike(drama, lamp_route_cm - camera_route_cm)
    if drama.get("flash"):
        scale *= eval_flash(drama, camera_route_cm - lamp_route_cm)
    return scale


def drama_active(drama):
    return bool(drama.get("strike_on_approach") or drama.get("slow_move") or drama.get("flash"))


# --------------------------------------------------------------------------
# Config and schedule.
# --------------------------------------------------------------------------

def load_config(path=CONFIG_PATH):
    data = _read_json(path)
    validate_config(data)
    return data


def _vec3(value, label):
    require(isinstance(value, list) and len(value) == 3, label + "_NOT_VEC3")
    return [_finite(v, label) for v in value]


def validate_config(data):
    require(data.get("schema_version") == 1, "CONFIG_SCHEMA_NOT_1")
    require(str(data.get("label_prefix", "")).startswith("P04 EVT"), "LABEL_PREFIX_WRONG")
    require(not str(data["label_prefix"]).startswith(LOOKS_LABEL_PREFIX.strip()),
            "LABEL_PREFIX_CLASHES_WITH_LOOKS")
    re.compile(data["passage"]["cue_label_regex"])
    int(data["seed"])
    camera = data["camera"]
    require(_finite(camera["nominal_speed_cm_s"], "SPEED") > _finite(camera["min_speed_cm_s"], "MIN_SPEED") > 0.0,
            "CAMERA_SPEED_BELOW_MINIMUM")
    require(_finite(camera["fps"], "FPS") >= 24.0, "FPS_TOO_LOW")
    require(_finite(data["nominal_bay_spacing_cm"], "SPACING") > 0.0, "SPACING_BAD")
    require(0.0 < _finite(data["bay_spacing_tolerance"], "SPACING_TOL") < 0.5, "SPACING_TOL_BAD")
    profile = data["flash_profile"]
    require(0.5 <= _finite(profile["attack_frames"], "ATTACK") <= 2.0, "ATTACK_NOT_1_TO_2_FRAMES")
    require(0.2 <= _finite(profile["decay_seconds"], "DECAY") <= 0.4, "DECAY_NOT_0_2_TO_0_4_S")
    require(set(data["sources"]) == set(SOURCE_KINDS), "SOURCE_SET_WRONG")
    for name, source in data["sources"].items():
        require(source["type"] in ("SPOT", "POINT"), "SOURCE_TYPE_BAD|" + name)
        _vec3(source["offset_cm"], "SOURCE_OFFSET")
        _vec3(source["aim_cm"], "SOURCE_AIM")
        require(_finite(source["intensity_cd"], "SOURCE_INTENSITY") > 0.0, "SOURCE_INTENSITY_BAD|" + name)
        require(1000.0 <= _finite(source["temperature_kelvin"], "SOURCE_K") <= 15000.0, "SOURCE_K_BAD|" + name)
        require(0.0 <= _finite(source["inner_cone_deg"], "INNER") <= _finite(source["outer_cone_deg"], "OUTER") <= 89.0,
                "SOURCE_CONE_BAD|" + name)
        require(_finite(source["attenuation_cm"], "ATTEN") > 0.0, "SOURCE_ATTEN_BAD|" + name)
    black = data["black_mode"]
    require(isinstance(black["gary_approved"], bool), "BLACK_APPROVAL_UNDECLARED")
    glimmer = black["glimmer"]
    require(0.0 < _finite(glimmer["intensity_cd"], "GLIMMER") <= _finite(glimmer["max_intensity_cd"], "GLIMMER_MAX") <= 25.0,
            "GLIMMER_ABOVE_CAP")
    sequence = black["sequence"]
    low, high = sequence["flashes_per_burst"]
    require(2 <= int(low) <= int(high) <= 5, "BURST_SIZE_NOT_2_TO_5")
    require(float(sequence["dark_gap_s"][0]) >= 3.0, "DARK_GAP_TOO_SHORT")
    require(float(sequence["intra_gap_s"][0]) >= 0.08, "INTRA_GAP_TOO_SHORT")
    require(0.0 <= float(sequence["camera_share"]) <= 1.0, "CAMERA_SHARE_BAD")
    require(set(sequence["fixture_sources"]).issubset(set(SOURCE_KINDS) - {"CAMERA"}),
            "FIXTURE_SOURCES_BAD")
    blink = data["blinkers"]
    require(blink["requires"] == "drama_flash", "BLINKER_REQUIREMENT_UNDECLARED")
    require(_finite(blink["min_gap_s"], "BLINK_MIN_GAP") >= 1.0, "BLINK_MIN_GAP_TOO_SHORT")
    require(_finite(blink["mean_gap_s"], "BLINK_MEAN_GAP") >= 2.0 * float(blink["min_gap_s"]),
            "BLINK_MEAN_GAP_TOO_REGULAR")
    require(0.0 <= _finite(blink["rest_scale"], "BLINK_REST") <= 0.05, "BLINK_REST_TOO_BRIGHT")
    require(data["shadow_budget"]["rule"] == "after_lte_before", "SHADOW_RULE_WRONG")
    require(isinstance(data["conflicts"]["allow_over_looks_prototype"], bool), "CONFLICT_POLICY_UNDECLARED")


def cm_per_s(config):
    return float(config["camera"]["nominal_speed_cm_s"])


def flash_attack_cm(config):
    return max(1.0, float(config["flash_profile"]["attack_frames"]) / float(config["camera"]["fps"]) * cm_per_s(config))


def flash_decay_cm(config):
    return float(config["flash_profile"]["decay_seconds"]) * cm_per_s(config)


def phase_a_drama(config):
    attack = flash_attack_cm(config)
    return {
        "strike_on_approach": True, "strike_distance_cm": attack, "strike_ramp_cm": attack,
        "ignition_stutter": 0.0, "unstruck_intensity_scale": 0.0, "after_pass": "DECAY",
        "after_pass_distance_cm": 0.0, "decay_distance_cm": flash_decay_cm(config),
        "slow_move": False,
    }


def phase_b_drama(config, offsets, attack_cm=None, decay_cm=None, rest=0.0):
    return {
        "strike_on_approach": False, "slow_move": False, "flash": True,
        "flash_camera_offsets_cm": [float(v) for v in offsets],
        "flash_attack_cm": float(attack_cm if attack_cm is not None else flash_attack_cm(config)),
        "flash_decay_cm": float(decay_cm if decay_cm is not None else flash_decay_cm(config)),
        "flash_rest_scale": float(rest),
    }


def black_schedule(config):
    """Seeded flash train over the black bays, in camera route distance (cm)
    relative to the FIRST black bay's station. Returns list of event dicts."""
    black = config["black_mode"]
    sequence = black["sequence"]
    seed = int(config["seed"])
    spacing = float(config["nominal_bay_spacing_cm"])
    v = cm_per_s(config)
    bays = [int(b) for b in black["bays"]]
    start_cm = -0.5 * spacing
    end_cm = (len(bays) - 0.5) * spacing
    first_gap = draw_range(seed, "black.first_gap", 0, sequence["first_gap_s"])
    position = start_cm + first_gap * v
    events = []
    burst = 0
    while position < end_cm:
        size = draw_int(seed, "black.burst_size", burst, sequence["flashes_per_burst"])
        for k in range(size):
            if k:
                gap = draw_range(seed, "black.intra_gap", len(events), sequence["intra_gap_s"])
                position += gap * v
            if position >= end_cm:
                break
            which = draw01(seed, "black.source_is_camera", len(events))
            if which < float(sequence["camera_share"]):
                source = "CAMERA"
            else:
                pick = draw_int(seed, "black.fixture", len(events),
                                [0, len(sequence["fixture_sources"]) - 1])
                source = sequence["fixture_sources"][pick]
            scale = draw_range(seed, "black.intensity", len(events), sequence["intensity_scale"])
            events.append({"index": len(events), "burst": burst, "source": source,
                           "camera_cm": position, "intensity_scale": scale})
        dark = draw_range(seed, "black.dark_gap", burst, sequence["dark_gap_s"])
        position += dark * v
        burst += 1
    return events


def blink_schedule(config, bay_index, blinker_index=0):
    """Seeded camera offsets (relative to the lamp) at which a blinker fires.
    Exponential gaps above a floor: a Poisson-like train, never periodic."""
    blink = config["blinkers"]
    seed = int(config["seed"])
    v = cm_per_s(config)
    window = [float(blink["window_cm"][0]), float(blink["window_cm"][1])]
    stream = "blink.%02d.%d" % (int(bay_index), int(blinker_index))
    offsets = []
    position = window[0]
    i = 0
    while True:
        u = draw01(seed, stream, i)
        gap_s = float(blink["min_gap_s"]) + (-math.log(1.0 - u)) * (float(blink["mean_gap_s"]) - float(blink["min_gap_s"]))
        position += gap_s * v
        i += 1
        if position > window[1]:
            break
        offsets.append(position)
    return offsets


# --------------------------------------------------------------------------
# Plan (pure; runs offline against plain cue rows, and in Unreal on a fresh read).
# --------------------------------------------------------------------------

def _plain_is_light(att):
    return str(att.get("kind", "")).upper().endswith("LIGHT")


def _plain_casts(att):
    return _plain_is_light(att) and bool(att.get("enabled", True)) and bool(
        att.get("lighting", {}).get("cast_shadows", False))


def _look_at_rpy(source, target):
    dx, dy, dz = (float(t) - float(s) for s, t in zip(source, target))
    horizontal = math.hypot(dx, dy)
    require(horizontal > 1.0e-6 or abs(dz) > 1.0e-6, "AIM_ZERO_VECTOR")
    return [0.0, math.degrees(math.atan2(dz, horizontal)), math.degrees(math.atan2(dy, dx))]


def _light_row(config, label, slot, bay, role, source, location, aim, intensity, drama, phase):
    return {
        "label": label, "slot": slot, "bay_index": int(bay), "role": role, "phase": phase,
        "authored_kind": "LIGHT", "type": source.get("type", "SPOT"),
        "transform": {"location_cm": [float(v) for v in location],
                      "rotation_rpy_deg": _look_at_rpy(location, aim)},
        "aim_cm": [float(v) for v in aim],
        "intensity_units": "CANDELAS", "intensity": float(intensity),
        "color_rgb_linear": list(source["color_rgb_linear"]),
        "temperature_kelvin": float(source["temperature_kelvin"]),
        "attenuation_cm": float(source["attenuation_cm"]),
        "inner_cone_deg": float(source.get("inner_cone_deg", 30.0)),
        "outer_cone_deg": float(source.get("outer_cone_deg", 50.0)),
        "source_radius_cm": float(source.get("source_radius_cm", 1.0)),
        "cast_shadows": bool(source.get("cast_shadows", False)),
        "volumetric_scattering": float(source.get("volumetric_scattering", 0.0)),
        "drama": drama,
    }


def _bay_and_x(camera_cm, bays, spacing):
    slot = int(math.floor(camera_cm / spacing + 0.5))
    slot = min(len(bays) - 1, max(0, slot))
    return bays[slot], camera_cm - slot * spacing


def build_fixtures(config, capabilities, looks_dead_practicals=None):
    """All event fixtures, grouped per bay index, plus the schedule."""
    phase_b = bool(capabilities.get("drama_flash"))
    prefix = config["label_prefix"]
    spacing = float(config["nominal_bay_spacing_cm"])
    seed = int(config["seed"])
    camera = config["camera"]
    by_bay = {}
    deferred = []
    schedule = []

    black = config["black_mode"]
    if black["enabled"]:
        bays = [int(b) for b in black["bays"]]
        glimmer = black["glimmer"]
        for bay in bays:
            by_bay.setdefault(bay, []).append(_light_row(
                config, "%s B%02d BLACK GLIMMER" % (prefix, bay), "GLIMMER", bay, "GLIMMER",
                dict(glimmer, type="SPOT", cast_shadows=False, volumetric_scattering=0.0, source_radius_cm=2.0),
                glimmer["offset_cm"], glimmer["aim_cm"], glimmer["intensity_cd"],
                {"strike_on_approach": False, "slow_move": False}, "A"))
        for event in black_schedule(config):
            bay, x = _bay_and_x(event["camera_cm"], bays, spacing)
            source = config["sources"][event["source"]]
            offset = source["offset_cm"]
            if event["source"] == "CAMERA":
                base = [x, float(camera["lateral_cm"]) + offset[1], float(camera["height_cm"]) + offset[2]]
                aim = [x + source["aim_cm"][0], source["aim_cm"][1], source["aim_cm"][2]]
            else:
                base = [x + offset[0], offset[1], offset[2]]
                aim = [x + source["aim_cm"][0], source["aim_cm"][1], source["aim_cm"][2]]
            if phase_b:
                if event["source"] == "CAMERA":
                    depth = -float(source["phase_b_behind_lens_cm"])
                else:
                    depth = draw_range(seed, "black.depth", event["index"], source["phase_b_depth_cm"])
                location = [base[0] + depth, base[1], base[2]]
                aim = [aim[0] + depth, aim[1], aim[2]]
                drama = phase_b_drama(config, [-depth])
                phase = "B"
            else:
                location = base
                drama = phase_a_drama(config)
                phase = "A"
            label = "%s B%02d BLACK F%02d %s" % (prefix, bay, event["index"], event["source"])
            row = _light_row(config, label, "F%02d_%s" % (event["index"], event["source"]), bay,
                             "FLASH_CAMERA" if event["source"] == "CAMERA" else "FLASH_FIXTURE",
                             source, location, aim, float(source["intensity_cd"]) * event["intensity_scale"],
                             drama, phase)
            row["event"] = dict(event, bay_index=bay, peak_camera_x_cm=x)
            by_bay.setdefault(bay, []).append(row)
            schedule.append(row["event"])

    for trigger in config.get("standalone_polaroids", []):
        bay = int(trigger["bay"])
        x = float(trigger["x_cm"])
        source = config["sources"]["CAMERA"]
        location = [x, float(camera["lateral_cm"]) + source["offset_cm"][1],
                    float(camera["height_cm"]) + source["offset_cm"][2]]
        aim = [x + source["aim_cm"][0], source["aim_cm"][1], source["aim_cm"][2]]
        label = "%s B%02d POLAROID X%+05d" % (prefix, bay, int(round(x)))
        by_bay.setdefault(bay, []).append(_light_row(
            config, label, "POLAROID_%+05d" % int(round(x)), bay, "FLASH_CAMERA", source,
            location, aim, source["intensity_cd"], phase_a_drama(config), "A"))

    blink = config["blinkers"]
    if blink["enabled"]:
        for bay in [int(b) for b in blink["bays"]]:
            offsets = blink_schedule(config, bay)
            location = list((looks_dead_practicals or {}).get(bay) or blink["fallback_offset_cm"])
            anchor = "looks_dead_practical" if (looks_dead_practicals or {}).get(bay) else "fallback_offset_cm"
            source = {"type": "POINT", "color_rgb_linear": blink["color_rgb_linear"],
                      "temperature_kelvin": blink["temperature_kelvin"],
                      "attenuation_cm": blink["attenuation_cm"], "source_radius_cm": 3.0,
                      "cast_shadows": False, "volumetric_scattering": 0.3}
            v = cm_per_s(config)
            drama = phase_b_drama(
                config, offsets,
                attack_cm=max(0.5, float(blink["blink_attack_frames"]) / float(camera["fps"]) * v),
                decay_cm=float(blink["blink_decay_s"]) * v, rest=float(blink["rest_scale"]))
            row = _light_row(config, "%s B%02d BLINKER" % (prefix, bay), "BLINKER", bay, "BLINKER",
                             source, location, [location[0] + 100.0, location[1], location[2] - 50.0],
                             blink["intensity_cd"], drama, "B")
            row["blink_offsets_cm"] = offsets
            row["anchor"] = anchor
            if phase_b:
                by_bay.setdefault(bay, []).append(row)
            else:
                deferred.append({"label": row["label"], "reason": "ENGINE_LACKS_DRAMA_FLASH",
                                 "blinks": len(offsets), "offsets_cm": offsets, "anchor": anchor})
    return by_bay, schedule, deferred


def build_plain_plan(config, cues, capabilities, looks_record=None, looks_dead_practicals=None):
    """Resolve target cues (label -> index + GUID, once) and prove scope/budget."""
    validate_config(config)
    cue_guids = [str(c.get("guid", "")) for c in cues]
    require(all(cue_guids) and len(cue_guids) == len(set(cue_guids)), "CUE_GUIDS_INVALID_OR_DUPLICATE")
    att_guids = [str(a.get("guid", "")) for c in cues for a in c.get("attachments", [])]
    require(all(att_guids) and len(att_guids) == len(set(att_guids)), "ATTACHMENT_GUIDS_INVALID_OR_DUPLICATE")
    pattern = re.compile(config["passage"]["cue_label_regex"])
    passage_cues = {}
    for index, cue in enumerate(cues):
        match = pattern.match(str(cue.get("label", "")))
        if match:
            bay = int(match.group(1))
            require(bay not in passage_cues, "BAY_LABEL_DUPLICATE|bay=%d" % bay)
            passage_cues[bay] = (index, cue)

    by_bay, schedule, deferred = build_fixtures(config, capabilities, looks_dead_practicals)
    black_bays = set(int(b) for b in config["black_mode"]["bays"]) if config["black_mode"]["enabled"] else set()
    looks_targets = set()
    if looks_record and looks_record.get("status") == "saved_readback_verified":
        looks_targets = set(looks_record["plan"]["target_cue_guids"])

    targets = []
    new_labels = []
    for bay in sorted(by_bay):
        require(bay in passage_cues, "TARGET_BAY_MISSING|bay=%d" % bay)
        show_index, cue = passage_cues[bay]
        lights = [a for a in cue.get("attachments", []) if _plain_is_light(a)]
        disable = [a["guid"] for a in lights if bay in black_bays and a.get("enabled", True)]
        fixtures = by_bay[bay]
        new_labels.extend(row["label"] for row in fixtures)
        targets.append({
            "bay_index": bay, "show_index": show_index, "cue_label": cue["label"],
            "cue_guid": str(cue["guid"]), "black": bay in black_bays,
            "existing_lights": len(lights), "disable_guids": disable,
            "disabled_shadow_casters": sum(_plain_casts(a) for a in lights if a["guid"] in set(disable)),
            "fixtures": fixtures, "fixture_count": len(fixtures),
            "new_shadow_casters": sum(bool(r["cast_shadows"]) for r in fixtures),
            "carries_looks_prototype": str(cue["guid"]) in looks_targets or any(
                str(a.get("label", "")).startswith(LOOKS_LABEL_PREFIX) for a in cue.get("attachments", [])),
            "enabled_props_left": [a["guid"] for a in cue.get("attachments", [])
                                   if not _plain_is_light(a) and a.get("enabled", True)
                                   and str(a.get("kind", "")).upper().endswith("PROP")],
        })
    require(len(new_labels) == len(set(new_labels)), "NEW_LABELS_DUPLICATE")
    existing_labels = {str(a.get("label", "")) for c in cues for a in c.get("attachments", [])}
    clashes = sorted(existing_labels.intersection(new_labels))
    require(not clashes, "EVENTS_ALREADY_PRESENT|labels=" + ",".join(clashes[:5]))
    for target in targets:
        for row in target["fixtures"]:
            require(row["phase"] == "A" or capabilities.get("drama_flash"),
                    "PHASE_B_ROW_WITHOUT_ENGINE|label=" + row["label"])

    p04 = [c for _, c in passage_cues.values()]
    before = sum(_plain_casts(a) for c in p04 for a in c.get("attachments", []))
    removed = sum(t["disabled_shadow_casters"] for t in targets)
    added = sum(t["new_shadow_casters"] for t in targets)
    after = before - removed + added
    require(after <= before, "SHADOW_BUDGET_EXCEEDED|before=%d|after=%d|removed=%d|added=%d"
            % (before, after, removed, added))
    conflicts = [t["cue_label"] for t in targets if t["carries_looks_prototype"]]
    return {
        "targets": targets,
        "target_cue_guids": sorted(t["cue_guid"] for t in targets),
        "fixture_count": sum(t["fixture_count"] for t in targets),
        "schedule": schedule,
        "deferred": deferred,
        "phase": "B" if capabilities.get("drama_flash") else "A",
        "looks_conflict_cues": conflicts,
        "black_bays": sorted(black_bays),
        "shadow": {"p04_before": before, "p04_after": after, "removed": removed, "added": added},
    }


def apply_plain_state(config, cues, capabilities, looks_record=None):
    """Offline model of the mutation (GUID-keyed); used by the harness."""
    plan = build_plain_plan(config, cues, capabilities, looks_record)
    result = copy.deepcopy(cues)
    by_guid = {str(c["guid"]): c for c in result}
    record = {"targets": {}}
    for target in plan["targets"]:
        cue = by_guid[target["cue_guid"]]
        record["targets"][target["cue_guid"]] = copy.deepcopy(cue["attachments"])
        disable = set(target["disable_guids"])
        for att in cue["attachments"]:
            if att["guid"] in disable:
                att["enabled"] = False
        for row in target["fixtures"]:
            cue["attachments"].append({
                "guid": "EVT-%s-%s" % (target["cue_guid"], row["slot"]),
                "label": row["label"], "kind": "Light", "enabled": True,
                "location": list(row["transform"]["location_cm"]),
                "lighting": {"cast_shadows": row["cast_shadows"], "intensity": row["intensity"],
                             "drama": copy.deepcopy(row["drama"]), "role": row["role"]},
            })
    return result, record, plan


def revert_plain_state(cues, record):
    result = copy.deepcopy(cues)
    by_guid = {str(c["guid"]): c for c in result}
    require(set(record["targets"]).issubset(by_guid), "REVERT_TARGET_MISSING")
    for guid, attachments in record["targets"].items():
        by_guid[guid]["attachments"] = copy.deepcopy(attachments)
    return result


def outside_hash(cues, target_guids):
    keep = set(target_guids)
    return _state_hash({str(c["guid"]): c.get("attachments", []) for c in cues if str(c["guid"]) not in keep})


def light_sum(cue_rows, station_cm, camera_cm, roles=None):
    """Offline model: total candelas lit at a camera position over the given
    cues' ENABLED lights (drama evaluated by the C++ port)."""
    total = 0.0
    for cue, station in zip(cue_rows, station_cm):
        for att in cue["attachments"]:
            if not _plain_is_light(att) or not att.get("enabled", True):
                continue
            lighting = att.get("lighting", {})
            if roles is not None and lighting.get("role") not in roles:
                continue
            drama = lighting.get("drama") or {}
            lamp = station + float((att.get("location") or [0.0])[0])
            scale = eval_drama(drama, lamp, camera_cm) if drama_active(drama) else 1.0
            total += float(lighting.get("intensity", 0.0)) * scale
    return total


# --------------------------------------------------------------------------
# Unreal side. Nothing below runs offline.
# --------------------------------------------------------------------------

def _asset_id(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name()).split(".", 1)[0]
    return str(value).split(".", 1)[0]


def _guid_text(value):
    if unreal is not None:
        try:
            return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()
        except Exception:  # noqa: BLE001 - wrapper variants differ.
            pass
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def _valid_guid_text(value):
    compact = "".join(c for c in str(value).upper() if c in "0123456789ABCDEF")
    return len(compact) == 32 and any(c != "0" for c in compact)


def _enum_member(enum_type, name):
    for candidate in (name, name.upper(), name.title().replace("_", "")):
        if hasattr(enum_type, candidate):
            return getattr(enum_type, candidate)
    raise LightingEventsError("ENUM_MEMBER_MISSING|enum=%s|name=%s" % (enum_type, name))


def _dirty_census():
    return {
        "content": sorted(_asset_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(_asset_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _require_context():
    project = os.path.normcase(os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))
    require(project.rstrip("\\/") == EXPECTED_PROJECT.rstrip("\\/"), "WRONG_PROJECT|actual=" + project)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(world is not None and _asset_id(world) == EXPECTED_WORLD, "WRONG_WORLD|actual=" + str(_asset_id(world)))
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    if library is not None:
        require(library.get_current_level_sequence() is None, "SEQUENCER_IS_OPEN")
    require(_dirty_census() == {"content": [], "maps": []}, "DIRTY_BEFORE|census=" + _canonical(_dirty_census()))
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    stray = sorted(a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_"))
    require(not stray, "STRAY_ZZ_ACTORS|labels=" + ",".join(stray))
    return world


def _probe_capabilities():
    """Phase B is available only if the built engine has the patch's fields."""
    drama = unreal.InfinityStageLightDrama()
    try:
        drama.get_editor_property("flash_camera_offsets_cm")
        drama.get_editor_property("flash")
        return {"drama_flash": True}
    except Exception:  # noqa: BLE001 - property absent on the unpatched build.
        return {"drama_flash": False}


def _exposure_state(world):
    """Read-only: every unbound PPV's auto-exposure min/max. Pinned = min == max."""
    rows = []
    for volume in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PostProcessVolume):
        settings = volume.get_editor_property("settings")
        rows.append({
            "label": volume.get_actor_label(),
            "unbound": bool(volume.get_editor_property("unbound")),
            "enabled": bool(volume.get_editor_property("enabled")),
            "method": str(settings.get_editor_property("auto_exposure_method")),
            "override_min": bool(settings.get_editor_property("override_auto_exposure_min_brightness")),
            "override_max": bool(settings.get_editor_property("override_auto_exposure_max_brightness")),
            "min": float(settings.get_editor_property("auto_exposure_min_brightness")),
            "max": float(settings.get_editor_property("auto_exposure_max_brightness")),
        })
    unbound = [r for r in rows if r["unbound"] and r["enabled"]]
    pinned = (len(unbound) == 1 and unbound[0]["override_min"] and unbound[0]["override_max"]
              and abs(unbound[0]["min"] - unbound[0]["max"]) < 1.0e-6)
    return {"volumes": rows, "pinned": pinned}


def _is_light(att):
    return att.get_editor_property("kind") == _enum_member(unreal.InfinityAttachmentKind, "LIGHT")


def _rows(attachments):
    return [S.attachment_state(a, _guid_text) for a in attachments]


def _require_rows_equal(actual, expected, message):
    differences = S.state_differences(expected, actual)
    require(not differences, "%s|differences=%s" % (message, _canonical(differences[:8])))


def _pair_attachments(cue):
    return list(cue.get_editor_property("wing_pair").get_editor_property("attachments"))


def _set_pair_attachments(show, cue_index, attachments):
    cues = list(show.get_editor_property("cues"))
    cue = cues[cue_index]
    pair = cue.get_editor_property("wing_pair")
    pair.set_editor_property("attachments", list(attachments))
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _plain_cues(show):
    rows = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        attachments = []
        for att in _pair_attachments(cue):
            settings = att.get_editor_property("lighting")
            location = att.get_editor_property("relative_transform").translation
            attachments.append({
                "guid": _guid_text(att.get_editor_property("attachment_guid")),
                "label": str(att.get_editor_property("label")),
                "kind": "Light" if _is_light(att) else str(att.get_editor_property("kind")).split(".")[-1].split(":")[0],
                "enabled": bool(att.get_editor_property("enabled")),
                "location": [float(location.x), float(location.y), float(location.z)],
                "lighting": {"cast_shadows": bool(settings.get_editor_property("cast_shadows")),
                             "intensity": float(settings.get_editor_property("intensity"))},
            })
        rows.append({"show_index": index, "guid": _guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")), "attachments": attachments})
    return rows


def _all_pair_rows(show):
    return {_guid_text(c.get_editor_property("cue_guid")): _rows(_pair_attachments(c))
            for c in show.get_editor_property("cues")}


def _outside_hash_live(all_rows, target_guids):
    keep = set(target_guids)
    return _state_hash({g: r for g, r in all_rows.items() if g not in keep})


def _looks_record():
    if not os.path.isfile(LOOKS_RECORD_PATH):
        return None
    return _read_json(LOOKS_RECORD_PATH)


def _looks_dead_practicals(plain, looks_record):
    """Bay -> relative location of the looks' DEAD practical, resolved by the
    GUIDs the looks record minted (role from that record's label)."""
    if not looks_record or looks_record.get("status") != "saved_readback_verified":
        return {}
    by_guid = {a["guid"]: a for c in plain for a in c["attachments"]}
    result = {}
    for target in looks_record["plan"]["targets"]:
        for added in target.get("added", []):
            if not re.search(r" PRACTICAL_[LR]$", added["label"]):
                continue
            live = by_guid.get(added["guid"])
            if live and live["kind"] == "Light" and live["enabled"] and live["lighting"]["intensity"] == 0.0:
                result[int(target["bay_index"])] = live["location"]
    return result


def _make_transform(row):
    roll, pitch, yaw = row["transform"]["rotation_rpy_deg"]
    return unreal.Transform(location=unreal.Vector(*row["transform"]["location_cm"]),
                            rotation=unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw),
                            scale=unreal.Vector(1.0, 1.0, 1.0))


def _make_blank_light():
    att = unreal.InfinityCueAttachment()
    att.set_editor_property("label", unreal.Text("P04 EVT GUID SCRATCH"))
    att.set_editor_property("kind", _enum_member(unreal.InfinityAttachmentKind, "LIGHT"))
    att.set_editor_property("enabled", False)
    att.set_editor_property("anchor", _enum_member(unreal.InfinityAttachmentAnchor, "STATION"))
    settings = unreal.InfinityStageLightSettings()
    settings.set_editor_property("type", _enum_member(unreal.InfinityStageLightType, "SPOT"))
    settings.set_editor_property("intensity", 0.0)
    settings.set_editor_property("cast_shadows", False)
    att.set_editor_property("lighting", settings)
    return att


def _make_light(row):
    att = unreal.InfinityCueAttachment()
    att.set_editor_property("label", unreal.Text(row["label"]))
    att.set_editor_property("kind", _enum_member(unreal.InfinityAttachmentKind, "LIGHT"))
    att.set_editor_property("enabled", True)
    att.set_editor_property("anchor", _enum_member(unreal.InfinityAttachmentAnchor, "STATION"))
    att.set_editor_property("relative_transform", _make_transform(row))
    settings = unreal.InfinityStageLightSettings()
    settings.set_editor_property("type", _enum_member(unreal.InfinityStageLightType, row["type"]))
    settings.set_editor_property("intensity_units", _enum_member(unreal.InfinityStageLightIntensityUnits, "CANDELAS"))
    settings.set_editor_property("intensity", float(row["intensity"]))
    rgb = row["color_rgb_linear"]
    settings.set_editor_property("color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    settings.set_editor_property("use_temperature", True)
    settings.set_editor_property("temperature_kelvin", float(row["temperature_kelvin"]))
    settings.set_editor_property("attenuation_radius_cm", float(row["attenuation_cm"]))
    settings.set_editor_property("cast_shadows", bool(row["cast_shadows"]))
    settings.set_editor_property("cast_volumetric_shadow", False)
    settings.set_editor_property("volumetric_scattering_intensity", float(row["volumetric_scattering"]))
    settings.set_editor_property("source_radius_cm", float(row["source_radius_cm"]))
    settings.set_editor_property("soft_source_radius_cm", 0.0)
    if row["type"] == "SPOT":
        settings.set_editor_property("inner_cone_angle_degrees", float(row["inner_cone_deg"]))
        settings.set_editor_property("outer_cone_angle_degrees", float(row["outer_cone_deg"]))
    drama = settings.get_editor_property("drama")
    spec = row["drama"]
    drama.set_editor_property("strike_on_approach", bool(spec.get("strike_on_approach")))
    drama.set_editor_property("slow_move", False)
    if spec.get("strike_on_approach"):
        drama.set_editor_property("strike_distance_cm", float(spec["strike_distance_cm"]))
        drama.set_editor_property("strike_ramp_cm", float(spec["strike_ramp_cm"]))
        drama.set_editor_property("ignition_stutter", 0.0)
        drama.set_editor_property("unstruck_intensity_scale", float(spec["unstruck_intensity_scale"]))
        drama.set_editor_property("after_pass", _enum_member(unreal.InfinityLightAfterPass, spec["after_pass"]))
        drama.set_editor_property("after_pass_distance_cm", float(spec["after_pass_distance_cm"]))
        drama.set_editor_property("decay_distance_cm", float(spec["decay_distance_cm"]))
    if spec.get("flash"):  # Phase B only; the capability probe gates these rows.
        drama.set_editor_property("flash", True)
        drama.set_editor_property("flash_camera_offsets_cm", [float(v) for v in spec["flash_camera_offsets_cm"]])
        drama.set_editor_property("flash_attack_cm", float(spec["flash_attack_cm"]))
        drama.set_editor_property("flash_decay_cm", float(spec["flash_decay_cm"]))
        drama.set_editor_property("flash_rest_scale", float(spec["flash_rest_scale"]))
    settings.set_editor_property("drama", drama)
    att.set_editor_property("lighting", settings)
    return att


def _overwrite_vessel(vessel, template):
    minted = _guid_text(vessel.get_editor_property("attachment_guid"))
    require(_valid_guid_text(minted), "MINTED_GUID_INVALID|guid=" + minted)
    for name in ("label", "kind", "enabled", "actor_class", "mesh", "anchor",
                 "relative_transform", "lighting", "effect", "trigger_distance_cm"):
        vessel.set_editor_property(name, template.get_editor_property(name))
    require(_guid_text(vessel.get_editor_property("attachment_guid")) == minted, "MINTED_GUID_CHANGED")
    return vessel


def _package_file(package_path):
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    base = os.path.normpath(os.path.join(content, package_path[len("/Game/"):].replace("/", os.sep)))
    for extension in (".uasset", ".umap"):
        if os.path.isfile(base + extension):
            return base + extension
    raise LightingEventsError("PACKAGE_FILE_MISSING|package=" + package_path)


def _backup(prefix, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    root = os.path.join(project, "Backups", prefix + run)
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (SHOW_PATH, EXPECTED_WORLD):
        source = _package_file(package)
        destination = os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1])
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        digest = _sha256_file(source)
        require(digest == _sha256_file(destination), "BACKUP_HASH_MISMATCH|package=" + package)
        rows.append({"package": package, "backup": destination, "sha256": digest})
    return {"root": root, "packages": rows}


def _passage_actor(show, config):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passages = [a for a in subsystem.get_all_level_actors()
                if a.get_class().get_name() == "InfinityStagePassageActor"
                and a.get_actor_label().startswith(config["passage"]["actor_label_prefix"])
                and a.get_editor_property("show_asset") == show]
    require(len(passages) == 1, "PASSAGE_ACTOR_COUNT|count=%d" % len(passages))
    return passages[0]


def _station_spacing(show, config, plan):
    """INFERRED-API read: station world location per target bay via a Station-
    anchored attachment's anchor transform; checks straight-line spacing."""
    passage = _passage_actor(show, config)
    cues = list(show.get_editor_property("cues"))
    stations = {}
    for target in plan["targets"]:
        cue = cues[target["show_index"]]
        cue_guid = cue.get_editor_property("cue_guid")
        for att in _pair_attachments(cue):
            if att.get_editor_property("anchor") != _enum_member(unreal.InfinityAttachmentAnchor, "STATION"):
                continue
            result = passage.get_attachment_anchor_world_transform(cue_guid, att.get_editor_property("attachment_guid"))
            ok, transform = (result if isinstance(result, tuple) else (True, result))
            if ok and transform is not None:
                t = transform.translation
                stations[target["bay_index"]] = [float(t.x), float(t.y), float(t.z)]
                break
    bays = sorted(stations)
    nominal = float(config["nominal_bay_spacing_cm"])
    gaps = []
    for a, b in zip(bays, bays[1:]):
        gap = math.dist(stations[a], stations[b]) / float(b - a)
        gaps.append(gap)
        require(abs(gap - nominal) <= nominal * float(config["bay_spacing_tolerance"]),
                "BAY_SPACING_MISMATCH|bays=%d-%d|gap=%.1f|nominal=%.1f" % (a, b, gap, nominal))
    return {"stations": stations, "per_bay_gap_cm": gaps}


def _materialize(show, config):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passage = _passage_actor(show, config)
    require(bool(passage.materialize_passage()), "MATERIALIZE_FAILED")
    structures = [a for a in subsystem.get_all_level_actors()
                  if a.get_class().get_name() == "InfinityStageStructureActor"
                  and a.get_editor_property("passage") == passage]
    require(len(structures) == 1, "STRUCTURE_COUNT|count=%d" % len(structures))
    require(bool(structures[0].materialize_structure()), "STRUCTURE_REFIT_FAILED")
    return {"passage": passage.get_actor_label(), "structure": structures[0].get_actor_label()}


def _save_narrow():
    census = _dirty_census()
    require(not (set(census["content"]) - {SHOW_PATH}) and not (set(census["maps"]) - {EXPECTED_WORLD}),
            "OUT_OF_SCOPE_DIRTY_BEFORE_SAVE|census=" + _canonical(census))
    require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), "SHOW_SAVE_FAILED")
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
    require(_dirty_census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|census=" + _canonical(_dirty_census()))


def _queue_master_test(world, marker, run):
    require(_dirty_census() == {"content": [], "maps": []}, "DIRTY_BEFORE_TEST")
    unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + MASTER_TEST)
    unreal.log("%s_SAVED_MASTER_QUEUED|run=%s|test=%s|alone=true" % (marker, run, MASTER_TEST))


def _show_index_by_guid(show, cue_guid):
    matches = [i for i, c in enumerate(show.get_editor_property("cues"))
               if _guid_text(c.get_editor_property("cue_guid")) == cue_guid]
    require(len(matches) == 1, "CUE_GUID_RESOLVE_COUNT|guid=%s|count=%d" % (cue_guid, len(matches)))
    return matches[0]


def _target_current(show, target):
    index = _show_index_by_guid(show, target["cue_guid"])
    require(index == target["show_index"], "TARGET_INDEX_DRIFT|guid=%s|was=%d|now=%d"
            % (target["cue_guid"], target["show_index"], index))
    return index, _pair_attachments(list(show.get_editor_property("cues"))[index])


def _runtime_plan(show, config, capabilities):
    plain = _plain_cues(show)
    looks = _looks_record()
    plan = build_plain_plan(config, plain, capabilities, looks, _looks_dead_practicals(plain, looks))
    for target in plan["targets"]:
        unused, attachments = _target_current(show, target)
        del unused
        target["before_rows"] = _rows(attachments)
    return plan


def _mutate_apply(show, plan, config):
    """Port of the looks tool's proven GUID-minting route
    (lighting_looks_apply.py:922-1030): pad a NON-target cue of this passage with
    blank lights, replicate to the targets to mint fresh GUIDs, restore the
    scratch cue exactly, then rebuild each target as original + authored."""
    cues = list(show.get_editor_property("cues"))
    target_guids = set(plan["target_cue_guids"])
    pattern = re.compile(config["passage"]["cue_label_regex"])
    scratch = [(i, c) for i, c in enumerate(cues)
               if _guid_text(c.get_editor_property("cue_guid")) not in target_guids
               and pattern.match(str(c.get_editor_property("label")))]
    require(scratch, "SCRATCH_CUE_MISSING")
    scratch_index, scratch_cue = scratch[-1]
    scratch_original = _pair_attachments(scratch_cue)
    scratch_before = _rows(scratch_original)
    scratch_lights = sum(_is_light(a) for a in scratch_original)
    needed = max(t["existing_lights"] + t["fixture_count"] for t in plan["targets"])
    padding = max(0, needed - scratch_lights)
    preexisting = {_guid_text(a.get_editor_property("attachment_guid")) for c in cues for a in _pair_attachments(c)}
    originals = {t["show_index"]: _pair_attachments(cues[t["show_index"]]) for t in plan["targets"]}
    try:
        _set_pair_attachments(show, scratch_index, scratch_original + [_make_blank_light() for _ in range(padding)])
        fresh = list(show.get_editor_property("cues"))
        changed = show.replicate_light_attachments(
            fresh[scratch_index].get_editor_property("cue_guid"),
            [fresh[t["show_index"]].get_editor_property("cue_guid") for t in plan["targets"]])
        require(int(changed) == len(plan["targets"]), "REPLICATION_TARGET_COUNT|count=%s" % changed)
        _set_pair_attachments(show, scratch_index, scratch_original)
        _require_rows_equal(_rows(_pair_attachments(list(show.get_editor_property("cues"))[scratch_index])),
                            scratch_before, "SCRATCH_NOT_RESTORED_EXACTLY")
        added = set()
        for target in plan["targets"]:
            index, replicated = _target_current(show, target)
            vessels = [a for a in replicated if _is_light(a)]
            start, stop = target["existing_lights"], target["existing_lights"] + target["fixture_count"]
            require(len(vessels) >= stop, "MINTED_SLOT_COUNT|cue=%s|need=%d|actual=%d"
                    % (target["cue_label"], stop, len(vessels)))
            disable = set(target["disable_guids"])
            rebuilt = []
            for att in originals[index]:
                if _guid_text(att.get_editor_property("attachment_guid")) in disable:
                    att.set_editor_property("enabled", False)
                rebuilt.append(att)
            authored = []
            for vessel, row in zip(vessels[start:stop], target["fixtures"]):
                minted = _guid_text(vessel.get_editor_property("attachment_guid"))
                require(minted not in preexisting and minted not in added, "MINTED_GUID_NOT_FRESH|guid=" + minted)
                authored.append(_overwrite_vessel(vessel, _make_light(row)))
                added.add(minted)
            _set_pair_attachments(show, index, rebuilt + authored)
            target["added"] = [{"guid": _guid_text(a.get_editor_property("attachment_guid")),
                                "label": str(a.get_editor_property("label"))} for a in authored]
            target["after_rows"] = _rows(rebuilt + authored)
            require([r["label"] for r in target["added"]] == [r["label"] for r in target["fixtures"]],
                    "NEW_LABEL_ORDER_WRONG|cue=" + target["cue_label"])
        require(len(added) == plan["fixture_count"], "ADDED_GUID_COUNT|expected=%d|actual=%d"
                % (plan["fixture_count"], len(added)))
    except Exception:
        _set_pair_attachments(show, scratch_index, scratch_original)
        # Restore the wrapper copies taken before any change, with their
        # recorded enabled flags (the rebuild may have disabled some).
        for index, attachments in originals.items():
            for att in attachments:
                guid = _guid_text(att.get_editor_property("attachment_guid"))
                before = next(t for t in plan["targets"] if t["show_index"] == index)["before_rows"]
                enabled = next(r["enabled"] for r in before if r["guid"] == guid)
                if _is_light(att):
                    att.set_editor_property("enabled", bool(enabled))
            _set_pair_attachments(show, index, attachments)
        _require_rows_equal(_rows(_pair_attachments(list(show.get_editor_property("cues"))[scratch_index])),
                            scratch_before, "APPLY_ROLLBACK_SCRATCH_FAILED")
        for target in plan["targets"]:
            _require_rows_equal(_rows(_pair_attachments(list(show.get_editor_property("cues"))[target["show_index"]])),
                                target["before_rows"], "APPLY_ROLLBACK_TARGET_FAILED|cue=" + target["cue_label"])
        raise


def _verify_applied(show, plan, outside_before):
    require(_outside_hash_live(_all_pair_rows(show), plan["target_cue_guids"]) == outside_before,
            "OUTSIDE_TARGET_SCOPE_CHANGED")
    for target in plan["targets"]:
        unused, attachments = _target_current(show, target)
        del unused
        _require_rows_equal(_rows(attachments), target["after_rows"], "APPLY_READBACK_MISMATCH|cue=" + target["cue_label"])
        live = {_guid_text(a.get_editor_property("attachment_guid")): a for a in attachments}
        for guid in target["disable_guids"]:
            require(not bool(live[guid].get_editor_property("enabled")), "BLACK_LIGHT_STILL_ENABLED|guid=" + guid)


def _mutate_revert(show, record):
    plan = record["plan"]
    outside_before = _outside_hash_live(_all_pair_rows(show), plan["target_cue_guids"])
    for target in plan["targets"]:
        index, attachments = _target_current(show, target)
        _require_rows_equal(_rows(attachments), target["after_rows"], "REVERT_CURRENT_STATE_DRIFT|cue=" + target["cue_label"])
    for target in plan["targets"]:
        index, attachments = _target_current(show, target)
        added = {r["guid"] for r in target["added"]}
        before_enabled = {r["guid"]: r["enabled"] for r in target["before_rows"]}
        restored = []
        for att in attachments:
            guid = _guid_text(att.get_editor_property("attachment_guid"))
            if guid in added:
                continue
            require(guid in before_enabled, "REVERT_UNKNOWN_ATTACHMENT|guid=" + guid)
            att.set_editor_property("enabled", bool(before_enabled[guid]))
            restored.append(att)
        require(len(attachments) - len(restored) == len(added), "REVERT_REMOVE_COUNT|cue=" + target["cue_label"])
        _set_pair_attachments(show, index, restored)
        _require_rows_equal(_rows(restored), target["before_rows"], "REVERT_NOT_EXACT|cue=" + target["cue_label"])
    require(_outside_hash_live(_all_pair_rows(show), plan["target_cue_guids"]) == outside_before,
            "REVERT_OUTSIDE_TARGET_SCOPE_CHANGED")


def _run(mode):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"ok": False, "mode": mode, "run": run, "config": CONFIG_PATH}
    try:
        config = load_config()
        report["config_sha256"] = _sha256_file(CONFIG_PATH)
        world = _require_context()
        show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        capabilities = _probe_capabilities()
        report["capabilities"] = capabilities

        if mode in ("DRY", "APPLY"):
            require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS")
            exposure = _exposure_state(world)
            report["exposure"] = exposure
            plan = _runtime_plan(show, config, capabilities)
            report["spacing"] = _station_spacing(show, config, plan)
            summary = {k: plan[k] for k in ("fixture_count", "phase", "looks_conflict_cues", "black_bays", "shadow")}
            report.update(summary)
            report["deferred"] = plan["deferred"]
            report["schedule"] = plan["schedule"]
            if mode == "DRY":
                report.update({"ok": True, "plan": plan, "mutated": False, "census": _dirty_census()})
                _write_json(REPORT_PATH, report)
                unreal.log("LIGHTING_EVENTS_DRY_OK|run=%s|phase=%s|attachments=%d|deferred=%d|looks_conflicts=%d|exposure_pinned=%d|p04_shadow=%d->%d|mutated=0"
                           % (run, plan["phase"], plan["fixture_count"], len(plan["deferred"]),
                              len(plan["looks_conflict_cues"]), int(exposure["pinned"]),
                              plan["shadow"]["p04_before"], plan["shadow"]["p04_after"]))
                return report
            if config["exposure"]["require_pinned"]:
                require(exposure["pinned"], "EXPOSURE_NOT_PINNED")
            if plan["black_bays"]:
                require(config["black_mode"]["gary_approved"], "BLACK_MODE_NEEDS_GARY")
            if plan["looks_conflict_cues"]:
                require(config["conflicts"]["allow_over_looks_prototype"],
                        "TARGETS_CARRY_LOOKS_PROTOTYPE|cues=" + ",".join(plan["looks_conflict_cues"]))
            outside_before = _outside_hash_live(_all_pair_rows(show), plan["target_cue_guids"])
            backup = _backup("PreLightingEventsP04-", run)
            looks_sha = _sha256_file(LOOKS_RECORD_PATH) if os.path.isfile(LOOKS_RECORD_PATH) else None
            record = {"schema_version": 1, "status": "prepared", "run": run, "config_sha256": report["config_sha256"],
                      "backup": backup, "outside_before_hash": outside_before, "plan": plan,
                      "looks_record_sha256_at_apply": looks_sha,
                      "ordering_rule": "REVERT this record BEFORE any lighting_looks REVERT/APPLY on the same cues"}
            _write_json(RECORD_PATH, record, exclusive=True)
            try:
                _mutate_apply(show, plan, config)
            except Exception:
                record["status"] = "failed_rolled_back_in_memory"
                _write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
                raise
            record["status"] = "mutated_verified"
            _write_json(RECORD_PATH, record)
            _verify_applied(show, plan, outside_before)
            materialized = _materialize(show, config)
            _save_narrow()
            _verify_applied(unreal.EditorAssetLibrary.load_asset(SHOW_PATH), plan, outside_before)
            record.update({"status": "saved_readback_verified", "materialized": materialized,
                           "saved_census": _dirty_census()})
            _write_json(RECORD_PATH, record)
            _queue_master_test(world, "LIGHTING_EVENTS", run)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized,
                           "saved_master_test": "queued", "census": _dirty_census()})
            _write_json(REPORT_PATH, report)
            unreal.log("LIGHTING_EVENTS_APPLY_OK|run=%s|phase=%s|attachments=%d|disabled=%d|p04_shadow=%d->%d|show_saved=1|level_saved=1|readback=1|saved_master=queued"
                       % (run, plan["phase"], plan["fixture_count"],
                          sum(len(t["disable_guids"]) for t in plan["targets"]),
                          plan["shadow"]["p04_before"], plan["shadow"]["p04_after"]))
            return report

        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT")
        record = _read_json(RECORD_PATH)
        require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|status=" + str(record.get("status")))
        backup = _backup("PreLightingEventsP04Revert-", run)
        _mutate_revert(show, record)
        materialized = _materialize(show, config)
        _save_narrow()
        readback = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
        for target in record["plan"]["targets"]:
            unused, attachments = _target_current(readback, target)
            del unused
            _require_rows_equal(_rows(attachments), target["before_rows"], "REVERT_READBACK_NOT_EXACT|cue=" + target["cue_label"])
        archived = RECORD_PATH + ".reverted-" + run
        os.rename(RECORD_PATH, archived)
        _queue_master_test(world, "LIGHTING_EVENTS_REVERT", run)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized,
                       "removed": record["plan"]["fixture_count"], "census": _dirty_census()})
        _write_json(REPORT_PATH, report)
        unreal.log("LIGHTING_EVENTS_REVERT_OK|run=%s|removed=%d|show_saved=1|level_saved=1|readback=1|saved_master=queued"
                   % (run, record["plan"]["fixture_count"]))
        return report
    except Exception as error:  # noqa: BLE001 - preserve a report for every stop.
        report["error"] = "%s: %s" % (type(error).__name__, error)
        report["census"] = _dirty_census() if unreal is not None else None
        _write_json(REPORT_PATH, report)
        if unreal is not None:
            unreal.log_error("LIGHTING_EVENTS_STOPPED|run=%s|mode=%s|%s" % (run, mode, report["error"]))
        raise


def main(mode=None):
    selected = str(mode or globals().get("LIGHTING_EVENTS_MODE", "DRY")).upper()
    require(selected in VALID_MODES, "MODE_INVALID|mode=" + selected)
    require(unreal is not None, "UNREAL_REQUIRED_FOR_MODE|mode=" + selected)
    return _run(selected)


if unreal is not None:
    main()
