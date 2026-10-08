"""Clam close-ups in PIE (read-only for the level: everything is spawned in the PIE world and destroyed).
Two calls, because a capture right after a transport jump can be a STALE frame (memory: geometrycache traps):
  CLAMSHOT_PHASE="SCRUB"   pause + scrub the Master to Scene 3 at CLAMSHOT_FRACTION -> CLAMSHOT_SCRUB_OK
  CLAMSHOT_PHASE="CAPTURE" SceneCapture2D x3 aimed at "S3 PearlClam Pearl" (no exposure override: the show's own
                           exposure, memory: capture-exposure convention) -> Saved/CodexConductor/Captures/<run>/
Markers CLAMSHOT_*|run=<id>. Needs an active PIE (conductor_pie_begin). Nothing is saved.
"""
import datetime
import json
import math
import os

PHASE = globals().get("CLAMSHOT_PHASE", "SCRUB")
FRACTION = float(globals().get("CLAMSHOT_FRACTION", 0.95))
SHOTS = (("a_0deg", 0.0, 25.0, 120.0), ("b_120deg", 120.0, 15.0, 110.0), ("c_240deg_close", 240.0, 30.0, 75.0))


def main():
    import unreal
    run = "CLAMSHOT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log_error("CLAMSHOT_FAILED|run=%s|no PIE world" % run)
        return
    if PHASE == "SCRUB":
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1:
            unreal.log_error("CLAMSHOT_FAILED|run=%s|show roots %d" % (run, len(roots)))
            return
        root = roots[0]
        segs = [s for s in list(root.transport.segments)
                if s.type == unreal.InfinityCueType.SCENE and (str(s.label) == "Scene 3" or str(s.label).startswith("Scene 3 "))]
        if len(segs) != 1:
            unreal.log_error("CLAMSHOT_FAILED|run=%s|Scene 3 segments %d" % (run, len(segs)))
            return
        a, b = int(segs[0].start_frame.value), int(segs[0].end_frame.value)
        f = int(a + (b - a) * FRACTION)
        root.sequence_player.pause()
        ok = root.transport.scrub_to_master_frame(unreal.FrameNumber(f))
        unreal.log("CLAMSHOT_SCRUB_OK|run=%s|frame=%d|seg=%d..%d|ok=%s" % (run, f, a, b, ok))
        return
    pearl = None
    for act in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor):
        if act.get_actor_label() == "S3 PearlClam Pearl":
            pearl = act
    if pearl is None:
        unreal.log_error("CLAMSHOT_FAILED|run=%s|pearl not found in PIE world" % run)
        return
    tgt = pearl.get_actor_location()
    hidden = bool(pearl.is_hidden_ed()) if hasattr(pearl, "is_hidden_ed") else None
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexConductor", "Captures", run)
    os.makedirs(out, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    rows = []
    for name, yaw_off, pitch_down, dist in SHOTS:
        # camera on a circle around the pearl (yaw_off from world +X), elevated pitch_down degrees, looking at it
        yaw, el = math.radians(yaw_off), math.radians(pitch_down)
        loc = unreal.Vector(tgt.x + dist * math.cos(el) * math.cos(yaw),
                            tgt.y + dist * math.cos(el) * math.sin(yaw),
                            tgt.z + dist * math.sin(el))
        rot = unreal.MathLibrary.find_look_at_rotation(loc, tgt)
        xf = unreal.Transform(location=loc, rotation=rot, scale=unreal.Vector(1, 1, 1))
        cap = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(world, unreal.SceneCapture2D, xf)
        cap = unreal.GameplayStatics.finish_spawning_actor(cap, xf)   # PIE world only: the editor map is not touched
        try:
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", 40.0)
            comp.set_editor_property("capture_every_frame", False)
            comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, out, name + ".png")
            p = os.path.join(out, name + ".png")
            rows.append({"shot": name, "loc": [loc.x, loc.y, loc.z], "bytes": os.path.getsize(p) if os.path.exists(p) else 0})
        finally:
            cap.destroy_actor()
    unreal.log("CLAMSHOT_CAPTURE_OK|run=%s|pearl=%.0f,%.0f,%.0f|hidden_ed=%s|dir=%s|%s"
               % (run, tgt.x, tgt.y, tgt.z, hidden, out, json.dumps(rows)))


main()
