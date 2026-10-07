"""S2 ceiling wings face the wrong way down the alley (Gary 7 Oct). Turn the 6 SM_S2_ceiling_wing actors in Klara's
Japanese_Alley level 180 deg about Z in place (yaw -43.6 -> 136.4). Her map is saved behind a backup + exact census
(precedent klara_reveal.py:2758-2771). Args s2_ceiling_flip_args.json {"mode":"DRY"|"APPLY"|"REVERT","confirm":...,"run":...}.
Markers S2CEIL_<MODE>_OK|run= / S2CEIL_FAILED|run=|reason."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
MAP = "/Game/Japanese_Alley/Maps/Japanese_Alley"
UMAP = "E:/PussStage/Content/Japanese_Alley/Maps/Japanese_Alley.umap"
REC = HERE + "s2_ceiling_flip_record.json"
MESH = "SM_S2_ceiling_wing"


def main():
    import unreal
    a = json.load(open(HERE + "s2_ceiling_flip_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))

    w = ed.get_editor_world()
    acts = [x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.StaticMeshActor)
            if x.static_mesh_component.static_mesh and x.static_mesh_component.static_mesh.get_name() == MESH
            and x.get_outermost().get_name() == MAP]
    rows = {str(x.get_actor_label()): x for x in acts}
    cur = {k: [x.get_actor_rotation().roll, x.get_actor_rotation().pitch, x.get_actor_rotation().yaw,
               x.get_actor_location().x, x.get_actor_location().y, x.get_actor_location().z] for k, x in rows.items()}
    if mode == "DRY":
        unreal.log("S2CEIL_DRY_OK|run=%s|n=%d|census=%s|%s" % (run, len(rows), census(), json.dumps(cur)))
        return
    if census() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    if mode == "APPLY":
        if a.get("confirm") != "APPLY S2CEIL" or os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_RECORD_EXISTS")
        if len(rows) != 6 or any(abs(((v[2] + 43.6) + 180) % 360 - 180) > 0.5 for v in cur.values()):
            raise RuntimeError("UNEXPECTED_STATE|%s" % json.dumps(cur))
        json.dump({"run": run, "state": "applying", "before": cur}, open(REC, "w"), indent=1)
        bdir = "E:/PussStage/Backups/PreS2CeilFlip-%s" % run
        os.makedirs(bdir)
        shutil.copy2(UMAP, bdir)
        for k, x in rows.items():
            x.modify()
            r = x.get_actor_rotation()
            x.set_actor_rotation(unreal.Rotator(roll=r.roll, pitch=r.pitch, yaw=r.yaw + 180.0), False)
        want = {k: (v[2] + 180.0 + 180.0) % 360.0 - 180.0 for k, v in cur.items()}
    elif mode == "REVERT":
        if a.get("confirm") != "REVERT S2CEIL" or not os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_NO_RECORD")
        before = json.load(open(REC))["before"]
        for k, x in rows.items():
            x.modify()
            b = before[k]
            x.set_actor_rotation(unreal.Rotator(roll=b[0], pitch=b[1], yaw=b[2]), False)
        want = {k: (v[2] + 180.0) % 360.0 - 180.0 for k, v in before.items()}
    else:
        raise RuntimeError("MODE")
    for k, x in rows.items():
        got = (x.get_actor_rotation().yaw + 180.0) % 360.0 - 180.0
        if abs(((got - want[k]) + 180) % 360 - 180) > 0.05:
            raise RuntimeError("READBACK|%s|%.2f vs %.2f|NOTHING SAVED; Don't-Save restart" % (k, got, want[k]))
        loc = x.get_actor_location()
        if max(abs(loc.x - cur[k][3]), abs(loc.y - cur[k][4]), abs(loc.z - cur[k][5])) > 0.01:
            raise RuntimeError("MOVED|%s|NOTHING SAVED; Don't-Save restart" % k)
    if census() != ([], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(MAP, only_if_is_dirty=False):
        raise RuntimeError("SAVE_FAILED")
    if census() != ([], []):
        raise RuntimeError("DIRTY_AFTER|%s" % (census(),))
    if mode == "APPLY":
        json.dump({"run": run, "state": "applied", "before": cur}, open(REC, "w"), indent=1)
    else:
        os.rename(REC, REC + ".reverted-%s" % run)
    unreal.log("S2CEIL_%s_OK|run=%s|n=%d|yaw=%s" % (mode, run, len(rows), sorted(set(round(v, 1) for v in want.values()))))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S2CEIL_FAILED|%r" % (exc,))
