"""Landscape block step 4 (30 Sep): re-seat the five Scene 3 foliage props that stood on the Wet Ground's relief onto
the new flat surface (Structure 03's boards at 0, or the P03 floor plane at -5). Each prop moves by
(new surface - old surface), so its own sunk or raised offset is kept. The old surface is the traced landscape
height from landscape_scope.json; the new one is traced now (the landscape is hidden with collision off) and is
accepted only if it is the P03 floor or Structure 03 - anything else refuses that prop rather than guessing.
Nobody owns Scene 3's props (conductor, 30 Sep); the moves are recorded to the cm.
Dry run (default). Apply (RESEAT_APPLY): record, Backups/PreP03Reseat-*, move, read back, save the level.
Revert (RESEAT_REVERT): restore the recorded locations. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "p03_props_reseat_record.json")
PROPS = ("SM_ivy_01_3", "SM_lily_01_1", "SM_lily_01_3", "SM_plant_02_2", "SM_foliage_fern_01_5")
SURFACES = ("Passage 03 - Floor", "Infinity Stage - Structure 03")


def fail(msg):
    unreal.log_error("RESEAT_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("RESEAT_APPLY")), bool(globals().get("RESEAT_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    old = {s["label"]: s for L in json.load(open(os.path.join(HERE, "landscape_scope.json"), encoding="utf-8"))["landscapes"]
           if L["label"] == "Passage 3 - Wet Ground" for s in L["standing"]}
    plan = []
    for label in PROPS:
        a = by.get(label)
        if a is None or label not in old:
            fail(f"{label}: missing in the level or the scope")
        o, e = a.get_actor_bounds(False)
        others = [x for x in actors if x.get_actor_label() in PROPS]
        hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(o.x, o.y, o.z - e.z + 60.0), unreal.Vector(o.x, o.y, -600.0),
                                                     unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, others, unreal.DrawDebugTrace.NONE, True)
        parts = hit.to_tuple() if hit else ()
        who = next((p for p in parts if isinstance(p, unreal.Actor)), None)
        loc = next((p for p in parts if isinstance(p, unreal.Vector)), None)
        new_surface = round(loc.z, 2) if loc else None
        ok_surface = who is not None and who.get_actor_label() in SURFACES
        delta = round(new_surface - old[label]["surface_z"], 2) if new_surface is not None else None
        l = a.get_actor_location()
        plan.append({"label": label, "old_surface": old[label]["surface_z"], "new_surface": new_surface, "hit": who.get_actor_label() if who else None,
                     "ok_surface": ok_surface, "delta_cm": delta, "loc": [l.x, l.y, l.z]})
    unreal.log(f"RESEAT_PLAN|{json.dumps(plan)}")
    if not (apply or revert):
        unreal.log("RESEAT_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() or any(l.startswith("ZZ_") for l in by):
        fail("Sequencer open or ZZ_ actors present")
    if revert:
        targets = {r["label"]: r["loc"] for r in json.load(open(RECORD, encoding="utf-8"))["plan"]}
    else:
        bad = [p["label"] for p in plan if not p["ok_surface"] or p["delta_cm"] is None]
        if bad or os.path.exists(RECORD):
            fail(f"refused: surface not the P03 floor/boards for {bad}, record exists={os.path.exists(RECORD)}")
        stamp = datetime.datetime.now()
        json.dump({"written": stamp.isoformat(timespec="seconds"), "plan": plan}, open(RECORD, "w", encoding="utf-8"), indent=1)
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreP03Reseat-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        targets = {p["label"]: [p["loc"][0], p["loc"][1], p["loc"][2] + p["delta_cm"]] for p in plan}
    for label, xyz in targets.items():
        by[label].set_actor_location(unreal.Vector(*xyz), False, True)
        got = by[label].get_actor_location()
        if abs(got.z - xyz[2]) > 0.1 or abs(got.x - xyz[0]) > 0.1 or abs(got.y - xyz[1]) > 0.1:
            fail(f"{label} landed at {got} (NOT saved)")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"RESEAT_OK|{'reverted' if revert else 'applied'}|{[(p['label'], p['delta_cm']) for p in plan]}|dirty_after={d}")


main()
