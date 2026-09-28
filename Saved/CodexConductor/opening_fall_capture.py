"""The opening fall, correctly pinned: settle, then drive the sequence through the drop.

Settles the spawned cloth at the hold frame so it hangs properly, then advances
Sequencer time through the transform-track drop while the editor ticks, so the
solver runs during the fall rather than the cloth being teleported frame to frame.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Chaos"
SETTLE_TICKS = 60          # let it hang properly first
FALL_START, FALL_END = 50, 130
OUT_DIR = "CodexConductor/Frames/opening_fall/"

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

L = unreal.LevelSequenceEditorBlueprintLibrary
L.open_level_sequence(unreal.EditorAssetLibrary.load_asset(SEQ))
L.set_current_time(FALL_START - 10)

OUT = unreal.Paths.project_saved_dir() + OUT_DIR
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(OUT + f)

rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.SceneCapture2D, unreal.Vector(-1400.0, 0.0, 150.0),
    unreal.Rotator(roll=0.0, pitch=14.0, yaw=0.0))
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
    sfx.set_editor_property("show_flag_name", fname); sfx.set_editor_property("enabled", on)
    flags.append(sfx)
c.set_editor_property("show_flag_settings", flags)
for h in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if "Camera + Shadow Figures" in h.get_actor_label() or h.get_class().get_name() == "InfinityStageShadowCatActor":
        c.hide_actor_components(h, True)

st = {"n": 0, "shot": 0, "handle": None, "cloths": []}

def tick(delta):
    try:
        st["n"] += 1
        if st["n"] == 3:
            for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
                for comp in a.get_components_by_class(unreal.ActorComponent):
                    if "Cloth" in comp.get_class().get_name() and abs(a.get_actor_location().x) < 600:
                        st["cloths"].append(comp)
            for cl in st["cloths"]:
                cl.set_simulate_in_editor(True)
                cl.set_editor_property("suspend_simulation", False)
            unreal.log("FALL_CLOTHS|%d" % len(st["cloths"]))
            if not st["cloths"]:
                raise StopIteration
        if st["n"] <= SETTLE_TICKS:
            return                                  # hang and settle, no capture
        # Drive the sequence through the drop, one frame per tick.
        f = FALL_START + (st["n"] - SETTLE_TICKS)
        if f > FALL_END:
            raise StopIteration
        L.set_current_time(f)
        c.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, "f%04d.png" % st["shot"])
        st["shot"] += 1
    except Exception:
        unreal.unregister_slate_post_tick_callback(st["handle"])
        for cl in st["cloths"]:
            try:
                cl.set_simulate_in_editor(False)
                cl.set_editor_property("suspend_simulation", True)
            except Exception:
                pass
        try:
            unreal.EditorLevelLibrary.destroy_actor(cap)
        except Exception:
            pass
        L.close_level_sequence()
        unreal.log("FALL_DONE|%d frames|%s" % (st["shot"], OUT))

st["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("FALL_CAPTURE_STARTED")
