"""The P04 backcloth's timeline, written once, read by two evaluators (30 Sep; needs patch G2 BUILT
and Soft goods' "P04 Backcloth (baked)" PLACED with bManualTick = true, running = true, looping = false).

Derives the cloth's release from the CROSSING, never from the box (Soft goods):
    cloth_release = T_cross(x CLOTH_X) - BACKCLOTH_LEAD_S          (Scene 4 time, negative)
    section_start = cloth_release - RELEASE_IN_CACHE_S             (the bake's release is 1.0 s in)
    section_end   = section_start + the component's own GetDuration()   (exactly, or it loops)
T_cross comes from P04's route: the camera walks a constant 2.5 m/s to its dead stop at the route
end, Scene 4's first frame (the compiler's distance is piecewise-linear; verified 30 Sep).

Writes into LS_S4_HangarRise: a possessable binding for the backcloth actor, ONE GeometryCache track
with ONE section [section_start, section_end), the actor's cache, offsets 0, play rate 1, not
reversed, completion KeepState. Sets S4 Arrival's BackclothActor and BackclothBindingGuid.
Sequencer plays the section from Scene 4's first frame; the Arrival plays it before (G2).
Dry run (default): every derived number and every precondition, nothing written. Apply
(P04_CLOTH_APPLY): guards, plain record, backups of the sequence and the level, read-back, saves
those two. Revert: P04_CLOTH_REVERT removes the binding and clears the Arrival's two properties.
Parameters: BACKCLOTH_LEAD_S (Soft goods sends it from final8's measured fall). Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RISE = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "p04_backcloth_section_record.json")
# The actor's label is the only name used: the cache is whatever the placed actor carries (final11_a06
# or whichever bake passes), and the section's length is that component's own duration.
CLOTH_LABEL = globals().get("CLOTH_LABEL", "P04 Backcloth (baked)")
CLOTH_X, SPEED = 10450.0, 250.0
BACKCLOTH_LEAD_S = float(globals().get("BACKCLOTH_LEAD_S", 2.70))
RELEASE_IN_CACHE_S = float(globals().get("RELEASE_IN_CACHE_S", 1.0))


def fail(msg):
    unreal.log_error("P04_CLOTH_STOPPED|" + msg)
    raise RuntimeError(msg)


def api_checks():
    """Every Python API the apply path uses, probed without writing: a throwaway params struct and
    eval-options struct, and the section range setter's existence."""
    out = {"set_range_seconds": hasattr(unreal.MovieSceneSection, "set_range_seconds"),
           "get_start_frame_seconds": hasattr(unreal.MovieSceneSection, "get_start_frame_seconds")}
    try:
        p = unreal.MovieSceneGeometryCacheParams()
        p.set_editor_property("play_rate", 1.0)
        p.get_editor_property("geometry_cache_asset")
        out["gc_params"] = True
    except Exception as exc:
        out["gc_params"] = f"FAIL {exc}"
    try:
        ev = unreal.MovieSceneSectionEvalOptions()
        ev.set_editor_property("completion_mode", unreal.MovieSceneCompletionMode.KEEP_STATE)
        out["eval_options"] = True
    except Exception as exc:
        out["eval_options"] = f"FAIL {exc}"
    return out


def main():
    apply, revert = bool(globals().get("P04_CLOTH_APPLY")), bool(globals().get("P04_CLOTH_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by_label = {a.get_actor_label(): a for a in actors}
    arrival = by_label.get("S4 Arrival")
    checks = {"arrival_placed": arrival is not None,
              "g2_built": arrival is not None and hasattr(arrival, "resolve_backcloth_time_at_master_frame"),
              "cloth_placed": CLOTH_LABEL in by_label}
    cloth = by_label.get(CLOTH_LABEL)
    gcc = cloth.get_component_by_class(unreal.GeometryCacheComponent) if cloth else None
    if gcc:
        checks.update({"manual_tick": bool(gcc.get_editor_property("manual_tick")), "running": bool(gcc.get_editor_property("running")),
                       "looping": bool(gcc.get_editor_property("looping")), "cache": bool(gcc.get_editor_property("geometry_cache"))})
    p04 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 04"))
    route_len = p04.get_editor_property("route").get_spline_length()
    cross_s = -(route_len - CLOTH_X) / SPEED
    release_s = cross_s - BACKCLOTH_LEAD_S
    start_s = release_s - RELEASE_IN_CACHE_S
    duration = float(gcc.get_duration()) if gcc and gcc.get_editor_property("geometry_cache") else None
    plan = {"cloth_label": CLOTH_LABEL, "cache": gcc.get_editor_property("geometry_cache").get_path_name() if gcc and gcc.get_editor_property("geometry_cache") else None,
            "cross_s": round(cross_s, 4), "cloth_release_s": round(release_s, 4), "section_start_s": round(start_s, 4),
            "duration_s": duration, "section_end_s": round(start_s + duration, 4) if duration else None,
            "lead_s": BACKCLOTH_LEAD_S, "release_in_cache_s": RELEASE_IN_CACHE_S, "checks": checks,
            "gc_track_class": hasattr(unreal, "MovieSceneGeometryCacheTrack"),
            "api": api_checks()}
    unreal.log(f"P04_CLOTH_PLAN|{json.dumps(plan)}")
    if not (apply or revert):
        unreal.log("P04_CLOTH_DRY_RUN_OK|mutated=0")
        return
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    rise = unreal.load_asset(RISE)
    fps = rise.get_display_rate().numerator / rise.get_display_rate().denominator
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        for b in list(rise.get_bindings()):
            if b.get_id().to_string() == rec["binding"]:
                b.remove()
        arrival.set_editor_property("backcloth_actor", None)
        arrival.set_editor_property("backcloth_binding_guid", unreal.Guid())
    else:
        missing = [k for k in ("arrival_placed", "g2_built", "cloth_placed", "manual_tick", "running", "cache") if not checks.get(k)]
        if missing or checks.get("looping"):
            fail(f"preconditions: missing {missing}, looping={checks.get('looping')}")
        if os.path.exists(RECORD):
            fail("already applied (record exists); revert first")
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreP04BackclothSection-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(os.path.join(project, "Content", *RISE[len("/Game/"):].split("/")) + ".uasset", backup)
        binding = rise.add_possessable(cloth)
        track = binding.add_track(unreal.MovieSceneGeometryCacheTrack)
        sec = track.add_section()
        params = sec.get_editor_property("params")
        params.set_editor_property("geometry_cache_asset", gcc.get_editor_property("geometry_cache"))
        params.set_editor_property("play_rate", 1.0)
        sec.set_editor_property("params", params)
        # Section range in the sequence's TICK resolution, so the end is exactly start + duration.
        sec.set_range_seconds(start_s, start_s + duration)
        ev = sec.get_editor_property("eval_options")
        ev.set_editor_property("completion_mode", unreal.MovieSceneCompletionMode.KEEP_STATE)
        sec.set_editor_property("eval_options", ev)
        arrival.set_editor_property("backcloth_actor", cloth)
        arrival.set_editor_property("backcloth_binding_guid", binding.get_id())
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": datetime.datetime.now().isoformat(timespec="seconds"), "binding": binding.get_id().to_string(), "plan": plan}, fh, indent=1)
        got = (sec.get_start_frame_seconds(), sec.get_end_frame_seconds())
        if abs(got[0] - start_s) > 1.0 / fps or abs((got[1] - got[0]) - duration) > 1.0 / fps:
            fail(f"section landed at {got}, wanted [{start_s:.4f}, {start_s + duration:.4f}] (NOT saved)")
    if not unreal.EditorAssetLibrary.save_asset(RISE, only_if_is_dirty=False):
        fail("sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    unreal.log(f"P04_CLOTH_OK|{'reverted' if revert else 'applied'}|plan={json.dumps(plan)}")


main()
