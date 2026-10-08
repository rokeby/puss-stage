"""S3 rect lights come on with the second shot (Gary 8 Oct ~06:35: "I need those rects to not be on before the first
ghost light is on, they can come on with the second shot, not the first").  Second shot = B02 at Scene 360 (15 s)
[measured cut 360-720].  For the 10 flickering rects (6 Ground Rows, Warm Side: track S3.WavesV3.Light; Warm Side2/3/4:
track S3.Flame), rebuilt from the S3FLAME-20261008-062908 record's base curves: 0 until ON, linear up to the lit level
by ON+24, held to 528, then the original base (shimmer, take dim-outs) — all x the same flame factor and phases as
S3FLAME.  Keys replaced every 2 frames.  Record + backup; saves LS_DevScene_03.  Args s3_rect_on_at_args.json
{"mode":"DRY"|"APPLY","run":..,"on":360}.  S3RECTON_<MODE>_OK / S3RECTON_FAILED."""
import json
import os
import runpy
import shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UA = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
REC_SRC = HERE + "s3_rect_flame_record_S3FLAME-20261008-062908.json"
END = 6240


def main():
    import unreal
    F = runpy.run_path(HERE + "s3_rect_flame.py", init_globals={"__name__": "lib"}) if False else None
    ns = {}
    src = open(HERE + "s3_rect_flame.py").read().split("def main():")[0]
    exec(src, ns)
    flame, curve_at = ns["flame"], ns["curve_at"]
    a = json.load(open(HERE + "s3_rect_on_at_args.json"))
    run, mode, ON = a["run"], a["mode"], int(a.get("on", 360))
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("DIRTY|%s" % dirty())
    rec = json.load(open(REC_SRC))
    plan = rec["plan"]
    order = sorted(plan)                       # same ordering/phases as S3FLAME
    targets = [k for k in order if k.startswith("S3 WaveV3 ")]
    seq = unreal.load_asset(SC)
    chans = {}
    for b in seq.get_bindings():
        p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else ""
        if own in targets:
            for t in b.get_tracks():
                if str(t.get_display_name()) in ("S3.WavesV3.Light", "S3.Flame"):
                    chans.setdefault(own, []).append(list(t.get_sections()[0].get_all_channels())[0])
    if sorted(chans) != sorted(targets) or any(len(v) != 1 for v in chans.values()):
        raise RuntimeError("CHANNELS|%s" % {k: len(v) for k, v in chans.items()})
    if mode == "DRY":
        unreal.log("S3RECTON_DRY_OK|run=%s|on=%d|lights=%s" % (run, ON, targets))
        return
    fr = lambda k: int(k.get_time().frame_number.value)
    json.dump({"run": run, "on": ON, "before": {k: [(fr(x), x.get_value()) for x in chans[k][0].get_keys()] for k in targets}},
              open(HERE + "s3_rect_on_at_record_%s.json" % run, "w"))
    bd = "E:/PussStage/Backups/PreS3RectOn-%s" % run
    os.makedirs(bd)
    shutil.copy2(UA, bd)
    seq.modify()
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    for lab in targets:
        p = plan[lab]
        ph = order.index(lab) * 1.37
        if p["kind"] == "keyed":
            pts = [tuple(x) for x in p["pts"]]
            lit = curve_at(pts, 528)
            base = lambda f, pts=pts, lit=lit: 0.0 if f < ON else (lit * (f - ON) / 24.0 if f < ON + 24 else (lit if f < 528 else curve_at(pts, f)))
        else:
            I = p["intensity"]
            base = lambda f, I=I: 0.0 if f < ON else (I * (f - ON) / 24.0 if f < ON + 24 else I)
        ch = chans[lab][0]
        for k in list(ch.get_keys()):
            ch.remove_key(k)
        ch.add_key(unreal.FrameNumber(0), 0.0, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        f = ON
        while f <= END:
            v = base(f)
            ch.add_key(unreal.FrameNumber(f), v * flame(f, ph) if v > 1e-6 else 0.0, time_unit=DR,
                       interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
            f += 2
        if any(abs(x.get_value()) > 1e-6 for x in ch.get_keys() if fr(x) < ON):
            raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % lab)
    if dirty() != [SC]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % dirty())
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3RECTON_APPLY_OK|run=%s|on=%d|lights=%d" % (run, ON, len(targets)))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3RECTON_FAILED|%r" % (exc,))
