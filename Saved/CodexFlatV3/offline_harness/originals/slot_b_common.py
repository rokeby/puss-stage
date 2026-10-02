"""Shared guarded helpers for Flat V3 Slot B (P04 swap)."""
import json
import math
import os
import unreal

RUN = "FV3B-20261002-03"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
BACKUP = "E:/PussStage/Backups/PreFlatV3SwapP04-20261002-0242"
BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexFlatV3"))
SAVED_ROOTS = [SHOW, WORLD]

LEFT_POOL = [
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_coventry_ruin_L_v1",
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_coventry_ruin_L_v2",
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_coventry_interior_L_v1",
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_ruined_gallery_L_v1",
]
RIGHT_POOL = [
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_coventry_ruin_R_v1",
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_ruined_gallery_R_v1",
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_ruined_gallery_R_v2",
    "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_ruined_gallery_R_v3",
]


def census():
    def names(packages):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in packages)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def assert_context(clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actual = world.get_outermost().get_name() if world else None
    if actual != WORLD:
        raise RuntimeError("WRONG_WORLD|expected=%s|actual=%s" % (WORLD, actual))
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_ACTIVE")
    current = census()
    if clean and current != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AT_SLOT_START|census=" + json.dumps(current, sort_keys=True))
    return editor, world


def asset_path(value):
    return None if value is None else str(value.get_path_name()).split(".", 1)[0]


def transform_plain(value):
    rotation = value.rotation.rotator()
    return {
        "location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


def transform_from_plain(value):
    return unreal.Transform(
        location=unreal.Vector(*value["location"]),
        rotation=unreal.Rotator(
            roll=value["rotation"][0], pitch=value["rotation"][1], yaw=value["rotation"][2]),
        scale=unreal.Vector(*value["scale"]))


def panel_plain(panel):
    return {
        "mesh": asset_path(panel.get_editor_property("mesh")),
        "material_overrides": [asset_path(value) for value in panel.get_editor_property("material_overrides")],
        "local_transform": transform_plain(panel.get_editor_property("local_transform")),
        "facing_policy": str(panel.get_editor_property("facing_policy")),
        "flip_image_horizontally": bool(panel.get_editor_property("flip_image_horizontally")),
    }


def frame_value(value):
    return int(value.value) if hasattr(value, "value") else int(value)


def mechanism_plain(mechanism):
    return {
        "kind": str(mechanism.get_editor_property("kind")),
        "playback_mode": str(mechanism.get_editor_property("playback_mode")),
        "phase_origin": str(mechanism.get_editor_property("phase_origin")),
        "explicit_origin_frame": frame_value(mechanism.get_editor_property("explicit_origin_frame")),
        "cycle_rate_hz": float(mechanism.get_editor_property("cycle_rate_hz")),
        "phase_offset_cycles": float(mechanism.get_editor_property("phase_offset_cycles")),
        "inward_travel_cm": float(mechanism.get_editor_property("inward_travel_cm")),
    }


def close_transform(actual, expected, tolerance=0.001):
    return all(abs(float(a) - float(b)) <= tolerance
               for key in ("location", "rotation", "scale")
               for a, b in zip(actual[key], expected[key]))


def write_json(name, value):
    path = os.path.join(BASE, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_json(name):
    with open(os.path.join(BASE, name), encoding="utf-8") as handle:
        return json.load(handle)


def p04_actor(show):
    matches = [actor for actor in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors()
        if actor.get_class().get_name() == "InfinityStagePassageActor"
        and actor.get_actor_label().startswith("Passage 04")
        and actor.get_editor_property("show_asset") == show]
    if len(matches) != 1:
        raise RuntimeError("P04_ACTOR_COUNT|actual=%d" % len(matches))
    return matches[0]


def set_panel(panel, record):
    mesh = unreal.EditorAssetLibrary.load_asset(record["mesh"])
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("MESH_LOAD_FAIL|path=" + str(record["mesh"]))
    overrides = [unreal.EditorAssetLibrary.load_asset(path)
                 for path in record["material_overrides"]]
    if any(value is None for value in overrides):
        raise RuntimeError("MATERIAL_OVERRIDE_LOAD_FAIL")
    policies = {
        "AUTO_BY_ROLE": unreal.InfinityPanelFacingPolicy.AUTO_BY_ROLE,
        "PRESERVE_ASSET": unreal.InfinityPanelFacingPolicy.PRESERVE_ASSET,
        "ROTATE180_AROUND_UP": unreal.InfinityPanelFacingPolicy.ROTATE180_AROUND_UP,
    }
    policy = next((value for key, value in policies.items()
                   if key in record["facing_policy"]), None)
    if policy is None:
        raise RuntimeError("UNKNOWN_FACING_POLICY|" + record["facing_policy"])
    panel.set_editor_property("mesh", mesh)
    panel.set_editor_property("material_overrides", overrides)
    panel.set_editor_property("local_transform", transform_from_plain(record["local_transform"]))
    panel.set_editor_property("facing_policy", policy)
    panel.set_editor_property("flip_image_horizontally", bool(record["flip_image_horizontally"]))
    return panel


def log_release(status, saved_roots, reason=None):
    roots = sorted(set(saved_roots))
    current = census()
    if reason is not None:
        report_path = os.path.join(BASE, "REPORT_%s.md" % RUN)
        lines = [
            "# Flat V3 Slot B Report - %s" % RUN,
            "",
            "Final status: **FAIL**.",
            "",
            "- **measured:** The guarded slot stopped with `%s`." % str(reason).replace("`", "'"),
            "- **measured:** Saved roots recorded by this slot: `%s`." % json.dumps(roots),
            "- **measured:** Release census: `content=%s`, `maps=%s`." %
            (json.dumps(current["content"]), json.dumps(current["maps"])),
            "- **inferred:** No visual or artistic acceptance is claimed for a failed slot.",
            "",
            "Backup target: `%s`" % BACKUP,
        ]
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        unreal.log_error("FLATV3_B_FAIL run=%s reason=%s census=%s" %
                         (RUN, str(reason).replace("\n", "\\n"),
                          json.dumps(current, separators=(",", ":"), sort_keys=True)))
    unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
               (RUN, status, len(roots), json.dumps(roots, separators=(",", ":")),
                json.dumps(current, separators=(",", ":"), sort_keys=True)))


def log_has(marker):
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_log_dir()), "PussStage.log")
    with open(path, encoding="utf-8", errors="replace") as handle:
        return marker in handle.read()

