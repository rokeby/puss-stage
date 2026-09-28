"""Automated pin check for the pinned Chaos curtains (Unreal Python, MCP route). A build does not ship until it PASSES.

Why: Chaos re-sorts cloth sim vertices, so a heading pin can read back correctly on the imported mesh
and still hold the wrong particles; only a running sim shows it (28 Sep: two days of benches on a
curtain hanging from its left edge). This hangs each pinned curtain OFF-STAGE (y >= 60000) under its
OWN lamp (the bench site is unlit), captures t0 and after HANG_TICKS of simulation, and writes the
frames. Scripts/curtain_pin_check_score.py then measures top-edge flatness and writes PASS/FAIL.

Transient only: ZZ_TEMP_SoftGoods_PinCheck_* actors, lamps and cameras, all destroyed at the end.
Announce before running (it is level activity). Refuses if any ZZ_ actor or dirty content exists.
"""
import json
import os

import unreal

CURTAINS = {
    "plain": "/Game/Scenes/Curtain/Chaos/CA_CurtainChaos_Plain_Q15",
    "ragged": "/Game/Scenes/Curtain/Chaos/CA_CurtainChaos_Ragged_Q15",
}
HANG_TICKS = 120
CAPTURE_AT = [0, 60, HANG_TICKS]
SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", "pin_check")
LOG = os.path.join(SAVED, "CodexSoftGoods", "curtain_pin_check.json")

ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    raise RuntimeError("wrong world")
if [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
    raise RuntimeError("dirty content: refusing")
if any(a.get_actor_label().startswith("ZZ_") for a in ss.get_all_level_actors()):
    raise RuntimeError("ZZ_ actors already present")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

report = {"errors": [], "captures": [], "curtains": CURTAINS, "hang_ticks": HANG_TICKS}
temps, runs = [], []
bp = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainChaosCloth")
for i, (tag, path) in enumerate(CURTAINS.items()):
    base = unreal.Vector(5400.0, 66000.0 + i * 3500.0, 0.0)
    act = ss.spawn_actor_from_class(bp, base, unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
    act.set_actor_label(f"ZZ_TEMP_SoftGoods_PinCheck_{tag}")
    temps.append(act)
    cloth = act.get_components_by_class(unreal.ChaosClothComponent)[0]
    cloth.set_asset(unreal.EditorAssetLibrary.load_asset(path))
    cloth.set_editor_property("suspend_simulation", False)
    lamp = ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(base.x - 1600.0, base.y, 1400.0),
                                     unreal.Rotator(roll=0.0, pitch=-28.0, yaw=0.0))
    lamp.set_actor_label(f"ZZ_TEMP_SoftGoods_PinCheck_Lamp_{tag}")
    temps.append(lamp)
    lc = lamp.spot_light_component
    lc.set_editor_property("intensity", 30000.0)
    lc.set_editor_property("attenuation_radius", 8000.0)
    lc.set_editor_property("outer_cone_angle", 60.0)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 640, 360, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cam = ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(base.x - 2400.0, base.y, 600.0),
                                    unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    cam.set_actor_label(f"ZZ_TransientCapture_SoftGoods_PinCheck_{tag}")
    temps.append(cam)
    cc = cam.capture_component2d
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    cc.set_editor_property("fov_angle", 70.0)
    cc.set_editor_property("capture_every_frame", False)
    cloth.set_simulate_in_editor(True)
    runs.append({"tag": tag, "cloth": cloth, "cc": cc, "rt": rt})

state = {"n": 0, "handle": None}


def cleanup():
    if state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    for r in runs:
        try:
            r["cloth"].set_simulate_in_editor(False)
        except Exception:  # noqa: BLE001
            pass
    for a in temps:
        try:
            ss.destroy_actor(a)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(str(exc))
    report["stray_after"] = [a.get_actor_label() for a in ss.get_all_level_actors() if a.get_actor_label().startswith("ZZ_")]
    report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_PIN_CHECK_CAPTURED|captures={len(report['captures'])}|stray={len(report['stray_after'])}")


def tick(delta):
    try:
        if state["n"] in CAPTURE_AT:
            for r in runs:
                r["cc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, r["rt"], OUT, f"{r['tag']}_{state['n']:04d}.png")
            report["captures"].append(state["n"])
        state["n"] += 1
        if state["n"] > max(CAPTURE_AT):
            cleanup()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        cleanup()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("PUSS_SOFTGOODS_PIN_CHECK_STARTED")
