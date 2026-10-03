"""Capture B02/B03 1600x900 viewport stills without changing packages."""
import builtins
import datetime
import json
import math
import os
import time
import traceback

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
SHOT_LABELS = ("S3 Shot B02", "S3 Shot B03")
BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
))
OUT = os.path.join(BASE, "S3BeachStills")
LANDED_RECORD = os.path.join(BASE, "s3_landed_preview_record.json")
SHOTLIST_RECORD = os.path.join(BASE, "s3_shotlist_record.json")
RUN = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def census():
    def names(packages):
        return sorted(str(package.get_path_name()).split(".", 1)[0] for package in packages)
    return {
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def vector_error(actual, expected):
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(actual, expected)))


def actor_relative_plain(actor):
    parent = actor.get_attach_parent_actor()
    value = actor.root_component.get_relative_transform() if parent else actor.get_actor_transform()
    rotation = value.rotation.rotator()
    return {
        "location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


def assert_landed():
    if not os.path.isfile(LANDED_RECORD):
        raise RuntimeError("S3_LANDED_RECORD_MISSING")
    with open(LANDED_RECORD, encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or int(record.get("scene", -1)) != 3:
        raise RuntimeError("S3_LANDED_RECORD_INVALID")
    index = {}
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        index.setdefault(str(actor.get_actor_label()), []).append(actor)
    errors = []
    for label in record.get("mover_labels", []):
        matches = index.get(label, [])
        if len(matches) != 1:
            raise RuntimeError("S3_LANDED_ACTOR_COUNT|label=%s|count=%d" % (label, len(matches)))
        actual = actor_relative_plain(matches[0])
        expected = record["landed_transforms"][label]
        errors.append({
            "label": label,
            "location_cm": vector_error(actual["location"], expected["location"]),
            "rotation_deg": vector_error(actual["rotation"], expected["rotation"]),
            "scale": vector_error(actual["scale"], expected["scale"]),
        })
    worst = {
        "location_cm": max(row["location_cm"] for row in errors),
        "rotation_deg": max(row["rotation_deg"] for row in errors),
        "scale": max(row["scale"] for row in errors),
    }
    if worst["location_cm"] > 0.01 or worst["rotation_deg"] > 0.001 or worst["scale"] > 0.000001:
        raise RuntimeError("S3_NOT_LANDED|" + json.dumps(errors, sort_keys=True))
    return worst


def shot_jobs(sequence):
    jobs = []
    by_label = {str(binding.get_display_name()): binding for binding in sequence.get_spawnables()}
    with open(SHOTLIST_RECORD, encoding="utf-8") as handle:
        shot_record = json.load(handle)
    recorded = {row["label"]: row["camera"] for row in shot_record["after"]["created"]}
    for label in SHOT_LABELS:
        binding = by_label.get(label)
        if binding is None:
            raise RuntimeError("SHOT_BINDING_MISSING|" + label)
        actor = binding.get_object_template()
        root = actor.get_editor_property("root_component") if actor is not None else None
        component = ((actor.get_cine_camera_component() or actor.get_editor_property("camera_component"))
                     if actor is not None else None)
        if actor is None or root is None or component is None:
            raise RuntimeError("SHOT_CAMERA_TEMPLATE_INCOMPLETE|" + label)
        if root.get_attach_parent() is not None:
            raise RuntimeError("SHOT_CAMERA_TEMPLATE_ATTACHED|" + label)
        # These camera actor templates have unattached roots. Their stored root
        # transform is therefore the actor's world transform, not a dock-local pose.
        location = root.get_editor_property("relative_location")
        rotation = root.get_editor_property("relative_rotation")
        expected = recorded.get(label)
        if expected is None:
            raise RuntimeError("SHOT_WORLD_RECORD_MISSING|" + label)
        if vector_error([location.x, location.y, location.z], expected["location"]) > 0.01:
            raise RuntimeError("SHOT_WORLD_LOCATION_DRIFT|" + label)
        if vector_error([rotation.roll, rotation.pitch, rotation.yaw], expected["rotation_rpy"]) > 0.001:
            raise RuntimeError("SHOT_WORLD_ROTATION_DRIFT|" + label)
        filmback = component.get_editor_property("filmback")
        sensor_width = float(filmback.get_editor_property("sensor_width"))
        focal_mm = float(component.get_editor_property("current_focal_length"))
        hfov = math.degrees(2.0 * math.atan(sensor_width / (2.0 * focal_mm)))
        short = label.rsplit(" ", 1)[-1]
        path = os.path.join(OUT, "S3_%s_BeachMarble_%s.png" % (short, RUN))
        if os.path.exists(path):
            raise RuntimeError("OUTPUT_ALREADY_EXISTS|" + path)
        jobs.append({
            "label": label,
            "location": location,
            "rotation": rotation,
            "focal_mm": focal_mm,
            "sensor_width_mm": sensor_width,
            "hfov_deg": hfov,
            "path": path,
            "actor_path": str(actor.get_path_name()),
        })
    return jobs


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = world.get_outermost().get_name() if world else None
if world_path != EXPECTED_WORLD:
    raise RuntimeError("WRONG_WORLD|" + str(world_path))
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_OR_SIE_ACTIVE")
before = census()
if before != {"maps": [], "content": []}:
    raise RuntimeError("DIRTY_BEFORE|" + json.dumps(before, sort_keys=True))
if hasattr(builtins, "PUSS_S3_BEACH_STILLS_HANDLE"):
    raise RuntimeError("CAPTURE_CALLBACK_ALREADY_REGISTERED")
landed_error = assert_landed()
sequence = unreal.load_asset(SEQUENCE_PATH)
if not isinstance(sequence, unreal.LevelSequence):
    raise RuntimeError("SEQUENCE_LOAD_FAILED")
jobs = shot_jobs(sequence)
os.makedirs(OUT, exist_ok=True)
original_camera = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
state = {
    "index": 0,
    "phase": "setup",
    "ticks": 0,
    "issued_at": 0.0,
    "last_size": -1,
    "stable_ticks": 0,
    "screen_messages_disabled": False,
}


def stop_callback():
    handle = getattr(builtins, "PUSS_S3_BEACH_STILLS_HANDLE", None)
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        delattr(builtins, "PUSS_S3_BEACH_STILLS_HANDLE")


def restore_viewport():
    unreal.SystemLibrary.execute_console_command(world, "FOV 90")
    if original_camera:
        unreal.EditorLevelLibrary.set_level_viewport_camera_info(original_camera[0], original_camera[1])
    if state["screen_messages_disabled"]:
        unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
        state["screen_messages_disabled"] = False


def finish_success():
    restore_viewport()
    after = census()
    if after != {"maps": [], "content": []}:
        raise RuntimeError("DIRTY_AFTER|" + json.dumps(after, sort_keys=True))
    files = [{
        "label": job["label"],
        "path": job["path"].replace("\\", "/"),
        "bytes": os.path.getsize(job["path"]),
        "focal_mm": job["focal_mm"],
        "sensor_width_mm": job["sensor_width_mm"],
        "hfov_deg": job["hfov_deg"],
    } for job in jobs]
    unreal.log("S3_BEACH_STILLS_DONE|run=%s|files=%s|camera_transform=world|screen_messages_off=1|screen_messages_restored=1|exposure_override=0|landed=1|census=%s" %
               (RUN, json.dumps(files, separators=(",", ":"), sort_keys=True),
                json.dumps(after, separators=(",", ":"), sort_keys=True)))
    stop_callback()


def tick(_delta_seconds):
    try:
        if state["index"] >= len(jobs):
            finish_success()
            return
        job = jobs[state["index"]]
        if state["phase"] == "setup":
            if not state["screen_messages_disabled"]:
                unreal.SystemLibrary.execute_console_command(world, "DisableAllScreenMessages")
                state["screen_messages_disabled"] = True
            unreal.SystemLibrary.execute_console_command(world, "FOV %.9f" % job["hfov_deg"])
            unreal.EditorLevelLibrary.set_level_viewport_camera_info(job["location"], job["rotation"])
            state["ticks"] = 0
            state["phase"] = "settle"
            return
        if state["phase"] == "settle":
            state["ticks"] += 1
            if state["ticks"] < 8:
                return
            unreal.SystemLibrary.execute_console_command(
                world, "HighResShot 1600x900 filename=" + job["path"].replace("\\", "/"))
            state["issued_at"] = time.time()
            state["last_size"] = -1
            state["stable_ticks"] = 0
            state["phase"] = "wait_file"
            return
        if state["phase"] == "wait_file":
            size = os.path.getsize(job["path"]) if os.path.isfile(job["path"]) else -1
            if size > 1000 and size == state["last_size"]:
                state["stable_ticks"] += 1
            else:
                state["stable_ticks"] = 0
                state["last_size"] = size
            if state["stable_ticks"] >= 4:
                unreal.log("S3_BEACH_STILL_FILE|run=%s|shot=%s|bytes=%d|path=%s" %
                           (RUN, job["label"], size, job["path"].replace("\\", "/")))
                state["index"] += 1
                state["phase"] = "setup"
                return
            if time.time() - state["issued_at"] > 45.0:
                raise RuntimeError("CAPTURE_TIMEOUT|" + job["path"])
    except Exception:
        try:
            restore_viewport()
        finally:
            unreal.log_error("S3_BEACH_STILLS_FAIL|run=%s|traceback=%s|census=%s" %
                             (RUN, traceback.format_exc().replace("\n", "\\n"),
                              json.dumps(census(), separators=(",", ":"), sort_keys=True)))
            stop_callback()


builtins.PUSS_S3_BEACH_STILLS_HANDLE = unreal.register_slate_post_tick_callback(tick)
unreal.log("S3_BEACH_STILLS_STARTED|run=%s|shots=B02,B03|resolution=1600x900|camera_transform=world|screen_messages_off=1|exposure_override=0|landed=1" % RUN)
