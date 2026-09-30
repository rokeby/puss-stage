"""Capture the Scene 4 fold as a sequence of frames. It opens LS_S4_HangarFold in
Sequencer, sets each moment, and captures two views: Scene 4's own camera, and a
wide view from behind and above. Then it closes the sequence, which restores the
standing pose. The hinge poses are logged at every moment (proof the evaluation
landed), and the pose after closing is checked.

Captures pin exposure like the hangar volume (EV100 0.5), with Local Exposure
neutral. Transient capture actors, destroyed in a finally. Dirty is logged
before and after. Mutates nothing. Lean: all work in main()."""
import math
import os

import unreal

SEQ = globals().get("FOLD_SEQ", "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold")
TAG = "RigAtmos.Scene4Hangar"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "Captures", globals().get("FOLD_SUBDIR", "Fold"))
FPS, EV, CY = 30, 0.5, 240000.0   # CY: the docked site (Scene 4 Entry Handoff Camera)
MOMENTS = globals().get("FOLD_MOMENTS", (0.0, 2.0, 3.0, 5.0, 6.5, 8.5, 10.0, 11.0, 13.5, 15.5, 18.5, 20.5, 23.0))
PROBES = globals().get("FOLD_PROBES", ("S4 Hangar Floor 3 Hinge", "S4 Hangar Left Wall Hinge", "S4 Hangar Far Wall Hinge",
                                       "S4 Hangar Roof Hinge", "S4 Hangar Lattice Fly"))


def pose(mine):
    out = {}
    for p in PROBES:
        r = mine[p].get_actor_rotation()
        out[p.split()[2]] = [round(r.roll, 1), round(r.pitch, 1), round(mine[p].get_actor_location().z, 1)]
    return out


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert c0 == 0 and m0 == 0, f"dirty before {c0}+{m0}"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    mine = {a.get_actor_label(): a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]}
    # The camera the show cuts to in Scene 4 (0-24 s): the Entry Handoff Camera at the mouth.
    cam = next(a for a in actors if isinstance(a, unreal.CineCameraActor)
               and "Scene 4" in a.get_actor_label() and "Entry Handoff Camera" in a.get_actor_label())
    cc = cam.get_cine_camera_component()
    fov = math.degrees(2.0 * math.atan(cc.get_editor_property("filmback").sensor_width
                                       / (2.0 * cc.get_editor_property("current_focal_length"))))
    x0 = cam.get_actor_location().x
    wide_loc = unreal.Vector(x0 - 1600.0, CY - 2200.0, 1500.0)
    views = (("cam", cam.get_actor_location(), cam.get_actor_rotation(), fov),
             ("wide", wide_loc, unreal.MathLibrary.find_look_at_rotation(wide_loc, unreal.Vector(x0 + 3500.0, CY, 900.0)), 85.0))
    if globals().get("FOLD_PITCHES"):
        # Look & camera's tilt candidates: the handoff camera's position, pitched up.
        views = tuple((f"p{int(p)}", cam.get_actor_location(), unreal.Rotator(roll=0.0, pitch=float(p), yaw=cam.get_actor_rotation().yaw), fov)
                      for p in globals()["FOLD_PITCHES"])
    for name, loc, at, f in globals().get("FOLD_EXTRA_VIEWS", ()):
        views = views + ((name, unreal.Vector(*loc), unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*loc), unreal.Vector(*at)), f),)
    fb = cc.get_editor_property("filmback")
    unreal.log(f"S4_CAMERA|label={cam.get_actor_label()}|loc={[round(v, 1) for v in cam.get_actor_location().to_tuple()]}"
               f"|sensor_w={fb.sensor_width:.2f}|sensor_h={fb.sensor_height:.2f}|focal={cc.get_editor_property('current_focal_length'):.2f}"
               f"|hfov={fov:.2f}")
    seq = unreal.EditorAssetLibrary.load_asset(SEQ)
    assert seq, "fold sequence missing"
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    log = []
    try:
        for t in MOMENTS:
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(int(round(t * FPS)))
            unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            lamp = mine["S4 Practical L1"].get_component_by_class(unreal.SpotLightComponent).get_editor_property("intensity")
            log.append(f"t={t}:{pose(mine)}:L1={lamp:.0f}")
            for name, loc, rot, f in views:
                cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
                try:
                    cap.set_actor_label(f"ZZ_S4FoldCapture_{name}")
                    comp = cap.capture_component2d
                    comp.set_editor_property("texture_target", rt)
                    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                    comp.set_editor_property("fov_angle", f)
                    pp = comp.post_process_settings
                    ev = globals().get("FOLD_VIEW_EV", {}).get(name, EV)
                    for k, v in (("auto_exposure_min_brightness", ev), ("auto_exposure_max_brightness", ev),
                                 ("local_exposure_highlight_contrast_scale", 1.0),
                                 ("local_exposure_shadow_contrast_scale", 1.0)):
                        pp.set_editor_property("override_" + k, True)
                        pp.set_editor_property(k, v)
                    comp.set_editor_property("post_process_settings", pp)
                    comp.capture_scene()
                    unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"Fold_{name}_{int(t * 10):03d}.png")
                finally:
                    sub.destroy_actor(cap)
    finally:
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    after = pose(mine)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    for line in log:
        unreal.log(f"S4_FOLD_FRAME|{line}")
    unreal.log(f"S4_FOLD_CAPTURE_OK|moments={len(MOMENTS)}|after_close={after}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
