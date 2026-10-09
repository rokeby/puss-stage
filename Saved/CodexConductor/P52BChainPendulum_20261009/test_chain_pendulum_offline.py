"""Offline positive/negative controls for P52b. Never imports Unreal."""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import unittest

import chain_pendulum_core as C


HERE = os.path.dirname(os.path.abspath(__file__))
DT = 1.0 / 240.0
CONFIG = {
    "damping_ratio": 0.10,
    "fixed_step_hz": 240.0,
    "idle_yaw_degrees": 0.0,
    "idle_pitch_degrees": 0.0,
    "idle_period_seconds": 7.0,
    "idle_phase_cycles": 0.0,
    "max_angle_degrees": 35.0,
    "decimation_error_degrees": 0.08,
    "null_link_mass_ratio": 0.05,
    "stability_guard": "refuse",
    "max_angular_velocity_degrees_s": 360.0,
}


def load_fixture():
    with open(os.path.join(HERE, "chandelier_chain_v1_fixture.json"), encoding="utf-8") as handle:
        return json.load(handle)


def one_link(length=300.0):
    return {"count": 1, "length_cm": length,
            "links": [{"index": 0, "pivot_cm": [0.0, 0.0, 0.0],
                       "length_cm": length, "mass_kg": None}],
            "body": {"attach_cm": [0.0, 0.0, -length], "mass_kg": 12.0}}


def constant_positions(seconds=12.0, speed=250.0):
    return [[i * DT, speed * i * DT, 0.0] for i in range(int(seconds / DT) + 1)]


def braking_positions(seconds=16.0, speed=250.0, brake_start=3.0, brake_duration=2.0):
    rows = []
    x = 0.0
    for i in range(int(seconds / DT) + 1):
        t = i * DT
        if t < brake_start:
            velocity = speed
        elif t < brake_start + brake_duration:
            velocity = speed * (1.0 - (t - brake_start) / brake_duration)
        else:
            velocity = 0.0
        if i:
            x += velocity * DT
        rows.append([t, x, 0.0])
    return rows


class ChainPendulumControls(unittest.TestCase):
    def test_positive_fixture_resolves_null_masses(self):
        schema = C.validate_schema(load_fixture(), 0.05)
        self.assertEqual(schema["count"], 3)
        self.assertEqual(len(schema["mass_inference"]["resolved"]), 3)
        self.assertTrue(all(abs(link["mass_kg"] - 0.6) < 1.0e-12 for link in schema["links"]))

    def test_positive_n1_is_exact_p52_reduction(self):
        positions = braking_positions()
        chain = C.simulate_chain(positions, one_link(), CONFIG)
        legacy_cfg = C.P52.check_config(dict(CONFIG, length_cm=300.0))
        legacy = C.P52.simulate(positions, legacy_cfg)
        self.assertEqual(chain["compatibility_mode"], "p52_exact_n1")
        self.assertEqual(chain["link_keys"][0], legacy["keys"])
        self.assertEqual(chain["body_keys"], legacy["keys"])

    def test_positive_braking_links_lag_and_body_follows_last(self):
        result = C.simulate_chain(braking_positions(), load_fixture(), CONFIG)
        link_peaks = []
        for dense in result["dense_links"]:
            post_brake = [row for row in dense if row[0] >= 3.0]
            link_peaks.append(max(post_brake, key=lambda row: abs(row[1])))
        self.assertGreater(len({round(row[1], 4) for row in link_peaks}), 1)
        self.assertGreaterEqual(link_peaks[-1][0], link_peaks[0][0])
        self.assertEqual(result["dense_body"], result["dense_links"][-1])
        self.assertGreater(max(abs(row[1]) for row in result["dense_body"]), 0.5)

    def test_positive_rebuild_after_speed_change_is_fresh_and_different(self):
        fixture = load_fixture()
        before = C.simulate_chain(constant_positions(), fixture, CONFIG)
        rebuilt = C.simulate_chain(braking_positions(), fixture, CONFIG)
        fresh = C.simulate_chain(braking_positions(), fixture, CONFIG)
        self.assertNotEqual(before["body_keys"], rebuilt["body_keys"])
        self.assertEqual(rebuilt["link_keys"], fresh["link_keys"])
        self.assertEqual(rebuilt["body_keys"], fresh["body_keys"])
        self.assertNotEqual(C.canonical_fingerprint({"speed": "constant"}),
                            C.canonical_fingerprint({"speed": "braking"}))

    def test_positive_decimation_and_stability_are_reported(self):
        result = C.simulate_chain(braking_positions(), load_fixture(), CONFIG)
        self.assertLessEqual(result["max_reconstruction_error_degrees"],
                             CONFIG["decimation_error_degrees"] + 1.0e-9)
        self.assertLessEqual(result["stability"]["dt_times_omega_max"], result["stability"]["limit"])
        self.assertEqual(result["stability"]["clipped_state_updates"], 0)

    def test_positive_explicit_clip_guard_reports_clips(self):
        config = dict(CONFIG, stability_guard="clip", max_angle_degrees=0.1,
                      max_angular_velocity_degrees_s=10.0)
        result = C.simulate_chain(braking_positions(speed=1000.0), load_fixture(), config)
        self.assertGreater(result["stability"]["clipped_state_updates"], 0)
        self.assertLessEqual(max(abs(row[1]) for dense in result["dense_links"] for row in dense),
                             config["max_angle_degrees"] + 1.0e-9)

    def test_negative_schema_violations_refuse(self):
        fixture = load_fixture()
        cases = []
        extra = copy.deepcopy(fixture); extra["unexpected"] = True; cases.append(extra)
        bad_count = copy.deepcopy(fixture); bad_count["count"] = 2; cases.append(bad_count)
        bad_index = copy.deepcopy(fixture); bad_index["links"][1]["index"] = 8; cases.append(bad_index)
        bad_geometry = copy.deepcopy(fixture); bad_geometry["body"]["attach_cm"][2] = -280.0; cases.append(bad_geometry)
        string_number = copy.deepcopy(fixture); string_number["length_cm"] = "300.0"; cases.append(string_number)
        bool_number = copy.deepcopy(fixture); bool_number["body"]["mass_kg"] = True; cases.append(bool_number)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaisesRegex(C.ChainPendulumError, "SCHEMA_"):
                    C.validate_schema(case)

    def test_negative_hand_edited_owned_keys_refuse_rebuild(self):
        recorded = {"link:0": [[100, 1.0, 2.0], [200, 2.0, 3.0]],
                    "body": [[100, 1.0, 2.0], [200, 2.0, 3.0]]}
        live = copy.deepcopy(recorded)
        live["link:0"][1][2] += 0.25
        self.assertFalse(C.drift_matches_tracks(recorded, live))

    def test_negative_non_finite_refuses(self):
        fixture = load_fixture()
        fixture["links"][0]["pivot_cm"][0] = float("nan")
        with self.assertRaisesRegex(C.ChainPendulumError, "NON_FINITE"):
            C.validate_schema(fixture)
        positions = braking_positions()
        positions[10][1] = float("inf")
        with self.assertRaisesRegex(C.ChainPendulumError, "NON_FINITE"):
            C.simulate_chain(positions, load_fixture(), CONFIG)

    def test_negative_unstable_dt_refuses_and_reports_dt(self):
        coarse = dict(CONFIG, fixed_step_hz=30.0)
        dt = 1.0 / coarse["fixed_step_hz"]
        rows = [[i * dt, 250.0 * i * dt, 0.0] for i in range(400)]
        tiny = load_fixture()
        for index, link in enumerate(tiny["links"]):
            link["length_cm"] = 1.0
            link["pivot_cm"] = [0.0, 0.0, -float(index)]
        tiny["length_cm"] = 3.0
        tiny["body"]["attach_cm"] = [0.0, 0.0, -3.0]
        with self.assertRaisesRegex(C.ChainPendulumError, r"STABILITY_DT\|dt="):
            C.simulate_chain(rows, tiny, coarse)


def write_preview(path):
    result = C.simulate_chain(braking_positions(), load_fixture(), CONFIG)
    width, height = 960, 420
    pixels = bytearray([248, 248, 244] * width * height)
    colors = ((185, 45, 45), (50, 145, 70), (45, 80, 190))
    duration = result["dense_body"][-1][0]

    def dot(x, y, color):
        if 0 <= x < width and 0 <= y < height:
            offset = (y * width + x) * 3
            pixels[offset:offset + 3] = bytes(color)

    for x in range(width):
        dot(x, height // 2, (175, 175, 175))
    for index, dense in enumerate(result["dense_links"]):
        for t, pitch, _yaw in dense:
            x = int(round(t / duration * (width - 1)))
            y = int(round(height / 2.0 - pitch / 16.0 * (height * 0.42)))
            dot(x, y, colors[index % len(colors)])
    with open(path, "wb") as handle:
        handle.write(("P6\n%d %d\n255\n" % (width, height)).encode("ascii"))
        handle.write(pixels)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ChainPendulumControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failed = len(result.failures) + len(result.errors)
    passed = result.testsRun - failed
    report = {"passed": passed, "failed": failed, "total": result.testsRun,
              "positive_controls": 6, "negative_controls": 4, "offline_only": True,
              "unreal_started": False, "blender_started": False}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    write_preview(os.path.join(HERE, "chain_braking_preview.ppm"))
    print("P52B_CHAIN_PENDULUM_HARNESS|PASS=%d|FAIL=%d|TOTAL=%d" % (passed, failed, result.testsRun))
    print("P52B_CHAIN_PENDULUM_CONTROLS|POSITIVE=6|NEGATIVE=4|OFFLINE=1|UNREAL=0|BLENDER=0")
    sys.exit(1 if failed else 0)
