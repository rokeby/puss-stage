"""Read-only: after hangar_revert S2 deleted 113/114, which recorded label is left or missing, and what S2-tagged or
"S2 "-labelled actors remain (the liners are expected). Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    rec = json.load(open(os.path.join(HERE, "hangar_s2_record.json.reverted"), encoding="utf-8"))
    labels = rec["labels"] if isinstance(rec["labels"], list) else eval(rec["labels"])
    alive = {a.get_actor_label(): a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)}
    left = [l for l in labels if l in alive]
    tagged = [a.get_actor_label() for a in alive.values() if unreal.Name("RigAtmos.Scene2Hangar") in a.tags]
    s2 = sorted(l for l in alive if l.startswith("S2 "))
    unreal.log(f"S2_LEFTOVER|recorded={len(labels)}|still_alive_from_record={left}|tagged_Scene2Hangar={tagged}|S2_labels={s2}")


main()
