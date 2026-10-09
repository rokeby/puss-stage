"""Job 95: exact Passage->Scene camera census plus narrow DRY/APPLY/REVERT.

Run only through ExecuteProjectPythonFile with camera_seam_args.json. Offline work
created this tool; the conductor owns every live run.

APPLY changes exactly two kinds of saved values in the open authoring world:
  * CrossingSettleSeconds on the six AInfinityStageCameraRig actors;
  * the six tagged Scene Entry CineCameraActor views (transform/lens/focus),
    copied from each incoming Passage's evaluated, un-bobbed end pose.
It saves only L_InfinityStage_V1VerticalSlice. It does not touch the Show or any
Level Sequence. REVERT restores the exact recorded values and saves that map.

Markers: JOB95_DRY_OK, JOB95_APPLY_OK, JOB95_REVERT_OK, JOB95_FAILED.
"""

import datetime
import hashlib
import json
import math
import os
import shutil
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import camera_seam_core as core

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
ARGS_PATH = os.path.join(HERE, "camera_seam_args.json")
RECORDS_DIR = os.path.join(HERE, "records")


def fail(run, message):
    unreal.log_error("JOB95_FAILED|run=%s|%s" % (run, message))
    raise RuntimeError(message)


def asset_id(obj):
    return obj.get_path_name().split(".", 1)[0] if obj else None


def guid_text(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def quat(value):
    return [float(value.x), float(value.y), float(value.z), float(value.w)]


def rot(value):
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def dirty_census():
    return {
        "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def unwrap(result, count, what):
    if result is None:
        raise RuntimeError("%s returned None" % what)
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        if not result[0]:
            raise RuntimeError("%s returned false" % what)
        return result[1:]
    if isinstance(result, tuple) and len(result) == count:
        return result
    raise RuntimeError("%s returned unexpected value %r" % (what, result))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_file(package, extension):
    if not package.startswith("/Game/"):
        raise RuntimeError("not a project package: %s" % package)
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + extension)


def transform_record(actor):
    value = actor.get_actor_transform()
    component = actor.get_cine_camera_component()
    focus = component.get_editor_property("focus_settings")
    return {
        "location": vec(value.translation),
        "rotation": rot(value.rotation.rotator()),
        "quaternion": quat(value.rotation),
        "scale": vec(value.scale3d),
        "focal_mm": float(component.get_editor_property("current_focal_length")),
        "focus_cm": float(focus.get_editor_property("manual_focus_distance")),
    }


def set_camera(actor, state):
    actor.set_actor_transform(unreal.Transform(
        location=unreal.Vector(*state["location"]),
        rotation=unreal.Rotator(roll=state["rotation"][0], pitch=state["rotation"][1], yaw=state["rotation"][2]),
        scale=unreal.Vector(*state["scale"])))
    component = actor.get_cine_camera_component()
    component.set_editor_property("current_focal_length", float(state["focal_mm"]))
    focus = component.get_editor_property("focus_settings")
    focus.set_editor_property("manual_focus_distance", float(state["focus_cm"]))
    component.set_editor_property("focus_settings", focus)


def passage_end_state(library, show, passage_guid):
    start, end = unwrap(library.get_passage_frame_range(show, passage_guid), 2, "get_passage_frame_range")
    view, focal, focus = unwrap(library.get_passage_camera_pose(show, passage_guid, int(end)), 3, "get_passage_camera_pose")
    return int(start), int(end), {
        "location": vec(view.translation),
        "rotation": rot(view.rotation.rotator()),
        "quaternion": quat(view.rotation),
        "scale": vec(view.scale3d),
        "focal_mm": float(focal),
        "focus_cm": float(focus),
    }


def build_rows(world, show):
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    passages = {}
    for row in show.get_editor_property("passage_settings"):
        label = str(row.get_editor_property("label"))
        if label.startswith("Passage ") and label.split()[-1].isdigit():
            passages[int(label.split()[-1])] = row
    rigs = {}
    for actor in actors:
        if not isinstance(actor, unreal.InfinityStageCameraRig):
            continue
        passage_actor = actor.get_editor_property("passage_actor")
        if passage_actor is None:
            continue
        rigs.setdefault(guid_text(passage_actor.get_editor_property("passage_guid")), []).append(actor)
    entries = {}
    for actor in actors:
        if not isinstance(actor, unreal.CineCameraActor) or not actor.actor_has_tag("InfinityStage.SceneEntry"):
            continue
        label = str(actor.get_actor_label())
        for number in range(1, 7):
            if label.startswith("Scene %d " % number):
                entries.setdefault(number, []).append(actor)
    if sorted(passages) != list(range(1, 7)):
        raise RuntimeError("exact Passage settings census failed: %r" % sorted(passages))
    rows = []
    library = unreal.InfinityStageCameraPilotLibrary
    for number in range(1, 7):
        passage = passages[number]
        passage_guid = passage.get_editor_property("passage_guid")
        key = guid_text(passage_guid)
        if len(rigs.get(key, [])) != 1:
            raise RuntimeError("Passage %d rig count is %d" % (number, len(rigs.get(key, []))))
        if len(entries.get(number, [])) != 1:
            raise RuntimeError("Scene %d Entry camera count is %d" % (number, len(entries.get(number, []))))
        rig, entry = rigs[key][0], entries[number][0]
        start, end, passage_state = passage_end_state(library, show, passage_guid)
        entry_state = transform_record(entry)
        delta = core.seam_delta(passage_state, entry_state)
        rows.append({
            "number": number,
            "passage_label": "Passage %d" % number,
            "scene_label": "Scene %d" % number,
            "passage_guid": key,
            "start_frame": start,
            "end_frame": end,
            "rig_path": rig.get_path_name(),
            "rig_label": str(rig.get_actor_label()),
            "settle_seconds": float(rig.get_editor_property("crossing_settle_seconds")),
            "entry_path": entry.get_path_name(),
            "entry_label": str(entry.get_actor_label()),
            "passage_end": passage_state,
            "entry": entry_state,
            "delta": delta,
            "matched": core.seam_is_matched(delta),
        })
    return rows


def locate(path):
    value = unreal.find_object(None, path)
    if value is None:
        raise RuntimeError("could not resolve recorded object %s" % path)
    return value


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def replace_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def backup_level(run, prefix):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.join(project, "Backups", "%s-%s-%s" % (prefix, run, stamp))
    os.makedirs(directory, exist_ok=False)
    source = package_file(EXPECTED_WORLD, ".umap")
    target = os.path.join(directory, os.path.basename(source))
    shutil.copy2(source, target)
    if os.path.getsize(source) != os.path.getsize(target) or sha256(source) != sha256(target):
        raise RuntimeError("level backup verification failed")
    return {"directory": directory, "file": target, "sha256": sha256(target), "bytes": os.path.getsize(target)}


def save_and_verify(world, run, expected):
    census = dirty_census()
    if census["content"] or [name for name in census["maps"] if name != EXPECTED_WORLD]:
        fail(run, "unexpected dirty packages before targeted save: %r" % census)
    if EXPECTED_WORLD in census["maps"] and not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        fail(run, "targeted map save returned false")
    after = dirty_census()
    if after["content"] or after["maps"]:
        fail(run, "dirty packages remain after targeted save: %r" % after)
    rows = build_rows(world, SHOW)
    for row in rows:
        wanted = expected[str(row["number"])]
        if abs(row["settle_seconds"] - float(wanted["settle_seconds"])) > 1.0e-6:
            fail(run, "Passage %d settle read-back mismatch" % row["number"])
        if not core.seam_is_matched(core.seam_delta(wanted["entry"], row["entry"]), {
                "position_cm": 0.01, "rotation_deg": 0.001, "focal_mm": 0.001, "focus_cm": 0.01}):
            fail(run, "Scene %d Entry read-back mismatch" % row["number"])
    return rows, after


def main():
    args = json.load(open(ARGS_PATH, encoding="utf-8"))
    mode, run, settle_seconds = core.validate_args(args)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or asset_id(world) != EXPECTED_WORLD:
        fail(run, "wrong editor world %r" % asset_id(world))
    if editor.get_game_world() is not None:
        fail(run, "PIE/SIE is active")
    before_dirty = dirty_census()
    if before_dirty["content"] or before_dirty["maps"]:
        fail(run, "requires zero dirty packages: %r" % before_dirty)
    global SHOW
    SHOW = unreal.load_asset(SHOW_PATH)
    if SHOW is None:
        fail(run, "Show asset did not load")

    before = build_rows(world, SHOW)
    census = core.exact_census(before)
    os.makedirs(RECORDS_DIR, exist_ok=True)
    if mode == "DRY":
        path = os.path.join(RECORDS_DIR, "job95_%s_dry.json" % run)
        report = {"version": 1, "mode": mode, "run": run, "requested_settle_seconds": settle_seconds,
                  "dirty_before": before_dirty, "census": census, "seams": before,
                  "planned_save_packages": [EXPECTED_WORLD], "writes": 0}
        write_json(path, report)
        unreal.log("JOB95_DRY_OK|run=%s|census=%s|record=%s" % (run, json.dumps(census, sort_keys=True), path))
        return

    if mode == "APPLY":
        backup = backup_level(run, "PreJob95CameraSeam")
        record_path = os.path.join(RECORDS_DIR, "job95_%s_apply.json" % run)
        record = {"version": 1, "status": "PREPARED_BEFORE_MUTATION", "mode": mode, "run": run,
                  "requested_settle_seconds": settle_seconds, "dirty_before": before_dirty,
                  "census_before": census, "before": before, "backup": backup,
                  "save_packages": [EXPECTED_WORLD]}
        write_json(record_path, record)
        expected = {}
        for row in before:
            rig = locate(row["rig_path"])
            entry = locate(row["entry_path"])
            rig.modify()
            entry.modify()
            rig.set_editor_property("crossing_settle_seconds", settle_seconds)
            set_camera(entry, row["passage_end"])
            expected[str(row["number"])] = {"settle_seconds": settle_seconds, "entry": row["passage_end"]}
        after, dirty_after = save_and_verify(world, run, expected)
        record.update({"status": "APPLIED_AND_READ_BACK", "after": after, "dirty_after": dirty_after})
        replace_json(record_path, record)
        unreal.log("JOB95_APPLY_OK|run=%s|seams=6|settle_seconds=%.3f|saved=%s|record=%s|backup=%s" %
                   (run, settle_seconds, EXPECTED_WORLD, record_path, backup["directory"]))
        return

    source_path = str(args["record"])
    if not os.path.isabs(source_path):
        source_path = os.path.join(HERE, source_path)
    source = json.load(open(source_path, encoding="utf-8"))
    if source.get("status") != "APPLIED_AND_READ_BACK" or len(source.get("before", [])) != 6:
        fail(run, "record is not a complete Job 95 APPLY record")
    backup = backup_level(run, "PreJob95CameraSeamRevert")
    revert_path = os.path.join(RECORDS_DIR, "job95_%s_revert.json" % run)
    revert = {"version": 1, "status": "PREPARED_BEFORE_MUTATION", "mode": mode, "run": run,
              "source_record": source_path, "dirty_before": before_dirty, "before_revert": before,
              "backup": backup, "save_packages": [EXPECTED_WORLD]}
    write_json(revert_path, revert)
    expected = {}
    for row in source["before"]:
        rig = locate(row["rig_path"])
        entry = locate(row["entry_path"])
        rig.modify()
        entry.modify()
        rig.set_editor_property("crossing_settle_seconds", float(row["settle_seconds"]))
        set_camera(entry, row["entry"])
        expected[str(row["number"])] = {"settle_seconds": row["settle_seconds"], "entry": row["entry"]}
    after, dirty_after = save_and_verify(world, run, expected)
    revert.update({"status": "REVERTED_AND_READ_BACK", "after": after, "dirty_after": dirty_after})
    replace_json(revert_path, revert)
    unreal.log("JOB95_REVERT_OK|run=%s|seams=6|saved=%s|record=%s|backup=%s" %
               (run, EXPECTED_WORLD, revert_path, backup["directory"]))


try:
    main()
except Exception as exc:
    if "JOB95_FAILED|" not in str(exc):
        unreal.log_error("JOB95_FAILED|%r" % (exc,))
    raise
