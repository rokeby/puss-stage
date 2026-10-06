"""Offline harness for backcloth_lead_fit.py (system Python, no Unreal). Every refusal has a failing control.

Fixture numbers, each from a record:
  section [-5.9072, 4.1261) s, offset 23200 ticks @ 24000     Saved/CodexStructure/p04_backcloth_section_record.json
  release in cache 1.0 s; hold AABB y[-0.394, 0.383] x+-5 m    DropBake/final11_backcloth_p04_a06.json checkpoint 479
  rise start -5.8739 s                                          Saved/CodexStructure/hangar_retime_record.json W0
  cloth line x 10450, stop x 10668.5 (= 42.674 s x 250 cm/s)    p04_backcloth_section_apply.py:45; slow-walk record
  today: tail 418.47 cm over 169447 ticks (7.0603 s)            passage_slow_walk_P04_apply_SW-P04-APPLY-20261002-A.json
  after the retime: walk 10668.5 cm over 50.4 - 0.5 s           passage_retime_to_music.py settle_compensation (inf)
Run: python test_backcloth_lead_fit.py -> BACKCLOTH_LEAD_FIT_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("blf", os.path.join(HERE, "backcloth_lead_fit.py"))
blf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blf)
assert blf.unreal is None, "harness must run without Unreal"

CHECKS = {"n": 0, "failed": []}
TESTS = []
TICK = 24000.0
STOP_X, CLOTH_X, Y0 = 10668.5, 10450.0, 240000.0


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(rows, prefix):
    return any(r.startswith(prefix) for r in rows)


def remaining(t, v, w):
    """Distance to the stop at time t <= 0 for speed v easing to 0 over the last w s (smoothstep, integrates to v w/2)."""
    if w <= 0.0:
        return -t * v
    if t <= -w:
        return v * w / 2.0 + v * (-w - t)
    u = (t + w) / w
    return v * w * ((1.0 - u) - (0.5 - u ** 3 + u ** 4 / 2.0))


def samples(v, w=1.0, span=24.0, step=0.05, yaw=0.0, lateral=0.0, origin=(0.0, 0.0)):
    out = []
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    n = int(round(span / step))
    for i in range(n + 1):
        t = -span + i * step
        lx, ly = STOP_X - remaining(t, v, w), Y0 + lateral
        x, y = origin[0] + lx * c - (ly - Y0) * s, origin[1] + Y0 + lx * s + (ly - Y0) * c
        out.append([round(t, 4), {"loc": [x, y, 150.0]}])
    return out


def inputs(v, w=1.0, yaw=0.0, lateral=0.0, passage_len=180.0, cloth_x=CLOTH_X):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return {
        "section": {"start_s": -5.9072, "end_s": 4.1261, "offset_ticks": 23200, "offset_s": 23200 / TICK,
                    "end_offset_ticks": 0, "tick_rate": TICK, "completion": "KEEP_STATE"},
        "cache": {"release_in_cache_s": 1.0, "duration_s": 11.0, "held_sample": 479,
                  "hang_aabb_cm": {"x": [-39.4, 38.3], "y": [-500.0, 500.0], "z": [20.0, 1220.0]}},
        "rise_sub": {"section_start_s": 0.0, "start_offset_s": 0.0, "inner_start_s": 0.0, "rate": 1.0},
        "rise_start_motion_s": -5.8739,
        "passage_camera": samples(v, w, yaw=yaw, lateral=lateral),
        "passage_len_s": passage_len,
        "cloth": {"loc": [cloth_x * c - 0.0 * s, Y0 + cloth_x * s if yaw else Y0], "yaw": yaw},
    }


V_TODAY_SETTLE = 418.47 / (169447 / TICK - 0.5)      # 63.79 cm/s: the tail span renormalised round a 1 s settle
V_TODAY_RAW = 59.26927500000001                       # slow-walk record new_speed_cm_s (no settle)
V_RETIMED = 10668.5 / (50.4 - 0.5)                    # 213.8 cm/s (settle-compensated retime)


@test
def t_today_is_late():
    for v, w, lo, hi in ((V_TODAY_SETTLE, 1.0, 1.2, 1.45), (V_TODAY_RAW, 0.0, 1.4, 1.65)):   # hang FRONT (39.4 cm before the line)
        p = blf.plan_fit(inputs(v, w), {})
        ref, warn = blf.check_plan(p)
        check(lo <= p["lead_now_s"] <= hi, "today lead %.3f in [%s, %s] (v %.2f, settle %s)" % (p["lead_now_s"], lo, hi, v, w))
        check(has(warn, "LEAD_NOW_SHORT"), "today warns LEAD_NOW_SHORT: %r" % warn)
        check(abs(p["release_now_scene_s"] + 5.87387) < 1e-4, "release now -5.8739: %r" % p["release_now_scene_s"])
        check(abs(p["lead_new_s"] - 5.0) < 1.0 / TICK + 1e-9, "after the fit lead = 5.0: %r" % p["lead_new_s"])
        check(has(warn, "RELEASE_VS_RISE"), "today's fit moves the release ~3 s before the rise: warned")
        check(not ref, "today DRY has no refusals: %r" % ref)


@test
def t_after_retime_nearly_right():
    p = blf.plan_fit(inputs(V_RETIMED, 1.0, passage_len=50.4), {})
    ref, warn = blf.check_plan(p)
    check(4.05 <= p["lead_now_s"] <= 4.3, "after the retime lead %.3f ~4.17 with NO change" % p["lead_now_s"])
    check(not has(warn, "LEAD_NOW_SHORT"), "after the retime no LEAD_NOW_SHORT")
    check(-0.95 <= p["delta_s"] <= -0.7, "after the retime delta %.3f ~ -0.83" % p["delta_s"])
    check(not has(warn, "RELEASE_VS_RISE"), "after the retime the release stays within 1 s of the rise: %r" % warn)
    check(not ref, "after the retime: no refusals %r" % ref)


@test
def t_control_30sep_is_noop():
    # 30 Sep fitted to the cloth LINE (CLOTH_X), not the hang front: lens_clear_cm -39.4 reproduces that plane
    p = blf.plan_fit(inputs(250.0, 0.0), {"lens_clear_cm": -39.4})
    check(abs(p["camera_cross_scene_s"] + 0.874) < 0.01, "30 Sep crossing -0.874: %r" % p["camera_cross_scene_s"])
    ref, warn = blf.check_plan(p, "DRY")
    check(has(warn, "NOOP") and not ref, "+control 30 Sep: DRY says NOOP, refuses nothing")
    ref, _ = blf.check_plan(p, "APPLY")
    check(has(ref, "NOOP"), "-control 30 Sep: APPLY refuses a NOOP")


@test
def t_lateral_and_never():
    p = blf.plan_fit(inputs(V_RETIMED, lateral=900.0), {})
    check(has(blf.check_plan(p)[0], "CAMERA_PASSES_BESIDE_CLOTH"), "-control camera 9 m to the side refused")
    p = blf.plan_fit(inputs(V_RETIMED, lateral=300.0), {})
    check(not has(blf.check_plan(p)[0], "CAMERA_PASSES_BESIDE_CLOTH"), "+control 3 m to the side passes")
    p = blf.plan_fit(inputs(V_RETIMED, cloth_x=STOP_X + 200.0), {})
    check(has(blf.check_plan(p)[0], "CAMERA_NEVER_REACHES_CLOTH"), "-control cloth beyond the stop refused")
    check(p["delta_s"] is None, "never-crossing plans no move")


@test
def t_lead_min_and_passage():
    p = blf.plan_fit(inputs(V_RETIMED), {"lead_s": 2.0})
    check(has(blf.check_plan(p)[0], "LEAD_BELOW_MIN"), "-control lead 2.0 < 2.7 refused")
    p = blf.plan_fit(inputs(V_RETIMED), {"lead_s": 2.7})
    check(not has(blf.check_plan(p)[0], "LEAD_BELOW_MIN"), "+control lead 2.7 passes")
    p = blf.plan_fit(inputs(V_RETIMED, passage_len=6.0), {})
    check(has(blf.check_plan(p)[0], "RELEASE_BEFORE_PASSAGE"), "-control a 6 s Passage cannot hold a -6.5 s release")
    try:
        blf.plan_fit(inputs(V_RETIMED), {"lead": 5})
        check(False, "-control unknown param must raise")
    except blf.PlanError:
        check(True, "unknown param raises")


@test
def t_crossing_not_pre_scene():
    inp = inputs(V_RETIMED)
    inp["passage_camera"] = [[t + 30.0, s] for t, s in inp["passage_camera"]]   # a camera that crosses after the cut
    p = blf.plan_fit(inp, {})
    check(has(blf.check_plan(p)[0], "CROSSING_NOT_PRE_SCENE"), "-control crossing after Scene 4's start refused")


@test
def t_rate_and_mapping():
    inp = inputs(V_RETIMED)
    inp["rise_sub"]["rate"] = 1.5
    try:
        blf.plan_fit(inp, {})
        check(False, "-control rate 1.5 must raise")
    except blf.PlanError:
        check(True, "rate != 1 raises")
    inp = inputs(V_RETIMED)
    inp["rise_sub"].update({"section_start_s": 2.0})                       # rise nested 2 s into the Scene
    p0, p1 = blf.plan_fit(inputs(V_RETIMED), {}), blf.plan_fit(inp, {})
    check(abs((p1["release_now_scene_s"] - p0["release_now_scene_s"]) - 2.0) < 1e-9, "nest offset maps motion->scene")
    check(abs(p1["delta_s"] - (p0["delta_s"] - 2.0)) < 1.0 / TICK + 1e-9, "the fit compensates the nest offset")


@test
def t_whole_ticks_rigid_move():
    p = blf.plan_fit(inputs(V_TODAY_SETTLE), {})
    b, a = p["section_before"], p["section_after"]
    check(abs((a["end_s"] - a["start_s"]) - (b["end_s"] - b["start_s"])) < 1e-9, "length kept")
    check(abs(p["delta_s"] * TICK - round(p["delta_s"] * TICK)) < 1e-6, "delta is whole ticks")
    check(a["offset_ticks"] == b["offset_ticks"] and a["end_offset_ticks"] == 0, "offsets kept")


@test
def t_yaw_invariance_and_mirror():
    p0 = blf.plan_fit(inputs(V_RETIMED), {})
    p1 = blf.plan_fit(inputs(V_RETIMED, yaw=-43.5725), {})
    check(abs(p0["camera_cross_scene_s"] - p1["camera_cross_scene_s"]) < 1e-6, "yawed world gives the same crossing")
    inp = inputs(V_RETIMED)
    inp["cloth"]["yaw"] = 180.0                                            # cloth facing back: camera comes from +x
    p2 = blf.plan_fit(inp, {})
    check(p2["approach_sign"] > 0, "approach from local +x detected")
    check(abs(p2["camera_cross_scene_s"] - p0["camera_cross_scene_s"]) < 0.03, "mirrored cloth: same crossing (front = x_hi)")


@test
def t_apply_gate_and_match():
    p = blf.plan_fit(inputs(V_RETIMED), {})
    check(has(blf.apply_gate(p, None), "EXPECTED_MISSING"), "-control no expected refused")
    check(has(blf.apply_gate(p, p["delta_s"] + 0.1), "PLAN_CHANGED_SINCE_DRY"), "-control moved plan refused")
    check(not blf.apply_gate(p, p["delta_s"] + 0.01), "+control within a frame passes")
    a = p["section_after"]
    live = dict(a, start_s=a["start_s"] + 1.0 / TICK, end_s=a["end_s"] + 1.0 / TICK)
    check(not blf.section_matches(live, a, TICK), "+control 1 tick off passes")
    live = dict(a, start_s=a["start_s"] + 3.0 / TICK)
    check(blf.section_matches(live, a, TICK), "-control 3 ticks off fails")
    check(blf.section_matches(dict(a, offset_ticks=a["offset_ticks"] + 1), a, TICK), "-control offset changed fails")


@test
def t_deterministic():
    a, b = blf.plan_fit(inputs(V_RETIMED), {}), blf.plan_fit(copy.deepcopy(inputs(V_RETIMED)), {})
    check(a["digest"] == b["digest"], "digest stable")
    c = blf.plan_fit(inputs(V_RETIMED), {"lead_s": 4.0})
    check(a["digest"] != c["digest"], "digest moves with the params")


def main():
    for fn in TESTS:
        before = len(CHECKS["failed"])
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            CHECKS["failed"].append("%s raised %s: %s" % (fn.__name__, type(exc).__name__, exc))
        print("%-32s %s" % (fn.__name__, "ok" if len(CHECKS["failed"]) == before else "FAIL"))
    for f in CHECKS["failed"]:
        print("  FAILED: " + f)
    for v, w, label, plen in ((V_TODAY_SETTLE, 1.0, "today (180 s, settle)", 180.0), (V_TODAY_RAW, 0.0, "today (no settle)", 180.0),
                              (V_RETIMED, 1.0, "after retime (50.4 s)", 50.4)):
        p = blf.plan_fit(inputs(v, w, passage_len=plen), {})
        print("NUMBERS|%s|v=%.2f|cross=%.3f|release_now=%.4f|lead_now=%.3f|delta_for_lead5=%.4f"
              % (label, v, p["camera_cross_scene_s"], p["release_now_scene_s"], p["lead_now_s"], p["delta_s"]))
    print("BACKCLOTH_LEAD_FIT_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
