"""Place the baked Opening curtain at the front, and the drape at every transition (29 Sep, Gary via the conductor:
"place the opening curtain where it's supposed to be (at the front and also in between transitions)").

OPENING (the real fall). Duplicates LS_Opening_Curtain -> LS_Opening_Curtain_Baked (the original is untouched, so
cue 0 can be pointed back) and in the duplicate:
  - removes the camera-following Fire Safety rig (0.1 scale, 1 m from the lens: "too close, focus off");
  - adds a spawnable GeometryCacheActor "Opening Drape (baked)" at the origin with GC_CurtainDrop_Opening. The cache
    is world-true (curtain line at X = 0, axis-checked on import), so the actor transform is identity;
  - a GeometryCache track in three sections: HOLD 0-25 (loops the first display frame: the hang), FALL 25-300 (the
    11 s bake; its release, 1.0 s in, lands on frame 50 as the old rig's lift did), PILE 300-375 (holds the last
    frame). Deterministic under any scrub; no reliance on completion modes;
  - a Camera Cut 0-375 to a LEVEL CineCamera "Opening — Stalls Camera" at (-1400, 0, 150), pitch +14, 15 mm on the
    23.76 x 13.365 filmback, focus off: Gary's stalls view from 28 Sep. Level actor (not spawnable) because the
    transport resolves a sub-sequence camera cut by locating it in the world. Without a cut the transport shows
    Passage 1's camera, which starts at X = 0, on the curtain line.
TRANSITIONS (stand-in). In LS_Interaction_01..05 and LS_Closing_Curtain, the camera-following rig's CurtainMesh
changes from SM_FireSafetyCurtain_01 to SM_CurtainDrape_Hanging (the bake's settled hang, velvet, the same
17.8 x 10 m frame), override materials cleared. Rig transforms, keys, distances and tests are unchanged.

Guards: expected world, no PIE, NOTHING dirty. Backs up the level and all seven sequences to
Backups/PreCurtainPlacement-<ts>/ first. Saves ONLY the level, LS_Opening_Curtain_Baked and the six sequences, and
only if nothing else went dirty. The Show repoint and the Master rebuild are a SEPARATE script.
Crash rules: all work inside functions, no UE objects at module level.
"""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_DIR = "/Game/InfinityStage/Interactions"
SRC = f"{SEQ_DIR}/LS_Opening_Curtain"
DST_NAME = "LS_Opening_Curtain_Baked"
DST = f"{SEQ_DIR}/{DST_NAME}"
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
DRAPE_SM = "/Game/Scenes/Curtain/Baked/SM_CurtainDrape_Hanging"
TRANSITIONS = ["LS_Interaction_01_WashingTheBoy", "LS_Interaction_02_Turnips", "LS_Interaction_03_ForgetsHisName",
               "LS_Interaction_04_GetsAName", "LS_Interaction_05_BecomesKing", "LS_Closing_Curtain"]
RIG_BINDING = "Curtain Rig - Fire Safety Curtain"
CAMERA_LABEL = "Opening — Stalls Camera"
FPS = 25
HOLD_END, FALL_END, SEQ_END = 25, 300, 375


def project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def content_file(asset_path, ext):
    return os.path.join(project(), "Content", *asset_path[len("/Game/"):].split("/")) + ext


def binding_id(seq, binding):
    for attempt in (lambda: seq.get_portable_binding_id(seq, binding), lambda: seq.get_binding_id(binding),
                    lambda: unreal.MovieSceneSequenceExtensions.get_binding_id(seq, binding)):
        try:
            return attempt()
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("no binding-id API worked")


def make_camera(report):
    ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = [a for a in ss.get_all_level_actors() if a.get_actor_label() == CAMERA_LABEL]
    if existing:
        raise RuntimeError(f"'{CAMERA_LABEL}' already exists; refusing to make a second")
    cam = ss.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(-1400.0, 0.0, 150.0),
                                    unreal.Rotator(roll=0.0, pitch=14.0, yaw=0.0))
    cam.set_actor_label(CAMERA_LABEL)
    cam.set_folder_path("InfinityStage/Opening")
    comp = cam.get_cine_camera_component()
    fb = comp.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", 23.76)
    fb.set_editor_property("sensor_height", 13.365)
    comp.set_editor_property("filmback", fb)
    comp.set_editor_property("current_focal_length", 15.0)
    fs = comp.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    comp.set_editor_property("focus_settings", fs)
    report["camera"] = {"label": cam.get_actor_label(), "loc": str(cam.get_actor_location()),
                        "rot": str(cam.get_actor_rotation()),
                        "focal": comp.get_editor_property("current_focal_length"),
                        "hfov": round(comp.get_editor_property("field_of_view"), 2)}
    return cam


def author_opening(report, cam):
    if unreal.EditorAssetLibrary.does_asset_exist(DST):
        raise RuntimeError(f"{DST} already exists; refusing to overwrite")
    seq = unreal.EditorAssetLibrary.duplicate_asset(SRC, DST)
    if not seq:
        raise RuntimeError("duplicate failed")
    tick = seq.get_tick_resolution()
    ticks_per_frame = (tick.numerator / tick.denominator) / FPS
    removed = []
    for b in list(seq.get_bindings()):
        if str(b.get_display_name()) == RIG_BINDING:
            b.remove()
            removed.append(RIG_BINDING)
    report["opening_removed"] = removed
    if removed != [RIG_BINDING]:
        raise RuntimeError(f"expected to remove exactly the rig binding, removed {removed}")
    cache = unreal.load_asset(GC)
    duration_s = (cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / 30.0
    dur_ticks = int(round(duration_s * tick.numerator / tick.denominator))
    one = int(round(ticks_per_frame))
    report["gc_duration_s"] = duration_s
    if abs(duration_s * FPS - (FALL_END - HOLD_END)) > 0.5:
        raise RuntimeError(f"cache is {duration_s} s, FALL section is {(FALL_END - HOLD_END) / FPS} s")

    drape = seq.add_spawnable_from_class(unreal.GeometryCacheActor)
    drape.set_display_name("Opening Drape (baked)")
    tmpl = drape.get_object_template()
    tmpl.set_actor_location(unreal.Vector(0, 0, 0), False, False)
    tmpl.set_actor_rotation(unreal.Rotator(0, 0, 0), False)
    comp = tmpl.get_editor_property("geometry_cache_component")
    comp.set_editor_property("geometry_cache", cache)
    set_props = {}
    for prop, value in (("running", False), ("looping", False)):
        try:
            comp.set_editor_property(prop, value)
            set_props[prop] = value
        except Exception as exc:  # noqa: BLE001
            set_props[prop] = f"not set: {exc}"
    report["drape_component"] = set_props

    tracks = [t.get_class().get_name() for t in drape.get_tracks()]
    if "MovieSceneSpawnTrack" not in tracks:
        st = drape.add_track(unreal.MovieSceneSpawnTrack)
        ss_ = st.add_section()
        ss_.set_range(0, SEQ_END)
        ch = ss_.get_all_channels()[0]
        ch.set_default(True)
        ch.add_key(unreal.FrameNumber(0), True)
    gt = drape.add_track(unreal.MovieSceneGeometryCacheTrack)
    plan = [("HOLD", 0, HOLD_END, 0, dur_ticks - one), ("FALL", HOLD_END, FALL_END, 0, 0),
            ("PILE", FALL_END, SEQ_END, dur_ticks - one, 0)]
    report["gc_sections"] = []
    for name, a, b, start_off, end_off in plan:
        s = gt.add_section()
        s.set_range(a, b)
        p = s.get_editor_property("params")
        p.set_editor_property("geometry_cache_asset", cache)
        p.set_editor_property("start_frame_offset", unreal.FrameNumber(start_off))
        p.set_editor_property("end_frame_offset", unreal.FrameNumber(end_off))
        p.set_editor_property("play_rate", 1.0)
        s.set_editor_property("params", p)
        try:
            s.set_completion_mode(unreal.MovieSceneCompletionMode.KEEP_STATE)
        except Exception:  # noqa: BLE001
            pass
        report["gc_sections"].append({"name": name, "range": [s.get_start_frame(), s.get_end_frame()],
                                      "start_off_ticks": start_off, "end_off_ticks": end_off})

    cam_binding = seq.add_possessable(cam)
    cam_binding.set_display_name(CAMERA_LABEL)
    try:
        cut_track = seq.add_track(unreal.MovieSceneCameraCutTrack)
    except Exception:  # noqa: BLE001
        cut_track = seq.add_master_track(unreal.MovieSceneCameraCutTrack)
    cut = cut_track.add_section()
    cut.set_range(0, SEQ_END)
    cut.set_camera_binding_id(binding_id(seq, cam_binding))
    report["camera_cut"] = {"range": [cut.get_start_frame(), cut.get_end_frame()],
                            "binding": str(cam_binding.get_id())}
    report["opening_bindings"] = [str(b.get_display_name()) for b in seq.get_bindings()]
    report["opening_range"] = [seq.get_playback_start(), seq.get_playback_end()]
    report["ticks_per_frame"] = ticks_per_frame


def swap_transition_meshes(report):
    drape_sm = unreal.load_asset(DRAPE_SM)
    rows = []
    for name in TRANSITIONS:
        seq = unreal.load_asset(f"{SEQ_DIR}/{name}")
        hits = [b for b in seq.get_bindings() if str(b.get_display_name()) == RIG_BINDING]
        if len(hits) != 1:
            raise RuntimeError(f"{name}: expected one '{RIG_BINDING}', found {len(hits)}")
        tmpl = hits[0].get_object_template()
        mesh = tmpl.get_editor_property("curtain_mesh")
        before = mesh.get_editor_property("static_mesh")
        mesh.set_editor_property("static_mesh", drape_sm)
        mesh.set_editor_property("override_materials", [])
        seq.modify()
        rows.append({"sequence": name, "before": before.get_path_name() if before else None,
                     "after": mesh.get_editor_property("static_mesh").get_path_name()})
    report["transitions"] = rows


def main():
    report = {"ok": False}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "curtain_place_opening_and_transitions.json")

    def finish(msg):
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_CURTAIN_PLACED|" if report["ok"] else "PUSS_SOFTGOODS_CURTAIN_PLACE_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_name = world.get_outermost().get_name()
    if world_name != EXPECTED_WORLD or editor.get_game_world() is not None:
        return finish(f"unsafe editor state: world={world_name}")
    if dirty():
        return finish(f"refusing: dirty packages {dirty()}")
    for p in (GC, DRAPE_SM, SRC):
        if not unreal.EditorAssetLibrary.does_asset_exist(p):
            return finish(f"missing {p}")

    backup = os.path.join(project(), "Backups", "PreCurtainPlacement-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(content_file(EXPECTED_WORLD, ".umap"), backup)
    for name in ["LS_Opening_Curtain"] + TRANSITIONS:
        shutil.copy2(content_file(f"{SEQ_DIR}/{name}", ".uasset"), backup)
    report["backup"] = backup

    try:
        cam = make_camera(report)
        author_opening(report, cam)
        del cam
        swap_transition_meshes(report)
    except Exception as exc:  # noqa: BLE001
        report["dirty_after_failure"] = dirty()
        return finish(f"FAILED mid-authoring, NOTHING saved (relaunch to discard; backup {backup}): {exc}")

    expected = {EXPECTED_WORLD, DST} | {f"{SEQ_DIR}/{n}" for n in TRANSITIONS}
    now = dirty()
    report["dirty_before_save"] = now
    unexpected = [p for p in now if p not in expected]
    if unexpected:
        return finish(f"unexpected dirty packages {unexpected}; NOTHING saved (relaunch to discard; backup {backup})")
    saved = {}
    for p in sorted(expected - {EXPECTED_WORLD}):
        saved[p] = unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False)
    saved[EXPECTED_WORLD] = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)
    report["saved"] = saved
    report["dirty_final"] = dirty()
    report["ok"] = all(saved.values()) and not report["dirty_final"]
    finish(f"saved={saved}|camera={report['camera']}|gc_sections={report['gc_sections']}|dirty_final={report['dirty_final']}"
           f"|backup={backup}")


main()
