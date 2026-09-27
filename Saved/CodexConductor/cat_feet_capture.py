"""Close shot of a cat's paws against the new board tops.

Rig's probe says P01 and P02's cats sit 5.5 and 11 cm BELOW z=0 (the board tops)
while P04-P06 hover 4.1 cm above, but that reading assumes the cat's root is at
its paws, which is unconfirmed. A close capture settles it.
"""
import unreal, os
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()

cats = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShadowCatActor)
unreal.log("CATS|%d" % len(cats))
for c in cats:
    l = c.get_actor_location()
    unreal.log("CAT|%s|x=%.0f y=%.0f z=%.1f" % (c.get_actor_label(), l.x, l.y, l.z))

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

# Frame each cat's feet from low and close, looking slightly down at the floor line.
for idx, c in enumerate(sorted(cats, key=lambda a: a.get_actor_location().y)):
    label = c.get_actor_label()
    l = c.get_actor_location()
    # Stand 320 cm in front, 60 cm up, looking down 10 degrees at the paws.
    cam = unreal.Vector(l.x - 320.0, l.y, l.z + 60.0)
    # Name by corridor (y separates the Passages) so six shots do not collide.
    name = "CATFEET_P%02d_z%+05.1f" % (idx + 1, l.z)
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, cam, unreal.Rotator(roll=0.0, pitch=-10.0, yaw=0.0))
    try:
        comp = cap.capture_component2d
        comp.set_editor_property("texture_target", rt)
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        comp.set_editor_property("fov_angle", 50.0)
        comp.set_editor_property("capture_every_frame", False)
        comp.set_editor_property("capture_on_movement", False)
        comp.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
        unreal.log("CAPTURE|%s|cat_z=%.1f" % (name, l.z))
    finally:
        unreal.EditorLevelLibrary.destroy_actor(cap)
unreal.log("CATFEET_DONE")
