"""Pit liners (30 Sep, completing conductor-approved option (b)): under each pit-hole at S1, S5 and S6, a dark
open-topped box so the approach no longer sees dusk sky through the hole below the lip (measured: the
pit-hole floors alone left 7-16% of the 10 m-back frame changed vs the old floor, all of it the hole).
Geometry from the same numbers as plane_pithole_apply.py (the builder's swept box + 25 cm):
  floor   under the whole hole, 250 cm below the lowest point the box ever reaches (every point of the
          box is lowest at rest, at -(depth + wall_t) below the hinge);
  walls   far, left and right, 25 cm outside the swept box, from the floor up to just under the floor
          strips; a near wall behind the hanging box floor (the builder guarantees nothing crosses
          back past apron - 25 cm).
The hangar walls' own black steel (M_Metal_Black_01_Mat). Level actors tagged RigAtmos.PitLiner. None of it
is inside the swept box, so the blocker test and the rise are untouched.
Dry run (default). Apply (LINER_APPLY): record, Backups/PrePitLiner-*, spawn, read back, save the level only.
Revert (LINER_REVERT): destroy the recorded pieces, save. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "plane_pitliner_record.json")
STEEL = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
CUBE = "/Engine/BasicShapes/Cube.Cube"
T, MARGIN = 20.0, 25.0


def fail(msg):
    unreal.log_error("LINER_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("LINER_APPLY")), bool(globals().get("LINER_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    pits = {p["scene"]: p for p in json.load(open(os.path.join(HERE, "plane_pithole_record.json"), encoding="utf-8"))["plan"]}
    plan = []
    for n in (1, 5, 6):
        p = pits[n]
        h = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))["hangar"]
        hz = float(h.get("hinge_z") or 0.0)
        (x0, x1), (y0, y1) = p["hole_x"], p["hole_y"]
        z_top = p["z"] - 0.5 * 100.0 * p["scale_z"] - 1.0          # just under the floor strips
        z_floor = hz - (h["depth"] + h["wall_t"]) - 250.0
        near = x0 - MARGIN - 40.0                                   # behind the hanging floor slab
        pieces = [("Floor", (x0, x1), (y0, y1), (z_floor - T, z_floor)),
                  ("Far Wall", (x1, x1 + T), (y0 - T, y1 + T), (z_floor - T, z_top)),
                  ("Left Wall", (near, x1), (y0 - T, y0), (z_floor - T, z_top)),
                  ("Right Wall", (near, x1), (y1, y1 + T), (z_floor - T, z_top)),
                  ("Near Wall", (near - T, near), (y0 - T, y1 + T), (z_floor - T, z_top))]
        plan.append({"scene": n, "z_top": round(z_top, 2), "z_floor": round(z_floor, 2),
                     "pieces": [{"label": f"S{n} Pit Liner {nm}", "x": [round(a, 2) for a in xs], "y": [round(a, 2) for a in ys],
                                 "z": [round(a, 2) for a in zs]} for nm, xs, ys, zs in pieces]})
    unreal.log(f"LINER_PLAN|{json.dumps(plan)}")
    if not (apply or revert):
        unreal.log("LINER_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    if any(l.startswith("ZZ_") for l in by):
        fail("bench actors (ZZ_) in the level")
    got = []
    if revert:
        for label in json.load(open(RECORD, encoding="utf-8"))["spawned"]:
            if label in by:
                sub.destroy_actor(by[label])
    else:
        if os.path.exists(RECORD) or any(pc["label"] in by for p in plan for pc in p["pieces"]):
            fail("already applied; revert first")
        stamp = datetime.datetime.now()
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": stamp.isoformat(timespec="seconds"), "spawned": [pc["label"] for p in plan for pc in p["pieces"]], "plan": plan}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PrePitLiner-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        mesh, mat = unreal.load_asset(CUBE), unreal.load_asset(STEEL)
        if not (mesh and mat):
            fail("cube or steel did not load")
        for p in plan:
            for pc in p["pieces"]:
                (xa, xb), (ya, yb), (za, zb) = pc["x"], pc["y"], pc["z"]
                a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector((xa + xb) / 2, (ya + yb) / 2, (za + zb) / 2), unreal.Rotator(0.0, 0.0, 0.0))
                a.set_actor_label(pc["label"])
                a.set_folder_path(f"Infinity Stage/Scene 0{p['scene']} Hangar")
                a.set_editor_property("tags", [unreal.Name("RigAtmos.PitLiner"), unreal.Name(f"RigAtmos.Scene{p['scene']}PitLiner")])
                smc = a.get_editor_property("static_mesh_component")
                smc.set_static_mesh(mesh)
                smc.set_material(0, mat)
                a.set_actor_scale3d(unreal.Vector((xb - xa) / 100.0, (yb - ya) / 100.0, (zb - za) / 100.0))
                o, e = a.get_actor_bounds(False)
                if max(abs((o.x - e.x) - xa), abs((o.x + e.x) - xb), abs((o.y - e.y) - ya), abs((o.y + e.y) - yb), abs((o.z - e.z) - za), abs((o.z + e.z) - zb)) > 0.5:
                    fail(f"{pc['label']} landed wrong (NOT saved)")
                got.append(pc["label"])
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
        [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"LINER_OK|{'reverted' if revert else 'applied'}|pieces={len(got)}|dirty_after={d}")


main()
