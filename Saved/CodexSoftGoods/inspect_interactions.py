"""READ-ONLY (29 Sep): is Interaction 3 still different from the others? Gary's run-through: "no curtain came down; the
sequence simply stopped", filed as downstream of the stale Master (fixed 12:56). Compare all five Interaction sequences
and the Closing: the rig binding, its spawn range, CurtainProgress and bCurtainActive keys, the camera-cut track,
marked frames (the hidden-changeover marker), the playback range and display rate; plus the Show cue fields that
drive the covered handoff, and each cue's compiled segment. Writes nothing; everything inside main()."""
import json
import os

import unreal

SEQS = ["LS_Interaction_01_WashingTheBoy", "LS_Interaction_02_Turnips", "LS_Interaction_03_ForgetsHisName",
        "LS_Interaction_04_GetsAName", "LS_Interaction_05_BecomesKing", "LS_Closing_Curtain"]


def keys_of(section):
    out = []
    for ch in section.get_all_channels():
        try:
            ks = ch.get_keys()
            if ks:
                out.append([(k.get_time().frame_number.value, k.get_value()) for k in ks[:8]])
        except Exception:  # noqa: BLE001
            pass
    return out


def describe(path):
    seq = unreal.load_asset(path)
    row = {"sequence": path.split("/")[-1], "range": [seq.get_playback_start(), seq.get_playback_end()],
           "rate": f"{seq.get_display_rate().numerator}/{seq.get_display_rate().denominator}", "bindings": [],
           "root_tracks": [t.get_class().get_name() for t in seq.get_tracks()]}
    try:
        row["marked_frames"] = [(m.get_editor_property("label"), m.get_editor_property("frame_number").value)
                                for m in seq.get_marked_frames()]
    except Exception as exc:  # noqa: BLE001
        row["marked_frames_err"] = str(exc)
    for b in seq.get_bindings():
        brow = {"name": str(b.get_display_name()), "tracks": {}}
        tmpl = b.get_object_template()
        if tmpl is not None:
            brow["template"] = tmpl.get_class().get_name()
            for prop in ("curtain_distance_cm", "follow_player_camera", "curtain_active"):
                try:
                    brow[prop] = tmpl.get_editor_property(prop)
                except Exception:  # noqa: BLE001
                    pass
        for t in b.get_tracks():
            secs = []
            for s in t.get_sections():
                secs.append({"range": [s.get_start_frame() if s.has_start_frame() else None,
                                       s.get_end_frame() if s.has_end_frame() else None], "active": s.is_active(),
                             "keys": keys_of(s)})
            brow["tracks"][str(t.get_display_name())] = secs
        row["bindings"].append(brow)
    return row


def main():
    base = "/Game/InfinityStage/Interactions/"
    report = {"sequences": [describe(base + n) for n in SEQS]}
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    cues = []
    for i, cue in enumerate(show.get_editor_property("cues")):
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence")
        if not seq or seq.get_name() not in SEQS:
            continue
        row = {"index": i, "label": str(cue.get_editor_property("label")), "sequence": seq.get_name()}
        for prop in ("sequence_owns_curtain", "curtain_mode", "retain_previous_camera", "reveal_next_passage_when_covered",
                     "curtain_entry_transition_frames", "curtain_hold_frames", "curtain_exit_transition_frames",
                     "covered_handoff_marker", "external_sound"):
            try:
                v = scene.get_editor_property(prop)
                row[prop] = v.value if hasattr(v, "value") else str(v)
            except Exception:  # noqa: BLE001
                pass
        cues.append(row)
    report["cues"] = cues
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    report["segments"] = []
    for s in tr.get_editor_property("segments"):
        label = str(s.get_editor_property("label"))
        if "Interaction" in label or "Closing" in label:
            row = {"label": label, "start": s.get_editor_property("start_frame").value,
                   "end": s.get_editor_property("end_frame").value}
            for prop in ("covered_handoff_frame", "retain_previous_camera", "reveal_next_passage_when_covered", "ready"):
                try:
                    v = s.get_editor_property(prop)
                    row[prop] = v.value if hasattr(v, "value") else v
                except Exception:  # noqa: BLE001
                    pass
            report["segments"].append(row)
    del tr, show
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "inspect_interactions.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log("PUSS_SOFTGOODS_INTERACTIONS|" + out)


main()
