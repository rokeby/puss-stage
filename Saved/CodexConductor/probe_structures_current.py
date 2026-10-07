"""Read-only: IsStructureCurrent for every Structure actor. Marker STRUCTCURRENT|"""
import json

import unreal

rows = {}
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_class().get_name() == "InfinityStageStructureActor":
        rows[str(a.get_actor_label())] = bool(a.is_structure_current())
unreal.log("STRUCTCURRENT|%s" % json.dumps(rows))
