"""Landscape block step 3 (30 Sep): the floors that replace the two (hidden) landscapes, top at z -5 like every other
passage floor plane (the Structure boards sit at 0 above them).
  P03: ONE flat plane over the Wet Ground's footprint, oak herringbone (P05's plane is a copy of P03's lost floor).
       NO pit-hole at S3, knowingly: six cast figures stand inside S3's swept footprint, and a hole would leave them
       hovering over an open pit. So S3's box still rises through the floor there, as it did through the terrain:
       a KNOWN FAULT left on purpose; the fix is a staging decision for Gary.
  P02: walnut herringbone (P01's), laid in S2's dock frame (yaw -43.57) around a pit-hole over S2's swept footprint
       (the builder's reach + 25 cm by +-(half_w + wall_t + 100 + 25)): Near (up to the hinge), Left, Right and Far
       pieces covering the rotated bounds of the old square, plus a black open-topped liner under the hole
       ("S2 Pit Liner ...", so the builder treats it as the hangar's own and never as a blocker).
Materials and collision are copied from the existing planes, not typed. Level actors tagged RigAtmos.LandscapeFloor
(the liner RigAtmos.PitLiner). Dry run (default). Apply (FLOORS_APPLY): record, Backups/PreLandscapeFloors-*, spawn,
read back each piece's transform, save the level. Revert (FLOORS_REVERT): destroy the recorded pieces. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "landscape_floors_record.json")
CUBE = "/Engine/BasicShapes/Cube.Cube"
STEEL = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
TOP, THICK, T, MARGIN = -5.0, 1.0, 20.0, 25.0


def fail(msg):
    unreal.log_error("FLOORS_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("FLOORS_APPLY")), bool(globals().get("FLOORS_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    scope = {L["label"]: L for L in json.load(open(os.path.join(HERE, "landscape_scope.json"), encoding="utf-8"))["landscapes"]}
    pieces = []            # (label, frame "world"|"s2", centre (u, v, z), size (du, dv, dz), yaw, source-plane label or "steel", tags)
    # P03: one axis-aligned plane over the Wet Ground's footprint.
    w3 = scope["Passage 3 - Wet Ground"]
    cx, cy = w3["centre"][0], w3["centre"][1]
    ex, ey = w3["extent_m"][0] * 100.0, w3["extent_m"][1] * 100.0
    pieces.append(("Passage 03 - Floor", (cx, cy, TOP - THICK / 2), (2 * ex, 2 * ey, THICK), 0.0, "Passage 05 - Floor (oak)", "RigAtmos.LandscapeFloor"))
    # P02: in S2's dock frame, around S2's pit-hole.
    cam = next(a for a in actors if a.get_actor_label().startswith("Scene 2 ") and "Entry Handoff Camera" in a.get_actor_label())
    yaw = cam.get_actor_rotation().yaw
    dock = unreal.Transform(location=unreal.Vector(cam.get_actor_location().x, cam.get_actor_location().y, 0.0), rotation=unreal.Rotator(0.0, 0.0, yaw))
    h2 = json.load(open(os.path.join(HERE, "hangar_s2_record.json"), encoding="utf-8"))["hangar"]
    reach = json.load(open(os.path.join(HERE, "hangar_s2_plan.json"), encoding="utf-8"))["reach_cm"]
    w2 = scope["Passage 1 - ForestedLandscape"]
    corners = [unreal.MathLibrary.inverse_transform_location(dock, unreal.Vector(w2["centre"][0] + sx * w2["extent_m"][0] * 100.0,
                                                                                w2["centre"][1] + sy * w2["extent_m"][1] * 100.0, 0.0))
               for sx in (-1, 1) for sy in (-1, 1)]
    u0, u1 = min(c.x for c in corners), max(c.x for c in corners)
    v0, v1 = min(c.y for c in corners), max(c.y for c in corners)
    hu0, hu1 = h2["apron"], h2["apron"] + reach + MARGIN
    hv = h2["half_w"] + h2["wall_t"] + 100.0 + MARGIN
    for name, (a0, a1), (b0, b1) in (("Near", (u0, hu0), (v0, v1)), ("Left", (hu0, u1), (v0, -hv)), ("Right", (hu0, u1), (hv, v1)),
                                     ("Far", (hu1, u1), (-hv, hv))):
        if a1 - a0 > 1.0 and b1 - b0 > 1.0:
            pieces.append((f"Passage 02 - Floor {name}", ((a0 + a1) / 2, (b0 + b1) / 2, TOP - THICK / 2), (a1 - a0, b1 - b0, THICK), yaw,
                           "Passage 01 - Opening Floor", "RigAtmos.LandscapeFloor"))
    z_top = TOP - THICK - 1.0
    z_floor = float(h2.get("hinge_z") or 0.0) - (h2["depth"] + h2["wall_t"]) - 250.0
    near = hu0 - MARGIN - 40.0
    for name, (a0, a1), (b0, b1), (c0, c1) in (("Floor", (hu0, hu1), (-hv, hv), (z_floor - T, z_floor)),
                                               ("Far Wall", (hu1, hu1 + T), (-hv - T, hv + T), (z_floor - T, z_top)),
                                               ("Left Wall", (near, hu1), (-hv - T, -hv), (z_floor - T, z_top)),
                                               ("Right Wall", (near, hu1), (hv, hv + T), (z_floor - T, z_top)),
                                               ("Near Wall", (near - T, near), (-hv - T, hv + T), (z_floor - T, z_top))):
        pieces.append((f"S2 Pit Liner {name}", ((a0 + a1) / 2, (b0 + b1) / 2, (c0 + c1) / 2), (a1 - a0, b1 - b0, c1 - c0), yaw, "steel", "RigAtmos.PitLiner"))
    plan = []
    for label, (u, v, z), size, pyaw, src, tag in pieces:
        loc = unreal.Vector(u, v, z) if label.startswith("Passage 03") else dock.transform_location(unreal.Vector(u, v, z))
        plan.append({"label": label, "loc": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)], "size": [round(s, 2) for s in size],
                     "yaw": round(pyaw, 4), "src": src, "tag": tag})
    unreal.log(f"FLOORS_PLAN|dock_yaw={yaw:.3f}|reach={reach}|hole_u=[{hu0},{hu1:.0f}] hole_v=+-{hv:.0f}|{json.dumps(plan)}")
    # LIP GUARD (30 Sep): no floor slab downstage of any stage-front lip (lip_guard.py); this builder laid four such.
    import runpy
    guard = runpy.run_path(os.path.join(HERE, "lip_guard.py"))
    lip_bad = guard["violations"](guard["mouth_frames"](actors), [p for p in plan if p["tag"] == "RigAtmos.LandscapeFloor"])
    unreal.log(f"FLOORS_LIP_GUARD|violations={lip_bad}")
    if lip_bad and (apply and not revert):
        fail(f"lip guard: {lip_bad}")
    if not (apply or revert):
        unreal.log("FLOORS_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() or any(l.startswith("ZZ_") for l in by):
        fail("Sequencer open or ZZ_ actors present")
    if revert:
        for label in json.load(open(RECORD, encoding="utf-8"))["spawned"]:
            if label in by:
                sub.destroy_actor(by[label])
        n_done = 0
    else:
        if os.path.exists(RECORD) or any(p["label"] in by for p in plan):
            fail("already applied; revert first")
        stamp = datetime.datetime.now()
        json.dump({"written": stamp.isoformat(timespec="seconds"), "spawned": [p["label"] for p in plan], "plan": plan},
                  open(RECORD, "w", encoding="utf-8"), indent=1)
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreLandscapeFloors-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
        cube, steel = unreal.load_asset(CUBE), unreal.load_asset(STEEL)
        for p in plan:
            a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*p["loc"]), unreal.Rotator(0.0, 0.0, p["yaw"]))
            a.set_actor_label(p["label"])
            a.set_folder_path("Infinity Stage/InfinityStage Passages" if p["tag"] == "RigAtmos.LandscapeFloor" else "Infinity Stage/Scene 02 Hangar")
            a.set_editor_property("tags", [unreal.Name(p["tag"])])
            smc = a.get_editor_property("static_mesh_component")
            if p["src"] == "steel":
                smc.set_static_mesh(cube)
                smc.set_material(0, steel)
            else:
                src = by[p["src"]].get_component_by_class(unreal.StaticMeshComponent)
                smc.set_static_mesh(src.get_editor_property("static_mesh"))
                smc.set_material(0, src.get_material(0))
                smc.set_collision_enabled(src.get_collision_enabled())
            a.set_actor_scale3d(unreal.Vector(p["size"][0] / 100.0, p["size"][1] / 100.0, p["size"][2] / 100.0))
            l, r, s = a.get_actor_location(), a.get_actor_rotation(), a.get_actor_scale3d()
            if (abs(l.x - p["loc"][0]) > 0.5 or abs(l.y - p["loc"][1]) > 0.5 or abs(l.z - p["loc"][2]) > 0.5
                    or abs(((r.yaw - p["yaw"]) + 180.0) % 360.0 - 180.0) > 0.01 or abs(s.x * 100.0 - p["size"][0]) > 0.5 or abs(s.y * 100.0 - p["size"][1]) > 0.5):
                fail(f"{p['label']} landed wrong (NOT saved)")
        n_done = len(plan)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    d = [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + [str(x.get_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"FLOORS_OK|{'reverted' if revert else 'applied'}|pieces={n_done}|dirty_after={d}")


main()
