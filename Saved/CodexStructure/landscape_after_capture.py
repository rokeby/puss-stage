"""Read-only captures (30 Sep) after the landscape block, from the three viewpoints that matter (the approach, the stop,
outside) at P02 and P03, plus the frame Gary needs most: P03's new oak floor from the cat's eye mid-passage. Rest state,
nothing posed; transient capture actors destroyed by reference in the same call. The P03 stop view reuses the exact
camera of Captures/Hangar_S3/S3_cam_00.png (02:35 today, wet ground) so the two form a before/after. Writes
Captures/LandscapeAfter/."""
import math
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "Captures", "LandscapeAfter")
LENS = 39.13     # 35 mm on Super 35, the passage camera


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    shots = []
    for n in (2, 3):
        cam = next(a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label())
        cc = cam.get_cine_camera_component()
        cam_fov = math.degrees(2.0 * math.atan(cc.get_editor_property("filmback").sensor_width / (2.0 * cc.get_editor_property("current_focal_length"))))
        yaw = cam.get_actor_rotation().yaw
        dock = unreal.Transform(location=unreal.Vector(cam.get_actor_location().x, cam.get_actor_location().y, 0.0), rotation=unreal.Rotator(0.0, 0.0, yaw))
        z = cam.get_actor_location().z
        views = [("approach_m25", unreal.Vector(-2500.0, 0.0, z), 0.0, LENS), ("approach_m10", unreal.Vector(-1000.0, 0.0, z), 0.0, LENS),
                 ("stop", unreal.Vector(0.0, 0.0, z), 0.0, cam_fov), ("stop_down15", unreal.Vector(0.0, 0.0, z), -15.0, cam_fov),
                 ("mid_passage", unreal.Vector(-5000.0, 0.0, z), -4.0, LENS)]
        over = unreal.Vector(-4000.0, -3500.0, 2500.0)
        for name, local, pitch, fov in views + [("outside", over, None, 70.0)]:
            loc = dock.transform_location(local)
            if pitch is None:
                rot = unreal.MathLibrary.find_look_at_rotation(loc, dock.transform_location(unreal.Vector(3000.0, 0.0, 0.0)))
            else:
                rot = unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw)
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
            try:
                comp = cap.capture_component2d
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", fov)
                comp.set_editor_property("capture_every_frame", False)
                for _ in range(2):
                    comp.capture_scene()
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"P0{n}_{name}.png")
                shots.append(f"P0{n}_{name}")
            finally:
                sub.destroy_actor(cap)
    left = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SceneCapture2D)]
    d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"LANDSCAPE_AFTER_OK|shots={len(shots)}|captures_left={left}|dirty={d[0]}+{d[1]}")


main()
