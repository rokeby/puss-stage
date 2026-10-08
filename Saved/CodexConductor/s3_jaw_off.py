"""S3 JAW GLINT OFF (Gary 8 Oct ~19:00: "now that we get some nice glint from these fires - switch off the light on the
jawbone, no longer needed").  Sets the 'S3 Jaw Glint' light component Visible=False (its S3.Drama.Light intensity keys
stay; an invisible light emits nothing).  Map-only save; record s3_jaw_off_record.json + Backups/PreS3JawOff-<run>.
Args s3_jaw_off_args.json {"mode": "APPLY"|"REVERT", "confirm": "<MODE> S3JAWOFF"}.  S3JAWOFF_<MODE>_OK / S3JAWOFF_FAILED."""
import datetime, json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_jaw_off_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LABEL = "S3 Jaw Glint"


def main():
    import unreal
    a = json.load(open(HERE + "s3_jaw_off_args.json"))
    mode = a["mode"]
    run = datetime.datetime.now().strftime("S3JAWOFF-%Y%m%d-%H%M%S")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    if a.get("confirm") != "%s S3JAWOFF" % mode: raise RuntimeError("CONFIRM")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    hits = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if str(x.get_actor_label()) == LABEL]
    if len(hits) != 1: raise RuntimeError("ACTOR|%d" % len(hits))
    lc = hits[0].get_component_by_class(unreal.LightComponent)
    before = bool(lc.is_visible())
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        want = False
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        want = bool(json.load(open(REC))["before_visible"])
    else:
        raise RuntimeError("MODE")
    bd = "E:/PussStage/Backups/PreS3JawOff-%s" % run
    os.makedirs(bd); shutil.copy2(UMAP, bd)
    if mode == "APPLY":
        json.dump({"run": run, "before_visible": before, "backup": bd}, open(REC, "w"), indent=1)
    hits[0].modify(); lc.modify(); lc.set_visibility(want, False)
    if bool(lc.is_visible()) != want: raise RuntimeError("READBACK_BEFORE_SAVE|NOTHING SAVED; Don't-Save restart")
    if census() != ([], [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    if bool(lc.is_visible()) != want: raise RuntimeError("READBACK_AFTER_SAVE")
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3JAWOFF_%s_OK|run=%s|visible %s->%s|backup=%s" % (mode, run, before, want, bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3JAWOFF_FAILED|%r" % (exc,))
