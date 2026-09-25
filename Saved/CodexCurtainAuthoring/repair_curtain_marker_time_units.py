"""One-shot conversion of curtain staging markers from tick to display-rate input."""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
SEQUENCE_NAMES = [
    "LS_Interaction_Template",
    "LS_Interaction_01_WashingTheBoy",
    "LS_Interaction_02_Turnips",
    "LS_Interaction_03_ForgetsHisName",
    "LS_Interaction_04_GetsAName",
    "LS_Interaction_05_BecomesKing",
]
MARKERS = [
    (75, "InfinityStage.CurtainFullyDown"),
    (75, "InfinityStage.BoyCatStart"),
    (375, "InfinityStage.HiddenChangeover"),
    (400, "InfinityStage.CurtainRiseStart"),
    (500, "InfinityStage.CurtainFullyOpen"),
]
DISPLAY_RATE_UNIT = unreal.MovieSceneTimeUnit.DISPLAY_RATE
TICK_RESOLUTION_UNIT = unreal.MovieSceneTimeUnit.TICK_RESOLUTION


def object_path(value):
    if value is None:
        return ""
    return value.get_path_name() if hasattr(value, "get_path_name") else str(value)


def package_path(value):
    return object_path(value).split(".", 1)[0]


def package_name(value):
    return str(value.get_name()) if hasattr(value, "get_name") else str(value)


def marker_pairs(sequence, time_unit):
    marked_frames = unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(
        sequence, time_unit
    )
    return sorted((int(marked.frame_number.value), str(marked.label)) for marked in marked_frames)


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
    raise RuntimeError(f"Marker repair requires a clean editor: {dirty_content}/{dirty_maps}")

expected_old_tick = sorted(MARKERS)
expected_display = sorted(MARKERS)
expected_new_tick = sorted((frame * 960, label) for frame, label in MARKERS)
sequences = []
for name in SEQUENCE_NAMES:
    path = INTERACTION_DIR + "/" + name
    sequence = unreal.load_asset(path)
    if sequence is None:
        raise RuntimeError(f"Missing {path}")
    if int(sequence.get_playback_end()) != 500:
        raise RuntimeError(f"Unexpected playback range for {path}")
    actual_old_tick = marker_pairs(sequence, TICK_RESOLUTION_UNIT)
    if actual_old_tick != expected_old_tick:
        raise RuntimeError(
            f"Unexpected pre-conversion tick markers for {path}: {actual_old_tick}"
        )
    sequences.append(sequence)

for sequence in sequences:
    sequence.delete_marked_frames()
    for frame, label in MARKERS:
        marked = unreal.MovieSceneMarkedFrame()
        marked.frame_number = unreal.FrameNumber(value=frame)
        marked.label = label
        unreal.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(
            sequence, marked, DISPLAY_RATE_UNIT
        )
    actual_display = marker_pairs(sequence, DISPLAY_RATE_UNIT)
    actual_tick = marker_pairs(sequence, TICK_RESOLUTION_UNIT)
    if actual_display != expected_display or actual_tick != expected_new_tick:
        raise RuntimeError(
            f"Marker conversion failed for {package_path(sequence)}: "
            f"display={actual_display}, tick={actual_tick}"
        )

expected_paths = {package_path(sequence) for sequence in sequences}
dirty_content = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
unexpected_dirty = sorted(set(dirty_content) - expected_paths)
if unexpected_dirty or dirty_maps:
    raise RuntimeError(
        f"Unexpected dirty packages before marker save: content={dirty_content}, "
        f"maps={dirty_maps}, unexpected={unexpected_dirty}"
    )

saved = []
for sequence in sequences:
    path = package_path(sequence)
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
        raise RuntimeError(f"Save failed for {path}")
    saved.append(path)

dirty_content_after = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps_after = [package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content_after or dirty_maps_after:
    raise RuntimeError(
        f"Marker repair left dirty packages: {dirty_content_after}/{dirty_maps_after}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "display_markers": expected_display,
    "tick_markers": expected_new_tick,
    "saved": saved,
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "repair_curtain_marker_time_units.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_MARKER_TIMEUNIT_REPAIR_SUCCESS"
    f"|sequences={len(sequences)}|markers={len(MARKERS)}"
    "|dirty_content=0|dirty_maps=0"
)
