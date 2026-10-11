"""Offline positive/negative controls for Job 189."""

from pathlib import Path
import copy
import json

import job189_core as core


HERE = Path(__file__).resolve().parent
SCORES = json.loads((HERE / "warp_scores.json").read_text(encoding="utf-8"))
PASSED = 0
FAILED = 0


def check(label, condition):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print("PASS", label)
    else:
        FAILED += 1
        print("FAIL", label)


def rejects(label, fn, needle=""):
    try:
        fn()
    except (ValueError, KeyError) as exc:
        check(label, needle.lower() in str(exc).lower())
    else:
        check(label, False)


def main():
    args = core.validate_args({})
    check("DRY is default", args["mode"] == "DRY")
    check("proposal defaults", (args["preset"], args["move_seconds"], args["push_cm"]) == ("Both", 2.8, 240.0))
    rejects("bad mode negative", lambda: core.validate_args({"mode": "GO"}), "mode")
    rejects("bad run negative", lambda: core.validate_args({"run": "bad"}), "run")
    rejects("APPLY confirm negative", lambda: core.validate_args({"mode": "APPLY", "run": "J189-ABC"}), "confirm")
    rejects("REVERT record negative", lambda: core.validate_args({"mode": "REVERT", "run": "J189-ABC", "confirm": core.CONFIRM["REVERT"]}), "record")
    check("exact APPLY accepted", core.validate_args({"mode": "APPLY", "run": "J189-ABC", "confirm": core.CONFIRM["APPLY"]})["mode"] == "APPLY")
    rejects("push low negative", lambda: core.validate_args({"push_cm": 0}), "push")
    rejects("move high negative", lambda: core.validate_args({"move_seconds": 9}), "move")
    rejects("ease negative", lambda: core.validate_args({"ease_fraction": 0}), "ease")

    digests = set()
    for preset in core.PRESETS:
        rows = core.compile_score(SCORES, preset)
        check("%s rows valid" % preset, len(rows) == 7 and rows[0]["time"] == 0 and rows[-1]["time"] == 194)
        check("%s unit bounded" % preset, all(0 <= row[name] <= 1 for row in rows for name in core.UNIT_PARAMETERS))
        keys = core.score_keys(rows, 25.0)
        check("%s key census" % preset, set(keys) == set(core.PARAMETERS) and all(len(value) == 7 for value in keys.values()))
        check("%s climax after gentle" % preset, rows[4]["Weird"] > rows[1]["Weird"])
        digests.add(core.stable_digest(rows))
    check("three presets distinct", len(digests) == 3)

    bad = copy.deepcopy(SCORES)
    bad["presets"]["Both"][1]["time"] = 0.0
    rejects("duplicate time negative", lambda: core.compile_score(bad, "Both"), "strictly")
    bad = copy.deepcopy(SCORES)
    bad["presets"]["Both"][1]["Weird"] = 1.1
    rejects("range negative", lambda: core.compile_score(bad, "Both"), "[0, 1]")
    bad = copy.deepcopy(SCORES)
    bad["presets"]["Both"][1]["RenderTarget"] = 1
    rejects("unknown field negative", lambda: core.compile_score(bad, "Both"), "unknown")

    check("move frame plan", core.move_frames(100000, 24000, 2.8, 0.35) == [32800, 56320, 100000])
    rejects("move frame underflow negative", lambda: core.move_frames(10, 24000, 2.8, 0.35), "invalid")
    midpoint = core.evaluate_score(core.compile_score(SCORES, "Both"), 80.0)
    check("score interpolation", 0.30 < midpoint["Weird"] < 0.40)

    source = (HERE / "job189_s6_warp.py").read_text(encoding="utf-8")
    check("one MPC path", source.count('MPC_PATH = "/Game/InfinityStage/Effects/S6/MPC_S6Warp"') == 1)
    check("one material path", source.count('MATERIAL_PATH = "/Game/InfinityStage/Effects/S6/M_S6Warp_UI"') == 1)
    check("no render target API", "RenderTarget" not in source and "render_target" not in source)
    check("DRY does not call mutation branch", 'if args["mode"] == "DRY":\n            run_dry' in source)
    check("success markers", all(marker in source for marker in ("JOB189_DRY_OK", "JOB189_APPLY_OK", "JOB189_REVERT_OK")))
    check("named saves only", "save_all" not in source.lower())
    check("no deletion APIs", all(token not in source for token in ("delete_asset", "os.remove", "shutil.rmtree")))

    print("JOB189_OFFLINE_HARNESS|passed=%d|failed=%d|positive_and_negative=1" % (PASSED, FAILED))
    raise SystemExit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
