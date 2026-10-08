"""Offline harness for klara_reveal.py pure maths (no Unreal). Every positive check has a negative control that must
FAIL the same check, so a planner that always says yes (or always no) cannot pass.
Run: python Saved/CodexConductor/KlaraIngest/test_klara_reveal_offline.py
Numbers: S1 land/cut/slot 104 / 376 / 5641 [meas klara_hookin_seq_record.json timeline]; dock (28784.0135, 0, 0) yaw 0
[meas klara_hookin_args.json]; box apron 500 depth 6000 half_w 1000 height 3000 lattice 1200 [decl hangar_build.py:61];
her S1 set 18.6 x 10.2 m, top 554 cm [meas klara_hookin_stream_record.json]. Camera/light values are SYNTHETIC.
v3 (lit frame): her copy range [-310, 6008) at 30 fps, 800 ticks/frame [meas klara_reveal_dry_S1.json her_range,
her_first.fps; klara_hookin_seq_record.json her_span.ticks_per_frame]; her light CURVES are SYNTHETIC (her real keys
were never read - the v2 DRY kept only first/last values).
"""
import copy
import json
import math
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import klara_reveal as R  # noqa: E402  (importing without unreal must run nothing)

with open(os.path.join(HERE, "klara_reveal_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
ARGS["allow_lattice_overlap"] = False      # the harness pins plan switches; the live args file may differ
ARGS["lattice"] = "cancel"
# 7 Oct (v5 session): the live args now carry Gary's S1 roof "keep" (scenes.1.roof); the harness pins the plan switch
# to the global "hide_roof" its assertions were written for (fixture fault, not a code fault: Plan.test_full_plan).
ARGS["scenes"]["1"].pop("roof", None)
TPF = 960                                  # 24000 / 25
# the rise's lattice lowering [meas hangar_retime_record.json scenes.1.after_keys.lattice_fly_z]: 2800 -> 1200 over
# 12.6261..16.6261 s; tangents SYNTHETIC (cubic, value/tick)
RISE_KEYS = [{"tick": 0, "value": 2800.0, "interp": "cubic", "arrive": 0.0, "leave": 0.0},
             {"tick": int(12.6261 * 24000), "value": 2800.0, "interp": "cubic", "arrive": 0.0, "leave": -0.002},
             {"tick": int(16.6261 * 24000), "value": 1200.0, "interp": "cubic", "arrive": -0.004, "leave": 0.0}]
FPS = 25.0
DOCK = {"loc": [28784.0135, 0.0, 0.0], "yaw": 0.0}
BOX = {"dock": DOCK, "dock_z": 0.0, "apron": 500.0, "depth": 6000.0, "half_w": 1000.0, "height": 3000.0,
       "lattice_z": 1200.0}


HER_LO, HER_HI, HER_FPS, HER_TPF = -310, 6008, 30.0, 800


def ramp_curve(t0, t1, v, extra=None):
    """Synthetic her Intensity: 0 at her start, 0 until t0, LINEAR up to v at t1 (her display frames)."""
    keys = [{"tick": HER_LO * HER_TPF, "value": 0.0, "interp": "linear", "arrive": 0.0, "leave": 0.0},
            {"tick": t0 * HER_TPF, "value": 0.0, "interp": "linear", "arrive": 0.0, "leave": 0.0},
            {"tick": t1 * HER_TPF, "value": float(v), "interp": "linear", "arrive": 0.0, "leave": 0.0}]
    keys += extra or []
    return {"tpf": float(HER_TPF), "keys": sorted(keys, key=lambda k: k["tick"]), "default": 0.0}


# lit at (ramp end): 120, 150, 180, 200, 210, 222, 227, 900(late) -> 7 of 8 ever lit by 227; 80% of 8 = 7th = 227
RAMPS = [(60, 120), (90, 150), (120, 180), (150, 200), (160, 210), (170, 222), (180, 227), (850, 900)]


def facts(n_lights=8, her_set=None, first_loc=None):
    # her set after the hookin: LevelTransform (32556, 122, 0), footprint centre at dock-local x 3772 [meas]
    her_set = her_set or [28784.0135 + 3772 - 928, 28784.0135 + 3772 + 928, 122 - 508, 122 + 508, 0.0, 554.0]
    first_loc = first_loc or [her_set[0] - 250.0, 60.0, 140.0]
    lights = [{"label": "SpotLight%d" % i, "name": "SpotLight_%d" % i, "class": "SpotLight",
               "loc": [her_set[0] + 200.0 * i, -300.0 + 80.0 * i, 400.0], "intensity": 1000.0 + i,
               "color": [1, 1, 1, 1], "visible": True, "hidden_in_game": False, "keyed": {}, "first": {}, "last": {},
               "target_first": 0.0, "target_last": 900.0 + i,
               "curves": {"Intensity": ramp_curve(RAMPS[i % len(RAMPS)][0], RAMPS[i % len(RAMPS)][1], 1000.0 + i)}}
              for i in range(n_lights)]
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
            "her_lights": lights, "her_range": [HER_LO, HER_HI], "her_fps": HER_FPS, "her_tpf": HER_TPF,
            "her_env": [{"label": "DirectionalLight", "class": "DirectionalLight", "property": "Intensity",
                         "value": 6.0, "her_keyed": False},
                        {"label": "PostProcessVolume", "class": "PostProcessVolume", "property": "BlendWeight",
                         "value": 1.0, "unbound": True, "priority": 0.0, "enabled": True,
                         "exposure_overrides": {"auto_exposure_method": False}}],
            "hangar_lights": [{"label": "S1 Practical L1", "role": "black", "class": "SpotLight", "loc": [0, 0, 0],
                               "radius": 2500.0},
                              {"label": "S1 Lattice Glow 1-1", "role": "ceiling", "class": "PointLight", "loc": [0, 0, 0],
                               "color": [1.0, 1.0, 1.0, 1.0],
                               "radius": 800.0, "reach": R.glow_reach({"x": 0, "y": 0, "z": 1211}, 800.0, 0.0)}],
            "our_ppv": [{"label": "S1 Hangar Pinned Exposure", "priority": 0.0}], "label": "Scene 1 — External Sound",
            "tick": 24000.0, "rig_bulbs": ["S1 Lattice Bulb 1-1"],
            "lattice_pieces": ["S1 Hangar Lattice Fly", "S1 Hangar Lattice Beam 01", "S1 Lattice Glow 1-1"],
            "lattice": {"keys": RISE_KEYS, "offset_ticks": 0, "section": [0, 775], "play_rate": 1.0}}


def her_lit_pose(f, frame):
    p = dict(copy.deepcopy(f["her_first"]))
    p.update(frame=frame, cut=[HER_LO, HER_HI], loc=[f["her_first"]["loc"][0] + 100.0, 60.0, 160.0],
             rot=[0.0, -2.0, 4.0], vel_cm_s=[0.0, 0.0, 0.0], lens_tracks={"CurrentFocalLength": 40.0,
                                                                          "ManualFocusDistance": 500.0})
    return p


def v3facts(args=None, **kw):
    """What gather does, minus Unreal: detect + snap the lit frame, read her camera AT it, values AT it."""
    f = facts(**kw)
    f["lit"] = R.detect_lit(f, args or ARGS, FPS)
    if f["lit"]["frame"] is not None:
        f["her_lit"] = her_lit_pose(f, f["lit"]["frame"])
        R.apply_lit_values(f, f["lit"]["frame"])
    return f


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


class Footprint(unittest.TestCase):
    ROWS = [
        {"label": "Floor", "class": "StaticMeshActor", "components": ["StaticMeshComponent"],
         "bounds": [100.0, 0.0, -5.0, 900.0, 500.0, 5.0]},
        {"label": "Pig", "class": "SkeletalMeshActor", "components": ["SkeletalMeshComponent"],
         "bounds": [200.0, 100.0, 50.0, 60.0, 30.0, 50.0]},
        {"label": "SkySphere", "class": "StaticMeshActor", "components": ["StaticMeshComponent"],
         "bounds": [0.0, 0.0, 0.0, 400000.0, 400000.0, 400000.0]},
        {"label": "SkyAtmosphere", "class": "SkyAtmosphere", "components": ["SkyAtmosphereComponent"],
         "bounds": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]},
        {"label": "Fog", "class": "ExponentialHeightFog", "components": ["ExponentialHeightFogComponent"],
         "bounds": [0.0, 0.0, -1026.0, 4000.0, 4000.0, 50.0]},
        {"label": "SpotLight2", "class": "SpotLight", "components": ["DrawFrustumComponent"],
         "bounds": [3000.0, 0.0, 400.0, 2000.0, 2000.0, 2000.0]},
        {"label": "PPV", "class": "PostProcessVolume", "components": ["BrushComponent"],
         "bounds": [0.0, 0.0, 0.0, 4000.0, 4000.0, 4000.0]},
        {"label": "BP_Empty", "class": "BP_Marker_C", "components": ["BillboardComponent"],
         "bounds": [9000.0, 0.0, 0.0, 10.0, 10.0, 10.0]},
        {"label": "Backdrop", "class": "StaticMeshActor", "components": ["StaticMeshComponent"],
         "bounds": [0.0, 3000.0, 0.0, 2500.0, 10.0, 800.0]},
    ]

    def test_only_diorama_meshes(self):
        fp = R.footprint_from_rows(self.ROWS)
        self.assertEqual(sorted(k["label"] for k in fp["kept"]), ["Floor", "Pig"])
        self.assertEqual(fp["box"], [-800.0, 1000.0, -500.0, 500.0, -10.0, 100.0])
        why = {e["label"]: e["why"] for e in fp["excluded"]}
        self.assertIn("size", why["SkySphere"])
        self.assertIn("size", why["Backdrop"])
        self.assertIn("class", why["SpotLight2"])
        self.assertIn("component", why["BP_Empty"])
        loose = R.footprint_from_rows(self.ROWS, max_size_cm=1e9)                     # control: no size cap
        self.assertGreater(loose["box"][1] - loose["box"][0], 100000.0)

    def test_empty(self):
        self.assertIsNone(R.footprint_from_rows(self.ROWS[3:7])["box"])


class GlideLength(unittest.TestCase):
    def test_peak_bounded(self):
        a = {"loc": [0.0, 0.0, 150.0], "rot": [0, 0, 0], "focal": 35.0, "focus": 1000.0}
        b = {"loc": [3700.0, 0.0, 80.0], "rot": [0, 0, 0], "focal": 24.0, "focus": 430.0}
        t, peak = R.glide_seconds(a, b, FPS, [0.0, 0.0, 0.0], 300.0, 6.0)
        self.assertLessEqual(peak, 300.0)
        self.assertGreater(t, 6.0)
        g = R.plan_glide(a, b, 0, int(round((t - 0.5) * FPS)), FPS)                    # control: 0.5 s shorter is too fast
        self.assertGreater(g["report"]["peak_speed_cm_s"], 300.0)
        short = {"loc": [600.0, 0.0, 150.0], "rot": [0, 0, 0], "focal": 35.0, "focus": 1000.0}
        self.assertEqual(R.glide_seconds(a, short, FPS, [0.0, 0.0, 0.0], 300.0, 6.0)[0], 6.0)


class Timeline(unittest.TestCase):
    def test_v2_order_glide_in_dark_then_light(self):
        t = R.plan_timeline(104, 376, 5641, FPS, 14, ARGS, 25, glide_in_s=6.0, glide_out_s=8.0)
        self.assertEqual(t["refusals"], [])
        d0, g1, S0 = t["dark"][1], t["glide_in"][1], t["strike_window"][0]
        self.assertEqual(t["glide_in"][0], d0)
        self.assertLess(g1, S0)                                                       # glide ends BEFORE any light
        self.assertEqual(t["glow_fade"][1], S0)                                       # rig glows out by the first strike
        self.assertGreaterEqual(t["glow_fade"][0], d0)
        self.assertEqual(t["glow_fade"][1] - t["glow_fade"][0], math.ceil(1.5 * FPS))   # a FADE, not a cut
        self.assertEqual(t["crossfade"][0], S0)                                       # her env starts with her lights
        self.assertEqual(t["hers_dark"], [104, S0])
        self.assertEqual(t["roof_hidden"][0], g1)                                     # roof goes while still dark
        self.assertEqual(t["rig_dark"][0], S0)
        self.assertGreaterEqual(t["rig_back"][0], max(t["env_out"][1], t["blink_window"][1]))
        self.assertEqual(t["rig_dark"][1], t["rig_back"][0])
        self.assertTrue(S0 < t["strike_window"][1] < t["crossfade"][1] < t["cut"])
        self.assertEqual(t["slot"][1] - t["slot"][0], 5641 - 376)                     # slot keeps her length
        self.assertTrue(t["slot"][1] < t["blink_window"][0] < t["glide_out"][0] < t["glide_out"][1] == t["exit_cut"][0])
        self.assertEqual(t["planned_end"], t["exit_cut"][1])
        bad = R.plan_timeline(400, 376, 5641, FPS, 8, ARGS, 25)                        # control: land after cut
        self.assertTrue(bad["refusals"])

    def test_cut_moves_for_strikes(self):
        t = R.plan_timeline(104, 376, 5641, FPS, 14, ARGS, 25, glide_in_s=6.0)
        self.assertGreater(t["slot_shift"], 0)
        self.assertGreaterEqual(t["strike_window"][1] - t["strike_window"][0], int(0.9 * 13 * FPS) - 2)
        t2 = R.plan_timeline(104, 2000, 7265, FPS, 2, ARGS, 25, glide_in_s=6.0)       # control: room enough
        self.assertEqual(t2["slot_shift"], 0)

    def test_no_rig_back(self):
        a2 = copy.deepcopy(ARGS)
        a2["outro"]["rig_glow_back"] = False
        t = R.plan_timeline(104, 376, 5641, FPS, 4, a2, 25)
        self.assertIsNone(t["rig_back"])
        self.assertEqual(t["rig_dark"][1], t["planned_end"])


class Lattice(unittest.TestCase):
    def test_cancel_is_exact(self):
        c = R.cancel_keys(RISE_KEYS, 0)
        self.assertEqual(c["hold"], 2800.0)
        self.assertEqual(c["lowers_cm"], 1600.0)
        for tick in range(0, int(18 * 24000), 997):
            self.assertAlmostEqual(R.curve_eval(RISE_KEYS, tick) + R.curve_eval(c["keys"], tick), 2800.0, places=6)
        bad = [dict(k, arrive=-k["arrive"], leave=-k["leave"]) for k in c["keys"]]    # control: tangents not negated
        worst = max(abs(R.curve_eval(RISE_KEYS, t) + R.curve_eval(bad, t) - 2800.0) for t in range(0, 420000, 997))
        self.assertGreater(worst, 1.0)
        moved = R.cancel_keys(RISE_KEYS, 960)                                          # control: wrong offset
        worst = max(abs(R.curve_eval(RISE_KEYS, t) + R.curve_eval(moved["keys"], t) - 2800.0)
                    for t in range(0, 420000, 997))
        self.assertGreater(worst, 1.0)

    def test_offset(self):
        self.assertEqual(R.rise_offset_ticks(0, 25.0, 24000.0, 0, 0, 24000.0), 0)
        self.assertEqual(R.rise_offset_ticks(10, 25.0, 24000.0, -4800, 960, 24000.0), 9600 + 4800 - 960)
        with self.assertRaises(R.PlanError):
            R.rise_offset_ticks(0, 25.0, 24000.0, 0, 0, 30000.0)
        with self.assertRaises(R.PlanError):
            R.rise_offset_ticks(0, 25.0, 24000.0, 0, 0, 24000.0, play_rate=1.5)
        with self.assertRaises(R.PlanError):
            R.cancel_keys([dict(RISE_KEYS[0], interp="smart")], 0)


class Plan(unittest.TestCase):
    def test_full_plan(self):
        p = R.build_plan(v3facts(), ARGS)
        self.assertEqual(p["refusals"], [], p["refusals"])
        tl = p["timeline"]
        keys = {k[0]: k for k in p["glide"]["keys"]}
        first, last = p["poses"]["her_lit"], p["poses"]["her_last"]           # v3: the intro ends on her LIT pose
        self.assertNotEqual(first["loc"], p["poses"]["her_first"]["loc"])
        self.assertEqual(keys[tl["cut"]][1:7], first["loc"] + first["rot"])          # intro ends ON her first frame
        held = [k for f, k in sorted(keys.items()) if tl["glide_in"][1] <= f <= tl["cut"]]   # LINEAR keys: equal
        self.assertGreaterEqual(len(held), 2)                                          # ends => at rest between
        for k in held:
            self.assertEqual(k[1:8], first["loc"] + first["rot"] + [first["focal"]])
        self.assertEqual(keys[tl["glide_in"][1]][1:7], first["loc"] + first["rot"])   # there BEFORE the first strike
        self.assertLess(tl["glide_in"][1], min(r["strike_frame"] for r in p["her_lights"] if r["strikes"]))
        self.assertEqual(keys[tl["slot"][1]][1:7], last["loc"] + last["rot"])        # outro starts ON her last frame
        self.assertEqual(keys[tl["cut"]][7], 40.0)                                    # her lens AT Lh, exact
        self.assertEqual(keys[tl["glide_in"][0]][1:4], [28784.0135, 0.0, 150.0])      # from the Entry pose
        self.assertEqual(keys[0][1:4], [28784.0135, 0.0, 150.0]) if 0 in keys else None
        cuts = p["cuts_after"]
        self.assertEqual(cuts[0][1][0], 0)
        self.assertTrue(all(cuts[i][1][1] == cuts[i + 1][1][0] for i in range(len(cuts) - 1)))
        self.assertEqual(cuts[-1][1][1], tl["planned_end"])
        for r in p["her_lights"]:
            self.assertEqual(r["intro_keys"][-1][1], r["target_lit"])
            self.assertLess(r["intro_keys"][-1][0], tl["cut"])
            self.assertEqual(r["outro_keys"][0], [tl["slot"][1], r["target_last"]])
            self.assertEqual(r["outro_keys"][-1][1], 0.0)
            self.assertLess(r["outro_keys"][-1][0], tl["glide_out"][0])
        acts = {h["label"]: h["action"] for h in p["hangar_lights"]}
        self.assertEqual(acts, {"S1 Practical L1": "black_color", "S1 Lattice Glow 1-1": "fade_color"})
        glow = [h for h in p["hangar_lights"] if h["action"] == "fade_color"][0]
        ck = {k[0]: k[1] for k in glow["color_keys"]}
        S0 = min(r["strike_frame"] for r in p["her_lights"] if r["strikes"])
        self.assertEqual(ck[tl["glow_fade"][1]][:3], [0.0, 0.0, 0.0])                 # black by the first strike
        self.assertLessEqual(tl["glow_fade"][1], S0)
        self.assertEqual(ck[tl["rig_back"][0]][:3], [0.0, 0.0, 0.0])                 # still black until rig back
        self.assertGreater(tl["rig_back"][0], max(r["outro_keys"][-1][0] for r in p["her_lights"]))
        self.assertEqual(p["rig_bulbs_hidden"], {"labels": ["S1 Lattice Bulb 1-1"], "range": tl["rig_dark"]})
        self.assertEqual(p["lattice"]["mode"], "cancel")
        self.assertEqual(p["lattice"]["cancel"]["lowers_cm"], 1600.0)
        self.assertEqual(p["hide"]["labels"], ["S1 Hangar Roof"])
        self.assertTrue(p["relength_first"])
        self.assertLessEqual(p["glide"]["in"]["peak_speed_cm_s"], 300.0)
        self.assertLessEqual(p["glide"]["out"]["peak_speed_cm_s"], 300.0)
        self.assertTrue(400.0 - 1e-6 <= p["placement"]["lead_cm"] <= 800.0)
        self.assertTrue(any("HER_PPV_NO_EXPOSURE_OVERRIDE" in w for w in p["warnings"]))
        self.assertTrue(any("PPV_PRIORITY" in w for w in p["warnings"]))

    def test_plan_refuses_when_set_too_wide(self):
        f = v3facts(her_set=[30000.0, 31000.0, -1500.0, 1500.0, 0.0, 300.0])           # control: 30 m wide
        p = R.build_plan(f, ARGS)
        self.assertTrue(any("SET_DOES_NOT_FIT_LIVE_BOX" in r for r in p["refusals"]))
        self.assertFalse(p["apply_ready"])

    def test_lattice_flag(self):
        f = v3facts(her_set=[28784.0135 + 900, 28784.0135 + 2500, -400.0, 400.0, 0.0, 1300.0],
                    first_loc=[28784.0135 + 800, 0.0, 140.0])
        p = R.build_plan(f, ARGS)
        self.assertTrue(any("SET_REACHES_LATTICE" in r for r in p["refusals"]))
        self.assertIn("params", json.dumps(p["refusals"]))
        a2 = copy.deepcopy(ARGS)
        a2["allow_lattice_overlap"] = True
        p2 = R.build_plan(f, a2)
        self.assertFalse(any("SET_REACHES_LATTICE" in r for r in p2["refusals"]))
        self.assertTrue(any("allow_lattice_overlap" in w for w in p2["warnings"]))

    def test_lead_in_range(self):
        p = R.build_plan(v3facts(), ARGS)
        cam = p["poses"]["her_lit"]["loc"]
        self.assertAlmostEqual(cam[0] - 28784.0135, p["placement"]["lead_cm"], places=6)
        self.assertFalse(any("LEAD_ABOVE_RANGE" in w for w in p["warnings"]))
        f = v3facts(first_loc=[28784.0135 + 3772 + 900, 0.0, 140.0])                 # control: camera far past her set
        p2 = R.build_plan(f, ARGS)
        self.assertTrue(any("LEAD_ABOVE_RANGE" in w for w in p2["warnings"]))

    def test_long_glide_speed_bounded(self):
        f = v3facts(first_loc=[28784.0135 + 3772 + 900, 0.0, 140.0])                 # set far down the box
        p = R.build_plan(f, ARGS)
        self.assertGreater(p["glide"]["in"]["distance_cm"], 2000.0)
        self.assertLessEqual(p["glide"]["in"]["peak_speed_cm_s"], 300.0)
        self.assertGreater(p["timeline"]["glide_in_s"], 6.0)

    def test_lattice_modes(self):
        f = v3facts()
        f["lattice"] = {"error": "AttributeError: no get_arrive_tangent"}
        p = R.build_plan(f, ARGS)
        self.assertTrue(any("LATTICE_CANCEL_UNAVAILABLE" in r for r in p["refusals"]))
        a2 = copy.deepcopy(ARGS)
        a2["lattice"] = "hide"
        p2 = R.build_plan(f, a2)                                                      # control: hide needs no keys
        self.assertFalse(any("LATTICE" in r for r in p2["refusals"]), p2["refusals"])
        self.assertIn("S1 Hangar Lattice Beam 01", p2["lattice"]["hide"]["labels"])
        a3 = copy.deepcopy(ARGS)
        a3["lattice"] = "maybe"
        self.assertTrue(any("LATTICE_MODE" in e for e in R.validate_args(a3)))

    def test_plan_refuses_on_order(self):
        f = v3facts()
        f["L"] = 500
        self.assertTrue(R.build_plan(f, ARGS)["refusals"])


class LitFrame(unittest.TestCase):
    """v3: her lit frame. Synthetic curves (RAMPS): 7 of 8 lights lit by her frame 227, one at 900."""

    def curves(self, n=8):
        return {r["label"]: r["curves"]["Intensity"] for r in facts(n_lights=n)["her_lights"]}

    def test_votes_frame(self):
        lit = R.find_lit_frame(self.curves(), HER_LO, HER_HI, HER_FPS, R.lit_cfg(ARGS))
        self.assertEqual(lit["refusals"], [])
        self.assertEqual(lit["n_ever_lit"], 8)
        self.assertEqual(lit["n_needed"], 7)                                          # ceil(0.8 x 8)
        # value_fraction 0.9 of a linear ramp (t0 -> t1) is reached at t0 + 0.9 (t1 - t0); the 7th is light 6 (180->227)
        self.assertEqual(lit["frame_raw"], 180 + int(math.ceil(0.9 * 47)))
        self.assertEqual(lit["per_light"]["SpotLight7"]["lit_at"], 850 + 45)            # the late one, reported
        lo = R.find_lit_frame(self.curves(), HER_LO, HER_HI, HER_FPS, R.lit_cfg(dict(ARGS, lit={"light_fraction": 0.5})))
        self.assertLess(lo["frame_raw"], lit["frame_raw"])                             # control: fraction matters
        allx = R.find_lit_frame(self.curves(), HER_LO, HER_HI, HER_FPS, R.lit_cfg(dict(ARGS, lit={"light_fraction": 1.0})))
        self.assertEqual(allx["frame_raw"], 895)                                       # control: 100% waits for the late one

    def test_flash_is_not_lit(self):
        c = self.curves()
        flash = [{"tick": (HER_LO + 5) * HER_TPF, "value": 0.0, "interp": "constant", "arrive": 0.0, "leave": 0.0},
                 {"tick": (HER_LO + 6) * HER_TPF, "value": 5000.0, "interp": "constant", "arrive": 0.0, "leave": 0.0},
                 {"tick": (HER_LO + 7) * HER_TPF, "value": 0.0, "interp": "linear", "arrive": 0.0, "leave": 0.0}]
        for k in list(c)[:7]:
            i = int(k[len("SpotLight"):])
            c[k] = ramp_curve(RAMPS[i][0], RAMPS[i][1], 1000.0, extra=flash)
        held = R.find_lit_frame(c, HER_LO, HER_HI, HER_FPS, R.lit_cfg(ARGS))
        self.assertGreater(held["frame_raw"], 200)                                     # a 1-frame flash does not count
        raw = R.find_lit_frame(c, HER_LO, HER_HI, HER_FPS, R.lit_cfg(dict(ARGS, lit={"hold_s": 0.0})))
        self.assertLess(raw["frame_raw"], HER_LO + 10)                                 # control: no hold -> fooled

    def test_snap_onto_scene_grid(self):
        self.assertEqual(R.snap_her_frame(227, HER_LO, 30.0, 25.0), (230, 6))           # 537 -> 540 = 90 x 6
        self.assertEqual(R.snap_her_frame(230, HER_LO, 30.0, 25.0), (230, 6))           # control: on grid stays
        self.assertEqual(R.snap_her_frame(5, 0, 25.0, 25.0), (5, 1))
        with self.assertRaises(R.PlanError):
            R.snap_her_frame(5, 0, 29.97, 25.0)

    def test_none_and_override(self):
        dark = {"a": ramp_curve(100, 200, 0.0)}
        lit = R.find_lit_frame(dark, HER_LO, HER_HI, HER_FPS, R.lit_cfg(ARGS))
        self.assertTrue(any("LIT_NONE" in r for r in lit["refusals"]))
        over = R.find_lit_frame(dark, HER_LO, HER_HI, HER_FPS, R.lit_cfg(dict(ARGS, lit={"frame": 400})))
        self.assertEqual((over["frame_raw"], over["refusals"]), (400, []))             # control: explicit frame
        late = R.find_lit_frame({"a": ramp_curve(3000, 3100, 5.0)}, HER_LO, HER_HI, HER_FPS, R.lit_cfg(ARGS))
        self.assertTrue(late["refusals"])                                              # past the 60 s search window

    def test_sum_crosscheck_warns(self):
        c = self.curves(8)
        ok = R.find_lit_frame(c, HER_LO, HER_HI, HER_FPS, R.lit_cfg(ARGS))
        self.assertFalse(any("DISAGREE" in w for w in ok["warnings"]), ok.get("sum_frame"))
        c2 = dict(c)
        for i in range(8, 14):                                                        # control: many late lights
            c2["Late%d" % i] = ramp_curve(1400, 1450, 100.0)
        bad = R.find_lit_frame(c2, HER_LO, HER_HI, HER_FPS, R.lit_cfg(dict(ARGS, lit={"light_fraction": 0.5})))
        self.assertTrue(any("DISAGREE" in w for w in bad["warnings"]))

    def test_curve_at_interpolates(self):
        c = ramp_curve(0, 100, 10.0)
        self.assertAlmostEqual(R.curve_at(c, 50), 5.0, places=9)
        self.assertEqual(R.curve_at(c, 100), 10.0)
        self.assertEqual(R.curve_at(c, 5000), 10.0)                                     # constant after the last key
        self.assertIsNone(R.eval_keys([[0, 0.0], [100, 10.0]], None, 50))               # control: v2 reader could not


class StrikeTargets(unittest.TestCase):
    def test_strikes_go_to_value_at_lit_frame(self):
        f = v3facts()
        Lh = f["lit"]["frame"]
        self.assertEqual((f["lit"]["frame_raw"], Lh), (223, 224))                    # 223 snapped up onto the 6-grid
        p = R.build_plan(f, ARGS)
        self.assertEqual(p["refusals"], [], p["refusals"])
        by = {r["label"]: r for r in p["her_lights"]}
        for r in f["her_lights"]:
            want = R.curve_at(r["curves"]["Intensity"], Lh)
            row = by[r["label"]]
            if want > 1e-3:
                self.assertTrue(row["strikes"])
                self.assertEqual(row["intro_keys"][-1][1], want)                       # settles at her value AT Lh
                self.assertNotEqual(row["intro_keys"][-1][1], r["target_first"])       # control: not her first frame (0)
            else:
                self.assertFalse(row["strikes"])                                       # dark at Lh: held at 0, no strike
                self.assertEqual(row["intro_keys"], [[p["timeline"]["land"], 0.0]])
        self.assertEqual(sum(1 for r in p["her_lights"] if r["strikes"]), 7)           # SpotLight7 is the late one

    def test_v2_mode_control(self):
        a2 = copy.deepcopy(ARGS)
        a2["lit"] = {"enabled": False}
        f = v3facts(args=a2)
        p = R.build_plan(f, a2)
        self.assertEqual(p["slot"]["skip_frames"], 0)
        self.assertEqual(p["poses"]["her_lit"]["loc"][0] - p["poses"]["her_first"]["loc"][0], 0.0)
        self.assertTrue(all(r["intro_keys"][-1][1] == 0.0 for r in p["her_lights"]))  # v2 would strike to 0

    def test_env_and_colour_at_lit(self):
        f = facts()
        f["her_env"][0].update(her_keyed=True, curve=ramp_curve(0, 300, 6.0))
        f["her_lights"][0]["curves"]["LightColor"] = [ramp_curve(0, 300, 1.0), ramp_curve(0, 300, 0.5),
                                                      ramp_curve(0, 300, 0.25), {"tpf": 800.0, "keys": [], "default": 1.0}]
        f["lit"] = R.detect_lit(f, ARGS, FPS)
        f["her_lit"] = her_lit_pose(f, f["lit"]["frame"])
        R.apply_lit_values(f, f["lit"]["frame"])
        p = R.build_plan(f, ARGS)
        env = {e["label"]: e for e in p["her_env"]}
        Lh = f["lit"]["frame"]
        self.assertAlmostEqual(env["DirectionalLight"]["target_intro"], 6.0 * Lh / 300.0, places=9)
        self.assertEqual(env["DirectionalLight"]["intro"][-1][1], env["DirectionalLight"]["target_intro"])
        self.assertEqual(env["PostProcessVolume"]["target_intro"], 1.0)               # control: unkeyed = level value
        col = [r for r in p["her_lights"] if r["label"] == "SpotLight0"][0]["intro_color"]
        self.assertAlmostEqual(col["rgba"][1], 0.5 * Lh / 300.0, places=9)
        self.assertEqual(col["rgba"][3], 1.0)
        self.assertEqual(col["range"], [p["timeline"]["land"], p["timeline"]["cut"]])


class SlotOffset(unittest.TestCase):
    def test_skip_maths(self):
        sk = R.slot_skip(HER_LO, HER_HI, 230, 30.0, 25.0, 800, 5265)
        self.assertEqual(sk["refusals"], [])
        self.assertEqual((sk["skip_frames"], sk["remaining_frames"]), (450, 4815))     # 540 x 25/30, 5778 x 25/30
        self.assertEqual(sk["offset_ticks"], 540 * 800)
        self.assertAlmostEqual(sk["skip_s"], 18.0, places=9)
        self.assertEqual(R.scene_frame_of_her(230, 594, 230, 30.0, 25.0), 594)         # the cut plays her Lh
        self.assertEqual(R.scene_frame_of_her(HER_HI, 594, 230, 30.0, 25.0), 594 + 4815)
        self.assertEqual(R.scene_frame_of_her(HER_HI, 594, HER_LO, 30.0, 25.0), 594 + 5265)   # control: no skip
        self.assertTrue(any("OFF_GRID" in r for r in R.slot_skip(HER_LO, HER_HI, 231, 30.0, 25.0, 800, 5265)["refusals"]))
        self.assertTrue(any("LENGTH_MISMATCH" in r for r in R.slot_skip(HER_LO, HER_HI, 230, 30.0, 25.0, 800, 5264)["refusals"]))
        self.assertTrue(R.slot_skip(HER_LO, HER_HI, HER_HI, 30.0, 25.0, 800, 5265)["refusals"])

    def test_plan_slot(self):
        f = v3facts()
        p = R.build_plan(f, ARGS)
        sl, Lh = p["slot"], f["lit"]["frame"]
        self.assertEqual(sl["her_frame_at_cut"], Lh)
        self.assertEqual(sl["start_offset_ticks"], (Lh - HER_LO) * 800)
        self.assertEqual(sl["skip_frames"], (Lh - HER_LO) * 25 // 30)
        self.assertEqual(sl["range"][1] - sl["range"][0], 5265 - sl["skip_frames"])
        self.assertEqual(R.scene_frame_of_her(Lh, sl["range"][0], Lh, 30.0, 25.0), sl["range"][0])
        self.assertEqual(sl["range_before"], [376, 5641])

    def test_audio_report(self):
        her = [{"sound": "CLICK", "start_frame": -311, "end_frame": 4165}, {"sound": "early", "start_frame": -300,
                                                                            "end_frame": 100},
               {"sound": "late", "start_frame": 2000, "end_frame": 2100}]
        a = R.audio_report(her, [{"track": "Narr", "range": [5216, 6091]}], [{"label": "m", "frame": 6000}], 230, 30.0,
                           594, 25.0, 5816)
        rows = {r["sound"]: r for r in a["her_audio"]}
        self.assertIn("first 18.03 s are skipped", rows["CLICK"]["after_skip"])
        self.assertIn("never plays", rows["early"]["after_skip"])
        self.assertAlmostEqual(rows["late"]["scene_start_frame"], 594 + (2000 - 230) * 25 / 30.0, places=9)
        self.assertEqual(len(a["scene_audio_past_end"]), 1)
        self.assertEqual(len(a["scene_markers_past_end"]), 1)
        b = R.audio_report(her, [{"track": "Narr", "range": [5216, 6091]}], [], 230, 30.0, 594, 25.0, 6266)
        self.assertEqual(b["scene_audio_past_end"], [])                               # control: v2 end keeps it


class SceneLength(unittest.TestCase):
    def test_skip_shortens_scene(self):
        t0 = R.plan_timeline(104, 376, 5641, FPS, 14, ARGS, 25, glide_in_s=6.0, glide_out_s=6.0)
        t1 = R.plan_timeline(104, 376, 5641, FPS, 14, ARGS, 25, glide_in_s=6.0, glide_out_s=6.0, skip=450)
        self.assertEqual(t0["planned_end"], 6266)                                      # v2 live end [meas dry/record]
        self.assertEqual(t1["cut"], t0["cut"])                                         # the intro is unchanged
        self.assertEqual(t1["planned_end"], t0["planned_end"] - 450)
        self.assertEqual(t1["slot"][1] - t1["slot"][0], 5265 - 450)
        self.assertEqual(t1["outro_s"], t0["outro_s"])                                 # outro unchanged
        self.assertTrue(R.plan_timeline(104, 376, 5641, FPS, 14, ARGS, 25, skip=5265)["refusals"])   # control
        t2 = R.plan_timeline(104, 376, 5641, FPS, 7, ARGS, 25, glide_in_s=6.0, glide_out_s=6.0, skip=450)
        self.assertLess(t2["cut"], t1["cut"])                                          # fewer strikes, earlier cut

    def test_plan_extend_mode(self):
        p = R.build_plan(v3facts(), ARGS)
        self.assertEqual(p["extend_mode"]["new_end_s"], round(p["timeline"]["planned_end"] / FPS, 6))
        self.assertTrue(p["relength_first"])


class Revert(unittest.TestCase):
    P = R.PREFIX
    HOOK = "Klara Hookin - Hers Dark: DirectionalLight"
    BEFORE = {HOOK, "Klara Hookin - Hers Dark: SkyAtmosphere", "Klara Levels (hookin)"}

    def rows(self, with_hookin_track=True):
        vis = [{"name": "Visibility", "cls": "MovieSceneVisibilityTrack"}] if with_hookin_track else []
        return [{"guid": "A", "name": self.P + "DirectionalLight", "parent": None, "tracks": vis},
                {"guid": "B", "name": self.P + "DirectionalLight/Component", "parent": "A",
                 "tracks": [{"name": self.P + "Intensity", "cls": "MovieSceneFloatTrack"}]},
                {"guid": "C", "name": self.P + "Hide: S1 Hangar Roof", "parent": None,
                 "tracks": [{"name": "Visibility", "cls": "MovieSceneVisibilityTrack"}]},
                {"guid": "D", "name": "Klara Hookin - Hers Dark: SkyAtmosphere", "parent": None,
                 "tracks": [{"name": "Visibility", "cls": "MovieSceneVisibilityTrack"}]},
                {"guid": "E", "name": "Scene 1 Entry", "parent": None, "tracks": []}]

    def test_legacy_v2_renamed_hookin_binding_is_restored(self):
        a = R.revert_actions(self.rows(), self.BEFORE, [])
        self.assertEqual(a["rename"], [["A", self.HOOK]])
        self.assertEqual(a["strip"], ["A"])
        self.assertEqual(a["remove"], ["B", "C"])                                      # child first; D, E untouched
        self.assertEqual(a["unrecoverable"], [])
        b = R.revert_actions(self.rows(with_hookin_track=False), self.BEFORE, [])     # control: no hookin track left
        self.assertIn("A", b["remove"])
        self.assertEqual(b["unrecoverable"], [self.HOOK])

    def test_v3_shared_binding_is_stripped_not_removed(self):
        rows = self.rows()
        rows[0]["name"] = self.HOOK                                                   # v3 never renames
        rows[0]["tracks"].append({"name": self.P + "BlendWeight", "cls": "MovieSceneFloatTrack"})
        a = R.revert_actions(rows, self.BEFORE, ["A"])
        self.assertEqual((a["rename"], a["strip"], a["remove"], a["unrecoverable"]), ([], ["A"], ["B", "C"], []))

    def test_measured_records_show_the_rename(self):
        """[meas] the v1 and v2 live records: the hookin names that vanished between 'before' and 'hookin_after' are
        exactly the env actors the reveal ramps (and so re-possessed). v4 note: the v3 APPLY (KLARAREVEAL-20261007-
        011535) replaced klara_reveal_record_S1.json, and the v2 record now lives at .reverted-...-011426; the v3 record
        is the CONTROL - its _possess never renames, so nothing vanished."""
        for name in ("klara_reveal_record_S1.json.reverted-KLARAREVEAL-20261007-011426",
                     "klara_reveal_record_S1.json.restored-from-backup"):
            path = os.path.join(HERE, name)
            if not os.path.exists(path):
                self.skipTest("record absent: " + name)
            rec = R.load_json(path)
            gone = {r["name"] for r in rec["before"]["hookin_bindings"]} - {r["name"] for r in rec["hookin_after"]}
            ramped = {"Klara Hookin - Hers Dark: " + e["label"] for e in rec["plan"]["her_env"] if e.get("action") == "ramp"}
            self.assertEqual(gone, ramped)
            self.assertEqual(len(gone), 4)
        v3 = os.path.join(HERE, "klara_reveal_record_S1.json")
        if os.path.exists(v3):
            rec = R.load_json(v3)
            if rec.get("version") == 3 and rec.get("applied"):
                gone = {r["name"] for r in rec["before"]["hookin_bindings"]} - {r["name"] for r in rec["hookin_after"]}
                self.assertEqual(gone, set())                                          # control: v3 renamed nothing


# =====================================================================================================================
# v4 (S4, 7 Oct): her ORIGINAL LS_Children, our copy, L_KK_children and L_Animals, re-read from BYTES (UE5 1018 reader
# from test_klara_void_s6_offline.py [prec], extended with the soft-object-path table and UniversalObjectLocator
# fragments). Every S4 number below is [meas] from these bytes unless marked.
# =====================================================================================================================

PROJECT = os.path.abspath(os.environ.get("PUSS_ASSET_PROJECT",
                                        os.path.join(HERE, "..", "..", "..")))
LS_CHILDREN = os.path.join(PROJECT, "Content", "LS_Children.uasset")
LS_CHILDREN_COPY = os.path.join(PROJECT, "Content", "InfinityStage", "KlaraHookin", "LS_Children_S4Hangar.uasset")
L_CHILDREN = os.path.join(PROJECT, "Content", "L_KK_children.umap")
L_ANIMALS = os.path.join(PROJECT, "Content", "KK_S1_Animals", "L_Animals.umap")
LS_ANIMALS_COPY = os.path.join(PROJECT, "Content", "InfinityStage", "KlaraHookin", "LS_Animals_1_S1Hangar.uasset")
S4_LT_HOOKIN = [13639.9695, 240008.5, 0.0] # [meas klara_hookin_stream_record.json placements L_KK_children]
S4_LT = None                               # set below from BYTES: the LT the copy is shifted by NOW (v5 session fix:
                                           # a live reveal moves the level, so the hookin LT went stale - 4 reds)
S4_ENTRY = [10668.4695, 240000.0, 180.0]   # [meas Saved/CodexStructure/scene_docks.json "Scene 4" entry camera]
S4_LCE = (104, 376, 4476)                  # [meas klara_hookin_seq_record.json scenes.4.plan.timeline]
_BYTES = {}


def _reader():
    import test_klara_void_s6_offline as V                  # noqa: E402 - sibling harness, its minimal reader
    return V


def _tag(p, r):
    nm = p.fname(r)
    if nm == "None":
        return None
    t = p.typename(r)
    size = r.i32()
    fl = r.raw(1)[0]
    if fl & 1:
        r.i32()
    if fl & 2:
        r.raw(16)
    if fl & 4:
        ext = r.raw(1)[0]
        if ext & 2:
            r.raw(2)
    return nm, t, r.raw(size)


def _struct_array(p, data):
    V = _reader()
    n = struct.unpack_from("<i", data, 0)[0]
    r = V.R(data, 4)
    rows = []
    for _ in range(n):
        row = {}
        while True:
            tg = _tag(p, r)
            if tg is None:
                break
            row[tg[0]] = tg
        rows.append(row)
    return rows


def _tags(p, data):
    V = _reader()
    r, out = V.R(data), {}
    while r.o < len(data):
        tg = _tag(p, r)
        if tg is None:
            break
        out[tg[0]] = tg
    return out


def _soft_paths(p):
    """FPackageFileSummary: after NameCount/NameOffset come SoftObjectPathsCount/Offset (UE5 >= 1008); each entry is
    package FName, asset FName, sub-path as a length-prefixed UTF-8 string WITHOUT a terminator [meas]."""
    V = _reader()
    r = V.R(p.b)
    r.u32(), r.i32(), r.i32(), r.i32(), r.i32(), r.i32()
    r.raw(20)
    r.i32()
    n = r.i32()
    r.raw(20 * n)
    r.fstr()
    r.u32(), r.i32(), r.i32()
    sc, so = r.i32(), r.i32()
    rr, out = V.R(p.b, so), []
    for _ in range(sc):
        pk, an = p.fname(rr), p.fname(rr)
        ln = rr.i32()
        sub = rr.raw(ln).decode("utf-8") if ln >= 0 else rr.raw(-2 * ln).decode("utf-16le")
        out.append("%s.%s%s" % (pk, an, (":" + sub) if sub else ""))
    return out


def _locator(p, v, soft):
    """UniversalObjectLocator: Fragments[] of (fragment type FName, tagged payload) [meas]."""
    V = _reader()
    data = _tag(p, V.R(v))[2]
    n = struct.unpack_from("<i", data, 0)[0]
    r, frags = V.R(data, 4), []
    for _ in range(n):
        ft = p.fname(r)
        pay = {}
        while True:
            tg = _tag(p, r)
            if tg is None:
                break
            nm, t, val = tg
            pay[nm] = soft[struct.unpack("<i", val[:4])[0]] if "SoftObjectPath" in t else (
                V.R(val).fstr() if t == "StrProperty" else val.hex())
        frags.append([ft, pay])
    return frags


def _key_curve(v, double):
    """Channel -> a klara_reveal curve {"tpf", "keys": [{"tick","value","interp","arrive","leave"}], "default"}.
    Key layout [meas]: value (float 4 / double 8), tangent data (arrive, leave, arrive w, leave w: 4 floats, weight
    mode u8, padded to 20), interp u8, tangent mode u8. NOTE the S6 reader's dchan reads interp at +24, which is the
    weight-mode byte for doubles (it labels every key LINEAR); S4's keys are all CUBIC/AUTO with stored tangents."""
    V = _reader()
    r = V.R(v, 2)
    r.i32()
    nt = r.i32()
    times = [r.i32() for _ in range(nt)]
    es, nv = r.i32(), r.i32()
    vs = 8 if double else 4
    keys = []
    for t in times[:nv]:
        st = r.o
        val = struct.unpack_from("<d" if double else "<f", v, st)[0]
        at, lt = struct.unpack_from("<ff", v, st + vs)
        keys.append({"tick": t, "value": float(val), "arrive": float(at), "leave": float(lt),
                     "interp": {0: "linear", 1: "constant", 2: "cubic"}.get(v[st + vs + 20], "?%d" % v[st + vs + 20])})
        r.o = st + es
    d = struct.unpack_from("<d" if double else "<f", v, r.o)[0]
    has = struct.unpack_from("<i", v, r.o + vs)[0]
    return {"tpf": 800.0, "keys": keys, "default": float(d) if has else None}


def derive_ls(path):
    """Bindings (possessables + reference locators), tracks, cuts, light Intensity curves, camera transforms."""
    if path in _BYTES:
        return _BYTES[path]
    V = _reader()
    p = V.Package(path)
    soft = _soft_paths(p)
    n = len(p.exports)
    ls = [i for i in range(1, n + 1) if p.cls(i) == "LevelSequence"][0]
    ms = [i for i in range(1, n + 1) if p.cls(i) == "MovieScene"][0]
    lsp = {t["name"]: t for t in p.props(ls)}
    msp = {t["name"]: t for t in p.props(ms)}
    refs = {}
    for row in _struct_array(p, _tags(p, lsp["BindingReferences"]["value"])["SortedReferences"][2]):
        refs[row["ID"][2][:16].hex()] = _locator(p, row["Locator"][2], soft)
    poss = {}
    for row in _struct_array(p, msp["Possessables"]["value"]):
        g = row["Guid"][2].hex()
        par = row["ParentGuid"][2].hex() if "ParentGuid" in row else None
        poss[g] = {"guid": g, "name": V.R(row["Name"][2]).fstr(), "parent": None if par in (None, "00" * 16) else par,
                   "class": soft[struct.unpack("<i", row["PossessedObjectClass"][2])[0]]
                   if "PossessedObjectClass" in row else None}
    tracks = {}
    for row in _struct_array(p, msp["ObjectBindings"]["value"]):
        v = row["Tracks"][2]
        tracks[row["ObjectGuid"][2].hex()] = [struct.unpack_from("<i", v, 4 + 4 * k)[0]
                                              for k in range(struct.unpack_from("<i", v, 0)[0])]
    cuts, audio = [], []
    fades = 0
    for i in range(1, n + 1):
        c = p.cls(i)
        if c == "MovieSceneCameraCutSection":
            pr = {t["name"]: t for t in p.props(i)}
            g = _tags(p, pr["CameraBindingID"]["value"])["Guid"][2].hex()
            cuts.append({"range": [x // 800 for x in V.frange(pr["SectionRange"]["value"])], "guid": g})
        elif c == "MovieSceneAudioSection":
            pr = {t["name"]: t for t in p.props(i)}
            audio.append({"sound": p.path(struct.unpack_from("<i", pr["Sound"]["value"], 0)[0]).split(".")[0],
                          "range_tick": V.frange(pr["SectionRange"]["value"])})
        elif c in ("MovieSceneFadeTrack", "MovieSceneFadeSection"):
            fades += 1
    cuts.sort(key=lambda c: c["range"][0])
    curves, cams = {}, {}
    for g, trk in tracks.items():
        b = poss.get(g)
        for ti in trk:
            secs = [j for j in range(1, n + 1) if p.exports[j - 1]["outer"] == ti and p.cls(j).endswith("Section")]
            tp = {t["name"]: t for t in p.props(ti)}
            prop = None
            if "PropertyBinding" in tp:
                prop = p.fname(V.R(_tags(p, tp["PropertyBinding"]["value"])["PropertyName"][2]))
            if p.cls(ti) == "MovieSceneFloatTrack" and prop == "Intensity" and b and b["parent"]:
                ch = [t for t in p.props(secs[0]) if "FloatChannel" in t["type"]][0]
                curves[b["parent"]] = _key_curve(ch["value"], False)
            elif p.cls(ti) == "MovieScene3DTransformTrack" and b and "CineCamera" in (b["class"] or ""):
                ch = {"%s[%d]" % (t["name"], t["index"]): _key_curve(t["value"], True)
                      for t in p.props(secs[0]) if "DoubleChannel" in t["type"]}
                cams[g] = ch
    pr = V.frange(msp["PlaybackRange"]["value"])
    out = {"refs": refs, "poss": poss, "tracks": tracks, "cuts": cuts, "audio": audio, "fades": fades,
           "intensity_by_parent_guid": curves, "camera_channels": cams, "playback": [pr[0] // 800, pr[1] // 800]}
    _BYTES[path] = out
    return out


def s4_lt_now():
    """[meas] the translation the COPY's camera keys carry over her original's = her level transform the copy was
    re-keyed for (the hookin's LT, or a live reveal's level_transform_after)."""
    o, c = derive_ls(LS_CHILDREN), derive_ls(LS_CHILDREN_COPY)
    g = "b28a821d72b7a24ea738eb622365a09c"                                             # CineCameraActor (_0)
    return [c["camera_channels"][g]["Translation[%d]" % i]["keys"][0]["value"] -
            o["camera_channels"][g]["Translation[%d]" % i]["keys"][0]["value"] for i in range(3)]


def s4_lt_allowed():
    """The LTs the copy may legitimately carry: the hookin's, or an APPLIED S4 reveal record's level_transform_after."""
    out = [list(S4_LT_HOOKIN)]
    rp = os.path.join(HERE, "klara_reveal_record_S4.json")
    if os.path.exists(rp):
        rec = R.load_json(rp)
        if rec.get("applied"):
            out.append(list(rec["plan"]["level_transform_after"]["loc"]))
    return out


def derive_level_rows(path):
    if path in _BYTES:
        return _BYTES[path]
    V = _reader()
    p = V.Package(path)
    rows = {}
    for i in range(1, len(p.exports) + 1):
        parts = p.path(i).split(".")
        if len(parts) < 3 or parts[1] != "PersistentLevel":
            continue
        a = rows.setdefault(parts[2], {"name": parts[2], "comps": {}})
        if len(parts) == 3:
            a["class"] = p.cls(i)
            for t in p.props(i):
                if t["name"] == "ActorLabel":
                    a["label"] = V.R(t["value"]).fstr()
        elif len(parts) == 4:
            c = a["comps"].setdefault(parts[3], {"class": p.cls(i)})
            for t in p.props(i):
                v = t["value"]
                if t["name"] == "RelativeLocation":
                    c["loc"] = V.vec3(v)
                elif t["name"] == "RelativeRotation":
                    pit, yaw, rol = V.vec3(v)
                    c["rot"] = [rol, pit, yaw]
                elif t["name"] in ("Intensity", "OuterConeAngle", "AttenuationRadius") and len(v) == 4:
                    c[t["name"]] = struct.unpack("<f", v)[0]
    _BYTES[path] = rows
    return rows


def _cam_pose(chans, frame, lt=(0.0, 0.0, 0.0)):
    ax = lambda nm, f: R.curve_at(chans[nm], f) if chans[nm]["keys"] else chans[nm]["default"]
    loc = [ax("Translation[%d]" % i, frame) + lt[i] for i in range(3)]
    rot = [ax("Rotation[%d]" % i, frame) for i in range(3)]
    nxt = [ax("Translation[%d]" % i, frame + 1) + lt[i] for i in range(3)]
    return {"loc": loc, "rot": rot, "vel_cm_s": [(nxt[i] - loc[i]) * 30.0 for i in range(3)],
            "ang_deg_s": [0.0, 0.0, 0.0]}


def s4_facts(style=None, lit_frame=None):
    """What gather() would assemble for S4, from bytes + records (the box / entry / hangar lights / rise keys are the
    hookin's stale 30 Sep values or SYNTHETIC, so placement numbers are a projection [inf])."""
    her = derive_ls(LS_CHILDREN_COPY)
    lvl = derive_level_rows(L_CHILDREN)
    by_name = {r["name"]: r for r in lvl.values()}
    # her copy's camera bindings resolve to actors by their locator path [meas]
    loc_actor = lambda g: (her["refs"].get(g) or [[None, {}]])[0][1].get("Path", "").split(".")[-1]
    bound = [g for g in her["poss"]]
    fb = R.first_bound_cut(her["cuts"], bound, her["playback"][0])

    def cam_at(frame):
        cut = [c for c in her["cuts"] if c["range"][0] <= frame < c["range"][1]][0]
        g = cut["guid"]
        pose = _cam_pose(her["camera_channels"][g], frame)          # the copy's keys are already shifted [meas]
        pose.update(binding=her["poss"][g]["name"], frame=frame, fps=30.0, cut=cut["range"],
                    lens_tracks={"CurrentFocalLength": 35.0, "ManualFocusDistance": 100000.0, "CurrentAperture": 2.8},
                    actor={"label": her["poss"][g]["name"], "sensor": [23.76, 13.365], "focal": 35.0,
                           "focus": 100000.0, "actor_name": loc_actor(g)})
        return pose

    lights = []
    curves = {her["poss"][g]["name"]: c for g, c in her["intensity_by_parent_guid"].items() if g in her["poss"]}
    for a in lvl.values():
        if a.get("class") != "SpotLight":
            continue
        comp = a["comps"]["LightComponent0"]
        lab = a.get("label", a["name"])
        lights.append({"label": lab, "name": a["name"], "class": "SpotLight",
                       "loc": [comp["loc"][i] + S4_LT[i] for i in range(3)], "rot": comp.get("rot", [0.0, 0.0, 0.0]),
                       "cone_deg": comp.get("OuterConeAngle"), "radius": comp.get("AttenuationRadius"),
                       "intensity": float(comp.get("Intensity", 5000.0)), "color": [1, 1, 1, 1], "visible": True,
                       "hidden_in_game": False, "keyed": {"Intensity": "LightComponent0"} if lab in curves else {},
                       "first": {}, "last": {}, "curves": {"Intensity": curves[lab]} if lab in curves else {}})
    for r in lights:
        c = (r["curves"] or {}).get("Intensity")
        r["target_first"] = R.curve_at(c, 0) if c else r["intensity"]
        r["target_last"] = R.curve_at(c, her["playback"][1] - 1) if c else r["intensity"]
    f = facts()
    f.update(scene="4", L=S4_LCE[0], C=S4_LCE[1], E=S4_LCE[2], label="Scene 4 — External Sound",
             box=dict(BOX, dock={"loc": [S4_ENTRY[0], S4_ENTRY[1], 0.0], "yaw": 0.0}),
             entry_camera=dict(f["entry_camera"], loc=list(S4_ENTRY), sensor=[23.76, 13.365]),
             exit_camera=dict(f["exit_camera"], loc=list(S4_ENTRY), sensor=[23.76, 13.365]),
             her_first=dict(cam_at(fb["frame"]), dangling_cuts=[{"range": c["range"], "guid": c["guid"]}
                                                                for c in fb["dangling"]]),
             her_last=cam_at(her["playback"][1] - 1), her_range=list(her["playback"]), her_fps=30.0, her_tpf=800,
             level_transform={"loc": list(S4_LT), "yaw": 0.0},
             # pivot footprint [meas klara_hookin_args.json scenes.4 footprint_her, z_top 700] + LT
             set_world=[-600 + S4_LT[0], 1657 + S4_LT[0], -674 + S4_LT[1], 657 + S4_LT[1], 0.0, 700.0],
             her_lights=lights,
             her_env=[{"label": "DirectionalLight", "class": "DirectionalLight", "property": "Intensity",
                       "value": float(by_name["DirectionalLight_0"]["comps"]["LightComponent0"]["Intensity"]),
                       "her_keyed": False},
                      {"label": "SkyLight", "class": "SkyLight", "property": "Intensity", "value": 1.0,
                       "her_keyed": False},                              # unserialised = class default 1.0 [inf]
                      {"label": "SkyAtmosphere", "class": "SkyAtmosphere", "property": None}],
             hangar_lights=[{"label": "S4 Practical L1", "role": "black", "class": "SpotLight", "loc": [0, 0, 0],
                             "radius": 2500.0}],
             rig_bulbs=["S4 Lattice Bulb 1-1"], lattice_pieces=["S4 Hangar Lattice Fly"], our_ppv=[],
             her_audio=[{"sound": a["sound"], "active": True, "start_frame": a["range_tick"][0] // 800,
                         "end_frame": -(-a["range_tick"][1] // 800)} for a in her["audio"]])
    args = copy.deepcopy(ARGS)
    args["scene"] = "4"
    if style:
        args["scenes"]["4"]["reveal_style"] = style
    if lit_frame is not None:
        args["scenes"]["4"]["lit"] = {"frame": lit_frame}
    # _gather_reveal, minus Unreal
    st = R.reveal_style(args, "4")
    if st != "strike":
        F, step = R.snap_her_frame(f["her_first"]["frame"], f["her_range"][0], 30.0, FPS)
        cam = cam_at(F)
        plat = {k: v["plateau"] for k, v in R.find_lit_frame(
            {r["label"]: (r["curves"] or {}).get("Intensity") for r in lights}, f["her_range"][0], f["her_range"][1],
            30.0, R.lit_cfg(args, "4"))["per_light"].items() if v.get("keyed")}
        dk = R.opening_darkness(lights, {"loc": cam["loc"], "rot": cam["rot"], "focal": 35.0, "sensor": [23.76, 13.365]},
                                F, plat, [], dict(R.DARK_DEFAULTS))
        rv = {"requested": st, "frame": F, "frame_first_bound": f["her_first"]["frame"], "snap_step": step,
              "darkness": dk, "dangling_cuts": f["her_first"]["dangling_cuts"]}
        rv["style"], rv["why"] = R.resolve_reveal(st, dk)
        f["reveal"] = rv
    f["lit"] = R.detect_lit(f, args, FPS)
    if f["lit"]["frame"] is not None:
        f["her_lit"] = cam_at(f["lit"]["frame"])
        R.apply_lit_values(f, f["lit"]["frame"])
    return f, args


S4_LT = s4_lt_now()


class S4Bytes(unittest.TestCase):
    """Why HER_CAMERA_BINDING_FIRST was 0, and what else in her S4 bindings is off. [meas] bytes."""

    def test_first_cut_is_dangling(self):
        for path in (LS_CHILDREN, LS_CHILDREN_COPY):
            b = derive_ls(path)
            first = b["cuts"][0]
            self.assertEqual(first["range"], [0, 2])
            self.assertEqual(first["guid"], "c6fa88373d73334ea4f018e65c4f2735")
            self.assertNotIn(first["guid"], b["poss"])                    # no possessable ...
            self.assertNotIn(first["guid"], b["refs"])                    # ... and no binding reference
            self.assertEqual(b["fades"], 0)                               # no fade track in her LS
            for c in b["cuts"][1:]:
                self.assertIn(c["guid"], b["poss"])                       # control: every later cut is bound
            fb = R.first_bound_cut(b["cuts"], list(b["poss"]), b["playback"][0])
            self.assertEqual((fb["frame"], len(fb["dangling"])), (2, 1))
        s1 = derive_ls(LS_ANIMALS_COPY)                                   # control: S1's first cut IS bound
        self.assertIn(s1["cuts"][0]["guid"], s1["poss"])

    def test_cameras_resolve_into_her_level_and_l_animals_repeats_labels(self):
        b = derive_ls(LS_CHILDREN)
        cam_paths = sorted(b["refs"][c["guid"]][0][1]["Path"] for c in b["cuts"][1:])
        self.assertTrue(all(p.startswith("/Game/L_KK_children.L_KK_children:PersistentLevel.CineCameraActor_")
                            for p in cam_paths), cam_paths)
        anim = {r.get("label") for r in derive_level_rows(L_ANIMALS).values()}
        mine = {r.get("label") for r in derive_level_rows(L_CHILDREN).values()}
        clash = sorted(x for x in {"CineCameraActor", "CineCameraActor2", "CineCameraActor3"} if x in anim and x in mine)
        self.assertEqual(clash, ["CineCameraActor", "CineCameraActor2", "CineCameraActor3"])
        own = [{"label": "CineCameraActor", "name": "CineCameraActor_0", "lvl": "children"}]
        other = [{"label": "CineCameraActor", "name": "CineCameraActor_0", "lvl": "animals"}]
        self.assertEqual([x["lvl"] for x in R.pick_camera_actor(own, other, "CineCameraActor")], ["children"])
        self.assertEqual(len([a for a in own + other if a["label"] == "CineCameraActor"]), 2)   # control: v3 pool
        self.assertEqual([x["lvl"] for x in R.pick_camera_actor([], other, "CineCameraActor")], ["animals"])

    def test_orphan_light_components_point_into_l_animals(self):
        b = derive_ls(LS_CHILDREN)
        orphans = [p for p in b["poss"].values() if p["parent"] and p["parent"] not in b["poss"]]
        self.assertEqual(len(orphans), 5)
        self.assertTrue(all(o["name"] == "LightComponent0" for o in orphans))
        tgt = sorted(b["refs"][o["parent"]][0][1]["Path"].split(".")[-1] for o in orphans)
        self.assertEqual(tgt, ["SpotLight_1", "SpotLight_17", "SpotLight_20", "SpotLight_22", "SpotLight_23"])
        self.assertTrue(all(b["refs"][o["parent"]][0][1]["Path"].startswith("/Game/KK_S1_Animals/L_Animals.")
                            for o in orphans))
        parented = [p for p in b["poss"].values() if p["parent"] and p["parent"] in b["poss"]]
        self.assertGreater(len(parented), 20)                                          # control: the rest are whole

    def test_copy_shift_equals_level_transform(self):
        o, c = derive_ls(LS_CHILDREN), derive_ls(LS_CHILDREN_COPY)
        for g, ch in o["camera_channels"].items():
            for i in range(3):
                a, b = ch["Translation[%d]" % i], c["camera_channels"][g]["Translation[%d]" % i]
                for ka, kb in zip(a["keys"], b["keys"]):
                    self.assertAlmostEqual(kb["value"] - ka["value"], S4_LT[i], places=3)
        self.assertNotEqual(S4_LT[1], 0.0)                                            # control: a real shift
        self.assertTrue(any(all(abs(S4_LT[i] - lt[i]) < 0.01 for i in range(3)) for lt in s4_lt_allowed()),
                        (S4_LT, s4_lt_allowed()))                                      # a KNOWN placement, not drift
        self.assertFalse(all(abs(S4_LT[i] - [0.0, 0.0, 0.0][i]) < 0.01 for i in range(3)))

    def test_her_opening_measured(self):
        """Her opening, her frames at 30 fps (curves CUBIC with stored zero tangents = eased)."""
        b = derive_ls(LS_CHILDREN)
        cam = b["camera_channels"]["b28a821d72b7a24ea738eb622365a09c"]               # CineCameraActor (_0)
        self.assertEqual([k["tick"] // 800 for k in cam["Translation[0]"]["keys"]], [2, 351, 795])
        self.assertEqual([k["value"] for k in cam["Translation[0]"]["keys"]], [692.0, 692.0, -1195.0])
        self.assertTrue(all(k["interp"] == "cubic" for k in cam["Translation[0]"]["keys"]))
        self.assertEqual(cam["Rotation[2]"]["keys"], [])                               # no pan: yaw is a default
        self.assertEqual((cam["Rotation[1]"]["default"], cam["Rotation[2]"]["default"]), (6.000000000000003, 5.0))
        p6, p351 = _cam_pose(cam, 6), _cam_pose(cam, 351)
        self.assertLess(math.dist(p6["loc"], p351["loc"]), 61.0)                       # static-ish until 11.7 s
        self.assertGreater(math.dist(p351["loc"], _cam_pose(cam, 795)["loc"]), 1900.0)   # then an 19 m dolly back
        lv = {r.get("label"): r for r in derive_level_rows(L_CHILDREN).values()}
        guid_of = {p["name"]: g for g, p in b["poss"].items()}
        curve = lambda lab: b["intensity_by_parent_guid"][guid_of[lab]]
        self.assertEqual(R.curve_at(curve("SpotLight"), 0), 0.0)
        self.assertEqual(R.curve_at(curve("SpotLight2"), 0), 0.0)
        self.assertEqual(R.curve_at(curve("Spot_MainLight_window"), 0), 160.0)        # constant (one key)
        self.assertAlmostEqual(R.curve_at(curve("SpotLight"), 384), 160.0, places=3)
        self.assertGreater(lv["SpotLight"]["comps"]["LightComponent0"]["OuterConeAngle"], 79.0)


class S4Reveal(unittest.TestCase):
    def test_darkness_at_her_first_frame(self):
        f, _a = s4_facts(style="auto")
        rv = f["reveal"]
        self.assertEqual((rv["frame_first_bound"], rv["frame"]), (2, 6))             # snapped up onto the 6-grid
        dk = rv["darkness"]
        self.assertTrue(dk["dark"], dk)
        self.assertEqual(dk["lit_fraction"], 0.0)
        covering = sorted(k for k, v in dk["cover"].items() if v["samples"])
        self.assertEqual(covering, ["SpotLight", "SpotLight2"])                        # only the two that ramp up
        self.assertGreater(dk["all_lights_fraction"], 0.3)                             # control: unweighted says lit
        self.assertEqual(rv["style"], "her_dark_pan")
        lights = copy.deepcopy(f["her_lights"])                                        # control: lit at Lh -> strike
        F = 354
        cam = _cam_pose(derive_ls(LS_CHILDREN_COPY)["camera_channels"]["b28a821d72b7a24ea738eb622365a09c"], F)
        dk2 = R.opening_darkness(lights, {"loc": cam["loc"], "rot": cam["rot"], "focal": 35.0,
                                          "sensor": [23.76, 13.365]}, F, {}, [], dict(R.DARK_DEFAULTS))
        self.assertFalse(dk2["dark"], dk2)
        self.assertEqual(R.resolve_reveal("auto", dk2)[0], "strike")
        self.assertTrue(R.opening_darkness(lights, {"loc": cam["loc"], "rot": cam["rot"], "focal": 35.0,
                                                    "sensor": [23.76, 13.365]}, F, {}, [1.0], dict(R.DARK_DEFAULTS))["dark"])
        with self.assertRaises(R.PlanError):
            R.resolve_reveal("sideways", dk2)

    def test_dark_pan_plan(self):
        f, a = s4_facts(style="auto")
        p = R.build_plan(f, a)
        self.assertEqual(p["refusals"], [], p["refusals"])
        tl = p["timeline"]
        self.assertEqual(p["reveal"]["style"], "her_dark_pan")
        self.assertEqual(p["slot"]["her_frame_at_cut"], 6)
        self.assertEqual(p["slot"]["skip_frames"], 5)                                 # 6 her frames = 5 of ours
        self.assertEqual(p["slot"]["start_offset_ticks"], 6 * 800)
        self.assertEqual(tl["slot"][1] - tl["slot"][0], (4476 - 376) - 5)
        self.assertFalse(any(r["strikes"] for r in p["her_lights"]))
        self.assertEqual(p["strike_schedule"]["frames"], [])
        by = {r["label"]: r for r in p["her_lights"]}
        for r in f["her_lights"]:
            want = R.curve_at(r["curves"]["Intensity"], 6) if r["curves"] else r["intensity"]
            row = by[r["label"]]
            self.assertEqual(row["intro_keys"][-1][1], want if want > 1e-3 else 0.0)   # continuous at the cut
            self.assertLess(row["intro_keys"][-1][0], tl["cut"])
            if want > 1e-3:
                self.assertEqual(row["ramp"], tl["crossfade"])
                steps = [b[1] - a_[1] for a_, b in zip(row["intro_keys"][1:], row["intro_keys"][2:])]
                self.assertTrue(all(s_ >= -1e-9 for s_ in steps))                     # a ramp, never a flicker
                self.assertLess(max(steps), 0.1 * want)
            else:
                self.assertEqual(row["intro_keys"], [[tl["land"], 0.0]])
        self.assertEqual(by["SpotLight"]["intro_keys"], [[tl["land"], 0.0]])          # the framed lights stay dark
        self.assertEqual(by["SpotLight2"]["intro_keys"], [[tl["land"], 0.0]])
        keys = {k[0]: k for k in p["glide"]["keys"]}
        first = p["poses"]["her_lit"]
        self.assertEqual(keys[tl["cut"]][1:7], first["loc"] + first["rot"])           # lands ON her frame-6 pose
        self.assertTrue(any("HER_FIRST_CUT_DANGLING" in w for w in p["warnings"]) or f["her_first"]["dangling_cuts"])
        self.assertFalse(any("HER_LIT_FRAME_MOVES" in w for w in p["warnings"]))      # 0.36 cm/s at her frame 6
        st, _a2 = s4_facts(style="strike")                                             # control: strike style
        ps = R.build_plan(st, _a2)
        self.assertEqual(ps["refusals"], [], ps["refusals"])
        self.assertNotIn("reveal", ps)
        self.assertEqual(ps["lit"]["frame"], 354)
        self.assertGreater(sum(1 for r in ps["her_lights"] if r["strikes"]), 4)
        self.assertGreater(ps["slot"]["skip_frames"], 250)
        self.assertGreater(tl["planned_end"], ps["timeline"]["planned_end"])           # dark pan keeps her opening

    def test_scene_lit_override(self):
        f, a = s4_facts(style="strike", lit_frame=798)
        self.assertEqual((f["lit"]["frame"], f["lit"]["method"]), (798, "args lit.frame"))
        self.assertEqual(R.lit_cfg(a, "4")["frame"], 798)
        self.assertIsNone(R.lit_cfg(a, "1")["frame"])                                 # control: S1 unaffected
        self.assertIsNone(R.lit_cfg(a)["frame"])

    def test_env_only_if_needed(self):
        f, a = s4_facts(style="her_dark_pan")
        f["her_env"].append({"label": "Fog0", "class": "ExponentialHeightFog", "property": "FogDensity", "value": 0.0,
                             "her_keyed": False})
        R.apply_lit_values(f, f["lit"]["frame"])
        p = R.build_plan(f, a)
        acts = {e["label"]: e["action"] for e in p["her_env"]}
        self.assertEqual(acts["DirectionalLight"], "ramp")
        self.assertTrue(acts["Fog0"].startswith("none_needed"))
        f2, a2 = s4_facts(style="strike")                                              # control: strike ramps all
        f2["her_env"].append(dict(f["her_env"][-1]))
        R.apply_lit_values(f2, f2["lit"]["frame"])
        self.assertEqual({e["label"]: e["action"] for e in R.build_plan(f2, a2)["her_env"]}["Fog0"], "ramp")

    def test_s1_replay_of_the_live_v3_dry(self):
        """[meas] klara_reveal_dry_S1.json (KLARAREVEAL-20261007-011442, the v3 DRY that preceded the live S1 APPLY):
        this code re-plans its facts to the recorded plan (floats to 1e-12 relative: the live Python's random.uniform
        differs in the last ulp). Control: the same facts forced to her_dark_pan give a different plan."""
        path = os.path.join(HERE, "klara_reveal_dry_S1.json")
        if not os.path.exists(path):
            self.skipTest("S1 DRY absent")
        d = R.load_json(path)
        got = json.loads(json.dumps(R.build_plan(copy.deepcopy(d["facts"]), d["args"]), sort_keys=True, default=str))
        want = json.loads(json.dumps(d["plan"], sort_keys=True, default=str))

        def same(x, y):
            if isinstance(x, float) or isinstance(y, float):
                return isinstance(x, (int, float)) and isinstance(y, (int, float)) and \
                    abs(x - y) <= 1e-12 * max(1.0, abs(x), abs(y))
            if isinstance(x, dict):
                return isinstance(y, dict) and set(x) == set(y) and all(same(x[k], y[k]) for k in x)
            if isinstance(x, list):
                return isinstance(y, list) and len(x) == len(y) and all(same(a, b) for a, b in zip(x, y))
            return x == y
        self.assertTrue(same(got, want))
        self.assertTrue(same(json.loads(json.dumps(R.build_plan(copy.deepcopy(d["facts"]), dict(d["args"])),
                                                   sort_keys=True, default=str)), want))
        live_args = copy.deepcopy(ARGS)
        live_args["scene"] = "1"
        self.assertEqual(R.reveal_style(live_args, "1"), "strike")                     # S1 stays strike
        fx = copy.deepcopy(d["facts"])
        fx["reveal"] = {"style": "her_dark_pan", "frame": fx["her_range"][0]}
        fx["lit"] = R.detect_lit(fx, d["args"], 25.0)
        self.assertFalse(same(json.loads(json.dumps(R.build_plan(fx, d["args"]), sort_keys=True, default=str)), want))


def bezier_ref(k0, k1, t):
    """INDEPENDENT reference for UE's cubic channel segment: de Casteljau on P0..P3 with P1 = v0 + leave*dt/3,
    P2 = v1 - arrive*dt/3 (time is linear in the parameter for unweighted tangents)."""
    dt = float(k1["tick"] - k0["tick"])
    u = (t - k0["tick"]) / dt
    pts = [k0["value"], k0["value"] + k0["leave"] * dt / 3.0, k1["value"] - k1["arrive"] * dt / 3.0, k1["value"]]
    while len(pts) > 1:
        pts = [a_ + (b_ - a_) * u for a_, b_ in zip(pts, pts[1:])]
    return pts[0]


class StrictEval(unittest.TestCase):
    """v4b: the live S4 DRY stopped HER_CAMERA_EVAL (her frame 2 is a key, frame 3 is between keys 2 and 351)."""
    CAM = "b28a821d72b7a24ea738eb622365a09c"

    def test_key_exact_and_bytes_cubic_vs_reference(self):
        ch = derive_ls(LS_CHILDREN_COPY)["camera_channels"][self.CAM]
        x = ch["Translation[0]"]
        self.assertEqual(R.strict_curve_at(x, 2), x["keys"][0]["value"])              # on a key: the key value
        y = ch["Translation[1]"]
        worst = 0.0
        for fr in (3, 6, 100, 200, 346):
            t = fr * 800.0
            worst = max(worst, abs(R.strict_curve_at(y, fr) - bezier_ref(y["keys"][0], y["keys"][1], t)))
        self.assertLess(worst, 0.01)
        self.assertGreater(abs(R.strict_curve_at(y, 200) - (293 + 60 * 198 / 345.0)), 1.0)   # control: not linear
        rot = derive_ls(LS_CHILDREN_COPY)["camera_channels"]["77a718f00c13674e821008824866da35"]["Rotation[2]"]
        k0, k1 = rot["keys"][0], rot["keys"][1]
        for fr in (3600, 3700, 3900):
            self.assertLess(abs(R.strict_curve_at(rot, fr) - bezier_ref(k0, k1, fr * 800.0)), 0.001)
        bent = copy.deepcopy(y)                                                        # control: tangents matter
        bent["keys"][0]["leave"] = 0.0005
        self.assertGreater(abs(R.strict_curve_at(bent, 100) - R.strict_curve_at(y, 100)), 0.01)
        self.assertGreater(abs(bezier_ref(bent["keys"][0], bent["keys"][1], 80000.0) -
                               bezier_ref(y["keys"][0], y["keys"][1], 80000.0)), 0.01)

    def test_nonzero_tangent_matches_reference(self):
        k = [{"tick": 0, "value": 10.0, "interp": "cubic", "interp_raw": "RCIM_CUBIC", "arrive": 0.0, "leave": 0.002,
              "weight_mode": "RCTWM_WEIGHTED_NONE"},
             {"tick": 24000, "value": 50.0, "interp": "cubic", "interp_raw": "RCIM_CUBIC", "arrive": -0.001, "leave": 0.0,
              "weight_mode": "RCTWM_WEIGHTED_NONE"}]
        c = {"tpf": 800.0, "keys": k, "default": None}
        for fr in (1, 7, 15, 29):
            self.assertLess(abs(R.strict_curve_at(c, fr) - bezier_ref(k[0], k[1], fr * 800.0)), 0.01)
        lin = copy.deepcopy(c)
        for x in lin["keys"]:
            x["interp"], x["interp_raw"] = "linear", "RCIM_LINEAR"
        self.assertAlmostEqual(R.strict_curve_at(lin, 15), 30.0, places=9)
        cst = copy.deepcopy(c)
        cst["keys"][0]["interp"], cst["keys"][0]["interp_raw"] = "constant", "RCIM_CONSTANT"
        self.assertEqual(R.strict_curve_at(cst, 15), 10.0)

    def test_unsupported_refuses(self):
        y = copy.deepcopy(derive_ls(LS_CHILDREN_COPY)["camera_channels"][self.CAM]["Translation[1]"])
        for k in y["keys"]:
            k.update(interp_raw="RCIM_CUBIC", weight_mode="RCTWM_WEIGHTED_NONE")
        self.assertIsNotNone(R.strict_curve_at(y, 6))                                 # control: supported passes
        for mut in ({"weight_mode": "RCTWM_WEIGHTED_BOTH"}, {"weight_unread": True}, {"interp_raw": "RCIM_NONE"},
                    {"interp_unread": True}, {"tangent_unread": True}):
            bad = copy.deepcopy(y)
            bad["keys"][0].update(mut)
            with self.assertRaises(R.PlanError) as cm:
                R.strict_curve_at(bad, 6)
            self.assertIn("HER_CURVE_UNSUPPORTED", str(cm.exception))
        self.assertEqual(R.strict_curve_at(dict(y, keys=y["keys"]), 2), y["keys"][0]["value"])   # key: no refusal path

    def test_live_channel_path_uses_strict(self):
        """_ch_eval_strict with a fake scripting channel: exact keys go through eval_keys (S1's path, unchanged),
        between keys through strict_curve_at - never None, never a snapped key."""
        class _N:
            def __init__(s_, v): s_.value = v
        class _T:
            def __init__(s_, v): s_.frame_number = _N(v)
        class _K:
            def __init__(s_, f, v): s_.f, s_.v = f, v
            def get_time(s_, time_unit=None): return _T(s_.f)
            def get_value(s_): return s_.v
        class _C:
            def __init__(s_, keys): s_.k = keys
            def get_keys(s_): return s_.k
            def has_default(s_): return False
            def get_default(s_): return 0.0
        y = derive_ls(LS_CHILDREN_COPY)["camera_channels"][self.CAM]["Translation[1]"]
        fake = _C([_K(k["tick"] // 800, k["value"]) for k in y["keys"]])
        self.assertEqual(R._ch_eval_strict(fake, y, 2), y["keys"][0]["value"])
        v3 = R._ch_eval_strict(fake, y, 3)
        self.assertIsNotNone(v3)
        self.assertNotIn(v3, [k["value"] for k in y["keys"]])                          # control: not snapped
        self.assertIsNone(R.eval_keys([[k["tick"] // 800, k["value"]] for k in y["keys"]], None, 3))   # the old stop


# Seeded mutations of the v4 code: each must make at least one v4 test fail (proves the tests can fail).
V4_MUTATIONS = [
    ("strikes = target > min_v and not dark_pan", "strikes = target > min_v"),
    ("    n_strike = 0 if dark_pan else sum(", "    n_strike = 0 if False else sum("),
    ("intro = dedupe_keys(intro + ramp_keys(0.0, target, tl[\"crossfade\"][0], tl[\"crossfade\"][1]))",
     "intro = dedupe_keys(intro + ramp_keys(0.0, target * 0.5, tl[\"crossfade\"][0], tl[\"crossfade\"][1]))"),
    ("        if c[\"guid\"] in bound:\n", "        if True:\n"),
    ("    return hit if hit else [a for a in other", "    return (hit + [a for a in other] if hit else [a for a in other]) or [a for a in other"),
    ("    if light.get(\"class\") != \"SpotLight\":\n        return True", "    if True:\n        return True"),
    ("    dark = (frac is not None and frac <= float(cfg[\"max_lit_fraction\"]))",
     "    dark = (frac is not None and frac >= float(cfg[\"max_lit_fraction\"]))"),
    ("    return (\"her_dark_pan\" if darkness[\"dark\"] else \"strike\")", "    return (\"strike\" if darkness[\"dark\"] else \"strike\")"),
    ("        cfg = dict(cfg, frame=int(rv[\"frame\"]), enabled=True)", "        cfg = dict(cfg, enabled=True)"),
    ("        if dark_pan and v_in <= EPS and v <= EPS:", "        if False:"),
    ("            if d[2] < -EPS:\n                t = -float(cam_loc[2]) / d[2]", "            if d[2] < -EPS:\n                t = 10.0"),
    ("        c.update(((args.get(\"scenes\") or {}).get(str(key)) or {}).get(\"lit\") or {})", "        pass"),
]
V4_MUTATIONS += [
    ("                    if k.get(\"weight_unread\") or k.get(\"weight_mode\", \"RCTWM_WEIGHTED_NONE\") not in STRICT_WEIGHT_OK:",
     "                    if False:"),
    ("                if k.get(\"interp_unread\") or raw not in STRICT_INTERP_RAW:", "                if False:"),
    ("    return v if v is not None else strict_curve_at(curve, frame)", "    return v"),
]
V4_TESTS = ("S4Bytes", "S4Reveal", "StrictEval")


def run_v4_mutations():
    src = open(R.__file__, encoding="utf-8").read()
    caught = []
    for old, new in V4_MUTATIONS:
        if src.count(old) != 1:
            caught.append((old[:50], "ANCHOR_MISSING"))
            continue
        mod = type(R)("klara_reveal_mut")
        mod.__dict__["__file__"] = R.__file__
        exec(compile(src.replace(old, new), R.__file__, "exec"), mod.__dict__)
        g = globals()
        saved = g["R"]
        g["R"] = mod
        try:
            suite = unittest.TestSuite()
            for cls in V4_TESTS:
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(g[cls]))
            _BYTES.clear()
            res = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
            caught.append((old[:50], "CAUGHT" if (res.failures or res.errors) else "SURVIVED"))
        finally:
            g["R"] = saved
            _BYTES.clear()
    return caught


class V4Mutations(unittest.TestCase):
    def test_every_mutation_is_caught(self):
        rows = run_v4_mutations()
        bad = [r for r in rows if r[1] != "CAUGHT"]
        self.assertEqual(bad, [], rows)
        self.assertEqual(len(rows), len(V4_MUTATIONS))


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
