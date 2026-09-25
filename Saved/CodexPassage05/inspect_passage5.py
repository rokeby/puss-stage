import json
import os

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_LEVEL = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
DEST_ROOT = "/Game/Wings/Passage05_BirdToMountain"


def guid_text(value):
    return str(value).replace("{", "").replace("}", "").lower()


def asset_path(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return value.get_path_name()
    return str(value)


def main():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world is None:
        raise RuntimeError("No editor world is open")
    world_path = world.get_path_name().split(":", 1)[0]
    if not world_path.startswith(EXPECTED_LEVEL):
        raise RuntimeError(f"Unexpected editor level: {world_path}")

    show = unreal.load_asset(SHOW_PATH)
    if show is None:
        raise RuntimeError("Show Asset did not load")

    cues = list(show.get_editor_property("cues"))
    passages = list(show.get_editor_property("passage_settings"))
    unreal.log(f"P05_INSPECT|world={world_path}|cues={len(cues)}|passages={len(passages)}")

    for index, passage in enumerate(passages):
        first_guid = guid_text(passage.get_editor_property("first_cue_guid"))
        last_guid = guid_text(passage.get_editor_property("last_cue_guid"))
        first_index = next(
            (i for i, cue in enumerate(cues) if guid_text(cue.get_editor_property("cue_guid")) == first_guid),
            -1,
        )
        last_index = next(
            (i for i, cue in enumerate(cues) if guid_text(cue.get_editor_property("cue_guid")) == last_guid),
            -1,
        )
        unreal.log(
            "P05_PASSAGE|"
            f"ordinal={index + 1}|label={passage.get_editor_property('label')}|"
            f"guid={passage.get_editor_property('passage_guid')}|first={first_index}|last={last_index}"
        )

    if len(passages) < 5:
        raise RuntimeError("Passage 5 does not exist")
    target = passages[4]
    first_guid = guid_text(target.get_editor_property("first_cue_guid"))
    last_guid = guid_text(target.get_editor_property("last_cue_guid"))
    first_index = next(i for i, cue in enumerate(cues) if guid_text(cue.get_editor_property("cue_guid")) == first_guid)
    last_index = next(i for i, cue in enumerate(cues) if guid_text(cue.get_editor_property("cue_guid")) == last_guid)
    if first_index > last_index:
        raise RuntimeError("Passage 5 cue range is reversed")

    rows = []
    row_payloads = []
    for cue_index in range(first_index, last_index + 1):
        cue = cues[cue_index]
        if "WING" not in str(cue.get_editor_property("type")).upper():
            continue
        wing = cue.get_editor_property("wing_pair")
        left = wing.get_editor_property("left")
        right = wing.get_editor_property("right")
        top = wing.get_editor_property("top")
        rows.append(cue_index)
        row_payloads.append(
            {
                "ordinal": len(rows),
                "cue_index": cue_index,
                "label": str(cue.get_editor_property("label")),
                "left": asset_path(left.get_editor_property("mesh")),
                "right": asset_path(right.get_editor_property("mesh")),
                "has_top": bool(wing.get_editor_property("has_top")),
                "top": asset_path(top.get_editor_property("mesh")),
            }
        )
        unreal.log(
            "P05_ROW|"
            f"ordinal={len(rows)}|cue_index={cue_index}|label={cue.get_editor_property('label')}|"
            f"left={asset_path(left.get_editor_property('mesh'))}|"
            f"right={asset_path(right.get_editor_property('mesh'))}|"
            f"has_top={wing.get_editor_property('has_top')}|"
            f"top={asset_path(top.get_editor_property('mesh'))}"
        )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = []
    target_guid = guid_text(target.get_editor_property("passage_guid"))
    for actor in actor_subsystem.get_all_level_actors():
        if actor.get_class().get_name() != "InfinityStagePassageActor":
            continue
        try:
            actor_show = actor.get_editor_property("show_asset")
            actor_guid = guid_text(actor.get_editor_property("passage_guid"))
        except Exception:
            continue
        if actor_show == show and actor_guid == target_guid:
            matches.append(actor)
            unreal.log(
                "P05_ACTOR|"
                f"label={actor.get_actor_label()}|guid={actor_guid}|"
                f"materialized={actor.get_editor_property('materialized_wing_pair_count')}|"
                f"budget={actor.get_editor_property('component_budget')}"
            )
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Passage 5 actor, found {len(matches)}")

    dirty_content = []
    dirty_maps = []
    try:
        dirty_content = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        dirty_maps = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    except Exception as exc:
        unreal.log_warning(f"P05_DIRTY_QUERY_UNAVAILABLE|{exc}")
    unreal.log(
        "P05_DIRTY|"
        f"content={','.join(str(item) for item in dirty_content)}|"
        f"maps={','.join(str(item) for item in dirty_maps)}"
    )
    unreal.log(
        "P05_INSPECT_SUCCESS|"
        f"rows={len(rows)}|first={first_index}|last={last_index}|"
        f"actor={matches[0].get_actor_label()}|destination_exists="
        f"{unreal.EditorAssetLibrary.does_directory_exist(DEST_ROOT)}"
    )
    output_path = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexPassage05",
        "p05_inspect.json",
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "status": "ok",
                "world": world_path,
                "show_asset": SHOW_PATH,
                "passage_ordinal": 5,
                "passage_label": str(target.get_editor_property("label")),
                "passage_guid": target_guid,
                "first_index": first_index,
                "last_index": last_index,
                "rows": row_payloads,
                "actor": matches[0].get_actor_label(),
                "materialized_wing_pair_count": int(
                    matches[0].get_editor_property("materialized_wing_pair_count")
                ),
                "component_budget": int(matches[0].get_editor_property("component_budget")),
                "dirty_content": [str(item) for item in dirty_content],
                "dirty_maps": [str(item) for item in dirty_maps],
                "destination_exists": unreal.EditorAssetLibrary.does_directory_exist(DEST_ROOT),
            },
            handle,
            indent=2,
            sort_keys=True,
        )
    unreal.log(f"P05_INSPECT_FILE|{output_path}")


main()
