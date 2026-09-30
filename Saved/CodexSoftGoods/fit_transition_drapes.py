"""Fit the transition curtain to each Interaction's CURRENT length (29 Sep plan; see Docs/ChaosClothCurtain.md
"transition curtain, RE-SIZED"). Gary: the Interaction happens ON the curtain, which falls at the end. Lengths are his
and will keep changing, so this is IDEMPOTENT and derives everything:
  the drape       GC_CurtainDrop_Opening, spawnable "Transition Drape (baked)", placed at Passage N+1's MOUTH (its
                  route start, yaw from the route's start tangent, on the floor). The cache is world-true for P01's
                  mouth at the origin, facing +X.
  sections        HOLD [0, end - lead) loops the cache's first frame, so a long hang costs nothing.
                  FALL [end - lead, end) plays the release (1 s in) and the landing.
  camera cut      [0, end) to Look & camera's level camera tagged InfinityStage.TransitionStalls + InfinityStage.Mouth.P0{N+1}.
  old rig         the fire-safety rig's bCurtainActive is keyed False (kept, not deleted: tests still count it until the
                  SavedFixturePIE Interaction block is rewritten in the same build).
Mode from fit_transition_drapes_mode.json: {"dry_run": true, "lead_s": 5.0, "interactions": [1,2,3,4,5]}.
DRY RUN (default) reads and reports the plan: transforms, frames, camera found or not. It writes nothing.
APPLY: no PIE; nothing dirty; exactly one camera per mouth. Backs up the five .uassets to
Backups/PreTransitionDrapes-<ts>/ (the revert is to restore them). Saves ONLY those sequences.
Run after Gary changes an Interaction's length, then the guarded Master rebuild. Crash rules: all inside main().
"""
import datetime
import json
import math
import os
import shutil

import unreal

SEQ_DIR = "/Game/InfinityStage/Interactions"
SEQS = {1: "LS_Interaction_01_WashingTheBoy", 2: "LS_Interaction_02_Turnips", 3: "LS_Interaction_03_ForgetsHisName",
        4: "LS_Interaction_04_GetsAName", 5: "LS_Interaction_05_BecomesKing"}
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
DRAPE = "Transition Drape (baked)"
RIG = "Curtain Rig - Fire Safety Curtain"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def mouth_of(actors, passage_number):
    label = f"Passage {passage_number:02d} — Fixed Wings"
    hits = [a for a in actors if a.get_actor_label() == label]
    if len(hits) != 1:
        return None, f"expected one '{label}', found {len(hits)}"
    passage = hits[0]
    route = passage.get_editor_property("route")
    if route:
        loc = route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
        tan = route.get_tangent_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
        yaw = math.degrees(math.atan2(tan.y, tan.x))
    else:
        loc, yaw = passage.get_actor_location(), passage.get_actor_rotation().yaw
    floor_z = passage.get_actor_location().z
    return {"x": round(loc.x, 2), "y": round(loc.y, 2), "z": round(floor_z, 2), "yaw": round(yaw, 3)}, None


def camera_for(actors, passage_number):
    tag = f"InfinityStage.Mouth.P{passage_number:02d}"
    hits = [a for a in actors if a.actor_has_tag("InfinityStage.TransitionStalls") and a.actor_has_tag(tag)]
    return hits


def plan_for(seq, lead_s):
    rate = seq.get_display_rate()
    fps = rate.numerator / rate.denominator
    end = seq.get_playback_end()
    lead = int(round(lead_s * fps))
    return {"fps": fps, "end": end, "fall_start": max(0, end - lead), "length_s": round(end / fps, 3)}


def apply_one(seq, mouth, camera, plan, report_row):
    cache = unreal.load_asset(GC)
    tick = seq.get_tick_resolution()
    one = int(round((tick.numerator / tick.denominator) / plan["fps"]))
    dur_ticks = int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / 30.0
                          * tick.numerator / tick.denominator))
    drape = next((b for b in seq.get_bindings() if str(b.get_display_name()) == DRAPE), None)
    if drape is None:
        drape = seq.add_spawnable_from_class(unreal.GeometryCacheActor)
        drape.set_display_name(DRAPE)
    tmpl = drape.get_object_template()
    tmpl.set_actor_location(unreal.Vector(mouth["x"], mouth["y"], mouth["z"]), False, False)
    tmpl.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=mouth["yaw"]), False)
    comp = tmpl.get_editor_property("geometry_cache_component")
    comp.set_editor_property("geometry_cache", cache)
    comp.set_editor_property("running", True)       # running=False freezes the track on frame 0 (29 Sep)
    comp.set_editor_property("looping", False)
    for t in list(drape.get_tracks()):
        if t.get_class().get_name() in ("MovieSceneGeometryCacheTrack", "MovieSceneSpawnTrack"):
            drape.remove_track(t)
    st = drape.add_track(unreal.MovieSceneSpawnTrack)
    ss = st.add_section()
    ss.set_range(0, plan["end"])
    ch = ss.get_all_channels()[0]
    ch.set_default(True)
    ch.add_key(unreal.FrameNumber(0), True)
    gt = drape.add_track(unreal.MovieSceneGeometryCacheTrack)
    for name, a, b, start_off, end_off in (("HOLD", 0, plan["fall_start"], 0, dur_ticks - one),
                                          ("FALL", plan["fall_start"], plan["end"], 0, 0)):
        if b <= a:
            continue
        s = gt.add_section()
        s.set_range(a, b)
        p = s.get_editor_property("params")
        p.set_editor_property("geometry_cache_asset", cache)
        p.set_editor_property("start_frame_offset", unreal.FrameNumber(start_off))
        p.set_editor_property("end_frame_offset", unreal.FrameNumber(end_off))
        s.set_editor_property("params", p)
    cam_binding = next((b for b in seq.get_bindings() if str(b.get_display_name()) == camera.get_actor_label()), None)
    if cam_binding is None:
        cam_binding = seq.add_possessable(camera)
        cam_binding.set_display_name(camera.get_actor_label())
    cuts = [t for t in seq.get_tracks() if t.get_class().get_name() == "MovieSceneCameraCutTrack"]
    cut_track = cuts[0] if cuts else seq.add_track(unreal.MovieSceneCameraCutTrack)
    for s in list(cut_track.get_sections()):
        cut_track.remove_section(s)
    cut = cut_track.add_section()
    cut.set_range(0, plan["end"])
    cut.set_camera_binding_id(seq.get_portable_binding_id(seq, cam_binding))
    rig = next((b for b in seq.get_bindings() if str(b.get_display_name()) == RIG), None)
    if rig is not None:
        for t in rig.get_tracks():
            if str(t.get_display_name()) == "bCurtainActive":
                for s in t.get_sections():
                    ch = s.get_all_channels()[0]
                    for k in list(ch.get_keys()):
                        ch.remove_key(k)
                    ch.set_default(False)
                    ch.add_key(unreal.FrameNumber(0), False)
    report_row["applied"] = True
    del cache, drape, tmpl, comp, gt, cam_binding, cut_track, cut, rig


def main():
    with open(os.path.join(HERE, "fit_transition_drapes_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    dry = bool(cfg.get("dry_run", True))
    lead_s = float(cfg.get("lead_s", 5.0))
    which = [int(n) for n in cfg.get("interactions", [1, 2, 3, 4, 5])]
    report = {"ok": False, "dry_run": dry, "lead_s": lead_s, "rows": []}
    out = os.path.join(HERE, "fit_transition_drapes.json")

    def finish(msg):
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_TRANSITION_FIT|" if report["ok"] else "PUSS_SOFTGOODS_TRANSITION_FIT_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        return finish("PIE is running")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    problems = []
    for n in which:
        seq = unreal.load_asset(f"{SEQ_DIR}/{SEQS[n]}")
        plan = plan_for(seq, lead_s)
        mouth, err = mouth_of(actors, n + 1)
        cams = camera_for(actors, n + 1)
        row = {"interaction": n, "sequence": SEQS[n], "plan": plan, "mouth": mouth,
               "camera": [c.get_actor_label() for c in cams]}
        if err:
            problems.append(f"I{n}: {err}")
        if len(cams) != 1:
            problems.append(f"I{n}: expected exactly one stalls camera for P{n + 1:02d}, found {len(cams)}")
        report["rows"].append(row)
        del seq
    if dry:
        report["ok"] = True
        del actors
        return finish(f"DRY RUN, nothing written|problems={problems}|rows={len(report['rows'])}")
    if problems:
        del actors
        return finish(f"refusing to apply: {problems}")
    if dirty():
        del actors
        return finish(f"refusing: dirty packages {dirty()}")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreTransitionDrapes-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    for n in which:
        shutil.copy2(os.path.join(project, "Content", "InfinityStage", "Interactions", SEQS[n] + ".uasset"), backup)
    report["backup"] = backup
    try:
        for row in report["rows"]:
            n = row["interaction"]
            seq = unreal.load_asset(f"{SEQ_DIR}/{SEQS[n]}")
            camera = camera_for(actors, n + 1)[0]
            apply_one(seq, row["mouth"], camera, row["plan"], row)
            del seq, camera
    except Exception as exc:  # noqa: BLE001
        del actors
        return finish(f"FAILED mid-apply, NOTHING saved (relaunch to discard; backup {backup}): {exc}")
    del actors
    expected = {f"{SEQ_DIR}/{SEQS[n]}" for n in which}
    now = dirty()
    if [p for p in now if p not in expected]:
        return finish(f"unexpected dirty packages {now}; NOTHING saved (backup {backup})")
    report["saved"] = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False) for p in sorted(expected)}
    report["dirty_final"] = dirty()
    report["ok"] = all(report["saved"].values()) and not report["dirty_final"]
    finish(f"applied|saved={report['saved']}|dirty_final={report['dirty_final']}|backup={backup}")


main()
