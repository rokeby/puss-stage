"""Read-only: camera-cut coverage and binding for every Scene and Sequence cue.

Soft goods' frame test (30 Sep): entering Interaction 1, tick 0 shows the stalls
view (Sequencer's own cut, evaluated inside the Master), tick 1 shows a different
camera for one frame, and tick 2 is the stalls again. The transport claims one
frame late (TG_PostUpdateWork). ClaimSceneCameraCut resolves the cut's binding
through the ROOT player (Player->GetBoundObjects) without the sub-sequence's
context, which looks the GUID up among the Master's own bindings. This lists,
for every enabled non-Passage cue, its cut sections' binding GUIDs and names,
whether each GUID also names a binding in the Master (and what that binding is
called), and which stretches of its PLAYBACK RANGE no cut covers.

Why coverage (Soft goods' probe, 30 Sep): a jump into a Scene or Sequence frame
with no cut of its own, on a cue with no retain and no opening reveal, resolves
NoRuleForSegment (ResolveHandover) and claims no camera. Scene 1's tail left the
player controller at the origin. So each row says which rule, if any, covers an
uncovered stretch. Also listed: each cut's completion mode (what Sequencer does
when the last cut ends in continuous play), and the cut tracks of nested
sub-sequences and shots (Soft goods' question: can LS_Animals_1's own cuts take
over under a parent Entry cut?). Frames are display-rate frames of the sequence
named. Plain property reads only: no SequencerTools helpers.
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


def completion(section):
    try:
        return str(section.get_completion_mode())
    except Exception as error:  # the getter's name is unverified in 5.8
        return "unreadable: %s" % error


def span(section, start, end):
    return (section.get_start_frame() if section.has_start_frame() else start,
            section.get_end_frame() if section.has_end_frame() else end)


def cut_sections(sequence):
    out = []
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        out.extend(track.get_sections())
    return out


def uncovered(cuts, start, end):
    gaps, cursor = [], start
    for a, b in sorted(cuts):
        if a > cursor:
            gaps.append([cursor, min(a, end)])
        cursor = max(cursor, b)
    if cursor < end:
        gaps.append([cursor, end])
    return [g for g in gaps if g[1] > g[0]]


def nested(sequence):
    """Sub-sequence and shot sections one level down, with their own cut tracks."""
    out, seen = [], set()
    for track_type in (unreal.MovieSceneCinematicShotTrack, unreal.MovieSceneSubTrack):
        for track in sequence.find_tracks_by_type(track_type):
            if track.get_path_name() in seen:
                continue
            seen.add(track.get_path_name())
            for section in track.get_sections():
                sub = section.get_sequence()
                if sub is None:
                    continue
                s0, s1 = sub.get_playback_start(), sub.get_playback_end()
                out.append({
                    "track": track.get_class().get_name(),
                    "sequence": sub.get_path_name().split(".")[0],
                    "active": section.is_active(),
                    "in_parent": list(span(section, None, None)),
                    "sub_playback": [s0, s1],
                    "sub_cuts": [{"span": list(span(c, s0, s1)), "active": c.is_active(),
                                  "completion": completion(c)} for c in cut_sections(sub)],
                })
    return out


def main():
    show = unreal.load_asset(SHOW_PATH)
    master = show.get_editor_property("managed_master_sequence")
    master_bindings = all_bindings(master)
    rows = []
    for cue in show.get_editor_property("cues"):
        cue_type = str(cue.get_editor_property("type"))
        if not cue.get_editor_property("enabled") or "WING_PAIR" in cue_type.upper():
            continue
        label = str(cue.get_editor_property("label"))
        scene = cue.get_editor_property("scene")
        retain = bool(scene.get_editor_property("retain_previous_camera"))
        curtain = str(scene.get_editor_property("curtain_mode"))
        # ResolveHandover's order: a cut wins; then an opening reveal; then retain; else no rule.
        rule_without_cut = ("opening_reveal" if "OPENING_REVEAL" in curtain.upper()
                            else "retain" if retain else None)
        sequence = scene.get_editor_property("sequence")
        if sequence is None:
            rows.append({"cue": label, "type": cue_type, "sequence": None, "retain": retain,
                         "curtain_mode": curtain, "rule_without_cut": rule_without_cut})
            continue
        start, end = sequence.get_playback_start(), sequence.get_playback_end()
        own = all_bindings(sequence)
        cuts = []
        for section in cut_sections(sequence):
            g = guid(section.get_camera_binding_id().get_editor_property("guid"))
            a, b = span(section, start, end)
            cuts.append({
                "start": a, "end": b, "active": section.is_active(), "completion": completion(section),
                "binding_guid": g, "name_in_own_sequence": own.get(g),
                "ALSO_IN_MASTER_AS": master_bindings.get(g),
            })
        gaps = uncovered([(c["start"], c["end"]) for c in cuts if c["active"]], start, end)
        rate = sequence.get_display_rate()
        rows.append({"cue": label, "type": cue_type, "sequence": sequence.get_path_name().split(".")[0],
                     "retain": retain, "curtain_mode": curtain, "rule_without_cut": rule_without_cut,
                     "camera_owner": str(scene.get_editor_property("camera_owner")),
                     "playback": [start, end], "fps": rate.numerator / float(rate.denominator),
                     "cuts": cuts, "uncovered": gaps,
                     "NO_RULE_STRETCHES": gaps if rule_without_cut is None else [],
                     "nested": nested(sequence)})
    collisions = [(r["cue"], c["name_in_own_sequence"], c["ALSO_IN_MASTER_AS"])
                  for r in rows for c in r.get("cuts", []) if c["ALSO_IN_MASTER_AS"]]
    no_rule = [(r["cue"], r["NO_RULE_STRETCHES"]) for r in rows if r.get("NO_RULE_STRETCHES")]
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "probe_interaction_cut_binding.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"master": master.get_path_name(), "master_binding_count": len(master_bindings),
                   "rows": rows, "collisions": collisions, "no_rule": no_rule},
                  handle, indent=1, ensure_ascii=False)
    unreal.log("PUSS_CUT_BINDING_PROBE|cues=%d|master_bindings=%d|collisions=%d|no_rule=%s"
               % (len(rows), len(master_bindings), len(collisions),
                  ["%s %s" % (label, stretches) for label, stretches in no_rule]))


main()
