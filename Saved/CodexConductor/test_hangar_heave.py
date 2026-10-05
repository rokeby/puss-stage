"""Offline harness for hangar_heave.py (system Python, no Unreal). Every gate has a failing control.

Synthetic inputs, cited:
  S1 root pitch start -5.8739 s, -90           Saved/CodexStructure/hangar_retime_record.json scenes.1.after_keys (1 Oct)
  S1 root land 4.1333 s, 0                     atf_hangar_timing_apply_record.json readback S1 land_seconds (2 Oct)
  S1 lattice 0 / 8.6333 / 12.6333 s, 2800/2800/1200   same readback (lattice_start/end), values hangar_retime_record
  S5 root -3.5667 -> 25.3 s                    Saved/CodexStructure/arrivals_record.json S5 keys_new + ATF land 25.3
  tick 24000/s, display 30 fps                 [inf] not read from the asset here; the live DRY reads both
  Cubic AUTO tangents in the fake = neighbour finite difference [inf]: UE's AutoSetTangents body is private (5.8 has no
  private .cpp); the fake only needs to move AUTO tangents when neighbours change so the pin path is exercised.
Run: python test_hangar_heave.py  -> HANGAR_HEAVE_HARNESS|tests=..|checks=..|failed=..  and writes hangar_heave_preview.png
"""
import copy
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("hangar_heave", os.path.join(HERE, "hangar_heave.py"))
hh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hh)
assert hh.unreal is None, "harness must run without Unreal"

CHECKS = {"n": 0, "failed": []}
TESTS = []
TICK, FPS = 24000.0, 30.0


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(failures, prefix):
    return any(prefix in f for f in failures)


# ------------------------------------------------------------------------------------------------------ fake channel

class FakeChannel(object):
    """Stands in for MovieSceneScriptingDoubleChannel. lie_interp: set_fields ignores interp (a lying setter)."""

    def __init__(self, keys, lie_interp=False, auto_any=False):
        self.k = {int(k["tick"]): dict(k) for k in keys}
        self.lie_interp = lie_interp
        self.auto_any = auto_any          # recompute AUTO tangents whatever the interp (worst case for the pin path)
        self._auto()

    def _auto(self):
        ticks = sorted(self.k)
        for i, t in enumerate(ticks):
            key = self.k[t]
            if (key["interp"] != "RCIM_CUBIC" and not self.auto_any) or key["tangent_mode"] not in hh.AUTO_MODES:
                continue
            if 0 < i < len(ticks) - 1:
                a, b = self.k[ticks[i - 1]], self.k[ticks[i + 1]]
                slope = (b["value"] - a["value"]) / float(ticks[i + 1] - ticks[i - 1])
            else:
                slope = 0.0
            key["arrive"] = key["leave"] = float(slope)

    def read(self):
        return [copy.deepcopy(self.k[t]) for t in sorted(self.k)]

    def remove_ticks(self, ticks):
        for t in list(ticks):
            self.k.pop(int(t), None)
        self._auto()

    def add(self, tick, value):
        self.k[int(tick)] = {"tick": int(tick), "sub": 0.0, "value": float(value), "interp": "RCIM_LINEAR",
                             "tangent_mode": "RCTM_AUTO", "arrive": 0.0, "leave": 0.0,
                             "weight_mode": "RCTWM_WEIGHTED_NONE", "arrive_w": 0.0, "leave_w": 0.0}
        self._auto()

    def set_fields(self, tick, fields):
        key = self.k[int(tick)]
        for f, v in fields.items():
            if f == "interp" and self.lie_interp:
                continue
            key[f] = v


def key(t_s, v, interp="RCIM_CUBIC", mode="RCTM_AUTO"):
    return {"tick": int(round(t_s * TICK)), "sub": 0.0, "value": float(v), "interp": interp, "tangent_mode": mode,
            "arrive": 0.0, "leave": 0.0, "weight_mode": "RCTWM_WEIGHTED_NONE", "arrive_w": 0.0, "leave_w": 0.0}


def settled(keys):
    """Keys as the editor would hold them (AUTO tangents computed)."""
    return FakeChannel(keys).read()


ROOT_S1 = settled([key(-5.8739, -90.0), key(4.1333333, 0.0)])
LATTICE_S1 = settled([key(0.0, 2800.0), key(8.6333333, 2800.0), key(12.6333333, 1200.0)])
ROOF_S1 = settled([key(0.0, -90.0), key(4.1333333, -90.0), key(8.6333333, 0.0)])
ROOT_S5 = settled([key(-3.5667, -90.0), key(25.3, 0.0)])
P = hh.merged_params({})


def plan(name, keys, prof=None):
    return hh.plan_channel(name, keys, prof or P[P["profiles"][name]], TICK, FPS)


# ------------------------------------------------------------------------------------------------------ profile shape

@test
def t_default_shapes_pass():
    for label in ("heave", "drop"):
        f = hh.check_shape(lambda u, p=P[label]: hh.profile(u, p), P[label])
        check(f == [], "default %s shape fails: %r" % (label, f))


@test
def t_shape_controls_fail():
    heave = P["heave"]
    f = hh.check_shape(hh.smoothstep, heave)                    # the current smooth curve must FAIL the contract
    for want in ("DIP", "HITCHES", "NO_OVERSHOOT", "REBOUNDS"):
        check(has(f, want), "smoothstep control should fail %s: %r" % (want, f))
    cases = [({"overshoot": 0.2}, "OVERSHOOT_BOUND"), ({"heaves": 1, "heave_weights": [1.0]}, "HEAVE_COUNT"),
             ({"hitch_creep": 0.6}, "HITCHES"), ({"fall_power": 0.5}, "NO_MOMENTUM_SHIFT"),
             ({"dip": 0.0}, "DIP"), ({"dip": 0.05}, "DIP"), ({"overshoot": 0.0}, "NO_OVERSHOOT"),
             ({"tip_time": 0.3, "heave_end": 0.25}, "TIP_NOT_MIDWAY")]
    for change, want in cases:
        p = dict(heave, **change)
        f = hh.check_shape(lambda u, p=p: hh.profile(u, p), p)
        check(has(f, want), "control %r should fail %s: %r" % (change, want, f))
    # a landing frame that is not exactly 1 must fail
    p = dict(heave)
    f = hh.check_shape(lambda u: hh.profile(u, p) + (0.01 if abs(u - p["land_time"]) < 1e-12 else 0.0), p)
    check(has(f, "LANDING_FRAME"), "perturbed landing frame should fail: %r" % f)


@test
def t_monotone_and_hitches_measured():
    p = P["heave"]
    us = [i / 4000.0 for i in range(4001)]
    ys = [hh.profile(u, p) for u in us]
    seg = [y for u, y in zip(us, ys) if p["dip_end"] <= u <= p["land_time"]]
    check(all(b >= a - 1e-12 for a, b in zip(seg, seg[1:])), "heave not monotone between lift and landing")
    check(min(ys) >= -0.02 - 1e-12 and min(ys) <= -0.01 + 1e-12, "dip %.4f outside -1..-2%%" % min(ys))
    check(max(ys) <= 1.0 + p["overshoot"] + 1e-9, "overshoot bound %.5f" % max(ys))
    # control: non-monotone injection is caught
    bad = dict(p)
    f = hh.check_shape(lambda u: hh.profile(u, bad) - (0.02 if 0.5 < u < 0.52 else 0.0), bad)
    check(has(f, "NOT_MONOTONE"), "injected backslide should fail NOT_MONOTONE: %r" % f)


# ------------------------------------------------------------------------------------------------------ planning

@test
def t_landing_frame_exact():
    for name, keys in (("root_pitch", ROOT_S1), ("lattice_fly_z", LATTICE_S1), ("root_pitch", ROOT_S5)):
        pl = plan(name, keys)
        hit = [d for d in pl["dense"] if d["tick"] == pl["thud_tick"]]
        check(len(hit) == 1 and hit[0]["value"] == pl["v1"], "%s: THUD key not exactly at v1: %r" % (name, hit))
        check(pl["thud_tick"] == hh.frame_tick(pl["thud_frame"], TICK, FPS), "%s: THUD_FRAME/tick mismatch" % name)
        check(pl["t0"] < pl["thud_tick"] < pl["t1"], "%s: THUD outside the window" % name)
        check(abs(pl["land_time_eff"] - P[P["profiles"][name]]["land_time"]) < 1.0 / FPS / ((pl["t1"] - pl["t0"]) / TICK),
              "%s: THUD snapped more than a frame" % name)
        ticks = [d["tick"] for d in pl["dense"]]
        check(ticks == sorted(set(ticks)) and all(pl["t0"] < t < pl["t1"] for t in ticks),
              "%s: dense keys not strictly inside the window" % name)
        check(all(t % int(TICK / FPS) == 0 for t in ticks), "%s: dense keys off display frames" % name)


@test
def t_window_detection():
    check(plan("lattice_fly_z", LATTICE_S1)["i0"] == 1, "lattice window must start at the hold's last key")
    check(plan("root_pitch", ROOT_S1)["i0"] == 0, "root window must start at the first key")
    try:
        hh.window_of(settled([key(0, 5.0), key(1, 5.0)]))
        check(False, "a flat channel must refuse NO_MOTION_WINDOW")
    except hh.PlanError as exc:
        check("NO_MOTION_WINDOW" in str(exc), "wrong refusal %s" % exc)


@test
def t_endpoint_preservation():
    for name, keys in (("root_pitch", ROOT_S1), ("lattice_fly_z", LATTICE_S1)):
        pl = plan(name, keys)
        want = hh.expected_after(keys, pl)
        check(hh.endpoint_gate(keys, want, pl) == [], "%s: model fails its own endpoint gate" % name)
        naive = copy.deepcopy(want)                           # control 1: an endpoint value nudged
        naive[pl["i0"]]["value"] += 1e-7
        check(has(hh.endpoint_gate(keys, naive, pl), "ENDPOINT_VALUE"), "%s: nudged endpoint not caught" % name)
        moved = [k for k in want if k["tick"] != pl["t1"]]   # control 2: last key moved one frame earlier
        moved.append(dict(want[-1], tick=pl["t1"] - int(TICK / FPS)))
        check(has(hh.endpoint_gate(keys, moved, pl), "ENDPOINT_MOVED"), "%s: moved end key not caught" % name)
    # control 3: a naive whole-range rewrite of the lattice (from its FIRST key) destroys the hold key
    naive_plan = dict(plan("lattice_fly_z", LATTICE_S1), i0=0)
    naive_after = [LATTICE_S1[0]] + [{"tick": t, "sub": 0.0, "value": 2800.0 - 1600.0 * hh.profile(t / LATTICE_S1[-1]["tick"], P["drop"]),
                                      "interp": "RCIM_LINEAR"} for t in range(800, LATTICE_S1[-1]["tick"], 800)] + [LATTICE_S1[-1]]
    check(has(hh.endpoint_gate(LATTICE_S1, naive_after, plan("lattice_fly_z", LATTICE_S1)), "ENDPOINT"),
          "naive whole-range lattice rewrite must fail the endpoint gate")
    check(naive_plan["i0"] == 0, "control setup")


# ------------------------------------------------------------------------------------------------------ write + revert

@test
def t_write_readback_and_pins():
    for name, keys in (("root_pitch", ROOT_S1), ("lattice_fly_z", LATTICE_S1), ("roof_pitch", ROOF_S1),
                       ("root_pitch", ROOT_S5)):
        pl = plan(name, keys)
        for auto_any in (False, True):
            ch = FakeChannel(keys, auto_any=auto_any)
            live, pins, fails = hh.write_channel(ch, keys, pl)
            check(fails == [], "%s write failures %r" % (name, fails[:4]))
            check(len(live) == len(keys) - len(pl["interior"]) + len(pl["dense"]), "%s key count" % name)
            if name in ("lattice_fly_z", "roof_pitch"):
                want_pins = 1 if auto_any else 0
                check(len(pins) == want_pins and all(p[0] == pl["t0"] for p in pins),
                      "%s auto_any=%s: pins %r, want %d at the hold end" % (name, auto_any, pins, want_pins))
                k1 = [k for k in live if k["tick"] == pl["t0"]][0]
                check(abs(k1["arrive"] - keys[pl["i0"]]["arrive"]) <= hh.TANGENT_TOL, "%s hold segment tangent changed" % name)
            if auto_any:
                errs = hh.restore_channel(ch, keys)
                check(errs == [], "%s: revert after a pin not exact %r" % (name, errs[:3]))
    # control: without the pin step the recomputed hold tangent IS caught by the read-back gate
    pl = plan("lattice_fly_z", LATTICE_S1)
    ch = FakeChannel(LATTICE_S1, auto_any=True)
    ch.remove_ticks(set())
    ch.set_fields(pl["t0"], {"interp": "RCIM_LINEAR"})
    for dd in pl["dense"]:
        ch.add(dd["tick"], dd["value"])
    check(has(hh.compare_keys(ch.read(), hh.expected_after(LATTICE_S1, pl)), "KEY_ARRIVE"),
          "unpinned hold tangent drift not caught")
    # control: a lying interp setter is caught by the read-back
    ch = FakeChannel(ROOT_S1, lie_interp=True)
    _live, _p, fails = hh.write_channel(ch, ROOT_S1, plan("root_pitch", ROOT_S1))
    check(has(fails, "KEY_INTERP"), "lying setter not caught: %r" % fails[:3])
    # control: readback with a wrong dense value fails
    pl = plan("root_pitch", ROOT_S1)
    want = hh.expected_after(ROOT_S1, pl)
    bad = copy.deepcopy(want)
    bad[5]["value"] += 0.01
    check(has(hh.compare_keys(bad, want), "KEY_VALUE"), "dense value drift not caught")


@test
def t_revert_exact_and_drift():
    for name, keys in (("root_pitch", ROOT_S1), ("lattice_fly_z", LATTICE_S1), ("roof_pitch", ROOF_S1)):
        pl = plan(name, keys)
        ch = FakeChannel(keys)
        live, pins, _f = hh.write_channel(ch, keys, pl)
        record = {"channels": {name: {"keys_before": keys, "keys_after": live}}}
        check(hh.drift({name: ch.read()}, record) == [], "%s: drift on an untouched applied channel" % name)
        touched = FakeChannel(live)                                   # control: someone edited a key after APPLY
        touched.set_fields(pl["dense"][10]["tick"], {"value": live[11]["value"] + 0.5})
        check(has(hh.drift({name: touched.read()}, record), "KEY_VALUE"), "%s: post-apply edit not seen as drift" % name)
        check(has(hh.drift({}, record), "CHANNEL_GONE"), "%s: missing channel not seen as drift" % name)
        errs = hh.restore_channel(ch, keys)
        check(errs == [], "%s: revert not exact %r" % (name, errs[:4]))
        check(hh.compare_keys(ch.read(), keys, check_all_tangents=True) == [], "%s: revert readback differs" % name)
    # control: exactness check must see a wrong restore (record perturbed after the fact)
    pl = plan("lattice_fly_z", LATTICE_S1)
    ch = FakeChannel(LATTICE_S1)
    hh.write_channel(ch, LATTICE_S1, pl)
    hh.restore_channel(ch, LATTICE_S1)
    wrong = copy.deepcopy(LATTICE_S1)
    wrong[1]["tangent_mode"] = "RCTM_USER"
    check(has(hh.compare_keys(ch.read(), wrong, check_all_tangents=True), "KEY_TANGENT_MODE"),
          "revert exactness misses a tangent-mode difference")
    # control: a fake that lies about interp cannot be reverted exactly
    ch = FakeChannel(ROOT_S1)
    hh.write_channel(ch, ROOT_S1, plan("root_pitch", ROOT_S1))
    ch.lie_interp = True
    check(has(hh.restore_channel(ch, ROOT_S1), "KEY_INTERP"), "lying revert setter not caught")


# ------------------------------------------------------------------------------------------------------ record

@test
def t_record_round_trip():
    pls = {"root_pitch": plan("root_pitch", ROOT_S1), "lattice_fly_z": plan("lattice_fly_z", LATTICE_S1)}
    chans = {"root_pitch": ROOT_S1, "lattice_fly_z": LATTICE_S1}
    rec = hh.new_record(1, "T", P, {"tick_rate": TICK, "fps": FPS}, chans, pls, "harness", "nowhere")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rec.json")
        hh.write_record_exclusive(path, rec)
        back = hh.load_record(path)
        for name in chans:
            check(hh.compare_keys(back["channels"][name]["keys_before"], chans[name], check_all_tangents=True) == [],
                  "%s keys do not round-trip" % name)
            check(all(set(hh.KEY_FIELDS) <= set(k) for k in back["channels"][name]["keys_before"]),
                  "%s record lacks key fields" % name)
        check(back["params_digest"] == hh.params_digest(P), "params digest round trip")
        try:
            hh.write_record_exclusive(path, rec)                       # control: exclusive create refuses
            check(False, "second exclusive record write must refuse")
        except FileExistsError:
            check(True, "")
        back["channels"]["root_pitch"]["keys_before"][0]["value"] = -89.0   # control: a corrupt record is detected
        check(has(hh.compare_keys(back["channels"]["root_pitch"]["keys_before"], ROOT_S1), "KEY_VALUE"),
              "corrupt record not detected")


# ------------------------------------------------------------------------------------------------------ refusals

@test
def t_refusals():
    base = {"mode": "APPLY", "scene": 1, "confirm": "APPLY S1", "pie": False, "sequencer_open": False,
            "census": {"content": [], "maps": []}, "record_exists": False, "record_applied": False,
            "decided_by": "Gary 5 Oct"}
    check(hh.live_gates(base) == [], "clean state refused: %r" % hh.live_gates(base))
    for change, want in (({"pie": True}, "PIE_OR_SIE_ACTIVE"), ({"sequencer_open": True}, "SEQUENCER_IS_OPEN"),
                         ({"census": {"content": ["/Game/X"], "maps": []}}, "DIRTY_CENSUS"),
                         ({"census": {"content": [], "maps": [hh.EXPECTED_WORLD]}}, "DIRTY_CENSUS"),
                         ({"record_exists": True}, "RECORD_EXISTS"), ({"confirm": "APPLY S2"}, "CONFIRM_MISMATCH"),
                         ({"decided_by": ""}, "NOT_DECIDED"), ({"scene": 7, "confirm": "APPLY S7"}, "SCENE_OUT_OF_SCOPE"),
                         ({"mode": "REVERT", "confirm": "REVERT S1"}, "NO_APPLIED_RECORD"),
                         ({"mode": "NUKE", "confirm": "NUKE S1"}, "MODE_INVALID")):
        check(has(hh.live_gates(dict(base, **change)), want), "%r should refuse %s" % (change, want))
    check(hh.live_gates(dict(base, mode="DRY", confirm="DRY S1", decided_by="")) == [], "DRY needs no decided_by")
    check(hh.live_gates(dict(base, mode="REVERT", confirm="REVERT S1", record_exists=True, record_applied=True)) == [],
          "REVERT with an applied record refused")
    r = {"playback": [0, 930], "section:root_pitch": [False, None, False, None]}
    check(hh.range_gate(r, copy.deepcopy(r)) == [], "unchanged range refused")
    check(has(hh.range_gate(r, dict(r, playback=[0, 931])), "RANGE_CHANGED"), "playback change not refused")
    check(has(hh.range_gate(r, dict(r, **{"section:root_pitch": [True, -177, False, None]})), "RANGE_CHANGED"),
          "section range change not refused")


@test
def t_params_and_scene_plan():
    for bad, want in (({"bogus": 1}, "UNKNOWN_PARAM"), ({"heave": {"wobble": 1}}, "UNKNOWN_PARAM"),
                      ({"channels": ["floor"]}, "UNKNOWN_CHANNEL"), ({"marker_label": "GO thud"}, "MARKER_NOT_GO_LESS"),
                      ({"map_dirty_policy": "clear"}, "map_dirty_policy")):
        try:
            hh.merged_params(bad)
            check(False, "%r should refuse" % bad)
        except hh.PlanError as exc:
            check(want in str(exc), "%r refused with %s" % (bad, exc))
    p = hh.merged_params({"channels": ["root_pitch", "lattice_fly_z", "roof_pitch"]})
    plans, ref, warn = hh.plan_scene({"root_pitch": ROOT_S1, "lattice_fly_z": LATTICE_S1}, p, TICK, FPS)  # S6: no roof
    check(ref == [] and has(warn, "CHANNEL_ABSENT: roof_pitch"), "S6 roofless should warn, not refuse: %r" % ref)
    check(has(warn, "ARRIVAL_TIMING_LOCK") and has(warn, "DRAPE_TWO_KEY_GATE") and has(warn, "DIP_BELOW_REST"),
          "consequence warnings missing")
    _p, ref, _w = hh.plan_scene({"lattice_fly_z": LATTICE_S1}, P, TICK, FPS)
    check(has(ref, "CHANNEL_MISSING: root_pitch"), "missing root must refuse")
    bad = hh.merged_params({"heave": {"overshoot": 0.2}})
    _p, ref, _w = hh.plan_scene({"root_pitch": ROOT_S1, "lattice_fly_z": LATTICE_S1}, bad, TICK, FPS)
    check(has(ref, "SHAPE_root_pitch: OVERSHOOT_BOUND"), "out-of-bound params must refuse at plan time")


# ------------------------------------------------------------------------------------------------------ preview

def write_preview(path):
    from PIL import Image, ImageDraw, ImageFont
    W, H, S = 1400, 900, 1
    img = Image.new("RGB", (W, H), "#fcfcfb")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
        small = ImageFont.truetype("arial.ttf", 14)
        big = ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = small = big = ImageFont.load_default()
    ink, ink2, grid = "#0b0b0b", "#52514e", "#e4e3df"
    old_c, new_c = "#2a78d6", "#eb6834"
    d.text((40, 18), "Hangar heave: current smooth curve vs heave (S1, defaults)", fill=ink, font=big)
    d.text((40, 50), "Blue = current (two AUTO cubic keys, drawn as smoothstep [inferred]).  Orange = heave, one linear key "
                     "per frame.  Start and end keys are unchanged.", fill=ink2, font=small)
    panels = [("Hangar rise: S1 Hangar Root pitch (deg)", ROOT_S1, "root_pitch", 95),
              ("Ceiling rig drop: S1 Hangar Lattice Fly Z (cm)", LATTICE_S1, "lattice_fly_z", 505)]
    for title, keys, name, top in panels:
        pl = plan(name, keys)
        t0, t1 = pl["t0"] / TICK, pl["t1"] / TICK
        pad = 0.6
        xa, xb = t0 - pad, t1 + pad
        vals = [pl["v0"], pl["v1"]] + [dd["value"] for dd in pl["dense"]]
        lo, hi = min(vals), max(vals)
        m = 0.06 * (hi - lo)
        lo, hi = lo - m, hi + m
        L, R, T, B = 110, W - 60, top + 40, top + 340
        X = lambda t: L + (t - xa) / (xb - xa) * (R - L)
        Y = lambda v: B - (v - lo) / (hi - lo) * (B - T)
        d.text((L, top + 8), title, fill=ink, font=font)
        step = 10.0 if hi - lo < 200 else 400.0
        v = step * int(lo / step)
        while v <= hi:
            if v >= lo:
                d.line([(L, Y(v)), (R, Y(v))], fill=grid, width=1)
                d.text((L - 60, Y(v) - 8), "%g" % v, fill=ink2, font=small)
            v += step
        t = float(int(xa))
        while t <= xb:
            if t >= xa:
                d.line([(X(t), B), (X(t), B + 5)], fill=ink2, width=1)
                d.text((X(t) - 8, B + 8), "%g" % t, fill=ink2, font=small)
            t += 1.0
        d.text((R - 210, B + 28), "rise-sequence time (s)", fill=ink2, font=small)
        old = [(xa, pl["v0"])] + [(t0 + (t1 - t0) * i / 400.0, pl["v0"] + (pl["v1"] - pl["v0"]) * hh.smoothstep(i / 400.0))
                                  for i in range(401)] + [(xb, pl["v1"])]
        new = [(xa, pl["v0"]), (t0, pl["v0"])] + [(dd["tick"] / TICK, dd["value"]) for dd in pl["dense"]] + \
              [(t1, pl["v1"]), (xb, pl["v1"])]
        d.line([(X(a), Y(b)) for a, b in old], fill=old_c, width=3)
        d.line([(X(a), Y(b)) for a, b in new], fill=new_c, width=3)
        for kk in keys:
            if xa <= kk["tick"] / TICK <= xb:
                x, y = X(kk["tick"] / TICK), Y(kk["value"])
                d.ellipse([x - 5, y - 5, x + 5, y + 5], outline=ink, width=2)
        tx = X(pl["thud_s"])
        d.line([(tx, T), (tx, B)], fill=ink2, width=1)
        d.text((tx + 6, T + 2), "THUD  frame %d  (%.2f s)" % (pl["thud_frame"], pl["thud_s"]), fill=ink, font=small)
        d.line([(R - 300, top + 18), (R - 270, top + 18)], fill=old_c, width=3)
        d.text((R - 262, top + 9), "current", fill=ink, font=small)
        d.line([(R - 190, top + 18), (R - 160, top + 18)], fill=new_c, width=3)
        d.text((R - 152, top + 9), "heave", fill=ink, font=small)
    img.save(path)
    return path


def main():
    for fn in TESTS:
        before = len(CHECKS["failed"])
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
        if len(CHECKS["failed"]) > before:
            print("FAIL", fn.__name__)
    for f in CHECKS["failed"]:
        print("  -", f)
    try:
        out = write_preview(os.path.join(HERE, "hangar_heave_preview.png"))
        print("PREVIEW", out)
    except Exception as exc:  # noqa: BLE001
        print("PREVIEW_FAILED", repr(exc))
    print("HANGAR_HEAVE_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
