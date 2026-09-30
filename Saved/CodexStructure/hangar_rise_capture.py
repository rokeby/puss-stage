"""Read-only capture of any scene's hangar rise (30 Sep). Opens LS_S{N}_HangarRise in
Sequencer, sets each moment (Scene 4's beats times the hangar's K, read from its record),
and captures two views: the dock camera (the Entry Handoff Camera, level) and a wide side
view placed from the box's own dimensions. No exposure override: the frame is what the
show renders (the hangar's pinned volume, or the passage's EV100 -3 outside it). The root
pitch is logged at every moment, and after closing Sequencer it must be back at -90.
Transient capture actors, destroyed in a finally; dirty must stay 0+0.
Scene from hangar_capture_mode.json ({"scene": N}). Writes Captures/Hangar_S{N}/.
Lean: all work in main()."""
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
FPS = 30
BEATS = (0.0, 6.0, 10.0, 16.0, 20.0, 24.0, 29.0)


def main():
    n = json.load(open(os.path.join(HERE, "hangar_capture_mode.json"), encoding="utf-8"))["scene"]
    rec = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))
    h, k = rec["hangar"], rec["k"]
    out = os.path.join(HERE, "Captures", f"Hangar_S{n}")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "dirty map"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    root = next(a for a in actors if a.get_actor_label() == f"S{n} Hangar Root")
    cam = next(a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label())
    cc = cam.get_cine_camera_component()
    fov = math.degrees(2.0 * math.atan(cc.get_editor_property("filmback").sensor_width / (2.0 * cc.get_editor_property("current_focal_length"))))
    yaw = cam.get_actor_rotation().yaw
    dock = unreal.Transform(location=unreal.Vector(cam.get_actor_location().x, cam.get_actor_location().y, 0.0),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    d, w, ht, apron = h["depth"], h["half_w"], h["height"], h["apron"]
    side = dock.transform_location(unreal.Vector(apron + d * 0.45, -(w + max(3000.0, 1.2 * d)), ht * 0.6))
    look = dock.transform_location(unreal.Vector(apron + d * 0.45, 0.0, -d * 0.15))
    views = (("cam", cam.get_actor_location(), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), fov),
             ("side", side, unreal.MathLibrary.find_look_at_rotation(side, look), 70.0))
    seq = unreal.load_asset(rec["sequence"])
    os.makedirs(out, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 960, 540, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    log, shots = [], []
    try:
        for beat in BEATS:
            t = beat * k
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(int(round(t * FPS)))
            unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            log.append(f"t={t:.1f}:root_pitch={root.root_component.get_editor_property('relative_rotation').pitch:.1f}")
            for name, loc, rot, f in views:
                cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
                try:
                    comp = cap.capture_component2d
                    comp.set_editor_property("texture_target", rt)
                    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                    comp.set_editor_property("fov_angle", f)
                    for _ in range(2):
                        comp.capture_scene()
                    fname = f"S{n}_{name}_{int(round(beat)):02d}.png"
                    unreal.RenderingLibrary.export_render_target(world, rt, out, fname)
                    shots.append(fname)
                finally:
                    sub.destroy_actor(cap)
    finally:
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    after = root.root_component.get_editor_property("relative_rotation").pitch
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"HANGAR_CAPTURE|S{n}|k={k:.3f}|{'|'.join(log)}|after_close_pitch={after:.1f}|shots={len(shots)}|dirty_after={c1}+{m1}")


main()
