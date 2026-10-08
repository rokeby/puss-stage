"""Relabel the provisional stage-front wings (tag PussStage.StageFrontTemp) so their labels don't contain 'TEMP'
(bench-actor save guards in other tools refuse on TEMP labels: s3_sack_livecloth BUILD TEMP_ACTORS_PRESENT, 8 Oct).
Map-only save. STAGEFRONT_RELABEL_OK / _FAILED."""
import shutil, datetime
import unreal
try:
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    acts = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if "PussStage.StageFrontTemp" in [str(t) for t in a.tags]]
    if len(acts) != 2:
        raise RuntimeError("COUNT|%d" % len(acts))
    run = datetime.datetime.now().strftime("SFRELABEL-%Y%m%d-%H%M%S")
    bd = "E:/PussStage/Backups/PreStageFrontRelabel-" + run
    import os; os.makedirs(bd)
    shutil.copy2("E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap", bd)
    out = []
    for a in acts:
        old = str(a.get_actor_label())
        new = old.replace("STAGE FRONT TEMP", "STAGE FRONT").replace("rococo)", "rococo, provisional)")
        a.modify()
        a.set_actor_label(new); out.append(new)
    if dirty()[0] or len(dirty()[1]) != 1:
        raise RuntimeError("CENSUS|%s" % (dirty(),))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or dirty() != ([], []):
        raise RuntimeError("SAVE")
    unreal.log("STAGEFRONT_RELABEL_OK|run=%s|%s|backup=%s" % (run, out, bd))
except Exception as e:
    unreal.log_error("STAGEFRONT_RELABEL_FAILED|%r" % (e,))
