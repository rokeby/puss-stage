"""The opening, from the exact camera the audience gets.

Pose measured by Look & camera via GetPassageCameraPose at P1's StartFrame:
location (0, 0, 150), rotation 0/0/0, forward +X, 25 mm on a 23.76 x 13.37 mm
filmback = 50.8 degrees horizontal. Not a guess and not the saved rig actor,
which is an evaluated fossil at (3850, 0, 150).

Nothing is moved. The capture actor is transient and destroyed after.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

OPENING_LOC = unreal.Vector(0.0, 0.0, 150.0)
OPENING_ROT = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
HFOV = 50.8

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

shots = [
    ("OPENING_asAudience", OPENING_LOC, OPENING_ROT, HFOV),
    # A second, wider one purely to see how much of the corridor the beam touches.
    ("OPENING_wide", OPENING_LOC, OPENING_ROT, 80.0),
    # Mid-throw, to see the beam travelling and the floats behind the curtain.
    ("OPENING_mid", unreal.Vector(2600.0, 0.0, 150.0), OPENING_ROT, HFOV),
]
for name, loc, rot, fov in shots:
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot)
    try:
        cap.set_actor_label("ZZ_TransientCapture")
        c = cap.capture_component2d
        c.set_editor_property("texture_target", rt)
        c.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        c.set_editor_property("fov_angle", fov)
        c.set_editor_property("capture_every_frame", False)
        c.set_editor_property("capture_on_movement", False)
        flags = []
        for fname, on in (("VolumetricFog", True), ("Editor", False), ("BillboardSprites", False),
                          ("Selection", False), ("Grid", False)):
            sfx = unreal.EngineShowFlagsSetting()
            sfx.set_editor_property("show_flag_name", fname)
            sfx.set_editor_property("enabled", on)
            flags.append(sfx)
        c.set_editor_property("show_flag_settings", flags)
        # The P01 camera rig's proxy mesh is editor-only and never renders in PIE;
        # the shadow cat is real content but is parked at the rig's FOSSIL position
        # (x 3569), not where the evaluated opening pose would put her. Hiding both
        # gives an honest look at the light and the curtain.
        hide = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if "Camera + Shadow Figures" in a.get_actor_label()
                or a.get_class().get_name() == "InfinityStageShadowCatActor"]
        # hidden_actors is template-locked; hide_actor_components works per instance.
        for h in hide:
            c.hide_actor_components(h, True)
        unreal.log("HIDDEN|%d actors" % len(hide))
        c.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
        unreal.log("CAPTURE|%s|loc=%.0f,%.0f,%.0f|hfov=%.1f" % (name, loc.x, loc.y, loc.z, fov))
    finally:
        unreal.EditorLevelLibrary.destroy_actor(cap)
unreal.log("OPENING_CAPTURE_DONE")
