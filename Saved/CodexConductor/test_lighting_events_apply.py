"""Offline harness for lighting_events_apply.py, with +/- controls.

Run: python Saved/CodexConductor/test_lighting_events_apply.py
Every property check is shown to FAIL on a deliberately bad input (negative
control) before it is trusted on the real schedule (positive control).
"""
from __future__ import annotations

import ast
import copy
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lighting_events_apply as E  # noqa: E402

PHASE_A = {"drama_flash": False}
PHASE_B = {"drama_flash": True}


# ---------------------------------------------------------------- metrics

def is_aperiodic(times_s, bin_s=0.25, max_autocorr=0.5, min_cv=0.35):
    """Two independent tests, both must pass:
    1. normalised autocorrelation of the binned impulse train (lags >= 1 s)
       stays below max_autocorr (catches exact periods);
    2. coefficient of variation of the intervals >= min_cv (catches jittered
       periods, which smear the autocorrelation peak)."""
    times = sorted(times_s)
    if len(times) < 4:
        return False, {"reason": "too_few_events", "n": len(times)}
    span = times[-1] - times[0]
    bins = int(span / bin_s) + 1
    series = [0.0] * bins
    for t in times:
        series[min(bins - 1, int((t - times[0]) / bin_s))] += 1.0
    energy = sum(v * v for v in series)
    peak = 0.0
    for lag in range(int(1.0 / bin_s), bins // 2 + 1):
        acc = sum(series[i] * series[i + lag] for i in range(bins - lag))
        # Count only lags with real overlap: normalise by events, not bins.
        peak = max(peak, acc / energy)
    gaps = [b - a for a, b in zip(times, times[1:])]
    mean = sum(gaps) / len(gaps)
    cv = math.sqrt(sum((g - mean) ** 2 for g in gaps) / len(gaps)) / mean
    return (peak < max_autocorr and cv >= min_cv), {"autocorr_peak": peak, "cv": cv, "n": len(times)}


def flash_shape(drama, speed_cm_s, fps, decay_s):
    """Sample a flash at a lamp at 0 cm while the camera moves at constant speed.
    Returns dict of shape facts (times in s, relative to the camera reaching
    the trigger)."""
    if drama.get("flash"):
        peak_cm = float(drama["flash_camera_offsets_cm"][0])
    else:
        peak_cm = 0.0
    dt = 1.0 / 2400.0
    samples = []
    t = -1.0
    while t <= 2.0:
        camera = peak_cm + t * speed_cm_s
        samples.append((t, E.eval_drama(drama, 0.0, camera)))
        t += dt
    peak = max(v for _, v in samples)
    t_peak = next(t for t, v in samples if v >= peak - 1e-9)
    t_on = next(t for t, v in samples if v > 1e-6)
    after = [(t, v) for t, v in samples if t >= t_peak]
    monotone = all(b[1] <= a[1] + 1e-9 for a, b in zip(after, after[1:]))
    t_half = next((t for t, v in after if v <= 0.5 * peak), None)
    t_off = next((t for t, v in after if v <= 0.02 * peak), None)
    lit_after_2s = samples[-1][1]
    return {
        "peak": peak,
        "attack_frames": (t_peak - t_on) * fps,
        "half_s": None if t_half is None else t_half - t_peak,
        "off_s": None if t_off is None else t_off - t_peak,
        "monotone_fall": monotone,
        "pre_glow": max(v for t, v in samples if t < t_on - dt) if t_on > -1.0 else 1.0,
        "lit_at_end": lit_after_2s,
        "decay_s": decay_s,
    }


def is_polaroid(shape, decay_s):
    return (shape["peak"] >= 0.99 and shape["attack_frames"] <= 2.0
            and shape["off_s"] is not None and shape["off_s"] <= decay_s + 1e-3
            and shape["half_s"] is not None and shape["half_s"] <= 0.6 * decay_s
            and shape["monotone_fall"] and shape["pre_glow"] == 0.0 and shape["lit_at_end"] == 0.0)


# ---------------------------------------------------------------- fixtures

def make_cues(bays=7, looks_bays=(1, 2, 3, 4, 5, 6)):
    cues = [{"guid": "C0FFEE%026d" % 1, "label": "P03 Wing 009", "attachments": [
        {"guid": "A%031d" % 999, "label": "P03 Wing 009 Key", "kind": "Light", "enabled": True,
         "location": [0, 0, 300], "lighting": {"cast_shadows": True, "intensity": 500.0}}]}]
    n = 0
    for bay in range(1, bays + 1):
        atts = []
        for k in range(2):  # original lights the looks tool disabled
            n += 1
            atts.append({"guid": "A%031d" % n, "label": "P04 Wing %03d Cross %d" % (bay, k), "kind": "Light",
                         "enabled": bay not in looks_bays, "location": [0, 300 * (k * 2 - 1), 250],
                         "lighting": {"cast_shadows": False, "intensity": 300.0}})
        if bay in looks_bays:
            for k in range(8):
                n += 1
                atts.append({"guid": "A%031d" % n, "label": "P04 LOOK B%02d MOODY S%d" % (bay, k),
                             "kind": "Light", "enabled": True, "location": [40, 0, 100],
                             "lighting": {"cast_shadows": k < 2, "intensity": 900.0 if k else 0.0}})
            n += 1
            atts.append({"guid": "A%031d" % n, "label": "P04 LOOK B%02d MOODY PRACTICAL_L_BODY" % bay,
                         "kind": "PROP", "enabled": True, "location": [0, 340, 200], "lighting": {}})
        cues.append({"guid": "C%031d" % bay, "label": "P04 Wing %03d" % bay, "attachments": atts})
    cues.append({"guid": "C0FFEE%026d" % 2, "label": "P05 Wing 001", "attachments": []})
    return cues


def config(**overrides):
    data = E.load_config()
    for path, value in overrides.items():
        node = data
        keys = path.split(".")
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = value
    return data


def stations(cfg, bays):
    return [(b - 1) * float(cfg["nominal_bay_spacing_cm"]) for b in bays]


def black_violations(cfg, cues_after, capabilities):
    """Camera positions (1 cm) in the black window where any NON-glimmer light
    is lit outside every flash window, plus whether flashes light at all."""
    bays = [int(b) for b in cfg["black_mode"]["bays"]]
    rows = [next(c for c in cues_after if c["label"] == "P04 Wing %03d" % b) for b in bays]
    st = stations(cfg, bays)
    windows = []
    for cue, s in zip(rows, st):
        for att in cue["attachments"]:
            drama = att.get("lighting", {}).get("drama") or {}
            if not att.get("enabled") or not drama:
                continue
            if drama.get("flash"):
                for off in drama["flash_camera_offsets_cm"]:
                    peak = s + att["location"][0] + off
                    windows.append((peak - drama["flash_attack_cm"], peak + drama["flash_decay_cm"]))
            elif drama.get("strike_on_approach") and drama.get("after_pass") == "DECAY":
                peak = s + att["location"][0]
                windows.append((peak - drama["strike_distance_cm"], peak + drama["decay_distance_cm"]))
    spacing = float(cfg["nominal_bay_spacing_cm"])
    bad, lit_inside = [], 0
    cam = -0.5 * spacing
    while cam < (len(bays) - 0.5) * spacing:
        inside = any(a - 0.5 <= cam <= b + 0.5 for a, b in windows)
        other = E.light_sum(rows, st, cam, roles=None) - E.light_sum(rows, st, cam, roles={"GLIMMER"})
        if not inside and other > 1e-6:
            bad.append(cam)
        if inside and other > 1e-6:
            lit_inside += 1
        cam += 1.0
    glimmer_total = E.light_sum(rows, st, -1e6, roles={"GLIMMER"})
    return bad, lit_inside, glimmer_total


# ---------------------------------------------------------------- tests

class ConfigTests(unittest.TestCase):
    def test_config_valid(self):
        E.validate_config(E.load_config())

    def test_bad_profiles_refused(self):
        for path, value, code in (("flash_profile.attack_frames", 6.0, "ATTACK_NOT_1_TO_2_FRAMES"),
                                  ("flash_profile.decay_seconds", 1.0, "DECAY_NOT_0_2_TO_0_4_S"),
                                  ("black_mode.glimmer.intensity_cd", 40.0, "GLIMMER_ABOVE_CAP"),
                                  ("black_mode.sequence.flashes_per_burst", [1, 7], "BURST_SIZE_NOT_2_TO_5"),
                                  ("blinkers.mean_gap_s", 3.0, "BLINK_MEAN_GAP_TOO_REGULAR")):
            with self.assertRaisesRegex(E.LightingEventsError, code):
                E.validate_config(config(**{path: value}))


class DeterminismTests(unittest.TestCase):
    def fingerprint(self, cfg, cap):
        by_bay, schedule, deferred = E.build_fixtures(cfg, cap)
        return json.dumps([by_bay, schedule, deferred], sort_keys=True)

    def test_same_seed_same_events(self):
        for cap in (PHASE_A, PHASE_B):
            self.assertEqual(self.fingerprint(E.load_config(), cap), self.fingerprint(E.load_config(), cap))

    def test_different_seed_different_events(self):  # negative control: the check can fail
        self.assertNotEqual(self.fingerprint(config(seed=1), PHASE_A), self.fingerprint(config(seed=2), PHASE_A))

    def test_streams_are_independent(self):
        # Changing the blinker stream's parameters must not re-roll the black train.
        a = E.black_schedule(E.load_config())
        b = E.black_schedule(config(**{"blinkers.mean_gap_s": 20.0}))
        self.assertEqual(a, b)

    def test_single_draw_per_expression(self):
        source = open(os.path.join(HERE, "lighting_events_apply.py"), encoding="utf-8").read()
        self.assertEqual(multi_draw_statements(source), [])
        bad = "def f(s):\n    return draw01(s, 'a', 0) * draw01(s, 'b', 0)\n"
        self.assertEqual(len(multi_draw_statements(bad)), 1)  # negative control


def multi_draw_statements(source):
    names = {"draw01", "draw_range", "draw_int"}
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef,)) and node.name in names:
            continue
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.Return, ast.Expr, ast.AnnAssign)):
            calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                     and getattr(n.func, "id", getattr(n.func, "attr", None)) in names]
            if len(calls) > 1:
                offenders.append(node.lineno)
    return offenders


class PeriodicityTests(unittest.TestCase):
    def test_metric_rejects_exact_period(self):
        for min_cv in (0.35, 0.2):
            ok, info = is_aperiodic([i * 6.0 for i in range(12)], min_cv=min_cv)
            self.assertFalse(ok, info)

    def test_metric_rejects_jittered_period(self):
        jitter = [0.0, 0.2, -0.25, 0.1, -0.15, 0.3, -0.05, 0.22, -0.3, 0.12, 0.0, -0.18]
        for min_cv in (0.35, 0.2):
            ok, info = is_aperiodic([i * 6.0 + j for i, j in enumerate(jitter)], min_cv=min_cv)
            self.assertFalse(ok, info)

    def test_blinkers_are_aperiodic(self):
        cfg = E.load_config()
        v = E.cm_per_s(cfg)
        for seed in range(20261001, 20261011):
            c = config(seed=seed, **{"blinkers.window_cm": [-12000.0, 200.0]})
            times = [x / v for x in E.blink_schedule(c, 1)]
            ok, info = is_aperiodic(times)
            self.assertTrue(ok, (seed, info))
            gaps = [b - a for a, b in zip(times, times[1:])]
            self.assertGreaterEqual(min(gaps), float(cfg["blinkers"]["min_gap_s"]) - 1e-9)

    def test_black_burst_starts_are_aperiodic(self):
        c = config(**{"black_mode.bays": list(range(1, 41))})
        v = E.cm_per_s(c)
        starts = {}
        for event in E.black_schedule(c):
            starts.setdefault(event["burst"], event["camera_cm"] / v)
        # Uniform dark gaps (6-18 s) give CV ~0.29 by construction; 0.2 still
        # rejects both negative controls above.
        ok, info = is_aperiodic(list(starts.values()), bin_s=0.5, min_cv=0.2)
        self.assertTrue(ok, info)

    def test_burst_sizes_in_range(self):
        c = config(**{"black_mode.bays": list(range(1, 41))})
        sizes = {}
        for event in E.black_schedule(c):
            sizes[event["burst"]] = sizes.get(event["burst"], 0) + 1
        whole = list(sizes.values())[:-1]  # the last burst may be cut by the window end
        self.assertTrue(all(2 <= s <= 5 for s in whole), whole)
        self.assertGreater(len(set(whole)), 1)


class FlashShapeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = E.load_config()
        self.v = E.cm_per_s(self.cfg)
        self.fps = float(self.cfg["camera"]["fps"])
        self.decay = float(self.cfg["flash_profile"]["decay_seconds"])

    def test_phase_a_is_polaroid(self):
        shape = flash_shape(E.phase_a_drama(self.cfg), self.v, self.fps, self.decay)
        self.assertTrue(is_polaroid(shape, self.decay), shape)

    def test_phase_b_is_polaroid_and_faster(self):
        a = flash_shape(E.phase_a_drama(self.cfg), self.v, self.fps, self.decay)
        b = flash_shape(E.phase_b_drama(self.cfg, [-300.0]), self.v, self.fps, self.decay)
        self.assertTrue(is_polaroid(b, self.decay), b)
        self.assertLess(b["half_s"], a["half_s"])  # cubic fall beats linear

    def test_looks_keying_is_not_a_flash(self):  # negative control
        looks = {"strike_on_approach": True, "strike_distance_cm": 650.0, "strike_ramp_cm": 150.0,
                 "ignition_stutter": 0.0, "unstruck_intensity_scale": 0.0, "after_pass": "HOLD",
                 "after_pass_distance_cm": 600.0, "decay_distance_cm": 1500.0}
        self.assertFalse(is_polaroid(flash_shape(looks, self.v, self.fps, self.decay), self.decay))

    def test_slow_ramp_is_not_a_flash(self):  # negative control
        slow = dict(E.phase_a_drama(self.cfg), strike_distance_cm=30.0, strike_ramp_cm=30.0)
        self.assertFalse(is_polaroid(flash_shape(slow, self.v, self.fps, self.decay), self.decay))

    def test_strike_port_matches_cpp_test_values(self):
        # Values asserted by InfinityStageLightDramaTests.cpp (StrikeIsDrivenByDistance).
        d = {"strike_on_approach": True, "strike_distance_cm": 2500.0, "strike_ramp_cm": 250.0,
             "ignition_stutter": 0.0, "unstruck_intensity_scale": 0.0, "after_pass": "HOLD",
             "after_pass_distance_cm": 600.0, "decay_distance_cm": 1500.0}
        lamp = 10000.0
        self.assertEqual(E.eval_drama(d, lamp, lamp - 3000.0), 0.0)
        self.assertAlmostEqual(E.eval_drama(d, lamp, lamp - 2375.0), 0.5, places=3)
        self.assertEqual(E.eval_drama(d, lamp, lamp - 2000.0), 1.0)
        self.assertEqual(E.eval_drama(d, lamp, lamp + 5000.0), 1.0)


class BlackModeTests(unittest.TestCase):
    def run_black(self, cfg, cap, mutate=None):
        cues = make_cues()
        after, record, plan = E.apply_plain_state(cfg, cues, cap)
        if mutate:
            mutate(after)
        return black_violations(cfg, after, cap), plan

    def test_black_outside_flashes_phase_a(self):
        cfg = E.load_config()
        (bad, lit_inside, glimmer), plan = self.run_black(cfg, PHASE_A)
        self.assertEqual(bad, [])
        self.assertGreater(lit_inside, 0)  # flashes do light something
        self.assertLessEqual(glimmer, len(cfg["black_mode"]["bays"]) * cfg["black_mode"]["glimmer"]["max_intensity_cd"])

    def test_black_outside_flashes_phase_b(self):
        (bad, lit_inside, _), _ = self.run_black(E.load_config(), PHASE_B)
        self.assertEqual(bad, [])
        self.assertGreater(lit_inside, 0)

    def test_negative_looks_light_left_on(self):
        def leave_one_on(after):
            cue = next(c for c in after if c["label"] == "P04 Wing 003")
            light = next(a for a in cue["attachments"] if a["label"].startswith("P04 LOOK") and a["kind"] == "Light"
                         and a["lighting"]["intensity"] > 0)
            light["enabled"] = True
        (bad, _, _), _ = self.run_black(E.load_config(), PHASE_A, leave_one_on)
        self.assertGreater(len(bad), 0)

    def test_negative_flash_that_holds(self):
        def hold(after):
            cue = next(c for c in after if c["label"] == "P04 Wing 001")
            att = next(a for a in cue["attachments"] if a["label"].startswith("P04 EVT") and "BLACK F" in a["label"])
            att["lighting"]["drama"]["after_pass"] = "HOLD"
        (bad, _, _), _ = self.run_black(E.load_config(), PHASE_A, hold)
        self.assertGreater(len(bad), 0)


class ScopeTests(unittest.TestCase):
    def test_guid_keyed_apply_and_exact_revert(self):
        cfg = E.load_config()
        cues = make_cues()
        after, record, plan = E.apply_plain_state(cfg, cues, PHASE_A)
        self.assertEqual(E.outside_hash(cues, plan["target_cue_guids"]),
                         E.outside_hash(after, plan["target_cue_guids"]))
        # Shuffle order: revert must still be exact, keyed by GUID.
        shuffled = list(reversed(after))
        restored = revert_sorted = E.revert_plain_state(shuffled, record)
        self.assertEqual(sorted(json.dumps(c, sort_keys=True) for c in restored),
                         sorted(json.dumps(c, sort_keys=True) for c in cues))
        del revert_sorted

    def test_outside_hash_detects_change(self):  # negative control
        cfg = E.load_config()
        cues = make_cues()
        after, _, plan = E.apply_plain_state(cfg, cues, PHASE_A)
        after[0]["attachments"][0]["enabled"] = False  # a P03 light: outside scope
        self.assertNotEqual(E.outside_hash(cues, plan["target_cue_guids"]),
                            E.outside_hash(after, plan["target_cue_guids"]))

    def test_shadow_budget_enforced(self):
        cfg = E.load_config()
        for source in cfg["sources"].values():
            source["cast_shadows"] = True
        cfg["black_mode"]["sequence"]["camera_share"] = 0.0
        with self.assertRaisesRegex(E.LightingEventsError, "SHADOW_BUDGET_EXCEEDED"):
            E.build_plain_plan(cfg, make_cues(), PHASE_A)

    def test_budget_ok_and_looks_conflict_reported(self):
        plan = E.build_plain_plan(E.load_config(), make_cues(), PHASE_A)
        self.assertLessEqual(plan["shadow"]["p04_after"], plan["shadow"]["p04_before"])
        self.assertEqual(len(plan["looks_conflict_cues"]), 6)
        # Without the looks' casters to free, black mode cannot fit the budget
        # (a real constraint, not a test artefact) ...
        with self.assertRaisesRegex(E.LightingEventsError, "SHADOW_BUDGET_EXCEEDED"):
            E.build_plain_plan(E.load_config(), make_cues(looks_bays=()), PHASE_A)
        # ... while blinkers alone on clean bays report no conflict.
        clean = E.build_plain_plan(config(**{"black_mode.enabled": False}), make_cues(looks_bays=()), PHASE_B)
        self.assertEqual(clean["looks_conflict_cues"], [])

    def test_phase_b_rows_deferred_without_engine(self):
        plan = E.build_plain_plan(E.load_config(), make_cues(), PHASE_A)
        self.assertTrue(all(r["phase"] == "A" for t in plan["targets"] for r in t["fixtures"]))
        self.assertEqual(len(plan["deferred"]), 2)
        plan_b = E.build_plain_plan(E.load_config(), make_cues(), PHASE_B)
        self.assertEqual(plan_b["deferred"], [])

    def test_already_present_refused(self):
        cfg = E.load_config()
        after, _, _ = E.apply_plain_state(cfg, make_cues(), PHASE_A)
        with self.assertRaisesRegex(E.LightingEventsError, "EVENTS_ALREADY_PRESENT"):
            E.build_plain_plan(cfg, after, PHASE_A)

    def test_missing_bay_refused(self):
        with self.assertRaisesRegex(E.LightingEventsError, "TARGET_BAY_MISSING"):
            E.build_plain_plan(E.load_config(), make_cues(bays=4), PHASE_A)


if __name__ == "__main__":
    unittest.main(verbosity=2)
