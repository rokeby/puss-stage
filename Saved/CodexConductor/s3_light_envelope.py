"""Multiply S3 light intensity curves by a gain envelope (keys only, LS_DevScene_03).
First use (Gary 8 Oct ~06:45): "at 2.43, where the second round of choir energy ignites ... a lift in the whiter
lighting, by about 25% say. Then it should come down again when Puss is thinking about stealing the song, so we focus on
the light of the pearl."  Whiter lighting = the four cool 6500 K wall grazes (S3 Drama Graze *), the lights that came on
with the choir [inferred: the choir bulbs are emissive only and their glow is a material value, not keyed].
Envelope (Scene frames @24): 1.0 @3912 (2:43) -> 1.25 @3960 (2:45), held to 4488 (3:07 chorus ends) -> 1.0 @4560
(3:10); the existing take dimming continues after.
Anchor keys are added at every envelope breakpoint from the current curve, then every key inside the envelope span is
multiplied by the interpolated gain.  Args s3_light_envelope_args.json {"mode":"DRY"|"APPLY","run":..,"prefixes":[..],
"track":"S3.Drama.Light","env":[[f,g],..]}.  Record + backup; saves LS_DevScene_03.  S3ENV_<MODE>_OK / S3ENV_FAILED."""
import json
import os
import shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UA = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"


def interp(pts, f):
    if f <= pts[0][0]:
        return pts[0][1]
    if f >= pts[-1][0]:
        return pts[-1][1]
    for (f0, v0), (f1, v1) in zip(pts, pts[1:]):
        if f0 <= f <= f1:
            return v0 if f1 == f0 else v0 + (v1 - v0) * (f - f0) / float(f1 - f0)


def main():
    import unreal
    a = json.load(open(HERE + "s3_light_envelope_args.json"))
    run, mode, env = a["run"], a["mode"], [tuple(x) for x in a["env"]]
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("DIRTY|%s" % dirty())
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")      # 8 Oct: a save during PIE returns False (first APPLY left the scene dirty)
    seq = unreal.load_asset(SC)
    fr = lambda k: int(k.get_time().frame_number.value)
    chans = {}
    for b in seq.get_bindings():
        p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else ""
        if any(own.startswith(x) for x in a["prefixes"]):
            for t in b.get_tracks():
                if str(t.get_display_name()) == a["track"]:
                    chans[own] = list(t.get_sections()[0].get_all_channels())[0]
    if mode == "DRY":
        unreal.log("S3ENV_DRY_OK|run=%s|lights=%s|env=%s" % (run, sorted(chans), env))
        return
    before = {o: sorted((fr(k), float(k.get_value())) for k in ch.get_keys()) for o, ch in chans.items()}
    json.dump({"run": run, "args": a, "before": before}, open(HERE + "s3_light_envelope_record_%s.json" % run, "w"))
    bd = "E:/PussStage/Backups/PreS3Env-%s" % run
    os.makedirs(bd)
    shutil.copy2(UA, bd)
    seq.modify()
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    lo, hi = env[0][0], env[-1][0]
    for o, ch in chans.items():
        pts = before[o]
        have = set(f for f, _ in pts)
        for f, _g in env:
            if f not in have:
                ch.add_key(unreal.FrameNumber(f), interp(pts, f), time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        for k in ch.get_keys():
            f = fr(k)
            if lo <= f <= hi:
                k.set_value(k.get_value() * interp(env, f))
    if dirty() != [SC]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % dirty())
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3ENV_APPLY_OK|run=%s|lights=%d|after=%s" % (run, len(chans), {o: sorted((fr(k), round(k.get_value())) for k in ch.get_keys())[:9] for o, ch in list(chans.items())[:1]}))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3ENV_FAILED|%r" % (exc,))
