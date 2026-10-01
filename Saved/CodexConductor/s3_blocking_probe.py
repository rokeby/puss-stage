"""Scene 3 blocking probe: asset-channel and level-state reads only.

No Sequencer UI, playback, evaluation, bound-object lookup, setters, or saves.
The only output is the required pair of log markers.
"""
import datetime
import json
import math
import os
import traceback

import unreal


def main():
    run = datetime.datetime.now().strftime("%H%M%S")

    def names(packages):
        return sorted(package.get_name() for package in packages)

    def census():
        return {
            "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        }

    def path_without_object(value):
        return value.get_path_name().split(".", 1)[0]

    def guid_text(value):
        return unreal.GuidLibrary.conv_guid_to_string(value)

    def vec(value, digits=3):
        return [round(float(value.x), digits), round(float(value.y), digits), round(float(value.z), digits)]

    def rot(value, digits=4):
        return {
            "pitch": round(float(value.pitch), digits),
            "yaw": round(float(value.yaw), digits),
            "roll": round(float(value.roll), digits),
        }

    def plain_transform(value):
        return {"location": vec(value.translation), "rotation": rot(value.rotation.rotator()), "scale": vec(value.scale3d, 6)}

    def frame_value(value):
        if hasattr(value, "frame_number"):
            return int(value.frame_number.value)
        if hasattr(value, "value"):
            return int(value.value)
        return int(value)

    def channel_name(channel):
        try:
            return str(channel.get_name())
        except Exception:
            return str(channel.channel_name)

    def key_rows(channel, fps):
        rows = []
        for key in channel.get_keys():
            frame = frame_value(key.get_time())
            value = key.get_value()
            try:
                value = float(value)
            except Exception:
                value = str(value)
            rows.append({"frame": frame, "seconds": round(frame / fps, 6), "value": value})
        rows.sort(key=lambda row: row["frame"])
        return rows

    def transform_track_rows(binding, sequence):
        fps = float(sequence.get_display_rate().numerator) / float(sequence.get_display_rate().denominator)
        rows = []
        for track in binding.get_tracks():
            if not isinstance(track, unreal.MovieScene3DTransformTrack):
                continue
            track_row = {"track": str(track.get_display_name()), "sections": []}
            for section in track.get_sections():
                section_row = {
                    "range_frames": [section.get_start_frame() if section.has_start_frame() else None,
                                     section.get_end_frame() if section.has_end_frame() else None],
                    "channels": [],
                }
                for channel in section.get_all_channels():
                    keys = key_rows(channel, fps)
                    channel_row = {"name": channel_name(channel), "key_count": len(keys)}
                    if keys:
                        channel_row["first"] = keys[0]
                        channel_row["last"] = keys[-1]
                    try:
                        if channel.has_default():
                            channel_row["default"] = float(channel.get_default())
                    except Exception:
                        pass
                    section_row["channels"].append(channel_row)
                track_row["sections"].append(section_row)
            rows.append(track_row)
        return rows

    def binding_kind_and_class(binding, spawnable_ids):
        identity = guid_text(binding.get_id())
        if identity in spawnable_ids:
            try:
                template = binding.get_object_template()
                return "spawnable", template.get_class().get_name() if template else None, template
            except Exception:
                return "spawnable", None, None
        try:
            klass = binding.get_possessed_object_class()
            return "possessable", klass.get_name() if klass else None, None
        except Exception:
            return "possessable", None, None

    def is_camera_binding(binding, class_name, template):
        if template is not None and isinstance(template, unreal.CameraActor):
            return True
        if class_name and "CameraActor" in class_name:
            return True
        name = str(binding.get_display_name()).lower()
        if ("camera" in name or "cam" in name) and binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
            return True
        try:
            for child in binding.get_child_possessables():
                child_class = child.get_possessed_object_class()
                if child_class and "CameraComponent" in child_class.get_name():
                    return True
        except Exception:
            pass
        return False

    def describe_sequence(sequence, world_cameras):
        fps = float(sequence.get_display_rate().numerator) / float(sequence.get_display_rate().denominator)
        bindings = list(sequence.get_bindings())
        binding_by_id = {guid_text(binding.get_id()): binding for binding in bindings}
        spawnable_ids = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
        camera_rows = []
        for binding in bindings:
            kind, class_name, template = binding_kind_and_class(binding, spawnable_ids)
            if not is_camera_binding(binding, class_name, template):
                continue
            name = str(binding.get_display_name())
            row = {
                "binding": name,
                "guid": guid_text(binding.get_id()),
                "kind": kind,
                "class": class_name,
                "transform_tracks": transform_track_rows(binding, sequence),
                "matching_level_actors": [
                    {"label": actor.get_actor_label(), "transform": plain_transform(actor.get_actor_transform())}
                    for actor in world_cameras if actor.get_actor_label() == name
                ],
            }
            if template is not None and isinstance(template, unreal.Actor):
                row["spawnable_template_transform"] = plain_transform(template.get_actor_transform())
            camera_rows.append(row)

        cuts = []
        for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
            for section in track.get_sections():
                binding_id = section.get_camera_binding_id().get_editor_property("guid")
                binding = binding_by_id.get(guid_text(binding_id))
                start = section.get_start_frame() if section.has_start_frame() else None
                end = section.get_end_frame() if section.has_end_frame() else None
                cuts.append({
                    "binding": str(binding.get_display_name()) if binding else None,
                    "binding_guid": guid_text(binding_id),
                    "range_frames": [start, end],
                    "range_seconds": [round(start / fps, 6) if start is not None else None,
                                      round(end / fps, 6) if end is not None else None],
                })

        nested = []
        seen_sections = set()
        for track in sequence.get_tracks():
            if not isinstance(track, (unreal.MovieSceneSubTrack, unreal.MovieSceneCinematicShotTrack)):
                continue
            for section in track.get_sections():
                child = section.get_sequence()
                if child is None:
                    continue
                token = (child.get_path_name(), section.get_start_frame(), section.get_end_frame())
                if token in seen_sections:
                    continue
                seen_sections.add(token)
                nested.append({
                    "track": str(track.get_display_name()),
                    "sequence": path_without_object(child),
                    "range_frames": [section.get_start_frame(), section.get_end_frame()],
                    "range_seconds": [round(section.get_start_frame() / fps, 6),
                                      round(section.get_end_frame() / fps, 6)],
                })
        return {
            "path": path_without_object(sequence),
            "display_rate": [sequence.get_display_rate().numerator, sequence.get_display_rate().denominator],
            "playback_frames": [sequence.get_playback_start(), sequence.get_playback_end()],
            "camera_bindings": camera_rows,
            "camera_cuts": cuts,
            "nested_sections": nested,
        }

    def describe_ls_clams_bindings(sequence):
        fps = float(sequence.get_display_rate().numerator) / float(sequence.get_display_rate().denominator)
        spawnable_ids = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
        rows = []
        for binding in sequence.get_bindings():
            kind, class_name, template = binding_kind_and_class(binding, spawnable_ids)
            track_rows = []
            location_key_rows = []
            animation_or_skeletal_only = True
            tracks = list(binding.get_tracks())
            for track in tracks:
                track_class = track.get_class().get_name()
                track_rows.append({
                    "name": str(track.get_display_name()),
                    "class": track_class,
                    "section_count": len(track.get_sections()),
                })
                lowered = (track_class + " " + str(track.get_display_name())).lower()
                if "animation" not in lowered and "skeletal" not in lowered:
                    animation_or_skeletal_only = False
                if not isinstance(track, unreal.MovieScene3DTransformTrack):
                    continue
                for section_index, section in enumerate(track.get_sections()):
                    for channel in section.get_all_channels():
                        name = channel_name(channel)
                        if not name.startswith("Location."):
                            continue
                        keys = key_rows(channel, fps)
                        if keys:
                            location_key_rows.append({
                                "track": str(track.get_display_name()),
                                "section_index": section_index,
                                "channel": name,
                                "first": keys[0],
                                "last": keys[-1],
                            })
            row = {
                "binding": str(binding.get_display_name()),
                "guid": guid_text(binding.get_id()),
                "kind": kind,
                "class": class_name,
                "tracks": track_rows,
                "has_transform_location_keys": bool(location_key_rows),
                "location_keys_first_last": location_key_rows,
                "only_animation_or_skeletal_tracks": bool(tracks) and animation_or_skeletal_only,
            }
            if template is not None:
                row["spawnable_template_class"] = template.get_class().get_name()
            rows.append(row)
        return {
            "path": path_without_object(sequence),
            "source": "LS_Clams LevelSequence asset bindings and channels only; no bound-object lookup or evaluation",
            "display_rate": [sequence.get_display_rate().numerator, sequence.get_display_rate().denominator],
            "bindings": rows,
        }

    def world_aabb(actor):
        origin, extent = actor.get_actor_bounds(False, True)
        minimum = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
        maximum = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
        return origin, extent, minimum, maximum

    def corners(minimum, maximum):
        return [unreal.Vector(x, y, z) for x in (minimum.x, maximum.x)
                for y in (minimum.y, maximum.y) for z in (minimum.z, maximum.z)]

    def bounds_from_points(points):
        return {
            "min": [round(min(point.x for point in points), 3),
                    round(min(point.y for point in points), 3),
                    round(min(point.z for point in points), 3)],
            "max": [round(max(point.x for point in points), 3),
                    round(max(point.y for point in points), 3),
                    round(max(point.z for point in points), 3)],
        }

    def actor_row(actor, dock):
        origin, extent, minimum, maximum = world_aabb(actor)
        dock_location = unreal.MathLibrary.inverse_transform_location(dock, actor.get_actor_location())
        dock_points = [unreal.MathLibrary.inverse_transform_location(dock, point) for point in corners(minimum, maximum)]
        parent = actor.get_attach_parent_actor()
        return {
            "label": actor.get_actor_label(),
            "class": actor.get_class().get_name(),
            "parent": parent.get_actor_label() if parent else None,
            "world_location": vec(actor.get_actor_location()),
            "world_rotation": rot(actor.get_actor_rotation()),
            "world_bounds": {"origin": vec(origin), "extent": vec(extent), "min": vec(minimum), "max": vec(maximum)},
            "dock_location": vec(dock_location),
            "dock_bounds": bounds_from_points(dock_points),
        }

    def transform_binding_map(sequence):
        return {str(binding.get_display_name()): binding for binding in sequence.get_bindings()
                if binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack)}

    def last_transform(binding, actor):
        parent = actor.get_attach_parent_actor()
        baseline = actor.root_component.get_relative_transform() if parent else actor.get_actor_transform()
        values = {
            "Location.X": float(baseline.translation.x), "Location.Y": float(baseline.translation.y),
            "Location.Z": float(baseline.translation.z), "Rotation.X": float(baseline.rotation.rotator().roll),
            "Rotation.Y": float(baseline.rotation.rotator().pitch), "Rotation.Z": float(baseline.rotation.rotator().yaw),
            "Scale.X": float(baseline.scale3d.x), "Scale.Y": float(baseline.scale3d.y), "Scale.Z": float(baseline.scale3d.z),
        }
        tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
            raise RuntimeError("%s has %d transform tracks / unexpected sections" % (actor.get_actor_label(), len(tracks)))
        for channel in tracks[0].get_sections()[0].get_all_channels():
            name = channel_name(channel)
            if name not in values:
                continue
            keys = list(channel.get_keys())
            if keys:
                keys.sort(key=lambda key: frame_value(key.get_time()))
                values[name] = float(keys[-1].get_value())
            else:
                try:
                    if channel.has_default():
                        values[name] = float(channel.get_default())
                except Exception:
                    pass
        return unreal.Transform(
            location=unreal.Vector(values["Location.X"], values["Location.Y"], values["Location.Z"]),
            rotation=unreal.Rotator(roll=values["Rotation.X"], pitch=values["Rotation.Y"], yaw=values["Rotation.Z"]),
            scale=unreal.Vector(values["Scale.X"], values["Scale.Y"], values["Scale.Z"]),
        )

    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or path_without_object(world) != "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice":
            raise RuntimeError("unexpected editor world: %s" % (world.get_path_name() if world else None))
        if editor.get_game_world() is not None:
            raise RuntimeError("PIE/SIE is active; probe refused")
        dirty_before = census()
        if dirty_before["maps"] or dirty_before["content"]:
            unreal.log_error("S3_BLOCKING_PROBE_STOPPED|run=%s|dirty_before=%s" %
                             (run, json.dumps(dirty_before, separators=(",", ":"))))
            return

        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        actors_by_label = {}
        for actor in actors:
            actors_by_label.setdefault(actor.get_actor_label(), []).append(actor)

        with open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                               "CodexStructure", "s3_pit_deck_record.json"), encoding="utf-8") as handle:
            pit_record = json.load(handle)
        dock_record = pit_record["dock"]
        dock = unreal.Transform(
            location=unreal.Vector(*dock_record["location"]),
            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(dock_record["yaw"])),
        )

        show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
        passage_rows = [row for row in show.get_editor_property("passage_settings")
                        if str(row.get_editor_property("label")) == "Passage 3"]
        if len(passage_rows) != 1:
            raise RuntimeError("expected one Show passage_settings row labelled Passage 3, found %d" % len(passage_rows))
        passage_guid = passage_rows[0].get_editor_property("passage_guid")
        library = unreal.InfinityStageCameraPilotLibrary

        def unwrap(result, count):
            if result is None:
                return None
            if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
                return result[1:] if result[0] else None
            return result

        frame_range = unwrap(library.get_passage_frame_range(show, passage_guid), 2)
        if frame_range is None:
            raise RuntimeError("Passage 3 has no compiled frame range")
        stop_frame = int(frame_range[1])
        camera_pose = unwrap(library.get_passage_camera_pose(show, passage_guid, stop_frame), 3)
        if camera_pose is None:
            raise RuntimeError("Passage 3 camera did not evaluate at compiled end frame %d" % stop_frame)
        camera_transform, focal_mm, focus_cm = camera_pose

        matching_passages = [actor for actor in actors if isinstance(actor, unreal.InfinityStagePassageActor)
                             and guid_text(actor.get_editor_property("passage_guid")) == guid_text(passage_guid)]
        if len(matching_passages) != 1:
            raise RuntimeError("expected one Passage 3 actor by passage_guid, found %d" % len(matching_passages))
        route = matching_passages[0].get_editor_property("route")
        route_length = float(route.get_spline_length())
        route_end = route.get_transform_at_distance_along_spline(
            route_length, unreal.SplineCoordinateSpace.WORLD, True)
        entry_cameras = [actor for actor in actors if isinstance(actor, unreal.CineCameraActor)
                         and actor.actor_has_tag("InfinityStage.SceneEntry")
                         and actor.get_actor_label().startswith("Scene 3 ")]

        world_cameras = [actor for actor in actors if isinstance(actor, unreal.CameraActor)]
        root_sequence = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
        queue = [root_sequence]
        sequence_rows = []
        sequence_assets = {}
        seen_paths = set()
        while queue:
            sequence = queue.pop(0)
            sequence_path = path_without_object(sequence)
            if sequence_path in seen_paths:
                continue
            seen_paths.add(sequence_path)
            sequence_assets[sequence_path] = sequence
            row = describe_sequence(sequence, world_cameras)
            sequence_rows.append(row)
            for nested in row["nested_sections"]:
                child = unreal.load_asset(nested["sequence"])
                if child is not None and isinstance(child, unreal.LevelSequence):
                    queue.append(child)

        ls_clams_matches = [sequence for path, sequence in sequence_assets.items()
                            if path.rsplit("/", 1)[-1] == "LS_Clams"]
        if len(ls_clams_matches) != 1:
            raise RuntimeError("expected exactly one nested LS_Clams asset, found %d" % len(ls_clams_matches))
        ls_clams_bindings = describe_ls_clams_bindings(ls_clams_matches[0])

        rise = unreal.load_asset("/Game/InfinityStage/RigAtmos/LS_S3_HangarRise")
        rise_bindings = transform_binding_map(rise)
        rise_key_rows = []
        for label, binding in sorted(rise_bindings.items()):
            if "Roof" in label or "Lattice" in label or label == "S3 Hangar Root":
                rise_key_rows.append({"binding": label, "transform_tracks": transform_track_rows(binding, rise)})

        requested_exact = [
            "Shore01_M56 Clam", "Shore02_F52 Clam", "Shore03_M59 Clam", "Shore04_F55 Clam",
            "Shore05_M53 Clam", "Shore06_F25 Clam", "Clam_Pedastal", "PointLight",
            "S3 Ghost Light", "S3 Ghost Light Stand", "S3 Hangar Deck", "S3 Hangar Far Wall",
            "S3 Hangar Left Wall", "S3 Hangar Right Wall", "S3 Hangar Roof",
            "S3 Hangar Lattice Beam 01", "S3 Hangar Lattice Beam 14",
        ]
        target_labels = list(requested_exact)
        target_labels += sorted(label for label in actors_by_label if label.startswith("S3 Strike"))
        missing = [label for label in requested_exact if len(actors_by_label.get(label, [])) != 1]
        target_rows = []
        for label in target_labels:
            matches = actors_by_label.get(label, [])
            if len(matches) == 1:
                target_rows.append(actor_row(matches[0], dock))

        pedestal_matches = actors_by_label.get("Clam_Pedastal", [])
        if len(pedestal_matches) != 1:
            raise RuntimeError("expected exactly one Clam_Pedastal, found %d" % len(pedestal_matches))
        pedestal_actor = pedestal_matches[0]
        _, _, pedestal_min, pedestal_max = world_aabb(pedestal_actor)
        search_min = pedestal_min
        search_max = unreal.Vector(pedestal_max.x, pedestal_max.y, pedestal_max.z + 50.0)

        def actor_clam_tokens(actor):
            tokens = [actor.get_actor_label(), actor.get_class().get_name(), actor.get_path_name()]
            for component in actor.get_components_by_class(unreal.StaticMeshComponent):
                mesh = component.get_editor_property("static_mesh")
                if mesh is not None:
                    tokens.append(mesh.get_path_name())
            for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
                try:
                    mesh = component.get_editor_property("skeletal_mesh_asset")
                    if mesh is not None:
                        tokens.append(mesh.get_path_name())
                except Exception:
                    pass
            return tokens

        nearby_rows = []
        clam_actors_on_pedestal = []
        shore_cast_labels = set(requested_exact[:6])
        for actor in actors:
            if actor == pedestal_actor:
                continue
            origin, _, actor_min, actor_max = world_aabb(actor)
            location = actor.get_actor_location()
            origin_inside = (search_min.x <= origin.x <= search_max.x
                             and search_min.y <= origin.y <= search_max.y
                             and search_min.z <= origin.z <= search_max.z)
            pivot_inside = (search_min.x <= location.x <= search_max.x
                            and search_min.y <= location.y <= search_max.y
                            and search_min.z <= location.z <= search_max.z)
            bounds_overlap = (actor_max.x >= search_min.x and actor_min.x <= search_max.x
                              and actor_max.y >= search_min.y and actor_min.y <= search_max.y
                              and actor_max.z >= search_min.z and actor_min.z <= search_max.z)
            if not (origin_inside or pivot_inside or bounds_overlap):
                continue
            tokens = actor_clam_tokens(actor)
            is_clam = (actor.get_actor_label() not in shore_cast_labels
                       and any("clam" in token.lower() for token in tokens))
            row = actor_row(actor, dock)
            row["search_match"] = {
                "origin_inside": origin_inside,
                "pivot_inside": pivot_inside,
                "bounds_overlap": bounds_overlap,
                "clam_name_or_asset_match": is_clam,
                "clam_match_tokens": [token for token in tokens if "clam" in token.lower()],
            }
            nearby_rows.append(row)
            if is_clam:
                clam_actors_on_pedestal.append(actor)
        nearby_rows.sort(key=lambda row: row["label"])
        clam_actors_on_pedestal.sort(key=lambda actor: actor.get_actor_label())
        if not clam_actors_on_pedestal:
            missing.append("clam actor within Clam_Pedastal world AABB extended +50 cm in Z")

        root_actor = actors_by_label.get("S3 Hangar Root", [None])[0]
        if root_actor is None:
            raise RuntimeError("S3 Hangar Root not found")
        final_cache = {}

        def final_actor_transform(actor):
            label = actor.get_actor_label()
            if label in final_cache:
                return final_cache[label]
            parent = actor.get_attach_parent_actor()
            local_or_world = last_transform(rise_bindings[label], actor) if label in rise_bindings else (
                actor.root_component.get_relative_transform() if parent else actor.get_actor_transform())
            value = unreal.MathLibrary.compose_transforms(local_or_world, final_actor_transform(parent)) if parent else local_or_world
            final_cache[label] = value
            return value

        def mesh_bounds_at(actor, transform):
            components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
            if len(components) != 1 or components[0].get_editor_property("static_mesh") is None:
                raise RuntimeError("%s does not have exactly one readable StaticMeshComponent" % actor.get_actor_label())
            box = components[0].get_editor_property("static_mesh").get_bounding_box()
            points = [unreal.MathLibrary.transform_location(transform, unreal.Vector(x, y, z))
                      for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
            return points

        landed_labels = ["S3 Hangar Deck", "S3 Hangar Far Wall", "S3 Hangar Left Wall", "S3 Hangar Right Wall",
                         "S3 Hangar Roof"] + sorted(label for label in actors_by_label
                                                    if label.startswith("S3 Hangar Lattice Beam "))
        landed = {}
        landed_points = {}
        for label in landed_labels:
            actor = actors_by_label[label][0]
            transform = final_actor_transform(actor)
            points = mesh_bounds_at(actor, transform)
            landed_points[label] = points
            dock_points = [unreal.MathLibrary.inverse_transform_location(dock, point) for point in points]
            landed[label] = {"world_transform": plain_transform(transform), "world_bounds": bounds_from_points(points),
                             "dock_bounds": bounds_from_points(dock_points)}

        cast_labels = requested_exact[:6]
        cast_actors = [actors_by_label[label][0] for label in cast_labels if len(actors_by_label.get(label, [])) == 1]
        cast_actors += clam_actors_on_pedestal
        cast_centres = [world_aabb(actor)[0] for actor in cast_actors]
        cast_centroid = unreal.Vector(
            sum(point.x for point in cast_centres) / len(cast_centres),
            sum(point.y for point in cast_centres) / len(cast_centres),
            sum(point.z for point in cast_centres) / len(cast_centres),
        )
        camera_location = camera_transform.translation
        forward = camera_transform.rotation.rotator().get_forward_vector()
        far_points = landed_points["S3 Hangar Far Wall"]
        far_center = unreal.Vector(sum(point.x for point in far_points) / len(far_points),
                                   sum(point.y for point in far_points) / len(far_points),
                                   sum(point.z for point in far_points) / len(far_points))
        box_points = []
        for label in ("S3 Hangar Deck", "S3 Hangar Far Wall", "S3 Hangar Left Wall",
                      "S3 Hangar Right Wall", "S3 Hangar Roof"):
            box_points.extend(landed_points[label])
        projected = [(point.x - camera_location.x) * forward.x + (point.y - camera_location.y) * forward.y
                     + (point.z - camera_location.z) * forward.z for point in box_points]
        roof_z = [point.z for point in landed_points["S3 Hangar Roof"]]
        lattice_points = [point for label, points in landed_points.items()
                          if label.startswith("S3 Hangar Lattice Beam ") for point in points]
        lattice_z = [point.z for point in lattice_points]
        roof_above_lattice = min(roof_z) > max(lattice_z)

        result = {
            "world": path_without_object(world),
            "dirty_before": dirty_before,
            "dock_frame": {"source": "Saved/CodexStructure/s3_pit_deck_record.json: dock.location/yaw",
                           "transform": plain_transform(dock)},
            "scene3_camera_stop": {
                "source": "DA_InfinityStage_V1Show.passage_settings[label=Passage 3].passage_guid; "
                          "InfinityStageCameraPilotLibrary.GetPassageFrameRange/GetPassageCameraPose at the compiled end frame",
                "passage_guid": guid_text(passage_guid),
                "compiled_frame_range": [int(frame_range[0]), int(frame_range[1])],
                "stop_frame": stop_frame,
                "world_transform": plain_transform(camera_transform),
                "dock_location": vec(unreal.MathLibrary.inverse_transform_location(dock, camera_transform.translation)),
                "focal_mm": round(float(focal_mm), 4), "focus_cm": round(float(focus_cm), 3),
                "passage_actor_route_property": "InfinityStagePassageActor.route",
                "route_length_cm": round(route_length, 3), "route_end_world": plain_transform(route_end),
                "scene3_entry_handoff_cameras": [actor_row(actor, dock) for actor in entry_cameras],
            },
            "sequences_root_and_nested": sequence_rows,
            "ls_clams_asset_only_bindings": ls_clams_bindings,
            "actors_current": target_rows,
            "clam_pedestal_search": {
                "definition": "all actor pivots/AABB origins inside or AABBs overlapping Clam_Pedastal world AABB, with max Z extended by 50 cm",
                "world_search_bounds": {"min": vec(search_min), "max": vec(search_max)},
                "nearby_actors": nearby_rows,
                "clam_actors": [actor_row(actor, dock) for actor in clam_actors_on_pedestal],
            },
            "rise_asset": {"path": path_without_object(rise), "transform_bindings": rise_key_rows,
                           "landed_geometry": landed,
                           "roof_vs_lattice": {"roof_world_z": [round(min(roof_z), 3), round(max(roof_z), 3)],
                                               "lattice_world_z": [round(min(lattice_z), 3), round(max(lattice_z), 3)],
                                               "roof_above_lattice": roof_above_lattice,
                                               "vertical_clearance_cm": round(min(roof_z) - max(lattice_z), 3)}},
            "derived": {
                "cast_centroid_definition": "mean of current world AABB origins for the six Shore cast plus clam actor(s) spatially discovered over Clam_Pedastal",
                "cast_centroid_world": vec(cast_centroid),
                "cast_centroid_dock": vec(unreal.MathLibrary.inverse_transform_location(dock, cast_centroid)),
                "camera_to_cast_centroid_horizontal_cm": round(math.hypot(cast_centroid.x - camera_location.x,
                                                                          cast_centroid.y - camera_location.y), 3),
                "camera_to_cast_centroid_forward_cm": round((cast_centroid.x - camera_location.x) * forward.x
                                                              + (cast_centroid.y - camera_location.y) * forward.y
                                                              + (cast_centroid.z - camera_location.z) * forward.z, 3),
                "landed_far_wall_center_world": vec(far_center),
                "camera_to_landed_far_wall_center_horizontal_cm": round(math.hypot(far_center.x - camera_location.x,
                                                                                    far_center.y - camera_location.y), 3),
                "landed_box_forward_projection_from_camera_cm": [round(min(projected), 3), round(max(projected), 3)],
                "landed_box_depth_along_camera_forward_cm": round(max(projected) - min(projected), 3),
                "camera_forward_world": vec(forward, 6),
            },
            "searched_not_found_or_nonunique": missing,
        }
        dirty_after = census()
        result["dirty_after"] = dirty_after
        unreal.log("S3_BLOCKING_PROBE|run=%s|%s" % (run, json.dumps(result, separators=(",", ":"), ensure_ascii=False)))
        unreal.log("S3_BLOCKING_PROBE_DONE|run=%s|census=%s" %
                   (run, json.dumps(dirty_after, separators=(",", ":"))))
    except Exception:
        after = census()
        unreal.log_error("S3_BLOCKING_PROBE_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"), json.dumps(after, separators=(",", ":"))))


main()
