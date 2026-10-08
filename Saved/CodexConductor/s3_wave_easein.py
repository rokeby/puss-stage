"""Ease in the old wave cut-outs' slide (Gary 8 Oct ~07:05: "the waves currently begin moving with a slight glitchy
lurch").  Measured: tracks S3.WaveSlide / S3.WaveSplit start at frame 239/240 at full speed (5.2 cm per 3 frames from
the first moving key) while S3.WavesV3.Motion already eases.  Time-warp their curves: g(f) = 239 + (f-239)^2/(2T) for
f < 239+T, g(f) = f - T/2 after (T = 48 frames, 2 s): velocity rises from 0 and the rest of the motion is continuous
(it plays 1 s later).  Each key's value is replaced by the original curve at g(f).  Record + backup; saves
LS_DevScene_03.  Args s3_wave_easein_args.json {"mode":"DRY"|"APPLY","run":..}.  S3EASE_<MODE>_OK / S3EASE_FAILED."""
import json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UA = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
F0, T = 239, 48
def g(f):
    if f <= F0:
        return f
    return F0 + (f - F0) ** 2 / (2.0 * T) if f < F0 + T else f - T / 2.0
def interp(pts, f):
    if f <= pts[0][0]:
        return pts[0][1]
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if a <= f <= b:
            return va if b == a else va + (vb - va) * (f - a) / float(b - a)
    return pts[-1][1]
def main():
    import unreal
    a = json.load(open(HERE + "s3_wave_easein_args.json"))
    run, mode = a["run"], a["mode"]
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("DIRTY|%s" % dirty())
    seq = unreal.load_asset(SC)
    fr = lambda k: int(k.get_time().frame_number.value)
    chans = []
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if str(t.get_display_name()) in ("S3.WaveSlide", "S3.WaveSplit"):
                for s in t.get_sections():
                    for ch in s.get_all_channels():
                        if ch.get_num_keys() > 5:
                            chans.append((str(b.get_display_name()) + "|" + str(ch.get_name()), ch))
    if mode == "DRY":
        unreal.log("S3EASE_DRY_OK|run=%s|channels=%d" % (run, len(chans)))
        return
    before = {n: sorted((fr(k), float(k.get_value())) for k in ch.get_keys()) for n, ch in chans}
    json.dump({"run": run, "before": before}, open(HERE + "s3_wave_easein_record_%s.json" % run, "w"))
    bd = "E:/PussStage/Backups/PreS3WaveEase-%s" % run
    os.makedirs(bd)
    shutil.copy2(UA, bd)
    seq.modify()
    for n, ch in chans:
        pts = before[n]
        for k in ch.get_keys():
            f = fr(k)
            if f > F0:
                k.set_value(interp(pts, g(f)))
    if dirty() != [SC]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % dirty())
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3EASE_APPLY_OK|run=%s|channels=%d" % (run, len(chans)))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3EASE_FAILED|%r" % (exc,))
