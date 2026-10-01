"""NOTE (review, 30 Sep): the dry run exercises every LOOKUP but not the write-path calls (add_possessable,
add_track, set_property_name_and_path, add_key); those run for the first time on apply. If apply fails
mid-write it raises before saving, so Interaction 1 is left dirty and unsaved. Cure: run
revert_walkin_i1_p02.py (it removes the named tracks) and discard with a Don't-Save restart. Never save it half
written. Focus (changed 30 Sep after the first dry run measured 100000 -> 600 cm, far to near): it moves
linearly in DIOPTERS, so mid-walk it sits near the stage (~1190 cm against ~1360 cm). Linear in distance would hold
it at infinity and rack in only in the last ~0.4 s. Drafted by Codex from Look & camera's spec; reviewed.
"""
"""Key the Interaction 1 -> Passage 2 walk-in without touching the Master.

DRY_RUN is deliberately True. The dry run resolves every Unreal dependency,
plans and checks all keys, and logs every fifth frame while writing nothing.
Set DRY_RUN to False only after Soft goods has extended/refit the drape and the
Interaction sequence playback end is at least frame 638.
"""

DRY_RUN = True


def main():
    import datetime
    import json
    import math
    import os
    import shutil

    import unreal

    show_path = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
    sequence_path = "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy"
    expected_world = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
    expected_project = os.path.normcase(os.path.normpath("E:/PussStage"))
    track_name = "WalkIn (Look & camera)"
    camera_label = "Interaction 1 — Stalls Camera"
    camera_tags = ("InfinityStage.TransitionStalls", "InfinityStage.Mouth.P02")
    ticks_per_frame = 960
    minimum_end_frame = 638
    ease_s = 1.0
    landed_s = 20.3
    pile_edge_cm = 190.0

    def fail(message):
        full = "PUSS_WALKIN_FAILED|" + str(message)
        unreal.log_error(full)
        raise RuntimeError(full)

    def asset_id(value):
        return value.get_path_name().split(".", 1)[0] if value is not None else None

    def guid_text(value):
        return unreal.GuidLibrary.conv_guid_to_string(value)

    def unwrap(result, count, label):
        if result is None:
            fail(label + " returned false/None")
        if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
            if not result[0]:
                fail(label + " returned false")
            result = result[1:]
        if not isinstance(result, tuple) or len(result) != count:
            fail("%s returned unexpected value %r" % (label, result))
        return result

    def census():
        maps = sorted(package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
        content = sorted(package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        return {"maps": maps, "content": content}

    def all_named_tracks(sequence):
        found = []
        for track in sequence.get_tracks():
            if str(track.get_display_name()) == track_name:
                found.append(("sequence", track))
        for binding in sequence.get_bindings():
            for track in binding.get_tracks():
                if str(track.get_display_name()) == track_name:
                    found.append((str(binding.get_display_name()), track))
        return found

    try:
        project_dir = os.path.normcase(os.path.normpath(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        )).rstrip("\\/")
        if project_dir != expected_project.rstrip("\\/"):
            fail("wrong project directory %s (expected E:/PussStage)" % project_dir)

        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or asset_id(world) != expected_world:
            fail("wrong editor world %s" % asset_id(world))
        if editor.get_game_world() is not None:
            fail("PIE/SIE is active")

        show = unreal.load_asset(show_path)
        if show is None:
            fail("Show asset did not load")
        passages = [
            passage for passage in show.get_editor_property("passage_settings")
            if str(passage.get_editor_property("label")) == "Passage 2"
        ]
        if len(passages) != 1:
            fail("expected exactly one Passage 2 row, found %d" % len(passages))
        passage_guid = passages[0].get_editor_property("passage_guid")

        library = unreal.InfinityStageCameraPilotLibrary
        start_tick, passage_end_tick = unwrap(
            library.get_passage_frame_range(show, passage_guid), 2,
            "get_passage_frame_range(Passage 2)",
        )
        start_tick = int(start_tick)
        passage_end_tick = int(passage_end_tick)
        target_view, focal1, focus1 = unwrap(
            library.get_passage_camera_pose(show, passage_guid, start_tick), 3,
            "get_passage_camera_pose(Passage 2 start)",
        )
        next_view, next_focal, next_focus = unwrap(
            library.get_passage_camera_pose(show, passage_guid, start_tick + ticks_per_frame), 3,
            "get_passage_camera_pose(Passage 2 start + 960)",
        )

        show_tick = show.get_editor_property("tick_resolution")
        show_ticks_per_s = show_tick.numerator / float(show_tick.denominator)
        if abs(show_ticks_per_s - 24000.0) > 1.0e-6:
            fail("Show tick resolution is %.6f, expected 24000" % show_ticks_per_s)
        target_location = target_view.translation
        target_rotation = target_view.rotation.rotator()
        next_location = next_view.translation
        v_end = (next_location - target_location).length() / (ticks_per_frame / show_ticks_per_s)
        if not math.isfinite(v_end) or v_end <= 0.0:
            fail("measured Passage 2 arrival speed is invalid: %r" % v_end)

        sequence = unreal.load_asset(sequence_path)
        if sequence is None:
            fail("Interaction 1 sequence did not load")
        display_rate = sequence.get_display_rate()
        fps = display_rate.numerator / float(display_rate.denominator)
        if abs(fps - 25.0) > 1.0e-6:
            fail("Interaction 1 display rate is %.6f fps, expected 25" % fps)
        playback_start = int(sequence.get_playback_start())
        playback_end = int(sequence.get_playback_end())
        if playback_start != 0:
            fail("Interaction 1 playback start is %d, expected 0" % playback_start)
        if playback_end < minimum_end_frame:
            fail(
                "Interaction 1 playback end is frame %d; Soft goods must refit the drape to >= %d first"
                % (playback_end, minimum_end_frame)
            )
        end_s = playback_end / fps

        cut_tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
        cut_sections = [section for track in cut_tracks for section in track.get_sections() if section.is_active()]
        covering = []
        for section in cut_sections:
            section_start = section.get_start_frame() if section.has_start_frame() else playback_start
            section_end = section.get_end_frame() if section.has_end_frame() else playback_end
            if section_start <= playback_start and section_end >= playback_end:
                covering.append(section)
        if len(covering) != 1:
            fail("expected one active camera-cut section covering Interaction 1, found %d" % len(covering))
        cut_guid = covering[0].get_camera_binding_id().get_editor_property("guid")
        actor_bindings = [
            binding for binding in sequence.get_bindings()
            if guid_text(binding.get_id()) == guid_text(cut_guid)
        ]
        if len(actor_bindings) != 1:
            fail("camera-cut binding resolved to %d sequence bindings" % len(actor_bindings))
        actor_binding = actor_bindings[0]
        bound_objects = list(sequence.locate_bound_objects(actor_binding, world))
        cameras = [value for value in bound_objects if isinstance(value, unreal.CineCameraActor)]
        if len(bound_objects) != 1 or len(cameras) != 1:
            fail("camera-cut possessable resolves to %r" % [value.get_path_name() for value in bound_objects])
        camera = cameras[0]
        if camera.get_actor_label() != camera_label:
            fail("camera-cut actor label is %r, expected %r" % (camera.get_actor_label(), camera_label))
        missing_tags = [tag for tag in camera_tags if not camera.actor_has_tag(tag)]
        if missing_tags:
            fail("stalls camera is missing tags %r" % missing_tags)
        component = camera.get_cine_camera_component()
        if component is None:
            fail("stalls camera has no CineCameraComponent")

        component_bindings = []
        for child in actor_binding.get_child_possessables():
            objects = list(sequence.locate_bound_objects(child, world))
            if any(value.get_path_name() == component.get_path_name() for value in objects):
                component_bindings.append(child)
        if len(component_bindings) > 1:
            fail("camera has %d CineCameraComponent child bindings" % len(component_bindings))
        component_binding = component_bindings[0] if component_bindings else None

        existing = all_named_tracks(sequence)
        if existing:
            fail("%r track already exists on %r; revert first" % (track_name, [host for host, _ in existing]))

        seat_location = camera.get_actor_location()
        seat_rotation = camera.get_actor_rotation()
        seat_scale = camera.get_actor_scale3d()
        focus_settings = component.get_editor_property("focus_settings")
        focal0 = float(component.get_editor_property("current_focal_length"))
        focus0 = float(focus_settings.get_editor_property("manual_focus_distance"))
        seat = {
            "x": float(seat_location.x), "y": float(seat_location.y), "z": float(seat_location.z),
            "pitch": float(seat_rotation.pitch), "yaw": float(seat_rotation.yaw), "roll": float(seat_rotation.roll),
        }
        target = {
            "x": float(target_location.x), "y": float(target_location.y), "z": float(target_location.z),
            "pitch": float(target_rotation.pitch), "yaw": float(target_rotation.yaw), "roll": float(target_rotation.roll),
        }

        saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        planner_path = os.path.join(saved_dir, "CodexCameraPilot", "walkin_plan.py")
        if not os.path.isfile(planner_path):
            fail("planner is missing at %s" % planner_path)
        with open(planner_path, "r", encoding="utf-8") as planner_handle:
            planner_source = planner_handle.read()
        planner = {"__name__": "puss_walkin_plan", "__file__": planner_path}
        exec(compile(planner_source, planner_path, "exec"), planner)
        if "plan_walk" not in planner or "check_plan" not in planner:
            fail("planner does not export plan_walk and check_plan")
        keys, plan_report = planner["plan_walk"](
            seat, target, v_end, ease_s, end_s, fps,
            focal0, float(focal1), focus0, float(focus1), landed_s, pile_edge_cm,
        )
        failures = planner["check_plan"](keys, plan_report, target, v_end, landed_s, pile_edge_cm)
        if failures:
            fail("plan validation failed: %r" % failures)

        dirty_before = census()
        report = {
            "sequence": sequence_path,
            "playback": {"start": playback_start, "end": playback_end, "fps": fps, "end_s": end_s},
            "passage": {"start_tick": start_tick, "end_tick": passage_end_tick, "ticks_per_s": show_ticks_per_s},
            "camera": camera.get_actor_label(),
            "camera_binding": str(actor_binding.get_display_name()),
            "component_binding_present": component_binding is not None,
            "measured_v_end_cm_s": v_end,
            "next_pose_focal_mm": float(next_focal),
            "next_pose_focus_cm": float(next_focus),
            "plan": plan_report,
            "dirty_before": dirty_before,
        }

        if DRY_RUN:
            unreal.log("PUSS_WALKIN_KEY_TABLE|columns=frame,t,x,y,z,pitch,yaw,roll,focal,focus")
            for index, key in enumerate(keys):
                if index % 5 == 0 or index == len(keys) - 1:
                    unreal.log(
                        "PUSS_WALKIN_KEY|%d|%.5f|%.4f|%.4f|%.4f|%.5f|%.5f|%.5f|%.5f|%.5f"
                        % ((index,) + key)
                    )
            unreal.log("PUSS_WALKIN_REPORT|" + json.dumps(report, sort_keys=True, default=str))
            unreal.log(
                "PUSS_WALKIN_DRYRUN|keys=%d|start_s=%.6f|end_s=%.6f|distance_cm=%.3f|v_end_cm_s=%.3f|component_binding=%s"
                % (
                    len(keys), plan_report["start_s"], end_s, plan_report["distance_cm"], v_end,
                    "present" if component_binding is not None else "absent",
                )
            )
            return

        if dirty_before["maps"] or dirty_before["content"]:
            fail("apply requires zero dirty map and content packages: %r" % dirty_before)

        sequence_file = os.path.join(
            project_dir, "Content", *sequence_path[len("/Game/"):].split("/"),
        ) + ".uasset"
        if not os.path.isfile(sequence_file):
            fail("sequence file is missing: %s" % sequence_file)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = os.path.join(project_dir, "Backups", "PreWalkInI1-" + stamp)
        os.makedirs(backup_dir, exist_ok=False)
        backup_file = os.path.join(backup_dir, os.path.basename(sequence_file))
        copied_path = shutil.copy2(sequence_file, backup_file)
        if os.path.normcase(os.path.normpath(copied_path)) != os.path.normcase(os.path.normpath(backup_file)):
            fail("backup copy returned unexpected path %s" % copied_path)
        if not os.path.isfile(backup_file) or os.path.getsize(backup_file) != os.path.getsize(sequence_file):
            fail("sequence backup verification failed")

        if component_binding is None:
            component_binding = sequence.add_possessable(component)
            if component_binding is None or not component_binding.is_valid():
                fail("could not create the CineCameraComponent possessable")
            component_binding.set_parent(actor_binding)
        parent = component_binding.get_parent()
        if parent is None or not parent.is_valid() or guid_text(parent.get_id()) != guid_text(actor_binding.get_id()):
            fail("CineCameraComponent binding is not parented to the cut's actor binding")

        frame_count = len(keys)
        transform_track = actor_binding.add_track(unreal.MovieScene3DTransformTrack)
        if transform_track is None:
            fail("could not add the transform track")
        transform_track.set_display_name(track_name)
        transform_section = transform_track.add_section()
        if transform_section is None:
            fail("could not add the transform section")
        transform_section.set_range(playback_start, playback_end + 1)
        transform_channels = {str(channel.channel_name): channel for channel in transform_section.get_all_channels()}
        pose_channels = {
            "Location.X": 1, "Location.Y": 2, "Location.Z": 3,
            "Rotation.X": 6, "Rotation.Y": 4, "Rotation.Z": 5,
        }
        missing = sorted(set(pose_channels) - set(transform_channels))
        if missing:
            fail("transform section is missing channels %r" % missing)
        for name, value in (
            ("Scale.X", seat_scale.x), ("Scale.Y", seat_scale.y), ("Scale.Z", seat_scale.z),
        ):
            if name not in transform_channels:
                fail("transform section is missing %s" % name)
            transform_channels[name].set_default(float(value))
        for frame, key in enumerate(keys):
            if abs(key[0] * fps - frame) > 1.0e-6:
                fail("planner key %d is off the display-frame grid" % frame)
            for channel_name, key_index in pose_channels.items():
                made = transform_channels[channel_name].add_key(
                    unreal.FrameNumber(frame), float(key[key_index]),
                    time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                    interpolation=unreal.MovieSceneKeyInterpolation.LINEAR,
                )
                if made is None:
                    fail("add_key returned None for %s frame %d" % (channel_name, frame))

        def add_float_track(property_name, property_path, key_index):
            track = component_binding.add_track(unreal.MovieSceneFloatTrack)
            if track is None:
                fail("could not add float track for " + property_path)
            track.set_property_name_and_path(unreal.Name(property_name), property_path)
            track.set_display_name(track_name)
            section = track.add_section()
            if section is None:
                fail("could not add float section for " + property_path)
            section.set_range(playback_start, playback_end + 1)
            channels = list(section.get_all_channels())
            if len(channels) != 1:
                fail("%s produced %d channels" % (property_path, len(channels)))
            channel = channels[0]
            for frame, key in enumerate(keys):
                made = channel.add_key(
                    unreal.FrameNumber(frame), float(key[key_index]),
                    time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                    interpolation=unreal.MovieSceneKeyInterpolation.LINEAR,
                )
                if made is None:
                    fail("add_key returned None for %s frame %d" % (property_path, frame))
            return track

        focal_track = add_float_track("CurrentFocalLength", "CurrentFocalLength", 7)
        focus_track = add_float_track("ManualFocusDistance", "FocusSettings.ManualFocusDistance", 8)

        saved = unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
        if not saved:
            fail("save_loaded_asset returned False for Interaction 1")

        named_after = all_named_tracks(sequence)
        if len(named_after) != 3:
            fail("read-back found %d named tracks, expected 3" % len(named_after))
        if transform_track not in [track for _, track in named_after]:
            fail("read-back did not find the new transform track")
        if focal_track not in [track for _, track in named_after] or focus_track not in [track for _, track in named_after]:
            fail("read-back did not find both new float tracks")

        readback = {}
        expected_last = {
            "Location.X": keys[-1][1], "Location.Y": keys[-1][2], "Location.Z": keys[-1][3],
            "Rotation.X": keys[-1][6], "Rotation.Y": keys[-1][4], "Rotation.Z": keys[-1][5],
        }
        for channel_name, expected_value in expected_last.items():
            channel_keys = list(transform_channels[channel_name].get_keys())
            readback[channel_name] = {"count": len(channel_keys), "last": float(channel_keys[-1].get_value())}
            if len(channel_keys) != frame_count:
                fail("%s read back %d keys, expected %d" % (channel_name, len(channel_keys), frame_count))
            last_frame = channel_keys[-1].get_time().frame_number.value
            if last_frame != playback_end or abs(float(channel_keys[-1].get_value()) - expected_value) > 1.0e-4:
                fail("%s last key read-back failed" % channel_name)

        for label, track, expected_value in (
            ("focal", focal_track, keys[-1][7]), ("focus", focus_track, keys[-1][8]),
        ):
            sections = list(track.get_sections())
            if len(sections) != 1:
                fail("%s track read back %d sections" % (label, len(sections)))
            channels = list(sections[0].get_all_channels())
            if len(channels) != 1:
                fail("%s track read back %d channels" % (label, len(channels)))
            channel_keys = list(channels[0].get_keys())
            readback[label] = {"count": len(channel_keys), "last": float(channel_keys[-1].get_value())}
            if len(channel_keys) != frame_count:
                fail("%s read back %d keys, expected %d" % (label, len(channel_keys), frame_count))
            last_frame = channel_keys[-1].get_time().frame_number.value
            tolerance = 0.01 if label == "focal" else 0.1
            if last_frame != playback_end or abs(float(channel_keys[-1].get_value()) - expected_value) > tolerance:
                fail("%s last key read-back failed" % label)

        dirty_after = census()
        if dirty_after["maps"] or dirty_after["content"]:
            fail("packages remain dirty after the targeted sequence save: %r" % dirty_after)
        unreal.log(
            "PUSS_WALKIN_KEYED|keys=%d|end_frame=%d|v_end_cm_s=%.3f|backup=%s|readback=%s|dirty_after=%s"
            % (frame_count, playback_end, v_end, backup_dir, json.dumps(readback, sort_keys=True), json.dumps(dirty_after))
        )
    except Exception as error:
        if "PUSS_WALKIN_FAILED|" not in str(error):
            unreal.log_error("PUSS_WALKIN_FAILED|" + str(error))
        raise


main()
