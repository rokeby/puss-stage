"""BENCH (30 Sep): what the TRANSPLANTED rise start (-3.567 s, no cloth in front) looks like at Scene 1, now nested.
Poses through S1 Arrival (production path; a transform, so a same-call capture is valid) along P01's approach:
the camera walks P01's last metres (tail 334 cm at 2.5 m/s, before that 3.0 m/s), level, 35 mm (39.13 deg).
Each frame is compared with the rest pose at the same camera position, so the change IS the rise.
Also checks the seam: the Arrival one tick before Scene 1 vs the rise channel at Scene time 0.
Originals (root rotation) to BenchOriginals/ first; restore by the Arrival's rest evaluation; verified against
the FILE. No save. Writes Captures/S1Transplant/. Lean: main()."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "S1Transplant")
ORIG = os.path.join(HERE, "BenchOriginals", "s1_transplant.json")
TIMES = (-3.567, -3.0, -2.5, -2.0, -1.5, -1.0, -0.5, -0.1)


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    root, arrival = by["S1 Hangar Root"], by["S1 Arrival"]
    cam = next(a for l, a in by.items() if l.startswith("Scene 1 ") and "Entry Handoff Camera" in l)
    stop = cam.get_actor_location()
    r0 = root.root_component.get_editor_property("relative_rotation")
    os.makedirs(os.path.dirname(ORIG), exist_ok=True)
    with open(ORIG, "w") as fh:
        json.dump({"root_rot": [r0.roll, r0.pitch, r0.yaw]}, fh)
        fh.flush()
        os.fsync(fh.fileno())
    unreal.log(f"S1_TRANSPLANT_ORIGINALS|{ORIG}")
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    start = next(s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene 1")).get_editor_property("start_frame").value
    del tr
    mt = lambda t: unreal.FrameTime(frame_number=unreal.FrameNumber(int(round(start + t * rate))), sub_frame=0.0)
    last = arrival.resolve_rotation_at_master_frame(show, unreal.FrameTime(frame_number=unreal.FrameNumber(start - 1), sub_frame=0.0))
    rise = unreal.load_asset("/Game/InfinityStage/RigAtmos/LS_S1_HangarRise")
    b = next(x for x in rise.get_bindings() if str(x.get_display_name()) == "S1 Hangar Root")
    trk = next(t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack))
    keys = [k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value / 30.0 for k in trk.get_sections()[0].get_all_channels()[4].get_keys()]
    u = -keys[0] / (keys[-1] - keys[0])
    at0 = -90.0 + 90.0 * (3 * u * u - 2 * u ** 3)
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    rows = []
    try:
        for t in TIMES:
            back = 250.0 * min(-t, 1.336) + 300.0 * max(-t - 1.336, 0.0)
            loc = unreal.Vector(stop.x - back, stop.y, stop.z)
            for state, when in (("rest", -60.0), ("rise", t)):
                arrival.evaluate_at_master_frame(show, mt(when))
                pitch = root.root_component.get_editor_property("relative_rotation").pitch
                cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, unreal.Rotator(0.0, 0.0, cam.get_actor_rotation().yaw), True)
                try:
                    comp = cap.capture_component2d
                    comp.set_editor_property("texture_target", rt)
                    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                    comp.set_editor_property("fov_angle", 39.13)
                    for _ in range(2):
                        comp.capture_scene()
                    unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"m{abs(t):05.3f}_{state}.png")
                finally:
                    sub.destroy_actor(cap)
                if state == "rise":
                    rows.append({"t": t, "camera_back_m": round(back / 100.0, 2), "pitch": round(pitch, 3)})
    finally:
        arrival.evaluate_at_master_frame(show, mt(-60.0))
    saved = json.load(open(ORIG))
    ok = abs(root.root_component.get_editor_property("relative_rotation").pitch - saved["root_rot"][1]) < 1e-3
    d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    json.dump({"rows": rows, "seam": {"arrival_last_tick": last.pitch if last else None, "channel_at_0": at0}}, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    unreal.log(f"S1_TRANSPLANT_OK|seam arrival {last.pitch if last else None:.3f} vs channel {at0:.3f}|restored={ok}|dirty_after={d[0]}+{d[1]}|{rows}")


main()
