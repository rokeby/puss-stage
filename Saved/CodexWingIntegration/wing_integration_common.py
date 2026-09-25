import gc
import json
import math
from pathlib import Path

import unreal


PROJECT_ROOT = Path("/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
EDGE_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"

P03_FAMILIES = [
    "P03_SunWashedAdministration_01",
    "P03_GlassBlockClassroom_01",
    "P03_YellowCurtainThreshold_01",
    "P03_RepeatingSanatoriumArches_01",
    "P03_PlasterSalonTransition_01",
    "P03_CeladonPalatialAntechamber_01",
]
P03_ASSETS = [f"{family}_{role}" for family in P03_FAMILIES for role in ("L", "R", "C")]
P03_ROWS = [
    {
        "left": f"{P03_FAMILIES[index % len(P03_FAMILIES)]}_L",
        "right": f"{P03_FAMILIES[index % len(P03_FAMILIES)]}_R",
        "top": f"{P03_FAMILIES[index % len(P03_FAMILIES)]}_C",
    }
    for index in range(21)
]

P05_SIDE_FAMILIES = [f"CloudRef{index:02d}" for index in range(1, 9)]
P05_TOPS = [
    "CloudCeilingLarge_01_C",
    "CloudCeilingLarge_02_C",
    "CloudCeilingLarge_03_C",
    "CloudCeilingSmall_01_C",
    "CloudCeilingSmall_02_C",
    "CloudCeilingSmall_03_C",
]
P05_ASSETS = [
    f"{family}_{role}" for family in P05_SIDE_FAMILIES for role in ("L", "R")
] + P05_TOPS
P05_ROWS = [
    {
        "left": f"{P05_SIDE_FAMILIES[index % len(P05_SIDE_FAMILIES)]}_L",
        "right": f"{P05_SIDE_FAMILIES[index % len(P05_SIDE_FAMILIES)]}_R",
        "top": P05_TOPS[index % len(P05_TOPS)],
    }
    for index in range(93)
]

CONFIGS = {
    3: {
        "code": "P03",
        "name": "SHRINE_FORGETTING",
        "source_root": PROJECT_ROOT / "DerivedAssets/GeneratedWingsV2_Passage03",
        "content_root": "/Game/Wings/Passage03_ShrineToForgetting",
        "backup": (
            "/Game/InfinityStage/Dev/SavedVersions/"
            "DA_InfinityStage_V1Show_P03_PreShrineToForgettingV2_20260815"
        ),
        "actor_label": "Passage 03 — Fixed Wings",
        "label_prefix": "P03 Wing ",
        "first_index": 73,
        "row_count": 21,
        "assets": P03_ASSETS,
        "rows": P03_ROWS,
    },
    5: {
        "code": "P05",
        "name": "BIRD_MOUNTAIN",
        "source_root": (
            PROJECT_ROOT
            / "DerivedAssets/Passage05BirdToMountainBatch/GeneratedWingsV2"
        ),
        "content_root": "/Game/Wings/Passage05_BirdToMountain",
        "backup": (
            "/Game/InfinityStage/Dev/SavedVersions/"
            "DA_InfinityStage_V1Show_P05_PreBirdToMountainV2_20260815"
        ),
        "actor_label": "Passage 05 — Fixed Wings",
        "label_prefix": "P05 Wing ",
        "first_index": 117,
        "row_count": 93,
        "assets": P05_ASSETS,
        "rows": P05_ROWS,
    },
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def config_for(passage):
    require(passage in CONFIGS, f"Unsupported Passage: {passage}")
    return CONFIGS[passage]


def asset_package(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value)


def load_asset(path, expected_class=None):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    require(asset is not None, f"Asset did not load: {path}")
    if expected_class is not None:
        require(isinstance(asset, expected_class), f"Wrong asset class: {path}")
    return asset


def validate_editor_state(require_clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "No editor world is open")
    world_path = world.get_path_name().split(".", 1)[0]
    require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
    require(editor.get_game_world() is None, "PIE/SIE is active")
    dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if require_clean:
        require(
            not dirty_content,
            f"Dirty content before operation: {[asset_package(x) for x in dirty_content]}",
        )
        require(
            not dirty_maps,
            f"Dirty maps before operation: {[asset_package(x) for x in dirty_maps]}",
        )
    return world_path


def settle_scoped_import_state(config):
    dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    dirty_names = {asset_package(item) for item in dirty_content}
    scoped_prefix = f"{config['content_root']}/"
    require(not dirty_maps, f"Dirty maps before settle save: {[asset_package(x) for x in dirty_maps]}")
    require(
        all(name.startswith(scoped_prefix) for name in dirty_names),
        f"Refusing to settle unrelated dirty content: {sorted(dirty_names)}",
    )
    if dirty_names:
        require(
            unreal.EditorAssetLibrary.save_directory(
                config["content_root"], only_if_is_dirty=True, recursive=True
            ),
            f"Scoped settle save failed: {config['content_root']}",
        )
        unreal.log(
            f"{config['code']}_V2_SCOPED_SETTLE_SAVE"
            f"|packages={len(dirty_names)}|scope={config['content_root']}"
        )
    validate_editor_state(require_clean=True)


def package_path(folder, name):
    return f"{folder}/{name}"


def texture_specs_for(config):
    specs = []
    for asset_name in config["assets"]:
        texture_dir = config["source_root"] / asset_name / "Textures"
        specs.extend(
            [
                (texture_dir / f"{asset_name}.png", f"T_{asset_name}", "base"),
                (texture_dir / f"{asset_name}_H.png", f"T_{asset_name}_H", "height"),
                (texture_dir / f"{asset_name}_N.png", f"T_{asset_name}_N", "normal"),
            ]
        )
    return specs


def mesh_specs_for(config):
    return [
        (
            config["source_root"] / asset_name / f"SM_{asset_name}.fbx",
            f"SM_{asset_name}",
        )
        for asset_name in config["assets"]
    ]


def make_fbx_options():
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
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


def import_texture_tasks(specs, root, asset_tools, code):
    missing = [
        spec
        for spec in specs
        if not unreal.EditorAssetLibrary.does_asset_exist(package_path(root, spec[1]))
    ]
    for start in range(0, len(missing), 60):
        tasks = []
        for filename, destination_name, _kind in missing[start : start + 60]:
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(filename))
            task.set_editor_property("destination_path", root)
            task.set_editor_property("destination_name", destination_name)
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", False)
            task.set_editor_property("save", True)
            tasks.append(task)
        if tasks:
            asset_tools.import_asset_tasks(tasks)
            unreal.log(f"{code}_V2_IMPORT_PROGRESS|textures={len(tasks)}")
            del tasks
            gc.collect()


def import_mesh_tasks(specs, root, asset_tools, code):
    missing = [
        spec
        for spec in specs
        if not unreal.EditorAssetLibrary.does_asset_exist(package_path(root, spec[1]))
    ]
    for start in range(0, len(missing), 15):
        tasks = []
        options = make_fbx_options()
        for filename, destination_name in missing[start : start + 15]:
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(filename))
            task.set_editor_property("destination_path", root)
            task.set_editor_property("destination_name", destination_name)
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", False)
            task.set_editor_property("save", True)
            task.set_editor_property("options", options)
            tasks.append(task)
        if tasks:
            asset_tools.import_asset_tasks(tasks)
            unreal.log(f"{code}_V2_IMPORT_PROGRESS|meshes={len(tasks)}")
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


def get_or_create_instance(asset_tools, path, name, parent):
    full_path = package_path(path, name)
    if unreal.EditorAssetLibrary.does_asset_exist(full_path):
        instance = load_asset(full_path)
    else:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        instance = asset_tools.create_asset(
            name, path, unreal.MaterialInstanceConstant, factory
        )
    require(isinstance(instance, unreal.MaterialInstanceConstant), f"Wrong MI: {full_path}")
    instance.set_editor_property("parent", parent)
    return instance


def validate_pipeline_report(config):
    report_path = config["source_root"] / "wing_pipeline_report.json"
    require(report_path.is_file(), f"Pipeline report missing: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    results = report.get("results", [])
    require(len(results) == len(config["assets"]), "Pipeline result count mismatch")
    require(
        {item.get("asset_name") for item in results} == set(config["assets"]),
        "Pipeline report asset set mismatch",
    )
    require(
        all(
            item.get("status") == "ok"
            and item.get("thickness_cm") == 10.0
            and item.get("height_m") == 2.0
            and item.get("final_height_m") == 10.0
            and item.get("ue_panel_scale") == 5.0
            and item.get("ue_yaw_deg") == 90.0
            and item.get("placement_transform_baked") is True
            and item.get("vertices", 0) > 0
            and item.get("polygons", 0) > 0
            for item in results
        ),
        "Pipeline V2 contract failed",
    )


def import_assets(passage):
    config = config_for(passage)
    world_path = validate_editor_state(require_clean=True)
    validate_pipeline_report(config)
    content_root = config["content_root"]
    mesh_root = f"{content_root}/StaticMeshes"
    texture_root = f"{content_root}/Textures"
    instance_root = f"{content_root}/Materials/Instances"
    texture_specs = texture_specs_for(config)
    mesh_specs = mesh_specs_for(config)
    for source_path, _name, _kind in texture_specs:
        require(source_path.is_file(), f"Missing source texture: {source_path}")
    for source_path, _name in mesh_specs:
        require(source_path.is_file(), f"Missing source FBX: {source_path}")

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    master = load_asset(MASTER_PATH)
    edge = load_asset(EDGE_PATH)
    import_texture_tasks(texture_specs, texture_root, asset_tools, config["code"])
    import_mesh_tasks(mesh_specs, mesh_root, asset_tools, config["code"])

    for _source, name, kind in texture_specs:
        texture = load_asset(package_path(texture_root, name), unreal.Texture2D)
        configure_texture(texture, kind)

    for asset_name in config["assets"]:
        base = load_asset(f"{texture_root}/T_{asset_name}", unreal.Texture2D)
        height = load_asset(f"{texture_root}/T_{asset_name}_H", unreal.Texture2D)
        normal = load_asset(f"{texture_root}/T_{asset_name}_N", unreal.Texture2D)
        mesh = load_asset(f"{mesh_root}/SM_{asset_name}", unreal.StaticMesh)
        instance = get_or_create_instance(
            asset_tools, instance_root, f"MI_{asset_name}_Relief", master
        )
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
        require(len(slot_names) == 3, f"Expected three mesh slots: {asset_name}")
        require(
            slot_names[0].endswith("_Front")
            and slot_names[1].endswith("_Back")
            and slot_names[2].endswith("_Edge"),
            f"Unexpected slot order for {asset_name}: {slot_names}",
        )
        mesh.set_material(0, instance)
        mesh.set_material(1, instance)
        mesh.set_material(2, edge)

    require(
        unreal.EditorAssetLibrary.save_directory(
            content_root, only_if_is_dirty=False, recursive=True
        ),
        f"Targeted save failed: {content_root}",
    )
    scoped_assets = unreal.EditorAssetLibrary.list_assets(
        content_root, recursive=True, include_folder=False
    )
    expected_total = len(config["assets"]) * 5
    require(len(scoped_assets) == expected_total, f"Scoped asset count mismatch: {len(scoped_assets)}")
    validate_editor_state(require_clean=True)
    unreal.log(
        f"{config['code']}_V2_IMPORT_SUCCESS"
        f"|meshes={len(config['assets'])}|textures={len(config['assets']) * 3}"
        f"|instances={len(config['assets'])}|total={expected_total}"
        "|thickness_cm=10|base_height_normal=1|relief_preview=1"
        "|height_ratio=0.004|reference_plane=0.50|normal_strength=4.5"
        "|source_flips=0|fbx_import_rotation=identity|fbx_import_scale=identity"
        f"|clean_fbx_imports={len(config['assets'])}|world={world_path}"
        f"|content_root={content_root}|dirty=0"
    )


def find_passage_actor(config, show):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    matches = []
    for actor in actors:
        if actor.get_class().get_name() != "InfinityStagePassageActor":
            continue
        if actor.get_actor_label() != config["actor_label"]:
            continue
        try:
            if actor.get_editor_property("show_asset") == show:
                matches.append(actor)
        except Exception:
            pass
    require(len(matches) == 1, f"Expected one actor {config['actor_label']}, found {len(matches)}")
    return matches[0]


def assign_passage(passage):
    config = config_for(passage)
    validate_editor_state(require_clean=False)
    settle_scoped_import_state(config)
    show = load_asset(SHOW_PATH)
    if not unreal.EditorAssetLibrary.does_asset_exist(config["backup"]):
        backup = unreal.EditorAssetLibrary.duplicate_asset(SHOW_PATH, config["backup"])
        require(backup is not None, f"Backup creation failed: {config['backup']}")
        require(
            unreal.EditorAssetLibrary.save_asset(config["backup"], only_if_is_dirty=False),
            f"Backup save failed: {config['backup']}",
        )
    else:
        load_asset(config["backup"])

    cues = list(show.get_editor_property("cues"))
    rows = [
        (index, cue)
        for index, cue in enumerate(cues)
        if str(cue.get_editor_property("label")).startswith(config["label_prefix"])
    ]
    expected_indexes = list(
        range(config["first_index"], config["first_index"] + config["row_count"])
    )
    expected_labels = [
        f"{config['label_prefix']}{ordinal:03d}"
        for ordinal in range(1, config["row_count"] + 1)
    ]
    require(len(rows) == config["row_count"], f"Wing row count mismatch: {len(rows)}")
    require([index for index, _cue in rows] == expected_indexes, "Cue indexes changed")
    require(
        [str(cue.get_editor_property("label")) for _index, cue in rows]
        == expected_labels,
        "Stable cue labels changed",
    )

    mesh_root = f"{config['content_root']}/StaticMeshes"
    for (cue_index, cue), row in zip(rows, config["rows"]):
        pair = cue.get_editor_property("wing_pair")
        for role in ("left", "right", "top"):
            panel = pair.get_editor_property(role)
            mesh = load_asset(f"{mesh_root}/SM_{row[role]}", unreal.StaticMesh)
            panel.set_editor_property("mesh", mesh)
            panel.set_editor_property("flip_image_horizontally", False)
            panel.set_editor_property("material_overrides", [])
            pair.set_editor_property(role, panel)
        pair.set_editor_property("has_top", True)
        cue.set_editor_property("wing_pair", pair)
        cues[cue_index] = cue

    show.set_editor_property("cues", cues)
    actor = find_passage_actor(config, show)
    require(bool(actor.materialize_passage()), f"Passage {passage} materialization failed")

    dirty_content = {
        asset_package(item)
        for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    }
    dirty_maps = {
        asset_package(item)
        for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    }
    require(dirty_content.issubset({SHOW_PATH}), f"Unexpected dirty content: {dirty_content}")
    require(dirty_maps.issubset({EXPECTED_WORLD}), f"Unexpected dirty maps: {dirty_maps}")
    require(
        unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False),
        "Show Asset save failed",
    )
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    require(bool(level_editor.save_current_level()), "Current level save failed")
    settle_scoped_import_state(config)
    unreal.log(
        f"{config['code']}_{config['name']}_ASSIGN_SUCCESS"
        f"|rows={config['row_count']}|left_flips=0|right_flips=0|top_flips=0"
        f"|tops={config['row_count']}|materialized=1|show_saved=1|level_saved=1"
        f"|backup={config['backup']}|dirty=0"
    )


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


def near(value, expected, tolerance=1.0e-6):
    return value is not None and math.isclose(float(value), float(expected), abs_tol=tolerance)


def verify_passage(passage):
    config = config_for(passage)
    validate_editor_state(require_clean=True)
    validate_pipeline_report(config)
    show = load_asset(SHOW_PATH)
    require(unreal.EditorAssetLibrary.does_asset_exist(config["backup"]), "Backup missing")
    load_asset(config["backup"])
    master = load_asset(MASTER_PATH)
    edge = load_asset(EDGE_PATH)
    content_root = config["content_root"]
    mesh_root = f"{content_root}/StaticMeshes"
    texture_root = f"{content_root}/Textures"
    instance_root = f"{content_root}/Materials/Instances"
    scoped_assets = unreal.EditorAssetLibrary.list_assets(
        content_root, recursive=True, include_folder=False
    )
    expected_total = len(config["assets"]) * 5
    require(len(scoped_assets) == expected_total, f"Scoped asset count mismatch: {len(scoped_assets)}")

    for asset_name in config["assets"]:
        base = load_asset(f"{texture_root}/T_{asset_name}", unreal.Texture2D)
        height = load_asset(f"{texture_root}/T_{asset_name}_H", unreal.Texture2D)
        normal = load_asset(f"{texture_root}/T_{asset_name}_N", unreal.Texture2D)
        mesh = load_asset(f"{mesh_root}/SM_{asset_name}", unreal.StaticMesh)
        instance = load_asset(
            f"{instance_root}/MI_{asset_name}_Relief", unreal.MaterialInstanceConstant
        )
        texture_parameters = serialized_texture_parameters(instance)
        scalar_parameters = serialized_scalar_parameters(instance)
        require(instance.get_editor_property("parent") == master, f"Wrong parent: {asset_name}")
        require(texture_parameters.get("BaseColor") == base, f"Wrong BaseColor: {asset_name}")
        require(texture_parameters.get("Height") == height, f"Wrong Height: {asset_name}")
        require(texture_parameters.get("Normal") == normal, f"Wrong Normal: {asset_name}")
        require(near(scalar_parameters.get("HeightRatio"), 0.004), f"Wrong HeightRatio: {asset_name}")
        require(near(scalar_parameters.get("Roughness"), 0.72), f"Wrong Roughness: {asset_name}")
        require(near(scalar_parameters.get("Specular"), 0.25), f"Wrong Specular: {asset_name}")
        require(bool(base.get_editor_property("srgb")), f"Base must be sRGB: {asset_name}")
        require(not bool(height.get_editor_property("srgb")), f"Height must be linear: {asset_name}")
        require(not bool(normal.get_editor_property("srgb")), f"Normal must be linear: {asset_name}")
        require(
            height.get_editor_property("compression_settings")
            == unreal.TextureCompressionSettings.TC_GRAYSCALE,
            f"Height compression mismatch: {asset_name}",
        )
        require(
            normal.get_editor_property("compression_settings")
            == unreal.TextureCompressionSettings.TC_NORMALMAP,
            f"Normal compression mismatch: {asset_name}",
        )
        require(not bool(normal.get_editor_property("flip_green_channel")), f"Normal green flip: {asset_name}")
        slot_names = [
            str(item.get_editor_property("material_slot_name"))
            for item in mesh.get_editor_property("static_materials")
        ]
        require(len(slot_names) == 3, f"Mesh slot count mismatch: {asset_name}")
        require(mesh.get_material(0) == instance, f"Front material mismatch: {asset_name}")
        require(mesh.get_material(1) == instance, f"Back material mismatch: {asset_name}")
        require(mesh.get_material(2) == edge, f"Edge material mismatch: {asset_name}")

    cues = list(show.get_editor_property("cues"))
    rows = [
        (index, cue)
        for index, cue in enumerate(cues)
        if str(cue.get_editor_property("label")).startswith(config["label_prefix"])
    ]
    require(len(rows) == config["row_count"], f"Wing row count mismatch: {len(rows)}")
    require(
        [index for index, _cue in rows]
        == list(range(config["first_index"], config["first_index"] + config["row_count"])),
        "Cue indexes changed",
    )
    for ordinal, ((_index, cue), row) in enumerate(zip(rows, config["rows"]), start=1):
        pair = cue.get_editor_property("wing_pair")
        require(bool(pair.get_editor_property("has_top")), f"Top disabled at row {ordinal}")
        for role in ("left", "right", "top"):
            panel = pair.get_editor_property(role)
            require(
                asset_package(panel.get_editor_property("mesh"))
                == f"{mesh_root}/SM_{row[role]}",
                f"{role} mesh mismatch at row {ordinal}",
            )
            require(
                not bool(panel.get_editor_property("flip_image_horizontally")),
                f"{role} image flip enabled at row {ordinal}",
            )

    actor = find_passage_actor(config, show)
    materialized = int(actor.get_editor_property("materialized_wing_pair_count"))
    require(materialized == config["row_count"], f"Materialized count mismatch: {materialized}")
    validate_editor_state(require_clean=True)
    unreal.log(
        f"{config['code']}_{config['name']}_VERIFY_SUCCESS"
        f"|rows={config['row_count']}|assets={expected_total}"
        f"|meshes={len(config['assets'])}|textures={len(config['assets']) * 3}"
        f"|instances={len(config['assets'])}|thickness_cm=10|base_height_normal=1"
        "|height_ratio=0.004|left_flips=0|right_flips=0|top_flips=0"
        f"|tops={config['row_count']}|materialized_pairs={materialized}"
        "|backup_readback=1|dirty=0"
    )
