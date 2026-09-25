"""Set every Passage 2 relief instance's opacity mask to its own wing texture."""

import json
import os

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CONTENT_ROOT = "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2"
TEXTURE_ROOT = f"{CONTENT_ROOT}/Textures"
INSTANCE_ROOT = f"{CONTENT_ROOT}/Materials/Instances"
MASTER_PATH = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
ACTOR_LABEL = "Passage 02 — Fixed Wings"
EXPECTED_ROWS = 23
EXPECTED_INSTANCES = 60


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_path(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value)


def texture_parameters(instance):
    return {
        str(item.get_editor_property("parameter_info").get_editor_property("name")):
        item.get_editor_property("parameter_value")
        for item in instance.get_editor_property("texture_parameter_values")
    }


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Unexpected world: {world_path}")
require(editor.get_game_world() is None, "PIE/SIE is active")
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "Dirty content exists before Passage 2 opacity fix",
)
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    "Dirty maps exist before Passage 2 opacity fix",
)

master = unreal.EditorAssetLibrary.load_asset(MASTER_PATH)
require(master is not None, f"Master material did not load: {MASTER_PATH}")
records = []
before = {"correct": 0, "missing_inherited": 0, "mismatch": 0}

for set_number in range(1, 21):
    for role in ("L", "R", "T"):
        asset_name = f"P02_SET{set_number:02d}_{role}"
        instance = unreal.EditorAssetLibrary.load_asset(
            f"{INSTANCE_ROOT}/MI_{asset_name}_Relief"
        )
        base = unreal.EditorAssetLibrary.load_asset(f"{TEXTURE_ROOT}/T_{asset_name}")
        require(
            isinstance(instance, unreal.MaterialInstanceConstant),
            f"Expected MaterialInstanceConstant: {asset_name}",
        )
        require(isinstance(base, unreal.Texture2D), f"Expected Texture2D: {asset_name}")
        require(instance.get_editor_property("parent") == master, f"Wrong parent: {asset_name}")
        parameters = texture_parameters(instance)
        require(parameters.get("BaseColor") == base, f"BaseColor mismatch: {asset_name}")
        opacity = parameters.get("OpacityMask")
        if opacity is None:
            status = "missing_inherited"
        elif opacity == base:
            status = "correct"
        else:
            status = "mismatch"
        before[status] += 1
        records.append(
            {
                "asset_name": asset_name,
                "instance": instance,
                "instance_path": asset_path(instance),
                "base": base,
                "base_path": asset_path(base),
                "before_status": status,
                "before_opacity": asset_path(opacity),
            }
        )

require(len(records) == EXPECTED_INSTANCES, f"Expected 60 instances, found {len(records)}")
require(
    before == {"correct": 5, "missing_inherited": 54, "mismatch": 1},
    f"Unexpected pre-change state: {before}",
)
mismatches = [record for record in records if record["before_status"] == "mismatch"]
require(len(mismatches) == 1, f"Expected one explicit mismatch, found {len(mismatches)}")
require(
    mismatches[0]["asset_name"] == "P02_SET04_T"
    and mismatches[0]["before_opacity"].endswith("/T_P02_SET04_R"),
    f"Unexpected explicit mismatch: {mismatches[0]}",
)

saved = []
for record in records:
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        record["instance"], "OpacityMask", record["base"]
    )
    unreal.MaterialEditingLibrary.update_material_instance(record["instance"])
    parameters = texture_parameters(record["instance"])
    require(
        parameters.get("OpacityMask") == record["base"],
        f"In-memory OpacityMask mismatch: {record['asset_name']}",
    )
    require(
        unreal.EditorAssetLibrary.save_asset(
            record["instance_path"], only_if_is_dirty=False
        ),
        f"Failed to save: {record['instance_path']}",
    )
    saved.append(record["instance_path"])

dirty_content = {
    asset_path(item)
    for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
}
dirty_maps = {
    asset_path(item)
    for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
}
require(not dirty_content, f"Dirty content after instance saves: {sorted(dirty_content)}")
require(not dirty_maps, f"Dirty maps before materialization: {sorted(dirty_maps)}")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, f"Show Asset did not load: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))
p02_rows = [
    cue
    for cue in cues
    if str(cue.get_editor_property("label")).startswith("P02 Wing ")
]
require(len(p02_rows) == EXPECTED_ROWS, f"Expected 23 Passage 2 rows, found {len(p02_rows)}")
require(
    {str(cue.get_editor_property("label")) for cue in p02_rows}
    == {f"P02 Wing {ordinal:03d}" for ordinal in range(1, EXPECTED_ROWS + 1)},
    "Passage 2 label set changed",
)

matches = []
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    if actor.get_actor_label() != ACTOR_LABEL:
        continue
    try:
        if actor.get_editor_property("show_asset") == show:
            matches.append(actor)
    except Exception:
        pass
require(len(matches) == 1, f"Expected one Passage 2 actor, found {len(matches)}")
require(bool(matches[0].materialize_passage()), "Passage 2 materialization failed")

dirty_content = {
    asset_path(item)
    for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
}
dirty_maps = {
    asset_path(item)
    for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
}
require(not dirty_content, f"Unexpected dirty content after materialization: {sorted(dirty_content)}")
require(
    dirty_maps.issubset({EXPECTED_WORLD}),
    f"Unexpected dirty maps after materialization: {sorted(dirty_maps)}",
)
level_saved = bool(
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
)
require(level_saved, "Current level save failed")

require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "Content remains dirty after Passage 2 opacity fix",
)
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    "Map remains dirty after Passage 2 opacity fix",
)

report = {
    "status": "ok",
    "world": world_path,
    "before": before,
    "instance_count": len(records),
    "saved_instances": saved,
    "materialized_passage": 2,
    "level_saved": level_saved,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "fix_p02_opacity_masks.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)

unreal.log(
    "P02_OPACITY_FIX_SUCCESS"
    f"|instances={len(records)}|before_missing={before['missing_inherited']}"
    f"|before_mismatch={before['mismatch']}|before_correct={before['correct']}"
    "|opacity_matches=60|materialized=1|level_saved=1|dirty=0"
)
