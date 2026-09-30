"""BENCH (30 Sep), multi-call, for Soft goods' discriminating tests on the "standing curtain":
  A: ONE pose (the Arrival at -0.1 s: bounds say a 0.84 m pile), then capture the same pose repeatedly
     with ONE persistent capture component, one capture per MCP call (the editor ticks between). If
     the curtain fades across captures, it is temporal history, not geometry.
  B: in the same state, a FRESH capture with temporal AA and anti-aliasing OFF (show flags), and a
     fresh AA-on control. If the curtain is gone with AA off, it is history.
Phases (p04_history_probe_mode.json {"phase": ...}): "pose" (originals to BenchOriginals/p04_history.json,
pose, spawn ZZ_P04HistoryProbe, capture A01), "again" (capture A02.., same component), "noaa" (test B),
"restore" (destroy the probe actor, Arrival rest evaluation, verify against the file). No save anywhere;
the ZZ_ label makes every save script refuse while the probe exists."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "P04HistoryProbe")
ORIG = os.path.join(HERE, "BenchOriginals", "p04_history.json")
PHASE = json.load(open(os.path.join(HERE, "p04_history_probe_mode.json")))["phase"]
LABEL = "ZZ_P04HistoryProbe"
LOC, ROT, FOV = unreal.Vector(10450.0 - 600.0, 240000.0, 180.0), unreal.Rotator(0.0, 0.0, 0.0), 60.0


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
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

    def shoot(comp, name):
        comp.set_editor_property("texture_target", rt)
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        comp.set_editor_property("fov_angle", FOV)
        comp.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)

    if PHASE == "pose":
        assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        assert LABEL not in by, "probe actor already exists"
        r0 = root.root_component.get_editor_property("relative_rotation")
        os.makedirs(os.path.dirname(ORIG), exist_ok=True)
        with open(ORIG, "w") as fh:
            json.dump({"root_rot": [r0.roll, r0.pitch, r0.yaw], "cloth": {k: bool(gcc.get_editor_property(k)) for k in ("manual_tick", "running", "looping")}}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        unreal.log(f"P04_HIST_ORIGINALS|{ORIG}")
        try:
            arrival.evaluate_at_master_frame(show, mt(-0.1))
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, LOC, ROT, True)
            cap.set_actor_label(LABEL)
            shoot(cap.capture_component2d, "A01.png")
        except Exception:
            arrival.evaluate_at_master_frame(show, mt(-60.0))
            raise
        o, e = cloth.get_actor_bounds(False)
        unreal.log(f"P04_HIST_POSED|bounds_z[{o.z - e.z:.0f},{o.z + e.z:.0f}]")
    elif PHASE == "again":
        n = len([f for f in os.listdir(OUT) if f.startswith("A")]) + 1
        shoot(by[LABEL].capture_component2d, f"A{n:02d}.png")
        o, e = cloth.get_actor_bounds(False)
        unreal.log(f"P04_HIST_AGAIN|A{n:02d}|bounds_z[{o.z - e.z:.0f},{o.z + e.z:.0f}]")
    elif PHASE == "repose":
        # Re-request the SAME cache time (the editor has ticked since the last request), fresh capture.
        n = len([f for f in os.listdir(OUT) if f.startswith("R")]) + 1
        arrival.evaluate_at_master_frame(show, mt(-0.1))
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, LOC, ROT, True)
        try:
            shoot(cap.capture_component2d, f"R{n:02d}.png")
        finally:
            sub.destroy_actor(cap)
        o, e = cloth.get_actor_bounds(False)
        unreal.log(f"P04_HIST_REPOSE|R{n:02d}|bounds_z[{o.z - e.z:.0f},{o.z + e.z:.0f}]")
    elif PHASE == "noaa":
        for name, off in (("B_fresh_aa_on.png", False), ("B_fresh_aa_off.png", True)):
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, LOC, ROT, True)
            try:
                comp = cap.capture_component2d
                if off:
                    comp.set_editor_property("show_flag_settings", [
                        unreal.EngineShowFlagsSetting(show_flag_name="TemporalAA", enabled=False),
                        unreal.EngineShowFlagsSetting(show_flag_name="AntiAliasing", enabled=False),
                        unreal.EngineShowFlagsSetting(show_flag_name="MotionBlur", enabled=False)])
                shoot(comp, name)
            finally:
                sub.destroy_actor(cap)
        unreal.log("P04_HIST_NOAA|done")
    else:
        if LABEL in by:
            sub.destroy_actor(by[LABEL])
        arrival.evaluate_at_master_frame(show, mt(-60.0))
        saved = json.load(open(ORIG))
        back = root.root_component.get_editor_property("relative_rotation")
        ok = abs(back.pitch - saved["root_rot"][1]) < 1e-3 and all(bool(gcc.get_editor_property(k)) == v for k, v in saved["cloth"].items())
        left = [a.get_actor_label() for a in sub.get_all_level_actors() if a.get_actor_label().startswith("ZZ_")]
        d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
        unreal.log(f"P04_HIST_RESTORE|restored={ok}|zz_left={left}|dirty={d[0]}+{d[1]}")


main()
