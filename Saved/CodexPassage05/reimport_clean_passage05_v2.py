import gc
import json
from pathlib import Path

import unreal


PROJECT_ROOT = Path("/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage")
SOURCE_ROOT = (
    PROJECT_ROOT
    / "DerivedAssets/Passage05BirdToMountainBatch/GeneratedWingsV2_Clean"
)
CONTENT_ROOT = "/Game/Wings/Passage05_BirdToMountain"
MESH_ROOT = f"{CONTENT_ROOT}/StaticMeshes"
INSTANCE_ROOT = f"{CONTENT_ROOT}/Materials/Instances"
EDGE_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
BACKUP_PATH = (
    "/Game/InfinityStage/Dev/SavedVersions/"
    "DA_InfinityStage_V1Show_P05_PreCleanFBXRepair_20260815"
)
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ACTOR_LABEL = "Passage 05 — Fixed Wings"
ASSETS = [
    *(f"CloudRef{index:02d}_{role}" for index in range(1, 9) for role in ("L", "R")),
    "CloudCeilingLarge_01_C",
    "CloudCeilingLarge_02_C",
    "CloudCeilingLarge_03_C",
    "CloudCeilingSmall_01_C",
    "CloudCeilingSmall_02_C",
    "CloudCeilingSmall_03_C",
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


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


def serialized_scalar_parameters(instance):
    return {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        float(value.get_editor_property("parameter_value"))
        for value in instance.get_editor_property("scalar_parameter_values")
    }


def validate_source_reports():
    pipeline = json.loads((SOURCE_ROOT / "wing_pipeline_report.json").read_text())
    results = pipeline.get("results", [])
    require(pipeline.get("status") == "ok", "Pipeline report status is not ok")
    require(pipeline.get("result_count") == len(ASSETS), "Pipeline report result count mismatch")
    require(len(results) == len(ASSETS), f"Pipeline result count mismatch: {len(results)}")
    require({item.get("asset_name") for item in results} == set(ASSETS), "Pipeline asset set mismatch")
    require(
        all(
            item.get("status") == "ok"
            and item.get("height_m") == 2.0
            and item.get("final_height_m") == 10.0
            and item.get("thickness_cm") == 10.0
            and item.get("ue_panel_scale") == 5.0
            and item.get("ue_yaw_deg") == 90.0
            and item.get("mesh_cleanup", {}).get("triangles_only") is True
            and item.get("mesh_cleanup", {}).get("non_manifold_edges") == 0
            and item.get("mesh_cleanup", {}).get("degenerate_triangles") == 0
            for item in results
        ),
        "Clean V2 pipeline report failed",
    )
    validation = json.loads((SOURCE_ROOT / "clean_fbx_validation_report.json").read_text())
    require(validation.get("status") == "ok", "Clean FBX validation report failed")
    require(validation.get("validated_fbx_count") == len(ASSETS), "Clean FBX validation count mismatch")


def validate_editor_state(require_clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "No editor world is open")
    world_path = world.get_path_name().split(".", 1)[0]
    require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
    require(editor.get_game_world() is None, "PIE/SIE is active")
    dirty_content = [
        asset_package(item)
        for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    ]
    dirty_maps = [
        asset_package(item)
        for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    ]
    if require_clean:
        require(not dirty_content, f"Dirty content before operation: {dirty_content}")
        require(not dirty_maps, f"Dirty maps before operation: {dirty_maps}")
    return world_path, dirty_content, dirty_maps


def find_passage_actor(show):
    matches = []
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        if actor.get_class().get_name() != "InfinityStagePassageActor":
            continue
        try:
            if actor.get_actor_label() == ACTOR_LABEL and actor.get_editor_property("show_asset") == show:
                matches.append(actor)
        except Exception:
            pass
    require(len(matches) == 1, f"Expected one {ACTOR_LABEL} actor, found {len(matches)}")
    return matches[0]


def inspect_existing_rows(show):
    cues = list(show.get_editor_property("cues"))
    rows = [
        (index, cue)
        for index, cue in enumerate(cues)
        if str(cue.get_editor_property("label")).startswith("P05 Wing ")
    ]
    require(len(rows) == 93, f"Expected 93 Passage 5 rows, found {len(rows)}")
    valid_meshes = {f"{MESH_ROOT}/SM_{name}" for name in ASSETS}
    flip_count = 0
    for ordinal, (_cue_index, cue) in enumerate(rows, start=1):
        pair = cue.get_editor_property("wing_pair")
        require(bool(pair.get_editor_property("has_top")), f"Top disabled at row {ordinal}")
        for role in ("left", "right", "top"):
            panel = pair.get_editor_property(role)
            require(
                asset_package(panel.get_editor_property("mesh")) in valid_meshes,
                f"Unexpected {role} mesh at row {ordinal}",
            )
            flip_count += int(bool(panel.get_editor_property("flip_image_horizontally")))
    return cues, rows, flip_count


def repair_row_handedness(show, cues, rows):
    repaired = 0
    for cue_index, cue in rows:
        pair = cue.get_editor_property("wing_pair")
        for role in ("left", "right", "top"):
            panel = pair.get_editor_property(role)
            repaired += int(bool(panel.get_editor_property("flip_image_horizontally")))
            panel.set_editor_property("flip_image_horizontally", False)
            pair.set_editor_property(role, panel)
        cue.set_editor_property("wing_pair", pair)
        cues[cue_index] = cue
    show.set_editor_property("cues", cues)
    return repaired


def main():
    validate_source_reports()
    world_path, _dirty_content, _dirty_maps = validate_editor_state(require_clean=True)
    show = load_asset(SHOW_PATH)
    cues, rows, existing_flip_count = inspect_existing_rows(show)
    actor = find_passage_actor(show)
    edge = load_asset(EDGE_PATH)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    for start in range(0, len(ASSETS), 8):
        tasks = []
        options = make_fbx_options()
        for asset_name in ASSETS[start : start + 8]:
            fbx = SOURCE_ROOT / asset_name / f"SM_{asset_name}.fbx"
            require(fbx.is_file(), f"Missing clean FBX: {fbx}")
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(fbx))
            task.set_editor_property("destination_path", MESH_ROOT)
            task.set_editor_property("destination_name", f"SM_{asset_name}")
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", True)
            try:
                task.set_editor_property("replace_existing_settings", True)
            except Exception:
                pass
            task.set_editor_property("save", False)
            task.set_editor_property("options", options)
            tasks.append(task)
        asset_tools.import_asset_tasks(tasks)
        unreal.log(f"P05_CLEAN_REIMPORT_PROGRESS|meshes={len(tasks)}|start={start}")
        del tasks
        gc.collect()

    mesh_records = []
    for asset_name in ASSETS:
        mesh_path = f"{MESH_ROOT}/SM_{asset_name}"
        mesh = load_asset(mesh_path, unreal.StaticMesh)
        instance_path = f"{INSTANCE_ROOT}/MI_{asset_name}_Relief"
        instance = load_asset(instance_path, unreal.MaterialInstanceConstant)
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, "HeightRatio", 0.0
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
            unreal.EditorAssetLibrary.save_asset(instance_path, only_if_is_dirty=False),
            f"Material instance save failed: {instance_path}",
        )
        require(
            unreal.EditorAssetLibrary.save_asset(mesh_path, only_if_is_dirty=False),
            f"Static Mesh save failed: {mesh_path}",
        )
        mesh_records.append(
            {
                "asset_name": asset_name,
                "mesh": mesh_path,
                "source_fbx": str(SOURCE_ROOT / asset_name / f"SM_{asset_name}.fbx"),
                "slots": slot_names,
                "height_ratio": serialized_scalar_parameters(instance).get("HeightRatio"),
            }
        )

    if not unreal.EditorAssetLibrary.does_asset_exist(BACKUP_PATH):
        backup = unreal.EditorAssetLibrary.duplicate_asset(SHOW_PATH, BACKUP_PATH)
        require(backup is not None, f"Show backup creation failed: {BACKUP_PATH}")
        require(
            unreal.EditorAssetLibrary.save_asset(BACKUP_PATH, only_if_is_dirty=False),
            f"Show backup save failed: {BACKUP_PATH}",
        )
    repaired_flip_count = repair_row_handedness(show, cues, rows)
    require(repaired_flip_count == existing_flip_count, "Flip repair count changed during operation")
    require(
        unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False),
        "Show Asset save failed",
    )
    require(bool(actor.materialize_passage()), "Passage 5 materialization failed")
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    require(bool(level_editor.save_current_level()), "Current level save failed")

    dirty_content = {
        asset_package(item)
        for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    }
    dirty_maps = {
        asset_package(item)
        for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    }
    require(not dirty_maps, f"Dirty maps after targeted save: {sorted(dirty_maps)}")
    require(
        all(name.startswith(f"{CONTENT_ROOT}/") for name in dirty_content),
        f"Unexpected dirty content after reimport: {sorted(dirty_content)}",
    )
    if dirty_content:
        require(
            unreal.EditorAssetLibrary.save_directory(
                CONTENT_ROOT, only_if_is_dirty=True, recursive=True
            ),
            "Scoped Passage 5 settle save failed",
        )
    validate_editor_state(require_clean=True)

    output_path = (
        PROJECT_ROOT / "Saved/CodexPassage05/reimport_clean_passage05_v2_result.json"
    )
    output_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "world": world_path,
                "content_root": CONTENT_ROOT,
                "source_root": str(SOURCE_ROOT),
                "mesh_count": len(mesh_records),
                "materialized_pairs": int(
                    actor.get_editor_property("materialized_wing_pair_count")
                ),
                "height_bump_regenerated": False,
                "height_ratio": 0.0,
                "show_rows_changed": repaired_flip_count > 0,
                "image_flips_repaired": repaired_flip_count,
                "show_backup": BACKUP_PATH,
                "meshes": mesh_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    unreal.log(
        "P05_CLEAN_REIMPORT_SUCCESS"
        f"|meshes={len(mesh_records)}|thickness_cm=10|final_height_m=10"
        "|ue_yaw_deg=90|fbx_import_rotation=identity|fbx_import_scale=identity"
        "|triangles_only=1|non_manifold=0|degenerate=0"
        f"|height_bump_regenerated=0|height_ratio=0.0|show_rows_changed={int(repaired_flip_count > 0)}"
        f"|image_flips_repaired={repaired_flip_count}|show_saved=1|backup={BACKUP_PATH}"
        f"|materialized_pairs={actor.get_editor_property('materialized_wing_pair_count')}"
        f"|content_root={CONTENT_ROOT}|level_saved=1|dirty=0"
    )


main()
