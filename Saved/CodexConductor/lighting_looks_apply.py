"""Guarded P04 lighting-look prototype authoring tool.

Modes are DRY (default), APPLY, and REVERT. Set ``LIGHTING_LOOKS_MODE`` through
``runpy.run_path(..., init_globals={...})`` when executing in Unreal.

The intensity ramp uses the project's existing distance route, not Sequencer:

* ``FInfinityStageLightDrama`` declares strike-on-approach as camera-distance
  driven (InfinityStageLightDrama.h:20-31).
* ``EvaluateStrike`` maps the last ``StrikeRampCm`` to intensity
  (InfinityStageLightDrama.cpp:24-59).
* ``AInfinityStagePassageActor`` evaluates it against the camera and lamp route
  distances in game worlds (InfinityStagePassageActor.cpp:1620-1660).

No source or Plugin file is modified. APPLY and REVERT back up the Show and
level, materialize Passage 04 only, save only those two packages, read the Show
back, require a clean census, and queue only SavedMasterMatchesShow.
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


def _load_attachment_state():
    try:
        import _infinity_attachment_state as module
        return module
    except ModuleNotFoundError:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_infinity_attachment_state.py")
        spec = importlib.util.spec_from_file_location("_infinity_attachment_state", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


S = _load_attachment_state()


EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
PASSAGE_NUMBER = 4
P04_LABEL = re.compile(r"^P04 Wing (\d{3})$")
VALID_MODES = ("DRY", "APPLY", "REVERT")
VALID_ROLES = ("TOP", "LOW_SIDE", "BEAM", "PRACTICAL")
ROLE_LIMITS = {"TOP": (2, 2), "LOW_SIDE": (2, 2), "BEAM": (0, 1), "PRACTICAL": (0, 2)}
REQUIRED_LOOKS = {"MOODY", "INDUSTRIAL", "THEATRICAL", "SPOT", "WASH"}
LIGHT_FIELDS = S.LIGHT_FIELDS
LIGHT_OBJECT_FIELDS = S.LIGHT_OBJECT_FIELDS
DRAMA_FIELDS = S.DRAMA_FIELDS
EFFECT_FIELDS = S.EFFECT_FIELDS
EFFECT_GUID_FIELDS = S.EFFECT_GUID_FIELDS
EFFECT_OBJECT_FIELDS = S.EFFECT_OBJECT_FIELDS
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lighting_looks.json")
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lighting_looks_report.json")
RECORD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lighting_looks_revert_record.json")


class LightingLooksError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise LightingLooksError(str(message))


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


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _state_hash(value):
    return _sha256_bytes(_canonical(value).encode("utf-8"))


def load_config(path=CONFIG_PATH):
    data = _read_json(path)
    validate_config(data)
    return data


def validate_config(data):
    require(data.get("schema_version") == 1, "CONFIG_SCHEMA_NOT_1")
    require(data.get("existing_light_policy") == "disable_all_in_target_bay",
            "EXISTING_LIGHT_POLICY_UNSAFE")
    keying = data.get("distance_keying", {})
    require(keying.get("mechanism") == "FInfinityStageLightDrama strike-on-approach",
            "DISTANCE_MECHANISM_WRONG")
    require(abs(_finite(keying.get("ramp_distance_cm"), "RAMP_DISTANCE") - 150.0) < 1.0e-9,
            "RAMP_NOT_150_CM")
    require(_finite(keying.get("strike_distance_cm"), "STRIKE_DISTANCE") >= 0.0,
            "NEGATIVE_STRIKE_DISTANCE")
    require(keying.get("after_pass") == "HOLD", "AFTER_PASS_NOT_HOLD")
    require(data.get("shadow_budget", {}).get("rule") == "after_lte_before",
            "SHADOW_BUDGET_RULE_WRONG")

    looks = data.get("looks", {})
    require(set(looks) == REQUIRED_LOOKS,
            "LOOK_SET_WRONG|actual=%s" % ",".join(sorted(looks)))
    all_slots = {}
    for look_name, look in sorted(looks.items()):
        instruments = look.get("instruments", [])
        require(instruments, "LOOK_EMPTY|look=" + look_name)
        slots = [row.get("slot") for row in instruments]
        require(len(slots) == len(set(slots)), "DUPLICATE_SLOT|look=" + look_name)
        counts = {role: 0 for role in VALID_ROLES}
        for row in instruments:
            role = row.get("role")
            require(role in VALID_ROLES, "BAD_ROLE|look=%s|role=%s" % (look_name, role))
            counts[role] += 1
            require(row.get("type") in ("SPOT", "POINT", "RECT"),
                    "BAD_LIGHT_TYPE|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(row.get("intensity_units") in ("CANDELAS", "LUMENS"),
                    "BAD_UNITS|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(_finite(row.get("intensity"), "INTENSITY") >= 0.0,
                    "NEGATIVE_INTENSITY|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(_finite(row.get("attenuation_cm"), "ATTENUATION") > 0.0,
                    "BAD_ATTENUATION|look=%s|slot=%s" % (look_name, row.get("slot")))
            rgb = row.get("color_rgb_linear", [])
            require(len(rgb) == 3 and all(_finite(v, "RGB") >= 0.0 for v in rgb),
                    "BAD_RGB|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(1000.0 <= _finite(row.get("temperature_kelvin"), "TEMPERATURE") <= 15000.0,
                    "BAD_TEMPERATURE|look=%s|slot=%s" % (look_name, row.get("slot")))
            transform = row.get("transform", {})
            require(len(transform.get("location_cm", [])) == 3
                    and len(transform.get("rotation_rpy_deg", [])) == 3,
                    "BAD_TRANSFORM|look=%s|slot=%s" % (look_name, row.get("slot")))
            if row.get("type") == "SPOT":
                inner = _finite(row.get("inner_cone_deg"), "INNER_CONE")
                outer = _finite(row.get("outer_cone_deg"), "OUTER_CONE")
                require(0.0 <= inner <= outer <= 89.0,
                        "BAD_CONE|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(not row.get("cast_shadows") or role == "LOW_SIDE",
                    "NON_SIDE_SHADOW_CASTER|look=%s|slot=%s" % (look_name, row.get("slot")))
            flicker = row.get("flicker", {})
            require("mode" in flicker and "material" in flicker,
                    "FLICKER_UNDECLARED|look=%s|slot=%s" % (look_name, row.get("slot")))
        for role, (minimum, maximum) in ROLE_LIMITS.items():
            require(minimum <= counts[role] <= maximum,
                    "ROLE_COUNT|look=%s|role=%s|count=%d" % (look_name, role, counts[role]))
        require(sum(1 for row in instruments if row.get("cast_shadows")) == 2,
                "LOOK_SHADOW_CASTERS_NOT_2|look=" + look_name)
        all_slots[look_name] = slots

    for look_name, expected_ratio in (("MOODY", 16.0), ("THEATRICAL", 4.0)):
        sides = [float(row["intensity"]) for row in looks[look_name]["instruments"]
                 if row["role"] == "LOW_SIDE"]
        actual = max(sides) / min(sides)
        require(abs(actual - expected_ratio) < 1.0e-9,
                "KEY_FILL_RATIO|look=%s|actual=%s" % (look_name, actual))
        require(abs(float(looks[look_name]["key_fill_ratio"]) - expected_ratio) < 1.0e-9,
                "KEY_FILL_METADATA|look=" + look_name)

    bays = data.get("bay_plan", [])
    require([row.get("bay_index") for row in bays] == list(range(1, 7)),
            "BAY_PLAN_NOT_1_TO_6")
    require([row.get("look") for row in bays]
            == ["MOODY", "MOODY", "INDUSTRIAL", "INDUSTRIAL", "THEATRICAL", "THEATRICAL"],
            "BAY_LOOK_ORDER_WRONG")
    for row in bays:
        expected = "P04 Wing %03d" % row["bay_index"]
        require(row.get("expected_label") == expected,
                "BAY_LABEL_WRONG|bay=%s" % row.get("bay_index"))
        require(row.get("resolve_identity") == "read fresh Show index and CueGuid",
                "BAY_IDENTITY_NOT_FRESH|bay=%s" % row.get("bay_index"))
        require(_finite(row.get("level_scale"), "LEVEL_SCALE") > 0.0,
                "BAD_LEVEL_SCALE|bay=%s" % row.get("bay_index"))
        require(row["look"] in all_slots, "UNKNOWN_BAY_LOOK|bay=%s" % row["bay_index"])


def fixture_label(config, bay_index, look_name, slot):
    return "%s B%02d %s %s" % (
        config["fixture_label_prefix"], int(bay_index), look_name, slot)


def expand_bay(config, bay_row):
    look_name = bay_row["look"]
    scale = float(bay_row["level_scale"])
    expanded = []
    for source in config["looks"][look_name]["instruments"]:
        row = copy.deepcopy(source)
        row["intensity"] = float(row["intensity"]) * scale
        row["label"] = fixture_label(config, bay_row["bay_index"], look_name, row["slot"])
        row["bay_index"] = int(bay_row["bay_index"])
        row["look"] = look_name
        row["distance_keying"] = copy.deepcopy(config["distance_keying"])
        expanded.append(row)
    return expanded


def _plain_is_light(attachment):
    return str(attachment.get("kind", "")).upper() == "LIGHT"


def _plain_casts(attachment):
    return (_plain_is_light(attachment) and bool(attachment.get("enabled", True))
            and bool(attachment.get("lighting", {}).get("cast_shadows", False)))


def _plain_p04(cue):
    return bool(P04_LABEL.match(str(cue.get("label", ""))))


def build_plain_plan(config, cues):
    """Resolve current cue index+GUID and prove the proposed scope/budget."""
    validate_config(config)
    cue_guids = [str(cue.get("guid", "")) for cue in cues]
    require(all(cue_guids) and len(cue_guids) == len(set(cue_guids)),
            "CUE_GUIDS_INVALID_OR_DUPLICATE")
    attachment_guids = [str(att.get("guid", "")) for cue in cues
                        for att in cue.get("attachments", [])]
    require(all(attachment_guids) and len(attachment_guids) == len(set(attachment_guids)),
            "ATTACHMENT_GUIDS_INVALID_OR_DUPLICATE")

    target_rows = []
    target_guid_set = set()
    new_labels = []
    for bay in config["bay_plan"]:
        matches = [(index, cue) for index, cue in enumerate(cues)
                   if cue.get("label") == bay["expected_label"]]
        require(len(matches) == 1,
                "TARGET_CUE_COUNT|label=%s|count=%d" % (bay["expected_label"], len(matches)))
        show_index, cue = matches[0]
        cue_guid = str(cue["guid"])
        target_guid_set.add(cue_guid)
        fixtures = expand_bay(config, bay)
        new_labels.extend(row["label"] for row in fixtures)
        current_lights = [att for att in cue.get("attachments", []) if _plain_is_light(att)]
        target_rows.append({
            "bay_index": bay["bay_index"],
            "look": bay["look"],
            "level_scale": bay["level_scale"],
            "show_index": show_index,
            "cue_label": cue["label"],
            "cue_guid": cue_guid,
            "existing_lights": len(current_lights),
            "existing_enabled_lights": sum(bool(att.get("enabled", True)) for att in current_lights),
            "existing_shadow_casters": sum(_plain_casts(att) for att in current_lights),
            "fixtures": fixtures,
            "fixture_count": len(fixtures),
            "new_shadow_casters": sum(bool(row["cast_shadows"]) for row in fixtures),
        })
    require(len(target_guid_set) == 6, "TARGET_GUIDS_NOT_UNIQUE")
    require(len(new_labels) == len(set(new_labels)), "NEW_LABELS_DUPLICATE")
    current_labels = {str(att.get("label", "")) for cue in cues
                      for att in cue.get("attachments", [])}
    clashes = sorted(current_labels.intersection(new_labels))
    require(not clashes, "PROTOTYPE_ALREADY_PRESENT|labels=" + ",".join(clashes))

    before = sum(_plain_casts(att) for cue in cues if _plain_p04(cue)
                 for att in cue.get("attachments", []))
    removed = sum(row["existing_shadow_casters"] for row in target_rows)
    added = sum(row["new_shadow_casters"] for row in target_rows)
    after = before - removed + added
    require(after <= before,
            "SHADOW_BUDGET_EXCEEDED|before=%d|after=%d|removed=%d|added=%d"
            % (before, after, removed, added))
    return {
        "targets": target_rows,
        "target_cue_guids": sorted(target_guid_set),
        "fixture_count": sum(row["fixture_count"] for row in target_rows),
        "existing_lights_disabled": sum(row["existing_lights"] for row in target_rows),
        "shadow": {
            "p04_before": before,
            "p04_after": after,
            "target_before": removed,
            "target_after": added,
            "budget_ok": after <= before,
        },
    }


def apply_plain_state(config, cues):
    """Offline model of the narrowly scoped mutation; used by the harness."""
    plan = build_plain_plan(config, cues)
    result = copy.deepcopy(cues)
    record = {"targets": {}}
    by_guid = {str(cue["guid"]): cue for cue in result}
    for target in plan["targets"]:
        cue = by_guid[target["cue_guid"]]
        record["targets"][target["cue_guid"]] = copy.deepcopy(cue["attachments"])
        for attachment in cue["attachments"]:
            if _plain_is_light(attachment):
                attachment["enabled"] = False
        for fixture in target["fixtures"]:
            cue["attachments"].append({
                "guid": "NEW-%02d-%s" % (target["bay_index"], fixture["slot"]),
                "label": fixture["label"],
                "kind": "Light",
                "enabled": True,
                "lighting": {
                    "cast_shadows": bool(fixture["cast_shadows"]),
                    "intensity": float(fixture["intensity"]),
                    "role": fixture["role"],
                },
            })
    return result, record, plan


def revert_plain_state(cues, record):
    result = copy.deepcopy(cues)
    by_guid = {str(cue["guid"]): cue for cue in result}
    require(set(record["targets"]).issubset(by_guid), "REVERT_TARGET_MISSING")
    for cue_guid, attachments in record["targets"].items():
        by_guid[cue_guid]["attachments"] = copy.deepcopy(attachments)
    return result


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
    compact = "".join(character for character in str(value).upper()
                      if character in "0123456789ABCDEF")
    return len(compact) == 32 and any(character != "0" for character in compact)


def _enum_member(enum_type, name):
    candidates = (name, name.upper(), name.title().replace("_", ""))
    for candidate in candidates:
        if hasattr(enum_type, candidate):
            return getattr(enum_type, candidate)
    raise LightingLooksError("ENUM_MEMBER_MISSING|enum=%s|name=%s" % (enum_type, name))


def _dirty_census():
    return {
        "content": sorted(_asset_id(package)
                          for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(_asset_id(package)
                       for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _require_context():
    project = os.path.normcase(os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))
    require(project.rstrip("\\/") == EXPECTED_PROJECT.rstrip("\\/"),
            "WRONG_PROJECT|actual=" + project)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(world is not None and _asset_id(world) == EXPECTED_WORLD,
            "WRONG_WORLD|actual=" + str(_asset_id(world)))
    sequence_library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    if sequence_library is not None:
        require(sequence_library.get_current_level_sequence() is None, "SEQUENCER_IS_OPEN")
    require(_dirty_census() == {"content": [], "maps": []},
            "DIRTY_BEFORE|census=" + _canonical(_dirty_census()))
    actor_class = getattr(unreal, "Actor", None)
    if actor_class is not None:
        actors = unreal.GameplayStatics.get_all_actors_of_class(world, actor_class)
        stray = sorted(actor.get_actor_label() for actor in actors
                       if actor.get_actor_label().startswith("ZZ_"))
        require(not stray, "STRAY_ZZ_ACTORS|labels=" + ",".join(stray))
    return world


def _is_light(attachment):
    return attachment.get_editor_property("kind") == _enum_member(
        unreal.InfinityAttachmentKind, "LIGHT")


def _attachment_row(attachment):
    return S.attachment_state(attachment, _guid_text)


def _attachment_rows(attachments):
    return [_attachment_row(attachment) for attachment in attachments]


def _state_differences(before, after, path=""):
    return S.state_differences(before, after, path)


def _require_attachment_rows_equal(actual, expected, message):
    differences = _state_differences(expected, actual)
    require(not differences, "%s|differences=%s" %
            (message, _canonical(differences)))


def _rows_hash(rows):
    return _state_hash(rows)


def _pair_attachments(cue):
    pair = cue.get_editor_property("wing_pair")
    return list(pair.get_editor_property("attachments"))


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
        for attachment in _pair_attachments(cue):
            settings = attachment.get_editor_property("lighting")
            attachments.append({
                "guid": _guid_text(attachment.get_editor_property("attachment_guid")),
                "label": str(attachment.get_editor_property("label")),
                "kind": "Light" if _is_light(attachment) else str(
                    attachment.get_editor_property("kind")),
                "enabled": bool(attachment.get_editor_property("enabled")),
                "lighting": {"cast_shadows": bool(settings.get_editor_property("cast_shadows"))},
            })
        rows.append({
            "show_index": index,
            "guid": _guid_text(cue.get_editor_property("cue_guid")),
            "label": str(cue.get_editor_property("label")),
            "attachments": attachments,
        })
    return rows


def _all_pair_rows(show):
    result = {}
    for cue in show.get_editor_property("cues"):
        guid = _guid_text(cue.get_editor_property("cue_guid"))
        result[guid] = _attachment_rows(_pair_attachments(cue))
    return result


def _show_index_by_guid(show, cue_guid):
    matches = [index for index, cue in enumerate(show.get_editor_property("cues"))
               if _guid_text(cue.get_editor_property("cue_guid")) == cue_guid]
    require(len(matches) == 1,
            "CUE_GUID_RESOLVE_COUNT|guid=%s|count=%d" % (cue_guid, len(matches)))
    return matches[0]


def _make_transform(row):
    location = row["transform"]["location_cm"]
    roll, pitch, yaw = row["transform"]["rotation_rpy_deg"]
    return unreal.Transform(
        location=unreal.Vector(*location),
        rotation=unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw),
        scale=unreal.Vector(1.0, 1.0, 1.0),
    )


def _look_at_rpy(source, target, label):
    """Return an Unreal X-forward look-at rotation in pair-local space."""
    dx = float(target[0]) - float(source[0])
    dy = float(target[1]) - float(source[1])
    dz = float(target[2]) - float(source[2])
    horizontal = math.hypot(dx, dy)
    require(horizontal > 1.0e-6 or abs(dz) > 1.0e-6,
            "TOP_AIM_ZERO_VECTOR|fixture=" + str(label))
    pitch = math.degrees(math.atan2(dz, horizontal))
    yaw = math.degrees(math.atan2(dy, dx))
    return [0.0, pitch, yaw]


def _apply_live_top_aims(show, plan):
    """Aim TOP_L/TOP_R at the live left/right panel origins for each bay.

    Both the lights and these panel locations are authored in pair-local space,
    so the resulting look-at rotation remains exact after the pair is placed on
    the P04 route. This deliberately replaces the JSON prototype's stale fixed
    rotations; the Show is read fresh immediately before DRY/APPLY.
    """
    cues = list(show.get_editor_property("cues"))
    for target in plan["targets"]:
        cue = cues[target["show_index"]]
        pair = cue.get_editor_property("wing_pair")
        panels = {
            "L": pair.get_editor_property("left"),
            "R": pair.get_editor_property("right"),
        }
        target["top_aims"] = []
        for fixture in target["fixtures"]:
            if fixture["role"] != "TOP":
                continue
            side = fixture["slot"].rsplit("_", 1)[-1]
            require(side in panels,
                    "TOP_SLOT_SIDE_UNKNOWN|fixture=" + fixture["label"])
            panel_transform = panels[side].get_editor_property("local_transform")
            panel_location = panel_transform.translation
            target_location = [
                float(panel_location.x),
                float(panel_location.y),
                float(panel_location.z),
            ]
            source_location = [float(value)
                               for value in fixture["transform"]["location_cm"]]
            rotation = _look_at_rpy(source_location, target_location, fixture["label"])
            fixture["transform"]["rotation_rpy_deg"] = rotation
            aim = {
                "fixture": fixture["label"],
                "panel": "LEFT" if side == "L" else "RIGHT",
                "source": "live Show panel local_transform",
                "source_relative_cm": source_location,
                "target_relative_cm": target_location,
                "rotation_rpy_deg": rotation,
            }
            fixture["live_top_aim"] = copy.deepcopy(aim)
            target["top_aims"].append(aim)
        require(len(target["top_aims"]) == 2,
                "TOP_AIM_COUNT|cue=%s|actual=%d" %
                (target["cue_label"], len(target["top_aims"])))
    return plan


def _make_blank_light():
    attachment = unreal.InfinityCueAttachment()
    attachment.set_editor_property("label", unreal.Text("P04 LOOK GUID SCRATCH"))
    attachment.set_editor_property("kind", _enum_member(unreal.InfinityAttachmentKind, "LIGHT"))
    attachment.set_editor_property("enabled", False)
    attachment.set_editor_property("anchor", _enum_member(unreal.InfinityAttachmentAnchor, "STATION"))
    settings = unreal.InfinityStageLightSettings()
    settings.set_editor_property("type", _enum_member(unreal.InfinityStageLightType, "SPOT"))
    settings.set_editor_property("intensity_units", _enum_member(
        unreal.InfinityStageLightIntensityUnits, "CANDELAS"))
    settings.set_editor_property("intensity", 0.0)
    settings.set_editor_property("cast_shadows", False)
    settings.set_editor_property("cast_volumetric_shadow", False)
    attachment.set_editor_property("lighting", settings)
    return attachment


def _make_light(row, materials):
    attachment = unreal.InfinityCueAttachment()
    attachment.set_editor_property("label", unreal.Text(row["label"]))
    attachment.set_editor_property("kind", _enum_member(unreal.InfinityAttachmentKind, "LIGHT"))
    attachment.set_editor_property("enabled", True)
    attachment.set_editor_property("anchor", _enum_member(unreal.InfinityAttachmentAnchor, "STATION"))
    attachment.set_editor_property("relative_transform", _make_transform(row))
    settings = unreal.InfinityStageLightSettings()
    settings.set_editor_property("type", _enum_member(unreal.InfinityStageLightType, row["type"]))
    settings.set_editor_property("intensity_units", _enum_member(
        unreal.InfinityStageLightIntensityUnits, row["intensity_units"]))
    settings.set_editor_property("intensity", float(row["intensity"]))
    rgb = row["color_rgb_linear"]
    settings.set_editor_property("color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    settings.set_editor_property("use_temperature", True)
    settings.set_editor_property("temperature_kelvin", float(row["temperature_kelvin"]))
    settings.set_editor_property("attenuation_radius_cm", float(row["attenuation_cm"]))
    settings.set_editor_property("cast_shadows", bool(row["cast_shadows"]))
    settings.set_editor_property("cast_volumetric_shadow", False)
    settings.set_editor_property("volumetric_scattering_intensity",
                                 float(row["volumetric_scattering"]))
    settings.set_editor_property("source_radius_cm", 2.0 if row["role"] != "PRACTICAL" else 4.0)
    settings.set_editor_property("soft_source_radius_cm", 8.0 if row["role"] != "PRACTICAL" else 12.0)
    if row["type"] == "SPOT":
        settings.set_editor_property("inner_cone_angle_degrees", float(row["inner_cone_deg"]))
        settings.set_editor_property("outer_cone_angle_degrees", float(row["outer_cone_deg"]))
    if row["type"] == "RECT":
        settings.set_editor_property("rect_source_width_cm", float(row["rect_source_width_cm"]))
        settings.set_editor_property("rect_source_height_cm", float(row["rect_source_height_cm"]))
    material_path = row["flicker"]["material"]
    if material_path:
        settings.set_editor_property("light_function_material", materials[material_path])
    drama = settings.get_editor_property("drama")
    keying = row["distance_keying"]
    drama.set_editor_property("strike_on_approach", True)
    drama.set_editor_property("strike_distance_cm", float(keying["strike_distance_cm"]))
    drama.set_editor_property("strike_ramp_cm", float(keying["ramp_distance_cm"]))
    drama.set_editor_property("ignition_stutter", 0.0)
    drama.set_editor_property("unstruck_intensity_scale",
                              float(keying["unstruck_intensity_scale"]))
    drama.set_editor_property("after_pass", _enum_member(
        unreal.InfinityLightAfterPass, keying["after_pass"]))
    drama.set_editor_property("slow_move", False)
    settings.set_editor_property("drama", drama)
    attachment.set_editor_property("lighting", settings)
    return attachment


def _overwrite_vessel(vessel, template):
    minted = _guid_text(vessel.get_editor_property("attachment_guid"))
    require(_valid_guid_text(minted), "MINTED_GUID_INVALID|guid=" + minted)
    for name in ("label", "kind", "enabled", "actor_class", "mesh", "anchor",
                 "relative_transform", "lighting", "effect", "trigger_distance_cm"):
        vessel.set_editor_property(name, template.get_editor_property(name))
    require(_guid_text(vessel.get_editor_property("attachment_guid")) == minted,
            "MINTED_GUID_CHANGED")
    return vessel


def _materials(config):
    paths = sorted({row["flicker"]["material"]
                    for look in config["looks"].values()
                    for row in look["instruments"] if row["flicker"]["material"]})
    loaded = {}
    for path in paths:
        asset = unreal.load_asset(path)
        require(asset is not None, "FLICKER_MATERIAL_MISSING|asset=" + path)
        loaded[path] = asset
    return loaded


def _package_file(package_path):
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    base = os.path.normpath(os.path.join(content, package_path[len("/Game/"):].replace("/", os.sep)))
    for extension in (".uasset", ".umap"):
        if os.path.isfile(base + extension):
            return base + extension
    raise LightingLooksError("PACKAGE_FILE_MISSING|package=" + package_path)


def _backup(prefix, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    root = os.path.join(project, "Backups", prefix + run)
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (SHOW_PATH, EXPECTED_WORLD):
        source = _package_file(package)
        relative = package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1]
        destination = os.path.join(root, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        source_hash = _sha256_file(source)
        require(source_hash == _sha256_file(destination),
                "BACKUP_HASH_MISMATCH|package=" + package)
        rows.append({"package": package, "source": source, "backup": destination,
                     "bytes": os.path.getsize(source), "sha256": source_hash})
    return {"root": root, "packages": rows}


def _materialize_p04(show):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passages = [actor for actor in subsystem.get_all_level_actors()
                if actor.get_class().get_name() == "InfinityStagePassageActor"
                and actor.get_actor_label().startswith("Passage 04")
                and actor.get_editor_property("show_asset") == show]
    require(len(passages) == 1, "P04_ACTOR_COUNT|count=%d" % len(passages))
    passage = passages[0]
    require(bool(passage.materialize_passage()), "P04_MATERIALIZE_FAILED")
    structures = [actor for actor in subsystem.get_all_level_actors()
                  if actor.get_class().get_name() == "InfinityStageStructureActor"
                  and actor.get_editor_property("passage") == passage]
    require(len(structures) == 1, "P04_STRUCTURE_COUNT|count=%d" % len(structures))
    structure = structures[0]
    require(bool(structure.materialize_structure()), "P04_STRUCTURE_REFIT_FAILED")
    return {
        "passage": passage.get_actor_label(),
        "structure": structure.get_actor_label(),
        "fixture_body_count": int(structure.get_editor_property("fixture_body_count")),
    }


def _save_narrow():
    census = _dirty_census()
    require(not (set(census["content"]) - {SHOW_PATH})
            and not (set(census["maps"]) - {EXPECTED_WORLD}),
            "OUT_OF_SCOPE_DIRTY_BEFORE_SAVE|census=" + _canonical(census))
    require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False),
            "SHOW_SAVE_FAILED")
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(),
            "LEVEL_SAVE_FAILED")
    require(_dirty_census() == {"content": [], "maps": []},
            "DIRTY_AFTER_SAVE|census=" + _canonical(_dirty_census()))


def _queue_master_test(world, marker, run):
    require(_dirty_census() == {"content": [], "maps": []}, "DIRTY_BEFORE_TEST")
    unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + MASTER_TEST)
    unreal.log("%s_SAVED_MASTER_QUEUED|run=%s|test=%s|alone=true" % (marker, run, MASTER_TEST))


def _target_current(show, target):
    index = _show_index_by_guid(show, target["cue_guid"])
    cue = list(show.get_editor_property("cues"))[index]
    require(index == target["show_index"],
            "TARGET_INDEX_DRIFT|guid=%s|was=%d|now=%d" %
            (target["cue_guid"], target["show_index"], index))
    require(str(cue.get_editor_property("label")) == target["cue_label"],
            "TARGET_LABEL_DRIFT|guid=" + target["cue_guid"])
    return index, cue, _pair_attachments(cue)


def _outside_hash(all_rows, target_guids):
    return _state_hash({guid: rows for guid, rows in all_rows.items()
                        if guid not in set(target_guids)})


def _runtime_plan(show, config):
    plain = _plain_cues(show)
    plan = build_plain_plan(config, plain)
    _apply_live_top_aims(show, plan)
    for target in plan["targets"]:
        cue = list(show.get_editor_property("cues"))[target["show_index"]]
        target["before_rows"] = _attachment_rows(_pair_attachments(cue))
        target["before_hash"] = _rows_hash(target["before_rows"])
        target["expected_new_labels"] = [row["label"] for row in target["fixtures"]]
    return plan


def _mutate_apply(show, plan, materials):
    cues = list(show.get_editor_property("cues"))
    target_guids = set(plan["target_cue_guids"])
    scratch_candidates = []
    for index, cue in enumerate(cues):
        guid = _guid_text(cue.get_editor_property("cue_guid"))
        label = str(cue.get_editor_property("label"))
        if guid not in target_guids and P04_LABEL.match(label):
            scratch_candidates.append((index, cue))
    require(scratch_candidates, "P04_SCRATCH_CUE_MISSING")
    scratch_index, scratch_cue = scratch_candidates[-1]
    scratch_original = _pair_attachments(scratch_cue)
    scratch_before = _attachment_rows(scratch_original)
    scratch_light_count = sum(_is_light(item) for item in scratch_original)
    needed = max(target["existing_lights"] + target["fixture_count"]
                 for target in plan["targets"])
    padding = max(0, needed - scratch_light_count)
    preexisting_guids = {_guid_text(item.get_editor_property("attachment_guid"))
                         for cue in cues for item in _pair_attachments(cue)}

    original_targets = {
        target["show_index"]: _pair_attachments(cues[target["show_index"]])
        for target in plan["targets"]
    }
    original_enabled = {
        _guid_text(attachment.get_editor_property("attachment_guid")):
            bool(attachment.get_editor_property("enabled"))
        for attachments in original_targets.values() for attachment in attachments
        if _is_light(attachment)
    }
    try:
        _set_pair_attachments(show, scratch_index,
                              scratch_original + [_make_blank_light() for _ in range(padding)])
        fresh_cues = list(show.get_editor_property("cues"))
        changed = show.replicate_light_attachments(
            fresh_cues[scratch_index].get_editor_property("cue_guid"),
            [fresh_cues[target["show_index"]].get_editor_property("cue_guid")
             for target in plan["targets"]])
        require(int(changed) == 6, "REPLICATION_TARGET_COUNT|count=%s" % changed)
        _set_pair_attachments(show, scratch_index, scratch_original)

        _require_attachment_rows_equal(
            _attachment_rows(_pair_attachments(
                list(show.get_editor_property("cues"))[scratch_index])),
            scratch_before, "SCRATCH_NOT_RESTORED_EXACTLY")

        added_guids = set()
        for target in plan["targets"]:
            index, unused_cue, replicated = _target_current(show, target)
            del unused_cue
            vessels = [item for item in replicated if _is_light(item)]
            start = target["existing_lights"]
            stop = start + target["fixture_count"]
            require(len(vessels) >= stop,
                    "MINTED_SLOT_COUNT|cue=%s|need=%d|actual=%d" %
                    (target["cue_label"], stop, len(vessels)))
            new_vessels = vessels[start:stop]
            original = original_targets[index]
            modified_original = []
            for attachment in original:
                if _is_light(attachment):
                    attachment.set_editor_property("enabled", False)
                modified_original.append(attachment)
            authored = []
            for vessel, fixture in zip(new_vessels, target["fixtures"]):
                minted = _guid_text(vessel.get_editor_property("attachment_guid"))
                require(minted not in preexisting_guids and minted not in added_guids,
                        "MINTED_GUID_NOT_FRESH|guid=" + minted)
                template = _make_light(fixture, materials)
                authored.append(_overwrite_vessel(vessel, template))
                added_guids.add(minted)
            _set_pair_attachments(show, index, modified_original + authored)
            target["added"] = [
                {"guid": _guid_text(item.get_editor_property("attachment_guid")),
                 "label": str(item.get_editor_property("label"))}
                for item in authored
            ]
            target["after_rows"] = _attachment_rows(modified_original + authored)
            target["after_hash"] = _rows_hash(target["after_rows"])
            require([row["label"] for row in target["added"]] == target["expected_new_labels"],
                    "NEW_LABEL_ORDER_WRONG|cue=" + target["cue_label"])

        require(len(added_guids) == plan["fixture_count"],
                "ADDED_GUID_COUNT|expected=%d|actual=%d" %
                (plan["fixture_count"], len(added_guids)))
    except Exception:
        _set_pair_attachments(show, scratch_index, scratch_original)
        for target_index, attachments in original_targets.items():
            for attachment in attachments:
                if _is_light(attachment):
                    attachment.set_editor_property(
                        "enabled",
                        original_enabled[_guid_text(
                            attachment.get_editor_property("attachment_guid"))],
                    )
            _set_pair_attachments(show, target_index, attachments)
        _require_attachment_rows_equal(
            _attachment_rows(_pair_attachments(
                list(show.get_editor_property("cues"))[scratch_index])),
            scratch_before, "APPLY_ROLLBACK_SCRATCH_FAILED")
        for target in plan["targets"]:
            restored = _attachment_rows(_pair_attachments(
                list(show.get_editor_property("cues"))[target["show_index"]]))
            _require_attachment_rows_equal(
                restored, target["before_rows"],
                "APPLY_ROLLBACK_TARGET_FAILED|cue=" + target["cue_label"])
        raise


def _verify_applied(show, plan, outside_before):
    all_rows = _all_pair_rows(show)
    require(_outside_hash(all_rows, plan["target_cue_guids"]) == outside_before,
            "OUTSIDE_TARGET_SCOPE_CHANGED")
    for target in plan["targets"]:
        unused_index, unused_cue, attachments = _target_current(show, target)
        del unused_index, unused_cue
        rows = _attachment_rows(attachments)
        _require_attachment_rows_equal(
            rows, target["after_rows"],
            "APPLY_READBACK_MISMATCH|cue=" + target["cue_label"])
        original_count = len(target["before_rows"])
        original = attachments[:original_count]
        require(all(not bool(item.get_editor_property("enabled"))
                    for item in original if _is_light(item)),
                "EXISTING_LIGHT_STILL_ENABLED|cue=" + target["cue_label"])
    current_plan = build_plain_plan_for_applied(show, plan)
    require(current_plan["shadow_after"] == plan["shadow"]["p04_after"],
            "SHADOW_READBACK_MISMATCH|expected=%d|actual=%d" %
            (plan["shadow"]["p04_after"], current_plan["shadow_after"]))
    return current_plan


def build_plain_plan_for_applied(show, plan):
    plain = _plain_cues(show)
    shadow_after = sum(_plain_casts(att) for cue in plain if _plain_p04(cue)
                       for att in cue["attachments"])
    labels = [att["label"] for cue in plain for att in cue["attachments"]
              if att["label"].startswith("P04 LOOK ")]
    return {"shadow_after": shadow_after, "prototype_labels": sorted(labels)}


def _mutate_revert(show, record):
    target_guids = record["plan"]["target_cue_guids"]
    outside_before = _outside_hash(_all_pair_rows(show), target_guids)
    current_by_index = {}
    current_enabled = {}
    try:
        for target in record["plan"]["targets"]:
            index, unused_cue, attachments = _target_current(show, target)
            del unused_cue
            current_by_index[index] = attachments
            for attachment in attachments:
                if _is_light(attachment):
                    current_enabled[_guid_text(
                        attachment.get_editor_property("attachment_guid"))] = bool(
                            attachment.get_editor_property("enabled"))
            current_rows = _attachment_rows(attachments)
            _require_attachment_rows_equal(
                current_rows, target["after_rows"],
                "REVERT_CURRENT_STATE_DRIFT|cue=" + target["cue_label"])
            added_guids = {row["guid"] for row in target["added"]}
            restored = []
            before_enabled = {row["guid"]: row["enabled"] for row in target["before_rows"]}
            removed = 0
            for attachment in attachments:
                guid = _guid_text(attachment.get_editor_property("attachment_guid"))
                if guid in added_guids:
                    removed += 1
                    continue
                require(guid in before_enabled,
                        "REVERT_UNKNOWN_ATTACHMENT|cue=%s|guid=%s" % (target["cue_label"], guid))
                if _is_light(attachment):
                    attachment.set_editor_property("enabled", bool(before_enabled[guid]))
                restored.append(attachment)
            require(removed == len(added_guids),
                    "REVERT_REMOVE_COUNT|cue=%s|expected=%d|actual=%d" %
                    (target["cue_label"], len(added_guids), removed))
            _set_pair_attachments(show, index, restored)
            _require_attachment_rows_equal(
                _attachment_rows(restored), target["before_rows"],
                "REVERT_NOT_EXACT|cue=" + target["cue_label"])
        require(_outside_hash(_all_pair_rows(show), target_guids) == outside_before,
                "REVERT_OUTSIDE_TARGET_SCOPE_CHANGED")
        return outside_before
    except Exception:
        for index, attachments in current_by_index.items():
            for attachment in attachments:
                if _is_light(attachment):
                    attachment.set_editor_property(
                        "enabled",
                        current_enabled[_guid_text(
                            attachment.get_editor_property("attachment_guid"))],
                    )
            _set_pair_attachments(show, index, attachments)
        raise


def _run(mode):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"ok": False, "mode": mode, "run": run, "config": CONFIG_PATH}
    try:
        config = load_config()
        report["config_sha256"] = _sha256_file(CONFIG_PATH)
        world = _require_context()
        materials = _materials(config)
        show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")

        if mode == "DRY":
            require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS")
            plan = _runtime_plan(show, config)
            report.update({
                "ok": True,
                "plan": plan,
                "fixture_count": plan["fixture_count"],
                "existing_lights_disabled": plan["existing_lights_disabled"],
                "shadow": plan["shadow"],
                "mutated": False,
                "census": _dirty_census(),
                "materials": sorted(materials),
            })
            _write_json(REPORT_PATH, report)
            unreal.log("LIGHTING_LOOKS_DRY_OK|run=%s|fixtures=%d|disabled=%d|p04_shadow=%d->%d|mutated=0" %
                       (run, plan["fixture_count"], plan["existing_lights_disabled"],
                        plan["shadow"]["p04_before"], plan["shadow"]["p04_after"]))
            return report

        if mode == "APPLY":
            require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS")
            plan = _runtime_plan(show, config)
            all_before = _all_pair_rows(show)
            outside_before = _outside_hash(all_before, plan["target_cue_guids"])
            backup = _backup("PreLightingLooksP04-", run)
            record = {
                "schema_version": 1,
                "status": "prepared",
                "run": run,
                "config_sha256": report["config_sha256"],
                "backup": backup,
                "outside_before_hash": outside_before,
                "plan": plan,
            }
            _write_json(RECORD_PATH, record, exclusive=True)
            try:
                _mutate_apply(show, plan, materials)
            except Exception:
                record["status"] = "failed_rolled_back_in_memory"
                failed_record = RECORD_PATH + ".failed-" + run
                _write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, failed_record)
                raise
            record["status"] = "mutated_verified"
            record["plan"] = plan
            _write_json(RECORD_PATH, record)
            verified = _verify_applied(show, plan, outside_before)
            materialized = _materialize_p04(show)
            _save_narrow()
            readback_show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
            verified = _verify_applied(readback_show, plan, outside_before)
            record["status"] = "saved_readback_verified"
            record["saved_census"] = _dirty_census()
            record["materialized"] = materialized
            _write_json(RECORD_PATH, record)
            _queue_master_test(world, "LIGHTING_LOOKS", run)
            report.update({
                "ok": True,
                "fixture_count": plan["fixture_count"],
                "existing_lights_disabled": plan["existing_lights_disabled"],
                "shadow": plan["shadow"],
                "prototype_labels": verified["prototype_labels"],
                "backup": backup,
                "record": RECORD_PATH,
                "materialized": materialized,
                "saved_master_test": "queued",
                "census": _dirty_census(),
            })
            _write_json(REPORT_PATH, report)
            unreal.log("LIGHTING_LOOKS_APPLY_OK|run=%s|fixtures=%d|disabled=%d|p04_shadow=%d->%d|show_saved=1|level_saved=1|readback=1|saved_master=queued" %
                       (run, plan["fixture_count"], plan["existing_lights_disabled"],
                        plan["shadow"]["p04_before"], plan["shadow"]["p04_after"]))
            return report

        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT")
        record = _read_json(RECORD_PATH)
        require(record.get("status") == "saved_readback_verified",
                "REVERT_RECORD_STATUS|status=" + str(record.get("status")))
        plan = record["plan"]
        current = build_plain_plan_for_applied(show, plan)
        before_revert_shadow = current["shadow_after"]
        backup = _backup("PreLightingLooksP04Revert-", run)
        _mutate_revert(show, record)
        expected_after = (before_revert_shadow - plan["shadow"]["target_after"]
                          + plan["shadow"]["target_before"])
        after_mutation = sum(_plain_casts(att) for cue in _plain_cues(show) if _plain_p04(cue)
                             for att in cue["attachments"])
        require(after_mutation == expected_after,
                "REVERT_SHADOW_MISMATCH|expected=%d|actual=%d" %
                (expected_after, after_mutation))
        materialized = _materialize_p04(show)
        _save_narrow()
        readback_show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
        for target in plan["targets"]:
            unused_index, unused_cue, attachments = _target_current(readback_show, target)
            del unused_index, unused_cue
            _require_attachment_rows_equal(
                _attachment_rows(attachments), target["before_rows"],
                "REVERT_READBACK_NOT_EXACT|cue=" + target["cue_label"])
        archived = RECORD_PATH + ".reverted-" + run
        os.rename(RECORD_PATH, archived)
        _queue_master_test(world, "LIGHTING_LOOKS_REVERT", run)
        report.update({
            "ok": True,
            "fixture_count_removed": plan["fixture_count"],
            "existing_lights_restored": plan["existing_lights_disabled"],
            "shadow": {"before_revert": before_revert_shadow,
                       "after_revert": after_mutation},
            "backup": backup,
            "record_archived": archived,
            "materialized": materialized,
            "saved_master_test": "queued",
            "census": _dirty_census(),
        })
        _write_json(REPORT_PATH, report)
        unreal.log("LIGHTING_LOOKS_REVERT_OK|run=%s|removed=%d|restored=%d|p04_shadow=%d->%d|show_saved=1|level_saved=1|readback=1|saved_master=queued" %
                   (run, plan["fixture_count"], plan["existing_lights_disabled"],
                    before_revert_shadow, after_mutation))
        return report
    except Exception as error:  # noqa: BLE001 - preserve a report for every stop.
        report["error"] = "%s: %s" % (type(error).__name__, error)
        report["census"] = _dirty_census() if unreal is not None else None
        _write_json(REPORT_PATH, report)
        if unreal is not None:
            unreal.log_error("LIGHTING_LOOKS_STOPPED|run=%s|mode=%s|%s" %
                             (run, mode, report["error"]))
        raise


def main(mode=None):
    selected = str(mode or globals().get("LIGHTING_LOOKS_MODE", "DRY")).upper()
    require(selected in VALID_MODES, "MODE_INVALID|mode=" + selected)
    require(unreal is not None, "UNREAL_REQUIRED_FOR_MODE|mode=" + selected)
    return _run(selected)


if unreal is not None:
    main()
