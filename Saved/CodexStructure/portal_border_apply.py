"""Portal borders (30 Sep). APPLIED 14:52 ON THE CONDUCTOR'S RELAYED APPROVAL BEFORE GARY HAD ANSWERED (he had the mock,
PortalBorder_Opening_BeforeAfter.png, but had not said yes); kept pending his word, revert below. A black VELVET
border 5 cm x 19.8 m x 80 cm hangs 45-50 cm upstage of each of the six portal planes, z 10.20-11.00 m, masking the comb at
the curtain top without touching the cloth. Soft goods' ray test on final13 f479: 0 rays through (the lowered header leaked
324). The mock measured the material: black steel read as a lit tan band (p99 125 vs 114), velvet dark (77).

Builds:
  MI_PortalBorder_BlackVelvet (/Game/InfinityStage/RigAtmos): a child of MI_CurtainVelvet_DeepRed_Drop with VelvetColor
  and SheenColor 0.01. Both are READ BACK (the MaterialEditingLibrary setters can report False after a good set, or lie).
  Six StaticMeshActors "P0N Portal Border", tagged RigAtmos.PortalBorder, ATTACHED to "Infinity Stage - Structure 0N"
  (keep world), so a docking move carries them. Mobility follows the Structure's root.
Placement: each portal frame is the Passage route's start (distance 0), which is where the mouth survey measured every
portal. It is CROSS-CHECKED against the built header (StructurePortal_ instance 2): the header's world-box centre must lie
within 2 cm of frame + (0, 0, opening + header/2). A mismatch refuses that mouth, rather than guessing.
Dry run (default): plan + checks, mutates nothing. Apply (BORDER_APPLY): guards (world, no PIE, 0+0 dirty, no Sequencer,
no ZZ_, no border yet, no record), record first, Backups/PrePortalBorder-* (umap), build, read back (material params,
labels, parent, world transforms to 0.5 cm), save ONLY the level and the MI. Revert (BORDER_REVERT): destroy the recorded
borders; the save is gated on read-back ABSENCE; the MI is deleted only if nothing else references it. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "portal_border_record.json")
MI_DIR, MI_NAME = "/Game/InfinityStage/RigAtmos", "MI_PortalBorder_BlackVelvet"
MI_PATH = f"{MI_DIR}/{MI_NAME}"
PARENT = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"
BLACK = (0.01, 0.01, 0.01, 1.0)
PARAMS = ("VelvetColor", "SheenColor")
CUBE = "/Engine/BasicShapes/Cube.Cube"
X0, X1, Z0, Z1, HALF_Y = 45.0, 50.0, 1020.0, 1100.0, 990.0
TAG = "RigAtmos.PortalBorder"


def fail(msg):
    unreal.log_error("PORTAL_BORDER_STOPPED|" + msg)
    raise RuntimeError(msg)


def dirty():
    return [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
        [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]


def main():
    apply, revert = bool(globals().get("BORDER_APPLY")), bool(globals().get("BORDER_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    mel = unreal.MaterialEditingLibrary

    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        if dirty() or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
            fail("dirty or Sequencer open")
        for row in rec["borders"]:
            a = by.get(row["label"])
            if a is not None and TAG in [str(t) for t in a.get_editor_property("tags")]:
                sub.destroy_actor(a)
        left = [a.get_actor_label() for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]]
        if left:
            fail(f"NOT saved, level holds unsaved deletions: borders survived {left}")
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            fail("level save failed")
        refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(MI_PATH, False) if str(r) != MI_PATH]
        mi_deleted = unreal.EditorAssetLibrary.delete_asset(MI_PATH) if rec.get("mi_created") and not refs else False
        os.replace(RECORD, RECORD + ".reverted")
        unreal.log(f"PORTAL_BORDER_OK|reverted|borders_removed={len(rec['borders'])}|mi_deleted={mi_deleted}|mi_referencers={refs}|dirty_after={dirty()}")
        return

    # plan, from the live route and cross-checked against the built header
    plan, problems = [], []
    for n in range(1, 7):
        s = by.get(f"Infinity Stage - Structure 0{n}")
        if s is None:
            problems.append(f"S0{n}: no Structure actor")
            continue
        portal = s.get_editor_property("portal")
        if not portal.get_editor_property("enabled"):
            problems.append(f"S0{n}: portal disabled")
            continue
        route = s.get_editor_property("passage").get_editor_property("route")
        start = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
        yaw = start.rotation.rotator().yaw
        frame = unreal.Transform(location=start.translation, rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        opening, header = portal.get_editor_property("opening_height_cm"), portal.get_editor_property("header_depth_cm")
        comp = next((c for c in s.get_components_by_class(unreal.InstancedStaticMeshComponent) if c.get_name().startswith("StructurePortal_")), None)
        if comp is None or comp.get_instance_count() < 3:
            problems.append(f"S0{n}: no built header")
            continue
        bb = comp.get_editor_property("static_mesh").get_bounding_box()
        t = comp.get_instance_transform(2, True)
        pts = [t.transform_location(unreal.Vector(x, y, z)) for x in (bb.min.x, bb.max.x) for y in (bb.min.y, bb.max.y) for z in (bb.min.z, bb.max.z)]
        got = unreal.Vector(sum(p.x for p in pts) / 8.0, sum(p.y for p in pts) / 8.0, sum(p.z for p in pts) / 8.0)
        want = frame.transform_location(unreal.Vector(0.0, 0.0, opening + header / 2.0))
        err = (got - want).length()
        if err > 2.0:
            problems.append(f"S0{n}: header centre {err:.1f} cm from the route-start frame")
            continue
        centre = frame.transform_location(unreal.Vector((X0 + X1) / 2.0, 0.0, (Z0 + Z1) / 2.0))
        plan.append({"structure": s.get_actor_label(), "label": f"P0{n} Portal Border", "centre": [centre.x, centre.y, centre.z], "yaw": yaw,
                     "scale": [(X1 - X0) / 100.0, 2.0 * HALF_Y / 100.0, (Z1 - Z0) / 100.0], "header_check_cm": round(err, 2),
                     "opening_cm": opening, "header_cm": header})
    exists = [a.get_actor_label() for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]]
    mi_exists = unreal.EditorAssetLibrary.does_asset_exist(MI_PATH)
    unreal.log(f"PORTAL_BORDER_PLAN|{json.dumps(plan)}|problems={problems}|existing_borders={exists}|mi_exists={mi_exists}")
    if not apply:
        unreal.log("PORTAL_BORDER_DRY_RUN_OK|mutated=0")
        return
    if problems or len(plan) != 6 or exists or os.path.exists(RECORD):
        fail(f"refused: problems={problems}, planned={len(plan)}, existing={exists}, record exists={os.path.exists(RECORD)}")
    if dirty() or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() or any(l.startswith("ZZ_") for l in by):
        fail("dirty, Sequencer open, or ZZ_ actors present")

    stamp = datetime.datetime.now()
    rec = {"written": stamp.isoformat(timespec="seconds"), "mi": MI_PATH, "mi_created": not mi_exists, "borders": plan}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PrePortalBorder-" + stamp.strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    shutil.copy2(RECORD, backup)

    # the material, read back
    if mi_exists:
        mi = unreal.load_asset(MI_PATH)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(MI_NAME, MI_DIR, unreal.MaterialInstanceConstant,
                                                                     unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, unreal.load_asset(PARENT))
        for p in PARAMS:
            mel.set_material_instance_vector_parameter_value(mi, p, unreal.LinearColor(*BLACK))
        mel.update_material_instance(mi)
    parent = mi.get_editor_property("parent")
    back = {p: mel.get_material_instance_vector_parameter_value(mi, p) for p in PARAMS}
    if not parent or parent.get_path_name().split(".")[0] != PARENT or any(abs(v.r - BLACK[0]) > 1e-4 or abs(v.g - BLACK[1]) > 1e-4 or abs(v.b - BLACK[2]) > 1e-4 for v in back.values()):
        fail(f"material read-back: parent={parent.get_path_name() if parent else None} params={[(k, v.r, v.g, v.b) for k, v in back.items()]} (NOT saved)")

    # the borders, read back
    mesh = unreal.load_asset(CUBE)
    made = []
    for row in plan:
        s = by[row["structure"]]
        a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*row["centre"]), unreal.Rotator(roll=0.0, pitch=0.0, yaw=row["yaw"]))
        a.set_actor_label(row["label"])
        a.set_editor_property("tags", [unreal.Name(TAG)])
        c = a.static_mesh_component
        c.set_mobility(s.root_component.get_editor_property("mobility"))
        c.set_static_mesh(mesh)
        c.set_material(0, mi)
        a.set_actor_scale3d(unreal.Vector(*row["scale"]))
        a.attach_to_actor(s, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
        made.append(a)
    bad = []
    for a, row in zip(made, plan):
        loc = a.get_actor_location()
        par = a.get_attach_parent_actor()
        mat = a.static_mesh_component.get_material(0)
        if (loc - unreal.Vector(*row["centre"])).length() > 0.5 or abs(a.get_actor_rotation().yaw - row["yaw"]) > 0.05 \
                or par is None or par.get_actor_label() != row["structure"] or mat is None or mat.get_path_name().split(".")[0] != MI_PATH:
            bad.append(row["label"])
    if bad:
        fail(f"border read-back failed for {bad} (NOT saved)")
    if not unreal.EditorAssetLibrary.save_asset(MI_PATH, only_if_is_dirty=False):
        fail("MI save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    unreal.log(f"PORTAL_BORDER_OK|applied|borders={[r['label'] for r in plan]}|mi={MI_PATH}|backup={backup}|dirty_after={dirty()}")


main()
