"""Fall bench: drop several variants of the falling curtain side by side and capture them.

Transient only: spawns ZZ_TEMP_SoftGoods* curtains, lights and ZZ_TransientCapture_SoftGoods*
cameras far off-stage (y >= 60000), overrides cloth parameters per variant through the
ChaosClothAssetInteractor (runtime only, nothing saved), releases them on the first tick, captures
every Nth tick, logs tick times and cloth bounds, then destroys everything. Content dirty stays 0;
the map flag is set by the spawns (net nil). A Slate post-tick callback drives it, because the
cloth only advances when the editor ticks.

Config comes from Saved/CodexSoftGoods/fall_bench_config.json so variants change without edits here.
"""
import json
import os
import time

import unreal

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
_ptr = os.path.join(SAVED, "CodexSoftGoods", "fall_bench_active.txt")
_cfg_name = open(_ptr, encoding="utf-8").read().strip() if os.path.exists(_ptr) else "fall_bench_config.json"
CFG = json.load(open(os.path.join(SAVED, "CodexSoftGoods", _cfg_name), encoding="utf-8"))
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", CFG["name"])
LOG = os.path.join(SAVED, "CodexSoftGoods", f"fall_bench_{CFG['name']}.json")

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    raise RuntimeError("wrong world")
if [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
    raise RuntimeError("dirty content: refusing")
actors_ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if any(a.get_actor_label().startswith("ZZ_TEMP_SoftGoods") for a in actors_ss.get_all_level_actors()):
    raise RuntimeError("stray ZZ_TEMP_SoftGoods actors from a previous bench: run fall_bench_cleanup.py")

os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

temps, runs = [], []
report = {"config": CFG, "ticks": [], "bounds": {}, "overrides": {}, "errors": []}
W, H = CFG.get("width", 640), CFG.get("height", 360)
for i, v in enumerate(CFG["variants"]):
    base = unreal.Vector(5400.0, 60000.0 + i * CFG.get("spacing", 3000.0), 0.0)
    bp = unreal.EditorAssetLibrary.load_blueprint_class(v.get("bp", "/Game/Scenes/Curtain/Chaos/BP_CurtainChaos_Plain_Q15"))
    act = actors_ss.spawn_actor_from_class(bp, base, unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
    act.set_actor_label(f"ZZ_TEMP_SoftGoods_{v['id']}")
    temps.append(act)
    lamp = actors_ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(base.x - 1200.0, base.y - 600.0, 1400.0),
                                            unreal.Rotator(roll=0.0, pitch=-40.0, yaw=20.0))
    lamp.set_actor_label(f"ZZ_TEMP_SoftGoods_Light_{v['id']}")
    lc = lamp.spot_light_component
    lc.set_editor_property("intensity", 12000.0)
    lc.set_editor_property("attenuation_radius", 6000.0)
    lc.set_editor_property("outer_cone_angle", 50.0)
    temps.append(lamp)
    rt = unreal.RenderingLibrary.create_render_target2d(world, W, H, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cam = actors_ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(base.x - 1900.0, base.y - 1100.0, 780.0),
                                           unreal.Rotator(roll=0.0, pitch=-20.0, yaw=28.0))
    cam.set_actor_label(f"ZZ_TransientCapture_SoftGoods_{v['id']}")
    temps.append(cam)
    cc = cam.capture_component2d
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    cc.set_editor_property("fov_angle", 72.0)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("capture_on_movement", False)
    cloth = act.get_components_by_class(unreal.ChaosClothComponent)[0]
    # Runtime setters with teleport, not set_editor_property: the editor-property path re-registers
    # the component, and its cloth proxy/interactor then never came up (bench2, 26 Sep).
    # Environment collision gathers colliders overlapping the cloth component's bounds, and those
    # bounds are the reference pose, not the simulation: a lifted or toppling cloth stops "seeing"
    # the FloorCatch and falls through (bench2b I_lift150). A bounds scale keeps the floor in range.
    if v.get("asset"):
        cloth.set_asset(unreal.EditorAssetLibrary.load_asset(v["asset"]))
    cloth.set_bounds_scale(float(v.get("bounds_scale", CFG.get("bounds_scale", 1.0))))
    if v.get("lift_cm"):
        # Lift only the cloth, so the hem starts above the FloorCatch and has somewhere to fall.
        cloth.set_relative_location(unreal.Vector(0.0, 0.0, float(v["lift_cm"])), False, True)
    if v.get("lean_deg"):
        # Lean only the cloth (about the curtain's base line), so its weight sits off the hem.
        cloth.set_relative_rotation(unreal.Rotator(roll=float(v["lean_deg"]), pitch=0.0, yaw=0.0), False, True)
    cloth.set_simulate_in_editor(True)
    cloth.set_enable_simulation(True)
    runs.append({"v": v, "actor": act, "cloth": cloth, "rt": rt, "cc": cc})

# Optional scene wind (a Wind Directional Source is GLOBAL, so use it with a single variant):
# {"yaw": 0.0, "events": [{"at": tick, "speed": s, "strength": st}, ...]}
wind_comp = None
if CFG.get("wind_source"):
    ws = CFG["wind_source"]
    wind_actor = actors_ss.spawn_actor_from_class(unreal.WindDirectionalSource, unreal.Vector(5400.0, 60000.0, 500.0),
                                                  unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(ws.get("yaw", 0.0))))
    wind_actor.set_actor_label("ZZ_TEMP_SoftGoods_Wind")
    temps.append(wind_actor)
    wind_comp = wind_actor.get_component_by_class(unreal.WindDirectionalSourceComponent)
    wind_comp.set_strength(0.0)
    wind_comp.set_speed(0.0)

state = {"n": 0, "handle": None, "t0": None, "last": None}


def apply_overrides(run):
    inter = run["cloth"].get_cloth_outfit_interactor()
    done = {}
    for name, value in run["v"].get("floats", {}).items():
        inter.set_float_property_value(name, -1, float(value))
        done[name] = inter.get_low_float_property_value(name, 0, -1.0)
    for name, value in run["v"].get("ints", {}).items():
        inter.set_int_property_value(name, -1, int(value))
        done[name] = inter.get_int_property_value(name, 0, -1)
    for name, value in run["v"].get("vectors", {}).items():
        inter.set_vector_property_value(name, -1, unreal.Vector(*value))
        vv = inter.get_vector_property_value(name, 0, unreal.Vector(-1, -1, -1))
        done[name] = [vv.x, vv.y, vv.z]
    report["overrides"][run["v"]["id"]] = done


def bounds(run):
    # The cloth component's own bounds (the actor's are swamped by the 30 m FloorCatch):
    # [x offset of centre from the hanging line, centre z, half-depth x, half-width y, half-height z] in cm.
    o, e, _ = unreal.SystemLibrary.get_component_bounds(run["cloth"])
    return [round(o.x - run["actor"].get_actor_location().x), round(o.z), round(e.x), round(e.y), round(e.z)]


def cleanup():
    if state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    for run in runs:
        try:
            run["cloth"].suspend_simulation()
            run["cloth"].set_simulate_in_editor(False)
        except Exception:  # noqa: BLE001
            pass
    for a in temps:
        try:
            actors_ss.destroy_actor(a)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(f"destroy {exc}")
    report["stray_after"] = [a.get_actor_label() for a in actors_ss.get_all_level_actors()
                             if a.get_actor_label().startswith(("ZZ_TEMP_SoftGoods", "ZZ_TransientCapture_SoftGoods"))]
    report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_FALL_BENCH_DONE|{CFG['name']}|ticks={state['n']}|stray={len(report['stray_after'])}")


def tick(delta):
    try:
        now = time.perf_counter()
        if state["n"] == 0:
            # The cloth's interactor appears a tick or more after simulate-in-editor is switched on
            # (and after a lean re-creates the proxy): wait for all of them, then override and release.
            state["waits"] = state.get("waits", 0) + 1
            if any(run["cloth"].get_cloth_outfit_interactor() is None for run in runs):
                if state["waits"] > 60:
                    raise RuntimeError("cloth interactors never appeared")
                return
            report["release_wait_ticks"] = state["waits"]
            for run in runs:
                apply_overrides(run)
                run["cloth"].resume_simulation()
            state["t0"] = now
        else:
            report["ticks"].append(round(now - state["last"], 4))
        state["last"] = now
        if wind_comp is not None:
            for event in CFG["wind_source"].get("events", []):
                if event["at"] == state["n"]:
                    wind_comp.set_speed(float(event.get("speed", 0.0)))
                    wind_comp.set_strength(float(event.get("strength", 0.0)))
                    report.setdefault("wind_events", []).append([state["n"], event])
        for run in runs:
            guide = run["v"].get("guide")
            if guide and state["n"] >= 1:
                # Carry the pinned heading down (gravity-timed: s^2) and forward, like a falling
                # batten. Local +Y is the curtain's face direction; the heading ends just off the floor.
                s = max(0.0, min(1.0, (state["n"] - 1 - guide.get("hold_ticks", 0)) / float(guide.get("ticks", 50))))
                fwd = guide.get("forward_cm", 0.0) * (s ** guide.get("forward_exp", 1.5))
                down = guide.get("drop_cm", 995.0) * (s * s)
                run["cloth"].set_relative_location(unreal.Vector(0.0, fwd, -down), False, False)
            for event in run["v"].get("schedule", []):
                if event["at"] == state["n"]:
                    inter = run["cloth"].get_cloth_outfit_interactor()
                    for name, value in event.get("floats", {}).items():
                        inter.set_float_property_value(name, -1, float(value))
                    for name, value in event.get("vectors", {}).items():
                        inter.set_vector_property_value(name, -1, unreal.Vector(*value))
        if CFG.get("capture_every", 3) and state["n"] % CFG.get("capture_every", 3) == 0:
            for run in runs:
                run["cc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, run["rt"], OUT, f"{run['v']['id']}_{state['n']:04d}.png")
        if state["n"] % CFG.get("bounds_every", 15) == 0:
            for run in runs:
                report["bounds"].setdefault(run["v"]["id"], []).append([state["n"], round(now - state["t0"], 2)] + bounds(run))
        state["n"] += 1
        if state["n"] >= CFG.get("ticks", 300):
            cleanup()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        cleanup()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log(f"PUSS_SOFTGOODS_FALL_BENCH_STARTED|{CFG['name']}|variants={len(runs)}")
