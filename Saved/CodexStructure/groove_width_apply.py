"""Grooves to 16 cm (Gary, 29 Sep night: "Widen to 16 cm"): Ground.SlotWidthCm 8 -> 16 on all six
structures, each re-fitted. Patch S is built, so the lanes' random draws are pinned: only the
boards meeting a slot change. Guards: world, no PIE, 0+0 dirty, no Sequencer, no ZZ_. Plain
record first (every structure's slot width and counts), level backup, read-back (width,
current, three plates per slot), level saved, dirty 0+0. Revert: GROOVE_WIDTH_REVERT=True
puts the recorded widths back and re-fits. Lean: all work in main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "groove_width_record.json")
WIDTH = 16.0


def fail(msg):
    unreal.log_error("GROOVE_WIDTH_STOPPED|" + msg)
    raise RuntimeError(msg)


def state(a):
    g = a.get_editor_property("ground")
    return {"slot_width_cm": float(g.get_editor_property("slot_width_cm")), "boards": int(a.get_editor_property("board_count")),
            "slots": int(a.get_editor_property("slot_count")), "plates": int(a.get_editor_property("groove_piece_count"))}


def main():
    revert = bool(globals().get("GROOVE_WIDTH_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith("ZZ_") for a in actors):
        fail("bench actors (ZZ_) in the level")
    structures = sorted((a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)), key=lambda a: a.get_actor_label())
    before = {a.get_actor_label(): state(a) for a in structures}
    if revert:
        targets = {k: v["slot_width_cm"] for k, v in json.load(open(RECORD, encoding="utf-8"))["before"].items()}
    else:
        if all(abs(v["slot_width_cm"] - WIDTH) < 1e-6 for v in before.values()):
            fail("already 16 cm everywhere")
        targets = {k: WIDTH for k in before}
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": datetime.datetime.now().isoformat(timespec="seconds"), "before": before}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreGrooveWidth-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
    for a in structures:
        a.modify()
        g = a.get_editor_property("ground")
        g.set_editor_property("slot_width_cm", float(targets[a.get_actor_label()]))
        a.set_editor_property("ground", g)
        if not a.materialize_structure():
            fail(f"{a.get_actor_label()} did not re-fit")
    after = {a.get_actor_label(): state(a) for a in structures}
    problems = []
    for a in structures:
        label = a.get_actor_label()
        s = after[label]
        if abs(s["slot_width_cm"] - targets[label]) > 1e-6 or not a.is_structure_current():
            problems.append(f"{label} width {s['slot_width_cm']} current {a.is_structure_current()}")
        if s["slots"] != before[label]["slots"] or (s["slots"] and s["plates"] != 3 * s["slots"]):
            problems.append(f"{label} slots {before[label]['slots']}->{s['slots']} plates {s['plates']}")
    if problems:
        fail(f"read-back: {problems} (NOT saved)")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
        fail("content dirtied")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    boards = {label[-2:]: f"{before[label]['boards']}->{after[label]['boards']}" for label in before}
    dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"GROOVE_WIDTH_OK|{'reverted' if revert else 'applied'}|boards={boards}|current=all|dirty_after={dirty[0]}+{dirty[1]}")


main()
