"""Put the Scene 4 hangar's hinges back at their RECORDED rest pose (plain numbers
from scene4_fold_revert_record.json), after the floor-rise preview's restore
failed. Its "originals" were UE struct wrappers that tracked the live value, so it
restored each hinge to its last preview pose, and Floor 3 was left flat. Mutates
only hinge rotations, and only to the record's values; saves nothing (the
verified save follows). Lean: all work in main()."""
import json
import os

import unreal

TAG = "RigAtmos.Scene4Hangar"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "scene4_fold_revert_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    rest = json.load(open(RECORD, encoding="utf-8"))["rest_pose"]["packed"]
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = {a.get_actor_label(): a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]}
    fixed = {}
    for label, (axis, packed) in rest.items():
        r = mine[label].root_component.get_editor_property("relative_rotation")
        got = float(r.roll if axis == "X" else r.pitch)
        if abs(got - packed) > 0.05:
            mine[label].set_actor_relative_rotation(unreal.Rotator(roll=float(packed) if axis == "X" else 0.0,
                                                                   pitch=float(packed) if axis == "Y" else 0.0, yaw=0.0), False, True)
            r2 = mine[label].root_component.get_editor_property("relative_rotation")
            fixed[label] = [round(got, 2), round(float(r2.roll if axis == "X" else r2.pitch), 2)]
    unreal.log(f"S4_REST_POSE_FIX|fixed={fixed}")


main()
