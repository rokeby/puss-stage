"""Build LS_Opening_Curtain_Chaos: the Opening cue with the guided-fall Chaos curtain (Unreal Python, MCP route).

Gary, 28 Sep: the curtain does not follow the camera; it stands ~15 m ahead of the opening camera
at (0, 0, 150), the whole proscenium visible, conventionally lit on a dark stage, and "as the
curtain falls, the drama begins".

Why not a subclass of AInfinityStageCurtainRig (the class the old Fire Safety curtain uses): its
constructor calls SetActorEnableCollision(false) (a bare UPROPERTY Blueprint cannot flip, so a floor
box inside it would be dead), it force-shows SM_FireSafetyCurtain_01 whenever active, and the
Interaction-1 automation test counts exactly one rig. With bSequenceOwnsCurtain the rig's
CurtainProgress contract is not read by anything outside the sequence, so plain actors do the job:

- BP_CurtainChaosCloth   one ChaosClothComponent (pinned PLAIN cloth), environment collision on.
                         Its ACTOR transform track is the guided drop: parked at CURTAIN_AT until
                         DROP_START, then carried DROP_CM down (s^2) and FORWARD_CM along DIRECTION
                         (s^1.5) by DROP_START + DROP_FRAMES, then held. The bench mechanism.
- BP_CurtainFloorCatch   a hidden box, top at z = 0, WorldStatic; ignores Pawn, Camera, Visibility
                         and CatFloor. A separate actor, so its collision is live.

The ORIGINAL LS_Opening_Curtain is not touched: this script duplicates it, removes the old binding
in the COPY only, and adds the two spawnables. No Show write, no level write; Show cue 0 keeps
playing the old sequence until this one is proven and Gary says repoint.
"""
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT = "/Game/Scenes/Curtain/Chaos"
SRC_SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain"
DST_SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Chaos"
CLOTH_ASSET = f"{ROOT}/CA_CurtainChaos_Plain_Q15"      # pinned heading (guided fall), plain: "nothing too fancy"
CURTAIN_AT = (0.0, 0.0, 0.0)                           # Gary 28 Sep: fully in front of all the wings, just upstream of station 1 (x=250);
                                                       # at 17.77 m it is wider than the 15 m wing corridor, so it hides every wing behind it
YAW = 90.0                                             # curtain face toward -X (the audience)
DIRECTION = +1.0                                       # Gary: "Upstage" (+X, away from the camera)
# 1.8 m, not the bench 4.5 m: station 1 stands at x = 250 with wings from +-750 outward and the pile is
# +-888 wide, so a longer throw would land the pile edges under those wing flats.
FORWARD_CM, DROP_CM = 180.0, 995.0
DROP_START, DROP_FRAMES = 50, 22                       # 2.0 s hold, then 0.88 s fall at 25 fps
END_FRAME = 375
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "build_opening_chaos_sequence.json")

report = {"errors": []}
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib = unreal.SubobjectDataBlueprintFunctionLibrary
created = []


def finish(ok, message=""):
    report["ok"], report["message"] = ok, message
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    if not ok:
        for asset in created:   # never leave this script's packages dirty in the shared editor
            try:
                eal.save_loaded_asset(asset, only_if_is_dirty=True)
            except Exception:  # noqa: BLE001
                pass
        raise RuntimeError(message)


def dirty_maps():
    return sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if (world.get_path_name().split(".", 1)[0] if world else None) != EXPECTED_WORLD:
    finish(False, "Unexpected editor world")
if editor.get_game_world() is not None:
    finish(False, "PIE/SIE is active")
if [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
    finish(False, "Dirty content packages: someone is mid-change")
cat_floor = getattr(unreal.CollisionChannel, "ECC_CAT_FLOOR", None)
if cat_floor is None:
    finish(False, "CatFloor channel not registered")
report["dirty_maps_before"] = dirty_maps()
if eal.does_asset_exist(DST_SEQ):
    finish(False, f"{DST_SEQ} already exists: not overwriting")
cloth_asset = eal.load_asset(CLOTH_ASSET)
if cloth_asset is None:
    finish(False, f"Missing {CLOTH_ASSET}")


def new_actor_bp(name):
    path = f"{ROOT}/{name}"
    if eal.does_asset_exist(path):
        finish(False, f"{path} already exists: not overwriting")
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    bp = tools.create_asset(name, ROOT, unreal.Blueprint, factory)
    created.append(bp)
    return bp


def add_component(bp, cls, name):
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)
    handle, reason = sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=cls, blueprint_context=bp))
    if not lib.is_handle_valid(handle):
        finish(False, f"Could not add {name} to {bp.get_name()}: {reason}")
    sds.rename_subobject(handle, unreal.Text(name))
    return lib.get_associated_object(lib.get_data(handle))


# --- the cloth actor ---------------------------------------------------------------------------
cloth_bp = new_actor_bp("BP_CurtainChaosCloth")
cloth = add_component(cloth_bp, unreal.ChaosClothComponent, "Curtain")
cloth.set_editor_property("asset", cloth_asset)
cloth.set_editor_property("suspend_simulation", False)
cloth.set_editor_property("collide_with_environment", True)
cloth.set_editor_property("bounds_scale", 2.0)
unreal.BlueprintEditorLibrary.compile_blueprint(cloth_bp)

# --- the floor catch actor ---------------------------------------------------------------------
floor_bp = new_actor_bp("BP_CurtainFloorCatch")
box = add_component(floor_bp, unreal.BoxComponent, "FloorCatch")
box.set_editor_property("box_extent", unreal.Vector(1500.0, 1500.0, 25.0))
box.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -25.0))
box.set_editor_property("hidden_in_game", True)
box.set_editor_property("visible", False)
box.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
box.set_collision_object_type(unreal.CollisionChannel.ECC_WORLD_STATIC)
box.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
for channel in (unreal.CollisionChannel.ECC_PAWN, unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionChannel.ECC_VISIBILITY, cat_floor):
    box.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)
unreal.BlueprintEditorLibrary.compile_blueprint(floor_bp)
report["blueprints"] = [cloth_bp.get_path_name(), floor_bp.get_path_name()]

# --- the sequence: a duplicate; the original stays exactly as it is ----------------------------
seq = eal.duplicate_asset(SRC_SEQ, DST_SEQ)
if seq is None:
    finish(False, "Could not duplicate LS_Opening_Curtain")
created.append(seq)
removed = []
for b in list(seq.get_bindings()):
    removed.append(str(b.get_display_name()))
    b.remove()
report["removed_in_copy"] = removed

T = unreal.MovieSceneTimeUnit.DISPLAY_RATE


def add_spawnable(bp, label):
    binding = seq.add_spawnable_from_class(unreal.BlueprintEditorLibrary.generated_class(bp))
    binding.set_display_name(label)
    spawn_track = binding.find_tracks_by_exact_type(unreal.MovieSceneSpawnTrack)
    spawn_track = spawn_track[0] if spawn_track else binding.add_track(unreal.MovieSceneSpawnTrack)
    sections = spawn_track.get_sections() or [spawn_track.add_section()]
    sections[0].set_range(0, END_FRAME)
    for ch in sections[0].get_all_channels():
        ch.set_default(True)
    return binding


def transform_section(binding):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(0, END_FRAME)
    chans = {str(c.channel_name): c for c in section.get_all_channels()}
    return section, chans


def set_static(chans, location):
    for axis, value in zip(("X", "Y", "Z"), location):
        chans[f"Location.{axis}"].set_default(value)
    chans["Rotation.X"].set_default(0.0)
    chans["Rotation.Y"].set_default(0.0)
    chans["Rotation.Z"].set_default(YAW)
    for axis in ("X", "Y", "Z"):
        chans[f"Scale.{axis}"].set_default(1.0)


# Cloth: parked, then the guided drop keyed per frame (linear between dense keys = the curve itself).
cloth_binding = add_spawnable(cloth_bp, "Chaos Curtain")
_, cc = transform_section(cloth_binding)
set_static(cc, CURTAIN_AT)
lin = unreal.MovieSceneKeyInterpolation.LINEAR
for frame in [0] + list(range(DROP_START, DROP_START + DROP_FRAMES + 1)):
    s = 0.0 if frame <= DROP_START else min(1.0, (frame - DROP_START) / float(DROP_FRAMES))
    x = CURTAIN_AT[0] + DIRECTION * FORWARD_CM * (s ** 1.5)
    z = CURTAIN_AT[2] - DROP_CM * s * s
    cc["Location.X"].add_key(unreal.FrameNumber(frame), x, 0.0, T, lin)
    cc["Location.Z"].add_key(unreal.FrameNumber(frame), z, 0.0, T, lin)
report["drop_keys"] = {"frames": [DROP_START, DROP_START + DROP_FRAMES], "end_location": [CURTAIN_AT[0] + DIRECTION * FORWARD_CM, CURTAIN_AT[1], CURTAIN_AT[2] - DROP_CM]}

# Floor: parked on the same spot for the whole cue.
floor_binding = add_spawnable(floor_bp, "Curtain Floor")
_, fc = transform_section(floor_binding)
set_static(fc, CURTAIN_AT)

# --- save only what this script made, then read it back -----------------------------------------
for asset in created:
    if not eal.save_loaded_asset(asset, only_if_is_dirty=False):
        finish(False, f"Save failed: {asset.get_path_name()}")

readback = []
for b in seq.get_bindings():
    info = {"name": str(b.get_display_name()), "tracks": []}
    for t in b.get_tracks():
        ti = {"class": t.get_class().get_name(), "sections": []}
        for s in t.get_sections():
            chans = {}
            for c in s.get_all_channels():
                keys = c.get_keys()
                chans[str(c.channel_name)] = {"keys": len(keys),
                                              "first_last": [[k.get_time(T).frame_number.value, round(float(k.get_value()), 2)] for k in (keys[:1] + keys[-1:])] if keys else None}
            ti["sections"].append({"range": [s.get_start_frame(), s.get_end_frame()], "channels": chans})
        info["tracks"].append(ti)
    readback.append(info)
report["sequence_readback"] = readback
report["original_bindings"] = [str(b.get_display_name()) for b in eal.load_asset(SRC_SEQ).get_bindings()]
report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
report["dirty_maps_after"] = dirty_maps()
if report["dirty_content_after"]:
    finish(False, f"Content left dirty: {report['dirty_content_after']}")
if report["dirty_maps_after"] != report["dirty_maps_before"]:
    finish(False, f"Level dirty state changed: {report['dirty_maps_before']} -> {report['dirty_maps_after']}")
finish(True)
unreal.log(f"PUSS_SOFTGOODS_OPENING_CHAOS_SUCCESS|bindings={len(readback)}|original={report['original_bindings']}")
