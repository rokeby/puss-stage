"""Rename the MISLABELLED P05 floor (30 Sep; conductor-approved as non-creative): "Passage 03 - Dark Wood Floor2" sits under
P05 (y ~320,000; Structure 05 at 320,000), not P03 (160,000). Its label sent at least one stream looking for "P03 oak" to
P05. Its pit strip carries the same prefix. New labels: "Passage 05 - Floor (oak)" and "... - Pit Strip Right".
A bare rename would break every record that finds these actors BY LABEL, so the records are rewritten IN THE SAME RUN
(backed up first): floors_to_stage_revert_record, plane_trim_record, plane_pithole_record, landscape_floors_record
(material source), hangar_s5_record and hangar_s5_plan. The six scripts' literals change in the same commit.
Historical outputs (inventories, sweeps, blink json) are snapshots and stay as they were.
Guards: world, no PIE, 0+0 dirty (both packages), no Sequencer, no ZZ_/TEMP_; each actor must lie in P05's lane
(|y - 320,000| < 40,000); no actor may already carry a new label. Dry run by default. Apply (RENAME_APPLY): record,
Backups/PreP05FloorRename-* (umap + the records), rename, read back, save the level, rewrite the records.
Revert (RENAME_REVERT): the reverse, from the record. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "rename_p05_floor_record.json")
RENAMES = [("Passage 03 - Dark Wood Floor2 - Pit Strip Right", "Passage 05 - Floor (oak) - Pit Strip Right"),   # longer first
           ("Passage 03 - Dark Wood Floor2", "Passage 05 - Floor (oak)")]
RECORDS = ("floors_to_stage_revert_record.json", "plane_trim_record.json", "plane_pithole_record.json",
           "landscape_floors_record.json", "hangar_s5_record.json", "hangar_s5_plan.json")
LANE5_Y, HALF = 320000.0, 40000.0


def fail(msg):
    unreal.log_error("RENAME_P05_STOPPED|" + msg)
    raise RuntimeError(msg)


def dirty():
    return [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()] + \
        [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]


def rewrite_records(pairs):
    done = {}
    for name in RECORDS:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            done[name] = "absent"
            continue
        text = open(path, encoding="utf-8").read()
        new = text
        for old, nu in pairs:
            new = new.replace(old, nu)
        if new != text:
            json.loads(new)                      # still valid JSON, or stop before writing
            open(path, "w", encoding="utf-8").write(new)
        done[name] = sum(text.count(o) for o, _ in pairs)
    return done


def main():
    apply, revert = bool(globals().get("RENAME_APPLY")), bool(globals().get("RENAME_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    pairs = [(n, o) for o, n in RENAMES] if revert else RENAMES
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by = {}
    for a in actors:
        by.setdefault(a.get_actor_label(), []).append(a)
    plan = []
    for old, nu in pairs:
        hits = by.get(old, [])
        if len(hits) != 1:
            fail(f"'{old}': {len(hits)} actors (need exactly 1)")
        if by.get(nu):
            fail(f"'{nu}' already exists")
        y = hits[0].get_actor_location().y
        if abs(y - LANE5_Y) > HALF:
            fail(f"'{old}' is at y {y:.0f}, not in P05's lane")
        plan.append({"old": old, "new": nu, "y": round(y)})
    unreal.log(f"RENAME_P05_PLAN|{json.dumps(plan)}|records={list(RECORDS)}")
    if not (apply or revert):
        unreal.log("RENAME_P05_DRY_RUN_OK|mutated=0")
        return
    if dirty() or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail(f"dirty {dirty()} or Sequencer open")
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP_")) for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)):
        fail("ZZ_/TEMP_ actors present")
    if apply and os.path.exists(RECORD):
        fail("already applied (record exists); revert first")
    stamp = datetime.datetime.now()
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", ("PreP05FloorRenameRevert-" if revert else "PreP05FloorRename-") + stamp.strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    for name in RECORDS:
        if os.path.exists(os.path.join(HERE, name)):
            shutil.copy2(os.path.join(HERE, name), backup)
    if apply:
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": stamp.isoformat(timespec="seconds"), "renames": plan, "backup": backup}, fh, indent=1)
        shutil.copy2(RECORD, backup)
    for row in plan:
        a = by[row["old"]][0]
        a.set_actor_label(row["new"])
        if a.get_actor_label() != row["new"]:
            fail(f"label read-back '{a.get_actor_label()}' (NOT saved)")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed (records NOT rewritten)")
    done = rewrite_records(pairs)
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    unreal.log(f"RENAME_P05_OK|{'reverted' if revert else 'applied'}|{[(r['old'], r['new']) for r in plan]}|records={done}|backup={backup}|dirty_after={dirty()}")


main()
