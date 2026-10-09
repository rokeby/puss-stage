"""S2 HANGAR FLOOR -> DARK WET (Gary 9 Oct, conductor session: "S2's floor, can it be made same as the others (shiny one)?").
[meas FLOORPROBE 9 Oct 04:06] S2 Hangar Floor 1/2/3 + S2 Hangar Apron carry M_Walnut_Hrrngbn_02_Mat_Inst_Dup on slot 0; the
other floors carry /Game/InfinityStage/RigAtmos/MI_Floor_DarkWet since floor_dark_wet APPLY 5 Oct (floor_dark_wet_record.json).
Material-only: sets slot 0 of each target's StaticMeshComponent to MI_Floor_DarkWet.  No transform, no other actor.  P02 is NOT
touched (Gary 6 Oct "not walnut shiny" history; deferred to him).  Record (old material paths) + backup umap; REVERT exact.
Saves the level only.  Args s2_floor_darkwet_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S2FLOORDW"}.
Markers S2FLOORDW_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s2_floor_darkwet_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MAP_FILE = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MI = "/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet"
LABELS = ["S2 Hangar Floor 1", "S2 Hangar Floor 2", "S2 Hangar Floor 3", "S2 Hangar Apron"]


def main():
    import unreal
    a = json.load(open(HERE + "s2_floor_darkwet_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S2FLOORDW-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    acts = {}
    for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        l = str(x.get_actor_label())
        if l in LABELS:
            if l in acts: raise RuntimeError("DUP|" + l)
            acts[l] = x
    if sorted(acts) != sorted(LABELS): raise RuntimeError("MISSING|%s" % sorted(set(LABELS) - set(acts)))
    comps = {}
    for l, x in acts.items():
        cs = list(x.get_components_by_class(unreal.StaticMeshComponent))
        if len(cs) != 1: raise RuntimeError("COMPS|%s|%d" % (l, len(cs)))
        comps[l] = cs[0]
    mi = unreal.load_asset(MI)
    if mi is None: raise RuntimeError("NO_MI")
    cur = {l: (c.get_material(0).get_path_name() if c.get_material(0) else None) for l, c in comps.items()}
    if mode == "DRY":
        unreal.log("S2FLOORDW_DRY_OK|current=%s|target=%s" % (cur, MI)); return
    if a.get("confirm") != "%s S2FLOORDW" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS2FloorDW-%s" % run; os.makedirs(bd); shutil.copy2(MAP_FILE, bd)
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        json.dump({"run": run, "backup": bd, "old": cur}, open(REC, "w"), indent=1)
        want = {l: mi for l in LABELS}
    elif mode == "REVERT":
        old = json.load(open(REC))["old"]
        want = {l: (unreal.load_asset(old[l].split(".")[0]) if old[l] else None) for l in LABELS}
    else:
        raise RuntimeError("MODE")
    for l in LABELS:
        acts[l].modify(); comps[l].modify(); comps[l].set_material(0, want[l])
    got = {l: (comps[l].get_material(0).get_path_name() if comps[l].get_material(0) else None) for l in LABELS}
    bad = [l for l in LABELS if (want[l].get_path_name() if want[l] else None) != got[l]]
    if bad: raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % bad)
    if census() != ([], [MAP.split("/")[-1]]) and census() != ([], [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []): raise RuntimeError("SAVE")
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S2FLOORDW_%s_OK|run=%s|now=%s|backup=%s" % (mode, run, got, bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S2FLOORDW_FAILED|%r" % (exc,))
