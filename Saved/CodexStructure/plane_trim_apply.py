"""End three Passage floor planes at their hangar's hinge line (30 Sep; conductor-approved: conforms
S1, S5 and S6 to the convention P04's Structure Ground already sets: void beyond the hinge, the
box hanging in it). The near end of each plane is unchanged, so the Passages do not change.
  S1 "Passage 01 - Opening Floor"     overruns its hinge by 399 m
  S5 "Passage 03 - Dark Wood Floor2"  by 16 m
  S6 "Passage 01 - Opening Floor2"    by 139 m
Each plane is a scaled engine Cube (100 cm, centred pivot), unrotated, untagged, unattached; the
far end moves to x = hinge (the Scene's Entry Handoff Camera x + the hangar's apron, from its
record), scale and location recomputed so the near end stays put.
Refuses (nothing written) if: wrong world or PIE; anything dirty; Sequencer open; a ZZ_ actor; a
plane missing, not a Cube, rotated, tagged or attached; its computed extent disagrees with its
bounds by more than 1 cm; its hinge is not inside it; or ANYTHING stands on it beyond the hinge
(re-checked now, not trusted from the survey).
Dry run (default): every number, nothing written. Apply (PLANE_TRIM_APPLY): plain record first,
Backups/PrePlaneTrim-* (level + record), set, read back from bounds, save the level only.
Revert (PLANE_TRIM_REVERT): restores each plane's recorded location and scale. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "plane_trim_record.json")
PLANES = {1: "Passage 01 - Opening Floor", 5: "Passage 03 - Dark Wood Floor2", 6: "Passage 01 - Opening Floor2"}
CUBE = "/Engine/BasicShapes/Cube.Cube"


def fail(msg):
    unreal.log_error("PLANE_TRIM_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("PLANE_TRIM_APPLY")), bool(globals().get("PLANE_TRIM_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    rows = []
    for n, label in PLANES.items():
        a = by.get(label)
        if a is None:
            fail(f"S{n}: '{label}' missing")
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        mesh = smc.get_editor_property("static_mesh") if smc else None
        rot, loc, sc = a.get_actor_rotation(), a.get_actor_location(), a.get_actor_scale3d()
        rec = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))
        cam = next(c for c in actors if c.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in c.get_actor_label())
        if abs(cam.get_actor_rotation().yaw) > 0.01 or abs(rec["dock"]["yaw"]) > 0.01:
            fail(f"S{n}: the dock is yawed; this script only handles docks along +X")
        hinge_x = cam.get_actor_location().x + rec["hangar"]["apron"]
        o, e = a.get_actor_bounds(False)
        near, far = loc.x - 50.0 * sc.x, loc.x + 50.0 * sc.x
        row = {"scene": n, "label": label, "hinge_x": hinge_x, "loc": [loc.x, loc.y, loc.z], "scale": [sc.x, sc.y, sc.z],
               "near_x": near, "far_x": far, "overrun_m": round((far - hinge_x) / 100.0, 2),
               "mesh_ok": bool(mesh) and mesh.get_path_name() == CUBE,
               "unrotated": max(abs(rot.roll), abs(rot.pitch), abs(rot.yaw)) < 0.01,
               "untagged": len(a.tags) == 0, "unattached": a.get_attach_parent_actor() is None,
               "bounds_agree": abs((o.x - e.x) - near) < 1.0 and abs((o.x + e.x) - far) < 1.0}
        top = o.z + e.z
        standing = []
        for b in actors:
            if b is a or b.get_actor_label().startswith(f"S{n} ") or isinstance(b, (unreal.PostProcessVolume, unreal.CameraActor)):
                continue
            bo, be = b.get_actor_bounds(False)
            if be.length() < 1.0 or max(be.x, be.y) > 2.0e5:
                continue
            if (bo.x + be.x) > hinge_x and (bo.x - be.x) < far and abs(bo.y - o.y) < e.y + be.y and abs((bo.z - be.z) - top) < 60.0:
                standing.append(b.get_actor_label())
        row["standing_beyond"] = standing
        row["new_scale_x"] = (hinge_x - near) / 100.0
        row["new_loc_x"] = (near + hinge_x) / 2.0
        rows.append(row)
    unreal.log(f"PLANE_TRIM_PLAN|{json.dumps(rows)}")
    if not (apply or revert):
        unreal.log("PLANE_TRIM_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    if any(l.startswith("ZZ_") for l in by):
        fail("bench actors (ZZ_) in the level")
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        for r in rec["planes"]:
            a = by[r["label"]]
            a.set_actor_scale3d(unreal.Vector(*r["scale"]))
            a.set_actor_location(unreal.Vector(*r["loc"]), False, True)
        want = {r["label"]: (r["near_x"], r["far_x"]) for r in rec["planes"]}
    else:
        bad = [(r["scene"], k) for r in rows for k in ("mesh_ok", "unrotated", "untagged", "unattached", "bounds_agree") if not r[k]]
        bad += [(r["scene"], f"standing beyond: {r['standing_beyond'][:3]}") for r in rows if r["standing_beyond"]]
        bad += [(r["scene"], "hinge not inside the plane") for r in rows if not (r["near_x"] < r["hinge_x"] < r["far_x"])]
        if bad or os.path.exists(RECORD):
            fail(f"refused: {bad}, record exists={os.path.exists(RECORD)}")
        stamp = datetime.datetime.now()
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": stamp.isoformat(timespec="seconds"), "planes": rows}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PrePlaneTrim-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        for r in rows:
            a = by[r["label"]]
            a.set_actor_scale3d(unreal.Vector(r["new_scale_x"], r["scale"][1], r["scale"][2]))
            a.set_actor_location(unreal.Vector(r["new_loc_x"], r["loc"][1], r["loc"][2]), False, True)
        want = {r["label"]: (r["near_x"], r["hinge_x"]) for r in rows}
    # Read back from the world bounds, before saving.
    got = []
    for label, (w_near, w_far) in want.items():
        o, e = by[label].get_actor_bounds(False)
        if abs((o.x - e.x) - w_near) > 0.5 or abs((o.x + e.x) - w_far) > 0.5:
            fail(f"{label}: x[{o.x - e.x:.1f},{o.x + e.x:.1f}], wanted [{w_near:.1f},{w_far:.1f}] (NOT saved)")
        got.append(f"{label}:x[{o.x - e.x:.1f},{o.x + e.x:.1f}]")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    dirty = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
            [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"PLANE_TRIM_OK|{'reverted' if revert else 'applied'}|{'|'.join(got)}|dirty_after={dirty}")


main()
