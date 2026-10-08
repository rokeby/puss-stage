"""S3 ocean lights a hint brighter and covering more (Gary 8 Oct ~07:00: "the lighting over the ocean - soft,
intermittent lighting that suggests storms but quite gently, is very nice and could be a hint brighter cover more
areas").  The 6 'S3 WaveV3 Ground Row' rect lights: source width/height and attenuation radius x1.5, barn door angle
-> 88 (widest).  (Their keyed intensity x1.2 is done separately with s3_light_envelope.py.)  Record + umap backup;
saves the map.  S3OCEAN_OK / S3OCEAN_FAILED."""
import json, os, shutil, time
HERE = "E:/PussStage/Saved/CodexConductor/"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
def main():
    import unreal
    run = "S3OCEAN-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    rows = [x for x in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.Actor)
            if str(x.get_actor_label()).startswith("S3 WaveV3 Ground Row")]
    if len(rows) != 6:
        raise RuntimeError("ROWS|%d" % len(rows))
    keys = ("source_width", "source_height", "attenuation_radius", "barn_door_angle")
    before = {str(x.get_actor_label()): {k: x.get_component_by_class(unreal.RectLightComponent).get_editor_property(k) for k in keys} for x in rows}
    json.dump({"run": run, "before": before}, open(HERE + "s3_ocean_wider_record_%s.json" % run, "w"), indent=1)
    bd = "E:/PussStage/Backups/PreS3Ocean-%s" % run
    os.makedirs(bd)
    shutil.copy2(UMAP, bd)
    for x in rows:
        c = x.get_component_by_class(unreal.RectLightComponent)
        c.modify()
        b = before[str(x.get_actor_label())]
        c.set_editor_property("source_width", b["source_width"] * 1.5)
        c.set_editor_property("source_height", b["source_height"] * 1.5)
        c.set_editor_property("attenuation_radius", b["attenuation_radius"] * 1.5)
        c.set_editor_property("barn_door_angle", 88.0)
    if dirty()[0] or len(dirty()[1]) != 1:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not lib.save_dirty_packages(True, False) or dirty() != ([], []):
        raise RuntimeError("SAVE")
    unreal.log("S3OCEAN_OK|run=%s|before=%s" % (run, json.dumps(list(before.values())[0])))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3OCEAN_FAILED|%r" % (exc,))
