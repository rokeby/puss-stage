"""Live-ready DRY/APPLY/REVERT tool for Job 195; never executes on import."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import job195_core as core


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORDS = os.path.join(HERE, "records")
MARK = "JOB195_ROOM_TONE"


class Stop(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise Stop(str(reason))


def asset_path(obj):
    return obj.get_path_name().split(".", 1)[0] if obj else None


def census():
    return {
        "content": sorted(package.get_name() for package in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(package.get_name() for package in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def write_new(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def read_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_file(package):
    require(package.startswith("/Game/"), "PACKAGE_OUTSIDE_GAME|" + package)
    relative = package[len("/Game/"):].replace("/", os.sep)
    extension = ".umap" if package == WORLD else ".uasset"
    return os.path.normpath(os.path.join(unreal.Paths.project_content_dir(), relative + extension))


def backup_level(run):
    source = package_file(WORLD)
    require(os.path.isfile(source), "LEVEL_FILE_MISSING|" + source)
    project = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    root = os.path.join(project, "Backups", "PreJob195RoomTone-" + run)
    os.makedirs(root, exist_ok=False)
    target = os.path.join(root, "L_InfinityStage_V1VerticalSlice.umap")
    shutil.copy2(source, target)
    require(sha256(source) == sha256(target), "BACKUP_HASH_MISMATCH")
    return {"root": root, "file": target, "sha256": sha256(target)}


def live_context(args):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(world is not None and asset_path(world) == WORLD,
            "WRONG_WORLD|%s" % asset_path(world))
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    require(len(roots) == 1, "SHOW_ROOT_COUNT|%d" % len(roots))
    root = roots[0]
    try:
        sound = root.get_editor_property("room_tone_sound")
        mpc = root.get_editor_property("room_tone_warp_parameters")
        parameter = str(root.get_editor_property("room_tone_warp_parameter"))
    except Exception as exc:
        raise Stop("CPP_PATCH_NOT_BUILT|%s" % exc)
    target = unreal.load_asset(args["asset_path"])
    warp = unreal.load_asset(args["mpc_path"])
    return world, root, {
        "room_tone_sound": asset_path(sound),
        "room_tone_warp_parameters": asset_path(mpc),
        "room_tone_warp_parameter": parameter,
        "target_exists": target is not None,
        "mpc_exists": warp is not None,
    }, warp


def import_sound(args, source):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source["path"])
    task.set_editor_property("destination_path", args["destination_path"])
    task.set_editor_property("destination_name", args["asset_name"])
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    sound = unreal.load_asset(args["asset_path"])
    require(sound is not None and sound.get_class().get_name() == "SoundWave", "IMPORT_NOT_SOUNDWAVE")
    sound.set_editor_property("looping", True)
    require(bool(sound.get_editor_property("looping")), "LOOPING_READBACK_FALSE")
    return sound


def save_named(paths):
    results = {path: bool(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)) for path in paths}
    require(all(results.values()), "SAVE_FAILED|%r" % results)
    return results


def run_dry(args, source):
    before_dirty = census()
    require(before_dirty == {"content": [], "maps": []}, "DIRTY_AT_START|%r" % before_dirty)
    if source["status"] != "READY":
        unreal.log_error("%s_DRY_REFUSED|run=%s|source=%s|path=%s|mutated=0|dirty=0+0" %
                         (MARK, args["run"], source["status"], source["path"]))
        return
    _world, _root, state, _warp = live_context(args)
    refusals = []
    if state["target_exists"]:
        refusals.append("TARGET_EXISTS")
    if args["enable_s6_dip"] and not state["mpc_exists"]:
        refusals.append("MPC_MISSING")
    unreal.log("%s_DRY_%s|run=%s|wav=%s|duration_s=%.3f|target=%s|mpc=%s|refusals=%s|mutated=0|dirty=0+0" %
               (MARK, "REFUSED" if refusals else "OK", args["run"], source["path"],
                source["duration_s"], args["asset_path"], args["mpc_path"],
                ",".join(refusals) or "none"))


def run_apply(args, source):
    require(source["status"] == "READY", "SOURCE_%s|%s" % (source["status"], source["path"]))
    require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|%r" % census())
    world, root, before, warp = live_context(args)
    require(not before["target_exists"], "TARGET_EXISTS_REFUSE_OVERWRITE|" + args["asset_path"])
    require(not args["enable_s6_dip"] or warp is not None, "MPC_MISSING|" + args["mpc_path"])
    backup = backup_level(args["run"])
    record_path = os.path.join(RECORDS, "job195_%s_ACTIVE.json" % args["run"])
    record = {
        "schema": 1, "status": "prepared", "run": args["run"],
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": source, "args": args, "before": before, "backup": backup,
        "dirty_before": census(),
    }
    write_new(record_path, record)
    sound = import_sound(args, source)
    root.modify()
    root.set_editor_property("room_tone_sound", sound)
    root.set_editor_property("room_tone_warp_parameters", warp if args["enable_s6_dip"] else None)
    root.set_editor_property("room_tone_warp_parameter", "Weird")
    saves = save_named([args["asset_path"], WORLD])
    after = {
        "room_tone_sound": asset_path(root.get_editor_property("room_tone_sound")),
        "room_tone_warp_parameters": asset_path(root.get_editor_property("room_tone_warp_parameters")),
        "room_tone_warp_parameter": str(root.get_editor_property("room_tone_warp_parameter")),
        "looping": bool(sound.get_editor_property("looping")),
        "duration_s": float(sound.get_editor_property("duration")),
    }
    require(after["room_tone_sound"] == args["asset_path"], "ROOT_SOUND_READBACK")
    require(after["looping"], "SOUND_LOOP_READBACK")
    require(after["room_tone_warp_parameter"] == "Weird", "WEIRD_PARAMETER_READBACK")
    require(census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|%r" % census())
    record.update({"status": "applied", "after": after, "saves": saves})
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    unreal.log("%s_APPLY_OK|run=%s|sound=%s|looping=1|owner=ShowRoot|mpc=%s|parameter=Weird|saved=%s,%s|readback=1|dirty=0+0|record=%s" %
               (MARK, args["run"], args["asset_path"], args["mpc_path"] if warp else "none",
                args["asset_path"], WORLD, record_path))


def run_revert(args):
    record_path = os.path.normpath(args["record"])
    require(os.path.isfile(record_path), "RECORD_MISSING|" + record_path)
    record = read_json(record_path)
    require(record.get("status") == "applied", "RECORD_NOT_APPLIED")
    require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|%r" % census())
    world, root, _current, _warp = live_context(record["args"])
    revert_backup = backup_level(args["run"])
    before = record["before"]
    prior_sound = unreal.load_asset(before["room_tone_sound"]) if before["room_tone_sound"] else None
    prior_mpc = unreal.load_asset(before["room_tone_warp_parameters"]) if before["room_tone_warp_parameters"] else None
    root.modify()
    root.set_editor_property("room_tone_sound", prior_sound)
    root.set_editor_property("room_tone_warp_parameters", prior_mpc)
    root.set_editor_property("room_tone_warp_parameter", before["room_tone_warp_parameter"])
    save_named([WORLD])
    require(asset_path(root.get_editor_property("room_tone_sound")) == before["room_tone_sound"],
            "REVERT_SOUND_READBACK")
    require(census() == {"content": [], "maps": []}, "DIRTY_AFTER_REVERT|%r" % census())
    record.update({"status": "reverted", "revert_run": args["run"],
                   "revert_backup": revert_backup,
                   "imported_asset_retained": record["args"]["asset_path"]})
    archive = record_path.replace("_ACTIVE.json", "_REVERTED_%s.json" % args["run"])
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    os.replace(record_path, archive)
    unreal.log("%s_REVERT_OK|run=%s|level_restored=1|imported_asset_retained=%s|saved=%s|readback=1|dirty=0+0|record=%s" %
               (MARK, args["run"], record["args"]["asset_path"], WORLD, archive))


def main(raw):
    run = str(raw.get("run", "J195-INVALID")) if isinstance(raw, dict) else "J195-INVALID"
    try:
        args = core.validate_args(raw)
        project = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
        source = core.resolve_source(project, args["source_wav"]) if args["mode"] != "REVERT" else None
        if args["mode"] == "DRY":
            run_dry(args, source)
        elif args["mode"] == "APPLY":
            run_apply(args, source)
        else:
            run_revert(args)
    except (core.PlanError, Stop) as exc:
        unreal.log_error("%s_REFUSED|run=%s|reason=%s|mutated=0_or_recorded_for_revert" % (MARK, run, exc))

