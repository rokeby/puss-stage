"""Read-only Flat V3 SK before/after stills; no save, spawn, or exposure override."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
    if _fv3_here not in _fv3_sys.path:
        _fv3_sys.path.insert(0, _fv3_here)

import json
import os
import time
import traceback

import unreal

import sk_common as c


POSES = {
    "P01": 0.0,
    "P02": 80000.0,
    "P03": 160000.0,
    "P04": 240000.0,
    "P05": 320000.0,
    "P06": 400000.0,
}
X_TARGET = 5250.0
Z_CAMERA = 500.0
CAPTURE_ROOT = os.path.join(c.HERE, "stills")
STATE = {"handle": None}


def classify(cfg):
    per_passage = {}
    for passage in POSES:
        rows = [row for row in cfg["rows"] if row["passage"] == passage]
        if not rows:
            raise RuntimeError("ST_PASSAGE_ROWS_MISSING|passage=" + passage)
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
                "ST_MI_STATE_MIXED|passage=%s|states=%s"
                % (passage, json.dumps(sorted(unique)))
            )
        per_passage[passage] = values[0]
    if len(set(per_passage.values())) != 1:
        raise RuntimeError("ST_PASSAGES_NOT_ONE_STATE|" + json.dumps(per_passage))
    return next(iter(per_passage.values())), per_passage


def make_jobs(vector_type):
    jobs = []
    for passage, centre_y in POSES.items():
        target = vector_type(X_TARGET, centre_y, Z_CAMERA)
        jobs.extend([
            {"passage": passage, "view": "front_on_pair",
             "location": vector_type(3250.0, centre_y, Z_CAMERA), "target": target},
            {"passage": passage, "view": "walking_camera_angle",
             "location": vector_type(3550.0, centre_y - 1300.0, Z_CAMERA), "target": target},
        ])
    return jobs


def actor_census(world):
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    return sorted(str(actor.get_path_name()) for actor in actors if actor is not None)


def stop():
    if STATE.get("handle") is not None:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        STATE["handle"] = None


def restore():
    world = STATE.get("world")
    if world is not None:
        unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
        unreal.SystemLibrary.execute_console_command(world, "viewmode lit")
    original = STATE.get("original_camera")
    if original:
        unreal.EditorLevelLibrary.set_level_viewport_camera_info(original[0], original[1])


def main(config_path=None):
    try:
        _editor, world = c.assert_context(clean=True)
        cfg = c.config(config_path)
        capture_state, passage_states = classify(cfg)
        jobs = make_jobs(unreal.Vector)
        output = os.path.join(CAPTURE_ROOT, capture_state)
        os.makedirs(output, exist_ok=True)
        for job in jobs:
            job["path"] = os.path.join(
                output,
                "%s_%s_%s.png" % (job["passage"], job["view"], capture_state),
            )
            if os.path.exists(job["path"]):
                raise RuntimeError("ST_OUTPUT_EXISTS|" + job["path"])
        STATE.update({
            "world": world,
            "jobs": jobs,
            "index": 0,
            "phase": "setup",
            "ticks": 0,
            "issued_at": 0.0,
            "last_size": -1,
            "stable": 0,
            "capture_state": capture_state,
            "passage_states": passage_states,
            "original_camera": unreal.EditorLevelLibrary.get_level_viewport_camera_info(),
            "actors_before": actor_census(world),
        })
        unreal.SystemLibrary.execute_console_command(world, "DisableAllScreenMessages")
        unreal.SystemLibrary.execute_console_command(world, "viewmode lit")

        def finish():
            restore()
            actors_after = actor_census(world)
            if actors_after != STATE["actors_before"]:
                raise RuntimeError("ST_ACTOR_CENSUS_CHANGED")
            final = c.census()
            if final != c.CLEAN:
                raise RuntimeError("ST_DIRTY_AFTER|" + json.dumps(final, sort_keys=True))
            files = [{"path": job["path"], "bytes": os.path.getsize(job["path"]),
                      "passage": job["passage"], "view": job["view"]} for job in jobs]
            if any(item["bytes"] <= 1000 for item in files):
                raise RuntimeError("ST_OUTPUT_TOO_SMALL")
            report = {
                "status": "PASS", "run": cfg["apply_run_id"], "state": capture_state,
                "shots": 12, "resolution": [3840, 2160], "lit_view": True,
                "screen_messages_during_capture": False, "exposure_override": False,
                "spawned_actors": False, "actor_census_unchanged": True,
                "saved_packages": [], "passage_states": passage_states,
                "files": files, "census": final,
            }
            path = c.write_report(
                "st_capture_%s_%s.json" % (capture_state, cfg["apply_run_id"]), report
            )
            unreal.log(
                "FLATV3_ST_STILLS_OK run=%s state=%s shots=12 exposure_override=false "
                "spawned_actors=false saved=0 actor_census_unchanged=true report=%s"
                % (cfg["apply_run_id"], capture_state, path)
            )
            stop()

        def tick(_delta):
            try:
                if STATE["index"] >= len(jobs):
                    finish()
                    return
                job = jobs[STATE["index"]]
                if STATE["phase"] == "setup":
                    rotation = unreal.MathLibrary.find_look_at_rotation(
                        job["location"], job["target"]
                    )
                    unreal.EditorLevelLibrary.set_level_viewport_camera_info(
                        job["location"], rotation
                    )
                    STATE["ticks"] = 0
                    STATE["phase"] = "settle"
                    return
                if STATE["phase"] == "settle":
                    STATE["ticks"] += 1
                    if STATE["ticks"] < 8:
                        return
                    unreal.SystemLibrary.execute_console_command(
                        world, "HighResShot 3840x2160 filename=" + job["path"].replace("\\", "/")
                    )
                    STATE.update({"issued_at": time.time(), "last_size": -1,
                                  "stable": 0, "phase": "wait"})
                    return
                size = os.path.getsize(job["path"]) if os.path.isfile(job["path"]) else -1
                if size > 1000 and size == STATE["last_size"]:
                    STATE["stable"] += 1
                else:
                    STATE["stable"], STATE["last_size"] = 0, size
                if STATE["stable"] >= 4:
                    STATE["index"] += 1
                    STATE["phase"] = "setup"
                elif time.time() - STATE["issued_at"] > 45.0:
                    raise RuntimeError("ST_CAPTURE_TIMEOUT|" + job["path"])
            except Exception:
                restore()
                stop()
                c.write_report(
                    "st_capture_%s_FAILURE.json" % cfg["apply_run_id"],
                    {"status": "FAIL", "traceback": traceback.format_exc(),
                     "saved_packages": [], "spawned_actors": False,
                     "exposure_override": False, "census": c.census()},
                )
                raise

        STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
        unreal.log(
            "FLATV3_ST_STILLS_STARTED run=%s state=%s shots=12 exposure_override=false "
            "spawned_actors=false saved=0"
            % (cfg["apply_run_id"], capture_state)
        )
    except Exception:
        if STATE.get("world") is not None:
            restore()
        stop()
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))

