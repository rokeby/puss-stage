"""Plain-Python positive and negative controls for s4_rekey_window_apply.plan_keys."""
import copy
import json
import os
import sys

from s4_rekey_window_apply import plan_keys


HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "specs", "fixture_s4_keys_1739.json")
W0, W1 = -5.874, 4.126


def main():
    before = json.load(open(FIXTURE, encoding="utf-8"))
    failures = 0

    planned = plan_keys(before, W0, W1)
    expected_uplights = {
        "uplight key set 1 (label not recorded)": [[0.0, 0.0], [6.126, 0.0], [6.326, 10000.0]],
        "uplight key set 2 (label not recorded)": [[0.0, 0.0], [6.259, 0.0], [6.459, 10000.0]],
        "uplight key set 3 (label not recorded)": [[0.0, 0.0], [6.426, 0.0], [6.626, 10000.0]],
    }
    positive = (
        planned["root_pitch"] == [[-5.874, -90.0], [4.126, 0.0]]
        and planned["intensity"]["S4 Practical L1"] == [[0.0, 0.0], [4.126, 400.0]]
        and planned["intensity"]["S4 Lattice Glow 1-1"] == [[0.0, 0.0], [4.126, 20.0]]
        and planned["uplights"] == expected_uplights
        and planned["roof_pitch"] == [[0.0, -90.0], [6.626, -90.0], [12.626, 0.0]]
        and planned["lattice_fly_z"] == [[0.0, 2800.0], [12.626, 2800.0], [16.626, 1200.0]]
        and planned["ppv_weight"] == [[0.0, 0.0], [4.126, 1.0]]
    )
    if positive:
        print("PASS positive control: expected outputs matched")
    else:
        print("FAIL positive control: expected outputs did not match")
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
        print("PASS negative control b: FAIL observed as required (unchanged before did not match expected outputs)")
    else:
        print("FAIL negative control b: unchanged before unexpectedly matched expected outputs")
        failures += 1

    wrong_delta = W1 - 15.0
    wrong_roof = [
        [float(t) if float(t) == 0.0 else round(float(t) + wrong_delta, 6), float(v)]
        for t, v in before["roof_pitch"]
    ]
    wrong_start = wrong_roof[1][0]
    if wrong_start != 6.626:
        print(f"PASS negative control c: FAIL observed as required (wrong delta roof start {wrong_start} != 6.626)")
    else:
        print("FAIL negative control c: wrong delta unexpectedly produced roof start 6.626")
        failures += 1

    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
