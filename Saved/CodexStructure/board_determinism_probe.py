"""Probe, 29 Sep evening, after groove_material_apply.py refused on board-count drift
(structures re-fitted in memory, NOT saved). Re-fits each structure once more
with the settings as they now stand, and checks that board and groove counts
repeat exactly, and that a hash of every board instance transform repeats.
Deterministic means the drift follows the current inputs (Show and stations),
not chance. Touches only the in-memory re-fit that is already dirty; saves
nothing. Lean: all work in main()."""
import hashlib

import unreal


def board_hash(actor):
    h = hashlib.sha1()
    n = 0
    for c in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        if not c.get_name().startswith("StructureGround"):
            continue
        for i in range(c.get_instance_count()):
            t = c.get_instance_transform(i, True)
            h.update(("%.1f,%.1f,%.1f,%.1f;" % (t.translation.x, t.translation.y, t.translation.z, t.scale3d.x)).encode())
            n += 1
    return h.hexdigest()[:12], n


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in sorted((x for x in sub.get_all_level_actors() if isinstance(x, unreal.InfinityStageStructureActor)),
                    key=lambda x: x.get_actor_label()):
        first = (int(a.get_editor_property("board_count")), int(a.get_editor_property("groove_piece_count"))) + board_hash(a)
        assert a.materialize_structure(), f"{a.get_actor_label()} did not re-fit"
        second = (int(a.get_editor_property("board_count")), int(a.get_editor_property("groove_piece_count"))) + board_hash(a)
        rows.append(f"{a.get_actor_label()[-2:]}:{first}->{second}:{'SAME' if first == second else 'DIFFERENT'}")
    dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
             len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"BOARD_DETERMINISM|{' '.join(rows)}|dirty={dirty[0]}+{dirty[1]}|saved=0")


main()
