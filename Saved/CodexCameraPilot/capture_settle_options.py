"""The settle before a Scene, as pictures: P04's last 2.5 s into Scene 4, four settle lengths side by side.

Gary (30 Sep): the cat's bob is not needed "in that moment between passages". Measured the same day: the
camera walks at a constant ~250 cm/s up to the cut, so there is no such moment until the Passage end
settles. The mechanism (declaration-proven, MovieSceneInfinityPassageTrack.cpp:318-367): SpeedMultiplier is
normalised per span between pins, and the Passage end is a pin, so a settle arrives at the SAME place at the
SAME moment and is paid for by walking slightly quicker earlier in the span.

Nothing is authored. Each option is simulated on the REAL route: at a moment tau seconds before the end, a
linear settle of length T leaves r = v * tau^2 / (2T) cm to go (tau <= T), else v * (tau - T/2). With the
measured constant speed, that is the authored pose at "equivalent time before end" r / v, read from the
Camera Pilot's GetPassageCameraPose (the rig's own evaluation, UN-BOBBED: the bob is not shown in any
option). After the end, every option shows the Scene 4 Entry camera, still. The world (lights, hangar)
follows the REAL time: the Master is scrubbed to each frame, stepwise (pose change -> a later call).
Exposure is pinned the validated way at EV100 -3, the passage's look. At the current look the hangar volume
blacks out the last metre (Gary's A1), which would hide the settle.

GROUND GUARD (the conductor, 30 Sep: the landscapes were deleted and floors are not rebuilt yet): a downward
trace from the camera at the first and last frame. No hit is recorded as UNKNOWN, not fine, and the composer
will not write the Gary-facing file while any is UNKNOWN.

Run the same request until PUSS_SETTLE_OPTIONS_DONE. Captures: Captures/Settle/. Refuses while PIE runs,
while content or maps are dirty, or while ZZ_ actors exist. Sequencer closes at the end.
"""
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
PASSAGE_LABEL = "Passage 4"
SCENE_PREFIX = "Scene 4 "
SETTLES_S = (0.0, 0.5, 1.0, 2.0)          # 0.0 = as now: full speed into the cut
BEFORE_S, AFTER_S, FPS = 2.5, 0.5, 25
EV100 = -3.0
TICKS_PER_S = 24000.0
WALK_CM_PER_S = 250.0                     # measured in PIE at P04's end, 30 Sep: 246-256 cm/s
STATE_VERSION = 1


def unwrap(result, count):
    """UE Python returns out-params as a tuple, or None when a bool UFUNCTION returns false."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    return result


def remaining_equivalent_s(tau, settle):
    """Seconds-before-end of the un-settled pose that has the settled cat's distance to go."""
    if tau <= 0.0:
        return 0.0
    if settle <= 0.0:
        return tau
    return tau * tau / (2.0 * settle) if tau <= settle else tau - settle / 2.0


def dirty():
    return ([p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
            + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def capture(world, location, rotation, fov, out_dir, name):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    target = unreal.RenderingLibrary.create_render_target2d(world, 960, 540, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    actor = subsystem.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation, True)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        component.set_editor_property("fov_angle", fov)
        post = component.post_process_settings
        for key, value in (("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM),
                           ("auto_exposure_min_brightness", EV100), ("auto_exposure_max_brightness", EV100),
                           ("auto_exposure_bias", 0.0)):
            post.set_editor_property("override_" + key, True)
            post.set_editor_property(key, value)
        component.set_editor_property("post_process_settings", post)
        for _ in range(2):
            component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        subsystem.destroy_actor(actor)


def ground_below(world, location, ignore):
    """The label of what a 6 m downward trace hits, or 'UNKNOWN' (no hit, or the trace could not be read)."""
    try:
        result = unreal.SystemLibrary.line_trace_single(
            world, location, location - unreal.Vector(0.0, 0.0, 600.0),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignore, unreal.DrawDebugTrace.NONE, True)
        hit = result[1] if isinstance(result, tuple) else result
        if hit is None:                   # a bool UFUNCTION returning false gives None in UE Python
            return "UNKNOWN (no hit within 6 m)"
        # break_hit_result has a documented order; a struct's to_tuple follows its declaration order.
        fields = unreal.GameplayStatics.break_hit_result(hit)
        if not fields[0]:
            return "UNKNOWN (no blocking hit within 6 m)"
        actor = fields[9]
        return "%s at %.0f cm" % (actor.get_actor_label() if actor else "?", fields[3])
    except Exception as error:
        return "UNKNOWN (%s)" % error


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "Settle")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "state.json")
    show = unreal.load_asset(SHOW_PATH)
    master = show.get_editor_property("managed_master_sequence")
    library = unreal.InfinityStageCameraPilotLibrary
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary
    passage = next(p for p in show.get_editor_property("passage_settings")
                   if str(p.get_editor_property("label")) == PASSAGE_LABEL)
    guid = passage.get_editor_property("passage_guid")
    rate = master.get_display_rate()
    ticks_per_display = TICKS_PER_S * rate.denominator / float(rate.numerator)

    if not os.path.exists(state_path):
        if dirty():
            raise RuntimeError(f"Refusing: packages dirty {dirty()}")
        if [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_actor_label().startswith("ZZ_")]:
            raise RuntimeError("Refusing: ZZ_ actors present")
        if sequencer.get_current_level_sequence():
            raise RuntimeError("Sequencer already open")
        frame_range = unwrap(library.get_passage_frame_range(show, guid), 2)
        if frame_range is None:
            raise RuntimeError(f"{PASSAGE_LABEL} has no frame range")
        end_tick = int(frame_range[1])
        steps = [round(-BEFORE_S + i / FPS, 4) for i in range(int(round((BEFORE_S + AFTER_S) * FPS)) + 1)]
        plan = [{"t": t, "world_display_frame": int(math.floor((end_tick + t * TICKS_PER_S) / ticks_per_display))}
                for t in steps]
        sequencer.open_level_sequence(master)
        sequencer.set_current_time(plan[0]["world_display_frame"])
        state = {"version": STATE_VERSION, "end_tick": end_tick, "plan": plan, "index": 0, "stills": [], "ground": {}}
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        unreal.log("PUSS_SETTLE_OPTIONS_STEP|opened Master|end_tick=%d|frames=%d" % (end_tick, len(plan)))
        return

    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)
    # Rig (30 Sep): PLAYING the Master dirties the map, and the only safe cure is a discard. If scrubbing it
    # does too, stop at the first step, not the 76th, and say so; never save.
    if dirty():
        sequencer.close_level_sequence()
        os.remove(state_path)
        unreal.log_error("PUSS_SETTLE_OPTIONS_ABORTED|packages went dirty during the run: %s|NOT saved; the cure is a "
                         "discard (close without saving), never a save" % dirty())
        raise RuntimeError("packages went dirty during the run")
    index = state["index"]
    step = state["plan"][index]
    if sequencer.get_current_time() != step["world_display_frame"]:
        raise RuntimeError("Sequencer is not at the expected frame; delete state.json and restart")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    rig = next(a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig"
               and a.get_editor_property("passage_actor") is not None
               and unreal.GuidLibrary.conv_guid_to_string(a.get_editor_property("passage_actor").get_editor_property("passage_guid"))
               == unreal.GuidLibrary.conv_guid_to_string(guid))
    entry = next(a for a in actors if isinstance(a, unreal.CineCameraActor)
                 and a.get_actor_label().startswith(SCENE_PREFIX) and "Entry Handoff" in a.get_actor_label())
    sensor = rig.get_editor_property("camera").get_editor_property("filmback").get_editor_property("sensor_width")
    del actors
    tau = -step["t"]
    for settle in SETTLES_S:
        if tau > 0.0:
            tick = int(round(state["end_tick"] - remaining_equivalent_s(tau, settle) * TICKS_PER_S))
            pose = unwrap(library.get_passage_camera_pose(show, guid, tick), 3)
            if pose is None:
                raise RuntimeError(f"{PASSAGE_LABEL} camera does not evaluate at {tick}")
            view, focal, _ = pose
            location, rotation = view.translation, view.rotation.rotator()
        else:
            component = entry.get_cine_camera_component()
            location, rotation = component.get_world_location(), component.get_world_rotation()
            focal = component.get_editor_property("current_focal_length")
        fov = math.degrees(2.0 * math.atan(sensor / (2.0 * focal)))
        name = "settle_%03.1fs_f%03d" % (settle, index)
        capture(world, location, rotation, fov, out_dir, name)
        remaining = remaining_equivalent_s(tau, settle)
        state["stills"].append({"settle": settle, "t": step["t"], "name": name,
                                "remaining_equiv_s": round(remaining, 4),
                                "to_go_cm": round(remaining * WALK_CM_PER_S, 1),
                                "xyz": [round(location.x, 1), round(location.y, 1), round(location.z, 1)]})
        if settle == 0.0 and index in (0, len(state["plan"]) - 1):
            state["ground"][str(index)] = ground_below(world, location, [rig, entry])

    if index + 1 < len(state["plan"]):
        state["index"] = index + 1
        sequencer.set_current_time(state["plan"][index + 1]["world_display_frame"])
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        unreal.log("PUSS_SETTLE_OPTIONS_STEP|%d/%d|t=%+.2f" % (index + 1, len(state["plan"]), step["t"]))
        return

    sequencer.close_level_sequence()
    os.remove(state_path)
    with open(os.path.join(out_dir, "settle_options.json"), "w", encoding="utf-8") as handle:
        json.dump({"stills": state["stills"], "ground": state["ground"], "settles_s": SETTLES_S, "fps": FPS,
                   "dirty_after": dirty()}, handle, indent=1)
    unreal.log("PUSS_SETTLE_OPTIONS_DONE|stills=%d|ground=%s|dirty_after=%s" % (len(state["stills"]), state["ground"], dirty()))


main()
