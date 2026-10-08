"""Gentle handheld shake on S3 Shot B06, the long wall shot (Gary 8 Oct ~07:00: "the long shot of the wall could also
have a gently bit of handheld shake").  Gary's B06 keys are NOT touched: a second section with blend type ADDITIVE is
added to B06's Transform track over its cut [3000, 3480] [measured probe_s3_shots], keyed every 3 frames with smooth
deterministic noise (sum of sines): location +-0.6 cm, pitch/yaw +-0.25 deg, roll +-0.12 deg, eased in/out over 12
frames.  Delete that one section to undo.  Record + backup; saves LS_DevScene_03.  Args s3_handheld_args.json
{"mode":"DRY"|"APPLY","run":..,"camera":"S3 Shot B06","range":[3000,3480]}.  S3HAND_<MODE>_OK / S3HAND_FAILED."""
import json, math, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UA = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
AMP = {"Location.X": 0.6, "Location.Y": 0.6, "Location.Z": 0.5, "Rotation.X": 0.12, "Rotation.Y": 0.25, "Rotation.Z": 0.25}
def noise(t, seed):
    return (0.55 * math.sin(2 * math.pi * 0.43 * t + seed) + 0.30 * math.sin(2 * math.pi * 1.07 * t + 2.1 * seed)
            + 0.15 * math.sin(2 * math.pi * 2.3 * t + 3.7 * seed))
def main():
    import unreal
    a = json.load(open(HERE + "s3_handheld_args.json"))
    run, mode, cam = a["run"], a["mode"], a.get("camera", "S3 Shot B06")
    lo, hi = a.get("range", [3000, 3480])
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("DIRTY|%s" % dirty())
    seq = unreal.load_asset(SC)
    tracks = [t for b in seq.get_bindings() if str(b.get_display_name()) == cam for t in b.get_tracks()
              if t.get_class().get_name() == "MovieScene3DTransformTrack"]
    if len(tracks) != 1:
        raise RuntimeError("TRACK|%d" % len(tracks))
    t = tracks[0]
    if any(str(s.get_blend_type().blend_type) .endswith("ADDITIVE") for s in t.get_sections() if s.get_blend_type().is_valid):
        raise RuntimeError("ALREADY_HAS_ADDITIVE")
    if mode == "DRY":
        unreal.log("S3HAND_DRY_OK|run=%s|camera=%s|sections=%d|range=%s" % (run, cam, len(t.get_sections()), [lo, hi]))
        return
    json.dump({"run": run, "camera": cam, "range": [lo, hi]}, open(HERE + "s3_handheld_record_%s.json" % run, "w"))
    bd = "E:/PussStage/Backups/PreS3Handheld-%s" % run
    os.makedirs(bd)
    shutil.copy2(UA, bd)
    seq.modify()
    s = t.add_section()
    s.set_blend_type(unreal.MovieSceneBlendType.ADDITIVE)
    s.set_range(lo, hi + 1)
    chans = {str(c.get_name()).rsplit("_", 1)[0]: c for c in s.get_all_channels()}
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    for i, (name, amp) in enumerate(AMP.items()):
        ch = chans[name]
        f = lo
        while f <= hi:
            e = min(1.0, (f - lo) / 12.0, (hi - f) / 12.0)
            ch.add_key(unreal.FrameNumber(f), amp * e * noise(f / 24.0, 1.3 * i + 0.4), time_unit=DR,
                       interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
            f += 3
    if chans["Rotation.Y"].get_num_keys() < 100 or dirty() != [SC]:
        raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % dirty())
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3HAND_APPLY_OK|run=%s|camera=%s|range=%s|keys_per_channel=%d" % (run, cam, [lo, hi], chans["Rotation.Y"].get_num_keys()))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3HAND_FAILED|%r" % (exc,))
