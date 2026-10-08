"""Move keys (time only) on one light's intensity track in LS_DevScene_03.  Args s3_key_move_args.json
{"mode":"DRY"|"APPLY","run":..,"owner":"S3 Drama Pearl Glow","track":"S3.Drama.Light","map":{"1440":1488,"1560":1536},
 "why":"..."}.  Record s3_key_move_record_<run>.json + backup first; saves LS_DevScene_03 only.
Markers S3KEYMOVE_<MODE>_OK|run=.. / S3KEYMOVE_FAILED|run=..|reason."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
RUN = {"run": "?"}


def main():
    import unreal
    a = json.load(open(HERE + "s3_key_move_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    lib = unreal.EditorLoadingAndSavingUtils
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census()[0]:
        raise RuntimeError("CONTENT_DIRTY|%s" % (census(),))
    seq = unreal.load_asset(SCENE)
    mp = {int(k): int(v) for k, v in a["map"].items()}
    fr = lambda k: int(k.get_time().frame_number.value)
    hits = []
    for b in seq.get_bindings():
        p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
        if own != a["owner"]:
            continue
        for t in b.get_tracks():
            if str(t.get_display_name()) != a["track"]:
                continue
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    allk = [(fr(k), round(k.get_value(), 3)) for k in ch.get_keys()]
                    hits.append((ch, allk))
    if len(hits) != 1:
        raise RuntimeError("CHANNELS|%d" % len(hits))
    ch, before = hits[0]
    if sorted(mp) != sorted(f for f, _ in before if f in mp):
        raise RuntimeError("FROM_KEYS_MISSING|%s|have=%s" % (sorted(mp), before))
    if mode == "DRY":
        unreal.log("S3KEYMOVE_DRY_OK|run=%s|before=%s|map=%s" % (run, before, mp))
        return
    rec = HERE + "s3_key_move_record_%s.json" % run
    json.dump({"run": run, "args": a, "before": before}, open(rec, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3KeyMove-%s" % run
    os.makedirs(bdir)
    shutil.copy2(UASSET, bdir)
    seq.modify()
    for k in list(ch.get_keys()):
        if fr(k) in mp:
            k.set_time(unreal.FrameNumber(mp[fr(k)]), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    after = sorted((fr(k), round(k.get_value(), 3)) for k in ch.get_keys())
    want = sorted((mp.get(f, f), v) for f, v in before)
    if after != want:
        raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % after)
    if census()[0] != [SCENE]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or census()[0]:
        raise RuntimeError("SAVE")
    unreal.log("S3KEYMOVE_APPLY_OK|run=%s|after=%s" % (run, after))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3KEYMOVE_FAILED|run=%s|%r" % (RUN["run"], exc))
