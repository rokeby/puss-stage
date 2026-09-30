"""Restore after p04_render_check.py: the Arrival's rest evaluation (60 s before Scene 4: pitch -90,
cache sample 0), then verify against BenchOriginals/p04_render_check.json. No save."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    root, arrival, cloth = by["S4 Hangar Root"], by["S4 Arrival"], by["P04 Backcloth (baked)"]
    before = root.root_component.get_editor_property("relative_rotation").pitch
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    start = next(s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene 4")).get_editor_property("start_frame").value
    del tr
    arrival.evaluate_at_master_frame(show, unreal.FrameTime(frame_number=unreal.FrameNumber(int(start - 60.0 * rate)), sub_frame=0.0))
    saved = json.load(open(os.path.join(HERE, "BenchOriginals", "p04_render_check.json")))
    back = root.root_component.get_editor_property("relative_rotation")
    gcc = cloth.get_component_by_class(unreal.GeometryCacheComponent)
    o, e = cloth.get_actor_bounds(False)
    ok = abs(back.pitch - saved["root_rot"][1]) < 1e-3 and all(bool(gcc.get_editor_property(k)) == v for k, v in saved["cloth"].items())
    d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"P04_RC_RESTORE|pitch {before:.3f}->{back.pitch:.3f}|cloth_z[{o.z - e.z:.0f},{o.z + e.z:.0f}]|restored={ok}|dirty={d[0]}+{d[1]}")


main()
