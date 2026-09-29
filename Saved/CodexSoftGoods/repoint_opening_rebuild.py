"""Repoint Show cue 0 ("Opening — Curtain") to LS_Opening_Curtain_Baked, then rebuild the managed Master (29 Sep).

Run ONLY after curtain_place_opening_and_transitions.py has saved LS_Opening_Curtain_Baked. The rebuild is the standing
step after any cue-sequence change: the Master's Opening sub-section must point at the new sequence (same 15.0 s / 25 fps,
so no timing moves).

Guarded one-shot, the same as rebuild_master.py plus the repoint:
- expected world, no PIE, NOTHING dirty;
- cue 0 must be labelled "Opening — Curtain", point at LS_Opening_Curtain, and own its curtain; the new sequence must
  exist with the same playback length;
- copies the Show and Master .uasset files to Backups/PreOpeningRepoint-<ts>/ (the revert: point cue 0 back and rebuild);
- sets cue 0's Scene.Sequence, then UInfinityStageSequenceBuilderLibrary.RebuildManagedMaster (the library call, NEVER
  the PussStageBootstrap.RebuildCurrentMaster automation test);
- saves ONLY the Show and the Master, and only if nothing else went dirty;
- AFTER: all 13 sequence segments match the Master to 0.05 s AND the Master's first section plays LS_Opening_Curtain_Baked.
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
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "repoint_opening_rebuild.json")
OLD_SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain"
NEW_SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
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
    unreal.log(("PUSS_SOFTGOODS_OPENING_REPOINTED|" if report["ok"] else "PUSS_SOFTGOODS_OPENING_REPOINT_STOPPED|") + msg)


def main():
    # Crash rule (puss-mcp-python-crashes-the-editor): no UE objects at module level.
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
        backup = os.path.join(PROJECT, "Backups", f"PreOpeningRepoint-{ts}")
        os.makedirs(backup, exist_ok=True)
        for f in FILES.values():
            shutil.copy2(f, backup)
        report["backup"] = backup
        cues = show.get_editor_property("cues")
        cue = cues[0]
        scene = cue.get_editor_property("scene")
        cur = scene.get_editor_property("sequence")
        report["cue0_before"] = {"label": str(cue.get_editor_property("label")), "sequence": cur.get_path_name() if cur else None,
                                 "owns_curtain": bool(scene.get_editor_property("sequence_owns_curtain"))}
        new_seq = unreal.load_asset(NEW_SEQ)
        old_seq = unreal.load_asset(OLD_SEQ)
        if not str(cue.get_editor_property("label")).startswith("Opening") or not cur or cur.get_path_name().split(".")[0] != OLD_SEQ             or not report["cue0_before"]["owns_curtain"] or not new_seq             or new_seq.get_playback_end_seconds() != old_seq.get_playback_end_seconds():
            del cues, cue, scene, cur, new_seq, old_seq, show, master
            finish(f"refusing: cue 0 / sequences not as expected {report['cue0_before']}")
            return
        show.modify()
        scene.set_editor_property("sequence", new_seq)
        cue.set_editor_property("scene", scene)
        cues[0] = cue
        show.set_editor_property("cues", cues)
        back = show.get_editor_property("cues")[0].get_editor_property("scene").get_editor_property("sequence")
        report["cue0_after"] = back.get_path_name() if back else None
        del cues, cue, scene, cur, new_seq, old_seq, back
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
            first = min(report["after"]["rows"], key=lambda r: r["master"][0]) if report["after"]["rows"] else {}
            report["opening_section"] = first.get("master_section")
            report["ok"] = all(saved.values()) and report["after"]["match"] and not report["dirty_final"]             and report["opening_section"] == NEW_SEQ.split("/")[-1] and report.get("cue0_after", "").split(".")[0] == NEW_SEQ
            finish(f"saved={saved}|match={report['after']['match']}|worst_err={report['after']['worst_err_s']}s"
                   f"|before_worst={report['before']['worst_err_s']}s|dirty_final={report['dirty_final']}|backup={backup}")
        del show, master
    del editor, world


main()
