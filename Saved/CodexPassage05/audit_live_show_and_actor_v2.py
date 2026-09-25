import json
import math
from collections import Counter
from pathlib import Path

import unreal


PROJECT_ROOT = Path("/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage")
SOURCE_ROOT = PROJECT_ROOT / "DerivedAssets/Passage05BirdToMountainBatch/GeneratedWingsV2_Clean"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CONTENT_ROOT = "/Game/Wings/Passage05_BirdToMountain"
MESH_ROOT = f"{CONTENT_ROOT}/StaticMeshes"
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


def package_names(values):
    return [asset_package(value) for value in values]


def scale_payload(value):
    return [float(value.x), float(value.y), float(value.z)]


def top_scale_is_target(value):
    return (
        math.isclose(float(value.x), 1.0, abs_tol=1.0e-6)
        and math.isclose(float(value.y), 0.2, abs_tol=1.0e-6)
        and math.isclose(float(value.z), 0.2, abs_tol=1.0e-6)
    )


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "No editor world is open")
    world_path = world.get_path_name().split(".", 1)[0]
    require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
    require(editor.get_game_world() is None, "PIE/SIE is active")
    dirty_content = package_names(
        unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    )
    dirty_maps = package_names(
        unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    )

    mesh_records = {}
    for asset_name in ASSETS:
        mesh_path = f"{MESH_ROOT}/SM_{asset_name}"
        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
        require(isinstance(mesh, unreal.StaticMesh), f"Static Mesh did not load: {mesh_path}")
        filenames = [
            str(value)
            for value in mesh.get_editor_property("asset_import_data").extract_filenames()
        ]
        expected_fbx = SOURCE_ROOT / asset_name / f"SM_{asset_name}.fbx"
        source_is_clean = bool(
            filenames and Path(filenames[0]).resolve() == expected_fbx.resolve()
        )
        require(source_is_clean, f"Mesh source is not clean: {asset_name} {filenames}")
        box = mesh.get_bounding_box()
        size = box.max - box.min
        require(math.isclose(float(size.x), 10.0, abs_tol=0.05), f"Bad thickness: {asset_name}")
        require(math.isclose(float(size.z), 1000.0, abs_tol=0.25), f"Bad height: {asset_name}")
        mesh_records[mesh_path] = {
            "asset_name": asset_name,
            "source_fbx": filenames[0],
            "source_is_clean": source_is_clean,
            "dimensions_cm": [float(size.x), float(size.y), float(size.z)],
        }

    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    require(show is not None, "Show Asset did not load")
    show_distribution = Counter()
    show_rows = []
    labels = []
    for cue in list(show.get_editor_property("cues")):
        label = str(cue.get_editor_property("label"))
        if not label.startswith("P05 Wing "):
            continue
        label_number = int(label.rsplit(" ", 1)[1])
        labels.append(label_number)
        source_index = label_number - 1
        expected = {
            "left": f"{MESH_ROOT}/SM_{SIDE_FAMILIES[source_index % len(SIDE_FAMILIES)]}_L",
            "right": f"{MESH_ROOT}/SM_{SIDE_FAMILIES[source_index % len(SIDE_FAMILIES)]}_R",
            "top": f"{MESH_ROOT}/SM_{TOPS[source_index % len(TOPS)]}",
        }
        pair = cue.get_editor_property("wing_pair")
        require(bool(pair.get_editor_property("has_top")), f"Top disabled at {label}")
        row = {"label": label}
        for role in ("left", "right", "top"):
            panel = pair.get_editor_property(role)
            mesh_path = asset_package(panel.get_editor_property("mesh"))
            require(mesh_path == expected[role], f"Show {role} mismatch at {label}")
            require(mesh_path in mesh_records, f"Show uses unapproved mesh: {mesh_path}")
            require(
                not bool(panel.get_editor_property("flip_image_horizontally")),
                f"Show image flip enabled at {label} {role}",
            )
            show_distribution[mesh_path] += 1
            row[role] = mesh_path
            if role == "top":
                scale = panel.get_editor_property("local_transform").get_editor_property("scale3d")
                require(top_scale_is_target(scale), f"Show top scale mismatch at {label}: {scale}")
                row["top_scale"] = scale_payload(scale)
        show_rows.append(row)
    require(len(show_rows) == 93, f"Expected 93 Show rows, found {len(show_rows)}")
    require(set(labels) == set(range(1, 94)), "Passage 5 labels are incomplete")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    matches = [
        actor
        for actor in actors
        if actor.get_class().get_name() == "InfinityStagePassageActor"
        and actor.get_actor_label() == ACTOR_LABEL
        and actor.get_editor_property("show_asset") == show
    ]
    require(len(matches) == 1, f"Expected one Passage 5 actor, found {len(matches)}")
    actor = matches[0]
    require(
        int(actor.get_editor_property("materialized_wing_pair_count")) == 93,
        "Actor materialized pair count mismatch",
    )

    managed_components = list(actor.get_editor_property("managed_components"))
    actor_distribution = Counter()
    component_records = []
    for component in managed_components:
        mesh_path = asset_package(component.get_editor_property("static_mesh"))
        require(mesh_path in mesh_records, f"Actor component uses unapproved mesh: {mesh_path}")
        instance_count = int(component.get_instance_count())
        actor_distribution[mesh_path] += instance_count
        component_records.append(
            {
                "component": component.get_name(),
                "mesh": mesh_path,
                "instances": instance_count,
                "source_fbx": mesh_records[mesh_path]["source_fbx"],
            }
        )
    require(
        actor_distribution == show_distribution,
        f"Actor instance distribution differs from Show: actor={actor_distribution} show={show_distribution}",
    )

    materialized_panels = list(actor.get_editor_property("materialized_panels"))
    require(len(materialized_panels) == 279, f"Expected 279 materialized panels, found {len(materialized_panels)}")
    top_ref_count = 0
    top_ref_scales = []
    for ref in materialized_panels:
        side = str(ref.get_editor_property("side"))
        component = ref.get_editor_property("component")
        require(component is not None, "Materialized panel has no component")
        mesh_path = asset_package(component.get_editor_property("static_mesh"))
        require(mesh_path in mesh_records, f"Materialized panel uses unapproved mesh: {mesh_path}")
        if "TOP" in side.upper():
            top_ref_count += 1
            scale = ref.get_editor_property("base_world_transform").get_editor_property("scale3d")
            require(top_scale_is_target(scale), f"Actor top instance scale mismatch: {scale}")
            top_ref_scales.append(scale_payload(scale))
    require(top_ref_count == 93, f"Expected 93 actor top refs, found {top_ref_count}")

    output = PROJECT_ROOT / "Saved/CodexPassage05/audit_live_show_and_actor_v2_result.json"
    output.write_text(
        json.dumps(
            {
                "status": "ok",
                "world": world_path,
                "show_asset": SHOW_PATH,
                "content_root": CONTENT_ROOT,
                "source_root": str(SOURCE_ROOT),
                "show_rows": len(show_rows),
                "materialized_pairs": 93,
                "materialized_panels": len(materialized_panels),
                "managed_components": len(managed_components),
                "top_ref_count": top_ref_count,
                "top_scale": [1.0, 0.2, 0.2],
                "show_distribution": dict(sorted(show_distribution.items())),
                "actor_distribution": dict(sorted(actor_distribution.items())),
                "components": component_records,
                "meshes": mesh_records,
                "dirty_content": dirty_content,
                "dirty_maps": dirty_maps,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    unreal.log(
        "P05_LIVE_SHOW_ACTOR_AUDIT_SUCCESS"
        f"|show_rows={len(show_rows)}|materialized_pairs=93"
        f"|materialized_panels={len(materialized_panels)}|managed_components={len(managed_components)}"
        f"|clean_meshes={len(mesh_records)}|actor_matches_show=1|top_scale=1,0.2,0.2"
        f"|dirty_content={len(dirty_content)}|dirty_maps={len(dirty_maps)}"
    )


main()
