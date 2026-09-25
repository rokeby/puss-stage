"""Add the missing always-active visibility track to the eight curtain sequences.

Guarded exact-scope mutation:
- intended vertical-slice map only
- PIE/SIE stopped
- zero dirty packages before starting
- each sequence must still have exactly one spawn, one float, and no bool track
- only the eight named Level Sequences may become dirty or be saved
"""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
PLAYBACK_END = 375
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


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def package_path(value):
    return object_path(value).split(".", 1)[0]


def package_name(value):
    try:
        return str(value.get_name())
    except Exception:
        return str(value)


def frame_value(value):
    if hasattr(value, "frame_number"):
        value = value.frame_number
    if hasattr(value, "value"):
        value = value.value
    return int(value)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = package_path(world)
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
partial_path = f"{INTERACTION_DIR}/LS_Interaction_Template"
dirty_content_names = {package_name(value) for value in dirty_content}
dirty_map_names = [package_name(value) for value in dirty_maps]
if dirty_content_names != {partial_path} or dirty_map_names:
    raise RuntimeError(
        "Resume requires the exact validated partial state: "
        f"content={sorted(dirty_content_names)}, maps={dirty_map_names}, "
        f"expected={[partial_path]}"
    )

sequences = {}
expected_paths = set()
for name in SEQUENCE_NAMES:
    path = f"{INTERACTION_DIR}/{name}"
    sequence = unreal.load_asset(path)
    if sequence is None:
        raise RuntimeError(f"Missing curtain sequence: {path}")
    if frame_value(sequence.get_playback_start()) != 0:
        raise RuntimeError(f"Unexpected playback start for {path}")
    if frame_value(sequence.get_playback_end()) != PLAYBACK_END:
        raise RuntimeError(f"Unexpected playback end for {path}")
    bindings = list(sequence.get_bindings())
    if len(bindings) != 1:
        raise RuntimeError(f"Unexpected binding count for {path}: {len(bindings)}")
    binding = bindings[0]
    tags = [str(value) for value in binding.get_binding_tags()]
    if "InfinityStage.SequenceCurtain" not in tags:
        raise RuntimeError(f"Missing sequence curtain tag for {path}: {tags}")
    tracks = list(binding.get_tracks())
    classes = [track.get_class().get_name() for track in tracks]
    if classes.count("MovieSceneSpawnTrack") != 1:
        raise RuntimeError(f"Unexpected spawn tracks for {path}: {classes}")
    if classes.count("MovieSceneFloatTrack") != 1:
        raise RuntimeError(f"Unexpected float tracks for {path}: {classes}")
    bool_tracks = [
        track
        for track in tracks
        if track.get_class().get_name() == "MovieSceneBoolTrack"
    ]
    if path == partial_path:
        if len(bool_tracks) != 1 or len(classes) != 3:
            raise RuntimeError(
                f"Validated partial track is missing or duplicated for {path}: {classes}"
            )
    elif bool_tracks or len(classes) != 2:
        raise RuntimeError(
            f"Unexpected pre-repair track state for {path}: {classes}"
        )
    sequences[path] = (
        sequence,
        binding,
        bool_tracks[0] if bool_tracks else None,
    )
    expected_paths.add(path)

rows = []
for path, (sequence, binding, track) in sequences.items():
    if track is None:
        sequence.modify()
        track = binding.add_track(unreal.MovieSceneBoolTrack)
        if track is None:
            raise RuntimeError(f"Could not add bCurtainActive track to {path}")
        track.set_property_name_and_path(
            unreal.Name("bCurtainActive"), "bCurtainActive"
        )
        section = track.add_section()
        if section is None:
            raise RuntimeError(f"Could not add bCurtainActive section to {path}")
        section.set_range(0, PLAYBACK_END)
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            raise RuntimeError(
                f"Unexpected bool channel count for {path}: {len(channels)}"
            )
        channel = channels[0]
        if channel.get_class().get_name() != "MovieSceneScriptingBoolChannel":
            raise RuntimeError(
                f"Unexpected bool channel type for {path}: "
                f"{channel.get_class().get_name()}"
            )
        channel.set_default(True)
        key = channel.add_key(
            time=unreal.FrameNumber(0),
            new_value=True,
            sub_frame=0.0,
            time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
        )
        if key is None:
            raise RuntimeError(f"Could not add bCurtainActive key to {path}")
    else:
        sections = list(track.get_sections())
        if len(sections) != 1:
            raise RuntimeError(
                f"Partial active section count is {len(sections)} for {path}"
            )
        section = sections[0]
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            raise RuntimeError(
                f"Partial active channel count is {len(channels)} for {path}"
            )
        channel = channels[0]

    if str(track.get_property_name()) != "bCurtainActive":
        raise RuntimeError(f"Unexpected active property name for {path}")
    if str(track.get_property_path()) != "bCurtainActive":
        raise RuntimeError(f"Unexpected active property path for {path}")
    if not channel.has_default() or not bool(channel.get_default()):
        raise RuntimeError(f"Active default is not true for {path}")
    keys = list(channel.get_keys())
    if len(keys) != 1:
        raise RuntimeError(f"Unexpected active key count for {path}: {len(keys)}")
    rows.append(
        {
            "path": path,
            "property_name": str(track.get_property_name()),
            "property_path": str(track.get_property_path()),
            "section_range": [
                frame_value(section.get_start_frame()),
                frame_value(section.get_end_frame()),
            ],
            "default": bool(channel.get_default()),
            "keys": [
                [
                    frame_value(
                        keys[0].get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                    ),
                    bool(keys[0].get_value()),
                ]
            ],
        }
    )

dirty_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if set(dirty_before_save) != expected_paths or dirty_maps_before_save:
    raise RuntimeError(
        f"Unexpected dirty scope before save: content={dirty_before_save}, "
        f"maps={dirty_maps_before_save}, expected={sorted(expected_paths)}"
    )

saved = []
for path, (sequence, _, _) in sequences.items():
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
        raise RuntimeError(f"Save failed for {path}")
    saved.append(path)

dirty_content_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_content_after or dirty_maps_after:
    raise RuntimeError(
        f"Repair left dirty packages: content={dirty_content_after}, "
        f"maps={dirty_maps_after}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "rows": rows,
    "saved": saved,
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "add_curtain_active_tracks.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_ACTIVE_TRACKS_ADDED"
    f"|sequences={len(rows)}|saved={len(saved)}|dirty_content=0|dirty_maps=0"
)
