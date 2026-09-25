"""Retry only the already-validated dirty Show save after releasing a file lock."""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_INDEX = 49
EXPECTED_LABEL = "Scene 1 " + chr(0x2014) + " External Sound"


def package_path(value):
    try:
        return value.get_path_name().split(".", 1)[0]
    except Exception:
        return str(value).split(".", 1)[0]


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

dirty_content = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_content != [SHOW_PATH] or dirty_maps:
    raise RuntimeError(f"Refusing unexpected retry scope: {dirty_content}/{dirty_maps}")

show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError(f"Missing Show: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))
cue = cues[EXPECTED_INDEX]
scene = cue.get_editor_property("scene")
timing = [
    frame_value(scene.get_editor_property("curtain_entry_transition_frames")),
    frame_value(scene.get_editor_property("curtain_hold_frames")),
    frame_value(scene.get_editor_property("curtain_exit_transition_frames")),
]
if (
    str(cue.get_editor_property("label")) != EXPECTED_LABEL
    or scene.get_editor_property("curtain_mode") != unreal.InfinityCurtainCueMode.NONE
    or timing != [0, 0, 0]
):
    raise RuntimeError(
        f"Dirty Show does not contain the validated Scene 1 cleanup: "
        f"label={cue.get_editor_property('label')}, "
        f"mode={scene.get_editor_property('curtain_mode')}, timing={timing}"
    )

legacy_candidates = []
for index, candidate in enumerate(cues):
    candidate_scene = candidate.get_editor_property("scene")
    if (
        candidate.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR
        and candidate_scene.get_editor_property("curtain_mode")
            != unreal.InfinityCurtainCueMode.NONE
        and not bool(candidate_scene.get_editor_property("sequence_owns_curtain"))
    ):
        legacy_candidates.append(index)
if legacy_candidates:
    raise RuntimeError(f"Legacy candidates remain before retry save: {legacy_candidates}")

if not unreal.EditorAssetLibrary.save_loaded_asset(show, False):
    raise RuntimeError(f"Retry save failed for {SHOW_PATH}")

dirty_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_after or dirty_maps_after:
    raise RuntimeError(f"Retry save left dirty packages: {dirty_after}/{dirty_maps_after}")

payload = {
    "status": "ok",
    "world": world_path,
    "saved": [SHOW_PATH],
    "scene_index": EXPECTED_INDEX,
    "scene_label": EXPECTED_LABEL,
    "curtain_mode": "NONE",
    "timing": timing,
    "remaining_legacy_candidates": legacy_candidates,
    "dirty_content_after": dirty_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "retry_scene1_legacy_save.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_SCENE1_LEGACY_SAVE_RETRY_SUCCESS"
    f"|index={EXPECTED_INDEX}|mode=None|timing=[0,0,0]"
    f"|remaining=0|saved=1|dirty_content=0|dirty_maps=0"
)
