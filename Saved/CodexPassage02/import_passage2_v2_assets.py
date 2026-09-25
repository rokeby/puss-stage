import gc
import json
from pathlib import Path

import unreal


PROJECT_ROOT = Path("/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage")
SOURCE_ROOT = PROJECT_ROOT / "DerivedAssets/Passage01V2Batch/GeneratedWings"
PIPELINE_REPORT = SOURCE_ROOT / "wing_pipeline_report.json"
FBX_VALIDATION_REPORT = (
    PROJECT_ROOT
    / "DerivedAssets/Passage01V2Batch/fbx_clean_reimport_validation.json"
)
TEXTURE_VALIDATION_REPORT = (
    PROJECT_ROOT
    / "DerivedAssets/Passage01V2Batch/texture_registration_validation.json"
)

CONTENT_ROOT = "/Game/Wings/Passage02_AnimalsToShrineV2"
MESH_ROOT = f"{CONTENT_ROOT}/StaticMeshes"
TEXTURE_ROOT = f"{CONTENT_ROOT}/Textures"
INSTANCE_ROOT = f"{CONTENT_ROOT}/Materials/Instances"
MASTER_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
EDGE_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_json(path):
    require(path.is_file(), f"Required report missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def package_path(folder, name):
    return f"{folder}/{name}"


def load_asset(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    require(asset is not None, f"Asset did not load: {path}")
    return asset


def import_texture_tasks(specs, asset_tools):
    missing_specs = [
        spec
        for spec in specs
        if not unreal.EditorAssetLibrary.does_asset_exist(
            package_path(TEXTURE_ROOT, spec[1])
        )
    ]
    for start in range(0, len(missing_specs), 60):
        tasks = []
        for filename, destination_name, _kind in missing_specs[start : start + 60]:
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(filename))
            task.set_editor_property("destination_path", TEXTURE_ROOT)
            task.set_editor_property("destination_name", destination_name)
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", False)
            task.set_editor_property("save", True)
            tasks.append(task)
        if tasks:
            asset_tools.import_asset_tasks(tasks)
            unreal.log(
                f"P02_V2_IMPORT_PROGRESS|texture_batch={start // 60 + 1}"
                f"|count={len(tasks)}"
            )
            del tasks
            gc.collect()


def make_fbx_options():
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property(
        "mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH
    )
    static_data = options.get_editor_property("static_mesh_import_data")
    static_data.set_editor_property("import_translation", unreal.Vector(0.0, 0.0, 0.0))
    static_data.set_editor_property("import_rotation", unreal.Rotator(0.0, 0.0, 0.0))
    static_data.set_editor_property("import_uniform_scale", 1.0)
    static_data.set_editor_property("combine_meshes", True)
    static_data.set_editor_property("generate_lightmap_u_vs", False)
    static_data.set_editor_property("auto_generate_collision", False)
    static_data.set_editor_property(
        "normal_import_method",
        unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,
    )
    return options


def import_mesh_tasks(specs, asset_tools):
    missing_specs = [
        spec
        for spec in specs
        if not unreal.EditorAssetLibrary.does_asset_exist(
            package_path(MESH_ROOT, spec[1])
        )
    ]
    for start in range(0, len(missing_specs), 15):
        options = make_fbx_options()
        tasks = []
        for filename, destination_name in missing_specs[start : start + 15]:
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(filename))
            task.set_editor_property("destination_path", MESH_ROOT)
            task.set_editor_property("destination_name", destination_name)
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", False)
            task.set_editor_property("save", True)
            task.set_editor_property("options", options)
            tasks.append(task)
        if tasks:
            asset_tools.import_asset_tasks(tasks)
            unreal.log(
                f"P02_V2_IMPORT_PROGRESS|mesh_batch={start // 15 + 1}"
                f"|count={len(tasks)}"
            )
            del tasks
            gc.collect()


def configure_texture(texture, kind):
    if kind == "base":
        texture.set_editor_property("srgb", True)
    elif kind == "height":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE
        )
    elif kind == "normal":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP
        )
        texture.set_editor_property("flip_green_channel", False)
    else:
        raise RuntimeError(f"Unknown texture kind: {kind}")


def get_or_create_instance(asset_tools, name, parent):
    path = package_path(INSTANCE_ROOT, name)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        instance = load_asset(path)
    else:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        instance = asset_tools.create_asset(
            name, INSTANCE_ROOT, unreal.MaterialInstanceConstant, factory
        )
    require(
        isinstance(instance, unreal.MaterialInstanceConstant),
        f"Expected MaterialInstanceConstant: {path}",
    )
    instance.set_editor_property("parent", parent)
    return instance


pipeline = load_json(PIPELINE_REPORT)
fbx_validation = load_json(FBX_VALIDATION_REPORT)
texture_validation = load_json(TEXTURE_VALIDATION_REPORT)
pipeline_results = pipeline.get("results", [])
require(len(pipeline_results) == 60, "Pipeline report must contain 60 assets")
require(
    all(
        item.get("status") == "ok"
        and item.get("thickness_cm") == 10.0
        and item.get("height_m") == 2.0
        and item.get("final_height_m") == 10.0
        and item.get("ue_panel_scale") == 5.0
        and item.get("ue_yaw_deg") == 90.0
        and item.get("vertices", 0) > 0
        and item.get("polygons", 0) > 0
        for item in pipeline_results
    ),
    "Pipeline V2 contract failed",
)
require(
    fbx_validation.get("status") == "ok"
    and fbx_validation.get("validated_count") == 60
    and fbx_validation.get("failed_count") == 0,
    "Factory-clean FBX validation report failed",
)
require(
    texture_validation.get("status") == "ok"
    and texture_validation.get("validated_count") == 60
    and texture_validation.get("failed_count") == 0,
    "Texture registration report failed",
)

editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor_subsystem.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
require(editor_subsystem.get_game_world() is None, "PIE/SIE is active")

dirty_content_before = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps_before = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(
    "P02_V2_IMPORT_PREFLIGHT"
    f"|world={world_path}"
    f"|dirty_content={len(dirty_content_before)}"
    f"|dirty_maps={len(dirty_maps_before)}"
)

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
master = load_asset(MASTER_PATH)
edge = load_asset(EDGE_PATH)

texture_specs = []
mesh_specs = []
asset_records = []
for set_number in range(1, 21):
    for role in ("L", "R", "T"):
        source_name = f"P01_SET{set_number:02d}_{role}"
        target_name = f"P02_SET{set_number:02d}_{role}"
        source_dir = SOURCE_ROOT / source_name
        texture_dir = source_dir / "Textures"
        base_name = f"T_{target_name}"
        height_name = f"T_{target_name}_H"
        normal_name = f"T_{target_name}_N"
        mesh_name = f"SM_{target_name}"
        mi_name = f"MI_{target_name}_Relief"
        base_file = texture_dir / f"{source_name}.png"
        height_file = texture_dir / f"{source_name}_H.png"
        normal_file = texture_dir / f"{source_name}_N.png"
        fbx_file = source_dir / f"SM_{source_name}.fbx"
        for path in (base_file, height_file, normal_file, fbx_file):
            require(path.is_file(), f"Missing source file: {path}")
        texture_specs.extend(
            [
                (base_file, base_name, "base"),
                (height_file, height_name, "height"),
                (normal_file, normal_name, "normal"),
            ]
        )
        mesh_specs.append((fbx_file, mesh_name))
        asset_records.append(
            {
                "target_name": target_name,
                "base_name": base_name,
                "height_name": height_name,
                "normal_name": normal_name,
                "mesh_name": mesh_name,
                "mi_name": mi_name,
            }
        )

import_texture_tasks(texture_specs, asset_tools)
import_mesh_tasks(mesh_specs, asset_tools)

for _filename, destination_name, kind in texture_specs:
    texture = load_asset(package_path(TEXTURE_ROOT, destination_name))
    require(isinstance(texture, unreal.Texture2D), f"Not Texture2D: {destination_name}")
    configure_texture(texture, kind)

for record in asset_records:
    base = load_asset(package_path(TEXTURE_ROOT, record["base_name"]))
    height = load_asset(package_path(TEXTURE_ROOT, record["height_name"]))
    normal = load_asset(package_path(TEXTURE_ROOT, record["normal_name"]))
    mesh = load_asset(package_path(MESH_ROOT, record["mesh_name"]))
    require(isinstance(mesh, unreal.StaticMesh), f"Not StaticMesh: {record['mesh_name']}")
    instance = get_or_create_instance(asset_tools, record["mi_name"], master)
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        instance, "BaseColor", base
    )
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        instance, "Height", height
    )
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        instance, "Normal", normal
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, "HeightRatio", 0.004
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, "Roughness", 0.72
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, "Specular", 0.25
    )
    unreal.MaterialEditingLibrary.update_material_instance(instance)

    slot_names = [
        str(item.get_editor_property("material_slot_name"))
        for item in mesh.get_editor_property("static_materials")
    ]
    require(len(slot_names) == 3, f"Expected three mesh slots: {mesh.get_path_name()}")
    require(
        slot_names[0].endswith("_Front")
        and slot_names[1].endswith("_Back")
        and slot_names[2].endswith("_Edge"),
        f"Unexpected slot order for {mesh.get_path_name()}: {slot_names}",
    )
    mesh.set_material(0, instance)
    mesh.set_material(1, instance)
    mesh.set_material(2, edge)

saved = unreal.EditorAssetLibrary.save_directory(
    CONTENT_ROOT, only_if_is_dirty=False, recursive=True
)
require(saved, f"Targeted save failed: {CONTENT_ROOT}")

expected_assets = set()
for record in asset_records:
    expected_assets.update(
        {
            package_path(TEXTURE_ROOT, record["base_name"]),
            package_path(TEXTURE_ROOT, record["height_name"]),
            package_path(TEXTURE_ROOT, record["normal_name"]),
            package_path(MESH_ROOT, record["mesh_name"]),
            package_path(INSTANCE_ROOT, record["mi_name"]),
        }
    )
missing_assets = sorted(
    path for path in expected_assets if not unreal.EditorAssetLibrary.does_asset_exist(path)
)
require(not missing_assets, f"Imported asset read-back missing: {missing_assets}")

unreal.log(
    "P02_V2_IMPORT_SUCCESS"
    "|meshes=60|textures=180|instances=60|total=300"
    "|height_ratio=0.004|reference_plane=0.50|normal_strength=4.5"
    "|source_flips=0|fbx_import_rotation=identity|fbx_import_scale=identity"
    f"|content_root={CONTENT_ROOT}"
)
