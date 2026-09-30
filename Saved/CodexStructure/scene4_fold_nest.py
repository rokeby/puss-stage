"""Nest the fold in Scene 4 and let its speed be ONE dial (Gary, 29 Sep: "grow to fit
and make speed changeable").

The fold (LS_S4_HangarFold) plays as a subsequence section in LS_DevScene_04,
starting at the Scene's first frame. Its section Time Scale IS the speed dial:
native, and in Sequencer's UI. Gary can drag it himself, then run this script
again (or have any session run it) to make everything follow. Nothing here is
set alongside the Time Scale; everything is DERIVED from it:
- the fold section ends at fold length / Time Scale;
- the Scene's playback ends at max(15 s, that end), because the Scene keeps its
  original 15 s floor;
- the camera cuts are entry 0 -> end - 1 s, and exit over the last second;
- the Master is rebuilt (the library call, never the PussStageBootstrap test),
  then Show and Master sections are verified 13/13, as Soft goods did for Scene 1.

At the extremes: Time Scale 0.5 gives a 50 s fold and a 50 s Scene. 1.0 gives
25 s and 25 s. 2.0 gives a 12.5 s fold, and the Scene stays at its 15 s floor.
The first run creates the section at Time Scale TIME_SCALE (default 1.0); later
runs keep whatever Time Scale the section already has, unless FOLD_TIME_SCALE is
given.

Guards: no PIE, 0+0 dirty. Backs up Show, Master, LS_DevScene_04 and the fold to
Backups/PreScene4Nest-<ts>/. Saves LS_DevScene_04, then rebuilds, then saves only
the Master (and the Show if the rebuild dirtied it). Refuses and saves nothing
if the scene edit dirties anything else. Lean: all work in main().
"""
import datetime
import json
import os
import shutil

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SCENE4 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
FOLD = globals().get("FOLD_PATH", "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold")   # v2: LS_S4_HangarRise
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TRACK_NAME = "Hangar Fold"
SCENE_FLOOR_S = 15.0
EXIT_CUT_S = 1.0


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def content_file(path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def compare(show, master):
    """Soft goods' check (scene1_extend_rebuild.py): every sequence segment against its Master section."""
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
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure",
                       "scene4_fold_nest.json")

    def finish(msg):
        report["message"] = msg
        json.dump(report, open(out, "w", encoding="utf-8"), indent=1, default=str)
        unreal.log(("S4_FOLD_NEST_OK|" if report["ok"] else "S4_FOLD_NEST_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        return finish("PIE is running")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        return finish("unsafe editor state")
    del world
    if dirty():
        return finish(f"refusing: dirty packages {dirty()}")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        return finish("a sequence is open in Sequencer; close it first")
    scene, fold = unreal.load_asset(SCENE4), unreal.load_asset(FOLD)
    if not scene or not fold:
        return finish("Scene 4 or the fold sequence is missing")
    ext = unreal.MovieSceneTimeWarpExtensions
    fold_len_s = fold.get_playback_end_seconds() - fold.get_playback_start_seconds()
    fps = scene.get_display_rate()
    fps_f = fps.numerator / fps.denominator

    tracks = [t for t in scene.find_tracks_by_type(unreal.MovieSceneSubTrack) if str(t.get_display_name()) == TRACK_NAME]
    existing = tracks[0].get_sections()[0] if tracks and tracks[0].get_sections() else None
    if globals().get("FOLD_TIME_SCALE") is not None:
        time_scale = float(globals()["FOLD_TIME_SCALE"])
    elif existing is not None:
        time_scale = float(ext.conv_time_warp_variant_to_play_rate(existing.get_editor_property("parameters").get_editor_property("time_scale")))
    else:
        time_scale = 1.0
    if not (0.1 <= time_scale <= 10.0):
        return finish(f"time scale {time_scale} outside 0.1-10")
    section_end_s = fold_len_s / time_scale
    scene_end_s = max(SCENE_FLOOR_S, section_end_s)
    f = lambda sec: int(round(sec * fps_f))
    report.update({"time_scale": time_scale, "fold_len_s": fold_len_s, "section_end_s": section_end_s, "scene_end_s": scene_end_s,
                   "scene_before_s": [scene.get_playback_start_seconds(), scene.get_playback_end_seconds()]})
    cuts = sorted((s for t in scene.find_tracks_by_type(unreal.MovieSceneCameraCutTrack) for s in t.get_sections()),
                  key=lambda s: s.get_start_frame())
    if len(cuts) != 2:
        return finish(f"expected two camera cuts (entry, exit), found {len(cuts)}")
    # The speed dial's conversions must exist before anything is touched: a pure
    # round trip, 1.5 -> time-warp variant -> 1.5.
    try:
        trip = float(ext.conv_time_warp_variant_to_play_rate(ext.conv_play_rate_to_time_warp_variant(1.5)))
    except Exception as exc:
        return finish(f"time-scale conversions unavailable in Python: {exc}")
    if abs(trip - 1.5) > 1e-6:
        return finish(f"time-scale round trip gave {trip}, not 1.5")
    report["round_trip"] = trip
    if globals().get("S4_NEST_DRY_RUN"):
        report["ok"] = True
        return finish(f"DRY RUN|time_scale={time_scale}|fold={fold_len_s:.2f}s|section_end={section_end_s:.2f}s|scene_end={scene_end_s:.2f}s|mutated=0")

    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    report["before"] = compare(show, master)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreScene4Nest-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    for p in (SHOW, MASTER, SCENE4, FOLD):
        shutil.copy2(content_file(p), backup)
    report["backup"] = backup

    if existing is None:
        track = scene.add_track(unreal.MovieSceneSubTrack)
        track.set_display_name(TRACK_NAME)
        section = track.add_section()
        section.set_sequence(fold)
    else:
        section = existing
        if section.get_sequence() != fold:          # re-point (v1 fold -> v2 rise, or back)
            report["repointed_from"] = section.get_sequence().get_path_name() if section.get_sequence() else None
            section.set_sequence(fold)
    params = section.get_editor_property("parameters")
    params.set_editor_property("time_scale", ext.conv_play_rate_to_time_warp_variant(time_scale))
    section.set_editor_property("parameters", params)
    section.set_range(0, f(section_end_s))
    scene.set_playback_end(f(scene_end_s))
    cuts[0].set_range(0, f(scene_end_s - EXIT_CUT_S))
    cuts[1].set_range(f(scene_end_s - EXIT_CUT_S), f(scene_end_s))
    got_scale = float(ext.conv_time_warp_variant_to_play_rate(section.get_editor_property("parameters").get_editor_property("time_scale")))
    report["after_scene"] = {"playback_s": [scene.get_playback_start_seconds(), scene.get_playback_end_seconds()],
                             "section_s": [section.get_start_frame_seconds(), section.get_end_frame_seconds()],
                             "time_scale": got_scale,
                             "cuts_s": [[c.get_start_frame_seconds(), c.get_end_frame_seconds()] for c in cuts]}
    if abs(got_scale - time_scale) > 1e-4:
        return finish(f"time scale did not take ({got_scale}); nothing saved (relaunch to discard; backup {backup})")
    if dirty() != [SCENE4]:
        return finish(f"scene edit dirtied {dirty()}; NOTHING saved (relaunch to discard; backup {backup})")
    report["saved_scene4"] = unreal.EditorAssetLibrary.save_asset(SCENE4, only_if_is_dirty=False)
    result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    report["rebuild_result"] = result
    after_dirty = dirty()
    unexpected = [p for p in after_dirty if p not in (SHOW, MASTER)]
    if not report["saved_scene4"] or not result or unexpected:
        return finish(f"stopped after the Scene 4 save: rebuild={result!r} unexpected={unexpected}; Master/Show NOT saved (backup {backup})")
    saved = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True) for p in (MASTER, SHOW) if p in after_dirty}
    report["saved"] = saved
    report["after"] = compare(unreal.load_asset(SHOW), unreal.load_asset(MASTER))
    s4 = next((r for r in report["after"]["rows"] if r["segment"].startswith("Scene 4")), None)
    report["scene4_segment"] = s4
    report["dirty_final"] = dirty()
    report["ok"] = all(saved.values()) and report["after"]["match"] and not report["dirty_final"] and s4 is not None \
        and abs((s4["show"][1] - s4["show"][0]) - scene_end_s) < 0.05
    del scene, fold, show, master, section, cuts
    finish(f"time_scale={time_scale}|scene4={s4}|total={report['after']['total_s']}s|match={report['after']['match']}"
           f"|worst={report['after']['worst_err_s']}|saved={saved}|dirty_final={report['dirty_final']}|backup={backup}")


main()
