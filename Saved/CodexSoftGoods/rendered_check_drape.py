"""Rendered check of a placed drape from its stalls seat (30 Sep; the last gate before Gary sees it in PIE).

One ACTION per MCP call, from rendered_check_drape_mode.json:
  {"action": "open",    "cue": "Opening — Curtain", "camera": "Opening — Stalls Camera"}   open the cue's sequence in Sequencer
  {"action": "pose",    "frame": 20}                        set the Sequencer time (display frame). Pose TWICE per frame,
                                                             in separate calls: a GeometryCache decodes asynchronously and a
                                                             capture after a single jump shows the previous frame.
  {"action": "capture", "frame": 20, "tag": "hold_a"}       a fresh SceneCapture2D at the camera, NO exposure override,
                                                             1920x1080, to Captures/<cue>_<frame>_<tag>.png. Refuses if the
                                                             Sequencer time is not `frame`.
  {"action": "close"}                                        close Sequencer and report the dirty packages
Hidden: the camera rigs' bodies and the shadow cat (primitives only). One ZZ_TransientCapture per still, destroyed at
once. Nothing is saved. Logs PUSS_SOFTGOODS_RENDER_CHECK|... Crash rules: everything inside main().
"""
import json
import math
import os

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
STATE = os.path.join(HERE, "rendered_check_drape_state.json")


def dirty():
    return sorted([p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
                  + [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def show_flags():
    flags = []
    for name, on in (("VolumetricFog", True), ("Editor", False), ("BillboardSprites", False)):
        s = unreal.EngineShowFlagsSetting()
        s.set_editor_property("show_flag_name", name)
        s.set_editor_property("enabled", on)
        flags.append(s)
    return flags


def main():
    with open(os.path.join(HERE, "rendered_check_drape_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    act = cfg["action"]
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        return unreal.log("PUSS_SOFTGOODS_RENDER_CHECK|refused: PIE is running")
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        return unreal.log("PUSS_SOFTGOODS_RENDER_CHECK|refused: unexpected world")
    seqlib = unreal.LevelSequenceEditorBlueprintLibrary
    if act == "open":
        show = unreal.load_asset(SHOW)
        cue = next(c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == cfg["cue"])
        seq = cue.get_editor_property("scene").get_editor_property("sequence")
        seqlib.open_level_sequence(seq)
        state = {"cue": cfg["cue"], "camera": cfg["camera"], "sequence": seq.get_path_name(), "dirty_at_open": dirty()}
        with open(STATE, "w", encoding="utf-8") as h:
            json.dump(state, h, indent=1)
        del show, cue, seq
        return unreal.log(f"PUSS_SOFTGOODS_RENDER_CHECK|opened|{state['sequence']}|dirty={state['dirty_at_open']}")
    with open(STATE, encoding="utf-8") as h:
        state = json.load(h)
    current = seqlib.get_current_level_sequence()
    if act == "close":
        seqlib.close_level_sequence()
        return unreal.log(f"PUSS_SOFTGOODS_RENDER_CHECK|closed|dirty={dirty()}|dirty_at_open={state['dirty_at_open']}")
    if current is None or current.get_path_name() != state["sequence"]:
        return unreal.log(f"PUSS_SOFTGOODS_RENDER_CHECK|refused: Sequencer is not on {state['sequence']}")
    if act == "pose":
        seqlib.set_current_time(int(cfg["frame"]))
        return unreal.log(f"PUSS_SOFTGOODS_RENDER_CHECK|posed|{cfg['frame']}")
    if act == "capture":
        if seqlib.get_current_time() != int(cfg["frame"]):
            return unreal.log(f"PUSS_SOFTGOODS_RENDER_CHECK|refused: time {seqlib.get_current_time()} != {cfg['frame']}")
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        cams = [a for a in actors if isinstance(a, unreal.CineCameraActor) and a.get_actor_label() == state["camera"]]
        if len(cams) != 1:
            return unreal.log(f"PUSS_SOFTGOODS_RENDER_CHECK|refused: {len(cams)} cameras labelled {state['camera']}")
        comp = cams[0].get_cine_camera_component()
        width = comp.get_editor_property("filmback").get_editor_property("sensor_width")
        fov = math.degrees(2.0 * math.atan(width / (2.0 * comp.get_editor_property("current_focal_length"))))
        hidden = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
                  or a.get_class().get_name() == "InfinityStageShadowCatActor"]
        target = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080,
                                                               unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
        out_dir = os.path.join(HERE, "RenderCheck")
        os.makedirs(out_dir, exist_ok=True)
        name = f"{state['cue'].split(' ')[0]}{state['cue'].split(' ')[1] if state['cue'].startswith('Interaction') else ''}" \
               f"_f{int(cfg['frame']):04d}_{cfg['tag']}"
        cap = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, comp.get_world_location(),
                                                                comp.get_world_rotation())
        try:
            cap.set_actor_label("ZZ_TransientCapture")
            c = cap.capture_component2d
            c.set_editor_property("texture_target", target)
            c.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            c.set_editor_property("fov_angle", fov)
            c.set_editor_property("capture_every_frame", False)
            c.set_editor_property("capture_on_movement", False)
            c.set_editor_property("show_flag_settings", show_flags())
            for a in hidden:
                c.hide_actor_components(a, True)
            c.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
        finally:
            unreal.EditorLevelLibrary.destroy_actor(cap)
        del actors, cams, comp, hidden
        return unreal.log(f"PUSS_SOFTGOODS_RENDER_CHECK|captured|{name}.png|fov={fov:.2f}")


main()
