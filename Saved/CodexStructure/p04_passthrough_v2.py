"""BENCH (30 Sep), PIPELINED: the P04 -> Scene 4 pass-through with final11, re-shot so that no frame of the
Geometry Cache is stale. A GC jump requests a frame that decodes asynchronously; the proxy draws its last
decoded frame until the NEXT request after the decode (proved 30 Sep: same-call capture stale, later-call
re-pose correct). So each call RE-POSES the previous moment (same time), captures it, then requests the next.
Before the cut the pose comes from S4 Arrival.EvaluateAtMasterFrame (production path); from the cut on,
LS_S4_HangarRise stays open in Sequencer across calls and is re-scrubbed to the same time before capture.
Views: "cam" = the cat's lens (35 mm on Super 35, 39.13 deg) on P04's route, then at the stop; "near" = a
fixed observer 6 m downstage of the cloth line; "oblique" = a 3/4 view of the cloth line; "down" = the stop
looking down 35 deg (from the cut on).
Phases (p04_pass2_mode.json {"phase": "start"|"step"|"finish"}), state in p04_pass2_state.json. Originals
(root rotation, cloth flags) to BenchOriginals/p04_pass2.json BEFORE anything is posed. "finish" closes
Sequencer, restores by the Arrival's rest evaluation and verifies against the FILE. No save anywhere."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "P04PassThroughV2")
ORIG = os.path.join(HERE, "BenchOriginals", "p04_pass2.json")
STATE = os.path.join(HERE, "p04_pass2_state.json")
PHASE = json.load(open(os.path.join(HERE, "p04_pass2_mode.json")))["phase"]
RISE = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
STOP_X, Y, Z, SPEED, CLOTH_X, FPS, CAM_FOV = 10668.47, 240000.0, 180.0, 250.0, 10450.0, 30, 39.13
MOMENTS = [-6.0, -4.5, -3.974, -3.907, -3.874, -3.774, -3.5, -3.0, -2.5, -2.0, -1.674, -1.5, -1.2, -0.874, -0.5, -0.1,
           0.0, 1.53, 6.126, 8.0, 12.0, 20.0]


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    root, arrival, cloth = by["S4 Hangar Root"], by["S4 Arrival"], by["P04 Backcloth (baked)"]
    gcc = cloth.get_component_by_class(unreal.GeometryCacheComponent)
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    start = next(s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene 4")).get_editor_property("start_frame").value
    del tr
    mt = lambda t: unreal.FrameTime(frame_number=unreal.FrameNumber(int(round(start + t * rate))), sub_frame=0.0)
    lse = unreal.LevelSequenceEditorBlueprintLibrary

    def pose(t):
        if t < 0.0:
            arrival.evaluate_at_master_frame(show, mt(t))
        else:
            if not lse.get_current_level_sequence():
                lse.open_level_sequence(unreal.load_asset(RISE))
            lse.set_current_time(int(round(t * FPS)))
            lse.refresh_current_level_sequence()

    def capture_all(t):
        rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
        x = STOP_X + SPEED * min(t, 0.0)
        views = [("cam", unreal.Vector(x, Y, Z), unreal.Rotator(0.0, 0.0, 0.0), CAM_FOV),
                 ("near", unreal.Vector(CLOTH_X - 600.0, Y, Z), unreal.Rotator(0.0, 0.0, 0.0), 60.0)]
        ob = unreal.Vector(CLOTH_X - 1100.0, Y - 900.0, 450.0)
        views.append(("oblique", ob, unreal.MathLibrary.find_look_at_rotation(ob, unreal.Vector(CLOTH_X + 50.0, Y, 350.0)), 70.0))
        if t >= 0.0:
            views.append(("down", unreal.Vector(STOP_X, Y, Z), unreal.Rotator(roll=0.0, pitch=-35.0, yaw=0.0), 60.0))
        tag = f"{'m' if t < 0 else 'p'}{abs(t):06.3f}"
        for name, loc, rot, fov in views:
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
            try:
                comp = cap.capture_component2d
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", fov)
                for _ in range(2):
                    comp.capture_scene()
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"{name}_{tag}.png")
            finally:
                sub.destroy_actor(cap)
        o, e = cloth.get_actor_bounds(False)
        return {"t": t, "cloth_z_top": round(o.z + e.z, 1), "pitch": round(root.root_component.get_editor_property("relative_rotation").pitch, 3),
                "cache_s": arrival.resolve_backcloth_time_at_master_frame(show, mt(t), float(gcc.get_duration())) if t < 0 else None}

    def restore():
        if lse.get_current_level_sequence():
            lse.close_level_sequence()
        arrival.evaluate_at_master_frame(show, mt(-60.0))
        saved = json.load(open(ORIG))
        back = root.root_component.get_editor_property("relative_rotation")
        return abs(back.pitch - saved["root_rot"][1]) < 1e-3 and all(bool(gcc.get_editor_property(k)) == v for k, v in saved["cloth"].items())

    if PHASE == "start":
        assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        assert not lse.get_current_level_sequence(), "Sequencer open"
        r0 = root.root_component.get_editor_property("relative_rotation")
        os.makedirs(os.path.dirname(ORIG), exist_ok=True)
        with open(ORIG, "w") as fh:
            json.dump({"root_rot": [r0.roll, r0.pitch, r0.yaw], "cloth": {k: bool(gcc.get_editor_property(k)) for k in ("manual_tick", "running", "looping")}}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.makedirs(OUT, exist_ok=True)
        pose(MOMENTS[0])
        json.dump({"i": 0, "rows": []}, open(STATE, "w"))
        unreal.log(f"P04_PASS2_START|{ORIG}|requested {MOMENTS[0]}")
    elif PHASE == "step":
        st = json.load(open(STATE))
        i = st["i"]
        try:
            pose(MOMENTS[i])                      # RE-POSE the same moment: its frame has decoded since
            st["rows"].append(capture_all(MOMENTS[i]))
            if i + 1 < len(MOMENTS):
                pose(MOMENTS[i + 1])              # request the next one
        except Exception:
            ok = restore()
            unreal.log_error(f"P04_PASS2_FAILED_AND_RESTORED|restored={ok}")
            raise
        st["i"] = i + 1
        json.dump(st, open(STATE, "w"), indent=1)
        unreal.log(f"P04_PASS2_STEP|{i + 1}/{len(MOMENTS)}|{st['rows'][-1]}")
    else:
        ok = restore()
        d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
        unreal.log(f"P04_PASS2_FINISH|restored={ok}|dirty={d[0]}+{d[1]}|sequencer_open={bool(lse.get_current_level_sequence())}")


main()
