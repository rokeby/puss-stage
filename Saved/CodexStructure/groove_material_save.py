"""Save the groove re-fit left unsaved when groove_material_apply.py refused on
board-count drift. Gary, 29 Sep evening: "Save it". Before saving, re-check the
in-memory state is exactly what was reported:
- only the level dirty, no content;
- no ZZ_ actors;
- all six current, each with GrooveMaterial = MI_Kit_SteelGroove;
- grooves 3 per slot;
- board counts as the determinism probe read them.
Saves the level only. Lean: all work in main()."""
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GROOVE = "/Game/Scenes/Wings/PaintedSurface/Kit/MI_Kit_SteelGroove"
BOARDS = {"01": 7171, "02": 2614, "03": 0, "04": 2919, "05": 6380, "06": 7062}


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    c = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    assert not c and m == [EXPECTED_WORLD], f"dirty set is not just the level: {c} {m}"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    assert not any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors), "bench actors in the level"
    rows = {}
    for a in actors:
        if not isinstance(a, unreal.InfinityStageStructureActor):
            continue
        key = a.get_actor_label()[-2:]
        g = a.get_editor_property("ground")
        mat = g.get_editor_property("groove_material")
        rows[key] = (bool(a.is_structure_current()), int(a.get_editor_property("board_count")),
                     int(a.get_editor_property("slot_count")), int(a.get_editor_property("groove_piece_count")),
                     mat.get_path_name().split(".")[0] if mat else None)
    assert len(rows) == 6, f"structures: {sorted(rows)}"
    for key, (current, boards, slots, grooves, mat) in rows.items():
        assert current, f"S{key} not current"
        assert boards == BOARDS[key], f"S{key} boards {boards} != probe {BOARDS[key]}"
        assert grooves == 3 * slots, f"S{key} grooves {grooves} for {slots} slots"
        assert mat == GROOVE, f"S{key} groove material {mat}"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    c2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"GROOVE_MATERIAL_SAVED|{rows}|level_saved=1|dirty_after={c2}+{m2}")


main()
