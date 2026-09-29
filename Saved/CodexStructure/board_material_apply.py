"""Gary, 29 Sep: "walnut planks". Assign Wing materiality's MI_Kit_WalnutPlank to
Ground.BoardMaterial on every structure whose ground layer is on, re-fit them,
and save the level only. The material drives the planks from the instance's local
position and custom data [variation, length, width, thickness] (never UV0),
with grain along local X, per the kit convention.

(Ground.GrooveMaterial -> MI_Kit_SteelGroove waits for the build that adds the
grooves; the loaded plugin has no such property yet.)

Guards: expected world, no PIE, 0+0 dirty, no bench actors, six structures all
current. Every count must be identical after the re-fit (only the material
changes), each board component must carry the new material, and the dirty set
must be exactly the level. The old material per structure goes to the revert
record first; board_material_revert.py restores it. Take a
Backups/PreBoardMaterial-* umap snapshot first. Lean: all work in main().
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MATERIAL = "/Game/Scenes/Wings/PaintedSurface/Kit/MI_Kit_WalnutPlank"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "board_material_revert_record.json")
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count",
          "fixture_body_count", "hanging_line_count", "portal_piece_count")


def fail(message):
    raise RuntimeError(f"BOARD_MATERIAL_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


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
    material = unreal.EditorAssetLibrary.load_asset(MATERIAL)
    if not material:
        fail(f"{MATERIAL} does not load")
    structures = sorted((a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)), key=lambda a: a.get_actor_label())
    if len(structures) != 6:
        fail(f"{len(structures)} structures")
    targets = [s for s in structures if s.get_editor_property("ground").get_editor_property("enabled")]
    before = {s.get_actor_label(): {"current": bool(s.is_structure_current()), **{c: int(s.get_editor_property(c)) for c in COUNTS}}
              for s in targets}
    if not all(v["current"] for v in before.values()):
        fail(f"not current: {[k for k, v in before.items() if not v['current']]}")
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "material": MATERIAL, "structures": {}}
    for s in targets:
        old = s.get_editor_property("ground").get_editor_property("board_material")
        record["structures"][s.get_actor_label()] = {"old_board_material": old.get_path_name() if old else None,
                                                     "before": before[s.get_actor_label()]}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if json.load(open(RECORD, encoding="utf-8"))["structures"].keys() != record["structures"].keys():
        fail("revert record did not read back")
    unreal.log(f"BOARD_MATERIAL_REVERT_RECORD_OK|targets={sorted(record['structures'])}")
    if globals().get("BOARD_MATERIAL_DRY_RUN"):
        unreal.log("BOARD_MATERIAL_DRY_RUN_OK|mutated=0")
        return "dry"

    problems = []
    for s in targets:
        s.modify()
        ground = s.get_editor_property("ground")
        ground.set_editor_property("board_material", material)
        s.set_editor_property("ground", ground)
        if not s.materialize_structure():
            fail(f"{s.get_actor_label()} did not re-fit")
        label = s.get_actor_label()
        now = {"current": bool(s.is_structure_current()), **{c: int(s.get_editor_property(c)) for c in COUNTS}}
        if now != before[label]:
            problems.append(f"{label}: {before[label]} -> {now}")
        boards = [c for c in s.get_editor_property("managed_components")
                  if c and "InfinityStage.Structure.Ground" in [str(t) for t in c.get_editor_property("component_tags")]]
        if not boards or any((c.get_material(0).get_path_name().split(".")[0] if c.get_material(0) else None) != MATERIAL
                             for c in boards):
            problems.append(f"{label}: board component does not carry the material")
    c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c1 or m1 != [EXPECTED_WORLD]:
        problems.append(f"dirty set {c1} {m1}")
    if problems:
        fail(f"NOT saved: {problems}")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    c2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"BOARD_MATERIAL_OK|structures={len(targets)}|material={MATERIAL}|counts_unchanged=1|level_saved=1"
               f"|dirty_after={c2}+{m2}")
    return "applied"


result = main()
