"""Move the moment S3's figures/props become visible (Gary 8 Oct: "around 100 frames into the level sequence" =
LS_DevScene_03 frame 100 = 4.17 s).  They are keyed in LS_S3_HangarRise (30 fps; nested at Scene 0, start offset 0
[measured probe_s3_fold]; time scale unreadable from Python [inferred 1:1]): every Visibility key with value True must
sit on ONE frame today; all move to round(scene_frame / 24 * 30).
Args s3_figures_time_args.json {"mode":"DRY"|"APPLY"|"REVERT","run":..,"scene_frame":100,"confirm":"<MODE> S3FIG"}.
Record s3_figures_time_record_<run>.json + Backups/PreS3Figures-<run>/ first; saves ONLY the rise.
Markers S3FIG_<MODE>_OK|run=.. / S3FIG_FAILED|run=..|reason."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
RISE_FILE = "E:/PussStage/Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset"
RUN = {"run": "?"}


def main():
    import unreal
    a = json.load(open(HERE + "s3_figures_time_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    c0 = census()
    if RISE in c0[0]:
        raise RuntimeError("RISE_ALREADY_DIRTY")
    rise = unreal.load_asset(RISE)
    rfps = rise.get_display_rate().numerator / float(rise.get_display_rate().denominator)
    if abs(rfps - 30.0) > 1e-6:
        raise RuntimeError("FPS|%s" % rfps)
    keys = []
    for b in rise.get_bindings():
        for t in b.get_tracks():
            if t.get_class().get_name() != "MovieSceneVisibilityTrack":
                continue
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    for k in ch.get_keys():
                        if bool(k.get_value()):
                            keys.append((str(b.get_display_name()), k))
    frames = sorted(set(int(k.get_time().frame_number.value) for _, k in keys))
    if mode == "REVERT":
        rec_path = HERE + "s3_figures_time_record_%s.json" % a["revert_run"]
        target = json.load(open(rec_path))["from_frame"]
    else:
        target = int(round(float(a["scene_frame"]) / 24.0 * rfps))
    if mode == "DRY":
        unreal.log("S3FIG_DRY_OK|run=%s|n=%d|frames=%s|target=%d|census=%s" % (run, len(keys), frames, target, c0))
        return
    if a.get("confirm") != "%s S3FIG" % mode:
        raise RuntimeError("CONFIRM")
    if len(frames) != 1 or not (0 < target < 930):
        raise RuntimeError("UNEXPECTED|frames=%s|target=%d" % (frames, target))
    if mode == "APPLY":
        rec_path = HERE + "s3_figures_time_record_%s.json" % run
        if os.path.exists(rec_path):
            raise RuntimeError("RECORD_EXISTS")
        json.dump({"run": run, "from_frame": frames[0], "to_frame": target, "n": len(keys),
                   "bindings": sorted(set(n for n, _ in keys))}, open(rec_path, "w"), indent=1)
        bdir = "E:/PussStage/Backups/PreS3Figures-%s" % run
        os.makedirs(bdir)
        shutil.copy2(RISE_FILE, bdir)
    rise.modify()
    for _, k in keys:
        k.set_time(unreal.FrameNumber(target), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    got = sorted(set(int(k.get_time().frame_number.value) for _, k in keys))
    if got != [target]:
        raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    extra = sorted(set(census()[0]) - set(c0[0]))
    if extra != [RISE]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % extra)
    if not unreal.EditorAssetLibrary.save_asset(RISE, only_if_is_dirty=False):
        raise RuntimeError("SAVE_FAILED")
    if RISE in census()[0]:
        raise RuntimeError("DIRTY_AFTER_SAVE")
    if mode == "REVERT":
        os.rename(rec_path, rec_path + ".reverted")
    unreal.log("S3FIG_%s_OK|run=%s|n=%d|%d->%d (rise frames @30)" % (mode, run, len(keys), frames[0], target))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3FIG_FAILED|run=%s|%r" % (RUN["run"], exc))
