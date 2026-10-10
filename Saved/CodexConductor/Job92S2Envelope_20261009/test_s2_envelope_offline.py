"""Offline +/- harness for job 92.  System Python only; writes no project state."""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s2_envelope_core as C  # noqa: E402

ARGS = json.load(open(os.path.join(HERE, "s2_envelope_args.json"), encoding="utf-8"))


def row(label, loc=(3000, 0, 1000), scale=(1, 1, 1)):
    return {"label": label, "root_local": list(loc), "scale": list(scale)}


class Proposal(unittest.TestCase):
    def test_offline_pivot_envelope_requires_widening(self):
        # Measured from s2v3_overlay_record.json: pivots y -1504..1851, ceiling pivot z 1640.
        p = C.proposal({"min": [1041, -1504, -1], "max": [4595, 1851, 1640]})
        self.assertEqual(p["half_width_cm"], 2500.0)
        self.assertEqual(p["height_cm"], 4700.0)
        self.assertFalse(C.contains({"min": [1041, -1504, 0], "max": [4595, 1851, 1640]}, 1000, 3000, 300, 300))

    def test_pass1_measured_bounds_drive_full_rig_envelope(self):
        measured = {"min": [-2931.035294114732, -7868.034872621067, -1207.990478515625],
                    "max": [13059.035199321967, 8122.035620815632, 13711.0]}
        p = C.proposal(measured)
        self.assertEqual(p, {"half_width_cm": 8500.0, "height_cm": 16000.0,
                             "lattice_landed_z_cm": 14100.0, "lattice_rest_z_cm": 15700.0,
                             "content_clearance_side_cm": 300.0,
                             "content_clearance_top_cm": 300.0})
        self.assertTrue(C.contains(measured, p["half_width_cm"], p["height_cm"], 300, 300))
        self.assertTrue(C.rig_clear(measured, p["lattice_landed_z_cm"],
                                    p["lattice_rest_z_cm"], p["height_cm"], 300))

    def test_bounds_gate_positive_and_negative(self):
        b = {"min": [500, -2100, 0], "max": [5000, 2150, 3900]}
        self.assertTrue(C.contains(b, 2500, 4500, 300, 300))
        self.assertFalse(C.contains(b, 2400, 4500, 300, 300))
        self.assertFalse(C.contains(b, 2500, 4100, 300, 300))

    def test_rig_and_roof_clearance_positive_and_negative(self):
        b = {"min": [500, -2100, 0], "max": [5000, 2150, 2400]}
        self.assertTrue(C.rig_clear(b, 2800, 4200, 4500, 300))
        self.assertFalse(C.rig_clear(b, 2600, 4200, 4500, 300))
        self.assertFalse(C.rig_clear(b, 2800, 4300, 4500, 300))

    def test_rounding_control(self):
        self.assertEqual(C.round_up(2151, 100), 2200)
        self.assertNotEqual(C.round_up(2151, 100), 2151)


class Actors(unittest.TestCase):
    def test_side_wall_height_and_width(self):
        got = C.target_actor(row("S2 Hangar Left Wall", (3000, -1025, 1500), (60, .5, 30)), ARGS["old"], ARGS["new"])
        self.assertEqual(got["root_local"], [3000, -8525.0, 8000.0])
        self.assertEqual(got["scale"][2], 160.0)
        self.assertNotEqual(got["scale"][2], 30.0)  # negative control: unchanged wall is wrong

    def test_floor_and_apron_widen(self):
        for label in ("S2 Hangar Floor 1", "S2 Hangar Apron"):
            got = C.target_actor(row(label, scale=(20, 20, .2)), ARGS["old"], ARGS["new"])
            self.assertEqual(got["scale"][1], 170.0)
            self.assertNotEqual(got["scale"][0], 50.0)

    def test_lattice_rises(self):
        got = C.target_actor(row("S2 Hangar Lattice Fly", (3000, 0, 1200)), ARGS["old"], ARGS["new"])
        self.assertEqual(got["root_local"][2], 14100.0)
        self.assertNotEqual(got["root_local"][2], 1200.0)

    def test_roof_hinge_rises(self):
        got = C.target_actor(row("S2 Hangar Roof Hinge", (6025, 0, 3000)), ARGS["old"], ARGS["new"])
        self.assertEqual(got["root_local"][2], 16000.0)

    def test_exit_opening_stays_300cm(self):
        left = C.target_actor(row("S2 Hangar Far Wall Left of Exit", (6025, -600, 225), (.5, 9, 4.5)), ARGS["old"], ARGS["new"])
        right = C.target_actor(row("S2 Hangar Far Wall Right of Exit", (6025, 600, 225), (.5, 9, 4.5)), ARGS["old"], ARGS["new"])
        half_piece = left["scale"][1] * 100 / 2
        inner_gap = right["root_local"][1] - half_piece - (left["root_local"][1] + half_piece)
        self.assertAlmostEqual(inner_gap, 300.0)
        self.assertNotAlmostEqual(inner_gap, 750.0)  # naïve 2.5x scale would widen the door


class KeysAndIdentity(unittest.TestCase):
    def test_lattice_values_only(self):
        self.assertEqual(C.remap_value(1200, 1200, 2800, 2800, 4200), 2800)
        self.assertEqual(C.remap_value(2800.00001, 1200, 2800, 2800, 4200), 4200)

    def test_unmapped_key_refuses(self):
        with self.assertRaises(ValueError):
            C.remap_value(2000, 1200, 2800, 2800, 4200)

    def test_enum_normalisation(self):
        self.assertEqual(C.enum_name("<MovieSceneBlendType.ABSOLUTE: 0>"), "ABSOLUTE")
        self.assertNotEqual(C.enum_name("<MovieSceneBlendType.ABSOLUTE: 0>"), "<MovieSceneBlendType.ABSOLUTE: 0>")

    def test_digest_detects_drift(self):
        p = {"actors": [{"label": "A", "x": 1}], "keys": [[0, 2800]]}
        self.assertEqual(C.plan_digest(p), C.plan_digest(copy.deepcopy(p)))
        q = copy.deepcopy(p); q["keys"][0][1] = 2801
        self.assertNotEqual(C.plan_digest(p), C.plan_digest(q))


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=1).result
    print("S2_ENVELOPE_HARNESS|tests=%d|failures=%d|errors=%d|positive_and_negative_controls=1" %
          (result.testsRun, len(result.failures), len(result.errors)))
    sys.exit(0 if result.wasSuccessful() else 1)
