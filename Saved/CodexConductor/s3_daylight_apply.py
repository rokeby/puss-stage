"""DRY/APPLY/REVERT tool for the Scene 3 daylight relight.

Offline import is side-effect free.  In Unreal, DRY is the default; wrappers may
set S3_DAYLIGHT_APPLY or S3_DAYLIGHT_REVERT.  APPLY scales existing keyed light
values without moving their keys, adds a raking daylight key and cool fill at
the established 10 s strike, pins the existing S3 PPV, and saves only the level
and LS_S3_HangarRise.  Shared material masters are never edited.
"""
import copy
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
ROOT_LABEL = "S3 Hangar Root"
EXPOSURE_LABEL = "S3 Hangar Pinned Exposure"
LINER_LABELS = ("S3 Marble Inner Wall Left", "S3 Marble Inner Wall Right")
STRIKE_LABELS = (
    "S3 Strike Key", "S3 Strike Fill L", "S3 Strike Fill R",
    "S3 Strike Cyc 1", "S3 Strike Cyc 2", "S3 Strike Cyc 3",
)
DAYLIGHT_LABELS = ("S3 Daylight Rake Key", "S3 Daylight Cool Fill")
STRIKE_SCALE = 0.40
RIG_SCALE = 0.40
TARGET_EV100 = 2.0
EXPECTED_STRIKE_SECONDS = 10.0
STRIKE_TOLERANCE_SECONDS = 1.0 / 24.0 + 1.0e-6
RAMP_SECONDS = 0.20
RECORD_NAME = "s3_daylight_record.json"
COPY_MI_PATH = "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Daylight"
REQUIRED_TESTS = (
    "InfinityStage.Editor.SavedMasterMatchesShow",
    "InfinityStage.Editor.SceneCutBindingsResolve",
)
RIG_PREFIXES = ("S3 Practical ", "S3 Uplight ", "S3 Lattice Glow ")
DAYLIGHT_SPECS = (
    {
        "label": DAYLIGHT_LABELS[0], "location": (1500.0, -780.0, 2200.0),
        "target": (4500.0, 820.0, 700.0), "intensity": 1800.0,
        "temperature": 5800.0, "rect": (900.0, 500.0), "shadows": True,
    },
    {
        "label": DAYLIGHT_LABELS[1], "location": (2400.0, 850.0, 1500.0),
        "target": (4300.0, -700.0, 650.0), "intensity": 450.0,
        "temperature": 6800.0, "rect": (1200.0, 700.0), "shadows": False,
    },
)


class PlanError(ValueError):
    pass


def _finite(value):
    return math.isfinite(float(value))


def scale_keys(keys, factor):
    """Scale values only; key times and zero holds must remain byte-logically equal."""
    factor = float(factor)
    if not _finite(factor) or not 0.30 <= factor <= 0.50:
        raise PlanError("intensity scale must be within the requested 30-50 percent")
    result = []
    for row in keys:
        if len(row) != 2 or not _finite(row[0]) or not _finite(row[1]):
            raise PlanError("malformed intensity key")
        result.append([float(row[0]), float(row[1]) * factor])
    if [row[0] for row in result] != [float(row[0]) for row in keys]:
        raise PlanError("key times changed")
    return result


def classify_marble_material(profile):
    """Choose reuse/copy-tune/refuse without ever authoring a shared master."""
    if not profile.get("is_material_instance"):
        raise PlanError("marble liner material is not a MaterialInstanceConstant")
    if profile.get("edits_shared_master"):
        raise PlanError("shared material master edits are forbidden")
    has_normal = bool(profile.get("has_normal_texture"))
    has_roughness = bool(profile.get("has_roughness_response"))
    tunable = bool(profile.get("normal_scalar_names") or profile.get("roughness_scalar_names"))
    if has_normal and has_roughness:
        return "reuse"
    if has_normal and tunable:
        return "copy_tune"
    raise PlanError("flat marble has no exposed normal/roughness response to tune in a copy MI")


def plan_daylight(state):
    """Pure planner shared by Unreal DRY/APPLY and the offline harness."""
    strike = list(state.get("strike_lights", []))
    by_label = {str(row.get("label")): row for row in strike}
    if set(by_label) != set(STRIKE_LABELS) or len(strike) != 6:
        raise PlanError("expected exactly the six S3 Strike lights")
    rig = list(state.get("rig_lights", []))
    if not rig:
        raise PlanError("S3 hangar rig spill census is empty")
    if any(not str(row.get("label", "")).startswith(RIG_PREFIXES) for row in rig):
        raise PlanError("rig spill census contains an out-of-scope light")

    strike_time = float(state.get("strike_seconds", -1.0))
    if abs(strike_time - EXPECTED_STRIKE_SECONDS) > STRIKE_TOLERANCE_SECONDS:
        raise PlanError("S3 strike timing is not +10 s")
    existing = set(state.get("existing_labels", []))
    collisions = sorted(existing.intersection(DAYLIGHT_LABELS))
    if collisions:
        raise PlanError("daylight actor labels already exist: " + ", ".join(collisions))

    exposure = dict(state.get("exposure", {}))
    if exposure.get("label") != EXPOSURE_LABEL:
        raise PlanError("S3 pinned exposure actor is absent")
    if not exposure.get("fixed"):
        raise PlanError("S3 exposure is not currently fixed")
    if float(exposure.get("blend_weight", 0.0)) < 0.999:
        raise PlanError("S3 exposure PPV is not fully blended at the landed state")

    liner_materials = list(state.get("liner_materials", []))
    if len(liner_materials) != 2 or {row.get("label") for row in liner_materials} != set(LINER_LABELS):
        raise PlanError("expected exactly the two S3 marble liners")
    material_paths = {row.get("material_path") for row in liner_materials}
    if len(material_paths) != 1 or None in material_paths:
        raise PlanError("marble liners do not share one readable material")
    material_profile = dict(state.get("material_profile", {}))
    material_action = classify_marble_material(material_profile)

    planned_strike = []
    for label in STRIKE_LABELS:
        row = copy.deepcopy(by_label[label])
        row["before_keys"] = copy.deepcopy(row["keys"])
        row["after_keys"] = scale_keys(row["keys"], STRIKE_SCALE)
        planned_strike.append(row)
    planned_rig = []
    for source in rig:
        row = copy.deepcopy(source)
        row["before_keys"] = copy.deepcopy(row["keys"])
        row["after_keys"] = scale_keys(row["keys"], RIG_SCALE)
        planned_rig.append(row)

    new_lights = []
    for spec in DAYLIGHT_SPECS:
        row = copy.deepcopy(spec)
        row["keys"] = [[0.0, 0.0], [strike_time, 0.0],
                       [strike_time + RAMP_SECONDS, float(row["intensity"])]]
        new_lights.append(row)
    return {
        "strike_seconds": strike_time,
        "strike_scale": STRIKE_SCALE,
        "rig_scale": RIG_SCALE,
        "strike_lights": planned_strike,
        "rig_lights": planned_rig,
        "new_lights": new_lights,
        "exposure": {"before_ev100": float(exposure["ev100"]),
                     "after_ev100": TARGET_EV100, "fixed": True},
        "material": {"source": next(iter(material_paths)), "action": material_action,
                     "target": COPY_MI_PATH if material_action == "copy_tune" else next(iter(material_paths))},
        "required_tests": list(REQUIRED_TESTS),
    }


def _path(value):
    return str(value.get_path_name()).split(".", 1)[0]


def package_census():
    return {
        "maps": sorted(_path(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": sorted(_path(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def stop(run, reason):
    unreal.log_error("S3_DAYLIGHT_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def _one(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        stop(run, "reason=ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
    return rows[0]


def _index():
    rows = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        rows.setdefault(str(actor.get_actor_label()), []).append(actor)
    return rows


def _frame(key):
    value = key.get_time()
    return int(value.frame_number.value if hasattr(value, "frame_number") else value.value)


def _bindings(sequence):
    result = {}
    for binding in sequence.get_bindings():
        parent = binding.get_parent()
        label = str(parent.get_display_name()) if parent is not None and parent.is_valid() else str(binding.get_display_name())
        result.setdefault(label, []).append(binding)
    return result


def _intensity_channel(binding, run):
    channels = []
    for track in binding.get_tracks():
        if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == "Intensity":
            for section in track.get_sections():
                channels.extend(section.get_all_channels())
    if len(channels) != 1:
        stop(run, "reason=INTENSITY_CHANNEL_COUNT|binding=%s|count=%d" %
             (binding.get_display_name(), len(channels)))
    return channels[0]


def _float_channel(binding, property_name, run):
    channels = []
    for track in binding.get_tracks():
        if (isinstance(track, unreal.MovieSceneFloatTrack) and
                str(track.get_property_name()) == property_name):
            for section in track.get_sections():
                channels.extend(section.get_all_channels())
    if len(channels) != 1:
        stop(run, "reason=FLOAT_CHANNEL_COUNT|property=%s|count=%d" %
             (property_name, len(channels)))
    return channels[0]


def _channel_rows(channel, fps):
    return [[_frame(key) / float(fps), float(key.get_value())]
            for key in sorted(channel.get_keys(), key=_frame)]


def _material_profile(material):
    tex_names = [str(value) for value in unreal.MaterialEditingLibrary.get_texture_parameter_names(material)]
    scalar_names = [str(value) for value in unreal.MaterialEditingLibrary.get_scalar_parameter_names(material)]
    lower_tex = [value.lower() for value in tex_names]
    lower_scalar = [value.lower() for value in scalar_names]
    return {
        "is_material_instance": isinstance(material, unreal.MaterialInstanceConstant),
        "has_normal_texture": any("normal" in value or "nrm" in value for value in lower_tex),
        "has_roughness_response": any("rough" in value or "ordp" in value or "orm" in value for value in lower_tex + lower_scalar),
        "normal_scalar_names": [name for name, low in zip(scalar_names, lower_scalar) if "normal" in low],
        "roughness_scalar_names": [name for name, low in zip(scalar_names, lower_scalar) if "rough" in low],
        "edits_shared_master": False,
        "texture_names": tex_names,
        "scalar_names": scalar_names,
    }


def _live_state(sequence, index, run):
    rate = sequence.get_display_rate()
    fps = float(rate.numerator) / float(rate.denominator)
    bindings = _bindings(sequence)
    rows = []
    for label in STRIKE_LABELS:
        actor = _one(index, label, run)
        found = bindings.get(label, [])
        if len(found) != 1:
            stop(run, "reason=STRIKE_BINDING_COUNT|label=%s|count=%d" % (label, len(found)))
        rows.append({"label": label, "actor_path": str(actor.get_path_name()),
                     "binding_guid": str(unreal.GuidLibrary.conv_guid_to_string(found[0].get_id())),
                     "keys": _channel_rows(_intensity_channel(found[0], run), fps)})
    rig = []
    for label, found in sorted(bindings.items()):
        if not label.startswith(RIG_PREFIXES):
            continue
        if len(found) != 1:
            stop(run, "reason=RIG_BINDING_COUNT|label=%s|count=%d" % (label, len(found)))
        rig.append({"label": label,
                    "binding_guid": str(unreal.GuidLibrary.conv_guid_to_string(found[0].get_id())),
                    "keys": _channel_rows(_intensity_channel(found[0], run), fps)})
    positive_times = [time for row in rows for time, value in row["keys"] if value > 0.0]
    if not positive_times:
        stop(run, "reason=NO_STRIKE_KEYS")
    strike_seconds = min(positive_times) - RAMP_SECONDS

    exposure_actor = _one(index, EXPOSURE_LABEL, run)
    settings = exposure_actor.get_editor_property("settings")
    fixed = (bool(settings.get_editor_property("override_auto_exposure_min_brightness")) and
             bool(settings.get_editor_property("override_auto_exposure_max_brightness")) and
             abs(float(settings.get_editor_property("auto_exposure_min_brightness")) -
                 float(settings.get_editor_property("auto_exposure_max_brightness"))) < 1.0e-4)
    ev = float(settings.get_editor_property("auto_exposure_min_brightness"))
    exposure_bindings = bindings.get(EXPOSURE_LABEL, [])
    if len(exposure_bindings) != 1:
        stop(run, "reason=EXPOSURE_BINDING_COUNT|count=%d" % len(exposure_bindings))
    blend_rows = _channel_rows(_float_channel(exposure_bindings[0], "BlendWeight", run), fps)
    if not blend_rows:
        stop(run, "reason=EXPOSURE_BLEND_KEYS_EMPTY")
    landed_blend_weight = float(blend_rows[-1][1])
    liners = []
    material = None
    for label in LINER_LABELS:
        actor = _one(index, label, run)
        components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
        if len(components) != 1 or len(components[0].get_materials()) != 1:
            stop(run, "reason=LINER_MATERIAL_COUNT|label=" + label)
        current = components[0].get_material(0)
        liners.append({"label": label, "material_path": _path(current)})
        material = current if material is None else material
    return ({"strike_lights": rows, "rig_lights": rig, "strike_seconds": strike_seconds,
             "existing_labels": list(index),
             "exposure": {"label": EXPOSURE_LABEL, "fixed": fixed, "ev100": ev,
                          "blend_weight": landed_blend_weight},
             "liner_materials": liners, "material_profile": _material_profile(material)},
            {"fps": fps, "bindings": bindings, "exposure_actor": exposure_actor,
             "material": material})


def _asset_filename(project, package, extension):
    return os.path.join(project, "Content", *package[len("/Game/"):].split("/")) + extension


def _backup(project, stamp, run):
    target = os.path.join(project, "Backups", "PreS3Daylight-" + stamp.strftime("%Y%m%d-%H%M%S"))
    if os.path.exists(target):
        stop(run, "reason=BACKUP_EXISTS")
    sources = (_asset_filename(project, EXPECTED_WORLD, ".umap"),
               _asset_filename(project, SEQUENCE_PATH, ".uasset"))
    if any(not os.path.isfile(path) for path in sources):
        stop(run, "reason=BACKUP_SOURCE_MISSING")
    for source in sources:
        relative = os.path.relpath(source, os.path.join(project, "Content"))
        destination = os.path.join(target, "Content", relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
    return target


def _rotation(location, target):
    dx, dy, dz = (float(target[i]) - float(location[i]) for i in range(3))
    horizontal = math.sqrt(dx * dx + dy * dy)
    return (0.0, math.degrees(math.atan2(dz, horizontal)), math.degrees(math.atan2(dy, dx)))


def _set_channel(channel, rows, fps):
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    for seconds, value in rows:
        frame = int(round(float(seconds) * fps))
        channel.add_key(unreal.FrameNumber(frame), float(value),
                        time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                        interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


def _require_channel_rows(channel, wanted, fps, run, label):
    got = _channel_rows(channel, fps)
    if (len(got) != len(wanted) or
            any(abs(got_row[0] - float(want_row[0])) > 0.5 / fps + 1.0e-6 or
                abs(got_row[1] - float(want_row[1])) > 0.001
                for got_row, want_row in zip(got, wanted))):
        stop(run, "reason=KEY_READBACK|label=%s|got=%s|wanted=%s" %
             (label, json.dumps(got), json.dumps(wanted)))


def _spawn_daylight(spec, root, sequence, fps, run):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.RectLight, unreal.Vector())
    if actor is None:
        stop(run, "reason=DAYLIGHT_SPAWN_FAILED|label=" + spec["label"])
    actor.set_actor_label(spec["label"])
    actor.tags = list(actor.tags) + ["RigAtmos.S3Daylight"]
    actor.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE,
                          unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE, False)
    rot = _rotation(spec["location"], spec["target"])
    actor.get_editor_property("root_component").set_relative_location(unreal.Vector(*spec["location"]), False, False)
    actor.get_editor_property("root_component").set_relative_rotation(
        unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]), False, False)
    component = actor.get_component_by_class(unreal.RectLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    component.set_editor_property("intensity", float(spec["intensity"]))
    component.set_editor_property("attenuation_radius", 9500.0)
    component.set_editor_property("source_width", float(spec["rect"][0]))
    component.set_editor_property("source_height", float(spec["rect"][1]))
    component.set_editor_property("use_temperature", True)
    component.set_editor_property("temperature", float(spec["temperature"]))
    component.set_editor_property("cast_shadows", bool(spec["shadows"]))
    binding = sequence.add_possessable(component)
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path("Intensity", "Intensity")
    section = track.add_section()
    section.set_range(int(sequence.get_playback_start()), int(sequence.get_playback_end()))
    channels = section.get_all_channels()
    if len(channels) != 1:
        stop(run, "reason=NEW_LIGHT_CHANNEL_COUNT|label=" + spec["label"])
    _set_channel(channels[0], spec["keys"], fps)
    _require_channel_rows(channels[0], spec["keys"], fps, run, spec["label"])
    return {"label": spec["label"], "actor_path": str(actor.get_path_name()),
            "binding_guid": str(unreal.GuidLibrary.conv_guid_to_string(binding.get_id()))}


def _write_record(record, exclusive, run):
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor", RECORD_NAME)
    try:
        with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
        return path
    except Exception as exc:
        stop(run, "reason=RECORD_WRITE|detail=" + str(exc))


def _read_record(run):
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor", RECORD_NAME)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle), path
    except Exception as exc:
        stop(run, "reason=RECORD_READ|detail=" + str(exc))


def _binding_by_guid(sequence, guid):
    rows = [binding for binding in sequence.get_bindings()
            if str(unreal.GuidLibrary.conv_guid_to_string(binding.get_id())) == guid]
    return rows[0] if len(rows) == 1 else None


def _save(run):
    if not unreal.EditorAssetLibrary.save_asset(SEQUENCE_PATH, only_if_is_dirty=False):
        stop(run, "reason=SEQUENCE_SAVE_FAILED")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "reason=LEVEL_SAVE_FAILED")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    return census


def _apply(sequence, index, plan, runtime, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    backup = _backup(project, stamp, run)
    record = {"world": EXPECTED_WORLD, "asset": SEQUENCE_PATH, "run": run,
              "written": stamp.isoformat(timespec="seconds"), "backup": backup,
              "plan": plan, "new_lights": [], "applied": False}
    _write_record(record, True, run)
    fps = runtime["fps"]
    for row in plan["strike_lights"] + plan["rig_lights"]:
        binding = _binding_by_guid(sequence, row["binding_guid"])
        if binding is None:
            stop(run, "reason=BINDING_CHANGED|label=" + row["label"])
        channel = _intensity_channel(binding, run)
        _set_channel(channel, row["after_keys"], fps)
        _require_channel_rows(channel, row["after_keys"], fps, run, row["label"])
        actor = index.get(row["label"], [None])[0]
        if actor is not None:
            component = actor.get_component_by_class(unreal.LightComponent)
            if component is not None:
                component.set_editor_property("intensity", max(value for _, value in row["after_keys"]))
    root = _one(index, ROOT_LABEL, run)
    for spec in plan["new_lights"]:
        record["new_lights"].append(_spawn_daylight(spec, root, sequence, fps, run))
        _write_record(record, False, run)
    settings = runtime["exposure_actor"].get_editor_property("settings")
    record["exposure_before"] = {
        "min": float(settings.get_editor_property("auto_exposure_min_brightness")),
        "max": float(settings.get_editor_property("auto_exposure_max_brightness")),
    }
    for name in ("override_auto_exposure_min_brightness", "override_auto_exposure_max_brightness"):
        settings.set_editor_property(name, True)
    settings.set_editor_property("auto_exposure_min_brightness", TARGET_EV100)
    settings.set_editor_property("auto_exposure_max_brightness", TARGET_EV100)
    runtime["exposure_actor"].set_editor_property("settings", settings)
    exposure_readback = runtime["exposure_actor"].get_editor_property("settings")
    if (abs(float(exposure_readback.get_editor_property("auto_exposure_min_brightness")) - TARGET_EV100) > 0.001 or
            abs(float(exposure_readback.get_editor_property("auto_exposure_max_brightness")) - TARGET_EV100) > 0.001):
        stop(run, "reason=EXPOSURE_READBACK")
    if plan["material"]["action"] == "copy_tune":
        if unreal.EditorAssetLibrary.does_asset_exist(COPY_MI_PATH):
            stop(run, "reason=COPY_MI_ALREADY_EXISTS")
        copied = unreal.EditorAssetLibrary.duplicate_asset(plan["material"]["source"], COPY_MI_PATH)
        if copied is None:
            stop(run, "reason=COPY_MI_FAILED")
        profile = _material_profile(copied)
        for name in profile["roughness_scalar_names"]:
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(copied, name, 0.65)
        for name in profile["normal_scalar_names"]:
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(copied, name, 1.20)
        for label in LINER_LABELS:
            _one(index, label, run).get_components_by_class(unreal.StaticMeshComponent)[0].set_material(0, copied)
        record["material_copy_created"] = COPY_MI_PATH
        if not unreal.EditorAssetLibrary.save_asset(COPY_MI_PATH, only_if_is_dirty=False):
            stop(run, "reason=COPY_MI_SAVE_FAILED")
    dirty = package_census()
    allowed_content = {SEQUENCE_PATH}
    if record.get("material_copy_created"):
        allowed_content.add(COPY_MI_PATH)
    if set(dirty["maps"]) != {EXPECTED_WORLD} or not set(dirty["content"]).issubset(allowed_content):
        stop(run, "reason=DIRTY_SCOPE|census=" + json.dumps(dirty, sort_keys=True))
    record["dirty_before_save"] = dirty
    record["post_save_census"] = _save(run)
    record["applied"] = True
    _write_record(record, False, run)
    unreal.log("S3_DAYLIGHT_DONE|run=%s|applied|backup=%s|tests_required_singly=%s" %
               (run, backup, ",".join(REQUIRED_TESTS)))


def _revert(sequence, index, run):
    record, path = _read_record(run)
    if record.get("world") != EXPECTED_WORLD or record.get("asset") != SEQUENCE_PATH or not record.get("applied"):
        stop(run, "reason=REVERT_RECORD_CONTEXT")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = _backup(project, datetime.datetime.now(), run)
    fps = float(sequence.get_display_rate().numerator) / float(sequence.get_display_rate().denominator)
    for row in record["plan"]["strike_lights"] + record["plan"]["rig_lights"]:
        binding = _binding_by_guid(sequence, row["binding_guid"])
        if binding is None:
            stop(run, "reason=REVERT_BINDING_CHANGED|label=" + row["label"])
        channel = _intensity_channel(binding, run)
        _set_channel(channel, row["before_keys"], fps)
        _require_channel_rows(channel, row["before_keys"], fps, run, row["label"])
        actor = index.get(row["label"], [None])[0]
        if actor is not None:
            component = actor.get_component_by_class(unreal.LightComponent)
            if component is not None:
                component.set_editor_property("intensity", max(value for _, value in row["before_keys"]))
    for row in record["new_lights"]:
        binding = _binding_by_guid(sequence, row["binding_guid"])
        if binding is None:
            stop(run, "reason=REVERT_NEW_BINDING|label=" + row["label"])
        binding.remove()
        actor = next((value for value in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                      if str(value.get_path_name()) == row["actor_path"]), None)
        if actor is None or not unreal.EditorLevelLibrary.destroy_actor(actor):
            stop(run, "reason=REVERT_NEW_ACTOR|label=" + row["label"])
    exposure = _one(_index(), EXPOSURE_LABEL, run)
    settings = exposure.get_editor_property("settings")
    settings.set_editor_property("auto_exposure_min_brightness", float(record["exposure_before"]["min"]))
    settings.set_editor_property("auto_exposure_max_brightness", float(record["exposure_before"]["max"]))
    exposure.set_editor_property("settings", settings)
    if record.get("material_copy_created"):
        source = unreal.load_asset(record["plan"]["material"]["source"])
        for label in LINER_LABELS:
            _one(_index(), label, run).get_components_by_class(unreal.StaticMeshComponent)[0].set_material(0, source)
        # The added MI is deliberately retained, unused: project policy forbids permanent deletion.
    census = _save(run)
    archived = path + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(path, archived)
    unreal.log("S3_DAYLIGHT_DONE|run=%s|reverted|backup=%s|census=%s|retained_copy_mi=%s" %
               (run, backup, json.dumps(census, sort_keys=True), record.get("material_copy_created")))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_DAYLIGHT_APPLY"))
    revert = bool(globals().get("S3_DAYLIGHT_REVERT"))
    if apply and revert:
        stop(run, "reason=APPLY_AND_REVERT_BOTH_SET")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        stop(run, "reason=SEQUENCER_IS_OPEN")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    record_path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                               "CodexConductor", RECORD_NAME)
    if apply and os.path.exists(record_path):
        stop(run, "reason=APPLY_RECORD_EXISTS")
    if revert and not os.path.isfile(record_path):
        stop(run, "reason=REVERT_RECORD_ABSENT")
    sequence = unreal.load_asset(SEQUENCE_PATH)
    if sequence is None or not isinstance(sequence, unreal.LevelSequence):
        stop(run, "reason=SEQUENCE_LOAD_FAILED")
    index = _index()
    if revert:
        _revert(sequence, index, run)
        return
    state, runtime = _live_state(sequence, index, run)
    try:
        plan = plan_daylight(state)
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    if not apply:
        if package_census() != census:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES")
        unreal.log("S3_DAYLIGHT_DRY_RUN_OK|run=%s|mutated=0|plan=%s" %
                   (run, json.dumps(plan, separators=(",", ":"), sort_keys=True)))
        return
    _apply(sequence, index, plan, runtime, run)


if unreal is not None:
    main()
