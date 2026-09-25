import json
from pathlib import Path

import unreal


PROJECT_ROOT = Path("/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
BACKUP_PATH = (
    "/Game/InfinityStage/Dev/SavedVersions/"
    "DA_InfinityStage_V1Show_P05_PreCleanFBXRepair_20260815"
)
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ACTOR_LABEL = "Passage 05 — Fixed Wings"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_package(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value)


def read_rows(show):
    rows = []
    for cue_index, cue in enumerate(list(show.get_editor_property("cues"))):
        label = str(cue.get_editor_property("label"))
        if not label.startswith("P05 Wing "):
            continue
        pair = cue.get_editor_property("wing_pair")
        record = {
            "ordinal": len(rows) + 1,
            "cue_index": cue_index,
            "label": label,
            "has_top": bool(pair.get_editor_property("has_top")),
        }
        for role in ("left", "right", "top"):
            panel = pair.get_editor_property(role)
            record[role] = asset_package(panel.get_editor_property("mesh"))
            record[f"{role}_flip"] = bool(
                panel.get_editor_property("flip_image_horizontally")
            )
        rows.append(record)
    return rows


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "No editor world is open")
    world_path = world.get_path_name().split(".", 1)[0]
    require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
    require(editor.get_game_world() is None, "PIE/SIE is active")
    dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    require(not dirty_content, f"Dirty content: {dirty_content}")
    require(not dirty_maps, f"Dirty maps: {dirty_maps}")

    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    require(show is not None, "Show Asset did not load")
    backup = unreal.EditorAssetLibrary.load_asset(BACKUP_PATH)
    require(backup is not None, "Show backup did not load")
    rows = read_rows(show)
    backup_rows = read_rows(backup)
    require(len(rows) == 93, f"Expected 93 Passage 5 rows, found {len(rows)}")
    require(len(backup_rows) == 93, f"Expected 93 backup Passage 5 rows, found {len(backup_rows)}")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    matches = [
        actor
        for actor in actors
        if actor.get_class().get_name() == "InfinityStagePassageActor"
        and actor.get_actor_label() == ACTOR_LABEL
        and actor.get_editor_property("show_asset") == show
    ]
    require(len(matches) == 1, f"Expected one Passage 5 actor, found {len(matches)}")
    materialized = int(matches[0].get_editor_property("materialized_wing_pair_count"))

    output_path = PROJECT_ROOT / "Saved/CodexPassage05/inspect_current_rows_v2_result.json"
    output_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "world": world_path,
                "rows": rows,
                "backup_rows": backup_rows,
                "row_count": len(rows),
                "materialized_pairs": materialized,
                "dirty_content": 0,
                "dirty_maps": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    unreal.log(
        "P05_CURRENT_ROWS_INSPECT_SUCCESS"
        f"|rows={len(rows)}|materialized_pairs={materialized}|dirty=0"
    )


main()
