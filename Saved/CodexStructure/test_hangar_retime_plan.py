"""Plain-Python positive and negative controls for hangar_retime_apply.plan_scene."""
import copy
import json
import os
import sys

from hangar_retime_apply import (
    ROLE_KEYS,
    _state_mismatches,
    builder_beats_for_scene,
    plan_scene,
    target_state_from_records,
)


HERE = os.path.dirname(os.path.abspath(__file__))
RECORD_DIR = os.environ.get("HANGAR_RETIME_RECORD_DIR", HERE)


def load(name):
    with open(os.path.join(RECORD_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def arrival_root():
    rows = load("arrivals_record.json")["scenes"]
    row = next(item for item in rows if int(item["scene"]) == 3)
    return row["keys_new"]


def expect_raises(label, callback):
    try:
        callback()
    except ValueError as exc:
        print(f"PASS {label}: FAIL observed as required ({exc})")
        return 0
    print(f"FAIL {label}: expected ValueError was not raised")
    return 1


def main():
    rekey = load("s4_rekey_window_record.json")
    predrive = load("s4_predrive_author_record.json")
    W0, W1 = float(rekey["W0"]), float(rekey["W1"])
    beats = builder_beats_for_scene(3, arrival_root(), has_roof=True, has_exposure=False)
    before = {key: copy.deepcopy(beats[key]) for key in ROLE_KEYS}
    failures = 0

    planned = plan_scene(before, W0, W1, beats)
    expected = target_state_from_records(3, rekey, predrive, has_roof=True, has_exposure=False)
    bad = _state_mismatches(planned, expected, beats["fps"])
    if not bad:
        print("PASS positive: S3 builder-old state plans to recorded S4 applied state role for role")
    else:
        print(f"FAIL positive: planned S3 differs from recorded S4 roles: {bad}")
        failures += 1

    not_arrived = copy.deepcopy(before)
    not_arrived["root_pitch"] = [[0.0, -90.0], [1.0, -90.0], [16.0, 0.0]]
    failures += expect_raises(
        "negative a (arrivals not applied)",
        lambda: plan_scene(not_arrived, W0, W1, beats),
    )

    unknown = copy.deepcopy(before)
    unknown["unknown_binding"] = [[0.0, 0.0]]
    failures += expect_raises(
        "negative b (unknown binding)",
        lambda: plan_scene(unknown, W0, W1, beats),
    )

    double_shifted = copy.deepcopy(planned)
    shift = W1 - 16.0
    double_shifted["root_pitch"] = [[time_s + shift, value] for time_s, value in planned["root_pitch"]]
    double_bad = _state_mismatches(double_shifted, expected, beats["fps"])
    if "root_pitch" in double_bad:
        print("PASS negative c (root double-shift): FAIL observed as required (root_pitch mismatch detected)")
    else:
        print("FAIL negative c (root double-shift): shifted root was not detected")
        failures += 1

    failures += expect_raises(
        "negative d (W0 >= 0)",
        lambda: plan_scene(before, 0.0, W1, beats),
    )
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
