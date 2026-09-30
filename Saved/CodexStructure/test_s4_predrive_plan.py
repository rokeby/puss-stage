"""Plain-Python positive and negative controls for s4_predrive_author_apply.plan_keys."""
import copy
import json
import os
import sys

from s4_predrive_author_apply import plan_keys


HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "specs", "fixture_s4_keys_1739.json")
W0, W1 = -5.874, 4.126


def fixture_before():
    with open(FIXTURE, encoding="utf-8") as handle:
        fixture = json.load(handle)
    intensity = {
        label: [[0.0, 0.0], [W1, max(float(value) for _time_s, value in keys)]]
        for label, keys in fixture["intensity"].items()
    }
    return {"intensity": intensity, "ppv_weight": [[0.0, 0.0], [W1, 1.0]]}


def main():
    before = fixture_before()
    failures = 0
    planned = plan_keys(before, W0, W1)
    positive = (
        planned["intensity"]["S4 Practical L1"] == [[-5.874, 0.0], [4.126, 400.0]]
        and planned["intensity"]["S4 Lattice Glow 1-1"] == [[-5.874, 0.0], [4.126, 20.0]]
        and planned["ppv_weight"] == [[-5.874, 0.0], [4.126, 1.0]]
    )
    if positive:
        print("PASS positive control: practical, glow and volume ramps start at W0")
    else:
        print("FAIL positive control: expected W0 ramps did not match")
        failures += 1

    try:
        plan_keys(before, 0.0, W1)
    except ValueError:
        print("PASS negative control a: FAIL observed as required (W0 >= 0 raised ValueError)")
    else:
        print("FAIL negative control a: W0 >= 0 did not raise")
        failures += 1

    unchanged = copy.deepcopy(before)
    if unchanged != planned:
        print("PASS negative control b: FAIL observed as required (unchanged before-state did not match expected)")
    else:
        print("FAIL negative control b: unchanged before-state unexpectedly matched expected")
        failures += 1

    wrong_plan = copy.deepcopy(planned)
    for keys in wrong_plan["intensity"].values():
        keys[0][0] = 0.0
    wrong_plan["ppv_weight"][0][0] = 0.0
    if wrong_plan != planned:
        print("PASS negative control c: FAIL observed as required (ramps left at 0 were detected)")
    else:
        print("FAIL negative control c: ramps left at 0 were not detected")
        failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
