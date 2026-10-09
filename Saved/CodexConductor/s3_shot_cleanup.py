"""S3 SHADOW-SHOT CLEANUP (Gary 8 Oct ~20:40, image 4 at 2:46: "shadow is great - but there's a weird cube. we can also
probably lose that white light in the lower left side so it's not disrupting the nice shadow").
[meas] pie_screen_find (t=166.1, cam (12772, 159203, 108)): the cube = 'S3 Practical R2 Body' (StaticMeshActor 15x15x11,
its light 'S3 Practical R2' at 0); the lower-left light = 'S3 Crowd Rim C' (1170 cd).  The shot = 'S3 Choir Close B'
[3688, 4146] (probe_s3_cuts).
WRITES (record s3_shot_cleanup_record.json + Backups/PreS3ShotCleanup-<run>; REVERT exact):
  1. 'S3 Practical R2 Body' hidden in game (actor bHidden; level).
  2. 'S3 Crowd Rim C' S3.Crowd.Light keys: value held to SHOT_A-1, 0 over [SHOT_A, SHOT_B-1], back at SHOT_B (keys added;
     any existing key inside (SHOT_A-1, SHOT_B) recorded and removed).
Saves the map + LS_DevScene_03.  Args s3_shot_cleanup_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3SHOTCLEAN",
"run"}.  S3SHOTCLEAN_<MODE>_OK / _FAILED."""
import json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_shot_cleanup_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
CUBE, RIM, TRACK = "S3 Practical R2 Body", "S3 Crowd Rim C", "S3.Crowd.Light"
SHOT_A, SHOT_B = 3688, 4146


def main():
    import unreal
    a = json.load(open(HERE + "s3_shot_cleanup_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    acts = {str(x.get_actor_label()): x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    if CUBE not in acts or RIM not in acts: raise RuntimeError("MISSING")
    seq = unreal.load_asset(SCENE)
    ch = None
    for b in seq.get_bindings():
        par = b.get_parent()                                   # component possessable under the actor binding
        if str(b.get_display_name()).startswith(RIM) or (par is not None and str(par.get_display_name()).startswith(RIM)):
            for t in b.get_tracks():
                if str(t.get_display_name()) == TRACK: ch = list(t.get_sections()[0].get_all_channels())[0]
    if ch is None: raise RuntimeError("NO_RIM_TRACK")
    keys = sorted([[int(k.get_time().frame_number.value), float(k.get_value())] for k in ch.get_keys()])
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    val_a = [v for f, v in keys if f <= SHOT_A]
    val_b = [v for f, v in keys if f <= SHOT_B]
    if mode == "DRY":
        unreal.log("S3SHOTCLEAN_DRY_OK|run=%s|cube_hidden=%s|rim_keys=%s|value_at_A=%s|value_at_B=%s" % (
            run, acts[CUBE].get_editor_property("hidden"), keys, val_a[-1] if val_a else None, val_b[-1] if val_b else None))
        return
    if a.get("confirm") != "%s S3SHOTCLEAN" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3ShotCleanup-%s" % run
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        rec = {"run": run, "backup": bd, "cube_hidden_before": bool(acts[CUBE].get_editor_property("hidden")), "rim_keys_before": keys}
        json.dump(rec, open(REC, "w"), indent=1)
        acts[CUBE].modify(); acts[CUBE].set_actor_hidden_in_game(True)
        va, vb = (val_a[-1] if val_a else 0.0), (val_b[-1] if val_b else 0.0)
        for k in list(ch.get_keys()):
            if SHOT_A - 1 < int(k.get_time().frame_number.value) < SHOT_B + 1: ch.remove_key(k)
        LIN = unreal.MovieSceneKeyInterpolation.LINEAR
        for f, v in ((SHOT_A - 1, va), (SHOT_A, 0.0), (SHOT_B - 1, 0.0), (SHOT_B, vb)):
            ch.add_key(unreal.FrameNumber(f), float(v), time_unit=DR, interpolation=LIN)
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        rec = json.load(open(REC)); os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        acts[CUBE].modify(); acts[CUBE].set_actor_hidden_in_game(rec["cube_hidden_before"])
        for k in list(ch.get_keys()): ch.remove_key(k)
        for f, v in rec["rim_keys_before"]:
            ch.add_key(unreal.FrameNumber(f), float(v), time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    else:
        raise RuntimeError("MODE")
    if census() != ([SCENE], [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False): raise RuntimeError("SAVE_SCENE")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3SHOTCLEAN_%s_OK|run=%s|cube_hidden=%s|rim_keys=%s|backup=%s" % (mode, run, acts[CUBE].get_editor_property("hidden"),
               sorted([[int(k.get_time().frame_number.value), round(float(k.get_value()), 1)] for k in ch.get_keys()])[:12], bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3SHOTCLEAN_FAILED|%r" % (exc,))
