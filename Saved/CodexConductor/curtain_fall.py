"""Let both curtains actually FALL, capturing a frame per editor tick.

A blocking Python loop cannot do this: the cloth only advances when the editor
ticks, and a loop holds the game thread. So this registers a Slate post-tick
callback, releases the suspension, and captures one frame per tick. Cleanup runs
inside the callback, and curtain_fall_cleanup.py exists if it ever doesn't.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
FRAMES = 220
OFFSET_Y = 2200.0

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

ragged = next((a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
               if a.get_actor_label() == "CurtainChaos Preview"), None)
if ragged is None:
    unreal.log_error("RAGGED_NOT_FOUND")
    raise SystemExit
rl = ragged.get_actor_location()

plain_bp = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainChaos_Plain_Q15")
temps = []
plain = unreal.EditorLevelLibrary.spawn_actor_from_class(
    plain_bp, unreal.Vector(rl.x, rl.y + OFFSET_Y, rl.z), ragged.get_actor_rotation())
plain.set_actor_label("ZZ_TEMP_PlainFall")
temps.append(plain)

for i, dy in enumerate((0.0, OFFSET_Y)):
    lamp = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SpotLight, unreal.Vector(rl.x - 1000.0, rl.y + dy + 200.0, rl.z + 1000.0),
        unreal.Rotator(roll=0.0, pitch=-34.0, yaw=-10.0))
    lamp.set_actor_label("ZZ_TEMP_FallLight%d" % i)
    c = lamp.spot_light_component
    c.set_editor_property("intensity", 9000.0)
    c.set_editor_property("attenuation_radius", 7000.0)
    c.set_editor_property("outer_cone_angle", 46.0)
    c.set_editor_property("inner_cone_angle", 14.0)
    temps.append(lamp)

cloths = []
for act in (ragged, plain):
    for comp in act.get_components_by_class(unreal.ActorComponent):
        if "Cloth" in comp.get_class().get_name():
            cloths.append(comp)
unreal.log("CLOTHS|%d" % len(cloths))

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Frames/curtain_fall/"
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(OUT + f)

rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.SceneCapture2D,
    unreal.Vector(rl.x - 2000.0, rl.y + OFFSET_Y / 2.0, rl.z + 640.0),
    unreal.Rotator(roll=0.0, pitch=-8.0, yaw=0.0))
cap.set_actor_label("ZZ_TransientCapture")
temps.append(cap)
comp = cap.capture_component2d
comp.set_editor_property("texture_target", rt)
comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
comp.set_editor_property("fov_angle", 74.0)
comp.set_editor_property("capture_every_frame", False)
comp.set_editor_property("capture_on_movement", False)

for cl in cloths:
    cl.set_simulate_in_editor(True)
    cl.set_enable_simulation(True)

state = {"n": 0, "handle": None, "released": False}

def tick(delta):
    try:
        if not state["released"]:
            for cl in cloths:
                cl.resume_simulation()
            state["released"] = True
            unreal.log("FALL_RELEASED")
        comp.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, "f%04d.png" % state["n"])
        state["n"] += 1
        if state["n"] >= FRAMES:
            raise StopIteration
    except Exception:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        for cl in cloths:
            try:
                cl.suspend_simulation()
                cl.set_simulate_in_editor(False)
            except Exception:
                pass
        for a in temps:
            try:
                unreal.EditorLevelLibrary.destroy_actor(a)
            except Exception:
                pass
        unreal.log("FALL_DONE|%d frames|%s" % (state["n"], OUT))

state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("FALL_STARTED|capturing %d ticks" % FRAMES)
