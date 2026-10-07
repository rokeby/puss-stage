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
ARGS["allow_lattice_overlap"] = False      # the harness pins plan switches; the live args file may differ
ARGS["lattice"] = "cancel"
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
                               "color": [1.0, 1.0, 1.0, 1.0],
                               "radius": 800.0, "reach": R.glow_reach({"x": 0, "y": 0, "z": 1211}, 800.0, 0.0)}],
            "our_ppv": [{"label": "S1 Hangar Pinned Exposure", "priority": 0.0}], "label": "Scene 1 — External Sound",
            "tick": 24000.0, "rig_bulbs": ["S1 Lattice Bulb 1-1"],
            "lattice_pieces": ["S1 Hangar Lattice Fly", "S1 Hangar Lattice Beam 01", "S1 Lattice Glow 1-1"],
            "lattice": {"keys": RISE_KEYS, "offset_ticks": 0, "section": [0, 775], "play_rate": 1.0}}


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
        p = R.build_plan(facts(), ARGS)
        self.assertEqual(p["refusals"], [], p["refusals"])
        tl = p["timeline"]
        keys = {k[0]: k for k in p["glide"]["keys"]}
        first, last = p["poses"]["her_first"], p["poses"]["her_last"]
        self.assertEqual(keys[tl["cut"]][1:7], first["loc"] + first["rot"])          # intro ends ON her first frame
        held = [k for f, k in sorted(keys.items()) if tl["glide_in"][1] <= f <= tl["cut"]]   # LINEAR keys: equal
        self.assertGreaterEqual(len(held), 2)                                          # ends => at rest between
        for k in held:
            self.assertEqual(k[1:8], first["loc"] + first["rot"] + [first["focal"]])
        self.assertEqual(keys[tl["glide_in"][1]][1:7], first["loc"] + first["rot"])   # there BEFORE the first strike
        self.assertLess(tl["glide_in"][1], min(r["strike_frame"] for r in p["her_lights"]))
        self.assertEqual(keys[tl["slot"][1]][1:7], last["loc"] + last["rot"])        # outro starts ON her last frame
        self.assertEqual(keys[tl["cut"]][7], 50.0)                                    # her lens, exact
        self.assertEqual(keys[tl["glide_in"][0]][1:4], [28784.0135, 0.0, 150.0])      # from the Entry pose
        self.assertEqual(keys[0][1:4], [28784.0135, 0.0, 150.0]) if 0 in keys else None
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
        self.assertEqual(acts, {"S1 Practical L1": "black_color", "S1 Lattice Glow 1-1": "fade_color"})
        glow = [h for h in p["hangar_lights"] if h["action"] == "fade_color"][0]
        ck = {k[0]: k[1] for k in glow["color_keys"]}
        S0 = min(r["strike_frame"] for r in p["her_lights"])
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
        f = facts(her_set=[30000.0, 31000.0, -1500.0, 1500.0, 0.0, 300.0])           # control: 30 m wide
        p = R.build_plan(f, ARGS)
        self.assertTrue(any("SET_DOES_NOT_FIT_LIVE_BOX" in r for r in p["refusals"]))
        self.assertFalse(p["apply_ready"])

    def test_lattice_flag(self):
        f = facts(her_set=[28784.0135 + 900, 28784.0135 + 2500, -400.0, 400.0, 0.0, 1300.0],
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
        p = R.build_plan(facts(), ARGS)
        cam = p["poses"]["her_first"]["loc"]
        self.assertAlmostEqual(cam[0] - 28784.0135, p["placement"]["lead_cm"], places=6)
        self.assertFalse(any("LEAD_ABOVE_RANGE" in w for w in p["warnings"]))
        f = facts(first_loc=[28784.0135 + 3772 + 900, 0.0, 140.0])                   # control: camera far past her set
        p2 = R.build_plan(f, ARGS)
        self.assertTrue(any("LEAD_ABOVE_RANGE" in w for w in p2["warnings"]))

    def test_long_glide_speed_bounded(self):
        f = facts(first_loc=[28784.0135 + 3772 + 900, 0.0, 140.0])                   # set far down the box
        p = R.build_plan(f, ARGS)
        self.assertGreater(p["glide"]["in"]["distance_cm"], 2000.0)
        self.assertLessEqual(p["glide"]["in"]["peak_speed_cm_s"], 300.0)
        self.assertGreater(p["timeline"]["glide_in_s"], 6.0)

    def test_lattice_modes(self):
        f = facts()
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
