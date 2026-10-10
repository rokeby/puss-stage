"""Job 110: guarded DRY/APPLY/REVERT tuning for the one P02 car sweep light.

The default proposal extends the attenuation radius from 3200 to 4600 cm and
aims at the far (house-right) wing line, about Y=-3800 cm in actor-local space.
Peak intensity and outer cone default to unchanged. Gary owns the look: the
checked-in args remain DRY and APPLY requires an explicit confirmation string.

Offline evidence (not a substitute for the mandatory DRY read-back):
  * place_p02_car_light_record.json, CAR-20261005-092430, read back radius 3200,
    aim [0,-2400,0], peak 9000 after placement.
  * p02_straighten_followons_record.json, P02FOL-20261007-015605, moved the
    actor with P02 but did not edit these light properties.
  * animated_gobo_pie_probe_AGPIE-20261009-02.json measured the live spot
    component at radius 3200 and outer cone 28 on 8 Oct.

APPLY/REVERT refuse PIE, the wrong world, dirty packages, a missing/duplicate
or wrong-class actor, placement-record mismatch, expected-current drift, and
out-of-range targets. They write an originals record and copy the level into a
Backups/PreP02CarLightTune-* folder before modifying the actor; save only the
named level; read back; require a clean census; and log a run-id marker.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "p02_car_light_tune_args.json")
PLACEMENT_RECORD = os.path.join(HERE, "place_p02_car_light_record.json")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LABEL = "P02 Car Light (trial, Gary to tune)"
CLASS = "InfinityStageSweepLight"
PLACEMENT_RUN = "CAR-20261005-092430"
FIELDS = ("attenuation_radius_cm", "aim_target_local", "peak_intensity", "outer_cone_degrees")
DEFAULT_EXPECTED = {
    "attenuation_radius_cm": 3200.0,
    "aim_target_local": [0.0, -2400.0, 0.0],
    "peak_intensity": 9000.0,
    "outer_cone_degrees": 28.0,
}
DEFAULT_TARGET = {
    "attenuation_radius_cm": 4600.0,
    "aim_target_local": [0.0, -3800.0, 0.0],
    "peak_intensity": None,
    "outer_cone_degrees": None,
}
LIMITS = {
    "attenuation_radius_cm": (1000.0, 8000.0),
    "peak_intensity": (100.0, 20000.0),
    "outer_cone_degrees": (1.0, 80.0),
}
TOLERANCE = 1.0e-3


class CarTuneError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise CarTuneError(message)


def _plain(value):
    if unreal is not None and isinstance(value, unreal.Vector):
        return [float(value.x), float(value.y), float(value.z)]
    if isinstance(value, (list, tuple)):
        return [float(v) for v in value]
    return float(value)


def _close(left, right, tolerance=TOLERANCE):
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        return (isinstance(left, (list, tuple)) and isinstance(right, (list, tuple))
                and len(left) == len(right)
                and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(left, right)))
    return abs(float(left) - float(right)) <= tolerance


def _assert_fields(values, prefix):
    require(set(values) == set(FIELDS), "%s_FIELDS|%s" % (prefix, sorted(values)))


def plan_change(current, expected, requested):
    """Pure plan used by the offline harness and the Unreal runner."""
    _assert_fields(current, "CURRENT")
    _assert_fields(expected, "EXPECTED")
    _assert_fields(requested, "TARGET")
    drift = {key: {"current": current[key], "expected": expected[key]}
             for key in FIELDS if not _close(current[key], expected[key])}
    require(not drift, "P02CAR_CURRENT_NOT_EXPECTED|%s|rerun DRY and update expected only after review"
            % json.dumps(drift, sort_keys=True))

    target = {key: (current[key] if requested[key] is None else requested[key]) for key in FIELDS}
    aim = target["aim_target_local"]
    require(isinstance(aim, (list, tuple)) and len(aim) == 3, "P02CAR_AIM_VECTOR")
    target["aim_target_local"] = [float(v) for v in aim]
    for key, (low, high) in LIMITS.items():
        require(low <= float(target[key]) <= high,
                "P02CAR_TARGET_OUT_OF_RANGE|%s=%s|[%s,%s]" % (key, target[key], low, high))
        target[key] = float(target[key])
    require(all(abs(v) <= 8000.0 for v in target["aim_target_local"]),
            "P02CAR_AIM_OUT_OF_RANGE|%s" % target["aim_target_local"])
    require(target["attenuation_radius_cm"] >= 4200.0,
            "P02CAR_RADIUS_CANNOT_REACH_FAR_WING|%s" % target["attenuation_radius_cm"])
    # Gary E28: radius only -> aim may stay unchanged (requested None); a REQUESTED aim must still face the far side.
    require(requested["aim_target_local"] is None or target["aim_target_local"][1] <= -3400.0,
            "P02CAR_AIM_NOT_AT_FAR_SIDE|%s" % target["aim_target_local"])
    return target


def _census():
    library = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(package.get_name() for package in library.get_dirty_content_packages()),
        "maps": sorted(package.get_name() for package in library.get_dirty_map_packages()),
    }


def _read(actor):
    return {key: _plain(actor.get_editor_property(key)) for key in FIELDS}


def _write(actor, values):
    actor.modify()
    for key in FIELDS:
        value = values[key]
        if key == "aim_target_local":
            value = unreal.Vector(*value)
        actor.set_editor_property(key, value)


def _load_json(path, purpose):
    require(os.path.isfile(path), "P02CAR_%s_MISSING|%s" % (purpose, path))
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _validate_placement_record(record):
    require(record.get("run") == PLACEMENT_RUN and record.get("label") == LABEL,
            "P02CAR_PLACEMENT_RECORD_IDENTITY")
    applied = record.get("applied", {})
    require(_close(applied.get("attenuation_radius_cm"), 3200.0)
            and _close(applied.get("aim_target_local"), [0.0, -2400.0, 0.0])
            and _close(applied.get("peak_intensity"), 9000.0),
            "P02CAR_PLACEMENT_RECORD_VALUES|%s" % json.dumps(applied, sort_keys=True))


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True)


def main():
    run = datetime.datetime.now().strftime("P02CAR-TUNE-%Y%m%d-%H%M%S")
    args = _load_json(ARGS, "ARGS")
    mode = str(args.get("mode", "DRY")).upper()
    confirm = "%s P02CAR_TUNE" % mode
    require(mode in ("DRY", "APPLY", "REVERT") and args.get("confirm") == confirm,
            "P02CAR_CONFIRM|mode=%s|confirm must be '%s'" % (mode, confirm))
    placement = _load_json(PLACEMENT_RECORD, "PLACEMENT_RECORD")
    _validate_placement_record(placement)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "P02CAR_PIE_ACTIVE")
    world = editor.get_editor_world()
    require(world.get_path_name().split(".")[0] == WORLD, "P02CAR_WRONG_WORLD")
    before_census = _census()
    require(before_census == {"content": [], "maps": []},
            "P02CAR_DIRTY_BEFORE|%s" % json.dumps(before_census))
    actors = [actor for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if str(actor.get_actor_label()) == placement["label"]]
    require(len(actors) == 1 and actors[0].get_class().get_name() == CLASS,
            "P02CAR_ACTOR_IDENTITY|count=%d|classes=%s" %
            (len(actors), [actor.get_class().get_name() for actor in actors]))
    actor = actors[0]
    current = _read(actor)

    if mode == "REVERT":
        original_name = args.get("revert_from")
        require(original_name and os.path.basename(original_name) == original_name,
                "P02CAR_REVERT_FILE_NAME")
        original = _load_json(os.path.join(HERE, original_name), "REVERT_RECORD")
        require(original.get("label") == LABEL and original.get("placement_run") == PLACEMENT_RUN,
                "P02CAR_REVERT_RECORD_IDENTITY")
        applied_name = original.get("applied_file")
        require(applied_name, "P02CAR_REVERT_HAS_NO_APPLIED_FILE")
        applied = _load_json(os.path.join(HERE, applied_name), "APPLIED_RECORD")
        _assert_fields(applied.get("values", {}), "APPLIED_RECORD")
        drift = {key: {"current": current[key], "applied": applied["values"][key]}
                 for key in FIELDS if not _close(current[key], applied["values"][key])}
        require(not drift, "P02CAR_REVERT_DRIFT|%s" % json.dumps(drift, sort_keys=True))
        target = original["values"]
    else:
        target = plan_change(current, args.get("expected", DEFAULT_EXPECTED),
                             args.get("target", DEFAULT_TARGET))

    report = {
        "run": run,
        "mode": mode,
        "placement_run": placement["run"],
        "label": LABEL,
        "actor_path": actor.get_path_name(),
        "current": current,
        "target": target,
        "dirty_before": before_census,
        "mutated": False,
        "stills_plan": args.get("stills_plan", {}),
    }
    if mode == "DRY":
        report_path = os.path.join(HERE, "p02_car_light_tune_dry_%s.json" % run)
        _write_json(report_path, report)
        unreal.log("P02_CAR_LIGHT_TUNE_DRY_OK|run=%s|current=%s|target=%s|mutated=0|report=%s"
                   % (run, json.dumps(current), json.dumps(target), report_path))
        return report

    originals_path = os.path.join(HERE, "p02_car_light_tune_originals_%s.json" % run)
    originals = {
        "run": run,
        "mode": mode,
        "placement_run": placement["run"],
        "label": LABEL,
        "actor_path": actor.get_path_name(),
        "values": current,
        "applied_file": None,
    }
    _write_json(originals_path, originals)
    backup = "E:/PussStage/Backups/PreP02CarLightTune-%s" % run
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    unreal.log("P02_CAR_LIGHT_TUNE_GUARD_OK|run=%s|originals=%s|backup=%s" %
               (run, originals_path, backup))

    _write(actor, target)
    immediate = _read(actor)
    require(all(_close(immediate[key], target[key]) for key in FIELDS),
            "P02CAR_SETTER_READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(immediate))
    dirty = _census()
    require(not dirty["content"] and dirty["maps"] == [WORLD],
            "P02CAR_DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "P02CAR_SAVE_FAILED")
    require(_census() == {"content": [], "maps": []}, "P02CAR_POST_SAVE_DIRTY")
    saved = _read(actor)
    require(all(_close(saved[key], target[key]) for key in FIELDS),
            "P02CAR_SAVED_READBACK|%s" % json.dumps(saved))

    applied_path = os.path.join(HERE, "p02_car_light_tune_applied_%s.json" % run)
    report.update({"mutated": True, "backup": backup, "originals": os.path.basename(originals_path),
                   "values": saved, "dirty_after": _census()})
    _write_json(applied_path, report)
    originals["applied_file"] = os.path.basename(applied_path)
    _write_json(originals_path, originals)
    unreal.log("P02_CAR_LIGHT_TUNE_%s_OK|run=%s|values=%s|level_saved=1|readback=1|dirty=0|backup=%s|originals=%s"
               % (mode, run, json.dumps(saved), backup, originals_path))
    return report


if unreal is not None:
    main()
