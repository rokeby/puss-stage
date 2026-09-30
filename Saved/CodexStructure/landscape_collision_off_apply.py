"""Landscape block step 1b (30 Sep): the hide set the ACTOR's collision off, but each landscape's 64
LandscapeHeightfieldCollisionComponents stayed QUERY_AND_PHYSICS (the actor flag does not reach them in the editor
world), so traces still hit the hidden terrain. Set every heightfield collision component of both landscapes to
NO_COLLISION, each recorded as it was. Dry run (default). Apply (LS_COLL_APPLY): record, Backups/PreLandscapeCollision-*,
set, read back, save the level. Revert (LS_COLL_REVERT): restore each component's recorded state. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "landscape_collision_off_record.json")
LABELS = ("Passage 1 - ForestedLandscape", "Passage 3 - Wet Ground")
STATES = {v.name: v for v in (unreal.CollisionEnabled.NO_COLLISION, unreal.CollisionEnabled.QUERY_ONLY,
                               unreal.CollisionEnabled.PHYSICS_ONLY, unreal.CollisionEnabled.QUERY_AND_PHYSICS)}


def fail(msg):
    unreal.log_error("LS_COLL_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("LS_COLL_APPLY")), bool(globals().get("LS_COLL_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    comps = {l: list(by[l].get_components_by_class(unreal.LandscapeHeightfieldCollisionComponent)) for l in LABELS}
    now = {l: [c.get_collision_enabled().name for c in comps[l]] for l in LABELS}
    unreal.log(f"LS_COLL_PLAN|" + " ".join(f"{l}:{len(v)} components, states {sorted(set(v))}" for l, v in now.items()))
    if not (apply or revert):
        unreal.log("LS_COLL_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer open")
    if revert:
        want = json.load(open(RECORD, encoding="utf-8"))["before"]
    else:
        if os.path.exists(RECORD):
            fail("already applied; revert first")
        stamp = datetime.datetime.now()
        json.dump({"written": stamp.isoformat(timespec="seconds"), "before": now}, open(RECORD, "w", encoding="utf-8"), indent=1)
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreLandscapeCollision-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        want = {l: [unreal.CollisionEnabled.NO_COLLISION.name] * len(comps[l]) for l in LABELS}
    for l in LABELS:
        if len(want[l]) != len(comps[l]):
            fail(f"{l}: component count changed ({len(comps[l])} vs recorded {len(want[l])})")
        for c, v in zip(comps[l], want[l]):
            c.modify()
            c.set_collision_enabled(STATES[v])
    got = {l: [c.get_collision_enabled().name for c in comps[l]] for l in LABELS}
    if got != want:
        fail("read-back mismatch (NOT saved)")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"LS_COLL_OK|{'reverted' if revert else 'applied'}|" + " ".join(f"{l}:{sorted(set(v))}" for l, v in got.items()) + f"|dirty_after={d}")


main()
