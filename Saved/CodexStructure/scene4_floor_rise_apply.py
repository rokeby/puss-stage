"""Build Gary's floor rise (29 Sep late; approved: "the floor of the hangar, where
the opening lamp sits, would itself fold upwards into view").

Floor slabs 2 (20-40 m, carrying the ghost light) and 3 (40-60 m) rest HANGING
from their existing near-edge hinges (pitch -90: far end below the floor plane,
top face toward the camera) and rise to flat:
- slab 2: 1.0-4.0 s, carrying the ghost light's stand, bulb and light (attached
  to its hinge);
- slab 3: 3.0-6.0 s (previously it fell away, +90 -> 0 over 1-4 s).
Everything else in LS_S4_HangarFold is untouched; Scene 4 stays 25 s, so no
Master rebuild.

Before any change:
- every corner of both slabs, and the ghost light, is sampled along its arc;
- it must stay at or below the floor plane (z <= +5 cm, the lamp excepted once
  near flat) and more than 1 m from the camera;
- the fold clip check must read OK.

Then it:
- records the prior state as plain numbers (scene4_floor_rise_record.json);
- updates scene4_fold_revert_record.json (rest pose and attachments), which
  level_verified_save.py and scene4_fold_revert.py read;
- rewrites the two hinges' closed= tags.
Saves the fold and the level. Dry run: FLOOR_RISE_DRY_RUN. Revert:
scene4_floor_rise_revert.py. Lean: all work in main().
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"
FOLD = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
FOLD_RECORD = os.path.join(HERE, "scene4_fold_revert_record.json")
RECORD = os.path.join(HERE, "scene4_floor_rise_record.json")
FPS = 30
HANG = -90.0
SLAB2, SLAB3 = "S4 Hangar Floor 2 Hinge", "S4 Hangar Floor 3 Hinge"
TIMES = {SLAB2: (1.0, 4.0), SLAB3: (3.0, 6.0)}
GHOST = ("S4 Ghost Light Stand", "S4 Ghost Light Bulb", "S4 Ghost Light")


def fail(message):
    raise RuntimeError(f"FLOOR_RISE_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def pitch_rot(deg):
    return unreal.Rotator(roll=0.0, pitch=deg, yaw=0.0)


def rotated(point, pivot, deg):
    return pivot + unreal.MathLibrary.transform_location(unreal.Transform(rotation=pitch_rot(deg)), point - pivot)


def box_corners(actor):
    smc = actor.get_component_by_class(unreal.StaticMeshComponent)
    box = smc.get_editor_property("static_mesh").get_bounding_box()
    tf = actor.get_actor_transform()
    return [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
            for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]


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
    if os.path.exists(RECORD):
        fail("the floor rise is already applied (record exists); run scene4_floor_rise_revert.py first")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
        fail("bench actors in the level")
    mine = {a.get_actor_label(): a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]}
    fold_rec = json.load(open(FOLD_RECORD, encoding="utf-8"))
    rest = fold_rec["rest_pose"]["packed"]
    if rest.get(SLAB3) != ["Y", 90.0] or SLAB2 in rest:
        fail(f"unexpected fold rest pose for the floor: {rest.get(SLAB3)} / {rest.get(SLAB2)}")
    h2, h3 = mine[SLAB2], mine[SLAB3]
    r2 = h2.root_component.get_editor_property("relative_rotation")
    r3 = h3.root_component.get_editor_property("relative_rotation")
    now = {SLAB2: float(r2.pitch), SLAB3: float(r3.pitch)}
    if abs(now[SLAB2]) > 0.05 or abs(now[SLAB3] - 90.0) > 0.05:
        fail(f"the floor hinges are not at their current rest (slab 2 0, slab 3 +90): {now}")
    if any(mine[g].get_attach_parent_actor() is not None for g in GHOST):
        fail("the ghost light is already attached")
    fold = unreal.EditorAssetLibrary.load_asset(FOLD)
    cam = next(a for a in actors if "Scene 4" in a.get_actor_label() and "Entry Handoff Camera" in a.get_actor_label())
    cam_loc = cam.get_actor_location()

    # ---- Check both arcs (from STANDING geometry: slab 3 is set flat for the sample) ----
    def slab_children(h):
        return [a for a in mine.values() if a.get_attach_parent_actor() == h
                and a.get_component_by_class(unreal.StaticMeshComponent)
                and a.get_component_by_class(unreal.StaticMeshComponent).get_editor_property("static_mesh")]

    problems = []
    pivot2, pivot3 = h2.get_actor_location(), h3.get_actor_location()
    slab2_pts = [p for c in slab_children(h2) for p in box_corners(c)]
    ghost_pts = [mine[g].get_actor_location() for g in GHOST] + [mine["S4 Ghost Light Bulb"].get_actor_location() + unreal.Vector(0, 0, 6.0)]
    # Slab 3's corners at its standing (flat) pose: un-rotate its current +90 rest.
    slab3_pts = [rotated(p, pivot3, -90.0) for c in slab_children(h3) for p in box_corners(c)]
    for label, pts, pivot, extra in ((SLAB2, slab2_pts, pivot2, ghost_pts), (SLAB3, slab3_pts, pivot3, [])):
        for k in range(0, 21):
            deg = HANG * (1.0 - k / 20.0)            # -90 -> 0
            moved = [rotated(p, pivot, deg) for p in pts]
            if max(p.z for p in moved) > 5.0:
                problems.append(f"{label} rises above the floor plane at {deg:.1f} deg")
            if min((p - cam_loc).length() for p in moved + [rotated(p, pivot, deg) for p in extra]) < 100.0:
                problems.append(f"{label} comes within 1 m of the camera at {deg:.1f} deg")
        hung = [rotated(p, pivot, HANG) for p in pts]
        if min(p.z for p in hung) > -1000.0:
            problems.append(f"{label} does not hang down at {HANG}")
    if problems:
        fail(f"arc checks: {problems[:5]}")

    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"),
              "before": {"rest": {SLAB2: 0.0, SLAB3: 90.0}, "slab3_keys": [[0.0, 90.0], [1.0, 90.0], [4.0, 0.0]],
                         "slab2_bound": False, "tags": {l: [str(t) for t in mine[l].get_editor_property("tags")] for l in (SLAB2, SLAB3)}},
              "after": {"rest": {SLAB2: HANG, SLAB3: HANG}, "times": TIMES, "ghost_on": SLAB2}}
    unreal.log(f"FLOOR_RISE_PLAN|arcs=OK|times={TIMES}|ghost_on={SLAB2}")
    if globals().get("FLOOR_RISE_DRY_RUN"):
        unreal.log("FLOOR_RISE_DRY_RUN_OK|mutated=0")
        return "dry"
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())

    # ---- Keys ------------------------------------------------------------------
    def pitch_channel(binding):
        for track in binding.get_tracks():
            if isinstance(track, unreal.MovieScene3DTransformTrack):
                return track.get_sections()[0].get_all_channels()[4]
        return None

    b3 = next((b for b in fold.get_bindings() if str(b.get_display_name()) == SLAB3), None)
    if b3 is None or pitch_channel(b3) is None:
        fail("slab 3's transform binding not found in the fold")
    ch3 = pitch_channel(b3)
    for k in list(ch3.get_keys()):
        ch3.remove_key(k)
    t0, t1 = TIMES[SLAB3]
    for t_s, v in ((0.0, HANG), (t0, HANG), (t1, 0.0)):
        ch3.add_key(unreal.FrameNumber(int(round(t_s * FPS))), v, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                    interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
    b2 = fold.add_possessable(h2)
    track = b2.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(0, int(round(fold.get_playback_end_seconds() * FPS)))
    chans = section.get_all_channels()
    loc = h2.get_actor_location()
    for i, d in enumerate((loc.x, loc.y, loc.z, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)):
        chans[i].set_default(float(d))
    t0, t1 = TIMES[SLAB2]
    for t_s, v in ((0.0, HANG), (t0, HANG), (t1, 0.0)):
        chans[4].add_key(unreal.FrameNumber(int(round(t_s * FPS))), v, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                         interpolation=unreal.MovieSceneKeyInterpolation.AUTO)

    # ---- Ghost light rides slab 2; both slabs rest hanging --------------------------
    for g in GHOST:
        mine[g].attach_to_actor(h2, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                                unreal.AttachmentRule.KEEP_WORLD, False)
    for h in (h2, h3):
        h.modify()
        h.set_actor_relative_rotation(pitch_rot(HANG), False, True)
        tags = [t if not t.startswith("Hinge|") else "|".join(
            [p if not p.startswith("closed=") else f"closed={HANG:g}" for p in t.split("|")]) for t in [str(x) for x in h.get_editor_property("tags")]]
        h.set_editor_property("tags", tags)
    got = {SLAB2: float(h2.root_component.get_editor_property("relative_rotation").pitch),
           SLAB3: float(h3.root_component.get_editor_property("relative_rotation").pitch)}
    if any(abs(v - HANG) > 0.05 for v in got.values()):
        fail(f"rest pose did not land: {got}")

    # The fold's own record: rest pose and attachments, which the verified save and fold revert read.
    fold_rec["rest_pose"]["packed"][SLAB2] = ["Y", HANG]
    fold_rec["rest_pose"]["packed"][SLAB3] = ["Y", HANG]
    for g in GHOST:
        fold_rec["attached"][g] = SLAB2
    with open(FOLD_RECORD, "w", encoding="utf-8") as fh:
        json.dump(fold_rec, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())

    c1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    m1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}
    if c1 - {FOLD} or m1 - {EXPECTED_WORLD}:
        fail(f"out-of-scope dirty: {sorted(c1)} {sorted(m1)}")
    if not unreal.EditorAssetLibrary.save_asset(FOLD, only_if_is_dirty=False):
        fail("fold save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    c2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"FLOOR_RISE_OK|rest={got}|ghost_attached={len(GHOST)}|saved=fold+level|dirty_after={c2}+{m2}")
    return "applied"


result = main()
