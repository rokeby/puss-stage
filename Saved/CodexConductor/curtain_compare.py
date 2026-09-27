"""Side-by-side of the ragged and plain curtains, lit well enough to judge.

The ragged one is placed at x=5400 in P01, which is close to unlit. The plain one
is not placed at all. So: spawn the plain one beside it, add a temporary light,
capture, then destroy both additions. Transient only -- nothing saved.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

ragged = None
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if a.get_actor_label() == "CurtainChaos Preview":
        ragged = a
        break
if ragged is None:
    unreal.log_error("RAGGED_NOT_FOUND")
    raise SystemExit
rl = ragged.get_actor_location()
unreal.log("RAGGED_AT|x=%.0f y=%.0f z=%.0f" % (rl.x, rl.y, rl.z))

plain_bp = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainChaos_Plain_Q15")
if not plain_bp:
    unreal.log_error("PLAIN_BP_NOT_FOUND")
    raise SystemExit

OFFSET_Y = 2200.0
spawned = []
try:
    plain = unreal.EditorLevelLibrary.spawn_actor_from_class(
        plain_bp, unreal.Vector(rl.x, rl.y + OFFSET_Y, rl.z), ragged.get_actor_rotation())
    plain.set_actor_label("ZZ_TEMP_PlainCompare")
    spawned.append(plain)
    unreal.log("PLAIN_SPAWNED|y=%.0f" % (rl.y + OFFSET_Y))

    # A temporary key light: P01 is near-black here and neither curtain would read.
    for i, dy in enumerate((0.0, OFFSET_Y)):
        lamp = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.SpotLight, unreal.Vector(rl.x - 900.0, rl.y + dy + 300.0, rl.z + 900.0),
            unreal.Rotator(roll=0.0, pitch=-32.0, yaw=-15.0))
        lamp.set_actor_label("ZZ_TEMP_CompareLight%d" % i)
        c = lamp.spot_light_component
        c.set_editor_property("intensity", 9000.0)
        c.set_editor_property("attenuation_radius", 6000.0)
        c.set_editor_property("outer_cone_angle", 42.0)
        c.set_editor_property("inner_cone_angle", 12.0)
        c.set_editor_property("light_color", unreal.Color(255, 244, 228))
        spawned.append(lamp)

    OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    FRAMES = 120
    FR = unreal.Paths.project_saved_dir() + "CodexConductor/Frames/curtain_compare/"
    os.makedirs(FR, exist_ok=True)
    for f in os.listdir(FR):
        if f.endswith(".png"):
            os.remove(FR + f)
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, unreal.Vector(0, 0, 0), unreal.Rotator())
    spawned.append(cap)
    cap.set_actor_label("ZZ_TransientCapture")
    comp = cap.capture_component2d
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    comp.set_editor_property("fov_angle", 60.0)
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("capture_on_movement", False)
    # Dolly along the pair: ragged first, then plain.
    for i in range(FRAMES):
        t = i / max(1, FRAMES - 1)
        y = rl.y - 700.0 + (OFFSET_Y + 1400.0) * t
        cap.set_actor_location_and_rotation(
            unreal.Vector(rl.x - 1500.0, y, rl.z + 620.0),
            unreal.Rotator(roll=0.0, pitch=-4.0, yaw=0.0), False, False)
        comp.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, FR, "f%04d.png" % i)
    unreal.log("CAPTURE|curtain_compare|%d frames" % FRAMES)
finally:
    for a in spawned:
        unreal.EditorLevelLibrary.destroy_actor(a)
    unreal.log("TEMP_CLEANED|%d actors destroyed" % len(spawned))

c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log("COMPARE_DIRTY|content=%d|map=%d" % (c, m))
