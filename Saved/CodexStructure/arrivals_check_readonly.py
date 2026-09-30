"""Read-only: the five placed Arrivals as saved. Each carries its Scene cue and binding GUIDs and
its rise; the rise is referenced by the level only (never the Show or a Scene/Master sequence);
and each Arrival still declines two seconds before its Scene. Mutates nothing."""
import json

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def main():
    show = unreal.load_asset(SHOW)
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    starts = {str(s.get_editor_property("label")).split()[1]: s.get_editor_property("start_frame").value
              for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene ")}
    del tr
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    out = []
    for a in sub.get_all_level_actors():
        if isinstance(a, unreal.InfinityStageArrival):
            n = a.get_actor_label()[1]
            seq = a.get_editor_property("motion_sequence")
            path = seq.get_path_name().split(".")[0] if seq else None
            refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)] if path else []
            mt = unreal.FrameTime(frame_number=unreal.FrameNumber(int(starts[n] - 2.0 * rate)), sub_frame=0.0)
            rot = a.resolve_rotation_at_master_frame(show, mt)
            out.append({"label": a.get_actor_label(), "cue": a.get_editor_property("scene_cue_guid").to_string(),
                        "binding": a.get_editor_property("motion_binding_guid").to_string(), "rise": path,
                        "driven": a.get_editor_property("driven_actor").get_actor_label() if a.get_editor_property("driven_actor") else None,
                        "referencers": refs, "at_minus_2s": round(rot.pitch, 3) if rot is not None else "declined"})
    unreal.log(f"ARRIVALS_CHECK|{json.dumps(sorted(out, key=lambda r: r['label']))}")


main()
