"""The P04 backcloth's timeline, written once, read by two evaluators (30 Sep; needs patch G2 BUILT
and Soft goods' "P04 Backcloth (baked)" PLACED with bManualTick = true, running = true, looping = false).

Derives the cloth's release from the CROSSING, never from the box (Soft goods):
    cloth_release = T_cross(x CLOTH_X) - BACKCLOTH_LEAD_S          (Scene 4 time, negative)
    section_start = cloth_release - release_in_cache            (read from the bake, see below)
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
NO DEFAULTS FROM A DEAD BAKE (30 Sep). The old defaults (lead 2.70, release 1.0 s) were final8's, a
bake that was stopped: every precondition would still pass and the fall would simply be mistimed.
- The release time inside the cache is READ FROM THE ARTIFACT, never typed. The placed actor's
  cache names the Alembic it was imported from (Soft goods' import copies DropBake/<bake_id>.abc
  to DerivedAssets/.../<cache name>_<bake_id>.abc), and that bake's own DropBake/<bake_id>.json
  gives (release_frame - show_start) / 30 fps. Fallback: Soft goods' import_passing_bake.json, but
  only if it names THIS cache (that file is overwritten by every import). No artifact: refuse.
  RELEASE_IN_CACHE_S, if passed, is only a cross-check: refuse if it disagrees by more than a frame.
- BACKCLOTH_LEAD_S is REQUIRED (Soft goods' measured fall for THE placed bake). Apply refuses
  without it; the dry run names what is missing. Lean: main()."""
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
BACKCLOTH_LEAD_S = globals().get("BACKCLOTH_LEAD_S")
RELEASE_IN_CACHE_S = globals().get("RELEASE_IN_CACHE_S")     # optional cross-check only
SOFTGOODS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
BAKE_FPS = 30.0                                                # Soft goods' bake and plan rate


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


def release_from_artifact(cache):
    """(seconds from the cache's first sample to the release, where it was read), or (None, why).
    Reads Soft goods' files; writes nothing."""
    try:
        aid = cache.get_editor_property("asset_import_data")
        files = list(aid.extract_filenames()) if aid else []
    except Exception as exc:  # noqa: BLE001
        files, why = [], f"no import source ({exc})"
    else:
        why = "the cache names no import source"
    if files:
        stem = os.path.splitext(os.path.basename(files[0]))[0]
        prefix = cache.get_name() + "_"
        if stem.startswith(prefix):
            bake_json = os.path.join(SOFTGOODS, "DropBake", stem[len(prefix):] + ".json")
            if os.path.exists(bake_json):
                bake = json.load(open(bake_json, encoding="utf-8"))
                if bake.get("release_frame") is not None and bake.get("show_start") is not None:   # travellers carry None
                    return (int(bake["release_frame"]) - int(bake["show_start"])) / BAKE_FPS, os.path.relpath(bake_json, SOFTGOODS)
                why = f"{os.path.basename(bake_json)} has no release_frame/show_start (a bake with no release?)"
            else:
                why = f"no {os.path.basename(bake_json)}"
        else:
            why = f"import source {os.path.basename(files[0])} is not <{cache.get_name()}>_<bake_id>.abc"
    report = os.path.join(SOFTGOODS, "import_passing_bake.json")
    if os.path.exists(report):
        rep = json.load(open(report, encoding="utf-8"))
        if rep.get("ok") and rep.get("cfg", {}).get("gc_name") == cache.get_name() and "plan" in rep:
            return float(rep["plan"]["release_in_cache_s"]), "import_passing_bake.json"
        why += "; import_passing_bake.json does not name this cache"
    return None, why


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
    cache_asset = gcc.get_editor_property("geometry_cache") if gcc else None
    in_cache, in_cache_src = release_from_artifact(cache_asset) if cache_asset else (None, "no cache placed")
    disagree = (RELEASE_IN_CACHE_S is not None and in_cache is not None and abs(float(RELEASE_IN_CACHE_S) - in_cache) > 1.0 / BAKE_FPS)
    missing = [k for k, v in (("BACKCLOTH_LEAD_S", BACKCLOTH_LEAD_S), ("release time in the cache", in_cache)) if v is None]
    release_s = cross_s - float(BACKCLOTH_LEAD_S) if BACKCLOTH_LEAD_S is not None else None
    start_s = release_s - in_cache if release_s is not None and in_cache is not None else None
    duration = float(gcc.get_duration()) if gcc and gcc.get_editor_property("geometry_cache") else None
    plan = {"cloth_label": CLOTH_LABEL, "cache": gcc.get_editor_property("geometry_cache").get_path_name() if gcc and gcc.get_editor_property("geometry_cache") else None,
            "cross_s": round(cross_s, 4), "cloth_release_s": round(release_s, 4) if release_s is not None else None,
            "section_start_s": round(start_s, 4) if start_s is not None else None, "missing_required": missing,
            "duration_s": duration, "section_end_s": round(start_s + duration, 4) if duration and start_s is not None else None,
            "lead_s": BACKCLOTH_LEAD_S, "release_in_cache_s": in_cache, "release_in_cache_from": in_cache_src,
            "release_in_cache_passed": RELEASE_IN_CACHE_S, "release_disagrees": disagree, "checks": checks,
            "gc_track_class": hasattr(unreal, "MovieSceneGeometryCacheTrack"),
            "api": api_checks()}
    unreal.log(f"P04_CLOTH_PLAN|{json.dumps(plan)}")
    if not (apply or revert):
        unreal.log(f"P04_CLOTH_DRY_RUN_OK|mutated=0|missing_required={missing}")
        return
    if apply and (missing or disagree):
        fail(f"timing inputs: missing {missing} ({in_cache_src}); passed release {RELEASE_IN_CACHE_S} vs the bake's {in_cache}"
             f" disagrees={disagree}. No defaults by design.")
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
