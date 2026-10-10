import copy
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("interaction_90b", os.path.join(HERE, "interaction_90b.py"))
T = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(T)


def channels(start=(0.0, -600.0, 500.0, 0.0, 0.0, 0.0)):
    return [{"base": name, "name": name + " (0)", "channel_index": i,
             "keys": [[0, value], [100, value + (100.0 if i == 1 else 0.0)], [200, value]]}
            for i, (name, value) in enumerate(zip(T.POSE, start))]


def snap(n):
    spots = [{"binding": "S%d Hangar Shadow Spot" % n, "side": "hangar", "keys": [[0, 0], [80, 1000], [300, 1000]],
              "max_intensity": 1000, "locator": ["A", 0, 0, 0]},
             {"binding": "I%d Mouth Shadow Spot" % n, "side": "mouth", "keys": [[0, 0], [80, 1000], [300, 1000]],
              "max_intensity": 1000, "locator": ["B", 0, 0, 0]}]
    return {"interaction": n, "cut": 300, "drop": 400, "playback": [0, 500],
            "mouth_transform": {"locator": ["M", 0, 0], "channels": channels()},
            "hangar_transform": {"locator": ["H", 0, 0], "channels": channels()},
            "mouth_drape": {"loc": [50, 0, 0], "yaw": 0}, "spots": spots}


class Planner(unittest.TestCase):
    def test_positive_enum_normalisation(self):
        self.assertEqual(T.enum_name("<LightUnits.CANDELAS: 1>"), "CANDELAS")

    def test_positive_channel_suffix(self):
        self.assertEqual(T.channel_base("Location.X (0)"), "Location.X")

    def test_positive_i2_preserves_before_cut_and_lands(self):
        s = snap(2); s["cut"] = 200; s["drop"] = 300
        target = {"x": 100, "y": 1000, "z": 600, "roll": 0, "pitch": 0, "yaw": 0}
        plan = T.plan_i2(s, target)
        self.assertEqual(plan["channels"]["Location.Y"][-1], [500, 1000.0])
        self.assertTrue(any(k[0] == 100 for k in plan["channels"]["Location.Y"]))
        self.assertEqual(plan["plane_result"], "crosses_plane")

    def test_positive_i2_live_target_lands_on_plane(self):
        s = snap(2); s["cut"] = 200; s["drop"] = 300
        target = {"x": 50, "y": 1000, "z": 600, "roll": 0, "pitch": 0, "yaw": 0}
        plan = T.plan_i2(s, target)
        self.assertEqual(plan["plane_result"], "lands_on_plane")
        self.assertEqual(plan["plane_distance"]["end"], 0.0)

    def test_negative_i2_not_through_plane(self):
        s = snap(2); s["cut"] = 200; s["drop"] = 300
        target = {"x": -100, "y": 1000, "z": 600, "roll": 0, "pitch": 0, "yaw": 0}
        with self.assertRaises(T.PlanError): T.plan_i2(s, target)

    def test_negative_i2_start_on_plane(self):
        s = snap(2); s["cut"] = 200; s["drop"] = 300
        for row in s["mouth_transform"]["channels"]:
            if row["base"] == "Location.X":
                row["keys"] = [[0, 50], [100, 50], [200, 50]]
        target = {"x": 100, "y": 1000, "z": 600, "roll": 0, "pitch": 0, "yaw": 0}
        with self.assertRaises(T.PlanError): T.plan_i2(s, target)

    def test_negative_i2_frame_order(self):
        with self.assertRaises(T.PlanError): T.rewrite_i2_channel([[0, 0]], 400, 300, 500, 1)

    def test_positive_i3_dark_move_then_spot(self):
        s = snap(3)
        for row in s["hangar_transform"]["channels"]:
            row["keys"][-1][1] = row["keys"][1][1]
        plan = T.plan_i3(s, {"hangar": 2000, "mouth": 2000}, 2, 25)
        self.assertEqual(plan["blackout"][0], [0, 1.0])
        self.assertGreater(plan["spot_start"], plan["settle"])
        self.assertEqual(plan["spots"][0]["after"][2][1], 2000.0)

    def test_negative_i3_no_move(self):
        s = snap(3)
        for row in s["hangar_transform"]["channels"]: row["keys"] = [[0, row["keys"][0][1]]]
        with self.assertRaises(T.PlanError): T.plan_i3(s, {}, 2, 25)

    def test_negative_i3_spot_after_cut(self):
        with self.assertRaises(T.PlanError): T.plan_i3(snap(3), {}, 2, 500)

    def test_positive_scene_tail_blackout(self):
        self.assertEqual(T.scene_tail_blackout([0, 100], 25), [[75, 0.0], [99, 1.0]])

    def test_negative_scene_tail_blackout(self):
        with self.assertRaises(T.PlanError): T.scene_tail_blackout([0, 100], 100)

    def test_positive_lighting_match(self):
        self.assertFalse(T.lighting_audit(snap(2))["pop"])

    def test_negative_lighting_pop(self):
        s = snap(2); s["spots"][1]["keys"] = [[0, 0], [300, 4000]]
        self.assertTrue(T.lighting_audit(s)["pop"])

    def test_negative_fix_shape(self):
        with self.assertRaises(T.PlanError): T.merged_params({"lighting_fix_steps": [{"interaction": 9}]})


class FakeBackend(object):
    def __init__(self, root): self.root, self.logs, self.state = root, [], "before"
    def log(self, text): self.logs.append(text)
    def fail(self, text): raise T.Stop(text)
    def census(self): return {"content": [], "maps": []}
    def preflight(self, mode, confirm):
        if confirm != T.CONFIRMS[mode]: raise T.Stop("CONFIRM")
    def build_report(self, params, run):
        body = {"params": params, "state": self.state}
        return {"input_digest": T.digest(body), "inputs": {"lighting": []}, "packages": [T.SEQS[2]]}
    def apply(self, report, run): self.state = "after"; return {"packages": report["packages"], "backup": "backup"}
    def revert(self, run): self.state = "before"; return {"packages": [T.SEQS[2]], "backup": "backup2", "archived": "record.reverted"}


class Contract(unittest.TestCase):
    def test_positive_dry_apply_revert(self):
        with tempfile.TemporaryDirectory() as root:
            b = FakeBackend(root); p = {"i2_enabled": True}
            T.main({"mode": "DRY", "confirm": T.CONFIRMS["DRY"], "run_id": "D", "params": p}, b)
            T.main({"mode": "APPLY", "confirm": T.CONFIRMS["APPLY"], "run_id": "A", "params": p}, b)
            T.main({"mode": "REVERT", "confirm": T.CONFIRMS["REVERT"], "run_id": "R", "params": p}, b)
            self.assertEqual(b.state, "before")

    def test_negative_confirm(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(T.Stop): T.main({"mode": "DRY", "confirm": "wrong"}, FakeBackend(root))

    def test_negative_state_drift(self):
        with tempfile.TemporaryDirectory() as root:
            b = FakeBackend(root); args = {"params": {}, "run_id": "D", "mode": "DRY", "confirm": T.CONFIRMS["DRY"]}
            T.main(args, b); b.state = "drift"; args.update({"mode": "APPLY", "confirm": T.CONFIRMS["APPLY"]})
            with self.assertRaises(T.Stop): T.main(args, b)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    print("INTERACTION_90B_HARNESS|pass=%d|fail=%d|total=%d" % (total - len(result.failures) - len(result.errors),
                                                                 len(result.failures) + len(result.errors), total))
    raise SystemExit(0 if result.wasSuccessful() else 1)
