"""BENCH (30 Sep), two-phase, for "is the tall curtain after the fall a stale render or another object?".
PHASE "pose" (P04_RC_PHASE=pose): originals (root rotation, cloth flags) to BenchOriginals/p04_render_check.json,
  then pose via S4 Arrival at -0.1 s (cache 4.774 s: bounds say a 0.84 m pile), capture far observer
  normally AND with the backcloth hidden from the capture, in the SAME frame as the pose; leave posed.
PHASE "capture": (the editor has ticked since) capture the same two views again, then restore by the
  Arrival's rest evaluation and verify against the file. No save in either phase."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "P04RenderCheck")
ORIG = os.path.join(HERE, "BenchOriginals", "p04_render_check.json")
PHASE = json.load(open(os.path.join(HERE, "p04_render_check_mode.json")))["phase"]


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

    def capture(name, hide):
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(10450.0 - 1500.0, 240000.0, 180.0), unreal.Rotator(0.0, 0.0, 0.0), True)
        try:
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", 37.5)
            if hide:
                comp.hide_actor_components(cloth, False)
            for _ in range(3):
                comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
        finally:
            sub.destroy_actor(cap)

    if PHASE == "pose":
        assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        r0 = root.root_component.get_editor_property("relative_rotation")
        os.makedirs(os.path.dirname(ORIG), exist_ok=True)
        with open(ORIG, "w") as fh:
            json.dump({"root_rot": [r0.roll, r0.pitch, r0.yaw], "cloth": {k: bool(gcc.get_editor_property(k)) for k in ("manual_tick", "running", "looping")}}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        unreal.log(f"P04_RC_ORIGINALS|{ORIG}")
        arrival.evaluate_at_master_frame(show, mt(-0.1))
        o, e = cloth.get_actor_bounds(False)
        try:
            capture("sameframe_normal.png", False)
            capture("sameframe_clothhidden.png", True)
        except Exception:
            arrival.evaluate_at_master_frame(show, mt(-60.0))   # never leave it posed on a failure
            raise
        unreal.log(f"P04_RC_POSED|bounds_z[{o.z - e.z:.0f},{o.z + e.z:.0f}]|left posed; run phase capture next")
    else:
        o, e = cloth.get_actor_bounds(False)
        try:
            capture("nextcall_normal.png", False)
            capture("nextcall_clothhidden.png", True)
        finally:
            arrival.evaluate_at_master_frame(show, mt(-60.0))
        saved = json.load(open(ORIG))
        back = root.root_component.get_editor_property("relative_rotation")
        ok = abs(back.pitch - saved["root_rot"][1]) < 1e-3
        d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
        unreal.log(f"P04_RC_DONE|bounds_z_at_capture[{o.z - e.z:.0f},{o.z + e.z:.0f}]|restored={ok}|dirty_after={d[0]}+{d[1]}")


main()
