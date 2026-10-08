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
import klara_s4v5_preview as PV     # noqa: E402  (offline half only; the PIE half runs only under unreal)
import test_klara_reveal_offline as T   # noqa: E402  (bytes readers; defines tests but runs none on import)

FPS = 25.0
DRY4 = R.load_json(os.path.join(HERE, "klara_reveal_dry_S4.json"))
# The args FILE now carries Gary's 8 Oct P8 call (strike_lights "none", preroll "whole_glide"). The pre-existing tests
# below were written for the strike entry, so V5ARGS is the file with strike_lights "auto" and no preroll key (the
# 7 Oct v5 default); DarkArrival / Preview test the file as it stands (V5ARGS_LIVE).
V5ARGS_LIVE = R.load_json(os.path.join(HERE, "klara_reveal_s4v5_args.json"))
V5ARGS = copy.deepcopy(V5ARGS_LIVE)
V5ARGS["scenes"]["4"]["v5"]["strike_lights"] = "auto"
for _k in ("preroll", "preroll_note", "strike_lights_decided_by"):
    V5ARGS["scenes"]["4"]["v5"].pop(_k, None)
RECORD4 = R.load_json(os.path.join(HERE, "klara_reveal_record_S4.json"))     # the LIVE applied v4 [meas]
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


class PrerollLiveFixes(unittest.TestCase):
    """Pure controls for the S1 8 Oct fixes that apply to S4."""

    def test_subframe_tick_recovery(self):
        self.assertEqual(P.ticks_from_seconds(-17199 / 24000.0, 24000.0), -17199)
        self.assertEqual(P.section_ticks([(-22, -17199 / 24000.0), (2, 1600 / 24000.0)],
                                         24000.0, 800), [-17199, 1600])
        with self.assertRaises(P.PlanError):
            P.section_ticks([(-21, -17199 / 24000.0)], 24000.0, 800)

    def test_motion_coverage_gaps(self):
        self.assertEqual(P.coverage_gaps([[100, 200], [200, 260]], [100, 260]), [])
        self.assertEqual(P.coverage_gaps([[100, 150], [170, 260]], [100, 260]), [[150, 170]])
        self.assertEqual(P.coverage_gaps([], [100, 260]), [[100, 260]])

    def test_probe_gated_to_scene4_segment(self):
        filled = {119.0: 0, 374.0: 0}
        self.assertEqual(P.probe_gate(100119, 100000, 200000, 119.2, list(filled), filled, 3, 376),
                         (119.0, None))
        self.assertEqual(P.probe_gate(300119, 100000, 200000, 119.2, list(filled), filled, 3, 376),
                         (None, "NOT_IN_SCENE"))
        self.assertEqual(P.probe_gate(100376, 100000, 200000, 376.0, [374.0], {374.0: 0}, 3, 376),
                         (None, "NO_WINDOW"))

    def test_actor_match_stays_in_klara_level(self):
        c = [{"idx": 0, "label": "BP_MHC_Child", "name": "Wrong", "level_pkg": "/Game/Other/L"},
             {"idx": 1, "label": "BP_MHC_Child", "name": "Right", "level_pkg": "/Game/UEDPIE_0_L_KK_children"}]
        v = P.match_actor(c, "BP_MHC_Child", "Right", "/Game/L_KK_children")
        self.assertEqual((v["found"], v["idx"], v["level_match"]), (True, 1, "path"))
        self.assertFalse(P.match_actor(c[:1], "BP_MHC_Child", "Wrong", "/Game/L_KK_children")["found"])

    def test_probe_classification_positive_and_negative(self):
        moving = [{"subject": "Pigeon", "window": 119, "found": True, "pose": {"root": [0]}},
                  {"subject": "Pigeon", "window": 119, "found": True, "pose": {"root": [1]}}]
        self.assertEqual(P.classify_probe(moving)["answer"], "MOVING")
        static = copy.deepcopy(moving)
        static[1]["pose"] = {"root": [0]}
        self.assertEqual(P.classify_probe(static)["answer"], "STATIC_OR_UNCLEAR")
        tiny_drift = copy.deepcopy(moving)
        tiny_drift[1]["pose"] = {"root": [0.000001]}
        self.assertEqual(P.classify_probe(tiny_drift, tol=1e-5)["answer"], "STATIC_OR_UNCLEAR")

    def test_motion_signature_ignores_duplicate_guids_not_coverage(self):
        a = {"bindings": [{"binding": "Body", "guid": "SOURCE", "classes": ["Anim"],
                            "ranges_tick": [[0, 20]], "wanted_tick": [0, 20], "gaps_tick": []}]}
        b = copy.deepcopy(a)
        b["bindings"][0]["guid"] = "DUPLICATE"
        self.assertEqual(P.motion_coverage_signature(a), P.motion_coverage_signature(b))
        b["bindings"][0]["ranges_tick"] = [[0, 19]]
        self.assertNotEqual(P.motion_coverage_signature(a), P.motion_coverage_signature(b))


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
        self.assertEqual(R.validate_args(V5ARGS_LIVE), [])
        self.assertEqual(V5ARGS_LIVE["mode"], "DRY")
        self.assertEqual(V5ARGS_LIVE["decided_by"], "")                            # APPLY refuses until filled
        self.assertEqual(V5ARGS_LIVE["scenes"]["4"]["v5"]["strike_lights"], "none")   # Gary 7 Oct ~18:00
        self.assertEqual(V5ARGS_LIVE["scenes"]["4"]["v5"]["preroll"], "whole_glide")
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


PRE_DARK = "ae84495"            # the last commit of klara_reveal.py + s4v5 args BEFORE strike_lights "none"
_PRE = {}


def pre_dark():
    """(module, args) as committed at PRE_DARK, imported with unreal = None: the byte-identity baseline for 'auto'."""
    if "m" not in _PRE:
        root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

        def show(f):
            return subprocess.run(["git", "show", "%s:Saved/CodexConductor/KlaraIngest/%s" % (PRE_DARK, f)], cwd=root,
                                  capture_output=True, check=True).stdout.decode("utf-8")
        src = show("klara_reveal.py")
        if "v5_preroll_mode" in src or 'strike_lights"] == "none"' in src:
            raise AssertionError("pinned pre-dark commit already carries strike_lights none")
        m = types.ModuleType("klara_reveal_predark")
        m.__file__ = os.path.join(HERE, "klara_reveal_predark.py")
        exec(compile(src, m.__file__, "exec"), m.__dict__)
        a = json.loads(show("klara_reveal_s4v5_args.json"))
        if a["scenes"]["4"]["v5"].get("strike_lights") != "auto" or "preroll" in a["scenes"]["4"]["v5"]:
            raise AssertionError("pinned pre-dark args are not the auto entry")
        _PRE["m"], _PRE["a"] = m, a
    return _PRE["m"], _PRE["a"]


def dump(p):
    return json.dumps(jsn(p), sort_keys=True)


class DarkArrival(unittest.TestCase):
    """Gary 7 Oct ~18:00: "we don't strike up, we just arrive in the dark" -> strike_lights none."""

    def test_auto_plan_byte_identical_to_pre_change(self):
        H, pa = pre_dark()
        for bc in (HELD, STANDING):
            for extra in ({}, {"strike_target": "at_cut"}, {"strike_lights": ["SpotLight7"]},
                          {"preroll_lead_frames": 3}, {"strike_start_s": 1.0}):
                a = copy.deepcopy(pa)
                a["scenes"]["4"]["v5"].update(copy.deepcopy(extra))
                f = v5facts(bc, a)
                self.assertEqual(dump(H.build_plan(copy.deepcopy(f), a)), dump(R.build_plan(copy.deepcopy(f), a)),
                                 extra)
                self.assertEqual(H.validate_args(a), R.validate_args(a))
        # control: the comparator CAN fail - the old code reads "none" as a set of characters and refuses
        a = copy.deepcopy(pa)
        a["scenes"]["4"]["v5"]["strike_lights"] = "none"
        f = v5facts(HELD, a)
        old, new = H.build_plan(copy.deepcopy(f), a), R.build_plan(copy.deepcopy(f), a)
        self.assertNotEqual(dump(old), dump(new))
        self.assertTrue(any(x.startswith("V5_STRIKE_LIGHTS_UNKNOWN") for x in old["refusals"]))

    def _assert_dark(self, p):
        tl = p["timeline"]
        self.assertEqual(p["refusals"], [], p["refusals"])
        self.assertTrue(p["apply_ready"])
        self.assertEqual(p["v5"]["strike_lights"], [])
        self.assertEqual(p["strike_schedule"]["frames"], [])
        self.assertFalse(any(r["strikes"] for r in p["her_lights"]))
        self.assertTrue(all(r["intro_keys"] == [[tl["land"], 0.0]] for r in p["her_lights"]))     # 0 to the cut
        self.assertFalse(any(x.startswith("V5_NO_CHARACTER_LIGHT_STRIKES") for x in p["refusals"]))
        self.assertFalse(any(w.startswith("V5_LIGHT_DROP_AT_HARD_CUT") for w in p["warnings"]))    # Gary's question
        self.assertTrue(any(w.startswith("V5_DARK_ARRIVAL") for w in p["warnings"]))
        self.assertIn(p["preroll"]["mode"], ("off", "whole_glide"))
        if p["preroll"]["mode"] == "off":
            self.assertIsNone(p["preroll"]["range"])
            self.assertIsNone(tl["preroll"])
        else:
            self.assertEqual(p["preroll"]["range"], [tl["glide_in"][0], tl["cut"]])
            self.assertEqual(tl["preroll"], p["preroll"]["range"])
        keys = {k[0]: k for k in p["glide"]["keys"]}
        ge = p["glide_end"]["pose"]
        self.assertEqual(keys[tl["glide_in"][1]][1:7], ge["loc"] + ge["rot"])     # glides in the dark to the pose
        self.assertEqual(p["slot"]["her_frame_at_cut"], 6)                         # hard cut on her frame 6
        self.assertEqual(p["slot"]["range"][0], tl["cut"])
        self.assertLessEqual(tl["glide_in"][1], tl["cut"])

    def test_none_zero_strikes_no_refusal(self):
        p, _a = plan5(HELD, strike_lights="none")                    # preroll absent -> off
        self._assert_dark(p)
        q = R.build_plan(v5facts(HELD, V5ARGS_LIVE), V5ARGS_LIVE)   # shipped args: dark + whole-glide pre-roll
        self._assert_dark(q)
        self.assertEqual(q["preroll"]["mode"], "whole_glide")
        self.assertEqual(jsn(q["her_lights"]), jsn(p["her_lights"]))
        a, _a2 = plan5(HELD)                                          # control: auto still strikes
        self.assertGreater(len(a["strike_schedule"]["frames"]), 0)
        self.assertFalse(any(w.startswith("V5_DARK_ARRIVAL") for w in a["warnings"]))
        self.assertEqual(a["glide_end"]["pose"], p["glide_end"]["pose"])                 # same framing, same glide
        self.assertEqual(a["timeline"]["glide_in"], p["timeline"]["glide_in"])
        self.assertEqual(a["timeline"]["cut"], p["timeline"]["cut"])

    def test_empty_list_still_refuses(self):
        e, _a = plan5(HELD, strike_lights=[])                         # control: [] is not "none"
        self.assertTrue(any(x.startswith("V5_NO_CHARACTER_LIGHT_STRIKES") for x in e["refusals"]), e["refusals"])
        self.assertFalse(e["apply_ready"])
        self.assertTrue(any(x.startswith("V5_PREROLL_NEEDS_A_STRIKE") for x in e["refusals"]))  # default from_first_strike

    def test_preroll_modes(self):
        w, _a = plan5(HELD, strike_lights="none", preroll="whole_glide")
        self.assertEqual(w["refusals"], [], w["refusals"])
        self.assertEqual(w["preroll"]["range"], [w["timeline"]["glide_in"][0], w["timeline"]["cut"]])
        self.assertEqual(w["preroll"]["mode"], "whole_glide")
        w3, _a = plan5(HELD, strike_lights="none", preroll="whole_glide", preroll_lead_frames=3)
        self.assertEqual(w3["preroll"]["range"][0], w["preroll"]["range"][0] - 3)
        x, a = plan5(HELD, strike_lights="none", preroll="from_first_strike")
        self.assertTrue(any(r.startswith("V5_PREROLL_NEEDS_A_STRIKE") for r in x["refusals"]))
        self.assertTrue(any("V5_PREROLL_NEEDS_A_STRIKE" in r for r in R.validate_args(a)))
        o, _a = plan5(HELD, preroll="off")                            # auto strikes, no pre-roll
        self.assertGreater(len(o["strike_schedule"]["frames"]), 0)
        self.assertIsNone(o["preroll"]["range"])
        d, _a = plan5(HELD)
        e, _a = plan5(HELD, preroll="from_first_strike")              # explicit = the default range, + its mode
        self.assertEqual(e["preroll"]["range"], d["preroll"]["range"])
        self.assertNotIn("mode", d["preroll"])                        # default keeps the auto plan byte-identical
        self.assertEqual(e["preroll"]["mode"], "from_first_strike")
        for bad in ({"preroll": "sometimes"}, {"strike_lights": "all"}, {"strike_lights": "None"}):
            self.assertTrue(R.validate_args(v5args(**bad)), bad)
        self.assertEqual(R.validate_args(v5args(strike_lights="none")), [])
        self.assertEqual(R.v5_preroll_mode({"strike_lights": "none"}), "off")
        self.assertEqual(R.v5_preroll_mode({"strike_lights": "auto"}), "from_first_strike")

    def test_env_ramp_flagged_when_preroll_off(self):
        p, _a = plan5(HELD, strike_lights="none", preroll="off")
        w = [x for x in p["warnings"] if x.startswith("V5_PREROLL_OFF_ENV_RAMPS")]
        self.assertEqual(len(w), 1)
        self.assertIn("DirectionalLight", w[0])
        q, _a = plan5(HELD, strike_lights="none", preroll="whole_glide")     # control: not when characters move
        self.assertFalse(any(x.startswith("V5_PREROLL_OFF_ENV_RAMPS") for x in q["warnings"]))

    def test_preroll_tool_skips_or_refuses(self):
        p, _a = plan5(HELD, strike_lights="none")
        rec = {"applied": True, "plan": {k: p[k] for k in ("version", "preroll", "timeline")}}
        pp = P.preroll_plan(rec, [0, 4920], 800.0, 960.0)
        self.assertTrue(pp.get("skip"))
        self.assertTrue(pp["refusals"][0].startswith("PREROLL_OFF"))
        g = P.preroll_off_gate("DRY", rec)
        self.assertEqual(g[0], "SKIP")
        self.assertTrue(g[1].startswith("PREROLL_OFF|"))
        self.assertEqual(P.preroll_off_gate("APPLY", rec)[0], "STOP")
        self.assertIsNone(P.preroll_off_gate("REVERT", rec))          # an applied pre-roll stays revertable
        a, _a = plan5(HELD)                                            # control: the strike entry proceeds
        reca = {"applied": True, "plan": {k: a[k] for k in ("version", "preroll", "timeline")}}
        self.assertIsNone(P.preroll_off_gate("DRY", reca))
        self.assertIsNone(P.preroll_off_gate("APPLY", reca))
        self.assertEqual(P.preroll_plan(reca, [0, 4920], 800.0, 960.0)["refusals"], [])
        self.assertIsNone(P.preroll_off_gate("APPLY", dict(rec, applied=False)))   # the normal path refuses it
        src = open(P.__file__, encoding="utf-8").read()
        main = src[src.index("def main():"):]
        self.assertLess(main.index("preroll_off_gate(mode"), main.index('{"DRY": run_dry'))
        skip = [ln for ln in main.splitlines() if "KLARAPREROLL_SKIPPED" in ln]
        self.assertEqual(len(skip), 1)
        self.assertIn("log_warning", skip[0])
        self.assertNotIn("_OK", skip[0])


class Preview(unittest.TestCase):
    def test_pose_matches_the_harness_plan(self):
        pose = PV.preview_pose(DRY4, V5ARGS_LIVE, RECORD4)
        full = R.build_plan(v5facts(HELD, V5ARGS_LIVE), V5ARGS_LIVE)       # bytes fixtures: subjects, cuts, cloth
        pose2 = PV.preview_pose(DRY4, V5ARGS_LIVE, RECORD4, plan=full)
        self.assertEqual(pose["poses"], pose2["poses"])
        self.assertEqual(pose["v5_frames"], pose2["v5_frames"])
        self.assertTrue(pose["ok"], (pose["plan_refusals_other"], pose["live"].get("why")))
        self.assertEqual(pose["n_strikes"], 0)
        self.assertEqual(pose["preroll"], "whole_glide")
        ge = pose["poses"]["glide_end"]
        for got, want in zip(ge["loc"] + ge["rot_roll_pitch_yaw"], [11527.667, 240000.0, 211.0, 0.0, -4.0, 5.0]):
            self.assertAlmostEqual(got, want, places=2)
        self.assertEqual(ge["focal_mm"], 24.0)
        hc = pose["poses"]["her_cut"]
        self.assertEqual(hc["her_frame"], 6)
        self.assertNotEqual(hc["loc"], ge["loc"])                                       # a hard cut
        fr = pose["v5_frames"]
        self.assertEqual((fr["glide_start"], fr["glide_end"], fr["cut"]), (119, 269, 376))
        self.assertEqual(fr["master_ticks_from_scene_start"]["cut"], 376 * 960)
        self.assertEqual(sorted(x.split(":")[0].split(" ")[0] for x in pose["plan_refusals_offline_expected"]),
                         ["BACKCLOTH_STATE_UNREAD", "HER_CUT_PATHS_UNREAD"])
        with self.assertRaises(PV.PreviewError):                                         # control: auto args
            PV.preview_pose(DRY4, V5ARGS, RECORD4)

    def test_live_validity_and_frames(self):
        pose = PV.preview_pose(DRY4, V5ARGS_LIVE, RECORD4)
        lv = pose["live"]
        self.assertTrue(lv["valid"])
        self.assertEqual(lv["level_delta_live_minus_v5_cm"], [0.0, 0.0, 0.0])
        self.assertEqual(lv["frames"], {"dark": 320, "env": 404, "her": 405})
        self.assertEqual(lv["frames"]["her"], RECORD4["plan"]["slot"]["range"][0])
        dk, en = lv["states"]["dark"], lv["states"]["env"]
        self.assertTrue(dk["her_lights_all_zero"] and dk["env_all_zero"] and dk["bulbs_hidden"])
        self.assertTrue(all(g["rgb_max"] == 0.0 for g in dk["ceiling_glows"].values()))
        self.assertFalse(en["her_lights_all_zero"])                                       # control: brighter bracket
        self.assertTrue(all(abs(v["value"] - v["her_value"]) < 1e-6 for v in en["her_env"].values()))
        moved = copy.deepcopy(RECORD4)                                                    # control: wrong placement
        moved["plan"]["level_transform_after"]["loc"][0] += 100.0
        bad = PV.preview_pose(DRY4, V5ARGS_LIVE, moved)
        self.assertFalse(bad["live"]["valid"])
        self.assertFalse(bad["ok"])
        self.assertFalse(PV.preview_pose(DRY4, V5ARGS_LIVE, dict(RECORD4, applied=False))["ok"])

    def test_pure_helpers(self):
        self.assertEqual(PV.keys_at([[0, 0.0], [10, 1.0]], 10), (1.0, "key"))
        self.assertEqual(PV.keys_at([[0, 0.0], [10, 1.0]], 5), (0.5, "linear"))
        self.assertEqual(PV.keys_at([[0, 0.0], [10, 1.0]], 20), (1.0, "after_last"))
        self.assertEqual(PV.keys_at([[0, [0, 0, 0, 1]], [10, [1, 1, 1, 1]]], 5)[0], [0.5, 0.5, 0.5, 1.0])
        self.assertEqual(PV.keys_at([], 3), (None, "unkeyed"))
        self.assertEqual(PV.master_ticks(1000, 320, 25.0), 1000 + 320 * 960)
        self.assertNotEqual(PV.master_ticks(1000, 320, 30.0), PV.master_ticks(1000, 320, 25.0))   # control

    def test_args_request_and_call_sequence(self):
        a = R.load_json(os.path.join(HERE, "klara_s4v5_preview_args.json"))
        self.assertEqual(PV.validate_args(a), [])
        self.assertTrue(PV.validate_args(dict(a, phase="save")))                          # control
        self.assertTrue(PV.validate_args(dict(a, phase="camera", pose_key=None)))
        self.assertTrue(PV.validate_args(dict(a, phase="shot", path="relative.png")))
        req = R.load_json(os.path.join(HERE, "klara_s4v5_preview_request.json"))
        self.assertEqual(req["arguments"]["arguments"]["relativeSavedPath"],
                         "CodexConductor/KlaraIngest/klara_s4v5_preview.py")
        pose = PV.preview_pose(DRY4, V5ARGS_LIVE, RECORD4)
        seq = PV.call_sequence(pose, "T")
        self.assertEqual(len(seq), 22)
        self.assertEqual([PV.validate_args(s) for s in seq], [[]] * 22)
        live = False
        for s in seq:                                    # every camera is cleaned up before the next one
            if s["phase"] == "camera":
                self.assertFalse(live)
                live = True
            if s["phase"] == "cleanup":
                live = False
            if s["phase"] == "shot":
                self.assertEqual(s["expect_view"], "preview" if live else "show")
        self.assertFalse(live)
        evs = {s["run"]: s["exposure_bias_ev"] for s in seq}
        self.assertEqual(evs, {"T-dark_true": None, "T-dark_plus6ev": 6.0, "T-env_true": None, "T-her_f6": None})
        self.assertEqual({s["scene_frame"] for s in seq if s["run"] == "T-her_f6"}, {405})
        self.assertEqual(len({s["path"] for s in seq if s["phase"] == "shot"}), 4)       # no file reused

    def test_pie_half_rules(self):
        import inspect
        src = open(PV.__file__, encoding="utf-8").read()
        glob = [ln for ln in src.splitlines() if re.match(r"^[A-Za-z_]\w*\s*=.*\bunreal\.", ln)]
        self.assertEqual(glob, [])
        for fn in (PV.main, PV.phase_jump, PV.phase_camera, PV.phase_shot, PV.phase_check, PV.phase_cleanup):
            body = inspect.getsource(fn)
            self.assertNotIn("import klara_reveal", body)                # no Saved/ import in the PIE path
            for banned in ("save_", "end_play", "quit", "get_sequence_player", "spawn_actor_from_class",
                           "EditorActorSubsystem"):
                self.assertNotIn(banned, body, (fn.__name__, banned))
        self.assertEqual(src.count("_ok(run, phase, extra)"), 1)            # the one OK, after the census check
        main = inspect.getsource(PV.main)
        self.assertLess(main.index("after = _census()"), main.index("_ok(run, phase, extra)"))
        self.assertIn("set_view_target_with_blend(cam, 0.0)", inspect.getsource(PV.phase_camera))
        self.assertIn("scrub_to_master_frame", inspect.getsource(PV.phase_jump))
        self.assertIn("unreal.InfinityCueType.SCENE", inspect.getsource(PV._segment))


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
V5_MUTATIONS += [                     # 7 Oct evening: strike_lights none / preroll modes / preview
    ("R", "    if not strikers and cfg5[\"strike_lights\"] != \"none\":", "    if not strikers:"),
    ("R", "    if not strikers and cfg5[\"strike_lights\"] != \"none\":", "    if False:"),
    ("R", "    elif cfg5[\"strike_lights\"] == \"none\":            # Gary", "    elif False:            # Gary"),
    ("R", "        return \"off\" if cfg5.get(\"strike_lights\") == \"none\" else \"from_first_strike\"",
     "        return \"from_first_strike\""),
    ("R", "        P0 = d0 - int(cfg5.get(\"preroll_lead_frames\", 0))",
     "        P0 = S0 - int(cfg5.get(\"preroll_lead_frames\", 0)) + 1"),
    ("R", "        if cfg5.get(\"preroll\") is not None:", "        if True:"),
    ("P", "    if plan.get(\"version\") == 5 and pr and pr.get(\"mode\") == \"off\":", "    if False:"),
    ("P", "    return (\"SKIP\", reason) if m == \"DRY\" else (\"STOP\", reason)", "    return (\"SKIP\", reason)"),
    ("PV", "    frames = {\"dark\": int(tl[\"crossfade\"][0]), ", "    frames = {\"dark\": int(tl[\"crossfade\"][0]) - 20, "),
    ("PV", "    out[\"valid\"] = max(abs(v) for v in dl) <= LT_TOL_CM",
     "    out[\"valid\"] = True or max(abs(v) for v in dl) <= LT_TOL_CM"),
    ("PV", "    if cfg5.get(\"strike_lights\") != \"none\":", "    if False:"),
]
V5_TESTS = ("S1Unchanged", "PathGate", "Plan5", "PrerollRange", "PrerollLiveFixes", "PrerollStrip",
            "Pendulum", "DarkArrival", "Preview")


def run_v5_mutations():
    mods = {"R": R, "P": P, "PD": PD, "PV": PV}
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
