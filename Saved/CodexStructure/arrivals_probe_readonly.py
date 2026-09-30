"""Read-only: for every Scene, the facts its Arrival needs, derived from the Show (never typed):
the Scene cue (label, GUID, sequence), the Passage that arrives there (the one whose last cue sits
just before the Scene cue), that Passage's end timing as the compiler builds it (last station, tail
distance and time, the end speed, the camera's total distance), the hangar's rise sequence and root
binding. Writes arrivals_probe.json. Mutates nothing."""
import json
import os

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "arrivals_probe.json")


def main():
    show = unreal.load_asset(SHOW)
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    cues = list(show.get_editor_property("cues"))
    ids = [c.get_editor_property("cue_guid").to_string() for c in cues]
    settings = list(show.get_editor_property("passage_settings"))
    by_last = {ids.index(s.get_editor_property("last_cue_guid").to_string()): s for s in settings}
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {a.get_actor_label() for a in sub.get_all_level_actors()}
    out = []
    for i, c in enumerate(cues):
        if c.get_editor_property("type") != unreal.InfinityCueType.SCENE:
            continue
        seq = c.get_editor_property("scene").get_editor_property("sequence")
        row = {"cue_index": i, "label": str(c.get_editor_property("label")), "guid": ids[i],
               "sequence": seq.get_path_name().split(".")[0] if seq else None}
        s = by_last.get(i - 1)
        if s:
            first = ids.index(s.get_editor_property("first_cue_guid").to_string())
            d = s.get_editor_property("lead_in_distance_cm")
            last_d = d
            for k in range(first, i - 1):
                last_d += cues[k].get_editor_property("wing_pair").get_editor_property("gap_to_next_cm")
            tail_d = s.get_editor_property("tail_distance_cm")
            tail_s = s.get_editor_property("tail_frames").value / rate
            pk = cues[i - 2].get_editor_property("wing_pair") if i - 2 >= first else None
            row.update({"passage_guid": s.get_editor_property("passage_guid").to_string(), "stations": i - first,
                        "last_station_cm": round(last_d, 2), "tail_cm": round(tail_d, 2), "tail_s": round(tail_s, 4),
                        "end_speed_cm_s": round(tail_d / tail_s, 3) if tail_s else None,
                        "last_interval_speed_cm_s": round(pk.get_editor_property("gap_to_next_cm") / (pk.get_editor_property("interval_to_next").value / rate), 3) if pk else None,
                        "camera_stop_cm": round(last_d + tail_d, 2)})
        n = None
        for k in range(1, 7):
            if row["label"].startswith(f"Scene {k}"):
                n = k
        if n:
            rise_path = f"/Game/InfinityStage/RigAtmos/LS_S{n}_HangarRise"
            rise = unreal.load_asset(rise_path) if unreal.EditorAssetLibrary.does_asset_exist(rise_path) else None
            b = next((b for b in rise.get_bindings() if str(b.get_display_name()) == f"S{n} Hangar Root"), None) if rise else None
            row.update({"scene": n, "rise": rise_path if rise else None, "root_binding": b.get_id().to_string() if b else None,
                        "root_actor": f"S{n} Hangar Root" in labels, "arrival_placed": f"S{n} Arrival" in labels})
        out.append(row)
    json.dump(out, open(OUT, "w"), indent=1)
    unreal.log(f"ARRIVALS_PROBE_OK|scenes={len(out)}")


main()
