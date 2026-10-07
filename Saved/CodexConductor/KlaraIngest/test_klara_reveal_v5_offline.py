"""Offline harness for the S4 v5 entry (strike_preroll): klara_reveal.py v5, klara_preroll_s4.py, klara_pendulum_s4.py.
No Unreal. Every positive check has a control that must FAIL the same check.
Run: python Saved/CodexConductor/KlaraIngest/test_klara_reveal_v5_offline.py

Inputs and tiers:
  - klara_reveal_dry_S4.json: the LIVE S4 DRY KLARAREVEAL-20261007-095026 (pre-apply, hookin LT) [meas] - the facts
    v5 is planned on after the v4 REVERT restores that state [inf: REVERT proven live for S1/S4];
  - her copy / original LS, L_KK_children: BYTES via test_klara_reveal_offline.py's reader [meas];
  - backcloth: STANDING = the live section [meas backcloth_lead_fit_record.json section_live_after: motion
    [-7.0326, +3.0008] s, offset 23200 ticks, KeepState] inside the Hangar Fold [0, 775) [meas
    s4_hangar_hold_dry_S4HOLD-20261007-102800.json]; HELD = that plus a Scene-level hold over [775, 4890) as the
    s4_hangar_hold extension would write it (SYNTHETIC - its exact numbers are that agent's);
  - S1: klara_reveal_dry_S1.json and the HEAD version of klara_reveal.py (git show) for the bit-identity proof.
"""
import copy
import json
import math
import os
import re
import subprocess
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import klara_reveal as R            # noqa: E402  (importing without unreal runs nothing)
import klara_preroll_s4 as P        # noqa: E402
import klara_pendulum_s4 as PD      # noqa: E402
import test_klara_reveal_offline as T   # noqa: E402  (bytes readers; defines tests but runs none on import)

FPS = 25.0
DRY4 = R.load_json(os.path.join(HERE, "klara_reveal_dry_S4.json"))
V5ARGS = R.load_json(os.path.join(HERE, "klara_reveal_s4v5_args.json"))
LT_HOOKIN = list(T.S4_LT_HOOKIN)
CUT_CAM = "b28a821d72b7a24ea738eb622365a09c"           # CineCameraActor (_0) [meas bytes]

# backcloth sections as _backcloth_state would read them (Scene frames, 25 fps)
_F0 = -176                                              # floor(-7.032583 x 25) [meas start_s]
_C0 = 23200 / 24000.0 - (176 + (-7.032583236694336 * 25.0)) / 25.0      # cache time at frame -176
STANDING = {"label": "P04 Backcloth (baked)", "loc": [10450.0, 240000.0, 0.0],
            "sections": [{"range": [_F0, 75], "clip": [0, 775], "cache_s_at_start": _C0, "rate": 1.0,
                          "keep_state": True, "source": "LS_S4_HangarRise via Hangar Fold [meas]"}]}
DOWN0 = int(math.ceil(_F0 + (9.0 - _C0) * 25.0 - 1e-9))     # first frame at cache time >= down_cache_s 9.0 (= 26)
HELD = copy.deepcopy(STANDING)
HELD["sections"].append({"range": [775, 4890], "clip": [0, 4890], "cache_s_at_start": 10.96, "rate": 1.0e-4,
                         "keep_state": True, "source": "SYNTHETIC hold (s4_hangar_hold extension)"})


def her_cuts():
    """Every cut of the copy with its camera Location curves, expressed in the DRY's (hookin-LT) world frame."""
    b = T.derive_ls(T.LS_CHILDREN_COPY)
    shift = [LT_HOOKIN[i] - T.S4_LT[i] for i in range(3)]
    out = []
    for c in b["cuts"]:
        ch = b["camera_channels"].get(c["guid"])
        row = {"range": list(c["range"]), "guid": c["guid"], "binding": (b["poss"].get(c["guid"]) or {}).get("name"),
               "curves": None}
        if ch:
            row["curves"] = {}
            for i, ax in enumerate("xyz"):
                cv = copy.deepcopy(ch["Translation[%d]" % i])
                for k in cv["keys"]:
                    k["value"] += shift[i]
                if cv.get("default") is not None:
                    cv["default"] += shift[i]
                row["curves"][ax] = cv
        out.append(row)
    return out


def subjects(prefixes=None):
    prefixes = prefixes or R.V5_DEFAULTS["subjects"]
    out = []
    for r in T.derive_level_rows(T.L_CHILDREN).values():
        lab = r.get("label", r["name"])
        if any(lab.startswith(p) for p in prefixes):
            comps = r["comps"]
            pick = comps.get("Root") or comps.get("PivotRoot") or                 [c for k, c in sorted(comps.items()) if c.get("loc") is not None and k not in ("Eyebrows", "Hair")][0]
            loc = pick["loc"]
            out.append({"label": lab, "origin": [loc[i] + LT_HOOKIN[i] for i in range(3)]})
    return out


def v5args(**v5):
    a = copy.deepcopy(V5ARGS)
    for k, v in v5.items():
        if isinstance(v, dict):
            a["scenes"]["4"]["v5"].setdefault(k, {}).update(v)
        else:
            a["scenes"]["4"]["v5"][k] = v
    return a


def v5facts(backcloth=HELD, args=None):
    a = args or V5ARGS
    f = copy.deepcopy(DRY4["facts"])
    f["reveal"] = dict(f["reveal"], requested="strike_preroll", style="strike_preroll", why="explicit")
    f["lit"] = R.detect_lit(f, a, FPS)
    R.apply_lit_values(f, f["lit"]["frame"])
    f["v5"] = {"subjects": subjects(), "her_cuts": her_cuts(), "backcloth": copy.deepcopy(backcloth)}
    return f


def plan5(backcloth=HELD, **v5):
    a = v5args(**v5)
    return R.build_plan(v5facts(backcloth, a), a), a


def gate_refusals(p):
    return [x for x in p["refusals"] if x.startswith(("CAMERA_PATH", "BACKCLOTH_STATE"))]


def same(x, y):
    if isinstance(x, float) or isinstance(y, float):
        return isinstance(x, (int, float)) and isinstance(y, (int, float)) and abs(x - y) <= 1e-12 * max(1.0, abs(x), abs(y))
    if isinstance(x, dict):
        return isinstance(y, dict) and set(x) == set(y) and all(same(x[k], y[k]) for k in x)
    if isinstance(x, list):
        return isinstance(y, list) and len(x) == len(y) and all(same(a, b) for a, b in zip(x, y))
    return x == y


def jsn(x):
    return json.loads(json.dumps(x, sort_keys=True, default=str))


_HEAD = {}


def head_module():
    """klara_reveal.py as committed BEFORE v5 (pinned: 8cb2830, the last commit before ae84495 added v5; was HEAD,
    which skipped once v5 was committed and let a v4->v5 routing mutation survive), imported with unreal = None."""
    if "m" not in _HEAD:
        root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
        src = subprocess.run(["git", "show", "8cb2830:Saved/CodexConductor/KlaraIngest/klara_reveal.py"], cwd=root,
                             capture_output=True, check=True).stdout.decode("utf-8")
        m = types.ModuleType("klara_reveal_head")
        m.__file__ = os.path.join(HERE, "klara_reveal_head.py")
        exec(compile(src, m.__file__, "exec"), m.__dict__)
        if "strike_preroll" in src:
            raise AssertionError("pinned pre-v5 commit carries v5")
        _HEAD["m"] = m
    return _HEAD["m"]


# =====================================================================================================================

class S1Unchanged(unittest.TestCase):
    """S1's plan must be bit-identical: (a) replay of the live S1 DRY, (b) HEAD code vs this code on the same facts."""

    def test_replay_of_live_s1_dry(self):
        d = R.load_json(os.path.join(HERE, "klara_reveal_dry_S1.json"))
        self.assertTrue(same(jsn(R.build_plan(copy.deepcopy(d["facts"]), d["args"])), jsn(d["plan"])))
        bent = copy.deepcopy(d["facts"])                                   # control: the comparator can fail
        bent["L"] += 1
        self.assertFalse(same(jsn(R.build_plan(bent, d["args"])), jsn(d["plan"])))

    def test_head_vs_new_identical(self):
        H = head_module()
        d = R.load_json(os.path.join(HERE, "klara_reveal_dry_S1.json"))
        for facts, args in ((d["facts"], d["args"]), (T.v3facts(), T.ARGS)):
            a = json.dumps(jsn(H.build_plan(copy.deepcopy(facts), copy.deepcopy(args))), sort_keys=True)
            b = json.dumps(jsn(R.build_plan(copy.deepcopy(facts), copy.deepcopy(args))), sort_keys=True)
            self.assertEqual(a, b)                                          # exact JSON, not tolerance
        # v4 her_dark_pan (the live S4 DRY facts) is unchanged too
        f4 = copy.deepcopy(DRY4["facts"])          # forced to v4 her_dark_pan (a later v5 DRY rewrites this file)
        f4["reveal"] = dict(f4["reveal"], style="her_dark_pan")
        f4.pop("v5", None)
        f4["lit"] = R.detect_lit(f4, DRY4["args"], FPS)
        R.apply_lit_values(f4, f4["lit"]["frame"])
        self.assertEqual(json.dumps(jsn(H.build_plan(copy.deepcopy(f4), DRY4["args"])), sort_keys=True),
                         json.dumps(jsn(R.build_plan(copy.deepcopy(f4), DRY4["args"])), sort_keys=True))
        for fn in ("detect_lit",):
            self.assertEqual(jsn(getattr(H, fn)(copy.deepcopy(f4), DRY4["args"], FPS)),
                             jsn(getattr(R, fn)(copy.deepcopy(f4), DRY4["args"], FPS)))
        # control: v5 facts produce a DIFFERENT plan from the old code's reading of them
        f5, a5 = v5facts(), V5ARGS
        self.assertNotEqual(json.dumps(jsn(H.build_plan(copy.deepcopy(f5), a5)), sort_keys=True),
                            json.dumps(jsn(R.build_plan(copy.deepcopy(f5), a5)), sort_keys=True))

    def test_s1_never_reaches_v5(self):
        live = R.load_json(os.path.join(HERE, "klara_reveal_args.json"))
        self.assertEqual(R.reveal_style(live, "1"), "strike")
        self.assertEqual(R.reveal_style(V5ARGS, "1"), "strike")
        self.assertEqual(R.reveal_style(V5ARGS, "4"), "strike_preroll")    # control
        src = open(R.__file__, encoding="utf-8").read()
        self.assertEqual(src.count("_gather_v5(facts, seq, copy, world, args, fps)"), 1)
        self.assertIn('if (facts.get("reveal") or {}).get("style") == "strike_preroll":   # v5 only', src)


class PathGate(unittest.TestCase):
    def test_standing_backcloth_fails(self):
        p, _a = plan5(STANDING)
        g = gate_refusals(p)
        self.assertTrue(any(x.startswith("CAMERA_PATH_BEHIND_STANDING_BACKCLOTH") for x in g), g)
        self.assertFalse(p["apply_ready"])
        hit = [h for h in p["path_gate"]["hits"] if h["kind"] == "standing"]
        self.assertEqual({h["binding"] for h in hit}, {"CineCameraActor"})       # her dolly-back, not our glide
        self.assertGreater(min(h["first"] for h in hit), 775)                    # past the fold end
        self.assertLess(min(h["min_local_x"] for h in hit), -400.0)              # her rest pose ~ -427 [bytes]
        self.assertEqual(p["path_gate"]["down_ranges"], [[DOWN0, 775]])

    def test_held_backcloth_passes(self):
        p, _a = plan5(HELD)
        self.assertEqual(gate_refusals(p), [])
        self.assertTrue(any(w.startswith("CAMERA_BEHIND_BACKCLOTH_PLANE_WHILE_DOWN") for w in p["warnings"]))
        self.assertEqual(p["path_gate"]["down_ranges"], [[DOWN0, 4890]])

    def test_unread_state_refuses_never_assumed(self):
        for bc in (None, {"error": "BACKCLOTH_ACTOR_COUNT 0"}, {"label": "x"}):
            p, _a = plan5(bc)
            self.assertTrue(any(x.startswith("BACKCLOTH_STATE_UNREAD") for x in p["refusals"]), p["refusals"])

    def test_x_min_can_fail(self):
        p, _a = plan5(HELD, camera_x_min_local=0.0)
        self.assertTrue(any(x.startswith("CAMERA_PATH_BEHIND_X_MIN") for x in p["refusals"]))
        p2, _a = plan5(HELD, camera_x_min_local=-1000.0)                        # control
        self.assertFalse(any(x.startswith("CAMERA_PATH_BEHIND_X_MIN") for x in p2["refusals"]))

    def test_whole_path_every_cut_every_frame(self):
        p, _a = plan5(STANDING)
        pg = p["path_gate"]
        bound = [c for c in her_cuts() if c["curves"]]
        self.assertEqual(len(pg["cuts"]), 5)
        self.assertEqual(len(pg["dangling"]), 0)                       # [0,2) ends before her cut frame 6
        tl = p["timeline"]
        self.assertGreaterEqual(pg["n_her_samples"], 4920 - 6)         # every her frame of the slot
        # control: a FIRST-FRAME-ONLY gate (the v4 blind spot) passes the same standing state
        s = R.sample_cut_path(bound, 0, 4920, 6, tl["cut"], tl["slot"][1], 30.0, FPS, p["placement"]["delta"])
        first = [x for x in s["samples"] if x["her_frame"] == 6]
        cfg5 = R.v5_cfg(V5ARGS, "4")
        g1 = R.gate_camera_path(first, [], DRY4["facts"]["box"]["dock"], DRY4["facts"]["box"], STANDING, cfg5, FPS)
        self.assertEqual(g1["refusals"], [])
        gall = R.gate_camera_path(s["samples"], [], DRY4["facts"]["box"]["dock"], DRY4["facts"]["box"], STANDING,
                                  cfg5, FPS)
        self.assertTrue(gall["refusals"])
        keys = [k["tick"] / 800.0 for k in bound[1]["curves"]["x"]["keys"]]
        self.assertTrue(all(any(abs(x["her_frame"] - kf) < 1e-9 for x in s["samples"]) for kf in keys if kf >= 6))

    def test_down_ranges(self):
        bc = R.v5_cfg(V5ARGS, "4")["backcloth"]
        self.assertEqual(R.backcloth_down_ranges(STANDING["sections"], bc, FPS), [[DOWN0, 775]])
        nokeep = copy.deepcopy(STANDING["sections"])
        nokeep[0]["keep_state"] = False                                # control: no KeepState -> no hold
        self.assertEqual(R.backcloth_down_ranges(nokeep, bc, FPS), [[DOWN0, 75]])
        self.assertEqual(R.backcloth_down_ranges(HELD["sections"], bc, FPS), [[DOWN0, 4890]])
        early = copy.deepcopy(STANDING["sections"])                    # control: ends HANGING, KeepState holds that
        early[0]["range"] = [_F0, 0]
        self.assertEqual(R.backcloth_down_ranges(early, bc, FPS), [])
        loop = [{"range": [775, 4890], "clip": [0, 4890], "cache_s_at_start": 10.0, "rate": 1.0, "keep_state": True}]
        self.assertEqual(R.backcloth_down_ranges(loop, bc, FPS), [[775, 801]])   # runs past the cache end: NOT down

    def test_glide_end_in_front_and_inside(self):
        p, _a = plan5(HELD)
        ge = p["glide_end"]["pose"]
        self.assertGreater(ge["loc"][0], 10450 + 39 + 20)
        self.assertFalse(any(x.startswith("GLIDE_END") for x in p["refusals"]))
        p2, _a = plan5(HELD, glide_end={"pullback_cm": 2100.0})          # control: behind the cloth
        self.assertTrue(any(x.startswith("GLIDE_END") for x in p2["refusals"]), p2["refusals"])


class Plan5(unittest.TestCase):
    def test_plan_shape_and_hard_cut(self):
        p, _a = plan5(HELD)
        self.assertEqual(p["refusals"], [], p["refusals"])
        self.assertEqual(p["version"], 5)
        tl = p["timeline"]
        self.assertEqual(p["slot"]["her_frame_at_cut"], 6)                    # restart at her frame
        self.assertEqual(p["slot"]["start_offset_ticks"], 6 * 800)
        keys = {k[0]: k for k in p["glide"]["keys"]}
        ge = p["glide_end"]["pose"]
        self.assertEqual(keys[tl["glide_in"][1]][1:7], ge["loc"] + ge["rot"])     # glide ends ON the dark pose
        self.assertNotEqual(ge["loc"], p["poses"]["her_cut"]["loc"])              # ... not her pose: a HARD cut
        self.assertEqual(p["cuts_after"][1][1][0], tl["glide_in"][0])
        self.assertLessEqual(tl["glide_in"][1], tl["cut"])
        for k in ("her_lights", "her_env", "hangar_lights", "rig_bulbs_hidden", "lattice", "glide", "hide",
                  "cuts_after", "hookin_edits", "slot", "extend_mode", "audio"):            # APPLY's keys
            self.assertIn(k, p)
        self.assertEqual(p["hookin_edits"]["hers_dark_range"], [tl["land"], tl["strike_window"][0]])

    def test_strikes_during_glide_on_character_lights(self):
        p, _a = plan5(HELD)
        tl, sch = p["timeline"], p["strike_schedule"]
        self.assertEqual(sch["frames"][0], tl["glide_in"][0])                   # first strike = glide start
        self.assertLess(sch["frames"][0], tl["glide_in"][1])
        self.assertLessEqual(sch["frames"][-1], tl["glide_in"][1])               # every strike DURING the glide
        self.assertTrue(tl["strikes_in_glide"])
        self.assertTrue(all(b > a for a, b in zip(sch["frames"], sch["frames"][1:])))
        struck = sorted(r["label"] for r in p["her_lights"] if r["strikes"])
        self.assertEqual(struck, sorted(p["v5"]["strike_lights"]))
        self.assertNotIn("SpotLight6", struck)                                  # a 60 cm practical: covers no one
        self.assertNotIn("SpotLight7", struck)
        self.assertIn("SpotLight", struck)                                      # the children's spots
        cover = p["v5"]["light_cover"]
        self.assertTrue(all(cover[x] for x in struck))
        self.assertTrue(any(not cover[x] for x in cover))                       # control: the filter excludes some
        order = [r for r in p["her_lights"] if r["strikes"]]
        self.assertEqual([r["label"] for r in order], [r["label"] for r in sorted(order, key=lambda r: r["strike_frame"])])
        dists = [r["dist_cm"] for r in order]
        self.assertEqual(dists, sorted(dists))                                   # near -> far from the glide end
        seed = "%s|S4" % V5ARGS["intro"]["seed"]
        for r in order:                                                          # S1's flicker machinery, unchanged
            want = R.dedupe_keys([[tl["land"], 0.0]] + R.strike_keys(r["target_intro"], r["strike_frame"], seed,
                                                                     r["label"], FPS, V5ARGS["intro"]["flicker_window_s"]))
            self.assertEqual(r["intro_keys"], want)
            self.assertGreater(len(r["intro_keys"]), 4)                          # a flicker, not a ramp
        for r in p["her_lights"]:
            if not r["strikes"]:
                self.assertEqual(r["intro_keys"], [[tl["land"], 0.0]])
        p2, _a = plan5(HELD, strike_lights=["SpotLight7"])                       # control: explicit list
        self.assertEqual([r["label"] for r in p2["her_lights"] if r["strikes"]], ["SpotLight7"])

    def test_strike_targets_plateau_vs_at_cut(self):
        p, _a = plan5(HELD)
        by = {r["label"]: r for r in p["her_lights"]}
        self.assertAlmostEqual(by["SpotLight"]["target_intro"], 160.0, places=3)     # plateau [bytes]
        self.assertTrue(any(w.startswith("V5_LIGHT_DROP_AT_HARD_CUT") for w in p["warnings"]))
        p2, _a = plan5(HELD, strike_target="at_cut")                                  # control: her value at frame 6
        by2 = {r["label"]: r for r in p2["her_lights"]}
        self.assertTrue(by["SpotLight"]["strikes"])
        self.assertFalse(by2["SpotLight"]["strikes"])                                # 0 at her frame 6 [bytes]


class Determinism(unittest.TestCase):
    def test_schedule_deterministic_and_seeded(self):
        a = R.schedule(6, 119, 260, FPS, "KLARA-REVEAL-7OCT|S4", (0.6, 1.2), 0.25)
        b = R.schedule(6, 119, 260, FPS, "KLARA-REVEAL-7OCT|S4", (0.6, 1.2), 0.25)
        self.assertEqual(a, b)
        c = R.schedule(6, 119, 260, FPS, "OTHER|S4", (0.6, 1.2), 0.25)            # control: the seed matters
        self.assertNotEqual(a["frames"], c["frames"])
        p1, _a = plan5(HELD)
        p2, _a = plan5(HELD)
        self.assertEqual(jsn(p1["her_lights"]), jsn(p2["her_lights"]))

    def test_across_processes_and_hash_seeds(self):
        code = ("import sys,json;sys.path.insert(0,%r);import klara_reveal as R;"
                "print(json.dumps([R.schedule(6,119,260,25.0,'KLARA-REVEAL-7OCT|S4',(0.6,1.2),0.25)['frames'],"
                "R.strike_keys(160.0,130,'KLARA-REVEAL-7OCT|S4','SpotLight',25.0)]))" % HERE)
        outs = set()
        for hs in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=hs)
            outs.add(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, check=True).stdout)
        self.assertEqual(len(outs), 1)

    def test_one_draw_per_statement(self):
        src = open(R.__file__, encoding="utf-8").read()
        lines = [ln for ln in src.splitlines() if "rng." in ln or "random." in ln]
        self.assertTrue(lines)                                                    # control: the scan sees draws
        self.assertEqual([ln for ln in lines if len(re.findall(r"\brng\.\w+\(", ln)) > 1], [])
        v5 = src[src.index("def v5_cfg("):src.index("# ----- live writers (APPLY)")]
        self.assertEqual(re.findall(r"\brng\.|random\.", v5), [])                  # v5 draws only via S1's helpers
        bad = "x = rng.uniform(0, 1) * rng.uniform(0, 1)"                          # control: the check can fail
        self.assertGreater(len(re.findall(r"\brng\.\w+\(", bad)), 1)


class PrerollRange(unittest.TestCase):
    def test_range_is_first_strike_to_cut(self):
        p, _a = plan5(HELD)
        pr, tl = p["preroll"], p["timeline"]
        self.assertEqual(pr["range"], [p["strike_schedule"]["frames"][0], tl["cut"]])
        self.assertEqual(pr["range"], tl["preroll"])
        self.assertEqual(pr["her_frame_start"], 192)
        self.assertEqual(pr["start_offset_ticks"], 192 * 800)
        self.assertLess(pr["her_frame_end"], 4920)
        q, _a = plan5(HELD, preroll_lead_frames=3)                                  # control: a lead moves it
        self.assertEqual(q["preroll"]["range"], [q["strike_schedule"]["frames"][0] - 3, q["timeline"]["cut"]])
        s, _a = plan5(HELD, strike_start_s=1.0)                                     # control: follows the strike
        self.assertEqual(s["preroll"]["range"][0], s["strike_schedule"]["frames"][0])
        self.assertEqual(s["preroll"]["range"][0] - p["preroll"]["range"][0], 25)

    def test_preroll_plan_from_record(self):
        p, _a = plan5(HELD)
        rec = {"applied": True, "plan": {k: p[k] for k in ("version", "preroll", "timeline")}}
        pp = P.preroll_plan(rec, [0, 4920], 800.0, 960.0)
        self.assertEqual(pp["refusals"], [])
        self.assertEqual(pp["range"], p["preroll"]["range"])
        self.assertEqual(pp["offset_ticks"], 192 * 800)
        self.assertTrue(P.preroll_plan(dict(rec, applied=False), [0, 4920], 800.0, 960.0)["refusals"])
        v4 = copy.deepcopy(rec)
        v4["plan"]["version"] = None
        self.assertTrue(P.preroll_plan(v4, [0, 4920], 800.0, 960.0)["refusals"])
        late = copy.deepcopy(rec)
        late["plan"]["preroll"]["range"][0] = late["plan"]["preroll"]["first_strike"] + 1
        self.assertTrue(any("AFTER_FIRST_STRIKE" in x for x in P.preroll_plan(late, [0, 4920], 800.0, 960.0)["refusals"]))


def copy_binding_rows(path=None):
    """klara_preroll_s4._binding_rows, from BYTES."""
    V = T._reader()
    path = path or T.LS_CHILDREN_COPY
    p = V.Package(path)
    b = T.derive_ls(path)
    rows = []
    for g, ps in b["poss"].items():
        tr = []
        for ti in b["tracks"].get(g, []):
            tp = {t["name"]: t for t in p.props(ti)}
            prop = None
            if "PropertyBinding" in tp:
                prop = p.fname(V.R(T._tags(p, tp["PropertyBinding"]["value"])["PropertyName"][2]))
            tr.append({"cls": p.cls(ti), "prop": prop})
        rows.append({"guid": g, "name": ps["name"], "parent": ps["parent"],
                     "cls": (ps.get("class") or "").split(".")[-1] or None, "tracks": tr})
    return rows, b


class PrerollStrip(unittest.TestCase):
    def test_strip_keeps_characters_only(self):
        rows, b = copy_binding_rows()
        lights = set()
        for r in T.derive_level_rows(T.L_CHILDREN).values():
            if "Light" in str(r.get("class")):
                lights.update([r.get("label", r["name"]), r["name"]])
        res = P.classify_bindings(rows, lights, [c["guid"] for c in b["cuts"]])
        self.assertEqual(res["refusals"], [])
        by = {r["guid"]: r for r in rows}
        kept = sorted(by[g]["name"] for g in res["keep"])
        want = sorted(["BP_MHC_Child"] + ["BP_MHC_Child%d" % i for i in range(2, 8)] + ["Body"] * 7 + ["Face"] * 7 +
                      ["Floor", "GC_Old_Book", "GeometryCacheComponent", "Paper_Fall_Cagliuso_Handwritten_30fps",
                       "Pendulum_Anchor", "SK_Pigeon_01"])
        self.assertEqual(kept, want)
        removed = {r["name"] for r in res["remove"]}
        self.assertTrue({"CineCameraActor", "CineCameraActor2", "CineCameraActor3", "CameraComponent", "SpotLight",
                         "LightComponent0", "Spot_MainLight_window"} <= removed)
        self.assertEqual(sum(1 for r in res["remove"] if r["name"] == "LightComponent0"), 12)   # 7 + 5 orphans
        # nothing kept resolves outside her S4 level (her own or its parent's locator) [meas bytes]
        for g in res["keep"]:                     # a 'subobj' locator resolves inside its parent binding's actor
            gg = g
            while "Path" not in b["refs"][gg][0][1]:
                gg = by[gg]["parent"]
            self.assertTrue(b["refs"][gg][0][1]["Path"].startswith("/Game/L_KK_children."), by[g]["name"])
        orph = [r["guid"] for r in res["remove"] if r["why"].startswith("light") and by[r["guid"]]["parent"] and by[r["guid"]]["parent"] not in by]
        # [bytes] in the COPY the 5 orphans' parent binding references are ABSENT (in her original they point at
        # L_Animals SpotLight_1/17/20/22/23): they resolve to nothing in the copy - stripped all the same
        self.assertEqual(len(orph), 5)
        self.assertTrue(all(by[g]["parent"] not in b["refs"] for g in orph))
        orig = T.derive_ls(T.LS_CHILDREN)
        self.assertTrue(all(orig["refs"][by[g]["parent"]][0][1]["Path"].startswith("/Game/KK_S1_Animals/L_Animals.")
                            for g in orph))                                            # control: her original
        # kept track classes only character animation
        self.assertTrue(all(t["cls"] in P.KEEP_TRACK_CLASSES for g in res["keep"] for t in by[g]["tracks"]))
        # children are removed before parents
        names = [r["name"] for r in res["remove"]]
        self.assertLess(names.index("CameraComponent"), names.index("CineCameraActor"))

    def test_controls(self):
        rows, b = copy_binding_rows()
        cuts = [c["guid"] for c in b["cuts"]]
        base = P.classify_bindings(rows, set(), cuts)
        self.assertEqual(base["refusals"], [])            # light rule needs no names: tracks/child names catch them
        bad = copy.deepcopy(rows)
        pend = [r for r in bad if r["name"] == "Pendulum_Anchor"][0]
        pend["tracks"].append({"cls": "MovieSceneFloatTrack", "prop": "SwingSpeed"})
        self.assertTrue(P.classify_bindings(bad, set(), cuts)["refusals"])            # unexpected kept track class
        nocut = P.classify_bindings([r for r in rows], set(), [])                     # cameras still go (class/props)
        self.assertNotIn("CineCameraActor", {rows_[ "name"] for rows_ in rows if rows_["guid"] in nocut["keep"]})
        orphan = [r for r in rows if r["name"] == "LightComponent0" and r["parent"] not in {x["guid"] for x in rows}]
        self.assertEqual(len(orphan), 5)

    def test_fingerprint_detects_reshift(self):
        rows = [{"binding": "Pendulum#0", "channel": "Location.X", "keys": [[0, 12810.82]], "default": 12810.82}]
        moved = copy.deepcopy(rows)
        moved[0]["default"] += 2204.3
        moved[0]["keys"][0][1] += 2204.3
        self.assertNotEqual(P.key_fingerprint(rows), P.key_fingerprint(moved))
        self.assertEqual(P.key_fingerprint(rows), P.key_fingerprint(copy.deepcopy(rows)))


def pendulum_chans():
    V = T._reader()
    p = V.Package(T.LS_CHILDREN_COPY)
    b = T.derive_ls(T.LS_CHILDREN_COPY)
    n = len(p.exports)
    g = [g for g, ps in b["poss"].items() if ps["name"] == "Pendulum_Anchor"][0]
    ti = [t for t in b["tracks"][g] if p.cls(t) == "MovieScene3DTransformTrack"][0]
    sec = [j for j in range(1, n + 1) if p.exports[j - 1]["outer"] == ti and p.cls(j).endswith("Section")][0]
    raw = {"%s[%d]" % (t["name"], t["index"]): T._key_curve(t["value"], True) for t in p.props(sec)
           if "DoubleChannel" in t["type"]}
    return {"Location.%s" % a: raw["Translation[%d]" % i] for i, a in enumerate("XYZ")} | \
        {"Rotation.%s" % a: raw["Rotation[%d]" % i] for i, a in enumerate("XYZ")}


class Pendulum(unittest.TestCase):
    def test_curve_matches_reveal_evaluator(self):
        ch = pendulum_chans()
        pit = ch["Rotation.Y"]
        self.assertEqual(len(pit["keys"]), 71)                                       # [bytes] investigation C
        for fr in (0, 6, 191, 250, 400, 1000, 4683, 4800):
            self.assertAlmostEqual(PD.curve_value(pit, fr), R.curve_at(pit, fr), places=6)
        self.assertAlmostEqual(PD.curve_value(pit, 6), 30.0, places=3)               # held until her 191
        self.assertNotAlmostEqual(PD.curve_value(pit, 300), 30.0, places=1)          # control: then it swings
        pr = PD.ls_prediction(ch, 300)
        self.assertAlmostEqual(pr["rot"][2], 130.0, places=3)
        self.assertAlmostEqual(pr["loc"][0] - T.S4_LT[0], 1375.15, places=1)          # LS anchor vs her LT [bytes]

    def _samples(self, rots, locs, window="t24s", tick=True, ls=True):
        ch = pendulum_chans()
        out = []
        for i, (r, l) in enumerate(zip(rots, locs)):
            pred = PD.ls_prediction(ch, 300 + i)
            out.append({"window": window, "loc": l if l != "ls" else pred["loc"], "rot": r if r != "ls" else pred["rot"],
                        "tick_enabled": tick, "pred_ls": pred if ls else None,
                        "pred_level": {"loc": [12300.8, 240040.3, 456.9]}})
        return out

    def test_classify(self):
        lv = [12300.8, 240040.3, 456.9]
        v = PD.classify_pendulum(self._samples(["ls"] * 3, ["ls"] * 3))
        self.assertEqual((v["verdict"], v["apply_recommended"], v["binding_resolves"]),
                         ("ls_wins_while_tick_enabled", True, True))
        v = PD.classify_pendulum(self._samples([[0, 12, 0]] * 3, ["ls"] * 3))
        self.assertEqual((v["verdict"], v["apply_recommended"]), ("tick_wins", True))
        v = PD.classify_pendulum(self._samples(["ls", [0, 12, 0], "ls"], ["ls"] * 3))
        self.assertEqual(v["verdict"], "tick_fights_ls")
        self.assertTrue(v["windows"]["t24s"]["who"].startswith("alternating"))
        v = PD.classify_pendulum(self._samples([[0, 12, 0]] * 3, [lv] * 3))           # LS never placed it
        self.assertEqual((v["verdict"], v["apply_recommended"]), ("binding_does_not_resolve", False))
        v = PD.classify_pendulum(self._samples(["ls"] * 3, ["ls"] * 3, tick=False))
        self.assertEqual((v["verdict"], v["apply_recommended"]), ("tick_disabled", False))
        v = PD.classify_pendulum(self._samples([[0, 12, 0]] * 3, [lv] * 3, window="t10s", ls=False))
        self.assertEqual((v["verdict"], v["apply_recommended"]), ("no_window_inside_her_sections", False))
        self.assertEqual(PD.classify_pendulum([])["verdict"], "no_samples")

    def test_her_frame_mapping(self):
        m = [{"range": [405, 4500], "her_start": 6, "ratio": 1.2, "what": "slot"},
             {"range": [119, 405], "her_start": 192, "ratio": 1.2, "what": "preroll"}]
        self.assertEqual(PD.her_frame_at(405, m), (6.0, "slot"))
        self.assertEqual(PD.her_frame_at(404, m)[1], "preroll")
        self.assertEqual(PD.her_frame_at(100, m), (None, None))
        self.assertGreater(PD.her_frame_at(600, m)[0], 191)                         # 24 s is past her frame 191
        self.assertAlmostEqual(PD.her_frame_at(600, m)[0], 6 + 195 * 1.2, places=9)    # 30/25 fps
        self.assertAlmostEqual(PD.her_frame_at(119, m)[0], 192.0, places=9)


class Args(unittest.TestCase):
    def test_arg_files(self):
        self.assertEqual(R.validate_args(V5ARGS), [])
        self.assertEqual(V5ARGS["mode"], "DRY")
        self.assertEqual(V5ARGS["decided_by"], "")                                 # APPLY refuses until filled
        bad = copy.deepcopy(V5ARGS)
        bad["scenes"]["4"]["v5"]["glide_end"]["mode"] = "sideways"
        self.assertTrue(R.validate_args(bad))
        pa = R.load_json(os.path.join(HERE, "klara_preroll_s4_args.json"))
        self.assertEqual(P.validate_args(pa), [])
        self.assertTrue(P.validate_args(dict(pa, dup_path=pa["copy"])))
        da = R.load_json(os.path.join(HERE, "klara_pendulum_s4_args.json"))
        self.assertEqual(PD.validate_args(da), [])
        self.assertEqual(da["mode"], "PROBE")
        self.assertTrue(PD.validate_args(dict(da, mode="MOVE")))
        g = {"mode": "DRY", "census": {}}
        self.assertEqual(P.live_gates(g), [])
        self.assertTrue(P.live_gates(dict(g, mode="APPLY", confirm="APPLY KLARAPREROLL")))      # decided_by empty
        self.assertTrue(P.live_gates(dict(g, pie=True)))

    def test_no_unreal_objects_in_module_globals(self):
        for m in (R, P, PD):
            src = open(m.__file__, encoding="utf-8").read()
            glob = [ln for ln in src.splitlines() if re.match(r"^[A-Za-z_]\w*\s*=.*\bunreal\.", ln)]
            self.assertEqual(glob, [], m.__name__)
        self.assertTrue(re.match(r"^[A-Za-z_]\w*\s*=.*\bunreal\.", "X = unreal.load_asset('a')"))   # control


# Seeded mutations of the v5 code (module, old, new): each must make at least one v5 test fail (the tests can fail).
V5_MUTATIONS = [
    ("R", "        if behind and not _in_ranges(fr, down):", "        if False:"),
    ("R", "        frames = set(range(a, b))", "        frames = {a}"),
    ("R", "        if s.get(\"keep_state\") and down_at_end and f1 < c1:", "        if s.get(\"keep_state\") and f1 < c1:"),
    ("R", "    strikers = [x for x in lights if x[\"label\"] in chosen and targets[x[\"label\"]] > min_v]",
     "    strikers = [x for x in lights if targets[x[\"label\"]] > min_v]"),
    ("R", "    P0 = S0 - int(cfg5.get(\"preroll_lead_frames\", 0))", "    P0 = S0 + 1"),
    ("R", "    loc = from_local(dock, [lc[0] - float(ge[\"pullback_cm\"])", "    loc = from_local(dock, [lc[0] + 0.0 * float(ge[\"pullback_cm\"])"),
    ("R", "    if not backcloth or backcloth.get(\"error\") or backcloth.get(\"loc\") is None:",
     "    if not backcloth:"),
    ("R", "    if (facts.get(\"reveal\") or {}).get(\"style\") == \"strike_preroll\":\n        return build_plan_v5",
     "    if (facts.get(\"reveal\") or {}).get(\"style\") in (\"strike_preroll\", \"her_dark_pan\"):\n        return build_plan_v5"),
    ("R", "        if lx < xmin:", "        if lx < xmin - 1.0e6:"),
    ("R", "    w1 = max(g1, S0 + span) if n_strike > 0 else S0", "    w1 = max(g1, S0 + span) + 200 if n_strike > 0 else S0"),
    ("P", "        elif props & set(LIGHT_PROPS) or r[\"name\"] in LIGHT_CHILD_NAMES or r[\"name\"] in light_names or \"Light\" in cls:",
     "        elif False:"),
    ("P", "        if r[\"guid\"] in cut_guids or r[\"name\"] in CAMERA_CHILD_NAMES or props & set(CAMERA_PROPS) or \"Camera\" in cls:",
     "        if False:"),
    ("PD", "        tick = abs(wrap(r[2])) <= tol_deg", "        tick = False and abs(wrap(r[2])) <= tol_deg"),
    ("PD", "            return float(m[\"her_start\"]) + (float(scene_frame) - float(m[\"range\"][0])) * float(m[\"ratio\"]), m[\"what\"]",
     "            return float(m[\"her_start\"]) + (float(scene_frame) - float(m[\"range\"][0])), m[\"what\"]"),
]
V5_TESTS = ("S1Unchanged", "PathGate", "Plan5", "PrerollRange", "PrerollStrip", "Pendulum")


def run_v5_mutations():
    mods = {"R": R, "P": P, "PD": PD}
    out = []
    for which, old, new in V5_MUTATIONS:
        m0 = mods[which]
        src = open(m0.__file__, encoding="utf-8").read()
        if src.count(old) != 1:
            out.append((old[:60], "ANCHOR_MISSING"))
            continue
        mod = types.ModuleType(m0.__name__ + "_mut")
        mod.__file__ = m0.__file__
        exec(compile(src.replace(old, new), m0.__file__, "exec"), mod.__dict__)
        g = globals()
        saved = g[which]
        g[which] = mod
        try:
            suite = unittest.TestSuite()
            for cls in V5_TESTS:
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(g[cls]))
            res = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
            out.append((old[:60], "CAUGHT" if (res.failures or res.errors) else "SURVIVED"))
        finally:
            g[which] = saved
    return out


class V5Mutations(unittest.TestCase):
    def test_every_mutation_is_caught(self):
        rows = run_v5_mutations()
        self.assertEqual([r for r in rows if r[1] != "CAUGHT"], [], rows)
        self.assertEqual(len(rows), len(V5_MUTATIONS))


if __name__ == "__main__":
    unittest.main(verbosity=1)
