"""Read back the Scene 4 hangar by tag, and capture it.
- Views: from Scene 4's own establishing camera, the ghost light, and up at the
  lattice.
- Exposure: pinned like the hangar's volume (EV100 0.5, min = max), with Local
  Exposure neutral.
- Capture actors: transient ZZ_S4Capture_*, destroyed in a finally.
- Dirty: logged before and after.

Mutates nothing in the level. Lean: all work in main()."""
import math
import os

import unreal

TAG = "RigAtmos.Scene4Hangar"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "Captures")
EV = 0.5


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert c0 == 0, "content dirty"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    mine = [a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]]
    hinges = [a.get_actor_label() for a in mine if any(str(t).startswith(("Hinge|", "Fly|")) for t in a.get_editor_property("tags"))]
    cam = next(a for a in actors if isinstance(a, unreal.CineCameraActor) and "Scene 04" in a.get_actor_label())
    cc = cam.get_cine_camera_component()
    fb = cc.get_editor_property("filmback")
    fov = math.degrees(2.0 * math.atan(fb.sensor_width / (2.0 * cc.get_editor_property("current_focal_length"))))
    cy = 280000.0
    views = [("establishing", cam.get_actor_location(), cam.get_actor_rotation(), fov),
             ("ghost", unreal.Vector(300.0, cy + 500.0, 170.0), None, 60.0),
             ("lattice", unreal.Vector(0.0, cy, 170.0), unreal.Rotator(roll=0.0, pitch=30.0, yaw=0.0), 70.0)]
    ghost_at = unreal.Vector(1500.0, cy - 400.0, 150.0)
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    shots = []
    for name, loc, rot, f in views:
        if rot is None:
            rot = unreal.MathLibrary.find_look_at_rotation(loc, ghost_at)
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
        try:
            cap.set_actor_label(f"ZZ_S4Capture_{name}")
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", f)
            pp = comp.post_process_settings
            for k, v in (("auto_exposure_min_brightness", EV), ("auto_exposure_max_brightness", EV),
                         ("local_exposure_highlight_contrast_scale", 1.0), ("local_exposure_shadow_contrast_scale", 1.0)):
                pp.set_editor_property("override_" + k, True)
                pp.set_editor_property(k, v)
            comp.set_editor_property("post_process_settings", pp)
            comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"S4Hangar_{name}.png")
            shots.append(name)
        finally:
            sub.destroy_actor(cap)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"S4_HANGAR_CAPTURE_OK|tagged={len(mine)}|hinges={len(hinges)}|camera={cam.get_actor_label()}"
               f"|cam_loc={[round(v) for v in cam.get_actor_location().to_tuple()]}|fov={fov:.1f}|shots={shots}"
               f"|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
