"""DRY/APPLY/REVERT the P06 camera light's fixture-body suppression.

Run through ExecuteProjectPythonFile.  The default is DRY.  APPLY sets the
Show-authoritative attachment flag, rebuilds only P06 fixture ISMs, then saves
only the Show and current level.  The automatic editor rebuild added by job 180
does not save; this one-time authoring tool deliberately does.
"""

import datetime
import hashlib
import json
import os
import shutil

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PASSAGE_PREFIX = "Passage 06"
TARGET_LABEL = "P06 EVT B02 BLACK F00 CAMERA"
APPLY_CONFIRM = "APPLY_JOB180_P06_FIXTURE_SUPPRESSION"
REVERT_PREFIX = "REVERT_JOB180_P06_FIXTURE_SUPPRESSION:"


class Job180Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Job180Refused(message)


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _package_name(package):
    text = str(package)
    return text.split("'")[1].split(".")[0] if "'" in text else text


def dirty_census():
    saving = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(_package_name(item) for item in saving.get_dirty_content_packages()),
        "maps": sorted(_package_name(item) for item in saving.get_dirty_map_packages()),
    }


def find_target(show):
    hits = []
    cues = list(show.get_editor_property("cues"))
    for cue_index, cue in enumerate(cues):
        pair = cue.get_editor_property("wing_pair")
        for attachment_index, attachment in enumerate(pair.get_editor_property("attachments")):
            if str(attachment.get_editor_property("label")) == TARGET_LABEL:
                hits.append((cue_index, attachment_index, cue, attachment))
    require(len(hits) == 1, "TARGET_COUNT|got=%d|label=%s" % (len(hits), TARGET_LABEL))
    cue_index, attachment_index, cue, attachment = hits[0]
    require("LIGHT" in str(attachment.get_editor_property("kind")).upper(), "TARGET_NOT_LIGHT")
    require(bool(attachment.get_editor_property("enabled")), "TARGET_DISABLED")
    require("STATION" in str(attachment.get_editor_property("anchor")).upper(), "TARGET_NOT_STATION_ANCHORED")
    return {
        "cue_index": cue_index,
        "attachment_index": attachment_index,
        "cue_label": str(cue.get_editor_property("label")),
        "attachment_guid": _guid(attachment.get_editor_property("attachment_guid")),
        "suppressed": bool(attachment.get_editor_property("suppress_fixture_body")),
    }


def set_target_suppressed(show, target, desired):
    """Assign every enclosing value struct back to the Show asset."""
    cues = list(show.get_editor_property("cues"))
    cue = cues[target["cue_index"]]
    pair = cue.get_editor_property("wing_pair")
    attachments = list(pair.get_editor_property("attachments"))
    attachment = attachments[target["attachment_index"]]
    require(_guid(attachment.get_editor_property("attachment_guid")) == target["attachment_guid"],
            "TARGET_GUID_MOVED")
    attachment.set_editor_property("suppress_fixture_body", bool(desired))
    attachments[target["attachment_index"]] = attachment
    pair.set_editor_property("attachments", attachments)
    cue.set_editor_property("wing_pair", pair)
    cues[target["cue_index"]] = cue
    show.set_editor_property("cues", cues)


def _content_file(package_path, suffix):
    relative = package_path.removeprefix("/Game/").replace("/", os.sep) + suffix
    return os.path.normpath(os.path.join(unreal.Paths.project_content_dir(), relative))


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_exclusive(path, payload):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def find_context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "NO_EDITOR_WORLD")
    require(world.get_path_name().split(".", 1)[0] == WORLD_PATH,
            "WRONG_WORLD|got=%s" % world.get_path_name())
    require(editor.get_game_world() is None, "PIE_ACTIVE")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    passages = [
        actor for actor in actors
        if isinstance(actor, unreal.InfinityStagePassageActor)
        and actor.get_actor_label().startswith(PASSAGE_PREFIX)
    ]
    require(len(passages) == 1, "PASSAGE_COUNT|got=%d" % len(passages))
    structures = [
        actor for actor in actors
        if isinstance(actor, unreal.InfinityStageStructureActor)
        and actor.get_editor_property("passage") == passages[0]
    ]
    require(len(structures) >= 1, "STRUCTURE_COUNT|got=0")
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    require(show is not None, "SHOW_MISSING")
    return {
        "editor": editor,
        "world": world,
        "passage": passages[0],
        "structures": structures,
        "show": show,
    }


def snapshot(context):
    target = find_target(context["show"])
    return {
        "target": target,
        "passage": context["passage"].get_actor_label(),
        "structures": [
            {
                "label": structure.get_actor_label(),
                "fixture_bodies": int(structure.get_editor_property("fixture_body_count")),
                "hanging_lines": int(structure.get_editor_property("hanging_line_count")),
                "fixtures_enabled": bool(
                    structure.get_editor_property("fixtures").get_editor_property("enabled")
                ),
                "current": bool(structure.is_structure_current()),
            }
            for structure in context["structures"]
        ],
        "dirty": dirty_census(),
    }


def _backup_before_change(run_id, mode, before, source_record):
    project_dir = os.path.normpath(unreal.Paths.project_dir())
    stem = "PreJob180FixtureSuppress" if mode == "APPLY" else "PreJob180FixtureSuppressRevert"
    backup_dir = os.path.join(project_dir, "Backups", "%s-%s" % (stem, run_id))
    os.makedirs(backup_dir, exist_ok=False)
    show_file = _content_file(SHOW_PATH, ".uasset")
    map_file = _content_file(WORLD_PATH, ".umap")
    require(os.path.isfile(show_file), "SHOW_FILE_MISSING|%s" % show_file)
    require(os.path.isfile(map_file), "MAP_FILE_MISSING|%s" % map_file)
    shutil.copy2(show_file, os.path.join(backup_dir, os.path.basename(show_file)))
    shutil.copy2(map_file, os.path.join(backup_dir, os.path.basename(map_file)))
    record = {
        "schema": 1,
        "job": 180,
        "run_id": run_id,
        "mode": mode,
        "show": SHOW_PATH,
        "world": WORLD_PATH,
        "target_label": TARGET_LABEL,
        "target_guid": before["target"]["attachment_guid"],
        "before_suppressed": before["target"]["suppressed"],
        "before": before,
        "source_record": source_record or "",
        "files": {
            "show": {"path": show_file, "sha256": _sha256(show_file)},
            "map": {"path": map_file, "sha256": _sha256(map_file)},
        },
    }
    record_path = os.path.join(backup_dir, "prechange.json")
    _write_json_exclusive(record_path, record)
    # Read it before the first UObject write; a named but unreadable record is no safety net.
    with open(record_path, "r", encoding="utf-8") as handle:
        require(json.load(handle)["target_guid"] == record["target_guid"], "BACKUP_RECORD_READBACK_FAILED")
    return backup_dir, record_path


def _desired_for_mode(mode, confirm, source_record):
    if mode == "APPLY":
        require(confirm == APPLY_CONFIRM, "CONFIRM_REQUIRED|%s" % APPLY_CONFIRM)
        return True, None
    require(mode == "REVERT", "MODE_REQUIRED|DRY|APPLY|REVERT")
    require(bool(source_record), "SOURCE_RECORD_REQUIRED")
    path = source_record
    if not os.path.isabs(path):
        path = os.path.join(unreal.Paths.project_dir(), path)
    with open(path, "r", encoding="utf-8") as handle:
        source = json.load(handle)
    require(source.get("job") == 180 and source.get("mode") == "APPLY", "BAD_SOURCE_RECORD")
    expected = REVERT_PREFIX + source["run_id"]
    require(confirm == expected, "CONFIRM_REQUIRED|%s" % expected)
    return bool(source["before_suppressed"]), os.path.normpath(path)


def main(mode=None, confirm=None, run_id=None, source_record=None):
    selected_mode = str(mode or globals().get("JOB180_MODE", "DRY")).upper()
    selected_confirm = str(confirm if confirm is not None else globals().get("JOB180_CONFIRM", ""))
    selected_source = source_record if source_record is not None else globals().get("JOB180_SOURCE_RECORD", "")
    selected_run = str(run_id or globals().get("JOB180_RUN_ID", "") or
                       datetime.datetime.now().strftime("J180-%Y%m%d-%H%M%S"))
    require(selected_mode in ("DRY", "APPLY", "REVERT"), "MODE_REQUIRED|DRY|APPLY|REVERT")

    context = find_context()
    before = snapshot(context)
    unreal.log(
        "JOB180_FIXTURE_SUPPRESSION_CENSUS|run=%s|phase=before|content=%s|maps=%s"
        % (selected_run, json.dumps(before["dirty"]["content"]), json.dumps(before["dirty"]["maps"]))
    )
    if selected_mode == "DRY":
        unreal.log(
            "JOB180_FIXTURE_SUPPRESSION_DRY_OK|run=%s|passage=%s|target=%s|guid=%s|suppressed=%d|structures=%d|writes=0"
            % (selected_run, before["passage"], TARGET_LABEL, before["target"]["attachment_guid"],
               int(before["target"]["suppressed"]), len(before["structures"]))
        )
        return before

    require(before["dirty"] == {"content": [], "maps": []},
            "DIRTY_PACKAGES_REFUSING|%s" % json.dumps(before["dirty"], sort_keys=True))
    require(all(row["current"] for row in before["structures"]), "STRUCTURE_NOT_CURRENT_BEFORE_APPLY")
    require(all(row["fixtures_enabled"] for row in before["structures"]), "FIXTURES_DISABLED")
    desired, resolved_source = _desired_for_mode(
        selected_mode, selected_confirm, selected_source)
    require(before["target"]["suppressed"] is not desired,
            "PRESTATE_ALREADY_DESIRED|suppressed=%d" % int(desired))
    backup_dir, record_path = _backup_before_change(
        selected_run, selected_mode, before, resolved_source)

    set_target_suppressed(context["show"], before["target"], desired)
    rebuilt = 0
    for structure in context["structures"]:
        require(structure.rebuild_fixtures_only(),
                "FIXTURE_REBUILD_FAILED|%s" % structure.get_actor_label())
        rebuilt += 1
    after_rebuild = snapshot(context)
    require(after_rebuild["target"]["attachment_guid"] == before["target"]["attachment_guid"], "GUID_CHANGED")
    require(after_rebuild["target"]["suppressed"] is desired, "SUPPRESSION_READBACK_FAILED")
    before_bodies = sum(row["fixture_bodies"] for row in before["structures"])
    after_bodies = sum(row["fixture_bodies"] for row in after_rebuild["structures"])
    expected_delta = -len(context["structures"]) if desired else len(context["structures"])
    require(after_bodies - before_bodies == expected_delta,
            "BODY_COUNT_DELTA|got=%d|want=%d" % (after_bodies - before_bodies, expected_delta))
    require(all(row["current"] for row in after_rebuild["structures"]), "STRUCTURE_NOT_CURRENT_AFTER_REBUILD")

    # Save only after the in-memory read-back has passed every semantic gate.
    require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), "SHOW_SAVE_FAILED")
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
    after = snapshot(context)
    require(after["target"]["attachment_guid"] == before["target"]["attachment_guid"], "GUID_CHANGED_AFTER_SAVE")
    require(after["target"]["suppressed"] is desired, "SUPPRESSION_SAVE_READBACK_FAILED")
    require(sum(row["fixture_bodies"] for row in after["structures"]) == after_bodies,
            "BODY_COUNT_CHANGED_DURING_SAVE")
    require(after["dirty"] == {"content": [], "maps": []},
            "DIRTY_AFTER_SAVE|%s" % json.dumps(after["dirty"], sort_keys=True))
    unreal.log(
        "JOB180_FIXTURE_SUPPRESSION_CENSUS|run=%s|phase=after|content=%s|maps=%s"
        % (selected_run, json.dumps(after["dirty"]["content"]), json.dumps(after["dirty"]["maps"]))
    )

    result = {
        "schema": 1,
        "job": 180,
        "mode": selected_mode,
        "run_id": selected_run,
        "backup_dir": backup_dir,
        "prechange_record": record_path,
        "before": before,
        "after": after,
        "rebuilt_structures": rebuilt,
    }
    result_path = os.path.join(backup_dir, "result.json")
    _write_json_exclusive(result_path, result)
    marker = "JOB180_FIXTURE_SUPPRESSION_%s_OK" % selected_mode
    unreal.log(
        "%s|run=%s|passage=%s|guid=%s|suppressed=%d|bodies=%d|backup=%s"
        % (marker, selected_run, after["passage"], after["target"]["attachment_guid"],
           int(desired), after_bodies, backup_dir)
    )
    return result


if __name__ == "__main__":
    main()
