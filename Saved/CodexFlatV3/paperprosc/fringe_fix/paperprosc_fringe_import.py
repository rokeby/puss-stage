"""Offline-written Unreal tool; do not run except through the guarded project Saved route.

Modes: DRY, IMPORT, REVERT. IMPORT creates three new textures and changes only
SkinColor on the six named Front/Flap MIs. REVERT restores the six MI parameters
but deliberately retains the now-unused new textures: this tool never performs
permanent deletion. Every mutation requires a clean dirty-package census, an
exact confirm string, a pre-change backup, named-package saves, and read-back.
"""
import datetime
import importlib.util
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
ARGS = os.path.join(HERE, "paperprosc_fringe_args.json")
MANIFEST = os.path.join(HERE, "fringe_fix_manifest.json")
RECORD = os.path.join(HERE, "paperprosc_fringe_record.json")
TEXTURE_PROPS = ("compression_settings", "srgb", "lod_group", "mip_gen_settings", "flip_green_channel",
                 "never_stream", "virtual_texture_streaming", "filter", "address_x", "address_y")


def load_core():
    path = os.path.join(HERE, "paperprosc_fringe_core.py")
    spec = importlib.util.spec_from_file_location("paperprosc_fringe_core_live", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True); handle.write("\n")


def package_path(obj):
    return str(obj.get_path_name()).split(".")[0] if obj is not None else None


def load(path, cls=None):
    obj = unreal.load_asset(path)
    if obj is None or (cls is not None and not isinstance(obj, cls)):
        raise RuntimeError("LOAD|" + path)
    return obj


def census():
    content = sorted(str(x.get_name()).split(".")[0] for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    maps = sorted(str(x.get_name()).split(".")[0] for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    return {"content": content, "maps": maps}


def content_file(package):
    return os.path.join(PROJECT, "Content", *package[6:].split("/")) + ".uasset"


def backup(run, packages, evidence):
    root = os.path.join(PROJECT, "Backups", "PrePaperProscFringe-" + run)
    if os.path.exists(root):
        raise RuntimeError("BACKUP_EXISTS|" + root)
    copied = []
    for package in packages:
        source = content_file(package)
        if os.path.isfile(source):
            target = os.path.join(root, "Content", *package[6:].split("/")) + ".uasset"
            os.makedirs(os.path.dirname(target), exist_ok=True); shutil.copy2(source, target); copied.append(target)
    for source in evidence:
        if os.path.isfile(source):
            target = os.path.join(root, "evidence", os.path.basename(source))
            os.makedirs(os.path.dirname(target), exist_ok=True); shutil.copy2(source, target); copied.append(target)
    write(os.path.join(root, "backup.json"), {"run": run, "packages": packages, "copied": copied})
    return root


def mi_state(plan):
    out = {}
    mel = unreal.MaterialEditingLibrary
    for mi, _expected in sorted(load_core().desired_mi_state(plan, True).items()):
        asset = load(mi, unreal.MaterialInstanceConstant)
        out[mi] = package_path(mel.get_material_instance_texture_parameter_value(asset, "SkinColor"))
    return out


def new_textures_present(plan):
    return sorted(row["new"] for row in plan["rows"] if unreal.EditorAssetLibrary.does_asset_exist(row["new"]))


def texture_readback(plan):
    out = {}
    for row in plan["rows"]:
        old = load(row["old"], unreal.Texture2D); new = load(row["new"], unreal.Texture2D)
        settings_equal = all(str(new.get_editor_property(p)) == str(old.get_editor_property(p)) for p in TEXTURE_PROPS)
        import_data = new.get_editor_property("asset_import_data")
        imported_from = str(import_data.get_first_filename()).replace("\\", "/") if import_data is not None else ""
        out[row["new"]] = {"settings_match_old": settings_equal, "imported_from": imported_from,
                           "source_matches": os.path.normcase(os.path.abspath(imported_from)) == os.path.normcase(os.path.abspath(row["png"]))}
    return out


def set_skin(plan, use_new):
    mel = unreal.MaterialEditingLibrary
    touched = []
    for row in plan["rows"]:
        texture = load(row["new"] if use_new else row["old"], unreal.Texture)
        for mi_path in row["mis"]:
            mi = load(mi_path, unreal.MaterialInstanceConstant)
            mi.modify()
            if not mel.set_material_instance_texture_parameter_value(mi, "SkinColor", texture):
                raise RuntimeError("SET_SKINCOLOR|" + mi_path)
            mel.update_material_instance(mi); touched.append(mi_path)
    return touched


def import_textures(plan):
    tasks = []
    for row in plan["rows"]:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", row["png"])
        task.set_editor_property("destination_path", row["new"].rsplit("/", 1)[0])
        task.set_editor_property("destination_name", row["new"].rsplit("/", 1)[1])
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("save", False)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    made = []
    for row, task in zip(plan["rows"], tasks):
        if not unreal.EditorAssetLibrary.does_asset_exist(row["new"]):
            raise RuntimeError("IMPORT_MISSING|%s|%s" % (row["owner"], list(task.imported_object_paths)))
        old = load(row["old"], unreal.Texture2D); new = load(row["new"], unreal.Texture2D); new.modify()
        for prop in TEXTURE_PROPS:
            new.set_editor_property(prop, old.get_editor_property(prop))
        new.post_edit_change(); made.append(row["new"])
    return made


def save_only(packages):
    for package in packages:
        if not unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False):
            raise RuntimeError("SAVE|" + package)


def main():
    core = load_core(); args = read(ARGS); manifest = read(MANIFEST)
    plan = core.build_plan(HERE, manifest)
    mode = str(args.get("mode") or "").upper()
    run = str(args.get("run_id") or "PPFRINGE-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    try:
        bad = core.validate_args(args, plan["digest8"])
        if bad: raise RuntimeError("ARGS|" + ",".join(bad))
        if census() != {"content": [], "maps": []}: raise RuntimeError("DIRTY_BEFORE|%s" % census())
        old_state = core.desired_mi_state(plan, False)
        current = mi_state(plan); present = new_textures_present(plan)
        if mode == "DRY":
            if present: raise RuntimeError("CREATE_ONLY_TARGETS_EXIST|%s" % present)
            if current != old_state: raise RuntimeError("SOURCE_MI_STATE|%s" % current)
            report = {"run_id": run, "mode": mode, "plan": plan, "dirty": census(), "mi_state": current,
                      "confirm_for_import": "IMPORT PAPERPROSC FRINGE " + plan["digest8"]}
            path = os.path.join(HERE, "paperprosc_fringe_dry_%s.json" % run); write(path, report)
            unreal.log("%s_DRY_OK|run=%s|digest=%s|textures=3|mis=6|report=%s" % (core.MARK, run, plan["digest8"], path)); return
        if mode == "IMPORT":
            dry = read(os.path.join(HERE, str(args.get("dry_report") or "")))
            if dry.get("plan", {}).get("digest") != plan["digest"]: raise RuntimeError("PLAN_CHANGED_SINCE_DRY")
            if present: raise RuntimeError("CREATE_ONLY_TARGETS_EXIST|%s" % present)
            if current != old_state: raise RuntimeError("SOURCE_MI_STATE|%s" % current)
            original_packages = sorted(old_state) + sorted(row["old"] for row in plan["rows"])
            backup_path = backup(run, original_packages, [ARGS, MANIFEST] + [row["png"] for row in plan["rows"]])
            record = {"run_id": run, "status": "STARTED", "digest": plan["digest"], "plan": plan,
                      "before_mi_state": current, "backup": backup_path}
            write(RECORD, record)
            made = import_textures(plan); touched = set_skin(plan, True); expected_dirty = sorted(made + touched)
            if census() != {"content": expected_dirty, "maps": []}: raise RuntimeError("DIRTY_SCOPE|%s|want=%s" % (census(), expected_dirty))
            save_only(expected_dirty)
            texture_state = texture_readback(plan)
            problems = core.state_problems(plan, new_textures_present(plan), mi_state(plan), True)
            if not all(x["settings_match_old"] and x["source_matches"] for x in texture_state.values()):
                problems.append("TEXTURE_READBACK")
            if problems or census() != {"content": [], "maps": []}: raise RuntimeError("READBACK|%s|%s" % (problems, census()))
            record.update(status="IMPORTED", saved=expected_dirty, readback_mi_state=mi_state(plan),
                          texture_readback=texture_state); write(RECORD, record)
            unreal.log("%s_IMPORT_OK|run=%s|digest=%s|saved=9|backup=%s" % (core.MARK, run, plan["digest8"], backup_path)); return
        record = read(RECORD)
        if record.get("status") != "IMPORTED" or record.get("digest") != plan["digest"]: raise RuntimeError("RECORD_STATE")
        if core.state_problems(plan, present, current, True): raise RuntimeError("CURRENT_STATE_DRIFTED")
        mi_packages = sorted(core.desired_mi_state(plan, True))
        backup_path = backup(run + "-REVERT", mi_packages + present, [ARGS, MANIFEST, RECORD])
        touched = sorted(set_skin(plan, False))
        if census() != {"content": touched, "maps": []}: raise RuntimeError("REVERT_DIRTY_SCOPE|%s" % census())
        save_only(touched)
        problems = core.state_problems(plan, present, mi_state(plan), False)
        if problems or census() != {"content": [], "maps": []}: raise RuntimeError("REVERT_READBACK|%s|%s" % (problems, census()))
        record.update(status="REVERTED_MI_ONLY", revert_run=run, revert_backup=backup_path,
                      retained_new_textures=present, readback_mi_state=mi_state(plan)); write(RECORD, record)
        unreal.log("%s_REVERT_OK|run=%s|digest=%s|saved=6|retained_new_textures=3|backup=%s" % (core.MARK, run, plan["digest8"], backup_path))
    except Exception as exc:
        unreal.log_error("%s_FAILED|run=%s|mode=%s|%s: %s" % (core.MARK, run, mode, type(exc).__name__, exc)); raise


if __name__ == "__main__" and unreal is not None:
    main()
