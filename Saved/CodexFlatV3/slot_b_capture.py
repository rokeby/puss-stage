"""Capture three P04 views in lit and unlit modes without spawning actors."""
import json
import importlib
import os
import sys
import time
import traceback
import unreal

BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3"))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
import slot_b_common as c
c = importlib.reload(c)
import slot_b_revert

CAPTURE_DIR = os.path.join(BASE, "captures")
state = {"handle": None, "released": False}


def release_failure(reason):
    if state["released"]:
        return
    state["released"] = True
    saved = []
    try:
        saved = slot_b_revert.revert(reason)
    except Exception as revert_exc:
        reason += "|REVERT_FAIL:" + str(revert_exc)
    c.log_release("FAIL", saved, reason)


try:
    editor, world = c.assert_context(clean=True)
    verify = c.read_json("slot_b_verify_%s.json" % c.RUN)
    if verify.get("status") != "PASS" or verify.get("dirty_after") != {"content": [], "maps": []}:
        raise RuntimeError("VERIFY_REPORT_NOT_PASS")
    plan = c.read_json("slot_b_capture_plan_%s.json" % c.RUN)
    if plan.get("exposure_override") is not False or plan.get("spawned_actors") is not False:
        raise RuntimeError("CAPTURE_PLAN_CONTRACT_FAIL")
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    jobs = []
    for mode in plan["modes"]:
        for pose in plan["poses"]:
            name = "flatv3_P04_%s_%s_%s.png" % (pose["name"], c.RUN, mode)
            path = os.path.join(CAPTURE_DIR, name)
            if os.path.exists(path):
                raise RuntimeError("CAPTURE_OUTPUT_EXISTS|" + path)
            jobs.append({"mode": mode, "pose": pose["name"],
                         "location": unreal.Vector(*pose["location"]), "path": path})
    target = unreal.Vector(*plan["target"])
    original_camera = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
    state.update({"index": 0, "phase": "setup", "ticks": 0, "issued_at": 0.0,
                  "last_size": -1, "stable_ticks": 0, "world": world,
                  "jobs": jobs, "target": target, "original_camera": original_camera})

    def restore_viewport():
        unreal.SystemLibrary.execute_console_command(world, "viewmode lit")
        if original_camera:
            unreal.EditorLevelLibrary.set_level_viewport_camera_info(original_camera[0], original_camera[1])

    def stop_callback():
        if state.get("handle") is not None:
            unreal.unregister_slate_post_tick_callback(state["handle"])
            state["handle"] = None

    def finish_success():
        restore_viewport()
        final_census = c.census()
        if final_census != {"content": [], "maps": []}:
            raise RuntimeError("CAPTURE_DIRTY_AFTER|" + json.dumps(final_census, sort_keys=True))
        files = [{"path": job["path"], "bytes": os.path.getsize(job["path"]),
                  "viewmode": job["mode"], "pose": job["pose"]} for job in jobs]
        report = {"run": c.RUN, "status": "PASS", "views": 3, "files": files,
                  "lit_unlit_pairs": True, "exposure_override": False,
                  "spawned_actors": False, "final_census": final_census}
        path = c.write_json("slot_b_captures_%s.json" % c.RUN, report)
        unreal.log("FLATV3_B_CAPTURES_OK run=%s views=3 files=6 lit_unlit=true exposure_override=false spawned_actors=false census=%s report=%s" %
                   (c.RUN, json.dumps(final_census, separators=(",", ":"), sort_keys=True), path))
        stop_callback()

    def tick(_delta_seconds):
        try:
            if state["index"] >= len(jobs):
                finish_success()
                return
            job = jobs[state["index"]]
            if state["phase"] == "setup":
                unreal.SystemLibrary.execute_console_command(world, "viewmode " + job["mode"])
                rotation = unreal.MathLibrary.find_look_at_rotation(job["location"], target)
                unreal.EditorLevelLibrary.set_level_viewport_camera_info(job["location"], rotation)
                state["ticks"] = 0
                state["phase"] = "settle"
                return
            if state["phase"] == "settle":
                state["ticks"] += 1
                if state["ticks"] < 8:
                    return
                unreal.SystemLibrary.execute_console_command(
                    world, "HighResShot 1920x1080 filename=" + job["path"].replace("\\", "/"))
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
                    unreal.log("FLATV3_B_CAPTURE_FILE run=%s pose=%s mode=%s bytes=%d path=%s" %
                               (c.RUN, job["pose"], job["mode"], size, job["path"]))
                    state["index"] += 1
                    state["phase"] = "setup"
                    return
                if time.time() - state["issued_at"] > 30.0:
                    raise RuntimeError("CAPTURE_TIMEOUT|" + job["path"])
        except Exception as exc:
            reason = "capture:" + str(exc)
            try:
                restore_viewport()
            finally:
                stop_callback()
            c.write_json("slot_b_captures_%s_FAILURE.json" % c.RUN,
                         {"run": c.RUN, "status": "FAIL", "reason": reason,
                          "traceback": traceback.format_exc(), "census": c.census()})
            release_failure(reason)

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("FLATV3_B_CAPTURE_STARTED run=%s views=3 files=6 lit_unlit=true exposure_override=false spawned_actors=false" % c.RUN)
except Exception as exc:
    reason = "capture_start:" + str(exc)
    c.write_json("slot_b_captures_%s_FAILURE.json" % c.RUN,
                 {"run": c.RUN, "status": "FAIL", "reason": reason,
                  "traceback": traceback.format_exc(), "census": c.census()})
    release_failure(reason)
