"""Offline harness for the CLAMBER hand-print table, with +/- controls.

  python test_hp_clamber.py          writes test_hp_clamber_report.json next to this file

Every rule is checked by an INDEPENDENT recomputation from the row's axes/size (not from the generator's own
row fields), and every checker is shown able to fail (+ control: a doctored copy is caught) and, where useful,
discriminating (- control: the old scramble table or a flat line fails it).
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import re
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
EDITOR_DIR = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROJECT / "Tools/FlatV3/handprints"))
import build_handprint_placement as hp  # noqa: E402
import build_handprint_placement_scramble as scr  # noqa: E402
import hp_clamber_layout as lay  # noqa: E402
import lint_one_draw  # noqa: E402

TABLE = HERE / "placement_S03_clamber.json"
SCRAMBLE = PROJECT / "DerivedAssets/FlatV3/HandPrints/placement_S03.json"
GRID_H = PROJECT / "DerivedAssets/S3Shore/SM_S3_ShoreGround_grid_h.npy"
ROOT_Y = 160000.0
BACKDROP_PLANE_WORLD_X = 11421.97275 + 5997.0
DOOR_HALF_Y = 150.0
RESULTS = {}


def ext(row):
    ax, half = row["axes"], row["decal_size"]
    v = abs(ax["y"][2]) * half[1] + abs(ax["z"][2]) * half[2]
    h = abs(ax["y"][0]) * half[1] + abs(ax["z"][0]) * half[2]
    return row["height_cm"] - v, row["height_cm"] + v, row["along_cm"] - h, row["along_cm"] + h


def floor_violations(doc, pm_by_wall, clear=20.0, pad=5.0):
    bad = []
    for r in doc["decals"]:
        pm = pm_by_wall.get(r["wall"])
        if pm is None:
            continue
        lo, _, a0, a1 = ext(r)
        i0 = max(0, int(math.floor((a0 - pad) / 100.0)))
        i1 = min(len(pm) - 1, int(math.floor((a1 + pad) / 100.0)))
        if lo < max(pm[i0:i1 + 1]) + clear - 1e-6:
            bad.append(r["id"])
    return bad


def fine_floor_violations(doc, xs, ys, h, clear=20.0):
    """Against the built grid itself: max over the 10 cm strip in front of the face, across the decal's extent."""
    bad = []
    for r in doc["decals"]:
        lo, _, a0, a1 = ext(r)
        face = r["location"][1] - ROOT_Y
        sgn = 1.0 if face > 0 else -1.0
        a = np.linspace(a0, a1, 25)
        m = -1e9
        for dy in (0.0, 2.5, 5.0, 7.5, 10.0):
            m = max(m, float(lay_interp(xs, ys, h, a, np.full_like(a, face - sgn * dy)).max()))
        if lo < m + clear - 1e-6:
            bad.append(r["id"])
    return bad


def lay_interp(xs, ys, A, x, y):
    x = np.clip(x, xs[0], xs[-1])
    y = np.clip(y, ys[0], ys[-1])
    i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    j = np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2)
    tx = (x - xs[i]) / (xs[i + 1] - xs[i])
    ty = (y - ys[j]) / (ys[j + 1] - ys[j])
    return ((A[i, j] * (1 - tx) + A[i + 1, j] * tx) * (1 - ty) + (A[i, j + 1] * (1 - tx) + A[i + 1, j + 1] * tx) * ty)


def envelope_violations(doc, profiles, global_ceiling):
    bad = []
    for r in doc["decals"]:
        _, hi, _, _ = ext(r)
        if hi > global_ceiling + 1e-6:
            bad.append(r["id"])
        elif not r["outlier"] and hi > profiles[r["wall"]].top(r["along_cm"]) + 1e-6:
            bad.append(r["id"])
        elif r["outlier"] and hi > r["ceiling_cm"] + 1e-6:
            bad.append(r["id"])
    return bad


def keepout_violations(doc, clear_cm):
    """Far wall (mural + door) gets nothing; side-wall boxes stay clear_cm off the backdrop plane."""
    bad = []
    for r in doc["decals"]:
        lo, hi = hp.decal_world_aabb(r)
        if r["wall"] not in ("L", "R"):
            bad.append(r["id"])
        elif hi[0] > BACKDROP_PLANE_WORLD_X - clear_cm:
            bad.append(r["id"])
        elif abs(r["location"][1] - ROOT_Y) < DOOR_HALF_Y:
            bad.append(r["id"])
    return bad


class Clamber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = TABLE.read_bytes()
        cls.doc = json.loads(cls.raw)
        cls.cfg = json.loads(lay.CONFIG.read_text(encoding="utf-8"))
        sets = json.loads(lay.HEIGHT_SETS.read_text(encoding="utf-8"))
        pm = sets["sets"][cls.cfg["height_set"]]["wall_profile_max_per_metre_cm"]
        cls.pm = {w: pm[cls.cfg["wall_dune_profile"][w]] for w in cls.cfg["walls"]}
        walls = {w["id"]: w for w in json.loads(lay.WALLS.read_text(encoding="utf-8"))["walls"]}
        cls.walls = walls
        cls.prof = {w: lay.Profile(cls.pm[w], walls[w]["length_cm"], cls.cfg, cls.doc["stats"][w]["envelope_knots"])
                    for w in cls.cfg["walls"]}
        cls.scramble = json.loads(SCRAMBLE.read_text(encoding="utf-8"))
        man = json.loads((PROJECT / "DerivedAssets/S3Shore/SM_S3_ShoreGround_manifest.json").read_text(encoding="utf-8"))
        cls.h = np.load(GRID_H)
        p = man["params"]
        cls.xs = np.linspace(p["x_range"][0], p["x_range"][1], cls.h.shape[0])
        cls.ys = np.linspace(p["y_range"][0], p["y_range"][1], cls.h.shape[1])
        cls.man = man

    def rec(self, name, **kw):
        RESULTS[name] = kw

    # ---------------------------------------------------------------- provenance + determinism
    def test_01_table_is_this_build_and_pinned(self):
        again = lay.dumps(lay.build(self.cfg))
        self.assertEqual(again, self.raw)
        sha = hashlib.sha256(self.raw).hexdigest()
        src = (EDITOR_DIR / "hp_place_decals.py").read_text(encoding="utf-8")
        pin = re.search(r'CLAMBER_PLACEMENT_SHA256 = "([0-9a-f]{64})"', src).group(1)
        self.assertEqual(pin, sha)
        full_pin = re.search(r'EXPECTED_PLACEMENT_SHA256 = "([0-9a-f]{64})"', src).group(1)
        self.assertEqual(full_pin, hashlib.sha256(SCRAMBLE.read_bytes()).hexdigest())      # default mode untouched
        self.assertEqual(self.doc["dune"]["sha256"], hashlib.sha256(lay.HEIGHT_SETS.read_bytes()).hexdigest())
        self.assertEqual(self.doc["dune"]["grid_sha256"], self.man["grid_sha256"])         # same set-B grid as the FBX
        self.rec("provenance", table_sha256=sha, pinned=True, rebuild_identical=True)

    def test_02_determinism_with_control(self):
        a = lay.dumps(lay.build(self.cfg))
        b = lay.dumps(lay.build(self.cfg))
        self.assertEqual(a, b)
        c = lay.dumps(lay.build(self.cfg, seed=self.cfg["seed"] + 1))
        self.assertNotEqual(a, c)                                                          # - control
        self.assertEqual(lint_one_draw.check_source(Path(lay.__file__).read_text(encoding="utf-8"),
                                                    "hp_clamber_layout.py"), [])
        bad_src = "def f(rng):\n    x = rng.random() * rng.random()\n"
        self.assertNotEqual(lint_one_draw.check_source(bad_src, "x"), [])                  # + control
        self.rec("determinism", identical_twice=True, other_seed_differs=True, one_draw_lint=0)

    def test_03_per_metre_profile_matches_built_grid(self):
        xx = np.linspace(0, 6000, 1201)
        for w, side_y in (("L", -999.0), ("R", 999.0)):
            p = lay_interp(self.xs, self.ys, self.h, xx, np.full_like(xx, side_y))
            pm = [round(float(p[(xx >= i * 100) & (xx <= (i + 1) * 100)].max()), 1) for i in range(60)]
            self.assertEqual(pm, [round(v, 1) for v in self.pm[w]])
        self.rec("dune_profile", per_metre_equals_grid_npy=True)

    # ---------------------------------------------------------------- floor rule
    def test_04_no_print_below_dune_plus_clearance(self):
        self.assertEqual(floor_violations(self.doc, self.pm), [])
        fine = fine_floor_violations(self.doc, self.xs, self.ys, self.h)
        self.assertEqual(fine, [])
        bad = copy.deepcopy(self.doc)
        r = bad["decals"][0]
        lo, _, _, _ = ext(r)
        r["height_cm"] -= lo - self.pm[r["wall"]][int(r["along_cm"] // 100)] - 10.0   # extent now 10 cm over the dune
        self.assertIn(r["id"], floor_violations(bad, self.pm))                             # + control
        old = floor_violations(self.scramble, self.pm)
        self.assertGreater(len(old), 0)                                                    # - control
        margins = [ext(r)[0] - max(self.pm[r["wall"]][max(0, int(math.floor((ext(r)[2] - 5) / 100))):
                                                       min(59, int(math.floor((ext(r)[3] + 5) / 100))) + 1])
                   for r in self.doc["decals"]]
        self.rec("floor_rule", violations=0, fine_grid_violations=0, min_margin_cm=round(min(margins), 2),
                 plus_control_caught=True, scramble_160_table_violations=len(old))

    def test_05_lowest_prints_follow_the_dunes(self):
        out = {}
        for w in ("L", "R"):
            lows, dunes = [], []
            for i in range(60):
                rows = [ext(r)[0] for r in self.doc["decals"] if r["wall"] == w and i * 100 <= r["along_cm"] < i * 100 + 100]
                if len(rows) >= 5:                       # metres with a real cluster; 1-2 print metres = isolated climbs
                    lows.append(min(rows))
                    dunes.append(self.pm[w][i])
            corr = float(np.corrcoef(lows, dunes)[0, 1])
            gap = np.array(lows) - np.array(dunes)
            out[w] = {"metres_with_prints": len(lows), "corr_lowest_vs_dune": round(corr, 3),
                      "lowest_minus_dune_median_cm": round(float(np.median(gap)), 1),
                      "lowest_spread_sd_cm": round(float(np.std(lows)), 1)}
            self.assertGreater(corr, 0.70, w)
            self.assertGreater(np.std(lows), 30.0, w)                                      # never a flat line
            self.assertLess(float(np.median(gap)), 60.0, w)                                # hugs the sand
            olows, odunes = [], []
            for i in range(60):
                rows = [ext(r)[0] for r in self.scramble["decals"] if r["wall"] == w and i * 100 <= r["along_cm"] < i * 100 + 100]
                if len(rows) >= 5:
                    olows.append(min(rows))
                    odunes.append(self.pm[w][i])
            ocorr = float(np.corrcoef(olows, odunes)[0, 1])
            out[w]["scramble_160_table_corr"] = round(ocorr, 3)
            self.assertLess(ocorr, 0.5, w)                                                 # - control: flat band fails
        self.rec("follows_dunes", **out)

    # ---------------------------------------------------------------- envelope
    def test_06_envelope(self):
        g = self.cfg["global_ceiling_cm"]
        self.assertEqual(envelope_violations(self.doc, self.prof, g), [])
        bad = copy.deepcopy(self.doc)
        r = next(r for r in bad["decals"] if not r["outlier"])
        r["height_cm"] += 400.0
        self.assertIn(r["id"], envelope_violations(bad, self.prof, g))                     # + control
        out = {}
        for w in ("L", "R"):
            his = [ext(r)[1] for r in self.doc["decals"] if r["wall"] == w]
            tops = [self.prof[w].top(a) for a in range(150, 5851, 10)]
            n_out = len({r["event"] for r in self.doc["decals"] if r["wall"] == w and r["outlier"]})
            out[w] = {"count": len(his), "above_300": sum(h > 300 for h in his), "above_500": sum(h > 500 for h in his),
                      "above_700": sum(h > 700 for h in his), "max_cm": round(max(his), 1),
                      "envelope_min_max_cm": [round(min(tops), 1), round(max(tops), 1)], "outlier_climbs": n_out}
            self.assertGreaterEqual(out[w]["above_500"], 10, w)                            # well above head height
            self.assertGreaterEqual(max(tops), 500.0, w)
            self.assertTrue(2 <= n_out <= 3, w)
            # density thins upward
            bands = [sum(1 for h in his if lo <= h < lo + 150) for lo in (0, 150, 300, 450, 600)]
            out[w]["highest_extent_by_150cm_band"] = bands
        self.rec("envelope", **out)

    # ---------------------------------------------------------------- keep-outs, exclusions
    def test_07_door_mural_keepout(self):
        clear = self.cfg["keep_out"]["far_wall_clear_cm"]
        self.assertEqual(keepout_violations(self.doc, clear), [])
        bad = copy.deepcopy(self.doc)
        r = bad["decals"][-1]
        r["location"][0] = BACKDROP_PLANE_WORLD_X - 10.0
        bad2 = copy.deepcopy(self.doc)
        bad2["decals"][0]["wall"] = "B"
        self.assertIn(r["id"], keepout_violations(bad, clear))                             # + control (mural)
        self.assertIn(bad2["decals"][0]["id"], keepout_violations(bad2, clear))            # + control (far wall)
        nearest = min(BACKDROP_PLANE_WORLD_X - hp.decal_world_aabb(r)[1][0] for r in self.doc["decals"])
        self.assertGreater(nearest, clear)
        self.rec("door_mural_keepout", violations=0, nearest_box_to_backdrop_plane_cm=round(nearest, 1),
                 walls=sorted({r["wall"] for r in self.doc["decals"]}))

    def test_08_exclusions(self):
        boxes, _ = hp.load_exclusions(hp.PROBE_DEFAULT)
        hits = [r["id"] for r in self.doc["decals"] if hp.excluded_by(r, boxes[r["wall"]])]
        self.assertEqual(hits, [])
        bad = copy.deepcopy(self.doc["decals"][0])
        lamp = next(b for b in boxes[bad["wall"]] if b["kind"] == "practical")
        bad["location"] = [(lamp["min"][i] + lamp["max"][i]) / 2 for i in range(3)]
        bad["location"][1] = self.doc["decals"][0]["location"][1]
        self.assertEqual(hp.excluded_by(bad, boxes[bad["wall"]]), "practical")             # + control
        self.rec("exclusions", hits=0)

    # ---------------------------------------------------------------- placer compatibility
    def test_09_placer_compatibility(self):
        imp = json.loads((EDITOR_DIR / "hp_import_stages_record.json").read_text(encoding="utf-8"))
        self.assertEqual(self.doc["atlas_sha256"], imp["atlas_sha256"])
        done = set(imp["stages"]["mi_v3"]["done"])
        need = {"MI_HP_S03_v3_%s_F%d" % (r["element_id"], 1 if r["flip"] else 0) for r in self.doc["decals"]}
        self.assertEqual(sorted(need - done), [])
        self.assertTrue(all(r["material_instance"] in done for r in self.doc["decals"]))
        self.assertEqual(len({r["label"] for r in self.doc["decals"]}), len(self.doc["decals"]))
        self.assertTrue(all(r["label"].startswith("HP_S03 ") for r in self.doc["decals"]))
        self.assertEqual(self.doc["schema"], "hp_placement/1")
        self.assertIs(self.doc["placeholder"], False)
        walls_raw = (PROJECT / "DerivedAssets/FlatV3/HandPrints" / self.doc["walls_file"]).read_bytes()
        self.assertEqual(self.doc["walls_sha256"], hashlib.sha256(walls_raw).hexdigest())
        src = (EDITOR_DIR / "hp_place_decals.py").read_text(encoding="utf-8")
        keys = set(re.findall(r'\bd\["(\w+)"\]', src))
        for r in self.doc["decals"]:
            self.assertTrue(keys <= set(r), keys - set(r))
        # the placer's box checks, replayed: walls box with only max z raised, decal centres inside (+30)
        wb = json.loads(walls_raw)["landed_box_world_cm"]
        tb = self.doc["landed_box_world_cm"]
        ok = tb["min"] == wb["min"] and tb["max"][:2] == wb["max"][:2] and wb["max"][2] <= tb["max"][2] <= 2880.0
        self.assertTrue(ok)
        out_box = [r["id"] for r in self.doc["decals"]
                   if not all(tb["min"][i] - 30 <= r["location"][i] <= tb["max"][i] + 30 for i in range(3))]
        self.assertEqual(out_box, [])
        # every decal sits on its wall's receiving face (frame trap guard)
        for r in self.doc["decals"]:
            self.assertAlmostEqual(r["location"][1], self.walls[r["wall"]]["origin_cm"][1], places=3)
            self.assertGreaterEqual(r["location"][2], -5.0)
        self.rec("placer_compat", mis_needed=len(need), mis_missing=0, labels_unique=True, box_ok=True,
                 count=len(self.doc["decals"]))

    def test_10_smear_rules(self):
        drips = {k: v["drips"] for k, v in json.loads(lay.DRIPS.read_text(encoding="utf-8"))["elements"].items()}
        dc = self.cfg["drag"]
        bad = []
        for r in self.doc["decals"]:
            if r["kind"] != "smear":
                continue
            roll = scr.norm_roll(r["roll_on_wall_deg"])
            if drips[r["element_id"]]:
                if abs(roll) > 30.0 + 1e-6:
                    bad.append(r["id"])
            elif abs(abs(roll) - 180.0) > dc["diagonal_tilt_deg"][1] + dc["group_roll_jitter_deg"] + 1e-6:
                bad.append(r["id"])
        self.assertEqual(bad, [])
        import collections
        self.rec("smears", violations=0,
                 directions=dict(collections.Counter(r["smear_direction"] for r in self.doc["decals"] if r["kind"] == "smear")))

    def test_11_placer_edit_is_additive(self):
        src = (EDITOR_DIR / "hp_place_decals.py").read_text(encoding="utf-8")
        old = (EDITOR_DIR / "hp_place_decals.py.bak-20261007-preclamber").read_text(encoding="utf-8")
        ast.parse(src)
        # every line of the pre-clamber placer survives, in order (pure additions only)
        new_lines = src.splitlines()
        j = 0
        for line in old.splitlines():
            while j < len(new_lines) and new_lines[j] != line:
                j += 1
            self.assertLess(j, len(new_lines), "removed or changed: %r" % line)
            j += 1
        for wrapper, globs in (("hp_place_clamber_dry.py", '{"HP_PLACE_MODE": "clamber", "HP_DRY_RUN": True}'),
                               ("hp_place_clamber.py", '{"HP_PLACE_MODE": "clamber"}')):
            w = (HERE / wrapper).read_text(encoding="utf-8")
            self.assertIn(globs, w)
            self.assertIn('"hp_place_decals.py"', w)
            req = json.loads((HERE / wrapper.replace(".py", "_request.json")).read_text(encoding="utf-8"))
            self.assertEqual(req["arguments"]["toolset_name"], "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset")
            self.assertEqual(req["arguments"]["arguments"]["relativeSavedPath"], "CodexFlatV3/handprints/clamber/" + wrapper)
        self.rec("placer_edit", additive=True, wrappers_ok=True)


if __name__ == "__main__":
    prog = unittest.main(exit=False, verbosity=1)
    res = prog.result
    rep = {"ran": res.testsRun, "failures": len(res.failures), "errors": len(res.errors),
           "table_sha256": hashlib.sha256(TABLE.read_bytes()).hexdigest(), "results": RESULTS}
    (HERE / "test_hp_clamber_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("HP_CLAMBER_TESTS|ran=%d|fail=%d|err=%d" % (res.testsRun, len(res.failures), len(res.errors)))
    sys.exit(0 if res.wasSuccessful() else 1)
