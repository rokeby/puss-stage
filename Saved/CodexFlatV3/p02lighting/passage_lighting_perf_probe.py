"""Read-only post-APPLY PIE frame-time gate for PASSAGELIGHT.

The conductor starts PIE at the chosen early/middle/late P02 review position,
then runs this hook. It never starts/stops PIE and never saves a package.
"""
import builtins
import datetime
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness
    unreal = None

HERE = (os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                     "CodexFlatV3", "p02lighting") if unreal is not None else os.path.dirname(__file__))
KEY = "PUSS_PASSAGE_LIGHTING_PERF_PROBE"


def require(condition, message):
    if not condition:
        raise RuntimeError(str(message))


def percentile(values, fraction):
    require(values, "NO_SAMPLES")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def summarise(values, args, run="offline", apply_run="offline"):
    require(values, "NO_SAMPLES")
    result = {"run": run, "apply_run": apply_run, "label": args["label"],
              "n": len(values), "mean_ms": sum(values) / len(values),
              "p50_ms": percentile(values, 0.50), "p95_ms": percentile(values, 0.95),
              "p99_ms": percentile(values, 0.99), "max_ms": max(values),
              "thresholds": {"max_p95_ms": float(args["max_p95_ms"]),
                             "max_p99_ms": float(args["max_p99_ms"])}}
    result["passed"] = (result["p95_ms"] <= result["thresholds"]["max_p95_ms"] and
                        result["p99_ms"] <= result["thresholds"]["max_p99_ms"])
    return result


def main():
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = datetime.datetime.now().strftime("PLFT-%Y%m%d-%H%M%S")
    with open(os.path.join(HERE, "passage_lighting_perf_probe_args.json"), encoding="utf-8") as handle:
        args = json.load(handle)
    with open(os.path.join(HERE, "passage_lighting_record.json"), encoding="utf-8") as handle:
        record = json.load(handle)
    require(record.get("status") == "saved_readback_verified", "APPLY_RECORD_NOT_READY")
    require(record.get("args", {}).get("target_passage") == "P02", "TARGET_NOT_P02")
    game_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    require(game_world is not None, "NO_PIE")
    require(getattr(builtins, KEY, None) is None, "ALREADY_RUNNING")
    seconds = float(args["seconds"])
    skip = int(args["skip_frames"])
    require(seconds > 0.0 and skip >= 0, "PROBE_ARGS_INVALID")
    state = {"run": run, "args": args, "apply_run": record.get("run"), "seen": 0,
             "elapsed": 0.0, "deltas_ms": []}

    def finish(st, error=None):
        try:
            unreal.unregister_slate_post_tick_callback(st["handle"])
        finally:
            if getattr(builtins, KEY, None) is not None:
                delattr(builtins, KEY)
        if error is not None:
            unreal.log_error("PASSAGELIGHT_PERF_FAILED|run=%s|reason=%s" % (st["run"], error))
            return
        result = summarise(st["deltas_ms"], args, st["run"], st["apply_run"])
        out = os.path.join(HERE, "passage_lighting_perf_%s.json" % st["run"])
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
        marker = "PASSAGELIGHT_PERF_OK" if result["passed"] else "PASSAGELIGHT_PERF_FAILED"
        log = unreal.log if result["passed"] else unreal.log_error
        log("%s|run=%s|apply_run=%s|n=%d|p95_ms=%.3f|p99_ms=%.3f|max_ms=%.3f|out=%s" %
            (marker, st["run"], st["apply_run"], result["n"], result["p95_ms"],
             result["p99_ms"], result["max_ms"], out))

    def tick(delta):
        st = getattr(builtins, KEY, None)
        if st is None:
            return
        try:
            st["seen"] += 1
            if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None:
                finish(st, "PIE_ENDED")
                return
            if st["seen"] <= skip:
                return
            st["deltas_ms"].append(float(delta) * 1000.0)
            st["elapsed"] += float(delta)
            if st["elapsed"] >= seconds:
                finish(st)
        except Exception as exc:  # always unhook on a callback fault
            finish(st, exc)

    setattr(builtins, KEY, state)
    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("PASSAGELIGHT_PERF_START|run=%s|apply_run=%s|seconds=%.1f|skip=%d" %
               (run, state["apply_run"], seconds, skip))


if unreal is not None:
    main()
