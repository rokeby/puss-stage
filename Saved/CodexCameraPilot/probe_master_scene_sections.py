"""Read-only: how the Master plays each Scene sub-sequence (start, end, parameters). (30 Sep)

Before the Scene 3 play-through: the Master's Scene 3 section runs 585.64 s against a 160.375 s sequence
(memory: puss-cue97-scene3-anomaly), so Sequencer may play it time-scaled, and the time at which ClamCam1
(root frames 81-1501 at 24 fps) should take the view depends on that. Also checks the premise of the Scene 1
result (scene1_tail_view.json): that the Master plays LS_DevScene_01 1:1 from the transport's Scene 1 start.
Plain property reads only. Success marker: PUSS_MASTER_SCENE_SECTIONS
"""
import json
import os

import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def main():
    show = unreal.load_asset(SHOW_PATH)
    master = show.get_editor_property("managed_master_sequence")
    rows = []
    for track in master.find_tracks_by_type(unreal.MovieSceneSubTrack):
        for section in track.get_sections():
            sub = section.get_sequence()
            if sub is None or "DevScene" not in sub.get_name():
                continue
            row = {"sequence": sub.get_name(), "track": track.get_class().get_name(),
                   "start_s": section.get_start_frame_seconds(), "end_s": section.get_end_frame_seconds(),
                   "row_index": section.get_row_index(), "active": section.is_active(),
                   "sub_fps": sub.get_display_rate().numerator / float(sub.get_display_rate().denominator),
                   "sub_playback": [sub.get_playback_start(), sub.get_playback_end()]}
            try:
                params = section.get_editor_property("parameters")
                for name in ("time_scale", "start_frame_offset", "end_frame_offset", "first_loop_start_frame_offset",
                             "can_loop", "hierarchical_bias"):
                    try:
                        row[name] = str(params.get_editor_property(name))
                    except Exception as error:
                        row[name] = "unreadable: %s" % error
            except Exception as error:
                row["parameters"] = "unreadable: %s" % error
            rows.append(row)
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "probe_master_scene_sections.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=1)
    unreal.log("PUSS_MASTER_SCENE_SECTIONS|%s" % json.dumps(rows))


main()
