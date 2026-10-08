"""Guarded DRY/APPLY/REVERT placement tool for the P03 bone dune.

Offline-authored only on 8 Oct 2026: this module has not been run in Unreal.
It adds seven Station-anchored PROP attachments to P03 Wing 013 (one dune and
six separate bones), materializes only P03, saves only the Show and current
level, then reads every minted GUID back. Gary must approve the previews first.

Args: Saved/CodexConductor/P03BoneDune/p03_bone_dune_request.json
Confirm strings: APPLY P03 BONE DUNE / REVERT P03 BONE DUNE
"""
from __future__ import annotations

import importlib.util
import json
import os

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = _load(os.path.join(CORE, "_fx_authoring_common.py"), "_p03_bone_dune_common")
K = _load(os.path.join(HERE, "p03_bone_dune_contract.py"), "_p03_bone_dune_contract")
STATE = _load(os.path.join(CORE, "_infinity_attachment_state.py"), "_p03_bone_dune_state")

ARGS = os.path.join(HERE, "p03_bone_dune_request.json")
RECORD = os.path.join(HERE, "p03_bone_dune_record.json")
LABEL_PREFIX = "P03 BONE DUNE"
PASSAGE_NUMBER = 3


def require(condition, token):
    H.require(condition, token)


def cue_kind(value):
    text = str(value).upper()
    return "WingPair" if "WING_PAIR" in text or "WINGPAIR" in text else text


def enum(enum_type, *names):
    return H.enum_member(enum_type, *names)


def attachments_of(cue):
    pair = cue.get_editor_property("wing_pair")
    return pair, list(pair.get_editor_property("attachments"))


def set_attachments(show, index, attachments):
    cues = list(show.get_editor_property("cues"))
    cue = cues[index]
    pair = cue.get_editor_property("wing_pair")
    pair.set_editor_property("attachments", list(attachments))
    cue.set_editor_property("wing_pair", pair)
    cues[index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def target_index(show, args):
    hits = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        if str(cue.get_editor_property("label")) == args["cue_label"]:
            hits.append((index, H.guid_text(cue.get_editor_property("cue_guid")), cue_kind(cue.get_editor_property("type"))))
    require(len(hits) == 1, "TARGET_CUE_COUNT|%s" % hits)
    require(hits[0][1:] == (args["cue_guid"], "WingPair"), "TARGET_CUE_IDENTITY|%s" % hits)
    return hits[0][0]


def make_transform(row):
    loc = row["location_cm"]
    rpy = row["rotation_rpy_deg"]
    scale = row.get("scale", [1, 1, 1])
    return unreal.Transform(location=unreal.Vector(*loc),
                            rotation=unreal.Rotator(roll=rpy[0], pitch=rpy[1], yaw=rpy[2]),
                            scale=unreal.Vector(*scale))


def plain_attachment(item):
    return {
        "guid": H.guid_text(item.get_editor_property("attachment_guid")),
        "label": str(item.get_editor_property("label")),
        "kind": str(item.get_editor_property("kind")),
        "enabled": bool(item.get_editor_property("enabled")),
        "anchor": str(item.get_editor_property("anchor")),
        "mesh": H.asset_id(item.get_editor_property("mesh")),
        "relative_transform": H.transform_plain(item.get_editor_property("relative_transform")),
    }


def valid_guid(item):
    text = H.guid_text(item.get_editor_property("attachment_guid"))
    compact = "".join(ch for ch in text if ch in "0123456789ABCDEF")
    return len(compact) == 32 and bool(compact.strip("0"))


def blank_light():
    item = unreal.InfinityCueAttachment()
    item.set_editor_property("label", "P03 BONE DUNE GUID SCRATCH")
    item.set_editor_property("kind", enum(unreal.InfinityAttachmentKind, "LIGHT"))
    item.set_editor_property("enabled", False)
    item.set_editor_property("anchor", enum(unreal.InfinityAttachmentAnchor, "STATION"))
    item.set_editor_property("relative_transform", make_transform(
        {"location_cm": [0, 0, 0], "rotation_rpy_deg": [0, 0, 0], "scale": [1, 1, 1]}))
    lighting = item.get_editor_property("lighting")
    lighting.set_editor_property("intensity", 0.0)
    lighting.set_editor_property("cast_shadows", False)
    item.set_editor_property("lighting", lighting)
    return item


def prop_template(row):
    mesh = unreal.load_asset(row["mesh"])
    require(mesh is not None and isinstance(mesh, unreal.StaticMesh), "MESH_LOAD|" + row["mesh"])
    item = unreal.InfinityCueAttachment()
    item.set_editor_property("label", row["label"])
    item.set_editor_property("kind", enum(unreal.InfinityAttachmentKind, "PROP"))
    item.set_editor_property("enabled", True)
    item.set_editor_property("mesh", mesh)
    item.set_editor_property("anchor", enum(unreal.InfinityAttachmentAnchor, "STATION"))
    item.set_editor_property("relative_transform", make_transform(row["transform"]))
    return item


def overwrite_vessel(vessel, template):
    guid = H.guid_text(vessel.get_editor_property("attachment_guid"))
    require(valid_guid(vessel), "MINTED_GUID_INVALID")
    for field in ("label", "kind", "enabled", "actor_class", "mesh", "anchor", "relative_transform",
                  "lighting", "effect", "trigger_distance_cm"):
        vessel.set_editor_property(field, template.get_editor_property(field))
    require(H.guid_text(vessel.get_editor_property("attachment_guid")) == guid, "MINTED_GUID_CHANGED")
    return vessel


def mint_props(show, target, rows):
    cues = list(show.get_editor_property("cues"))
    _pair, original = attachments_of(cues[target])
    existing = {H.guid_text(item.get_editor_property("attachment_guid"))
                for cue in cues if cue_kind(cue.get_editor_property("type")) == "WingPair"
                for item in attachments_of(cue)[1]}
    target_lights = sum(item.get_editor_property("kind") == enum(unreal.InfinityAttachmentKind, "LIGHT") for item in original)
    scratch = next((i for i in reversed(range(len(cues)))
                    if i != target and cue_kind(cues[i].get_editor_property("type")) == "WingPair"), None)
    require(scratch is not None, "SCRATCH_CUE_MISSING")
    _sp, scratch_original = attachments_of(cues[scratch])
    scratch_before = [STATE.attachment_state(item, H.guid_text) for item in scratch_original]
    scratch_lights = sum(item.get_editor_property("kind") == enum(unreal.InfinityAttachmentKind, "LIGHT")
                         for item in scratch_original)
    padding = max(0, target_lights + len(rows) - scratch_lights)
    complete = False
    try:
        set_attachments(show, scratch, scratch_original + [blank_light() for _ in range(padding)])
        count = show.replicate_light_attachments(
            list(show.get_editor_property("cues"))[scratch].get_editor_property("cue_guid"),
            [list(show.get_editor_property("cues"))[target].get_editor_property("cue_guid")])
        require(int(count) == 1, "REPLICATION_TARGET_COUNT|%s" % count)
        set_attachments(show, scratch, scratch_original)
        replicated = attachments_of(list(show.get_editor_property("cues"))[target])[1]
        vessels = [item for item in replicated
                   if item.get_editor_property("kind") == enum(unreal.InfinityAttachmentKind, "LIGHT")]
        vessels = vessels[target_lights:target_lights + len(rows)]
        require(len(vessels) == len(rows), "REPLICATION_SLOT_COUNT")
        props = [overwrite_vessel(vessel, prop_template(row)) for vessel, row in zip(vessels, rows)]
        guids = [H.guid_text(item.get_editor_property("attachment_guid")) for item in props]
        require(len(set(guids)) == len(rows) and not (set(guids) & existing), "MINTED_GUID_SET")
        set_attachments(show, target, original + props)
        scratch_after = [STATE.attachment_state(item, H.guid_text)
                         for item in attachments_of(list(show.get_editor_property("cues"))[scratch])[1]]
        require(not STATE.state_differences(scratch_before, scratch_after), "SCRATCH_NOT_RESTORED")
        complete = True
        return props, {"scratch_index": scratch, "padding": padding}
    finally:
        set_attachments(show, scratch, scratch_original)
        if not complete:
            set_attachments(show, target, original)


def owned(show, index, guids=None):
    wanted = set(guids or [])
    rows = []
    for item in attachments_of(list(show.get_editor_property("cues"))[index])[1]:
        state = plain_attachment(item)
        if state["label"].startswith(LABEL_PREFIX) or state["guid"] in wanted:
            rows.append(state)
    return sorted(rows, key=lambda row: row["label"])


def remove_guids(show, index, guids):
    pair, items = attachments_of(list(show.get_editor_property("cues"))[index])
    wanted = set(guids)
    kept = [item for item in items if H.guid_text(item.get_editor_property("attachment_guid")) not in wanted]
    require(len(items) - len(kept) == len(wanted), "REMOVE_GUID_COUNT")
    set_attachments(show, index, kept)


def report_path(mode, run):
    return os.path.join(HERE, "p03_bone_dune_report_%s_%s.json" % (mode, run))


def main():
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = H.stamp_now()
    raw = json.load(open(ARGS, encoding="utf-8")) if os.path.isfile(ARGS) else {}
    args = K.check_args(raw)
    plan = K.placement_plan(args)
    report = {"run": run, "mode": args["mode"], "args": args, "plan": plan, "ok": False}
    try:
        report["dirty_before"] = H.require_clean(unreal, "PRE")
        _editor, world = H.editor_context(unreal)
        show = unreal.load_asset(H.SHOW_PATH)
        require(show is not None, "SHOW_LOAD")
        index = target_index(show, args)
        report["existing_owned"] = owned(show, index)
        if args["mode"] == "DRY":
            require(not report["existing_owned"], "OWNED_ATTACHMENTS_ALREADY_PRESENT")
            for row in plan["all"]:
                require(unreal.EditorAssetLibrary.does_asset_exist(row["mesh"]), "ASSET_MISSING|" + row["mesh"])
            require(H.dirty_census(unreal) == report["dirty_before"], "DRY_CHANGED_CENSUS")
            report.update({"ok": True, "dirty_after": H.dirty_census(unreal)})
            H.write_json(report_path("DRY", run), report)
            unreal.log("P03_BONE_DUNE_DRY_OK|run=%s|cue=%s|props=%d|route_clearance_cm=%.1f" %
                       (run, args["cue_label"], len(plan["all"]), plan["route_clearance_cm"]))
            return
        expected_dirty = {"content": [H.SHOW_PATH], "maps": [H.EXPECTED_WORLD]}
        if args["mode"] == "APPLY":
            require(not os.path.isfile(RECORD), "APPLY_RECORD_EXISTS")
            require(not report["existing_owned"], "OWNED_ATTACHMENTS_ALREADY_PRESENT")
            backup = H.backup_packages(unreal, "PreP03BoneDune-", run, [H.SHOW_PATH, H.EXPECTED_WORLD])
            record = {"schema": "p03_bone_dune_record/1", "run": run, "status": "prepared",
                      "target": plan["target"], "plan": plan, "backup": backup, "added": []}
            H.write_json(RECORD, record, exclusive=True)
            props, mint = mint_props(show, index, plan["all"])
            expected = [plain_attachment(item) for item in props]
            record.update({"added": expected, "guid_mint": mint, "status": "in_memory"})
            H.write_json(RECORD, record)
            actor = H.find_passage_actor(unreal, show, PASSAGE_NUMBER)
            require(actor.materialize_passage(), "MATERIALIZE_FAILED")
            require(H.dirty_census(unreal) == expected_dirty, "APPLY_DIRTY_SCOPE|%s" % H.dirty_census(unreal))
            H.save_show_and_level(unreal)
            actual = owned(unreal.load_asset(H.SHOW_PATH), index, [row["guid"] for row in expected])
            require(not K.drift_paths(sorted(expected, key=lambda x: x["label"]), actual), "SAVED_READBACK_MISMATCH")
            command = H.queue_saved_master_test(unreal, world, "P03_BONE_DUNE", run)
            record.update({"status": "applied", "saved_master_command": command})
            H.write_json(RECORD, record)
            report.update({"ok": True, "backup": backup, "readback": actual,
                           "dirty_after": H.dirty_census(unreal), "saved_master_command": command})
            H.write_json(report_path("APPLY", run), report)
            unreal.log("P03_BONE_DUNE_APPLY_OK|run=%s|props=%d|backup=%s|census=%s" %
                       (run, len(actual), backup["root"], json.dumps(report["dirty_after"], separators=(",", ":"))))
            return
        require(os.path.isfile(RECORD), "REVERT_RECORD_MISSING")
        record = H.load_json(RECORD)
        require(record.get("status") == "applied", "REVERT_RECORD_STATUS")
        guids = [row["guid"] for row in record["added"]]
        live = owned(show, index, guids)
        drift = K.drift_paths(sorted(record["added"], key=lambda x: x["label"]), live)
        require(not drift or args["revert_accept_drift"], "REVERT_DRIFT|%s" % drift)
        backup = H.backup_packages(unreal, "PreP03BoneDuneRevert-", run, [H.SHOW_PATH, H.EXPECTED_WORLD])
        remove_guids(show, index, guids)
        actor = H.find_passage_actor(unreal, show, PASSAGE_NUMBER)
        require(actor.materialize_passage(), "REVERT_MATERIALIZE_FAILED")
        require(H.dirty_census(unreal) == expected_dirty, "REVERT_DIRTY_SCOPE|%s" % H.dirty_census(unreal))
        H.save_show_and_level(unreal)
        require(not owned(unreal.load_asset(H.SHOW_PATH), index, guids), "REVERT_READBACK_PRESENT")
        command = H.queue_saved_master_test(unreal, world, "P03_BONE_DUNE_REVERT", run)
        record.update({"status": "reverted", "revert_run": run, "revert_backup": backup,
                       "saved_master_command": command})
        H.write_json(RECORD, record)
        report.update({"ok": True, "backup": backup, "dirty_after": H.dirty_census(unreal),
                       "saved_master_command": command})
        H.write_json(report_path("REVERT", run), report)
        unreal.log("P03_BONE_DUNE_REVERT_OK|run=%s|removed=%d|backup=%s" % (run, len(guids), backup["root"]))
    except Exception as error:
        report["error"] = str(error)
        try:
            report["census_at_stop"] = H.dirty_census(unreal)
            H.write_json(report_path(args["mode"], run), report)
        except Exception:
            pass
        unreal.log_error("P03_BONE_DUNE_STOPPED|run=%s|mode=%s|%s|if dirty: Don't-Save restart" %
                         (run, args["mode"], error))
        raise


if unreal is not None and __name__ in ("__main__", "__p03_bone_dune_runner__"):
    main()
