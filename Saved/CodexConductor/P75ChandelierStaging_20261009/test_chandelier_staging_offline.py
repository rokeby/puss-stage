from __future__ import annotations

import importlib.util
import json
import os
import py_compile
from typing import Callable


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p75_core", os.path.join(HERE, "chandelier_staging_core.py"))
CORE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CORE)


def _args() -> dict:
    with open(os.path.join(HERE, "chandelier_staging_args.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _fails(fn: Callable[[], object], token: str) -> None:
    try:
        fn()
    except CORE.P75Error as error:
        assert token in str(error), (token, str(error))
        return
    raise AssertionError("expected failure: " + token)


def main() -> None:
    tests: list[tuple[str, str, Callable[[], None]]] = []

    def add(kind: str, name: str, fn: Callable[[], None]) -> None:
        tests.append((kind, name, fn))

    def positive_plan() -> None:
        plan = CORE.build_plan(_args())
        assert plan["opening"]["drive_by"]["passes"] == 1
        assert plan["lights"]["grouped_count"] == 4
        assert plan["lights"]["shadow_casters"] == 2
        assert plan["p06"]["new_sound"] is False

    def positive_hidden() -> None:
        plan = CORE.build_plan(_args())
        CORE.verify_hidden_shadow(plan["opening"]["body"], plan["opening"]["chain"])

    def positive_order() -> None:
        one = CORE.seeded_candle_order(44, 7501)
        two = CORE.seeded_candle_order(44, 7501)
        assert one == two and len(one) == 44 and len({row["draw"] for row in one}) == 44

    def positive_shadow() -> None:
        shadow = CORE.build_plan(_args())["opening"]["projected_shadow_at_peak"]
        assert abs(shadow["width_cm"] - 331.57894736842104) < 1.0e-9
        assert abs(shadow["height_cm"] - 243.1578947368421) < 1.0e-9

    def positive_clearance() -> None:
        plan = CORE.build_plan(_args())
        assert plan["p06"]["clearances_cm"] == {"nearest_topple_row": 3750.0,
                                                   "nearest_wing_station": 550.0}

    def positive_hash() -> None:
        a = CORE.build_plan(_args())["plan_sha256"]
        raw = _args(); raw["confirm"] = "anything"; raw["reviewed_plan_sha256"] = "ignored"
        assert CORE.build_plan(raw)["plan_sha256"] == a

    add("POSITIVE", "plan", positive_plan)
    add("POSITIVE", "hidden-shadow flags", positive_hidden)
    add("POSITIVE", "seeded single-draw order", positive_order)
    add("POSITIVE", "projected shadow", positive_shadow)
    add("POSITIVE", "P06 clearances", positive_clearance)
    add("POSITIVE", "stable plan hash", positive_hash)
    add("NEGATIVE", "GPU light cap", lambda: _fails(lambda: CORE.build_plan({**_args(), "grouped_light_count": 5}), "GPU_LIGHT_CAP_4"))
    add("NEGATIVE", "GPU shadow cap", lambda: _fails(lambda: CORE.build_plan({**_args(), "shadow_caster_count": 3}), "GPU_SHADOW_CAP_2"))
    add("NEGATIVE", "hidden shadow flag", lambda: _fails(lambda: CORE.verify_hidden_shadow(
        {"hidden_in_game": True, "cast_hidden_shadow": False},
        {"hidden_in_game": True, "cast_hidden_shadow": True}), "BODY_NO_HIDDEN_SHADOW"))
    add("NEGATIVE", "topple overlap", lambda: _fails(lambda: CORE.build_plan({**_args(), "p06_hang_station_cm": 9450.0}), "TOPPLE_ROW_OVERLAP"))
    add("NEGATIVE", "socket count", lambda: _fails(lambda: CORE.build_plan({**_args(), "socket_count": 43}), "SOCKET_COUNT_44_REQUIRED"))
    add("NEGATIVE", "APPLY confirm", lambda: _fails(lambda: CORE.build_plan({**_args(), "mode": "APPLY"}), "CONFIRM"))
    add("NEGATIVE", "stale APPLY review hash", lambda: _fails(lambda: CORE.build_plan(
        {**_args(), "mode": "APPLY", "confirm": "APPLY P75 CHANDELIER",
         "reviewed_plan_sha256": "stale"}), "REVIEWED_PLAN_HASH"))

    passed, failed, details = 0, 0, []
    for kind, name, fn in tests:
        try:
            fn(); passed += 1; details.append({"kind": kind, "name": name, "ok": True})
        except Exception as error:  # noqa: BLE001 - harness must retain each exact failure.
            failed += 1; details.append({"kind": kind, "name": name, "ok": False, "error": repr(error)})

    for filename in ("chandelier_staging_core.py", "chandelier_staging.py", "chandelier_staging_run.py",
                     "make_timeline_previews.py", "test_chandelier_staging_offline.py"):
        py_compile.compile(os.path.join(HERE, filename), doraise=True)
    plan = CORE.build_plan(_args())
    with open(os.path.join(HERE, "p75_offline_plan.json"), "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, sort_keys=True)
    result = {"pass": passed, "fail": failed, "total": len(tests),
              "positive": sum(1 for kind, _, _ in tests if kind == "POSITIVE"),
              "negative": sum(1 for kind, _, _ in tests if kind == "NEGATIVE"),
              "offline": True, "unreal": False, "blender": False, "details": details}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
    line = "P75_CHANDELIER_HARNESS|PASS=%d|FAIL=%d|TOTAL=%d|POSITIVE=%d|NEGATIVE=%d|OFFLINE=1|UNREAL=0|BLENDER=0" % (
        passed, failed, len(tests), result["positive"], result["negative"])
    with open(os.path.join(HERE, "harness_result.txt"), "w", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
