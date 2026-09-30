"""BENCH (restored, nothing saved): does 20 cd on the lattice glow lights read in a
-15 deg look-down during the authored hold (+3 s)?

Rig (30 Sep): the ghost light is occluded by the box's own floor until about
+9.5 s, but the lattice sits outside the floor's shadow, with 9 of 24 bulbs in a
-15 deg look-down at +3 s. Its 24 glow lights ("S4 Lattice Glow r-c",
PointLights, candelas) are keyed to 0 until +4 s. The question is whether 20 cd
registers at the show's exposure.

STEPWISE (one MCP call per step):
  1. open LS_DevScene_04 in Sequencer and scrub to +3 s, so Rig's keys pose the
     box (no hand posing);
  2. read the hangar root's pitch; capture a CONTROL (the glow as keyed); set the
     24 glow lights to 20 cd; capture TESTS at -15 and -25 deg; restore every
     intensity to the value read; close Sequencer; verify the restore.
Captures from the Entry camera's position and yaw with no exposure override. At
the stop the camera is inside the hangar volume, where no override was proven
identical to the pinned EV (validate_exposure_blend.py, |diff| 0.00 at x 10668.5).
Transient capture actors. Nothing is saved.
Success marker: PUSS_LATTICE_GLOW_BENCH
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"
T_SECONDS = 3.0
TEST_CD = 20.0
GLOW_PREFIX = "S4 Lattice Glow "
ROOT_LABEL = "S4 Hangar Root"


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def capture(world, target, location, rotation, fov, out_dir, name):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation, True)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        component.set_editor_property("fov_angle", fov)
        for _ in range(2):
            component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        subsystem.destroy_actor(actor)


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "LatticeGlow")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "state.json")

    show = unreal.load_asset(SHOW_PATH)
    cue = [c for c in show.get_editor_property("cues")
           if str(c.get_editor_property("label")).startswith(SCENE_PREFIX)
           and "SCENE" in str(c.get_editor_property("type")).upper()][0]
    sequence = cue.get_editor_property("scene").get_editor_property("sequence")
    rate = sequence.get_display_rate()
    frame = sequence.get_playback_start() + int(round(T_SECONDS * rate.numerator / float(rate.denominator)))
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary

    if not os.path.exists(state_path):
        others = [p for p in dirty() if p != EXPECTED_WORLD]
        if others:
            raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")
        if sequencer.get_current_level_sequence():
            raise RuntimeError("Sequencer already open")
        sequencer.open_level_sequence(sequence)
        sequencer.set_current_time(frame)
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"frame": frame}, handle)
        unreal.log("PUSS_LATTICE_GLOW_STEP|opened|scrubbed_to=%d" % frame)
        return

    current = sequencer.get_current_level_sequence()
    if current is None or current.get_path_name() != sequence.get_path_name() or sequencer.get_current_time() != frame:
        raise RuntimeError("Sequencer is not at the bench frame; delete state.json and restart")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    root = [a for a in actors if a.get_actor_label() == ROOT_LABEL]
    root_pitch = root[0].root_component.get_editor_property("relative_rotation").pitch if root else None
    glows = [a for a in actors if a.get_actor_label().startswith(GLOW_PREFIX)]
    entry = [a for a in actors if isinstance(a, unreal.CineCameraActor)
             and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith(SCENE_PREFIX + " ")][0]
    del actors
    component = entry.get_cine_camera_component()
    location = component.get_world_location()
    yaw = entry.get_actor_rotation().yaw
    width = component.get_editor_property("filmback").get_editor_property("sensor_width")
    fov = math.degrees(2.0 * math.atan(width / (2.0 * component.get_editor_property("current_focal_length"))))
    target = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

    lights = [g.get_component_by_class(unreal.PointLightComponent) for g in glows]
    before = [float(l.get_editor_property("intensity")) for l in lights]
    # The originals go to a FILE before anything changes, so a crash between the
    # set and the restore still leaves the true values on disk (conductor, 30 Sep).
    originals_path = os.path.join(out_dir, "originals.json")
    with open(originals_path, "w", encoding="utf-8") as handle:
        json.dump({g.get_actor_label(): v for g, v in zip(glows, before)}, handle, indent=1)
    unreal.log("PUSS_LATTICE_GLOW_ORIGINALS|%s" % originals_path)
    restored = False
    try:
        capture(world, target, location, unreal.Rotator(roll=0.0, pitch=-15.0, yaw=yaw), fov, out_dir, "control_m15")
        for light in lights:
            light.set_intensity(TEST_CD)
        capture(world, target, location, unreal.Rotator(roll=0.0, pitch=-15.0, yaw=yaw), fov, out_dir, "glow20_m15")
        capture(world, target, location, unreal.Rotator(roll=0.0, pitch=-25.0, yaw=yaw), fov, out_dir, "glow20_m25")
    finally:
        for light, value in zip(lights, before):
            light.set_intensity(value)
        restored = all(abs(float(l.get_editor_property("intensity")) - v) < 1e-4 for l, v in zip(lights, before))
        sequencer.close_level_sequence()
        os.remove(state_path)
    report = {"t": T_SECONDS, "frame": frame, "root_pitch": root_pitch, "glow_lights": len(lights),
              "intensity_before": sorted(set(round(v, 3) for v in before)), "test_cd": TEST_CD,
              "restored": restored, "dirty_after": dirty()}
    with open(os.path.join(out_dir, "bench.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    unreal.log("PUSS_LATTICE_GLOW_BENCH|%s" % json.dumps(report))


main()
