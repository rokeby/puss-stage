import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
labs = [str(a.get_actor_label()) for a in acts]
unreal.log("WORLD_PROBE|world=%s|actors=%d|p02floor=%d|structures=%d|pie=%s" % (w.get_path_name() if w else None, len(acts),
           sum(1 for l in labs if l.startswith("Passage 02 - Floor")), sum(1 for a in acts if isinstance(a, unreal.InfinityStageStructureActor)),
           unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None))
