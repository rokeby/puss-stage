"""Offline harness for hangar_resize_s4.py (system Python, no Unreal). Every positive check has a negative control
that must FAIL the same check. Synthetic "live" hangars are built from hangar_resize_s4_targets.json's OLD poses
(themselves hangar_build.py plan_for, by AST) in the four live states (fly rest/landed x roof flat/upright).
Also checks the 7 Oct klara args edits: S4-only, S1 subtrees identical to git HEAD, and klara_reveal.py's per-Scene
placement override (S4 lead_max) does not reach S1. Run: python Saved/CodexStructure/test_hangar_resize_s4_offline.py
"""
import copy
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hangar_resize_s4 as H  # noqa: E402  (importing without unreal runs nothing)

KLARA = os.path.join(HERE, "..", "CodexConductor", "KlaraIngest")
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
TARGETS = json.load(open(os.path.join(HERE, H.TARGETS_NAME), encoding="utf-8"))
ARGS = json.load(open(os.path.join(HERE, "hangar_resize_s4_args.json"), encoding="utf-8"))
TOL = H.tolerances(ARGS)


def synth_live(fly="rest", roof_pitch=0.0, targets=TARGETS):
    st = {"rest": TARGETS["lattice_fly"]["rest_z_old"], "landed": TARGETS["lattice_fly"]["landed_z_old"]}[fly]
    fs = H.fly_state(st, targets, 1.0)
    rs = H.roof_state(roof_pitch)
    pieces = {}
    kids = {}
    for p in targets["pieces"]:
        if p["parent"]:
            kids[p["parent"]] = kids.get(p["parent"], 0) + 1
    for p in targets["pieces"]:
        scale = H.scale_of(p["size_old"], 100.0) if p["size_old"] else [1.0, 1.0, 1.0]
        pieces[p["label"]] = {"rel": H.pose_rel(p, "old", fs, rs, targets["roof_hinge_loc"]), "scale": scale,
                              "depth": len(p["ancestors"]), "children": kids.get(p["label"], 0)}
    wf = targets["world_fixed"]
    return {"pieces": pieces, "fly_rel_z": st, "roof_pitch": roof_pitch,
            "world_fixed": {H.APRON_LABEL: {"scale": list(wf[H.APRON_LABEL]["scale_old"])},
                            H.PPV_LABEL: {"scale": [11.0, wf[H.PPV_LABEL]["scale_y_old"], 16.0]}}}


KEYS = [[0, 2800.0], [379, 2800.0], [499, 1200.0]]


class Targets(unittest.TestCase):
    def test_contract_counts(self):
        self.assertFalse(TARGETS["fails"])
        self.assertEqual(len(TARGETS["pieces"]), 119)                      # 114 plan_for - far wall + 5 door pieces
        self.assertEqual(len(H.expected_labels(TARGETS)), 121)
        self.assertNotIn("S4 Hangar Far Wall", H.expected_labels(TARGETS))
        self.assertIn("S4 Hangar Far Wall Above Exit", H.expected_labels(TARGETS))
        self.assertEqual(TARGETS["k_old"], TARGETS["k_new"])
        self.assertEqual(TARGETS["counts_old"], TARGETS["counts_new"])


class ActorPlan(unittest.TestCase):
    def by(self, plan):
        return {w["label"]: w for w in plan["writes"]}

    def test_rest_flat(self):
        p = H.plan_actor_writes(TARGETS, synth_live("rest", 0.0), TOL)
        self.assertEqual((p["drift"], p["refusals"]), ([], []))
        w = self.by(p)
        self.assertAlmostEqual(w["S4 Hangar Lattice Fly"]["rel_after"][2], 2900.0)
        self.assertAlmostEqual(w["S4 Lattice Bulb 1-1"]["rel_after"][2], 2911.0)
        self.assertAlmostEqual(w["S4 Hangar Lattice Rail 1"]["rel_after"][1], -1100.0)
        self.assertAlmostEqual(w["S4 Ghost Light"]["rel_after"][0], 3500.0)
        self.assertAlmostEqual(w["S4 Hangar Roof"]["scale_after"][1], 29.0)
        self.assertAlmostEqual(w["S4 Hangar Floor 2"]["scale_after"][1], 28.0)
        self.assertAlmostEqual(w["S4 Hangar Far Wall Above Exit"]["scale_after"][1], 29.0)
        self.assertNotIn("S4 Hangar Root", w)                               # the root is never written
        self.assertNotIn("S4 Hangar Exit Door Leaf", w)
        fx = {f["label"]: f for f in p["world_fixed"]}
        self.assertEqual(fx[H.APRON_LABEL]["scale_after"], [5.0, 28.0, 0.2])
        self.assertEqual(fx[H.PPV_LABEL]["scale_after"], [11.0, 15.0, 16.0])

    def test_landed_upright(self):
        p = H.plan_actor_writes(TARGETS, synth_live("landed", -90.0), TOL)
        self.assertEqual((p["drift"], p["refusals"]), ([], []))
        w = self.by(p)
        self.assertAlmostEqual(w["S4 Hangar Lattice Fly"]["rel_after"][2], 1700.0)
        self.assertAlmostEqual(w["S4 Lattice Glow 2-3"]["rel_after"][2], 1711.0)
        self.assertAlmostEqual(w["S4 Hangar Roof"]["rel_after"][0], w["S4 Hangar Roof"]["rel_before"][0])
        # control: the same live read as if the fly were at rest drifts everywhere under the fly
        live = synth_live("landed", -90.0)
        live["fly_rel_z"] = TARGETS["lattice_fly"]["rest_z_old"]
        self.assertTrue(H.plan_actor_writes(TARGETS, live, TOL)["drift"])

    def test_roof_state_matters(self):
        live = synth_live("rest", -90.0)
        live["roof_pitch"] = 0.0                                            # control: pitch says flat, pose is upright
        self.assertTrue(any("S4 Hangar Roof " in d for d in H.plan_actor_writes(TARGETS, live, TOL)["drift"]))

    def test_drift_control(self):
        live = synth_live()
        live["pieces"]["S4 Practical L3"]["rel"][1] += 2.0
        p = H.plan_actor_writes(TARGETS, live, TOL)
        self.assertTrue(any(d.startswith("S4 Practical L3") for d in p["drift"]))
        live = synth_live()
        live["pieces"]["S4 Hangar Floor 1"]["scale"][1] = 21.0
        self.assertTrue(H.plan_actor_writes(TARGETS, live, TOL)["drift"])
        live = synth_live()
        live["world_fixed"][H.APRON_LABEL]["scale"][1] = 25.0
        self.assertTrue(H.plan_actor_writes(TARGETS, live, TOL)["drift"])

    def test_unknown_states_refuse(self):
        live = synth_live()
        live["fly_rel_z"] = 2000.0
        self.assertRaises(H.PlanError, H.plan_actor_writes, TARGETS, live, TOL)
        live = synth_live()
        live["roof_pitch"] = -45.0
        self.assertRaises(H.PlanError, H.plan_actor_writes, TARGETS, live, TOL)

    def test_structure_refusals(self):
        live = synth_live()
        live["pieces"]["S4 Hangar Roof"]["children"] = 1
        self.assertTrue(any("RESIZED_PIECE_HAS_CHILDREN" in r for r in H.plan_actor_writes(TARGETS, live, TOL)["refusals"]))
        live = synth_live()
        live["pieces"]["S4 Hangar Left Wall Hinge"]["scale"] = [1.5, 1.0, 1.0]
        self.assertTrue(any("HINGE_NOT_UNIT_SCALE" in r for r in H.plan_actor_writes(TARGETS, live, TOL)["refusals"]))
        live = synth_live()
        del live["pieces"]["S4 Uplight 2"]
        self.assertTrue(any("PIECE_NOT_READ" in r for r in H.plan_actor_writes(TARGETS, live, TOL)["refusals"]))

    def _simulate(self, writes, live):
        """Translation-only hierarchy: setting an actor's location carries its plan descendants by the same delta."""
        pos = {k: list(v["rel"]) for k, v in live["pieces"].items()}
        desc = {p["label"]: [q["label"] for q in TARGETS["pieces"] if p["label"] in q["ancestors"]] for p in TARGETS["pieces"]}
        for w in writes:
            d = [w["rel_after"][i] - pos[w["label"]][i] for i in range(3)]
            for lab in [w["label"]] + desc[w["label"]]:
                pos[lab] = [pos[lab][i] + d[i] for i in range(3)]
        return {k: {"rel": v, "scale": [1, 1, 1]} for k, v in pos.items()}

    def test_parents_first_reaches_every_target(self):
        for fly in ("rest", "landed"):
            live = synth_live(fly, 0.0)
            p = H.plan_actor_writes(TARGETS, live, TOL)
            got = self._simulate(p["writes"], live)
            self.assertEqual(H.readback_bad(p["all_after"], got, 0.05), [])
            bad = H.readback_bad(p["all_after"], self._simulate(list(reversed(p["writes"])), live), 0.05)
            self.assertTrue(bad)                                            # control: children-first is wrong

    def test_revert_round_trip(self):
        live = synth_live("landed", 0.0)
        p = H.plan_actor_writes(TARGETS, live, TOL)
        after = self._simulate(p["writes"], live)
        back = [dict(w, rel_after=w["rel_before"]) for w in p["writes"]]
        before = {k: v["rel"] for k, v in live["pieces"].items()}
        self.assertEqual(H.readback_bad(before, self._simulate(back, {"pieces": after}), 0.05), [])
        self.assertTrue(H.readback_bad(before, after, 0.05))               # control: applied != before


class Keys(unittest.TestCase):
    def test_values_only(self):
        k = H.plan_key_values(KEYS, 2800.0, TARGETS, 0.01)
        self.assertEqual(k["refusals"], [])
        self.assertEqual(k["keys_after"], [[0, 2900.0], [379, 2900.0], [499, 1700.0]])
        self.assertEqual([t for t, _ in k["keys_after"]], [t for t, _ in KEYS])
        self.assertEqual(k["default_after"], 2900.0)
        self.assertIsNone(H.plan_key_values(KEYS, None, TARGETS, 0.01)["default_after"])

    def test_unmapped_refuse(self):
        self.assertTrue(H.plan_key_values(KEYS + [[600, 2500.0]], 2800.0, TARGETS, 0.01)["refusals"])
        self.assertTrue(H.plan_key_values(KEYS, 3000.0, TARGETS, 0.01)["refusals"])
        self.assertTrue(H.plan_key_values([], None, TARGETS, 0.01)["refusals"])

    def test_readback_float32(self):
        want = [[0, 2900.0], [379, 2900.0], [499, 1700.0]]
        f32 = [[0, 2900.0000305], [379, 2899.9999695], [499, 1700.0000153]]
        self.assertEqual(H.keys_bad(f32, want, 2900.00003, 2900.0, 0.01), [])
        self.assertTrue(H.keys_bad([[0, 2900.0], [380, 2900.0], [499, 1700.0]], want, None, None, 0.01))   # time moved
        self.assertTrue(H.keys_bad([[0, 2800.0], [379, 2900.0], [499, 1700.0]], want, None, None, 0.01))
        self.assertTrue(H.keys_bad(want, want, 2800.0, 2900.0, 0.01))


class Contract(unittest.TestCase):
    def rows(self):
        return {l: {"count": 1, "owned": True} for l in H.expected_labels(TARGETS)}

    def test_labels(self):
        self.assertEqual(H.label_contract(TARGETS, self.rows(), []), ([], [], []))
        r = self.rows()
        del r["S4 Lattice Glow 3-8"]
        self.assertEqual(H.label_contract(TARGETS, r, [])[0], ["S4 Lattice Glow 3-8"])
        r = self.rows()
        r["S4 Uplight 1"]["count"] = 2
        self.assertEqual(H.label_contract(TARGETS, r, [])[1], ["S4 Uplight 1"])
        r = self.rows()
        r["S4 Hangar Pit Liner"] = {"count": 1, "owned": True}
        self.assertEqual(H.label_contract(TARGETS, r, [])[2], ["S4 Hangar Pit Liner"])
        self.assertEqual(H.label_contract(TARGETS, r, ["S4 Hangar Pit Liner"])[2], [])
        r = self.rows()
        r["S4 Arrival"] = {"count": 1, "owned": False}                       # not owned: never an extra
        self.assertEqual(H.label_contract(TARGETS, r, []), ([], [], []))

    def test_confirm_and_sha(self):
        self.assertEqual(H.check_confirm({"mode": "DRY", "confirm": "DRY HANGARRESIZES4"}), "DRY")
        self.assertRaises(H.PlanError, H.check_confirm, {"mode": "DRY", "confirm": "DRY S1REDOCK"})
        self.assertRaises(H.PlanError, H.check_confirm, {"mode": "APPLY", "confirm": "APPLY HANGARRESIZES4",
                                                         "approved_by": "conductor"})
        self.assertRaises(H.PlanError, H.check_confirm, {"mode": "APPLY", "confirm": "APPLY HANGARRESIZES4",
                                                         "plan_sha256": "x"})
        self.assertEqual(H.check_confirm({"mode": "APPLY", "confirm": "APPLY HANGARRESIZES4", "plan_sha256": "x",
                                          "approved_by": "conductor"}), "APPLY")
        self.assertEqual(H.check_confirm(ARGS), "DRY")                       # the args file ships as DRY
        p = H.plan_actor_writes(TARGETS, synth_live(), TOL)
        k = H.plan_key_values(KEYS, 2800.0, TARGETS, 0.01)
        a = H.plan_sha256(p, k, "t")
        self.assertEqual(a, H.plan_sha256(copy.deepcopy(p), copy.deepcopy(k), "t"))
        p2 = copy.deepcopy(p)
        p2["writes"][0]["rel_before"][0] += 0.5
        self.assertNotEqual(a, H.plan_sha256(p2, k, "t"))
        self.assertNotEqual(a, H.plan_sha256(H.plan_actor_writes(TARGETS, synth_live("landed"), TOL), k, "t"))


class KlaraArgs(unittest.TestCase):
    def load(self, name):
        return json.load(open(os.path.join(KLARA, name), encoding="utf-8"))

    def head(self, name):
        rel = "Saved/CodexConductor/KlaraIngest/" + name
        try:
            out = subprocess.run(["git", "-C", PROJECT, "show", "HEAD:" + rel], capture_output=True, check=True).stdout
        except Exception:  # noqa: BLE001
            self.skipTest("git unavailable")
        return json.loads(out.decode("utf-8"))

    def test_s4_values(self):
        r, h = self.load("klara_reveal_args.json"), self.load("klara_hookin_args.json")
        self.assertEqual(r["scenes"]["4"]["placement"], {"lead_max_cm": 1500.0})
        self.assertEqual(r["hookin_hangars"]["4"]["lattice_z"], 1700.0)
        self.assertEqual((h["hangars"]["4"]["half_w"], h["hangars"]["4"]["lattice_z"]), (1400.0, 1700.0))
        self.assertEqual((h["hangars"]["4"]["depth"], h["hangars"]["4"]["height"], h["hangars"]["4"]["apron"]),
                         (6000.0, 3000.0, 500.0))
        self.assertEqual(r["placement"]["lead_max_cm"], 800.0)               # the global (S1) value is untouched
        self.assertNotIn("placement", r["scenes"]["1"])

    def test_s1_identical_to_head(self):
        for name in ("klara_reveal_args.json", "klara_hookin_args.json"):
            cur, old = self.load(name), self.head(name)
            s1 = lambda d: {k: v["1"] for k, v in d.items() if isinstance(v, dict) and "1" in v}
            self.assertEqual(s1(cur), s1(old), name)
            self.assertEqual(cur.get("placement"), old.get("placement"), name)

    def test_override_scoped(self):
        sys.path.insert(0, KLARA)
        import test_klara_reveal_offline as T  # noqa: E402
        import klara_reveal as R  # noqa: E402
        f = T.v3facts()                                                     # an S1 plan (scene "1")
        base = R.build_plan(f, T.ARGS)
        self.assertFalse([w for w in base["warnings"] if "LEAD_ABOVE_RANGE" in w])
        a = copy.deepcopy(T.ARGS)
        a["scenes"]["4"]["placement"] = {"lead_max_cm": 100.0}
        self.assertFalse([w for w in R.build_plan(f, a)["warnings"] if "LEAD_ABOVE_RANGE" in w])    # S4's never reaches S1
        a = copy.deepcopy(T.ARGS)
        a["scenes"]["1"]["placement"] = {"lead_max_cm": 100.0}
        self.assertTrue([w for w in R.build_plan(f, a)["warnings"] if "LEAD_ABOVE_RANGE" in w])     # control: S1's does


if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=1).result
    print("HANGARRESIZES4_HARNESS|tests=%d|failures=%d|errors=%d" % (res.testsRun, len(res.failures), len(res.errors)))
    sys.exit(0 if res.wasSuccessful() else 1)
