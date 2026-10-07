"""Restore the saved-LANDED convention (memory puss-level-saved-landed-frame-trap): the six 'S<n> Hangar Root' actors were
found folded at pitch -90 in the editor world on 7 Oct ~19:40 (probe_roots). Set pitch 0 (keep location, roll, yaw),
record first, umap backup, census exact (map only), save, read back. Args hangar_roots_land_args.json
{"mode":"DRY"|"APPLY"|"REVERT","confirm":"<MODE> ROOTSLAND","run":"..."}. Markers ROOTSLAND_<MODE>_OK / ROOTSLAND_FAILED."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "hangar_roots_land_record.json"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def main():
    import unreal
    a = json.load(open(HERE + "hangar_roots_land_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    w = ed.get_editor_world()
    roots = {str(x.get_actor_label()): x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
             if str(x.get_actor_label()).endswith("Hangar Root") and str(x.get_actor_label()).startswith("S")}
    if len(roots) != 6:
        raise RuntimeError("ROOT_COUNT|%d" % len(roots))
    cur = {k: [x.get_actor_rotation().roll, x.get_actor_rotation().pitch, x.get_actor_rotation().yaw] for k, x in roots.items()}
    if mode == "DRY":
        unreal.log("ROOTSLAND_DRY_OK|run=%s|%s|census=%s" % (run, json.dumps(cur), census()))
        return
    if census() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    if mode == "APPLY":
        if a.get("confirm") != "APPLY ROOTSLAND" or os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_RECORD")
        json.dump({"run": run, "state": "applying", "before": cur}, open(REC, "w"), indent=1)
        b = "E:/PussStage/Backups/PreRootsLand-%s" % run
        os.makedirs(b)
        shutil.copy2(UMAP, b)
        target = {k: [v[0], 0.0, v[2]] for k, v in cur.items()}
    elif mode == "REVERT":
        if a.get("confirm") != "REVERT ROOTSLAND" or not os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_NO_RECORD")
        target = json.load(open(REC))["before"]
    else:
        raise RuntimeError("MODE")
    for k, x in roots.items():
        x.modify()
        t = target[k]
        x.set_actor_rotation(unreal.Rotator(roll=t[0], pitch=t[1], yaw=t[2]), False)
    for k, x in roots.items():
        r = x.get_actor_rotation()
        if abs(r.pitch - target[k][1]) > 0.01 or abs(((r.yaw - target[k][2]) + 180) % 360 - 180) > 0.01:
            raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % k)
    if census() != ([], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(MAP, only_if_is_dirty=False):
        raise RuntimeError("SAVE_FAILED")
    if census() != ([], []):
        raise RuntimeError("DIRTY_AFTER|%s" % (census(),))
    if mode == "APPLY":
        json.dump({"run": run, "state": "applied", "before": cur}, open(REC, "w"), indent=1)
    else:
        os.rename(REC, REC + ".reverted-" + run)
    unreal.log("ROOTSLAND_%s_OK|run=%s|n=6" % (mode, run))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("ROOTSLAND_FAILED|%r" % (exc,))
