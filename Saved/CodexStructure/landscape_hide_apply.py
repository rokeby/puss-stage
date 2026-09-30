"""Landscape block step 1 (30 Sep; Gary: "remove all landscapes and replace them with the floors"; the DELETE waits
for his eyes): HIDE both landscapes, "Passage 1 - ForestedLandscape" (P02) and "Passage 3 - Wet Ground" (P03):
hidden in game and collision off, so traces and the swept-volume sweep see the new floors, not the terrain.
Reversible property writes; the landscapes still load (so a hide does not show the load-time benefit).
Dry run (default). Apply (LS_HIDE_APPLY): record, Backups/PreLandscapeHide-*, set, read back, save the level.
Revert (LS_HIDE_REVERT): restore the recorded values. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "landscape_hide_record.json")
LABELS = ("Passage 1 - ForestedLandscape", "Passage 3 - Wet Ground")


def fail(msg):
    unreal.log_error("LS_HIDE_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("LS_HIDE_APPLY")), bool(globals().get("LS_HIDE_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    state = {l: {"hidden": bool(by[l].get_editor_property("hidden")), "collision": bool(by[l].get_actor_enable_collision())} for l in LABELS}
    unreal.log(f"LS_HIDE_PLAN|{json.dumps(state)}")
    if not (apply or revert):
        unreal.log("LS_HIDE_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() or any(l.startswith("ZZ_") for l in by):
        fail("Sequencer open or ZZ_ actors present")
    if revert:
        want = json.load(open(RECORD, encoding="utf-8"))["before"]
    else:
        if os.path.exists(RECORD):
            fail("already applied; revert first")
        stamp = datetime.datetime.now()
        json.dump({"written": stamp.isoformat(timespec="seconds"), "before": state}, open(RECORD, "w", encoding="utf-8"), indent=1)
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreLandscapeHide-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        want = {l: {"hidden": True, "collision": False} for l in LABELS}
    for l in LABELS:
        a = by[l]
        a.modify()
        a.set_editor_property("hidden", want[l]["hidden"])
        a.set_actor_enable_collision(want[l]["collision"])
    got = {l: {"hidden": bool(by[l].get_editor_property("hidden")), "collision": bool(by[l].get_actor_enable_collision())} for l in LABELS}
    if got != want:
        fail(f"read-back {got} != {want} (NOT saved)")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"LS_HIDE_OK|{'reverted' if revert else 'applied'}|{json.dumps(got)}|dirty_after={d}")


main()
