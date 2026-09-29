"""Read-only: the Scene 4 score's bindings (ids, parents, tracks) and
how the fold hosts it. It writes nothing. Plain property reads only: an earlier
version called SequencerTools.get_bound_objects with an open range, which asserts
(RangeBound.h:104) and crashed the editor on 29 Sep 18:41.
Success marker: PUSS_S4_SCORE_INSPECT"""

import json
import os

import unreal

SCORE_PATH = "/Game/InfinityStage/CameraScores/LS_S4_CameraScore"
FOLD_PATH = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"


def guid(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def main():
    score = unreal.load_asset(SCORE_PATH)
    fold = unreal.load_asset(FOLD_PATH)
    rows = []
    for binding in score.get_bindings():
        parent = binding.get_parent()
        rows.append({
            "name": str(binding.get_display_name()),
            "id": guid(binding.get_id()),
            "parent_id": guid(parent.get_id()) if parent is not None and parent.is_valid() else None,
            "tracks": [t.get_class().get_name() for t in binding.get_tracks()],
        })
    hosted = []
    for track in fold.find_tracks_by_type(unreal.MovieSceneSubTrack):
        for section in track.get_sections():
            sub = section.get_sequence()
            hosted.append({"track": str(track.get_display_name()),
                           "sequence": sub.get_path_name() if sub else None,
                           "range": [section.get_start_frame(), section.get_end_frame()]})
    report = {"bindings": rows, "fold_sub_tracks": hosted}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "inspect_scene4_score.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    unreal.log("PUSS_S4_SCORE_INSPECT|bindings=%d|hosted=%d" % (len(rows), len(hosted)))


main()
