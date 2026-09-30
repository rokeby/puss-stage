"""BENCH (restored; 30 Sep): does GC_CurtainBackcloth_P04 still contain something TALL after the fall?
Poses the cache through S4 Arrival (production path) at the hang (-6 s) and at 3.8 s after release
(-0.1 s), reads the component's bounds each time, and tries to count the cache's tracks. Originals
(root rotation, cloth flags) to BenchOriginals/ first; restore by the Arrival's rest evaluation;
verified against the file. No save."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    root, arrival, cloth = by["S4 Hangar Root"], by["S4 Arrival"], by["P04 Backcloth (baked)"]
    gcc = cloth.get_component_by_class(unreal.GeometryCacheComponent)
    r0 = root.root_component.get_editor_property("relative_rotation")
    path = os.path.join(HERE, "BenchOriginals", f"p04_cache_bounds_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    json.dump({"root_rot": [r0.roll, r0.pitch, r0.yaw], "cloth": {k: bool(gcc.get_editor_property(k)) for k in ("manual_tick", "running", "looping")}}, open(path, "w"))
    unreal.log(f"P04_BOUNDS_ORIGINALS|{path}")
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    start = next(s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene 4")).get_editor_property("start_frame").value
    del tr
    mt = lambda t: unreal.FrameTime(frame_number=unreal.FrameNumber(int(round(start + t * rate))), sub_frame=0.0)
    cache = gcc.get_editor_property("geometry_cache")
    tracks = "n/a"
    for prop in ("tracks", "Tracks"):
        try:
            tracks = len(cache.get_editor_property(prop))
            break
        except Exception as exc:  # noqa: BLE001
            tracks = f"not exposed ({exc.__class__.__name__})"
    out = []
    try:
        for t in (-6.0, -3.874, -2.0, -0.1):
            arrival.evaluate_at_master_frame(show, mt(t))
            b = gcc.get_editor_property("bounds") if False else None
            o, e = cloth.get_actor_bounds(False)
            ct = arrival.resolve_backcloth_time_at_master_frame(show, mt(t), float(gcc.get_duration()))
            out.append(f"t={t}:cache={ct:.3f}:z[{o.z - e.z:.0f},{o.z + e.z:.0f}]:x[{o.x - e.x:.0f},{o.x + e.x:.0f}]")
    finally:
        arrival.evaluate_at_master_frame(show, mt(-60.0))
    saved = json.load(open(path))
    back = root.root_component.get_editor_property("relative_rotation")
    ok = abs(back.pitch - saved["root_rot"][1]) < 1e-3
    d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"P04_BOUNDS|tracks={tracks}|{' '.join(out)}|restored={ok}|dirty_after={d[0]}+{d[1]}")


main()
