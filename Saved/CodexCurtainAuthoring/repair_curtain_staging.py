"""Guarded one-shot repair for the production curtain staging pass.

This updates only the curtain Blueprint, its eight managed Level Sequences,
the five post-Scene interaction cues, and the managed Master. It requires the
known 15-second pre-state and a completely clean editor before mutation.
"""

import json
import math
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
BLUEPRINT_PATH = INTERACTION_DIR + "/BP_InfinityStageSequenceCurtain"
CURTAIN_MESH_PATH = (
    "/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/"
    "SM_FireSafetyCurtain_01.SM_FireSafetyCurtain_01"
)

OLD_END = 375
NEW_END = 500
NEW_SECONDS = 20.0
OLD_KEYS = [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)]
NEW_KEYS = [(0, 0.0), (75, 1.0), (400, 1.0), (500, 0.0)]
MARKERS = [
    (75, "InfinityStage.CurtainFullyDown"),
    (75, "InfinityStage.BoyCatStart"),
    (375, "InfinityStage.HiddenChangeover"),
    (400, "InfinityStage.CurtainRiseStart"),
    (500, "InfinityStage.CurtainFullyOpen"),
]

SEQUENCE_NAMES = [
    "LS_Interaction_Template",
    "LS_Opening_Curtain",
    "LS_Interaction_01_WashingTheBoy",
    "LS_Interaction_02_Turnips",
    "LS_Interaction_03_ForgetsHisName",
    "LS_Interaction_04_GetsAName",
    "LS_Interaction_05_BecomesKing",
    "LS_Closing_Curtain",
]
RETIMED_NAMES = {
    "LS_Interaction_Template",
    "LS_Interaction_01_WashingTheBoy",
    "LS_Interaction_02_Turnips",
    "LS_Interaction_03_ForgetsHisName",
    "LS_Interaction_04_GetsAName",
    "LS_Interaction_05_BecomesKing",
}

DASH = chr(0x2014)
INTERACTIONS = [
    ("Interaction 1 " + DASH + " Washing the Boy", "LS_Interaction_01_WashingTheBoy"),
    ("Interaction 2 " + DASH + " Turnips", "LS_Interaction_02_Turnips"),
    ("Interaction 3 " + DASH + " Forgets His Name", "LS_Interaction_03_ForgetsHisName"),
    ("Interaction 4 " + DASH + " Gets a Name", "LS_Interaction_04_GetsAName"),
    ("Interaction 5 " + DASH + " Becomes King", "LS_Interaction_05_BecomesKing"),
]


def object_path(value):
    if value is None:
        return ""
    return value.get_path_name() if hasattr(value, "get_path_name") else str(value)


def package_path(value):
    return object_path(value).split(".", 1)[0]


def package_name(value):
    return str(value.get_name()) if hasattr(value, "get_name") else str(value)


def frame_value(value):
    try:
        return int(value.value)
    except Exception:
        return int(value)


def near(left, right, tolerance=0.001):
    return math.isclose(float(left), float(right), abs_tol=tolerance)


def vector_near(value, expected):
    return near(value.x, expected[0]) and near(value.y, expected[1]) and near(value.z, expected[2])


def transform_at_z(z_value, uniform_scale):
    result = unreal.Transform()
    result.set_editor_property("rotation", unreal.Quat(0.0, 0.0, 0.0, 1.0))
    result.set_editor_property("translation", unreal.Vector(0.0, 0.0, float(z_value)))
    result.set_editor_property(
        "scale3d", unreal.Vector(float(uniform_scale), float(uniform_scale), float(uniform_scale))
    )
    return result


def require_clean_editor():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = package_path(world)
    if world_path != EXPECTED_WORLD:
        raise RuntimeError(f"Unexpected editor world: {world_path}")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if dirty_content or dirty_maps:
        raise RuntimeError(f"Repair requires a clean editor: {dirty_content}/{dirty_maps}")
    return world_path


def sequence_path(name):
    return INTERACTION_DIR + "/" + name


def tracks_for(sequence):
    bindings = list(sequence.get_bindings())
    spawnables = list(sequence.get_spawnables())
    if len(bindings) != 1 or len(spawnables) != 1:
        raise RuntimeError(
            f"Unexpected binding/spawnable counts for {package_path(sequence)}: "
            f"{len(bindings)}/{len(spawnables)}"
        )
    binding = bindings[0]
    tracks = list(binding.get_tracks())
    float_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneFloatTrack"]
    bool_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneBoolTrack"]
    spawn_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneSpawnTrack"]
    if len(tracks) != 3 or len(float_tracks) != 1 or len(bool_tracks) != 1 or len(spawn_tracks) != 1:
        raise RuntimeError(
            f"Unexpected curtain tracks for {package_path(sequence)}: "
            f"{[track.get_class().get_name() for track in tracks]}"
        )
    return binding, float_tracks[0], bool_tracks[0], spawn_tracks[0]


def float_channel_for(track, expected_end):
    sections = list(track.get_sections())
    if len(sections) != 1:
        raise RuntimeError(f"Unexpected float section count: {len(sections)}")
    section = sections[0]
    actual_range = (frame_value(section.get_start_frame()), frame_value(section.get_end_frame()))
    if actual_range != (0, expected_end):
        raise RuntimeError(f"Unexpected float section range: {actual_range}")
    channels = list(section.get_all_channels())
    if len(channels) != 1 or channels[0].get_class().get_name() != "MovieSceneScriptingFloatChannel":
        raise RuntimeError("Unexpected CurtainProgress channel")
    return section, channels[0]


def read_float_keys(channel):
    rows = []
    for key in channel.get_keys():
        time = key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        rows.append((frame_value(time.frame_number), float(key.get_value()), key))
    rows.sort(key=lambda row: row[0])
    return rows


def require_old_framing(owner, label, template_state=False):
    if bool(owner.get_editor_property("curtain_active")) == bool(template_state):
        raise RuntimeError(f"{label} curtain active state has changed")
    if not bool(owner.get_editor_property("follow_player_camera")):
        raise RuntimeError(f"{label} does not follow the player camera")
    if bool(owner.get_editor_property("use_authored_open_closed_transforms")) == bool(template_state):
        raise RuntimeError(f"{label} authored-transform state has changed")
    if not near(owner.get_editor_property("curtain_distance_cm"), 500.0):
        raise RuntimeError(f"{label} curtain distance has changed")
    if not vector_near(owner.get_editor_property("curtain_view_local_offset_cm"), (0.0, 0.0, 0.0)):
        raise RuntimeError(f"{label} view-local offset has changed")
    rotation = owner.get_editor_property("curtain_view_rotation_offset")
    if not (near(rotation.pitch, 0.0) and near(rotation.yaw, 0.0) and near(rotation.roll, 0.0)):
        raise RuntimeError(f"{label} view rotation offset has changed")
    opened = owner.get_editor_property("curtain_open_relative_transform")
    closed = owner.get_editor_property("curtain_closed_relative_transform")
    if not vector_near(opened.translation, (0.0, 0.0, 700.0)) or not vector_near(opened.scale3d, (1.1, 1.1, 1.1) if template_state else (1.0, 1.0, 1.0)):
        raise RuntimeError(f"{label} open transform has changed: {opened}")
    if not vector_near(closed.translation, (0.0, 0.0, 0.0 if template_state else -500.0)) or not vector_near(closed.scale3d, (1.1, 1.1, 1.1) if template_state else (1.0, 1.0, 1.0)):
        raise RuntimeError(f"{label} closed transform has changed: {closed}")


def set_new_framing(owner):
    owner.set_editor_property("curtain_active", True)
    owner.set_editor_property("follow_player_camera", True)
    owner.set_editor_property("use_authored_open_closed_transforms", True)
    owner.set_editor_property("curtain_distance_cm", 1500.0)
    owner.set_editor_property("curtain_view_local_offset_cm", unreal.Vector(0.0, 0.0, 0.0))
    owner.set_editor_property("curtain_view_rotation_offset", unreal.Rotator())
    owner.set_editor_property("curtain_open_relative_transform", transform_at_z(1400.0, 3.5))
    owner.set_editor_property("curtain_closed_relative_transform", transform_at_z(-1750.0, 3.5))
    owner.set_editor_property("curtain_progress", 0.0)


world_path = require_clean_editor()
blueprint = unreal.load_asset(BLUEPRINT_PATH)
show = unreal.load_asset(SHOW_PATH)
master = unreal.load_asset(MASTER_PATH)
if blueprint is None or show is None or master is None:
    raise RuntimeError(f"Missing production assets: blueprint={blueprint}, show={show}, master={master}")

generated_class = blueprint.generated_class()
if generated_class is None:
    raise RuntimeError(f"Missing generated class for {BLUEPRINT_PATH}")
cdo = unreal.get_default_object(generated_class)
require_old_framing(cdo, "Blueprint CDO")
curtain_mesh = cdo.get_editor_property("curtain_mesh")
if object_path(curtain_mesh.get_editor_property("static_mesh")) != CURTAIN_MESH_PATH:
    raise RuntimeError("Curtain Blueprint no longer uses the approved fire-safety curtain mesh")

sequences = {}
retime_rows = {}
for name in SEQUENCE_NAMES:
    sequence = unreal.load_asset(sequence_path(name))
    if sequence is None:
        raise RuntimeError(f"Missing managed sequence: {sequence_path(name)}")
    rate = sequence.get_display_rate()
    tick = sequence.get_tick_resolution()
    if (int(rate.numerator), int(rate.denominator)) != (25, 1):
        raise RuntimeError(f"Unexpected display rate for {sequence_path(name)}: {rate}")
    if (int(tick.numerator), int(tick.denominator)) != (24000, 1):
        raise RuntimeError(f"Unexpected tick resolution for {sequence_path(name)}: {tick}")
    expected_end = OLD_END
    if frame_value(sequence.get_playback_start()) != 0 or frame_value(sequence.get_playback_end()) != expected_end:
        raise RuntimeError(f"Unexpected playback range for {sequence_path(name)}")
    binding, float_track, bool_track, spawn_track = tracks_for(sequence)
    template = binding.get_object_template()
    require_old_framing(template, sequence_path(name) + " template", True)
    if name in RETIMED_NAMES:
        section, channel = float_channel_for(float_track, OLD_END)
        key_rows = read_float_keys(channel)
        actual = [(frame, value) for frame, value, _ in key_rows]
        if len(actual) != len(OLD_KEYS) or any(
            frame != expected_frame or not near(value, expected_value)
            for (frame, value), (expected_frame, expected_value) in zip(actual, OLD_KEYS)
        ):
            raise RuntimeError(f"Unexpected pre-repair keys for {sequence_path(name)}: {actual}")
        if list(unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(sequence, unreal.MovieSceneTimeUnit.DISPLAY_RATE)):
            raise RuntimeError(f"Expected no pre-existing markers in {sequence_path(name)}")
        retime_rows[name] = (section, channel, key_rows, bool_track, spawn_track)
    sequences[name] = (sequence, template)

show_cues = list(show.get_editor_property("cues"))
managed = {}
for index, cue in enumerate(show_cues):
    label = str(cue.get_editor_property("label"))
    if label in {row[0] for row in INTERACTIONS}:
        if label in managed:
            raise RuntimeError(f"Duplicate managed Show cue: {label}")
        managed[label] = (index, cue)
if set(managed) != {row[0] for row in INTERACTIONS}:
    raise RuntimeError(f"Managed interaction cue mismatch: {sorted(managed)}")

for label, asset_name in INTERACTIONS:
    _, cue = managed[label]
    scene = cue.get_editor_property("scene")
    timing = tuple(
        frame_value(scene.get_editor_property(field))
        for field in (
            "curtain_entry_transition_frames",
            "curtain_hold_frames",
            "curtain_exit_transition_frames",
        )
    )
    if package_path(scene.get_editor_property("sequence")) != sequence_path(asset_name):
        raise RuntimeError(f"Unexpected sequence reference for {label}")
    if timing != (48000, 264000, 48000):
        raise RuntimeError(f"Unexpected pre-repair timing for {label}: {timing}")
    if frame_value(scene.get_editor_property("duration_frames")) != 360000:
        raise RuntimeError(f"Unexpected pre-repair duration for {label}")
    if not bool(scene.get_editor_property("use_sequence_length")):
        raise RuntimeError(f"{label} is not sequence-length driven")
    if not bool(scene.get_editor_property("sequence_owns_curtain")):
        raise RuntimeError(f"{label} no longer sequence-owns its curtain")
    if not bool(scene.get_editor_property("retain_previous_camera")):
        raise RuntimeError(f"{label} no longer retains the prior Scene camera")
    if not bool(scene.get_editor_property("reveal_next_passage_when_covered")):
        raise RuntimeError(f"{label} no longer performs a covered reveal")
    if scene.get_editor_property("curtain_mode") != unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL:
        raise RuntimeError(f"Unexpected curtain mode for {label}")

# All guards passed. From here on, mutate only the exact managed assets.
set_new_framing(cdo)

for name, (sequence, template) in sequences.items():
    set_new_framing(template)
    if name not in RETIMED_NAMES:
        continue
    section, channel, key_rows, bool_track, spawn_track = retime_rows[name]
    sequence.set_playback_end(NEW_END)
    if hasattr(sequence, "set_work_range_end_seconds"):
        sequence.set_work_range_end_seconds(NEW_SECONDS)
    if hasattr(sequence, "set_view_range_end_seconds"):
        sequence.set_view_range_end_seconds(NEW_SECONDS)
    for (_, _, key), (new_frame, new_value) in zip(key_rows, NEW_KEYS):
        key.set_time(unreal.FrameNumber(value=new_frame), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        key.set_value(float(new_value))
    section.set_range(0, NEW_END)
    for track in (bool_track, spawn_track):
        for track_section in track.get_sections():
            track_section.set_range(0, NEW_END)
    sequence.delete_marked_frames()
    for frame, label in MARKERS:
        marked = unreal.MovieSceneMarkedFrame()
        marked.frame_number = unreal.FrameNumber(value=frame)
        marked.label = label
        unreal.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(sequence, marked, unreal.MovieSceneTimeUnit.DISPLAY_RATE)

for label, _ in INTERACTIONS:
    index, cue = managed[label]
    scene = cue.get_editor_property("scene")
    scene.set_editor_property("duration_frames", unreal.FrameNumber(value=480000))
    scene.set_editor_property("curtain_entry_transition_frames", unreal.FrameNumber(value=72000))
    scene.set_editor_property("curtain_hold_frames", unreal.FrameNumber(value=312000))
    scene.set_editor_property("curtain_exit_transition_frames", unreal.FrameNumber(value=96000))
    cue.set_editor_property("scene", scene)
    show_cues[index] = cue
show.set_editor_property("cues", show_cues)
show.ensure_stable_ids()
show.reconcile_passage_settings()

result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
if isinstance(result, tuple):
    rebuilt, rebuild_report = bool(result[0]), str(result[1])
else:
    rebuilt, rebuild_report = bool(result), ""
if not rebuilt:
    raise RuntimeError(f"Managed Master rebuild failed: {rebuild_report}")

expected_paths = {
    BLUEPRINT_PATH,
    SHOW_PATH,
    MASTER_PATH,
    *[sequence_path(name) for name in SEQUENCE_NAMES],
}
dirty_content = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
unexpected_dirty = sorted(set(dirty_content) - expected_paths)
if unexpected_dirty or dirty_maps:
    raise RuntimeError(
        f"Unexpected dirty packages before save: content={dirty_content}, maps={dirty_maps}, "
        f"unexpected={unexpected_dirty}"
    )

assets_to_save = [blueprint]
assets_to_save.extend(sequence for sequence, _ in sequences.values())
assets_to_save.extend([show, master])
saved = []
for asset in assets_to_save:
    path = package_path(asset)
    if path not in expected_paths:
        raise RuntimeError(f"Refusing to save unexpected asset: {path}")
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
        raise RuntimeError(f"Save failed for {path}")
    saved.append(path)

dirty_content_after = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps_after = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content_after or dirty_maps_after:
    raise RuntimeError(
        f"Curtain staging repair left dirty packages: {dirty_content_after}/{dirty_maps_after}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "framing": {
        "distance_cm": 1500.0,
        "open_z": 1400.0,
        "closed_z": -1750.0,
        "scale": 3.5,
    },
    "retimed_sequences": sorted(RETIMED_NAMES),
    "keys": NEW_KEYS,
    "markers": MARKERS,
    "interaction_timing_ticks": [72000, 312000, 96000],
    "rebuild_report": rebuild_report,
    "saved": saved,
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "repair_curtain_staging.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_STAGING_REPAIR_SUCCESS"
    f"|framed={len(SEQUENCE_NAMES)}|retimed={len(RETIMED_NAMES)}"
    f"|show_cues={len(INTERACTIONS)}|saved={len(saved)}|dirty_content=0|dirty_maps=0"
)
