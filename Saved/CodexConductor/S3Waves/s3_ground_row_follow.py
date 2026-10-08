"""S3 GROUND ROW FOLLOW (Gary 8 Oct ~19:10: "yes move the lights"). The 6 'S3 WaveV3 Ground Row <i>' rect lights were
placed 20 cm behind their layer's P1 piece (s3_waves_v3_core.py:548, LAYER_X :523) = 5 cm behind P2.  W&T's t5o APPLY
(S3T5O-20261008-190357) shifted the pieces +6..+34 cm in x (spacing_plan_t5o.json), leaving the lights inside them.
Move: each light's RELATIVE x -> its layer's NEW P2 x + 5 cm (the original 5 cm clearance behind P2). y/z/rotation and
every other property untouched (aim moves < 0.5 deg [inf: 30 cm over >= 750 cm]).  Map-only save; record
s3_ground_row_follow_record.json + Backups/PreS3GroundRow-<run>.  Args s3_ground_row_follow_args.json
{"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3GROUNDROW", "run"}.  S3GROUNDROW_<MODE>_OK / _FAILED."""
import json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/S3Waves/"
REC = HERE + "s3_ground_row_follow_record.json"
PLAN = "E:/PussStage/Saved/CodexFlatV3/s3waves/spacing_plan_t5o.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LAYERS = ["L1_Breakers", "L2_SwellNear", "L3_SwellMid", "L4_SwellFar", "L5_Rollers", "L6_Foam"]   # sorted LAYER_X


def main():
    import unreal
    a = json.load(open(HERE + "s3_ground_row_follow_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    pieces = {(p["layer"], p["piece"]): p for p in json.load(open(PLAN))["layout"]["pieces"]}
    acts = {str(x.get_actor_label()): x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    plan = {}
    for i, lid in enumerate(LAYERS):
        lab = "S3 WaveV3 Ground Row %d" % (i + 1)
        x = acts.get(lab)
        if x is None: raise RuntimeError("MISSING|" + lab)
        rl = x.root_component.get_editor_property("relative_location")
        p1, p2 = pieces[(lid, "P1")], pieces[(lid, "P2")]
        plan[lab] = {"layer": lid, "old_rel": [rl.x, rl.y, rl.z], "expected_old_x": p1["old_x"] + 20.0,
                     "new_x": p2["new_x"] + 5.0, "p2_new_x": p2["new_x"]}
    if mode == "DRY":
        unreal.log("S3GROUNDROW_DRY_OK|run=%s|plan=%s" % (run, json.dumps(plan)))
        return
    if a.get("confirm") != "%s S3GROUNDROW" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3GroundRow-%s" % run
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        bad = {k: v for k, v in plan.items() if abs(v["old_rel"][0] - v["expected_old_x"]) > 0.5}
        if bad: raise RuntimeError("OLD_X_UNEXPECTED|%s" % bad)
        os.makedirs(bd); shutil.copy2(UMAP, bd)
        json.dump({"run": run, "backup": bd, "plan": plan}, open(REC, "w"), indent=1)
        want = {k: v["new_x"] for k, v in plan.items()}
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        old = json.load(open(REC))["plan"]
        os.makedirs(bd); shutil.copy2(UMAP, bd)
        want = {k: v["old_rel"][0] for k, v in old.items()}
    else:
        raise RuntimeError("MODE")
    for lab, nx in want.items():
        x = acts[lab]; rc = x.root_component
        x.modify(); rc.modify()
        rl = rc.get_editor_property("relative_location")
        rc.set_editor_property("relative_location", unreal.Vector(nx, rl.y, rl.z))
    got = {lab: acts[lab].root_component.get_editor_property("relative_location").x for lab in want}
    if any(abs(got[k] - want[k]) > 0.01 for k in want): raise RuntimeError("READBACK_BEFORE_SAVE|%s|NOTHING SAVED; Don't-Save restart" % got)
    if census() != ([], [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3GROUNDROW_%s_OK|run=%s|x=%s|backup=%s" % (mode, run, json.dumps({k: round(v, 1) for k, v in got.items()}), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3GROUNDROW_FAILED|%r" % (exc,))
