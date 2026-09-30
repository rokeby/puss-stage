"""Pit-hole floors (30 Sep, conductor-approved option (b)): give back the floor this morning's trim removed
beyond each hangar's hinge at S1, S5 and S6, EXCEPT over the hangar's swept footprint, so the approach sees
a dark floor to the horizon again (Gary: "bright dusky horizon") and the box still rises cleanly out of its
pit. The hole is x = hinge .. hinge + reach (+25 cm) by +-(half_w + wall_t + 100 + 25 cm) in the dock frame:
the builder's own swept box (reach from hangar_sN_plan.json) plus a margin, so no strip can ever be a
blocker. Up to three new strips per scene, beside the trimmed plane (which is untouched): LEFT and RIGHT of
the hole (hinge -> the plane's old far end) and FAR beyond it. Same engine Cube, material, thickness and z
as the plane; transient-free level actors tagged RigAtmos.PitFloor. A strip with no length is not made
(S5: its box is as wide as its plane and reaches past the old 16 m, so nothing comes back there).
Dry run (default): every number. Apply (PIT_APPLY): plain record, Backups/PrePitFloor-*, spawn, read back
from bounds, save the level only. Revert (PIT_REVERT): destroy the recorded strips, save. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "plane_pithole_record.json")
MARGIN = 25.0


def fail(msg):
    unreal.log_error("PIT_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("PIT_APPLY")), bool(globals().get("PIT_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    trim = {r["scene"]: r for r in json.load(open(os.path.join(HERE, "plane_trim_record.json"), encoding="utf-8"))["planes"]}
    plan = []
    for n in (1, 5, 6):
        t = trim[n]
        rec = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))
        h = rec["hangar"]
        reach = json.load(open(os.path.join(HERE, f"hangar_s{n}_plan.json"), encoding="utf-8"))["reach_cm"]
        cam = next(a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label())
        if abs(cam.get_actor_rotation().yaw) > 0.01:
            fail(f"S{n}: dock yawed")
        dock_y = cam.get_actor_location().y
        hinge = t["hinge_x"]
        far = t["far_x"]
        py0, py1 = t["loc"][1] - 50.0 * t["scale"][1], t["loc"][1] + 50.0 * t["scale"][1]
        half_y = h["half_w"] + h["wall_t"] + 100.0 + MARGIN
        hole_x1 = hinge + reach + MARGIN
        strips = []
        for name, x0, x1, y0, y1 in (("Left", hinge, far, py0, dock_y - half_y), ("Right", hinge, far, dock_y + half_y, py1),
                                     ("Far", hole_x1, far, max(py0, dock_y - half_y), min(py1, dock_y + half_y))):
            if x1 - x0 > 1.0 and y1 - y0 > 1.0:
                strips.append({"label": f"{t['label']} - Pit Strip {name}", "x": [round(x0, 2), round(x1, 2)], "y": [round(y0, 2), round(y1, 2)]})
        plan.append({"scene": n, "plane": t["label"], "hinge_x": hinge, "old_far_x": far, "reach_cm": reach, "hole_x": [hinge, round(hole_x1, 2)],
                     "hole_y": [round(dock_y - half_y, 2), round(dock_y + half_y, 2)], "plane_y": [py0, py1], "z": t["loc"][2],
                     "scale_z": t["scale"][2], "strips": strips})
    unreal.log(f"PIT_PLAN|{json.dumps(plan)}")
    if not (apply or revert):
        unreal.log("PIT_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    if any(l.startswith("ZZ_") for l in by):
        fail("bench actors (ZZ_) in the level")
    got = []
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        for label in rec["spawned"]:
            if label in by:
                sub.destroy_actor(by[label])
    else:
        if os.path.exists(RECORD) or any(s["label"] in by for p in plan for s in p["strips"]):
            fail("already applied (record or strips exist); revert first")
        stamp = datetime.datetime.now()
        spawned = [s["label"] for p in plan for s in p["strips"]]
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": stamp.isoformat(timespec="seconds"), "spawned": spawned, "plan": plan}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PrePitFloor-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        for p in plan:
            src = by[p["plane"]]
            smc_src = src.get_component_by_class(unreal.StaticMeshComponent)
            for s in p["strips"]:
                (x0, x1), (y0, y1) = s["x"], s["y"]
                a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector((x0 + x1) / 2.0, (y0 + y1) / 2.0, p["z"]), unreal.Rotator(0.0, 0.0, 0.0))
                a.set_actor_label(s["label"])
                a.set_folder_path(src.get_folder_path())
                a.set_editor_property("tags", [unreal.Name("RigAtmos.PitFloor"), unreal.Name(f"RigAtmos.Scene{p['scene']}PitFloor")])
                smc = a.get_editor_property("static_mesh_component")
                smc.set_static_mesh(smc_src.get_editor_property("static_mesh"))
                smc.set_material(0, smc_src.get_material(0))
                smc.set_collision_enabled(smc_src.get_collision_enabled())
                a.set_actor_scale3d(unreal.Vector((x1 - x0) / 100.0, (y1 - y0) / 100.0, p["scale_z"]))
                o, e = a.get_actor_bounds(False)
                if abs((o.x - e.x) - x0) > 0.5 or abs((o.x + e.x) - x1) > 0.5 or abs((o.y - e.y) - y0) > 0.5 or abs((o.y + e.y) - y1) > 0.5:
                    fail(f"{s['label']} landed x[{o.x - e.x:.1f},{o.x + e.x:.1f}] y[{o.y - e.y:.1f},{o.y + e.y:.1f}] (NOT saved)")
                got.append(f"{s['label']}:x[{o.x - e.x:.0f},{o.x + e.x:.0f}]y[{o.y - e.y:.0f},{o.y + e.y:.0f}]")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
        [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"PIT_OK|{'reverted' if revert else 'applied'}|{'|'.join(got)}|dirty_after={d}")


main()
