"""Fix S3 figures/clam vanishing at the end of the Hangar Fold (measured 8 Oct 05:5x: bHidden flips True between S3
31.0 and 35.4 s while PLAYING; the fold sub-section ends at Scene 777 = 32.4 s).  Set CompletionMode KEEP_STATE on every
Visibility section in LS_S3_HangarRise so ending the section does not restore the pre-animated (hidden) state.
Args s3_rise_keepstate_args.json {"mode":"DRY"|"APPLY"|"REVERT","run":..}.  Record + backup; saves the rise only.
S3KEEP_<MODE>_OK / S3KEEP_FAILED."""
import json
import os
import shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
UA = "E:/PussStage/Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset"
def main():
    import unreal
    a = json.load(open(HERE + "s3_rise_keepstate_args.json"))
    run, mode = a["run"], a["mode"]
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("DIRTY|%s" % dirty())
    rise = unreal.load_asset(RISE)
    secs = []
    for b in rise.get_bindings():
        for t in b.get_tracks():
            if t.get_class().get_name() == "MovieSceneVisibilityTrack":
                for s in t.get_sections():
                    secs.append((str(b.get_display_name()), s))
    before = {n: str(s.get_completion_mode()) for n, s in secs}
    if mode == "DRY":
        unreal.log("S3KEEP_DRY_OK|run=%s|n=%d|modes=%s" % (run, len(secs), sorted(set(before.values()))))
        return
    rec = HERE + "s3_rise_keepstate_record.json"
    if mode == "APPLY":
        json.dump({"run": run, "before": before}, open(rec, "w"), indent=1)
        bd = "E:/PussStage/Backups/PreS3KeepState-%s" % run
        os.makedirs(bd)
        shutil.copy2(UA, bd)
        target = {n: unreal.MovieSceneCompletionMode.KEEP_STATE for n, _ in secs}
    else:
        old = json.load(open(rec))["before"]
        conv = {"MovieSceneCompletionModeOverride.KEEP_STATE": unreal.MovieSceneCompletionMode.KEEP_STATE,
                "MovieSceneCompletionMode.RESTORE_STATE": unreal.MovieSceneCompletionMode.RESTORE_STATE,
                "<MovieSceneCompletionMode.PROJECT_DEFAULT: 2>": unreal.MovieSceneCompletionMode.PROJECT_DEFAULT}
        target = {n: conv[old[n]] for n, _ in secs}
    rise.modify()
    for n, s in secs:
        s.set_completion_mode(target[n])
    if any(s.get_completion_mode() != target[n] for n, s in secs) or dirty() != [RISE]:
        raise RuntimeError("READBACK_OR_CENSUS|%s|NOTHING SAVED; Don't-Save restart" % dirty())
    if not unreal.EditorAssetLibrary.save_asset(RISE, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3KEEP_%s_OK|run=%s|n=%d|now=%s" % (mode, run, len(secs), sorted(set(str(s.get_completion_mode()) for _, s in secs))))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3KEEP_FAILED|%r" % (exc,))
