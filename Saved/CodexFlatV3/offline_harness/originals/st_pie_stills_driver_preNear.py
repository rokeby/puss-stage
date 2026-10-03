"""Owned PIE-game-view stills for Flat V3 SK before/after comparison.

Arm this through st_pie_first_still_check.py or st_pie_full_run.py, then run
st_pie_begin_owned_play.py.  No package is saved.  Unreal objects live only in
the registered callback's closure; builtins carries plain state plus the handle.
"""
from __future__ import annotations

import builtins
import datetime
import hashlib
import json
import pathlib
import re
import time
import traceback

import unreal

import sk_common as c


BASE = pathlib.Path("E:/PussStage/Saved/CodexFlatV3/swapkit")
CAPTURE_ROOT = BASE / "stills"
CONDUCTOR = pathlib.Path("E:/PussStage/Saved/CodexConductor")
CURRENT = CONDUCTOR / "pie_recording_current_run.json"
OWNER = CONDUCTOR / "pie_recording_owner.json"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HANDLE_NAME = "PUSS_FLATV3_ST_PIE_HANDLE"
STATE_NAME = "PUSS_FLATV3_ST_PIE_STATE"
MODES = ("first_still_check", "full")
RUN_IDS = {
    "before": "FV3STB-20261003-02",
    "after": "FV3STA-20261003-02",
}
OK_MARKERS = {"before": "FLATV3_STB_OK", "after": "FLATV3_STA_OK"}
RESOLUTION = (3840, 2160)
SHOT_MIN_BYTES = 1000
MAX_SHOT_ERROR_FRAMES = 624  # 26 ms at the Master's 24,000 tick/s resolution.


def utc_now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def frame_value(value):
    return int(value.value if hasattr(value, "value") else value)


def package_names(packages):
    return sorted(str(value.get_name()).split(".", 1)[0] for value in packages)


def package_census():
    return {
        "content": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def assert_clean_package_census(value, label):
    if value != c.CLEAN:
        raise RuntimeError("ST_PIE_DIRTY_%s|%s" % (label, json.dumps(value, sort_keys=True)))
    return True


def actor_census(world):
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    return sorted(str(actor.get_path_name()) for actor in actors if actor is not None)


def asset_path(value):
    if value is None:
        return None
    return str(value.get_path_name()).split(".", 1)[0]


def classify(cfg):
    """Reuse retired ST's exhaustive old/new MI classification, fail closed."""
    per_passage = {}
    for passage in ("P01", "P02", "P03", "P04", "P05", "P06"):
        rows = [row for row in cfg["rows"] if row["passage"] == passage]
        if not rows:
            raise RuntimeError("ST_PIE_PASSAGE_ROWS_MISSING|passage=" + passage)
        values = []
        for row in rows:
            instance = c.load_asset(row["mi"], unreal.MaterialInstanceConstant)
            actual = c.mi_textures(instance)
            relevant = {name: actual.get(name) for name in c.KINDS}
            values.append(
                "before" if relevant == row["old_textures"] else
                "after" if relevant == row["new_textures"] else "mixed"
            )
        unique = set(values)
        if len(unique) != 1 or "mixed" in unique:
            raise RuntimeError(
                "ST_PIE_MI_STATE_MIXED|passage=%s|states=%s"
                % (passage, json.dumps(sorted(unique)))
            )
        per_passage[passage] = values[0]
    if len(set(per_passage.values())) != 1:
        raise RuntimeError("ST_PIE_PASSAGES_NOT_ONE_STATE|" + json.dumps(per_passage))
    return next(iter(per_passage.values())), per_passage


def derive_passage_jobs(passage, start_frame, end_frame, lead_in_frames, cue_rows):
    """Choose the swapped cue pass nearest the Passage midpoint; return walk/front."""
    if end_frame <= start_frame:
        raise RuntimeError("ST_PIE_BAD_PASSAGE_RANGE|passage=" + passage)
    pass_frame = start_frame + lead_in_frames
    candidates = []
    cue_pass_frames = []
    for row in cue_rows:
        recorded = dict(row)
        recorded["pass_frame"] = pass_frame
        cue_pass_frames.append(recorded)
        if row["swapped"] and start_frame <= pass_frame <= end_frame:
            candidates.append(recorded)
        pass_frame += int(row["interval_to_next"])
    if not candidates:
        raise RuntimeError("ST_PIE_NO_SWAPPED_CUE_IN_RANGE|passage=" + passage)
    midpoint = start_frame + (end_frame - start_frame) // 2
    target = min(candidates, key=lambda row: (abs(row["pass_frame"] - midpoint), row["cue_index"]))
    common = {
        "passage": passage,
        "master_frame": target["pass_frame"],
        "passage_range": [start_frame, end_frame],
        "passage_midpoint": midpoint,
        "target_cue_index": target["cue_index"],
        "target_cue_guid": target["cue_guid"],
        "target_cue_label": target["cue_label"],
        "cue_pass_frames": [
            {key: row[key] for key in ("cue_index", "cue_guid", "cue_label", "pass_frame", "swapped")}
            for row in cue_pass_frames
        ],
        "frame_source": "PIE transport Passage range + Show lead_in_frames/interval_to_next",
    }
    return [dict(common, view="walk"), dict(common, view="front")]


def panel_mi_paths(cue):
    pair = cue.get_editor_property("wing_pair")
    paths = set()
    for side in ("left", "right"):
        panel = pair.get_editor_property(side)
        for value in panel.get_editor_property("material_overrides"):
            path = asset_path(value)
            if path:
                paths.add(path)
        mesh = panel.get_editor_property("mesh")
        if mesh is not None:
            for row in mesh.get_editor_property("static_materials"):
                path = asset_path(row.get_editor_property("material_interface"))
                if path:
                    paths.add(path)
    return paths


def passage_number(label):
    match = re.search(r"\bPassage\s+0*(\d+)\b", str(label), re.IGNORECASE)
    if match is None:
        raise RuntimeError("ST_PIE_PASSAGE_LABEL_UNPARSEABLE|label=" + str(label))
    return int(match.group(1))


def runtime_plan(world, root, cfg):
    show = unreal.load_asset(SHOW)  # EditorAssetLibrary refuses during PIE ("Editor is currently in a play mode", 3 Oct)
    if show is None:
        raise RuntimeError("ST_PIE_SHOW_LOAD_FAIL")
    cues = list(show.get_editor_property("cues"))
    swapped_mis = {row["mi"] for row in cfg["rows"]}
    segments = [segment for segment in root.transport.segments
                if segment.type == unreal.InfinityCueType.WING_PAIR]
    if len(segments) != 6:
        raise RuntimeError("ST_PIE_PASSAGE_SEGMENT_COUNT|actual=%d" % len(segments))
    passage_actors = list(unreal.GameplayStatics.get_all_actors_of_class(
        world, unreal.InfinityStagePassageActor
    ))
    settings = list(show.get_editor_property("passage_settings"))
    jobs = []
    sources = []
    for ordinal, segment in enumerate(segments, 1):
        passage = "P%02d" % ordinal
        start_frame = frame_value(segment.start_frame)
        end_frame = frame_value(segment.end_frame)
        actors = [actor for actor in passage_actors
                  if passage_number(actor.get_actor_label()) == ordinal]
        if len(actors) != 1:
            raise RuntimeError("ST_PIE_PASSAGE_ACTOR_COUNT|passage=%s|actual=%d"
                               % (passage, len(actors)))
        actor = actors[0]
        pilot_range = unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(
            show, actor.get_editor_property("passage_guid")
        )
        if isinstance(pilot_range, tuple) and len(pilot_range) == 3 and isinstance(pilot_range[0], bool):
            pilot_range = pilot_range[1:] if pilot_range[0] else None
        if pilot_range is None or len(pilot_range) != 2:
            raise RuntimeError("ST_PIE_CAMERA_PILOT_RANGE_FAIL|passage=" + passage)
        pilot_values = [frame_value(pilot_range[0]), frame_value(pilot_range[1])]
        if pilot_values != [start_frame, end_frame]:
            raise RuntimeError(
                "ST_PIE_PASSAGE_RANGE_MISMATCH|passage=%s|transport=%s|pilot=%s"
                % (passage, [start_frame, end_frame], pilot_values)
            )
        actor_guid = actor.get_editor_property("passage_guid").to_string()
        matches = [value for value in settings
                   if value.get_editor_property("passage_guid").to_string() == actor_guid]
        if len(matches) != 1:
            raise RuntimeError("ST_PIE_PASSAGE_SETTINGS_COUNT|passage=" + passage)
        lead_in = frame_value(matches[0].get_editor_property("lead_in_frames"))
        cue_rows = []
        for index, cue in enumerate(cues):
            label = str(cue.get_editor_property("label"))
            if not label.startswith(passage + " "):
                continue
            cue_rows.append({
                "cue_index": index,
                "cue_guid": cue.get_editor_property("cue_guid").to_string(),
                "cue_label": label,
                "interval_to_next": frame_value(
                    cue.get_editor_property("wing_pair").get_editor_property("interval_to_next")
                ),
                "swapped": bool(panel_mi_paths(cue) & swapped_mis),
            })
        if not cue_rows:
            raise RuntimeError("ST_PIE_CUE_ROWS_MISSING|passage=" + passage)
        passage_jobs = derive_passage_jobs(
            passage, start_frame, end_frame, lead_in, cue_rows
        )
        jobs.extend(passage_jobs)
        sources.append({
            "passage": passage,
            "transport_range": [start_frame, end_frame],
            "camera_pilot_range": pilot_values,
            "lead_in_frames": lead_in,
            "chosen_cue": passage_jobs[0]["target_cue_label"],
            "chosen_pass_frame": passage_jobs[0]["master_frame"],
        })
    if len(jobs) != 12:
        raise RuntimeError("ST_PIE_JOB_COUNT|actual=%d" % len(jobs))
    return jobs, sources


def camera_world_key(world):
    return None if world is None else str(world.get_path_name())


def assert_no_preexisting_pie(editor):
    if editor.get_game_world() is not None:
        raise RuntimeError("ST_PIE_ALREADY_RUNNING")
    return True


def assert_game_camera(camera, game_world, editor_world):
    actual = camera.get_world() if camera is not None else None
    if (camera is None or actual is not game_world or actual is editor_world or
            camera_world_key(actual) == camera_world_key(editor_world)):
        raise RuntimeError(
            "ST_PIE_CAMERA_NOT_GAME_WORLD|camera=%s|game=%s|editor=%s"
            % (camera_world_key(actual), camera_world_key(game_world), camera_world_key(editor_world))
        )
    return True


def target_pair_pose(world, job):
    show = unreal.load_asset(SHOW)  # EditorAssetLibrary refuses during PIE ("Editor is currently in a play mode", 3 Oct)
    cues = list(show.get_editor_property("cues"))
    cue = cues[job["target_cue_index"]]
    if (cue.get_editor_property("cue_guid").to_string() != job["target_cue_guid"] or
            str(cue.get_editor_property("label")) != job["target_cue_label"]):
        raise RuntimeError("ST_PIE_TARGET_CUE_IDENTITY_DRIFT|passage=" + job["passage"])
    actors = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(
        world, unreal.InfinityStagePassageActor
    ) if passage_number(actor.get_actor_label()) == int(job["passage"][1:])]
    if len(actors) != 1:
        raise RuntimeError("ST_PIE_TARGET_ACTOR_COUNT|passage=" + job["passage"])
    refs = [ref for ref in actors[0].get_editor_property("materialized_panels")
            if ref.get_editor_property("cue_guid").to_string() == job["target_cue_guid"]]
    if not refs:
        raise RuntimeError("ST_PIE_TARGET_PANEL_REFS_MISSING|cue=" + job["target_cue_label"])
    ref = next((value for value in refs
                if "LEFT" in str(value.get_editor_property("side")).upper()), refs[0])
    side = "left" if "LEFT" in str(ref.get_editor_property("side")).upper() else "right"
    local = cue.get_editor_property("wing_pair").get_editor_property(side).get_editor_property(
        "local_transform"
    )
    component = ref.get_editor_property("component")
    instance_index = int(ref.get_editor_property("instance_index"))
    panel_world = component.get_instance_transform(instance_index, True)
    scaled_local = unreal.Vector(
        local.translation.x * panel_world.scale3d.x,
        local.translation.y * panel_world.scale3d.y,
        local.translation.z * panel_world.scale3d.z,
    )
    pair_location = panel_world.translation - panel_world.rotation.rotate_vector(scaled_local)
    pair_x = panel_world.rotation.rotate_vector(unreal.Vector(1.0, 0.0, 0.0))
    pair_z = panel_world.rotation.rotate_vector(unreal.Vector(0.0, 0.0, 1.0))
    heights = []
    for panel_ref in refs:
        panel_component = panel_ref.get_editor_property("component")
        panel_index = int(panel_ref.get_editor_property("instance_index"))
        panel_transform = panel_component.get_instance_transform(panel_index, True)
        mesh = panel_component.get_editor_property("static_mesh")
        bounds = mesh.get_bounding_box()
        for x in (bounds.min.x, bounds.max.x):
            for y in (bounds.min.y, bounds.max.y):
                for z in (bounds.min.z, bounds.max.z):
                    point = panel_transform.transform_location(unreal.Vector(x, y, z))
                    heights.append(float((point - pair_location).dot(pair_z)))
    if not heights:
        raise RuntimeError("ST_PIE_TARGET_PAIR_BOUNDS_EMPTY|cue=" + job["target_cue_label"])
    target_height = (min(heights) + max(heights)) * 0.5
    target = pair_location + pair_z * target_height
    location = pair_location - pair_x * 600.0 + pair_z * 300.0
    rotation = unreal.MathLibrary.find_look_at_rotation(location, target)
    return location, target, rotation, target_height


def spawn_front_camera(world, editor_world, job):
    location, target, rotation, target_height = target_pair_pose(world, job)
    transform = unreal.Transform(location=location, rotation=rotation)
    camera = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(
        world,
        unreal.CineCameraActor,
        transform,
        unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,
        None,
    )
    camera = unreal.GameplayStatics.finish_spawning_actor(camera, transform)
    assert_game_camera(camera, world, editor_world)
    camera.set_actor_label("FlatV3_ST_PIE_%s" % job["passage"], False)
    component = camera.get_cine_camera_component()
    component.set_current_focal_length(15.0)
    return camera, {
        "location": [float(location.x), float(location.y), float(location.z)],
        "target": [float(target.x), float(target.y), float(target.z)],
        "height_cm": 300.0,
        "target_height_cm": float(target_height),
        "front_distance_cm": 600.0,
        "focal_length_mm": 15.0,
    }


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def owner_matches(state):
    if not OWNER.is_file():
        return False
    owner = json.loads(OWNER.read_text(encoding="utf-8"))
    return (bool(owner.get("active")) and owner.get("run_id") == state["run_id"] and
            owner.get("run_dir") == state["run_dir"] and owner.get("kind") == "flatv3_st_pie_stills")


def write_owner(state, active, note):
    OWNER.write_text(json.dumps({
        "active": active,
        "kind": "flatv3_st_pie_stills",
        "note": note,
        "run_dir": state["run_dir"],
        "run_id": state["run_id"],
        "started_utc": state["started_utc"],
        "updated_utc": utc_now(),
    }, indent=2), encoding="utf-8")


def persist(state):
    name = "st_pie_first_check_runtime.json" if state["mode"] == "first_still_check" \
        else "st_pie_full_runtime.json"
    pathlib.Path(state["run_dir"], name).write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def release_log(state, status):
    unreal.log(
        "FLATV3_SLOT_RELEASED run=%s slot=ST_PIE mode=%s status=%s saved_count=0 census=%s"
        % (state["run_id"], state["mode"], status,
           json.dumps(state.get("dirty_after", {}), separators=(",", ":"), sort_keys=True))
    )


def unregister():
    if hasattr(builtins, HANDLE_NAME):
        unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
        delattr(builtins, HANDLE_NAME)


def prepare_output(state, jobs):
    run_dir = pathlib.Path(state["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    first_record = run_dir / "st_pie_first_still_check.json"
    for job in jobs:
        job["path"] = (run_dir / (job["passage"] + "_" + job["view"] + ".png")).as_posix()
        job["phase"] = "pending"
    existing = [path for path in run_dir.glob("P??_*.png") if path.is_file()]
    if state["mode"] == "first_still_check":
        selected = [job for job in jobs if job["passage"] == "P04" and job["view"] == "front"]
        if len(selected) != 1:
            raise RuntimeError("ST_PIE_FIRST_CHECK_PLAN_FAIL")
        check_dir = run_dir / "first_still_check"
        check_path = check_dir / "P04_front.png"
        if existing or first_record.exists() or check_path.exists():
            raise RuntimeError("ST_PIE_FIRST_CHECK_OUTPUT_EXISTS|run_dir=" + run_dir.as_posix())
        check_dir.mkdir(parents=True, exist_ok=True)
        selected[0]["path"] = check_path.as_posix()
        return selected
    if not first_record.is_file():
        raise RuntimeError("ST_PIE_FULL_REQUIRES_FIRST_CHECK|path=" + first_record.as_posix())
    record = json.loads(first_record.read_text(encoding="utf-8"))
    expected = run_dir / "first_still_check" / "P04_front.png"
    if (record.get("run_id") != state["run_id"] or record.get("state") != state["capture_state"] or
            record.get("path") != expected.as_posix() or not expected.is_file() or
            expected.stat().st_size <= SHOT_MIN_BYTES or file_sha256(expected) != record.get("sha256")):
        raise RuntimeError("ST_PIE_FIRST_CHECK_RECORD_INVALID")
    unexpected = [path.as_posix() for path in existing if path != expected]
    if unexpected:
        raise RuntimeError("ST_PIE_UNEXPECTED_EXISTING_OUTPUTS|" + json.dumps(unexpected))
    return jobs


def arm(mode):
    if mode not in MODES:
        raise RuntimeError("ST_PIE_BAD_MODE|" + str(mode))
    if hasattr(builtins, HANDLE_NAME):
        raise RuntimeError("ST_PIE_CALLBACK_ALREADY_REGISTERED")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    editor_world = editor.get_editor_world()
    if editor_world is None or str(editor_world.get_outermost().get_name()) != EXPECTED_WORLD:
        raise RuntimeError("ST_PIE_WRONG_EDITOR_WORLD")
    cfg = c.config()
    capture_state, passage_states = classify(cfg)
    run_id = RUN_IDS[capture_state]
    try:
        assert_no_preexisting_pie(editor)
    except RuntimeError:
        unreal.log_error("ST_PIE_PREEXISTING_PIE_ABORT run=%s" % run_id)
        unreal.log("FLATV3_SLOT_RELEASED run=%s slot=ST_PIE mode=%s status=ABORTED_PREEXISTING_PIE saved_count=0"
                   % (run_id, mode))
        raise
    dirty_before = package_census()
    assert_clean_package_census(dirty_before, "BEFORE")
    if OWNER.is_file() and json.loads(OWNER.read_text(encoding="utf-8")).get("active"):
        raise RuntimeError("ST_PIE_OTHER_OWNER_ACTIVE")

    state = {
        "schema_version": 1,
        "run_id": run_id,
        "run_dir": (CAPTURE_ROOT / capture_state / run_id).as_posix(),
        "mode": mode,
        "capture_state": capture_state,
        "passage_states": passage_states,
        "status": "waiting_for_owned_pie",
        "final_status": None,
        "started_utc": utc_now(),
        "started_monotonic": time.monotonic(),
        "inside": False,
        "pie_observed": False,
        "screen_messages_disabled": False,
        "screen_messages_restored": False,
        "dirty_before": dirty_before,
        "dirty_after": None,
        "editor_actors_before": actor_census(editor_world),
        "game_actors_baseline": None,
        "jobs": [],
        "job_index": 0,
        "errors": [],
        "saved_packages": [],
        "exposure_override": False,
        "resolution": list(RESOLUTION),
        "start_api": {
            "play_mode": "PlayMode_InEditorFloating",
            "begin_script": "CodexFlatV3/swapkit/st_pie_begin_owned_play.py",
            "api": "LevelEditorSubsystem.editor_request_begin_play",
        },
    }
    runtime = {"camera": None, "restore_view_target": None}

    def restore_messages(world):
        if world is not None and state.get("screen_messages_disabled"):
            unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
            state["screen_messages_disabled"] = False
            state["screen_messages_restored"] = True

    def destroy_runtime_camera(world):
        camera = runtime.get("camera")
        if camera is None:
            return
        assert_game_camera(camera, world, editor_world)
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        if runtime.get("restore_view_target") is not None:
            controller.set_view_target_with_blend(runtime["restore_view_target"], 0.0)
        camera.destroy_actor()
        runtime["camera"] = None
        runtime["restore_view_target"] = None

    def finalize(status, error=None):
        if error:
            state["errors"].append(error)
        state["finished_utc"] = utc_now()
        state["dirty_after"] = package_census()
        current_editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        state["editor_actors_after"] = actor_census(current_editor_world) if current_editor_world else []
        try:
            assert_clean_package_census(state["dirty_after"], "AFTER")
        except RuntimeError as exc:
            state["errors"].append(str(exc))
        if state["editor_actors_after"] != state["editor_actors_before"]:
            state["errors"].append("ST_PIE_EDITOR_ACTOR_CENSUS_CHANGED")
        if not state.get("screen_messages_restored"):
            state["errors"].append("ST_PIE_SCREEN_MESSAGES_NOT_RESTORED")
        expected_jobs = 1 if state["mode"] == "first_still_check" else 12
        complete_jobs = [job for job in state["jobs"]
                         if job.get("phase") == "complete" and job.get("bytes", 0) > SHOT_MIN_BYTES]
        if len(state["jobs"]) != expected_jobs or len(complete_jobs) != expected_jobs:
            state["errors"].append(
                "ST_PIE_SHOT_COUNT_FAIL|expected=%d|jobs=%d|complete=%d"
                % (expected_jobs, len(state["jobs"]), len(complete_jobs))
            )
        if state["errors"]:
            status = "failed"
        state["status"] = status
        state["final_status"] = status
        if owner_matches(state):
            write_owner(state, False, "this Flat V3 still run ended; post-PIE census recorded")
        persist(state)
        if status == "passed" and state["mode"] == "first_still_check":
            job = state["jobs"][0]
            pathlib.Path(state["run_dir"], "st_pie_first_still_check.json").write_text(
                json.dumps({
                    "status": "PASS",
                    "run_id": state["run_id"],
                    "state": state["capture_state"],
                    "path": job["path"],
                    "bytes": job["bytes"],
                    "sha256": job["sha256"],
                    "human_review": "PENDING_CONDUCTOR_LOOK",
                }, indent=2), encoding="utf-8"
            )
            unreal.log("FLATV3_ST_FIRST_STILL_CHECK_OK run=%s path=%s human_review=pending"
                       % (state["run_id"], job["path"]))
        elif status == "passed":
            unreal.log(
                "%s run=%s shots=12 saved_count=0 exposure_override=false game_view=true"
                % (OK_MARKERS[state["capture_state"]], state["run_id"])
            )
        release_log(state, status)
        unregister()

    def request_end(status, error=None, world=None):
        if error:
            state["errors"].append(error)
        if world is None or not state.get("pie_observed"):
            finalize("failed", "ST_PIE_REFUSED_END_UNOBSERVED")
            return
        if not owner_matches(state):
            restore_messages(world)
            finalize("failed", "ST_PIE_REFUSED_END_OWNER_MISMATCH")
            return
        destroy_runtime_camera(world)
        restore_messages(world)
        if actor_census(world) != state["game_actors_baseline"]:
            state["errors"].append("ST_PIE_GAME_ACTOR_CENSUS_CHANGED_BEFORE_END")
            status = "failed"
        state["final_status"] = status
        state["status"] = "stopping_owned_pie"
        state["stop_requested_wall"] = time.monotonic()
        write_owner(state, True, "end requested for this run's observed owned PIE")
        persist(state)
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()

    def begin_job(world, root, index):
        state["job_index"] = index
        job = state["jobs"][index]
        root.sequence_player.pause()
        result = root.transport.scrub_to_master_frame(unreal.FrameNumber(job["master_frame"]))
        job["scrub_result"] = str(result)
        job["actual_frame_after_scrub"] = frame_value(root.transport.get_current_master_frame())
        job["phase"] = "settle_before_repose"
        job["settle_ticks"] = 0
        state["status"] = "capturing"
        unreal.log("FLATV3_ST_PIE_JUMP run=%s passage=%s view=%s target=%d actual=%d"
                   % (state["run_id"], job["passage"], job["view"], job["master_frame"],
                      job["actual_frame_after_scrub"]))
        persist(state)

    def advance_job(world, root):
        if state["job_index"] + 1 < len(state["jobs"]):
            begin_job(world, root, state["job_index"] + 1)
        else:
            request_end("passed", world=world)

    def tick(_delta):
        if state.get("inside"):
            return
        state["inside"] = True
        world = None
        try:
            editor_now = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
            world = editor_now.get_game_world()
            if state["status"] == "stopping_owned_pie":
                if world is None:
                    finalize(state.get("final_status") or "failed")
                elif (time.monotonic() - state["stop_requested_wall"] > 20.0 and
                      not state.get("end_timeout_recorded")):
                    state["errors"].append("ST_PIE_END_TIMEOUT")
                    state["final_status"] = "failed"
                    state["end_timeout_recorded"] = True
                    persist(state)
                return
            if time.monotonic() - state["started_monotonic"] > 900.0:
                raise RuntimeError("ST_PIE_TIMEOUT_900S")
            if state["status"] == "waiting_for_owned_pie":
                if world is None:
                    return
                if not owner_matches(state):
                    raise RuntimeError("ST_PIE_OWNER_MISMATCH_AFTER_START")
                state["pie_observed"] = True
                roots = list(unreal.GameplayStatics.get_all_actors_of_class(
                    world, unreal.InfinityStageShowRoot
                ))
                if len(roots) != 1 or not roots[0].sequence_player:
                    return
                root = roots[0]
                root.sequence_player.pause()
                root.transport.set_editor_property("performance_mode", False)
                if root.transport.get_editor_property("performance_mode"):
                    raise RuntimeError("ST_PIE_PERFORMANCE_MODE_ON")
                jobs, sources = runtime_plan(world, root, cfg)
                state["frame_sources"] = sources
                state["jobs"] = prepare_output(state, jobs)
                state["game_actors_baseline"] = actor_census(world)
                unreal.SystemLibrary.execute_console_command(world, "DisableAllScreenMessages")
                state["screen_messages_disabled"] = True
                state["screen_messages_restored"] = False
                unreal.log("FLATV3_ST_PIE_READY run=%s state=%s mode=%s jobs=%d"
                           % (state["run_id"], state["capture_state"], state["mode"],
                              len(state["jobs"])))
                begin_job(world, root, 0)
                return
            if world is None:
                finalize("failed", "ST_PIE_ENDED_EARLY")
                return
            roots = list(unreal.GameplayStatics.get_all_actors_of_class(
                world, unreal.InfinityStageShowRoot
            ))
            if len(roots) != 1 or not roots[0].sequence_player:
                raise RuntimeError("ST_PIE_LOST_SHOW_ROOT")
            root = roots[0]
            job = state["jobs"][state["job_index"]]
            if job["phase"] == "settle_before_repose":
                job["settle_ticks"] += 1
                if job["settle_ticks"] < 8:
                    return
                result = root.transport.scrub_to_master_frame(unreal.FrameNumber(job["master_frame"]))
                job["repose_result"] = str(result)
                job["settle_ticks"] = 0
                job["phase"] = "settle_after_repose"
                if job["view"] == "front":
                    controller = unreal.GameplayStatics.get_player_controller(world, 0)
                    runtime["restore_view_target"] = controller.get_view_target()
                    camera, pose = spawn_front_camera(world, editor_world, job)
                    runtime["camera"] = camera
                    job["front_camera"] = pose
                    controller.set_view_target_with_blend(camera, 0.0)
                return
            if job["phase"] == "settle_after_repose":
                job["settle_ticks"] += 1
                if job["settle_ticks"] < 8:
                    return
                if job["view"] == "front":
                    assert_game_camera(runtime.get("camera"), world, editor_world)
                else:
                    view_target = unreal.GameplayStatics.get_player_controller(world, 0).get_view_target()
                    if view_target is None or str(view_target.get_actor_label()).startswith("FlatV3_ST_PIE_"):
                        raise RuntimeError("ST_PIE_WALK_SHOW_VIEW_TARGET_MISSING|passage=" + job["passage"])
                    job["show_view_target"] = str(view_target.get_path_name())
                actual_frame = frame_value(root.transport.get_current_master_frame())
                job["actual_frame_at_shot"] = actual_frame
                job["shot_error_frames"] = actual_frame - job["master_frame"]
                if abs(job["shot_error_frames"]) > MAX_SHOT_ERROR_FRAMES:
                    raise RuntimeError(
                        "ST_PIE_SHOT_TIME_MISS|passage=%s|view=%s|target=%d|actual=%d"
                        % (job["passage"], job["view"], job["master_frame"], actual_frame)
                    )
                path = pathlib.Path(job["path"])
                if path.exists():
                    raise RuntimeError("ST_PIE_OUTPUT_EXISTS_AT_CAPTURE|" + path.as_posix())
                command = 'HighResShot %dx%d filename="%s"' % (
                    RESOLUTION[0], RESOLUTION[1], path.as_posix()
                )
                unreal.SystemLibrary.execute_console_command(world, command)
                job["command"] = command
                job["phase"] = "wait_file"
                job["issued_wall"] = time.monotonic()
                job["last_size"] = -1
                job["stable_ticks"] = 0
                return
            if job["phase"] == "wait_file":
                path = pathlib.Path(job["path"])
                size = path.stat().st_size if path.is_file() else -1
                if size > SHOT_MIN_BYTES and size == job["last_size"]:
                    job["stable_ticks"] += 1
                else:
                    job["stable_ticks"] = 0
                    job["last_size"] = size
                if job["stable_ticks"] >= 4:
                    job["bytes"] = size
                    job["sha256"] = file_sha256(path)
                    job["phase"] = "cleanup_camera" if job["view"] == "front" else "complete"
                    if job["view"] == "front":
                        destroy_runtime_camera(world)
                        job["cleanup_started_wall"] = time.monotonic()
                    else:
                        advance_job(world, root)
                    return
                if time.monotonic() - job["issued_wall"] > 45.0:
                    raise RuntimeError("ST_PIE_CAPTURE_TIMEOUT|" + job["path"])
                return
            if job["phase"] == "cleanup_camera":
                if actor_census(world) == state["game_actors_baseline"]:
                    job["phase"] = "complete"
                    advance_job(world, root)
                    return
                if time.monotonic() - job["cleanup_started_wall"] > 10.0:
                    raise RuntimeError("ST_PIE_CAMERA_CLEANUP_CENSUS_FAIL")
        except Exception:
            error = traceback.format_exc()
            if world is not None and state.get("pie_observed") and owner_matches(state):
                request_end("failed", error, world)
            else:
                finalize("failed", error)
        finally:
            state["inside"] = False

    pathlib.Path(state["run_dir"]).mkdir(parents=True, exist_ok=True)
    setattr(builtins, STATE_NAME, state)
    CURRENT.write_text(json.dumps({
        "kind": "flatv3_st_pie_stills",
        "run_dir": state["run_dir"],
        "run_id": state["run_id"],
        "mode": mode,
        "prepared_utc": utc_now(),
        "status": "owned_flatv3_st_pie_armed",
    }, indent=2), encoding="utf-8")
    write_owner(state, True, "owner flag written before starting this Flat V3 still PIE")
    persist(state)
    try:
        setattr(builtins, HANDLE_NAME, unreal.register_slate_post_tick_callback(tick))
    except Exception:
        write_owner(state, False, "callback registration failed; PIE was not started")
        raise
    unreal.log("FLATV3_ST_PIE_ARMED run=%s state=%s mode=%s play_mode=PlayMode_InEditorFloating"
               % (state["run_id"], state["capture_state"], mode))
    return state


if __name__ == "__main__":
    arm(globals().get("FLATV3_ST_PIE_MODE", "first_still_check"))
