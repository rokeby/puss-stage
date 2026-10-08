"""P16: make Passage 03 use Passage 01's lighting structure, but keep P03 colour.

Offline-authored only.  The conductor runs this later through
``p03_lighting_as_p01_run.py``.  Modes are DRY / APPLY / REVERT.

Authority and safety contract (declaration-proven unless marked otherwise):

* Lights live in ``FInfinityWingOccurrence::Attachments`` and are materialised
  by ``AInfinityStagePassageActor``.  The Show asset is therefore written first,
  Passage 03 alone is materialised, then only the Show and current level save.
* APPLY copies every ordinary P01 LIGHT at the same WingPair ordinal (wrapping
  when P03 is longer), including transform, type, intensity, cone, attenuation,
  shadows, light function and Drama.  It substitutes P03 colour/temperature by
  label-derived role; a missing role uses P03's dominant existing colour and is
  reported.
* P03 EFFECT/PROP attachments, labels/tags naming car/move/event/fx/smoke/etc.,
  and keyed lights whose role has no P01 counterpart are retained verbatim.
* ``match_p01_atmosphere`` defaults true.  Existing P03 BeamLook actors are
  moved/material-matched to the P01ATMOS BeamLook actors that fall within the
  mapped ordinal range; P03 Smoke Test actors and unmatched atmosphere actors
  are suppressed, not deleted.  Unmatched P03 LocalFogVolumes have extinction
  set to zero.  This is deliberately reversible and makes no asset deletion.
* A record and ``Backups/PreP03LightingAsP01-<run>`` (Show + level) precede the
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
RECORD_PATH = os.path.join(HERE, "p03_lighting_as_p01_record.json")
ARGS_PATH = os.path.join(HERE, "p03_lighting_as_p01_args.json")
MARK = "P03ASP01"
SOURCE_PASSAGE = "Passage 1"
TARGET_PASSAGE = "Passage 3"
SOURCE_PREFIX = "P01"
TARGET_PREFIX = "P03"
MANAGED_PREFIX = "P03 P01STRUCT"
FLOAT_TOL = 1.0e-4
TERMINAL_RECORD_STATUSES = {"reverted", "archived", "complete", "failed", "failed_rolled_back_in_memory"}
MOVER_FIELDS = ("enabled", "trigger", "approach_distance_cm", "yaw_amplitude_degrees",
                "pitch_amplitude_degrees", "steps_per_second", "ease_fraction", "calm_scale",
                "erratic_ramp_cm", "seed")
BODY_FIELDS = ("follow_light", "light_attachment_guid", "intensity_parameter", "full_intensity",
               "flicker", "seed", "slight_depth", "flicker_rate_hz", "fail_window_cm",
               "fail_at_cm", "flicker_also_drives_light")


def _load(name):
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location("_p03asp01_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load("_fx_authoring_common")
S = _load("_infinity_attachment_state")

DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "expected_plan_sha256": "",
    "match_p01_atmosphere": True,
    "special_label_tokens": [
        "car", "moving", "move", "event", "fx", "smoke", "haze", "fire",
        "rain", "spark", "mote", "pyro", "polaroid", "flash",
    ],
    "atmosphere": {
        "source_tag": "P01ATMOS",
        "target_tag": "P03ATMOS",
        "beam_tag": "InfinityStage.BeamLook",
        "smoke_tag": "InfinityStage.SmokeTest",
        "footprint_x_cm": [-2000.0, 20000.0],
        "footprint_half_y_cm": 6000.0,
        "footprint_half_z_cm": 6000.0,
    },
    "ack_records": [],
}


class P03AsP01Error(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise P03AsP01Error(str(message))


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
    require(isinstance(out["match_p01_atmosphere"], bool), "MATCH_ATMOS_NOT_BOOL")
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
    require(isinstance(out["ack_records"], list) and all(isinstance(x, str) for x in out["ack_records"]),
            "ACK_RECORDS_INVALID")
    return out


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
    managed = re.search(r"\bP01STRUCT\s+B\d+\s+(.+)$", text, re.I)
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
        return "keyed_without_p01_counterpart"
    return None


def colour_signature(row):
    lighting = row.get("lighting") or {}
    rgba = list(lighting.get("color") or [1.0, 1.0, 1.0, 1.0])
    while len(rgba) < 4:
        rgba.append(1.0)
    # 8 Oct conductor: keep P03's HUE only. P03 dims some lights through near-black RGB (e.g. all 42 "Low" lights
    # 0.0006/0.0006/0.0012); copying raw RGB would leave P01's structure dark in P03. Brightness comes from P01's
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
    require(lights, "P03_HAS_NO_LIGHT_COLOUR")
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


def build_plan(source_cues, target_cues, args):
    require(source_cues and target_cues, "PASSAGE_BAYS_EMPTY")
    all_target = [a for c in target_cues for a in c["attachments"]]
    colours = role_colours(all_target)
    dominant = dominant_colour(all_target)
    targets, colour_mappings = [], []
    wrapped = len(target_cues) > len(source_cues)
    for ordinal, target in enumerate(target_cues, start=1):
        source_ordinal = ((ordinal - 1) % len(source_cues)) + 1
        source = source_cues[source_ordinal - 1]
        source_lights = [r for r in source["attachments"] if is_light(r)]
        source_roles = {role_from_label(r["label"]) for r in source_lights}
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
            row = apply_colour(source_row, colour)
            row["guid"] = None  # minted by replication during APPLY
            row["label"] = "%s B%02d %s" % (MANAGED_PREFIX, ordinal, role)
            added.append(row)
            colour_mappings.append({
                "p03_ordinal": ordinal, "source_ordinal": source_ordinal, "role": role,
                "mapping": mapping, "colour": colour,
            })
        targets.append({
            "ordinal": ordinal, "source_ordinal": source_ordinal,
            "cue_guid": target["guid"], "cue_label": target["label"],
            "source_cue_guid": source["guid"], "source_cue_label": source["label"],
            "show_index": target["show_index"], "source_show_index": source["show_index"],
            "before_rows": copy.deepcopy(target["attachments"]),
            "cue_tags": list(target.get("tags", [])),
            "kept": kept, "removed": removed, "added_specs": added,
            "wing_y": list(target.get("wing_y") or [-900.0, 900.0]),
            "source_wing_y": list(source.get("wing_y") or [-900.0, 900.0]),
        })
    plan = {
        "source_bays": len(source_cues), "target_bays": len(target_cues),
        "wrapped": wrapped, "wrap_count": max(0, len(target_cues) - len(source_cues)),
        "dominant_colour": dominant, "role_colours": colours,
        "colour_mappings": colour_mappings, "targets": targets,
        "counts": {
            "removed_lights": sum(len(t["removed"]) for t in targets),
            "added_lights": sum(len(t["added_specs"]) for t in targets),
            "kept_specials": sum(1 for t in targets for k in t["kept"]
                                 if is_light(k["row"]) or is_effect(k["row"])),
            "kept_nonlights": sum(1 for t in targets for k in t["kept"] if not is_light(k["row"])),
            "dominant_fallbacks": sum(m["mapping"] == "dominant" for m in colour_mappings),
        },
    }
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
            changes.append({"action": "suppress_actor", "target": target, "reason": "no_p01_counterpart"})
    for target in target_actors:
        if target.get("beam"):
            continue
        if target.get("lfv"):
            changes.append({"action": "zero_lfv", "target": target})
        else:
            changes.append({"action": "suppress_actor", "target": target,
                            "reason": "p03_atmosphere_without_p01_counterpart"})
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

    source_rows = [[r for r in t["added_specs"]] for t in plan["targets"]]
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
    a.set_editor_property("label", unreal.Text("P03ASP01 GUID SCRATCH"))
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


def _atmos_actors(show, number, atm):
    passage = _passage_actor(show, number)
    prefix = "P%02d" % number
    own_tag = atm["source_tag"] if number == 1 else atm["target_tag"]
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
    """Inventory P03-local named special actors; this tool never writes them."""
    passage = _passage_actor(show, 3)
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
                    or actor.get_attach_parent_actor() == passage or label.upper().startswith("P03")):
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


def _mutate_lights(show, plan):
    target_guids = {t["cue_guid"] for t in plan["targets"]}
    cues = list(show.get_editor_property("cues"))
    scratch = next((i for i, c in enumerate(cues)
                    if _guid_text(c.get_editor_property("cue_guid")) not in target_guids
                    and enum_name(c.get_editor_property("type")) == "WING_PAIR"
                    and "P01 " not in str(c.get_editor_property("label"))), None)
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


def _restore_lights(show, plan):
    for target in plan["targets"]:
        rebuilt = [_attachment_from_state(row, preserve_guid=True) for row in target["before_rows"]]
        _set_pair_attachments(show, _show_index(show, target["cue_guid"]), rebuilt)


def _verify_rows(show, plan, side):
    for target in plan["targets"]:
        got = [_full_attachment_state(a) for a in _pair_attachments(show, _show_index(show, target["cue_guid"]))]
        expected = target["after_rows"] if side == "after" else target["before_rows"]
        diff = S.state_differences(expected, got)
        require(not diff, "%s_READBACK|cue=%s|diff=%s" % (side.upper(), target["cue_label"], canonical(diff[:8])))


def _foreign_records():
    rows = []
    for name in os.listdir(HERE):
        if not (name.endswith(".json") and "record" in name.lower() and "p03" in name.lower()):
            continue
        path = os.path.join(HERE, name)
        if path == RECORD_PATH:
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
    return os.path.join(HERE, "p03_lighting_as_p01_report_%s_%s.json" % (mode, run))


def _preview_path(mode, run):
    return os.path.join(HERE, "p03_lighting_as_p01_preview_%s_%s.png" % (mode, run))


def _log_table(run, plan):
    for t in plan["targets"]:
        removed = ",".join(r["label"] for r in t["removed"]) or "-"
        added = ",".join(r["label"] for r in t["added_specs"]) or "-"
        kept = ",".join("%s{%s}" % (k["row"]["label"], k["reason"]) for k in t["kept"]
                        if is_light(k["row"]) or is_effect(k["row"])) or "-"
        unreal.log("%s_DRY_ROW|run=%s|p03=%02d|p01=%02d|removed=%s|added=%s|kept=%s" %
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
            diff = S.state_differences(expected, got)
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


def _run(args):
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = C.stamp_now()
    mode = args["mode"]
    report = {"ok": False, "mode": mode, "run": run, "args": args,
              "proof": "offline-authored; live results are measured only after conductor execution"}
    try:
        world, show, dirty_before = _context()
        if mode == "REVERT":
            require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_MISSING")
            record = C.load_json(RECORD_PATH)
            require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS")
            _verify_rows(show, record["plan"], "after")
            p03_actor = _passage_actor(show, 3)
            current_atmos = _actor_readback(record.get("atmos_after", []), p03_actor,
                                            record["args"]["atmosphere"], TARGET_PREFIX)
            _require_actor_rows(current_atmos, record.get("atmos_after", []), "REVERT_ATMOS_DRIFT")
            backup = C.backup_packages(unreal, "PreP03LightingAsP01Revert-", run,
                                       [C.SHOW_PATH, C.EXPECTED_WORLD])
            for row in record.get("atmos_before", []):
                _restore_actor_state(row, p03_actor)
            _restore_lights(show, record["plan"])
            require(_outside_hash(show, record["plan"]["target_cue_guids"]) == record["outside_before_hash"],
                    "REVERT_OUTSIDE_CHANGED")
            materialized = C.find_passage_actor(unreal, show, 3).materialize_passage()
            require(bool(materialized), "P03_MATERIALIZE_FAILED")
            restored_atmos = _actor_readback(record.get("atmos_before", []), p03_actor,
                                             record["args"]["atmosphere"], TARGET_PREFIX)
            _require_actor_rows(restored_atmos, record.get("atmos_before", []), "REVERT_ATMOS_READBACK")
            expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
            require(C.dirty_census(unreal) == expected_dirty, "REVERT_DIRTY_SCOPE|%s" % C.dirty_census(unreal))
            C.save_show_and_level(unreal)
            show_rb = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
            _verify_rows(show_rb, record["plan"], "before")
            restored_saved = _actor_readback(record.get("atmos_before", []), p03_actor,
                                              record["args"]["atmosphere"], TARGET_PREFIX)
            _require_actor_rows(restored_saved, record.get("atmos_before", []), "REVERT_ATMOS_SAVED_READBACK")
            command = C.queue_saved_master_test(unreal, world, MARK + "_REVERT", run)
            archived = C.archive_record(RECORD_PATH, run)
            report.update({"ok": True, "backup": backup, "record_archived": archived,
                           "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
            C.write_json(_report_path(mode, run), report)
            unreal.log("%s_REVERT_OK|run=%s|show_saved=1|level_saved=1|readback=1|saved_master=queued" % (MARK, run))
            return report

        plain = _plain_cues(show)
        source, source_guid = _passage_rows(show, SOURCE_PASSAGE, plain)
        target, target_guid = _passage_rows(show, TARGET_PASSAGE, plain)
        plan = build_plan(source, target, args)
        plan.update({"source_passage_guid": source_guid, "target_passage_guid": target_guid,
                     "target_cue_guids": [t["cue_guid"] for t in plan["targets"]]})
        # Hash includes live passage identity but excludes itself.
        plan["plan_sha256"] = state_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
        p01_actor, p01_atmos = _atmos_actors(show, 1, args["atmosphere"])
        p03_actor, p03_atmos = _atmos_actors(show, 3, args["atmosphere"])
        atmosphere = atmos_plan(p01_atmos, p03_atmos, len(target), args["match_p01_atmosphere"])
        foreign = _foreign_records()
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
            unreal.log("%s_DRY_OK|run=%s|p01_bays=%d|p03_bays=%d|removed=%d|added=%d|kept_specials=%d|"
                       "wrapped=%d|fallback_colours=%d|atmos_changes=%d|plan_sha256=%s|preview=%s|mutated=0" %
                       (MARK, run, plan["source_bays"], plan["target_bays"], plan["counts"]["removed_lights"],
                        plan["counts"]["added_lights"], plan["counts"]["kept_specials"], int(plan["wrapped"]),
                        plan["counts"]["dominant_fallbacks"], len(atmosphere["changes"]), plan["plan_sha256"],
                        preview["path"]))
            return report

        require(args["expected_plan_sha256"] == plan["plan_sha256"],
                "PLAN_DRIFT|dry=%s|live=%s" % (args["expected_plan_sha256"], plan["plan_sha256"]))
        ack = {os.path.normcase(os.path.abspath(x)) for x in args["ack_records"]}
        unacked = [r["path"] for r in foreign if os.path.normcase(os.path.abspath(r["path"])) not in ack]
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_UNACKNOWLEDGED|" + ";".join(unacked))
        require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS")
        outside_before = _outside_hash(show, plan["target_cue_guids"])
        backup = C.backup_packages(unreal, "PreP03LightingAsP01-", run, [C.SHOW_PATH, C.EXPECTED_WORLD])
        record = {"schema_version": 1, "status": "prepared", "run": run, "args": args, "plan": plan,
                  "atmosphere": atmosphere, "atmos_before": p03_atmos, "backup": backup,
                  "outside_before_hash": outside_before, "acknowledged_records": sorted(ack)}
        C.write_json(RECORD_PATH, record, exclusive=True)
        try:
            added = _mutate_lights(show, plan)
            if atmosphere["enabled"]:
                for change in atmosphere["changes"]:
                    if change["action"] == "match_beam_actor":
                        _apply_actor_state(change["target"], p03_actor, source=change["source"])
                    elif change["action"] == "zero_lfv":
                        _apply_actor_state(change["target"], p03_actor, zero_lfv=True)
                    else:
                        _apply_actor_state(change["target"], p03_actor, suppress=True)
            record["atmos_after"] = _actor_readback(p03_atmos, p03_actor, args["atmosphere"], TARGET_PREFIX)
            _verify_atmos_result(atmosphere, record["atmos_after"], "ATMOS_WRITE_READBACK")
        except Exception as original:
            import traceback
            unreal.log_error("%s_ORIGINAL_ERROR|run=%s|%r|%s" % (MARK, run, original,
                             traceback.format_exc().replace(chr(10), " / ")[-1500:]))
            _restore_lights(show, plan)
            for row in p03_atmos:
                _restore_actor_state(row, p03_actor)
            record["status"] = "failed_rolled_back_in_memory"
            C.write_json(RECORD_PATH, record)
            os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
            raise
        _verify_rows(show, plan, "after")
        require(_outside_hash(show, plan["target_cue_guids"]) == outside_before, "OUTSIDE_P03_CHANGED")
        require(bool(p03_actor.materialize_passage()), "P03_MATERIALIZE_FAILED")
        expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
        require(C.dirty_census(unreal) == expected_dirty, "APPLY_DIRTY_SCOPE|%s" % C.dirty_census(unreal))
        record.update({"status": "mutated_verified", "plan": plan, "added_count": added})
        C.write_json(RECORD_PATH, record)
        C.save_show_and_level(unreal)
        show_rb = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        _verify_rows(show_rb, plan, "after")
        saved_atmos = _actor_readback(record["atmos_after"], p03_actor, args["atmosphere"], TARGET_PREFIX)
        _require_actor_rows(saved_atmos, record["atmos_after"], "ATMOS_SAVED_READBACK")
        _verify_atmos_result(atmosphere, saved_atmos, "ATMOS_SAVED_SEMANTICS")
        record.update({"status": "saved_readback_verified", "saved_census": C.dirty_census(unreal)})
        C.write_json(RECORD_PATH, record)
        command = C.queue_saved_master_test(unreal, world, MARK, run)
        report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "added_count": added,
                       "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
        C.write_json(_report_path(mode, run), report)
        unreal.log("%s_APPLY_OK|run=%s|removed=%d|added=%d|kept_specials=%d|atmos_changes=%d|"
                   "show_saved=1|level_saved=1|readback=1|saved_master=queued" %
                   (MARK, run, plan["counts"]["removed_lights"], added, plan["counts"]["kept_specials"],
                    len(atmosphere["changes"])))
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


if unreal is not None and __name__ in ("__main__", "__p03_lighting_as_p01_runner__"):
    main(globals().get("P03ASP01_ARGS"))
