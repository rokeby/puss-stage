"""Offline harness for klara_reveal.py pure maths (no Unreal). Every positive check has a negative control that must
FAIL the same check, so a planner that always says yes (or always no) cannot pass.
Run: python Saved/CodexConductor/KlaraIngest/test_klara_reveal_offline.py
Numbers: S1 land/cut/slot 104 / 376 / 5641 [meas klara_hookin_seq_record.json timeline]; dock (28784.0135, 0, 0) yaw 0
[meas klara_hookin_args.json]; box apron 500 depth 6000 half_w 1000 height 3000 lattice 1200 [decl hangar_build.py:61];
her S1 set 18.6 x 10.2 m, top 554 cm [meas klara_hookin_stream_record.json]. Camera/light values are SYNTHETIC.
"""
import copy
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import klara_reveal as R  # noqa: E402  (importing without unreal must run nothing)

with open(os.path.join(HERE, "klara_reveal_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
FPS = 25.0
DOCK = {"loc": [28784.0135, 0.0, 0.0], "yaw": 0.0}
BOX = {"dock": DOCK, "dock_z": 0.0, "apron": 500.0, "depth": 6000.0, "half_w": 1000.0, "height": 3000.0,
       "lattice_z": 1200.0}


def facts(n_lights=8, her_set=None, first_loc=None):
    # her set after the hookin: LevelTransform (32556, 122, 0), footprint centre at dock-local x 3772 [meas]
    her_set = her_set or [28784.0135 + 3772 - 928, 28784.0135 + 3772 + 928, 122 - 508, 122 + 508, 0.0, 554.0]
    first_loc = first_loc or [her_set[0] - 250.0, 60.0, 140.0]
    lights = [{"label": "SpotLight%d" % i, "name": "SpotLight_%d" % i, "class": "SpotLight",
               "loc": [her_set[0] + 200.0 * i, -300.0 + 80.0 * i, 400.0], "intensity": 1000.0 + i,
               "color": [1, 1, 1, 1], "visible": True, "hidden_in_game": False, "keyed": {}, "first": {}, "last": {},
               "target_first": 1000.0 + i, "target_last": 900.0 + i} for i in range(n_lights)]
    return {"scene": "1", "fps": FPS, "playback": [0, 0], "L": 104, "C": 376, "E": 5641, "box": BOX,
            "entry_camera": {"label": "Entry", "loc": [28784.0135, 0.0, 150.0], "rot": [0.0, 0.0, 0.0], "focal": 35.0,
                             "focus": 1000.0, "aperture": 2.8, "sensor": [36.0, 20.25]},
            "exit_camera": {"label": "Exit", "loc": [28784.0135, 0.0, 150.0], "rot": [0.0, 0.0, 180.0], "focal": 35.0,
                            "focus": 1000.0, "aperture": 2.8, "sensor": [36.0, 20.25]},
            "her_first": {"binding": "CineCameraActor4", "loc": first_loc, "rot": [0.0, -5.0, 10.0],
                          "vel_cm_s": [20.0, 0.0, 0.0], "ang_deg_s": [0.0, 0.0, 1.0],
                          "lens_tracks": {"CurrentFocalLength": 50.0, "ManualFocusDistance": 400.0},
                          "actor": {"sensor": [36.0, 20.25], "focal": 50.0, "focus": 400.0}},
            "her_last": {"binding": "CineCameraActor", "loc": [her_set[1] - 300.0, 0.0, 120.0], "rot": [0.0, 0.0, 170.0],
                         "vel_cm_s": [0.0, 0.0, 0.0], "ang_deg_s": [0.0, 0.0, 0.0],
                         "lens_tracks": {"CurrentFocalLength": 24.0}, "actor": {"sensor": [36.0, 20.25], "focal": 24.0,
                                                                                "focus": 300.0}},
            "set_world": her_set, "level_transform": {"loc": [32556.0135, 122.0, 0.0], "yaw": 0.0},
            "her_lights": lights,
            "her_env": [{"label": "DirectionalLight", "class": "DirectionalLight", "property": "Intensity",
                         "value": 6.0, "her_keyed": False},
                        {"label": "PostProcessVolume", "class": "PostProcessVolume", "property": "BlendWeight",
                         "value": 1.0, "unbound": True, "priority": 0.0, "enabled": True,
                         "exposure_overrides": {"auto_exposure_method": False}}],
            "hangar_lights": [{"label": "S1 Practical L1", "role": "black", "class": "SpotLight", "loc": [0, 0, 0],
                               "radius": 2500.0},
                              {"label": "S1 Lattice Glow 1-1", "role": "ceiling", "class": "PointLight", "loc": [0, 0, 0],
                               "radius": 800.0, "reach": R.glow_reach({"x": 0, "y": 0, "z": 1211}, 800.0, 0.0)}],
            "our_ppv": [{"label": "S1 Hangar Pinned Exposure", "priority": 0.0}], "label": "Scene 1 — External Sound"}


class Maths(unittest.TestCase):
    def test_wrap(self):
        self.assertEqual(R.wrap(190), -170)
        self.assertEqual(R.wrap(-180), 180)
        self.assertNotEqual(R.wrap(190), 190)                         # control

    def test_hermite_endpoints_and_velocity(self):
        self.assertEqual(R.hermite(1.0, 5.0, 3.0, -2.0, 2.0, 0.0), 1.0)
        self.assertEqual(R.hermite(1.0, 5.0, 3.0, -2.0, 2.0, 1.0), 5.0)
        self.assertAlmostEqual(R.hermite_vel(1.0, 5.0, 3.0, -2.0, 2.0, 0.0), 3.0, places=9)
        self.assertAlmostEqual(R.hermite_vel(1.0, 5.0, 3.0, -2.0, 2.0, 1.0), -2.0, places=9)
        self.assertNotAlmostEqual(R.hermite_vel(1.0, 5.0, 0.0, 0.0, 2.0, 0.5), 0.0)   # control: moving mid-glide

    def test_equiv_focal_keeps_hfov(self):
        f = R.equiv_focal(35.0, 36.0, 24.89)
        self.assertAlmostEqual(R.hfov_deg(35.0, 36.0), R.hfov_deg(f, 24.89), places=9)
        self.assertNotAlmostEqual(R.hfov_deg(35.0, 36.0), R.hfov_deg(35.0, 24.89), places=3)   # control

    def test_shift_channels_exact(self):
        ch = {"x": {"keys": [[0, 1.0], [10, 2.0]], "default": 5.0}, "y": {"keys": [], "default": None}}
        out = R.shift_channels(ch, [3.0, -1.0, 0.0])
        self.assertEqual(out["x"]["keys"], [[0, 4.0], [10, 5.0]])
        self.assertEqual(out["x"]["default"], 8.0)
        self.assertIsNone(out["y"]["default"])
        back = R.shift_channels(out, [-3.0, 1.0, 0.0])
        self.assertEqual(back["x"], ch["x"])
        self.assertNotEqual(R.shift_channels(ch, [0.5, 0, 0])["x"], ch["x"])          # control

    def test_eval_keys(self):
        keys = [[0, 1.0], [10, 3.0]]
        self.assertEqual(R.eval_keys(keys, None, 10), 3.0)
        self.assertEqual(R.eval_keys(keys, None, -5), 1.0)
        self.assertEqual(R.eval_keys(keys, None, 50), 3.0)
        self.assertIsNone(R.eval_keys(keys, None, 5))                 # control: between keys is NOT guessed
        self.assertEqual(R.eval_keys([], 7.0, 5), 7.0)

    def test_channel_base(self):
        self.assertEqual(R.channel_base("Location.X_183"), "Location.X")
        self.assertEqual(R.channel_base("Location.X"), "Location.X")

    def test_dedupe(self):
        self.assertEqual(R.dedupe_keys([[5, 1], [3, 2], [5, 9]]), [[3, 2], [5, 9]])


class Glide(unittest.TestCase):
    A = {"loc": [0.0, 0.0, 150.0], "rot": [0.0, 0.0, 170.0], "focal": 35.0, "focus": 1000.0}
    B = {"loc": [400.0, 50.0, 140.0], "rot": [0.0, -5.0, -170.0], "focal": 50.0, "focus": 400.0}

    def test_endpoints_bit_exact_and_speeds(self):
        g = R.plan_glide(self.A, self.B, 226, 376, FPS, v1=[20.0, 0.0, 0.0])
        self.assertEqual(g["keys"][0][1:], self.A["loc"] + self.A["rot"] + [35.0, 1000.0])
        self.assertEqual(g["keys"][-1][1:], self.B["loc"] + self.B["rot"] + [50.0, 400.0])
        self.assertEqual([k[0] for k in g["keys"]], list(range(226, 377)))
        self.assertAlmostEqual(g["report"]["start_speed_cm_s"], 0.0, places=9)
        self.assertAlmostEqual(g["report"]["end_speed_cm_s"], 20.0, places=6)
        g0 = R.plan_glide(self.A, self.B, 226, 376, FPS)                               # control: no end velocity
        self.assertNotAlmostEqual(g0["report"]["end_speed_cm_s"], 20.0, places=2)

    def test_keys_carry_velocity(self):
        g = R.plan_glide(self.A, self.B, 0, 150, FPS, v1=[20.0, 0.0, 0.0])
        g0 = R.plan_glide(self.A, self.B, 0, 150, FPS)                                 # control: zero end velocity
        fd = lambda gg: (gg["keys"][-1][1] - gg["keys"][-2][1]) * FPS                  # last-frame finite difference
        self.assertAlmostEqual(fd(g) - fd(g0), 20.0, delta=0.6)                        # the 20 cm/s is IN the keys
        self.assertLess(abs(fd(g0)), 2.0)

    def test_shortest_arc(self):
        g = R.plan_glide(self.A, self.B, 0, 100, FPS)
        self.assertAlmostEqual(g["report"]["turn_deg"][2], 20.0, places=9)             # 170 -> -170 is +20
        mid_yaw = g["keys"][50][6]
        self.assertTrue(170.0 <= mid_yaw <= 190.0, mid_yaw)
        self.assertNotAlmostEqual(g["report"]["turn_deg"][2], -340.0)                  # control

    def test_consecutive_frame_steps_smooth(self):
        g = R.plan_glide(self.A, self.B, 0, 150, FPS, v1=[20.0, 0, 0])
        steps = [math.dist(g["keys"][i][1:4], g["keys"][i + 1][1:4]) for i in range(len(g["keys"]) - 1)]
        jumps = [abs(steps[i + 1] - steps[i]) for i in range(len(steps) - 1)]
        self.assertLess(max(jumps), 0.5)                                               # no speed pop (cm/frame)
        bad = copy.deepcopy(g["keys"])
        bad[75][1] += 30.0                                                             # control: injected pop
        steps_b = [math.dist(bad[i][1:4], bad[i + 1][1:4]) for i in range(len(bad) - 1)]
        self.assertGreater(max(abs(steps_b[i + 1] - steps_b[i]) for i in range(len(steps_b) - 1)), 0.5)

    def test_empty_refused(self):
        with self.assertRaises(R.PlanError):
            R.plan_glide(self.A, self.B, 10, 10, FPS)


class Placement(unittest.TestCase):
    def test_camera_lands_lead_ahead(self):
        f = facts()
        p = R.solve_placement(f["her_first"]["loc"], f["set_world"][:4], 554.0, DOCK, BOX, 350.0, 500.0, 100.0)
        cam_after = [f["her_first"]["loc"][i] + p["delta"][i] for i in range(3)]
        self.assertAlmostEqual(cam_after[0], DOCK["loc"][0] + p["lead_cm"], places=6)
        self.assertAlmostEqual(cam_after[1], 0.0, places=6)
        self.assertEqual(p["delta"][2], 0.0)
        self.assertTrue(p["fits"])
        self.assertGreaterEqual(p["set_local_after"][0], 500.0 - 1e-6)

    def test_set_behind_camera_pushes_lead(self):
        f = facts()
        cam = [f["set_world"][0] + 400.0, 0.0, 140.0]                                  # camera INSIDE her set
        p = R.solve_placement(cam, f["set_world"][:4], 554.0, DOCK, BOX, 350.0, 500.0, 100.0)
        self.assertGreater(p["lead_cm"], 350.0)
        self.assertAlmostEqual(p["set_local_after"][0], 500.0, places=6)
        p2 = R.solve_placement(cam, f["set_world"][:4], 554.0, DOCK, BOX, 350.0, -1e9, 100.0)   # control
        self.assertEqual(p2["lead_cm"], 350.0)
        self.assertLess(p2["set_local_after"][0], 500.0)

    def test_too_wide_and_too_long(self):
        wide = [0.0, 1000.0, -1200.0, 1200.0]
        p = R.solve_placement([-100.0, 0.0, 100.0], wide, 100.0, {"loc": [0, 0, 0], "yaw": 0.0}, BOX, 350, 500, 100)
        self.assertFalse(p["checks"]["side_ok"])
        self.assertFalse(p["fits"])
        long_ = [0.0, 7000.0, -100.0, 100.0]
        p = R.solve_placement([-100.0, 0.0, 100.0], long_, 100.0, {"loc": [0, 0, 0], "yaw": 0.0}, BOX, 350, 500, 100)
        self.assertFalse(p["checks"]["far_ok"])
        ok = R.solve_placement([-100.0, 0.0, 100.0], [0, 1000, -100, 100], 100.0, {"loc": [0, 0, 0], "yaw": 0.0}, BOX,
                               350, 500, 100)
        self.assertTrue(ok["fits"])                                                    # control

    def test_off_axis_set_shifts_laterally(self):
        p = R.solve_placement([-100.0, 0.0, 100.0], [0, 1000, 0, 1700], 100.0, {"loc": [0, 0, 0], "yaw": 0.0}, BOX,
                              350, 500, 100)
        self.assertNotEqual(p["lateral_cm"], 0.0)
        self.assertTrue(p["checks"]["side_ok"])


class Hangar(unittest.TestCase):
    def test_proposal_snug_and_k(self):
        cur = {"apron": 500.0, "depth": 6000.0, "half_w": 1000.0, "height": 3000.0, "lattice_z": 1200.0}
        p = R.propose_hangar([500.0, 2100.0, -500.0, 500.0], 554.0, cur)   # 2100 + 300 - 500 = 1900 -> 2000
        self.assertEqual(p["params"]["depth"], 2000.0)
        self.assertEqual(p["params"]["half_w"], 1000.0)
        self.assertFalse(p["timing_changes"])
        big = R.propose_hangar([500.0, 9000.0, -500.0, 500.0], 554.0, cur)             # control: deeper than 2 x height
        self.assertTrue(big["timing_changes"])
        tall = R.propose_hangar([500.0, 2400.0, -500.0, 500.0], 1500.0, cur)
        self.assertGreater(tall["params"]["lattice_z"], 1200.0)

    def test_glow_reach(self):
        g = R.glow_reach({"x": 0.0, "y": 0.0, "z": 1211.0}, 800.0, 0.0, [-100, 100, -100, 100, 0, 554])
        self.assertFalse(g["reaches_floor"])
        self.assertTrue(g["reaches_set"])
        self.assertAlmostEqual(g["clamp_cm"], 1211 - 554 - 10, places=6)
        far = R.glow_reach({"x": 5000.0, "y": 0.0, "z": 1211.0}, 800.0, 0.0, [-100, 100, -100, 100, 0, 554])
        self.assertFalse(far["reaches_set"])                                           # control
        self.assertIsNone(far["clamp_cm"])
        low = R.glow_reach({"x": 0.0, "y": 0.0, "z": 500.0}, 800.0, 0.0)
        self.assertTrue(low["reaches_floor"])

    def test_surfaces_seen(self):
        box = BOX
        set_box = [800, 2600, -500, 500, 0, 554]
        s = R.surfaces_seen([400, 0, 150], [0, 0, 0], 40.0, 16 / 9, box, set_box)
        self.assertGreater(s["set"], s["left_wall"] + s["right_wall"] + s["far_wall"])
        side = R.surfaces_seen([400, 0, 150], [0, 0, 90], 40.0, 16 / 9, box, set_box)  # control: look at a wall
        self.assertGreater(side["right_wall"], 0)
        self.assertEqual(side["set"], 0)


class Lights(unittest.TestCase):
    def test_order(self):
        rows = [{"label": "b", "loc": [10, 0, 0]}, {"label": "a", "loc": [5, 0, 0]}, {"label": "c", "loc": [5, 0, 0]}]
        self.assertEqual([r["label"] for r in R.order_lights(rows, [0, 0, 0])], ["a", "c", "b"])
        self.assertEqual([r["label"] for r in R.order_lights(rows, [0, 0, 0], "far_to_near")], ["b", "c", "a"])
        with self.assertRaises(R.PlanError):
            R.order_lights(rows, [0, 0, 0], "random")

    def test_schedule_deterministic_and_bounded(self):
        a = R.schedule(8, 119, 350, FPS, "seed")
        b = R.schedule(8, 119, 350, FPS, "seed")
        self.assertEqual(a["frames"], b["frames"])
        self.assertTrue(all(y > x for x, y in zip(a["frames"], a["frames"][1:])))
        self.assertLessEqual(a["frames"][-1], 350)
        self.assertNotEqual(a["frames"], R.schedule(8, 119, 350, FPS, "other")["frames"])   # control: seed matters
        self.assertEqual(a["refusals"], [])

    def test_schedule_compresses_then_refuses(self):
        c = R.schedule(14, 119, 350, FPS, "seed")
        self.assertTrue(c["warnings"])
        self.assertEqual(c["refusals"], [])
        self.assertLessEqual(c["frames"][-1], 350)
        r = R.schedule(60, 119, 350, FPS, "seed")                                      # control: cannot fit
        self.assertTrue(r["refusals"])

    def test_schedule_frames_strictly_increase_when_crowded(self):
        c = R.schedule(80, 100, 160, FPS, "seed", min_gap_s=0.0)
        self.assertTrue(all(y > x for x, y in zip(c["frames"], c["frames"][1:])))
        self.assertTrue(c["refusals"])                                                 # 80 strikes cannot fit 60 frames

    def test_strike_keys(self):
        k = R.strike_keys(1000.0, 200, "seed", "SpotLight1", FPS)
        self.assertEqual(k[0], [199, 0.0])
        self.assertEqual(k[-1][1], 1000.0)
        n = (len(k) - 2) // 2
        self.assertTrue(2 <= n <= 4)
        self.assertLessEqual(k[-1][0] - 200, int(0.32 * FPS))
        self.assertEqual(k, R.strike_keys(1000.0, 200, "seed", "SpotLight1", FPS))
        one = R.strike_keys(1000.0, 200, "seed", "SpotLight1", FPS, window_s=0.12)    # control: window caps pulses
        self.assertEqual((len(one) - 2) // 2, 1)

    def test_blink_out(self):
        k = R.blink_out_keys(900.0, 5700, "seed", "SpotLight1", FPS)
        self.assertEqual(k[0], [5699, 900.0])
        self.assertEqual(k[-1][1], 0.0)
        self.assertNotEqual(k, R.blink_out_keys(900.0, 5700, "seed", "SpotLight2", FPS))   # per-light stream

    def test_ramp(self):
        r = R.ramp_keys(0.0, 6.0, 226, 366)
        self.assertEqual(r[0], [226, 0.0])
        self.assertEqual(r[-1], [366, 6.0])
        self.assertTrue(all(b[1] >= a[1] for a, b in zip(r, r[1:])))
        with self.assertRaises(R.PlanError):
            R.ramp_keys(0, 1, 5, 5)


class Timeline(unittest.TestCase):
    def test_order(self):
        t = R.plan_timeline(104, 376, 5641, FPS, 8, ARGS, 25)
        self.assertEqual(t["refusals"], [])
        self.assertTrue(t["land"] <= t["dark"][1] <= t["glide_in"][0] < t["cut"])
        self.assertTrue(t["glide_in"][0] <= t["crossfade"][0] < t["crossfade"][1] < t["cut"])
        self.assertEqual(t["hers_dark"], [104, t["glide_in"][0]])
        self.assertTrue(5641 < t["blink_window"][0] < t["glide_out"][0] < t["glide_out"][1] == t["exit_cut"][0])
        self.assertEqual(t["planned_end"], t["exit_cut"][1])
        self.assertGreaterEqual(t["glide_out"][0], t["env_out"][1])
        bad = R.plan_timeline(400, 376, 5641, FPS, 8, ARGS, 25)                        # control
        self.assertTrue(bad["refusals"])

    def test_short_glide_warns(self):
        t = R.plan_timeline(330, 376, 5641, FPS, 2, ARGS, 25)
        self.assertTrue(any("GLIDE_SHORT" in w for w in t["warnings"]))


class Plan(unittest.TestCase):
    def test_full_plan(self):
        p = R.build_plan(facts(), ARGS)
        self.assertEqual(p["refusals"], [], p["refusals"])
        tl = p["timeline"]
        keys = {k[0]: k for k in p["glide"]["keys"]}
        first, last = p["poses"]["her_first"], p["poses"]["her_last"]
        self.assertEqual(keys[tl["cut"]][1:7], first["loc"] + first["rot"])          # intro ends ON her first frame
        self.assertEqual(keys[tl["slot"][1]][1:7], last["loc"] + last["rot"])        # outro starts ON her last frame
        self.assertEqual(keys[tl["cut"]][7], 50.0)                                    # her lens, exact
        self.assertEqual(keys[tl["glide_in"][0]][1:4], [28784.0135, 0.0, 150.0])      # from the Entry pose
        cuts = p["cuts_after"]
        self.assertEqual(cuts[0][1][0], 0)
        self.assertTrue(all(cuts[i][1][1] == cuts[i + 1][1][0] for i in range(len(cuts) - 1)))
        self.assertEqual(cuts[-1][1][1], tl["planned_end"])
        for r in p["her_lights"]:
            self.assertEqual(r["intro_keys"][-1][1], r["target_first"])
            self.assertLess(r["intro_keys"][-1][0], tl["cut"])
            self.assertEqual(r["outro_keys"][0], [tl["slot"][1], r["target_last"]])
            self.assertEqual(r["outro_keys"][-1][1], 0.0)
            self.assertLess(r["outro_keys"][-1][0], tl["glide_out"][0])
        acts = {h["label"]: h["action"] for h in p["hangar_lights"]}
        self.assertEqual(acts, {"S1 Practical L1": "black_color", "S1 Lattice Glow 1-1": "keep"})
        self.assertEqual(p["hide"]["labels"], ["S1 Hangar Roof"])
        self.assertTrue(p["relength_first"])
        self.assertTrue(any("HER_PPV_NO_EXPOSURE_OVERRIDE" in w for w in p["warnings"]))
        self.assertTrue(any("PPV_PRIORITY" in w for w in p["warnings"]))

    def test_plan_refuses_when_set_too_wide(self):
        f = facts(her_set=[30000.0, 31000.0, -1500.0, 1500.0, 0.0, 300.0])           # control: 30 m wide
        p = R.build_plan(f, ARGS)
        self.assertTrue(any("SET_DOES_NOT_FIT_LIVE_BOX" in r for r in p["refusals"]))
        self.assertFalse(p["apply_ready"])

    def test_plan_refuses_on_order(self):
        f = facts()
        f["L"] = 500
        self.assertTrue(R.build_plan(f, ARGS)["refusals"])


class Args(unittest.TestCase):
    def test_args_valid(self):
        self.assertEqual(R.validate_args(ARGS), [])
        bad = copy.deepcopy(ARGS)
        bad["roof"] = "maybe"
        bad["scenes"]["1"]["scene_sequence"] = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
        errs = R.validate_args(bad)
        self.assertTrue(any("ROOF" in e for e in errs) and any("MASTER" in e for e in errs))

    def test_gates(self):
        ok = {"mode": "DRY", "census": {}, "hookin_applied": True}
        self.assertEqual(R.live_gates(ok), [])
        self.assertTrue(R.live_gates(dict(ok, hookin_applied=False)))
        self.assertTrue(R.live_gates(dict(ok, mode="APPLY", confirm="APPLY KLARAREVEAL")))   # decided_by empty
        self.assertEqual(R.live_gates(dict(ok, mode="APPLY", confirm="APPLY KLARAREVEAL", decided_by="x")), [])
        self.assertTrue(R.live_gates(dict(ok, pie=True)))
        self.assertTrue(R.live_gates(dict(ok, census={"maps": ["/Game/x"]})))


if __name__ == "__main__":
    unittest.main(verbosity=1)
