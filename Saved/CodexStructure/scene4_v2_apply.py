"""Scene 4 v2 (Gary via the conductor, 29 Sep late: the WHOLE BOX hangs below the
passage floor, hinged at the mouth, and rotates up as one piece, ASSEMBLED and
dark except the ghost light inside. Then the lights strike, the roof swings over,
the lattice flies in. The walls' inward swing and the floor rise are dropped.
About a 15 s rise).

Level side:
- "S4 Hangar Root" (a mesh-less actor on the mouth's hinge line, axis Y) is
  created, and the hangar's top-level hinges (floors 1-3, walls, far wall,
  lattice fly) attach to it. Everything already nested rides along: the roof on
  the far wall, slabs, practicals, uplights, bulbs, and the ghost light on
  floor 2.
- The post-process volume stays world-fixed, so exposure is pinned during the
  rise as well.
- The internal pose becomes ASSEMBLED: floors and walls at 0; the roof upright
  over the far wall (relative -90); the lattice flown (+16 m); practicals and
  uplights at 0 cd; the ghost light on.
- The root rests HANGING at -90.

Sequence side: a NEW sequence, /Game/InfinityStage/RigAtmos/LS_S4_HangarRise
(30 fps, 31 s), keys the whole timeline. The old LS_S4_HangarFold is left
unreferenced once scene4_fold_nest.py re-points Scene 4 (FOLD_PATH):
  0-1     hold, hanging
  1-16    root -90 -> 0, eased (the rise)
  16.5+   practicals strike in pairs 0.3 s apart (ramp 0.2 s, 400 cd)
  18.0    uplights strike (18.0/18.15/18.3, to 10,000 cd)
  18.5-24.5  the roof swings over (-90 -> 0 relative to the far wall)
  24.5-28.5  the lattice flies in (z 2800 -> 1200, root-relative)
  -31     hold

Checks before any change (sampled over the swing, assembled geometry):
- no corner enters the passage (x < mouth - 25 cm; the floor slab's 20 cm
  underside is allowed for);
- no corner comes within 1 m of the camera;
- while hanging, nothing stands above the passage floor plane (z > +5 cm).
Also: no PIE, 0+0 dirty, no ZZ_ actors, Sequencer closed, no root yet.

The prior state is recorded as plain numbers (scene4_v2_record.json), for
scene4_v2_revert.py and level_verified_save.py. One save of the level and the
new sequence. Dry run: S4_V2_DRY_RUN. Lean: all work in main().
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG, ROOT_TAG = "RigAtmos.Scene4Hangar", "RigAtmos.Scene4Root"
SEQ_DIR, SEQ_NAME = "/Game/InfinityStage/RigAtmos", "LS_S4_HangarRise"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "scene4_v2_record.json")
FOLDER = "Infinity Stage/Scene 04 Hangar"
FPS, END_S = 30, 31.0
HANG = -90.0
# The lip (29 Sep late, with Look & camera): the Entry camera stands ON the mouth line, so
# the edge was at its feet (84-90 deg down) and no look-down could frame it. A fixed 5 m
# APRON slab now runs from the camera to the hinge, which moves 5 m ahead: the lip sits
# about 20 deg down, framed by a -15 deg look-down. The whole box translates +APRON via the
# root before it hangs; no geometry is rebuilt.
APRON_CM = 500.0
FLOOR_MAT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
HALF_W, FLOOR_T = 1000.0, 20.0
TOP = ("S4 Hangar Floor 1 Hinge", "S4 Hangar Floor 2 Hinge", "S4 Hangar Floor 3 Hinge", "S4 Hangar Left Wall Hinge",
       "S4 Hangar Right Wall Hinge", "S4 Hangar Far Wall Hinge", "S4 Hangar Lattice Fly")
HINGES = ("S4 Hangar Floor 1 Hinge", "S4 Hangar Floor 2 Hinge", "S4 Hangar Floor 3 Hinge", "S4 Hangar Left Wall Hinge",
          "S4 Hangar Right Wall Hinge", "S4 Hangar Far Wall Hinge", "S4 Hangar Roof Hinge")
ROOF_UPRIGHT = -90.0      # relative to the far wall: upright, in line with it (verified in the v1 sign pass)
LATTICE_Z, LATTICE_RISE = 1200.0, 1600.0
RISE = (1.0, 16.0)
ROOF = (18.5, 24.5)
LATTICE = (24.5, 28.5)
WAVE_START, WAVE_STEP, RAMP, PRACTICAL_CD = 16.5, 0.3, 0.2, 400.0
UPLIGHT_STRIKES, UPLIGHT_CD = (18.0, 18.15, 18.3), 10000.0


def fail(message):
    raise RuntimeError(f"S4_V2_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def rot_y(deg):
    return unreal.Rotator(roll=0.0, pitch=deg, yaw=0.0)


def swing(p, pivot, deg):
    return pivot + unreal.MathLibrary.transform_location(unreal.Transform(rotation=rot_y(deg)), p - pivot)


def rel_rot(actor):
    r = actor.root_component.get_editor_property("relative_rotation")
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE active")
    c0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c0 or m0:
        fail(f"editor already dirty: {c0} {m0}")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("a sequence is open in Sequencer")
    if unreal.EditorAssetLibrary.does_asset_exist(f"{SEQ_DIR}/{SEQ_NAME}") or os.path.exists(RECORD):
        fail("v2 already applied (sequence or record exists); run scene4_v2_revert.py first")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
        fail("bench actors in the level")
    mine = {a.get_actor_label(): a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]}
    if any(ROOT_TAG in [str(t) for t in a.get_editor_property("tags")] for a in mine.values()):
        fail("a hangar root already exists")
    tops = [l for l, a in mine.items() if a.get_attach_parent_actor() is None and not isinstance(a, unreal.PostProcessVolume)]
    if sorted(tops) != sorted(TOP):
        fail(f"unexpected top-level hangar actors: {sorted(tops)}")
    cams = [a for a in actors if "Scene 4" in a.get_actor_label() and "Entry Handoff Camera" in a.get_actor_label()]
    if len(cams) != 1:
        fail("Scene 4 Entry Handoff Camera not found")
    cam = cams[0].get_actor_location()
    x0, cy = cam.x, cam.y
    pivot = unreal.Vector(x0 + APRON_CM, cy, 0.0)        # the hinge: the apron's far edge

    # ---- Record the prior state (plain numbers) ------------------------------------
    lamps = sorted(l for l in mine if l.startswith("S4 Practical ") and not l.endswith("Body"))
    uplights = sorted(l for l in mine if l.startswith("S4 Uplight"))
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "mouth": [x0, cy],
              "before": {"rel_rot": {h: rel_rot(mine[h]) for h in HINGES},
                         "lattice_z": float(mine["S4 Hangar Lattice Fly"].get_actor_location().z),
                         "cd": {l: float(mine[l].get_component_by_class(unreal.LightComponent).get_editor_property("intensity"))
                                for l in lamps + uplights + ["S4 Ghost Light"]},
                         "ghost_parent": mine["S4 Ghost Light"].get_attach_parent_actor().get_actor_label()
                         if mine["S4 Ghost Light"].get_attach_parent_actor() else None},
              "rest": {"root": HANG, "internal": {h: 0.0 for h in HINGES if h != "S4 Hangar Roof Hinge"},
                       "roof": ROOF_UPRIGHT, "lattice_root_z": LATTICE_Z + LATTICE_RISE, "lamps": lamps, "uplights": uplights},
              "top": list(TOP), "sequence": f"{SEQ_DIR}/{SEQ_NAME}", "apron_cm": APRON_CM,
              "hinge": [pivot.x, pivot.y, pivot.z]}

    # ---- Arc checks on the ASSEMBLED geometry (computed, nothing moved yet) ----------
    def assembled_points():
        """World corners of every hangar mesh as it would sit ASSEMBLED (root level).
        Each mesh's world transform is recomposed from its attachment chain, with every
        hinge's relative rotation replaced by its assembled target (0; the roof -90
        upright) and the lattice fly lifted to its flown height."""
        pts = []
        for a in mine.values():
            smc = a.get_component_by_class(unreal.StaticMeshComponent)
            mesh = smc.get_editor_property("static_mesh") if smc else None
            if not mesh:
                continue
            chain, p = [], a
            while p is not None:
                chain.append(p)
                p = p.get_attach_parent_actor()
            # chain: [mesh actor, parent, ..., top-level]
            world = None
            for node in reversed(chain):
                label = node.get_actor_label()
                if node.get_attach_parent_actor() is None:
                    loc = node.get_actor_location()
                    if label == "S4 Hangar Lattice Fly":
                        loc = unreal.Vector(loc.x, loc.y, LATTICE_Z + LATTICE_RISE)
                    rot = rot_y(0.0) if label in HINGES or label == "S4 Hangar Lattice Fly" else node.get_actor_rotation()
                    world = unreal.Transform(location=loc, rotation=rot, scale=node.get_actor_scale3d())
                else:
                    rel = node.root_component.get_relative_transform()
                    if label in HINGES:
                        target = ROOF_UPRIGHT if label == "S4 Hangar Roof Hinge" else 0.0
                        rel = unreal.Transform(location=rel.translation, rotation=rot_y(target), scale=rel.scale3d)
                    world = unreal.MathLibrary.compose_transforms(rel, world)
            box = mesh.get_bounding_box()
            pts.extend(unreal.MathLibrary.transform_location(world, unreal.Vector(x, y, z))
                       for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z))
        return pts

    pts = [p + unreal.Vector(APRON_CM, 0.0, 0.0) for p in assembled_points()]   # the box sits APRON further out
    problems = []
    for k in range(0, 31):
        deg = HANG * (1.0 - k / 30.0)
        moved = [swing(p, pivot, deg) for p in pts]
        if min(p.x for p in moved) < pivot.x - 25.0:
            problems.append(f"crosses back over the apron at {deg:.0f} deg (x {min(p.x for p in moved) - pivot.x:.1f} cm)")
        if min((p - cam).length() for p in moved) < 100.0:
            problems.append(f"within 1 m of the camera at {deg:.0f} deg")
    hung = [swing(p, pivot, HANG) for p in pts]
    if max(p.z for p in hung) > 5.0:
        problems.append(f"hanging, something stands {max(p.z for p in hung):.1f} cm above the passage floor plane")
    if problems:
        fail(f"arc checks: {problems[:6]}")
    unreal.log(f"S4_V2_PLAN|points={len(pts)}|arcs=OK|mouth=({x0:.1f},{cy:.1f})|rise={RISE}|end={END_S}s")
    if globals().get("S4_V2_DRY_RUN"):
        unreal.log("S4_V2_DRY_RUN_OK|mutated=0")
        return "dry"
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())

    # ---- Level: assemble, create the root, attach, hang -------------------------------
    for h in HINGES:
        mine[h].modify()
        mine[h].set_actor_relative_rotation(rot_y(ROOF_UPRIGHT) if h == "S4 Hangar Roof Hinge" else rot_y(0.0), False, True)
    fly = mine["S4 Hangar Lattice Fly"]
    fly.modify()
    fl = fly.get_actor_location()
    fly.set_actor_location(unreal.Vector(fl.x, fl.y, LATTICE_Z + LATTICE_RISE), False, True)
    for l in lamps + uplights:
        mine[l].modify()
        mine[l].get_component_by_class(unreal.LightComponent).set_editor_property("intensity", 0.0)
    root = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x0, cy, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    root.get_editor_property("static_mesh_component").set_mobility(unreal.ComponentMobility.MOVABLE)
    root.set_actor_label("S4 Hangar Root")
    root.set_folder_path(FOLDER)
    root.set_editor_property("tags", [TAG, ROOT_TAG, f"Hinge|edge=mouth|axis=Y|closed={HANG:g}|open=0"])
    for l in TOP:
        mine[l].attach_to_actor(root, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                                unreal.AttachmentRule.KEEP_WORLD, False)
    root.set_actor_location(pivot, False, True)            # the whole box moves APRON further out
    # The apron: a fixed floor slab from the camera to the hinge, NOT on the root.
    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    apron = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x0 + APRON_CM / 2.0, cy, -FLOOR_T / 2.0),
                                       unreal.Rotator(0.0, 0.0, 0.0))
    asmc = apron.get_editor_property("static_mesh_component")
    asmc.set_static_mesh(cube)
    asmc.set_material(0, unreal.EditorAssetLibrary.load_asset(FLOOR_MAT))
    apron.set_actor_scale3d(unreal.Vector(APRON_CM / 100.0, 2.0 * HALF_W / 100.0, FLOOR_T / 100.0))
    apron.set_actor_label("S4 Hangar Apron")
    apron.set_folder_path(FOLDER)
    apron.set_editor_property("tags", [TAG, "RigAtmos.Scene4Apron"])
    # Keys need root-relative defaults, taken while the root is still level.
    defaults = {l: [float(v) for v in unreal.MathLibrary.inverse_transform_location(root.get_actor_transform(),
                                                                                    mine[l].get_actor_location()).to_tuple()]
                for l in ("S4 Hangar Lattice Fly",)}
    roof_rel = [float(v) for v in mine["S4 Hangar Roof Hinge"].root_component.get_editor_property("relative_location").to_tuple()]
    root.set_actor_relative_rotation(rot_y(HANG), False, True)

    # ---- The sequence -----------------------------------------------------------------
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = tools.create_asset(SEQ_NAME, SEQ_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if not seq:
        fail("sequence not created")
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    end = int(END_S * FPS)
    seq.set_playback_start(0)
    seq.set_playback_end(end)
    f = lambda s: unreal.FrameNumber(int(round(s * FPS)))

    def key_transform(actor, loc_defaults, channel, keys):
        b = seq.add_possessable(actor)
        tr = b.add_track(unreal.MovieScene3DTransformTrack)
        sec = tr.add_section()
        sec.set_range(0, end)
        ch = sec.get_all_channels()
        for i, d in enumerate(list(loc_defaults) + [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]):
            ch[i].set_default(float(d))
        for t_s, v in keys:
            ch[channel].add_key(f(t_s), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=unreal.MovieSceneKeyInterpolation.AUTO)

    def key_intensity(actor, keys):
        comp = actor.get_component_by_class(unreal.LightComponent)
        b = seq.add_possessable(comp)
        tr = b.add_track(unreal.MovieSceneFloatTrack)
        tr.set_property_name_and_path("Intensity", "Intensity")
        sec = tr.add_section()
        sec.set_range(0, end)
        ch = sec.get_all_channels()[0]
        for t_s, v in keys:
            ch.add_key(f(t_s), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                       interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)

    key_transform(root, [pivot.x, pivot.y, pivot.z], 4, [(0.0, HANG), (RISE[0], HANG), (RISE[1], 0.0)])
    key_transform(mine["S4 Hangar Roof Hinge"], roof_rel, 4, [(0.0, ROOF_UPRIGHT), (ROOF[0], ROOF_UPRIGHT), (ROOF[1], 0.0)])
    key_transform(fly, defaults["S4 Hangar Lattice Fly"], 2,
                  [(0.0, LATTICE_Z + LATTICE_RISE), (LATTICE[0], LATTICE_Z + LATTICE_RISE), (LATTICE[1], LATTICE_Z)])
    by_x = sorted(lamps, key=lambda l: (float(l.split()[2][1:]), l))                # L1,R1,L2,R2...: one pair per step
    for i, l in enumerate(by_x):
        t = WAVE_START + (i // 2) * WAVE_STEP
        key_intensity(mine[l], [(0.0, 0.0), (t, 0.0), (t + RAMP, PRACTICAL_CD)])
    for l, t in zip(uplights, UPLIGHT_STRIKES):
        key_intensity(mine[l], [(0.0, 0.0), (t, 0.0), (t + RAMP, UPLIGHT_CD)])

    # ---- Verify the rest pose landed, save ------------------------------------------
    got_root = rel_rot(root)[1]
    far_z = mine["S4 Hangar Far Wall Hinge"].get_actor_location().z
    if abs(got_root - HANG) > 0.05 or far_z > -5000.0 or abs(root.get_actor_location().x - pivot.x) > 0.5:
        fail(f"rest pose did not land: root pitch {got_root}, far wall hinge z {far_z:.0f}")
    c1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    m1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}
    if c1 - {f"{SEQ_DIR}/{SEQ_NAME}"} or m1 - {EXPECTED_WORLD}:
        fail(f"out-of-scope dirty: {sorted(c1)} {sorted(m1)}")
    if not unreal.EditorAssetLibrary.save_asset(f"{SEQ_DIR}/{SEQ_NAME}", only_if_is_dirty=False):
        fail("sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    c2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"S4_V2_OK|root_pitch={got_root}|far_wall_hinge_z={far_z:.0f}|lamps={len(lamps)}|uplights={len(uplights)}"
               f"|saved=sequence+level|dirty_after={c2}+{m2}")
    return "applied"


result = main()
