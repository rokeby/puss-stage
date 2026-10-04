"""Set the six Scene cues' Camera Owner to Timeline (Gary, 4 Oct).

Gary, 4 Oct: "Keep all camera locked and let dog freelook be optional."
All six Scene cues of DA_InfinityStage_V1Show go to
FInfinitySceneCueData::CameraOwner = Timeline. Dog free-look stays available as
the operator's live Force Dog override (Docs/Conductor/SCENE_CAMERA_OWNERS_2026-10-04.md).

Modes: DRY (default), APPLY, REVERT. The runner scripts select a mode with
``runpy.run_path(..., init_globals={"SCENE_CAMERA_OWNER_MODE": "APPLY"})``.

Names used, and how sure we are of each:
* ``cues``, ``cue_guid``, ``type``, ``label``, ``scene``, ``camera_owner`` --
  declaration-proven UPROPERTY names (InfinityStageShowAsset.h:49,
  InfinityStageTypes.h:910,913,916,928,814) and measured: the same names were
  read and written by Saved/CodexCameraPilot/apply_camera_owners.py on 30 Sep.
* ``unreal.InfinityCameraOwner.TIMELINE / DOG_FREE_LOOK / DOG_GAZE_ONLY`` and
  ``unreal.InfinityCueType.SCENE`` -- declaration-proven enumerators
  (InfinityStageTypes.h:45-55, 21-26); the Python spellings were measured
  (audit_camera_owners.json prints ``<InfinityCameraOwner.TIMELINE: 0>``).
* ``StructBase.export_text()`` -- INFERRED (UE Python API; the engine's
  private source is not on this machine). DRY stops with
  ``EXPORT_TEXT_MISSING`` if it is absent, and cross-checks the exported
  ``CameraOwner=`` token against the property read for every target, so a wrong
  assumption about the text format stops the run before any write.

Fail-closed rules: refuses (never ends) PIE/SIE; refuses an open Sequencer;
refuses any dirty package before it starts; backs up the Show to
Backups/PreSceneCameraOwner-YYYYMMDD-HHMM/; changes only the six CameraOwner
fields, keyed by cue GUID (label is a drift check); proves everything else in
the Show is byte-identical in export text (outside hash); saves ONLY the Show
asset (never Save All, never the level, never reloads anything); reads back;
logs one explicit marker per run carrying the run id.

Everything Unreal-related lives inside functions: UE wrappers left in module
globals crash the editor on a re-run (memory: MCP Python crash pattern 4).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import uuid

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness import.
    unreal = None


EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
VALID_MODES = ("DRY", "APPLY", "REVERT")
MARKER = "SCENE_CAMERA_OWNER"
BACKUP_PREFIX = "PreSceneCameraOwner-"
DECIDED_BY = ("Gary, 4 Oct 2026: 'Keep all camera locked and let dog freelook be "
              "optional.' (Docs/Conductor/MORNING_SUMMARY_2026-10-04.md:82)")

# The six Scene cues, keyed by cue GUID. GUIDs and labels recorded in
# Saved/CodexStructure/arrivals_probe.json; labels also in
# Saved/CodexCameraPilot/camera_owner_plan.json (all DOG_FREE_LOOK since
# 30 Sep 17:42). The index is informational only (cues get inserted).
TARGETS = (
    {"guid": "91030A272145EBEF25D33BA016458739", "label": "Scene 1 \u2014 External Sound", "recorded_index": 49},
    {"guid": "42D2F59416487AF7018DAEB62639C9BB", "label": "Scene 2 \u2014 External Sound", "recorded_index": 74},
    {"guid": "D8F61D9DF94F1E6080CC8D9028EE49D3", "label": "Scene 3 \u2014 External Sound", "recorded_index": 97},
    {"guid": "5C960C0C7A462BFEA4C86F93ADF5558D", "label": "Scene 4 \u2014 External Sound", "recorded_index": 120},
    {"guid": "730D67269F425DDC45C72A867BA04217", "label": "Scene 5 \u2014 External Sound", "recorded_index": 215},
    {"guid": "673B3535884DEBAE99723B8CC6BE877B", "label": "Scene 6 \u2014 External Sound", "recorded_index": 272},
)
TARGET_OWNER = "TIMELINE"
OWNER_NAMES = ("TIMELINE", "DOG_FREE_LOOK", "DOG_GAZE_ONLY")

# Every UPROPERTY of UInfinityStageShowAsset (InfinityStageShowAsset.h:39-66)
# except the two TSoftObjectPtrs (managed_master_sequence, wing_library),
# which are not read so the Master is never resolved/loaded by this tool.
# Rewriting ``cues`` cannot reach them (inferred: separate properties).
SHOW_PROPERTIES = ("show_guid", "display_rate", "tick_resolution", "cues",
                   "passage_settings", "music_rails", "schema_version")
CAMERA_OWNER_TOKEN = re.compile(r"CameraOwner=([A-Za-z_:]+)")

_HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(_HERE, "scene_camera_owner_report.json")
RECORD_PATH = os.path.join(_HERE, "scene_camera_owner_revert_record.json")


class SceneCameraOwnerError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise SceneCameraOwnerError(str(message))


# ---------------------------------------------------------------- plain helpers
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


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _norm_guid(text):
    return "".join(c for c in str(text).upper() if c in "0123456789ABCDEF")


def _token_matches_owner(token, owner_name):
    """'DogFreeLook' / 'EInfinityCameraOwner::DogFreeLook' <-> 'DOG_FREE_LOOK'."""
    short = token.split("::")[-1]
    return short.replace("_", "").lower() == owner_name.replace("_", "").lower()


def neutral_cue_text(text):
    """Export text with its single CameraOwner token blanked; else stop."""
    found = CAMERA_OWNER_TOKEN.findall(text)
    require(len(found) == 1, "CAMERA_OWNER_TOKEN_COUNT|count=%d" % len(found))
    return CAMERA_OWNER_TOKEN.sub("CameraOwner=<target>", text), found[0]


# ---------------------------------------------------------------- engine access
def _guid_text(value):
    try:
        return _norm_guid(unreal.GuidLibrary.conv_guid_to_string(value))
    except Exception:  # noqa: BLE001 - wrapper variants differ.
        return _norm_guid(value)


def _asset_id(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name()).split(".", 1)[0]
    return str(value).split(".", 1)[0]


def _owner_members():
    enum_type = getattr(unreal, "InfinityCameraOwner", None)
    require(enum_type is not None, "ENUM_MISSING|enum=InfinityCameraOwner")
    members = {}
    for name in OWNER_NAMES:
        require(hasattr(enum_type, name), "ENUM_MEMBER_MISSING|enum=InfinityCameraOwner|name=" + name)
        members[name] = getattr(enum_type, name)
    return members


def _scene_type():
    enum_type = getattr(unreal, "InfinityCueType", None)
    require(enum_type is not None and hasattr(enum_type, "SCENE"),
            "ENUM_MEMBER_MISSING|enum=InfinityCueType|name=SCENE")
    return enum_type.SCENE


def _owner_name(value, members):
    for name, member in members.items():
        if value == member:
            return name
    raise SceneCameraOwnerError("OWNER_VALUE_UNKNOWN|value=%r" % (value,))


def _export(value):
    exporter = getattr(value, "export_text", None)
    require(callable(exporter), "EXPORT_TEXT_MISSING|type=" + type(value).__name__)
    return str(exporter())


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if callable(getattr(value, "export_text", None)):
        return _export(value)
    if isinstance(value, (list, tuple)) or (hasattr(value, "__len__") and hasattr(value, "__getitem__")):
        return [_plain(item) for item in list(value)]
    if callable(getattr(value, "get_path_name", None)):
        return str(value.get_path_name())
    require(False, "UNHASHABLE_VALUE|type=" + type(value).__name__)


def _cues(show):
    return list(show.get_editor_property("cues"))


def _cue_owner(cue):
    return cue.get_editor_property("scene").get_editor_property("camera_owner")


def show_state(show, target_guids):
    """Field-complete Show state; target cues carry their CameraOwner blanked
    in ``outside`` and verbatim in ``full``."""
    targets = set(target_guids)
    full, outside = {}, {}
    for name in SHOW_PROPERTIES:
        if name == "cues":
            full_rows, outside_rows = [], []
            for cue in _cues(show):
                text = _export(cue)
                guid = _guid_text(cue.get_editor_property("cue_guid"))
                full_rows.append(text)
                outside_rows.append(neutral_cue_text(text)[0] if guid in targets else text)
            full[name], outside[name] = full_rows, outside_rows
        else:
            full[name] = outside[name] = _plain(show.get_editor_property(name))
    return {"full_hash": _state_hash(full), "outside_hash": _state_hash(outside),
            "cue_count": len(full["cues"])}


def resolve_targets(show, members, targets=None):
    """Find each target by GUID; label and Scene-set are drift checks."""
    targets = TARGETS if targets is None else targets
    scene_type = _scene_type()
    cues = _cues(show)
    by_guid = {}
    scene_guids = []
    for index, cue in enumerate(cues):
        guid = _guid_text(cue.get_editor_property("cue_guid"))
        by_guid.setdefault(guid, []).append(index)
        if cue.get_editor_property("type") == scene_type:
            scene_guids.append(guid)
    rows = []
    for target in targets:
        hits = by_guid.get(target["guid"], [])
        require(len(hits) == 1, "TARGET_GUID_%s|guid=%s|label=%s" % (
            "MISSING" if not hits else "DUPLICATE", target["guid"], target["label"]))
        index = hits[0]
        cue = cues[index]
        label = str(cue.get_editor_property("label"))
        require(label == target["label"], "TARGET_LABEL_DRIFT|guid=%s|expected=%s|actual=%s" % (
            target["guid"], target["label"], label))
        require(cue.get_editor_property("type") == scene_type,
                "TARGET_NOT_SCENE|guid=%s|type=%s" % (target["guid"], cue.get_editor_property("type")))
        owner = _owner_name(_cue_owner(cue), members)
        unused, token = neutral_cue_text(_export(cue))
        require(_token_matches_owner(token, owner),
                "EXPORT_TOKEN_MISMATCH|guid=%s|token=%s|property=%s" % (target["guid"], token, owner))
        rows.append({"guid": target["guid"], "label": label, "index": index,
                     "recorded_index": target.get("recorded_index"),
                     "owner_before": owner, "export_token": token})
    wanted = sorted(t["guid"] for t in targets)
    require(sorted(scene_guids) == wanted,
            "SCENE_SET_DRIFT|scenes=%s|targets=%s" % (",".join(sorted(scene_guids)), ",".join(wanted)))
    return rows


def write_owners(show, owner_by_guid, members):
    """Rewrite the cues array with the given owners on the given GUIDs only."""
    cues = _cues(show)
    touched = 0
    for index, cue in enumerate(cues):
        guid = _guid_text(cue.get_editor_property("cue_guid"))
        if guid not in owner_by_guid:
            continue
        scene = cue.get_editor_property("scene")
        scene.set_editor_property("camera_owner", members[owner_by_guid[guid]])
        cue.set_editor_property("scene", scene)
        cues[index] = cue
        touched += 1
    require(touched == len(owner_by_guid), "WRITE_TOUCHED|expected=%d|actual=%d" % (len(owner_by_guid), touched))
    show.set_editor_property("cues", cues)


def read_owners(show, guids, members):
    wanted = set(guids)
    return {_guid_text(cue.get_editor_property("cue_guid")): _owner_name(_cue_owner(cue), members)
            for cue in _cues(show)
            if _guid_text(cue.get_editor_property("cue_guid")) in wanted}


def verify_state(show, expected_owners, outside_hash, cue_count, members, phase):
    actual = read_owners(show, expected_owners, members)
    require(actual == expected_owners, "%s_OWNERS_MISMATCH|expected=%s|actual=%s" % (
        phase, _canonical(expected_owners), _canonical(actual)))
    state = show_state(show, expected_owners)
    require(state["cue_count"] == cue_count, "%s_CUE_COUNT|expected=%d|actual=%d" % (
        phase, cue_count, state["cue_count"]))
    _require_outside_unchanged(outside_hash, state["outside_hash"], phase)
    return state


def _require_outside_unchanged(expected, actual, phase):
    require(expected == actual, "%s_OUTSIDE_HASH_CHANGED|expected=%s|actual=%s" % (phase, expected, actual))


# ---------------------------------------------------------------- editor context
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
    # Refuse, never end: this tool must not stop PIE or quit the editor.
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE|refused_not_ended=1")
    world = editor.get_editor_world()
    require(world is not None and _asset_id(world) == EXPECTED_WORLD, "WRONG_WORLD|actual=" + str(_asset_id(world)))
    sequence_library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    if sequence_library is not None:
        require(sequence_library.get_current_level_sequence() is None, "SEQUENCER_IS_OPEN")
    census = _dirty_census()
    require(census == {"content": [], "maps": []}, "DIRTY_BEFORE|census=" + _canonical(census))


def _show_file():
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    path = os.path.normpath(os.path.join(content, SHOW_PATH[len("/Game/"):].replace("/", os.sep) + ".uasset"))
    require(os.path.isfile(path), "SHOW_FILE_MISSING|path=" + path)
    return path


def _backup(stamp_minute):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    root = os.path.join(project, "Backups", BACKUP_PREFIX + stamp_minute)
    require(not os.path.exists(root), "BACKUP_DIR_EXISTS|path=" + root)
    source = _show_file()
    destination = os.path.join(root, SHOW_PATH[len("/Game/"):].replace("/", os.sep) + ".uasset")
    os.makedirs(os.path.dirname(destination), exist_ok=False)
    shutil.copy2(source, destination)
    source_hash = _sha256_file(source)
    require(source_hash == _sha256_file(destination), "BACKUP_HASH_MISMATCH")
    return {"root": root, "source": source, "backup": destination,
            "bytes": os.path.getsize(source), "sha256": source_hash}


def _mutate_and_save(show, owner_by_guid, restore_by_guid, expected_owners,
                     outside_hash, cue_count, members, phase):
    """Write, verify in memory, census, save the Show only, read back.

    On any failure before the save, the owners are written back in memory and
    nothing is saved (the Show package may stay dirty: reported, not saved).
    """
    try:
        write_owners(show, owner_by_guid, members)
        verify_state(show, expected_owners, outside_hash, cue_count, members, phase + "_MEMORY")
        census = _dirty_census()
        require(census == {"content": [SHOW_PATH], "maps": []},
                phase + "_CENSUS_AFTER_MUTATION|census=" + _canonical(census))
    except Exception:
        try:
            write_owners(show, restore_by_guid, members)
        except Exception as rollback_error:  # noqa: BLE001
            unreal.log_error("%s_ROLLBACK_FAILED|%s" % (MARKER, rollback_error))
        raise
    require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), phase + "_SHOW_SAVE_FAILED")
    census = _dirty_census()
    require(census == {"content": [], "maps": []}, phase + "_DIRTY_AFTER_SAVE|census=" + _canonical(census))
    readback = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    require(readback is not None, phase + "_READBACK_LOAD_FAILED")
    return verify_state(readback, expected_owners, outside_hash, cue_count, members, phase + "_READBACK")


# ---------------------------------------------------------------- modes
def _run(mode):
    now = datetime.datetime.now()
    run = now.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    report = {"ok": False, "mode": mode, "run": run, "decided_by": DECIDED_BY}
    unreal.log("%s_BEGIN|run=%s|mode=%s" % (MARKER, run, mode))
    try:
        _require_context()
        members = _owner_members()
        show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        rows = resolve_targets(show, members)
        guids = [row["guid"] for row in rows]
        state = show_state(show, guids)
        report.update({
            "found": {"enum_members": {name: str(m) for name, m in members.items()},
                      "export_text": "available", "targets": rows,
                      "scene_cue_count": len(rows), "cue_count": state["cue_count"],
                      "show_properties_hashed": list(SHOW_PROPERTIES)},
            "before": state,
        })

        if mode == "DRY":
            would = [row["guid"] for row in rows if row["owner_before"] != TARGET_OWNER]
            report.update({"ok": True, "mutated": False, "would_change": would,
                           "active_record": os.path.exists(RECORD_PATH), "census": _dirty_census()})
            _write_json(REPORT_PATH, report)
            unreal.log("%s_DRY_OK|run=%s|targets=%d|would_change=%d|owners=%s|token_check=1|mutated=0" % (
                MARKER, run, len(rows), len(would),
                ",".join("%s:%s" % (r["label"][:7], r["owner_before"]) for r in rows)))
            return report

        if mode == "APPLY":
            require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS|path=" + RECORD_PATH)
            before = {row["guid"]: row["owner_before"] for row in rows}
            change = {guid: TARGET_OWNER for guid, owner in before.items() if owner != TARGET_OWNER}
            if not change:
                report.update({"ok": True, "noop": True, "mutated": False})
                _write_json(REPORT_PATH, report)
                unreal.log("%s_APPLY_NOOP|run=%s|already=TIMELINE|saved=0" % (MARKER, run))
                return report
            backup = _backup(now.strftime("%Y%m%d-%H%M"))
            record = {"schema_version": 1, "status": "prepared", "run": run, "decided_by": DECIDED_BY,
                      "backup": backup, "before_owners": before, "changed_guids": sorted(change),
                      "before_full_hash": state["full_hash"], "outside_hash": state["outside_hash"],
                      "cue_count": state["cue_count"], "targets": rows}
            _write_json(RECORD_PATH, record, exclusive=True)
            expected = {guid: TARGET_OWNER for guid in before}
            try:
                after = _mutate_and_save(show, change, {g: before[g] for g in change}, expected,
                                         state["outside_hash"], state["cue_count"], members, "APPLY")
            except Exception:
                record["status"] = "failed"
                _write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
                raise
            disk_hash = _sha256_file(backup["source"])
            require(disk_hash != backup["sha256"], "APPLY_DISK_UNCHANGED_AFTER_SAVE")
            record.update({"status": "saved_readback_verified", "after_full_hash": after["full_hash"],
                           "after_disk_sha256": disk_hash, "census_after": _dirty_census()})
            _write_json(RECORD_PATH, record)
            report.update({"ok": True, "mutated": True, "changed": sorted(change), "after": after,
                           "backup": backup, "record": RECORD_PATH, "census": record["census_after"],
                           "readback": "in_memory_after_save+disk_sha_changed"})
            _write_json(REPORT_PATH, report)
            unreal.log("%s_APPLY_OK|run=%s|changed=%d|owners=TIMELINE|show_saved=1|level_saved=0|readback=1|outside_hash=same|backup=%s" % (
                MARKER, run, len(change), backup["root"]))
            return report

        # REVERT
        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT")
        record = _read_json(RECORD_PATH)
        require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|status=" + str(record.get("status")))
        require(sorted(record["before_owners"]) == sorted(guids), "REVERT_TARGET_SET_DRIFT")
        current = read_owners(show, guids, members)
        require(current == {g: TARGET_OWNER for g in guids}, "REVERT_NOT_IN_APPLIED_STATE|owners=" + _canonical(current))
        require(state["full_hash"] == record["after_full_hash"],
                "REVERT_SHOW_CHANGED_SINCE_APPLY|expected=%s|actual=%s" % (record["after_full_hash"], state["full_hash"]))
        restore = {g: record["before_owners"][g] for g in record["changed_guids"]}
        backup = _backup(now.strftime("%Y%m%d-%H%M") + "-Revert")
        after = _mutate_and_save(show, restore, {g: TARGET_OWNER for g in restore}, dict(record["before_owners"]),
                                 record["outside_hash"], record["cue_count"], members, "REVERT")
        require(after["full_hash"] == record["before_full_hash"],
                "REVERT_NOT_EXACT|expected=%s|actual=%s" % (record["before_full_hash"], after["full_hash"]))
        archived = RECORD_PATH + ".reverted-" + run
        os.rename(RECORD_PATH, archived)
        report.update({"ok": True, "mutated": True, "restored": restore, "after": after,
                       "backup": backup, "record_archived": archived, "census": _dirty_census()})
        _write_json(REPORT_PATH, report)
        unreal.log("%s_REVERT_OK|run=%s|restored=%d|full_hash=pre_apply|show_saved=1|level_saved=0|readback=1" % (
            MARKER, run, len(restore)))
        return report
    except Exception as error:  # noqa: BLE001 - every stop leaves a report.
        report["error"] = "%s: %s" % (type(error).__name__, error)
        try:
            report["census"] = _dirty_census()
        except Exception:  # noqa: BLE001
            report["census"] = None
        _write_json(REPORT_PATH, report)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|%s" % (MARKER, run, mode, report["error"]))
        raise


def main(mode=None):
    selected = str(mode or globals().get("SCENE_CAMERA_OWNER_MODE", "DRY")).upper()
    require(selected in VALID_MODES, "MODE_INVALID|mode=" + selected)
    require(unreal is not None, "UNREAL_REQUIRED")
    return _run(selected)


if unreal is not None:
    main()
