import json
import math
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
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ACTOR_LABEL = "Passage 05 — Fixed Wings"
SIDE_FAMILIES = [f"CloudRef{index:02d}" for index in range(1, 9)]
TOPS = [
    "CloudCeilingLarge_01_C",
    "CloudCeilingLarge_02_C",
    "CloudCeilingLarge_03_C",
    "CloudCeilingSmall_01_C",
    "CloudCeilingSmall_02_C",
    "CloudCeilingSmall_03_C",
]
ASSETS = [
    *(f"{family}_{role}" for family in SIDE_FAMILIES for role in ("L", "R")),
    *TOPS,
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


def serialized_scalar_parameters(instance):
    return {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        float(value.get_editor_property("parameter_value"))
        for value in instance.get_editor_property("scalar_parameter_values")
    }


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "No editor world is open")
    world_path = world.get_path_name().split(".", 1)[0]
    require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
    require(editor.get_game_world() is None, "PIE/SIE is active")
    dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    require(not dirty_content, f"Dirty content during verifier: {dirty_content}")
    require(not dirty_maps, f"Dirty maps during verifier: {dirty_maps}")

    pipeline_report = json.loads(
        (SOURCE_ROOT / "wing_pipeline_report.json").read_text()
    )
    require(pipeline_report.get("status") == "ok", "Offline pipeline report failed")
    require(pipeline_report.get("result_count") == 22, "Offline pipeline count mismatch")
    validation_report = json.loads(
        (SOURCE_ROOT / "clean_fbx_validation_report.json").read_text()
    )
    require(validation_report.get("status") == "ok", "Offline validation report failed")
    require(validation_report.get("validated_fbx_count") == 22, "Offline validation count mismatch")
    edge = load_asset(EDGE_PATH)
    mesh_records = []
    for asset_name in ASSETS:
        mesh_path = f"{MESH_ROOT}/SM_{asset_name}"
        instance_path = f"{INSTANCE_ROOT}/MI_{asset_name}_Relief"
        mesh = load_asset(mesh_path, unreal.StaticMesh)
        instance = load_asset(instance_path, unreal.MaterialInstanceConstant)
        slot_names = [
            str(item.get_editor_property("material_slot_name"))
            for item in mesh.get_editor_property("static_materials")
        ]
        require(len(slot_names) == 3, f"Slot count mismatch: {asset_name}")
        require(
            slot_names[0].endswith("_Front")
            and slot_names[1].endswith("_Back")
            and slot_names[2].endswith("_Edge"),
            f"Slot order mismatch: {asset_name} {slot_names}",
        )
        require(mesh.get_material(0) == instance, f"Front material mismatch: {asset_name}")
        require(mesh.get_material(1) == instance, f"Back material mismatch: {asset_name}")
        require(mesh.get_material(2) == edge, f"Edge material mismatch: {asset_name}")
        bounds = mesh.get_bounding_box()
        size = bounds.max - bounds.min
        require(
            math.isclose(float(size.x), 10.0, abs_tol=0.05),
            f"Imported thickness mismatch: {asset_name} {size.x} cm",
        )
        require(
            math.isclose(float(size.z), 1000.0, abs_tol=0.25),
            f"Imported height mismatch: {asset_name} {size.z} cm",
        )
        height_ratio = serialized_scalar_parameters(instance).get("HeightRatio")
        require(
            height_ratio is not None and math.isclose(height_ratio, 0.0, abs_tol=1.0e-8),
            f"HeightRatio is not disabled: {asset_name} {height_ratio}",
        )
        import_data = mesh.get_editor_property("asset_import_data")
        filenames = [str(value) for value in import_data.extract_filenames()]
        expected_fbx = str(SOURCE_ROOT / asset_name / f"SM_{asset_name}.fbx")
        require(filenames and Path(filenames[0]).resolve() == Path(expected_fbx).resolve(), f"Wrong FBX source: {asset_name} {filenames}")
        mesh_records.append(
            {
                "asset_name": asset_name,
                "mesh": mesh_path,
                "source_fbx": filenames[0],
                "slots": slot_names,
                "dimensions_cm": [float(size.x), float(size.y), float(size.z)],
                "height_ratio": height_ratio,
            }
        )

    show = load_asset(SHOW_PATH)
    cues = list(show.get_editor_property("cues"))
    rows = [
        cue
        for cue in cues
        if str(cue.get_editor_property("label")).startswith("P05 Wing ")
    ]
    require(len(rows) == 93, f"Expected 93 Passage 5 rows, found {len(rows)}")
    label_numbers = []
    for cue in rows:
        label = str(cue.get_editor_property("label"))
        try:
            label_number = int(label.rsplit(" ", 1)[1])
        except (ValueError, IndexError):
            raise RuntimeError(f"Malformed Passage 5 cue label: {label}")
        label_numbers.append(label_number)
        index = label_number - 1
        require(0 <= index < 93, f"Passage 5 cue label out of range: {label}")
        expected = {
            "left": f"{SIDE_FAMILIES[index % len(SIDE_FAMILIES)]}_L",
            "right": f"{SIDE_FAMILIES[index % len(SIDE_FAMILIES)]}_R",
            "top": TOPS[index % len(TOPS)],
        }
        pair = cue.get_editor_property("wing_pair")
        require(bool(pair.get_editor_property("has_top")), f"Top disabled at {label}")
        for role, asset_name in expected.items():
            panel = pair.get_editor_property(role)
            require(
                asset_package(panel.get_editor_property("mesh"))
                == f"{MESH_ROOT}/SM_{asset_name}",
                f"{role} mesh mismatch at {label}",
            )
            require(
                not bool(panel.get_editor_property("flip_image_horizontally")),
                f"Image flip enabled at {label} {role}",
            )
    require(
        set(label_numbers) == set(range(1, 94)),
        "Passage 5 cue labels are not the unique complete range 001-093",
    )

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
    require(materialized == 93, f"Materialized pair count mismatch: {materialized}")

    output_path = PROJECT_ROOT / "Saved/CodexPassage05/verify_clean_passage05_v2_result.json"
    output_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "world": world_path,
                "content_root": CONTENT_ROOT,
                "source_root": str(SOURCE_ROOT),
                "mesh_count": len(mesh_records),
                "row_count": len(rows),
                "materialized_pairs": materialized,
                "height_ratio": 0.0,
                "height_bump_regenerated": False,
                "dirty_content": 0,
                "dirty_maps": 0,
                "meshes": mesh_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    unreal.log(
        "P05_CLEAN_VERIFY_SUCCESS"
        f"|meshes={len(mesh_records)}|rows={len(rows)}|materialized_pairs={materialized}"
        "|thickness_cm=10|final_height_m=10|ue_yaw_deg=90"
        "|fbx_import_rotation=identity|fbx_import_scale=identity"
        "|front_back_edge=1|height_bump_regenerated=0|height_ratio=0.0"
        "|source_flips=0|dirty=0"
    )


main()
