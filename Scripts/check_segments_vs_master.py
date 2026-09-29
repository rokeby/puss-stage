"""READ-ONLY: compile the Show's segments on a TRANSIENT transport (BuildSegments: no world, no player) and compare
them with the Master's subsequence sections. Tests the hypothesis that SavedFixturePIE's Closing assertion fails
because every segment after Scene 3 sits ~425 s earlier in the Show than in the Master."""
import json, os
import unreal
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "segments_vs_master.json")
dirty = lambda: sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
    sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
before = dirty()
show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
tr = unreal.new_object(unreal.InfinityStageTransportController)
ok = tr.build_segments(show)
tick = 24000.0
segs = []
for i, s in enumerate(tr.get_editor_property("segments")):
    row = {"i": i, "label": str(s.get_editor_property("label"))}
    for k in ("start_frame", "end_frame", "covered_handoff_frame"):
        try:
            row[k + "_s"] = round(s.get_editor_property(k).value / tick, 3)
        except Exception:
            pass
    segs.append(row)
sections = []
for track in master.find_tracks_by_type(unreal.MovieSceneSubTrack):
    for sec in track.get_sections():
        sub = sec.get_sequence()
        sections.append({"sequence": sub.get_name() if sub else None, "start_s": round(sec.get_start_frame_seconds(), 3),
                         "end_s": round(sec.get_end_frame_seconds(), 3)})
res = {"build_ok": ok, "segments": segs, "master_sections": sorted(sections, key=lambda r: r["start_s"]),
       "dirty_before": before, "dirty_after": dirty()}
res["dirty_unchanged"] = res["dirty_before"] == res["dirty_after"]
open(OUT, "w", encoding="utf-8").write(json.dumps(res, indent=1, default=str))
s18 = segs[18] if len(segs) > 18 else None
unreal.log(f"PUSS_SOFTGOODS_SEGMENTS|n={len(segs)}|seg18={s18}|dirty_unchanged={res['dirty_unchanged']}")
