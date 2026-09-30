"""Build the Scene 4 hangar (Mechanism plan item 2; Gary, 29 Sep: "clear big rig spaces
for the Scene spaces with the sense of mechanism clearly established"). Approved by the
conductor under the standing delegation: additive only (no existing actor touched),
backed up (Backups/PreScene4Hangar-*), every actor tagged RigAtmos.Scene4Hangar, so
scene4_hangar_revert.py deletes it in one pass. Saves the level only.

Scene 4 is the narrow, tall one (Docs/SceneScaleAudit_2026-09-26.md): a nave 20 m
wide and 30 m tall. Since the late-29 Sep re-dock, the MOUTH sits on the Scene 4
Entry Handoff Camera (the end of Passage 04, where the show's camera really
stops) and the interior runs 60 m ahead of it along +X, y +-10 m, z 0 to 30 m.

Every surface is a HINGED FLAT, standing, not animated. It is an engine Cube attached
to a mesh-less hinge actor on its hinge line, so it can fold later without
re-authoring. Hinge actors carry a tag "Hinge|edge=..|axis=..|closed=..|open=0" (and
"Fly|axis=Z|closed=..|open=0" for the lattice). Walls fold OUTWARD; the roof rides the
far wall's hinge. The working lattice sits at 12 m, where a level 35 mm camera sees it
down the nave (the 30 m roof is above frame and closes the sky for Lumen).

Light: one ghost light (a stand and bulb, with a warm shadowed point light) and one
rank of 14 shadowless warm wall practicals. A post-process volume pins exposure,
because auto exposure would otherwise flatten the dark. The values are starting
points for Gary's eye.

Lean, to the crash rule: all work inside main().
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"
FOLDER = "Infinity Stage/Scene 04 Hangar"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "scene4_hangar_build.json")
# Docked 29 Sep late (Docs/Conductor/SCENE_DOCKING_AUDIT_2026-09-29.md; Gary: mouth
# at the arrival). The origin is read from the live "Scene 4 ... Entry Handoff
# Camera", which the Scene Handoff Builder regenerates from Passage 04's last
# frame, never typed. The mouth (X0) sits on the camera and the nave runs 60 m
# along its forward (+X). NAVE_LEN is the depth.
CAMERA_LABEL = ("Scene 4", "Entry Handoff Camera")
NAVE_LEN = 6000.0
HALF_W = 1000.0                          # interior half-width
HEIGHT = 3000.0
WALL_T = 50.0
FLOOR_T = 20.0
LATTICE_Z = 1200.0
CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
SPHERE = "/Engine/BasicShapes/Sphere.Sphere"
FLOOR_MAT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
# Plain black metal, not MI_Kit_SteelGroove: the kit material maps from per-instance
# custom data ([tone, X, Y, Z] cm on instanced meshes), which a plain cube can't carry.
STEEL_MAT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
PINNED_EV100 = 0.5                       # starting value for Gary's eye


def fail(message):
    raise RuntimeError(f"SCENE4_HANGAR_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE active")
    c0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c0 or m0:
        fail(f"editor already dirty: {c0} {m0}")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
        fail("bench actors in the level")
    if any(TAG in [str(t) for t in a.get_editor_property("tags")] for a in actors):
        fail("a Scene 4 hangar already exists; revert it first")
    cams = [a for a in actors if all(k in a.get_actor_label() for k in CAMERA_LABEL)]
    if len(cams) != 1:
        fail(f"expected one Scene 4 Entry Handoff Camera, found {[a.get_actor_label() for a in cams]}")
    cam_loc, cam_rot = cams[0].get_actor_location(), cams[0].get_actor_rotation()
    if abs(cam_rot.yaw) > 0.5 or abs(cam_rot.pitch) > 0.5 or abs(cam_rot.roll) > 0.5:
        fail(f"the dock camera is rotated {cam_rot}; this build assumes a pure translation along +X")
    CY = cam_loc.y
    X0, X1 = cam_loc.x, cam_loc.x + NAVE_LEN
    # Nothing may stand in the swept volume beyond the mouth: walls lying outward
    # (41 m to each side), the far wall and the roof lying in line (151 m ahead).
    lo = (X0 + 50.0, CY - HALF_W - 3200.0, -100.0)
    hi = (X1 + 3000.0 + 6100.0, CY + HALF_W + 3200.0, 3200.0)
    blockers = []
    for a in actors:
        if a in cams or "Handoff Camera" in a.get_actor_label():
            continue
        o, e = a.get_actor_bounds(False)
        if e.length() < 0.01 or e.x > 1e6:
            continue
        ot, et = o.to_tuple(), e.to_tuple()
        if all(ot[i] + et[i] >= lo[i] and ot[i] - et[i] <= hi[i] for i in range(3)):
            blockers.append(a.get_actor_label())
    if blockers:
        fail(f"the dock's swept volume is occupied: {blockers[:10]}")
    del actors
    cube = unreal.EditorAssetLibrary.load_asset(CUBE)
    cyl = unreal.EditorAssetLibrary.load_asset(CYL)
    sphere = unreal.EditorAssetLibrary.load_asset(SPHERE)
    floor_mat = unreal.EditorAssetLibrary.load_asset(FLOOR_MAT)
    steel = unreal.EditorAssetLibrary.load_asset(STEEL_MAT)
    if not all((cube, cyl, sphere, floor_mat, steel)):
        fail("an engine shape or material did not load")
    created = []

    def place(actor, label, tags):
        actor.set_actor_label(label)
        actor.set_folder_path(FOLDER)
        actor.set_editor_property("tags", [TAG] + tags)
        created.append(label)
        return actor

    def hinge(label, loc, tag):
        a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*loc), unreal.Rotator(0, 0, 0))
        a.get_editor_property("static_mesh_component").set_mobility(unreal.ComponentMobility.MOVABLE)
        return place(a, label, [tag])

    def slab(label, mesh, mat, centre, size_cm, parent=None, shadows=True):
        a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*centre), unreal.Rotator(0, 0, 0))
        smc = a.get_editor_property("static_mesh_component")
        smc.set_mobility(unreal.ComponentMobility.MOVABLE)
        smc.set_static_mesh(mesh)
        if mat:
            smc.set_material(0, mat)
        smc.set_cast_shadow(shadows)
        a.set_actor_scale3d(unreal.Vector(size_cm[0] / 100.0, size_cm[1] / 100.0, size_cm[2] / 100.0))
        if parent is not None:
            a.attach_to_actor(parent, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, False)
        return place(a, label, [])

    length = X1 - X0
    # Floor: three 20 m squares (uniform herringbone scale), each hinged at its near edge.
    for k in range(3):
        near = X0 + k * 2000.0
        h = hinge(f"S4 Hangar Floor {k + 1} Hinge", (near, CY, 0.0), "Hinge|edge=near|axis=Y|closed=90|open=0")
        slab(f"S4 Hangar Floor {k + 1}", cube, floor_mat, (near + 1000.0, CY, -FLOOR_T / 2), (2000.0, 2 * HALF_W, FLOOR_T), h)
    # Side walls, hinged along their bottom edge, folding outward.
    for side, sign, closed in (("Left", -1.0, -90), ("Right", 1.0, 90)):
        y = CY + sign * (HALF_W + WALL_T / 2)
        h = hinge(f"S4 Hangar {side} Wall Hinge", ((X0 + X1) / 2, y, 0.0), f"Hinge|edge=bottom|axis=X|closed={closed}|open=0")
        slab(f"S4 Hangar {side} Wall", cube, steel, ((X0 + X1) / 2, y, HEIGHT / 2), (length, WALL_T, HEIGHT), h)
    # Far wall, hinged along its bottom edge, folding away; the roof rides its top edge.
    far = hinge("S4 Hangar Far Wall Hinge", (X1 + WALL_T / 2, CY, 0.0), "Hinge|edge=bottom|axis=Y|closed=90|open=0")
    slab("S4 Hangar Far Wall", cube, steel, (X1 + WALL_T / 2, CY, HEIGHT / 2), (WALL_T, 2 * (HALF_W + WALL_T), HEIGHT), far)
    roof = hinge("S4 Hangar Roof Hinge", (X1 + WALL_T / 2, CY, HEIGHT), "Hinge|edge=far|axis=Y|closed=180|open=0|rides=S4 Hangar Far Wall Hinge")
    roof.attach_to_actor(far, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                         unreal.AttachmentRule.KEEP_WORLD, False)
    slab("S4 Hangar Roof", cube, steel, ((X0 + X1 + WALL_T) / 2, CY, HEIGHT + WALL_T / 2),
         (length + WALL_T, 2 * (HALF_W + WALL_T), WALL_T), roof)
    # The working lattice at 12 m: cross beams every 4 m and three rails on top. It can fly.
    fly = hinge("S4 Hangar Lattice Fly", ((X0 + X1) / 2, CY, LATTICE_Z), "Fly|axis=Z|closed=1800|open=0")
    beams = 0
    x = X0 + 400.0
    while x < X1 - 100.0:
        slab(f"S4 Hangar Lattice Beam {beams + 1:02d}", cube, steel, (x, CY, LATTICE_Z), (26.0, 2 * HALF_W, 34.0), fly, shadows=False)
        beams += 1
        x += 400.0
    for r, yoff in enumerate((-800.0, 0.0, 800.0)):
        slab(f"S4 Hangar Lattice Rail {r + 1}", cube, steel, ((X0 + X1) / 2, CY + yoff, LATTICE_Z + 34.0),
             (length, 26.0, 34.0), fly, shadows=False)

    # The ghost light: a stand and bulb off the cat's line, in the camera's view.
    gx, gy = X0 + 2500.0, CY - 400.0
    slab("S4 Ghost Light Stand", cyl, steel, (gx, gy, 90.0), (4.0, 4.0, 180.0), shadows=True)
    slab("S4 Ghost Light Bulb", sphere, None, (gx, gy, 188.0), (12.0, 12.0, 12.0), shadows=False)
    ghost = sub.spawn_actor_from_class(unreal.PointLight, unreal.Vector(gx, gy, 188.0), unreal.Rotator(0, 0, 0))
    lc = ghost.get_editor_property("point_light_component")
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    lc.set_editor_property("intensity", 60.0)
    lc.set_editor_property("attenuation_radius", 1500.0)
    lc.set_editor_property("use_temperature", True)
    lc.set_editor_property("temperature", 2600.0)
    lc.set_editor_property("cast_shadows", True)
    lc.set_editor_property("source_radius", 3.0)
    place(ghost, "S4 Ghost Light", ["Light|role=ghost"])

    # One rank of practicals on both walls at 7 m, every 8 m, aimed down and inward; shadowless.
    n = 0
    for side, sign in (("L", -1.0), ("R", 1.0)):
        for i in range(7):
            px = X0 + 1000.0 + i * 800.0
            wall_y = CY + sign * (HALF_W - 40.0)
            slab(f"S4 Practical {side}{i + 1} Body", cube, steel, (px, CY + sign * (HALF_W - 15.0), 700.0), (30.0, 30.0, 22.0), shadows=False)
            spot = sub.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(px, wall_y, 690.0),
                                              unreal.Rotator(roll=0.0, pitch=-35.0, yaw=-90.0 * sign))
            sc = spot.get_editor_property("spot_light_component")
            sc.set_mobility(unreal.ComponentMobility.MOVABLE)
            sc.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
            sc.set_editor_property("intensity", 400.0)
            sc.set_editor_property("attenuation_radius", 2500.0)
            sc.set_editor_property("use_temperature", True)
            sc.set_editor_property("temperature", 2900.0)
            sc.set_editor_property("inner_cone_angle", 30.0)
            sc.set_editor_property("outer_cone_angle", 55.0)
            sc.set_editor_property("cast_shadows", False)
            sc.set_editor_property("volumetric_scattering_intensity", 0.5)
            place(spot, f"S4 Practical {side}{i + 1}", ["Light|role=practical"])
            n += 1

    # Pinned exposure inside the hangar.
    ppv = sub.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector((X0 + X1) / 2, CY, HEIGHT / 2), unreal.Rotator(0, 0, 0))
    ppv.set_actor_scale3d(unreal.Vector((length + 200.0) / 200.0, (2 * HALF_W + 200.0) / 200.0, (HEIGHT + 200.0) / 200.0))
    ppv.set_editor_property("unbound", False)
    settings = ppv.get_editor_property("settings")
    settings.set_editor_property("override_auto_exposure_min_brightness", True)
    settings.set_editor_property("auto_exposure_min_brightness", PINNED_EV100)
    settings.set_editor_property("override_auto_exposure_max_brightness", True)
    settings.set_editor_property("auto_exposure_max_brightness", PINNED_EV100)
    # Local Exposure neutral: it's per-pixel and lifts a dark subject against a bright
    # ground, which would undo a near-dark arrival (conductor, 29 Sep, from the shaders).
    for name in ("local_exposure_highlight_contrast_scale", "local_exposure_shadow_contrast_scale"):
        try:
            settings.set_editor_property("override_" + name, True)
            settings.set_editor_property(name, 1.0)
        except Exception as exc:
            unreal.log_warning(f"SCENE4_HANGAR_LOCAL_EXPOSURE_NOT_SET|{name}|{exc}")
    ppv.set_editor_property("settings", settings)
    place(ppv, "S4 Hangar Pinned Exposure", ["PostProcess|exposure=pinned"])

    c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c1 or m1 != [EXPECTED_WORLD]:
        fail(f"unexpected dirty set: {c1} {m1} (created {len(created)}; revert with scene4_hangar_revert.py)")
    json.dump({"created": created, "beams": beams, "practicals": n, "mouth": [X0, CY], "far_wall_x": X1},
              open(OUT, "w"), indent=1)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    unreal.log(f"SCENE4_HANGAR_OK|actors={len(created)}|beams={beams}|practicals={n}|mouth=({X0:.1f},{CY:.1f})"
               f"|level_saved=1|tag={TAG}")
    return len(created)


result = main()
