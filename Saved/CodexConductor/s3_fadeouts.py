"""S3 take: successive lights dim out (Gary 8 Oct ~05:35 UTC): "as we pause for him to take it, the camera pulls to a
wide shot and to a blurry bokeh, at which point the pearl dims (and should later disappear) to indicate that he has
taken it, and then successive lights should dim out, leaving us almost in total darkness with a single light and the
sound of sobbing."  The single light left = the ghost-light flame.
For each (owner prefix, track, t0, t1): keys after t0 are multiplied by a linear ramp 1 -> 0 reaching 0 at t1 and held 0
(anchor keys are added at t0 and t1 from the existing curve).  Keys before t0 untouched.  LS_DevScene_03 only.
Args s3_fadeouts_args.json {"mode":"DRY"|"APPLY","run":..,"fades":[[prefix, track, t0, t1], ...]}.
Record + backup; saves LS_DevScene_03.  S3FADES_<MODE>_OK / S3FADES_FAILED."""
import json
import os
import shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UA = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"


def main():
    import unreal
    a = json.load(open(HERE + "s3_fadeouts_args.json"))
    run, mode = a["run"], a["mode"]
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("DIRTY|%s" % dirty())
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    seq = unreal.load_asset(SC)
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    fr = lambda k: int(k.get_time().frame_number.value)
    plan = []
    for prefix, track, t0, t1 in a["fades"]:
        for b in seq.get_bindings():
            p = b.get_parent()
            own = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
            if not own.startswith(prefix):
                continue
            for t in b.get_tracks():
                if str(t.get_display_name()) == track:
                    plan.append((own, list(t.get_sections()[0].get_all_channels())[0], int(t0), int(t1)))
    summary = {}
    for own, ch, t0, t1 in plan:
        summary[own] = [t0, t1, ch.get_num_keys()]
    if mode == "DRY":
        unreal.log("S3FADES_DRY_OK|run=%s|n=%d|%s" % (run, len(plan), json.dumps(summary)))
        return
    before = {own: [(fr(k), float(k.get_value())) for k in ch.get_keys()] for own, ch, _, _ in plan}
    json.dump({"run": run, "args": a, "before": before}, open(HERE + "s3_fadeouts_record_%s.json" % run, "w"))
    bd = "E:/PussStage/Backups/PreS3Fades-%s" % run
    os.makedirs(bd)
    shutil.copy2(UA, bd)
    seq.modify()

    def val_at(pts, f):
        prev = max((q for q in pts if q[0] <= f), key=lambda q: q[0])
        nxts = [q for q in pts if q[0] >= f]
        if not nxts:
            return prev[1]
        nxt = min(nxts, key=lambda q: q[0])
        return prev[1] if nxt[0] == prev[0] else prev[1] + (nxt[1] - prev[1]) * (f - prev[0]) / float(nxt[0] - prev[0])
    for own, ch, t0, t1 in plan:
        pts = before[own]
        for k in ch.get_keys():
            f = fr(k)
            if f > t0:
                g = 0.0 if f >= t1 else 1.0 - (f - t0) / float(t1 - t0)
                k.set_value(k.get_value() * g)
        have = set(fr(k) for k in ch.get_keys())
        if t0 not in have:
            ch.add_key(unreal.FrameNumber(t0), val_at(pts, t0), time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        if t1 not in have:
            ch.add_key(unreal.FrameNumber(t1), 0.0, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        if any(abs(k.get_value()) > 1e-4 for k in ch.get_keys() if fr(k) >= t1):
            raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % own)
    if dirty() != [SC]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % dirty())
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3FADES_APPLY_OK|run=%s|n=%d" % (run, len(plan)))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3FADES_FAILED|%r" % (exc,))
