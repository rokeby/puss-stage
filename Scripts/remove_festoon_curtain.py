"""Retire the rejected festoon curtain (Unreal Python, via the MCP route). Needs Gary's go and the level slot.

The festoon Geometry Cache (/Game/Scenes/Curtain/Cloth/GC_CurtainCloth_Festoon_V1, the swag bake
Gary rejected on 21 Sep) and its preview actor "CurtainCloth Preview" at x = 4400 kept being
mistaken for the live curtain. This script:

1. checks the world, that no content package is dirty, and that the level is dirty at most by
   the conductor's net-nil capture flag (no ZZ_TransientCapture actor survives);
2. checks that exactly one actor uses the cache and that it is the expected GeometryCacheActor;
3. destroys that actor and saves the level (only the level);
4. deletes the cache asset ONLY if the asset registry then reports no referencers; otherwise it
   leaves the asset and reports what still refers to it.

Take a Backups/PreFestoonRemoval-<ts> snapshot (the .umap and the cache .uasset) first.
The fly bake on disk (DerivedAssets/CurtainCloth/CurtainCloth_Fly_V1.abc) is untouched.
"""

import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GC = "/Game/Scenes/Curtain/Cloth/GC_CurtainCloth_Festoon_V1"
LABEL = "CurtainCloth Preview"
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "remove_festoon_curtain.json")
report = {}


def finish(ok, message=""):
    report["ok"], report["message"] = ok, message
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    if not ok:
        raise RuntimeError(message)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if (world.get_path_name().split(".", 1)[0] if world else None) != EXPECTED_WORLD:
    finish(False, "Unexpected editor world")
if editor.get_game_world() is not None:
    finish(False, "PIE/SIE is active")
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
dirty_content = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
stray = [a.get_actor_label() for a in actors if "ZZ_TransientCapture" in a.get_actor_label() or "ZZ_TransientCapture" in a.get_name()]
if dirty_content or any(m != EXPECTED_WORLD for m in dirty_maps) or stray:
    finish(False, f"Refusing: dirty content {dirty_content}, dirty maps {dirty_maps}, stray captures {stray}")
report["absorbed_capture_map_flag"] = bool(dirty_maps)

users = []
for a in actors:
    for c in a.get_components_by_class(unreal.GeometryCacheComponent):
        cache = c.get_editor_property("geometry_cache")
        if cache and cache.get_path_name().split(".")[0] == GC:
            users.append(a)
report["users"] = [(a.get_actor_label(), a.get_name(), a.get_class().get_name()) for a in users]
if len(users) != 1 or users[0].get_actor_label() != LABEL or not isinstance(users[0], unreal.GeometryCacheActor):
    finish(False, f"Expected exactly one GeometryCacheActor '{LABEL}' using the cache, found {report['users']}")

if not subsystem.destroy_actor(users[0]):
    finish(False, "destroy_actor failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    finish(False, "Level save failed")
report["actor_removed"] = LABEL

referencers = [str(p) for p in unreal.EditorAssetLibrary.find_package_referencers_for_asset(GC, False)]
report["referencers_after_actor_removal"] = referencers
if referencers:
    report["asset"] = "kept: still referenced"
else:
    report["asset"] = "deleted" if unreal.EditorAssetLibrary.delete_asset(GC) else "delete failed"
report["asset_exists_after"] = unreal.EditorAssetLibrary.does_asset_exist(GC)
report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
report["dirty_maps_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if report["dirty_content_after"] or report["dirty_maps_after"]:
    finish(False, f"Left dirty: {report['dirty_content_after']} {report['dirty_maps_after']}")
finish(True)
unreal.log(f"PUSS_SOFTGOODS_FESTOON_REMOVED_SUCCESS|asset={report['asset']}|dirty=0/0")
