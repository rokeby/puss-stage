"""Validate Rig's exposure-blend sheet (p04_exposure_blend_capture.py) before it goes to Gary.

Rig priced options A/B/C by computing the EV at each camera position and pinning
it in the capture (Histogram, min = max = EV). For option A ("as it is") at x
10100 and 10450 (weight 0, EV -3) and at x 10668.5 (inside the hangar volume,
EV 0.5), the pinned EV equals what the show's own volumes give, so a capture
with NO exposure override at those positions must match Rig's A frames. If it
does, the pinning method reproduces the show and the B and C frames can be
trusted. Same camera as Rig: y 240000, z 180, level, hfov 37.5, 960x540, two
capture passes. Transient capture actors; nothing is saved.
Success marker: PUSS_EXPOSURE_BLEND_VALIDATE
"""

import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
POSITIONS = (10100.0, 10450.0, 10668.5)
Y, Z = 240000.0, 180.0


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        raise RuntimeError("Sequencer is open")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "Captures", "ExposureValidate")
    os.makedirs(out, exist_ok=True)
    target = unreal.RenderingLibrary.create_render_target2d(world, 960, 540, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    for x in POSITIONS:
        actor = subsystem.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(x, Y, Z), unreal.Rotator(0.0, 0.0, 0.0), True)
        try:
            actor.set_actor_label("ZZ_TransientCapture")
            component = actor.capture_component2d
            component.set_editor_property("texture_target", target)
            component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            component.set_editor_property("fov_angle", 37.5)
            # No post-process override: the level's own volumes decide the exposure.
            for _ in range(2):
                component.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, target, out, "NoOverride_x%d.png" % int(x))
        finally:
            subsystem.destroy_actor(actor)
    unreal.log("PUSS_EXPOSURE_BLEND_VALIDATE|positions=%s" % (POSITIONS,))


main()
