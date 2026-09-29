"""Scene 1 plays its full content (29 Sep; Gary: "S01 and S03, the longer times are right ... about 3-4min"; the
conductor's go, under Gary's delegation, for S1 ONLY).

Fault (read live today): every cue already has bUseSequenceLength = true, but the compiler takes the length from the
scene sequence's PLAYBACK RANGE. LS_DevScene_01 plays 0-15 s while its CinematicShot section LS_Animals_1 runs to
210.8 s, so 195.8 s of Gary's content was cut. The fix extends LS_DevScene_01's playback end to the END OF ITS LATEST
SHOT SECTION: the SECTION, not the child (a trimmed section is an authoring decision), and derived, not typed in.

Guarded one-shot: no PIE, nothing dirty, exactly one active shot section. Backs up the Show, the Master and
LS_DevScene_01 to Backups/PreScene1Extend-<ts>/. Saves LS_DevScene_01, then RebuildManagedMaster (the library call,
never the PussStageBootstrap test), then saves ONLY the Master (and the Show if the rebuild dirtied it). AFTER: all 13
sequence segments match their Master sections to 0.05 s, and Scene 1's segment equals the section end.
Scene 3 is NOT touched (its 60.58 s section trim is Gary's to judge). Everything inside main().
"""
import datetime
import json
import os
import shutil

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SCENE1 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def content_file(path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def compare(show, master):
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [{"label": str(s.get_editor_property("label")), "start": s.get_editor_property("start_frame").value / rate,
             "end": s.get_editor_property("end_frame").value / rate} for s in tr.get_editor_property("segments")]
    del tr
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
        rows.append({"segment": s["label"], "show": [round(s["start"], 3), round(s["end"], 3)],
                     "master_section": m["sequence"], "master": [round(m["start"], 3), round(m["end"], 3)], "err_s": round(err, 3)})
    return {"rows": rows, "worst_err_s": round(worst, 3), "total_s": round(segs[-1]["end"], 3) if segs else None,
            "match": len(seq_segs) == len(secs) and worst <= 0.05}


def main():
    report = {"ok": False}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "scene1_extend_rebuild.json")

    def finish(msg):
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_SCENE1_EXTENDED|" if report["ok"] else "PUSS_SOFTGOODS_SCENE1_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:          # check PIE FIRST: in play mode get_editor_world() is None
        return finish("PIE is running")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        return finish("unsafe editor state (no editor world or wrong world)")
    del world
    if dirty():
        return finish(f"refusing: dirty packages {dirty()}")
    scene1 = unreal.load_asset(SCENE1)
    shots = [s for t in scene1.get_tracks() if "CinematicShot" in t.get_class().get_name() for s in t.get_sections()
             if s.is_active() and s.has_end_frame()]
    report["shots"] = [{"child": s.get_sequence().get_name() if s.get_sequence() else None,
                        "end_frame": s.get_end_frame(), "end_s": round(s.get_end_frame_seconds(), 3)} for s in shots]
    if len(shots) != 1:
        return finish(f"expected exactly one active shot section, found {report['shots']}")
    new_end = shots[0].get_end_frame()
    report["playback_before"] = [scene1.get_playback_start(), scene1.get_playback_end()]
    report["new_playback_end_frame"] = new_end
    if new_end <= scene1.get_playback_end():
        return finish(f"nothing to do: playback end {scene1.get_playback_end()} already covers the shot end {new_end}")
    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    report["before"] = compare(show, master)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreScene1Extend-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    for p in (SHOW, MASTER, SCENE1):
        shutil.copy2(content_file(p), backup)
    report["backup"] = backup
    scene1.set_playback_end(new_end)
    report["playback_after"] = [scene1.get_playback_start(), scene1.get_playback_end(),
                                round(scene1.get_playback_end_seconds(), 3)]
    if dirty() != [SCENE1]:
        return finish(f"playback edit dirtied {dirty()}; NOTHING saved (relaunch to discard; backup {backup})")
    report["saved_scene1"] = unreal.EditorAssetLibrary.save_asset(SCENE1, only_if_is_dirty=False)
    result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    report["rebuild_result"] = result
    after_dirty = dirty()
    unexpected = [p for p in after_dirty if p not in (SHOW, MASTER)]
    if not report["saved_scene1"] or not result or unexpected:
        return finish(f"stopped after the Scene 1 save: rebuild={result!r} unexpected={unexpected}; Master/Show NOT saved "
                      f"(backup {backup})")
    saved = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True) for p in (MASTER, SHOW) if p in after_dirty}
    report["saved"] = saved
    report["after"] = compare(unreal.load_asset(SHOW), unreal.load_asset(MASTER))
    s1 = next((r for r in report["after"]["rows"] if r["segment"].startswith("Scene 1")), None)
    report["scene1_segment"] = s1
    report["dirty_final"] = dirty()
    report["ok"] = all(saved.values()) and report["after"]["match"] and not report["dirty_final"] and s1 is not None \
        and abs((s1["show"][1] - s1["show"][0]) - report["playback_after"][2]) < 0.05
    del scene1, show, master, shots
    finish(f"scene1={s1}|total={report['after']['total_s']}s|match={report['after']['match']}|worst={report['after']['worst_err_s']}"
           f"|saved={saved}|dirty_final={report['dirty_final']}|backup={backup}")


main()
