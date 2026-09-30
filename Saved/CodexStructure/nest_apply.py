"""Nest hangar rises into their Scene sequences (30 Sep; Gary: "Go ahead on ... nesting"). Scene 4's pattern,
read from LS_DevScene_04: a MovieSceneSubTrack named "Hangar Fold" with ONE section playing LS_SN_HangarRise
over [0, the rise's playback end], offsets 0, completion KeepState. Nesting is what wakes the scene's Arrival
(its motion sub-section now exists) and plays the rise from the Scene's first frame on.
REFUSES a Scene whose sequence is shorter than its rise: the compiled segment follows the Scene sequence's
playback range (the Show's DurationFrames is 15 s everywhere and is not what the compiler uses), so a 15 s
Scene would cut a 31 s (S5: 49 s) rise before it lands. Lengthening a Scene moves every later segment, so it
is a timeline decision, not this script's.
Scenes from NEST_SCENES (default (1,)). Dry run (default): what would be nested, and why not where refused.
Apply (NEST_APPLY): record, Backups/PreNest-* (the Scene sequences), add, read back, save those only.
Revert (NEST_REVERT): remove the recorded "Hangar Fold" tracks. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "nest_record.json")
SCENES = tuple(globals().get("NEST_SCENES", (1,)))
TRACK_NAME = "Hangar Fold"


def fail(msg):
    unreal.log_error("NEST_STOPPED|" + msg)
    raise RuntimeError(msg)


def fold_tracks(scene, rise_path):
    return [t for t in scene.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            and any(s.get_sequence() and s.get_sequence().get_path_name().split(".")[0] == rise_path for s in t.get_sections())]


def main():
    apply, revert = bool(globals().get("NEST_APPLY")), bool(globals().get("NEST_REVERT"))
    if 4 in SCENES:
        fail("Scene 4 is already nested")
    rows = []
    for n in SCENES:
        scene_path, rise_path = f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{n}", f"/Game/InfinityStage/RigAtmos/LS_S{n}_HangarRise"
        scene, rise = unreal.load_asset(scene_path), unreal.load_asset(rise_path)
        if not (scene and rise):
            fail(f"S{n}: scene or rise missing")
        scene_end, rise_end = scene.get_playback_end_seconds(), rise.get_playback_end_seconds()
        rows.append({"scene": n, "scene_path": scene_path, "rise_path": rise_path, "scene_end_s": round(scene_end, 3), "rise_end_s": round(rise_end, 3),
                     "fits": scene_end + 1e-3 >= rise_end, "already_nested": bool(fold_tracks(scene, rise_path))})
    unreal.log(f"NEST_PLAN|{json.dumps(rows)}")
    if not (apply or revert):
        unreal.log("NEST_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    done = []
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        for r in rec["nested"]:
            scene = unreal.load_asset(r["scene_path"])
            for t in fold_tracks(scene, r["rise_path"]):
                scene.remove_track(t)
            done.append(r["scene_path"])
    else:
        bad = [(r["scene"], "shorter than its rise (%.1f s < %.1f s): a timeline decision" % (r["scene_end_s"], r["rise_end_s"])) for r in rows if not r["fits"]]
        bad += [(r["scene"], "already nested") for r in rows if r["already_nested"]]
        if bad or os.path.exists(RECORD):
            fail(f"refused: {bad}, record exists={os.path.exists(RECORD)}")
        stamp = datetime.datetime.now()
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": stamp.isoformat(timespec="seconds"), "nested": rows}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreNest-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        for r in rows:
            shutil.copy2(os.path.join(project, "Content", *r["scene_path"][len("/Game/"):].split("/")) + ".uasset", backup)
        shutil.copy2(RECORD, backup)
        for r in rows:
            scene, rise = unreal.load_asset(r["scene_path"]), unreal.load_asset(r["rise_path"])
            track = scene.add_track(unreal.MovieSceneSubTrack)
            track.set_display_name(TRACK_NAME)
            sec = track.add_section()
            sec.set_sequence(rise)
            sec.set_range_seconds(0.0, r["rise_end_s"])
            ev = sec.get_editor_property("eval_options")
            ev.set_editor_property("completion_mode", unreal.MovieSceneCompletionMode.KEEP_STATE)
            sec.set_editor_property("eval_options", ev)
            got = (sec.get_start_frame_seconds(), sec.get_end_frame_seconds())
            if abs(got[0]) > 1e-3 or abs(got[1] - r["rise_end_s"]) > 1.0 / 30.0 or len(fold_tracks(scene, r["rise_path"])) != 1:
                fail(f"S{r['scene']}: section landed {got} (NOT saved)")
            done.append(f"{r['scene_path']}:[{got[0]:.3f},{got[1]:.3f}]")
    for r in rows:
        if not unreal.EditorAssetLibrary.save_asset(r["scene_path"], only_if_is_dirty=False):
            fail(f"save failed: {r['scene_path']}")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
        [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"NEST_OK|{'reverted' if revert else 'applied'}|{'|'.join(done)}|dirty_after={d}")


main()
