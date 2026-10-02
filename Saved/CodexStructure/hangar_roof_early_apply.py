"""Move hangar roof closure to landing and follow it immediately with the lattice.

Dry run is the default.  HANGAR_ROOF_EARLY_APPLY records and backs up only the
rise sequences whose roof/lattice keys still match the declared 2 October
state, rekeys only those two mechanism channels, verifies the exact dirty
package set, and saves only those assets.  HANGAR_ROOF_EARLY_REVERT requires
the recorded applied state and restores the recorded keys.

The script never opens or evaluates Sequencer.  Clearance is calculated from
the static-mesh bounds in the landed actor hierarchy while analytically
rotating the roof hinge over the proposed window.  plan_scene() is deliberately
Unreal-free for test_hangar_roof_early_plan.py.
"""
import copy
import datetime
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
RISE_ROOT = "/Game/InfinityStage/RigAtmos"
FPS = 30.0
LANDING_S = 4.1261
OLD_ROOF_START_S = 6.6261
OLD_ROOF_END_S = 12.6261
OLD_LATTICE_START_S = 12.6261
OLD_LATTICE_END_S = 16.6261
NEW_ROOF_START_S = LANDING_S
NEW_ROOF_END_S = 8.6261
NEW_LATTICE_START_S = NEW_ROOF_END_S
NEW_LATTICE_END_S = 12.6261
AUTOMATION_TEST = "InfinityStage.Editor.SavedMasterMatchesShow"

STANDARD_ROOF = [[0.0, -90.0], [OLD_ROOF_START_S, -90.0], [OLD_ROOF_END_S, 0.0]]
STANDARD_LATTICE = [[0.0, 2800.0], [OLD_LATTICE_START_S, 2800.0], [OLD_LATTICE_END_S, 1200.0]]

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexStructure",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "hangar_roof_early_record.json")


def _plain_keys(keys):
    if keys is None:
        return None
    return [[float(time_s), float(value)] for time_s, value in keys]


def _keys_match(got, wanted, fps=FPS, value_tolerance=1e-3):
    if got is None or wanted is None:
        return got is None and wanted is None
    if len(got) != len(wanted):
        return False
    time_tolerance = 1.0 / float(fps) + 1e-9
    return all(
        abs(float(gt) - float(wt)) <= time_tolerance
        and abs(float(gv) - float(wv)) <= value_tolerance
        for (gt, gv), (wt, wv) in zip(got, wanted)
    )


def state_mismatches(got, wanted, fps=FPS):
    return [
        role
        for role in ("root_pitch", "roof_pitch", "lattice_fly_z")
        if not _keys_match(got.get(role), wanted.get(role), fps)
    ]


def plan_scene(
    before,
    fps=FPS,
    landing_s=LANDING_S,
    roof_start_s=NEW_ROOF_START_S,
    roof_end_s=NEW_ROOF_END_S,
    lattice_start_s=NEW_LATTICE_START_S,
    lattice_end_s=NEW_LATTICE_END_S,
):
    """Validate the declared current shape and return a mechanism-only plan."""
    if not isinstance(before, dict):
        raise ValueError("before must be an object")
    missing = [role for role in ("root_pitch", "roof_pitch", "lattice_fly_z") if role not in before]
    if missing:
        raise ValueError("before is missing: " + ", ".join(missing))

    original = {
        "root_pitch": _plain_keys(before["root_pitch"]),
        "roof_pitch": _plain_keys(before["roof_pitch"]),
        "lattice_fly_z": _plain_keys(before["lattice_fly_z"]),
    }
    if original["roof_pitch"] is None:
        return {
            "action": "skip",
            "reason": "no roof hinge; lattice-only sequence is left unchanged",
            "before": copy.deepcopy(original),
            "after": copy.deepcopy(original),
        }

    landing_s = float(landing_s)
    roof_start_s = float(roof_start_s)
    roof_end_s = float(roof_end_s)
    lattice_start_s = float(lattice_start_s)
    lattice_end_s = float(lattice_end_s)
    epsilon = 1e-9
    if roof_start_s < landing_s - epsilon:
        raise ValueError(f"roof starts before landing: roof={roof_start_s}, landing={landing_s}")
    if roof_end_s <= roof_start_s:
        raise ValueError(f"invalid roof window: {roof_start_s} -> {roof_end_s}")
    if lattice_start_s < roof_end_s - epsilon:
        raise ValueError(
            f"lattice overlaps roof: roof ends {roof_end_s}, lattice starts {lattice_start_s}"
        )
    if lattice_end_s <= lattice_start_s:
        raise ValueError(f"invalid lattice window: {lattice_start_s} -> {lattice_end_s}")

    bad = []
    if not _keys_match(original["roof_pitch"], STANDARD_ROOF, fps):
        bad.append("roof_pitch")
    if not _keys_match(original["lattice_fly_z"], STANDARD_LATTICE, fps):
        bad.append("lattice_fly_z")
    if bad:
        actual = {role: original[role] for role in bad}
        expected = {
            "roof_pitch": STANDARD_ROOF,
            "lattice_fly_z": STANDARD_LATTICE,
        }
        raise ValueError(
            "current keys do not match the declared 2 October state within one frame: "
            f"roles={bad}, actual={json.dumps(actual, sort_keys=True)}, "
            f"expected={json.dumps({role: expected[role] for role in bad}, sort_keys=True)}"
        )

    after = copy.deepcopy(original)
    after["roof_pitch"] = [
        original["roof_pitch"][0],
        [roof_start_s, original["roof_pitch"][1][1]],
        [roof_end_s, original["roof_pitch"][2][1]],
    ]
    after["lattice_fly_z"] = [
        original["lattice_fly_z"][0],
        [lattice_start_s, original["lattice_fly_z"][1][1]],
        [lattice_end_s, original["lattice_fly_z"][2][1]],
    ]
    return {
        "action": "include",
        "reason": "roof and lattice match the standard current shape",
        "before": original,
        "after": after,
    }


if unreal is not None:
    def fail(run, message):
        unreal.log_error(f"HANGAR_ROOF_EARLY_STOPPED|run={run}|{message}")
        raise RuntimeError(message)


    def package_census():
        return {
            "dirty_maps": sorted(
                str(package.get_name())
                for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
            ),
            "dirty_content": sorted(
                str(package.get_name())
                for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
            ),
        }


    def keys_of(channel, fps):
        return [
            [key.get_time().frame_number.value / float(fps), float(key.get_value())]
            for key in channel.get_keys()
        ]


    def interpolation_matches(channel, expected):
        wanted = {"AUTO": "RCIM_CUBIC", "LINEAR": "RCIM_LINEAR"}[expected]
        keys = list(channel.get_keys())
        return bool(keys) and all(key.get_interpolation_mode().name == wanted for key in keys)


    def set_keys(channel, keys, fps, interpolation):
        for key in list(channel.get_keys()):
            channel.remove_key(key)
        mode = getattr(unreal.MovieSceneKeyInterpolation, interpolation)
        for time_s, value in keys:
            channel.add_key(
                unreal.FrameNumber(int(round(float(time_s) * float(fps)))),
                float(value),
                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                interpolation=mode,
            )


    def guid_text(guid):
        return str(unreal.GuidLibrary.conv_guid_to_string(guid))


    def _one_track_channel(binding, track_class, property_name, channel_index, run):
        found = []
        for track in binding.get_tracks():
            if not isinstance(track, track_class):
                continue
            if property_name is not None and str(track.get_property_name()) != property_name:
                continue
            for section in track.get_sections():
                channels = list(section.get_all_channels())
                if len(channels) > channel_index:
                    found.append(channels[channel_index])
        if len(found) != 1:
            fail(
                run,
                f"expected one {property_name or track_class.__name__} channel on "
                f"{binding.get_display_name()}, found {len(found)}",
            )
        return found[0]


    def discover_sequence(sequence, scene, run):
        labels = {
            "root": f"S{scene} Hangar Root",
            "roof": f"S{scene} Hangar Roof Hinge",
            "lattice": f"S{scene} Hangar Lattice Fly",
        }
        direct = {
            str(binding.get_display_name()): binding
            for binding in sequence.get_bindings()
            if str(binding.get_display_name()) in labels.values()
        }
        missing = [label for role, label in labels.items() if role != "roof" and label not in direct]
        if missing:
            fail(run, f"S{scene}: required bindings absent: {missing}")
        roof_binding = direct.get(labels["roof"])
        return {
            "channels": {
                "root_pitch": _one_track_channel(
                    direct[labels["root"]], unreal.MovieScene3DTransformTrack, None, 4, run
                ),
                "roof_pitch": None
                if roof_binding is None
                else _one_track_channel(
                    roof_binding, unreal.MovieScene3DTransformTrack, None, 4, run
                ),
                "lattice_fly_z": _one_track_channel(
                    direct[labels["lattice"]], unreal.MovieScene3DTransformTrack, None, 2, run
                ),
            },
            "bindings": list(sequence.get_bindings()),
        }


    def capture_state(discovery, fps):
        channels = discovery["channels"]
        return {
            "root_pitch": keys_of(channels["root_pitch"], fps),
            "roof_pitch": None
            if channels["roof_pitch"] is None
            else keys_of(channels["roof_pitch"], fps),
            "lattice_fly_z": keys_of(channels["lattice_fly_z"], fps),
        }


    def apply_state(discovery, state, fps):
        set_keys(discovery["channels"]["roof_pitch"], state["roof_pitch"], fps, "AUTO")
        set_keys(discovery["channels"]["lattice_fly_z"], state["lattice_fly_z"], fps, "AUTO")


    def section_ranges(sequence):
        rows = []
        for binding in sequence.get_bindings():
            for track_index, track in enumerate(binding.get_tracks()):
                for section_index, section in enumerate(track.get_sections()):
                    rows.append({
                        "binding": guid_text(binding.get_id()),
                        "track_index": track_index,
                        "track_class": track.get_class().get_name(),
                        "section_index": section_index,
                        "start_s": float(section.get_start_frame_seconds())
                        if section.has_start_frame()
                        else None,
                        "end_s": float(section.get_end_frame_seconds())
                        if section.has_end_frame()
                        else None,
                    })
        return rows


    def rise_assets(run):
        found = {}
        for value in unreal.EditorAssetLibrary.list_assets(
            RISE_ROOT, recursive=True, include_folder=False
        ):
            path = str(value).split(".", 1)[0]
            match = re.search(r"/LS_S(\d+)_HangarRise$", path)
            if match:
                found[int(match.group(1))] = path
        if not found:
            fail(run, f"no LS_S<N>_HangarRise assets found below {RISE_ROOT}")
        missing_core = [scene for scene in (1, 2, 3, 6) if scene not in found]
        if missing_core:
            fail(run, f"required rise assets absent for scenes {missing_core}")
        return dict(sorted(found.items()))


    def expected_dirty(paths):
        return {"dirty_maps": [], "dirty_content": sorted(paths)}


    def disk_asset(project, asset_path):
        return os.path.join(project, "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


    def backup_files(stamp, project, paths, record_path):
        backup = os.path.join(
            project, "Backups", "PreHangarRoofEarly-" + stamp.strftime("%Y%m%d-%H%M")
        )
        os.makedirs(backup, exist_ok=False)
        for path in paths:
            shutil.copy2(disk_asset(project, path), backup)
        shutil.copy2(record_path, backup)
        return backup


    def _all_level_actors(world):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


    def _one_actor(actors, label, run):
        found = [actor for actor in actors if str(actor.get_actor_label()) == label]
        if len(found) != 1:
            fail(run, f"expected one level actor {label!r}, found {len(found)}")
        return found[0]


    def _under(actor, ancestor):
        parent = actor.get_attach_parent_actor()
        while parent is not None:
            if parent == ancestor:
                return True
            parent = parent.get_attach_parent_actor()
        return False


    def _mesh_corners(component):
        bounds = component.static_mesh.get_bounds()
        origin, extent = bounds.origin, bounds.box_extent
        return [
            unreal.Vector(
                origin.x + sx * extent.x,
                origin.y + sy * extent.y,
                origin.z + sz * extent.z,
            )
            for sx in (-1.0, 1.0)
            for sy in (-1.0, 1.0)
            for sz in (-1.0, 1.0)
        ]


    def _aabb(points):
        return (
            [min(getattr(point, axis) for point in points) for axis in ("x", "y", "z")],
            [max(getattr(point, axis) for point in points) for axis in ("x", "y", "z")],
        )


    def _aabb_clearance(left, right):
        amin, amax = left
        bmin, bmax = right
        gaps = [max(bmin[i] - amax[i], amin[i] - bmax[i], 0.0) for i in range(3)]
        if any(gap > 0.0 for gap in gaps):
            return math.sqrt(sum(gap * gap for gap in gaps))
        overlaps = [min(amax[i], bmax[i]) - max(amin[i], bmin[i]) for i in range(3)]
        return -min(overlaps)


    def _auto_value(start, end, alpha):
        smooth = 3.0 * alpha * alpha - 2.0 * alpha * alpha * alpha
        return float(start) + (float(end) - float(start)) * smooth


    def clearance_for_scene(scene, actors, plan, run):
        """Conservative bounds sweep in root space; does not pose or mutate actors."""
        root = _one_actor(actors, f"S{scene} Hangar Root", run)
        roof_hinge = _one_actor(actors, f"S{scene} Hangar Roof Hinge", run)
        lattice_fly = _one_actor(actors, f"S{scene} Hangar Lattice Fly", run)
        left_hinge = _one_actor(actors, f"S{scene} Hangar Left Wall Hinge", run)
        right_hinge = _one_actor(actors, f"S{scene} Hangar Right Wall Hinge", run)
        roof_meshes = [
            actor
            for actor in actors
            if isinstance(actor, unreal.StaticMeshActor) and _under(actor, roof_hinge)
        ]
        lattice_meshes = [
            actor
            for actor in actors
            if isinstance(actor, unreal.StaticMeshActor) and _under(actor, lattice_fly)
        ]
        wall_meshes = [
            actor
            for actor in actors
            if isinstance(actor, unreal.StaticMeshActor)
            and (_under(actor, left_hinge) or _under(actor, right_hinge))
        ]
        if not roof_meshes or not lattice_meshes or not wall_meshes:
            fail(
                run,
                f"S{scene}: clearance geometry incomplete: roof={len(roof_meshes)}, "
                f"lattice={len(lattice_meshes)}, walls={len(wall_meshes)}",
            )

        root_world = root.get_actor_transform()
        hinge_world = roof_hinge.get_actor_transform()
        roof_local = []
        for actor in roof_meshes:
            component = actor.static_mesh_component
            if component.static_mesh is None:
                continue
            world = component.get_world_transform()
            roof_local.append((
                str(actor.get_actor_label()),
                [
                    hinge_world.inverse_transform_location(world.transform_location(corner))
                    for corner in _mesh_corners(component)
                ],
            ))

        lattice_relative_z = float(
            lattice_fly.root_component.get_editor_property("relative_location").z
        )
        parked_z = float(plan["before"]["lattice_fly_z"][1][1])
        parked_delta = parked_z - lattice_relative_z
        obstacles = []
        for kind, group in (("lattice", lattice_meshes), ("wall", wall_meshes)):
            for actor in group:
                component = actor.static_mesh_component
                if component.static_mesh is None:
                    continue
                world = component.get_world_transform()
                points = [
                    root_world.inverse_transform_location(world.transform_location(corner))
                    for corner in _mesh_corners(component)
                ]
                if kind == "lattice":
                    points = [unreal.Vector(point.x, point.y, point.z + parked_delta) for point in points]
                obstacles.append((kind, str(actor.get_actor_label()), _aabb(points)))

        rel_location = roof_hinge.root_component.get_editor_property("relative_location")
        rel_rotation = roof_hinge.root_component.get_editor_property("relative_rotation")
        rel_scale = roof_hinge.root_component.get_editor_property("relative_scale3d")
        start_s, start_pitch = plan["after"]["roof_pitch"][1]
        end_s, end_pitch = plan["after"]["roof_pitch"][2]
        sample_count = max(2, int(math.ceil((end_s - start_s) * FPS * 4.0)) + 1)
        best = {"lattice": (float("inf"), None), "wall": (float("inf"), None)}
        pitches = []
        max_radius = max(
            math.sqrt(point.x * point.x + point.y * point.y + point.z * point.z)
            for _label, points in roof_local
            for point in points
        )
        for index in range(sample_count):
            alpha = index / float(sample_count - 1)
            time_s = start_s + (end_s - start_s) * alpha
            pitch = _auto_value(start_pitch, end_pitch, alpha)
            pitches.append(pitch)
            hinge_to_root = unreal.Transform(
                location=rel_location,
                rotation=unreal.Rotator(
                    roll=rel_rotation.roll, pitch=pitch, yaw=rel_rotation.yaw
                ),
                scale=rel_scale,
            )
            for roof_label, points in roof_local:
                roof_box = _aabb([hinge_to_root.transform_location(point) for point in points])
                for kind, obstacle_label, obstacle_box in obstacles:
                    clearance = _aabb_clearance(roof_box, obstacle_box)
                    if clearance < best[kind][0]:
                        best[kind] = (
                            clearance,
                            {
                                "time_s": round(time_s, 6),
                                "roof": roof_label,
                                "obstacle": obstacle_label,
                                "sample_clearance_cm": round(clearance, 3),
                            },
                        )
        max_step_radians = max(
            abs(math.radians(right - left)) for left, right in zip(pitches, pitches[1:])
        )
        between_sample_motion_bound = max_radius * max_step_radians
        result = {
            "method": "static-mesh local bounds; analytic roof hinge sweep at quarter-frame samples",
            "samples": sample_count,
            "parked_lattice_z_cm": parked_z,
            "between_sample_motion_bound_cm": round(between_sample_motion_bound, 3),
            "minimums": {},
        }
        for kind in ("lattice", "wall"):
            sample_clearance, detail = best[kind]
            conservative = sample_clearance - between_sample_motion_bound
            result["minimums"][kind] = {
                "conservative_clearance_cm": round(conservative, 3),
                **detail,
            }
            if conservative < 0.0:
                fail(
                    run,
                    f"S{scene}: proposed roof sweep intersects or cannot prove clearance from {kind}: "
                    f"{json.dumps(result['minimums'][kind], sort_keys=True)}",
                )
        return result


    def _channel_times(section, fps):
        rows = []
        for channel in section.get_all_channels():
            for key in channel.get_keys():
                rows.append((str(channel.get_name()), key.get_time().frame_number.value / fps))
        return rows


    def timed_light_exposure_rows(sequence, scene, fps):
        targets = {
            "old_roof_start": OLD_ROOF_START_S,
            "old_roof_end_lattice_start": OLD_ROOF_END_S,
            "old_lattice_end": OLD_LATTICE_END_S,
        }
        tolerance = 1.0 / fps + 1e-9
        rows = []
        for binding in sequence.get_bindings():
            label = str(binding.get_display_name())
            lowered = label.lower()
            if not any(token in lowered for token in ("light", "glow", "uplight", "practical", "exposure", "ppv")):
                continue
            for track in binding.get_tracks():
                for section in track.get_sections():
                    for channel, time_s in _channel_times(section, fps):
                        for event, target in targets.items():
                            if abs(time_s - target) <= tolerance:
                                rows.append({
                                    "scene": scene,
                                    "binding": label,
                                    "track": str(track.get_display_name()),
                                    "channel": channel,
                                    "time_s": time_s,
                                    "mechanism_event": event,
                                })
        return rows


    def _camera_times(sequence):
        fps = sequence.get_display_rate().numerator / float(sequence.get_display_rate().denominator)
        rows = []
        for binding in sequence.get_bindings():
            label = str(binding.get_display_name())
            lowered = label.lower()
            if "camera" not in lowered and not re.search(r"(^|[^a-z])cam([^a-z]|$)", lowered):
                continue
            for track in binding.get_tracks():
                for section in track.get_sections():
                    for channel, time_s in _channel_times(section, fps):
                        rows.append({
                            "binding": label,
                            "track": str(track.get_display_name()),
                            "channel": channel,
                            "time_s": time_s,
                            "kind": "key",
                        })
        for track in sequence.get_tracks():
            if "cameracut" not in str(track.get_class().get_name()).lower():
                continue
            for section in track.get_sections():
                if section.has_start_frame():
                    rows.append({
                        "binding": None,
                        "track": str(track.get_display_name()),
                        "channel": None,
                        "time_s": float(section.get_start_frame_seconds()),
                        "kind": "camera_cut_start",
                    })
                if section.has_end_frame():
                    rows.append({
                        "binding": None,
                        "track": str(track.get_display_name()),
                        "channel": None,
                        "time_s": float(section.get_end_frame_seconds()),
                        "kind": "camera_cut_end",
                    })
        return rows


    def _master_scene_offsets(master):
        offsets = {}
        for track in master.get_tracks():
            for section in track.get_sections():
                child = section.get_sequence() if hasattr(section, "get_sequence") else None
                path = child.get_path_name().split(".", 1)[0] if child else ""
                match = re.search(r"/LS_DevScene_0?(\d+)$", path)
                if match and section.has_start_frame():
                    offsets[int(match.group(1))] = float(section.get_start_frame_seconds())
        return offsets


    def camera_report(scenes, run):
        rows = []
        tolerance = 1.0
        master = unreal.load_asset(MASTER)
        if master is None:
            fail(run, f"Master sequence missing: {MASTER}")
        master_times = _camera_times(master)
        offsets = _master_scene_offsets(master)
        for scene in scenes:
            scene_path = f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{scene}"
            scene_sequence = unreal.load_asset(scene_path)
            if scene_sequence is None:
                fail(run, f"S{scene}: scene sequence missing: {scene_path}")
            for source_path, source_rows, offset in (
                (scene_path, _camera_times(scene_sequence), 0.0),
                (MASTER, master_times, offsets.get(scene)),
            ):
                if offset is None:
                    rows.append({
                        "scene": scene,
                        "asset": source_path,
                        "status": "scene subsection offset not found; Master camera proximity is UNCLEAR",
                    })
                    continue
                for event, local_target in (
                    ("old_roof_start", OLD_ROOF_START_S),
                    ("old_lattice_start", OLD_LATTICE_START_S),
                ):
                    target = offset + local_target
                    for item in source_rows:
                        if abs(item["time_s"] - target) <= tolerance:
                            rows.append({
                                "scene": scene,
                                "asset": source_path,
                                "event": event,
                                "target_s": target,
                                "delta_s": round(item["time_s"] - target, 6),
                                **item,
                            })
        return rows


    def log_scene(run, scene, path, plan, decision, interpolation, reports):
        unreal.log(
            f"HANGAR_ROOF_EARLY_SCENE|run={run}|S{scene}|asset={path}|decision={decision}|"
            f"reason={plan['reason']}|interpolation={json.dumps(interpolation, sort_keys=True)}|"
            f"before={json.dumps(plan['before'], sort_keys=True)}|"
            f"after={json.dumps(plan['after'], sort_keys=True)}|"
            f"timed_light_exposure={json.dumps(reports, sort_keys=True)}"
        )


    def assert_editor_guards(run):
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if (
            not world
            or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD
            or editor.get_game_world() is not None
        ):
            fail(run, "wrong world, or PIE/SIE is running")
        if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
            fail(run, "Sequencer is open")
        census = package_census()
        if census != {"dirty_maps": [], "dirty_content": []}:
            fail(run, f"packages already dirty: {census}")
        return editor, world


    def read_record(run):
        if not os.path.exists(RECORD):
            fail(run, "revert record is absent")
        with open(RECORD, encoding="utf-8") as handle:
            return json.load(handle)


    def revert_run(run):
        record = read_record(run)
        touched = [row["asset"] for row in record["included"]]
        loaded = {}
        for row in record["included"]:
            scene, path = int(row["scene"]), row["asset"]
            sequence = unreal.load_asset(path)
            if sequence is None:
                fail(run, f"S{scene}: recorded rise sequence missing: {path}")
            fps = sequence.get_display_rate().numerator / float(sequence.get_display_rate().denominator)
            discovery = discover_sequence(sequence, scene, run)
            got = capture_state(discovery, fps)
            bad = state_mismatches(got, row["after"], fps)
            if bad:
                fail(run, f"S{scene}: revert refused; live applied state drifted: {bad}")
            loaded[scene] = (sequence, discovery, fps, row)
        for scene, (sequence, discovery, fps, row) in loaded.items():
            apply_state(discovery, row["before"], fps)
            got = capture_state(discovery, fps)
            if state_mismatches(got, row["before"], fps):
                fail(run, f"S{scene}: revert read-back failed before save")
            if [float(sequence.get_playback_start_seconds()), float(sequence.get_playback_end_seconds())] != row["playback"]:
                fail(run, f"S{scene}: playback range changed during revert")
            if section_ranges(sequence) != row["section_ranges"]:
                fail(run, f"S{scene}: section ranges changed during revert")
        if package_census() != expected_dirty(touched):
            fail(run, f"revert dirty census is not exactly the touched rise assets: {package_census()}")
        for path in touched:
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                fail(run, f"revert save failed: {path}")
        final_census = package_census()
        if final_census != {"dirty_maps": [], "dirty_content": []}:
            fail(run, f"revert left dirty packages: {final_census}")
        os.replace(RECORD, RECORD + ".reverted")
        unreal.log(
            f"HANGAR_ROOF_EARLY_DONE|run={run}|reverted|assets={json.dumps(touched)}|"
            f"census={json.dumps(final_census, sort_keys=True)}"
        )


    def main():
        run = datetime.datetime.now().strftime("%H%M%S")
        apply = bool(globals().get("HANGAR_ROOF_EARLY_APPLY"))
        revert = bool(globals().get("HANGAR_ROOF_EARLY_REVERT"))
        if apply and revert:
            fail(run, "apply and revert modes are mutually exclusive")
        _editor, world = assert_editor_guards(run)
        if revert:
            revert_run(run)
            return
        if apply and os.path.exists(RECORD):
            fail(run, "record already exists; revert first")

        assets = rise_assets(run)
        actors = _all_level_actors(world)
        included = []
        skipped = []
        fatal = []
        loaded = {}
        for scene, path in assets.items():
            sequence = unreal.load_asset(path)
            if sequence is None:
                fail(run, f"S{scene}: rise sequence did not load: {path}")
            rate = sequence.get_display_rate()
            fps = rate.numerator / float(rate.denominator)
            discovery = discover_sequence(sequence, scene, run)
            before = capture_state(discovery, fps)
            interpolation = {
                "roof_pitch": None
                if discovery["channels"]["roof_pitch"] is None
                else interpolation_matches(discovery["channels"]["roof_pitch"], "AUTO"),
                "lattice_fly_z": interpolation_matches(
                    discovery["channels"]["lattice_fly_z"], "AUTO"
                ),
            }
            try:
                plan = plan_scene(before, fps=fps)
                if plan["action"] == "include" and not all(interpolation.values()):
                    raise ValueError(f"mechanism interpolation is not AUTO: {interpolation}")
            except ValueError as exc:
                plan = {
                    "action": "skip",
                    "reason": str(exc),
                    "before": before,
                    "after": copy.deepcopy(before),
                }
                if scene not in (4, 5):
                    fatal.append(f"S{scene}: {exc}")
            reports = timed_light_exposure_rows(sequence, scene, fps)
            decision = plan["action"]
            if decision == "include":
                row = {
                    "scene": scene,
                    "asset": path,
                    "fps": fps,
                    "playback": [
                        float(sequence.get_playback_start_seconds()),
                        float(sequence.get_playback_end_seconds()),
                    ],
                    "section_ranges": section_ranges(sequence),
                    "before": plan["before"],
                    "after": plan["after"],
                    "interpolation": interpolation,
                    "timed_light_exposure": reports,
                }
                included.append(row)
                loaded[scene] = (sequence, discovery, row)
            else:
                skipped.append({
                    "scene": scene,
                    "asset": path,
                    "reason": plan["reason"],
                    "keys": before,
                    "timed_light_exposure": reports,
                })
            log_scene(run, scene, path, plan, decision, interpolation, reports)

        cameras = camera_report(list(assets), run)
        unreal.log(
            f"HANGAR_ROOF_EARLY_REPORT_FOR_GARY|run={run}|camera_keys={json.dumps(cameras, sort_keys=True)}"
        )
        if fatal:
            fail(run, "precondition failures: " + " | ".join(fatal))
        if not included:
            fail(run, "no roof-bearing rise sequence matched the standard shape")

        clearance = {}
        for row in included:
            clearance[str(row["scene"])] = clearance_for_scene(
                row["scene"], actors, {"before": row["before"], "after": row["after"]}, run
            )
            unreal.log(
                f"HANGAR_ROOF_EARLY_CLEARANCE|run={run}|S{row['scene']}|"
                f"{json.dumps(clearance[str(row['scene'])], sort_keys=True)}"
            )

        if not apply:
            unreal.log(
                f"HANGAR_ROOF_EARLY_DRY_RUN_OK|run={run}|included="
                f"{json.dumps([row['scene'] for row in included])}|skipped={json.dumps(skipped, sort_keys=True)}|"
                f"camera_report={json.dumps(cameras, sort_keys=True)}|mutated=0|"
                f"census={json.dumps(package_census(), sort_keys=True)}"
            )
            return

        stamp = datetime.datetime.now()
        record = {
            "written": stamp.isoformat(timespec="seconds"),
            "run": run,
            "landing_s": LANDING_S,
            "included": included,
            "skipped": skipped,
            "camera_report_for_gary": cameras,
            "clearance": clearance,
            "automation_test_after_apply": AUTOMATION_TEST,
        }
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        touched = [row["asset"] for row in included]
        backup = backup_files(stamp, project, touched, RECORD)

        for scene, (sequence, discovery, row) in loaded.items():
            apply_state(discovery, row["after"], row["fps"])
            got = capture_state(discovery, row["fps"])
            if state_mismatches(got, row["after"], row["fps"]):
                fail(run, f"S{scene}: apply read-back failed before save")
            if got["root_pitch"] != row["before"]["root_pitch"]:
                fail(run, f"S{scene}: root keys changed")
            if [float(sequence.get_playback_start_seconds()), float(sequence.get_playback_end_seconds())] != row["playback"]:
                fail(run, f"S{scene}: playback range changed")
            if section_ranges(sequence) != row["section_ranges"]:
                fail(run, f"S{scene}: section ranges changed")
        if package_census() != expected_dirty(touched):
            fail(run, f"apply dirty census is not exactly the touched rise assets: {package_census()}")
        for path in touched:
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                fail(run, f"sequence save failed: {path}")
        final_census = package_census()
        if final_census != {"dirty_maps": [], "dirty_content": []}:
            fail(run, f"apply left dirty packages: {final_census}")
        unreal.SystemLibrary.execute_console_command(
            world, f"Automation RunTests {AUTOMATION_TEST}"
        )
        unreal.log(
            f"HANGAR_ROOF_EARLY_AUTOMATION_QUEUED|run={run}|test={AUTOMATION_TEST}|alone=true"
        )
        unreal.log(
            f"HANGAR_ROOF_EARLY_DONE|run={run}|applied|assets={json.dumps(touched)}|"
            f"backup={backup}|census={json.dumps(final_census, sort_keys=True)}"
        )


    main()
