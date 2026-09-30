"""Read-only: does an Interaction's camera-cut binding GUID also exist in the MASTER sequence?

Soft goods' frame test (30 Sep): entering Interaction 1, tick 0 shows the stalls
view (Sequencer's own cut, evaluated inside the Master), tick 1 shows a different
camera for one frame, and tick 2 is the stalls again. The transport claims one
frame late (TG_PostUpdateWork). ClaimSceneCameraCut resolves the cut's binding
through the ROOT player (Player->GetBoundObjects) without the sub-sequence's
context, which looks the GUID up among the Master's own bindings. This lists,
for every Interaction and Scene sequence, its cut sections' binding GUIDs and
names, whether each GUID also names a binding in the Master (and what that
binding is called), and which stretches of its PLAYBACK RANGE no cut covers:
a jump into one finds no camera to claim (Soft goods' probe, 30 Sep: Scene 1's
tail left the player controller at the origin). Plain property reads only: no SequencerTools helpers.
Success marker: PUSS_CUT_BINDING_PROBE
"""

import json
import os

import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def guid(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def all_bindings(sequence):
    out = {}
    for binding in sequence.get_bindings():
        out[guid(binding.get_id())] = str(binding.get_display_name())
    return out


def main():
    show = unreal.load_asset(SHOW_PATH)
    master = show.get_editor_property("managed_master_sequence")
    master_bindings = all_bindings(master)
    rows = []
    for cue in show.get_editor_property("cues"):
        label = str(cue.get_editor_property("label"))
        if not (label.startswith("Interaction") or label.startswith("Scene")):
            continue
        sequence = cue.get_editor_property("scene").get_editor_property("sequence")
        if sequence is None:
            continue
        own = all_bindings(sequence)
        cuts = []
        for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
            for section in track.get_sections():
                binding_id = section.get_camera_binding_id()
                g = guid(binding_id.get_editor_property("guid"))
                cuts.append({
                    "start": section.get_start_frame(), "end": section.get_end_frame(),
                    "binding_guid": g, "name_in_own_sequence": own.get(g),
                    "ALSO_IN_MASTER_AS": master_bindings.get(g),
                })
        start, end = sequence.get_playback_start(), sequence.get_playback_end()
        # Uncovered stretches of the playback range: where a jump finds no cut and,
        # with no other rule, the transport claims no camera (dev grid at the origin).
        gaps, cursor = [], start
        for c in sorted(cuts, key=lambda c: c["start"]):
            if c["start"] > cursor:
                gaps.append([cursor, c["start"]])
            cursor = max(cursor, c["end"])
        if cursor < end:
            gaps.append([cursor, end])
        rate = sequence.get_display_rate()
        rows.append({"cue": label, "sequence": sequence.get_path_name().split(".")[0], "cuts": cuts,
                     "playback": [start, end], "fps": rate.numerator / float(rate.denominator),
                     "uncovered": gaps})
    collisions = [(r["cue"], c["name_in_own_sequence"], c["ALSO_IN_MASTER_AS"]) for r in rows for c in r["cuts"] if c["ALSO_IN_MASTER_AS"]]
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "probe_interaction_cut_binding.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"master": master.get_path_name(), "master_binding_count": len(master_bindings),
                   "rows": rows, "collisions": collisions}, handle, indent=1, ensure_ascii=False)
    uncovered = [(r["cue"], r["uncovered"]) for r in rows if r["uncovered"]]
    unreal.log("PUSS_CUT_BINDING_PROBE|cues=%d|master_bindings=%d|collisions=%d|uncovered=%d"
               % (len(rows), len(master_bindings), len(collisions), len(uncovered)))


main()
