"""Offline harness for lighting_events_apply.py, with +/- controls.

Run: python Saved/CodexConductor/test_lighting_events_apply.py
Every property check is shown to FAIL on a deliberately bad input (negative
control) before it is trusted on the real schedule (positive control).

Target (Gary 4 Oct): black mode on P06 bays 2-10 of W&T's 64-cue interleave.
The synthetic Show is a MODEL: P06's per-cue lights follow the live census
read on 4 Oct (light_guid_audit_20261004-102539.json: 10 lights per cue, 9
enabled, enabled casters = Entry Top + Entry Fwd +Y, Top Down disabled; Wing
044/055 add a Blink Spot), laid out as the 64-cue interleave (restored cues
labelled 'P06 OLD NN - family', p6_workflow.py:387). It is not a read of the
post-interleave Show, which does not exist yet.
"""
from __future__ import annotations

import ast
import copy
import hashlib
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
SCORES_CFG = E._read_json(os.path.join(HERE, "lighting_scores.json"))
STANDARD = [("Cross +Y", True, False), ("Cross -Y", True, False), ("Low +Y", True, False),
            ("Low -Y", True, False), ("Entry Top", True, True), ("Entry Fwd +Y", True, True),
            ("Entry Fwd -Y", True, False), ("Entry High +Y", True, False), ("Entry High -Y", True, False),
            ("Top Down", False, True)]  # (name, enabled, casts) per the 4 Oct census


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
        peak = max(peak, acc / energy)
    gaps = [b - a for a, b in zip(times, times[1:])]
    mean = sum(gaps) / len(gaps)
    cv = math.sqrt(sum((g - mean) ** 2 for g in gaps) / len(gaps)) / mean
    return (peak < max_autocorr and cv >= min_cv), {"autocorr_peak": peak, "cv": cv, "n": len(times)}


def flash_shape(drama, speed_cm_s, fps, decay_s):
    """Sample a flash at a lamp at 0 cm while the camera moves at constant speed."""
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
    return {
        "peak": peak,
        "attack_frames": (t_peak - t_on) * fps,
        "half_s": None if t_half is None else t_half - t_peak,
        "off_s": None if t_off is None else t_off - t_peak,
        "monotone_fall": monotone,
        "pre_glow": max(v for t, v in samples if t < t_on - dt) if t_on > -1.0 else 1.0,
        "lit_at_end": samples[-1][1],
        "decay_s": decay_s,
    }


def is_polaroid(shape, decay_s):
    return (shape["peak"] >= 0.99 and shape["attack_frames"] <= 2.0
            and shape["off_s"] is not None and shape["off_s"] <= decay_s + 1e-3
            and shape["half_s"] is not None and shape["half_s"] <= 0.6 * decay_s
            and shape["monotone_fall"] and shape["pre_glow"] == 0.0 and shape["lit_at_end"] == 0.0)


# ---------------------------------------------------------------- fixtures

def gid(*parts):
    return hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest().upper()


def bay_lights(cue_label, cue_guid, casters=True, blink=False, candle=False):
    rows = []
    for name, enabled, casts in STANDARD:
        rows.append({"guid": gid(cue_guid, name), "label": "%s %s" % (cue_label, name), "kind": "Light",
                     "enabled": enabled, "location": [-420.0, 0.0, 300.0],
                     "lighting": {"cast_shadows": casts and casters, "intensity": 30.0}})
    if candle:  # live Wing 055 carries 'FX TEST - S6 Candle Light' (+ its prop), census 4 Oct
        rows.append({"guid": gid(cue_guid, "candle"), "label": "FX TEST - S6 Candle Light", "kind": "Light",
                     "enabled": True, "location": [0.0, 0.0, 100.0],
                     "lighting": {"cast_shadows": True, "intensity": 5.0}})
        rows.append({"guid": gid(cue_guid, "candle prop"), "label": "FX TEST - S6 Candle", "kind": "Prop",
                     "enabled": True, "location": [0.0, 0.0, 100.0], "lighting": {}})
    if blink:
        rows.append({"guid": gid(cue_guid, "blink"), "label": cue_label + " Blink Spot", "kind": "Light",
                     "enabled": True, "location": [-425.0, 0.0, 300.0],
                     "lighting": {"cast_shadows": True, "intensity": 1963.6}})
        rows.append({"guid": gid(cue_guid, "gobo"), "label": cue_label + " Blink Gobo", "kind": "Prop",
                     "enabled": True, "location": [-292.0, 0.0, 300.0], "lighting": {"cast_shadows": True}})
    return rows


def p06_label(ordinal):
    """64-cue interleave labels: odd = kept V3 'P06 Wing NNN'; even = old slots
    (moved legacy keep 'P06 Wing NNN', restored become 'P06 OLD NN - family')."""
    if ordinal % 2:
        return "P06 Wing %03d" % ((ordinal + 1) // 2)
    slot = ordinal // 2
    if slot in (2, 6, 9, 13, 16, 19, 23, 26, 30):  # restored slots (P6_additive.md)
        return "P06 OLD %02d - family" % slot
    # Moved legacy cues keep their labels; plan v3 puts Wing 044 at seq 44 and
    # Wing 055 at seq 64 (p06_interleave_plan_v3.json order_rows); the rest are
    # labelled approximately (only the drift guard reads them).
    return {22: "P06 Wing 044", 32: "P06 Wing 055"}.get(slot, "P06 Wing %03d" % (100 + slot))


def make_show(p06_count=64, casters=True, sting_in_range=False):
    cues = [{"guid": gid("opening"), "label": "Opening - Curtain", "type": "SEQUENCE", "attachments": []}]
    passages = []
    # P04 with the looks prototype's casters: must NOT count toward P06's budget.
    first = last = None
    for ordinal in range(1, 7):
        guid = gid("P04", ordinal)
        label = "P04 Wing %03d" % ordinal
        atts = bay_lights(label, guid)
        for k in range(2):
            atts.append({"guid": gid(guid, "look", k), "label": "P04 LOOK B%02d MOODY S%d" % (ordinal, k),
                         "kind": "Light", "enabled": True, "location": [40, 0, 100],
                         "lighting": {"cast_shadows": True, "intensity": 900.0}})
        cues.append({"guid": guid, "label": label, "type": "WING_PAIR", "attachments": atts})
        first, last = first or guid, guid
    passages.append({"label": "Passage 4", "guid": gid("passage", 4), "first_cue_guid": first, "last_cue_guid": last})
    cues.append({"guid": gid("scene", 5), "label": "Scene 5", "type": "SCENE", "attachments": []})
    first = last = None
    for ordinal in range(1, p06_count + 1):
        guid = gid("P06", ordinal)
        label = p06_label(ordinal) if p06_count == 64 else "P06 Wing %03d" % ordinal
        cues.append({"guid": guid, "label": label, "type": "WING_PAIR",
                     "attachments": bay_lights(label, guid, casters, blink=label == "P06 Wing 044",
                                               candle=label == "P06 Wing 055")})
        first, last = first or guid, guid
        if sting_in_range and ordinal == 4:
            cues.append({"guid": gid("P06-sting"), "label": "P06 sting", "type": "SEQUENCE", "attachments": []})
    passages.append({"label": "Passage 6", "guid": gid("passage", 6), "first_cue_guid": first, "last_cue_guid": last})
    cues.append({"guid": gid("scene", 6), "label": "Scene 6", "type": "SCENE", "attachments": []})
    # Decoy: a WingPair OUTSIDE every range that reuses a black-bay label.
    cues.append({"guid": gid("decoy"), "label": p06_label(3), "type": "WING_PAIR",
                 "attachments": bay_lights(p06_label(3), gid("decoy"))})
    return cues, passages


def config(**overrides):
    data = E.load_config()
    for path, value in overrides.items():
        node = data
        keys = path.split(".")
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = value
    return data


def plan(cfg=None, cap=PHASE_A, cues=None, passages=None, scores=SCORES_CFG, record=None):
    cfg = cfg or E.load_config()
    if cues is None:
        cues, passages = make_show()
    return E.build_plain_plan(cfg, cues, passages, cap, scores, record)


def apply(cfg=None, cap=PHASE_A, cues=None, passages=None, scores=SCORES_CFG, record=None):
    cfg = cfg or E.load_config()
    if cues is None:
        cues, passages = make_show()
    return E.apply_plain_state(cfg, cues, passages, cap, scores, record)


def black_rows(cfg, cues, passages):
    unused, rows = E.resolve_passage_bays(passages, cues, cfg["passage"]["passage_label"])
    by_guid = {c["guid"]: c for c in cues}
    return [by_guid[rows[b - 1]["cue_guid"]] for b in cfg["black_mode"]["bays"]]


def stations(cfg):
    bays = [int(b) for b in cfg["black_mode"]["bays"]]
    return [(b - bays[0]) * float(cfg["nominal_bay_spacing_cm"]) for b in bays]


def black_violations(cfg, rows):
    """Camera positions (1 cm) in the black window where any NON-glimmer light
    is lit outside every flash window, plus whether flashes light at all."""
    st = stations(cfg)
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
    while cam < (len(rows) - 0.5) * spacing:
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
    def test_config_valid_and_targets_p06_2_to_10(self):
        cfg = E.load_config()
        E.validate_config(cfg)
        self.assertEqual(cfg["passage"]["key"], "P06")
        self.assertEqual(cfg["black_mode"]["bays"], list(range(2, 11)))
        self.assertTrue(cfg["black_mode"]["gary_approved"])
        self.assertEqual(cfg["black_mode"]["decided_by"], "Gary 4 Oct questionnaire: P06 bays 2-10")
        self.assertEqual(cfg["passage"]["expected_cue_count"], 64)

    def test_bad_profiles_refused(self):
        for path, value, code in (("flash_profile.attack_frames", 6.0, "ATTACK_NOT_1_TO_2_FRAMES"),
                                  ("flash_profile.decay_seconds", 1.0, "DECAY_NOT_0_2_TO_0_4_S"),
                                  ("black_mode.glimmer.intensity_cd", 40.0, "GLIMMER_ABOVE_CAP"),
                                  ("black_mode.sequence.flashes_per_burst", [1, 7], "BURST_SIZE_NOT_2_TO_5"),
                                  ("blinkers.mean_gap_s", 3.0, "BLINK_MEAN_GAP_TOO_REGULAR"),
                                  ("black_mode.decided_by", "", "BLACK_APPROVAL_WITHOUT_DECIDED_BY"),
                                  ("black_mode.bays", [2, 3, 5], "BLACK_BAYS_NOT_CONTIGUOUS_ASCENDING"),
                                  ("black_mode.bays", [60, 61, 62, 63, 64, 65], "BLACK_BAYS_OUTSIDE_LAYOUT"),
                                  ("label_prefix", "P04 EVT", "LABEL_PREFIX_WRONG")):
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
            c = config(seed=seed, **{"blinkers.window_cm": [-50000.0, 200.0]})
            times = [x / v for x in E.blink_schedule(c, 1)]
            ok, info = is_aperiodic(times)
            self.assertTrue(ok, (seed, info))
            gaps = [b - a for a, b in zip(times, times[1:])]
            self.assertGreaterEqual(min(gaps), float(cfg["blinkers"]["min_gap_s"]) - 1e-9)

    def test_black_burst_starts_are_aperiodic(self):
        c = config(**{"black_mode.bays": list(range(1, 161))})
        v = E.cm_per_s(c)
        starts = {}
        for event in E.black_schedule(c):
            starts.setdefault(event["burst"], event["camera_cm"] / v)
        ok, info = is_aperiodic(list(starts.values()), bin_s=0.5, min_cv=0.2)
        self.assertTrue(ok, info)

    def test_burst_sizes_in_range(self):
        c = config(**{"black_mode.bays": list(range(1, 161))})
        sizes = {}
        for event in E.black_schedule(c):
            sizes[event["burst"]] = sizes.get(event["burst"], 0) + 1
        whole = list(sizes.values())[:-1]
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
        self.assertLess(b["half_s"], a["half_s"])

    def test_looks_keying_is_not_a_flash(self):  # negative control
        looks = {"strike_on_approach": True, "strike_distance_cm": 650.0, "strike_ramp_cm": 150.0,
                 "ignition_stutter": 0.0, "unstruck_intensity_scale": 0.0, "after_pass": "HOLD",
                 "after_pass_distance_cm": 600.0, "decay_distance_cm": 1500.0}
        self.assertFalse(is_polaroid(flash_shape(looks, self.v, self.fps, self.decay), self.decay))

    def test_slow_ramp_is_not_a_flash(self):  # negative control
        slow = dict(E.phase_a_drama(self.cfg), strike_distance_cm=125.0, strike_ramp_cm=125.0)
        self.assertFalse(is_polaroid(flash_shape(slow, self.v, self.fps, self.decay), self.decay))

    def test_strike_port_matches_cpp_test_values(self):
        d = {"strike_on_approach": True, "strike_distance_cm": 2500.0, "strike_ramp_cm": 250.0,
             "ignition_stutter": 0.0, "unstruck_intensity_scale": 0.0, "after_pass": "HOLD",
             "after_pass_distance_cm": 600.0, "decay_distance_cm": 1500.0}
        lamp = 10000.0
        self.assertEqual(E.eval_drama(d, lamp, lamp - 3000.0), 0.0)
        self.assertAlmostEqual(E.eval_drama(d, lamp, lamp - 2375.0), 0.5, places=3)
        self.assertEqual(E.eval_drama(d, lamp, lamp - 2000.0), 1.0)
        self.assertEqual(E.eval_drama(d, lamp, lamp + 5000.0), 1.0)


class BlackModeTests(unittest.TestCase):
    def run_black(self, cap, mutate=None):
        cfg = E.load_config()
        cues, passages = make_show()
        after, unused, p = apply(cfg, cap, cues, passages)
        if mutate:
            mutate(cfg, after, passages)
        return black_violations(cfg, black_rows(cfg, after, passages)), p

    def test_black_outside_flashes_phase_a(self):
        cfg = E.load_config()
        (bad, lit_inside, glimmer), p = self.run_black(PHASE_A)
        self.assertEqual(bad, [])
        self.assertGreater(lit_inside, 0)
        self.assertLessEqual(glimmer, len(cfg["black_mode"]["bays"]) * cfg["black_mode"]["glimmer"]["max_intensity_cd"])
        self.assertGreater(len(p["schedule"]), 0)

    def test_black_outside_flashes_phase_b(self):
        (bad, lit_inside, _), _ = self.run_black(PHASE_B)
        self.assertEqual(bad, [])
        self.assertGreater(lit_inside, 0)

    def test_negative_existing_light_left_on(self):
        def leave_one_on(cfg, after, passages):
            cue = black_rows(cfg, after, passages)[3]
            light = next(a for a in cue["attachments"] if a["label"].endswith(" Entry Fwd +Y"))
            light["enabled"] = True
        (bad, _, _), _ = self.run_black(PHASE_A, leave_one_on)
        self.assertGreater(len(bad), 0)

    def test_negative_flash_that_holds(self):
        def hold(cfg, after, passages):
            for cue in black_rows(cfg, after, passages):
                for att in cue["attachments"]:
                    if "BLACK F" in att["label"]:
                        att["lighting"]["drama"]["after_pass"] = "HOLD"
                        return
        (bad, _, _), _ = self.run_black(PHASE_A, hold)
        self.assertGreater(len(bad), 0)

    def test_every_enabled_light_in_black_bays_is_disabled(self):
        cfg = E.load_config()
        cues, passages = make_show()
        after, unused, p = apply(cfg, PHASE_A, cues, passages)
        for cue in black_rows(cfg, after, passages):
            on = [a["label"] for a in cue["attachments"] if a["kind"] == "Light" and a["enabled"]
                  and not a["label"].startswith("P06 EVT")]
            self.assertEqual(on, [], cue["label"])
        self.assertEqual(sum(len(t["disable_guids"]) for t in p["targets"]), 9 * 9)


class LayoutGateTests(unittest.TestCase):
    def test_post_interleave_count_resolves_by_ordinal(self):
        cues, passages = make_show()
        p = plan(cues=cues, passages=passages)
        expected = [gid("P06", o) for o in range(2, 11)]
        self.assertEqual([t["cue_guid"] for t in p["targets"]], expected)
        self.assertEqual([t["ordinal"] for t in p["targets"]], list(range(2, 11)))
        self.assertIn("P06 OLD 02 - family", [t["cue_label"] for t in p["targets"]])  # restored slot = bay 4
        self.assertNotIn(gid("decoy"), p["target_cue_guids"])  # label-reusing decoy outside the range

    def test_negative_today_55_cues_refused(self):
        cues, passages = make_show(p06_count=55)
        with self.assertRaisesRegex(E.LightingEventsError, "CUE_COUNT_NOT_POST_INTERLEAVE.*expected=64.*actual=55"):
            plan(cues=cues, passages=passages)

    def test_count_is_configurable(self):
        cues, passages = make_show(p06_count=55)
        cfg = config(**{"passage.expected_cue_count": 55})
        scores = copy.deepcopy(SCORES_CFG)
        scores["passages"]["P06"]["yield_to_events"]["layout_bay_count"] = 55
        p = plan(cfg, cues=cues, passages=passages, scores=scores)
        self.assertEqual(p["passage"]["bay_count"], 55)

    def test_negative_non_wingpair_row_is_not_a_bay(self):
        # A SEQUENCE row inside the range does not shift ordinals or the count...
        cues, passages = make_show(sting_in_range=True)
        p = plan(cues=cues, passages=passages)
        self.assertEqual([t["cue_guid"] for t in p["targets"]], [gid("P06", o) for o in range(2, 11)])
        # ... but the same row typed as a WingPair breaks the count gate.
        for cue in cues:
            if cue["guid"] == gid("P06-sting"):
                cue["type"] = "WING_PAIR"
        with self.assertRaisesRegex(E.LightingEventsError, "CUE_COUNT_NOT_POST_INTERLEAVE"):
            plan(cues=cues, passages=passages)

    def test_negative_label_drift_refused(self):
        cues, passages = make_show()
        next(c for c in cues if c["guid"] == gid("P06", 5))["label"] = "Passage 6 mystery"
        with self.assertRaisesRegex(E.LightingEventsError, "CUE_LABEL_DRIFT"):
            plan(cues=cues, passages=passages)


class ScoresInterlockTests(unittest.TestCase):
    def test_real_scores_config_yields_exactly_the_black_bays(self):
        p = plan()
        self.assertTrue(p["ownership"]["scored"])
        self.assertEqual(p["ownership"]["yield"]["bays"], [2, 10])

    def test_negative_scores_without_yield_refused(self):
        scores = copy.deepcopy(SCORES_CFG)
        del scores["passages"]["P06"]["yield_to_events"]
        with self.assertRaisesRegex(E.LightingEventsError, "SCORES_DO_NOT_YIELD_BLACK_BAYS"):
            plan(scores=scores)

    def test_negative_yield_range_short_refused(self):
        scores = copy.deepcopy(SCORES_CFG)
        scores["passages"]["P06"]["yield_to_events"]["bays"] = [2, 9]
        with self.assertRaisesRegex(E.LightingEventsError, "SCORES_DO_NOT_YIELD_BLACK_BAYS"):
            plan(scores=scores)

    def test_negative_yield_for_other_layout_refused(self):
        scores = copy.deepcopy(SCORES_CFG)
        scores["passages"]["P06"]["yield_to_events"]["layout_bay_count"] = 55
        with self.assertRaisesRegex(E.LightingEventsError, "SCORES_YIELD_LAYOUT_MISMATCH"):
            plan(scores=scores)

    def test_negative_active_score_on_a_black_bay_refused(self):
        record = {"status": "saved_readback_verified",
                  "plan": {"target_cue_guids": [gid("P06", 1), gid("P06", 5), gid("P06", 11)]}}
        with self.assertRaisesRegex(E.LightingEventsError, "BLACK_BAYS_CARRY_ACTIVE_SCORE"):
            plan(record=record)

    def test_reverted_or_disjoint_score_record_passes(self):
        reverted = {"status": "reverted", "plan": {"target_cue_guids": [gid("P06", 5)]}}
        self.assertEqual(plan(record=reverted)["ownership"]["record_overlap"], [])
        disjoint = {"status": "saved_readback_verified",
                    "plan": {"target_cue_guids": [gid("P06", o) for o in [1] + list(range(11, 65))]}}
        self.assertEqual(plan(record=disjoint)["ownership"]["record_overlap"], [])

    def test_cross_tool_scores_at_64_never_touch_black_bays(self):
        """End to end with the REAL scores tool: rescore P06 to 64 (as the
        rescore would), plan both tools on one Show, apply events then scores,
        and check disjoint targets, both budgets, and both exact reverts."""
        import lighting_scores_apply as L
        tool = L.load_p04_tool()
        scores = copy.deepcopy(SCORES_CFG)
        p6 = scores["passages"]["P06"]
        p6["expected_bay_count"] = 64
        p6["segments"][1]["bays"] = [13, 63]
        p6["segments"][2]["bays"] = [64, 64]
        p6["max_consecutive_lit_exempt"] = [[13, 64]]
        p6["monotone_dark_segment"] = [13, 64]
        # The rescore must also accept W&T's restored-cue labels (p6_workflow.py:387);
        # today's guard '^P06 Wing \d{3}$' refuses them (CUE_LABEL_DRIFT), see below.
        today_guard = p6["cue_label_drift_guard"]
        p6["cue_label_drift_guard"] = E.load_config()["passage"]["cue_label_drift_guard"]
        looks = L.resolve_looks(scores, L.load_base_looks(scores)[0])
        cues, passages = make_show()
        cfg = E.load_config()
        after_events, events_record, events_plan = apply(cfg, PHASE_A, cues, passages, scores)
        score_plan = L.build_score_plan(tool, scores, looks, "P06", passages, after_events)
        self.assertEqual(set(score_plan["target_cue_guids"]) & set(events_plan["target_cue_guids"]), set())
        self.assertEqual([s["bay"] for s in score_plan["skipped"]], list(range(2, 11)))
        after_both, score_record = L.apply_plain_state(score_plan, after_events)
        p06 = [gid("P06", o) for o in range(1, 65)]
        casters = L.passage_casters(tool, after_both, p06)
        self.assertLessEqual(casters, L.passage_casters(tool, cues, p06))
        # Reverse-order reverts are exact.
        back = E.revert_plain_state(L.revert_plain_state(after_both, score_record), events_record)
        self.assertEqual(L._canonical(back), L._canonical(cues))
        # Negative control: the same scores WITHOUT the yield target the black bays.
        del p6["yield_to_events"]
        naive = L.build_score_plan(tool, scores, looks, "P06", passages, cues)
        self.assertTrue(set(events_plan["target_cue_guids"]) <= set(naive["target_cue_guids"]))
        # Finding: today's scores drift guard refuses the 64-cue labels.
        p6["cue_label_drift_guard"] = today_guard
        with self.assertRaisesRegex(L.LightingScoresError, "CUE_LABEL_DRIFT"):
            L.build_score_plan(tool, scores, looks, "P06", passages, cues)


class ScopeTests(unittest.TestCase):
    def test_guid_keyed_apply_and_exact_revert(self):
        cues, passages = make_show()
        after, record, p = apply(cues=cues, passages=passages)
        self.assertEqual(E.outside_hash(cues, p["target_cue_guids"]), E.outside_hash(after, p["target_cue_guids"]))
        restored = E.revert_plain_state(list(reversed(after)), record)
        self.assertEqual(sorted(json.dumps(c, sort_keys=True) for c in restored),
                         sorted(json.dumps(c, sort_keys=True) for c in cues))

    def test_outside_hash_detects_change(self):  # negative control
        cues, passages = make_show()
        after, unused, p = apply(cues=cues, passages=passages)
        next(c for c in after if c["guid"] == gid("P06", 11))["attachments"][0]["enabled"] = False  # bay 11
        self.assertNotEqual(E.outside_hash(cues, p["target_cue_guids"]), E.outside_hash(after, p["target_cue_guids"]))

    def test_record_names_only_black_bays(self):
        cues, passages = make_show()
        p = plan(cues=cues, passages=passages)
        text = json.dumps(p).upper()
        others = [gid("P06", o) for o in [1] + list(range(11, 65))]
        self.assertEqual([g for g in others if g in text], [])
        self.assertTrue(all(gid("P06", o) in text for o in range(2, 11)))
        # Negative control: the full bay list WOULD name the other bays.
        unused, rows = E.resolve_passage_bays(passages, cues, "Passage 6")
        full = json.dumps([r["cue_guid"] for r in rows]).upper()
        self.assertTrue(all(g in full for g in others))

    def test_already_present_refused(self):
        cues, passages = make_show()
        after, unused, unused2 = apply(cues=cues, passages=passages)
        with self.assertRaisesRegex(E.LightingEventsError, "EVENTS_ALREADY_PRESENT"):
            plan(cues=after, passages=passages)

    def test_phase_b_rows_deferred_without_engine(self):
        p = plan()
        self.assertTrue(all(r["phase"] == "A" for t in p["targets"] for r in t["fixtures"]))
        self.assertEqual(p["deferred"], [])  # blinkers disabled since the P06 retarget
        cfg = config(**{"blinkers.enabled": True})
        self.assertEqual(len(plan(cfg)["deferred"]), 2)
        self.assertEqual(plan(cfg, cap=PHASE_B)["deferred"], [])


class ShadowBudgetTests(unittest.TestCase):
    def test_p06_budget_holds_on_the_census_model(self):
        p = plan()
        s = p["shadow"]
        self.assertLessEqual(s["passage_after"], s["passage_before"])
        self.assertEqual(s["removed"], 9 * 2)  # Entry Top + Entry Fwd +Y in each black bay
        self.assertGreater(s["added"], 0)
        # Budget is P06's own: P04's looks casters are not in it.
        self.assertEqual(s["passage_before"], 64 * 2 + 2)  # + Wing 044 Blink Spot + Wing 055 FX candle

    def test_negative_no_casters_to_free_refused(self):
        cues, passages = make_show(casters=False)
        with self.assertRaisesRegex(E.LightingEventsError, "SHADOW_BUDGET_EXCEEDED"):
            plan(cues=cues, passages=passages)

    def test_negative_all_sources_casting_with_many_bursts_refused(self):
        cfg = E.load_config()
        for source in cfg["sources"].values():
            source["cast_shadows"] = True
        cfg["black_mode"]["sequence"]["dark_gap_s"] = [3.0, 3.0]
        cfg["black_mode"]["sequence"]["intra_gap_s"] = [0.08, 0.1]
        cfg["black_mode"]["sequence"]["first_gap_s"] = [0.1, 0.1]
        cfg["black_mode"]["sequence"]["flashes_per_burst"] = [5, 5]  # fixture forces the excess
        with self.assertRaisesRegex(E.LightingEventsError, "SHADOW_BUDGET_EXCEEDED"):
            plan(cfg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
