import hashlib
import json
import os

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TARGETS = {
    2: ("P02 Wing ", 23, "/Game/Wings/Passage02_AnimalsToShrineV2"),
    3: ("P03 Wing ", 21, "/Game/Wings/Passage03_ShrineToForgetting"),
    5: ("P05 Wing ", 93, "/Game/Wings/Passage05_BirdToMountain"),
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def guid_text(value):
    return str(value).replace("{", "").replace("}", "").lower()


def asset_package(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Unexpected world: {world_path}")
require(editor.get_game_world() is None, "PIE/SIE is active")

dirty_content = [
    asset_package(item)
    for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps = [
    asset_package(item)
    for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
require(not dirty_content, f"Dirty content before integration: {dirty_content}")
require(not dirty_maps, f"Dirty maps before integration: {dirty_maps}")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, f"Show Asset did not load: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))
passages = list(show.get_editor_property("passage_settings"))
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()

records = {}
fingerprint_parts = []
for ordinal, (label_prefix, expected_rows, destination) in TARGETS.items():
    require(len(passages) >= ordinal, f"Passage {ordinal} does not exist")
    passage = passages[ordinal - 1]
    expected_actor_label = f"Passage {ordinal:02d} — Fixed Wings"

    rows = []
    for cue_index, cue in enumerate(cues):
        label = str(cue.get_editor_property("label"))
        if not label.startswith(label_prefix):
            continue
        pair = cue.get_editor_property("wing_pair")
        left = pair.get_editor_property("left")
        right = pair.get_editor_property("right")
        top = pair.get_editor_property("top")
        row = {
            "ordinal": len(rows) + 1,
            "cue_index": cue_index,
            "label": str(cue.get_editor_property("label")),
            "left": asset_package(left.get_editor_property("mesh")),
            "right": asset_package(right.get_editor_property("mesh")),
            "has_top": bool(pair.get_editor_property("has_top")),
            "top": asset_package(top.get_editor_property("mesh")),
        }
        rows.append(row)
        fingerprint_parts.append(json.dumps(row, sort_keys=True))
    require(
        len(rows) == expected_rows,
        f"Expected {expected_rows} {label_prefix.strip()} rows, found {len(rows)}",
    )
    row_indexes = [row["cue_index"] for row in rows]
    require(
        row_indexes == list(range(row_indexes[0], row_indexes[-1] + 1)),
        f"Passage {ordinal} wing rows are not contiguous: {row_indexes}",
    )

    matches = []
    for actor in actors:
        if actor.get_class().get_name() != "InfinityStagePassageActor":
            continue
        try:
            if (
                actor.get_editor_property("show_asset") == show
                and actor.get_actor_label() == expected_actor_label
            ):
                matches.append(actor)
        except Exception:
            pass
    require(len(matches) == 1, f"Expected one Passage {ordinal} actor, found {len(matches)}")
    actor = matches[0]

    destination_assets = []
    if unreal.EditorAssetLibrary.does_directory_exist(destination):
        destination_assets = unreal.EditorAssetLibrary.list_assets(
            destination, recursive=True, include_folder=False
        )
    records[str(ordinal)] = {
        "label": str(passage.get_editor_property("label")),
        "first_index": row_indexes[0],
        "last_index": row_indexes[-1],
        "wing_row_count": len(rows),
        "rows": rows,
        "actor_label": actor.get_actor_label(),
        "materialized_wing_pair_count": int(
            actor.get_editor_property("materialized_wing_pair_count")
        ),
        "component_budget": int(actor.get_editor_property("component_budget")),
        "destination": destination,
        "destination_asset_count": len(destination_assets),
    }

payload = {
    "status": "ok",
    "world": world_path,
    "show_asset": SHOW_PATH,
    "show_cue_count": len(cues),
    "show_passage_count": len(passages),
    "target_state_fingerprint": hashlib.sha256(
        "\n".join(fingerprint_parts).encode("utf-8")
    ).hexdigest(),
    "dirty_content": dirty_content,
    "dirty_maps": dirty_maps,
    "passages": records,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "preflight_all_passages.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
unreal.log(
    "PUSS_WING_INTEGRATION_PREFLIGHT_SUCCESS"
    f"|cues={len(cues)}|p02={records['2']['wing_row_count']}"
    f"|p03={records['3']['wing_row_count']}|p05={records['5']['wing_row_count']}"
    f"|fingerprint={payload['target_state_fingerprint']}|dirty=0"
)
