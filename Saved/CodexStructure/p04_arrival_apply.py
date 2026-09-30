"""The P04 -> Scene 4 transition, the rise half (30 Sep; Gary: "that moment of moving through
is where we are already into the movement of the hangar folding upwards").

Needs patch G BUILT (AInfinityStageArrival). Two changes, one timing decision:
1. RE-KEY LS_S4_HangarRise's root pitch so the rise starts at NEGATIVE time, at the
   backcloth's release, and still lands at 16 s: keys -90 at RELEASE_S and 0 at 16 s,
   AUTO (flat ends). Every later beat (wave, uplights, roof, lattice, glow) is unchanged,
   and so is Look & camera's hosting. The release is derived, never typed: the camera
   crosses the cloth line at x CLOTH_X, walking 2.5 m/s to its stop at P04's route end,
   the Scene 4 boundary; the cloth releases LEAD_S before that crossing (Soft goods'
   "below 1.35 m at 2.7 s").
2. PLACE the Arrival: SceneCueGuid = Scene 4's cue, MotionSequence = LS_S4_HangarRise,
   MotionBindingGuid = the root's binding, DrivenActor = S4 Hangar Root. Before Scene 4's
   first frame it evaluates the same channel at negative time; after, Sequencer does.
Dry run (default) reports every derived number and the class check; nothing is written.
Apply (P04_ARRIVAL_APPLY): guards, plain record first, backups of the sequence and the
level, read-back, saves only those two. Revert: P04_ARRIVAL_REVERT restores the recorded
keys and deletes the Arrival. Lean: all work in main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE4 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
RISE = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "p04_arrival_record.json")
CLOTH_X, LEAD_S, LAND_S = 10450.0, 2.7, 16.0


def fail(msg):
    unreal.log_error("P04_ARRIVAL_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    apply, revert = bool(globals().get("P04_ARRIVAL_APPLY")), bool(globals().get("P04_ARRIVAL_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by_label = {a.get_actor_label(): a for a in actors}
    show = unreal.load_asset(SHOW)
    rate = show.get_editor_property("tick_resolution")
    rate = rate.numerator / rate.denominator
    # The Scene 4 cue: the one whose Scene sequence is LS_DevScene_04.
    scene_cue = None
    for c in show.get_editor_property("cues"):
        sq = c.get_editor_property("scene").get_editor_property("sequence")
        if sq and sq.get_path_name().split(".")[0] == SCENE4:
            scene_cue = c
    if scene_cue is None:
        fail("no Show cue plays LS_DevScene_04")
    # The camera's crossing, from the route: constant 2.5 m/s to the stop at the route end.
    p04 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 04"))
    route_len = p04.get_editor_property("route").get_spline_length()
    speed = 250.0
    cross_s = -(route_len - CLOTH_X) / speed
    release_s = cross_s - LEAD_S
    rise = unreal.load_asset(RISE)
    fps = rise.get_display_rate().numerator / rise.get_display_rate().denominator
    root = by_label["S4 Hangar Root"]
    binding = next(b for b in rise.get_bindings() if str(b.get_display_name()) == "S4 Hangar Root")
    track = next(t for t in binding.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack))
    sec = track.get_sections()[0]
    pitch = sec.get_all_channels()[4]
    keys_now = [(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value / fps, k.get_value()) for k in pitch.get_keys()]
    arrival_cls = getattr(unreal, "InfinityStageArrival", None)
    plan = {"scene_cue": str(scene_cue.get_editor_property("cue_guid").to_string()), "binding": binding.get_id().to_string(),
            "route_len_cm": route_len, "cross_s": round(cross_s, 3), "release_s": round(release_s, 3), "land_s": LAND_S,
            "rise_duration_s": round(LAND_S - release_s, 3), "keys_now": keys_now, "keys_new": [(round(release_s, 3), -90.0), (LAND_S, 0.0)],
            "arrival_class_loaded": arrival_cls is not None}
    unreal.log(f"P04_ARRIVAL_PLAN|{json.dumps(plan)}")
    if not (apply or revert):
        unreal.log("P04_ARRIVAL_DRY_RUN_OK|mutated=0")
        return
    if arrival_cls is None:
        fail("AInfinityStageArrival is not in the loaded binaries: build patch G first")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    f = lambda s: unreal.FrameNumber(int(round(s * fps)))
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        for k in list(pitch.get_keys()):
            pitch.remove_key(k)
        for t_s, v in rec["keys_before"]:
            pitch.add_key(f(t_s), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
        arr = by_label.get("S4 Arrival")
        if arr:
            sub.destroy_actor(arr)
    else:
        if "S4 Arrival" in by_label or os.path.exists(RECORD):
            fail("already applied (the Arrival or its record exists); revert first")
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": datetime.datetime.now().isoformat(timespec="seconds"), "keys_before": keys_now, "plan": plan}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreP04Arrival-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(os.path.join(project, "Content", *RISE[len("/Game/"):].split("/")) + ".uasset", backup)
        shutil.copy2(RECORD, backup)
        for k in list(pitch.get_keys()):
            pitch.remove_key(k)
        for t_s, v in ((release_s, -90.0), (LAND_S, 0.0)):
            pitch.add_key(f(t_s), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
        arr = sub.spawn_actor_from_class(arrival_cls, root.get_actor_location(), unreal.Rotator(0.0, 0.0, 0.0))
        arr.set_actor_label("S4 Arrival")
        arr.set_folder_path("Infinity Stage/Scene 04 Hangar")
        arr.set_editor_property("tags", [unreal.Name("RigAtmos.Scene4Hangar"), unreal.Name("RigAtmos.Arrival")])
        arr.set_editor_property("scene_cue_guid", scene_cue.get_editor_property("cue_guid"))
        arr.set_editor_property("motion_sequence", rise)
        arr.set_editor_property("motion_binding_guid", binding.get_id())
        arr.set_editor_property("driven_actor", root)
    got = [(round(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value / fps, 3), k.get_value()) for k in pitch.get_keys()]
    if not unreal.EditorAssetLibrary.save_asset(RISE, only_if_is_dirty=False):
        fail("sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    after = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"P04_ARRIVAL_OK|{'reverted' if revert else 'applied'}|keys={got}|dirty_after={after[0]}+{after[1]}")


main()
