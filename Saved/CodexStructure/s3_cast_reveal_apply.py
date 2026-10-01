"""Author Scene 3's landing reveal and reversibly retire the old clam set.

Dry run is the default. S3_CAST_REVEAL_APPLY records and backs up the level
and LS_S3_HangarRise, hides the nine cast actors in the saved level, gives each
one a visibility track that reveals it 0.5 s after the hangar lands, and hides
and disables the four retired actors. S3_CAST_REVEAL_REVERT first verifies the
recorded applied state, then restores every recorded property and removes only
the bindings/tracks added by apply.

plan() is deliberately Unreal-free for test_s3_cast_reveal_plan.py.
"""
import collections
import copy
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
ROOT_LABEL = "S3 Hangar Root"
TRACK_NAME = "RigAtmos S3 Cast Reveal"
REMOVED_TAG = "RigAtmos.RemovedFromS3"
REMOVED_FOLDER = "RigAtmos/RemovedFromS3"
REVEAL_DELAY_S = 0.5

SHORE_IDS = (
    "Shore01_M56",
    "Shore02_F52",
    "Shore03_M59",
    "Shore04_F55",
    "Shore05_M53",
    "Shore06_F25",
)
CAST_LABELS = tuple(value + " Clam" for value in SHORE_IDS) + (
    "Clam_with_Pearl_Clam_with_Pearl_0",
    "source_Anim",
    "tg0pfjxda_tier_0",
)
REMOVE_LABELS = (
    "SM_P03_CeladonPalatialAntechamber_01_L",
    "SM_P03_CeladonPalatialAntechamber_01_L2",
    "SM_P03_CeladonPalatialAntechamber_01_L3",
    "PointLight",
)
ALL_TARGET_LABELS = CAST_LABELS + REMOVE_LABELS

# The installed launcher headers declare a visibility-specific source-value
# processor but do not include its implementation. The apply assumption is the
# normal Sequencer UI reading: a visibility-channel True value means visible.
# Dry run always prints both possible readings so this inference is explicit.
VISIBILITY_HEADER_FINDING = "UNCLEAR_FROM_INSTALLED_UE58_HEADERS"
APPLY_KEY_SEMANTICS = "key_value_means_visible"

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexStructure",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_RECORD = os.path.join(HERE, "s4_rekey_window_record.json")
HANGAR_PLAN = os.path.join(HERE, "hangar_s3_plan.json")
LANDSCAPE_SWEEP = os.path.join(HERE, "landscape_sweep.json")
RECORD = os.path.join(HERE, "s3_cast_reveal_record.json")


def _close(a, b, tolerance=1e-6):
    return abs(float(a) - float(b)) <= tolerance


def _time_close(a, b):
    # The live sequence is frame-quantized; this pure guard allows one 24-fps frame.
    return _close(a, b, 1.0 / 24.0 + 1e-9)


def _plain_keys(keys):
    return [[float(time_s), float(value)] for time_s, value in keys]


def plan(labels_found, root_keys, W0, W1):
    """Validate labels/timing and return the complete, Unreal-free target plan."""
    W0, W1 = float(W0), float(W1)
    if not W0 < 0.0 < W1:
        raise ValueError(f"required W0 < 0 < W1, found W0={W0}, W1={W1}")

    counts = collections.Counter(str(label) for label in labels_found)
    bad_counts = {label: counts[label] for label in ALL_TARGET_LABELS if counts[label] != 1}
    if bad_counts:
        raise ValueError(f"target labels must each occur exactly once: {bad_counts}")

    got_root = _plain_keys(root_keys)
    expected_root = [[W0, -90.0], [W1, 0.0]]
    if len(got_root) != 2 or any(
        not _time_close(got_time, wanted_time) or not _close(got_value, wanted_value, 1e-3)
        for (got_time, got_value), (wanted_time, wanted_value) in zip(got_root, expected_root)
    ):
        raise ValueError(f"S3 root keys {got_root!r} do not match applied retime {expected_root!r}")

    reveal_s = round(W1 + float(REVEAL_DELAY_S), 4)
    if reveal_s <= W1:
        raise ValueError(f"REVEAL_S={reveal_s} must be after W1={W1}")

    visible_reading = [[0.0, False], [reveal_s, True]]
    hidden_reading = [[0.0, True], [reveal_s, False]]
    return {
        "W0": W0,
        "W1": W1,
        "reveal_s": reveal_s,
        "reveals": list(CAST_LABELS),
        "removals": list(REMOVE_LABELS),
        "root_keys": expected_root,
        "visibility_header_finding": VISIBILITY_HEADER_FINDING,
        "apply_key_semantics": APPLY_KEY_SEMANTICS,
        "keys_if_value_means_visible": visible_reading,
        "keys_if_value_means_hidden": hidden_reading,
        "apply_keys": visible_reading,
    }


def fail(run, message):
    unreal.log_error(f"S3_CAST_REVEAL_STOPPED|run={run}|{message}")
    raise RuntimeError(message)


def package_census():
    return {
        "dirty_maps": sorted(str(package.get_name()) for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "dirty_content": sorted(
            str(package.get_name()) for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ),
    }


def guid_text(guid):
    return str(unreal.GuidLibrary.conv_guid_to_string(guid))


def object_path(value):
    return str(value.get_path_name()) if value is not None and hasattr(value, "get_path_name") else str(value)


def all_level_actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def exact_actors(actors, run):
    found = {}
    for label in ALL_TARGET_LABELS:
        matches = [actor for actor in actors if str(actor.get_actor_label()) == label]
        if len(matches) != 1:
            fail(run, f"expected exactly one actor labelled {label!r}, found {len(matches)}")
        found[label] = matches[0]

    for shore_id in SHORE_IDS:
        label = shore_id + " Clam"
        expected_class = "BP_" + shore_id + "_Draped_C"
        got_class = str(found[label].get_class().get_name())
        if got_class != expected_class:
            fail(run, f"{label}: class {got_class!r}, expected {expected_class!r}")
    if not isinstance(found["source_Anim"], unreal.SkeletalMeshActor):
        fail(run, "source_Anim is not a SkeletalMeshActor")
    return found


def one_light_component(actor, run):
    components = list(actor.get_components_by_class(unreal.LightComponent))
    if len(components) != 1:
        fail(run, f"PointLight must have exactly one LightComponent, found {len(components)}")
    return components[0]


def root_pitch_keys(sequence, run):
    bindings = [binding for binding in sequence.get_bindings() if str(binding.get_display_name()) == ROOT_LABEL]
    if len(bindings) != 1:
        fail(run, f"expected one {ROOT_LABEL!r} binding, found {len(bindings)}")
    tracks = [track for track in bindings[0].get_tracks() if isinstance(track, unreal.MovieScene3DTransformTrack)]
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        fail(run, f"{ROOT_LABEL}: expected one transform track and section")
    channels = list(tracks[0].get_sections()[0].get_all_channels())
    if len(channels) <= 4:
        fail(run, f"{ROOT_LABEL}: transform section has only {len(channels)} channels")
    fps = sequence.get_display_rate().numerator / float(sequence.get_display_rate().denominator)
    return [[key.get_time().frame_number.value / fps, float(key.get_value())] for key in channels[4].get_keys()]


def read_inputs(run):
    for path in (WINDOW_RECORD, HANGAR_PLAN, LANDSCAPE_SWEEP):
        if not os.path.isfile(path):
            fail(run, f"required input is missing: {path}")
    with open(WINDOW_RECORD, encoding="utf-8") as handle:
        timing = json.load(handle)
    W0, W1 = timing.get("W0"), timing.get("W1")
    if W0 is None or W1 is None:
        fail(run, f"{os.path.basename(WINDOW_RECORD)} has no W0/W1")

    with open(HANGAR_PLAN, encoding="utf-8") as handle:
        hangar = json.load(handle)
    dock = hangar.get("dock", {})
    loc, yaw = dock.get("loc"), dock.get("yaw")
    if not isinstance(loc, list) or len(loc) != 3 or yaw is None:
        fail(run, f"{os.path.basename(HANGAR_PLAN)} has no valid dock loc/yaw")
    if abs(float(yaw)) > 1e-3:
        fail(run, f"S3 dock yaw is {yaw}, expected 0 for the specified world-offset check")

    with open(LANDSCAPE_SWEEP, encoding="utf-8") as handle:
        sweep = json.load(handle)
    sweep_rows = [
        row
        for group in ("standing_on_landscape", "near_landscape")
        for row in sweep.get(group, [])
        if row.get("label") == "PointLight"
    ]
    return float(W0), float(W1), [float(value) for value in loc], sweep_rows


def point_light_guard(actor, dock, run):
    offset = (2063.0, -631.0, 322.5)
    expected = [dock[index] + offset[index] for index in range(3)]
    location = actor.get_actor_location()
    got = [float(location.x), float(location.y), float(location.z)]
    distance = math.dist(got, expected)
    # 100 cm: the expected point came from landscape_sweep.json's base_z, not the actor location (run 120556 read 51.988 cm).
    # The label is also checked unique; this only proves it is the S3 clam light, not one elsewhere.
    if distance > 100.0:
        fail(run, f"PointLight is {distance:.3f} cm from dock + offset; expected <= 100 cm")
    return {"world": got, "expected_world": expected, "distance_cm": distance}


def root_completion_mode(sequence, run):
    """The cast follow the BOX: copy the root transform section's completion mode.
    KEEP_STATE would leave the cast visible after a transport rewind to P03 (over the pit)."""
    bindings = [binding for binding in sequence.get_bindings() if str(binding.get_display_name()) == ROOT_LABEL]
    tracks = [track for track in bindings[0].get_tracks() if isinstance(track, unreal.MovieScene3DTransformTrack)] if len(bindings) == 1 else []
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        fail(run, f"{ROOT_LABEL}: expected one transform track and section for its completion mode")
    return completion_mode_name(tracks[0].get_sections()[0], run)


def completion_mode_name(section, run):
    try:
        mode = section.get_completion_mode()
    except Exception:
        try:
            mode = section.get_editor_property("eval_options").get_editor_property("completion_mode")
        except Exception as exc:
            fail(run, f"could not read section completion mode: {exc}")
    if not hasattr(mode, "name"):
        fail(run, f"section completion mode has no .name: {mode!r}")
    return str(mode.name)


def section_coverage(scene, rise, run):
    matches = []
    for track in scene.get_tracks():
        if not isinstance(track, unreal.MovieSceneSubTrack):
            continue
        for section in track.get_sections():
            nested = section.get_sequence()
            if nested and nested.get_path_name().split(".", 1)[0] == RISE:
                matches.append((track, section))
    scene_range = [float(scene.get_playback_start_seconds()), float(scene.get_playback_end_seconds())]
    rise_range = [float(rise.get_playback_start_seconds()), float(rise.get_playback_end_seconds())]
    if len(matches) != 1:
        return {
            "scene_playback_s": scene_range,
            "rise_playback_s": rise_range,
            "nest_count": len(matches),
            "blocker": f"expected one LS_S3_HangarRise nest section, found {len(matches)}",
        }
    track, section = matches[0]
    section_range = [float(section.get_start_frame_seconds()), float(section.get_end_frame_seconds())]
    completion = completion_mode_name(section, run)
    overrun = scene_range[1] > section_range[1] + 1.0 / 24.0
    blocker = None
    if overrun and completion == "RESTORE_STATE":
        blocker = (
            f"scene ends at {scene_range[1]:.4f}s after rise section {section_range[1]:.4f}s "
            "with RESTORE_STATE"
        )
    return {
        "scene_playback_s": scene_range,
        "rise_playback_s": rise_range,
        "nest_count": 1,
        "nest_track": str(track.get_display_name()),
        "nest_section_s": section_range,
        "completion_mode": completion,
        "scene_overruns_nest": overrun,
        "blocker": blocker,
    }


def assert_guards(editor, actors, run, applying, reverting):
    census = package_census()
    if census["dirty_maps"] or census["dirty_content"]:
        fail(run, f"packages already dirty: {census}")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail(run, "Sequencer is open")
    temps = sorted(
        str(actor.get_actor_label())
        for actor in actors
        if str(actor.get_actor_label()).startswith(("ZZ_", "TEMP_"))
        or str(actor.get_name()).startswith(("ZZ_", "TEMP_"))
    )
    if temps:
        fail(run, f"temporary actors present: {temps}")
    if applying and os.path.exists(RECORD):
        fail(run, "already applied (record exists); revert first")
    if reverting and not os.path.exists(RECORD):
        fail(run, "revert record is absent")
    if not (applying or reverting) and os.path.exists(RECORD):
        fail(run, "dry run refused because the apply record exists; revert first")


def actor_state(actor, point_component=None):
    state = {
        "object_path": object_path(actor),
        "class": str(actor.get_class().get_name()),
        "hidden": bool(actor.get_editor_property("hidden")),
    }
    if str(actor.get_actor_label()) in REMOVE_LABELS:
        state.update(
            {
                "collision": bool(actor.get_actor_enable_collision()),
                "tags": [str(tag) for tag in actor.get_editor_property("tags")],
                "folder": str(actor.get_folder_path()),
            }
        )
    if point_component is not None:
        state["light_visible"] = bool(point_component.get_editor_property("visible"))
    return state


def capture_states(targets, point_component):
    return {
        label: actor_state(actor, point_component if label == "PointLight" else None)
        for label, actor in targets.items()
    }


def planned_states(before):
    after = copy.deepcopy(before)
    for label in CAST_LABELS:
        after[label]["hidden"] = True
    for label in REMOVE_LABELS:
        after[label]["hidden"] = True
        after[label]["collision"] = False
        after[label]["folder"] = REMOVED_FOLDER
        if REMOVED_TAG not in after[label]["tags"]:
            after[label]["tags"].append(REMOVED_TAG)
    after["PointLight"]["light_visible"] = False
    return after


def set_states(targets, wanted, point_component):
    for label, actor in targets.items():
        row = wanted[label]
        actor.modify()
        actor.set_editor_property("hidden", bool(row["hidden"]))
        if label in REMOVE_LABELS:
            actor.set_actor_enable_collision(bool(row["collision"]))
            actor.set_editor_property("tags", [unreal.Name(tag) for tag in row["tags"]])
            actor.set_folder_path(unreal.Name(row["folder"]))
        if label == "PointLight":
            point_component.modify()
            point_component.set_editor_property("visible", bool(row["light_visible"]))


def bindings_for_actor(sequence, actor, world):
    wanted = object_path(actor)
    found = []
    for binding in sequence.get_bindings():
        try:
            resolved = list(sequence.locate_bound_objects(binding, world))
        except Exception:
            continue
        if len(resolved) == 1 and object_path(resolved[0]) == wanted:
            found.append(binding)
    return found


def visibility_tracks(binding):
    return [
        track
        for track in binding.get_tracks()
        if str(track.get_class().get_name()) == "MovieSceneVisibilityTrack"
    ]


def binding_by_guid(sequence, guid):
    found = [binding for binding in sequence.get_bindings() if guid_text(binding.get_id()) == guid]
    return found[0] if len(found) == 1 else None


def bool_keys(channel, fps):
    return [
        [key.get_time().frame_number.value / fps, bool(key.get_value())]
        for key in channel.get_keys()
    ]


def bool_keys_match(got, wanted, fps):
    if len(got) != len(wanted):
        return False
    return all(
        abs(float(got_time) - float(wanted_time)) <= 1.0 / fps + 1e-9 and bool(got_value) == bool(wanted_value)
        for (got_time, got_value), (wanted_time, wanted_value) in zip(got, wanted)
    )


def named_visibility_track(binding, run):
    tracks = [
        track
        for track in visibility_tracks(binding)
        if str(track.get_display_name()) == TRACK_NAME
    ]
    if len(tracks) != 1:
        fail(run, f"binding {guid_text(binding.get_id())} has {len(tracks)} named visibility tracks")
    return tracks[0]


def verify_binding_rows(sequence, world, rows, expected_keys, run):
    fps = sequence.get_display_rate().numerator / float(sequence.get_display_rate().denominator)
    playback_end = float(sequence.get_playback_end_seconds())
    readback = []
    for row in rows:
        binding = binding_by_guid(sequence, row["binding_guid"])
        if binding is None:
            fail(run, f"binding GUID {row['binding_guid']} is absent or duplicated")
        resolved = [object_path(value) for value in sequence.locate_bound_objects(binding, world)]
        if resolved != [row["actor_path"]]:
            fail(run, f"{row['label']}: binding {row['binding_guid']} resolves to {resolved}")
        track = named_visibility_track(binding, run)
        sections = list(track.get_sections())
        if len(sections) != 1:
            fail(run, f"{row['label']}: visibility track has {len(sections)} sections")
        channels = list(sections[0].get_all_channels())
        if len(channels) != 1:
            fail(run, f"{row['label']}: visibility section has {len(channels)} channels")
        got_keys = bool_keys(channels[0], fps)
        if not bool_keys_match(got_keys, expected_keys, fps):
            fail(run, f"{row['label']}: visibility keys {got_keys}, wanted {expected_keys}")
        wanted_mode = root_completion_mode(sequence, run)
        if completion_mode_name(sections[0], run) != wanted_mode:
            fail(run, f"{row['label']}: visibility section is not {wanted_mode} (the root's mode)")
        section_range = [sections[0].get_start_frame_seconds(), sections[0].get_end_frame_seconds()]
        if abs(section_range[0]) > 1.0 / fps or abs(section_range[1] - playback_end) > 1.0 / fps:
            fail(run, f"{row['label']}: visibility section range {section_range}, expected [0,{playback_end}]")
        readback.append(
            {
                "label": row["label"],
                "binding_guid": row["binding_guid"],
                "resolved": resolved,
                "keys": got_keys,
                "completion_mode": wanted_mode,
            }
        )
    return readback


def author_visibility(sequence, world, targets, planned, run):
    if not hasattr(unreal, "MovieSceneVisibilityTrack"):
        fail(run, "unreal.MovieSceneVisibilityTrack is unavailable")
    fps = sequence.get_display_rate().numerator / float(sequence.get_display_rate().denominator)
    playback_end = float(sequence.get_playback_end_seconds())
    rows = []
    for label in CAST_LABELS:
        actor = targets[label]
        existing = bindings_for_actor(sequence, actor, world)
        if len(existing) > 1:
            fail(run, f"{label}: {len(existing)} possessable bindings resolve to the actor")
        created = not existing
        binding = sequence.add_possessable(actor) if created else existing[0]
        if binding is None or not binding.is_valid():
            fail(run, f"{label}: could not add/reuse a possessable binding")
        if visibility_tracks(binding):
            fail(run, f"{label}: reused binding already has a visibility track")
        track = binding.add_track(unreal.MovieSceneVisibilityTrack)
        if track is None:
            fail(run, f"{label}: could not add MovieSceneVisibilityTrack")
        track.set_display_name(TRACK_NAME)
        section = track.add_section()
        section.set_range_seconds(0.0, playback_end)
        section.set_completion_mode(getattr(unreal.MovieSceneCompletionMode, root_completion_mode(sequence, run)))
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            fail(run, f"{label}: new visibility section has {len(channels)} channels")
        channel = channels[0]
        for time_s, value in planned["apply_keys"]:
            made = channel.add_key(
                unreal.FrameNumber(int(round(float(time_s) * fps))),
                bool(value),
                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
            )
            if made is None:
                fail(run, f"{label}: add_key returned None at {time_s}s")
        rows.append(
            {
                "label": label,
                "actor_path": object_path(actor),
                "binding_guid": guid_text(binding.get_id()),
                "binding_created": created,
                "track_added": True,
            }
        )
    return rows


def binding_actions(sequence, world, targets, run):
    rows = []
    for label in CAST_LABELS:
        bindings = bindings_for_actor(sequence, targets[label], world)
        if len(bindings) > 1:
            fail(run, f"{label}: {len(bindings)} possessable bindings resolve to the actor")
        existing_visibility = sum(len(visibility_tracks(binding)) for binding in bindings)
        if existing_visibility:
            fail(run, f"{label}: an existing actor binding already has a visibility track")
        rows.append(
            {
                "label": label,
                "actor_path": object_path(targets[label]),
                "binding_action": "reuse" if bindings else "add",
                "existing_binding_guid": guid_text(bindings[0].get_id()) if bindings else None,
                "track_action": "add",
            }
        )
    return rows


def write_record(record):
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def disk_asset(project, asset_path, extension):
    return os.path.join(project, "Content", *asset_path[len("/Game/"):].split("/")) + extension


def backup_files(stamp, project):
    backup = os.path.join(project, "Backups", "PreS3CastReveal-" + stamp.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=False)
    sources = (
        disk_asset(project, EXPECTED_WORLD, ".umap"),
        disk_asset(project, RISE, ".uasset"),
        RECORD,
    )
    for source in sources:
        if not os.path.isfile(source):
            fail(stamp.strftime("%H%M%S"), f"backup source missing: {source}")
        copied = shutil.copy2(source, backup)
        destination = os.path.join(backup, os.path.basename(source))
        if os.path.normcase(os.path.normpath(copied)) != os.path.normcase(os.path.normpath(destination)):
            fail(stamp.strftime("%H%M%S"), f"backup copy returned unexpected path: {copied}")
        if os.path.getsize(source) != os.path.getsize(destination):
            fail(stamp.strftime("%H%M%S"), f"backup size mismatch for {source}")
    return backup


def remove_authored_visibility(sequence, rows, run):
    for row in rows:
        binding = binding_by_guid(sequence, row["binding_guid"])
        if binding is None:
            fail(run, f"revert cannot find binding {row['binding_guid']}")
        track = named_visibility_track(binding, run)
        if row["binding_created"]:
            binding.remove()
        elif not binding.remove_track(track):
            fail(run, f"{row['label']}: remove_track returned False")


def verify_removed_visibility(sequence, rows, run):
    for row in rows:
        binding = binding_by_guid(sequence, row["binding_guid"])
        if row["binding_created"]:
            if binding is not None:
                fail(run, f"{row['label']}: added binding remains after revert")
        else:
            if binding is None:
                fail(run, f"{row['label']}: reused binding was removed during revert")
            remaining = [track for track in binding.get_tracks() if str(track.get_display_name()) == TRACK_NAME]
            if remaining:
                fail(run, f"{row['label']}: added visibility track remains after revert")


def require_target_dirty_set(run):
    census = package_census()
    if census["dirty_maps"] != [EXPECTED_WORLD] or census["dirty_content"] != [RISE]:
        fail(run, f"dirty set is not exactly the level and rise sequence: {census}")


def save_targets(run):
    if not unreal.EditorAssetLibrary.save_asset(RISE, only_if_is_dirty=False):
        fail(run, "rise sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail(run, "level save failed")
    census = package_census()
    if census["dirty_maps"] or census["dirty_content"]:
        fail(run, f"targeted saves left dirty packages: {census}")
    return census


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    applying = bool(globals().get("S3_CAST_REVEAL_APPLY"))
    reverting = bool(globals().get("S3_CAST_REVEAL_REVERT"))
    if applying and reverting:
        fail(run, "apply and revert modes are mutually exclusive")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or editor.get_game_world() is not None:
        fail(run, "wrong world, or PIE")
    actors = all_level_actors()
    assert_guards(editor, actors, run, applying, reverting)
    targets = exact_actors(actors, run)
    point_component = one_light_component(targets["PointLight"], run)

    W0, W1, dock, sweep_rows = read_inputs(run)
    rise = unreal.load_asset(RISE)
    scene = unreal.load_asset(SCENE)
    if rise is None or scene is None:
        fail(run, f"required sequence missing: rise={rise is not None}, scene={scene is not None}")
    root_keys = root_pitch_keys(rise, run)
    try:
        planned = plan([actor.get_actor_label() for actor in actors], root_keys, W0, W1)
    except ValueError as exc:
        fail(run, f"plan precondition failed: {exc}")
    loaded_census = package_census()
    if loaded_census["dirty_maps"] or loaded_census["dirty_content"]:
        fail(run, f"loading the required assets changed the clean-package guard: {loaded_census}")

    point_guard = point_light_guard(targets["PointLight"], dock, run)
    coverage = section_coverage(scene, rise, run)
    # Applied visibility tracks are expected during revert, so the pre-apply
    # collision check is meaningful only for dry run/apply.
    actions = [] if reverting else binding_actions(rise, world, targets, run)
    before_states = capture_states(targets, point_component)
    after_states = planned_states(before_states)
    plan_report = {
        "plan": planned,
        "binding_actions": actions,
        "point_light": point_guard,
        "landscape_sweep_pointlight_rows": sweep_rows,
        "section_coverage": coverage,
        "before_states": before_states,
        "after_states": after_states,
        "group_actor0_targeted": False,
        "dirty": package_census(),
    }
    unreal.log(f"S3_CAST_REVEAL_PLAN|run={run}|{json.dumps(plan_report, sort_keys=True)}")
    if coverage["blocker"]:
        unreal.log_warning(f"S3_CAST_REVEAL_BLOCKER|run={run}|{coverage['blocker']}")
    if not (applying or reverting):
        unreal.log(
            f"S3_CAST_REVEAL_DRY_RUN_OK|run={run}|mutated=0|reveals={len(CAST_LABELS)}|"
            f"removals={len(REMOVE_LABELS)}|visibility_semantics={VISIBILITY_HEADER_FINDING}|"
            f"keys_if_value_means_visible={json.dumps(planned['keys_if_value_means_visible'])}|"
            f"keys_if_value_means_hidden={json.dumps(planned['keys_if_value_means_hidden'])}|"
            f"{json.dumps(package_census(), sort_keys=True)}"
        )
        return

    playback_before = [float(rise.get_playback_start_seconds()), float(rise.get_playback_end_seconds())]
    if reverting:
        with open(RECORD, encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("world") != EXPECTED_WORLD or record.get("rise") != RISE:
            fail(run, "revert record names a different world or rise sequence")
        if coverage != record["section_coverage"]:
            fail(run, f"revert refused: nest coverage drifted: {coverage}")
        current_states = capture_states(targets, point_component)
        if current_states != record["after_states"]:
            fail(run, f"revert refused: actor state drifted: {current_states}")
        verify_binding_rows(rise, world, record["bindings"], record["plan"]["apply_keys"], run)
        if playback_before != record["rise_playback_before"]:
            fail(run, "revert refused: rise playback range drifted")

        set_states(targets, record["before_states"], point_component)
        remove_authored_visibility(rise, record["bindings"], run)
        restored_states = capture_states(targets, point_component)
        if restored_states != record["before_states"]:
            fail(run, f"revert actor read-back failed before save: {restored_states}")
        verify_removed_visibility(rise, record["bindings"], run)
        if [float(rise.get_playback_start_seconds()), float(rise.get_playback_end_seconds())] != playback_before:
            fail(run, "rise playback range changed during revert")
        require_target_dirty_set(run)
        census = save_targets(run)
        os.replace(RECORD, RECORD + ".reverted")
        unreal.log(
            f"S3_CAST_REVEAL_DONE|run={run}|reverted|reveals={len(CAST_LABELS)}|"
            f"removals={len(REMOVE_LABELS)}|census={json.dumps(census, sort_keys=True)}"
        )
        return

    if coverage["blocker"]:
        fail(run, f"section coverage BLOCKER: {coverage['blocker']}")
    stamp = datetime.datetime.now()
    record = {
        "written": stamp.isoformat(timespec="seconds"),
        "run": run,
        "world": EXPECTED_WORLD,
        "rise": RISE,
        "scene": SCENE,
        "timing_source": os.path.basename(WINDOW_RECORD),
        "hangar_plan_source": os.path.basename(HANGAR_PLAN),
        "landscape_sweep_source": os.path.basename(LANDSCAPE_SWEEP),
        "plan": copy.deepcopy(planned),
        "point_light_guard": point_guard,
        "section_coverage": copy.deepcopy(coverage),
        "rise_playback_before": playback_before,
        "binding_actions": copy.deepcopy(actions),
        "before_states": copy.deepcopy(before_states),
        "after_states": copy.deepcopy(after_states),
        "bindings": [],
    }
    write_record(record)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = backup_files(stamp, project)

    set_states(targets, after_states, point_component)
    record["bindings"] = author_visibility(rise, world, targets, planned, run)
    write_record(record)
    got_states = capture_states(targets, point_component)
    if got_states != after_states:
        fail(run, f"apply actor read-back failed before save: {got_states}")
    binding_readback = verify_binding_rows(rise, world, record["bindings"], planned["apply_keys"], run)
    if [float(rise.get_playback_start_seconds()), float(rise.get_playback_end_seconds())] != playback_before:
        fail(run, "rise playback range changed during apply")
    if section_coverage(scene, rise, run) != coverage:
        fail(run, "nest section coverage changed during apply")
    require_target_dirty_set(run)
    census = save_targets(run)
    unreal.log(
        f"S3_CAST_REVEAL_DONE|run={run}|applied|reveals={len(CAST_LABELS)}|"
        f"removals={len(REMOVE_LABELS)}|bindings={len(binding_readback)}|backup={backup}|"
        f"visibility_semantics={VISIBILITY_HEADER_FINDING}|apply_assumption={APPLY_KEY_SEMANTICS}|"
        f"census={json.dumps(census, sort_keys=True)}"
    )


if unreal is not None:
    main()
