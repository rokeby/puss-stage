"""READ-ONLY dry run (29 Sep): what would each Scene cue become with bUseSequenceLength = True? Gary: "S01 and S03, the
longer times are right. S03 isn't done yet will eventually be about 3-4min, same for S01". Writes nothing.

The compiler (InfinityStageCompiler.cpp ResolveSceneDuration) takes the Scene's length from its sequence's own PLAYBACK
RANGE, so nested content outside that range would still be cut. For every cue with a sequence, report:
bUseSequenceLength, DurationFrames (s), the sequence's playback range (s, display rate), and every sub or cinematic-shot
section one level down and two levels down: its outer range in the parent and the child's own playback range. Also
report the compiled segment table now (a transient transport), so the new total can be computed exactly.
"""
import json
import os

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def seconds(scene_seq, frames):
    rate = scene_seq.get_display_rate()
    return round(frames * rate.denominator / rate.numerator, 3)


def nested(seq, depth):
    rows = []
    for track in seq.get_tracks():
        cls = track.get_class().get_name()
        if "Sub" not in cls and "CinematicShot" not in cls:
            continue
        for sec in track.get_sections():
            child = sec.get_sequence()
            row = {"track": cls, "child": child.get_name() if child else None,
                   "outer_s": [round(sec.get_start_frame_seconds(), 3) if sec.has_start_frame() else None,
                               round(sec.get_end_frame_seconds(), 3) if sec.has_end_frame() else None],
                   "active": sec.is_active()}
            if child:
                row["child_playback_s"] = [round(child.get_playback_start_seconds(), 3),
                                           round(child.get_playback_end_seconds(), 3)]
                row["child_len_s"] = round(child.get_playback_end_seconds() - child.get_playback_start_seconds(), 3)
                if depth < 2:
                    row["nested"] = nested(child, depth + 1)
            rows.append(row)
    return rows


def main():
    show = unreal.load_asset(SHOW)
    tick = show.get_editor_property("tick_resolution")
    tick_rate = tick.numerator / tick.denominator
    report = {"cues": [], "dirty": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}
    for i, cue in enumerate(show.get_editor_property("cues")):
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence")
        if not seq:
            continue
        row = {"index": i, "label": str(cue.get_editor_property("label")), "type": str(cue.get_editor_property("type")),
               "sequence": seq.get_name(), "use_sequence_length": scene.get_editor_property("use_sequence_length"),
               "duration_s": round(scene.get_editor_property("duration_frames").value / tick_rate, 3),
               "playback_s": [round(seq.get_playback_start_seconds(), 3), round(seq.get_playback_end_seconds(), 3)],
               "display_rate": f"{seq.get_display_rate().numerator}/{seq.get_display_rate().denominator}"}
        row["playback_len_s"] = round(row["playback_s"][1] - row["playback_s"][0], 3)
        row["nested"] = nested(seq, 1)
        spans = [n["outer_s"][1] for n in row["nested"] if n["outer_s"][1] is not None]
        row["nested_outer_end_s"] = max(spans) if spans else None
        report["cues"].append(row)
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [{"label": str(s.get_editor_property("label")), "start": round(s.get_editor_property("start_frame").value / tick_rate, 3),
             "end": round(s.get_editor_property("end_frame").value / tick_rate, 3)} for s in tr.get_editor_property("segments")]
    report["segments"] = segs
    report["total_s"] = segs[-1]["end"] if segs else None
    del tr, show
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "scene_length_dryrun.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log("PUSS_SOFTGOODS_SCENE_LENGTH_DRYRUN|" + out)


main()
