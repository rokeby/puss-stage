"""S3 CROWD FEET (Gary 8 Oct ~21:20: "these guys are still halfway in the ground").  [meas] PIE t=30 foot bones
(pie_crowd_pelvis.json): the copies' lowest foot is 20-60 cm under the dune surface (grid validated on F52/M59): the
regather assumed feet = hero-calibrated root, but in the animated pose the feet sit 25-40 cm below the root.
Per copy (s3_crowd_feet_plan.json, computed offline): level z += dz so the lowest foot is 2 cm into the sand at its
fire spot, and for the 9 ocean copies the S3LATE ABSOLUTE section Location.Z default := ocean surface - 2 - foot offset.
Heroes untouched.  Saves map + LS_Clams; record + backup; REVERT exact.  Args s3_crowd_feet_args.json
{"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3FEET"}.  S3FEET_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd_feet_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CLAMS = "/Game/Scenes/LS_Clams"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap", "E:/PussStage/Content/Scenes/LS_Clams.uasset"]
def main():
    import unreal
    a = json.load(open(HERE + "s3_crowd_feet_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S3FEET-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    plan = json.load(open(HERE + "s3_crowd_feet_plan.json"))
    acts = {str(x.get_actor_label()): x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    late = json.load(open(HERE + "s3_crowd_late_record.json"))
    sec_by = {o["label"]: o["added"]["transform"] for o in late["ocean"] if o["added"].get("transform")}
    crec = json.load(open(HERE + "s3_crowd_structure_record.json"))
    gid = {c["label"]: c["actor_binding_guid"] for c in crec["copies"]}
    clams = unreal.load_asset(CLAMS)
    by_guid = {b.get_id().export_text(): b for b in clams.get_bindings()}
    def zchan(lab):
        b = by_guid[gid[lab]]
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieScene3DTransformTrack):
                for s in t.get_sections():
                    if str(s.get_name()) == sec_by[lab]:
                        return [c for c in s.get_all_channels() if str(c.get_name()).startswith("Location.Z")][0]
        raise RuntimeError("NO_OCEAN_SECTION|" + lab)
    for lab in plan["level"]:
        if lab not in acts: raise RuntimeError("MISSING|" + lab)
    if mode == "DRY":
        unreal.log("S3FEET_DRY_OK|level=%d|ocean=%d|now=%s" % (len(plan["level"]), len(plan["ocean"]),
                   {l[:11]: round(acts[l].get_actor_location().z, 1) for l in plan["level"]})); return
    if a.get("confirm") != "%s S3FEET" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3Feet-%s" % run; os.makedirs(bd)
    for f in FILES: shutil.copy2(f, bd)
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        rec = {"run": run, "backup": bd, "level_before": {l: acts[l].get_actor_location().z for l in plan["level"]},
               "ocean_before": {l: float(zchan(l).get_default()) for l in plan["ocean"]}}
        json.dump(rec, open(REC, "w"), indent=1)
        lv = {l: rec["level_before"][l] + plan["level"][l]["dz"] for l in plan["level"]}
        oc = {l: plan["ocean"][l]["new_z"] for l in plan["ocean"]}
    elif mode == "REVERT":
        rec = json.load(open(REC)); lv, oc = rec["level_before"], rec["ocean_before"]
    else:
        raise RuntimeError("MODE")
    for l, z in lv.items():
        x = acts[l]; x.modify(); p = x.get_actor_location()
        x.set_actor_location(unreal.Vector(p.x, p.y, float(z)), False, True)
    for l, z in oc.items(): zchan(l).set_default(float(z))
    if census() != ([CLAMS], [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(CLAMS, only_if_is_dirty=False): raise RuntimeError("SAVE_CLAMS")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []): raise RuntimeError("SAVE")
    bad = [l for l, z in lv.items() if abs(acts[l].get_actor_location().z - float(z)) > 0.5]
    if bad: raise RuntimeError("READBACK|%s" % bad)
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3FEET_%s_OK|run=%s|level=%d|ocean=%d|backup=%s" % (mode, run, len(lv), len(oc), bd))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3FEET_FAILED|%r" % (exc,))
