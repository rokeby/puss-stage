"""Clear the one obsolete Scene 1 legacy curtain setting superseded by its sequence."""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_INDEX = 49
EXPECTED_LABEL = "Scene 1 " + chr(0x2014) + " External Sound"
EXPECTED_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"


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
    try:
        return int(value.value)
    except Exception:
        return int(value)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world_path = package_path(editor.get_editor_world())
if world_path != EXPECTED_WORLD or editor.get_game_world() is not None:
    raise RuntimeError(f"Unsafe editor state: world={world_path}, game_world={editor.get_game_world()}")

dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if dirty_content or dirty_maps:
    raise RuntimeError(f"Legacy cleanup requires clean editor: {dirty_content}/{dirty_maps}")

show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError(f"Missing Show: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))

candidates = []
for index, cue in enumerate(cues):
    scene = cue.get_editor_property("scene")
    if (
        cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR
        and scene.get_editor_property("curtain_mode") != unreal.InfinityCurtainCueMode.NONE
        and not bool(scene.get_editor_property("sequence_owns_curtain"))
    ):
        candidates.append((index, cue))
if len(candidates) != 1:
    raise RuntimeError(f"Expected one legacy candidate, found {len(candidates)}")

index, cue = candidates[0]
scene = cue.get_editor_property("scene")
label = str(cue.get_editor_property("label"))
sequence = package_path(scene.get_editor_property("sequence"))
old_timing = [
    frame_value(scene.get_editor_property("curtain_entry_transition_frames")),
    frame_value(scene.get_editor_property("curtain_hold_frames")),
    frame_value(scene.get_editor_property("curtain_exit_transition_frames")),
]
if (
    index != EXPECTED_INDEX
    or label != EXPECTED_LABEL
    or not bool(cue.get_editor_property("enabled"))
    or cue.get_editor_property("type") != unreal.InfinityCueType.SCENE
    or sequence != EXPECTED_SEQUENCE
    or scene.get_editor_property("curtain_mode")
        != unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL
):
    raise RuntimeError(
        f"Refusing unexpected legacy candidate: index={index}, label={label}, "
        f"enabled={cue.get_editor_property('enabled')}, "
        f"type={cue.get_editor_property('type')}, sequence={sequence}, "
        f"mode={scene.get_editor_property('curtain_mode')}"
    )

scene.set_editor_property("curtain_mode", unreal.InfinityCurtainCueMode.NONE)
scene.set_editor_property("curtain_entry_transition_frames", unreal.FrameNumber(0))
scene.set_editor_property("curtain_hold_frames", unreal.FrameNumber(0))
scene.set_editor_property("curtain_exit_transition_frames", unreal.FrameNumber(0))
scene.set_editor_property("sequence_owns_curtain", False)
scene.set_editor_property("reveal_next_passage_when_covered", False)
cue.set_editor_property("scene", scene)
cues[index] = cue
show.set_editor_property("cues", cues)

dirty_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_before_save != [SHOW_PATH] or dirty_maps_before_save:
    raise RuntimeError(
        f"Unexpected dirty scope before save: {dirty_before_save}/{dirty_maps_before_save}"
    )
if not unreal.EditorAssetLibrary.save_loaded_asset(show, False):
    raise RuntimeError(f"Save failed for {SHOW_PATH}")

dirty_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_after or dirty_maps_after:
    raise RuntimeError(f"Cleanup left dirty packages: {dirty_after}/{dirty_maps_after}")

remaining = []
for candidate_index, candidate_cue in enumerate(show.get_editor_property("cues")):
    candidate_scene = candidate_cue.get_editor_property("scene")
    if (
        candidate_cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR
        and candidate_scene.get_editor_property("curtain_mode")
            != unreal.InfinityCurtainCueMode.NONE
        and not bool(candidate_scene.get_editor_property("sequence_owns_curtain"))
    ):
        remaining.append(candidate_index)
if remaining:
    raise RuntimeError(f"Legacy curtain candidates remain after save: {remaining}")

payload = {
    "status": "ok",
    "world": world_path,
    "saved": [SHOW_PATH],
    "cleared_index": index,
    "cleared_label": label,
    "sequence": sequence,
    "old_timing": old_timing,
    "new_timing": [0, 0, 0],
    "remaining_legacy_candidates": remaining,
    "dirty_content_after": dirty_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "clear_scene1_legacy_curtain.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_SCENE1_LEGACY_CLEARED"
    f"|index={index}|old_timing={old_timing}|new_timing=[0,0,0]"
    f"|remaining=0|saved=1|dirty_content=0|dirty_maps=0"
)
