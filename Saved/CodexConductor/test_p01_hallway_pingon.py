"""Offline positive/negative controls for p01_hallway_pingon.py."""

import copy
import sys

from p01_hallway_pingon import plan_hallway_pingon, validate_plan


FPS = 30.0
MASTER_START = 0
MASTER_END = 1800
PASSAGE_START_S = 15.0
PASSAGE_END_S = 40.0
ENTRY_SPEED = 250.0


def light(cue, ordinal, intensity=1000.0):
    return {
        "attachment_guid": "%s-light-%d" % (cue, ordinal),
        "label": "%s Light %d" % (cue, ordinal),
        "intensity": intensity,
    }


BAYS = [
    {
        "cue_guid": "bay-%d" % index,
        "cue_label": "P01 Wing %03d" % index,
        "station_cm": 250.0 + (index - 1) * 600.0,
        "pass_s": PASSAGE_START_S + 1.0 + (index - 1) * 2.4,
        "lights": [light("bay-%d" % index, 1), light("bay-%d" % index, 2, 750.0)],
    }
    for index in range(1, 7)
]
ANCHORS = [(PASSAGE_START_S, 0.0)] + [
    (bay["pass_s"], bay["station_cm"]) for bay in BAYS
] + [(PASSAGE_END_S, 3900.0)]


def case(name, condition, detail=""):
    if condition:
        print("PASS %s" % name)
        return True
    print("FAIL %s: %s" % (name, detail))
    return False


def main():
    results = []
    plan = plan_hallway_pingon(
        bays=BAYS,
        anchors=ANCHORS,
        entry_speed_cm_s=ENTRY_SPEED,
        passage_end_s=PASSAGE_END_S,
        master_start_frame=MASTER_START,
        master_end_frame=MASTER_END,
        fps=FPS,
        trigger_distance_cm=600.0,
        flicker_min_s=0.10,
        flicker_max_s=0.30,
    )
    positive_failures = validate_plan(plan)
    results.append(case(
        "positive_route_order_pretrigger_dark_all_on",
        not positive_failures
        and plan["bays"][0]["trigger_s"] < PASSAGE_START_S
        and all(0.10 <= bay["duration_s"] <= 0.30 for bay in plan["bays"]),
        repr(positive_failures),
    ))

    out_of_order = copy.deepcopy(plan)
    out_of_order["bays"][1]["trigger_frame"], out_of_order["bays"][2]["trigger_frame"] = (
        out_of_order["bays"][2]["trigger_frame"], out_of_order["bays"][1]["trigger_frame"]
    )
    order_failures = validate_plan(out_of_order)
    results.append(case(
        "negative_route_order_detected",
        "route-order" in order_failures,
        repr(order_failures),
    ))

    early = copy.deepcopy(plan)
    early_bay = early["bays"][2]
    early_light = early_bay["lights"][0]
    early_light["keys"].append({
        "frame": early_bay["trigger_frame"] - 2,
        "value": early_light["intensity"] * 0.5,
    })
    early_failures = validate_plan(early)
    results.append(case(
        "negative_pretrigger_light_detected",
        any(item.startswith("pretrigger:") for item in early_failures),
        repr(early_failures),
    ))

    dark_end = copy.deepcopy(plan)
    final_light = dark_end["bays"][-1]["lights"][-1]
    final_light["keys"].append({
        "frame": dark_end["passage_end_frame"],
        "value": 0.0,
    })
    end_failures = validate_plan(dark_end)
    results.append(case(
        "negative_not_on_by_end_detected",
        any(item.startswith("not-on-by-end:") for item in end_failures),
        repr(end_failures),
    ))

    late = copy.deepcopy(plan)
    late["bays"][-1]["settle_frame"] = late["passage_end_frame"] + 1
    late_failures = validate_plan(late)
    results.append(case(
        "negative_late_settle_detected",
        any(item.startswith("settles-after-end:") for item in late_failures),
        repr(late_failures),
    ))

    print("P01_HALLWAY_OFFLINE_HARNESS|passed=%d|total=%d" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
