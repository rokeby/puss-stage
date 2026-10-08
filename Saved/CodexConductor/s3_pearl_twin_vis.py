"""S3 pearl = the translucent twin for the whole reveal (Gary 8 Oct, in the finishing-touches session: pick "the 4th" =
d_green_twinfade_05: twin MI_PearlClam_Pearl_Fade at half opacity with the green-orange values, glow light as keyed).
Finishing touches did the MI steps (MIS-20261008-044828 opacity 0.5, S3PROPS-20261008-044838 swap, -044841 twin sync).
This tool is step 4, in LS_DevScene_03 only:
  * SOLID pearl ("S3 Hangar Float Hold: S3 PearlClam Pearl" Visibility, section [744,6240]): every key -> False and the
    channel default -> False (hidden for the whole hold; before 744 the rise sub-sequence owns it, which keeps it hidden
    until the clam appears at 1080 [inferred from its 1080 True key]);
  * TWIN ("S3 PearlClam Pearl Fade" Visibility [0,6241]): keys exactly [[0,F],[1080,T],[5040,F]] (was 0 F, 4944 T,
    5040 F). The Fade 1->0 over 4944->5040 is untouched.
The glow light is attached to the SOLID pearl; a hidden parent does not hide an attached actor [inferred; PIE check].
Args s3_pearl_twin_vis_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3PTWIN", "decided_by": ".."}.
Record + Backups/PreS3PearlTwin-<run>; saves LS_DevScene_03 only. Markers S3PTWIN_<MODE>_OK|run=.. / S3PTWIN_FAILED."""
import datetime
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_pearl_twin_vis_record.json"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UA = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
SOLID = "S3 Hangar Float Hold: S3 PearlClam Pearl"
TWIN = "S3 PearlClam Pearl Fade"
TWIN_KEYS = [[0, False], [1080, True], [5040, False]]


def main():
    import unreal
    a = json.load(open(HERE + "s3_pearl_twin_vis_args.json"))
    mode = a["mode"]
    run = datetime.datetime.now().strftime("S3PTWIN-%Y%m%d-%H%M%S")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    seq = unreal.load_asset(SC)
    chans = {}
    for b in seq.get_bindings():
        nm = str(b.get_display_name())
        if nm in (SOLID, TWIN):
            vt = [t for t in b.get_tracks() if t.get_class().get_name() == "MovieSceneVisibilityTrack"]
            if len(vt) != 1 or len(vt[0].get_sections()) != 1:
                raise RuntimeError("TRACKS|%s|%d" % (nm, len(vt)))
            if nm in chans:
                raise RuntimeError("DUP_BINDING|" + nm)
            chans[nm] = list(vt[0].get_sections()[0].get_all_channels())[0]
    if set(chans) != {SOLID, TWIN}:
        raise RuntimeError("MISSING|%s" % sorted(chans))
    read = lambda ch: {"keys": [[int(k.get_time().frame_number.value), bool(k.get_value())] for k in ch.get_keys()], "default": bool(ch.get_default())}
    before = {n: read(c) for n, c in chans.items()}
    if mode == "REVERT":
        rec = json.load(open(REC))
        target = rec["before"]
    else:
        target = {SOLID: {"keys": [[f, False] for f, _ in before[SOLID]["keys"]], "default": False},
                  TWIN: {"keys": TWIN_KEYS, "default": before[TWIN]["default"]}}
    if mode == "DRY":
        unreal.log("S3PTWIN_DRY_OK|run=%s|before=%s|target=%s" % (run, json.dumps(before), json.dumps(target)))
        return
    if a.get("confirm") != "%s S3PTWIN" % mode or not a.get("decided_by"):
        raise RuntimeError("CONFIRM_OR_DECIDED_BY")
    if mode == "APPLY" and os.path.exists(REC):
        raise RuntimeError("RECORD_EXISTS")
    bd = "E:/PussStage/Backups/PreS3PearlTwin-%s" % run
    os.makedirs(bd)
    shutil.copy2(UA, bd)
    if mode == "APPLY":
        json.dump({"run": run, "args": a, "before": before, "target": target, "backup": bd}, open(REC, "w"), indent=1)
    seq.modify()
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    for n, ch in chans.items():
        for k in list(ch.get_keys()):
            ch.remove_key(k)
        for f, v in target[n]["keys"]:
            ch.add_key(unreal.FrameNumber(int(f)), bool(v), time_unit=DR)
        ch.set_default(bool(target[n]["default"]))
    got = {n: read(c) for n, c in chans.items()}
    if got != target:
        raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(got))
    if dirty() != ([SC], []):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty() != ([], []):
        raise RuntimeError("SAVE")
    if mode == "REVERT":
        os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3PTWIN_%s_OK|run=%s|after=%s|backup=%s" % (mode, run, json.dumps(got), bd))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3PTWIN_FAILED|%r" % (exc,))
