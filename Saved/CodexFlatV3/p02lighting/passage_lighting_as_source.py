"""Generalise one Passage's lights from another Passage's lighting structure.

Offline-authored only.  The conductor runs this later through
``passage_lighting_run.py``.  Modes are DRY / APPLY / REVERT.

Authority and safety contract (declaration-proven unless marked otherwise):

* Lights live in ``FInfinityWingOccurrence::Attachments`` and are materialised
  by ``AInfinityStagePassageActor``.  The Show asset is therefore written first,
  the target Passage alone is materialised, then only the Show and current level save.
* APPLY copies ordinary source LIGHTs at the same WingPair ordinal without
  wrapping.  Full density is the default; half density selects alternating
  source lights across the flattened, ordinal-stable source list.
* Target EFFECT/PROP attachments, labels/tags naming car/move/event/fx/smoke/etc.,
  and keyed lights whose role has no source counterpart are retained verbatim.
* ``match_source_atmosphere`` defaults true. Existing target BeamLook actors are
  moved/material-matched to source BeamLook actors that fall within the
  mapped ordinal range; target Smoke Test actors and unmatched atmosphere actors
  are suppressed, not deleted. Unmatched target LocalFogVolumes have extinction
  set to zero.  This is deliberately reversible and makes no asset deletion.
* A record and ``Backups/Pre<Target>LightingAs<Source>-<run>`` (Show + level) precede the
  first mutation.  APPLY/REVERT require exact confirm strings and APPLY also
  requires the plan sha256 printed by DRY.

Proof boundary: source declarations and saved records informed this code, but
no Unreal/editor/MCP/PIE call was made while authoring it.  Live DRY is required
before APPLY; rendered acceptance remains Gary's.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import struct
import zlib

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
RECORD_PATH = os.path.join(HERE, "passage_lighting_record.json")
ARGS_PATH = os.path.join(HERE, "passage_lighting_args.json")
MARK = "PASSAGELIGHT"
FLOAT_TOL = 1.0e-4
TERMINAL_RECORD_STATUSES = {"reverted", "archived", "complete", "failed", "failed_rolled_back_in_memory"}
GPU_PROBE_COMMAND = (
    "python Saved/CodexMocap/mcp_request.py tools/call --params-file "
    "Saved/CodexFlatV3/p02lighting/passage_lighting_perf_probe_request.json"
)
IMMEDIATE_REVERT_COMMAND = (
    "python Saved/CodexMocap/mcp_request.py tools/call --params-file "
    "Saved/CodexFlatV3/p02lighting/passage_lighting_immediate_revert_request.json"
)
MOVER_FIELDS = ("enabled", "trigger", "approach_distance_cm", "yaw_amplitude_degrees",
                "pitch_amplitude_degrees", "steps_per_second", "ease_fraction", "calm_scale",
                "erratic_ramp_cm", "seed")
BODY_FIELDS = ("follow_light", "light_attachment_guid", "intensity_parameter", "full_intensity",
               "flicker", "seed", "slight_depth", "flicker_rate_hz", "fail_window_cm",
               "fail_at_cm", "flicker_also_drives_light")


def _load(name):
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location("_passagelight_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load("_fx_authoring_common")
S = _load("_infinity_attachment_state")

DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "expected_plan_sha256": "",
    "source_passage": "P01",
    "target_passage": "P02",
    "source_ordinal_policy": "same_ordinal_no_wrap",
    "colour_policy": "target_role_then_dominant",
    "aim_policy": "own_side_wing",
    "density": "full",
    "preserve_nonlights": True,
    "expected_target_bays": 23,
    "expected_added_lights": 414,
    "max_added_lights": 414,
    "own_side_aim_x_cm": 0.0,
    "own_side_aim_height_cm": 600.0,
    "match_source_atmosphere": True,
    "special_label_tokens": [
        "car", "moving", "move", "event", "fx", "smoke", "haze", "fire",
        "rain", "spark", "mote", "pyro", "polaroid", "flash", "meshy", "dead",
    ],
    "atmosphere": {
        "source_tag": "",
        "target_tag": "",
        "beam_tag": "InfinityStage.BeamLook",
        "smoke_tag": "InfinityStage.SmokeTest",
        "footprint_x_cm": [-2000.0, 20000.0],
        "footprint_half_y_cm": 6000.0,
        "footprint_half_z_cm": 6000.0,
    },
    "perf_probe": {
        "relative_saved_path": "CodexFlatV3/p02lighting/passage_lighting_perf_probe.py",
        "seconds": 60.0,
        "skip_frames": 30,
        "max_p95_ms": 33.4,
        "max_p99_ms": 50.0,
    },
    "ack_records": [],
}


class PassageLightingError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise PassageLightingError(str(message))


def passage_number(value):
    match = re.fullmatch(r"P0?([1-6])", str(value).upper())
    require(match, "PASSAGE_INVALID|" + str(value))
    return int(match.group(1))


def passage_prefix(value):
    return "P%02d" % passage_number(value)


def passage_label(value):
    return "Passage %d" % passage_number(value)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def state_hash(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def finite(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), label + "_NOT_NUMBER")
    value = float(value)
    require(math.isfinite(value), label + "_NOT_FINITE")
    return value


def check_args(raw):
    require(isinstance(raw, dict), "ARGS_NOT_OBJECT")
    unknown = sorted(set(raw) - set(DEFAULTS))
    require(not unknown, "ARGS_UNKNOWN|" + ",".join(unknown))
    out = copy.deepcopy(DEFAULTS)
    out.update(copy.deepcopy(raw))
    mode = str(out["mode"]).upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID|" + mode)
    out["mode"] = mode
    if mode != "DRY":
        require(out["confirm"] == "%s %s" % (mode, MARK), "CONFIRM_MISSING|want=%s %s" % (mode, MARK))
    if mode == "APPLY":
        require(re.fullmatch(r"[0-9a-f]{64}", str(out["expected_plan_sha256"])), "EXPECTED_PLAN_SHA256_REQUIRED")
    out["source_passage"] = passage_prefix(out["source_passage"])
    out["target_passage"] = passage_prefix(out["target_passage"])
    require(out["source_passage"] != out["target_passage"], "SOURCE_EQUALS_TARGET")
    require(out["source_ordinal_policy"] == "same_ordinal_no_wrap", "SOURCE_ORDINAL_POLICY_INVALID")
    require(out["colour_policy"] == "target_role_then_dominant", "COLOUR_POLICY_INVALID")
    require(out["aim_policy"] in ("own_side_wing", "preserve_source"), "AIM_POLICY_INVALID")
    require(out["density"] in ("full", "half"), "DENSITY_INVALID")
    require(out["preserve_nonlights"] is True, "PRESERVE_NONLIGHTS_REQUIRED")
    for key in ("expected_target_bays", "expected_added_lights", "max_added_lights"):
        require(isinstance(out[key], int) and not isinstance(out[key], bool) and out[key] > 0, key.upper() + "_INVALID")
    for key in ("own_side_aim_x_cm", "own_side_aim_height_cm"):
        out[key] = finite(out[key], key.upper())
    require(isinstance(out["match_source_atmosphere"], bool), "MATCH_ATMOS_NOT_BOOL")
    tokens = out["special_label_tokens"]
    require(isinstance(tokens, list) and tokens and all(isinstance(x, str) and x.strip() for x in tokens),
            "SPECIAL_TOKENS_INVALID")
    out["special_label_tokens"] = sorted(set(x.strip().lower() for x in tokens))
    atm = out["atmosphere"]
    require(isinstance(atm, dict) and set(atm) == set(DEFAULTS["atmosphere"]), "ATMOS_ARGS_KEYS")
    require(isinstance(atm["footprint_x_cm"], list) and len(atm["footprint_x_cm"]) == 2,
            "ATMOS_FOOTPRINT_X")
    atm["footprint_x_cm"] = [finite(x, "ATMOS_X") for x in atm["footprint_x_cm"]]
    require(atm["footprint_x_cm"][0] < atm["footprint_x_cm"][1], "ATMOS_X_ORDER")
    for key in ("footprint_half_y_cm", "footprint_half_z_cm"):
        atm[key] = finite(atm[key], key.upper())
        require(atm[key] > 0.0, key.upper() + "_RANGE")
    atm["source_tag"] = str(atm["source_tag"] or (out["source_passage"] + "ATMOS"))
    atm["target_tag"] = str(atm["target_tag"] or (out["target_passage"] + "ATMOS"))
    perf = out["perf_probe"]
    require(isinstance(perf, dict) and set(perf) == set(DEFAULTS["perf_probe"]), "PERF_PROBE_ARGS_KEYS")
    require(str(perf["relative_saved_path"]).startswith("CodexFlatV3/p02lighting/"), "PERF_PROBE_PATH_SCOPE")
    perf["seconds"] = finite(perf["seconds"], "PERF_SECONDS")
    require(perf["seconds"] > 0.0, "PERF_SECONDS_RANGE")
    require(isinstance(perf["skip_frames"], int) and perf["skip_frames"] >= 0, "PERF_SKIP_INVALID")
    for key in ("max_p95_ms", "max_p99_ms"):
        perf[key] = finite(perf[key], key.upper())
        require(perf[key] > 0.0, key.upper() + "_RANGE")
    require(isinstance(out["ack_records"], list) and all(isinstance(x, str) for x in out["ack_records"]),
            "ACK_RECORDS_INVALID")
    return out


def immediate_revert_args(record):
    """Build the exact field-scoped REVERT args from the active APPLY record."""
    require(isinstance(record, dict), "IMMEDIATE_REVERT_RECORD_NOT_OBJECT")
    require(record.get("status") == "saved_readback_verified", "IMMEDIATE_REVERT_RECORD_NOT_READY")
    raw = copy.deepcopy(record.get("args"))
    require(isinstance(raw, dict), "IMMEDIATE_REVERT_RECORD_ARGS_MISSING")
    raw["mode"] = "REVERT"
    raw["confirm"] = "REVERT " + MARK
    return check_args(raw)


def enum_name(value):
    text = str(value).upper()
    if "." in text:
        text = text.split(".")[-1]
    return text.split(":")[0].strip(" <>')\"")


def is_light(row):
    return enum_name(row.get("kind")) == "LIGHT"


def is_effect(row):
    return enum_name(row.get("kind")) == "EFFECT"


def role_from_label(label):
    """Map labels without guessing between sides: the literal suffix is the role."""
    text = str(label).strip()
    score = re.search(r"\bSCORE\s+B\d+\s+\S+\s+(.+)$", text, re.I)
    if score:
        return re.sub(r"[^A-Z0-9+-]+", "_", score.group(1).upper()).strip("_")
    managed = re.search(r"\bP0[1-6]STRUCT\s+B\d+\s+(.+)$", text, re.I)
    if managed:
        return re.sub(r"[^A-Z0-9+-]+", "_", managed.group(1).upper()).strip("_")
    wing = re.search(r"\bP0[1-6]\s+Wing\s+\d+\s+(.+)$", text, re.I)
    if wing:
        return re.sub(r"[^A-Z0-9+-]+", "_", wing.group(1).upper()).strip("_")
    return re.sub(r"[^A-Z0-9+-]+", "_", text.upper()).strip("_")


def drama_active(row):
    d = (row.get("lighting") or {}).get("drama") or {}
    after = enum_name(d.get("after_pass", "HOLD"))
    return bool(d.get("strike_on_approach") or d.get("slow_move") or after not in ("", "HOLD"))


def special_reason(row, source_roles, tokens, cue_tags=()):
    if not is_light(row):
        return "effect_attachment" if is_effect(row) else "non_light_attachment"
    label = str(row.get("label", ""))
    lower = label.lower()
    tag_text = " ".join(str(x).lower() for x in cue_tags)
    tag_hit = next((t for t in tokens if re.search(
        r"(^|[^a-z0-9])%s([^a-z0-9]|$)" % re.escape(t), tag_text)), None)
    if tag_hit:
        return "cue_tag:" + tag_hit
    hit = next((t for t in tokens if re.search(r"(^|[^a-z0-9])%s([^a-z0-9]|$)" % re.escape(t), lower)), None)
    if hit:
        return "label_token:" + hit
    role = role_from_label(label)
    if drama_active(row) and role not in source_roles:
        return "keyed_without_source_counterpart"
    return None


def colour_signature(row):
    lighting = row.get("lighting") or {}
    rgba = list(lighting.get("color") or [1.0, 1.0, 1.0, 1.0])
    while len(rgba) < 4:
        rgba.append(1.0)
    # 8 Oct conductor: keep the target's HUE only. Some target lights are dimmed through near-black RGB;
    # copying raw RGB would leave the copied structure dark. Brightness comes from the source's
    # intensity; the colour is normalised so its brightest channel is 1.
    peak = max(float(x) for x in rgba[:3])
    rgb = [float(x) / peak for x in rgba[:3]] if peak > 1e-6 else [1.0, 1.0, 1.0]
    return {
        "color": [round(x, 6) for x in rgb] + [float(rgba[3])],
        "near_black": peak < 0.02,
        "use_temperature": bool(lighting.get("use_temperature", False)),
        "temperature_kelvin": float(lighting.get("temperature_kelvin", 6500.0)),
    }


def dominant_colour(rows):
    lights = [r for r in rows if is_light(r) and not colour_signature(r)["near_black"]]
    require(lights, "TARGET_HAS_NO_LIGHT_COLOUR")
    groups = {}
    for row in lights:
        sig = colour_signature(row)
        key = canonical(sig)
        groups.setdefault(key, {"count": 0, "value": sig, "labels": []})
        groups[key]["count"] += 1
        groups[key]["labels"].append(row.get("label"))
    return sorted(groups.values(), key=lambda x: (-x["count"], canonical(x["value"])))[0]


def role_colours(rows):
    grouped = {}
    for row in rows:
        if not is_light(row) or colour_signature(row)["near_black"]:
            continue
        role = role_from_label(row.get("label", ""))
        sig = colour_signature(row)
        key = canonical(sig)
        grouped.setdefault(role, {}).setdefault(key, {"count": 0, "value": sig})
        grouped[role][key]["count"] += 1
    return {role: sorted(values.values(), key=lambda x: (-x["count"], canonical(x["value"])))[0]["value"]
            for role, values in grouped.items()}


def apply_colour(row, colour):
    out = copy.deepcopy(row)
    lighting = out.setdefault("lighting", {})
    lighting["color"] = list(colour["color"])
    out.pop("near_black", None)
    lighting["use_temperature"] = bool(colour["use_temperature"])
    lighting["temperature_kelvin"] = float(colour["temperature_kelvin"])
    return out


def _side_for_role(role, wing_y):
    """Return the actual target-wing Y for an explicitly sided role."""
    text = str(role).upper()
    if "+Y" in text:
        return max(float(x) for x in wing_y), "+Y"
    if "-Y" in text:
        return min(float(x) for x in wing_y), "-Y"
    if re.search(r"(^|_)L($|_)", text):
        return float(wing_y[0]), "L"
    if re.search(r"(^|_)R($|_)", text):
        return float(wing_y[1]), "R"
    return None, None


def _aim_quaternion(location, target):
    """Quaternion (xyzw) whose Unreal +X axis points from location to target."""
    dx, dy, dz = [float(target[i]) - float(location[i]) for i in range(3)]
    horizontal = math.hypot(dx, dy)
    require(horizontal > 1.0e-6 or abs(dz) > 1.0e-6, "AIM_ZERO_VECTOR")
    yaw = math.atan2(dy, dx)
    pitch = math.atan2(dz, horizontal)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    return [round(-sp * sy, 9), round(sp * cy, 9), round(cp * sy, 9), round(cp * cy, 9)]


def apply_aim_policy(row, role, target_wing_y, args):
    out = copy.deepcopy(row)
    if args["aim_policy"] == "preserve_source":
        return out, None
    light_type = enum_name((out.get("lighting") or {}).get("type"))
    target_y, side = _side_for_role(role, target_wing_y)
    if target_y is None or light_type not in ("SPOT", "RECT"):
        return out, None
    transform = out["relative_transform"]
    before = copy.deepcopy(transform)
    location = [float(x) for x in transform["location"]]
    # If the source layout placed a sided lamp across the centre line, mirror
    # only Y so both lamp and aim point remain on the named target-wing side.
    if location[1] * target_y <= 0.0:
        location[1] = math.copysign(max(abs(location[1]), 1.0), target_y)
    target = [float(args["own_side_aim_x_cm"]), target_y, float(args["own_side_aim_height_cm"])]
    require(location[1] * target_y > 0.0, "OWN_SIDE_AIM_CROSSES_CENTRE|" + role)
    transform["location"] = location
    transform["rotation_xyzw"] = _aim_quaternion(location, target)
    return out, {"role": role, "side": side, "target": target,
                 "before_transform": before, "after_transform": copy.deepcopy(transform)}


def enforce_budgets(plan, args):
    actual = int(plan["counts"]["added_lights"])
    require(int(plan["target_bays"]) == int(args["expected_target_bays"]),
            "TARGET_BAY_COUNT|expected=%d|actual=%d" % (args["expected_target_bays"], plan["target_bays"]))
    require(actual == int(args["expected_added_lights"]),
            "EXPECTED_ADDED_LIGHTS|expected=%d|actual=%d" % (args["expected_added_lights"], actual))
    require(actual <= int(args["max_added_lights"]),
            "PERF_COUNT_CAP_EXCEEDED|cap=%d|actual=%d" % (args["max_added_lights"], actual))
    gate = {"status": "DRY_COUNT_PASS", "density": args["density"], "actual_added_lights": actual,
            "expected_added_lights": args["expected_added_lights"], "cap_added_lights": args["max_added_lights"],
            "post_apply_probe_required": True, "post_apply_probe": copy.deepcopy(args["perf_probe"])}
    plan["perf_gate"] = gate
    return gate


def build_plan(source_cues, target_cues, args):
    require(source_cues and target_cues, "PASSAGE_BAYS_EMPTY")
    require(len(source_cues) >= len(target_cues),
            "SOURCE_BAYS_SHORT|policy=same_ordinal_no_wrap|source=%d|target=%d" %
            (len(source_cues), len(target_cues)))
    all_target = [a for c in target_cues for a in c["attachments"]]
    colours = role_colours(all_target)
    dominant = dominant_colour(all_target)
    targets, colour_mappings = [], []
    global_source_index = 0
    aim_mappings = []
    for ordinal, target in enumerate(target_cues, start=1):
        source_ordinal = ordinal
        source = source_cues[source_ordinal - 1]
        all_source_lights = [r for r in source["attachments"] if is_light(r)]
        source_roles = {role_from_label(r["label"]) for r in all_source_lights}
        source_lights = []
        for source_row in all_source_lights:
            take = args["density"] == "full" or global_source_index % 2 == 0
            global_source_index += 1
            if take:
                source_lights.append(source_row)
        kept, removed = [], []
        for row in target["attachments"]:
            reason = special_reason(row, source_roles, args["special_label_tokens"], target.get("tags", []))
            if not is_light(row) or reason:
                kept.append({"row": copy.deepcopy(row), "reason": reason or "non_light_attachment"})
            else:
                removed.append(copy.deepcopy(row))
        added = []
        for source_row in source_lights:
            role = role_from_label(source_row["label"])
            colour = colours.get(role, dominant["value"])
            mapping = "role" if role in colours else "dominant"
            source_spec = apply_colour(source_row, colour)
            row, aim = apply_aim_policy(source_spec, role, target.get("wing_y") or [-900.0, 900.0], args)
            row["guid"] = None  # minted by replication during APPLY
            row["label"] = "%s %sSTRUCT B%02d %s" % (args["target_passage"], args["source_passage"], ordinal, role)
            added.append(row)
            if aim:
                aim.update({"target_ordinal": ordinal, "source_ordinal": source_ordinal,
                            "source_label": source_row["label"], "managed_label": row["label"]})
                aim_mappings.append(aim)
            colour_mappings.append({
                "target_ordinal": ordinal, "source_ordinal": source_ordinal, "role": role,
                "mapping": mapping, "colour": colour,
            })
        targets.append({
            "ordinal": ordinal, "source_ordinal": source_ordinal,
            "cue_guid": target["guid"], "cue_label": target["label"],
            "source_cue_guid": source["guid"], "source_cue_label": source["label"],
            "show_index": target["show_index"], "source_show_index": source["show_index"],
            "before_rows": copy.deepcopy(target["attachments"]),
            "cue_tags": list(target.get("tags", [])),
            "kept": kept, "removed": removed, "source_specs": [copy.deepcopy(x) for x in source_lights],
            "added_specs": added,
            "wing_y": list(target.get("wing_y") or [-900.0, 900.0]),
            "source_wing_y": list(source.get("wing_y") or [-900.0, 900.0]),
        })
    plan = {
        "source_passage": args["source_passage"], "target_passage": args["target_passage"],
        "source_bays": len(source_cues), "target_bays": len(target_cues),
        "source_ordinal_policy": args["source_ordinal_policy"], "wrapped": False, "wrap_count": 0,
        "dominant_colour": dominant, "role_colours": colours,
        "colour_mappings": colour_mappings, "aim_mappings": aim_mappings, "targets": targets,
        "counts": {
            "removed_lights": sum(len(t["removed"]) for t in targets),
            "added_lights": sum(len(t["added_specs"]) for t in targets),
            "kept_specials": sum(1 for t in targets for k in t["kept"]
                                 if is_light(k["row"]) or is_effect(k["row"])),
            "kept_nonlights": sum(1 for t in targets for k in t["kept"] if not is_light(k["row"])),
            "dominant_fallbacks": sum(m["mapping"] == "dominant" for m in colour_mappings),
            "shadow_casting_added": sum(bool((r.get("lighting") or {}).get("cast_shadows"))
                                         for t in targets for r in t["added_specs"]),
            "projected_target_lights": sum(len(t["added_specs"]) + sum(is_light(k["row"]) for k in t["kept"])
                                           for t in targets),
        },
    }
    plan["per_row_counts"] = [{"ordinal": t["ordinal"], "source_ordinal": t["source_ordinal"],
                               "before_lights": sum(is_light(r) for r in t["before_rows"]),
                               "removed_lights": len(t["removed"]), "added_lights": len(t["added_specs"]),
                               "kept_lights": sum(is_light(k["row"]) for k in t["kept"]),
                               "projected_lights": len(t["added_specs"]) + sum(is_light(k["row"]) for k in t["kept"])}
                              for t in targets]
    plan["plan_sha256"] = state_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
    return plan


def atmos_plan(source_actors, target_actors, target_bay_count, enabled=True):
    if not enabled:
        return {"enabled": False, "changes": [], "inventory": target_actors}
    source_beams = sorted((a for a in source_actors if a.get("beam") and (a.get("ordinal") or 10**9) <= target_bay_count),
                          key=lambda a: (a.get("ordinal") or 10**9, a["label"]))
    target_beams = sorted((a for a in target_actors if a.get("beam")),
                          key=lambda a: (a.get("ordinal") or 10**9, a["label"]))
    changes = []
    for index, target in enumerate(target_beams):
        if index < len(source_beams):
            source = source_beams[index]
            changes.append({"action": "match_beam_actor", "target": target, "source": source})
        else:
            changes.append({"action": "suppress_actor", "target": target, "reason": "no_source_counterpart"})
    for target in target_actors:
        if target.get("beam"):
            continue
        if target.get("lfv"):
            changes.append({"action": "zero_lfv", "target": target})
        else:
            changes.append({"action": "suppress_actor", "target": target,
                            "reason": "target_atmosphere_without_source_counterpart"})
    require(len(target_beams) >= len(source_beams),
            "ATMOS_TARGET_BEAMS_MISSING|need=%d|have=%d" % (len(source_beams), len(target_beams)))
    return {"enabled": True, "source_beams": source_beams, "target_beams": target_beams,
            "changes": changes, "inventory": target_actors}


# --------------------------------------------------------------- tiny PNG
def _png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def write_preview_png(path, plan, width=1400, height=760):
    """Dependency-free top-down source-vs-planned plot; returns pixel statistics."""
    pixels = bytearray([248, 248, 246] * width * height)

    def px(x, y, colour):
        if 0 <= x < width and 0 <= y < height:
            i = (y * width + x) * 3
            pixels[i:i + 3] = bytes(colour)

    def line(x0, y0, x1, y1, colour, thick=1):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            for ox in range(-thick, thick + 1):
                for oy in range(-thick, thick + 1):
                    px(x0 + ox, y0 + oy, colour)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy

    def dot(x, y, colour, radius=4):
        for yy in range(y - radius, y + radius + 1):
            for xx in range(x - radius, x + radius + 1):
                if (xx - x) ** 2 + (yy - y) ** 2 <= radius ** 2:
                    px(xx, yy, colour)

    def panel(x0, x1, rows, wing_key, colour):
        pts = [r["relative_transform"]["location"] for row in rows for r in row if is_light(r)]
        max_x = max([abs(p[0]) for p in pts] + [1.0])
        max_y = max([abs(p[1]) for p in pts] + [1200.0])
        cx, cy = (x0 + x1) // 2, height // 2
        sx = (x1 - x0 - 100) / (2.0 * max_x)
        sy = (height - 110) / (2.0 * max_y)
        line(x0 + 25, cy, x1 - 25, cy, (180, 180, 180))
        wing_values = []
        for target in plan["targets"]:
            wing_values.extend(target[wing_key])
        for wy in sorted(set(round(float(v), 2) for v in wing_values)):
            yy = int(round(cy - wy * sy))
            line(x0 + 35, yy, x1 - 35, yy, (75, 75, 75), 1)
        for p in pts:
            dot(int(round(cx + p[0] * sx)), int(round(cy - p[1] * sy)), colour)
        return len(pts)

    source_rows = [[r for r in t["source_specs"]] for t in plan["targets"]]
    target_rows = [[r for r in t["added_specs"]] for t in plan["targets"]]
    line(width // 2, 20, width // 2, height - 20, (40, 40, 40), 2)
    left = panel(0, width // 2, source_rows, "source_wing_y", (212, 72, 52))
    right = panel(width // 2, width, target_rows, "wing_y", (35, 104, 190))
    raw = b"".join(b"\x00" + bytes(pixels[y * width * 3:(y + 1) * width * 3]) for y in range(height))
    data = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return {"path": path, "bytes": len(data), "width": width, "height": height,
            "source_points": left, "target_points": right}


def field_scoped_revert_rows(current_rows, target):
    """Pure reconcile used by REVERT and the offline +/- harness."""
    current = {row["guid"]: row for row in current_rows}
    require(len(current) == len(current_rows), "REVERT_CURRENT_DUPLICATE_GUID")
    added = _added_expected(target)
    for guid, expected in added.items():
        require(guid in current, "REVERT_ADDED_GUID_MISSING|" + guid)
        diff = S.state_differences(expected, current[guid])
        require(not diff, "REVERT_OWNED_FIELD_DRIFT|guid=%s|diff=%s" % (guid, canonical(diff[:8])))
    removed = {row["guid"]: row for row in target["removed"]}
    require(not (set(removed) & set(current)), "REVERT_ORIGINAL_GUID_ALREADY_PRESENT")
    return ([copy.deepcopy(row) for row in current_rows if row["guid"] not in added] +
            [copy.deepcopy(row) for row in target["removed"]])


# --------------------------------------------------------------- Unreal-only
def _guid_text(value):
    return C.guid_text(value)


def _parse_guid(text):
    result = unreal.GuidLibrary.parse_string_to_guid(str(text))
    if isinstance(result, tuple):
        value, ok = result
        require(ok, "GUID_PARSE_FAILED|" + str(text))
    else:
        value = result
    require(_guid_text(value) == str(text).replace("-", "").upper(), "GUID_PARSE_ROUNDTRIP|" + str(text))
    return value


def _enum(enum_type, text):
    return C.enum_member(enum_type, enum_name(text), enum_name(text).upper())


def _object(path, class_object=False):
    if not path or str(path) == "None":
        return None
    return unreal.load_object(None, str(path)) if class_object else unreal.load_asset(str(path).split(".", 1)[0])


def _plain_transform(value):
    return S._transform_state(value)


def _full_attachment_state(attachment):
    """Attachment state plus the 6 Oct Mover/Body structs absent from the older shared helper."""
    row = S.attachment_state(attachment, _guid_text)
    mover = attachment.get_editor_property("mover")
    body = attachment.get_editor_property("body")
    row["mover"] = {}
    row["body"] = {}
    for name in MOVER_FIELDS:
        value = mover.get_editor_property(name)
        row["mover"][name] = enum_name(value) if name == "trigger" else (
            bool(value) if name == "enabled" else int(value) if name == "seed" else float(value))
    for name in BODY_FIELDS:
        value = body.get_editor_property(name)
        if name == "flicker":
            value = enum_name(value)
        elif name == "light_attachment_guid":
            value = _guid_text(value)
        elif name == "intensity_parameter":
            value = str(value)
        elif name in ("follow_light", "flicker_also_drives_light"):
            value = bool(value)
        elif name == "seed":
            value = int(value)
        else:
            value = float(value)
        row["body"][name] = value
    return row


def _make_transform(row):
    t = unreal.Transform()
    t.set_editor_property("translation", unreal.Vector(*[float(x) for x in row["location"]]))
    t.set_editor_property("rotation", unreal.Quat(*[float(x) for x in row["rotation_xyzw"]]))
    t.set_editor_property("scale3d", unreal.Vector(*[float(x) for x in row["scale"]]))
    return t


def _plain_cues(show):
    out = []
    cues = list(show.get_editor_property("cues"))
    for index, cue in enumerate(cues):
        pair = cue.get_editor_property("wing_pair")
        wing_y = []
        for side in ("left", "right"):
            panel = pair.get_editor_property(side)
            wing_y.append(float(panel.get_editor_property("local_transform").translation.y))
        out.append({
            "show_index": index, "guid": _guid_text(cue.get_editor_property("cue_guid")),
            "label": str(cue.get_editor_property("label")), "wing_y": wing_y,
            "tags": [str(x) for x in cue.get_editor_property("tags")],
            "attachments": [_full_attachment_state(a)
                            for a in pair.get_editor_property("attachments")],
        })
    return out


def _passage_rows(show, label, plain):
    settings = [s for s in show.get_editor_property("passage_settings") if str(s.get_editor_property("label")) == label]
    require(len(settings) == 1, "PASSAGE_SETTINGS_COUNT|%s|%d" % (label, len(settings)))
    passage_guid = settings[0].get_editor_property("passage_guid")
    guids = [_guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(passage_guid)]
    by_guid = {r["guid"]: r for r in plain}
    require(len(guids) == len(set(guids)) and all(g in by_guid for g in guids), "PASSAGE_GUID_RESOLUTION|" + label)
    return [by_guid[g] for g in guids], _guid_text(passage_guid)


def _show_index(show, guid):
    hits = [i for i, c in enumerate(show.get_editor_property("cues"))
            if _guid_text(c.get_editor_property("cue_guid")) == guid]
    require(len(hits) == 1, "CUE_INDEX|%s|%d" % (guid, len(hits)))
    return hits[0]


def _pair_attachments(show, index):
    cue = list(show.get_editor_property("cues"))[index]
    return list(cue.get_editor_property("wing_pair").get_editor_property("attachments"))


def _set_pair_attachments(show, index, attachments):
    cues = list(show.get_editor_property("cues"))
    cue = cues[index]
    pair = cue.get_editor_property("wing_pair")
    pair.set_editor_property("attachments", list(attachments))
    cue.set_editor_property("wing_pair", pair)
    cues[index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _set_plain_value(obj, name, value, kind=None):
    if kind == "vec4":
        value = unreal.LinearColor(*[float(x) for x in value])
    elif kind == "vec3":
        value = unreal.Vector(*[float(x) for x in value])
    elif kind == "vec2":
        value = unreal.Vector2D(*[float(x) for x in value])
    obj.set_editor_property(name, value)


def _set_prop(obj, name, value):
    """set_editor_property, falling back to import_text for read-only GUID fields (5.8: AttachmentGuid,
    ReplicatedFromAttachmentGuid ... are read-only to Python; import_text sets them [measured 8 Oct])."""
    try:
        obj.set_editor_property(name, value)
        return
    except Exception as exc:
        m = re.search(r"Property '([A-Za-z0-9_]+)' for attribute", str(exc))
        if not m or "read-only" not in str(exc) or not isinstance(value, unreal.Guid):
            raise
        g = unreal.GuidLibrary.conv_guid_to_string(value)
        obj.import_text("(%s=%s)" % (m.group(1), g))
        require(unreal.GuidLibrary.conv_guid_to_string(obj.get_editor_property(name)) == g, "GUID_IMPORT_READBACK|" + name)


def _attachment_from_state(row, preserve_guid=True):
    a = unreal.InfinityCueAttachment()
    if preserve_guid:
        # AttachmentGuid is read-only to set_editor_property in 5.8; import_text sets it [measured 8 Oct,
        # probe_guid_import.py: '(AttachmentGuid=<32 hex>)' read back identical].
        g = str(row["guid"]).replace("-", "").upper()
        require(len(g) == 32, "GUID_TEXT|" + g)
        a.import_text("(AttachmentGuid=%s)" % g)
        require(_guid_text(a.get_editor_property("attachment_guid")) == g, "GUID_IMPORT_READBACK|" + g)
    a.set_editor_property("label", unreal.Text(str(row["label"])))
    a.set_editor_property("kind", _enum(unreal.InfinityAttachmentKind, row["kind"]))
    a.set_editor_property("enabled", bool(row["enabled"]))
    a.set_editor_property("actor_class", _object(row.get("actor_class"), True))
    a.set_editor_property("mesh", _object(row.get("mesh")))
    a.set_editor_property("anchor", _enum(unreal.InfinityAttachmentAnchor, row["anchor"]))
    a.set_editor_property("relative_transform", _make_transform(row["relative_transform"]))
    lighting = unreal.InfinityStageLightSettings()
    L = row["lighting"]
    enum_fields = {"type": unreal.InfinityStageLightType,
                   "intensity_units": unreal.InfinityStageLightIntensityUnits}
    for name in S.LIGHT_FIELDS:
        value = L[name]
        if name in enum_fields:
            value = _enum(enum_fields[name], value)
        elif name in S.LIGHT_OBJECT_FIELDS:
            value = _object(value)
        elif name == "color":
            value = unreal.LinearColor(*[float(x) for x in value])
        elif name == "light_function_scale":
            value = unreal.Vector(*[float(x) for x in value])
        lighting.set_editor_property(name, value)
    drama = unreal.InfinityStageLightDrama()
    for name in S.DRAMA_FIELDS:
        value = L["drama"][name]
        if name == "after_pass":
            value = _enum(unreal.InfinityLightAfterPass, value)
        drama.set_editor_property(name, value)
    lighting.set_editor_property("drama", drama)
    a.set_editor_property("lighting", lighting)
    effect = unreal.InfinityStageEffectSettings()
    E = row["effect"]
    for name in S.EFFECT_FIELDS:
        value = E[name]
        if name == "type":
            value = _enum(unreal.InfinityStageEffectType, value)
        elif name in S.EFFECT_GUID_FIELDS:
            value = _parse_guid(value)
        elif name in S.EFFECT_OBJECT_FIELDS:
            value = _object(value)
        elif name in ("tint",):
            value = unreal.LinearColor(*[float(x) for x in value])
        elif name in ("medium_offset_cm", "motes_extent_cm"):
            value = unreal.Vector(*[float(x) for x in value])
        elif name in ("ignition_uv", "burn_u_axis", "burn_v_axis"):
            value = unreal.Vector2D(*[float(x) for x in value])
        _set_prop(effect, name, value)
    a.set_editor_property("effect", effect)
    a.set_editor_property("trigger_distance_cm", float(row["trigger_distance_cm"]))
    if "mover" in row:
        mover = a.get_editor_property("mover")
        for name in MOVER_FIELDS:
            value = row["mover"][name]
            if name == "trigger":
                value = _enum(unreal.InfinityLightMoverTrigger, value)
            _set_prop(mover, name, value)
        a.set_editor_property("mover", mover)
    if "body" in row:
        body = a.get_editor_property("body")
        for name in BODY_FIELDS:
            value = row["body"][name]
            if name == "flicker":
                value = _enum(unreal.InfinityBulbBodyFlicker, value)
            elif name == "light_attachment_guid":
                value = _parse_guid(value)
            elif name == "intensity_parameter":
                value = unreal.Name(value)
            _set_prop(body, name, value)
        a.set_editor_property("body", body)
    return a


def _blank_light():
    a = unreal.InfinityCueAttachment()
    a.set_editor_property("label", unreal.Text("PASSAGELIGHT GUID SCRATCH"))
    a.set_editor_property("kind", _enum(unreal.InfinityAttachmentKind, "LIGHT"))
    a.set_editor_property("enabled", False)
    a.set_editor_property("anchor", _enum(unreal.InfinityAttachmentAnchor, "STATION"))
    return a


def _overwrite_vessel(vessel, template):
    minted = _guid_text(vessel.get_editor_property("attachment_guid"))
    require(len(minted) == 32 and minted.strip("0"), "MINTED_GUID_INVALID|" + minted)
    for name in ("label", "kind", "enabled", "actor_class", "mesh", "anchor", "relative_transform",
                 "lighting", "effect", "trigger_distance_cm", "body", "mover"):
        vessel.set_editor_property(name, template.get_editor_property(name))
    require(_guid_text(vessel.get_editor_property("attachment_guid")) == minted, "MINTED_GUID_CHANGED")
    return vessel


def _all_rows(show):
    return {_guid_text(c.get_editor_property("cue_guid")):
            [_full_attachment_state(a) for a in c.get_editor_property("wing_pair").get_editor_property("attachments")]
            for c in show.get_editor_property("cues")}


def _outside_hash(show, target_guids):
    rows = _all_rows(show)
    return state_hash({g: rows[g] for g in sorted(rows) if g not in set(target_guids)})


def _passage_actor(show, number):
    return C.find_passage_actor(unreal, show, number)


def _actor_tags(actor):
    return sorted(str(x) for x in actor.tags)


def _actor_id(actor):
    return str(actor.get_path_name())


def _actor_plain(actor, passage, atm, prefix):
    label, tags = actor.get_actor_label(), _actor_tags(actor)
    parent = actor.get_attach_parent_actor()
    rel = unreal.MathLibrary.make_relative_transform(actor.get_actor_transform(), passage.get_actor_transform())
    loc = rel.translation
    is_lfv = isinstance(actor, unreal.LocalFogVolume)
    beam = atm["beam_tag"] in tags
    smoke = atm["smoke_tag"] in tags or "SMOKE TEST" in label.upper()
    ordinal_hit = re.search(r"\bB(\d+)\b", label)
    row = {
        "id": _actor_id(actor), "label": label, "tags": tags,
        "class": str(actor.get_class().get_path_name()), "relative_transform": _plain_transform(rel),
        # UE 5.8 exposes AActor::bHidden as the ``hidden`` editor property;
        # StaticMeshActor.is_hidden() is not in the 5.8 Python API.
        "hidden_game": bool(actor.get_editor_property("hidden")), "attached_to_passage": parent == passage,
        "beam": beam, "smoke": smoke, "lfv": is_lfv,
        "ordinal": int(ordinal_hit.group(1)) if ordinal_hit else None,
    }
    smc = actor.get_component_by_class(unreal.StaticMeshComponent)
    if smc:
        row["static_mesh"] = C.asset_id(smc.get_editor_property("static_mesh"))
        row["materials"] = [C.asset_id(x) for x in smc.get_materials()]
        row["visible"] = bool(smc.is_visible())
    if is_lfv:
        comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        row["radial_fog_extinction"] = float(comp.get_editor_property("radial_fog_extinction"))
        row["height_fog_extinction"] = float(comp.get_editor_property("height_fog_extinction"))
    return row


def _local_in_bounds(actor, passage, atm):
    rel = unreal.MathLibrary.make_relative_transform(actor.get_actor_transform(), passage.get_actor_transform())
    p = rel.translation
    lo, hi = atm["footprint_x_cm"]
    return lo <= p.x <= hi and abs(p.y) <= atm["footprint_half_y_cm"] and abs(p.z) <= atm["footprint_half_z_cm"]


def _atmos_actors(show, number, atm, own_tag):
    passage = _passage_actor(show, number)
    prefix = "P%02d" % number
    rows = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label, tags = actor.get_actor_label(), _actor_tags(actor)
        named = own_tag in tags or label.upper().startswith(prefix + " ") and any(
            x in label.upper() for x in ("FOG", "HAZE", "SMOKE", "BEAMLOOK"))
        lfv = isinstance(actor, unreal.LocalFogVolume) and _local_in_bounds(actor, passage, atm)
        if named or lfv:
            rows.append(_actor_plain(actor, passage, atm, prefix))
    return passage, sorted(rows, key=lambda r: (r["label"], r["id"]))


def _special_level_actors(show, args):
    """Inventory target-local named special actors; this tool never writes them."""
    target_number = passage_number(args["target_passage"])
    target_prefix = args["target_passage"]
    passage = _passage_actor(show, target_number)
    tokens = args["special_label_tokens"]
    rows = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = actor.get_actor_label()
        tags = _actor_tags(actor)
        if (args["atmosphere"]["target_tag"] in tags
                or args["atmosphere"]["beam_tag"] in tags
                or args["atmosphere"]["smoke_tag"] in tags
                or isinstance(actor, unreal.LocalFogVolume)):
            continue  # listed, and optionally normalised, by the atmosphere table
        searchable = (label + " " + " ".join(tags)).lower()
        hit = next((t for t in tokens if re.search(r"(^|[^a-z0-9])%s([^a-z0-9]|$)" % re.escape(t), searchable)), None)
        if hit and (_local_in_bounds(actor, passage, args["atmosphere"])
                    or actor.get_attach_parent_actor() == passage or label.upper().startswith(target_prefix)):
            rows.append({"id": _actor_id(actor), "label": label, "class": actor.get_class().get_name(),
                         "tags": tags, "matched_token": hit, "action": "KEEP_UNTOUCHED"})
    return sorted(rows, key=lambda r: (r["label"], r["id"]))


def _find_actor(actor_id):
    hits = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if _actor_id(a) == actor_id]
    require(len(hits) == 1, "ACTOR_RESOLVE|%s|%d" % (actor_id, len(hits)))
    return hits[0]


def _apply_actor_state(row, passage, source=None, suppress=False, zero_lfv=False):
    actor = _find_actor(row["id"])
    actor.modify()
    if source is not None:
        world = unreal.MathLibrary.compose_transforms(_make_transform(source["relative_transform"]),
                                                      passage.get_actor_transform())
        actor.set_actor_transform(world, False, True)
        smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc and source.get("static_mesh"):
            smc.modify()
            smc.set_static_mesh(_object(source["static_mesh"]))
            for i, material in enumerate(source.get("materials", [])):
                smc.set_material(i, _object(material))
            smc.set_visibility(bool(source.get("visible", True)), True)
        actor.set_actor_hidden_in_game(bool(source.get("hidden_game", False)))
    if suppress:
        actor.set_actor_hidden_in_game(True)
        smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.modify()
            smc.set_visibility(False, True)
    if zero_lfv:
        comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        require(comp is not None, "LFV_COMPONENT_MISSING|" + row["label"])
        comp.modify()
        comp.set_radial_fog_extinction(0.0)
        comp.set_height_fog_extinction(0.0)


def _restore_actor_state(row, passage):
    actor = _find_actor(row["id"])
    actor.modify()
    world = unreal.MathLibrary.compose_transforms(_make_transform(row["relative_transform"]), passage.get_actor_transform())
    actor.set_actor_transform(world, False, True)
    actor.set_actor_hidden_in_game(bool(row.get("hidden_game", False)))
    smc = actor.get_component_by_class(unreal.StaticMeshComponent)
    if smc:
        smc.modify()
        if row.get("static_mesh"):
            smc.set_static_mesh(_object(row["static_mesh"]))
        for i, material in enumerate(row.get("materials", [])):
            smc.set_material(i, _object(material))
        smc.set_visibility(bool(row.get("visible", True)), True)
    if row.get("lfv"):
        comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        comp.modify()
        comp.set_radial_fog_extinction(float(row["radial_fog_extinction"]))
        comp.set_height_fog_extinction(float(row["height_fog_extinction"]))


def _restore_actor_fields(change, passage):
    """Restore only atmosphere fields written by one action."""
    row = change["target"]
    actor = _find_actor(row["id"])
    actor.modify()
    action = change["action"]
    if action == "match_beam_actor":
        world = unreal.MathLibrary.compose_transforms(_make_transform(row["relative_transform"]),
                                                      passage.get_actor_transform())
        actor.set_actor_transform(world, False, True)
        smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.modify()
            if row.get("static_mesh"):
                smc.set_static_mesh(_object(row["static_mesh"]))
            for i, material in enumerate(row.get("materials", [])):
                smc.set_material(i, _object(material))
            smc.set_visibility(bool(row.get("visible", True)), True)
        actor.set_actor_hidden_in_game(bool(row.get("hidden_game", False)))
    elif action == "suppress_actor":
        actor.set_actor_hidden_in_game(bool(row.get("hidden_game", False)))
        smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.modify()
            smc.set_visibility(bool(row.get("visible", True)), True)
    elif action == "zero_lfv":
        comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        require(comp is not None, "LFV_COMPONENT_MISSING|" + row["label"])
        comp.modify()
        comp.set_radial_fog_extinction(float(row["radial_fog_extinction"]))
        comp.set_height_fog_extinction(float(row["height_fog_extinction"]))


def _mutate_lights(show, plan):
    target_guids = {t["cue_guid"] for t in plan["targets"]}
    cues = list(show.get_editor_property("cues"))
    scratch = next((i for i, c in enumerate(cues)
                    if _guid_text(c.get_editor_property("cue_guid")) not in target_guids
                    and enum_name(c.get_editor_property("type")) == "WING_PAIR"
                    and (plan["source_passage"] + " ") not in str(c.get_editor_property("label"))), None)
    require(scratch is not None, "SCRATCH_CUE_MISSING")
    scratch_original = _pair_attachments(show, scratch)
    scratch_before = [_full_attachment_state(a) for a in scratch_original]
    originals = {t["show_index"]: _pair_attachments(show, t["show_index"]) for t in plan["targets"]}
    maximum = max(len(t["added_specs"]) for t in plan["targets"])
    require(maximum > 0, "SOURCE_HAS_NO_LIGHTS")
    preexisting = {r["guid"] for rows in _all_rows(show).values() for r in rows}
    try:
        # Replication reuses target light GUIDs before minting new ones. Clear
        # target lights in memory and make scratch contain exactly N blank
        # lights so every authored P01-structure light receives a fresh GUID.
        # Originals are restored on every failure path and special lights are
        # inserted verbatim below.
        scratch_nonlights = [a for a in scratch_original if not is_light(_full_attachment_state(a))]
        _set_pair_attachments(show, scratch, scratch_nonlights + [_blank_light() for _ in range(maximum)])
        for index, attachments in originals.items():
            _set_pair_attachments(show, index,
                                  [a for a in attachments if not is_light(_full_attachment_state(a))])
        fresh = list(show.get_editor_property("cues"))
        changed = show.replicate_light_attachments(
            fresh[scratch].get_editor_property("cue_guid"),
            [fresh[t["show_index"]].get_editor_property("cue_guid") for t in plan["targets"]])
        require(int(changed) == len(plan["targets"]), "REPLICATION_TARGET_COUNT|%s" % changed)
        _set_pair_attachments(show, scratch, scratch_original)
        require(not S.state_differences(scratch_before,
                                       [_full_attachment_state(a) for a in _pair_attachments(show, scratch)]),
                "SCRATCH_NOT_RESTORED")
        all_added = set()
        for target in plan["targets"]:
            index = _show_index(show, target["cue_guid"])
            replicated = _pair_attachments(show, index)
            vessels = [a for a in replicated if is_light(_full_attachment_state(a))
                       and _guid_text(a.get_editor_property("attachment_guid")) not in preexisting]
            require(len(vessels) >= len(target["added_specs"]), "MINTED_SLOT_COUNT|" + target["cue_label"])
            kept_guids = {k["row"]["guid"] for k in target["kept"]}
            kept_live = [a for a in originals[index]
                         if _guid_text(a.get_editor_property("attachment_guid")) in kept_guids]
            authored = []
            for vessel, spec in zip(vessels, target["added_specs"]):
                made = _attachment_from_state(dict(spec, guid="0" * 32), preserve_guid=False)
                authored.append(_overwrite_vessel(vessel, made))
            target["added"] = [{"guid": _guid_text(a.get_editor_property("attachment_guid")),
                                "label": str(a.get_editor_property("label"))} for a in authored]
            require(not all_added.intersection(x["guid"] for x in target["added"]), "ADDED_GUID_DUPLICATE")
            all_added.update(x["guid"] for x in target["added"])
            _set_pair_attachments(show, index, kept_live + authored)
            target["after_rows"] = [_full_attachment_state(a) for a in _pair_attachments(show, index)]
        return len(all_added)
    except Exception:
        _set_pair_attachments(show, scratch, scratch_original)
        for index, attachments in originals.items():
            _set_pair_attachments(show, index, attachments)
        raise


def _restore_lights_snapshot(show, plan):
    for target in plan["targets"]:
        rebuilt = [_attachment_from_state(row, preserve_guid=True) for row in target["before_rows"]]
        _set_pair_attachments(show, _show_index(show, target["cue_guid"]), rebuilt)


def _added_expected(target):
    added_guids = {row["guid"] for row in target.get("added", [])}
    return {row["guid"]: row for row in target.get("after_rows", []) if row.get("guid") in added_guids}


def _verify_owned_rows(show, plan, side):
    """Compare only rows this tool writes; unrelated cue rows may change freely."""
    for target in plan["targets"]:
        got_rows = [_full_attachment_state(a) for a in _pair_attachments(show, _show_index(show, target["cue_guid"]))]
        got = {row["guid"]: row for row in got_rows}
        removed = {row["guid"]: row for row in target["removed"]}
        added = _added_expected(target)
        if side == "after":
            require(not (set(removed) & set(got)), "AFTER_REMOVED_GUID_PRESENT|" + target["cue_label"])
            for guid, expected in added.items():
                require(guid in got, "AFTER_ADDED_GUID_MISSING|%s|%s" % (target["cue_label"], guid))
                diff = S.state_differences(expected, got[guid])
                require(not diff, "AFTER_OWNED_FIELDS|cue=%s|guid=%s|diff=%s" %
                        (target["cue_label"], guid, canonical(diff[:8])))
        else:
            require(not (set(added) & set(got)), "BEFORE_ADDED_GUID_PRESENT|" + target["cue_label"])
            for guid, expected in removed.items():
                require(guid in got, "BEFORE_REMOVED_GUID_MISSING|%s|%s" % (target["cue_label"], guid))
                diff = S.state_differences(expected, got[guid])
                require(not diff, "BEFORE_RESTORED_FIELDS|cue=%s|guid=%s|diff=%s" %
                        (target["cue_label"], guid, canonical(diff[:8])))


def _unowned_rows_hash(show, plan):
    owned = ({row["guid"] for target in plan["targets"] for row in target.get("added", [])} |
             {row["guid"] for target in plan["targets"] for row in target.get("removed", [])})
    payload = {}
    for target in plan["targets"]:
        rows = [_full_attachment_state(a) for a in _pair_attachments(show, _show_index(show, target["cue_guid"]))]
        payload[target["cue_guid"]] = [row for row in rows if row["guid"] not in owned]
    return state_hash(payload)


def _restore_lights_field_scoped(show, plan):
    """Remove our minted rows and reinsert removed originals; preserve every other current row."""
    for target in plan["targets"]:
        index = _show_index(show, target["cue_guid"])
        live = _pair_attachments(show, index)
        live_rows = [_full_attachment_state(a) for a in live]
        live_states = {row["guid"]: row for row in live_rows}
        field_scoped_revert_rows(live_rows, target)  # validates owned drift and GUID collisions
        added_expected = _added_expected(target)
        for guid, expected in added_expected.items():
            require(guid in live_states, "REVERT_ADDED_GUID_MISSING|%s|%s" % (target["cue_label"], guid))
            diff = S.state_differences(expected, live_states[guid])
            require(not diff, "REVERT_OWNED_FIELD_DRIFT|cue=%s|guid=%s|diff=%s" %
                    (target["cue_label"], guid, canonical(diff[:8])))
        removed = {row["guid"]: row for row in target["removed"]}
        require(not (set(removed) & set(live_states)), "REVERT_ORIGINAL_GUID_ALREADY_PRESENT|" + target["cue_label"])
        keep = [a for a in live if _guid_text(a.get_editor_property("attachment_guid")) not in added_expected]
        restored = [_attachment_from_state(row, preserve_guid=True) for row in target["removed"]]
        _set_pair_attachments(show, index, keep + restored)


def _foreign_records(target_prefix):
    rows = []
    saved_root = os.path.dirname(os.path.dirname(HERE))
    for root, unused_dirs, names in os.walk(saved_root):
        for name in names:
            if not (name.endswith(".json") and "record" in name.lower() and
                    target_prefix.lower() in name.lower()):
                continue
            path = os.path.join(root, name)
            if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(RECORD_PATH)):
                continue
            try:
                data = C.load_json(path)
            except Exception:
                continue
            status = str(data.get("status", "active")).lower()
            if status not in TERMINAL_RECORD_STATUSES:
                rows.append({"path": path, "status": status})
    return sorted(rows, key=lambda r: r["path"])

def _context():
    unused_editor, world = C.editor_context(unreal)
    before = C.require_clean(unreal, "PRE")
    show = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
    require(show is not None, "SHOW_LOAD_FAILED")
    return world, show, before


def _report_path(mode, run):
    return os.path.join(HERE, "passage_lighting_report_%s_%s.json" % (mode, run))


def _preview_path(mode, run):
    return os.path.join(HERE, "passage_lighting_preview_%s_%s.png" % (mode, run))


def _gpu_log_cursor():
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir()),
                        "PussStage.log")
    return {"log_path": path, "log_offset": os.path.getsize(path) if os.path.isfile(path) else 0}


def _log_table(run, plan):
    for t in plan["targets"]:
        removed = ",".join(r["label"] for r in t["removed"]) or "-"
        added = ",".join(r["label"] for r in t["added_specs"]) or "-"
        kept = ",".join("%s{%s}" % (k["row"]["label"], k["reason"]) for k in t["kept"]
                        if is_light(k["row"]) or is_effect(k["row"])) or "-"
        unreal.log("%s_DRY_ROW|run=%s|target=%02d|source=%02d|removed=%s|added=%s|kept=%s" %
                   (MARK, run, t["ordinal"], t["source_ordinal"], removed, added, kept))


def _actor_readback(rows, passage, atm, prefix):
    return [_actor_plain(_find_actor(r["id"]), passage, atm, prefix) for r in rows]


def _require_actor_rows(actual, expected, message):
    diff = S.state_differences(expected, actual)
    require(not diff, "%s|diff=%s" % (message, canonical(diff[:8])))


def _verify_atmos_result(atmosphere, actual_rows, message):
    """Verify the intended semantic result, not merely a captured post-state."""
    by_id = {row["id"]: row for row in actual_rows}
    for change in atmosphere["changes"]:
        target_id = change["target"]["id"]
        require(target_id in by_id, "%s|ACTOR_MISSING|%s" % (message, target_id))
        actual = by_id[target_id]
        if change["action"] == "match_beam_actor":
            source = change["source"]
            keys = ("relative_transform", "static_mesh", "materials", "visible", "hidden_game")
            expected = {key: source.get(key) for key in keys}
            got = {key: actual.get(key) for key in keys}
            diff = [d for d in S.state_differences(expected, got)
                    # 8 Oct conductor: actor transforms round-trip with ~1e-8 float noise (live APPLY
                    # 20261008-050947 stopped on -699.126 vs -699.1259999999893); accept numeric drift < 1e-3.
                    if not (isinstance(d.get("before"), (int, float)) and isinstance(d.get("after"), (int, float))
                            and not isinstance(d.get("before"), bool)
                            and abs(float(d["before"]) - float(d["after"])) < 1.0e-3)]
            require(not diff, "%s|BEAM_MISMATCH|%s|diff=%s" %
                    (message, target_id, canonical(diff[:8])))
        elif change["action"] == "suppress_actor":
            require(actual.get("hidden_game") is True, "%s|NOT_HIDDEN|%s" % (message, target_id))
            if "visible" in actual:
                require(actual["visible"] is False, "%s|STILL_VISIBLE|%s" % (message, target_id))
        elif change["action"] == "zero_lfv":
            require(abs(float(actual["radial_fog_extinction"])) <= FLOAT_TOL,
                    "%s|RADIAL_FOG_NONZERO|%s" % (message, target_id))
            require(abs(float(actual["height_fog_extinction"])) <= FLOAT_TOL,
                    "%s|HEIGHT_FOG_NONZERO|%s" % (message, target_id))


def _verify_atmos_original(atmosphere, actual_rows, message):
    """Verify only the target fields each atmosphere action originally overwrote."""
    by_id = {row["id"]: row for row in actual_rows}
    for change in atmosphere["changes"]:
        expected = change["target"]
        target_id = expected["id"]
        require(target_id in by_id, "%s|ACTOR_MISSING|%s" % (message, target_id))
        actual = by_id[target_id]
        if change["action"] == "match_beam_actor":
            keys = ("relative_transform", "static_mesh", "materials", "visible", "hidden_game")
        elif change["action"] == "suppress_actor":
            keys = ("visible", "hidden_game")
        else:
            keys = ("radial_fog_extinction", "height_fog_extinction")
        diff = [d for d in S.state_differences({k: expected.get(k) for k in keys},
                                               {k: actual.get(k) for k in keys})
                if not (isinstance(d.get("before"), (int, float)) and isinstance(d.get("after"), (int, float))
                        and not isinstance(d.get("before"), bool)
                        and abs(float(d["before"]) - float(d["after"])) < 1.0e-3)]
        require(not diff, "%s|ORIGINAL_FIELD_MISMATCH|%s|diff=%s" %
                (message, target_id, canonical(diff[:8])))


def _run(args):
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = C.stamp_now()
    mode = args["mode"]
    source_prefix, target_prefix = args["source_passage"], args["target_passage"]
    source_number, target_number = passage_number(source_prefix), passage_number(target_prefix)
    report = {"ok": False, "mode": mode, "run": run, "args": args,
              "proof": "offline-authored; live results are measured only after conductor execution"}
    try:
        world, show, dirty_before = _context()
        if mode == "REVERT":
            require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_MISSING")
            record = C.load_json(RECORD_PATH)
            require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS")
            require(record["args"]["source_passage"] == source_prefix and
                    record["args"]["target_passage"] == target_prefix, "REVERT_PASSAGE_MISMATCH")
            _verify_owned_rows(show, record["plan"], "after")
            target_actor = _passage_actor(show, target_number)
            current_atmos = _actor_readback(record.get("atmos_after", []), target_actor,
                                            record["args"]["atmosphere"], target_prefix)
            _verify_atmos_result(record["atmosphere"], current_atmos, "REVERT_ATMOS_OWNED_DRIFT")
            unowned_before = _unowned_rows_hash(show, record["plan"])
            backup = C.backup_packages(
                unreal, "Pre%sLightingAs%sRevert-" % (target_prefix, source_prefix), run,
                [C.SHOW_PATH, C.EXPECTED_WORLD])
            for change in record["atmosphere"]["changes"]:
                _restore_actor_fields(change, target_actor)
            _restore_lights_field_scoped(show, record["plan"])
            require(_outside_hash(show, record["plan"]["target_cue_guids"]) == record["outside_before_hash"],
                    "REVERT_OUTSIDE_TARGET_CHANGED")
            require(_unowned_rows_hash(show, record["plan"]) == unowned_before,
                    "REVERT_UNOWNED_TARGET_ROWS_CHANGED")
            require(bool(target_actor.materialize_passage()), target_prefix + "_MATERIALIZE_FAILED")
            restored_atmos = _actor_readback(record.get("atmos_before", []), target_actor,
                                             record["args"]["atmosphere"], target_prefix)
            _verify_atmos_original(record["atmosphere"], restored_atmos, "REVERT_ATMOS_READBACK")
            expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
            require(C.dirty_census(unreal) == expected_dirty, "REVERT_DIRTY_SCOPE|%s" % C.dirty_census(unreal))
            C.save_show_and_level(unreal)
            show_rb = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
            _verify_owned_rows(show_rb, record["plan"], "before")
            restored_saved = _actor_readback(record.get("atmos_before", []), target_actor,
                                              record["args"]["atmosphere"], target_prefix)
            _verify_atmos_original(record["atmosphere"], restored_saved, "REVERT_ATMOS_SAVED_READBACK")
            command = C.queue_saved_master_test(unreal, world, MARK + "_REVERT", run)
            archived = C.archive_record(RECORD_PATH, run)
            report.update({"ok": True, "backup": backup, "record_archived": archived,
                           "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
            C.write_json(_report_path(mode, run), report)
            unreal.log("%s_REVERT_OK|run=%s|source=%s|target=%s|show_saved=1|level_saved=1|"
                       "field_scoped=1|readback=1|saved_master=queued" %
                       (MARK, run, source_prefix, target_prefix))
            return report

        plain = _plain_cues(show)
        source, source_guid = _passage_rows(show, passage_label(source_prefix), plain)
        target, target_guid = _passage_rows(show, passage_label(target_prefix), plain)
        plan = build_plan(source, target, args)
        plan.update({"source_passage_guid": source_guid, "target_passage_guid": target_guid,
                     "target_cue_guids": [t["cue_guid"] for t in plan["targets"]]})
        enforce_budgets(plan, args)
        plan["plan_sha256"] = state_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
        source_actor, source_atmos = _atmos_actors(
            show, source_number, args["atmosphere"], args["atmosphere"]["source_tag"])
        target_actor, target_atmos = _atmos_actors(
            show, target_number, args["atmosphere"], args["atmosphere"]["target_tag"])
        atmosphere = atmos_plan(source_atmos, target_atmos, len(target), args["match_source_atmosphere"])
        foreign = _foreign_records(target_prefix)
        special_level_actors = _special_level_actors(show, args)
        report.update({"dirty_before": dirty_before, "plan": plan, "atmosphere": atmosphere,
                       "foreign_active_records": foreign, "kept_special_level_actors": special_level_actors})
        preview = write_preview_png(_preview_path(mode, run), plan)
        report["preview"] = preview
        _log_table(run, plan)
        for actor in special_level_actors:
            unreal.log("%s_SPECIAL_ACTOR|run=%s|label=%s|class=%s|token=%s|action=KEEP_UNTOUCHED" %
                       (MARK, run, actor["label"], actor["class"], actor["matched_token"]))
        if mode == "DRY":
            require(C.dirty_census(unreal) == dirty_before, "DRY_CHANGED_CENSUS")
            report.update({"ok": True, "mutated": False, "dirty_after": C.dirty_census(unreal)})
            C.write_json(_report_path(mode, run), report)
            unreal.log("%s_DRY_OK|run=%s|source=%s|target=%s|source_bays=%d|target_bays=%d|"
                       "removed=%d|added=%d|projected_total=%d|shadows=%d|kept_specials=%d|"
                       "fallback_colours=%d|own_side_aimed=%d|atmos_changes=%d|count_cap=%d|"
                       "plan_sha256=%s|preview=%s|mutated=0" %
                       (MARK, run, source_prefix, target_prefix, plan["source_bays"], plan["target_bays"],
                        plan["counts"]["removed_lights"], plan["counts"]["added_lights"],
                        plan["counts"]["projected_target_lights"], plan["counts"]["shadow_casting_added"],
                        plan["counts"]["kept_specials"], plan["counts"]["dominant_fallbacks"],
                        len(plan["aim_mappings"]), len(atmosphere["changes"]), args["max_added_lights"],
                        plan["plan_sha256"], preview["path"]))
            return report

        require(args["expected_plan_sha256"] == plan["plan_sha256"],
                "PLAN_DRIFT|dry=%s|live=%s" % (args["expected_plan_sha256"], plan["plan_sha256"]))
        ack = {os.path.normcase(os.path.abspath(x)) for x in args["ack_records"]}
        unacked = [r["path"] for r in foreign if os.path.normcase(os.path.abspath(r["path"])) not in ack]
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_UNACKNOWLEDGED|" + ";".join(unacked))
        require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS")
        outside_before = _outside_hash(show, plan["target_cue_guids"])
        gpu_cursor = _gpu_log_cursor()
        backup = C.backup_packages(
            unreal, "Pre%sLightingAs%s-" % (target_prefix, source_prefix), run,
            [C.SHOW_PATH, C.EXPECTED_WORLD])
        record = {"schema_version": 3, "status": "prepared", "run": run, "args": args, "plan": plan,
                   "atmosphere": atmosphere, "atmos_before": target_atmos, "backup": backup,
                  "outside_before_hash": outside_before, "acknowledged_records": sorted(ack),
                  "dirty_before": dirty_before,
                  "gpu_health_probe": dict({"status": "PENDING", "command": GPU_PROBE_COMMAND},
                                           **gpu_cursor),
                  "immediate_revert": {"status": "READY_AFTER_SAVED_READBACK",
                                       "field_scoped": True,
                                       "command": IMMEDIATE_REVERT_COMMAND}}
        C.write_json(RECORD_PATH, record, exclusive=True)
        try:
            added = _mutate_lights(show, plan)
            if atmosphere["enabled"]:
                for change in atmosphere["changes"]:
                    if change["action"] == "match_beam_actor":
                        _apply_actor_state(change["target"], target_actor, source=change["source"])
                    elif change["action"] == "zero_lfv":
                        _apply_actor_state(change["target"], target_actor, zero_lfv=True)
                    else:
                        _apply_actor_state(change["target"], target_actor, suppress=True)
            record["atmos_after"] = _actor_readback(target_atmos, target_actor, args["atmosphere"], target_prefix)
            _verify_atmos_result(atmosphere, record["atmos_after"], "ATMOS_WRITE_READBACK")
        except Exception as original:
            import traceback
            unreal.log_error("%s_ORIGINAL_ERROR|run=%s|%r|%s" % (
                MARK, run, original, traceback.format_exc().replace(chr(10), " / ")[-1500:]))
            _restore_lights_snapshot(show, plan)
            for change in atmosphere["changes"]:
                _restore_actor_fields(change, target_actor)
            record["status"] = "failed_rolled_back_in_memory"
            C.write_json(RECORD_PATH, record)
            os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
            raise
        _verify_owned_rows(show, plan, "after")
        require(_outside_hash(show, plan["target_cue_guids"]) == outside_before, "OUTSIDE_TARGET_CHANGED")
        require(bool(target_actor.materialize_passage()), target_prefix + "_MATERIALIZE_FAILED")
        expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
        require(C.dirty_census(unreal) == expected_dirty, "APPLY_DIRTY_SCOPE|%s" % C.dirty_census(unreal))
        record.update({"status": "mutated_verified", "plan": plan, "added_count": added})
        C.write_json(RECORD_PATH, record)
        C.save_show_and_level(unreal)
        show_rb = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        _verify_owned_rows(show_rb, plan, "after")
        saved_atmos = _actor_readback(record["atmos_after"], target_actor, args["atmosphere"], target_prefix)
        _verify_atmos_result(atmosphere, saved_atmos, "ATMOS_SAVED_SEMANTICS")
        perf_hook = {"status": "PENDING", "required": True,
                      "relative_saved_path": args["perf_probe"]["relative_saved_path"],
                      "args_path": os.path.join(HERE, "passage_lighting_perf_probe_args.json"),
                      "request_path": os.path.join(HERE, "passage_lighting_perf_probe_request.json"),
                      "command": GPU_PROBE_COMMAND,
                      "gpu_loss_log_scan": True,
                      "thresholds": {"max_p95_ms": args["perf_probe"]["max_p95_ms"],
                                     "max_p99_ms": args["perf_probe"]["max_p99_ms"]}}
        record.update({"status": "saved_readback_verified", "saved_census": C.dirty_census(unreal),
                       "post_apply_perf_gate": perf_hook})
        C.write_json(RECORD_PATH, record)
        command = C.queue_saved_master_test(unreal, world, MARK, run)
        report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "added_count": added,
                        "dirty_after": C.dirty_census(unreal), "saved_master_command": command,
                       "post_apply_perf_gate": perf_hook,
                       "gpu_health_probe_command": GPU_PROBE_COMMAND,
                       "immediate_revert_command": IMMEDIATE_REVERT_COMMAND})
        C.write_json(_report_path(mode, run), report)
        unreal.log("%s_APPLY_OK|run=%s|source=%s|target=%s|removed=%d|added=%d|kept_specials=%d|"
                   "atmos_changes=%d|show_saved=1|level_saved=1|field_scoped=1|readback=1|"
                   "saved_master=queued|gpu_health=PENDING|gpu_probe_command=%s|"
                   "immediate_revert_command=%s|perf_hook=%s" %
                   (MARK, run, source_prefix, target_prefix, plan["counts"]["removed_lights"], added,
                     plan["counts"]["kept_specials"], len(atmosphere["changes"]),
                     GPU_PROBE_COMMAND, IMMEDIATE_REVERT_COMMAND,
                     args["perf_probe"]["relative_saved_path"]))
        return report
    except Exception as error:
        report["error"] = "%s: %s" % (type(error).__name__, error)
        try:
            report["census_at_stop"] = C.dirty_census(unreal)
        except Exception:
            pass
        C.write_json(_report_path(mode + "_STOPPED", run), report)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|%s|census=%s|if dirty: Don't-Save restart" %
                         (MARK, run, mode, report["error"], report.get("census_at_stop")))
        raise

def main(raw=None):
    if raw is None:
        raw = C.load_json(ARGS_PATH) if os.path.isfile(ARGS_PATH) else {}
    return _run(check_args(raw))


if unreal is not None and __name__ in ("__main__", "__passage_lighting_runner__"):
    main(globals().get("PASSAGE_LIGHTING_ARGS"))
