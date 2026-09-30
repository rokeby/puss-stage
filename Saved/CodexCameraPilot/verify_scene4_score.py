"""Prove the Scene 4 score evaluates end to end, STEPWISE (one MCP call per step).

LS_DevScene_04 hosts Rig's LS_S4_HangarRise (v2), which hosts LS_S4_CameraScore. This
opens the Scene sequence in Sequencer. Each call reads the Entry Handoff
Camera's component pitch at the time the previous call scrubbed to, compares it
with the smoothstep the flat-tangent keys predict, and captures a TRUE still
from the camera's actual view (no exposure override). Then it scrubs
on. Run the same request until PUSS_S4_SCORE_VERIFIED.

Plain property reads only; no SequencerTools helpers (see the crash memory).
LEVEL ACTIVITY: one ZZ_TransientCapture per still, destroyed at once. Nothing is
saved. Sequencer closes on the last step, which restores the camera.
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"
# Scene 4 v2 (30 Sep): post-landing only; the rise is the dog's (Dog Gaze), so the base stays level.
KEYS = [(0.0, 0.0), (18.8, 0.0), (22.0, 30.0), (24.8, 30.0), (29.6, 0.0)]
BEATS = [(10.0, "rise_dog_owned"), (18.0, "lights_level"), (20.4, "swing_rising"), (23.0, "swing_held"),
         (27.2, "lattice_down"), (29.3, "settle")]
TOLERANCE_DEG = 0.5
STATE_VERSION = 3


def expected_pitch(t):
    for (t0, p0), (t1, p1) in zip(KEYS, KEYS[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0)
            return p0 + (p1 - p0) * (3 * u * u - 2 * u * u * u)
    return KEYS[-1][1]


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def show_flags():
    flags = []
    for name, on in (("VolumetricFog", True), ("Editor", False), ("BillboardSprites", False)):
        setting = unreal.EngineShowFlagsSetting()
        setting.set_editor_property("show_flag_name", name)
        setting.set_editor_property("enabled", on)
        flags.append(setting)
    return flags


def capture(world, target, location, rotation, fov, hidden_actors, out_dir, name):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        component.set_editor_property("fov_angle", fov)
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        component.set_editor_property("show_flag_settings", show_flags())
        # No post-process override: the global volume applies itself (30 Sep finding).
        for hidden in hidden_actors:
            component.hide_actor_components(hidden, True)
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)
    path = os.path.join(out_dir, name + ".png")
    return os.path.getsize(path) if os.path.exists(path) else 0


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")

    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "Scene4Score")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "verify_state.json")
    state = None
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)

    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(SCENE_PREFIX)
            and "SCENE" in str(c.get_editor_property("type")).upper()]
    sequence = cues[0].get_editor_property("scene").get_editor_property("sequence")
    rate = sequence.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    start_frame = sequence.get_playback_start()
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary

    def frame_for(index):
        return start_frame + int(round(BEATS[index][0] * fps))

    if state is None or state.get("version") != STATE_VERSION:
        others = [p for p in dirty() if p != EXPECTED_WORLD]
        if others:
            raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")
        sequencer.open_level_sequence(sequence)
        sequencer.set_current_time(frame_for(0))
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"version": STATE_VERSION, "index": 0, "rows": []}, handle)
        unreal.log("PUSS_S4_VERIFY_STEP|opened|scrubbed_to=%d" % frame_for(0))
        return

    index = state["index"]
    current = sequencer.get_current_level_sequence()
    if current is None or current.get_path_name() != sequence.get_path_name():
        raise RuntimeError("Sequencer is not open on the Scene 4 sequence; delete verify_state.json and restart")
    if sequencer.get_current_time() != frame_for(index):
        raise RuntimeError(f"Sequencer at {sequencer.get_current_time()}, expected {frame_for(index)}")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    entries = [a for a in actors if isinstance(a, unreal.CineCameraActor)
               and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith(SCENE_PREFIX + " ")]
    hidden = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
              or a.get_class().get_name() == "InfinityStageShadowCatActor"]
    del actors
    component = entries[0].get_cine_camera_component()
    measured = component.get_editor_property("relative_rotation").pitch
    actor_pitch = entries[0].get_actor_rotation().pitch
    t, tag = BEATS[index]
    expected = expected_pitch(t)
    lens_width = component.get_editor_property("filmback").get_editor_property("sensor_width")
    fov = math.degrees(2.0 * math.atan(lens_width / (2.0 * component.get_editor_property("current_focal_length"))))
    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    name = "S4score_t%05.2f_%s" % (t, tag)
    size = capture(world, target, component.get_world_location(), component.get_world_rotation(),
                   fov, hidden, out_dir, name)
    row = {"t": t, "beat": tag, "expected": round(expected, 3), "measured": round(measured, 3),
           "actor_pitch": round(actor_pitch, 3), "ok": abs(measured - expected) <= TOLERANCE_DEG
           and abs(actor_pitch) < 0.01, "still": name, "bytes": size}
    state["rows"].append(row)
    unreal.log("PUSS_S4_VERIFY_BEAT|%s" % json.dumps(row))

    if index + 1 < len(BEATS):
        sequencer.set_current_time(frame_for(index + 1))
        state["index"] = index + 1
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        return

    sequencer.close_level_sequence()
    restored = component.get_editor_property("relative_rotation").pitch
    os.remove(state_path)
    rows = state["rows"]
    report = {"rows": rows, "all_ok": all(r["ok"] for r in rows), "restored_pitch_after_close": round(restored, 3),
              "dirty_after": dirty()}
    with open(os.path.join(out_dir, "verify.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    unreal.log("PUSS_S4_SCORE_VERIFIED|all_ok=%s|restored=%.3f|measured=%s|dirty_after=%s"
               % (report["all_ok"], restored, [r["measured"] for r in rows], report["dirty_after"]))


main()
