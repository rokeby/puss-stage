"""Offline harness for the GREASE SHEEN table, with +/- controls.  Writes test_hp_grease_report.json.

  python test_hp_grease.py
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hp_grease_layout as gl  # noqa: E402
import test_hp_clamber as tc  # noqa: E402  (independent extent / floor / keep-out checkers)

hp, scr, lint_one_draw = gl.hp, gl.scr, tc.lint_one_draw
TABLE = HERE / "placement_S03_grease.json"
CLAMBER_V1 = HERE / "placement_S03_clamber.json"
RESULTS = {}


def ladders(doc):
    """Chains of >= 4 same-element decals each 15-45 cm above the last and < 25 cm along (a climb 'ladder')."""
    out = 0
    by = collections.defaultdict(list)
    for r in doc["decals"]:
        by[(r["wall"], r["element_id"])].append(r)
    for rows in by.values():
        rows.sort(key=lambda r: r["height_cm"])
        nxt = {}
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                dz = b["height_cm"] - a["height_cm"]
                if dz > 45:
                    break
                if dz >= 15 and abs(b["along_cm"] - a["along_cm"]) < 25:
                    nxt.setdefault(a["id"], b["id"])
        ids = {r["id"] for r in rows}
        for start in ids - set(nxt.values()):
            n, cur = 1, start
            while cur in nxt:
                cur, n = nxt[cur], n + 1
            if n >= 4:
                out += 1
    return out


def mirror_pairs(doc):
    """Same element, opposite flip, 38-60 cm apart along, |dz| <= 8 (the v1 'pair' event)."""
    n = 0
    by = collections.defaultdict(list)
    for r in doc["decals"]:
        by[(r["wall"], r["element_id"])].append(r)
    for rows in by.values():
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a["flip"] != b["flip"] and 38 <= abs(a["along_cm"] - b["along_cm"]) <= 60 and \
                        abs(a["height_cm"] - b["height_cm"]) <= 8:
                    n += 1
    return n


def roll_spread(doc):
    rolls = [math.radians(r["roll_on_wall_deg"]) for r in doc["decals"] if r["kind"] == "print"]
    R = math.hypot(sum(math.cos(x) for x in rolls), sum(math.sin(x) for x in rolls)) / len(rolls)
    return math.degrees(math.sqrt(-2 * math.log(max(R, 1e-9))))


class Grease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = TABLE.read_bytes()
        cls.doc = json.loads(cls.raw)
        cls.cfg = json.loads(gl.CONFIG.read_text(encoding="utf-8"))
        sets = json.loads(gl.base.HEIGHT_SETS.read_text(encoding="utf-8"))
        pm = sets["sets"][cls.cfg["height_set"]]["wall_profile_max_per_metre_cm"]
        cls.pm = {w: pm[cls.cfg["wall_dune_profile"][w]] for w in cls.cfg["walls"]}
        walls = {w["id"]: w for w in json.loads(gl.base.WALLS.read_text(encoding="utf-8"))["walls"]}
        cls.prof = {w: gl.base.Profile(cls.pm[w], walls[w]["length_cm"], cls.cfg, cls.doc["stats"][w]["envelope_knots"])
                    for w in cls.cfg["walls"]}
        cls.v1 = json.loads(CLAMBER_V1.read_text(encoding="utf-8"))
        man = json.loads((gl.PROJECT / "DerivedAssets/S3Shore/SM_S3_ShoreGround_manifest.json").read_text(encoding="utf-8"))
        cls.h = np.load(tc.GRID_H)
        p = man["params"]
        cls.xs = np.linspace(p["x_range"][0], p["x_range"][1], cls.h.shape[0])
        cls.ys = np.linspace(p["y_range"][0], p["y_range"][1], cls.h.shape[1])

    def test_01_build_determinism(self):
        a = gl.base.dumps(gl.build(self.cfg))
        self.assertEqual(a, self.raw)                                                       # shipped = rebuild
        self.assertEqual(a, gl.base.dumps(gl.build(self.cfg)))
        self.assertNotEqual(a, gl.base.dumps(gl.build(self.cfg, seed=self.cfg["seed"] + 1)))  # - control
        self.assertEqual(lint_one_draw.check_source(Path(gl.__file__).read_text(encoding="utf-8"), "g"), [])
        self.assertEqual(self.doc["dune"]["sha256"], gl.base.sha(gl.base.HEIGHT_SETS))
        RESULTS["determinism"] = {"table_sha256": hashlib.sha256(self.raw).hexdigest(), "identical": True,
                                  "other_seed_differs": True, "lint": 0}

    def test_02_floor(self):
        self.assertEqual(tc.floor_violations(self.doc, self.pm), [])
        self.assertEqual(tc.fine_floor_violations(self.doc, self.xs, self.ys, self.h), [])
        bad = copy.deepcopy(self.doc)
        r = bad["decals"][5]
        lo = tc.ext(r)[0]
        r["height_cm"] -= lo - self.pm[r["wall"]][int(r["along_cm"] // 100)] - 10.0
        self.assertIn(r["id"], tc.floor_violations(bad, self.pm))                           # + control
        m = min(tc.ext(r)[0] - r["dune_floor_cm"] for r in self.doc["decals"])
        RESULTS["floor"] = {"violations": 0, "fine_grid_violations": 0, "min_margin_cm": round(m, 2)}

    def test_03_envelope(self):
        g = self.cfg["global_ceiling_cm"]
        self.assertEqual(tc.envelope_violations(self.doc, self.prof, g), [])
        bad = copy.deepcopy(self.doc)
        r = next(r for r in bad["decals"] if not r["outlier"])
        r["height_cm"] += 500.0
        self.assertIn(r["id"], tc.envelope_violations(bad, self.prof, g))                   # + control
        out = {w: {"max_cm": round(max(tc.ext(r)[1] for r in self.doc["decals"] if r["wall"] == w), 1),
                   "above_450": sum(tc.ext(r)[1] > 450 for r in self.doc["decals"] if r["wall"] == w),
                   "high_outliers": sum(r["outlier"] for r in self.doc["decals"] if r["wall"] == w)}
               for w in ("L", "R")}
        RESULTS["envelope"] = out

    def test_04_irregular_with_controls(self):
        lg, lv = ladders(self.doc), ladders(self.v1)
        pg, pv = mirror_pairs(self.doc), mirror_pairs(self.v1)
        sg, sv = roll_spread(self.doc), roll_spread(self.v1)
        self.assertEqual(lg, 0)
        self.assertGreater(lv, 10)                                                          # - control: v1 has ladders
        self.assertLess(pg, pv / 4.0)
        self.assertGreater(pv, 20)                                                          # - control: v1 pairs
        self.assertGreater(sg, 2 * sv)
        smear_share = sum(r["kind"] == "smear" for r in self.doc["decals"]) / len(self.doc["decals"])
        prints = [r for r in self.doc["decals"] if r["kind"] == "print"]
        partial = sum(r["crop_name"] != "full" for r in prints) / len(prints)
        self.assertGreater(smear_share, 0.4)
        self.assertGreater(partial, 0.5)
        sizes = [r["size_cm"][1] for r in self.doc["decals"] if r["kind"] == "smear"]
        gains = collections.Counter(r["gain"] for r in self.doc["decals"])
        RESULTS["irregularity"] = {"ladders_grease_vs_v1": [lg, lv], "mirror_pairs_grease_vs_v1": [pg, pv],
                                   "print_roll_circular_sd_deg_grease_vs_v1": [round(sg, 1), round(sv, 1)],
                                   "smear_share": round(smear_share, 3), "partial_share_of_prints": round(partial, 3),
                                   "smear_length_cm_min_p50_max": [round(min(sizes), 1), round(sorted(sizes)[len(sizes) // 2], 1),
                                                                   round(max(sizes), 1)],
                                   "gains": {str(k): v for k, v in sorted(gains.items())},
                                   "decals_by_kind": dict(collections.Counter(r["event_kind"] for r in self.doc["decals"]))}

    def test_05_keepout_exclusions_drips(self):
        self.assertEqual(tc.keepout_violations(self.doc, self.cfg["keep_out"]["far_wall_clear_cm"]), [])
        bad = copy.deepcopy(self.doc)
        bad["decals"][-1]["location"][0] = tc.BACKDROP_PLANE_WORLD_X - 5
        self.assertIn(bad["decals"][-1]["id"], tc.keepout_violations(bad, 120.0))           # + control
        boxes, _ = hp.load_exclusions(hp.PROBE_DEFAULT)
        self.assertEqual([r["id"] for r in self.doc["decals"] if hp.excluded_by(r, boxes[r["wall"]])], [])
        drips = {k: v["drips"] for k, v in json.loads(gl.base.DRIPS.read_text(encoding="utf-8"))["elements"].items()}
        dv = [r["id"] for r in self.doc["decals"] if r["kind"] == "smear" and drips[r["element_id"]]
              and abs(scr.norm_roll(r["roll_on_wall_deg"])) > 30.0 + 1e-6]
        self.assertEqual(dv, [])
        RESULTS["keepout_exclusions_drips"] = {"violations": 0}

    def test_06_pool_and_safety(self):
        pool = {p["mi"]: p for p in self.doc["mi_pool"]}
        self.assertLessEqual(len(pool), self.cfg["pool"]["print_entries"] + self.cfg["pool"]["smear_entries"])
        self.assertTrue(all(r["material_instance"] in pool for r in self.doc["decals"]))
        self.assertTrue(all(p["coverage"] >= self.cfg["pool"]["min_crop_coverage"] for p in pool.values()))
        for r in self.doc["decals"]:
            p = pool[r["material_instance"]]
            self.assertEqual((r["element_id"], r["flip"], r["gain"], r["crop_name"]),
                             (p["element"], p["flip"], p["gain"], p["crop_name"]))
        self.assertEqual(len({r["label"] for r in self.doc["decals"]}), len(self.doc["decals"]))
        self.assertTrue(all(r["label"].startswith("HP_S03G ") for r in self.doc["decals"]))   # never 'HP_S03 '
        self.assertNotEqual(self.doc["schema"], "hp_placement/1")                             # stain placer refuses
        placer = (gl.HERE.parent / "hp_place_decals.py").read_text(encoding="utf-8")
        self.assertIn('table.get("schema") == "hp_placement/1"', placer)
        RESULTS["pool"] = {"pool": len(pool), "used": len(self.doc["mi_used"]), "count": len(self.doc["decals"]),
                           "per_wall": {w: s["count"] for w, s in self.doc["stats"].items()}}


if __name__ == "__main__":
    prog = unittest.main(exit=False, verbosity=1)
    res = prog.result
    rep = {"ran": res.testsRun, "failures": len(res.failures), "errors": len(res.errors), "results": RESULTS}
    (HERE / "test_hp_grease_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("HP_GREASE_TESTS|ran=%d|fail=%d|err=%d" % (res.testsRun, len(res.failures), len(res.errors)))
    sys.exit(0 if res.wasSuccessful() else 1)
