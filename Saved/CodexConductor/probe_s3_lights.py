"""READ-ONLY: census of every light in Scene 3's hangar (editor world) + which ones the S3 rise / Scene 3 sequence key.
Writes probe_s3_lights.json; marker PROBE_S3_LIGHTS_OK|run=..|n=.. / PROBE_S3_LIGHTS_FAILED. No modify, no save."""
import json

OUT = "E:/PussStage/Saved/CodexConductor/probe_s3_lights.json"
SEQS = ["/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"]


def main():
    import unreal
    import time; run = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    w = ed.get_editor_world()
    lib = unreal.EditorLoadingAndSavingUtils
    c0 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    rows = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        folder = str(a.get_folder_path())
        label = str(a.get_actor_label())
        if not ("Scene 03" in folder or label.startswith("S3 ") or "S3_" in label or "S3 " in label):
            continue
        for lc in a.get_components_by_class(unreal.LightComponent):
            att = None
            try:
                att = lc.get_editor_property("attenuation_radius")
            except Exception:
                pass
            units = None
            try:
                units = str(lc.get_editor_property("intensity_units"))
            except Exception:
                pass
            rows.append({"label": label, "folder": folder, "actor_class": a.get_class().get_name(),
                         "comp": lc.get_name(), "comp_class": lc.get_class().get_name(),
                         "intensity": lc.intensity, "units": units, "visible": lc.is_visible(),
                         "hidden_in_game": a.is_hidden_ed() if hasattr(a, "is_hidden_ed") else None,
                         "temp_k": lc.get_editor_property("temperature") if lc.get_editor_property("use_temperature") else None,
                         "atten": att, "cast_shadows": lc.cast_shadows,
                         "loc": [round(v, 1) for v in (a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z)]})
    keyed = {}
    for sp in SEQS:
        seq = unreal.load_asset(sp)
        if seq is None:
            keyed[sp] = "LOAD_NONE"
            continue
        names = {}
        for b in seq.get_bindings():
            for t in b.get_tracks():
                tn = str(t.get_display_name())
                if "ntensity" in tn or t.get_class().get_name() == "MovieSceneVisibilityTrack":
                    names.setdefault(str(b.get_display_name()), []).append(tn)
        keyed[sp] = names
    c1 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    json.dump({"run": run, "rows": rows, "keyed": keyed, "census_before": c0, "census_after": c1}, open(OUT, "w"), indent=1)
    unreal.log("PROBE_S3_LIGHTS_OK|run=%s|n=%d|census_unchanged=%s" % (run, len(rows), c0 == c1))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_S3_LIGHTS_FAILED|%r" % (exc,))
