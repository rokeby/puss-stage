import json
import traceback

import unreal


CORE_ASSETS = [
    ("rock_a", "/Game/Rock_Pack/Mesh/SM_Rock_A", "StaticMesh", True),
    ("rock_l", "/Game/Rock_Pack/Mesh/SM_Rock_L", "StaticMesh", True),
    ("background_bird_mesh", "/Game/BackgroundBirds/SM_Bird", "StaticMesh", True),
    ("background_bird_directional", "/Game/BackgroundBirds/NS_Birds_Directional", "NiagaraSystem", False),
    ("background_bird_directional_burst", "/Game/BackgroundBirds/NS_Birds_Directional_Burst", "NiagaraSystem", False),
    ("background_bird_swarm", "/Game/BackgroundBirds/NS_Birds_Swarm", "NiagaraSystem", False),
    ("background_bird_swarm_close", "/Game/BackgroundBirds/NS_Birds_Swarm_Close", "NiagaraSystem", False),
    ("background_bird_v", "/Game/BackgroundBirds/NS_Birds_V", "NiagaraSystem", False),
    ("background_bird_spline", "/Game/BackgroundBirds/NS_Bird_Spline", "NiagaraSystem", False),
    ("background_bird_spline_figure_eight", "/Game/BackgroundBirds/NS_Bird_Spline_FigureEight", "NiagaraSystem", False),
    ("honeybee_mesh", "/Game/Animalia/HoneyBee/Meshes/Honeybee", "SkeletalMesh", True),
    ("honeybee_fly", "/Game/Animalia/HoneyBee/Animations/Fly", "AnimSequence", False),
    ("crow_mesh", "/Game/Birds/Crow/Meshes/SK_Crow", "SkeletalMesh", True),
    ("pigeon_mesh", "/Game/Birds/Pigeon/Meshes/Pigeon", "SkeletalMesh", True),
    ("seagull_mesh", "/Game/Birds/Seagull/Meshes/SK_Seagull", "SkeletalMesh", True),
    ("crow_npc", "/Game/Birds/Crow/Blueprints/BP_NPC_Crow", "Blueprint", False),
    ("pigeon_npc", "/Game/Birds/Pigeon/Blueprint/BP_NPC_Pigeon", "Blueprint", False),
    ("seagull_npc", "/Game/Birds/Seagull/Blueprints/BP_NPC_Seagull", "Blueprint", False),
]

OPTIONAL_ASSETS = [
    ("azure_mountain", "/Game/AzureHillside/Meshes/SM_Mountain", "StaticMesh", True),
]


def material_slots(asset):
    if isinstance(asset, unreal.StaticMesh):
        slots = asset.get_editor_property("static_materials")
    elif isinstance(asset, unreal.SkeletalMesh):
        slots = asset.get_editor_property("materials")
    else:
        return {"slot_count": 0, "materials": [], "missing_material_slots": []}

    materials = []
    missing = []
    for index, slot in enumerate(slots):
        material = slot.get_editor_property("material_interface")
        if material is None:
            materials.append(None)
            missing.append(index)
        else:
            materials.append(material.get_path_name())
    return {
        "slot_count": len(slots),
        "materials": materials,
        "missing_material_slots": missing,
    }


def inspect_asset(name, path, expected_class, require_materials):
    result = {
        "name": name,
        "path": path,
        "expected_class": expected_class,
        "loaded": False,
        "usable": False,
    }
    asset = unreal.load_asset(path)
    if asset is None:
        result["error"] = "load returned None"
        return result

    result["loaded"] = True
    result["class"] = asset.get_class().get_name()
    result.update(material_slots(asset))

    class_ok = result["class"] == expected_class
    materials_ok = True
    if require_materials:
        materials_ok = result["slot_count"] > 0 and not result["missing_material_slots"]
    result["usable"] = class_ok and materials_ok
    if not class_ok:
        result["error"] = "unexpected class"
    elif not materials_ok:
        result["error"] = "missing material assignment"
    return result


try:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    roots = ["/Game/Rock_Pack", "/Game/BackgroundBirds", "/Game/Animalia", "/Game/Birds", "/Game/AzureHillside"]
    registry.scan_paths_synchronous(roots, force_rescan=True)

    root_counts = {
        root: len(registry.get_assets_by_path(root, recursive=True))
        for root in roots
    }
    core = [inspect_asset(*entry) for entry in CORE_ASSETS]
    optional = [inspect_asset(*entry) for entry in OPTIONAL_ASSETS]
    failures = [entry for entry in core if not entry["usable"]]

    details = {
        "root_counts": root_counts,
        "core": core,
        "optional": optional,
    }
    if failures:
        raise RuntimeError("core asset verification failures: " + json.dumps(failures, sort_keys=True))

    optional_usable = sum(1 for entry in optional if entry["usable"])
    unreal.log(
        "ASSET_REVIEW_IMPORT_VERIFY_SUCCESS"
        f"|core={len(core)}"
        f"|optional_usable={optional_usable}"
        f"|rock_assets={root_counts['/Game/Rock_Pack']}"
        f"|bird_assets={root_counts['/Game/Birds']}"
        f"|background_bird_assets={root_counts['/Game/BackgroundBirds']}"
        f"|bee_assets={root_counts['/Game/Animalia']}"
    )
    unreal.log("ASSET_REVIEW_IMPORT_DETAILS|" + json.dumps(details, sort_keys=True))
except Exception:
    unreal.log_error("ASSET_REVIEW_IMPORT_VERIFY_FAILED|" + traceback.format_exc().replace("\n", " | "))
    raise
