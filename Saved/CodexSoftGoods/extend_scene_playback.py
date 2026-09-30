"""Change a Scene's playback length SAFELY (30 Sep): end, handoff rematch, cut coverage, Master rebuild, exact saves.

Why: Scene 1 was lengthened (0-375 -> 0-5270) on 29 Sep without re-running the scene-handoff match. Its Exit Handoff cut
stayed at 350-375 and 375-5270 had NO camera cut, so a transport jump into the tail left the player controller at the
origin (the dev grid). Scenes 2, 5 and 6 are about to be lengthened for the hangar rises. This script makes the
omission impossible: the rematch and a coverage check are part of the change, not a separate step.

Mode file extend_scene_playback_mode.json:
  {"scene_label": "Scene 2 — External Sound", "new_end_s": 31.0, "dry_run": true}
  {"scene_label": "Scene 1 — External Sound", "rematch_only": true, "dry_run": true}   # fix an existing gap, range unchanged
Steps (apply):
  1. Guards: no PIE, the show level open, nothing dirty; the cue must be an enabled Scene cue with a sequence.
  2. Backups of the Show, the Master, the scene sequence and the level, to Backups/PreSceneExtend-<scene>-<ts>/.
  3. set_playback_end (unless rematch_only).
  4. InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [cue guid], 1). This is the Cue Desk's Match,
     narrow by construction (it refuses an empty list). It moves the Exit cut to the NEW end and stretches the Entry cut.
  5. CUT COVERAGE: the scene's camera cut track must cover [playback start, playback end) with no gap, or NOTHING is saved.
  6. Rebuild the managed Master (the library call, never PussStageBootstrap.RebuildCurrentMaster).
  7. Save exactly: the scene sequence, the level (the rematch writes the handoff cameras), the Master, and the Show if
     the rebuild dirtied it. Read back the coverage and the Show/Master match.
Logs PUSS_SOFTGOODS_SCENE_EXTENDED|... or _STOPPED|... Crash rules: everything inside main().
"""
import datetime
import json
import os
import shutil

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def content_file(path, ext=".uasset"):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext


def cut_coverage(seq):
    """Stretches of [playback start, playback end) with NO camera cut section, in display frames. [] = fully covered."""
    start, end = seq.get_playback_start(), seq.get_playback_end()
    spans = []
    for t in seq.get_tracks():
        if t.get_class().get_name() == "MovieSceneCameraCutTrack":
            for s in t.get_sections():
                if s.is_active():
                    spans.append((s.get_start_frame() if s.has_start_frame() else start,
                                  s.get_end_frame() if s.has_end_frame() else end))
    spans.sort()
    gaps, cursor = [], start
    for a, b in spans:
        if a > cursor:
            gaps.append([cursor, min(a, end)])
        cursor = max(cursor, b)
        if cursor >= end:
            break
    if cursor < end:
        gaps.append([cursor, end])
    return {"range": [start, end], "cuts": [list(x) for x in spans], "gaps": [g for g in gaps if g[1] > g[0]]}


def show_master_match(show, master):
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [(str(s.get_editor_property("label")), s.get_editor_property("start_frame").value / rate,
             s.get_editor_property("end_frame").value / rate) for s in tr.get_editor_property("segments")]
    del tr
    secs = sorted((sec.get_start_frame_seconds(), sec.get_end_frame_seconds())
                  for track in master.find_tracks_by_type(unreal.MovieSceneSubTrack) for sec in track.get_sections())
    seq_segs = [s for s in segs if not s[0].startswith("Passage")]
    worst = max((max(abs(s[1] - m[0]), abs(s[2] - m[1])) for s, m in zip(seq_segs, secs)), default=0.0)
    return {"worst_err_s": round(worst, 3), "match": len(seq_segs) == len(secs) and worst <= 0.05}


def main():
    with open(os.path.join(HERE, "extend_scene_playback_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    dry = bool(cfg.get("dry_run", True))
    rematch_only = bool(cfg.get("rematch_only", False))
    report = {"ok": False, "cfg": cfg}
    out = os.path.join(HERE, "extend_scene_playback.json")

    def finish(msg):
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_SCENE_EXTENDED|" if report["ok"] else "PUSS_SOFTGOODS_SCENE_EXTEND_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:                 # PIE first: in play mode get_editor_world() is None
        return finish("PIE is running")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        return finish("unsafe editor state (wrong or no world)")
    if dirty():
        return finish(f"refusing: dirty packages {dirty()}")
    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    cues = [c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == cfg["scene_label"]]
    if len(cues) != 1 or str(cues[0].get_editor_property("type")) != str(unreal.InfinityCueType.SCENE) \
            or not cues[0].get_editor_property("enabled"):
        return finish(f"refusing: '{cfg['scene_label']}' is not exactly one enabled Scene cue")
    cue_guid = cues[0].get_editor_property("cue_guid")
    seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    if seq is None:
        return finish("refusing: the Scene cue has no sequence")
    seq_path = seq.get_path_name().split(".")[0]
    rate = seq.get_display_rate()
    fps = rate.numerator / rate.denominator
    new_end = seq.get_playback_end() if rematch_only else int(round(float(cfg["new_end_s"]) * fps))
    report.update({"sequence": seq_path, "fps": fps, "playback_before": [seq.get_playback_start(), seq.get_playback_end()],
                   "new_end": new_end, "coverage_before": cut_coverage(seq)})
    if not rematch_only and new_end <= seq.get_playback_start():
        return finish(f"refusing: new end {new_end} is not after the start")
    if dry:
        report["ok"] = True
        return finish(f"DRY RUN|{seq_path}|{report['playback_before']} -> end {new_end}|gaps before "
                      f"{report['coverage_before']['gaps']}")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", f"PreSceneExtend-{seq_path.split('/')[-1]}-{stamp}")
    os.makedirs(backup, exist_ok=True)
    for p in (SHOW, MASTER, seq_path):
        shutil.copy2(content_file(p), backup)
    shutil.copy2(content_file(EXPECTED_WORLD, ".umap"), backup)
    report["backup"] = backup
    if not rematch_only:
        seq.set_playback_end(new_end)
    res = unreal.InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [cue_guid], 1)
    matched, match_report = (res if isinstance(res, tuple) else (res, ""))
    report["match"] = {"ok": bool(matched), "report": str(match_report)}
    report["coverage_after_match"] = cut_coverage(seq)
    if not matched or report["coverage_after_match"]["gaps"]:
        return finish(f"STOPPED: match={matched} gaps={report['coverage_after_match']['gaps']}; NOTHING saved "
                      f"(relaunch to discard; backup {backup})")
    result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    report["rebuild_result"] = result
    expected = {seq_path, EXPECTED_WORLD, MASTER, SHOW}
    now = dirty()
    report["dirty_before_save"] = now
    if not result or [p for p in now if p not in expected]:
        return finish(f"STOPPED: rebuild={result!r} unexpected dirty {[p for p in now if p not in expected]}; NOTHING "
                      f"saved (backup {backup})")
    saved = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True) for p in (seq_path, MASTER, SHOW) if p in now}
    if EXPECTED_WORLD in now:
        saved[EXPECTED_WORLD] = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)
    report["saved"] = saved
    seq = unreal.load_asset(seq_path)
    report["coverage_after"] = cut_coverage(seq)
    report["playback_after"] = [seq.get_playback_start(), seq.get_playback_end()]
    report["show_master"] = show_master_match(unreal.load_asset(SHOW), unreal.load_asset(MASTER))
    report["dirty_final"] = dirty()
    report["ok"] = (all(saved.values()) and not report["coverage_after"]["gaps"] and report["show_master"]["match"]
                    and not report["dirty_final"] and report["playback_after"][1] == new_end)
    del show, master, seq, cues, world
    finish(f"{seq_path}|end={new_end}|gaps={report['coverage_after']['gaps']}|master_match={report['show_master']}"
           f"|saved={saved}|backup={backup}")


main()
