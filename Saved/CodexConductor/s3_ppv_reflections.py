"""S3 reflections detail (Gary 8 Oct ~06:15: "increase the LOD or distances in this scene for reflections and asset detail
because some reflections are coming in too late").  Scene-scoped: only the S3 box PPV 'S3 Hangar Pinned Exposure'
(bound; all Lumen settings at defaults with no overrides [measured probe_s3_ppv]) gets overrides:
  Ray Lighting Mode = Hit Lighting for Reflections (traced reflections instead of screen-space/surface-cache
  fallback, which is what pops in late [inferred]); Lumen Reflection Quality 1 -> 4; Lumen Scene Detail 1 -> 4 (smaller
  objects get Lumen cards); Lumen Scene View Distance 20000 -> 40000; Max Trace Distance 20000 -> 40000;
  Max Roughness To Trace Reflections 0.4 -> 0.6 (so the semi-gloss grease and wet sand trace too).
PIE cost goes up [inferred]; this is for the cinematic look (memory gary-cinematic-video-priority).
Args s3_ppv_reflections_args.json {"mode":"DRY"|"APPLY"|"REVERT","run":..}.  Record + umap backup; saves the map.
S3PPVR_<MODE>_OK / S3PPVR_FAILED."""
import json
import os
import shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_ppv_reflections_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LABEL = "S3 Hangar Pinned Exposure"
FIELDS = ["lumen_ray_lighting_mode", "lumen_reflection_quality", "lumen_scene_detail", "lumen_scene_view_distance",
          "lumen_max_trace_distance", "lumen_max_roughness_to_trace_reflections"]


def main():
    import unreal
    a = json.load(open(HERE + "s3_ppv_reflections_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    w = ed.get_editor_world()
    vs = [x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.PostProcessVolume) if str(x.get_actor_label()) == LABEL]
    if len(vs) != 1:
        raise RuntimeError("PPV_COUNT|%d" % len(vs))
    v = vs[0]
    s = v.get_editor_property("settings")
    target = {"lumen_ray_lighting_mode": unreal.LumenRayLightingModeOverride.HIT_LIGHTING_FOR_REFLECTIONS,
              "lumen_reflection_quality": 4.0, "lumen_scene_detail": 4.0, "lumen_scene_view_distance": 40000.0,
              "lumen_max_trace_distance": 40000.0, "lumen_max_roughness_to_trace_reflections": 0.6}
    before = {k: [str(s.get_editor_property(k)), bool(s.get_editor_property("override_" + k))] for k in FIELDS}
    if mode == "DRY":
        unreal.log("S3PPVR_DRY_OK|run=%s|before=%s" % (run, json.dumps(before)))
        return
    v.modify()
    if mode == "APPLY":
        if os.path.exists(REC):
            raise RuntimeError("RECORD_EXISTS")
        json.dump({"run": run, "before": before}, open(REC, "w"), indent=1)
        bd = "E:/PussStage/Backups/PreS3PPVReflections-%s" % run
        os.makedirs(bd)
        shutil.copy2(UMAP, bd)
        for k, val in target.items():
            s.set_editor_property(k, val)
            s.set_editor_property("override_" + k, True)
    elif mode == "REVERT":
        for k in FIELDS:
            s.set_editor_property("override_" + k, False)
    v.set_editor_property("settings", s)
    s2 = v.get_editor_property("settings")
    if mode == "APPLY" and not all(s2.get_editor_property("override_" + k) for k in FIELDS):
        raise RuntimeError("READBACK|NOTHING SAVED; Don't-Save restart")
    if dirty() != ([], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not lib.save_dirty_packages(True, False) or dirty() != ([], []):
        raise RuntimeError("SAVE")
    if mode == "REVERT":
        os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3PPVR_%s_OK|run=%s|now=%s" % (mode, run, json.dumps({k: str(s2.get_editor_property(k)) for k in FIELDS})))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3PPVR_FAILED|%r" % (exc,))
