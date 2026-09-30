"""Landscape block step 2 (30 Sep): turn on Structure 03's ground so P03 gets floor boards like every other passage
(the Wet Ground landscape WAS its floor). Ground.enabled False -> True, board_material None -> Structure 02's own
(MI_Kit_WalnutPlank, read from it, not typed); every other ground field is already the shared default. Then
materialize and read back (enabled, a non-zero board count, current).
Dry run (default). Apply (S03_GROUND_APPLY): record, Backups/PreS03Ground-*, set, materialize, read back, save the
level. Revert (S03_GROUND_REVERT): restore the recorded enabled/material and materialize. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "structure03_ground_record.json")


def fail(msg):
    unreal.log_error("S03_GROUND_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("S03_GROUND_APPLY")), bool(globals().get("S03_GROUND_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    s3, s2 = by["Infinity Stage - Structure 03"], by["Infinity Stage - Structure 02"]
    g = s3.get_editor_property("ground")
    mat2 = s2.get_editor_property("ground").get_editor_property("board_material")
    before = {"enabled": bool(g.get_editor_property("enabled")),
              "board_material": g.get_editor_property("board_material").get_path_name() if g.get_editor_property("board_material") else None,
              "board_count": int(s3.get_editor_property("board_count"))}
    unreal.log(f"S03_GROUND_PLAN|before={json.dumps(before)}|material_from_S02={mat2.get_path_name() if mat2 else None}")
    if not (apply or revert):
        unreal.log("S03_GROUND_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() or any(l.startswith("ZZ_") for l in by):
        fail("Sequencer open or ZZ_ actors present")
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))["before"]
        enabled, material = rec["enabled"], unreal.load_asset(rec["board_material"]) if rec["board_material"] else None
    else:
        if os.path.exists(RECORD):
            fail("already applied; revert first")
        if not mat2:
            fail("Structure 02 has no board material to reuse")
        stamp = datetime.datetime.now()
        json.dump({"written": stamp.isoformat(timespec="seconds"), "before": before}, open(RECORD, "w", encoding="utf-8"), indent=1)
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreS03Ground-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        enabled, material = True, mat2
    g.set_editor_property("enabled", enabled)
    g.set_editor_property("board_material", material)
    s3.set_editor_property("ground", g)
    if not s3.materialize_structure():
        fail("materialize failed (NOT saved)")
    g2 = s3.get_editor_property("ground")
    count = int(s3.get_editor_property("board_count"))
    ok = bool(g2.get_editor_property("enabled")) == enabled and s3.is_structure_current() and ((count > 0) == enabled)
    if not ok:
        fail(f"read-back: enabled {g2.get_editor_property('enabled')}, boards {count}, current {s3.is_structure_current()} (NOT saved)")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"S03_GROUND_OK|{'reverted' if revert else 'applied'}|enabled={enabled}|boards {before['board_count']}->{count}|dirty_after={d}")


main()
