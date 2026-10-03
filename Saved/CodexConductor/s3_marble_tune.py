"""DRY/APPLY/REVERT material-only tuning for the two S3 marble liners.

The tool always duplicates the currently assigned MaterialInstanceConstant and
edits only that S3-owned copy.  Shared masters and source instances are never
changed.  REVERT restores the two source assignments and retains the copy MI;
no content asset is permanently deleted.

PIE luminance is deliberately a later acceptance gate.  This offline-authored
tool records that before/after wall-still measurements remain required; it does
not claim rendered acceptance from material parameter read-back.
"""
import datetime
import json
import math
import os
import shutil
import traceback

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LINER_LABELS = ("S3 Marble Inner Wall Left", "S3 Marble Inner Wall Right")
COPY_MI_PATH = "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Heavy_Daylight"
RECORD_NAME = "s3_marble_tune_record.json"
TARGET_PARAMETERS = {"Brightness": 0.70, "Min Roughness": 0.28, "Max Roughness": 0.38}
REQUIRED_TEXTURE_TOKENS = ("basecolor", "normal", "roughness")
REQUIRED_TESTS = ("InfinityStage.Editor.SavedMasterMatchesShow",
                  "InfinityStage.Editor.SceneCutBindingsResolve")


class PlanError(ValueError):
    pass


def project_file(*parts):
    if unreal is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    else:
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, *parts))


def record_path():
    return project_file("Saved", "CodexConductor", RECORD_NAME)


def normalize_asset_path(value):
    if value is None:
        return None
    path = str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)
    return path.split(".", 1)[0]


def plan_marble_tune(state):
    liners = list(state.get("liners", []))
    if len(liners) != 2 or {row.get("label") for row in liners} != set(LINER_LABELS):
        raise PlanError("expected exactly the two S3 marble liners")
    sources = {row.get("material_path") for row in liners}
    if len(sources) != 1 or None in sources:
        raise PlanError("liners do not share one readable source MI")
    source = next(iter(sources))
    if source == COPY_MI_PATH:
        raise PlanError("marble copy MI is already assigned")
    if state.get("target_exists"):
        raise PlanError("S3 marble copy MI path already exists")
    profile = dict(state.get("profile", {}))
    if not profile.get("is_material_instance"):
        raise PlanError("source is not a MaterialInstanceConstant")
    scalar_map = {str(name).casefold(): str(name) for name in profile.get("scalar_names", [])}
    selected = {}
    for wanted, value in TARGET_PARAMETERS.items():
        actual = scalar_map.get(wanted.casefold())
        if actual is None:
            raise PlanError("copy MI cannot expose required parameter: " + wanted)
        selected[actual] = value
    if selected.get(scalar_map["min roughness"]) < 0.25 or selected.get(scalar_map["max roughness"]) > 0.40:
        raise PlanError("roughness targets leave the requested 0.25-0.40 range")
    if selected[scalar_map["min roughness"]] > selected[scalar_map["max roughness"]]:
        raise PlanError("roughness minimum exceeds maximum")
    texture_names = [str(name).casefold().replace(" ", "") for name in profile.get("texture_names", [])]
    missing = [token for token in REQUIRED_TEXTURE_TOKENS
               if not any(token in name or (token == "roughness" and "metallicroughness" in name)
                          for name in texture_names)]
    if missing:
        raise PlanError("source MI lacks veining/normal/roughness textures: " + ",".join(missing))
    return {"source": source, "target": COPY_MI_PATH, "copy_mi_only": True,
            "parameters": selected, "liners": [row["label"] for row in liners],
            "shared_master_mutated": False, "pie_luminance": {
                "status": "REQUIRED_AFTER_APPLY", "before_wall_still": None,
                "after_wall_still": None, "brightest_pixel_must_be_below_clipping": True},
            "required_tests": list(REQUIRED_TESTS)}


def luminance_summary(rgb_pixels):
    values = []
    for pixel in rgb_pixels:
        if len(pixel) < 3:
            raise PlanError("luminance pixel has fewer than three channels")
        values.append(0.2126 * float(pixel[0]) + 0.7152 * float(pixel[1]) + 0.0722 * float(pixel[2]))
    if not values or any(not math.isfinite(value) or value < 0.0 for value in values):
        raise PlanError("invalid luminance sample")
    ordered = sorted(values)
    index = int(round(0.95 * (len(ordered) - 1)))
    return {"mean": sum(values) / len(values), "p95": ordered[index], "max": ordered[-1],
            "sample_count": len(values)}


def validate_luminance_pair(before, after, clip_level=1.0):
    if before["sample_count"] != after["sample_count"] or before["sample_count"] <= 0:
        raise PlanError("before/after luminance samples do not match")
    if after["max"] >= float(clip_level):
        raise PlanError("after wall still still clips")
    if after["p95"] >= before["p95"]:
        raise PlanError("after wall p95 was not reduced")
    return {"before": before, "after": after, "clip_level": float(clip_level),
            "p95_reduction": before["p95"] - after["p95"]}


def _package_census():
    names = lambda rows: sorted(str(value.get_path_name()).split(".", 1)[0] for value in rows)
    return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def _actor_index():
    result = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def _one(index, label):
    rows = index.get(label, [])
    if len(rows) != 1:
        raise PlanError("expected exactly one actor labelled %s, found %d" % (label, len(rows)))
    return rows[0]


def _component(actor):
    rows = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    if len(rows) != 1 or len(rows[0].get_materials()) != 1:
        raise PlanError(actor.get_actor_label() + " must have one mesh component and one material")
    return rows[0]


def _profile(material):
    library = unreal.MaterialEditingLibrary
    return {"is_material_instance": isinstance(material, unreal.MaterialInstanceConstant),
            "scalar_names": [str(value) for value in library.get_scalar_parameter_names(material)],
            "vector_names": [str(value) for value in library.get_vector_parameter_names(material)],
            "texture_names": [str(value) for value in library.get_texture_parameter_names(material)]}


def _live_state():
    index = _actor_index()
    liners, material = [], None
    for label in LINER_LABELS:
        component = _component(_one(index, label))
        current = component.get_material(0)
        liners.append({"label": label, "actor_path": str(_one(index, label).get_path_name()),
                       "material_path": normalize_asset_path(current)})
        material = current if material is None else material
    if len({row["material_path"] for row in liners}) != 1:
        raise PlanError("liners have different live materials")
    state = {"liners": liners, "profile": _profile(material),
             "target_exists": unreal.EditorAssetLibrary.does_asset_exist(COPY_MI_PATH)}
    return state, index, material


def _assert_context(apply, revert):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if (world.get_outermost().get_name() if world else None) != EXPECTED_WORLD:
        raise PlanError("WRONG_WORLD")
    if editor.get_game_world() is not None:
        raise PlanError("PIE_OR_SIE_ACTIVE")
    census = _package_census()
    if census["maps"] or census["content"]:
        raise PlanError("DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if apply and os.path.exists(record_path()):
        raise PlanError("APPLY_RECORD_ALREADY_EXISTS")
    if revert and not os.path.isfile(record_path()):
        raise PlanError("REVERT_RECORD_ABSENT")


def _backup(prefix):
    source = project_file("Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap"
    if not os.path.isfile(source):
        raise PlanError("LEVEL_BACKUP_SOURCE_MISSING")
    folder = project_file("Backups", prefix + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    if os.path.exists(folder):
        raise PlanError("BACKUP_EXISTS|path=" + folder)
    relative = os.path.relpath(source, project_file("Content"))
    destination = os.path.join(folder, "Content", relative)
    os.makedirs(os.path.dirname(destination))
    shutil.copy2(source, destination)
    return folder


def _write_record(value, exclusive=False):
    with open(record_path(), "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _save_level():
    census = _package_census()
    if census["content"] or census["maps"] != [EXPECTED_WORLD]:
        raise PlanError("DIRTY_SCOPE|census=" + json.dumps(census, sort_keys=True))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise PlanError("LEVEL_SAVE_FAILED")
    after = _package_census()
    if after["maps"] or after["content"]:
        raise PlanError("POST_SAVE_DIRTY|census=" + json.dumps(after, sort_keys=True))
    return after


def _apply(run, plan, index, source):
    backup = _backup("PreS3MarbleTune-")
    record = {"world": EXPECTED_WORLD, "run": run, "backup": backup, "plan": plan,
              "assignments": [], "parameter_before": {}, "parameter_after": {},
              "applied": False}
    _write_record(record, exclusive=True)
    copied = unreal.EditorAssetLibrary.duplicate_asset(plan["source"], plan["target"])
    if copied is None or not isinstance(copied, unreal.MaterialInstanceConstant):
        raise PlanError("COPY_MI_FAILED")
    library = unreal.MaterialEditingLibrary
    for name, value in plan["parameters"].items():
        record["parameter_before"][name] = float(library.get_material_instance_scalar_parameter_value(copied, name))
        if not library.set_material_instance_scalar_parameter_value(copied, name, float(value)):
            raise PlanError("PARAMETER_SET_FAILED|name=" + name)
        actual = float(library.get_material_instance_scalar_parameter_value(copied, name))
        if abs(actual - float(value)) > 1.0e-4:
            raise PlanError("PARAMETER_READBACK_MISMATCH|name=" + name)
        record["parameter_after"][name] = actual
    for label in LINER_LABELS:
        actor = _one(index, label)
        component = _component(actor)
        record["assignments"].append({"label": label, "actor_path": str(actor.get_path_name()),
                                      "before": normalize_asset_path(component.get_material(0)),
                                      "after": plan["target"]})
        component.modify(); component.set_material(0, copied)
        if normalize_asset_path(component.get_material(0)) != plan["target"]:
            raise PlanError("LINER_ASSIGNMENT_READBACK|label=" + label)
    if normalize_asset_path(source) != plan["source"]:
        raise PlanError("SOURCE_MI_CHANGED")
    if not unreal.EditorAssetLibrary.save_asset(plan["target"], only_if_is_dirty=False):
        raise PlanError("COPY_MI_SAVE_FAILED")
    census = _package_census()
    if census["content"] or census["maps"] != [EXPECTED_WORLD]:
        raise PlanError("POST_MI_SAVE_DIRTY_SCOPE|census=" + json.dumps(census, sort_keys=True))
    record["post_save_census"] = _save_level()
    record["applied"] = True
    _write_record(record)
    unreal.log("S3_MARBLE_TUNE_DONE|run=%s|applied|copy_mi=%s|roughness=0.28..0.38|brightness=0.70|backup=%s|pie_luminance=REQUIRED|tests_required_singly=%s" %
               (run, plan["target"], backup, ",".join(REQUIRED_TESTS)))


def _revert(run):
    with open(record_path(), encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        raise PlanError("REVERT_RECORD_INVALID")
    index = _actor_index()
    target = unreal.load_asset(record["plan"]["target"])
    source = unreal.load_asset(record["plan"]["source"])
    if target is None or source is None:
        raise PlanError("REVERT_MATERIAL_MISSING")
    for row in record["assignments"]:
        actor = _one(index, row["label"])
        component = _component(actor)
        if (str(actor.get_path_name()) != row["actor_path"] or
                normalize_asset_path(component.get_material(0)) != row["after"]):
            raise PlanError("REVERT_OWNERSHIP_MISMATCH|label=" + row["label"])
    backup = _backup("PreS3MarbleTuneRevert-")
    for row in record["assignments"]:
        component = _component(_one(index, row["label"]))
        component.modify(); component.set_material(0, source)
        if normalize_asset_path(component.get_material(0)) != row["before"]:
            raise PlanError("REVERT_ASSIGNMENT_READBACK|label=" + row["label"])
    census = _save_level()
    archived = record_path() + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(record_path(), archived)
    unreal.log("S3_MARBLE_TUNE_DONE|run=%s|reverted|retained_copy_mi=%s|backup=%s|record=%s|census=%s" %
               (run, record["plan"]["target"], backup, os.path.basename(archived),
                json.dumps(census, sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_MARBLE_TUNE_APPLY"))
    revert = bool(globals().get("S3_MARBLE_TUNE_REVERT"))
    try:
        if apply and revert:
            raise PlanError("APPLY_AND_REVERT_BOTH_SET")
        _assert_context(apply, revert)
        if revert:
            _revert(run)
            return
        state, index, source = _live_state()
        plan = plan_marble_tune(state)
        unreal.log("S3_MARBLE_TUNE_PLAN|run=%s|%s" %
                   (run, json.dumps(plan, separators=(",", ":"), sort_keys=True)))
        if not apply:
            if _package_census() != {"maps": [], "content": []}:
                raise PlanError("DRY_RUN_DIRTIED_PACKAGES")
            unreal.log("S3_MARBLE_TUNE_DRY_RUN_OK|run=%s|mutated=0|copy_mi_only=1|pie_luminance=REQUIRED" % run)
            return
        _apply(run, plan, index, source)
    except PlanError as exc:
        unreal.log_error("S3_MARBLE_TUNE_%s_STOPPED|run=%s|reason=%s|census=%s" %
                         ("REVERT" if revert else ("APPLY" if apply else "DRY_RUN"), run, str(exc),
                          json.dumps(_package_census(), separators=(",", ":"), sort_keys=True)))
    except Exception:
        unreal.log_error("S3_MARBLE_TUNE_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(_package_census(), separators=(",", ":"), sort_keys=True)))


if unreal is not None:
    main()
