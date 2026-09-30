"""TRANSIENT preview of Gary's floor-rise (29 Sep late): "the floor of the hangar,
where the opening lamp sits, would itself fold upwards into view, implying it was
hidden, folded behind the horizon".

Proposal:
- Floor slab 2 (20-40 m, carrying the ghost light) and slab 3 (40-60 m) hang DOWN
  from their near-edge hinges (-90 deg, far end below the floor plane) and rise to
  flat.
- The ghost light rides slab 2 up.
- The whole arc stays below z 0, so it can never cross the camera.

This script does NOT build it. It:
1. poses the two hinges at the proposal's key angles;
2. temporarily attaches the ghost light's stand, bulb and light to slab 2's hinge,
   so they ride it;
3. captures each pose from the Scene 4 Entry Handoff Camera;
4. restores everything exactly, and asserts it.
The map is left dirty with no net change; clear it with level_verified_save.py.
Practicals stay off, which is their rest; this shows the floor and the ghost
light only. Lean: all work in main().
"""
import os

import unreal

TAG = "RigAtmos.Scene4Hangar"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "Captures", "FloorRise")
# (label, slab 2 pitch, slab 3 pitch): -90 hangs the far end down, 0 is flat.
POSES = (("t0_before", -90.0, -90.0), ("t1_slab2_rising", -60.0, -90.0), ("t2_slab2_high", -25.0, -90.0),
         ("t3_slab2_flat_slab3_rising", 0.0, -50.0), ("t4_both_flat", 0.0, 0.0))
GHOST = ("S4 Ghost Light Stand", "S4 Ghost Light Bulb", "S4 Ghost Light")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "content dirty"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "map already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    mine = {a.get_actor_label(): a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]}
    h2, h3 = mine["S4 Hangar Floor 2 Hinge"], mine["S4 Hangar Floor 3 Hinge"]
    cam = next(a for a in actors if "Scene 4" in a.get_actor_label() and "Entry Handoff Camera" in a.get_actor_label())
    # Plain floats: a struct wrapper here tracked the LIVE rotation (29 Sep), so the
    # "restore" restored the last preview pose and its check passed trivially.
    orig_rot = {}
    for h in (h2, h3):
        r = h.root_component.get_editor_property("relative_rotation")
        orig_rot[h.get_actor_label()] = (float(r.roll), float(r.pitch), float(r.yaw))
    orig_ghost = {g: (tuple(float(v) for v in mine[g].get_actor_location().to_tuple()), None, mine[g].get_attach_parent_actor())
                  for g in GHOST}
    assert all(v[2] is None for v in orig_ghost.values()), "the ghost light is already attached to something"
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    shots = []
    try:
        for g in GHOST:
            mine[g].attach_to_actor(h2, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                                    unreal.AttachmentRule.KEEP_WORLD, False)
        for name, p2, p3 in POSES:
            h2.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=p2, yaw=0.0), False, True)
            h3.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=p3, yaw=0.0), False, True)
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, cam.get_actor_location(), cam.get_actor_rotation(), True)
            try:
                cap.set_actor_label(f"ZZ_FloorRise_{name}")
                comp = cap.capture_component2d
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", 37.5)
                pp = comp.post_process_settings
                for k, v in (("auto_exposure_min_brightness", 0.5), ("auto_exposure_max_brightness", 0.5),
                             ("local_exposure_highlight_contrast_scale", 1.0), ("local_exposure_shadow_contrast_scale", 1.0)):
                    pp.set_editor_property("override_" + k, True)
                    pp.set_editor_property(k, v)
                comp.set_editor_property("post_process_settings", pp)
                comp.capture_scene()
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"FloorRise_{name}.png")
                shots.append(name)
            finally:
                sub.destroy_actor(cap)
    finally:
        # Restore exactly: hinges to their rest rotation, the ghost light off the slab.
        for h in (h2, h3):
            ro, pi, ya = orig_rot[h.get_actor_label()]
            h.set_actor_relative_rotation(unreal.Rotator(roll=ro, pitch=pi, yaw=ya), False, True)
        for g in GHOST:
            mine[g].detach_from_actor(unreal.DetachmentRule.KEEP_WORLD, unreal.DetachmentRule.KEEP_WORLD,
                                      unreal.DetachmentRule.KEEP_WORLD)
    bad = []
    for h in (h2, h3):
        r, o = h.root_component.get_editor_property("relative_rotation"), orig_rot[h.get_actor_label()]
        if max(abs(r.roll - o[0]), abs(r.pitch - o[1]), abs(r.yaw - o[2])) > 0.01:
            bad.append(f"{h.get_actor_label()} rot {r}")
    for g, (loc, rot, _) in orig_ghost.items():
        a = mine[g]
        if max(abs(a.get_actor_location().to_tuple()[i] - loc[i]) for i in range(3)) > 0.05 or a.get_attach_parent_actor() is not None:
            bad.append(f"{g} at {a.get_actor_location()} (was {loc})")
    unreal.log(f"S4_FLOOR_RISE_PREVIEW|shots={shots}|restored={'OK' if not bad else bad}"
               f"|dirty_maps={len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}")


main()
