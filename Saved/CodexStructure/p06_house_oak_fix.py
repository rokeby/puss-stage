"""Fix (30 Sep): mouth_floor_apply.py copied the house plane's material from the mouth's own floor. P06's floor is Versailles,
so "Passage 06 - House Floor (oak)" came out Versailles. Gary asked for OAK on the house floor: set it to the same oak material
as P03's and P05's house planes, read it back, save the level only. Guards: world, no PIE, both packages clean, no Sequencer.
Records the previous material for a revert (P06_OAK_REVERT). Marker P06_OAK_OK."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "p06_house_oak_record.json")
OAK = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Oak_Hrrngbn_01_Mat_Inst_Dup"
LABEL = "Passage 06 - House Floor (oak)"


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    dirty = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()] + \
        [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None or dirty \
            or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        raise RuntimeError(f"guard: world/PIE/dirty {dirty}/Sequencer")
    hits = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label() == LABEL]
    if len(hits) != 1:
        raise RuntimeError(f"{LABEL}: {len(hits)} actors")
    c = hits[0].static_mesh_component
    revert = bool(globals().get("P06_OAK_REVERT"))
    before = c.get_material(0).get_path_name().split(".")[0] if c.get_material(0) else None
    target = json.load(open(RECORD, encoding="utf-8"))["before"] if revert else OAK
    if not revert:
        json.dump({"before": before}, open(RECORD, "w", encoding="utf-8"), indent=1)
    c.set_material(0, unreal.load_asset(target))
    got = c.get_material(0).get_path_name().split(".")[0] if c.get_material(0) else None
    if got != target:
        raise RuntimeError(f"read-back {got} (NOT saved)")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("level save failed")
    after = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()] + \
        [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    unreal.log(f"P06_OAK_OK|{'reverted' if revert else 'applied'}|before={before}|now={got}|dirty_after={after}")


main()
