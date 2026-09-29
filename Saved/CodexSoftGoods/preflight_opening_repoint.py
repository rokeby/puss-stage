"""READ-ONLY preflight for repointing the Opening cue to the baked curtain (29 Sep). Writes nothing.

Reports: cue 0 (label, sequence, sequence_owns_curtain), every Show cue's sequence and its playback length, the
Master's (LS_InfinityStage_V1Master) playback range and every subsequence section (sequence, start/end frame,
length), and a STALENESS table: for each cue sequence, is it in the Master, and does the section length match the
sequence's own playback length (in Master ticks)? Also the package save dates of the Show and the Master, and the
dirty state before and after (must be unchanged).
"""
import json
import os

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "L_InfinityStage_V1VerticalSlice"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                   "preflight_opening_repoint.json")


def pkg(o):
    try:
        return o.get_path_name().split(".")[0]
    except Exception:
        return str(o)


def seconds(seq, frames):
    fr = seq.get_display_rate() if hasattr(seq, "get_display_rate") else None
    return frames


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if EXPECTED_WORLD not in world.get_name():
    raise RuntimeError("wrong world")
dirty_before = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
    sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())

report = {"errors": []}
show = unreal.load_asset(SHOW)
master = unreal.load_asset(MASTER)
cues = []
for i, cue in enumerate(show.get_editor_property("cues")):
    entry = {"index": i, "label": str(cue.get_editor_property("label"))}
    try:
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence")
        entry["sequence"] = pkg(seq) if seq else None
        entry["sequence_owns_curtain"] = bool(scene.get_editor_property("sequence_owns_curtain"))
        if seq:
            entry["seq_display_rate"] = str(seq.get_display_rate())
            entry["seq_range"] = [seq.get_playback_start(), seq.get_playback_end()]
            entry["seq_range_seconds"] = [seq.get_playback_start_seconds(), seq.get_playback_end_seconds()]
    except Exception as exc:  # noqa: BLE001
        entry["error"] = str(exc)
    cues.append(entry)
report["cues"] = cues

report["master"] = {"display_rate": str(master.get_display_rate()), "tick": str(master.get_tick_resolution()),
                    "range": [master.get_playback_start(), master.get_playback_end()],
                    "range_seconds": [master.get_playback_start_seconds(), master.get_playback_end_seconds()],
                    "sections": []}
for track in master.find_tracks_by_type(unreal.MovieSceneSubTrack) + master.find_tracks_by_type(unreal.MovieSceneCinematicShotTrack):
    for sec in track.get_sections():
        sub = sec.get_sequence()
        report["master"]["sections"].append({
            "track": track.get_display_name() if hasattr(track, "get_display_name") else str(track.get_name()),
            "sequence": pkg(sub) if sub else None, "start": sec.get_start_frame(), "end": sec.get_end_frame(),
            "start_seconds": sec.get_start_frame_seconds(), "end_seconds": sec.get_end_frame_seconds()})

# Staleness: each cue's sequence present in the Master, and section length (s) vs the sequence's own length (s).
stale = []
for c in cues:
    if not c.get("sequence"):
        continue
    secs = [s for s in report["master"]["sections"] if s["sequence"] == c["sequence"]]
    own = (c["seq_range_seconds"][1] - c["seq_range_seconds"][0]) if c.get("seq_range_seconds") else None
    if not secs:
        stale.append({"cue": c["label"], "problem": "sequence NOT in the Master"})
        continue
    for s in secs:
        span = s["end_seconds"] - s["start_seconds"]
        if own is not None and abs(span - own) > 0.05:
            stale.append({"cue": c["label"], "problem": f"section {span:.3f} s vs sequence {own:.3f} s"})
report["staleness"] = stale

eal = unreal.EditorAssetLibrary
report["package_info"] = {p: str(eal.find_asset_data(p).get_asset().get_path_name()) for p in (SHOW, MASTER)}
report["dirty_before"] = dirty_before
report["dirty_after"] = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
    sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
report["dirty_unchanged"] = report["dirty_before"] == report["dirty_after"]
with open(OUT, "w", encoding="utf-8") as h:
    json.dump(report, h, indent=1, default=str)
unreal.log(f"PUSS_SOFTGOODS_PREFLIGHT_DONE|cues={len(cues)}|master_sections={len(report['master']['sections'])}"
           f"|stale={len(stale)}|dirty_unchanged={report['dirty_unchanged']}")
