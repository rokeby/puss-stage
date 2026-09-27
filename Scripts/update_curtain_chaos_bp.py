"""Make BP_CurtainChaos the FALLING curtain (Unreal Python, via the MCP route).

Gary, 26 Sep: the curtain is already down, lit; at the cue it falls to the ground and stays as
a pile. Chaos cannot un-pin at runtime (the kinematic set is baked when the simulation starts),
so the falling cloth has nothing pinned and its component starts SUSPENDED: it holds its
hanging start pose until the cue resumes it (bSuspendSimulation is Sequencer-keyable), then drops
as a whole, the hem lands first and it crumples up from the floor.

This script edits the Blueprint only. It:
- points the ChaosClothComponent at CA_<STEM>_Fall, starts it suspended, and turns on
  environment collision;
- adds a hidden BoxComponent "FloorCatch" (top at z = 0, 30 x 30 m, WorldStatic, ignores
  Pawn/Camera/Visibility) so the pile lands whether or not the stage boards carry collision;
- compiles and saves the Blueprint. It never saves the level. Recompiling reinstances placed
  actors, which can flag the level dirty; the report records the before/after state and whether
  each placed instance picked up the new asset (an instance override would need a level save,
  which is Gary's call).

Refuses to start with dirty content packages. A dirty level flag is recorded, not touched.
"""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
STEM = os.environ.get("CURTAIN_STEM", "CurtainChaos_Ragged_Q15")
ROOT = "/Game/Scenes/Curtain/Chaos"
# The ragged Q15 curtain owns the original BP (placed in the level); other patterns get their own,
# duplicated from it, for Gary to drag in and compare. No level write here either way.
BP_PATH = f"{ROOT}/BP_CurtainChaos" if STEM == "CurtainChaos_Ragged_Q15" else f"{ROOT}/BP_CurtainChaos_{STEM.split('CurtainChaos_')[-1]}"
# "guided" (27 Sep, Gary: "swap to guided"): the pinned-heading asset CA_<STEM>; the fall is staged by
# carrying the cloth component down and forward (Sequencer transform track). "free" = the free-release
# CA_<STEM>_Fall, which cannot sprawl (four benches) and is kept only as a record.
MODE = os.environ.get("CURTAIN_BP_MODE", "guided")
FALL_ASSET = f"{ROOT}/CA_{STEM}" if MODE == "guided" else f"{ROOT}/CA_{STEM}_Fall"
FLOOR_HALF = unreal.Vector(1500.0, 1500.0, 25.0)
# The CatFloor trace channel (ECC_GameTraceChannel1 in Config/DefaultEngine.ini). Python names a
# configured game channel by its display name, so it is ECC_CAT_FLOOR, not ECC_GAME_TRACE_CHANNEL1.
CAT_FLOOR = getattr(unreal.CollisionChannel, "ECC_CAT_FLOOR", None)
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "update_curtain_chaos_bp.json")

report = {}


def finish(ok, message=""):
    report["ok"] = ok
    report["message"] = message
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    if not ok:
        raise RuntimeError(message)


def dirty_maps():
    return [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if (world.get_path_name().split(".", 1)[0] if world else None) != EXPECTED_WORLD:
    finish(False, "Unexpected editor world")
if editor.get_game_world() is not None:
    finish(False, "PIE/SIE is active")
dirty_content = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
if dirty_content:
    finish(False, f"Refusing to start with dirty content packages: {dirty_content}")
report["dirty_maps_before"] = dirty_maps()
if CAT_FLOOR is None:
    finish(False, "CatFloor channel not registered (no ECC_CAT_FLOOR); restart the editor after the config change")

eal = unreal.EditorAssetLibrary
if not eal.does_asset_exist(BP_PATH):
    if eal.duplicate_asset(f"{ROOT}/BP_CurtainChaos", BP_PATH) is None:
        finish(False, f"Could not duplicate BP_CurtainChaos to {BP_PATH}")
    report["bp_duplicated_from"] = f"{ROOT}/BP_CurtainChaos"
bp = eal.load_asset(BP_PATH)
fall = eal.load_asset(FALL_ASSET)
if bp is None or fall is None:
    finish(False, f"Missing {BP_PATH if bp is None else FALL_ASSET}")

sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib = unreal.SubobjectDataBlueprintFunctionLibrary
handles = sds.k2_gather_subobject_data_for_blueprint(bp)
objects = {}
for h in handles:
    obj = lib.get_associated_object(lib.get_data(h))
    if obj is not None:
        objects[obj.get_name()] = (h, obj)
report["components_before"] = sorted(objects)

cloth = next((o for _, o in objects.values() if isinstance(o, unreal.ChaosClothComponent)), None)
if cloth is None:
    finish(False, "BP_CurtainChaos has no ChaosClothComponent")
report["asset_before"] = cloth.get_editor_property("asset").get_path_name() if cloth.get_editor_property("asset") else None
cloth.set_editor_property("asset", fall)
cloth.set_editor_property("suspend_simulation", True)
cloth.set_editor_property("collide_with_environment", True)
# Cheap insurance: environment colliders are gathered from the cloth bounds (reference pose). This did
# NOT fix the lifted-cloth fall-through in the bench; it is kept because the failure without it is silent.
cloth.set_editor_property("bounds_scale", 2.0)

floor = next((o for _, o in objects.values() if isinstance(o, unreal.BoxComponent)), None)
if floor is None:
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.BoxComponent, blueprint_context=bp)
    handle, reason = sds.add_new_subobject(params)
    if not lib.is_handle_valid(handle):
        finish(False, f"Could not add FloorCatch: {reason}")
    sds.rename_subobject(handle, unreal.Text("FloorCatch"))
    floor = lib.get_associated_object(lib.get_data(handle))
    report["floor_catch"] = "created"
else:
    report["floor_catch"] = "existing"
floor.set_editor_property("box_extent", FLOOR_HALF)
floor.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -FLOOR_HALF.z))
floor.set_editor_property("hidden_in_game", True)
floor.set_editor_property("visible", False)
floor.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
floor.set_collision_object_type(unreal.CollisionChannel.ECC_WORLD_STATIC)
floor.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
# CatFloor (ECC_GameTraceChannel1, conductor 26 Sep) is how the cat finds what to stand on. FloorCatch
# is a hidden safety net for the cloth, not a floor, so it must NOT answer the cat's traces: setting
# 'all channels' to Block also sets that slot, so ignore it explicitly. Pile proxies opt in instead.
for channel in (unreal.CollisionChannel.ECC_PAWN, unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionChannel.ECC_VISIBILITY, CAT_FLOOR):
    floor.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
if not eal.save_loaded_asset(bp, only_if_is_dirty=False):
    finish(False, "Blueprint save failed")

# Read back the Blueprint and every placed instance.
report["bp_template"] = {
    "asset": cloth.get_editor_property("asset").get_path_name(),
    "suspend_simulation": cloth.get_editor_property("suspend_simulation"),
    "collide_with_environment": cloth.get_editor_property("collide_with_environment"),
    "floor_extent": [floor.get_editor_property("box_extent").x, floor.get_editor_property("box_extent").y, floor.get_editor_property("box_extent").z],
    "floor_catfloor_response": str(floor.get_collision_response_to_channel(CAT_FLOOR)),
    "floor_worldstatic_response": str(floor.get_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_STATIC)),
}
instances = []
bp_class = unreal.BlueprintEditorLibrary.generated_class(bp)
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_class() == bp_class:
        c = a.get_components_by_class(unreal.ChaosClothComponent)
        asset = c[0].get_editor_property("asset") if c else None
        instances.append({"label": a.get_actor_label(), "asset": asset.get_path_name() if asset else None,
                          "suspend_simulation": c[0].get_editor_property("suspend_simulation") if c else None,
                          "floor_catch": len(a.get_components_by_class(unreal.BoxComponent)),
                          "floor_catfloor_response": [str(bx.get_collision_response_to_channel(CAT_FLOOR))
                                                      for bx in a.get_components_by_class(unreal.BoxComponent)]})
report["instances"] = instances
report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
report["dirty_maps_after"] = dirty_maps()
stale = [i["label"] for i in instances if i["asset"] != fall.get_path_name()]
report["instances_needing_level_save"] = stale
if report["dirty_content_after"]:
    finish(False, f"Content still dirty: {report['dirty_content_after']}")
finish(True)
unreal.log(f"PUSS_SOFTGOODS_CURTAIN_BP_FALL_SUCCESS|instances={len(instances)}|stale={len(stale)}|maps_before={len(report['dirty_maps_before'])}|maps_after={len(report['dirty_maps_after'])}")
