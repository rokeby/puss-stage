"""Restore the P04 Wing 004 right Flat V3 design's two MIs to v1 parents."""
from __future__ import annotations

import json
import pathlib

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
V1_FRONT = "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front"
V1_FLAP = "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap"
TARGETS = {
    "/Game/Scenes/Wings/FlatV3/Passage04/Materials/Instances/"
    "MI_FlatV3_P04_ruined_gallery_R_v3_Front": V1_FRONT,
    "/Game/Scenes/Wings/FlatV3/Passage04/Materials/Instances/"
    "MI_FlatV3_P04_ruined_gallery_R_v3_Flap": V1_FLAP,
}
RECORD = pathlib.Path("E:/PussStage/Saved/CodexFlatV3/gloss/gloss_test_parents.json")
RESULT = pathlib.Path("E:/PussStage/Saved/CodexFlatV3/gloss/gloss_test_revert_result.json")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_path(value):
    return None if value is None else str(value.get_path_name()).split(".", 1)[0]


def load(path, expected_type=None):
    value = unreal.EditorAssetLibrary.load_asset(path)
    require(value is not None, "MISSING_ASSET|" + path)
    if expected_type is not None:
        require(isinstance(value, expected_type), "WRONG_ASSET_TYPE|" + path)
    return value


def package_names(packages):
    return sorted(str(package.get_name()).split(".", 1)[0] for package in packages)


def census():
    return {
        "content": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "NO_EDITOR_WORLD")
    require(str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_EDITOR_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    require(RECORD.is_file(), "MISSING_PARENT_RECORD")
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    require(record.get("target_cue") == "P04 Wing 004", "RECORD_CUE_MISMATCH")
    require(record.get("target_side") == "right", "RECORD_SIDE_MISMATCH")
    require(record.get("old_parents") == TARGETS, "RECORD_PARENT_SET_MISMATCH")

    before = census()
    target_paths = set(TARGETS)
    mel = unreal.MaterialEditingLibrary
    for path, parent_path in TARGETS.items():
        instance = load(path, unreal.MaterialInstanceConstant)
        mel.set_material_instance_parent(
            instance, load(parent_path, unreal.MaterialInstanceConstant)
        )
        mel.update_material_instance(instance)
        require(asset_path(instance.get_editor_property("parent")) == parent_path,
                "PARENT_SET_READBACK_FAILED|" + path)
    for path in TARGETS:
        require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False),
                "SAVE_FAILED|" + path)

    readback = {}
    for path, parent_path in TARGETS.items():
        instance = load(path, unreal.MaterialInstanceConstant)
        readback[path] = asset_path(instance.get_editor_property("parent"))
        require(readback[path] == parent_path, "SAVED_PARENT_READBACK_FAILED|" + path)
    after = census()
    unrelated_before = set(before["content"]) - target_paths
    newly_dirty_unrelated = set(after["content"]) - unrelated_before - target_paths
    require(not newly_dirty_unrelated,
            "UNRELATED_PACKAGES_DIRTIED|" + json.dumps(sorted(newly_dirty_unrelated)))
    require(not (set(after["content"]) & target_paths), "TARGET_MIS_STILL_DIRTY")
    require(after["maps"] == before["maps"], "MAP_DIRTY_CENSUS_CHANGED")

    result = {
        "status": "PASS",
        "target_cue": "P04 Wing 004",
        "target_side": "right",
        "parents_readback": readback,
        "saved_only": sorted(TARGETS),
        "dirty_before": before,
        "dirty_after": after,
    }
    RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    unreal.log(
        "PUSS_BILLBOARD_GLOSS_TEST_REVERT_SUCCESS|cue=P04_Wing_004|side=right|"
        "saved_count=2|parents=v1|readback=1"
    )


if __name__ == "__main__":
    main()
