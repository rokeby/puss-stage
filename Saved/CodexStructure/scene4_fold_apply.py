"""Key the Scene 4 hangar's fold (conductor, 29 Sep, after Gary: "does hangar part
also solve the rotation/hinge thing"). Additive and reversible: one new Level
Sequence, LS_S4_HangarFold, possessing the hangar's own tagged actors. The
practicals are attached to their walls so they fold with them, and the hinge
tags are rewritten to the verified angles. Saves the new sequence and the level
only; the Master is untouched.

The fold, packed -> standing (display rate 30 fps):
- 0-1 s: packed, near dark; only the ghost light burns.
- 1-4 s: floor slab 3 falls away from the camera, from standing across the
  path to flat. It's the reveal. Slabs 1 and 2 stay down: slab 1 would sweep
  over the camera, and the ghost light stands on slab 2.
- Side walls rise from lying outward: left 4-8 s, right 4.5-8.5 s.
- 8-12 s: the far wall rises, carrying the roof upright in line with it.
- 12.5-18.5 s: the roof swings 90 deg over the nave, last, once the path is
  under it.
- 18.5-22.5 s: the lattice flies in from 16 m above its working height.
- From 9 s: the practicals strike as a wave running away from the camera, one
  pair every 0.3 s, each ramping 0 -> 400 cd over 0.2 s.
- To 25 s: hold.

Rotation signs are NOT taken from the build-time tags: each packed pose is
chosen numerically. Walls must lie outside the nave, the far wall beyond it,
the roof upright in line with the far wall, and slab 3 standing, not buried.
Every swing is sampled, and the pass refuses if any corner enters the nave
interior or comes within 1 m of the camera. Swings are slow (22-30 deg/s,
15 deg/s for the roof), because Gary has complained of smearing on moving wings.

BLINK-style guards: world, no PIE, 0+0 dirty, no ZZ_ actors, the hangar
present (64 tagged), no fold sequence already. Revert record written before any
change. Dry run via S4_FOLD_DRY_RUN (scene4_fold_dryrun.py). Revert:
scene4_fold_revert.py. Lean: all work in main().
"""
import datetime
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"
SEQ_DIR, SEQ_NAME = "/Game/InfinityStage/RigAtmos", "LS_S4_HangarFold"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "scene4_fold_revert_record.json")
OUT = os.path.join(HERE, "scene4_fold_plan.json")
FPS = 30
# Docked late 29 Sep: the site is read from the Scene 4 Entry Handoff Camera (the
# mouth), as scene4_hangar_build.py builds it: nave 60 m along +X, 20 m wide.
CAMERA_LABEL = ("Scene 4", "Entry Handoff Camera")
NAVE_LEN, HALF_W, HEIGHT = 6000.0, 1000.0, 3000.0
LATTICE_RISE = 1600.0
TIMELINE = {  # hinge label: (start s, end s)
    "S4 Hangar Floor 3 Hinge": (1.0, 4.0),
    "S4 Hangar Left Wall Hinge": (4.0, 8.0),
    "S4 Hangar Right Wall Hinge": (4.5, 8.5),
    "S4 Hangar Far Wall Hinge": (8.0, 12.0),
    "S4 Hangar Roof Hinge": (12.5, 18.5),
    "S4 Hangar Lattice Fly": (18.5, 22.5),
}
END_S = 25.0
# Lit fold (Gary, 29 Sep): the practicals strike BEFORE the walls rise, so the lamps ride them up.
WAVE_START, WAVE_STEP, RAMP, PRACTICAL_CD = 2.0, 0.3, 0.2, 400.0


def fail(message):
    raise RuntimeError(f"S4_FOLD_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def rot_about(axis, deg):
    return unreal.Rotator(roll=deg if axis == "X" else 0.0, pitch=deg if axis == "Y" else 0.0, yaw=0.0)


def rotate(rot, v):
    return unreal.MathLibrary.transform_location(unreal.Transform(rotation=rot), v)


def corners(actor):
    """World corners of a mesh actor's oriented box, from its component bounds."""
    smc = actor.get_component_by_class(unreal.StaticMeshComponent)
    box = smc.get_editor_property("static_mesh").get_bounding_box()
    tf = actor.get_actor_transform()
    return [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
            for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]


def swing(points, pivot, rot):
    return [pivot + rotate(rot, p - pivot) for p in points]


def in_nave(p, nave, tol=5.0):
    lo, hi = nave
    return all(lo[i] + tol < p.to_tuple()[i] < hi[i] - tol for i in range(3))


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
    mine = {a.get_actor_label(): a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]}
    if len(mine) != 64:
        fail(f"expected the 64-actor hangar, found {len(mine)}")
    if unreal.EditorAssetLibrary.does_asset_exist(f"{SEQ_DIR}/{SEQ_NAME}"):
        fail("the fold sequence already exists; run scene4_fold_revert.py first")
    cams = [a for a in actors if all(k in a.get_actor_label() for k in CAMERA_LABEL)]
    if len(cams) != 1:
        fail(f"expected one Scene 4 Entry Handoff Camera, found {len(cams)}")
    cam = cams[0].get_actor_location()
    X0, X1, CY = cam.x, cam.x + NAVE_LEN, cam.y
    nave = ((X0, CY - HALF_W, 0.0), (X1, CY + HALF_W, HEIGHT))
    far = mine["S4 Hangar Far Wall Hinge"].get_actor_location()
    if abs(far.x - (X1 + 25.0)) > 5.0 or abs(far.y - CY) > 5.0:
        fail(f"the hangar is not docked at the handoff camera (far wall hinge at {far}); rebuild it there first")

    def children(hinge_label):
        h = mine[hinge_label]
        return [a for a in mine.values() if a.get_attach_parent_actor() == h and a.get_component_by_class(unreal.StaticMeshComponent)
                and a.get_component_by_class(unreal.StaticMeshComponent).get_editor_property("static_mesh")]

    # ---- Choose each packed pose numerically --------------------------------------
    chosen, report = {}, {}

    def check_swing(label, axis, packed, pts, pivot, packed_ok):
        bad = []
        for k in range(0, 11):
            r = rot_about(axis, packed * k / 10.0)
            moved = swing(pts, pivot, r)
            if k > 0 and any(in_nave(p, nave) for p in moved):
                bad.append(f"enters nave at {packed * k / 10.0:.0f} deg")
            if min((p - cam).length() for p in moved) < 100.0:
                bad.append(f"within 1 m of camera at {packed * k / 10.0:.0f} deg")
        if not packed_ok(swing(pts, pivot, rot_about(axis, packed))):
            bad.append("packed pose wrong")
        return bad

    def pick(label, axis, magnitude, packed_ok, pts=None, pivot=None):
        pivot = pivot or mine[label].get_actor_location()
        pts = pts or [p for c in children(label) for p in corners(c)]
        results = {}
        for sign in (1.0, -1.0):
            results[sign * magnitude] = check_swing(label, axis, sign * magnitude, pts, pivot, packed_ok)
        good = [a for a, bad in results.items() if not bad]
        report[label] = {"axis": axis, "candidates": {str(k): v for k, v in results.items()}}
        if len(good) != 1:
            fail(f"{label}: {len(good)} valid packed angles: {report[label]}")
        chosen[label] = (axis, good[0])

    pick("S4 Hangar Floor 3 Hinge", "Y", 90.0,
         lambda ps: min(p.z for p in ps) > -30.0 and max(p.x for p in ps) < X0 + 4000.0 + 60.0 and max(p.z for p in ps) > 1900.0)
    pick("S4 Hangar Left Wall Hinge", "X", 90.0,
         lambda ps: min(p.z for p in ps) > -60.0 and max(p.y for p in ps) < CY - 1000.0 + 30.0)
    pick("S4 Hangar Right Wall Hinge", "X", 90.0,
         lambda ps: min(p.z for p in ps) > -60.0 and min(p.y for p in ps) > CY + 1000.0 - 30.0)
    # The roof, relative to the STANDING far wall: upright in line with it.
    roof_pts = [p for c in children("S4 Hangar Roof Hinge") for p in corners(c)]
    pick("S4 Hangar Roof Hinge", "Y", 90.0,
         lambda ps: min(p.z for p in ps) > HEIGHT - 60.0 and min(p.x for p in ps) > X1 - 60.0,
         pts=roof_pts, pivot=mine["S4 Hangar Roof Hinge"].get_actor_location())
    # The far wall carries the upright roof: test both together.
    roof_axis, roof_packed = chosen["S4 Hangar Roof Hinge"]
    upright_roof = swing(roof_pts, mine["S4 Hangar Roof Hinge"].get_actor_location(), rot_about(roof_axis, roof_packed))
    far_pts = [p for c in children("S4 Hangar Far Wall Hinge") for p in corners(c)] + upright_roof
    pick("S4 Hangar Far Wall Hinge", "Y", 90.0,
         lambda ps: min(p.z for p in ps) > -60.0 and min(p.x for p in ps) > X1 - 30.0, pts=far_pts)

    # ---- Practicals: attach each body and lamp to its wall's hinge -----------------
    practicals = {}
    for label, a in mine.items():
        if label.startswith("S4 Practical "):
            side = label.split()[2][0]
            practicals[label] = "S4 Hangar Left Wall Hinge" if side == "L" else "S4 Hangar Right Wall Hinge"
    lamps = sorted((l for l in practicals if not l.endswith("Body")), key=lambda l: (mine[l].get_actor_location().x, l))
    if len(practicals) != 28 or len(lamps) != 14:
        fail(f"expected 14 practical lamps and 14 bodies, found {len(lamps)} and {len(practicals) - len(lamps)}")
    strike = {l: WAVE_START + (i // 2) * WAVE_STEP for i, l in enumerate(lamps)}

    tags_before = {l: [str(t) for t in mine[l].get_editor_property("tags")] for l in chosen}
    plan = {"chosen": {k: list(v) for k, v in chosen.items()}, "report": report, "strike_s": strike,
            "timeline": TIMELINE, "end_s": END_S, "lattice_rise_cm": LATTICE_RISE}
    json.dump(plan, open(OUT, "w"), indent=1)
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "sequence": f"{SEQ_DIR}/{SEQ_NAME}",
              "attached": practicals, "tags_before": tags_before}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if json.load(open(RECORD, encoding="utf-8"))["attached"] != practicals:
        fail("revert record did not read back")
    unreal.log(f"S4_FOLD_PLAN_OK|chosen={plan['chosen']}")
    if globals().get("S4_FOLD_DRY_RUN"):
        unreal.log("S4_FOLD_DRY_RUN_OK|mutated=0")
        return "dry"

    # ---- Mutate: attachments and tags --------------------------------------------
    for label, hinge_label in practicals.items():
        mine[label].attach_to_actor(mine[hinge_label], "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                                    unreal.AttachmentRule.KEEP_WORLD, False)
    for label, (axis, packed) in chosen.items():
        new = [t if not t.startswith("Hinge|") else
               "|".join([p if not p.startswith("closed=") else f"closed={packed:g}" for p in t.split("|")])
               for t in tags_before[label]]
        mine[label].set_editor_property("tags", new)

    # ---- The sequence ---------------------------------------------------------------
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = tools.create_asset(SEQ_NAME, SEQ_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if not seq:
        fail("sequence not created")
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    end = int(END_S * FPS)
    seq.set_playback_start(0)
    seq.set_playback_end(end)

    def key_transform(actor, channel_index, keys):
        binding = seq.add_possessable(actor)
        track = binding.add_track(unreal.MovieScene3DTransformTrack)
        section = track.add_section()
        section.set_range(0, end)
        chans = section.get_all_channels()
        parent = actor.get_attach_parent_actor()
        rel = (unreal.MathLibrary.inverse_transform_location(parent.get_actor_transform(), actor.get_actor_location())
               if parent else actor.get_actor_location())
        defaults = [rel.x, rel.y, rel.z, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        for i, ch in enumerate(chans[:9]):
            ch.set_default(defaults[i])
        for t_s, value in keys:
            chans[channel_index].add_key(unreal.FrameNumber(int(round(t_s * FPS))), value,
                                         time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                         interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
        return len(keys)

    keyed = 0
    for label, (axis, packed) in chosen.items():
        t0, t1 = TIMELINE[label]
        keyed += key_transform(mine[label], 3 if axis == "X" else 4, [(0.0, packed), (t0, packed), (t1, 0.0)])
    fly = mine["S4 Hangar Lattice Fly"]
    t0, t1 = TIMELINE["S4 Hangar Lattice Fly"]
    z = fly.get_actor_location().z
    keyed += key_transform(fly, 2, [(0.0, z + LATTICE_RISE), (t0, z + LATTICE_RISE), (t1, z)])
    for label in lamps:
        comp = mine[label].get_component_by_class(unreal.SpotLightComponent)
        binding = seq.add_possessable(comp)
        track = binding.add_track(unreal.MovieSceneFloatTrack)
        track.set_property_name_and_path("Intensity", "Intensity")
        section = track.add_section()
        section.set_range(0, end)
        ch = section.get_all_channels()[0]
        t = strike[label]
        for t_s, v in ((0.0, 0.0), (t, 0.0), (t + RAMP, PRACTICAL_CD)):
            ch.add_key(unreal.FrameNumber(int(round(t_s * FPS))), v, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                       interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        keyed += 3

    # ---- Rest the level at frame 0 (packed, lamps off) --------------------------------
    # Nested in the show, the fold starts from this pose, so there's nothing to snap:
    # P04's approach sees the packed hangar, and the Scene unfolds it.
    for label, (axis, packed) in chosen.items():
        mine[label].modify()
        mine[label].set_actor_relative_rotation(rot_about(axis, packed), False, True)
    fly.modify()
    fly.set_actor_location(unreal.Vector(fly.get_actor_location().x, fly.get_actor_location().y, z + LATTICE_RISE), False, True)
    for label in lamps:
        mine[label].modify()
        mine[label].get_component_by_class(unreal.SpotLightComponent).set_editor_property("intensity", 0.0)
    rest = {label: [round(v, 1) for v in (mine[label].get_actor_rotation().roll, mine[label].get_actor_rotation().pitch)]
            for label in chosen}
    rest_z = round(fly.get_actor_location().z, 1)
    if abs(rest_z - (z + LATTICE_RISE)) > 1.0:
        fail(f"lattice rest pose did not land: {rest_z}")
    record["rest_pose"] = {"packed": {k: list(v) for k, v in chosen.items()}, "lattice_standing_z": z,
                           "practical_cd": PRACTICAL_CD, "lamps": lamps}
    json.dump(record, open(RECORD, "w", encoding="utf-8"), indent=1)

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
    unreal.log(f"S4_FOLD_OK|keys={keyed}|hinges={len(chosen)}|lamps={len(lamps)}|attached={len(practicals)}|rest={rest}|lattice_z={rest_z}"
               f"|chosen={plan['chosen']}|saved=sequence+level|dirty_after={c2}+{m2}")
    return "applied"


result = main()
