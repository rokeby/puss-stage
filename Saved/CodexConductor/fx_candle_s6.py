"""Author the first S6 candle as Show-owned Fire + linked Point Light.

Modes: DRY (default), APPLY, REVERT.  The Fire/Light pair is anchored to the
last P06 WingPair preceding the Scene 6 cue because the current Effect API only
accepts WingPair cues.  This is deliberately a test placement; Gary can move the
materialized actors in PIE/editor and let normal attachment write-back update the
Show.

The tool fails closed unless a purpose-built BP_Effect_Candle exists.  The
native Fire fallback is a 60 x 60 x 80 cm greybox and does not satisfy the
2 cm x 10 cm candle / realistic flame brief.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness import.
    unreal = None


def _load_common():
    try:
        import _fx_authoring_common as module
        return module
    except ModuleNotFoundError:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_fx_authoring_common.py")
        spec = importlib.util.spec_from_file_location("_fx_authoring_common", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


C = _load_common()

SCENE6_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_06"
CANDLE_BP = "/Game/Scenes/Effects/BP_Effect_Candle"
CANDLE_CLASS = CANDLE_BP + ".BP_Effect_Candle_C"
CANDLE_LABEL = "FX TEST - S6 Candle"
LIGHT_LABEL = "FX TEST - S6 Candle Light"
PASSAGE_NUMBER = 6

# S6 is a 60 m-deep hangar.  The P06 tail to the stop is measured as 390 cm;
# 390 + 3000 places the test at the hangar's depth centre.  Gary adjusts it.
P06_TAIL_TO_STOP_CM = 390.0
S6_DEPTH_CM = 6000.0
TABLE_HEIGHT_CM = 110.0
CANDLE_HEIGHT_CM = 10.0
BASE_RELATIVE_LOCATION = (
    P06_TAIL_TO_STOP_CM + S6_DEPTH_CM * 0.5,
    0.0,
    TABLE_HEIGHT_CM,
)
LIGHT_RELATIVE_LOCATION = (
    BASE_RELATIVE_LOCATION[0],
    BASE_RELATIVE_LOCATION[1],
    BASE_RELATIVE_LOCATION[2] + CANDLE_HEIGHT_CM,
)

LIGHT_INTENSITY_LUMENS = 120.0
LIGHT_TEMPERATURE_K = 1900.0
LIGHT_ATTENUATION_CM = 700.0
LIGHT_VOLUMETRIC_SCATTERING = 1.0
FLICKER_AMOUNT = 0.12


def cue_kind_token(value):
    text = str(value).upper()
    if "WING_PAIR" in text or "WINGPAIR" in text:
        return "WingPair"
    if "SCENE" in text:
        return "Scene"
    if "SEQUENCE" in text:
        return "Sequence"
    return text


def choose_scene_anchor(cues):
    """Pure plan: return the Scene 6 index and preceding WingPair index."""
    scene_indices = [index for index, cue in enumerate(cues)
                     if cue.get("kind") == "Scene"
                     and cue.get("sequence") == SCENE6_SEQUENCE]
    C.require(len(scene_indices) == 1,
              "SCENE6_CUE_COUNT|count=%d" % len(scene_indices))
    scene_index = scene_indices[0]
    anchors = [index for index in range(scene_index - 1, -1, -1)
               if cues[index].get("kind") == "WingPair"
               and cues[index].get("enabled", True)]
    C.require(bool(anchors), "SCENE6_PRECEDING_WINGPAIR_MISSING")
    return {"scene_index": scene_index, "anchor_index": anchors[0]}


def candle_plan(cues, candle_class_exists, duplicate_labels=()):
    anchor = choose_scene_anchor(cues)
    C.require(candle_class_exists, "CANDLE_BLUEPRINT_MISSING|asset=" + CANDLE_BP)
    duplicates = sorted(set(duplicate_labels) & {CANDLE_LABEL, LIGHT_LABEL})
    C.require(not duplicates, "CANDLE_ALREADY_AUTHORED|labels=" + ",".join(duplicates))
    return {
        **anchor,
        "candle_location_cm": list(BASE_RELATIVE_LOCATION),
        "light_location_cm": list(LIGHT_RELATIVE_LOCATION),
        "light": {
            "type": "Point",
            "intensity_lumens": LIGHT_INTENSITY_LUMENS,
            "temperature_kelvin": LIGHT_TEMPERATURE_K,
            "attenuation_cm": LIGHT_ATTENUATION_CM,
            "cast_shadows": True,
            "cast_volumetric_shadow": True,
            "volumetric_scattering_intensity": LIGHT_VOLUMETRIC_SCATTERING,
        },
        "effect": {"type": "Fire", "flicker_amount": FLICKER_AMOUNT},
        "visual_contract": {
            "wax_cylinder_diameter_cm": 2.0,
            "wax_cylinder_height_cm": CANDLE_HEIGHT_CM,
            "flame_width_cm": [2.0, 3.0],
            "flame_height_cm": 4.0,
            "niagara_required": True,
        },
    }


def _scene_path(cue):
    scene = cue.get_editor_property("scene")
    return C.asset_id(scene.get_editor_property("sequence"))


def _cue_rows(show):
    rows = []
    for cue in show.get_editor_property("cues"):
        kind = cue_kind_token(cue.get_editor_property("type"))
        rows.append({
            "kind": kind,
            "sequence": _scene_path(cue) if kind != "WingPair" else None,
            "enabled": bool(cue.get_editor_property("enabled")),
            "label": str(cue.get_editor_property("label")),
        })
    return rows


def _attachments(cue):
    pair = cue.get_editor_property("wing_pair")
    return pair, list(pair.get_editor_property("attachments"))


def _find_by_label(attachments, label):
    return [item for item in attachments
            if str(item.get_editor_property("label")) == label]


def _find_by_guid(attachments, guid_text):
    return [item for item in attachments
            if C.guid_text(item.get_editor_property("attachment_guid")) == guid_text]


def _make_transform(location):
    return unreal.Transform(
        location=unreal.Vector(*location),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
        scale=unreal.Vector(1.0, 1.0, 1.0),
    )


def _enum(enum_type, *names):
    return C.enum_member(enum_type, *names)


def _set_cue(show, index, cue):
    cues = list(show.get_editor_property("cues"))
    cues[index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _append_light(show, cue_index, relative_transform):
    cues = list(show.get_editor_property("cues"))
    cue = cues[cue_index]
    pair, attachments = _attachments(cue)
    attachment = unreal.InfinityCueAttachment()
    guid = C.new_guid(unreal)
    attachment.set_editor_property("attachment_guid", guid)
    attachment.set_editor_property("label", LIGHT_LABEL)
    attachment.set_editor_property("kind", _enum(unreal.InfinityAttachmentKind, "LIGHT"))
    attachment.set_editor_property("enabled", True)
    attachment.set_editor_property("anchor", _enum(
        unreal.InfinityAttachmentAnchor, "PAIR_CENTRE", "PAIR_CENTER"))
    attachment.set_editor_property("relative_transform", relative_transform)

    settings = attachment.get_editor_property("lighting")
    settings.set_editor_property("type", _enum(unreal.InfinityStageLightType, "POINT"))
    settings.set_editor_property("intensity_units", _enum(
        unreal.InfinityStageLightIntensityUnits, "LUMENS"))
    settings.set_editor_property("intensity", LIGHT_INTENSITY_LUMENS)
    settings.set_editor_property("use_temperature", True)
    settings.set_editor_property("temperature_kelvin", LIGHT_TEMPERATURE_K)
    settings.set_editor_property("attenuation_radius_cm", LIGHT_ATTENUATION_CM)
    settings.set_editor_property("source_radius_cm", 1.0)
    settings.set_editor_property("soft_source_radius_cm", 3.0)
    settings.set_editor_property("cast_shadows", True)
    settings.set_editor_property("cast_volumetric_shadow", True)
    settings.set_editor_property("volumetric_scattering_intensity",
                                 LIGHT_VOLUMETRIC_SCATTERING)
    attachment.set_editor_property("lighting", settings)
    attachments.append(attachment)
    pair.set_editor_property("attachments", attachments)
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue
    show.modify()
    show.set_editor_property("cues", cues)
    return guid


def _append_fire(show, cue_index, cue_guid, light_guid, candle_class):
    fire_type = _enum(unreal.InfinityStageEffectType, "FIRE")
    anchor = _enum(unreal.InfinityAttachmentAnchor, "PAIR_CENTRE", "PAIR_CENTER")
    effect_guid = unreal.InfinityStageEffectLibrary.add_effect_attachment(
        show, cue_guid, fire_type, anchor, _make_transform(BASE_RELATIVE_LOCATION),
        CANDLE_LABEL)
    effect_guid_text = C.guid_text(effect_guid)
    C.require(effect_guid_text.strip("0()=AGUID"), "ADD_FIRE_RETURNED_INVALID_GUID")

    cues = list(show.get_editor_property("cues"))
    cue = cues[cue_index]
    pair, attachments = _attachments(cue)
    matches = _find_by_guid(attachments, effect_guid_text)
    C.require(len(matches) == 1, "ADDED_FIRE_READBACK_COUNT|count=%d" % len(matches))
    attachment = matches[0]
    attachment.set_editor_property("actor_class", candle_class)
    settings = attachment.get_editor_property("effect")
    settings.set_editor_property("flicker_amount", FLICKER_AMOUNT)
    settings.set_editor_property("output", 0.25)
    settings.set_editor_property("active_radius_cm", 3500.0)
    settings.set_editor_property("feeds_local_medium", False)
    settings.set_editor_property("linked_light_attachment_guid", light_guid)
    attachment.set_editor_property("effect", settings)
    for index, candidate in enumerate(attachments):
        if C.guid_text(candidate.get_editor_property("attachment_guid")) == effect_guid_text:
            attachments[index] = attachment
            break
    pair.set_editor_property("attachments", attachments)
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue
    show.modify()
    show.set_editor_property("cues", cues)
    return effect_guid


def _remove_guids(show, cue_index, guid_texts):
    cues = list(show.get_editor_property("cues"))
    cue = cues[cue_index]
    pair, attachments = _attachments(cue)
    before = len(attachments)
    wanted = set(guid_texts)
    attachments = [item for item in attachments
                   if C.guid_text(item.get_editor_property("attachment_guid")) not in wanted]
    C.require(before - len(attachments) == len(wanted),
              "REVERT_ATTACHMENT_COUNT|expected=%d|removed=%d" %
              (len(wanted), before - len(attachments)))
    pair.set_editor_property("attachments", attachments)
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _materialize(unreal, show):
    actor = C.find_passage_actor(unreal, show, PASSAGE_NUMBER)
    C.require(actor.materialize_passage(), "P06_MATERIALIZE_FAILED")
    return actor


def _snapshot(show, cue_index, guid_texts):
    cue = list(show.get_editor_property("cues"))[cue_index]
    pair, attachments = _attachments(cue)
    del pair
    rows = []
    wanted = set(guid_texts)
    for item in attachments:
        guid = C.guid_text(item.get_editor_property("attachment_guid"))
        if guid not in wanted:
            continue
        kind = str(item.get_editor_property("kind"))
        row = {
            "guid": guid,
            "label": str(item.get_editor_property("label")),
            "kind": kind,
            "anchor": str(item.get_editor_property("anchor")),
            "relative_transform": C.transform_plain(item.get_editor_property("relative_transform")),
        }
        if "LIGHT" in kind.upper():
            light = item.get_editor_property("lighting")
            row["light"] = {
                "intensity": float(light.get_editor_property("intensity")),
                "temperature_kelvin": float(light.get_editor_property("temperature_kelvin")),
                "attenuation_radius_cm": float(light.get_editor_property("attenuation_radius_cm")),
                "cast_shadows": bool(light.get_editor_property("cast_shadows")),
                "cast_volumetric_shadow": bool(light.get_editor_property("cast_volumetric_shadow")),
                "volumetric_scattering_intensity": float(
                    light.get_editor_property("volumetric_scattering_intensity")),
            }
        else:
            effect = item.get_editor_property("effect")
            row["effect"] = {
                "type": str(effect.get_editor_property("type")),
                "flicker_amount": float(effect.get_editor_property("flicker_amount")),
                "linked_light_guid": C.guid_text(
                    effect.get_editor_property("linked_light_attachment_guid")),
            }
            row["actor_class"] = C.asset_id(item.get_editor_property("actor_class"))
        rows.append(row)
    return sorted(rows, key=lambda row: row["label"])


def _candle_class_preflight():
    C.require(unreal.EditorAssetLibrary.does_asset_exist(CANDLE_BP),
              "CANDLE_BLUEPRINT_MISSING|asset=" + CANDLE_BP)
    candle_class = unreal.EditorAssetLibrary.load_blueprint_class(CANDLE_BP)
    C.require(candle_class is not None, "CANDLE_CLASS_LOAD_FAILED|asset=" + CANDLE_BP)
    effect_base = getattr(unreal, "InfinityStageEffectSource", None)
    if effect_base is not None:
        base_class = effect_base.static_class()
        cursor = candle_class
        is_child = False
        while cursor is not None:
            if cursor == base_class:
                is_child = True
                break
            get_super = getattr(cursor, "get_super_class", None)
            cursor = get_super() if callable(get_super) else None
        C.require(is_child, "CANDLE_CLASS_NOT_EFFECT_SOURCE|class=" + str(candle_class))
    default = unreal.get_default_object(candle_class)
    niagara_type = getattr(unreal, "NiagaraComponent", None)
    systems = default.get_components_by_class(niagara_type) if niagara_type else []
    C.require(len(systems) >= 1, "CANDLE_BLUEPRINT_HAS_NO_NIAGARA_COMPONENT")
    return candle_class, len(systems)


def main(mode=None):
    C.require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    selected = str(mode or globals().get("FX_CANDLE_S6_MODE", "DRY")).upper()
    C.require(selected in ("DRY", "APPLY", "REVERT"), "MODE_INVALID|" + selected)
    run = C.stamp_now()
    base = C.saved_dir(unreal)
    report_path = os.path.join(base, "fx_candle_s6_report.json")
    record_path = os.path.join(base, "fx_candle_s6_record.json")
    report = {"ok": False, "mode": selected, "run": run}

    def fail(error):
        report["error"] = str(error)
        report["census_at_stop"] = C.dirty_census(unreal)
        C.write_json(report_path, report)
        unreal.log_error("FX_CANDLE_S6_STOPPED|run=%s|mode=%s|%s" %
                         (run, selected, str(error)))
        if isinstance(error, C.FxToolError):
            raise error
        raise C.FxToolError(str(error))

    try:
        editor, world = C.editor_context(unreal)
        del editor
        report["dirty_before"] = C.require_clean(unreal, "PRE")
        show = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        C.require(show is not None, "SHOW_LOAD_FAILED")
        rows = _cue_rows(show)
        anchor = choose_scene_anchor(rows)
        cue_index = anchor["anchor_index"]
        cue = list(show.get_editor_property("cues"))[cue_index]
        pair, attachments = _attachments(cue)
        del pair
        duplicate_labels = [str(item.get_editor_property("label")) for item in attachments]

        # Revert must remain available if the visual Blueprint is later moved or
        # deleted, and the authored labels are expected to exist in this mode.
        if selected == "REVERT":
            C.require(os.path.isfile(record_path), "REVERT_RECORD_MISSING")
            record = C.load_json(record_path)
            C.require(record.get("status") == "applied", "REVERT_RECORD_NOT_APPLIED")
            cue_index = int(record["cue_index"])
            guid_texts = [record["light_guid"], record["effect_guid"]]
            current = _snapshot(show, cue_index, guid_texts)
            C.require(current == record["expected"], "REVERT_LIVE_STATE_MISMATCH")
            backup = C.backup_packages(
                unreal, "PreFxCandleS6Revert-", run, [C.SHOW_PATH, C.EXPECTED_WORLD])
            _remove_guids(show, cue_index, guid_texts)
            _materialize(unreal, show)
            expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
            C.require(C.dirty_census(unreal) == expected_dirty,
                      "REVERT_DIRTY_SCOPE|actual=" +
                      json.dumps(C.dirty_census(unreal), sort_keys=True))
            C.save_show_and_level(unreal)
            C.require(_snapshot(show, cue_index, guid_texts) == [],
                      "REVERT_READBACK_PRESENT")
            command = C.queue_saved_master_test(
                unreal, world, "FX_CANDLE_S6_REVERT", run)
            archived = C.archive_record(record_path, run)
            report.update({"ok": True, "backup": backup, "archived_record": archived,
                           "dirty_after": C.dirty_census(unreal),
                           "saved_master_command": command})
            C.write_json(report_path, report)
            unreal.log("FX_CANDLE_S6_REVERTED|run=%s|cue='%s'|backup=%s|record=%s|census=%s" %
                       (run, record["cue_label"], backup["root"], archived,
                        json.dumps(report["dirty_after"], separators=(",", ":"))))
            return

        candle_class, niagara_count = _candle_class_preflight()
        plan = candle_plan(rows, True, duplicate_labels)
        report.update({
            "plan": plan,
            "anchor_cue_label": rows[cue_index]["label"],
            "scene_cue_label": rows[anchor["scene_index"]]["label"],
            "candle_blueprint": CANDLE_BP,
            "niagara_component_count": niagara_count,
        })

        if selected == "DRY":
            C.require(C.dirty_census(unreal) == report["dirty_before"],
                      "DRY_CHANGED_CENSUS")
            report.update({"ok": True, "dirty_after": C.dirty_census(unreal)})
            C.write_json(report_path, report)
            unreal.log("FX_CANDLE_S6_DRY_OK|run=%s|anchor='%s'|scene='%s'|census=%s" %
                       (run, report["anchor_cue_label"], report["scene_cue_label"],
                        json.dumps(report["dirty_after"], separators=(",", ":"))))
            return

        if selected == "APPLY":
            C.require(not os.path.exists(record_path), "APPLY_RECORD_ALREADY_EXISTS")
            backup = C.backup_packages(
                unreal, "PreFxCandleS6-", run, [C.SHOW_PATH, C.EXPECTED_WORLD])
            record = {
                "status": "prepared",
                "run": run,
                "backup": backup,
                "cue_index": cue_index,
                "cue_guid": C.guid_text(cue.get_editor_property("cue_guid")),
                "cue_label": rows[cue_index]["label"],
                "scene_index": anchor["scene_index"],
                "scene_label": rows[anchor["scene_index"]]["label"],
            }
            C.write_json(record_path, record, exclusive=True)
            light_guid = _append_light(show, cue_index, _make_transform(LIGHT_RELATIVE_LOCATION))
            # Re-read cue guid after the Light struct write.
            cue = list(show.get_editor_property("cues"))[cue_index]
            effect_guid = _append_fire(
                show, cue_index, cue.get_editor_property("cue_guid"), light_guid, candle_class)
            guid_texts = [C.guid_text(light_guid), C.guid_text(effect_guid)]
            expected = _snapshot(show, cue_index, guid_texts)
            C.require(len(expected) == 2, "IN_MEMORY_READBACK_COUNT|count=%d" % len(expected))
            actor = _materialize(unreal, show)
            del actor
            expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
            C.require(C.dirty_census(unreal) == expected_dirty,
                      "APPLY_DIRTY_SCOPE|expected=%s|actual=%s" %
                      (json.dumps(expected_dirty, sort_keys=True),
                       json.dumps(C.dirty_census(unreal), sort_keys=True)))
            C.save_show_and_level(unreal)
            show_readback = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
            actual = _snapshot(show_readback, cue_index, guid_texts)
            C.require(actual == expected, "SAVED_READBACK_MISMATCH")
            command = C.queue_saved_master_test(unreal, world, "FX_CANDLE_S6", run)
            record.update({
                "status": "applied",
                "light_guid": guid_texts[0],
                "effect_guid": guid_texts[1],
                "expected": expected,
                "saved_master_command": command,
            })
            C.write_json(record_path, record)
            report.update({"ok": True, "backup": backup, "readback": actual,
                           "dirty_after": C.dirty_census(unreal),
                           "saved_master_command": command})
            C.write_json(report_path, report)
            unreal.log("FX_CANDLE_S6_APPLIED|run=%s|cue='%s'|effect=%s|light=%s|volumetric=%.3f|shadows=true|backup=%s|census=%s" %
                       (run, rows[cue_index]["label"], guid_texts[1], guid_texts[0],
                        LIGHT_VOLUMETRIC_SCATTERING, backup["root"],
                        json.dumps(report["dirty_after"], separators=(",", ":"))))
            return

    except Exception as error:  # noqa: BLE001 - report every fail-closed stop.
        fail(error)


if __name__ == "__main__":
    main()
