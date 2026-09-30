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
APPLY: no PIE; no dirty CONTENT (a dirty map is tolerated, never saved); exactly one camera per mouth. Backs up the five .uassets to
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
# Mouths that are NOT the P01 stage front the pile was baked onto (29 Sep, Rig): flag, do not assume.
SITE_NOTES = {3: "S03 is FRAME ONLY: no stage front, because P03 stands on the Wet Ground landscape. The pile was baked onto "
                 "P01's stage front (lip, fascia, house floor at -120), so its spill may float or clip here. CHECK "
                 "this mouth before trusting it."}
# HOLD AT THE RELEASE (30 Sep, conductor-approved on Gary's delegation; "say if you disagree and it comes back out").
# The HOLD used to freeze the cache's FIRST sample, then the FALL played 1 s of still-settling hang before the release.
# That moving second is visible or not depending on the lens (P04's 35 mm made 1.59 mm/frame about 0.5 px). Now the HOLD
# freezes the sample ONE FRAME BEFORE the release, and the FALL starts from there. Nothing moves on screen before the
# release, whatever the lens.
# TIMING CHANGE WITH THE SAME PICTURE: lead_s drops from 5.0 to 4.0. The FALL no longer carries the 1 s of hang, so it
# starts one frame before the release instead of 1 s before, and the pile still shows about 1.5 s before the cut.
# CONDITION: the frozen frame must read as a curtain AT REST. final2's release-minus-one frame is arrested mid-sway
# (check_frozen_frames_at_rest_NOT_SHOW_FRAME.png), so hold_at="release" is applied only with a settled cache.
LANDED_AFTER_RELEASE_S = 2.5     # the 10 m drape's top is under 1.35 m about 2.7 s after release; "down" about 2.5 s
CACHE_FPS = 30.0
BAKE_DIR = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "DropBake")
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
        # DISTANCE 0 IS LOAD-BEARING (30 Sep). The portal is built in the route-start frame. P02's route curves (tangent yaw
        # 22.908 deg at 0 m, 24.30 at the first station), and at an 18.8 m track with about 10 cm to each 40 cm-deep post,
        # 1.4 deg of yaw error puts the curtain's ends about +-23 cm fore and aft of the post plane. Never "improve" this
        # to the first station.
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


def release_in_cache_s(cache):
    """Seconds from the cache's first sample to its release, read from the cache's own import chain: its source is
    <cache>_<bake_id>.abc (import_passing_bake.py), which gives DropBake/<bake_id>.json and so (release - start) / 30.
    final2 predates that naming, and its bake JSON is named explicitly. Anything else refuses; the value is never assumed."""
    src = os.path.basename(cache.get_editor_property("asset_import_data").get_first_filename())
    stem = GC.split("/")[-1] + "_"
    if src.startswith(stem) and src.endswith(".abc"):
        bake_id = src[len(stem):-4]
    elif src == "CurtainDrop_Opening_final2.abc":
        bake_id = "final2_stage_v2"
    else:
        raise RuntimeError(f"cannot trace {GC} to a bake: source {src}")
    with open(os.path.join(BAKE_DIR, f"{bake_id}.json"), encoding="utf-8") as h:
        bake = json.load(h)
    return (bake["release_frame"] - bake["show_start"]) / CACHE_FPS, bake_id


def timeline(length_s, lead_s, release_into_fall_s):
    fall = max(0.0, length_s - lead_s)
    return (f"hangs 0-{fall:.1f} s (the shadow play), releases at {fall + release_into_fall_s:.1f} s, down by about "
            f"{fall + release_into_fall_s + LANDED_AFTER_RELEASE_S:.1f} s, cut to the Passage at {length_s:.1f} s")


def plan_for(seq, lead_s, release_into_fall_s):
    rate = seq.get_display_rate()
    fps = rate.numerator / rate.denominator
    end = seq.get_playback_end()
    lead = int(round(lead_s * fps))
    length_s = end / fps
    return {"fps": fps, "end": end, "fall_start": max(0, end - lead), "length_s": round(length_s, 3),
            "now": timeline(length_s, lead_s, release_into_fall_s), "if_60s": timeline(60.0, lead_s, release_into_fall_s)}


def apply_one(seq, mouth, camera, plan, report_row, hold_at, release_s):
    cache = unreal.load_asset(GC)
    tick = seq.get_tick_resolution()
    tps = tick.numerator / tick.denominator
    dur_ticks = int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / CACHE_FPS * tps))
    # the sample held, in ticks from the cache's start: 0 (first) or one cache frame before the release
    hold_off = int(round((release_s - 1.0 / CACHE_FPS) * tps)) if hold_at == "release" else 0
    fall_len = int(round((plan["end"] - plan["fall_start"]) / plan["fps"] * tps))
    if hold_off + fall_len > dur_ticks:
        raise RuntimeError(f"FALL ({fall_len} ticks) from offset {hold_off} overruns the {dur_ticks}-tick cache: it would LOOP")
    drape = next((b for b in seq.get_bindings() if str(b.get_display_name()) == DRAPE), None)
    if drape is None:
        drape = seq.add_spawnable_from_class(unreal.GeometryCacheActor)
        drape.set_display_name(DRAPE)
    tmpl = drape.get_object_template()
    # A spawnable TEMPLATE has no world: set_actor_location/rotation on it saved (0, 0, 0) and yaw 0 on all five (30 Sep
    # read-back), so every drape would have spawned at P01's stage front. Write the root component's relative transform.
    root = tmpl.get_editor_property("root_component")
    root.set_editor_property("relative_location", unreal.Vector(mouth["x"], mouth["y"], mouth["z"]))
    root.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=mouth["yaw"]))
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
    # HOLD loops a ONE-TICK window at the cache's start, so it shows exactly the first sample. The Opening's first
    # version looped one DISPLAY frame (960 ticks): the evaluated time wandered up to 0.04 s, between cache samples,
    # and flickered on a cloth still moving (30 Sep).
    planned = (("HOLD", 0, plan["fall_start"], hold_off, dur_ticks - hold_off - 1),
               ("FALL", plan["fall_start"], plan["end"], hold_off, 0))
    report_row["sections_planned"] = [[a, b, so, eo] for _, a, b, so, eo in planned]
    for name, a, b, start_off, end_off in planned:
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
    del cache, drape, tmpl, root, comp, gt, cam_binding, cut_track, cut, rig


def main():
    with open(os.path.join(HERE, "fit_transition_drapes_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    dry = bool(cfg.get("dry_run", True))
    hold_at = cfg.get("hold_at", "first")                     # "release" only with a settled cache (see HOLD AT THE RELEASE)
    lead_s = float(cfg.get("lead_s", 4.0 if hold_at == "release" else 5.0))
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
    try:
        cache0 = unreal.load_asset(GC)
        release_s, bake_id = release_in_cache_s(cache0)
        del cache0
    except Exception as exc:  # noqa: BLE001
        return finish(f"refusing: {exc}")
    # When the HOLD sits one frame before the release, the FALL releases one cache frame in; otherwise release_s in.
    release_into_fall_s = 1.0 / CACHE_FPS if hold_at == "release" else release_s
    report.update({"hold_at": hold_at, "release_in_cache_s": release_s, "cache_bake": bake_id,
                   "timing_note": ("lead_s 4.0 (was 5.0): the FALL starts one frame before the release instead of 1 s "
                                   "before; the picture is unchanged, the pile still shows about 1.5 s before the cut")
                   if hold_at == "release" else "legacy: HOLD freezes the cache's first sample"})
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    problems = []
    for n in which:
        seq = unreal.load_asset(f"{SEQ_DIR}/{SEQS[n]}")
        plan = plan_for(seq, lead_s, release_into_fall_s)
        mouth, err = mouth_of(actors, n + 1)
        cams = camera_for(actors, n + 1)
        row = {"interaction": n, "sequence": SEQS[n], "plan": plan, "mouth": mouth,
               "camera": [c.get_actor_label() for c in cams], "site_note": SITE_NOTES.get(n + 1)}
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
    # A dirty MAP is tolerated (30 Sep: Look & camera's stills leave the level dirty with no net change); the fit never
    # saves it. Any dirty CONTENT package still refuses, since this script must save only its own sequences.
    baseline = dirty()
    maps_before = set(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if [p for p in baseline if p not in maps_before]:
        del actors
        return finish(f"refusing: dirty content packages {[p for p in baseline if p not in maps_before]}")
    report["dirty_maps_tolerated"] = sorted(maps_before)
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
            apply_one(seq, row["mouth"], camera, row["plan"], row, hold_at, release_s)
            del seq, camera
    except Exception as exc:  # noqa: BLE001
        del actors
        return finish(f"FAILED mid-apply, NOTHING saved (relaunch to discard; backup {backup}): {exc}")
    del actors
    expected = {f"{SEQ_DIR}/{SEQS[n]}" for n in which}
    now = dirty()
    if [p for p in now if p not in expected and p not in maps_before]:
        return finish(f"unexpected dirty packages {now}; NOTHING saved (backup {backup})")
    report["saved"] = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False) for p in sorted(expected)}
    report["dirty_final"] = dirty()
    report["ok"] = all(report["saved"].values()) and not [p for p in report["dirty_final"] if p not in maps_before]
    finish(f"applied|saved={report['saved']}|dirty_final={report['dirty_final']}|backup={backup}")


main()
