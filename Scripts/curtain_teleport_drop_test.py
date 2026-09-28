"""Teleport test for the guided drop in the Opening arrangement (Unreal Python, MCP route; announce first).

RESULT 28 Sep: A (teleport=False) and B (teleport=True) are indistinguishable. UChaosClothComponent ignores
ETeleportType; both descend rigid and pass BELOW a separate BP_CurtainFloorCatch. See Docs/ChaosClothCurtain.md.
"""
import json
import os

import unreal

HOLD, DROP, TOTAL = 30, 32, 170
SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", "teleport_drop")
LOG = os.path.join(SAVED, "CodexSoftGoods", "teleport_drop_test.json")
ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    raise RuntimeError("wrong world")
# Nothing here saves. Record what was already dirty (the Opening sequence, after the conductor's capture)
# and require that this test adds nothing to it.
DIRTY_BEFORE = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if [p for p in DIRTY_BEFORE if "/Scenes/Curtain/" in p]:
    raise RuntimeError("curtain content dirty: refusing")
if any(a.get_actor_label().startswith("ZZ_") for a in ss.get_all_level_actors()):
    raise RuntimeError("ZZ_ actors already present")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

cloth_bp = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainChaosCloth")
floor_bp = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainFloorCatch")
report = {"errors": [], "captures": 0, "dirty_before": DIRTY_BEFORE}
temps, runs = [], []
for i, (tag, teleport) in enumerate((("A_noteleport", False), ("B_teleport", True))):
    base = unreal.Vector(5400.0, 73000.0 + i * 3500.0, 0.0)
    rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0)
    cloth_actor = ss.spawn_actor_from_class(cloth_bp, base, rot)
    cloth_actor.set_actor_label(f"ZZ_TEMP_SoftGoods_Tele_{tag}")
    floor_actor = ss.spawn_actor_from_class(floor_bp, base, rot)
    floor_actor.set_actor_label(f"ZZ_TEMP_SoftGoods_TeleFloor_{tag}")
    lamp = ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(base.x - 1600.0, base.y, 1400.0), unreal.Rotator(roll=0.0, pitch=-35.0, yaw=0.0))
    lamp.set_actor_label(f"ZZ_TEMP_SoftGoods_TeleLamp_{tag}")
    lamp.spot_light_component.set_editor_property("intensity", 30000.0)
    lamp.spot_light_component.set_editor_property("attenuation_radius", 8000.0)
    lamp.spot_light_component.set_editor_property("outer_cone_angle", 60.0)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 640, 360, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cam = ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(base.x - 2400.0, base.y - 900.0, 700.0),
                                    unreal.Rotator(roll=0.0, pitch=-10.0, yaw=20.0))
    cam.set_actor_label(f"ZZ_TransientCapture_SoftGoods_Tele_{tag}")
    temps += [cloth_actor, floor_actor, lamp, cam]
    cc = cam.capture_component2d
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    cc.set_editor_property("fov_angle", 75.0)
    cc.set_editor_property("capture_every_frame", False)
    cloth = cloth_actor.get_components_by_class(unreal.ChaosClothComponent)[0]
    cloth.set_asset(unreal.EditorAssetLibrary.load_asset("/Game/Scenes/Curtain/Chaos/CA_CurtainChaos_Plain_Q15"))
    cloth.set_editor_property("suspend_simulation", False)
    cloth.set_simulate_in_editor(True)
    runs.append({"tag": tag, "teleport": teleport, "actor": cloth_actor, "cloth": cloth, "base": base, "cc": cc, "rt": rt})

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
    report["dirty_content_after"] = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    report["new_dirty"] = [p for p in report["dirty_content_after"] if p not in DIRTY_BEFORE]
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_TELEPORT_TEST_DONE|captures={report['captures']}|stray={len(report['stray_after'])}|new_dirty={report['new_dirty']}|errors={len(report['errors'])}")


def tick(delta):
    try:
        n = state["n"]
        if n >= HOLD:
            s = min(1.0, (n - HOLD) / float(DROP))
            for r in runs:
                b = r["base"]
                loc = unreal.Vector(b.x + 180.0 * (s ** 1.5), b.y, b.z - 995.0 * s * s)
                r["actor"].set_actor_location(loc, False, r["teleport"])
        if n % 4 == 0:
            for r in runs:
                r["cc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, r["rt"], OUT, f"{r['tag']}_{n:04d}.png")
            report["captures"] += 1
        state["n"] += 1
        if state["n"] > TOTAL:
            cleanup()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        cleanup()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("PUSS_SOFTGOODS_TELEPORT_TEST_STARTED")
