"""READ-ONLY editor probe for the Opening -> Passage 1 walk-in plan.

Loads the Show, Master, Opening sequence, level camera, and Geometry Cache as
asset data.  It does not open/evaluate Sequencer and has no package-write path.
The JSON report is ordinary evidence under Saved/CodexConductor.

Success marker: P01_OPENING_WALKIN_PROBE_OK
Failure marker: P01_OPENING_WALKIN_PROBE_STOPPED
"""

import json
import math
import os

import unreal


SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
OPENING_LABEL = "Opening — Curtain"
P01_LABEL = "Passage 1"
OPENING_CAMERA_LABEL = "Opening — Stalls Camera"
OPENING_DRAPE_LABEL = "Opening Drape (baked)"
CACHE_FPS = 30.0
LANDED_TOP_Z_M = 1.0


class ProbeStopped(Exception):
    """Internal control flow; failures are written to the report, not re-raised."""


def read_property(owner, python_name, report_name, missing):
    """Read one reflected property without allowing an Unreal lookup error out."""
    if owner is None:
        missing.append(
            {
                "property": report_name,
                "value": None,
                "reason": "owner is null",
            }
        )
        return None
    try:
        return owner.get_editor_property(python_name)
    except Exception as error:  # noqa: BLE001 - Unreal reports absent reflected fields this way
        missing.append(
            {
                "property": report_name,
                "value": None,
                "reason": str(error),
            }
        )
        return None


def require_value(value, report_name):
    if value is None:
        raise ProbeStopped("required value is null: " + report_name)
    return value


def frame_number_value(value, report_name, missing):
    if value is None:
        return None
    try:
        return int(value.value)
    except Exception as error:  # noqa: BLE001 - keep reflected value failures in the report
        missing.append(
            {
                "property": report_name,
                "value": None,
                "reason": str(error),
            }
        )
        return None


def asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def guid_text(value):
    return unreal.GuidLibrary.conv_guid_to_string(value) if value is not None else None


def census():
    return {
        "maps": sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        ),
        "content": sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ),
    }


def unwrap(result, count, label):
    if result is None:
        raise ProbeStopped(label + " returned None")
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        if not result[0]:
            raise ProbeStopped(label + " returned false")
        result = result[1:]
    if not isinstance(result, tuple) or len(result) != count:
        raise ProbeStopped("%s returned unexpected value %r" % (label, result))
    return result


def vector_row(value):
    return [float(value.x), float(value.y), float(value.z)]


def rotator_row(value):
    return [float(value.pitch), float(value.yaw), float(value.roll)]


def find_show_rows(show, missing):
    show_cues = read_property(show, "cues", "show.cues", missing)
    passage_settings = read_property(
        show, "passage_settings", "show.passage_settings", missing
    )
    require_value(show_cues, "show.cues")
    require_value(passage_settings, "show.passage_settings")
    cues = [
        cue
        for cue in show_cues
        if str(read_property(cue, "label", "cue.label", missing)) == OPENING_LABEL
    ]
    passages = [
        passage
        for passage in passage_settings
        if str(read_property(passage, "label", "passage_settings.label", missing))
        == P01_LABEL
    ]
    if len(cues) != 1 or len(passages) != 1:
        raise ProbeStopped(
            "expected one Opening cue and one P01 row, found %d/%d"
            % (len(cues), len(passages))
        )
    return cues[0], passages[0]


def find_p01_section(master, passage_guid, missing):
    wanted = guid_text(passage_guid)
    found = []
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for section in track.get_sections():
            section_guid = read_property(
                section,
                "passage_guid",
                "master.passage_section.passage_guid",
                missing,
            )
            if guid_text(section_guid) == wanted:
                found.append(section)
    if len(found) != 1:
        raise ProbeStopped("expected one P01 Master section, found %d" % len(found))
    return found[0]


def find_cut_camera(sequence, world, missing):
    cut_tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    active = [
        section
        for track in cut_tracks
        for section in track.get_sections()
        if section.is_active()
    ]
    playback_start = int(sequence.get_playback_start())
    playback_end = int(sequence.get_playback_end())
    covering = []
    for section in active:
        start = section.get_start_frame() if section.has_start_frame() else playback_start
        end = section.get_end_frame() if section.has_end_frame() else playback_end
        if start <= playback_start and end >= playback_end:
            covering.append(section)
    if len(covering) != 1:
        raise ProbeStopped("expected one active full-span Opening cut, found %d" % len(covering))
    cut_binding_id = covering[0].get_camera_binding_id()
    cut_guid = read_property(
        cut_binding_id,
        "guid",
        "opening.camera_cut.binding_id.guid",
        missing,
    )
    require_value(cut_guid, "opening.camera_cut.binding_id.guid")
    bindings = [binding for binding in sequence.get_bindings() if guid_text(binding.get_id()) == guid_text(cut_guid)]
    if len(bindings) != 1:
        raise ProbeStopped("Opening cut resolves to %d sequence bindings" % len(bindings))
    objects = list(sequence.locate_bound_objects(bindings[0], world))
    cameras = [value for value in objects if isinstance(value, unreal.CineCameraActor)]
    if len(objects) != 1 or len(cameras) != 1:
        raise ProbeStopped("Opening cut binding resolves to %r" % [value.get_path_name() for value in objects])
    camera = cameras[0]
    if camera.get_actor_label() != OPENING_CAMERA_LABEL:
        raise ProbeStopped("Opening cut camera is %r" % camera.get_actor_label())
    return covering[0], bindings[0], camera


def cache_evidence(sequence, tick_rate, here, missing):
    bindings = [binding for binding in sequence.get_bindings() if str(binding.get_display_name()) == OPENING_DRAPE_LABEL]
    if len(bindings) != 1:
        raise ProbeStopped("expected one Opening drape binding, found %d" % len(bindings))
    tracks = [
        track
        for track in bindings[0].get_tracks()
        if track.get_class().get_name() == "MovieSceneGeometryCacheTrack"
    ]
    if len(tracks) != 1:
        raise ProbeStopped("expected one Opening Geometry Cache track, found %d" % len(tracks))
    sections = sorted(tracks[0].get_sections(), key=lambda section: section.get_start_frame())
    if len(sections) < 2:
        raise ProbeStopped("Opening Geometry Cache track has fewer than two sections")
    rows = []
    assets = []
    for section_index, section in enumerate(sections):
        prefix = "opening.geometry_cache.sections[%d]" % section_index
        params = read_property(section, "params", prefix + ".params", missing)
        cache = read_property(
            params,
            "geometry_cache_asset",
            prefix + ".params.geometry_cache_asset",
            missing,
        )
        start_offset = read_property(
            params,
            "start_frame_offset",
            prefix + ".params.start_frame_offset",
            missing,
        )
        end_offset = read_property(
            params,
            "end_frame_offset",
            prefix + ".params.end_frame_offset",
            missing,
        )
        if cache is not None:
            assets.append(cache)
        rows.append(
            {
                "range": [int(section.get_start_frame()), int(section.get_end_frame())],
                "asset": asset_id(cache),
                "start_offset_tick": frame_number_value(
                    start_offset, prefix + ".params.start_frame_offset.value", missing
                ),
                "end_offset_tick": frame_number_value(
                    end_offset, prefix + ".params.end_frame_offset.value", missing
                ),
            }
        )
    unique_assets = {asset_id(value) for value in assets}
    if len(unique_assets) != 1:
        raise ProbeStopped("Opening sections reference cache set %r" % sorted(unique_assets))
    cache = assets[0]
    import_data = read_property(
        cache,
        "asset_import_data",
        "opening.geometry_cache.asset_import_data",
        missing,
    )
    source_filename = import_data.get_first_filename() if import_data is not None else None
    source = os.path.basename(source_filename) if source_filename else None
    stem = cache.get_name() + "_"
    if source and source.startswith(stem) and source.endswith(".abc"):
        bake_id = source[len(stem):-4]
    elif source == "CurtainDrop_Opening_final2.abc":
        bake_id = "final2_stage_v2"
    else:
        bake_id = None
    result = {
        "cache": asset_id(cache),
        "import_source": source,
        "bake_id": bake_id,
        "sections": rows,
        "release_frame": None,
        "release_sequence_s": None,
        "landed_bake_frame": None,
        "landed_s": None,
        "pile_route_extent_cm": None,
        "notes": [],
    }
    if bake_id is None:
        result["notes"].append("Import filename does not identify a DropBake record.")
        return result
    bake_path = os.path.join(os.path.dirname(here), "CodexSoftGoods", "DropBake", bake_id + ".json")
    if not os.path.isfile(bake_path):
        result["notes"].append("DropBake record is absent: " + bake_path)
        return result
    with open(bake_path, "r", encoding="utf-8") as handle:
        bake = json.load(handle)
    result["bake_path"] = bake_path
    result["release_frame"] = bake.get("release_frame")
    result["cache_show_start_frame"] = bake.get("show_start")
    rig_cm = bake.get("rig_limits", {}).get("unreal_cm", {})
    if "X_min" in rig_cm and "X_max" in rig_cm:
        result["pile_route_extent_cm"] = [float(rig_cm["X_min"]), float(rig_cm["X_max"])]
    release_frame = bake.get("release_frame")
    show_start = bake.get("show_start")
    if release_frame is None or show_start is None:
        result["notes"].append("release_frame/show_start is null; release and landed time stay null.")
        return result
    release_in_cache_s = (float(release_frame) - float(show_start)) / CACHE_FPS
    fall = rows[1]
    release_sequence_s = (
        fall["range"][0] / float(sequence.get_display_rate().numerator / sequence.get_display_rate().denominator)
        + max(0.0, release_in_cache_s - fall["start_offset_tick"] / tick_rate)
    )
    result["release_in_cache_s"] = release_in_cache_s
    result["release_sequence_s"] = release_sequence_s
    top_z = bake.get("top_z")
    frames = bake.get("frames")
    if not isinstance(top_z, list) or not top_z or frames is None:
        result["notes"].append("Bake has no top_z/frame series; landed time stays null.")
        return result
    first_top_frame = int(frames) - len(top_z) + 1
    landed_frame = next(
        (
            first_top_frame + index
            for index, value in enumerate(top_z)
            if first_top_frame + index >= int(release_frame) and float(value) <= LANDED_TOP_Z_M
        ),
        None,
    )
    if landed_frame is None:
        result["notes"].append("top_z never reaches the 1.0 m landed threshold.")
        return result
    landed_s = release_sequence_s + (landed_frame - int(release_frame)) / CACHE_FPS
    result["landed_bake_frame"] = landed_frame
    result["landed_s"] = landed_s
    result["landed_s_registry_0p1"] = round(landed_s, 1)
    return result


def main():
    here = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
    out_path = os.path.join(here, "opening_walkin_probe.json")
    report = {"ok": False, "errors": [], "missing_properties": []}
    before = None
    after = None
    completed = False
    sequence = None
    section_start_s = None
    arrival_speed = None
    cache = None

    try:
        # A read-only probe starts clean; the matching end assertion is in finally.
        before = census()
        report["dirty_before"] = before
        report["dirty_before_clean"] = not before["maps"] and not before["content"]
        if not report["dirty_before_clean"]:
            raise ProbeStopped("start census is not clean: %s" % json.dumps(before, sort_keys=True))

        project = os.path.normcase(
            os.path.normpath(
                unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
            )
        ).rstrip("\\/")
        if project != EXPECTED_PROJECT.rstrip("\\/"):
            raise ProbeStopped("wrong project directory %s" % project)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or asset_id(world) != EXPECTED_WORLD:
            raise ProbeStopped("wrong editor world %s" % asset_id(world))
        if editor.get_game_world() is not None:
            raise ProbeStopped("PIE/SIE is active")

        show = unreal.load_asset(SHOW)
        master = unreal.load_asset(MASTER)
        if show is None or master is None:
            raise ProbeStopped("Show or Master failed to load")
        opening_cue, p01 = find_show_rows(show, report["missing_properties"])
        opening_scene = read_property(
            opening_cue,
            "scene",
            "opening_cue.scene",
            report["missing_properties"],
        )
        require_value(opening_scene, "opening_cue.scene")
        sequence = read_property(
            opening_scene,
            "sequence",
            "opening_cue.scene.sequence",
            report["missing_properties"],
        )
        if sequence is None:
            raise ProbeStopped("Opening cue scene.sequence is null")
        p01_guid = read_property(
            p01,
            "passage_guid",
            "p01.passage_guid",
            report["missing_properties"],
        )
        require_value(p01_guid, "p01.passage_guid")
        display = sequence.get_display_rate()
        fps = display.numerator / float(display.denominator)
        tick = sequence.get_tick_resolution()
        sequence_tick_rate = tick.numerator / float(tick.denominator)
        master_tick = master.get_tick_resolution()
        master_tick_rate = master_tick.numerator / float(master_tick.denominator)
        section = find_p01_section(
            master, p01_guid, report["missing_properties"]
        )
        section_start_s = float(section.get_start_frame_seconds())
        start_tick, end_tick = unwrap(
            unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(
                show, p01_guid
            ),
            2,
            "get_passage_frame_range(P01)",
        )
        start_view, start_focal, start_focus = unwrap(
            unreal.InfinityStageCameraPilotLibrary.get_passage_camera_pose(
                show, p01_guid, int(start_tick)
            ),
            3,
            "get_passage_camera_pose(P01 start)",
        )
        one_display_tick = int(round(master_tick_rate / fps))
        next_view, next_focal, next_focus = unwrap(
            unreal.InfinityStageCameraPilotLibrary.get_passage_camera_pose(
                show,
                p01_guid,
                int(start_tick) + one_display_tick,
            ),
            3,
            "get_passage_camera_pose(P01 start + one display frame)",
        )
        arrival_speed = (
            next_view.translation - start_view.translation
        ).length() / (one_display_tick / master_tick_rate)
        cut, binding, camera = find_cut_camera(
            sequence, world, report["missing_properties"]
        )
        component = camera.get_cine_camera_component()
        focus_settings = read_property(
            component,
            "focus_settings",
            "opening.camera.component.focus_settings",
            report["missing_properties"],
        )
        manual_focus_distance = read_property(
            focus_settings,
            "manual_focus_distance",
            "opening.camera.component.focus_settings.manual_focus_distance",
            report["missing_properties"],
        )
        current_focal_length = read_property(
            component,
            "current_focal_length",
            "opening.camera.component.current_focal_length",
            report["missing_properties"],
        )
        camera_tags = read_property(
            camera,
            "tags",
            "opening.camera.tags",
            report["missing_properties"],
        )
        opening_label = read_property(
            opening_cue,
            "label",
            "opening_cue.label",
            report["missing_properties"],
        )
        cache = cache_evidence(
            sequence, sequence_tick_rate, here, report["missing_properties"]
        )
        report.update(
            {
                "opening": {
                    "cue_label": str(opening_label) if opening_label is not None else None,
                    "sequence": asset_id(sequence),
                    "playback_frames": [int(sequence.get_playback_start()), int(sequence.get_playback_end())],
                    "fps": fps,
                    "camera_cut_frames": [int(cut.get_start_frame()), int(cut.get_end_frame())],
                    "camera_binding": str(binding.get_display_name()),
                    "camera": {
                        "label": camera.get_actor_label(),
                        "path": camera.get_path_name(),
                        "tags": [str(tag) for tag in camera_tags] if camera_tags is not None else None,
                        "location_cm": vector_row(camera.get_actor_location()),
                        "rotation_deg": rotator_row(camera.get_actor_rotation()),
                        "focal_mm": float(current_focal_length) if current_focal_length is not None else None,
                        "focus_cm": float(manual_focus_distance) if manual_focus_distance is not None else None,
                    },
                },
                "p01": {
                    "master_section_range_s": [section_start_s, float(section.get_end_frame_seconds())],
                    "library_range_tick": [int(start_tick), int(end_tick)],
                    "start_tick_matches_section": abs(int(start_tick) / master_tick_rate - section_start_s) <= 1.0e-6,
                    "start_pose": {
                        "location_cm": vector_row(start_view.translation),
                        "rotation_deg": rotator_row(start_view.rotation.rotator()),
                        "focal_mm": float(start_focal),
                        "focus_cm": float(start_focus),
                    },
                    "next_frame_pose": {
                        "location_cm": vector_row(next_view.translation),
                        "rotation_deg": rotator_row(next_view.rotation.rotator()),
                        "focal_mm": float(next_focal),
                        "focus_cm": float(next_focus),
                    },
                    "arrival_speed_cm_s": float(arrival_speed),
                },
                "curtain": cache,
            }
        )
        completed = True
    except ProbeStopped as error:
        report["errors"].append(str(error))
    except Exception as error:  # noqa: BLE001 - report failure and still run the end census
        report["errors"].append("unexpected failure: " + str(error))
    finally:
        try:
            after = census()
            report["dirty_after"] = after
            report["dirty_after_clean"] = not after["maps"] and not after["content"]
            report["dirty_unchanged"] = before is not None and after == before
            if not report["dirty_after_clean"]:
                report["errors"].append(
                    "end census is not clean: %s" % json.dumps(after, sort_keys=True)
                )
            if before is not None and after != before:
                report["errors"].append("read-only probe changed the dirty census")
        except Exception as error:  # noqa: BLE001 - preserve the original failure too
            report["dirty_after"] = None
            report["dirty_after_clean"] = False
            report["dirty_unchanged"] = False
            report["errors"].append("end census failed: " + str(error))

        if report["missing_properties"]:
            missing_names = sorted(
                {entry["property"] for entry in report["missing_properties"]}
            )
            report["errors"].append(
                "reflected properties were unavailable: " + ", ".join(missing_names)
            )
        report["ok"] = completed and not report["errors"]
        if report["errors"]:
            report["error"] = "; ".join(report["errors"])
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
        if report["ok"]:
            unreal.log(
                "P01_OPENING_WALKIN_PROBE_OK|sequence=%s|playback=%s|p01_start_s=%.6f|arrival_speed_cm_s=%.6f|landed_s=%s|census=%s"
                % (
                    asset_id(sequence),
                    report["opening"]["playback_frames"],
                    section_start_s,
                    arrival_speed,
                    cache.get("landed_s"),
                    json.dumps(after, sort_keys=True),
                )
            )
        else:
            unreal.log_error(
                "P01_OPENING_WALKIN_PROBE_STOPPED|" + report.get("error", "unknown failure")
            )


main()
