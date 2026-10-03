"""Author one reversible WingBurn on the RIGHT panel of P06 position 32.

Modes: DRY (default), APPLY, REVERT.  DRY proves the exact cue/mesh/material
chain, requires Front and Flap to inherit the Billboard burn master with
UseBurn enabled, and freshly measures the mesh's planar UV mapping.  APPLY is
impossible until that gate is green; it never edits materials itself.
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

TARGET_CUE_LABEL = "P06 Wing 032"
TARGET_SIDE = "right"
TARGET_ANCHOR = "RIGHT_PANEL"
TARGET_EFFECT_LABEL = "FX TEST - P06 Wing 032 Right WingBurn"
EXPECTED_MASTER = "/Game/Scenes/Wings/PaintedSurface/Billboard/M_Wing_Billboard_Master"
REQUIRED_SLOTS = ("Front", "Flap")
PASSAGE_NUMBER = 6
FIT_TOLERANCE = 1.0e-5


def linear_fit(xs, ys):
    C.require(len(xs) == len(ys) and len(xs) >= 3, "FIT_SAMPLE_COUNT")
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    variance = sum((value - mean_x) ** 2 for value in xs)
    C.require(variance > 1.0e-12, "FIT_DEGENERATE_AXIS")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance
    intercept = mean_y - slope * mean_x
    residual = max(abs(y - (slope * x + intercept)) for x, y in zip(xs, ys))
    return slope, intercept, residual


def material_gate(slot_rows, required_slots=REQUIRED_SLOTS):
    by_slot = {row["slot"]: row for row in slot_rows}
    missing = [slot for slot in required_slots if slot not in by_slot]
    C.require(not missing, "BURN_SLOT_MISSING|slots=" + ",".join(missing))
    checked = []
    for slot in required_slots:
        row = by_slot[slot]
        C.require(row.get("parent") == EXPECTED_MASTER,
                  "BURN_PARENT_MISMATCH|slot=%s|parent=%s" %
                  (slot, row.get("parent")))
        C.require(bool(row.get("has_use_burn_parameter")),
                  "BURN_SWITCH_MISSING|slot=" + slot)
        C.require(bool(row.get("use_burn")),
                  "BURN_SWITCH_OFF|slot=%s|material=%s" %
                  (slot, row.get("material")))
        checked.append(dict(row))
    return checked


def wingburn_plan(cues, slot_rows, duplicate=False):
    matches = [index for index, cue in enumerate(cues)
               if cue.get("label") == TARGET_CUE_LABEL and cue.get("kind") == "WingPair"]
    C.require(len(matches) == 1, "TARGET_CUE_COUNT|count=%d" % len(matches))
    C.require(not duplicate, "WINGBURN_ALREADY_AUTHORED")
    checked = material_gate(slot_rows)
    return {
        "cue_index": matches[0],
        "side": TARGET_SIDE,
        "anchor": TARGET_ANCHOR,
        "ignition_uv": [0.5, 1.0],
        "burn_start_ahead_cm": 3000.0,
        "burn_span_cm": 4000.0,
        "materials": checked,
    }


def _kind(value):
    text = str(value).upper()
    return "WingPair" if "WING_PAIR" in text or "WINGPAIR" in text else text


def _cue_rows(show):
    return [{
        "label": str(cue.get_editor_property("label")),
        "kind": _kind(cue.get_editor_property("type")),
    } for cue in show.get_editor_property("cues")]


def _target(show):
    rows = _cue_rows(show)
    matches = [index for index, row in enumerate(rows)
               if row["label"] == TARGET_CUE_LABEL and row["kind"] == "WingPair"]
    C.require(len(matches) == 1, "TARGET_CUE_COUNT|count=%d" % len(matches))
    index = matches[0]
    cue = list(show.get_editor_property("cues"))[index]
    pair = cue.get_editor_property("wing_pair")
    panel = pair.get_editor_property(TARGET_SIDE)
    mesh = panel.get_editor_property("mesh")
    C.require(mesh is not None, "TARGET_MESH_MISSING")
    return rows, index, cue, panel, mesh


def _static_material_rows(mesh, panel):
    overrides = list(panel.get_editor_property("material_overrides"))
    rows = []
    mel = unreal.MaterialEditingLibrary
    static_materials = list(mesh.get_editor_property("static_materials"))
    for index, static in enumerate(static_materials):
        slot = str(static.get_editor_property("material_slot_name"))
        material = overrides[index] if index < len(overrides) and overrides[index] else \
            static.get_editor_property("material_interface")
        parent = None
        use_burn = False
        has_parameter = False
        if material is not None and material.get_class().get_name() == "MaterialInstanceConstant":
            parent = material.get_editor_property("parent")
            name_reader = getattr(mel, "get_static_switch_parameter_names", None)
            if parent is not None and callable(name_reader):
                names = [str(value) for value in name_reader(parent)]
                has_parameter = "UseBurn" in names
            else:
                # The exact parent is independently declaration-proven to own
                # UseBurn; older Python wrappers omit the parameter-name reader.
                has_parameter = C.asset_id(parent) == EXPECTED_MASTER
            if has_parameter:
                use_burn = bool(mel.get_material_instance_static_switch_parameter_value(
                    material, "UseBurn"))
        rows.append({
            "index": index,
            "slot": slot,
            "material": C.asset_id(material),
            "parent": C.asset_id(parent),
            "has_use_burn_parameter": has_parameter,
            "use_burn": use_burn,
        })
    return rows


def _measure_uv(mesh):
    description = mesh.get_static_mesh_description(0)
    C.require(description is not None, "MESH_DESCRIPTION_MISSING")
    ys, zs, us, vs = [], [], [], []
    for index in range(description.get_vertex_instance_count()):
        instance_id = unreal.VertexInstanceID()
        instance_id.set_editor_property("id_value", index)
        vertex_id = description.get_vertex_instance_vertex(instance_id)
        position = description.get_vertex_position(vertex_id)
        uv = description.get_vertex_instance_uv(instance_id, 0)
        ys.append(float(position.y))
        zs.append(float(position.z))
        us.append(float(uv.x))
        vs.append(float(uv.y))
    a_u, b_u, residual_u = linear_fit(ys, us)
    a_v, b_v, residual_v = linear_fit(zs, vs)
    C.require(abs(a_u) > 1.0e-9 and abs(a_v) > 1.0e-9, "UV_MAPPING_DEGENERATE")
    C.require(residual_u <= FIT_TOLERANCE and residual_v <= FIT_TOLERANCE,
              "UV_MAPPING_NON_PLANAR|u=%.9g|v=%.9g" % (residual_u, residual_v))
    return {
        "mesh": C.asset_id(mesh),
        "u_axis": [a_u, b_u],
        "v_axis": [a_v, b_v],
        "u_fit_error": residual_u,
        "v_fit_error": residual_v,
        "samples": len(us),
    }


def _attachments(cue):
    pair = cue.get_editor_property("wing_pair")
    return pair, list(pair.get_editor_property("attachments"))


def _duplicate(cue):
    pair, attachments = _attachments(cue)
    del pair
    return any(str(item.get_editor_property("label")) == TARGET_EFFECT_LABEL
               for item in attachments)


def _snapshot(show, cue_index, attachment_guid_text):
    cue = list(show.get_editor_property("cues"))[cue_index]
    pair, attachments = _attachments(cue)
    del pair
    matches = [item for item in attachments
               if C.guid_text(item.get_editor_property("attachment_guid")) == attachment_guid_text]
    if not matches:
        return None
    C.require(len(matches) == 1, "ATTACHMENT_GUID_DUPLICATE")
    item = matches[0]
    settings = item.get_editor_property("effect")
    return {
        "guid": attachment_guid_text,
        "label": str(item.get_editor_property("label")),
        "kind": str(item.get_editor_property("kind")),
        "anchor": str(item.get_editor_property("anchor")),
        "type": str(settings.get_editor_property("type")),
        "ignition_uv": [
            float(settings.get_editor_property("ignition_uv").x),
            float(settings.get_editor_property("ignition_uv").y),
        ],
        "burn_start_ahead_cm": float(settings.get_editor_property("burn_start_ahead_cm")),
        "burn_span_cm": float(settings.get_editor_property("burn_span_cm")),
        "burn_u_axis": [
            float(settings.get_editor_property("burn_u_axis").x),
            float(settings.get_editor_property("burn_u_axis").y),
        ],
        "burn_v_axis": [
            float(settings.get_editor_property("burn_v_axis").x),
            float(settings.get_editor_property("burn_v_axis").y),
        ],
        "measured_mesh": C.asset_id(settings.get_editor_property("burn_uv_measured_mesh")),
    }


def _remove(show, cue_index, guid_text):
    cues = list(show.get_editor_property("cues"))
    cue = cues[cue_index]
    pair, attachments = _attachments(cue)
    kept = [item for item in attachments
            if C.guid_text(item.get_editor_property("attachment_guid")) != guid_text]
    C.require(len(attachments) - len(kept) == 1, "REVERT_ATTACHMENT_COUNT")
    pair.set_editor_property("attachments", kept)
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _materialize_and_check(show, cue_guid_text):
    actor = C.find_passage_actor(unreal, show, PASSAGE_NUMBER)
    C.require(actor.materialize_passage(), "P06_MATERIALIZE_FAILED")
    refs = list(actor.get_editor_property("materialized_panels"))
    side_token = "RIGHT"
    matches = []
    for ref in refs:
        if (C.guid_text(ref.get_editor_property("cue_guid")) == cue_guid_text
                and side_token in str(ref.get_editor_property("side")).upper()):
            matches.append(ref)
    C.require(len(matches) == 1, "TARGET_PANEL_REF_COUNT|count=%d" % len(matches))
    component = matches[0].get_editor_property("component")
    count = int(component.get_editor_property("num_custom_data_floats"))
    C.require(count == 4, "TARGET_CUSTOM_DATA_FLOATS|expected=4|actual=%d" % count)
    return actor, count


def main(mode=None):
    C.require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    selected = str(mode or globals().get("FX_WINGBURN_MODE", "DRY")).upper()
    C.require(selected in ("DRY", "APPLY", "REVERT"), "MODE_INVALID|" + selected)
    run = C.stamp_now()
    base = C.saved_dir(unreal)
    report_path = os.path.join(base, "fx_wingburn_test_report.json")
    record_path = os.path.join(base, "fx_wingburn_test_record.json")
    report = {"ok": False, "mode": selected, "run": run}

    def fail(error):
        report["error"] = str(error)
        report["census_at_stop"] = C.dirty_census(unreal)
        C.write_json(report_path, report)
        unreal.log_error("FX_WINGBURN_TEST_STOPPED|run=%s|mode=%s|%s" %
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
        rows, cue_index, cue, panel, mesh = _target(show)

        # Revert removes only the recorded attachment.  It must not depend on
        # the mesh, UVs, or material switch still matching apply-time state.
        if selected == "REVERT":
            C.require(os.path.isfile(record_path), "REVERT_RECORD_MISSING")
            record = C.load_json(record_path)
            C.require(record.get("status") == "applied", "REVERT_RECORD_NOT_APPLIED")
            cue_index = int(record["cue_index"])
            guid_text = record["attachment_guid"]
            C.require(_snapshot(show, cue_index, guid_text) == record["expected"],
                      "REVERT_LIVE_STATE_MISMATCH")
            backup = C.backup_packages(
                unreal, "PreFxWingBurnTestRevert-", run,
                [C.SHOW_PATH, C.EXPECTED_WORLD])
            _remove(show, cue_index, guid_text)
            actor = C.find_passage_actor(unreal, show, PASSAGE_NUMBER)
            C.require(actor.materialize_passage(), "P06_REVERT_MATERIALIZE_FAILED")
            expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
            C.require(C.dirty_census(unreal) == expected_dirty,
                      "REVERT_DIRTY_SCOPE|actual=" +
                      json.dumps(C.dirty_census(unreal), sort_keys=True))
            C.save_show_and_level(unreal)
            C.require(_snapshot(show, cue_index, guid_text) is None,
                      "REVERT_READBACK_PRESENT")
            command = C.queue_saved_master_test(
                unreal, world, "FX_WINGBURN_TEST_REVERT", run)
            archived = C.archive_record(record_path, run)
            report.update({"ok": True, "backup": backup, "archived_record": archived,
                           "dirty_after": C.dirty_census(unreal),
                           "saved_master_command": command})
            C.write_json(report_path, report)
            unreal.log("FX_WINGBURN_TEST_REVERTED|run=%s|cue='%s'|side=%s|backup=%s|record=%s|census=%s" %
                       (run, TARGET_CUE_LABEL, TARGET_SIDE, backup["root"], archived,
                        json.dumps(report["dirty_after"], separators=(",", ":"))))
            return

        slot_rows = _static_material_rows(mesh, panel)
        uv = _measure_uv(mesh)
        duplicate = _duplicate(cue)
        plan = wingburn_plan(rows, slot_rows, duplicate)
        report.update({"plan": plan, "uv_mapping": uv, "mesh": C.asset_id(mesh),
                       "slot_rows": slot_rows})

        if selected == "DRY":
            C.require(C.dirty_census(unreal) == report["dirty_before"],
                      "DRY_CHANGED_CENSUS")
            report.update({"ok": True, "dirty_after": C.dirty_census(unreal)})
            C.write_json(report_path, report)
            unreal.log("FX_WINGBURN_TEST_DRY_OK|run=%s|cue='%s'|side=%s|mesh=%s|u=%s|v=%s|census=%s" %
                       (run, TARGET_CUE_LABEL, TARGET_SIDE, C.asset_id(mesh),
                        json.dumps(uv["u_axis"]), json.dumps(uv["v_axis"]),
                        json.dumps(report["dirty_after"], separators=(",", ":"))))
            return

        if selected == "APPLY":
            C.require(not os.path.exists(record_path), "APPLY_RECORD_ALREADY_EXISTS")
            backup = C.backup_packages(
                unreal, "PreFxWingBurnTest-", run, [C.SHOW_PATH, C.EXPECTED_WORLD])
            record = {
                "status": "prepared",
                "run": run,
                "backup": backup,
                "cue_index": cue_index,
                "cue_guid": C.guid_text(cue.get_editor_property("cue_guid")),
                "cue_label": TARGET_CUE_LABEL,
                "side": TARGET_SIDE,
                "mesh": C.asset_id(mesh),
                "materials": plan["materials"],
                "uv_mapping": uv,
            }
            C.write_json(record_path, record, exclusive=True)
            effect_type = C.enum_member(unreal.InfinityStageEffectType,
                                        "WING_BURN", "WINGBURN")
            anchor = C.enum_member(unreal.InfinityAttachmentAnchor, TARGET_ANCHOR)
            identity = unreal.Transform(
                location=unreal.Vector(0.0, 0.0, 0.0),
                rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
                scale=unreal.Vector(1.0, 1.0, 1.0),
            )
            guid = unreal.InfinityStageEffectLibrary.add_effect_attachment(
                show, cue.get_editor_property("cue_guid"), effect_type, anchor,
                identity, TARGET_EFFECT_LABEL)
            guid_text = C.guid_text(guid)
            C.require(guid_text.strip("0()=AGUID"), "ADD_WINGBURN_INVALID_GUID")
            ok = unreal.InfinityStageEffectLibrary.set_wing_burn_uv_mapping(
                show, cue.get_editor_property("cue_guid"), guid,
                unreal.Vector2D(*uv["u_axis"]), unreal.Vector2D(*uv["v_axis"]), mesh)
            C.require(ok, "SET_WINGBURN_UV_FAILED")
            expected = _snapshot(show, cue_index, guid_text)
            C.require(expected is not None, "IN_MEMORY_READBACK_MISSING")
            C.require(expected["ignition_uv"] == [0.5, 1.0], "IGNITION_DEFAULT_CHANGED")
            C.require(expected["burn_start_ahead_cm"] == 3000.0,
                      "BURN_START_DEFAULT_CHANGED")
            C.require(expected["burn_span_cm"] == 4000.0,
                      "BURN_SPAN_DEFAULT_CHANGED")
            actor, custom_float_count = _materialize_and_check(show, record["cue_guid"])
            del actor
            expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
            C.require(C.dirty_census(unreal) == expected_dirty,
                      "APPLY_DIRTY_SCOPE|actual=" + json.dumps(C.dirty_census(unreal), sort_keys=True))
            C.save_show_and_level(unreal)
            actual = _snapshot(show, cue_index, guid_text)
            C.require(actual == expected, "SAVED_READBACK_MISMATCH")
            command = C.queue_saved_master_test(unreal, world, "FX_WINGBURN_TEST", run)
            record.update({"status": "applied", "attachment_guid": guid_text,
                           "expected": expected, "custom_data_floats": custom_float_count,
                           "saved_master_command": command})
            C.write_json(record_path, record)
            report.update({"ok": True, "backup": backup, "readback": actual,
                           "custom_data_floats": custom_float_count,
                           "dirty_after": C.dirty_census(unreal),
                           "saved_master_command": command})
            C.write_json(report_path, report)
            unreal.log("FX_WINGBURN_TEST_APPLIED|run=%s|cue='%s'|side=%s|attachment=%s|mesh=%s|custom_data=4|backup=%s|census=%s" %
                       (run, TARGET_CUE_LABEL, TARGET_SIDE, guid_text, C.asset_id(mesh),
                        backup["root"],
                        json.dumps(report["dirty_after"], separators=(",", ":"))))
            return

    except Exception as error:  # noqa: BLE001 - report every fail-closed stop.
        fail(error)


if __name__ == "__main__":
    main()
