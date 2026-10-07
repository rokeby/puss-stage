"""Read-only: which level owns each P02 follow-ons 'unclassified' actor. Marker P02UNCL_LEVELS|..."""
import collections
import json
import os

import unreal

here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
labels = set(json.load(open(os.path.join(here, "p02_straighten_followons_capture.json")))["unclassified"])
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
persistent = world.get_outermost().get_name()
by = collections.defaultdict(list)
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    lab = str(a.get_actor_label())
    if lab in labels:
        by[a.get_outermost().get_name()].append(lab)
unreal.log("P02UNCL_LEVELS|persistent=%s|%s" % (persistent, json.dumps({k: len(v) for k, v in by.items()})))
unreal.log("P02UNCL_PERSISTENT|%s" % json.dumps(sorted(by.get(persistent, []))))
