"""Assign the steel grooves' material and re-fit (Gary, 29 Sep: "walnut planks on the
boards plus procedural steel grooves"). The grooves are built from 1ef583b, compiled
in the 29 Sep evening batch, with bSteelGrooves on by default. So every structure
with slots gets Ground.GrooveMaterial = MI_Kit_SteelGroove and is re-fitted.

Per structure, only groove_piece_count may change, and it must reach exactly 3 per
slot. Every other count (stations, beams, rails, boards, slots, fixtures, lines,
portal pieces) must be unchanged, and all six must read current. Structures
without slots (Structure 03) are re-fitted untouched. Saves the level only.

Guards: world, no PIE, 0+0 dirty, no ZZ_ actors, the groove material loads, and
the grooves are compiled in (groove_piece_count exists). Revert record written
first. Dry run: GROOVE_DRY_RUN (groove_material_dryrun.py). Revert:
groove_material_revert.py. It restores the recorded material and turns
bSteelGrooves OFF, the pre-build look with no grooves, rather than leaving
grooves in the default material. Take Backups/PreGrooveMaterial-* (umap) first.
Lean: all work in main().
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GROOVE = "/Game/Scenes/Wings/PaintedSurface/Kit/MI_Kit_SteelGroove"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "groove_material_revert_record.json")
OUT = os.path.join(HERE, "groove_material.json")
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count", "cloth_count",
          "fixture_body_count", "hanging_line_count", "portal_piece_count", "groove_piece_count")
PLATES_PER_SLOT = 3


def fail(message):
    raise RuntimeError(f"GROOVE_MATERIAL_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def state(a):
    return {"current": bool(a.is_structure_current()), **{c: int(a.get_editor_property(c)) for c in COUNTS}}


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE active")
    c0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c0 or m0:
        fail(f"editor already dirty: {c0} {m0}")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
        fail("bench actors in the level")
    structures = sorted((a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)), key=lambda a: a.get_actor_label())
    if len(structures) != 6:
        fail(f"expected 6 structures, found {len(structures)}")
    try:
        structures[0].get_editor_property("groove_piece_count")
    except Exception:
        fail("the loaded plugin has no grooves (stale binaries)")
    mat = unreal.EditorAssetLibrary.load_asset(GROOVE)
    if not isinstance(mat, unreal.MaterialInterface):
        fail(f"{GROOVE} did not load")
    before = {a.get_actor_label(): state(a) for a in structures}
    ground_before = {}
    for a in structures:
        g = a.get_editor_property("ground")
        m = g.get_editor_property("groove_material")
        ground_before[a.get_actor_label()] = {"steel_grooves": bool(g.get_editor_property("steel_grooves")),
                                              "groove_material": m.get_path_name() if m else None}
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "before": before, "ground_before": ground_before}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if json.load(open(RECORD, encoding="utf-8"))["ground_before"] != ground_before:
        fail("revert record did not read back")
    unreal.log(f"GROOVE_REVERT_RECORD_OK|before={before}|ground_before={ground_before}")
    if globals().get("GROOVE_DRY_RUN"):
        json.dump({"before": before, "ground_before": ground_before}, open(OUT, "w"), indent=1)
        unreal.log("GROOVE_DRY_RUN_OK|mutated=0")
        return "dry"

    for a in structures:
        a.modify()
        g = a.get_editor_property("ground")
        g.set_editor_property("groove_material", mat)
        g.set_editor_property("steel_grooves", True)
        a.set_editor_property("ground", g)
        if not a.materialize_structure():
            fail(f"{a.get_actor_label()} did not re-fit")
    after = {a.get_actor_label(): state(a) for a in structures}
    problems = []
    for label, rec in after.items():
        if not rec["current"]:
            problems.append(f"{label} not current")
        for c in COUNTS:
            if c != "groove_piece_count" and rec[c] != before[label][c]:
                problems.append(f"{label} {c}: {before[label][c]} -> {rec[c]}")
        if rec["groove_piece_count"] != PLATES_PER_SLOT * rec["slot_count"]:
            problems.append(f"{label}: {rec['groove_piece_count']} groove plates for {rec['slot_count']} slots")
    json.dump({"before": before, "after": after, "problems": problems}, open(OUT, "w"), indent=1)
    if problems:
        fail(f"unexpected, NOT saved: {problems}")
    c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c1 or m1 != [EXPECTED_WORLD]:
        fail(f"unexpected dirty set: {c1} {m1}")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    grooves = {k: v["groove_piece_count"] for k, v in after.items()}
    unreal.log(f"GROOVE_MATERIAL_OK|grooves={grooves}|current=6/6|level_saved=1")
    return "applied"


result = main()
