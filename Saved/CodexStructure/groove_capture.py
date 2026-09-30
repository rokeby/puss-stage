"""Capture the steel grooves for Gary's floor decision, after groove_material_apply.py.
- "slot": low, 60 cm above the floor, looking along one chariot slot's run, from
  3 m back. Shows whether the steel reads as LET INTO the floor or as a stripe on
  it.
- "floor": standing on P01's cat line, eye height, looking down the route across
  several slots (for the A-versus-C board surface decision).
- "rhythm": raised 4.5 m on the cat line, looking down the route over several
  wing stations. Are the grooves the floor's feature or an accent, with slots
  starting SlotInboardCm (150) inside each wing?

Also logs the groove plates' top relative to the board top near the chosen slot,
the recess depth, as a number beside the picture. Transient capture actors,
destroyed in a finally; manual exposure EV 1.0, like the other P01 captures.
Dirty logged before and after. Mutates nothing. Lean: all work in main().
"""
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "Captures")
EV = 1.0


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert c0 == 0, "content dirty"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    p01 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
    s01 = next(a for a in actors if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == p01)
    ptf = p01.get_actor_transform()
    grooves = [c for c in s01.get_components_by_class(unreal.InstancedStaticMeshComponent)
               if "InfinityStage.Structure.Grooves" in [str(t) for t in c.get_editor_property("component_tags")]]
    boards = [c for c in s01.get_components_by_class(unreal.InstancedStaticMeshComponent) if c.get_name().startswith("StructureGround")]
    assert grooves and grooves[0].get_instance_count() > 0, "no groove plates on Structure 01"
    # The groove plate nearest a point a few stations in, just off the cat line.
    target = unreal.MathLibrary.transform_location(ptf, unreal.Vector(1500.0, 300.0, 0.0))
    best = None
    for c in grooves:
        for i in range(c.get_instance_count()):
            tf = c.get_instance_transform(i, True)
            d = (tf.translation - target).length()
            if best is None or d < best[0]:
                best = (d, tf)
    tf = best[1]
    run = unreal.MathLibrary.transform_direction(tf, unreal.Vector(1.0, 0.0, 0.0))
    run = run / run.length()
    centre = tf.translation
    # Recess: the plate tops near this slot, against the nearest board top.
    plate_tops = []
    for c in grooves:
        for i in range(c.get_instance_count()):
            t = c.get_instance_transform(i, True)
            if (t.translation - centre).length() < 200.0:
                plate_tops.append(round(unreal.MathLibrary.transform_location(t, unreal.Vector(0.0, 0.0, 50.0)).z, 1))
    board_top = None
    for c in boards:
        o, e, _ = unreal.SystemLibrary.get_component_bounds(c)
        if abs(centre.x - o.x) <= e.x and abs(centre.y - o.y) <= e.y:
            board_top = round(o.z + e.z, 1)
    eye = unreal.MathLibrary.transform_location(ptf, unreal.Vector(600.0, 0.0, 160.0))
    ahead = unreal.MathLibrary.transform_location(ptf, unreal.Vector(2600.0, 0.0, 0.0))
    # Look DOWN the slot from above its inner end (the 29 Sep first framing, from
    # inboard at 60 cm, looked straight into the timber under the wing).
    half_len = tf.scale3d.x * 50.0
    ends = (centre - run * half_len, centre + run * half_len)
    route_line = unreal.MathLibrary.transform_location(ptf, unreal.Vector(unreal.MathLibrary.inverse_transform_location(ptf, centre).x, 0.0, 0.0))
    inner = min(ends, key=lambda e: (e - route_line).length())
    outward = (centre - inner) / max(1.0, (centre - inner).length())
    slot_cam = inner - outward * 80.0 + unreal.Vector(0.0, 0.0, 120.0)
    centre = inner + outward * 200.0
    run = outward
    # "rhythm": raised on the cat line, looking down the route over several wing
    # stations, so the slots read as a receding rhythm (feature or accent?).
    high = unreal.MathLibrary.transform_location(ptf, unreal.Vector(300.0, 0.0, 450.0))
    far = unreal.MathLibrary.transform_location(ptf, unreal.Vector(3600.0, 0.0, 0.0))
    views = (("slot", slot_cam, unreal.MathLibrary.find_look_at_rotation(slot_cam, centre), 60.0),
             ("floor", eye, unreal.MathLibrary.find_look_at_rotation(eye, ahead), 70.0),
             ("rhythm", high, unreal.MathLibrary.find_look_at_rotation(high, far), 55.0))
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    for name, loc, rot, fov in views:
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
        try:
            cap.set_actor_label(f"ZZ_GrooveCapture_{name}")
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", fov)
            pp = comp.post_process_settings
            pp.set_editor_property("override_auto_exposure_method", True)
            pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
            pp.set_editor_property("override_auto_exposure_bias", True)
            pp.set_editor_property("auto_exposure_bias", EV + (1.0 if name == "slot" else 0.0))
            comp.set_editor_property("post_process_settings", pp)
            comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"Grooves_{name}.png")
        finally:
            sub.destroy_actor(cap)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"GROOVE_CAPTURE_OK|slot_centre={[round(v) for v in centre.to_tuple()]}|plate_tops={sorted(set(plate_tops))}"
               f"|board_top={board_top}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
