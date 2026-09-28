"""Let the Opening's own spawned curtain SETTLE, then capture it.

Scrubbing Sequencer spawns the curtain but does not simulate it: the cloth is
authored suspended, so a scrubbed frame shows the rest pose. This opens the
sequence at the hold frame, un-suspends the spawned cloth, ticks the editor via a
Slate post-tick callback so the solver actually runs, captures, then re-suspends
and closes. Nothing is saved.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Chaos"
SETTLE_TICKS = 90
HOLD_FRAME = 40

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

L = unreal.LevelSequenceEditorBlueprintLibrary
L.open_level_sequence(unreal.EditorAssetLibrary.load_asset(SEQ))
L.set_current_time(HOLD_FRAME)

# The spawnable only exists once the editor has TICKED after set_current_time.
# Querying immediately finds nothing, so the lookup happens inside the callback.
cloths = []

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
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

state = {"n": 0, "handle": None}
def tick(delta):
    try:
        state["n"] += 1
        if state["n"] == 3 and not cloths:
            for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
                for comp in a.get_components_by_class(unreal.ActorComponent):
                    if "Cloth" in comp.get_class().get_name() and abs(a.get_actor_location().x) < 600:
                        cloths.append(comp)
                        unreal.log("SETTLE_FOUND|%s|x=%.0f" % (a.get_actor_label(), a.get_actor_location().x))
            for cl in cloths:
                cl.set_simulate_in_editor(True)
                cl.set_editor_property("suspend_simulation", False)
            unreal.log("SETTLE_CLOTHS|%d" % len(cloths))
            if not cloths:
                raise StopIteration
        if state["n"] in (1, 30, 60, SETTLE_TICKS):
            c.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, "SETTLE_t%03d.png" % state["n"])
            unreal.log("CAPTURE|SETTLE_t%03d" % state["n"])
        if state["n"] >= SETTLE_TICKS:
            raise StopIteration
    except Exception:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        for cl in cloths:
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
        unreal.log("SETTLE_DONE|%d ticks" % state["n"])

state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("SETTLE_STARTED")
