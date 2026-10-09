"""Offline positive/negative controls for P42 p06_retime.py."""
from __future__ import annotations

import copy
import importlib.util
import math
import os


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p06_retime", os.path.join(HERE, "p06_retime.py"))
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class Checks:
    def __init__(self):
        self.count = 0

    def yes(self, value, label):
        self.count += 1
        if not value:
            raise AssertionError(label)

    def near(self, got, want, tol, label):
        self.yes(math.isclose(float(got), float(want), rel_tol=0.0, abs_tol=tol),
                 "%s: got %r want %r" % (label, got, want))


C = Checks()


def fixture():
    args = {
        "mode": "DRY", "confirm": "DRY P06 RETIME", "passage_label": R.P06_LABEL,
        "passage_guid": R.P06_GUID, "old_length_s": R.OLD_P06_SECONDS,
        "selected_music_s": R.SELECTED_MUSIC_SECONDS, "length_tolerance_s": 0.05,
        "review": {"plan_sha256": None}, "decided_by": "test",
    }
    sunset = {"animate": True, "cycle_duration_seconds": 1902.8571428571427,
              "cycle_rate_multiplier": 1.0, "entry_phase_offset_cycles": 0.7305555555555555}
    car = {"start_delay_seconds": 67.05, "travel_seconds": 3.0, "repeat_every_seconds": 0.0,
           "repeat_jitter_seconds": 0.0, "fade_in_seconds": 0.5, "fade_out_seconds": 0.9}
    bindings = []
    for i, (start, end) in enumerate(((2000, 2062), (2500, 2575), (2950, 3050))):
        bindings.append({"name": "%s%d @%.1fs" % (R.GLINT_PREFIX, i + 1, (80, 100, 118)[i]),
                         "spawn_keys": [[start, True], [end, False]], "spawn_range": [0, 3150],
                         "transform_ranges": [[0, 3150]],
                         "transform_defaults": [[['Location.X', 100.0 + i], ['Rotation.Z', 90.0]]]})
    bee = {"bindings": bindings, "fps": 25.0, "tick": 24000.0, "playback": [0, 3150],
           "subtrack_range": [0, 3150], "protected_choreo": [{"name": "CHAIN_A", "sections": []}]}
    expected_glints = [{"name": row["name"], "spawn_keys": row["spawn_keys"]} for row in bindings]
    live = {"p06_length_s": 110.6, "sunset": sunset, "car": car, "bee": bee, "fx": []}
    records = {
        "sunset": {"applied": True, "after": {"cycle": copy.deepcopy(sunset)}},
        "car": {"applied": {"start_delay_seconds": 67.05}, "settings": copy.deepcopy(car)},
        "bee": {"applied": True, "after": {"glints": expected_glints,
                                                "subtrack": {"range": [0, 3150]}}},
        "fx": {"status": "applied", "args": {"placements": [
            {"cue_label": "P06 Wing 052", "type": "Motes", "active_radius_cm": 2400.0},
            {"cue_label": "P06 Wing 044", "type": "WingBurn", "burn_start_ahead_cm": 3000.0,
             "burn_span_cm": 4000.0},
            {"cue_label": "P06 Wing 049", "type": "Fire", "active_radius_cm": 2200.0},
        ]}},
    }
    return args, live, records


def positive_controls():
    args, live, records = fixture()
    plan = R.build_plan(args, live, records)
    C.yes(not plan["refusals"], "baseline apply-ready")
    C.near(plan["scale"], 110.6 / R.OLD_P06_SECONDS, 1.0e-12, "live scale")
    C.near(plan["events"]["sunset_horizon"], 37.0 * plan["scale"], 1.0e-12, "dusk")
    C.near(plan["events"]["car_midpoint"], 68.55 * plan["scale"], 1.0e-12, "car midpoint")
    C.yes(plan["bee_after"]["bindings"][0]["spawn_keys"] == [[1756, True], [1810, False]],
          "bee display frames scale")
    C.yes(plan["bee_after"]["playback"] == [0, 2765], "owned playback follows live length")
    C.yes(plan["bee_after"]["protected_choreo"] == plan["bee_before"]["protected_choreo"],
          "topple/foreign choreo untouched")
    C.yes(plan["fx"]["retime"] is False and plan["fx"]["activation"] == "distance/view", "FX excluded")
    C.yes(len(plan["plan_sha256"]) == 64, "review hash")

    no_fx = copy.deepcopy(records)
    no_fx["fx"] = None
    C.yes(not R.build_plan(args, live, no_fx)["refusals"], "not-yet-applied FX set is a safe no-op")

    after = {"sunset": copy.deepcopy(plan["sunset_after"]), "car": copy.deepcopy(plan["car_after"]),
             "bee": copy.deepcopy(plan["bee_after"]), "fx": []}
    wanted = copy.deepcopy(after)
    after["sunset"]["cycle_duration_seconds"] += 5.0e-5
    C.yes(not R.state_matches(after, wanted), "float32 read-back tolerance")

    zeros = R.scaled_car(live["car"], plan["scale"])
    C.yes(zeros["repeat_every_seconds"] == 0.0 and zeros["repeat_jitter_seconds"] == 0.0,
          "disabled repeat remains disabled")
    C.yes(R.validate_args(args) == [], "DRY args valid")
    return 5


def negative_controls():
    args, live, records = fixture()

    old = copy.deepcopy(live)
    old["p06_length_s"] = R.OLD_P06_SECONDS
    C.yes(any(x.startswith("P33_NOT_APPLIED") for x in R.build_plan(args, old, records)["refusals"]),
          "refuse pre-P33 length")

    wrong = copy.deepcopy(live)
    wrong["p06_length_s"] = 109.0
    C.yes(any(x.startswith("P33_LENGTH_UNEXPECTED") for x in R.build_plan(args, wrong, records)["refusals"]),
          "refuse unknown new length")

    sun = copy.deepcopy(live)
    sun["sunset"]["entry_phase_offset_cycles"] += 0.1
    C.yes("SUNSET_DRIFT:entry_phase_offset_cycles" in R.build_plan(args, sun, records)["refusals"],
          "refuse sunset drift")

    missing_car = copy.deepcopy(records)
    missing_car["car"] = None
    C.yes("CAR_RECORD_MISSING_OR_INVALID" in R.build_plan(args, live, missing_car)["refusals"],
          "refuse missing car record")

    bees = copy.deepcopy(live)
    bees["bee"]["bindings"][2]["spawn_keys"][0][0] += 1
    C.yes("BEE_KEYS_DRIFT:2" in R.build_plan(args, bees, records)["refusals"], "refuse bee drift")

    timed_fx = copy.deepcopy(records)
    timed_fx["fx"]["args"]["placements"][0]["start_time_seconds"] = 69.0
    C.yes(any(x.startswith("FX_TIME_FIELD") for x in R.build_plan(args, live, timed_fx)["refusals"]),
          "refuse future time-keyed FX silently appearing")

    bad_confirm = copy.deepcopy(args)
    bad_confirm["confirm"] = "APPLY P06 RETIME"
    C.yes(any(x.startswith("CONFIRM_MISMATCH") for x in R.validate_args(bad_confirm)), "refuse wrong confirm")

    apply_args = copy.deepcopy(args)
    apply_args.update(mode="APPLY", confirm="APPLY P06 RETIME")
    C.yes("APPLY_REQUIRES_DRY_PLAN_SHA256" in R.validate_args(apply_args), "refuse unreviewed APPLY")

    drifted = {"sunset": copy.deepcopy(live["sunset"]), "car": copy.deepcopy(live["car"]),
               "bee": copy.deepcopy(live["bee"]), "fx": []}
    expected = copy.deepcopy(drifted)
    drifted["bee"]["protected_choreo"].append({"name": "CHAIN_B", "sections": []})
    C.yes("BEE" in R.state_matches(drifted, expected), "detect protected choreography drift")
    return 9


positive = positive_controls()
negative = negative_controls()
print("P06_RETIME_HARNESS_OK|positive=%d/%d|negative=%d/%d|checks=%d" %
      (positive, positive, negative, negative, C.count))
