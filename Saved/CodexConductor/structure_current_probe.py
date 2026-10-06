import json, unreal
out = {}
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor):
        try:
            out[str(a.get_actor_label())] = bool(a.is_structure_current())
        except Exception as e:
            out[str(a.get_actor_label())] = "ERR %s" % e
unreal.log("STRUCTURE_CURRENT_PROBE|%s" % json.dumps(out))
