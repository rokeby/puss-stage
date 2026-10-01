"""Scene 3 landed-box probe: asset-channel and level-state reads only.

No Sequencer UI, playback, evaluation, bound-object lookup, setters, or saves.
The only output is the required pair of log markers (or a STOPPED/ERROR marker).
"""
import datetime
import json
import math
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

    def vec(value, digits=3):
        return [round(float(value.x), digits), round(float(value.y), digits), round(float(value.z), digits)]

    def rot(value, digits=4):
        return {
            "pitch": round(float(value.pitch), digits),
            "yaw": round(float(value.yaw), digits),
            "roll": round(float(value.roll), digits),
        }

    def plain_transform(value):
        return {
            "location": vec(value.translation),
            "rotation": rot(value.rotation.rotator()),
            "scale": vec(value.scale3d, 6),
        }

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

    channel_axes = (
        "Location.X", "Location.Y", "Location.Z",
        "Rotation.X", "Rotation.Y", "Rotation.Z",
        "Scale.X", "Scale.Y", "Scale.Z",
    )

    def canonical_channel_name(name):
        for candidate in channel_axes:
            if name == candidate or name.startswith(candidate + "_"):
                return candidate
        return None

    def transform_values(value):
        rotation = value.rotation.rotator()
        return {
            "Location.X": float(value.translation.x),
            "Location.Y": float(value.translation.y),
            "Location.Z": float(value.translation.z),
            "Rotation.X": float(rotation.roll),
            "Rotation.Y": float(rotation.pitch),
            "Rotation.Z": float(rotation.yaw),
            "Scale.X": float(value.scale3d.x),
            "Scale.Y": float(value.scale3d.y),
            "Scale.Z": float(value.scale3d.z),
        }

    def make_transform(values):
        return unreal.Transform(
            location=unreal.Vector(values["Location.X"], values["Location.Y"], values["Location.Z"]),
            rotation=unreal.Rotator(
                roll=values["Rotation.X"], pitch=values["Rotation.Y"], yaw=values["Rotation.Z"]),
            scale=unreal.Vector(values["Scale.X"], values["Scale.Y"], values["Scale.Z"]),
        )

    def read_binding_transform(binding, actor, sequence):
        tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
            raise RuntimeError("%s has %d transform tracks or an unexpected section count" %
                               (actor.get_actor_label(), len(tracks)))
        track = tracks[0]
        section = track.get_sections()[0]
        parent = actor.get_attach_parent_actor()
        baseline = actor.root_component.get_relative_transform() if parent else actor.get_actor_transform()
        first_values = transform_values(baseline)
        last_values = dict(first_values)
        fps = float(sequence.get_display_rate().numerator) / float(sequence.get_display_rate().denominator)
        channels = []
        seen = set()
        for channel in section.get_all_channels():
            raw_name = channel_name(channel)
            name = canonical_channel_name(raw_name)
            if name is None:
                continue
            seen.add(name)
            keys = list(channel.get_keys())
            keys.sort(key=lambda key: frame_value(key.get_time()))
            default_value = None
            try:
                if channel.has_default():
                    default_value = float(channel.get_default())
            except Exception:
                pass
            if keys:
                first_key = keys[0]
                last_key = keys[-1]
                first_values[name] = float(first_key.get_value())
                last_values[name] = float(last_key.get_value())
                source = "first/last key"
                first_row = {
                    "frame": frame_value(first_key.get_time()),
                    "seconds": round(frame_value(first_key.get_time()) / fps, 6),
                    "value": round(float(first_key.get_value()), 6),
                }
                last_row = {
                    "frame": frame_value(last_key.get_time()),
                    "seconds": round(frame_value(last_key.get_time()) / fps, 6),
                    "value": round(float(last_key.get_value()), 6),
                }
            elif default_value is not None:
                first_values[name] = default_value
                last_values[name] = default_value
                source = "channel default (no keys)"
                first_row = None
                last_row = None
            else:
                source = "current relative/world baseline (no keys or default)"
                first_row = None
                last_row = None
            channels.append({
                "property": name,
                "raw_channel": raw_name,
                "source": source,
                "default": round(default_value, 6) if default_value is not None else None,
                "first_key": first_row,
                "last_key": last_row,
                "rest_value": round(first_values[name], 6),
                "landed_value": round(last_values[name], 6),
            })
        missing = [name for name in channel_axes if name not in seen]
        if missing:
            raise RuntimeError("%s transform track is missing channels: %s" %
                               (actor.get_actor_label(), ", ".join(missing)))
        return {
            "binding": str(binding.get_display_name()),
            "bound_actor": actor.get_actor_label(),
            "resolution": "binding display name matched exactly one level actor; no bound-object lookup",
            "track": str(track.get_display_name()),
            "track_class": track.get_class().get_name(),
            "property": "Transform",
            "channels": channels,
            "rest_transform": make_transform(first_values),
            "landed_transform": make_transform(last_values),
        }

    def bounds_from_points(points):
        if not points:
            return None
        return {
            "min": [round(min(point.x for point in points), 3),
                    round(min(point.y for point in points), 3),
                    round(min(point.z for point in points), 3)],
            "max": [round(max(point.x for point in points), 3),
                    round(max(point.y for point in points), 3),
                    round(max(point.z for point in points), 3)],
        }

    def box_corners(minimum, maximum):
        return [unreal.Vector(x, y, z) for x in (minimum.x, maximum.x)
                for y in (minimum.y, maximum.y) for z in (minimum.z, maximum.z)]

    def actor_local_bound_points(actor):
        actor_world = actor.get_actor_transform()
        points = []
        sources = []
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = component.get_editor_property("static_mesh")
            if mesh is None:
                continue
            box = mesh.get_bounding_box()
            component_world = unreal.Transform(
                location=component.get_world_location(),
                rotation=component.get_world_rotation(),
                scale=component.get_world_scale(),
            )
            for mesh_point in box_corners(box.min, box.max):
                world_point = unreal.MathLibrary.transform_location(component_world, mesh_point)
                points.append(unreal.MathLibrary.inverse_transform_location(actor_world, world_point))
            sources.append(mesh.get_path_name())
        if points:
            return points, {"kind": "static_mesh_local_boxes", "meshes": sorted(sources)}
        origin, extent = actor.get_actor_bounds(False, True)
        minimum = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
        maximum = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
        for world_point in box_corners(minimum, maximum):
            points.append(unreal.MathLibrary.inverse_transform_location(actor_world, world_point))
        return points, {"kind": "actor_bounds_fallback_for_non_mesh_actor"}

    def distance(a, b):
        return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)

    def max_scale_error(a, b):
        return max(abs(float(a.x) - float(b.x)), abs(float(a.y) - float(b.y)),
                   abs(float(a.z) - float(b.z)))

    def max_rotation_error(a, b):
        delta = unreal.MathLibrary.normalized_delta_rotator(a, b)
        return max(abs(float(delta.pitch)), abs(float(delta.yaw)), abs(float(delta.roll)))

    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or path_without_object(world) != "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice":
            raise RuntimeError("unexpected editor world: %s" % (world.get_path_name() if world else None))
        if editor.get_game_world() is not None:
            unreal.log_error("S3_LANDED_BOX_STOPPED|run=%s|reason=PIE_OR_SIE_ACTIVE" % run)
            return
        dirty_before = census()
        if dirty_before["maps"] or dirty_before["content"]:
            unreal.log_error("S3_LANDED_BOX_STOPPED|run=%s|reason=DIRTY_BEFORE|census=%s" %
                             (run, json.dumps(dirty_before, separators=(",", ":"))))
            return

        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        actors_by_label = {}
        for actor in actors:
            actors_by_label.setdefault(actor.get_actor_label(), []).append(actor)

        def one_actor(label):
            matches = actors_by_label.get(label, [])
            if len(matches) != 1:
                raise RuntimeError("expected exactly one actor labelled %s, found %d" % (label, len(matches)))
            return matches[0]

        mover_labels = ("S3 Hangar Root", "S3 Hangar Roof Hinge", "S3 Hangar Lattice Fly")
        movers = {label: one_actor(label) for label in mover_labels}
        rise = unreal.load_asset("/Game/InfinityStage/RigAtmos/LS_S3_HangarRise")
        if rise is None or not isinstance(rise, unreal.LevelSequence):
            raise RuntimeError("LS_S3_HangarRise did not load as a LevelSequence")
        bindings_by_name = {}
        for binding in rise.get_bindings():
            if binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
                bindings_by_name.setdefault(str(binding.get_display_name()), []).append(binding)

        binding_rows = []
        rest_overrides = {}
        landed_overrides = {}
        for label in mover_labels:
            matches = bindings_by_name.get(label, [])
            if len(matches) != 1:
                raise RuntimeError("expected exactly one transform binding named %s, found %d" %
                                   (label, len(matches)))
            row = read_binding_transform(matches[0], movers[label], rise)
            rest_overrides[label] = row.pop("rest_transform")
            landed_overrides[label] = row.pop("landed_transform")
            row["rest_transform"] = plain_transform(rest_overrides[label])
            row["landed_transform"] = plain_transform(landed_overrides[label])
            binding_rows.append(row)

        def in_scope(label):
            return (label in ("S3 Hangar Deck", "S3 Hangar Far Wall", "S3 Hangar Left Wall",
                              "S3 Hangar Right Wall", "S3 Hangar Roof")
                    or label.startswith("S3 Hangar Lattice Beam ")
                    or label.startswith("S3 Hangar Lattice Rail ")
                    or label.startswith("S3 Strike ")
                    or label.startswith("S3 Practical "))

        targets = sorted((actor for actor in actors if in_scope(actor.get_actor_label())),
                         key=lambda actor: actor.get_actor_label())
        required = ("S3 Hangar Deck", "S3 Hangar Far Wall", "S3 Hangar Left Wall",
                    "S3 Hangar Right Wall", "S3 Hangar Roof")
        for label in required:
            one_actor(label)
        if not targets:
            raise RuntimeError("no S3 hangar target actors found")

        rest_cache = {}
        landed_cache = {}

        def predicted_world(actor, overrides, cache):
            label = actor.get_actor_label()
            if label in cache:
                return cache[label]
            parent = actor.get_attach_parent_actor()
            if label in overrides:
                local_or_world = overrides[label]
            else:
                local_or_world = (actor.root_component.get_relative_transform()
                                  if parent else actor.get_actor_transform())
            value = (unreal.MathLibrary.compose_transforms(local_or_world,
                                                            predicted_world(parent, overrides, cache))
                     if parent else local_or_world)
            cache[label] = value
            return value

        def chain_and_relative_to_carrier(actor):
            chain = [actor.get_actor_label()]
            relative = actor.root_component.get_relative_transform()
            parent = actor.get_attach_parent_actor()
            while parent is not None:
                chain.append(parent.get_actor_label())
                if parent.get_actor_label() in mover_labels:
                    return chain, parent.get_actor_label(), relative
                grandparent = parent.get_attach_parent_actor()
                if grandparent is None:
                    break
                relative = unreal.MathLibrary.compose_transforms(
                    relative, parent.root_component.get_relative_transform())
                parent = grandparent
            raise RuntimeError("%s has no moving S3 hangar actor in its attach-parent chain: %s" %
                               (actor.get_actor_label(), " -> ".join(chain)))

        dock = unreal.Transform(
            location=unreal.Vector(10921.973, 160000.0, 0.0),
            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
        )
        actor_rows = []
        dock_bounds_by_label = {}
        rest_errors = []
        for actor in targets:
            chain, carrier, relative_to_carrier = chain_and_relative_to_carrier(actor)
            rest_world = predicted_world(actor, rest_overrides, rest_cache)
            landed_world = predicted_world(actor, landed_overrides, landed_cache)
            current_world = actor.get_actor_transform()
            location_error = distance(rest_world.translation, current_world.translation)
            rotation_error = max_rotation_error(rest_world.rotation.rotator(), current_world.rotation.rotator())
            scale_error = max_scale_error(rest_world.scale3d, current_world.scale3d)
            rest_errors.append((location_error, rotation_error, scale_error, actor.get_actor_label()))
            local_points, bounds_source = actor_local_bound_points(actor)
            landed_points = [unreal.MathLibrary.transform_location(landed_world, point) for point in local_points]
            dock_points = [unreal.MathLibrary.inverse_transform_location(dock, point) for point in landed_points]
            landed_world_bounds = bounds_from_points(landed_points)
            landed_dock_bounds = bounds_from_points(dock_points)
            dock_bounds_by_label[actor.get_actor_label()] = landed_dock_bounds
            actor_rows.append({
                "label": actor.get_actor_label(),
                "class": actor.get_class().get_name(),
                "attach_chain_actor_to_carrier": chain,
                "moving_carrier": carrier,
                "relative_transform_to_carrier": plain_transform(relative_to_carrier),
                "current_world_transform": plain_transform(current_world),
                "rest_composed_world_transform": plain_transform(rest_world),
                "rest_error_cm": round(location_error, 6),
                "rest_rotation_error_deg": round(rotation_error, 6),
                "rest_scale_error": round(scale_error, 9),
                "landed_world_transform": plain_transform(landed_world),
                "landed_world_aabb": landed_world_bounds,
                "landed_dock_aabb": landed_dock_bounds,
                "bounds_source": bounds_source,
            })

        worst = max(rest_errors, key=lambda row: row[0])
        rest_check = {
            "status": "PASS" if worst[0] <= 1.0 else "MISMATCH",
            "limit_cm": 1.0,
            "max_location_error_cm": round(worst[0], 6),
            "worst_actor": worst[3],
            "max_rotation_error_deg": round(max(row[1] for row in rest_errors), 6),
            "max_scale_error": round(max(row[2] for row in rest_errors), 9),
            "actor_count": len(rest_errors),
        }
        if rest_check["status"] != "PASS":
            after = census()
            result = {
                "world": path_without_object(world),
                "dirty_before": dirty_before,
                "dirty_after": after,
                "rise_asset": path_without_object(rise),
                "binding_tracks": binding_rows,
                "rest_pose_check": rest_check,
                "actors": actor_rows,
                "stopped_before_landed_report": True,
            }
            unreal.log("S3_LANDED_BOX|run=%s|%s" %
                       (run, json.dumps(result, separators=(",", ":"), ensure_ascii=False)))
            unreal.log("S3_LANDED_BOX_DONE|run=%s|census=%s" %
                       (run, json.dumps(after, separators=(",", ":"))))
            return

        deck = dock_bounds_by_label["S3 Hangar Deck"]
        far_wall = dock_bounds_by_label["S3 Hangar Far Wall"]
        left_wall = dock_bounds_by_label["S3 Hangar Left Wall"]
        right_wall = dock_bounds_by_label["S3 Hangar Right Wall"]
        roof = dock_bounds_by_label["S3 Hangar Roof"]
        lattice_bounds = [bounds for label, bounds in dock_bounds_by_label.items()
                          if label.startswith("S3 Hangar Lattice Beam ")
                          or label.startswith("S3 Hangar Lattice Rail ")]
        if not lattice_bounds:
            raise RuntimeError("no lattice beam/rail bounds found")
        floor_top = float(deck["max"][2])
        roof_underside = float(roof["min"][2])
        lattice_min = min(float(bounds["min"][2]) for bounds in lattice_bounds)
        lattice_max = max(float(bounds["max"][2]) for bounds in lattice_bounds)
        left_inner = max(float(left_wall["min"][1]), float(left_wall["max"][1]))
        right_inner = min(float(right_wall["min"][1]), float(right_wall["max"][1]))
        inner_y = sorted((left_inner, right_inner))
        front_opening_x = min(float(deck["min"][0]), float(left_wall["min"][0]),
                              float(right_wall["min"][0]))
        far_inner_x = min(float(far_wall["min"][0]), float(far_wall["max"][0]))
        floor_center_dock = unreal.Vector(
            (front_opening_x + far_inner_x) * 0.5,
            (inner_y[0] + inner_y[1]) * 0.5,
            floor_top,
        )
        arrival_camera_dock = unreal.Vector(0.0, 0.0, 180.0)

        pedestal = one_actor("Clam_Pedastal")
        pedestal_origin, pedestal_extent = pedestal.get_actor_bounds(False, True)
        search_min = unreal.Vector(pedestal_origin.x - pedestal_extent.x,
                                   pedestal_origin.y - pedestal_extent.y,
                                   pedestal_origin.z - pedestal_extent.z)
        search_max = unreal.Vector(pedestal_origin.x + pedestal_extent.x,
                                   pedestal_origin.y + pedestal_extent.y,
                                   pedestal_origin.z + pedestal_extent.z + 50.0)
        shore_labels = (
            "Shore01_M56 Clam", "Shore02_F52 Clam", "Shore03_M59 Clam",
            "Shore04_F55 Clam", "Shore05_M53 Clam", "Shore06_F25 Clam",
        )
        shore_actors = [one_actor(label) for label in shore_labels]

        def clam_tokens(actor):
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

        clam_actors = []
        for actor in actors:
            if actor == pedestal or actor in shore_actors:
                continue
            origin, extent = actor.get_actor_bounds(False, True)
            minimum = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
            maximum = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
            overlaps = (maximum.x >= search_min.x and minimum.x <= search_max.x
                        and maximum.y >= search_min.y and minimum.y <= search_max.y
                        and maximum.z >= search_min.z and minimum.z <= search_max.z)
            if overlaps and any("clam" in token.lower() for token in clam_tokens(actor)):
                clam_actors.append(actor)
        clam_actors.sort(key=lambda actor: actor.get_actor_label())
        if not clam_actors:
            raise RuntimeError("no clam actor overlapped the Clam_Pedastal search bounds")
        cast_actors = shore_actors + clam_actors
        cast_origins = [actor.get_actor_bounds(False, True)[0] for actor in cast_actors]
        cast_centroid_world = unreal.Vector(
            sum(point.x for point in cast_origins) / len(cast_origins),
            sum(point.y for point in cast_origins) / len(cast_origins),
            sum(point.z for point in cast_origins) / len(cast_origins),
        )
        cast_centroid_dock = unreal.MathLibrary.inverse_transform_location(dock, cast_centroid_world)
        pedestal_dock = unreal.MathLibrary.inverse_transform_location(dock, pedestal.get_actor_location())
        move_vector = unreal.Vector(floor_center_dock.x - pedestal_dock.x,
                                    floor_center_dock.y - pedestal_dock.y,
                                    floor_center_dock.z - pedestal_dock.z)

        after = census()
        result = {
            "world": path_without_object(world),
            "dirty_before": dirty_before,
            "dirty_after": after,
            "dock_frame": {"origin_world_cm": [10921.973, 160000.0, 0.0], "yaw_deg": 0.0},
            "rise_asset": path_without_object(rise),
            "binding_tracks": binding_rows,
            "rest_pose_check": rest_check,
            "actors": actor_rows,
            "landed_interior_box": {
                "floor_top_z_cm": round(floor_top, 3),
                "roof_underside_z_cm": round(roof_underside, 3),
                "lattice_z_range_cm": [round(lattice_min, 3), round(lattice_max, 3)],
                "lattice_z_center_cm": round((lattice_min + lattice_max) * 0.5, 3),
                "inner_walls_y_cm": [round(inner_y[0], 3), round(inner_y[1], 3)],
                "front_opening_x_cm": round(front_opening_x, 3),
                "far_wall_inner_face_x_cm": round(far_inner_x, 3),
                "roof_above_lattice": roof_underside > lattice_max,
                "roof_to_lattice_clearance_cm": round(roof_underside - lattice_max, 3),
                "floor_center_dock_cm": vec(floor_center_dock),
                "arrival_camera_dock_cm": [0.0, 0.0, 180.0],
                "arrival_camera_to_floor_center_3d_cm": round(distance(arrival_camera_dock, floor_center_dock), 3),
                "arrival_camera_to_floor_center_horizontal_cm": round(
                    math.hypot(floor_center_dock.x, floor_center_dock.y), 3),
            },
            "current_cast_group": {
                "centroid_definition": "mean current world-AABB origins of six Shore cast actors plus spatially discovered clam actors over Clam_Pedastal",
                "actor_labels": [actor.get_actor_label() for actor in cast_actors],
                "centroid_dock_cm": vec(cast_centroid_dock),
                "pedestal_actor_location_dock_cm": vec(pedestal_dock),
                "move_vector_for_pedestal_to_floor_center_dock_cm": vec(move_vector),
            },
        }
        unreal.log("S3_LANDED_BOX|run=%s|%s" %
                   (run, json.dumps(result, separators=(",", ":"), ensure_ascii=False)))
        unreal.log("S3_LANDED_BOX_DONE|run=%s|census=%s" %
                   (run, json.dumps(after, separators=(",", ":"))))
    except Exception:
        after = census()
        unreal.log_error("S3_LANDED_BOX_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(after, separators=(",", ":"))))


main()
