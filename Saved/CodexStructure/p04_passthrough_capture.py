"""BENCH (level activity, restored; 30 Sep): the P04 -> Scene 4 pass-through with the placed final11
backcloth, rendered at the show's exposure (no override).
Before Scene 4's first frame the frame is posed by the PRODUCTION path: S4 Arrival's
EvaluateAtMasterFrame (root pitch + cloth cache time), camera on P04's route walking 2.5 m/s to
its stop. From the cut on, LS_S4_HangarRise is scrubbed in Sequencer (its cloth section and root
keys), camera at the stop, including well past the section's end: the pile must HOLD its last
sample, not loop. Extra frames around the release (Soft goods: "watch the seam at release") and
the crossing (cloth top should be ~0.7 m under the lens). A side view shows the fall and pile.
Bench discipline: the root's relative rotation and the cloth component's manual_tick / running /
looping go to BenchOriginals/ (path logged) BEFORE anything is posed; restore = the Arrival's own
rest evaluation (60 s before the Scene: pitch -90, cache sample 0) after Sequencer closes, then
verified against the FILE. No save. Transient capture actors destroyed in a finally.
Writes Captures/P04PassThrough/ and p04_passthrough.json. Lean: main()."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "P04PassThrough")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RISE = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
CLOTH_LABEL = "P04 Backcloth (baked)"
STOP_X, Y, Z, SPEED, CLOTH_X, FPS = 10668.47, 240000.0, 180.0, 250.0, 10450.0, 30
BEFORE = (-6.0, -4.874, -4.074, -3.974, -3.874, -3.774, -3.674, -3.374, -3.0, -2.5, -2.0, -1.5, -0.874, -0.5, -0.1)
AFTER = (0.0, 0.5, 1.0, 1.53, 2.5, 4.0, 6.126, 6.5, 8.0, 12.0, 20.0)
SIDE = {-4.874, -3.874, -3.0, -2.0, -0.874, 0.0, 1.53, 6.126, 12.0}


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "dirty map"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    assert not any(a.get_actor_label().startswith("ZZ_") for a in actors), "bench actors (ZZ_) in the level"
    by = {a.get_actor_label(): a for a in actors}
    root, arrival, cloth = by["S4 Hangar Root"], by["S4 Arrival"], by[CLOTH_LABEL]
    gcc = cloth.get_component_by_class(unreal.GeometryCacheComponent)
    r0 = root.root_component.get_editor_property("relative_rotation")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs(os.path.join(HERE, "BenchOriginals"), exist_ok=True)
    orig_path = os.path.join(HERE, "BenchOriginals", f"p04_passthrough_{stamp}.json")
    orig = {"root_rot": [float(r0.roll), float(r0.pitch), float(r0.yaw)],
            "cloth": {k: bool(gcc.get_editor_property(k)) for k in ("manual_tick", "running", "looping")}}
    with open(orig_path, "w", encoding="utf-8") as fh:
        json.dump(orig, fh)
        fh.flush()
        os.fsync(fh.fileno())
    unreal.log(f"P04_PASS_ORIGINALS|{orig_path}")
    show = unreal.load_asset(SHOW)
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    start = next(s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene 4")).get_editor_property("start_frame").value
    del tr
    duration = float(gcc.get_duration())
    mt = lambda t: unreal.FrameTime(frame_number=unreal.FrameNumber(int(round(start + t * rate))), sub_frame=0.0)
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

    def capture(name, loc, rot, fov):
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
        try:
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", fov)
            for _ in range(3):
                comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
        finally:
            sub.destroy_actor(cap)

    side_loc = unreal.Vector(CLOTH_X + 200.0, Y - 1800.0, 350.0)
    side_rot = unreal.MathLibrary.find_look_at_rotation(side_loc, unreal.Vector(CLOTH_X + 150.0, Y, 250.0))
    rows = []
    restored = None
    try:
        for t in BEFORE:
            drove = arrival.evaluate_at_master_frame(show, mt(t))
            cache_t = arrival.resolve_backcloth_time_at_master_frame(show, mt(t), duration)
            pitch = root.root_component.get_editor_property("relative_rotation").pitch
            x = STOP_X + SPEED * t
            name = f"front_m{abs(t):06.3f}.png"
            capture(name, unreal.Vector(x, Y, Z), unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), 37.5)
            if t in SIDE:
                capture(f"side_m{abs(t):06.3f}.png", side_loc, side_rot, 60.0)
            rows.append({"t": t, "path": "arrival", "drove": bool(drove), "cache_s": round(cache_t, 4) if cache_t is not None else None,
                         "pitch": round(pitch, 3), "camera_x": round(x, 1), "to_cloth_m": round((CLOTH_X - x) / 100.0, 2), "file": name})
        seq = unreal.load_asset(RISE)
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
        try:
            for t in AFTER:
                unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(int(round(t * FPS)))
                unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
                pitch = root.root_component.get_editor_property("relative_rotation").pitch
                name = f"front_p{t:06.3f}.png"
                capture(name, unreal.Vector(STOP_X, Y, Z), unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), 37.5)
                capture(f"down_p{t:06.3f}.png", unreal.Vector(STOP_X, Y, Z), unreal.Rotator(roll=0.0, pitch=-35.0, yaw=0.0), 60.0)
                if t in SIDE:
                    capture(f"side_p{t:06.3f}.png", side_loc, side_rot, 60.0)
                rows.append({"t": t, "path": "sequencer", "pitch": round(pitch, 3), "camera_x": STOP_X, "file": name})
        finally:
            unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    finally:
        # Restore through the Arrival's own rest evaluation (well before the Scene: pitch -90, cache
        # sample 0), then verify against the FILE.
        arrival.evaluate_at_master_frame(show, mt(-60.0))
        saved = json.load(open(orig_path, encoding="utf-8"))
        back = root.root_component.get_editor_property("relative_rotation")
        restored = (abs(back.pitch - saved["root_rot"][1]) < 1e-3 and abs(back.yaw - saved["root_rot"][2]) < 1e-3 and abs(back.roll - saved["root_rot"][0]) < 1e-3
                    and all(bool(gcc.get_editor_property(k)) == v for k, v in saved["cloth"].items()))
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    json.dump({"scene4_start_frame": start, "rate": rate, "duration": duration, "rows": rows, "restored": restored},
              open(os.path.join(HERE, "p04_passthrough.json"), "w"), indent=1)
    unreal.log(f"P04_PASS_OK|frames={len(rows)}|restored={restored}|dirty_after={c1}+{m1}|"
               + " ".join(f"{r['t']}:{r.get('cache_s')}:{r['pitch']}" for r in rows))


main()
