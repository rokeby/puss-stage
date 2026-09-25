import math

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
BACKUP_PATH = (
    "/Game/InfinityStage/Dev/SavedVersions/"
    "DA_InfinityStage_V1Show_P02_PreAnimalsToShrineV2_20260815"
)
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CONTENT_ROOT = "/Game/Wings/Passage02_AnimalsToShrineV2"
MESH_ROOT = f"{CONTENT_ROOT}/StaticMeshes"
TEXTURE_ROOT = f"{CONTENT_ROOT}/Textures"
INSTANCE_ROOT = f"{CONTENT_ROOT}/Materials/Instances"
MASTER_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
EDGE_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
ACTOR_LABEL = "Passage 02 — Fixed Wings"
SET_SEQUENCE = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2,
    13, 14, 15, 16, 13,
    17, 18, 19, 20,
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_asset(path, expected_class=None):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    require(asset is not None, f"Asset did not load: {path}")
    if expected_class is not None:
        require(isinstance(asset, expected_class), f"Wrong asset class: {path}")
    return asset


def asset_package(value):
    if value is None:
        return "None"
    return value.get_path_name().split(".", 1)[0]


def near(value, expected, tolerance=1.0e-6):
    return math.isclose(float(value), float(expected), abs_tol=tolerance)


def serialized_texture_parameters(instance):
    return {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        value.get_editor_property("parameter_value")
        for value in instance.get_editor_property("texture_parameter_values")
    }


def serialized_scalar_parameters(instance):
    return {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        float(value.get_editor_property("parameter_value"))
        for value in instance.get_editor_property("scalar_parameter_values")
    }


editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor_subsystem.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
require(editor_subsystem.get_game_world() is None, "PIE/SIE is active")

show = load_asset(SHOW_PATH)
require(unreal.EditorAssetLibrary.does_asset_exist(BACKUP_PATH), "Backup is missing")
backup = load_asset(BACKUP_PATH)
require(backup is not None, "Backup did not load")

master = load_asset(MASTER_PATH)
edge = load_asset(EDGE_PATH)
all_assets = unreal.EditorAssetLibrary.list_assets(
    CONTENT_ROOT, recursive=True, include_folder=False
)
require(len(all_assets) == 300, f"Expected 300 scoped assets, found {len(all_assets)}")

for set_number in range(1, 21):
    for role in ("L", "R", "T"):
        target_name = f"P02_SET{set_number:02d}_{role}"
        base = load_asset(f"{TEXTURE_ROOT}/T_{target_name}", unreal.Texture2D)
        height = load_asset(f"{TEXTURE_ROOT}/T_{target_name}_H", unreal.Texture2D)
        normal = load_asset(f"{TEXTURE_ROOT}/T_{target_name}_N", unreal.Texture2D)
        mesh = load_asset(f"{MESH_ROOT}/SM_{target_name}", unreal.StaticMesh)
        instance = load_asset(
            f"{INSTANCE_ROOT}/MI_{target_name}_Relief",
            unreal.MaterialInstanceConstant,
        )
        texture_parameters = serialized_texture_parameters(instance)
        scalar_parameters = serialized_scalar_parameters(instance)
        require(instance.get_editor_property("parent") == master, f"Wrong MI parent: {target_name}")
        require(
            texture_parameters.get("BaseColor") == base,
            f"BaseColor mismatch: {target_name}",
        )
        require(
            texture_parameters.get("Height") == height,
            f"Height mismatch: {target_name}",
        )
        require(
            texture_parameters.get("Normal") == normal,
            f"Normal mismatch: {target_name}",
        )
        require(
            near(scalar_parameters.get("HeightRatio"), 0.004),
            f"HeightRatio mismatch: {target_name}",
        )
        require(
            near(scalar_parameters.get("Roughness"), 0.72),
            f"Roughness mismatch: {target_name}",
        )
        require(
            near(scalar_parameters.get("Specular"), 0.25),
            f"Specular mismatch: {target_name}",
        )
        require(bool(base.get_editor_property("srgb")), f"Base must be sRGB: {target_name}")
        require(not bool(height.get_editor_property("srgb")), f"Height must be linear: {target_name}")
        require(not bool(normal.get_editor_property("srgb")), f"Normal must be linear: {target_name}")
        require(
            height.get_editor_property("compression_settings")
            == unreal.TextureCompressionSettings.TC_GRAYSCALE,
            f"Height compression mismatch: {target_name}",
        )
        require(
            normal.get_editor_property("compression_settings")
            == unreal.TextureCompressionSettings.TC_NORMALMAP,
            f"Normal compression mismatch: {target_name}",
        )
        require(
            not bool(normal.get_editor_property("flip_green_channel")),
            f"DirectX normal green channel must not flip: {target_name}",
        )
        slot_names = [
            str(item.get_editor_property("material_slot_name"))
            for item in mesh.get_editor_property("static_materials")
        ]
        require(len(slot_names) == 3, f"Mesh slot count mismatch: {target_name}")
        require(mesh.get_material(0) == instance, f"Front material mismatch: {target_name}")
        require(mesh.get_material(1) == instance, f"Back material mismatch: {target_name}")
        require(mesh.get_material(2) == edge, f"Edge material mismatch: {target_name}")

cues = list(show.get_editor_property("cues"))
p02_rows = [
    (index, cue)
    for index, cue in enumerate(cues)
    if str(cue.get_editor_property("label")).startswith("P02 Wing ")
]
require(len(p02_rows) == 23, f"Expected 23 Passage 2 rows, found {len(p02_rows)}")
require([index for index, _cue in p02_rows] == list(range(49, 72)), "Cue indexes changed")

for ordinal, ((cue_index, cue), set_number) in enumerate(
    zip(p02_rows, SET_SEQUENCE), start=1
):
    pair = cue.get_editor_property("wing_pair")
    left = pair.get_editor_property("left")
    right = pair.get_editor_property("right")
    top = pair.get_editor_property("top")
    expected = {
        "left": f"{MESH_ROOT}/SM_P02_SET{set_number:02d}_L",
        "right": f"{MESH_ROOT}/SM_P02_SET{set_number:02d}_R",
        "top": f"{MESH_ROOT}/SM_P02_SET{set_number:02d}_T",
    }
    require(
        asset_package(left.get_editor_property("mesh")) == expected["left"],
        f"Left mismatch at row {ordinal}",
    )
    require(
        asset_package(right.get_editor_property("mesh")) == expected["right"],
        f"Right mismatch at row {ordinal}",
    )
    require(bool(pair.get_editor_property("has_top")), f"Top disabled at row {ordinal}")
    require(
        asset_package(top.get_editor_property("mesh")) == expected["top"],
        f"Top mismatch at row {ordinal}",
    )
    require(
        not bool(left.get_editor_property("flip_image_horizontally")),
        f"Left image flip enabled at row {ordinal}",
    )
    require(
        not bool(right.get_editor_property("flip_image_horizontally")),
        f"Right image flip enabled at row {ordinal}",
    )
    require(
        not bool(top.get_editor_property("flip_image_horizontally")),
        f"Top image flip enabled at row {ordinal}",
    )

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
matches = []
for actor in actor_subsystem.get_all_level_actors():
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
materialized_pairs = int(matches[0].get_editor_property("materialized_wing_pair_count"))
require(materialized_pairs == 23, f"Expected 23 materialized pairs, found {materialized_pairs}")

dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
require(not dirty_content, f"Content remains dirty: {[asset_package(x) for x in dirty_content]}")
require(not dirty_maps, f"Map remains dirty: {[asset_package(x) for x in dirty_maps]}")

unreal.log(
    "P02_ANIMALS_SHRINE_VERIFY_SUCCESS"
    "|rows=23|stage_counts=14,5,4"
    "|sets=01,02,03,04,05,06,07,08,09,10,11,12,01,02,13,14,15,16,13,17,18,19,20"
    "|assets=300|meshes=60|textures=180|instances=60"
    "|height_ratio=0.004|reference_plane=0.50|normal_strength=4.5"
    "|left_flips=0|right_flips=0|top_flips=0|tops=23"
    f"|materialized_pairs={materialized_pairs}|backup_readback=1|dirty=0"
)
