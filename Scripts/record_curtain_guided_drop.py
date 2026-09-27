"""Record the guided curtain drop in situ, under the show's own lighting (Unreal Python, MCP route).

Gary, 27 Sep: "suspend the curtain sim and swap to guided - can you record the new curtain so I can
see it remotely". This records the placed "CurtainChaos Preview" (ragged, BP_CurtainChaos) plus a
TRANSIENT plain one beside it (BP_CurtainChaos_Plain_Q15, y + 2200), from the conductor's framing.
NO light is added: if P01 is too dark to read, the clip says so.

Sequence (a Slate post-tick callback, because the cloth only advances when the editor ticks):
hang for HOLD ticks, then carry each cloth component down (gravity-timed, s^2) and FORWARD_CM along
its face over DROP_TICKS (~0.9 s of simulation), then keep recording while it settles. One PNG per
tick, contiguous from f0000, for ffmpeg.

Afterwards the placed actor is restored exactly (cloth offset 0, suspended, not simulating in
editor) and the transient curtain and camera are destroyed. Content dirty stays 0; the level keeps
the net-nil dirty flag that spawning/destroying transients sets.

Note: on ChaosClothComponent, `suspend_simulation` is a bool PROPERTY in Python (it shadows the
SuspendSimulation function): set it with set_editor_property, don't call it.
"""
import json
import os

import unreal

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
LABEL = "CurtainChaos Preview"
PLAIN_BP = "/Game/Scenes/Curtain/Chaos/BP_CurtainChaos_Plain_Q15"
OFFSET_Y = 2200.0
HOLD, DROP_TICKS, TOTAL = 20, 32, 200
FORWARD_CM, DROP_CM = 450.0, 995.0
SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", "curtain_guided_insitu")
LOG = os.path.join(SAVED, "CodexSoftGoods", "record_curtain_guided_drop.json")

ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    raise RuntimeError("wrong world")
if [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
    raise RuntimeError("dirty content: refusing")
actors = ss.get_all_level_actors()
if any(a.get_actor_label().startswith(("ZZ_TEMP_SoftGoods", "ZZ_TransientCapture_SoftGoods")) for a in actors):
    raise RuntimeError("stray SoftGoods temps: run curtain_fall_bench_cleanup.py first")
placed = next((a for a in actors if a.get_actor_label() == LABEL), None)
if placed is None:
    raise RuntimeError(f"'{LABEL}' not found")

os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

report = {"errors": [], "frames": 0}
loc, rot = placed.get_actor_location(), placed.get_actor_rotation()
temps = []
plain = ss.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(PLAIN_BP),
                                  unreal.Vector(loc.x, loc.y + OFFSET_Y, loc.z), rot)
plain.set_actor_label("ZZ_TEMP_SoftGoods_PlainRecord")
temps.append(plain)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
cam = ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(loc.x - 2000.0, loc.y + OFFSET_Y / 2.0, loc.z + 640.0),
                                unreal.Rotator(roll=0.0, pitch=-8.0, yaw=0.0))
cam.set_actor_label("ZZ_TransientCapture_SoftGoods_Record")
temps.append(cam)
cc = cam.capture_component2d
cc.set_editor_property("texture_target", rt)
cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
cc.set_editor_property("fov_angle", 74.0)
cc.set_editor_property("capture_every_frame", False)
cc.set_editor_property("capture_on_movement", False)

cloths = [a.get_components_by_class(unreal.ChaosClothComponent)[0] for a in (placed, plain)]
report["assets"] = [c.get_editor_property("asset").get_path_name() for c in cloths]
for c in cloths:
    c.set_simulate_in_editor(True)
    c.set_enable_simulation(True)

state = {"n": 0, "waits": 0, "handle": None, "released": False}


def restore():
    if state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    placed_cloth = cloths[0]
    try:
        placed_cloth.set_relative_location(unreal.Vector(0.0, 0.0, 0.0), False, True)
        # ORDER MATTERS: switch editor simulation off FIRST, then suspend. The other way round, the
        # suspend was undone and the placed curtain was left live-simulating (27 Sep, caught on read-back).
        placed_cloth.set_simulate_in_editor(False)
        placed_cloth.set_editor_property("suspend_simulation", True)
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"restore {exc}")
    for a in temps:
        try:
            ss.destroy_actor(a)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(f"destroy {exc}")
    rl = placed_cloth.get_editor_property("relative_location")
    report["placed_after"] = {"relative_location": [rl.x, rl.y, rl.z],
                              "suspend_simulation": placed_cloth.get_editor_property("suspend_simulation"),
                              "simulate_in_editor": placed_cloth.get_editor_property("simulate_in_editor")}
    report["stray_after"] = [a.get_actor_label() for a in ss.get_all_level_actors()
                             if a.get_actor_label().startswith(("ZZ_TEMP_SoftGoods", "ZZ_TransientCapture_SoftGoods"))]
    report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    report["out"] = OUT
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_GUIDED_RECORD_DONE|frames={report['frames']}|stray={len(report['stray_after'])}|errors={len(report['errors'])}")


def tick(delta):
    try:
        if not state["released"]:
            state["waits"] += 1
            if any(c.get_cloth_outfit_interactor() is None for c in cloths):
                if state["waits"] > 60:
                    raise RuntimeError("cloth proxies never came up")
                return
            for c in cloths:
                c.set_editor_property("suspend_simulation", False)
            state["released"] = True
        n = state["n"]
        if n >= HOLD:
            s = min(1.0, (n - HOLD) / float(DROP_TICKS))
            offset = unreal.Vector(0.0, FORWARD_CM * (s ** 1.5), -DROP_CM * s * s)
            for c in cloths:
                c.set_relative_location(offset, False, False)
        cc.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"f{n:04d}.png")
        state["n"] += 1
        report["frames"] = state["n"]
        if state["n"] >= TOTAL:
            restore()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        restore()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log(f"PUSS_SOFTGOODS_GUIDED_RECORD_STARTED|hold={HOLD}|drop_ticks={DROP_TICKS}|total={TOTAL}")
