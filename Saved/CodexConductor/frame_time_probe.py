"""READ-ONLY frame-time probe for a PIE session (5 Oct: P04 shadow cost, Gary's bedtime approval).

Collects the editor's per-frame delta for FT_SECONDS from a Slate post-tick callback, then logs
FRAME_TIME_PROBE_OK|run=..|label=..|n=..|mean_ms=..|p50_ms=..|p95_ms=..|p99_ms=..|max_ms=..
It changes nothing, never starts or ends PIE, never saves. Refuses without a PIE world.
Inputs (runpy init_globals or frame_time_probe_args.json): FT_LABEL, FT_SECONDS (default 20), FT_SKIP (default 30 frames).
The callback handle lives in builtins (never a UE wrapper in module globals: that crashed the editor before).
"""
import builtins
import datetime
import json
import os

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
KEY = "PUSS_FRAME_TIME_PROBE"


def _args():
    path = HERE + "frame_time_probe_args.json"
    a = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return (str(globals().get("FT_LABEL", a.get("label", "unlabelled"))),
            float(globals().get("FT_SECONDS", a.get("seconds", 20.0))),
            int(globals().get("FT_SKIP", a.get("skip", 30))))


def pct(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def summary(deltas_s):
    ms = sorted(d * 1000.0 for d in deltas_s)
    return {"n": len(ms), "mean_ms": sum(ms) / len(ms) if ms else float("nan"), "p50_ms": pct(ms, 0.5),
            "p95_ms": pct(ms, 0.95), "p99_ms": pct(ms, 0.99), "max_ms": ms[-1] if ms else float("nan")}


def main():
    run = datetime.datetime.now().strftime("FT-%Y%m%d-%H%M%S")
    label, seconds, skip = _args()
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None:
        unreal.log_error("FRAME_TIME_PROBE_FAILED|run=%s|reason=NO_PIE" % run)
        raise RuntimeError("FRAME_TIME_PROBE_FAILED|NO_PIE")
    old = getattr(builtins, KEY, None)
    if old is not None:
        unreal.log_error("FRAME_TIME_PROBE_FAILED|run=%s|reason=ALREADY_RUNNING|%s" % (run, old.get("run")))
        raise RuntimeError("FRAME_TIME_PROBE_FAILED|ALREADY_RUNNING")
    state = {"run": run, "label": label, "seconds": seconds, "skip": skip, "deltas": [], "stamps": [], "elapsed": 0.0, "seen": 0}

    def tick(delta):
        st = getattr(builtins, KEY, None)
        if st is None:
            return
        try:
            st["seen"] += 1
            if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None:
                raise RuntimeError("PIE_ENDED")
            if st["seen"] <= st["skip"]:
                return
            st["deltas"].append(float(delta))
            st["stamps"].append(datetime.datetime.utcnow().strftime("%Y.%m.%d-%H.%M.%S:%f")[:-3])
            st["elapsed"] += float(delta)
            if st["elapsed"] >= st["seconds"]:
                unreal.unregister_slate_post_tick_callback(st["handle"])
                delattr(builtins, KEY)
                s = summary(st["deltas"])
                out = HERE + "frame_time_probe_%s.json" % st["run"]
                json.dump(dict(s, run=st["run"], label=st["label"], frames=list(zip(st["stamps"], st["deltas"]))), open(out, "w", encoding="utf-8"))
                unreal.log("FRAME_TIME_PROBE_OK|run=%s|label=%s|n=%d|mean_ms=%.2f|p50_ms=%.2f|p95_ms=%.2f|p99_ms=%.2f|max_ms=%.2f|out=%s"
                           % (st["run"], st["label"], s["n"], s["mean_ms"], s["p50_ms"], s["p95_ms"], s["p99_ms"],
                              s["max_ms"], out))
        except Exception as exc:  # noqa: BLE001 -- always unhook, report, never leave a callback behind
            try:
                unreal.unregister_slate_post_tick_callback(st["handle"])
            finally:
                if getattr(builtins, KEY, None) is not None:
                    delattr(builtins, KEY)
            unreal.log_error("FRAME_TIME_PROBE_FAILED|run=%s|reason=%s" % (st["run"], exc))

    setattr(builtins, KEY, state)
    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("FRAME_TIME_PROBE_START|run=%s|label=%s|seconds=%.1f|skip=%d" % (run, label, seconds, skip))


main()
