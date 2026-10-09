"""Offline positive/negative harness for P52.  Does not import Unreal."""
from __future__ import annotations

import json
import math
import os
import sys
import unittest

import pendulum_core as C


HERE = os.path.dirname(os.path.abspath(__file__))
DT = 1.0 / 120.0
BASE = {
    "length_cm": 300.0,
    "damping_ratio": 0.12,
    "fixed_step_hz": 120.0,
    "idle_yaw_degrees": 2.5,
    "idle_pitch_degrees": 1.5,
    "idle_period_seconds": 7.0,
    "idle_phase_cycles": 0.0,
    "max_angle_degrees": 35.0,
    "decimation_error_degrees": 0.08,
}


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


class PendulumControls(unittest.TestCase):
    def test_positive_constant_speed_is_idle_only(self):
        result = C.simulate(constant_positions(), BASE)
        self.assertLess(result["max_motion_pitch_degrees"], 1.0e-9)
        self.assertLess(result["max_motion_yaw_degrees"], 1.0e-9)
        for t, pitch, yaw, _motion_pitch, _motion_yaw in result["dense"][::137]:
            phase = t * 2.0 * math.pi / BASE["idle_period_seconds"]
            self.assertAlmostEqual(pitch, BASE["idle_pitch_degrees"] * math.sin(phase + math.pi / 2.0), places=9)
            self.assertAlmostEqual(yaw, BASE["idle_yaw_degrees"] * math.sin(phase), places=9)

    def test_positive_braking_swings_forward_then_decays(self):
        cfg = dict(BASE, idle_pitch_degrees=0.0, idle_yaw_degrees=0.0)
        result = C.simulate(braking_positions(), cfg)
        during = [abs(row[3]) for row in result["dense"] if 3.0 <= row[0] <= 7.0]
        tail = [abs(row[3]) for row in result["dense"] if row[0] >= 14.0]
        self.assertGreater(max(during), 1.0)
        self.assertLess(max(tail), max(during) * 0.45)
        self.assertLess(result["max_motion_yaw_degrees"], 1.0e-9)

    def test_positive_rebuild_after_speed_change_differs_and_matches_fresh(self):
        first = C.simulate(constant_positions(speed=250.0), BASE)
        changed_positions = braking_positions(speed=250.0)
        rebuilt = C.simulate(changed_positions, BASE)
        fresh = C.simulate(changed_positions, BASE)
        self.assertNotEqual(first["keys"], rebuilt["keys"])
        self.assertEqual(rebuilt["keys"], fresh["keys"])
        old_fp = C.canonical_fingerprint({"speed_keys": [[0, 1.0], [100, 1.0]]})
        new_fp = C.canonical_fingerprint({"speed_keys": [[0, 1.0], [100, 0.0]]})
        self.assertNotEqual(old_fp, new_fp)

    def test_positive_decimation_is_error_bounded(self):
        result = C.simulate(braking_positions(), BASE)
        error = C.max_reconstruction_error(result["dense"], result["keys"])
        self.assertLessEqual(error, BASE["decimation_error_degrees"] + 1.0e-9)
        self.assertLess(len(result["keys"]), len(result["dense"]) // 3)

    def test_positive_fingerprint_is_order_stable(self):
        self.assertEqual(C.canonical_fingerprint({"a": 1, "b": [2, 3]}),
                         C.canonical_fingerprint({"b": [2, 3], "a": 1}))

    def test_negative_hand_edited_keys_refuse_rebuild(self):
        applied = [[100, 1.0, 2.0], [200, 2.0, 3.0]]
        hand_edited = [[100, 1.0, 2.0], [200, 2.0, 3.25]]
        self.assertFalse(C.drift_matches(applied, hand_edited))

    def test_negative_kick_without_cue_id_refuses(self):
        with self.assertRaisesRegex(C.PendulumError, "KICK_REQUIRES_CUE_ID"):
            C.validate_cue_kick(8.0, [])
        self.assertEqual(C.validate_cue_kick(8.0, ["cue-guid"])["cue_ids"], ["cue-guid"])

    def test_negative_non_finite_position_refuses(self):
        rows = constant_positions()
        rows[5][1] = float("nan")
        with self.assertRaisesRegex(C.PendulumError, "NON_FINITE"):
            C.simulate(rows, BASE)

    def test_negative_non_finite_config_refuses(self):
        with self.assertRaisesRegex(C.PendulumError, "NON_FINITE"):
            C.simulate(constant_positions(), dict(BASE, damping_ratio=float("inf")))

    def test_negative_variable_step_refuses(self):
        rows = constant_positions()
        rows[10][0] += 0.001
        with self.assertRaisesRegex(C.PendulumError, "FIXED_STEP_REQUIRED"):
            C.simulate(rows, BASE)


def write_preview(path):
    """Dependency-free PPM preview: braking response (red pitch, blue yaw)."""
    result = C.simulate(braking_positions(), BASE)
    width, height = 900, 360
    pixels = bytearray([248, 248, 244] * width * height)

    def point(t, value):
        return (int(round(t / result["dense"][-1][0] * (width - 1))),
                int(round(height / 2.0 - value / 12.0 * (height * 0.42))))

    def dot(x, y, color):
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                xx, yy = x + ox, y + oy
                if 0 <= xx < width and 0 <= yy < height:
                    offset = (yy * width + xx) * 3
                    pixels[offset:offset + 3] = bytes(color)

    for x in range(width):
        offset = ((height // 2) * width + x) * 3
        pixels[offset:offset + 3] = b"\xb4\xb4\xb4"
    for row in result["dense"]:
        dot(*point(row[0], row[1]), (190, 45, 45))
        dot(*point(row[0], row[2]), (45, 80, 190))
    with open(path, "wb") as handle:
        handle.write(("P6\n%d %d\n255\n" % (width, height)).encode("ascii"))
        handle.write(pixels)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PendulumControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    report = {"passed": passed, "failed": len(result.failures) + len(result.errors), "total": result.testsRun,
              "positive_controls": 5, "negative_controls": 5, "offline_only": True,
              "unreal_started": False, "blender_started": False}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    write_preview(os.path.join(HERE, "pendulum_braking_preview.ppm"))
    print("P52_PENDULUM_HARNESS|PASS=%d|FAIL=%d|TOTAL=%d" %
          (passed, report["failed"], result.testsRun))
    print("P52_PENDULUM_CONTROLS|POSITIVE=5|NEGATIVE=5|OFFLINE=1|UNREAL=0|BLENDER=0")
    sys.exit(1 if report["failed"] else 0)
