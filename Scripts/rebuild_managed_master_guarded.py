"""Rebuild the managed Master from the Show (29 Sep, Gary: "Scene 3 is saved, go ahead with the rebuild").

Why: the Master laid Scene 3 at 585.640 s while LS_DevScene_03 was shortened, so every segment after Scene 3 sat
425.265 s off (PIE could not get past Scene 3; SavedFixturePIE's Closing assertion failed). Standing rule: after changing
a Scene's playback range, rebuild the Master.

Guarded one-shot:
- expected world, no PIE, NOTHING dirty (an unsaved scene length can't be baked in);
- BEFORE: Show segments (BuildSegments on a transient transport) vs Master sub-sequence sections;
- copies the Show and Master .uasset files to Backups/PreMasterRebuild-<ts>/ (the revert);
- UInfinityStageSequenceBuilderLibrary.RebuildManagedMaster(Show, Master), the library call and NEVER the
  PussStageBootstrap.RebuildCurrentMaster automation test;
- saves ONLY the Master (and the Show only if the rebuild dirtied it); if anything else went dirty it saves nothing;
- AFTER: every sequence segment must match its Master section to 0.05 s.
"""
import datetime
import json
import os
import shutil

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FILES = {SHOW: os.path.join(PROJECT, "Content", "InfinityStage", "Dev", "DA_InfinityStage_V1Show.uasset"),
         MASTER: os.path.join(PROJECT, "Content", "InfinityStage", "Dev", "Sequences", "LS_InfinityStage_V1Master.uasset")}
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "rebuild_master.json")
TICK = 24000.0
report = {"ok": False}


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def compare(show, master):
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [{"label": str(s.get_editor_property("label")), "start": s.get_editor_property("start_frame").value / TICK,
             "end": s.get_editor_property("end_frame").value / TICK} for s in tr.get_editor_property("segments")]
    secs = []
    for track in master.find_tracks_by_type(unreal.MovieSceneSubTrack):
        for sec in track.get_sections():
            sub = sec.get_sequence()
            secs.append({"sequence": sub.get_name() if sub else None, "start": sec.get_start_frame_seconds(),
                         "end": sec.get_end_frame_seconds()})
    secs.sort(key=lambda r: r["start"])
    seq_segs = [s for s in segs if not s["label"].startswith("Passage")]
    rows, worst = [], 0.0
    for s, m in zip(seq_segs, secs):
        err = max(abs(s["start"] - m["start"]), abs(s["end"] - m["end"]))
        worst = max(worst, err)
        rows.append({"segment": s["label"], "show": [round(s["start"], 3), round(s["end"], 3)], "master_section": m["sequence"],
                     "master": [round(m["start"], 3), round(m["end"], 3)], "err_s": round(err, 3)})
    return {"n_segments": len(segs), "n_sequence_segments": len(seq_segs), "n_sections": len(secs), "rows": rows,
            "worst_err_s": round(worst, 3), "match": len(seq_segs) == len(secs) and worst <= 0.05}


def finish(msg):
    report["message"] = msg
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(("PUSS_SOFTGOODS_MASTER_REBUILT|" if report["ok"] else "PUSS_SOFTGOODS_MASTER_REBUILD_STOPPED|") + msg)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world.get_outermost().get_name() != EXPECTED_WORLD or editor.get_game_world() is not None:
    finish(f"unsafe editor state: world={world.get_outermost().get_name()} pie={editor.get_game_world()}")
elif dirty():
    finish(f"refusing: dirty packages {dirty()}")
else:
    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    report["before"] = compare(show, master)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(PROJECT, "Backups", f"PreMasterRebuild-{ts}")
    os.makedirs(backup, exist_ok=True)
    for f in FILES.values():
        shutil.copy2(f, backup)
    report["backup"] = backup
    result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    report["rebuild_result"] = result
    after_dirty = dirty()
    report["dirty_after_rebuild"] = after_dirty
    allowed = {MASTER.split("/")[-1], SHOW.split("/")[-1]}
    unexpected = [p for p in after_dirty if p.split("/")[-1] not in allowed]
    if result is False or result is None:
        finish(f"rebuild returned {result!r}; nothing saved; dirty={after_dirty}")
    elif unexpected:
        finish(f"rebuild dirtied unexpected packages {unexpected}; NOTHING saved (backup {backup})")
    else:
        saved = {}
        for path in (MASTER, SHOW):
            if any(p.split("/")[-1] == path.split("/")[-1] for p in after_dirty):
                saved[path] = unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=True)
        report["saved"] = saved
        report["after"] = compare(unreal.load_asset(SHOW), unreal.load_asset(MASTER))
        report["dirty_final"] = dirty()
        report["ok"] = all(saved.values()) and report["after"]["match"] and not report["dirty_final"]
        finish(f"saved={saved}|match={report['after']['match']}|worst_err={report['after']['worst_err_s']}s"
               f"|before_worst={report['before']['worst_err_s']}s|dirty_final={report['dirty_final']}|backup={backup}")
