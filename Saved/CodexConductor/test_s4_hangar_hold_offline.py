"""Offline harness for s4_hangar_hold.py pure functions (no Unreal). Each positive check has a negative control that
must FAIL the same check. Run: python Saved/CodexConductor/test_s4_hangar_hold_offline.py
Numbers: fold [0, 775), S4 playback [0, 4890) [meas klara_reveal_record_S4.json plan.lattice.facts / timeline];
tick 24000 at 25 fps -> 960 ticks/frame; lattice fly Z 2900 -> 1700 at 379 frames [meas hangar_resize_s4_record.json
key_plan]. Root pitch keys -90 -> 0 are SYNTHETIC."""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s4_hangar_hold as H  # noqa: E402  (import without unreal must run nothing)

TPF = 960
FOLD = {"range": [0, 775], "start_offset_tick": 0, "play_rate": 1.0}
PLAY = [0, 4890]
RISE_END = 775 * TPF


def chans(**over):
    c = {n: {"keys": [], "default": 1.0 if n.startswith("Scale") else 0.0} for n in H.CHANNELS}
    for k, v in over.items():
        c[k.replace("_", ".")] = v
    return c


def movers():
    return [
        {"binding": "S4 Hangar Root", "sections": [{"blend": "UNSET", "channels": chans(
            Rotation_Y={"keys": [[-141 * TPF, -90.0], [99 * TPF, 0.0]], "default": -90.0})}]},
        {"binding": "S4 Hangar Lattice Fly", "sections": [{"blend": "ABSOLUTE", "channels": chans(
            Location_X={"keys": [], "default": 3000.0},
            Location_Z={"keys": [[0, 2900.0], [259 * TPF, 2900.0], [379 * TPF, 1700.0]], "default": 2900.0})}]},
    ]


def refuses(fn, *a):
    try:
        fn(*a)
    except H.PlanError as exc:
        return str(exc)
    return None


class Plan(unittest.TestCase):
    def test_landed_values_and_range(self):
        p = H.plan_holds(FOLD, PLAY, TPF, RISE_END, movers())
        self.assertEqual(p["range"], [775, 4890])
        v = {t["binding"]: t["values"] for t in p["targets"]}
        self.assertEqual(v["S4 Hangar Root"]["Rotation.Y"], 0.0)          # landed, not REST -90
        self.assertEqual(v["S4 Hangar Lattice Fly"]["Location.Z"], 1700.0)
        self.assertEqual(v["S4 Hangar Lattice Fly"]["Location.X"], 3000.0)  # unkeyed -> default
        self.assertEqual(v["S4 Hangar Root"]["Scale.X"], 1.0)
        # control: a planner that used the FIRST key (REST) would differ
        self.assertNotEqual(v["S4 Hangar Root"]["Rotation.Y"], movers()[0]["sections"][0]["channels"]["Rotation.Y"]["keys"][0][1])

    def test_unsorted_keys_use_latest_time(self):
        m = movers()
        m[0]["sections"][0]["channels"]["Rotation.Y"]["keys"].reverse()
        self.assertEqual(H.plan_holds(FOLD, PLAY, TPF, RISE_END, m)["targets"][0]["values"]["Rotation.Y"], 0.0)

    def test_refusals(self):
        cases = {
            "FOLD_NOT_AT_ZERO": (dict(FOLD, range=[5, 775]), PLAY, RISE_END, movers()),
            "FOLD_START_OFFSET": (dict(FOLD, start_offset_tick=960), PLAY, RISE_END, movers()),
            "FOLD_PLAY_RATE": (dict(FOLD, play_rate=2.0), PLAY, RISE_END, movers()),
            "FOLD_NOT_WHOLE_RISE": (FOLD, PLAY, RISE_END + TPF, movers()),
            "NOTHING_UNCOVERED": (FOLD, [0, 775], RISE_END, movers()),
            "NO_TRANSFORM_MOVERS": (FOLD, PLAY, RISE_END, []),
        }
        for want, (f, pl, re_, mv) in cases.items():
            self.assertIn(want, refuses(H.plan_holds, f, pl, TPF, re_, mv) or "", want)
        m = movers(); m[1]["sections"][0]["blend"] = "ADDITIVE"
        self.assertIn("MOVER_NOT_ABSOLUTE", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); m[0]["sections"].append(copy.deepcopy(m[0]["sections"][0]))
        self.assertIn("MOVER_SECTIONS", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); m[0]["sections"][0]["channels"]["Rotation.Y"]["keys"].append([800 * TPF, 5.0])
        self.assertIn("KEY_AFTER_RISE_END", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); m[0]["sections"][0]["channels"]["Location.Z"] = {"keys": [], "default": None}
        self.assertIn("CHANNEL_UNKEYED_NO_DEFAULT", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); del m[0]["sections"][0]["channels"]["Scale.Z"]
        self.assertIn("MOVER_CHANNELS_MISSING", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers() + [movers()[0]]
        self.assertIn("DUPLICATE_MOVER", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        # control: the clean case refuses nothing
        self.assertIsNone(refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, movers()))


class Survey(unittest.TestCase):
    def test_short_and_covers(self):
        r = H.survey_row(4, PLAY, [{"range": [0, 775]}], 25.0)
        self.assertEqual((r["verdict"], r["uncovered_frames"], r["uncovered_s"]), ("SHORT", 4115, 164.6))
        c = H.survey_row(5, [0, 1225], [{"range": [0, 1225]}], 25.0)
        self.assertEqual((c["verdict"], c["uncovered_frames"]), ("COVERS", 0))
        self.assertEqual(H.survey_row(6, PLAY, [], 25.0)["verdict"], "NO_RISE_SUBSECTION")
        # S1 now 247.04 s = 6176 frames vs fold 775 [meas hookin dry; conductor]
        self.assertEqual(H.survey_row(1, [0, 6176], [{"range": [0, 775]}], 25.0)["verdict"], "SHORT")


class Args(unittest.TestCase):
    def test_args(self):
        with open(os.path.join(HERE, "s4_hangar_hold_args.json"), encoding="utf-8") as h:
            a = json.load(h)
        self.assertEqual(H.validate_args(a), [])                       # shipped file: DRY, valid
        self.assertEqual(a["mode"], "DRY")
        self.assertIn("SCENE_NOT_4 (S4-only tool)", H.validate_args(dict(a, scene=1)))
        self.assertIn("CONFIRM", H.validate_args(dict(a, mode="APPLY", decided_by="x")))
        self.assertIn("DECIDED_BY", H.validate_args(dict(a, mode="APPLY", confirm="APPLY S4HOLD")))
        self.assertEqual(H.validate_args(dict(a, mode="APPLY", confirm="APPLY S4HOLD", decided_by="x")), [])
        self.assertIn("CONFIRM", H.validate_args(dict(a, mode="REVERT", confirm="APPLY S4HOLD")))
        self.assertIn("COMPLETION", H.validate_args(dict(a, completion="WHATEVER")))


class Readback(unittest.TestCase):
    def test_diff(self):
        vals = {c: float(i) for i, c in enumerate(H.CHANNELS)}
        want = {"range": [775, 4890], "completion": "KEEP_STATE", "values": vals}
        got = {"range": [775, 4890], "completion": "KEEP_STATE", "values": dict(vals), "n_keys": 0}
        self.assertEqual(H.readback_diff(want, got), [])
        for mut in (lambda g: g.update(range=[775, 4889]), lambda g: g.update(completion="RESTORE_STATE"),
                    lambda g: g.update(n_keys=1), lambda g: g["values"].update({"Rotation.Y": 0.5}),
                    lambda g: g["values"].pop("Scale.Z")):
            g = copy.deepcopy(got)
            mut(g)
            self.assertTrue(H.readback_diff(want, g), "mutation not caught")

    def test_channel_base(self):
        self.assertEqual(H.channel_base("Location.Y_183"), "Location.Y")
        self.assertEqual(H.channel_base("Rotation.Z"), "Rotation.Z")


if __name__ == "__main__":
    unittest.main(verbosity=1)
