"""In-situ settle test: does the Opening curtain gain folds once it actually simulates?

Spawns a transient BP_CurtainChaosCloth + BP_CurtainFloorCatch at the Opening spot (0, 0, 0) yaw 90
and a capture at the chosen framing ((-1400, 0, 150), pitch +14, 15 mm = 76.8 deg hfov). Captures the
UNSIMULATED pose, then the same frame as the pinned cloth hangs and settles, and measures fold contrast
on horizontal slices through the cloth body. Show lighting only. Cleans up all transients.
"""
import json
import os

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", "opening_settle")
LOG = os.path.join(SAVED, "CodexSoftGoods", "opening_settle_probe.json")
CAPTURE_AT = [0, 30, 60, 120, 180]
ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    raise RuntimeError("wrong world")
if [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
    raise RuntimeError("dirty content: refusing")
actors = ss.get_all_level_actors()
if any(a.get_actor_label().startswith("ZZ_") for a in actors):
    raise RuntimeError("ZZ_ actors already present")
near = [a.get_actor_label() for a in actors if a.get_components_by_class(unreal.ChaosClothComponent)
        and abs(a.get_actor_location().x) < 500 and abs(a.get_actor_location().y) < 500]
if near:
    raise RuntimeError(f"a cloth already stands at the Opening spot (Sequencer spawnable?): {near}")

os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))
report = {"errors": [], "captures": []}
temps = []
cloth_actor = ss.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainChaosCloth"),
                                        unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
cloth_actor.set_actor_label("ZZ_TEMP_SoftGoods_OpeningCloth")
temps.append(cloth_actor)
floor_actor = ss.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainFloorCatch"),
                                        unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
floor_actor.set_actor_label("ZZ_TEMP_SoftGoods_OpeningFloor")
temps.append(floor_actor)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
cam = ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(-1400.0, 0.0, 150.0), unreal.Rotator(roll=0.0, pitch=14.0, yaw=0.0))
cam.set_actor_label("ZZ_TransientCapture_SoftGoods_Opening")
temps.append(cam)
cc = cam.capture_component2d
cc.set_editor_property("texture_target", rt)
cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
cc.set_editor_property("fov_angle", 76.8)
cc.set_editor_property("capture_every_frame", False)
cc.set_editor_property("capture_on_movement", False)
cloth = cloth_actor.get_components_by_class(unreal.ChaosClothComponent)[0]
report["cloth_asset"] = cloth.get_editor_property("asset").get_path_name()

state = {"n": 0, "handle": None, "started": False, "waits": 0}


def capture(tag):
    cc.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"{tag}.png")
    report["captures"].append(tag)


def cleanup():
    if state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    try:
        cloth.set_simulate_in_editor(False)
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"sie {exc}")
    for a in temps:
        try:
            ss.destroy_actor(a)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(f"destroy {exc}")
    report["stray_after"] = [a.get_actor_label() for a in ss.get_all_level_actors() if a.get_actor_label().startswith("ZZ_")]
    report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    report["dirty_maps_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_OPENING_SETTLE_DONE|captures={len(report['captures'])}|stray={len(report['stray_after'])}")


def tick(delta):
    try:
        if not state["started"]:
            # First, the pose the conductor's scrubbed capture shows: never simulated.
            capture("t0000_unsimulated")
            cloth.set_simulate_in_editor(True)
            cloth.set_editor_property("suspend_simulation", False)
            state["started"] = True
            return
        state["n"] += 1
        if state["n"] in CAPTURE_AT:
            capture(f"t{state['n']:04d}_simulated")
        if state["n"] >= max(CAPTURE_AT):
            cleanup()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        cleanup()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("PUSS_SOFTGOODS_OPENING_SETTLE_STARTED")
