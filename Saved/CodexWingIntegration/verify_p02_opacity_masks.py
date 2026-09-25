"""Independent saved-state verifier for Passage 2 wing opacity masks."""

import json
import os

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CONTENT_ROOT = "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2"
MESH_ROOT = f"{CONTENT_ROOT}/StaticMeshes"
TEXTURE_ROOT = f"{CONTENT_ROOT}/Textures"
INSTANCE_ROOT = f"{CONTENT_ROOT}/Materials/Instances"
MASTER_PATH = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
EDGE_PATH = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
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
    "Dirty content exists before verification",
)
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    "Dirty maps exist before verification",
)

master = unreal.EditorAssetLibrary.load_asset(MASTER_PATH)
edge = unreal.EditorAssetLibrary.load_asset(EDGE_PATH)
require(master is not None, f"Master material did not load: {MASTER_PATH}")
require(edge is not None, f"Edge material did not load: {EDGE_PATH}")

verified_instances = []
for set_number in range(1, 21):
    for role in ("L", "R", "T"):
        asset_name = f"P02_SET{set_number:02d}_{role}"
        base = unreal.EditorAssetLibrary.load_asset(f"{TEXTURE_ROOT}/T_{asset_name}")
        height = unreal.EditorAssetLibrary.load_asset(f"{TEXTURE_ROOT}/T_{asset_name}_H")
        normal = unreal.EditorAssetLibrary.load_asset(f"{TEXTURE_ROOT}/T_{asset_name}_N")
        mesh = unreal.EditorAssetLibrary.load_asset(f"{MESH_ROOT}/SM_{asset_name}")
        instance = unreal.EditorAssetLibrary.load_asset(
            f"{INSTANCE_ROOT}/MI_{asset_name}_Relief"
        )
        require(isinstance(base, unreal.Texture2D), f"Base texture missing: {asset_name}")
        require(isinstance(height, unreal.Texture2D), f"Height texture missing: {asset_name}")
        require(isinstance(normal, unreal.Texture2D), f"Normal texture missing: {asset_name}")
        require(isinstance(mesh, unreal.StaticMesh), f"Static mesh missing: {asset_name}")
        require(
            isinstance(instance, unreal.MaterialInstanceConstant),
            f"Material instance missing: {asset_name}",
        )
        require(instance.get_editor_property("parent") == master, f"Wrong parent: {asset_name}")
        parameters = texture_parameters(instance)
        require(parameters.get("BaseColor") == base, f"BaseColor mismatch: {asset_name}")
        require(parameters.get("Height") == height, f"Height mismatch: {asset_name}")
        require(parameters.get("Normal") == normal, f"Normal mismatch: {asset_name}")
        require(parameters.get("OpacityMask") == base, f"OpacityMask mismatch: {asset_name}")
        require(
            "bamboo" not in asset_path(parameters.get("OpacityMask")).lower(),
            f"Bamboo opacity remains: {asset_name}",
        )
        slots = list(mesh.get_editor_property("static_materials"))
        require(len(slots) == 3, f"Mesh slot count mismatch: {asset_name}")
        require(mesh.get_material(0) == instance, f"Front material mismatch: {asset_name}")
        require(mesh.get_material(1) == instance, f"Back material mismatch: {asset_name}")
        require(mesh.get_material(2) == edge, f"Edge material mismatch: {asset_name}")
        verified_instances.append(asset_path(instance))

require(
    len(verified_instances) == EXPECTED_INSTANCES,
    f"Expected 60 verified instances, found {len(verified_instances)}",
)
require(len(set(verified_instances)) == EXPECTED_INSTANCES, "Duplicate material instance paths")

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

used_meshes = set()
for cue in p02_rows:
    label = str(cue.get_editor_property("label"))
    pair = cue.get_editor_property("wing_pair")
    require(bool(pair.get_editor_property("has_top")), f"Top disabled: {label}")
    for role in ("left", "right", "top"):
        panel = pair.get_editor_property(role)
        mesh = panel.get_editor_property("mesh")
        mesh_name = asset_path(mesh)
        require(
            mesh_name and "/Passage02_AnimalsToShrineV2/StaticMeshes/SM_P02_SET" in mesh_name,
            f"Unexpected {role} mesh for {label}: {mesh_name}",
        )
        require(
            not list(panel.get_editor_property("material_overrides")),
            f"Unexpected material override for {label}:{role}",
        )
        used_meshes.add(mesh_name)
require(len(used_meshes) == EXPECTED_INSTANCES, f"Expected 60 used meshes, found {len(used_meshes)}")

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
materialized = int(matches[0].get_editor_property("materialized_wing_pair_count"))
require(materialized == EXPECTED_ROWS, f"Materialized pair count mismatch: {materialized}")

require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "Verification dirtied content",
)
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    "Verification dirtied a map",
)

report = {
    "status": "ok",
    "world": world_path,
    "rows": len(p02_rows),
    "used_meshes": len(used_meshes),
    "instances": len(verified_instances),
    "opacity_matches": len(verified_instances),
    "bamboo_opacity_assignments": 0,
    "materialized_pairs": materialized,
    "dirty_content": [],
    "dirty_maps": [],
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "verify_p02_opacity_masks.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)

unreal.log(
    "P02_OPACITY_VERIFY_SUCCESS"
    f"|rows={len(p02_rows)}|used_meshes={len(used_meshes)}"
    f"|instances={len(verified_instances)}|opacity_matches={len(verified_instances)}"
    f"|bamboo=0|materialized_pairs={materialized}|dirty=0"
)
