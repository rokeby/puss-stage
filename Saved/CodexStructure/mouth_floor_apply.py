"""Mouth floor, generalised from p03_mouth_floor_apply.py (30 Sep). P03: Gary's own yes in the Rig & atmosphere session
("1 yes 2 sure"), applied 17:32. P05 and P06: Gary chose "Yes, same as P03" in the conductor session, confirmed with him.
MOUTH selects the passage (MOUTHS below); P02 is REFUSED here: its floor is rotated 66.5 deg to its mouth, so a straight
trim cannot express the lip (a notch is a separate design). For P05 the mislabelled floor and its pit strip are renamed IN
THE SAME RUN (rename_p05_floor_apply.py's pairs and record rewrites), so its trim and rename are one save.
The P03 design follows, unchanged:
1. TRIM "Passage 03 - Floor" (oak, top -5.0) to start at the lip, x -150 in P03's portal frame, across its full width, as
   P01's "Opening Floor" does. Today it starts 84 m downstage and buries the stage front's fascia and the house floor at
   -120 (Soft goods, measured), so the shared curtain pile (spill to z -0.71, 1.9 m downstage) would sink into it.
   Visible consequence, said to Gary: the fascia and the 1.2 m drop show where flat oak shows now.
2. OAK HOUSE FLOOR: the house floor at -120 is built by the stage front with the SAME material as every P03 stage board
   (InfinityStageStructureActor.cpp:1184), so recolouring it through the Structure would turn the whole stage oak. Instead:
   a 1 cm oak plane, "Passage 03 - House Floor (oak)", over exactly the "House floor: front" box of the stage-front colliders
   (x -2600..-155, |y| <= 2000 cm) with its top at -119 (1 cm above the boards), attached to Structure 03. The pile never
   reaches -120 (the cache's site table: "house floor at -120, not reached"; spill to -71), so it has no cloth effect.
Refuses unless the floor lies square to P03's frame (yaw within 0.05 deg) and the portal lip reads -150 as built.
Dry run (default): the plan in the portal frame, mutates nothing. Apply (P03FLOOR_APPLY): guards (world, no PIE, BOTH
packages clean, no Sequencer, no ZZ_/TEMP_, no record), record first, Backups/PreP03MouthFloor-*, edit, read back true
corners in the frame (0.5 cm), save the level only. Revert (P03FLOOR_REVERT): restore the floor's recorded transform,
destroy the house plane, save gated on read-back. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
MOUTHS = {"P03": {"structure": "Infinity Stage - Structure 03", "floor": "Passage 03 - Floor", "house": "Passage 03 - House Floor (oak)"},
          "P05": {"structure": "Infinity Stage - Structure 05", "floor": "Passage 03 - Dark Wood Floor2", "house": "Passage 05 - House Floor (oak)",
                  "renames": [("Passage 03 - Dark Wood Floor2 - Pit Strip Right", "Passage 05 - Floor (oak) - Pit Strip Right"),
                              ("Passage 03 - Dark Wood Floor2", "Passage 05 - Floor (oak)")]},
          "P06": {"structure": "Infinity Stage - Structure 06", "floor": "Passage 01 - Opening Floor2", "house": "Passage 06 - House Floor (oak)"}}
MOUTH = globals().get("MOUTH", "P03")
if MOUTH not in MOUTHS:
    raise RuntimeError(f"MOUTH {MOUTH} not handled here (P02 needs a notch design)")
M = MOUTHS[MOUTH]
RECORD = os.path.join(HERE, "p03_mouth_floor_record.json" if MOUTH == "P03" else f"mouth_floor_{MOUTH.lower()}_record.json")
FLOOR, HOUSE = M["floor"], M["house"]
RENAMES = M.get("renames", [])
RENAME_RECORDS = ("floors_to_stage_revert_record.json", "plane_trim_record.json", "plane_pithole_record.json",
                  "landscape_floors_record.json", "hangar_s5_record.json", "hangar_s5_plan.json")
HOUSE_BOX = {"x": (-2600.0, -155.0), "y": (-2000.0, 2000.0), "top": -119.0, "thick": 1.0}
TAG = "RigAtmos.LandscapeFloor"
CUBE = "/Engine/BasicShapes/Cube.Cube"


def fail(msg):
    unreal.log_error(f"MOUTHFLOOR_STOPPED|{MOUTH}|" + msg)
    raise RuntimeError(msg)


def dirty():
    return [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()] + \
        [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]


def extents(actor, frame):
    bb = actor.static_mesh_component.static_mesh.get_bounding_box()
    xf = actor.static_mesh_component.get_world_transform()
    pts = [frame.inverse_transform_location(xf.transform_location(unreal.Vector(x, y, z)))
           for x in (bb.min.x, bb.max.x) for y in (bb.min.y, bb.max.y) for z in (bb.min.z, bb.max.z)]
    return {"x": (min(p.x for p in pts), max(p.x for p in pts)), "y": (min(p.y for p in pts), max(p.y for p in pts)),
            "z": (min(p.z for p in pts), max(p.z for p in pts))}


def main():
    apply, revert = bool(globals().get("MOUTHFLOOR_APPLY") or globals().get("P03FLOOR_APPLY")), bool(globals().get("MOUTHFLOOR_REVERT") or globals().get("P03FLOOR_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    s, floor = by.get(M["structure"]), by.get(FLOOR)
    if s is None or floor is None:
        fail(f"{M['structure']} or {FLOOR} is missing")
    route = s.get_editor_property("passage").get_editor_property("route")
    start = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
    yaw = start.rotation.rotator().yaw
    frame = unreal.Transform(location=start.translation, rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    lip = -float(s.get_editor_property("portal").get_editor_property("forestage_depth_cm"))

    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        if dirty() or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
            fail("dirty or Sequencer open")
        o = rec["floor_before"]
        floor.set_actor_location(unreal.Vector(*o["loc"]), False, False)
        floor.set_actor_scale3d(unreal.Vector(*o["scale"]))
        h = by.get(HOUSE)
        if h is not None and TAG in [str(t) for t in h.get_editor_property("tags")]:
            sub.destroy_actor(h)
        now = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        if any(a.get_actor_label() == HOUSE for a in now) or (floor.get_actor_location() - unreal.Vector(*o["loc"])).length() > 0.5:
            fail("NOT saved: read-back after revert failed")
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            fail("level save failed")
        os.replace(RECORD, RECORD + ".reverted")
        unreal.log(f"MOUTHFLOOR_OK|{MOUTH}|reverted|dirty_after={dirty()}")
        return

    if abs(lip + 150.0) > 0.5:
        fail(f"portal lip reads {lip} cm, expected -150")
    if abs(((floor.get_actor_rotation().yaw - yaw) + 180.0) % 360.0 - 180.0) > 0.05:
        fail(f"the floor is not square to {MOUTH}'s frame")
    e = extents(floor, frame)
    old_len = e["x"][1] - e["x"][0]
    new_len = e["x"][1] - lip
    sc = floor.get_actor_scale3d()
    loc = floor.get_actor_location()
    lo = frame.inverse_transform_location(loc)
    new_loc = frame.transform_location(unreal.Vector(lo.x + (lip - e["x"][0]) / 2.0, lo.y, lo.z))
    new_scale = unreal.Vector(sc.x * new_len / old_len, sc.y, sc.z)
    hb = HOUSE_BOX
    house_centre = frame.transform_location(unreal.Vector(sum(hb["x"]) / 2.0, sum(hb["y"]) / 2.0, hb["top"] - hb["thick"] / 2.0))
    house_scale = unreal.Vector((hb["x"][1] - hb["x"][0]) / 100.0, (hb["y"][1] - hb["y"][0]) / 100.0, hb["thick"] / 100.0)
    plan = {"lip_cm": lip, "floor_before_frame": {k: [round(v[0], 1), round(v[1], 1)] for k, v in e.items()},
            "floor_after_x": [lip, round(e["x"][1], 1)], "trimmed_off_m": round((lip - e["x"][0]) / 100.0, 1),
            "house_plane": {"x": hb["x"], "y": hb["y"], "top": hb["top"]}, "house_exists": HOUSE in by}
    plan["renames"] = RENAMES
    unreal.log(f"MOUTHFLOOR_PLAN|{MOUTH}|{json.dumps(plan)}")
    if not apply:
        unreal.log(f"MOUTHFLOOR_DRY_RUN_OK|{MOUTH}|mutated=0")
        return
    if e["x"][0] >= lip - 1.0:
        fail("the floor already starts at or behind the lip; nothing to trim")
    if HOUSE in by or os.path.exists(RECORD):
        fail("house plane or record already exists")
    if dirty() or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail(f"dirty {dirty()} or Sequencer open")
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP_")) for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)):
        fail("ZZ_/TEMP_ actors present")
    stamp = datetime.datetime.now()
    rec = {"written": stamp.isoformat(timespec="seconds"), "mouth": MOUTH, "renames": RENAMES, "floor_before": {"loc": [loc.x, loc.y, loc.z], "scale": [sc.x, sc.y, sc.z]}, "plan": plan}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", f"PreMouthFloor{MOUTH}-" + stamp.strftime("%Y%m%d-%H%M"))
    for name in RENAME_RECORDS if RENAMES else ():
        if os.path.exists(os.path.join(HERE, name)):
            os.makedirs(backup, exist_ok=True)
            shutil.copy2(os.path.join(HERE, name), backup)
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    shutil.copy2(RECORD, backup)

    floor.set_actor_location(new_loc, False, False)
    floor.set_actor_scale3d(new_scale)
    # The house plane is OAK by Gary's word at every mouth. Copying the floor's material made P06's Versailles (30 Sep,
    # fixed by p06_house_oak_fix.py); set it explicitly.
    mat = unreal.load_asset("/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Oak_Hrrngbn_01_Mat_Inst_Dup")
    h = sub.spawn_actor_from_class(unreal.StaticMeshActor, house_centre, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    h.set_actor_label(HOUSE)
    h.set_editor_property("tags", [unreal.Name(TAG)])
    h.static_mesh_component.set_mobility(s.root_component.get_editor_property("mobility"))
    h.static_mesh_component.set_static_mesh(unreal.load_asset(CUBE))
    h.static_mesh_component.set_material(0, mat)
    h.set_actor_scale3d(house_scale)
    h.attach_to_actor(s, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)

    ef, eh = extents(floor, frame), extents(h, frame)
    bad = []
    if abs(ef["x"][0] - lip) > 0.5 or abs(ef["x"][1] - e["x"][1]) > 0.5 or abs(ef["z"][1] - e["z"][1]) > 0.1 \
            or abs(ef["y"][0] - e["y"][0]) > 0.5 or abs(ef["y"][1] - e["y"][1]) > 0.5:
        bad.append(f"floor {ef}")
    if abs(eh["x"][0] - hb["x"][0]) > 0.5 or abs(eh["x"][1] - hb["x"][1]) > 0.5 or abs(eh["z"][1] - hb["top"]) > 0.1 \
            or abs(eh["y"][0] - hb["y"][0]) > 0.5 or abs(eh["y"][1] - hb["y"][1]) > 0.5 or h.get_attach_parent_actor() != s:
        bad.append(f"house {eh}")
    if bad:
        fail(f"read-back failed {bad} (NOT saved)")
    renamed = []
    for old, nu in RENAMES:
        hits = [a for a in sub.get_all_level_actors() if a.get_actor_label() == old]
        if len(hits) != 1 or any(a.get_actor_label() == nu for a in sub.get_all_level_actors()):
            fail(f"rename '{old}' -> '{nu}': {len(hits)} actors or target exists (NOT saved)")
        hits[0].set_actor_label(nu)
        if hits[0].get_actor_label() != nu:
            fail(f"rename read-back '{hits[0].get_actor_label()}' (NOT saved)")
        renamed.append(nu)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed (records NOT rewritten)")
    rewrote = {}
    for name in RENAME_RECORDS if RENAMES else ():
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        new = text
        for old, nu in RENAMES:
            new = new.replace(old, nu)
        if new != text:
            json.loads(new)
            open(path, "w", encoding="utf-8").write(new)
        rewrote[name] = sum(text.count(o) for o, _ in RENAMES)
    unreal.log(f"MOUTHFLOOR_OK|{MOUTH}|applied|renamed={renamed}|records={rewrote}|floor_x={[round(v, 1) for v in ef['x']]}|house_x={[round(v, 1) for v in eh['x']]}|house_top={round(eh['z'][1], 2)}"
               f"|material={mat.get_path_name() if mat else None}|backup={backup}|dirty_after={dirty()}")


main()
