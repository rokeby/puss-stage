"""Re-fit stale Infinity Stage structures (6 Oct night: Structures 01/02/04/06 went not-current after the W&T wing
placements). Guards: no PIE, clean census. Backup the umap, record per-layer component/instance counts per structure,
MaterializeStructure, require IsStructureCurrent, report count diffs (refuse if any layer lost ALL its instances),
census = level only, save the level. Args structure_refit_args.json {"mode": "DRY"|"APPLY", "confirm": "APPLY REFIT"}.
Marker STRUCTURE_REFIT_<MODE>_OK|run=.."""
import datetime, json, os, shutil
import unreal
HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
RUN = datetime.datetime.now().strftime("REFIT-%Y%m%d-%H%M%S")


def stop(m):
    unreal.log_error("STRUCTURE_REFIT_FAILED|run=%s|%s" % (RUN, m))
    raise RuntimeError(m)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def layers(actor):
    out = {}
    for c in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        k = str(c.get_name()).rstrip("0123456789_")
        out[k] = out.get(k, 0) + int(c.get_instance_count())
    out["_static_mesh_components"] = len(actor.get_components_by_class(unreal.StaticMeshComponent))
    out["_lights"] = len(actor.get_components_by_class(unreal.LightComponent))
    return out


def main():
    a = json.load(open(HERE + "structure_refit_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode != "DRY" and a.get("confirm") != "APPLY REFIT":
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    acts = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if isinstance(x, unreal.InfinityStageStructureActor)]
    stale = [x for x in acts if not x.is_structure_current()]
    before = {str(x.get_actor_label()): layers(x) for x in stale}
    unreal.log("STRUCTURE_REFIT_PLAN|run=%s|stale=%s" % (RUN, json.dumps(sorted(before))))
    if mode == "DRY":
        unreal.log("STRUCTURE_REFIT_DRY_OK|run=%s|stale=%d" % (RUN, len(stale)))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    backup = "E:/PussStage/Backups/PreStructureRefit-" + RUN
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    with open(HERE + "structure_refit_record_%s.json" % RUN, "w", encoding="utf-8") as h:
        json.dump({"run": RUN, "before": before, "backup": backup}, h, indent=1)
    after, diffs = {}, {}
    for x in stale:
        lab = str(x.get_actor_label())
        if not x.materialize_structure():
            stop("MATERIALIZE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % lab)
        if not x.is_structure_current():
            stop("NOT_CURRENT_AFTER|%s|NOTHING SAVED; Don't-Save restart" % lab)
        after[lab] = layers(x)
        d = {k: [before[lab].get(k), after[lab].get(k)] for k in set(before[lab]) | set(after[lab])
             if before[lab].get(k) != after[lab].get(k)}
        diffs[lab] = d
        lost = [k for k, (b, n) in d.items() if (b or 0) > 0 and not n]
        if lost:
            stop("LAYER_LOST|%s|%s|NOTHING SAVED; Don't-Save restart" % (lab, json.dumps({k: d[k] for k in lost})))
    unreal.log("STRUCTURE_REFIT_DIFFS|run=%s|%s" % (RUN, json.dumps(diffs)))
    c = census()
    if c["content"] or c["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(c))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    unreal.log("STRUCTURE_REFIT_APPLY_OK|run=%s|refit=%s|level_saved=1" % (RUN, json.dumps(sorted(after))))


main()
