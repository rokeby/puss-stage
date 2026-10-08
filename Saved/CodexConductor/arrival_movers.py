"""Fill each Scene Arrival's AdditionalInitialTransformDrives (roof hinge + lattice fly) so PIE/game worlds pose them at
the rise's FIRST keys at BeginPlay, like the root.  Measured 8 Oct 07:45 (pie_s1_rig_tap): at the P01->S1 cut the S1
roof hinge flipped (-36.1 -> -57.8 world pitch, yaw 180) and the lattice jumped +1.57 m, because during P01 they sat in
the saved LANDED level pose; every Arrival logged INFINITY_HANGAR_INITIAL_POSE ... movers=1 (root only).  The header
(InfinityStageArrival.h:157-162) says to author the sequence's actual transform movers here (S6 has no roof).
For S1..S6: rise = the Arrival's MotionSequence; drives = every binding there whose name contains 'Roof Hinge' or
'Lattice Fly' AND has a 3D transform track, target = the editor actor with that exact label.
Record + umap backup; saves the map only.  Args arrival_movers_args.json {"mode":"DRY"|"APPLY"|"REVERT","run":..}.
ARRIVALMOVERS_<MODE>_OK / ARRIVALMOVERS_FAILED."""
import json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "arrival_movers_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
def main():
    import unreal
    a = json.load(open(HERE + "arrival_movers_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    acts = {str(x.get_actor_label()): x for x in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.Actor)}
    plan, before = {}, {}
    for n in range(1, 7):
        arr = acts.get("S%d Arrival" % n)
        if arr is None:
            raise RuntimeError("NO_ARRIVAL|S%d" % n)
        cur = list(arr.get_editor_property("additional_initial_transform_drives"))
        before["S%d" % n] = [[d.get_editor_property("target").get_actor_label() if d.get_editor_property("target") else None,
                             d.get_editor_property("binding_guid").to_string() if hasattr(d.get_editor_property("binding_guid"), "to_string") else str(d.get_editor_property("binding_guid"))] for d in cur]
        seq = arr.get_editor_property("motion_sequence")
        seq = seq.load_synchronous() if hasattr(seq, "load_synchronous") else (unreal.load_asset(seq.get_path_name()) if seq else None)
        if seq is None:
            raise RuntimeError("NO_MOTION|S%d" % n)
        rows = []
        for b in seq.get_bindings():
            nm = str(b.get_display_name())
            if not ("Roof Hinge" in nm or "Lattice Fly" in nm):
                continue
            if not any(t.get_class().get_name() == "MovieScene3DTransformTrack" for t in b.get_tracks()):
                continue
            tgt = acts.get(nm)
            if tgt is None:
                raise RuntimeError("NO_TARGET|S%d|%s" % (n, nm))
            rows.append((nm, tgt, b.get_id()))
        plan["S%d" % n] = (arr, rows)
    summary = {k: [r[0] for r in v[1]] for k, v in plan.items()}
    if mode == "DRY":
        unreal.log("ARRIVALMOVERS_DRY_OK|run=%s|plan=%s|before=%s" % (run, json.dumps(summary), json.dumps(before)))
        return
    if mode != "APPLY":
        raise RuntimeError("MODE (revert = Backups/PreArrivalMovers-<run> umap)")
    if os.path.exists(REC):
        raise RuntimeError("RECORD_EXISTS")
    json.dump({"run": run, "before": before, "plan": summary}, open(REC, "w"), indent=1)
    bd = "E:/PussStage/Backups/PreArrivalMovers-%s" % run
    os.makedirs(bd)
    shutil.copy2(UMAP, bd)
    for k, (arr, rows) in plan.items():
        arr.modify()
        drives = []
        for nm, tgt, guid in rows:
            d = unreal.InfinityArrivalInitialTransformDrive()
            d.set_editor_property("target", tgt)
            d.set_editor_property("binding_guid", guid)
            drives.append(d)
        arr.set_editor_property("additional_initial_transform_drives", drives)
        got = list(arr.get_editor_property("additional_initial_transform_drives"))
        if len(got) != len(rows) or any(g.get_editor_property("target") != r[1] for g, r in zip(got, rows)):
            raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % k)
    if dirty() != ([], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not lib.save_dirty_packages(True, False) or dirty() != ([], []):
        raise RuntimeError("SAVE")
    unreal.log("ARRIVALMOVERS_APPLY_OK|run=%s|%s" % (run, json.dumps(summary)))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("ARRIVALMOVERS_FAILED|%r" % (exc,))
