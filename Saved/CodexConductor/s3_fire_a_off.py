"""S3 FIRE A OFF (Gary 8 Oct ~21:05: "Fire A and fire B should not be together. Turn one of them off.").  Fire A sits
~25 cm from Fire B (S3REGATHER DRY: A (14448, 160623), B (14430, 160640)).  Hides 'S3 Fire A' (emitter) and
'S3 Fire A Light' in game, and DEACTIVATES Fire A's visibility section in LS_DevScene_03 (it would un-hide the emitter at
ignition).  The light's flicker keys stay (a hidden light emits nothing).  Record + backup; REVERT exact.
Args s3_fire_a_off_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3FIREAOFF"}.  S3FIREAOFF_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_fire_a_off_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
ACTORS = ["S3 Fire A", "S3 Fire A Light"]


def main():
    import unreal
    a = json.load(open(HERE + "s3_fire_a_off_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S3FIREAOFF-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    acts = {str(x.get_actor_label()): x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    if any(n not in acts for n in ACTORS): raise RuntimeError("MISSING")
    seq = unreal.load_asset(SCENE)
    vis = []
    for b in seq.get_bindings():
        par = b.get_parent()
        nm = str(b.get_display_name()); pn = str(par.get_display_name()) if par is not None else ""
        if nm == "S3 Fire A" or pn == "S3 Fire A":
            for t in b.get_tracks():
                if isinstance(t, unreal.MovieSceneVisibilityTrack):
                    vis += list(t.get_sections())
    if mode == "DRY":
        unreal.log("S3FIREAOFF_DRY_OK|vis_sections=%d|hidden=%s" % (len(vis), {n: acts[n].get_editor_property("hidden") for n in ACTORS})); return
    if a.get("confirm") != "%s S3FIREAOFF" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3FireAOff-%s" % run; os.makedirs(bd)
    for f in FILES: shutil.copy2(f, bd)
    if mode == "APPLY":
        if os.path.exists(REC) or not vis: raise RuntimeError("PRECONDITION|vis=%d" % len(vis))
        json.dump({"run": run, "backup": bd, "hidden": {n: bool(acts[n].get_editor_property("hidden")) for n in ACTORS},
                   "vis_active": [bool(s.is_active()) for s in vis]}, open(REC, "w"), indent=1)
        for n in ACTORS: acts[n].modify(); acts[n].set_actor_hidden_in_game(True)
        for s in vis: s.set_is_active(False)
    elif mode == "REVERT":
        r = json.load(open(REC))
        for n in ACTORS: acts[n].modify(); acts[n].set_actor_hidden_in_game(r["hidden"][n])
        for s, act in zip(vis, r["vis_active"]): s.set_is_active(act)
    else:
        raise RuntimeError("MODE")
    if census() != ([SCENE], [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False): raise RuntimeError("SAVE_SCENE")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []): raise RuntimeError("SAVE")
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3FIREAOFF_%s_OK|run=%s|hidden=%s|vis_active=%s|backup=%s" % (mode, run, {n: acts[n].get_editor_property("hidden") for n in ACTORS}, [s.is_active() for s in vis], bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3FIREAOFF_FAILED|%r" % (exc,))
