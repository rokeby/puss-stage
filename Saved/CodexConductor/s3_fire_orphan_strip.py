"""S3 FIRE ORPHAN STRIP (9 Oct).  [meas S3FIREVISPROBE] each of S3 Fire A/B/C and S3 Ghost Light Flame has TWO top-level
bindings in LS_DevScene_03; one resolves to the level actor, the other resolves to nothing (locate_bound_objects=[]) and
holds only a duplicate visibility track (same keys).  Orphans are inert but trip S3 polish's one-track guard (and would
keep the OLD ignition frame if they ever re-resolved).  Removes bindings with those names that (a) resolve to nothing in
the editor world and (b) carry only MovieSceneVisibilityTrack.  Backup; REVERT = copy the backup uasset back with the
editor closed (binding removal has no in-editor undo path here).  Args s3_fire_orphan_strip_args.json
{"mode": DRY|APPLY, "confirm": "APPLY S3FIREORPHAN"}.  Markers S3FIREORPHAN_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
SCENE_FILE = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
NAMES = ("S3 Fire A", "S3 Fire B", "S3 Fire C", "S3 Ghost Light Flame")


def main():
    import unreal
    a = json.load(open(HERE + "s3_fire_orphan_strip_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S3FIREORPHAN-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    seq = unreal.load_asset(SCENE)
    live, orph = {}, []
    for b in seq.get_bindings():
        n = str(b.get_display_name())
        if n not in NAMES: continue
        if seq.locate_bound_objects(b, w):
            live[n] = live.get(n, 0) + 1
        elif all(isinstance(t, unreal.MovieSceneVisibilityTrack) for t in b.get_tracks()) and not b.get_child_possessables():
            orph.append(b)
    if sorted(live) != sorted(NAMES) or any(v != 1 for v in live.values()): raise RuntimeError("LIVE|%s" % live)
    ids = [(str(b.get_display_name()), b.get_id().export_text()) for b in orph]
    if mode == "DRY":
        unreal.log("S3FIREORPHAN_DRY_OK|live=%s|orphans=%s" % (live, ids)); return
    if mode != "APPLY" or a.get("confirm") != "APPLY S3FIREORPHAN": raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3FireOrphan-%s" % run; os.makedirs(bd); shutil.copy2(SCENE_FILE, bd)
    json.dump({"run": run, "backup": bd, "removed": ids}, open(HERE + "s3_fire_orphan_strip_record.json", "w"), indent=1)
    for b in orph: b.remove()
    left = [str(b.get_display_name()) for b in seq.get_bindings() if b.get_id().export_text() in {i for _, i in ids}]
    if left: raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % left)
    if census() != ([SCENE], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or census() != ([], []): raise RuntimeError("SAVE")
    unreal.log("S3FIREORPHAN_APPLY_OK|run=%s|removed=%s|backup=%s" % (run, ids, bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3FIREORPHAN_FAILED|%r" % (exc,))
