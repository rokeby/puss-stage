"""Undo portal_enable_apply.py: switch Structure 01's portal off, re-fit, and save
the level only. The pass is deterministic, so the re-fit restores every count the
revert record holds; the Backups/PrePortal-* umap is the fallback. Refuses while
lip floats exist (revert p01_lip_floats first, or they would stand in void)."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "portal_enable_revert_record.json")


def fail(message):
    raise RuntimeError(f"PORTAL_ENABLE_REVERT_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
c0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if c0 or m0:
    fail(f"editor already dirty: {c0} {m0}")
record = json.load(open(RECORD, encoding="utf-8"))
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
lips = [str(a.get_editor_property("label")) for cue in show.get_editor_property("cues")
        for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")
        if " Lip " in str(a.get_editor_property("label"))]
if lips:
    fail(f"{len(lips)} lip floats still in the Show; run p01_lip_floats_revert.py first")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if any(a.get_actor_label().startswith("ZZ_") for a in sub.get_all_level_actors()):
    fail("stray ZZ_ actors in the level")
target = next((a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)
               and a.get_actor_label() == record["structure"]), None)
if target is None:
    fail(f"{record['structure']} not found")
target.modify()
portal = target.get_editor_property("portal")
portal.set_editor_property("enabled", False)
portal.set_editor_property("forestage_depth_cm", float(record.get("forestage_depth_before", 150.0)))
target.set_editor_property("portal", portal)
if not target.materialize_structure():
    fail(f"{record['structure']} did not re-fit")
want = record["before"][record["structure"]]
got = {"current": bool(target.is_structure_current()), **{c: int(target.get_editor_property(c)) for c in want if c != "current"}}
if got != want:
    fail(f"re-fit did not restore the recorded state, NOT saved: {want} vs {got}")
c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if c1 or m1 != [EXPECTED_WORLD]:
    fail(f"unexpected dirty set before save: {c1} {m1}")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
unreal.log(f"PORTAL_ENABLE_REVERT_OK|structure={record['structure']}|portal_pieces=0|level_saved=1")
