"""Gary, 29 Sep, after seeing the boards: "the chariot slots don't look nearly as
good as the regular floor ... ideally we would use the walnut". Raise the three
textured slabs from under the boards (top -5) to just ABOVE them (top +0.5), so
the walnut, oak and Versailles are the visible corridor floor again, without
fighting the boards' top at 0. P01's trim at the lip (x -150) is kept. Only Z
changes: the location z goes from -5.5 to 0.0, with the scale Z of 0.01 kept (a
1 cm slab from -0.5 to +0.5).

Expects exactly the state floors_to_stage_apply.py left, and refuses otherwise.
The revert record holds that state; floors_above_boards_revert.py restores it.
Take a Backups/PreFloorsAboveBoards-* umap snapshot first. Saves the level only,
refusing on any other dirty package or bench actor. Rehearse with
FLOORS_ABOVE_DRY_RUN via runpy.
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "floors_above_boards_revert_record.json")
EXPECTED = {   # the state after floors_to_stage_apply.py (29 Sep 12:33), read back by the floor sweep
    "StaticMeshActor_0": ((34499.98, 0.0, -5.5), (692.9996, 200.0, 0.01)),
    "StaticMeshActor_1": ((17000.0, 399485.79, -5.5), (500.0, 200.0, 0.01)),
    "StaticMeshActor_7": ((23714.58, 320309.98, -5.5), (500.0, 200.0, 0.01)),
}
NEW_Z = 0.0     # a 1 cm slab centred at 0: top +0.5, just above the boards' top at 0


def fail(message):
    raise RuntimeError(f"FLOORS_ABOVE_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def near(a, b, tol):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
    fail("wrong world, or PIE active")
content0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if content0 or maps0:
    fail(f"editor already dirty: {content0} {maps0}")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
    fail("bench actors in the level")
found = {a.get_name(): a for a in actors if a.get_name() in EXPECTED}
if sorted(found) != sorted(EXPECTED):
    fail(f"slabs found {sorted(found)}")
record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "slabs": {}}
for name, (loc, scale) in EXPECTED.items():
    tf = found[name].get_actor_transform()
    cur_loc = [tf.translation.x, tf.translation.y, tf.translation.z]
    cur_scale = [tf.scale3d.x, tf.scale3d.y, tf.scale3d.z]
    if not near(cur_loc, loc, 0.05) or not near(cur_scale, scale, 0.001):
        fail(f"{name} is not in the state floors_to_stage_apply.py left: {cur_loc} {cur_scale}")
    record["slabs"][name] = {"loc": cur_loc, "scale": cur_scale}
with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
if json.load(open(RECORD, encoding="utf-8"))["slabs"] != record["slabs"]:
    fail("revert record did not read back")
unreal.log(f"FLOORS_ABOVE_REVERT_RECORD_OK|slabs={len(record['slabs'])}")
if globals().get("FLOORS_ABOVE_DRY_RUN"):
    unreal.log("FLOORS_ABOVE_DRY_RUN_OK|mutated=0")
    raise RuntimeError("FLOORS_ABOVE_DRY_RUN_COMPLETE")

for name, a in found.items():
    old = record["slabs"][name]["loc"]
    a.modify()
    a.set_actor_location(unreal.Vector(old[0], old[1], NEW_Z), False, False)
problems = []
for name, a in found.items():
    origin, extent = a.get_actor_bounds(False)
    if abs(origin.z + extent.z - 0.5) > 0.05:
        problems.append(f"{name} top {origin.z + extent.z:.3f}")
    old = record["slabs"][name]["loc"]
    if abs(origin.x - old[0]) > 1.0 or abs(origin.y - old[1]) > 1.0:
        problems.append(f"{name} moved laterally")
c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if c1 or m1 != [EXPECTED_WORLD]:
    problems.append(f"dirty set {c1} {m1}")
if problems:
    fail(f"NOT saved: {problems}")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
c2 = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
m2 = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.log(f"FLOORS_ABOVE_OK|slabs=3|top=0.5|p01_trim_kept=1|level_saved=1|dirty_after={len(c2)}+{len(m2)}")
