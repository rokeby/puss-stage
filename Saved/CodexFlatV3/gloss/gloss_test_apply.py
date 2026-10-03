"""Reparent one P04 Flat V3 design's Front/Flap MIs to billboard v2.

Target: P04 Wing 004 right, SM_FlatV3_P04_ruined_gallery_R_v3.  This is inside
the conductor's bays 1-6 side-lit prototype and carries the INDUSTRIAL look.
The previous parents are recorded before either MI is changed.
"""
from __future__ import annotations

import datetime
import json
import pathlib

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TARGET_CUE = "P04 Wing 004"
TARGET_SIDE = "right"
TARGET_MESH = (
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/"
    "SM_FlatV3_P04_ruined_gallery_R_v3"
)
V1_FRONT = "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front"
V1_FLAP = "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap"
V2_FRONT = "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front_v2"
V2_FLAP = "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap_v2"
TARGETS = {
    "/Game/Scenes/Wings/FlatV3/Passage04/Materials/Instances/"
    "MI_FlatV3_P04_ruined_gallery_R_v3_Front": (V1_FRONT, V2_FRONT),
    "/Game/Scenes/Wings/FlatV3/Passage04/Materials/Instances/"
    "MI_FlatV3_P04_ruined_gallery_R_v3_Flap": (V1_FLAP, V2_FLAP),
}
RECORD = pathlib.Path("E:/PussStage/Saved/CodexFlatV3/gloss/gloss_test_parents.json")
RESULT = pathlib.Path("E:/PussStage/Saved/CodexFlatV3/gloss/gloss_test_apply_result.json")


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


def assert_editor():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "NO_EDITOR_WORLD")
    require(str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_EDITOR_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")


def write_or_validate_record(old_parents, current_parents):
    expected = {
        "schema_version": 1,
        "target_cue": TARGET_CUE,
        "target_side": TARGET_SIDE,
        "target_mesh": TARGET_MESH,
        "old_parents": old_parents,
    }
    if RECORD.is_file():
        existing = json.loads(RECORD.read_text(encoding="utf-8"))
        for key in ("schema_version", "target_cue", "target_side", "target_mesh", "old_parents"):
            require(existing.get(key) == expected[key], "EXISTING_RECORD_MISMATCH|" + key)
        return existing
    require(current_parents == old_parents,
            "REFUSING_FIRST_RECORD_AFTER_PARENT_CHANGE|" + json.dumps(current_parents, sort_keys=True))
    expected["recorded_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
    RECORD.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    require(RECORD.is_file(), "PARENT_RECORD_WRITE_FAILED")
    return expected


def main():
    assert_editor()
    before = census()
    target_paths = set(TARGETS)
    instances = {path: load(path, unreal.MaterialInstanceConstant) for path in TARGETS}
    current = {path: asset_path(instance.get_editor_property("parent"))
               for path, instance in instances.items()}
    allowed = {path: {parents[0], parents[1]} for path, parents in TARGETS.items()}
    for path, parent in current.items():
        require(parent in allowed[path], "UNEXPECTED_CURRENT_PARENT|%s|%s" % (path, parent))

    old_parents = {path: parents[0] for path, parents in TARGETS.items()}
    record = write_or_validate_record(old_parents, current)
    require(record["old_parents"] == old_parents, "RECORDED_PARENT_SET_DRIFT")

    mel = unreal.MaterialEditingLibrary
    for path, instance in instances.items():
        destination = TARGETS[path][1]
        mel.set_material_instance_parent(instance, load(destination, unreal.MaterialInstanceConstant))
        mel.update_material_instance(instance)
        require(asset_path(instance.get_editor_property("parent")) == destination,
                "PARENT_SET_READBACK_FAILED|" + path)
    for path in TARGETS:
        require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False),
                "SAVE_FAILED|" + path)

    readback = {}
    for path in TARGETS:
        instance = load(path, unreal.MaterialInstanceConstant)
        readback[path] = asset_path(instance.get_editor_property("parent"))
        require(readback[path] == TARGETS[path][1], "SAVED_PARENT_READBACK_FAILED|" + path)
    after = census()
    unrelated_before = set(before["content"]) - target_paths
    newly_dirty_unrelated = set(after["content"]) - unrelated_before - target_paths
    require(not newly_dirty_unrelated,
            "UNRELATED_PACKAGES_DIRTIED|" + json.dumps(sorted(newly_dirty_unrelated)))
    require(not (set(after["content"]) & target_paths), "TARGET_MIS_STILL_DIRTY")
    require(after["maps"] == before["maps"], "MAP_DIRTY_CENSUS_CHANGED")

    result = {
        "status": "PASS",
        "target_cue": TARGET_CUE,
        "target_side": TARGET_SIDE,
        "target_mesh": TARGET_MESH,
        "record": RECORD.as_posix(),
        "old_parents": old_parents,
        "new_parents_readback": readback,
        "saved_only": sorted(TARGETS),
        "dirty_before": before,
        "dirty_after": after,
    }
    RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    unreal.log(
        "PUSS_BILLBOARD_GLOSS_TEST_APPLY_SUCCESS|cue=P04_Wing_004|side=right|"
        "mesh=SM_FlatV3_P04_ruined_gallery_R_v3|saved_count=2|readback=1"
    )


if __name__ == "__main__":
    main()
