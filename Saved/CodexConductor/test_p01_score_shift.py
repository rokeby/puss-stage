"""Offline controls for p01_score_shift.py.  No Unreal import is required."""

import sys

from p01_score_shift import ScoreShiftError, plan_score_shift, revert_rows_from_plan


RATE = 24000.0
START = 360000
TIMES = [0, 174240, 348480]  # 0.0, 7.26, 14.52 s
VALUES = {
    "Wing.InwardTravelScale": [0.5, 1.3, 1.0],
    "Wing.CycleRateScale": [0.6, 2.0, 1.0],
    "Wing.PhaseBiasCycles": [0.0, 1.0, 0.0],
}


def channels(times=None):
    actual_times = list(times or TIMES)
    return {
        name: [
            {"frame": frame, "sub_frame": 0.0, "value": value}
            for frame, value in zip(actual_times, values)
        ]
        for name, values in VALUES.items()
    }


def case(name, condition, detail=""):
    if condition:
        print("PASS %s" % name)
        return True
    print("FAIL %s: %s" % (name, detail))
    return False


def main():
    results = []
    plan = plan_score_shift(START, RATE, channels())
    results.append(
        case(
            "positive_constant_shift",
            plan["shift_tick"] == START
            and abs(plan["shift_s"] - 15.0) < 1.0e-12
            and all(rows[0]["frame"] == START for rows in plan["after"].values()),
            repr(plan),
        )
    )
    spacing_ok = all(
        [row["frame"] - rows[0]["frame"] for row in rows]
        == [0, 174240, 348480]
        for rows in plan["after"].values()
    )
    values_ok = all(
        [row["value"] for row in plan["after"][name]] == values
        for name, values in VALUES.items()
    )
    results.append(case("spacing_and_values_preserved", spacing_ok and values_ok))
    results.append(case("revert_round_trip", revert_rows_from_plan(plan) == plan["before"]))

    bad = channels()
    bad["Wing.PhaseBiasCycles"] = [dict(row) for row in bad["Wing.PhaseBiasCycles"]]
    for row in bad["Wing.PhaseBiasCycles"]:
        row["frame"] += 1
    refused = False
    message = ""
    try:
        plan_score_shift(START, RATE, bad)
    except ScoreShiftError as error:
        refused = "not the shared score times" in str(error) or "clean constant" in str(error)
        message = str(error)
    results.append(case("negative_non_constant_offset_refuses", refused, message))

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
