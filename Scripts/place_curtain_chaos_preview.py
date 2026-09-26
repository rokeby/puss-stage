"""Place the Chaos curtain in the level so it can be scrubbed (Unreal Python, via the MCP route).

Needs the conductor's exclusive level slot: it writes the level. Copy into Saved/CodexSoftGoods/
and run "CodexSoftGoods/place_curtain_chaos_preview.py".

- Creates /Game/Scenes/Curtain/Chaos/BP_CurtainChaos if missing: an Actor whose root is a
  ChaosClothComponent holding CA_<STEM>. Flying the curtain = moving this actor; the heading
  is kinematic and follows it.
- Spawns one "CurtainChaos Preview" instance at LOCATION / YAW, in folder Scenes/Curtain.
  Refuses if one already exists (move it by hand, or delete it, rather than stacking copies).
- Saves the Blueprint and the current level only. Refuses to start with any dirty package.

"Simulate In Editor" on the ChaosClothComponent is transient and per instance: tick it in the
Details panel to watch the cloth fall and move it live; it never dirties the level.
"""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
STEM = os.environ.get("CURTAIN_STEM", "CurtainChaos_Ragged_Q15")
ROOT = "/Game/Scenes/Curtain/Chaos"
BP_PATH = f"{ROOT}/BP_CurtainChaos"
LABEL = "CurtainChaos Preview"
LOCATION = unreal.Vector(5400.0, 0.0, 0.0)
YAW = 90.0
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "place_curtain_chaos_preview.json")

report = {}


def dirty_packages():
    return [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
           [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]


def finish(ok, message=""):
    report["ok"] = ok
    report["message"] = message
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    if not ok:
        raise RuntimeError(message)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = world.get_path_name().split(".", 1)[0] if world else None
if world_path != EXPECTED_WORLD:
    finish(False, f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    finish(False, "PIE/SIE is active")
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
# The conductor's offscreen capture (Saved/CodexConductor/capture_probe.py) spawns and destroys
# a transient SceneCapture2D, which leaves the level's dirty flag set with no content change, and
# UE 5.8 Python cannot clear it. This script saves the level anyway, so it may absorb exactly that
# flag: the level is the ONLY dirty package, and no ZZ_TransientCapture actor survives. Anything
# else dirty means someone is mid-change, and we stop.
dirty_content = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
stray_captures = [a.get_actor_label() for a in actors.get_all_level_actors()
                  if "ZZ_TransientCapture" in a.get_actor_label() or "ZZ_TransientCapture" in a.get_name()]
if dirty_content or any(m != EXPECTED_WORLD for m in dirty_maps) or stray_captures:
    finish(False, f"Refusing to start: dirty content {dirty_content}, dirty maps {dirty_maps}, stray captures {stray_captures}")
report["absorbed_capture_map_flag"] = bool(dirty_maps)
if any(a.get_actor_label() == LABEL for a in actors.get_all_level_actors()):
    finish(False, f"'{LABEL}' already exists in the level")

eal = unreal.EditorAssetLibrary
cloth = eal.load_asset(f"{ROOT}/CA_{STEM}")
if cloth is None:
    finish(False, f"Missing {ROOT}/CA_{STEM}; run build_curtain_chaos_asset.py first")

# --- Blueprint --------------------------------------------------------------------------------
bp = eal.load_asset(BP_PATH)
if bp is None:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset("BP_CurtainChaos", ROOT, unreal.Blueprint, factory)
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.ChaosClothComponent, blueprint_context=bp)
    handle, reason = sds.add_new_subobject(params)
    if not unreal.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(handle):
        finish(False, f"Could not add ChaosClothComponent to the Blueprint: {reason}")
    sds.rename_subobject(handle, unreal.Text("Curtain"))
    template = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    template.set_editor_property("asset", cloth)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    report["blueprint"] = "created"
else:
    report["blueprint"] = "existing"

# --- instance ---------------------------------------------------------------------------------
actor = actors.spawn_actor_from_object(bp, LOCATION, unreal.Rotator(roll=0.0, pitch=0.0, yaw=YAW))
if actor is None:
    finish(False, "Spawn failed")
actor.set_actor_label(LABEL)
actor.set_folder_path("Scenes/Curtain")
comps = actor.get_components_by_class(unreal.ChaosClothComponent)
if len(comps) != 1:
    finish(False, f"Expected one ChaosClothComponent on the instance, found {len(comps)}")
asset = comps[0].get_editor_property("asset")
if asset is None or asset.get_path_name() != cloth.get_path_name():
    finish(False, f"Instance component holds {asset}")
origin, extent = actor.get_actor_bounds(False)
report["actor"] = {"path": actor.get_path_name(), "location": [LOCATION.x, LOCATION.y, LOCATION.z], "yaw": YAW,
                   "bounds_origin": [origin.x, origin.y, origin.z], "bounds_extent": [extent.x, extent.y, extent.z],
                   "asset": asset.get_path_name()}

# --- save only the Blueprint and the level ---------------------------------------------------
if not eal.save_loaded_asset(bp, only_if_is_dirty=False):
    finish(False, "Blueprint save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    finish(False, "Level save failed")
report["dirty_after"] = dirty_packages()
if report["dirty_after"]:
    finish(False, f"Still dirty after save: {report['dirty_after']}")
finish(True)
unreal.log(f"PUSS_SOFTGOODS_CURTAIN_PLACED_SUCCESS|actor={actor.get_path_name()}|extent={[round(extent.x), round(extent.y), round(extent.z)]}")
