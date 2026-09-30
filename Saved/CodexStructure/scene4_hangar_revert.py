"""Undo scene4_hangar_build.py: delete every actor tagged RigAtmos.Scene4Hangar, in
one pass, children before their hinge parents, and save the level only. Refuses on
PIE, dirty content, or a map dirtied by anything else. Lean: all work in main()."""
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = [a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]]
    assert mine, "no Scene 4 hangar actors found"

    def depth(a):
        d, p = 0, a.get_attach_parent_actor()
        while p is not None:
            d, p = d + 1, p.get_attach_parent_actor()
        return d

    n = 0
    for a in sorted(mine, key=depth, reverse=True):
        if sub.destroy_actor(a):
            n += 1
    left = [a.get_actor_label() for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]]
    assert not left, f"still present: {left[:5]}"
    c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    assert not c1 and m1 == [EXPECTED_WORLD], f"unexpected dirty set: {c1} {m1}"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    unreal.log(f"SCENE4_HANGAR_REVERTED|deleted={n}|level_saved=1")


main()
