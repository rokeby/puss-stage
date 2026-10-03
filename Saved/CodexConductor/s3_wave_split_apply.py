"""DRY/APPLY/REVERT tool for splitting Scene 3 wave rows into short overlaps.

The six landed source actors remain the source of meshes/materials and are only
hidden by APPLY.  Nine tool-owned duplicates (three per row) carry independent
strike-gated 15 s slide phases.  REVERT removes only those duplicates and
restores the six originals.  Offline import never contacts Unreal.
"""
import datetime
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
ROOT_LABEL = "S3 Hangar Root"
UPLIGHT_LABEL = "S3 Uplight 1"
EXPECTED_FPS = 24.0
EXPECTED_PLAYBACK = (0, 6240)
EXPECTED_STRIKE_SECONDS = 10.0
STRIKE_TOLERANCE_FRAMES = 1
PERIOD_FRAMES = 360
KEY_STEP_FRAMES = 3
AMPLITUDE_CM = 100.0
ROW_DIRECTIONS = (1, -1, 1)
ROW_DELAYS = (0, 24, 48)
PIECE_PHASE_DELAYS = (0, 40, 80)
VAMP_RANGE = (3480, 4200)
PIECE_WIDTH_CM = 1200.0
PIECE_WIDTH_FRACTION = 0.60
PIECE_CENTRES_Y_CM = (-500.0, 0.0, 500.0)
PIECE_DEPTH_OFFSETS_CM = (-35.0, 0.0, 35.0)
BOX_Y_LIMIT_CM = 1000.0
BOX_X_RANGE_CM = (500.0, 6500.0)
BOX_Z_RANGE_CM = (-5.0, 600.0)
MAX_CONTROLLED_OVERHANG_CM = 200.0
TRACK_NAME = "S3.WaveSplit"
TAG = "S3.WaveSplit.ToolOwned"
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW = 0.0
TARGET_LABELS = tuple("S3 Wave Row%d %s" % (row, half)
                      for row in (1, 2, 3) for half in ("A", "B"))
CHANNELS = ("Location.X", "Location.Y", "Location.Z",
            "Rotation.X", "Rotation.Y", "Rotation.Z",
            "Scale.X", "Scale.Y", "Scale.Z")
RECORD_NAME = "s3_wave_split_record.json"
REQUIRED_TESTS = ("InfinityStage.Editor.SavedMasterMatchesShow",
                  "InfinityStage.Editor.SceneCutBindingsResolve")


class PlanError(ValueError):
    pass


def compute_strike_frame(parent_fps, child_fps, section_start, child_offset,
                         child_strike, time_scale=1.0):
    values = [parent_fps, child_fps, time_scale]
    if any(not math.isfinite(float(value)) or float(value) <= 0.0 for value in values):
        raise PlanError("invalid strike mapping rates")
    raw = (float(section_start) +
           (float(child_strike) - float(child_offset)) * float(parent_fps) /
           float(child_fps) / float(time_scale))
    frame = int(round(raw))
    expected_child = int(round(EXPECTED_STRIKE_SECONDS * float(child_fps)))
    expected = int(round(float(section_start) +
                         (expected_child - float(child_offset)) * float(parent_fps) /
                         float(child_fps) / float(time_scale)))
    if abs(frame - expected) > STRIKE_TOLERANCE_FRAMES:
        raise PlanError("computed strike %d is not the mapped +10 s frame %d" % (frame, expected))
    return {"frame": frame, "raw_parent_frame": raw, "expected_frame": expected,
            "parent_fps": float(parent_fps), "child_fps": float(child_fps),
            "section_start_frame": int(section_start), "child_start_frame_offset": int(child_offset),
            "child_strike_frame": int(child_strike), "time_scale": float(time_scale)}


def piece_offset(frame, strike_frame, row, piece):
    row_index, piece_index = int(row) - 1, int(piece) - 1
    delay = ROW_DELAYS[row_index] + PIECE_PHASE_DELAYS[piece_index]
    elapsed = max(0, int(frame) - int(strike_frame) - delay)
    return (ROW_DIRECTIONS[row_index] * AMPLITUDE_CM *
            math.sin(2.0 * math.pi * elapsed / PERIOD_FRAMES))


def _coverage(intervals):
    ordered = sorted(intervals)
    cursor = -BOX_Y_LIMIT_CM
    for low, high in ordered:
        if low > cursor + 1.0e-6:
            return False
        cursor = max(cursor, high)
    return cursor >= BOX_Y_LIMIT_CM - 1.0e-6


def plan_wave_split(state):
    fps = float(state.get("fps", 0.0))
    playback = tuple(int(value) for value in state.get("playback", ()))
    strike = dict(state.get("strike", {}))
    strike_frame = int(strike.get("frame", -1))
    if abs(fps - EXPECTED_FPS) > 1.0e-6:
        raise PlanError("Scene 3 root is not 24 fps")
    if playback != EXPECTED_PLAYBACK:
        raise PlanError("unexpected Scene 3 playback range")
    if abs(strike_frame - 240) > STRIKE_TOLERANCE_FRAMES:
        raise PlanError("strike gate is not +10 s in the 24 fps root")
    actors = list(state.get("actors", []))
    counts = {label: 0 for label in TARGET_LABELS}
    by_label = {}
    for actor in actors:
        label = str(actor.get("label", ""))
        if label in counts:
            counts[label] += 1
            by_label[label] = actor
    if len(actors) != 6 or any(value != 1 for value in counts.values()):
        raise PlanError("expected exactly the six original S3 wave actors")
    for label in TARGET_LABELS:
        actor = by_label[label]
        if actor.get("parent_label") != ROOT_LABEL:
            raise PlanError(label + " is not attached to S3 Hangar Root")
        if int(actor.get("transform_track_count", 0)) != 1:
            raise PlanError(label + " does not have exactly one original transform track")
        if actor.get("tool_owned"):
            raise PlanError(label + " is unexpectedly tool-owned")
        origin = actor.get("landed_origin_dock_cm")
        if not isinstance(origin, (list, tuple)) or len(origin) != 3:
            raise PlanError(label + " has no live landed origin")
        if (not BOX_X_RANGE_CM[0] <= float(origin[0]) <= BOX_X_RANGE_CM[1] or
                not -BOX_Y_LIMIT_CM <= float(origin[1]) <= BOX_Y_LIMIT_CM or
                not BOX_Z_RANGE_CM[0] <= float(origin[2]) <= BOX_Z_RANGE_CM[1]):
            raise PlanError(label + " is outside the live landed S3 box")
    existing = set(state.get("existing_labels", []))
    planned_labels = ["S3 Wave Split Row%d Piece%d" % (row, piece)
                      for row in (1, 2, 3) for piece in (1, 2, 3)]
    if existing.intersection(planned_labels):
        raise PlanError("wave split actor labels already exist")

    key_frames = [strike_frame - 1] + list(range(strike_frame, playback[1] + 1, KEY_STEP_FRAMES))
    if key_frames[-1] != playback[1]:
        raise PlanError("key cadence does not land on Scene 3 end")
    pieces = []
    for row in (1, 2, 3):
        source_labels = ("S3 Wave Row%d A" % row, "S3 Wave Row%d B" % row,
                         "S3 Wave Row%d A" % row)
        for piece in (1, 2, 3):
            source = by_label[source_labels[piece - 1]]
            source_width = float(source.get("landed_width_cm", 0.0))
            if source_width <= 1.0:
                raise PlanError(source["label"] + " has no usable landed width")
            source_origin = source["landed_origin_dock_cm"]
            piece_x = float(source_origin[0]) + PIECE_DEPTH_OFFSETS_CM[piece - 1]
            piece_z = float(source_origin[2])
            if not BOX_X_RANGE_CM[0] <= piece_x <= BOX_X_RANGE_CM[1] or not BOX_Z_RANGE_CM[0] <= piece_z <= BOX_Z_RANGE_CM[1]:
                raise PlanError("planned piece leaves the live landed S3 box")
            keys = [[frame, piece_offset(frame, strike_frame, row, piece)] for frame in key_frames]
            seam = [piece_offset(frame, strike_frame, row, piece) for frame in VAMP_RANGE]
            if abs(seam[1] - seam[0]) > 0.01:
                raise PlanError("vamp seam unequal for row %d piece %d" % (row, piece))
            centre = PIECE_CENTRES_Y_CM[piece - 1]
            swept_centre = [centre - AMPLITUDE_CM, centre + AMPLITUDE_CM]
            if swept_centre[0] < -BOX_Y_LIMIT_CM or swept_centre[1] > BOX_Y_LIMIT_CM:
                raise PlanError("piece centre leaves the live landed box")
            overhang = max(0.0, -(centre - AMPLITUDE_CM - PIECE_WIDTH_CM / 2.0) - BOX_Y_LIMIT_CM,
                           centre + AMPLITUDE_CM + PIECE_WIDTH_CM / 2.0 - BOX_Y_LIMIT_CM)
            if overhang > MAX_CONTROLLED_OVERHANG_CM + 1.0e-6:
                raise PlanError("piece mesh overhang exceeds the controlled allowance")
            pieces.append({
                "label": planned_labels[(row - 1) * 3 + piece - 1], "row": row, "piece": piece,
                "source_label": source["label"], "source_actor_path": source.get("actor_path"),
                "target_width_cm": PIECE_WIDTH_CM,
                "width_fraction_of_hangar": PIECE_WIDTH_FRACTION,
                "scale_y_multiplier": PIECE_WIDTH_CM / source_width,
                "centre_y_cm": centre, "depth_offset_cm": PIECE_DEPTH_OFFSETS_CM[piece - 1],
                "landed_origin_dock_cm": [piece_x, centre, piece_z],
                "phase_delay_frames": ROW_DELAYS[row - 1] + PIECE_PHASE_DELAYS[piece - 1],
                "direction": ROW_DIRECTIONS[row - 1], "keys": keys,
                "seam_error_cm": abs(seam[1] - seam[0]), "swept_centre_y_cm": swept_centre,
                "controlled_overhang_cm": overhang,
            })

    worst_gap = 0.0
    for frame in range(strike_frame, playback[1] + 1, KEY_STEP_FRAMES):
        for row in (1, 2, 3):
            row_pieces = [piece for piece in pieces if piece["row"] == row]
            intervals = []
            for piece in row_pieces:
                offset = piece_offset(frame, strike_frame, row, piece["piece"])
                centre = piece["centre_y_cm"] + offset
                intervals.append((centre - PIECE_WIDTH_CM / 2.0, centre + PIECE_WIDTH_CM / 2.0))
            ordered = sorted(intervals)
            gaps = [max(0.0, ordered[index + 1][0] - ordered[index][1])
                    for index in range(len(ordered) - 1)]
            worst_gap = max([worst_gap] + gaps)
            if not _coverage(intervals):
                raise PlanError("row %d loses horizontal cover at frame %d" % (row, frame))
    return {
        "asset": ROOT_PATH, "fps": fps, "playback": list(playback), "strike": strike,
        "period_frames": PERIOD_FRAMES, "period_seconds": PERIOD_FRAMES / fps,
        "amplitude_cm": AMPLITUDE_CM, "piece_width_fraction": PIECE_WIDTH_FRACTION,
        "piece_count": len(pieces), "pieces": pieces, "worst_gap_cm": worst_gap,
        "vamp_range": list(VAMP_RANGE), "inside_box_guard": True,
        "max_controlled_overhang_cm": max(piece["controlled_overhang_cm"] for piece in pieces),
        "required_tests": list(REQUIRED_TESTS),
    }


def _path(value):
    return str(value.get_path_name()).split(".", 1)[0]


def package_census():
    return {"maps": sorted(_path(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": sorted(_path(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def stop(run, reason):
    unreal.log_error("S3_WAVE_SPLIT_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def _frame(value):
    if hasattr(value, "frame_number"):
        return int(value.frame_number.value)
    return int(value.value if hasattr(value, "value") else value)


def _guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def _index():
    result = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def _one(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        stop(run, "reason=ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
    return rows[0]


def _plain(value):
    rotation = value.rotation.rotator()
    return {"location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
            "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)]}


def _transform(row):
    return unreal.Transform(location=unreal.Vector(*row["location"]),
                            rotation=unreal.Rotator(roll=row["rotation"][0], pitch=row["rotation"][1], yaw=row["rotation"][2]),
                            scale=unreal.Vector(*row["scale"]))


def _canonical(channel):
    try:
        name = str(channel.get_name())
    except Exception:
        name = str(channel.get_editor_property("channel_name"))
    name = re.sub(r"_\d+$", "", name)
    return name if name in CHANNELS else None


def _root_landed(rise, root, run):
    bindings = [binding for binding in rise.get_bindings()
                if str(binding.get_display_name()) == ROOT_LABEL and
                binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack)]
    if len(bindings) != 1:
        stop(run, "reason=ROOT_RISE_BINDING_COUNT")
    tracks = list(bindings[0].find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        stop(run, "reason=ROOT_RISE_TRACK_SHAPE")
    base = _plain(root.get_actor_transform())
    values = {"Location.X": base["location"][0], "Location.Y": base["location"][1], "Location.Z": base["location"][2],
              "Rotation.X": base["rotation"][0], "Rotation.Y": base["rotation"][1], "Rotation.Z": base["rotation"][2],
              "Scale.X": base["scale"][0], "Scale.Y": base["scale"][1], "Scale.Z": base["scale"][2]}
    for channel in tracks[0].get_sections()[0].get_all_channels():
        name = _canonical(channel)
        keys = sorted(channel.get_keys(), key=lambda key: _frame(key.get_time()))
        if name and keys:
            values[name] = float(keys[-1].get_value())
    return unreal.Transform(location=unreal.Vector(values["Location.X"], values["Location.Y"], values["Location.Z"]),
                            rotation=unreal.Rotator(roll=values["Rotation.X"], pitch=values["Rotation.Y"], yaw=values["Rotation.Z"]),
                            scale=unreal.Vector(values["Scale.X"], values["Scale.Y"], values["Scale.Z"]))


def _dock():
    return unreal.Transform(location=unreal.Vector(*DOCK_ORIGIN),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW))


def _actor_bindings(sequence, actor, world):
    wanted = str(actor.get_path_name())
    rows = []
    for binding in sequence.get_bindings():
        parent = binding.get_parent()
        if parent is not None and parent.is_valid():
            continue
        try:
            resolved = [str(value.get_path_name()) for value in sequence.locate_bound_objects(binding, world)]
        except Exception:
            continue
        if wanted in resolved:
            rows.append(binding)
    return rows


def _read_strike(sequence, rise):
    matches = []
    for track in sequence.get_tracks():
        if isinstance(track, unreal.MovieSceneSubTrack):
            for section in track.get_sections():
                nested = section.get_sequence()
                if nested is not None and _path(nested) == RISE_PATH:
                    matches.append(section)
    if len(matches) != 1 or not matches[0].is_active():
        raise PlanError("expected one active S3 rise subsection")
    section = matches[0]
    parameters = section.get_editor_property("parameters")
    offset = _frame(parameters.get_editor_property("start_frame_offset"))
    try:
        time_scale = float(unreal.MovieSceneTimeWarpExtensions.conv_time_warp_variant_to_play_rate(
            parameters.get_editor_property("time_scale")))
    except Exception as exc:
        raise PlanError("rise time scale is not fixed: " + str(exc))
    candidates = []
    for binding in rise.get_bindings():
        parent = binding.get_parent()
        label = str(parent.get_display_name()) if parent is not None and parent.is_valid() else str(binding.get_display_name())
        if label != UPLIGHT_LABEL:
            continue
        for track in binding.get_tracks():
            if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == "Intensity":
                for candidate in track.get_sections():
                    keys = sorted(candidate.get_all_channels()[0].get_keys(), key=lambda key: _frame(key.get_time()))
                    rows = [[_frame(key.get_time()), float(key.get_value())] for key in keys]
                    candidates.extend(rows[i][0] for i in range(len(rows) - 1)
                                      if abs(rows[i][1]) < 1.0e-6 and rows[i + 1][1] > 0.0)
    if len(candidates) != 1:
        raise PlanError("uplight strike is ambiguous")
    pr, cr = sequence.get_display_rate(), rise.get_display_rate()
    return compute_strike_frame(float(pr.numerator) / pr.denominator,
                                float(cr.numerator) / cr.denominator,
                                _frame(section.get_start_frame()), offset, candidates[0], time_scale)


def _landed_bounds(actor, relative, landed, dock, run):
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    mesh = component.get_editor_property("static_mesh") if component else None
    if mesh is None:
        stop(run, "reason=SOURCE_MESH_MISSING|label=" + actor.get_actor_label())
    world = unreal.MathLibrary.compose_transforms(relative, landed)
    box = mesh.get_bounding_box()
    ys = []
    for x in (box.min.x, box.max.x):
        for y in (box.min.y, box.max.y):
            for z in (box.min.z, box.max.z):
                point = unreal.MathLibrary.transform_location(world, unreal.Vector(x, y, z))
                ys.append(float(unreal.MathLibrary.inverse_transform_location(dock, point).y))
    return [min(ys), max(ys)]


def _live_state(sequence, rise, world, run):
    strike = _read_strike(sequence, rise)
    rate = sequence.get_display_rate()
    fps = float(rate.numerator) / rate.denominator
    index = _index()
    root = _one(index, ROOT_LABEL, run)
    landed, dock = _root_landed(rise, root, run), _dock()
    actors, runtime = [], {}
    for label in TARGET_LABELS:
        actor = _one(index, label, run)
        parent = actor.get_attach_parent_actor()
        if parent is None or str(parent.get_actor_label()) != ROOT_LABEL:
            stop(run, "reason=SOURCE_PARENT|label=" + label)
        bindings = _actor_bindings(sequence, actor, world)
        tracks = list(bindings[0].find_tracks_by_type(unreal.MovieScene3DTransformTrack)) if len(bindings) == 1 else []
        relative = actor.get_editor_property("root_component").get_relative_transform()
        bounds = _landed_bounds(actor, relative, landed, dock, run)
        landed_world = unreal.MathLibrary.compose_transforms(relative, landed)
        landed_plain = _plain(landed_world)
        landed_origin = unreal.MathLibrary.inverse_transform_location(
            dock, unreal.Vector(*landed_plain["location"]))
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        actors.append({"label": label, "actor_path": str(actor.get_path_name()), "parent_label": ROOT_LABEL,
                       "transform_track_count": len(tracks), "landed_width_cm": bounds[1] - bounds[0],
                       "landed_origin_dock_cm": [float(landed_origin.x), float(landed_origin.y), float(landed_origin.z)],
                       "tool_owned": TAG in [str(value) for value in actor.tags]})
        runtime[label] = {"actor": actor, "component": component, "relative": relative}
    return ({"fps": fps, "playback": [int(sequence.get_playback_start()), int(sequence.get_playback_end())],
             "strike": strike, "actors": actors, "existing_labels": list(index)},
            runtime, root, landed, dock)


def _piece_relative(source_relative, landed, dock, plan):
    source_world = unreal.MathLibrary.compose_transforms(source_relative, landed)
    source_plain = _plain(source_world)
    source_dock = unreal.MathLibrary.inverse_transform_location(dock, unreal.Vector(*source_plain["location"]))
    wanted_dock = unreal.Vector(source_dock.x + plan["depth_offset_cm"], plan["centre_y_cm"], source_dock.z)
    wanted_world_location = unreal.MathLibrary.transform_location(dock, wanted_dock)
    wanted_world = unreal.Transform(location=wanted_world_location,
                                    rotation=source_world.rotation.rotator(), scale=source_world.scale3d)
    relative = unreal.MathLibrary.make_relative_transform(wanted_world, landed)
    plain = _plain(relative)
    plain["scale"][1] *= float(plan["scale_y_multiplier"])
    return _transform(plain)


def _track_rows(base_relative, plan, landed, dock):
    base_world = unreal.MathLibrary.compose_transforms(base_relative, landed)
    base = _plain(base_world)
    base_dock = unreal.MathLibrary.inverse_transform_location(dock, unreal.Vector(*base["location"]))
    rows = []
    for frame, offset in plan["keys"]:
        wanted = unreal.Vector(base_dock.x, base_dock.y + float(offset), base_dock.z)
        location = unreal.MathLibrary.transform_location(dock, wanted)
        world = unreal.Transform(location=location, rotation=base_world.rotation.rotator(), scale=base_world.scale3d)
        relative = unreal.MathLibrary.make_relative_transform(world, landed)
        rows.append({"frame": int(frame), **_plain(relative)})
    return rows


def _add_track(binding, rows, run):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    track.set_display_name(TRACK_NAME)
    section = track.add_section()
    section.set_range(rows[0]["frame"], rows[-1]["frame"] + 1)
    channels = {_canonical(channel): channel for channel in section.get_all_channels() if _canonical(channel)}
    if set(channels) != set(CHANNELS):
        stop(run, "reason=NEW_TRACK_CHANNELS")
    for name, value in zip(CHANNELS[6:], rows[0]["scale"]):
        channels[name].set_default(float(value))
    for row in rows:
        values = row["location"] + row["rotation"]
        for name, value in zip(CHANNELS[:6], values):
            channels[name].add_key(unreal.FrameNumber(row["frame"]), float(value),
                                   time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                   interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    return track


def _verify_track(track, rows, run, label):
    sections = list(track.get_sections())
    if len(sections) != 1:
        stop(run, "reason=TRACK_SECTION_READBACK|label=" + label)
    channels = {_canonical(channel): channel for channel in sections[0].get_all_channels() if _canonical(channel)}
    wanted_frames = [row["frame"] for row in rows]
    for axis, name in enumerate(CHANNELS[:6]):
        keys = sorted(channels[name].get_keys(), key=lambda key: _frame(key.get_time()))
        frames = [_frame(key.get_time()) for key in keys]
        field = "location" if axis < 3 else "rotation"
        component = axis if axis < 3 else axis - 3
        wanted_values = [float(row[field][component]) for row in rows]
        got_values = [float(key.get_value()) for key in keys]
        if frames != wanted_frames or any(abs(left - right) > 0.001 for left, right in zip(got_values, wanted_values)):
            stop(run, "reason=TRACK_KEY_READBACK|label=%s|channel=%s" % (label, name))
    return {"key_count": len(wanted_frames), "first_frame": wanted_frames[0], "last_frame": wanted_frames[-1]}


def _asset_filename(project, package, ext):
    return os.path.join(project, "Content", *package[len("/Game/"):].split("/")) + ext


def _backup(project, stamp, run):
    target = os.path.join(project, "Backups", "PreS3WaveSplit-" + stamp.strftime("%Y%m%d-%H%M%S"))
    if os.path.exists(target):
        stop(run, "reason=BACKUP_EXISTS")
    sources = (_asset_filename(project, EXPECTED_WORLD, ".umap"), _asset_filename(project, ROOT_PATH, ".uasset"))
    if any(not os.path.isfile(path) for path in sources):
        stop(run, "reason=BACKUP_SOURCE_MISSING")
    for source in sources:
        rel = os.path.relpath(source, os.path.join(project, "Content"))
        dest = os.path.join(target, "Content", rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(source, dest)
    return target


def _record_path():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor", RECORD_NAME)


def _write(record, exclusive, run):
    try:
        with open(_record_path(), "x" if exclusive else "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
    except Exception as exc:
        stop(run, "reason=RECORD_WRITE|detail=" + str(exc))


def _binding_by_guid(sequence, guid):
    rows = [binding for binding in sequence.get_bindings() if _guid(binding.get_id()) == guid]
    return rows[0] if len(rows) == 1 else None


def _save(run):
    if not unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False):
        stop(run, "reason=SEQUENCE_SAVE_FAILED")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "reason=LEVEL_SAVE_FAILED")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    return census


def _apply(sequence, runtime, root, landed, dock, plan, run):
    stamp = datetime.datetime.now()
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = _backup(project, stamp, run)
    record = {"world": EXPECTED_WORLD, "asset": ROOT_PATH, "run": run, "backup": backup,
              "written": stamp.isoformat(timespec="seconds"), "plan": plan,
              "originals": [], "created": [], "applied": False}
    _write(record, True, run)
    for label in TARGET_LABELS:
        source = runtime[label]
        actor, component = source["actor"], source["component"]
        record["originals"].append({"label": label, "actor_path": str(actor.get_path_name()),
                                    "hidden_in_game": bool(actor.is_hidden()),
                                    "component_visible": bool(component.is_visible())})
        actor.set_actor_hidden_in_game(True)
        component.set_visibility(False, True)
        if not actor.is_hidden() or component.is_visible():
            stop(run, "reason=ORIGINAL_HIDE_READBACK|label=" + label)
    for piece in plan["pieces"]:
        source = runtime[piece["source_label"]]
        source_component = source["component"]
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
        if actor is None:
            stop(run, "reason=SPAWN_FAILED|label=" + piece["label"])
        actor.set_actor_label(piece["label"])
        actor.tags = list(actor.tags) + [TAG]
        actor.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE,
                              unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE, False)
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_static_mesh(source_component.get_editor_property("static_mesh"))
        for index, material in enumerate(source_component.get_materials()):
            component.set_material(index, material)
        relative = _piece_relative(source["relative"], landed, dock, piece)
        relative_plain = _plain(relative)
        actor.set_actor_relative_location(unreal.Vector(*relative_plain["location"]), False, True)
        actor.set_actor_relative_rotation(
            unreal.Rotator(roll=relative_plain["rotation"][0], pitch=relative_plain["rotation"][1],
                           yaw=relative_plain["rotation"][2]), False, True)
        actor.set_actor_relative_scale3d(unreal.Vector(*relative_plain["scale"]))
        binding = sequence.add_possessable(actor)
        rows = _track_rows(relative, piece, landed, dock)
        track = _add_track(binding, rows, run)
        track_readback = _verify_track(track, rows, run, piece["label"])
        resolved = [str(value.get_path_name()) for value in sequence.locate_bound_objects(binding,
                    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world())]
        if resolved != [str(actor.get_path_name())]:
            stop(run, "reason=NEW_BINDING_READBACK|label=" + piece["label"])
        record["created"].append({"label": piece["label"], "actor_path": str(actor.get_path_name()),
                                  "binding_guid": _guid(binding.get_id()), "source_label": piece["source_label"],
                                  "key_count": len(rows), "track_readback": track_readback})
        _write(record, False, run)
    if len(record["created"]) != 9:
        stop(run, "reason=CREATED_COUNT")
    census = package_census()
    if set(census["maps"]) != {EXPECTED_WORLD} or set(census["content"]) != {ROOT_PATH}:
        stop(run, "reason=DIRTY_SCOPE|census=" + json.dumps(census, sort_keys=True))
    record["dirty_before_save"] = census
    record["post_save_census"] = _save(run)
    record["applied"] = True
    _write(record, False, run)
    unreal.log("S3_WAVE_SPLIT_DONE|run=%s|applied|backup=%s|pieces=9|tests_required_singly=%s" %
               (run, backup, ",".join(REQUIRED_TESTS)))


def _revert(sequence, run):
    try:
        with open(_record_path(), encoding="utf-8") as handle:
            record = json.load(handle)
    except Exception as exc:
        stop(run, "reason=RECORD_READ|detail=" + str(exc))
    if record.get("world") != EXPECTED_WORLD or record.get("asset") != ROOT_PATH or not record.get("applied"):
        stop(run, "reason=REVERT_RECORD_CONTEXT")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = _backup(project, datetime.datetime.now(), run)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_path = {str(actor.get_path_name()): actor for actor in actors}
    for row in record["created"]:
        binding = _binding_by_guid(sequence, row["binding_guid"])
        actor = by_path.get(row["actor_path"])
        if binding is None or actor is None or TAG not in [str(value) for value in actor.tags]:
            stop(run, "reason=REVERT_CREATED_CHANGED|label=" + row["label"])
        binding.remove()
        if not unreal.EditorLevelLibrary.destroy_actor(actor):
            stop(run, "reason=REVERT_ACTOR_REMOVE|label=" + row["label"])
    index = _index()
    for row in record["originals"]:
        actor = _one(index, row["label"], run)
        if str(actor.get_path_name()) != row["actor_path"]:
            stop(run, "reason=REVERT_ORIGINAL_CHANGED|label=" + row["label"])
        actor.set_actor_hidden_in_game(bool(row["hidden_in_game"]))
        actor.get_component_by_class(unreal.StaticMeshComponent).set_visibility(bool(row["component_visible"]), True)
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if bool(actor.is_hidden()) != bool(row["hidden_in_game"]) or bool(component.is_visible()) != bool(row["component_visible"]):
            stop(run, "reason=REVERT_VISIBILITY_READBACK|label=" + row["label"])
    census = _save(run)
    archived = _record_path() + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(_record_path(), archived)
    unreal.log("S3_WAVE_SPLIT_DONE|run=%s|reverted|backup=%s|census=%s" %
               (run, backup, json.dumps(census, sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_WAVE_SPLIT_APPLY"))
    revert = bool(globals().get("S3_WAVE_SPLIT_REVERT"))
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
    if apply and os.path.exists(_record_path()):
        stop(run, "reason=APPLY_RECORD_EXISTS")
    if revert and not os.path.isfile(_record_path()):
        stop(run, "reason=REVERT_RECORD_ABSENT")
    sequence, rise = unreal.load_asset(ROOT_PATH), unreal.load_asset(RISE_PATH)
    if not isinstance(sequence, unreal.LevelSequence) or not isinstance(rise, unreal.LevelSequence):
        stop(run, "reason=SEQUENCE_LOAD_FAILED")
    if revert:
        _revert(sequence, run)
        return
    try:
        state, runtime, root, landed, dock = _live_state(sequence, rise, world, run)
        plan = plan_wave_split(state)
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    if not apply:
        if package_census() != census:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES")
        summary = dict(plan)
        summary["pieces"] = [{key: piece[key] for key in
                              ("label", "row", "piece", "source_label", "target_width_cm",
                               "centre_y_cm", "depth_offset_cm", "phase_delay_frames",
                               "seam_error_cm", "controlled_overhang_cm")}
                             for piece in plan["pieces"]]
        unreal.log("S3_WAVE_SPLIT_DRY_RUN_OK|run=%s|mutated=0|plan=%s" %
                   (run, json.dumps(summary, separators=(",", ":"), sort_keys=True)))
        return
    _apply(sequence, runtime, root, landed, dock, plan, run)


if unreal is not None:
    main()
