"""Merge the imported Animals and Shrine scenes into the StageTest world.

The script is intentionally dry-run by default. Run with ``-MergeImportedScenes``
on the Unreal command line to perform the edit. It is designed for Unreal
Editor 5.8 and keeps all imported actors in scene-specific Outliner folders.
"""

import gc

import unreal


TARGET_WORLD = "/Game/Levels/StageTest"

SCENES = (
    {
        "key": "Animals",
        "source_world": "/Game/KK_S1_Animals/Main",
        "source_sequence": "/Game/KK_S1_Animals/LS_Animals_1",
        "target_sequence": "/Game/Stage/Sequences/Imported/LS_Animals_StageTest",
        "root_folder": "Imported Sequences/Animals",
        "rig_label": "CSR_Animals",
        "sequence_actor_label": "SEQ_Animals_StageTest",
        "expected_actor_count": 49,
        "expected_wing_actors": 14,
        "expected_actor_bindings": 9,
        "expected_managed_lights": 11,
        "expected_managed_effects": 0,
        "expected_managed_audio": 0,
    },
    {
        "key": "Shrine",
        "source_world": "/Game/KK_S2_Shrine/KK_Main_S2_Shrine",
        "source_sequence": "/Game/KK_S2_Shrine/LS_Shrine",
        "target_sequence": "/Game/Stage/Sequences/Imported/LS_Shrine_StageTest",
        "root_folder": "Imported Sequences/Shrine",
        "rig_label": "CSR_Shrine",
        "sequence_actor_label": "SEQ_Shrine_StageTest",
        "expected_actor_count": 24,
        "expected_wing_actors": 11,
        "expected_actor_bindings": 1,
        "expected_managed_lights": 5,
        "expected_managed_effects": 3,
        "expected_managed_audio": 0,
    },
)


GLOBAL_ENVIRONMENT_CLASSES = {
    "DirectionalLight",
    "SkyLight",
    "SkyAtmosphere",
    "ExponentialHeightFog",
    "VolumetricCloud",
}

GLOBAL_ENVIRONMENT_LABELS = {
    "SM_SkySphere",
}

EDITOR_ONLY_EXCLUDED_CLASSES = {
    "LevelSequenceActor",
    "PlayerStart",
    "WorldSettings",
    "Brush",
}

SOURCE_DEPENDENCY_COPIES = (
    (
        "/Game/KK_S2_Shrine/StarterContent/Particles/P_Fire",
        "/Game/StarterContent/Particles/P_Fire",
    ),
    (
        "/Game/KK_S2_Shrine/StarterContent/Materials/M_Metal_Burnished_Steel",
        "/Game/StarterContent/Materials/M_Metal_Burnished_Steel",
    ),
)


def _class_name(actor):
    return actor.get_class().get_name()


def _actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def _actor_folder(actor):
    try:
        return str(actor.get_folder_path())
    except Exception:
        return ""


def _static_mesh_paths(actor):
    paths = []
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        if mesh:
            paths.append(mesh.get_path_name())
    return paths


def _is_wing_actor(actor):
    candidates = [_actor_label(actor), actor.get_name(), *_static_mesh_paths(actor)]
    for candidate in candidates:
        normalized = candidate.replace("\\", "/").lower()
        leaf = normalized.rsplit("/", 1)[-1]
        if "wing" in leaf or "opening_curtain" in leaf or "ceiling_flap" in leaf:
            return True
    return False


def _exclusion_reason(actor):
    class_name = _class_name(actor)
    if (
        class_name in GLOBAL_ENVIRONMENT_CLASSES
        or _actor_label(actor) in GLOBAL_ENVIRONMENT_LABELS
    ):
        return "default global environment"
    if class_name in EDITOR_ONLY_EXCLUDED_CLASSES:
        return "editor/source-map infrastructure"
    return ""


def _source_actors():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(actor_subsystem.get_all_level_actors())


def inventory():
    unreal.log("=== Imported sequence merge inventory ===")
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    for scene in SCENES:
        if not level_subsystem.load_level(scene["source_world"]):
            raise RuntimeError("Could not load {}".format(scene["source_world"]))

        included = []
        excluded = []
        for actor in _source_actors():
            reason = _exclusion_reason(actor)
            entry = (
                actor.get_name(),
                _actor_label(actor),
                _class_name(actor),
                _actor_folder(actor),
                ";".join(_static_mesh_paths(actor)),
            )
            if reason:
                excluded.append((reason, entry))
            else:
                included.append(entry)

        unreal.log(
            "[{}] included={} excluded={}".format(
                scene["key"], len(included), len(excluded)
            )
        )
        for entry in included:
            unreal.log(
                "[{}][INCLUDE] name={} label={} class={} folder={} assets={}".format(
                    scene["key"], *entry
                )
            )
        for reason, entry in excluded:
            unreal.log(
                "[{}][EXCLUDE:{}] name={} label={} class={} folder={} assets={}".format(
                    scene["key"], reason, *entry
                )
            )


def _add_tag(actor, tag):
    tags = list(actor.get_editor_property("tags"))
    if tag not in [str(existing) for existing in tags]:
        tags.append(tag)
        actor.set_editor_property("tags", tags)


def _outliner_subfolder(scene, actor):
    class_name = _class_name(actor)
    if actor.get_components_by_class(unreal.LightComponent):
        return scene["root_folder"] + "/Lighting"
    if class_name == "CineCameraActor":
        return scene["root_folder"] + "/Cameras"
    if _is_wing_actor(actor):
        return scene["root_folder"] + "/Wings"
    if class_name in {"NiagaraActor", "Emitter"}:
        return scene["root_folder"] + "/Effects"
    if actor.get_components_by_class(unreal.AudioComponent):
        return scene["root_folder"] + "/Audio"
    return scene["root_folder"] + "/Scenery"


def _assert_clean_target():
    for scene in SCENES:
        if unreal.EditorAssetLibrary.does_asset_exist(scene["target_sequence"]):
            raise RuntimeError(
                "Target sequence already exists: {}".format(scene["target_sequence"])
            )

    existing_labels = {_actor_label(actor) for actor in _source_actors()}
    reserved_labels = {
        label
        for scene in SCENES
        for label in (scene["rig_label"], scene["sequence_actor_label"])
    }
    collisions = sorted(existing_labels.intersection(reserved_labels))
    if collisions:
        raise RuntimeError(
            "StageTest already contains merge-managed actors: {}".format(
                ", ".join(collisions)
            )
        )


def _ensure_source_dependencies():
    for source_path, target_path in SOURCE_DEPENDENCY_COPIES:
        if unreal.EditorAssetLibrary.does_asset_exist(target_path):
            unreal.log(
                "Source dependency already available: {}".format(target_path)
            )
            continue
        duplicated = unreal.EditorAssetLibrary.duplicate_asset(
            source_path, target_path
        )
        if not duplicated:
            raise RuntimeError(
                "Could not duplicate source dependency {} to {}".format(
                    source_path, target_path
                )
            )
        if not unreal.EditorAssetLibrary.save_loaded_asset(duplicated, False):
            raise RuntimeError(
                "Could not save source dependency {}".format(target_path)
            )
        unreal.log(
            "Created source dependency {} from {}".format(
                target_path, source_path
            )
        )


def _copy_sequence(scene):
    source_sequence = unreal.load_asset(scene["source_sequence"])
    if not source_sequence:
        raise RuntimeError(
            "Could not load source sequence {}".format(scene["source_sequence"])
        )

    copied_sequence = unreal.EditorAssetLibrary.duplicate_asset(
        scene["source_sequence"], scene["target_sequence"]
    )
    if not copied_sequence:
        raise RuntimeError(
            "Could not copy sequence to {}".format(scene["target_sequence"])
        )
    return copied_sequence


def _key_visual_asset(actor):
    paths = list(
        unreal.StageSceneMergeLibrary.get_primary_visual_asset_paths(actor)
    )
    return ";".join(str(path) for path in paths)


def _copy_streamed_scene(scene, target_world):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    before_paths = {
        actor.get_path_name() for actor in actor_subsystem.get_all_level_actors()
    }

    source_streaming = unreal.EditorLevelUtils.add_level_to_world(
        target_world,
        scene["source_world"],
        unreal.LevelStreamingAlwaysLoaded,
    )
    if not source_streaming:
        raise RuntimeError(
            "Could not temporarily stream {}".format(scene["source_world"])
        )

    source_actors = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor.get_path_name() not in before_paths
    ]
    if not source_actors:
        raise RuntimeError(
            "No actors appeared after streaming {}".format(scene["source_world"])
        )

    included = [
        actor for actor in source_actors if not _exclusion_reason(actor)
    ]
    excluded = [
        actor for actor in source_actors if _exclusion_reason(actor)
    ]
    unreal.log(
        "[{}] cloning {} actors; excluding {} global/infrastructure actors".format(
            scene["key"], len(included), len(excluded)
        )
    )

    copied_actors = []
    for source_actor in included:
        copied_actor = (
            unreal.StageSceneMergeLibrary.clone_actor_to_persistent_level(
                source_actor
            )
        )
        if not copied_actor:
            raise RuntimeError(
                "[{}] could not clone {} ({})".format(
                    scene["key"],
                    _actor_label(source_actor),
                    _class_name(source_actor),
                )
            )
        copied_actor.set_editor_property("is_spatially_loaded", False)
        copied_actor.set_folder_path(_outliner_subfolder(scene, copied_actor))
        _add_tag(copied_actor, "ImportedScene_{}".format(scene["key"]))
        source_assets = sorted(
            str(path)
            for path in unreal.StageSceneMergeLibrary.get_primary_visual_asset_paths(
                source_actor
            )
        )
        copied_assets = sorted(
            str(path)
            for path in unreal.StageSceneMergeLibrary.get_primary_visual_asset_paths(
                copied_actor
            )
        )
        if copied_assets != source_assets:
            raise RuntimeError(
                "[{}] visual assets differ for {}: source={} copied={}".format(
                    scene["key"],
                    _actor_label(source_actor),
                    source_assets,
                    copied_assets,
                )
            )
        copied_actors.append(copied_actor)
        unreal.log(
            "[{}] cloned {} ({}) visual_asset={}".format(
                scene["key"],
                _actor_label(copied_actor),
                _class_name(copied_actor),
                ";".join(copied_assets)
                or "<component settings only>",
            )
        )

    expected_count = len(included)
    source_level = source_actors[0].get_outer()
    del source_actor
    del included
    del excluded
    del source_actors
    gc.collect()
    if not unreal.EditorLevelUtils.remove_level_from_world(
        source_level, True, True
    ):
        raise RuntimeError(
            "Could not remove temporary source level {}".format(
                scene["source_world"]
            )
        )
    if len(copied_actors) != expected_count:
        raise RuntimeError(
            "[{}] cloned {} of {} requested actors".format(
                scene["key"], len(copied_actors), expected_count
            )
        )
    return copied_actors


def _binding_display_name(binding):
    try:
        return str(binding.get_display_name())
    except Exception:
        return str(
            unreal.MovieSceneBindingExtensions.get_display_name(binding)
        )


def _bind_sequence_actor_by_label(scene, sequence_actor, sequence, actors):
    rebound = unreal.StageSceneMergeLibrary.rebind_level_sequence_actors_by_label(
        sequence_actor, actors
    )
    for binding in unreal.MovieSceneSequenceExtensions.get_bindings(sequence):
        label = _binding_display_name(binding)
        if any(_actor_label(actor) == label for actor in actors):
            unreal.log(
                "[{}] rebound direct sequence-asset binding '{}'".format(
                    scene["key"], label
                )
            )
    return rebound


def _validate_direct_sequence_bindings(scene, sequence, actors, world):
    actors_by_label = {}
    for actor in actors:
        actors_by_label.setdefault(_actor_label(actor), []).append(actor)

    resolved_count = 0
    for binding in unreal.MovieSceneSequenceExtensions.get_bindings(sequence):
        label = _binding_display_name(binding)
        candidates = actors_by_label.get(label, [])
        if not candidates:
            continue
        if len(candidates) != 1:
            raise RuntimeError(
                "[{}] binding '{}' has {} matching actors".format(
                    scene["key"], label, len(candidates)
                )
            )
        resolved = list(
            unreal.MovieSceneSequenceExtensions.locate_bound_objects(
                sequence, binding, world
            )
        )
        if resolved != candidates:
            raise RuntimeError(
                "[{}] direct binding '{}' resolved to {}, expected {}".format(
                    scene["key"],
                    label,
                    [obj.get_path_name() for obj in resolved],
                    [obj.get_path_name() for obj in candidates],
                )
            )
        resolved_count += 1

    if resolved_count != scene["expected_actor_bindings"]:
        raise RuntimeError(
            "[{}] resolved {} direct actor bindings; expected {}".format(
                scene["key"],
                resolved_count,
                scene["expected_actor_bindings"],
            )
        )
    return resolved_count


def _merge_scene(scene, target_world):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    copied_actors = _copy_streamed_scene(scene, target_world)

    copied_sequence = _copy_sequence(scene)

    sequence_actor = actor_subsystem.spawn_actor_from_class(
        unreal.LevelSequenceActor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if not sequence_actor:
        raise RuntimeError(
            "[{}] could not create LevelSequenceActor".format(scene["key"])
        )
    sequence_actor.set_actor_label(scene["sequence_actor_label"], True)
    sequence_actor.set_folder_path(scene["root_folder"] + "/Playback")
    sequence_actor.set_editor_property("is_spatially_loaded", False)
    sequence_actor.set_sequence(copied_sequence)
    rebound_count = _bind_sequence_actor_by_label(
        scene, sequence_actor, copied_sequence, copied_actors
    )
    if rebound_count != scene["expected_actor_bindings"]:
        raise RuntimeError(
            "[{}] rebound {} actor bindings; expected {}".format(
                scene["key"],
                rebound_count,
                scene["expected_actor_bindings"],
            )
        )
    scene_tag = "ImportedScene_{}".format(scene["key"])
    _add_tag(sequence_actor, scene_tag)

    rig = actor_subsystem.spawn_actor_from_class(
        unreal.StageContainedSceneRig,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if not rig:
        raise RuntimeError(
            "[{}] could not create StageContainedSceneRig".format(scene["key"])
        )
    rig.set_actor_label(scene["rig_label"], True)
    rig.set_folder_path(scene["root_folder"])
    rig.set_editor_property("is_spatially_loaded", False)
    rig.set_editor_property("scene_rig_id", scene["key"])
    rig.set_editor_property("included", True)
    rig.set_editor_property("start_active", False)
    rig.set_editor_property("use_built_in_playback_controls", True)
    rig.set_editor_property("contained_actors", copied_actors + [sequence_actor])
    rig.add_managed_level_sequence(sequence_actor)
    rig.auto_assign_attached_playback_content()
    _add_tag(rig, scene_tag)

    unreal.EditorAssetLibrary.save_loaded_asset(copied_sequence, False)
    unreal.log(
        "[{}] merged actors={} rebound_bindings={} lights={} effects={} audio={}".format(
            scene["key"],
            len(copied_actors),
            rebound_count,
            len(rig.get_editor_property("managed_light_actors")),
            len(rig.get_editor_property("managed_effect_actors")),
            len(rig.get_editor_property("managed_audio_actors")),
        )
    )
    return len(copied_actors)


def _load_all_world_partition_actors():
    result = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    success = True
    actor_descs = result
    if isinstance(result, tuple):
        success_values = [item for item in result if isinstance(item, bool)]
        collection_values = [
            item
            for item in result
            if not isinstance(item, bool) and hasattr(item, "__iter__")
        ]
        success = all(success_values) if success_values else True
        actor_descs = collection_values[-1] if collection_values else []

    actor_descs = list(actor_descs or [])
    if not success or not actor_descs:
        raise RuntimeError("Could not enumerate World Partition actor descriptors")

    guids = []
    for actor_desc in actor_descs:
        try:
            guids.append(actor_desc.get_editor_property("guid"))
        except Exception:
            guids.append(actor_desc.guid)
    unreal.WorldPartitionBlueprintLibrary.load_actors(guids)
    unreal.log(
        "Loaded {} World Partition actor descriptors for validation".format(
            len(guids)
        )
    )
    return actor_descs


def _synchronize_primary_visual_assets(scene, target_world, rig):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    target_actors = [
        actor
        for actor in rig.get_editor_property("contained_actors")
        if actor and _class_name(actor) != "LevelSequenceActor"
    ]
    targets_by_label = {}
    for actor in target_actors:
        targets_by_label.setdefault(_actor_label(actor), []).append(actor)

    before_paths = {
        actor.get_path_name() for actor in actor_subsystem.get_all_level_actors()
    }
    source_streaming = unreal.EditorLevelUtils.add_level_to_world(
        target_world,
        scene["source_world"],
        unreal.LevelStreamingAlwaysLoaded,
    )
    if not source_streaming:
        raise RuntimeError(
            "[{}] could not stream source for visual-asset verification".format(
                scene["key"]
            )
        )

    source_actors = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor.get_path_name() not in before_paths
    ]
    included = [
        actor for actor in source_actors if not _exclusion_reason(actor)
    ]
    checked_count = 0
    for source_actor in included:
        source_paths = sorted(
            str(path)
            for path in unreal.StageSceneMergeLibrary.get_primary_visual_asset_paths(
                source_actor
            )
        )
        if not source_paths:
            continue

        candidates = [
            actor
            for actor in targets_by_label.get(_actor_label(source_actor), [])
            if _class_name(actor) == _class_name(source_actor)
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                "[{}] visual source {} has {} target matches".format(
                    scene["key"],
                    _actor_label(source_actor),
                    len(candidates),
                )
            )
        target_actor = candidates[0]
        unreal.StageSceneMergeLibrary.copy_primary_visual_assets(
            source_actor, target_actor
        )
        target_paths = sorted(
            str(path)
            for path in unreal.StageSceneMergeLibrary.get_primary_visual_asset_paths(
                target_actor
            )
        )
        if target_paths != source_paths:
            raise RuntimeError(
                "[{}] visual assets differ for {}: source={} target={}".format(
                    scene["key"],
                    _actor_label(source_actor),
                    source_paths,
                    target_paths,
                )
            )
        checked_count += 1

    source_level = source_actors[0].get_outer()
    del source_actor
    del target_actor
    del included
    del source_actors
    gc.collect()
    if not unreal.EditorLevelUtils.remove_level_from_world(
        source_level, True, True
    ):
        raise RuntimeError(
            "[{}] could not remove visual verification source level".format(
                scene["key"]
            )
        )
    unreal.log(
        "[{}] synchronized and verified {} visual-asset actors".format(
            scene["key"], checked_count
        )
    )
    return checked_count


def _validate_saved_merge(expected_actor_counts):
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not level_subsystem.load_level(TARGET_WORLD):
        raise RuntimeError("Could not reopen {} for validation".format(TARGET_WORLD))

    _load_all_world_partition_actors()
    all_actors = list(actor_subsystem.get_all_level_actors())
    labels = {_actor_label(actor): actor for actor in all_actors}
    for scene in SCENES:
        rig = labels.get(scene["rig_label"])
        sequence_actor = labels.get(scene["sequence_actor_label"])
        if not rig or not sequence_actor:
            raise RuntimeError(
                "[{}] rig or sequence actor did not persist".format(scene["key"])
            )

        root = scene["root_folder"]
        copied = [
            actor
            for actor in all_actors
            if str(actor.get_folder_path()).startswith(root + "/")
            and _actor_label(actor) != scene["sequence_actor_label"]
        ]
        if len(copied) != expected_actor_counts[scene["key"]]:
            raise RuntimeError(
                "[{}] persisted actor count {} != expected {}".format(
                    scene["key"],
                    len(copied),
                    expected_actor_counts[scene["key"]],
                )
            )

        wing_count = sum(1 for actor in copied if _is_wing_actor(actor))
        if wing_count != scene["expected_wing_actors"]:
            raise RuntimeError(
                "[{}] persisted wing count {} != expected {}".format(
                    scene["key"],
                    wing_count,
                    scene["expected_wing_actors"],
                )
            )

        forbidden = [
            "{} ({})".format(_actor_label(actor), _exclusion_reason(actor))
            for actor in copied
            if _exclusion_reason(actor)
        ]
        if forbidden:
            raise RuntimeError(
                "[{}] forbidden actors persisted: {}".format(
                    scene["key"], ", ".join(forbidden)
                )
            )

        if sequence_actor.get_sequence() != unreal.load_asset(
            scene["target_sequence"]
        ):
            raise RuntimeError(
                "[{}] sequence actor points at the wrong asset".format(scene["key"])
            )

        if len(rig.get_editor_property("managed_level_sequences")) != 1:
            raise RuntimeError(
                "[{}] contained rig has the wrong sequence count".format(
                    scene["key"]
                )
            )

        if len(rig.get_editor_property("contained_actors")) != len(copied) + 1:
            raise RuntimeError(
                "[{}] contained-actor membership count is incorrect".format(
                    scene["key"]
                )
            )

        for property_name, expected_key in (
            ("managed_light_actors", "expected_managed_lights"),
            ("managed_effect_actors", "expected_managed_effects"),
            ("managed_audio_actors", "expected_managed_audio"),
        ):
            actual_count = len(rig.get_editor_property(property_name))
            expected_count = scene[expected_key]
            if actual_count != expected_count:
                raise RuntimeError(
                    "[{}] {} count {} != expected {}".format(
                        scene["key"],
                        property_name,
                        actual_count,
                        expected_count,
                    )
                )

        stage_actors = copied + [sequence_actor, rig]
        spatial = [
            _actor_label(actor)
            for actor in stage_actors
            if actor.get_editor_property("is_spatially_loaded")
        ]
        if spatial:
            raise RuntimeError(
                "[{}] imported actors are still spatially loaded: {}".format(
                    scene["key"], ", ".join(spatial)
                )
            )

        binding_overrides = sequence_actor.get_editor_property(
            "binding_overrides"
        )
        binding_data = (
            list(binding_overrides.get_editor_property("binding_data"))
            if binding_overrides
            else []
        )
        if len(binding_data) != scene["expected_actor_bindings"]:
            raise RuntimeError(
                "[{}] persisted binding overrides {} != expected {}".format(
                    scene["key"],
                    len(binding_data),
                    scene["expected_actor_bindings"],
                )
            )

        direct_binding_count = _validate_direct_sequence_bindings(
            scene,
            sequence_actor.get_sequence(),
            copied,
            unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem
            ).get_editor_world(),
        )

        unreal.log(
            "[{}] validation passed: actors={} wings={} overrides={} direct_bindings={} folder={} sequence={}".format(
                scene["key"],
                len(copied),
                wing_count,
                len(binding_data),
                direct_binding_count,
                root,
                scene["target_sequence"],
            )
        )


def merge(validate_after_save=True):
    _ensure_source_dependencies()
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level_subsystem.load_level(TARGET_WORLD):
        raise RuntimeError("Could not load target world {}".format(TARGET_WORLD))

    _assert_clean_target()
    target_world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    expected_actor_counts = {}
    for scene in SCENES:
        expected_actor_counts[scene["key"]] = _merge_scene(scene, target_world)

    if not level_subsystem.save_current_level():
        raise RuntimeError("Could not save {}".format(TARGET_WORLD))
    if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
        raise RuntimeError("One or more dirty packages could not be saved")

    if validate_after_save:
        _validate_saved_merge(expected_actor_counts)
        unreal.log("MERGE_SUCCESS")
    else:
        unreal.log(
            "MERGE_SAVED; run -ValidateImportedScenes in a fresh editor process"
        )


def _is_merge_managed_actor(actor):
    label = _actor_label(actor)
    folder = _actor_folder(actor)
    tags = {str(tag) for tag in actor.get_editor_property("tags")}
    for scene in SCENES:
        if label in {scene["rig_label"], scene["sequence_actor_label"]}:
            return True
        if folder == scene["root_folder"] or folder.startswith(
            scene["root_folder"] + "/"
        ):
            return True
        if "ImportedScene_{}".format(scene["key"]) in tags:
            return True
    return False


def reimport():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not level_subsystem.load_level(TARGET_WORLD):
        raise RuntimeError("Could not load target world {}".format(TARGET_WORLD))

    _load_all_world_partition_actors()
    existing = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if _is_merge_managed_actor(actor)
    ]
    unreal.log(
        "Removing {} remaining merge-managed actors before reimport".format(
            len(existing)
        )
    )
    if existing and not actor_subsystem.destroy_actors(existing):
        raise RuntimeError("Could not remove the previous imported scene actors")
    del existing
    gc.collect()
    unreal.SystemLibrary.collect_garbage()

    if not level_subsystem.save_current_level():
        raise RuntimeError("Could not save cleaned {}".format(TARGET_WORLD))
    if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
        raise RuntimeError("Could not save cleaned imported actor packages")

    for scene in SCENES:
        if unreal.EditorAssetLibrary.does_asset_exist(scene["target_sequence"]):
            if not unreal.EditorAssetLibrary.delete_asset(
                scene["target_sequence"]
            ):
                raise RuntimeError(
                    "Could not remove old target sequence {}".format(
                        scene["target_sequence"]
                    )
                )
            unreal.log(
                "Removed old target sequence {}".format(
                    scene["target_sequence"]
                )
            )

    gc.collect()
    unreal.SystemLibrary.collect_garbage()
    # Deleting and recreating a sequence package under the same name leaves a
    # stale "missing package" entry in this editor process's loader cache.
    # Validation is therefore intentionally performed by a fresh commandlet.
    merge(validate_after_save=False)
    unreal.log("FULL_WING_REIMPORT_SAVED")


def repair_and_validate_existing_merge():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not level_subsystem.load_level(TARGET_WORLD):
        raise RuntimeError("Could not load target world {}".format(TARGET_WORLD))

    _load_all_world_partition_actors()
    labels = {
        _actor_label(actor): actor
        for actor in actor_subsystem.get_all_level_actors()
    }
    for scene in SCENES:
        rig = labels.get(scene["rig_label"])
        sequence_actor = labels.get(scene["sequence_actor_label"])
        if not rig:
            raise RuntimeError(
                "[{}] could not load contained-scene rig".format(scene["key"])
            )
        if not sequence_actor:
            raise RuntimeError(
                "[{}] could not load Level Sequence Actor".format(scene["key"])
            )
        copied_actors = [
            actor
            for actor in rig.get_editor_property("contained_actors")
            if actor and _class_name(actor) != "LevelSequenceActor"
        ]
        rebound_count = _bind_sequence_actor_by_label(
            scene,
            sequence_actor,
            sequence_actor.get_sequence(),
            copied_actors,
        )
        if rebound_count != scene["expected_actor_bindings"]:
            raise RuntimeError(
                "[{}] repaired {} bindings; expected {}".format(
                    scene["key"],
                    rebound_count,
                    scene["expected_actor_bindings"],
                )
            )
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            sequence_actor.get_sequence(), False
        ):
            raise RuntimeError(
                "[{}] could not save repaired sequence asset".format(
                    scene["key"]
                )
            )

    _validate_saved_merge(
        {scene["key"]: scene["expected_actor_count"] for scene in SCENES}
    )
    unreal.log("MERGE_REPAIR_AND_VALIDATION_SUCCESS")


def validate_existing_merge():
    _validate_saved_merge(
        {scene["key"]: scene["expected_actor_count"] for scene in SCENES}
    )
    unreal.log("MERGE_READ_ONLY_VALIDATION_SUCCESS")


def reconstruction_probe():
    """Exercise the complete merge in memory without saving project packages."""

    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not level_subsystem.load_level(TARGET_WORLD):
        raise RuntimeError("Could not load probe target {}".format(TARGET_WORLD))
    target_world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()

    for scene in SCENES:
        actors = _copy_streamed_scene(scene, target_world)
        forbidden = [
            "{} ({})".format(_actor_label(actor), _exclusion_reason(actor))
            for actor in actors
            if _exclusion_reason(actor)
        ]
        if forbidden:
            raise RuntimeError(
                "[{}] probe reconstructed forbidden actors: {}".format(
                    scene["key"], ", ".join(forbidden)
                )
            )

        source_sequence = unreal.load_asset(scene["source_sequence"])
        sequence_actor = actor_subsystem.spawn_actor_from_class(
            unreal.LevelSequenceActor,
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            False,
        )
        if not source_sequence or not sequence_actor:
            raise RuntimeError(
                "[{}] probe could not create sequence playback".format(
                    scene["key"]
                )
            )
        sequence_actor.set_sequence(source_sequence)
        rebound_count = _bind_sequence_actor_by_label(
            scene, sequence_actor, source_sequence, actors
        )
        if rebound_count != scene["expected_actor_bindings"]:
            raise RuntimeError(
                "[{}] probe rebound {} actor bindings; expected {}".format(
                    scene["key"],
                    rebound_count,
                    scene["expected_actor_bindings"],
                )
            )

        rig = actor_subsystem.spawn_actor_from_class(
            unreal.StageContainedSceneRig,
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            False,
        )
        if not rig:
            raise RuntimeError(
                "[{}] probe could not create contained-scene rig".format(
                    scene["key"]
                )
            )
        rig.set_editor_property("scene_rig_id", scene["key"])
        rig.set_editor_property("is_spatially_loaded", False)
        rig.set_editor_property("included", True)
        rig.set_editor_property("start_active", False)
        rig.set_editor_property(
            "contained_actors", actors + [sequence_actor]
        )
        rig.add_managed_level_sequence(sequence_actor)
        rig.auto_assign_attached_playback_content()
        unreal.log(
            "[{}] full probe passed: actors={} bindings={} lights={} effects={} audio={}".format(
                scene["key"],
                len(actors),
                rebound_count,
                len(rig.get_editor_property("managed_light_actors")),
                len(rig.get_editor_property("managed_effect_actors")),
                len(rig.get_editor_property("managed_audio_actors")),
            )
        )

    unreal.log(
        "FULL_MERGE_PROBE_SUCCESS (in-memory only; no packages saved)"
    )


def _run():
    command_line = unreal.SystemLibrary.get_command_line()
    if "-ReimportImportedScenes" in command_line:
        reimport()
        return
    if "-ValidateImportedScenes" in command_line:
        validate_existing_merge()
        return
    if "-RepairAndValidateImportedScenes" in command_line:
        repair_and_validate_existing_merge()
        return
    if "-ProbeImportedSceneReconstruction" in command_line:
        reconstruction_probe()
        return
    if "-MergeImportedScenes" not in command_line:
        inventory()
        unreal.log(
            "Dry run only. Add -MergeImportedScenes after reviewing the inventory."
        )
        return
    merge()


_run()
