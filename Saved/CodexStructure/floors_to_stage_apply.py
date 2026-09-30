"""Gary, 29 Sep: "drop all floors to zero". Lower the three textured floor slabs
(engine Cubes 100 cm thick, top at +49.5) to the stage level, and save the level
only. Found by floor_slabs_sweep_readonly.py:
  StaticMeshActor_0  "Passage 01 - Opening Floor"    under P01, walnut
  StaticMeshActor_1  "Passage 01 - Opening Floor2"   under P06, Versailles
  StaticMeshActor_7  "Passage 05 - Floor (oak)" under P05, oak
Every structure's stage level is 0, and our ground boards' top is also 0, so the
slab's new top is chosen by MODE to avoid two coplanar floors fighting:
  "above": top +0.5, so his textures stay the visible stage.
  "below": top -5.0, under the boards, so our boards and slots show.
TRIM_P01_AT_LIP ends the P01 slab at the portal's lip (x -150), so the stage
front and its house floor (-120) aren't buried. Only X extent and position
change, never Y. Height, and the trim, are Gary's choices; set them before
running, as the conductor relays them.

Reversible: the old location and scale of each slab go to the revert record
(written, flushed and re-read first); floors_to_stage_revert.py puts them back.
Take a Backups/PreFloorsToStage-* umap snapshot first. The guard tolerates
exactly one foreign dirty package, Gary's LS_DevScene_03, which it never saves
and requires to still be dirty afterwards, plus the map's own flag. It refuses
on anything else. Rehearse with FLOORS_DRY_RUN via runpy.
"""
import datetime
import json
import os

import unreal

# Gary, 29 Sep, via the conductor: "Show me the boards" (slabs under them), and
# trim P01 at the lip so the stage front shows.
MODE = "below"
TRIM_P01_AT_LIP = True

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FOREIGN_OK = {"/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"}
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "floors_to_stage_revert_record.json")
CUBE = "/Engine/BasicShapes/Cube.Cube"
SLABS = {   # name: (label, expected loc, expected scale), as swept on 29 Sep
    "StaticMeshActor_0": ("Passage 01 - Opening Floor", (17000.0, 0.0, -0.5), (1042.9992, 200.0, 1.0)),
    "StaticMeshActor_1": ("Passage 01 - Opening Floor2", (17000.0, 399485.79, -0.5), (500.0, 200.0, 1.0)),
    "StaticMeshActor_7": ("Passage 05 - Floor (oak)", (23714.58, 320309.98, -0.5), (500.0, 200.0, 1.0)),
}
THICKNESS_SCALE = 0.01    # 1 cm: the engine Cube is 100 cm
P01_LIP_X = -150.0


def fail(message):
    raise RuntimeError(f"FLOORS_TO_STAGE_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return (sorted(pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            sorted(pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))


def near(a, b, tol=0.05):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


if MODE not in ("above", "below") or TRIM_P01_AT_LIP not in (True, False):
    fail("MODE and TRIM_P01_AT_LIP are Gary's choices and are not set")
top_z = 0.5 if MODE == "above" else -5.0
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
content0, maps0 = dirty()
if set(content0) - FOREIGN_OK or set(maps0) - {EXPECTED_WORLD}:
    fail(f"unexpected dirty state: {content0} {maps0}")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
    fail("bench actors in the level")
found = {a.get_name(): a for a in actors if a.get_name() in SLABS}
if sorted(found) != sorted(SLABS):
    fail(f"slabs found {sorted(found)}")
plan, record = {}, {"written": datetime.datetime.now().isoformat(timespec="seconds"), "mode": MODE,
                    "trim_p01_at_lip": TRIM_P01_AT_LIP, "slabs": {}}
for name, (label, loc, scale) in SLABS.items():
    a = found[name]
    tf = a.get_actor_transform()
    cur_loc = (tf.translation.x, tf.translation.y, tf.translation.z)
    cur_scale = (tf.scale3d.x, tf.scale3d.y, tf.scale3d.z)
    r = tf.rotation.rotator()
    if a.get_actor_label() != label or not near(cur_loc, loc) or not near(cur_scale, scale, 0.001) \
            or abs(r.roll) > 0.01 or abs(r.pitch) > 0.01 or abs(r.yaw) > 0.01:
        fail(f"{name} is not as swept: {a.get_actor_label()} {cur_loc} {cur_scale}")
    mesh = a.get_editor_property("static_mesh_component").get_editor_property("static_mesh")
    if not mesh or mesh.get_path_name() != CUBE:
        fail(f"{name} is not an engine Cube")
    record["slabs"][name] = {"label": label, "loc": list(cur_loc), "scale": list(cur_scale)}
    new_loc = [cur_loc[0], cur_loc[1], top_z - THICKNESS_SCALE * 50.0]
    new_scale = [cur_scale[0], cur_scale[1], THICKNESS_SCALE]
    if name == "StaticMeshActor_0" and TRIM_P01_AT_LIP:
        far_x = cur_loc[0] + cur_scale[0] * 50.0              # the upstage end stays put
        new_loc[0] = (P01_LIP_X + far_x) * 0.5
        new_scale[0] = (far_x - P01_LIP_X) / 100.0
    plan[name] = {"loc": new_loc, "scale": new_scale}
record["plan"] = plan
# LIP GUARD (30 Sep): TRIM_P01_AT_LIP only ever protected P01; P05's and P06's slabs from this pass buried their fascia.
# Refuse any planned slab downstage of any stage-front lip (lip_guard.py) before anything is written.
import runpy
_guard = runpy.run_path(os.path.join(HERE, "lip_guard.py"))
_lip_bad = _guard["violations"](_guard["mouth_frames"](actors),
                                [{"label": found[n].get_actor_label(), "loc": q["loc"], "size": [v * 100.0 for v in q["scale"]], "yaw": 0.0}
                                 for n, q in plan.items()])
unreal.log(f"FLOORS_TO_STAGE_LIP_GUARD|violations={_lip_bad}")
if _lip_bad:
    fail(f"lip guard: {_lip_bad}")

with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
if json.load(open(RECORD, encoding="utf-8"))["slabs"] != record["slabs"]:
    fail("revert record did not read back")
unreal.log(f"FLOORS_TO_STAGE_REVERT_RECORD_OK|mode={MODE}|top={top_z}|trim={TRIM_P01_AT_LIP}|plan={plan}")
if globals().get("FLOORS_DRY_RUN"):
    unreal.log("FLOORS_TO_STAGE_DRY_RUN_OK|mutated=0")
    raise RuntimeError("FLOORS_TO_STAGE_DRY_RUN_COMPLETE")

for name, p in plan.items():
    a = found[name]
    a.modify()
    a.set_actor_location(unreal.Vector(*p["loc"]), False, False)
    a.set_actor_scale3d(unreal.Vector(*p["scale"]))
problems = []
for name, p in plan.items():
    a = found[name]
    origin, extent = a.get_actor_bounds(False)
    top = origin.z + extent.z
    if abs(top - top_z) > 0.05:
        problems.append(f"{name} top {top:.3f}, want {top_z}")
    if name == "StaticMeshActor_0" and TRIM_P01_AT_LIP and abs((origin.x - extent.x) - P01_LIP_X) > 0.5:
        problems.append(f"P01 slab starts at {origin.x - extent.x:.1f}, want {P01_LIP_X}")
content1, maps1 = dirty()
if set(content1) != set(content0) or maps1 != [EXPECTED_WORLD]:
    problems.append(f"dirty set changed: {content1} {maps1}")
if problems:
    fail(f"NOT saved: {problems} (revert with floors_to_stage_revert.py, or relaunch without saving)")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
if set(content2) != set(content0):
    fail(f"a foreign package changed state across the save: {content0} -> {content2}")
unreal.log(f"FLOORS_TO_STAGE_OK|mode={MODE}|top={top_z}|trim={TRIM_P01_AT_LIP}|slabs=3|level_saved=1"
           f"|foreign_untouched={sorted(content2)}|dirty_after={len(content2)}+{len(maps2)}")
