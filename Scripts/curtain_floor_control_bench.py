"""Floor control bench (Unreal Python, MCP route; announce first). Transient only, saves nothing.

Question 1: why does the correctly pinned curtain go THROUGH the floor catch? Question 2: why does it
descend rigid instead of crumpling? Six pinned PLAIN curtains off-stage (y >= 73000), each carried
995 cm down and 180 cm upstage (world +X) over DROP ticks (s^2 / s^1.5), exactly the Opening drop:

  V1 inactor   BP_CurtainChaos (FloorCatch is a component of the same actor); the cloth COMPONENT moves
  V2 separate  cloth actor over a separate BP_CurtainFloorCatch; the cloth ACTOR moves (the Opening)
  V3 thick     as V2, but the separate box is made 400 cm thick (top still at z = 0)
  V4 ccd       as V2, interactor UseCCD = 1 (continuous collision), if the asset exposes it
  V5 vscale1   as V2, interactor LinearVelocityScale = (1,1,1), if the asset exposes it
  V6 nofloor   cloth actor with NO floor at all (the control: identical to V2 means the floor is ignored)

Each has a perspective capture (lit, own lamp) and a SIDE ORTHOGRAPHIC show-only capture of just the
cloth in base colour, so the cloth's z-range and upstage spread can be measured in pixels, below the
ground plane included. Tick deltas are logged (the sim time the drop really takes).
"""
import json
import os

import unreal

HOLD, DROP, TOTAL, EVERY = 30, 32, 170, 4
ASSET = "/Game/Scenes/Curtain/Chaos/CA_CurtainChaos_Plain_Q15"
ROOT = "/Game/Scenes/Curtain/Chaos"
ORTHO_W, SIDE_W, SIDE_H = 2600.0, 640, 360
SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", "floor_control")
LOG = os.path.join(SAVED, "CodexSoftGoods", "floor_control_bench.json")
VARIANTS = [
    {"id": "V1_inactor", "bp": "BP_CurtainChaos", "move": "component", "floor": None},
    {"id": "V2_separate", "bp": "BP_CurtainChaosCloth", "move": "actor", "floor": "normal"},
    {"id": "V3_thick", "bp": "BP_CurtainChaosCloth", "move": "actor", "floor": "thick"},
    {"id": "V4_ccd", "bp": "BP_CurtainChaosCloth", "move": "actor", "floor": "normal", "ints": {"UseCCD": 1}},
    {"id": "V5_vscale1", "bp": "BP_CurtainChaosCloth", "move": "actor", "floor": "normal",
     "vectors": {"LinearVelocityScale": (1.0, 1.0, 1.0)}},
    {"id": "V6_nofloor", "bp": "BP_CurtainChaosCloth", "move": "actor", "floor": None},
]

ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    raise RuntimeError("wrong world")
DIRTY_BEFORE = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if DIRTY_BEFORE:
    raise RuntimeError(f"dirty content {DIRTY_BEFORE}: refusing")
if any(a.get_actor_label().startswith("ZZ_") for a in ss.get_all_level_actors()):
    raise RuntimeError("ZZ_ actors already present")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

asset = unreal.EditorAssetLibrary.load_asset(ASSET)
report = {"errors": [], "captures": 0, "deltas": [], "variants": {}, "hold": HOLD, "drop": DROP, "every": EVERY,
          "side": {"ortho_width": ORTHO_W, "w": SIDE_W, "h": SIDE_H}}
temps, runs = [], []


def capture_rig(tag, base, cloth_actor):
    rt = unreal.RenderingLibrary.create_render_target2d(world, 640, 360, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cam = ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(base.x - 2400.0, base.y - 900.0, 700.0),
                                    unreal.Rotator(roll=0.0, pitch=-10.0, yaw=20.0))
    cam.set_actor_label(f"ZZ_TransientCapture_SoftGoods_Floor_{tag}")
    cc = cam.capture_component2d
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    cc.set_editor_property("fov_angle", 75.0)
    cc.set_editor_property("capture_every_frame", False)
    # Side ortho: stands at +Y looking toward -Y, so screen-right is world +X (upstage) and up is +Z.
    side_center = unreal.Vector(base.x + 300.0, base.y + 4000.0, 400.0)
    srt = unreal.RenderingLibrary.create_render_target2d(world, SIDE_W, SIDE_H, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    side = ss.spawn_actor_from_class(unreal.SceneCapture2D, side_center, unreal.Rotator(roll=0.0, pitch=0.0, yaw=-90.0))
    side.set_actor_label(f"ZZ_TransientCapture_SoftGoods_FloorSide_{tag}")
    sc = side.capture_component2d
    sc.set_editor_property("texture_target", srt)
    sc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
    sc.set_editor_property("projection_type", unreal.CameraProjectionMode.ORTHOGRAPHIC)
    sc.set_editor_property("ortho_width", ORTHO_W)
    sc.set_editor_property("primitive_render_mode", unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
    sc.show_only_actor_components(cloth_actor, False)
    sc.set_editor_property("capture_every_frame", False)
    temps.extend([cam, side])
    return cc, rt, sc, srt, side_center


def setup():
  for i, v in enumerate(VARIANTS):
      tag = v["id"]
      base = unreal.Vector(5400.0, 73000.0 + i * 3500.0, 0.0)
      rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0)
      cloth_actor = ss.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(f"{ROOT}/{v['bp']}"), base, rot)
      cloth_actor.set_actor_label(f"ZZ_TEMP_SoftGoods_Floor_{tag}")
      temps.append(cloth_actor)
      info = {"bp": v["bp"], "move": v["move"], "floor": v["floor"]}
      if v["floor"]:
          floor_actor = ss.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(f"{ROOT}/BP_CurtainFloorCatch"), base, rot)
          floor_actor.set_actor_label(f"ZZ_TEMP_SoftGoods_FloorCatch_{tag}")
          temps.append(floor_actor)
          box = floor_actor.get_components_by_class(unreal.BoxComponent)[0]
          ext = box.get_unscaled_box_extent()
          info["box_extent_before"] = [ext.x, ext.y, ext.z]
          info["box_rel_z_before"] = box.get_editor_property("relative_location").z
          if v["floor"] == "thick":
              box.set_box_extent(unreal.Vector(ext.x, ext.y, 200.0), True)
              box.set_relative_location(unreal.Vector(0.0, 0.0, -200.0), False, True)
              info["box_extent_after"] = [ext.x, ext.y, 200.0]
      else:
          boxes = cloth_actor.get_components_by_class(unreal.BoxComponent)
          if boxes:
              ext = boxes[0].get_unscaled_box_extent()
              info["inactor_box_extent"] = [ext.x, ext.y, ext.z]
              info["inactor_box_rel_z"] = boxes[0].get_editor_property("relative_location").z
      lamp = ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(base.x - 1600.0, base.y, 1400.0), unreal.Rotator(roll=0.0, pitch=-35.0, yaw=0.0))
      lamp.set_actor_label(f"ZZ_TEMP_SoftGoods_FloorLamp_{tag}")
      lamp.spot_light_component.set_editor_property("intensity", 30000.0)
      lamp.spot_light_component.set_editor_property("attenuation_radius", 8000.0)
      lamp.spot_light_component.set_editor_property("outer_cone_angle", 60.0)
      temps.append(lamp)
      cloth = cloth_actor.get_components_by_class(unreal.ChaosClothComponent)[0]
      cloth.set_asset(asset)
      cloth.set_editor_property("suspend_simulation", False)
      cc, rt, sc, srt, side_center = capture_rig(tag, base, cloth_actor)
      info["side_center"] = [side_center.x, side_center.y, side_center.z]
      info["base"] = [base.x, base.y, base.z]
      report["variants"][tag] = info
      cloth.set_simulate_in_editor(True)
      runs.append({"v": v, "tag": tag, "actor": cloth_actor, "cloth": cloth, "base": base, "cc": cc, "rt": rt, "sc": sc, "srt": srt,
                   "applied": False})


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
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_FLOOR_BENCH_DONE|captures={report['captures']}|stray={len(report['stray_after'])}"
               f"|dirty={report['dirty_content_after']}|errors={len(report['errors'])}")


def apply_overrides(r):
    inter = r["cloth"].get_cloth_outfit_interactor()
    if inter is None:
        return False
    names = [str(n) for n in inter.get_all_property_names(-1)]
    got = {}
    for name, value in r["v"].get("ints", {}).items():
        got[name] = name in names
        if name in names:
            inter.set_int_property_value(name, -1, int(value))
    for name, value in r["v"].get("vectors", {}).items():
        got[name] = name in names
        if name in names:
            inter.set_vector_property_value(name, -1, unreal.Vector(*value))
    report["variants"][r["tag"]]["overrides_present"] = got
    if r["tag"] == "V2_separate":
        report["interactor_property_names"] = names
    return True


def tick(delta):
    try:
        n = state["n"]
        report["deltas"].append(round(delta, 4))
        for r in runs:
            if not r["applied"]:
                r["applied"] = apply_overrides(r)
        if n >= HOLD:
            s = min(1.0, (n - HOLD) / float(DROP))
            fwd, down = 180.0 * (s ** 1.5), 995.0 * s * s
            for r in runs:
                if r["v"]["move"] == "component":
                    # actor yaw 90: local -Y is world +X (upstage)
                    r["cloth"].set_relative_location(unreal.Vector(0.0, -fwd, -down), False, False)
                else:
                    b = r["base"]
                    r["actor"].set_actor_location(unreal.Vector(b.x + fwd, b.y, b.z - down), False, False)
        if n % EVERY == 0:
            for r in runs:
                r["cc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, r["rt"], OUT, f"{r['tag']}_{n:04d}.png")
                r["sc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, r["srt"], OUT, f"{r['tag']}_side_{n:04d}.png")
            report["captures"] += 1
        state["n"] += 1
        if state["n"] > TOTAL:
            cleanup()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        cleanup()


try:
    setup()
except Exception as exc:  # noqa: BLE001
    report["errors"].append(f"setup {exc}")
    cleanup()
    raise
state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("PUSS_SOFTGOODS_FLOOR_BENCH_STARTED")
