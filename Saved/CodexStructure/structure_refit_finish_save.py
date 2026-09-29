"""Finish structure_refit_all.py after its guard refused (29 Sep, 01:59): the in-memory
re-fit changed Structure 05's slot_count 186 -> 185, which the guard had assumed
impossible ("no Passage has a side with no wing"). P05 Wing 004's Right panel
stands ON the route line (lateral 0), so under the per-side fix (c8aee3b, "a side
with no wing gets no slot") that side correctly gets no slot. The old code gave it
one from the other side's wing.

This SAVES the level only, and only if the in-memory state is exactly that:
all six current; every count equal to the dry run's before-state except board
counts and that single Structure 05 slot; exactly one one-sided station
(P05 Wing 004); and the dirty set exactly the level. It re-fits nothing.
Backup: Backups/PreStructureRefit-20260929-0158.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
BEFORE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                      "Backups", "PreStructureRefit-20260929-0158", "structure_refit_before.json")
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count",
          "fixture_body_count", "hanging_line_count", "portal_piece_count")


def fail(message):
    raise RuntimeError(f"STRUCTURE_REFIT_FINISH_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if any(a.get_actor_label().startswith("ZZ_") for a in sub.get_all_level_actors()):
    fail("stray ZZ_ actors in the level")
before = json.load(open(BEFORE, encoding="utf-8"))["before"]
structures = sorted((a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)),
                    key=lambda a: a.get_actor_label())
if sorted(a.get_actor_label() for a in structures) != sorted(before):
    fail("structure set differs from the dry run")
problems, after = [], {}
for a in structures:
    label = a.get_actor_label()
    rec = {"current": bool(a.is_structure_current()), **{c: int(a.get_editor_property(c)) for c in COUNTS}}
    after[label] = rec
    if not rec["current"]:
        problems.append(f"{label} not current")
    for c in COUNTS:
        if c == "board_count":
            continue
        want = before[label][c]
        if label == "Infinity Stage - Structure 05" and c == "slot_count":
            want = before[label][c] - 1
        if rec[c] != want:
            problems.append(f"{label} {c}: {before[label][c]} -> {rec[c]} (allowed {want})")
p05 = next(a for a in structures if a.get_actor_label() == "Infinity Stage - Structure 05")
res = p05.gather_stations()
stations = res[0] if isinstance(res, tuple) else res
one_sided = [i for i, st in enumerate(stations)
             if st.get_editor_property("negative_side_cm") <= 0.0 or st.get_editor_property("positive_side_cm") <= 0.0]
if one_sided != [3]:
    problems.append(f"one-sided stations {one_sided}, expected [3] (P05 Wing 004)")
content, maps = ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
                 [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
if content or maps != [EXPECTED_WORLD]:
    problems.append(f"dirty set {content} {maps}")
json.dump({"before": before, "after": after, "problems": problems},
          open(os.path.join(HERE, "structure_refit_finish.json"), "w"), indent=1)
if problems:
    fail(f"NOT saved: {problems}")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
c2 = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
m2 = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.log(f"STRUCTURE_REFIT_OK|current={sum(v['current'] for v in after.values())}/6"
           f"|boards={sum(v['board_count'] for v in before.values())}->{sum(v['board_count'] for v in after.values())}"
           f"|slots_p05=186->185|level_saved=1|dirty_after={len(c2)}+{len(m2)}")
