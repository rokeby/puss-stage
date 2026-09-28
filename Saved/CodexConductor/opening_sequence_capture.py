"""Play the Chaos opening sequence in Sequencer and capture the real thing.

The curtain is a SPAWNABLE: it does not exist in the level, only while the
sequence is evaluated. So this opens LS_Opening_Curtain_Chaos, scrubs to given
frames, and captures. Sequencer is closed afterwards and nothing is saved.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Chaos"

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

b_c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
b_m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())

seq = unreal.EditorAssetLibrary.load_asset(SEQ)
if not seq:
    unreal.log_error("SEQ_NOT_FOUND|%s" % SEQ)
    raise SystemExit
L = unreal.LevelSequenceEditorBlueprintLibrary
L.open_level_sequence(seq)
unreal.log("SEQ_OPEN|%s" % seq.get_name())

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

# 15 mm on the 23.76 mm filmback = 76.8 deg horizontal.
FRAMINGS = [("stalls", 150.0, 14.0)]
FRAMES = [(40, "hanging"), (58, "release"), (66, "falling"), (120, "fallen")]

try:
    for fr, label in FRAMES:
        L.set_current_time(fr)
        for tag, z, pitch in FRAMINGS:
            cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.SceneCapture2D, unreal.Vector(-1400.0, 0.0, z),
                unreal.Rotator(roll=0.0, pitch=pitch, yaw=0.0))
            try:
                cap.set_actor_label("ZZ_TransientCapture")
                c = cap.capture_component2d
                c.set_editor_property("texture_target", rt)
                c.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                c.set_editor_property("fov_angle", 76.8)
                c.set_editor_property("capture_every_frame", False)
                c.set_editor_property("capture_on_movement", False)
                flags = []
                for fname, on in (("VolumetricFog", True), ("Editor", False), ("BillboardSprites", False)):
                    sfx = unreal.EngineShowFlagsSetting()
                    sfx.set_editor_property("show_flag_name", fname)
                    sfx.set_editor_property("enabled", on)
                    flags.append(sfx)
                c.set_editor_property("show_flag_settings", flags)
                hide = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                        if "Camera + Shadow Figures" in a.get_actor_label()
                        or a.get_class().get_name() == "InfinityStageShadowCatActor"]
                for h in hide:
                    c.hide_actor_components(h, True)
                c.capture_scene()
                name = "LIT_%s" % label
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
                unreal.log("CAPTURE|%s|frame=%d" % (name, fr))
            finally:
                unreal.EditorLevelLibrary.destroy_actor(cap)
finally:
    L.close_level_sequence()
    a_c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    a_m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log("SEQ_CAPTURE_DONE|dirty %d+%d -> %d+%d" % (b_c, b_m, a_c, a_m))
