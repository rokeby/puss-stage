"""Offline harness for the S2 V3 wings overlay (8 Oct).  System Python, no Unreal.  Writes ONLY into a temp folder
(the tool's HERE/PROJECT are redirected there) plus test_s2v3_overlay_offline_report.json next to this file.

Part A  core maths / gates, each with a POSITIVE and a NEGATIVE control.
Part B  the editor tool end-to-end against a FAKE `unreal` module (sequences, bindings, tracks, sections, channels,
        keys, actors, dirty census, saves), fed by the REAL kit files (DerivedAssets/FlatV3/KlaraS2: manifest, pivot
        offsets, rzimport plan -- read only): DRY -> APPLY (scene coverage [104, 3891), hold key + shifted keys) ->
        VERIFY -> VARIANT B (refused while B's MIs are missing, then ok) -> VERIFY -> RESYNC (noop) -> re-ingest -> VERIFY
        (stale) -> RESYNC -> VERIFY -> REVERT (scene fingerprint == pre-APPLY), plus negative controls (foreign edit
        during APPLY, Klara level dirtied, wrong binding resolution, PIE, Sequencer open, stale DRY, wrong pivot,
        unclear pre-section pose, missing level-visibility section, missing kit file) and a 'cinematic' coverage run.
Part C  static checks of the tool source (no forbidden calls, no module-level unreal objects) with a +/- control.

The fake is MY model of the UE API (names taken from precedent scripts); it proves the tool's logic and guards, not
UE behaviour.  Tier of every PASS here: measured-offline (against the fake)."""
import ast
import copy as _copy
import importlib.util
import json
import math
import os
import random
import shutil
import sys
import tempfile
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
S2K = os.path.dirname(HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"name": name, "ok": bool(cond), "detail": str(detail)[:400]})
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  :: " + str(detail)[:400]))


def expect_raise(name, fn, contains):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        check(name, contains in str(exc), "raised %r" % exc)
        return
    check(name, False, "did not raise")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


C = load("s2v3_core_test", os.path.join(HERE, "s2v3_overlay_core.py"))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
REAL_KIT = {k: os.path.join(PROJECT, v) for k, v in C.KIT.items()}
KIT_JSON = {k: json.load(open(v, encoding="utf-8")) for k, v in REAL_KIT.items()}
CENSUS = json.load(open(os.path.join(S2K, "her_wings_census.json"), encoding="utf-8"))
DECODE = json.load(open(os.path.join(S2K, "her_seq_decode.json"), encoding="utf-8"))

# her world sizes (PROPOSAL.md table [meas]): local half-widths and heights of her meshes
HER_LOCAL_BOX = {"L": [[-2.5, -212.7, 0.0], [2.5, 212.7, 1000.0]], "R": [[-2.5, -207.6, 0.0], [2.5, 207.6, 1000.0]],
                 "C": [[-2.5, -1976.0, 0.0], [2.5, 1976.0, 1000.0]]}
HER_SCALE = {"L": [1.89, 1.89, 2.25], "R": [2.25, 2.25, 2.25], "C": [0.88, 0.88, 0.88]}


def our_world_size(t):
    b, s = HER_LOCAL_BOX[t], HER_SCALE[t]
    return (b[1][1] - b[0][1]) * s[1], (b[1][2] - b[0][2]) * s[2]


def our_box(t):
    w, h = our_world_size(t)                     # V3 board: front at x=-15..-10 face, backbone pivot at y=0, y 0..W
    return [[-15.0, 0.0, 0.0], [0.0, w, h]]


def type_row(t, sign=1.0):
    w, _h = our_world_size(t)
    return {"mesh": "/Game/Scenes/Wings/FlatV3/KlaraS2/SM_S2K_%s" % t, "pivot_offset_cm": [0.0, sign * w / 2.0, 0.0],
            "rot_offset_deg": [0.0, 0.0, 180.0], "pivot_frame": "her_local_world_cm",
            "variants": {"A": {"Front": "/Game/Scenes/Wings/FlatV3/KlaraS2/MI_S2K_%s_A" % t},
                         "B": {"Front": "/Game/Scenes/Wings/FlatV3/KlaraS2/MI_S2K_%s_B" % t,
                               "Flap": "/Game/Scenes/Wings/FlatV3/KlaraS2/MI_S2K_%s_B" % t}}}


def synth_channels(label, level_yaw=-43.57, rng=None):
    """Her copy channels for one wing, shaped by her_seq_decode.json summaries (n keys, t1, v0->v1, min/max)."""
    rng = rng or random.Random(hash(label) & 0xffff)
    d = DECODE["wings"][label]
    n, t1 = d["z"]["n"], d["z"]["t1_s"]
    ticks = [int(round(i * t1 * 24000 / (n - 1))) for i in range(n)]
    out = {}
    for ch in ("x", "y", "z", "roll", "pitch"):
        s = d[ch]
        vals = []
        for i in range(n):
            f = i / (n - 1.0)
            if ch == "z":
                v = s["v0"] + (s["v1"] - s["v0"]) * (1 - (1 - f) ** 2)
            else:
                v = s["v0"] + (s["max"] - s["min"]) * 0.5 * math.sin(f * 7.0) * (1 - f)
            vals.append(round(v, 4))
        vals[-1] = s["v1"]
        out[ch] = {"keys": [[t, v, "RCIM_LINEAR"] for t, v in zip(ticks, vals)], "default": None,
                   "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"}
    out["yaw"] = {"keys": [[0, level_yaw, "RCIM_LINEAR"]], "default": None, "pre": "RCCE_CONSTANT",
                  "post": "RCCE_CONSTANT"}
    return out


def fake_eval(keys, t):
    """The fake's channel evaluator (stands in for UE): constant extrapolation; per segment LINEAR, CONSTANT or CUBIC
    (Bezier with P1 = v0 + leave0*dt/3, P2 = v1 - arrive1*dt/3, tangents in value per tick).  keys rows:
    [tick, value, interp, tmode, arrive, leave, wmode]."""
    if not keys:
        return 0.0
    if t <= keys[0][0]:
        return float(keys[0][1])
    if t >= keys[-1][0]:
        return float(keys[-1][1])
    i = max(j for j in range(len(keys)) if keys[j][0] <= t)
    a, b = keys[i], keys[i + 1]
    dt = float(b[0] - a[0])
    u = (t - a[0]) / dt
    if a[2] == "RCIM_CONSTANT":
        return float(a[1])
    if a[2] == "RCIM_LINEAR":
        return a[1] + (b[1] - a[1]) * u
    p0, p3 = a[1], b[1]
    p1, p2 = p0 + a[5] * dt / 3.0, p3 - b[4] * dt / 3.0
    return (1 - u) ** 3 * p0 + 3 * (1 - u) ** 2 * u * p1 + 3 * (1 - u) * u ** 2 * p2 + u ** 3 * p3


def cubic_channels(label, level_yaw=-43.57, tangent_scale=1.0):
    """Her copy channels as measured live (DRY S2V3OV-20261008-212010): RCIM_CUBIC x/y/z/roll/pitch on her 30 fps frame
    grid (800 ticks), counts from her_seq_decode.json, auto-like tangents; yaw one key."""
    lin = synth_channels(label, level_yaw)
    out = {}
    for n in ("x", "y", "z", "roll", "pitch"):
        ks = lin[n]["keys"]
        ks = [[int(round(k[0] / 800.0)) * 800, k[1]] for k in ks]
        rows = []
        for i, (t, v) in enumerate(ks):
            lo, hi = ks[max(i - 1, 0)], ks[min(i + 1, len(ks) - 1)]
            slope = 0.0 if hi[0] == lo[0] else (hi[1] - lo[1]) / float(hi[0] - lo[0]) * tangent_scale
            rows.append([t, v, "RCIM_CUBIC", "RCTM_AUTO", slope, slope, "RCTWM_WEIGHTED_NONE"])
        out[n] = {"keys": rows, "default": None, "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"}
    out["yaw"] = {"keys": [[0, level_yaw, "RCIM_LINEAR", "RCTM_AUTO", 0.0, 0.0, "RCTWM_WEIGHTED_NONE"]],
                  "default": None, "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"}
    return out


def part_a15():
    label = "SM_S2_L_Wing_Shrine4"                     # 136 keys, longest fall
    ch = cubic_channels(label)
    kt = [k[0] for n in C.CHANNELS for k in ch[n]["keys"]]
    g = C.sampling_grid(kt, [24000, 1], [30, 1], [25, 1], 261120)
    check("A15+ grid: 160 ticks (150 fps) = gcd(800, 960); covers every 30 and 25 fps tick",
          g["interval"] == 160 and g["rate"] == [150, 1] and all(t % 160 == 0 for t in g["ticks"][:50]), g["interval"])
    samples = {n: [fake_eval(ch[n]["keys"], t) for t in g["ticks"]] for n in C.CHANNELS}
    al = C.key_alignment(ch, g["ticks"], samples)
    check("A15+ alignment: evaluated == key value at every key tick", not al["problems"] and al["checked"] == al["keys"],
          al)
    shifted = {n: v[1:] + v[-1:] for n, v in samples.items()}
    check("A15- samples shifted by one interval -> SAMPLE_ALIGNMENT", any(x.startswith("SAMPLE_ALIGNMENT") for x in
                                                                        C.key_alignment(ch, g["ticks"], shifted)["problems"]))
    expect_raise("A15- old linear-only path refuses the cubic source (what the live DRY saw)",
                 lambda: C.req(not C.source_problems(ch), "|".join(C.source_problems(ch))), "NONLINEAR_SOURCE")
    check("A15+ sampled path accepts cubic (source_problems linear_only=False)",
          C.source_problems(ch, linear_only=False) == [])
    row = type_row("L")
    kp = C.plan_wing_keys_sampled(samples, g["ticks"], row)
    check("A15+ cubic -> LINEAR fit passes the gate (max %.4f cm / %.5f deg), %d keys from %d samples" % (
        kp["max_dev_cm"], kp["max_dev_deg"], kp["n"], kp["samples"]), not kp["problems"] and kp["n"] < kp["samples"],
        kp["problems"])
    fine = [t + 40 for t in g["ticks"][:-1]]                  # quarter-sample probe: between render ticks
    worst = 0.0
    for t in fine:
        her = [fake_eval(ch[n]["keys"], t) for n in C.CHANNELS]
        q = C.eval_linear_keys(kp["keys"], t)
        tr = C.compose_pose(her, row)
        worst = max(worst, math.sqrt(sum((q[i] - tr[i]) ** 2 for i in range(3))))
    check("A15+ between samples (off the render grid) our linear keys stay within 0.5 cm of her cubic (%.4f cm)" % worst,
          worst <= 0.5, worst)
    zero = dict(row, pivot_offset_cm=[0.0, 0.0, 0.0], rot_offset_deg=[0.0, 0.0, 0.0])
    kz = C.plan_wing_keys_sampled(samples, g["ticks"], zero)
    errz = max(abs(C.eval_linear_keys(kz["keys"], t)[2] - samples["z"][i]) for i, t in enumerate(g["ticks"]))
    check("A15+ zero offset: our Z reproduces her UE-evaluated Z at every sample within the 0.1 cm fit (%.4f)" % errz,
          errz <= 0.1 + 1e-9)
    kt_ = C.plan_wing_keys_sampled(samples, g["ticks"], row, fit_cm=5.0, fit_deg=1.0, tol_cm=0.5, tol_deg=0.05)
    check("A15- a coarse fit (5 cm) fails the 0.5 cm gate (the gate is measured, not assumed)",
          any(x.startswith("SAMPLED_GATE") for x in kt_["problems"]), kt_["problems"])
    ch2 = cubic_channels(label, tangent_scale=1.3)
    check("A15- a tangent-only change (same key values) changes the source hash",
          C.source_hashes(ch2)["all"] != C.source_hashes(ch)["all"] and
          [k[1] for k in ch2["z"]["keys"]] == [k[1] for k in ch["z"]["keys"]])
    expect_raise("A15- pre-roll off the sample grid refused",
                 lambda: C.sampling_grid(kt, [24000, 1], [30, 1], [25, 1], 261120 + 7), "PRE_ROLL_OFF_SAMPLE_GRID")


# ===================================================================================================== PART A
def part_a():
    rnd = random.Random(7)
    worst = 0.0
    for _ in range(300):
        r = [rnd.uniform(-180, 180), rnd.uniform(-85, 85), rnd.uniform(-180, 180)]
        back = C.matrix_rotator(C.rot_matrix(*r))
        m1, m2 = C.rot_matrix(*r), C.rot_matrix(*back)
        worst = max(worst, max(abs(m1[i][j] - m2[i][j]) for i in range(3) for j in range(3)))
    check("A1+ rotator round trip (300 random)", worst < 1e-9, worst)
    x = C.apply_rot(C.rot_matrix(0, 0, 90), [1, 0, 0])
    check("A1+ yaw 90 maps +X to +Y (UE convention)", abs(x[0]) < 1e-12 and abs(x[1] - 1) < 1e-12, x)
    z = C.apply_rot(C.rot_matrix(0, 30, 0), [1, 0, 0])
    check("A1+ pitch +30 raises +X (nose up)", z[2] > 0.49, z)
    check("A1- a different rotator is NOT a round trip", max(abs(a - b) for a, b in zip(
        C.rot_matrix(0, 0, 90)[0], C.rot_matrix(0, 0, 91)[0])) > 1e-3)

    row = type_row("L")
    her = [100.0, 200.0, 789.0, 0.0, 0.0, -43.57]
    p = C.compose_pose(her, row)
    w = our_world_size("L")[0]
    exp = C.apply_rot(C.rot_matrix(0, 0, -43.57), [0, w / 2, 0])
    check("A2+ compose: loc = her + R_her.offset", all(abs(p[i] - (her[i] + exp[i])) < 1e-9 for i in range(3)), p)
    check("A2+ compose: yaw = her yaw + 180", C.angle_diff(p[5], -43.57 + 180) < 1e-9 and abs(p[3]) < 1e-9, p[3:])
    r0 = dict(row, rot_offset_deg=[0.0, 0.0, 0.0])
    r0b = dict(r0, pivot_frame="our_local_cm")         # (with yaw 180 the two frames coincide for a pure-Y offset)
    check("A2- our_local_cm frame gives a different location", max(abs(a - b) for a, b in zip(
        C.compose_pose(her, r0b)[:3], C.compose_pose(her, r0)[:3])) > 1.0)
    zero = dict(row, pivot_offset_cm=[0.0, 0.0, 0.0], rot_offset_deg=[0.0, 0.0, 0.0])
    tilt = [5.0, 6.0, 7.0, 3.3, -0.9, -43.57]
    check("A2+ zero offset reproduces her pose", all(abs(a - b) < 1e-9 for a, b in zip(C.compose_pose(tilt, zero), tilt)))

    ch = {"keys": [[0, 0.0, "RCIM_LINEAR"], [100, 10.0, "RCIM_CONSTANT"], [200, 20.0, "RCIM_LINEAR"]], "default": None}
    check("A3+ linear eval", abs(C.eval_channel(ch, 50) - 5.0) < 1e-12)
    check("A3+ constant segment holds", C.eval_channel(ch, 150) == 10.0)
    check("A3+ constant extrapolation", C.eval_channel(ch, -5) == 0.0 and C.eval_channel(ch, 999) == 20.0)
    cub = {"keys": [[0, 0.0, "RCIM_CUBIC"], [100, 10.0, "RCIM_LINEAR"]], "default": None}
    expect_raise("A3- cubic segment refused", lambda: C.eval_channel(cub, 50), "NONLINEAR_SOURCE_KEY")

    label = "SM_S2_ceiling_wing5"
    chans = synth_channels(label)
    kp0 = C.plan_wing_keys(chans, zero)
    same = all(abs(k[3] - C.eval_channel(chans["z"], k[0])) < 1e-9 for k in kp0["keys"])
    check("A4+ zero offset: our Z keys == her Z keys at her ticks", same and kp0["n"] == DECODE["wings"][label]["z"]["n"],
          kp0.get("n"))
    kp = C.plan_wing_keys(chans, type_row("C"))
    check("A4+ ceiling with 1976 cm half-width offset: midpoint deviation within tol", not kp["problems"],
          (kp["midpoint_dev_cm"], kp["midpoint_dev_deg"]))
    kpt = C.plan_wing_keys(chans, type_row("C"), tol_cm=1e-9, tol_deg=1e-9)
    check("A4- tolerance control: a near-zero tol refuses (deviation is measured, not assumed)",
          any(x.startswith("MIDPOINT_DEVIATION") for x in kpt["problems"]), kpt["problems"])
    kz = C.plan_wing_keys(chans, zero, copy_channels="z_only")
    restx = C.eval_channel(chans["x"], 10 ** 9)
    check("A4+ z_only holds X at her rest value", all(abs(k[1] - restx) < 1e-9 for k in kz["keys"]))
    bad = _copy.deepcopy(chans)
    bad["x"]["post"] = "RCCE_CYCLE"
    check("A4- cyclic extrapolation refused", any("EXTRAPOLATION" in x for x in C.plan_wing_keys(bad, zero)["problems"]))

    h0 = C.source_hashes(chans)
    n1 = _copy.deepcopy(chans)
    n1["z"]["keys"][5][1] += 1e-6
    check("A5+ hash stable under 1e-6 transport noise", C.source_hashes(n1) == h0)
    n2 = _copy.deepcopy(chans)
    n2["z"]["keys"][5][1] += 0.01
    check("A5- hash changes on a 0.01 cm key edit (re-ingest detectable)",
          C.source_hashes(n2)["z"] != h0["z"] and C.source_hashes(n2)["all"] != h0["all"])

    before = {"SEQ": {"a": 1}, "M/T0:MovieSceneSubTrack:Klara Hookin - Replacement Shot": {"s": 1}}
    tp = "M/T5:MovieSceneSubTrack:" + C.OVERLAY_TRACK
    after = dict(before, **{tp: {"x": 1}, tp + "/S0": {"y": 1}})
    check("A6+ only our rows new -> no violations", C.fingerprint_diff(before, after, tp) == [])
    after2 = dict(after, **{"M/T6:MovieSceneSubTrack:" + C.OVERLAY_TRACK + "2": {"z": 1}})
    check("A6- prefix collision ('...Overlay2') is a violation", len(C.fingerprint_diff(before, after2, tp)) == 1)
    after3 = dict(after, SEQ={"a": 2})
    check("A6- a changed foreign row is a violation", C.fingerprint_diff(before, after3, tp)[0]["why"] == "CHANGED")
    after4 = {k: v for k, v in after.items() if k != "SEQ"}
    check("A6- a removed row is a violation", C.fingerprint_diff(before, after4, tp)[0]["why"] == "REMOVED")

    check("A7+ exact census passes", C.census_gate({"content": ["/Game/a"], "maps": []}, ["/Game/a"]) == [])
    g = C.census_gate({"content": ["/Game/a"], "maps": [C.HER_LEVEL]}, ["/Game/a"])
    check("A7- her level dirty -> KLARA_PACKAGE_DIRTY", any(x.startswith("KLARA_PACKAGE_DIRTY") for x in g), g)
    g2 = C.census_gate({"content": ["/Game/a", "/Game/b"], "maps": []}, ["/Game/a"])
    check("A7- extra dirty content refused", any(x.startswith("CONTENT_CENSUS") for x in g2))

    M, P, R = KIT_JSON["manifest_path"], KIT_JSON["pivot_path"], KIT_JSON["rzimport_plan_path"]
    res, probs = C.resolve_types({}, M, P, R)
    check("A8+ REAL kit resolves all three owners with no problems", not probs, probs)
    check("A8+ REAL kit: L child transform (-10.27, 402.38, 0) yaw 180, frame her_local_world_cm",
          res["L"]["pivot_offset_cm"] == [-10.27, 402.38, 0.0] and res["L"]["rot_offset_deg"] == [0.0, 0.0, 180.0]
          and res["L"]["pivot_frame"] == "her_local_world_cm", res["L"].get("pivot_offset_cm"))
    check("A8+ REAL kit: mesh paths from the rzimport plan (T5P / T5J)",
          res["L"]["mesh"].endswith("/T5P/SM_FlatV3_S2K_shrine_L_t5p") and
          res["C"]["mesh"].endswith("/T5J/SM_FlatV3_S2K_ceiling_C_t5j"), [res[t]["mesh"] for t in C.TYPES])
    va, vb = res["R"]["variants"]["A"], res["R"]["variants"]["B"]
    check("A8+ REAL kit: A = kit Front/Flap MIs; B = KlaraS2 LacqWet copies (bare Flap name -> B Front's folder); "
          "Timber/Edge unchanged (absent)",
          va["Front"].endswith("/Realism/Materials/Instances/MI_FlatV3_S2K_shrine_R_Front") and
          vb["Front"] == "/Game/Scenes/Wings/FlatV3/KlaraS2/Materials/MI_S2K_S2K_shrine_R_Front_LacqWet" and
          vb["Flap"] == "/Game/Scenes/Wings/FlatV3/KlaraS2/Materials/MI_S2K_S2K_shrine_R_Flap_LacqWet" and
          set(va) == {"Front", "Flap"} and set(vb) == {"Front", "Flap"}, (va, vb))
    check("A8+ REAL kit: her_actors per type == census labels", C.check_her_actor_lists(
        res, C.her_wings_from_census(CENSUS)) == [])
    P2 = _copy.deepcopy(P)
    P2["wings"]["shrine_L"]["child_relative_transform_ue"]["location_cm"][1] = 400.0
    check("A8- pivot file vs manifest disagree -> PIVOT_SOURCES_DISAGREE",
          any("PIVOT_SOURCES_DISAGREE" in x for x in C.resolve_types({}, M, P2, R)[1]))
    M2 = _copy.deepcopy(M)
    M2["meshes"][1]["klara_s2"]["front_variants"]["B"]["Front"] = "/Game/WetGround/MI_LacqueredPaper_Wet = hers"
    check("A8- a variant pointing at HER material is refused (copies only)",
          any("VARIANT_USES_KLARA_ASSET" in x for x in C.resolve_types({}, M2, P, R)[1]))
    P3 = _copy.deepcopy(P)
    P3["child_transform_rule"] = "world(ours) = Translate(T) * HerActorTransform"
    check("A8- an unknown composition rule is refused", any("PIVOT_RULE_UNKNOWN" in x for x in C.resolve_types(
        {}, M, P3, R)[1]))
    check("A8- no kit at all -> unresolved mesh + pivot for every type",
          sum(("unresolved" in x) for x in C.resolve_types({}, None, None, None)[1]) == 6)
    a3 = {"types": {"L": {"owner": "S2K_shrine_L", "pivot_offset_cm": [9, 9, 9]}}}
    check("A8+ args override the kit", C.resolve_types(a3, M, P, R)[0]["L"]["pivot_offset_cm"] == [9, 9, 9])
    w2 = C.her_wings_from_census(CENSUS)
    res2 = _copy.deepcopy(res)
    res2["C"]["her_actors"] = res2["C"]["her_actors"][:4]
    check("A8- kit her_actors missing one ceiling -> KIT_HER_ACTORS", C.check_her_actor_lists(res2, w2) != [])

    cov = C.coverage_plan("scene", [376, 3891], [104, 3891], [25, 1], [24000, 1])
    check("A12+ scene coverage: [104, 3891), pre-roll 272 frames = 10.88 s = 261120 ticks",
          cov["range"] == [104, 3891] and cov["pre_ticks"] == 261120 and abs(cov["pre_seconds"] - 10.88) < 1e-9, cov)
    check("A12+ cinematic coverage: exactly the hookin section, no pre-roll",
          C.coverage_plan("cinematic", [376, 3891], None, [25, 1], [24000, 1]) ==
          {"range": [376, 3891], "pre_frames": 0, "pre_ticks": 0, "pre_seconds": 0.0})
    expect_raise("A12- level visible only after the hookin starts -> refused",
                 lambda: C.coverage_plan("scene", [376, 3891], [400, 3891], [25, 1], [24000, 1]),
                 "LEVEL_VISIBLE_AFTER_HOOKIN")
    expect_raise("A12- pre-roll off the tick grid -> refused",
                 lambda: C.coverage_plan("scene", [376, 3891], [104, 3891], [25, 1], [7, 1]), "PRE_ROLL_NOT_ON_TICK_GRID")
    expect_raise("A12- scene coverage without a level-visibility section -> refused",
                 lambda: C.coverage_plan("scene", [376, 3891], None, [25, 1], [24000, 1]), "LEVEL_VIS_SECTION_MISSING")
    first, rest = [0, 0, 6657, 0, 0, -43.57], [0, 0, 789, 0, 0, -43.57]
    check("A13+ pre-pose classification: rest / first",
          C.classify_pre_pose([0, 0, 789.5, 0, 0, -43.57], first, rest) == "rest" and
          C.classify_pre_pose(first, first, rest) == "first")
    check("A13- a mid-fall pose is 'unclear' (refused unless forced)",
          C.classify_pre_pose([0, 0, 3000, 0, 0, -43.57], first, rest) == "unclear")
    ks = [[0, 1, 2, 3, 0, 0, 10], [800, 1, 2, 2, 0, 0, 10]]
    hk, hi = C.with_hold(ks, 261120, [5, 5, 5, 0, 0, -350])
    check("A14+ hold: CONSTANT key at 0 with the hold pose, her keys shifted by the pre-roll, yaw unwrapped",
          hk[0][:4] == [0, 5, 5, 5] and hi[0] == "RCIM_CONSTANT" and [k[0] for k in hk[1:]] == [261120, 261920] and
          hi[1:] == ["RCIM_LINEAR"] * 2 and abs(hk[0][6] - 10) < 1e-9, (hk[0], hi))
    hk0, hi0 = C.with_hold(ks, 0, [5, 5, 5, 0, 0, 0])
    check("A14- no pre-roll: no hold key, keys unshifted", hk0 == ks and hi0 == ["RCIM_LINEAR"] * 2)
    check("A14- keys_sha sees an interpolation change", C.keys_sha(hk, hi) != C.keys_sha(hk, ["RCIM_LINEAR"] * 3))

    wings = C.her_wings_from_census(CENSUS)
    check("A9+ census -> 15 wings (5 L, 5 R, 5 C)", len(wings) == 15)
    cut = dict(CENSUS, rows=[r for r in CENSUS["rows"] if r.get("label") != "SM_S2_L_Wing_Shrine3"])
    expect_raise("A9- a missing wing refuses", lambda: C.her_wings_from_census(cut), "HER_WING_COUNT")

    good = {"mode": "APPLY", "confirm": "APPLY S2V3OVERLAY", "decided_by": "x",
            "overlay_asset": "/Game/Scenes/KlaraS2V3/LS_S2_V3WingsOverlay", "types": {}}
    check("A10+ valid APPLY args", C.validate_args(good) == [], C.validate_args(good))
    check("A10- wrong confirm", any(x.startswith("CONFIRM") for x in C.validate_args(dict(good, confirm="APPLY"))))
    check("A10- overlay inside her folder refused", any(x.startswith("OVERLAY_ASSET") for x in C.validate_args(
        dict(good, overlay_asset="/Game/KK_S2_Shrine/LS_X"))))
    check("A10- bad coverage mode refused", any(x.startswith("COVERAGE") for x in C.validate_args(
        dict(good, coverage="whole"))))
    check("A10- PIE refused", any("PIE_RUNNING" in x for x in C.check_mode(good, True, None, None)))
    check("A10- Sequencer open refused (DRY too)", any("SEQUENCER_OPEN" in x for x in C.check_mode(
        dict(good, mode="DRY"), False, "/Game/X", None)))

    al = C.box_alignment(our_box("L"), HER_LOCAL_BOX["L"], HER_SCALE["L"], type_row("L"))
    check("A11+ correct pivot: our box lands on hers (Y/Z within 0.01 cm)", al["max_yz_cm"] < 0.01, al["delta"])
    al2 = C.box_alignment(our_box("L"), HER_LOCAL_BOX["L"], HER_SCALE["L"], type_row("L", sign=-1.0))
    check("A11- wrong pivot sign: off by a full width", al2["max_yz_cm"] > 700, al2["delta"])


# ===================================================================================================== FAKE UNREAL
class Enum:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "Enum." + self.name

    def __eq__(self, o):
        return isinstance(o, Enum) and o.name == self.name

    def __hash__(self):
        return hash(self.name)


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FrameNumber:
    def __init__(self, value):
        self.value = int(value)


class FrameRate:
    def __init__(self, n=None, d=1, numerator=None, denominator=None):
        self.numerator = numerator if numerator is not None else n
        self.denominator = denominator if denominator is not None else d


class FrameTime:
    def __init__(self, fn, sub=0.0):
        self.frame_number, self.sub_frame = fn, sub


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class FakeClass:
    def __init__(self, name):
        self._n = name

    def get_name(self):
        return self._n


class Obj:
    def get_class(self):
        return FakeClass(getattr(self, "_cls_name", type(self).__name__))


class World:
    def __init__(self, U, pkg):
        self.U, self.pkg, self.actors = U, pkg, []

    def get_outermost(self):
        return NS(get_name=lambda: self.pkg)


class Key:
    def __init__(self, tick, value, interp="RCIM_LINEAR", arrive=0.0, leave=0.0):
        self.tick, self.value, self.interp, self.arrive, self.leave = int(tick), value, interp, arrive, leave

    def get_arrive_tangent(self):
        return self.arrive

    def get_leave_tangent(self):
        return self.leave

    def get_tangent_weight_mode(self):
        return Enum("RCTWM_WEIGHTED_NONE")

    def get_time(self, time_unit=None):
        if time_unit is None or time_unit.name != "TICK_RESOLUTION":
            raise RuntimeError("fake: only TICK_RESOLUTION supported")
        return FrameTime(FrameNumber(self.tick), 0.0)

    def get_value(self):
        return self.value

    def get_interpolation_mode(self):
        return Enum(self.interp)

    def get_tangent_mode(self):
        return Enum("RCTM_AUTO")


class Channel(Obj):
    def __init__(self, sec, name, kind="double"):
        self.sec, self.channel_name, self.kind = sec, name, kind
        self.keys, self.default = [], None
        self.pre = self.post = Enum("RCCE_CONSTANT")

    def _d(self):
        self.sec._d()

    def get_name(self):
        return self.channel_name

    def get_keys(self):
        return list(self.keys)

    def add_key(self, time, new_value, sub_frame=0.0, time_unit=None, interpolation=None):
        if time_unit is None or time_unit.name != "TICK_RESOLUTION":
            raise RuntimeError("fake: tool must key in TICK_RESOLUTION")
        self.keys = [k for k in self.keys if k.tick != time.value]
        k = Key(time.value, new_value, {"LINEAR": "RCIM_LINEAR", "CONSTANT": "RCIM_CONSTANT"}.get(
            interpolation.name if interpolation else "", "RCIM_CUBIC"))
        self.keys.append(k)
        self.keys.sort(key=lambda k: k.tick)
        self._d()
        return k

    def remove_key(self, k):
        self.keys.remove(k)
        self._d()

    def set_default(self, v):
        self.default = v
        self._d()

    def get_default(self):
        return self.default

    def has_default(self):
        return self.default is not None

    def evaluate_keys(self, rng, frame_rate):
        """UE's EvaluateKeysInChannel [decl MovieSceneScriptingChannel.h:218-245]: step one requested-rate frame (in
        ticks) from the range's lower tick, exclusive upper.  The fake's range object carries ticks."""
        seq = self.sec.track.owner
        seq = getattr(seq, "seq", seq)                   # binding track -> its sequence (UE: OwningSequence)
        tick = seq.tick.numerator / float(seq.tick.denominator)
        interval = tick * frame_rate.denominator / float(frame_rate.numerator)
        rows = [[k.tick, k.value, k.interp, "RCTM_AUTO", k.arrive, k.leave] for k in self.keys]
        out, t = [], float(rng.lo)
        while t < rng.hi:
            out.append(fake_eval(rows, int(math.floor(t))) if rows else (self.default or 0.0))
            t += interval
        return out

    def get_pre_infinity_extrapolation(self):
        return self.pre

    def get_post_infinity_extrapolation(self):
        return self.post


class Params:
    def __init__(self, offset=0, scale=1.0):
        self.start_frame_offset, self.time_scale = offset, scale

    def export_text(self):
        return "(StartFrameOffset=(Value=%d),TimeScale=%.6f)" % (self.start_frame_offset, self.time_scale)


class Section(Obj):
    def __init__(self, track, chan_spec=()):
        self.track, self.start, self.end, self.active = track, 0, 0, True
        self.completion = Enum("KEEP_STATE")
        self.channels = [Channel(self, n, k) for n, k in chan_spec]
        self.blend = Enum("ABSOLUTE")
        self.level_names = []

    def get_level_names(self):
        return list(self.level_names)

    def _d(self):
        self.track._d()

    def get_all_channels(self):
        return list(self.channels)

    def set_range(self, a, b):
        self.start, self.end = int(a), int(b)
        self._d()

    def get_start_frame(self):
        return self.start

    def get_end_frame(self):
        return self.end

    def has_start_frame(self):
        return True

    def has_end_frame(self):
        return True

    def is_active(self):
        return self.active

    def set_is_active(self, v):
        self.active = bool(v)
        self._d()

    def set_completion_mode(self, m):
        self.completion = m
        self._d()

    def get_completion_mode(self):
        return self.completion

    def get_blend_type(self):
        return self.blend


class SubSection(Section):
    _cls_name = "MovieSceneSubSection"

    def __init__(self, track):
        super().__init__(track)
        self.sequence, self.params = None, Params()

    def get_sequence(self):
        return self.sequence

    def set_sequence(self, s):
        self.sequence = s
        self._d()

    def get_editor_property(self, n):
        assert n == "parameters"
        return Params(self.params.start_frame_offset, self.params.time_scale)

    def set_editor_property(self, n, v):
        assert n == "parameters"
        self.params = Params(v.start_frame_offset, v.time_scale)
        self._d()


TRANSFORM_CH = [("Location.X_183", "d"), ("Location.Y_183", "d"), ("Location.Z_183", "d"), ("Rotation.X_183", "d"),
                ("Rotation.Y_183", "d"), ("Rotation.Z_183", "d"), ("Scale.X_183", "d"), ("Scale.Y_183", "d"),
                ("Scale.Z_183", "d")]


class Track(Obj):
    def __init__(self, owner, cls_name):
        self.owner, self._cls_name, self.name, self.prop, self.sections = owner, cls_name, cls_name, "", []

    def _d(self):
        self.owner._d()

    def get_display_name(self):
        return self.name

    def set_display_name(self, n):
        self.name = n
        self._d()

    def get_property_name(self):
        return self.prop

    def set_property_name_and_path(self, n, p):
        self.prop = n
        self._d()

    def add_section(self):
        if self._cls_name in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
            s = SubSection(self)
        elif self._cls_name == "MovieScene3DTransformTrack":
            s = Section(self, TRANSFORM_CH)
        elif self._cls_name in ("MovieSceneVisibilityTrack", "MovieSceneSpawnTrack", "MovieSceneBoolTrack"):
            s = Section(self, [("Bool", "b")])
        else:
            s = Section(self, [("Float", "d")])
        self.sections.append(s)
        self._d()
        return s

    def remove_section(self, s):
        self.sections.remove(s)
        self._d()

    def get_sections(self):
        return list(self.sections)


TRACK_CLASSES = {}


def track_cls(name):
    if name not in TRACK_CLASSES:
        TRACK_CLASSES[name] = type(name, (Track,), {"_cls_name": name})
    return TRACK_CLASSES[name]


class Component(Obj):
    _cls_name = "StaticMeshComponent"

    def __init__(self, owner):
        self.owner = owner
        self.props = {"mobility": Enum("STATIC"), "static_mesh": None, "override_materials": [],
                      "relative_location": Vector(), "relative_rotation": Rotator(), "relative_scale3d": Vector(1, 1, 1)}

    def get_editor_property(self, n):
        return self.props[n]

    def set_editor_property(self, n, v):
        if n not in self.props:
            raise AttributeError(n)
        self.props[n] = list(v) if isinstance(v, list) else v
        if self.owner is not None:
            self.owner._d()


class Template(Obj):
    _cls_name = "StaticMeshActor"

    def __init__(self, binding):
        self.binding = binding
        self.comp = Component(self)

    def _d(self):
        self.binding._d()

    def get_editor_property(self, n):
        if n in ("static_mesh_component", "root_component"):
            return self.comp
        raise AttributeError(n)


class Binding(Obj):
    def __init__(self, seq, name, actor=None, spawnable=False):
        self.seq, self.name, self.actor, self.tracks = seq, name, actor, []
        self.guid = "%032X" % random.getrandbits(128)
        self.template = Template(self) if spawnable else None

    def _d(self):
        self.seq._d()

    def is_valid(self):
        return True

    def get_id(self):
        return self.guid

    def get_display_name(self):
        return self.name

    def set_display_name(self, n):
        self.name = n
        self._d()

    def add_track(self, cls):
        t = track_cls(cls.__name__)(self, cls.__name__)
        self.tracks.append(t)
        self._d()
        return t

    def remove_track(self, t):
        self.tracks.remove(t)
        self._d()

    def get_tracks(self):
        return list(self.tracks)

    def get_object_template(self):
        return self.template

    def get_parent(self):
        return None

    def get_child_possessables(self):
        return []


class Sequence(Obj):
    _cls_name = "LevelSequence"

    def __init__(self, U, path, fps, tick=24000, playback=(0, 100)):
        self.U, self.path, self.fps, self.tick = U, path, FrameRate(fps), FrameRate(tick)
        self.pb, self.tracks, self.bindings = list(playback), [], []

    def _d(self):
        self.U.dirty_content.add(self.path)

    def get_path_name(self):
        return "%s.%s" % (self.path, self.path.rsplit("/", 1)[-1])

    def get_name(self):
        return self.path

    def get_display_rate(self):
        return self.fps

    def get_tick_resolution(self):
        return self.tick

    def set_display_rate(self, r):
        self.fps = FrameRate(r.numerator, r.denominator)
        self._d()

    def set_tick_resolution(self, r):
        self.tick = FrameRate(r.numerator, r.denominator)
        self._d()

    def get_playback_start(self):
        return self.pb[0]

    def get_playback_end(self):
        return self.pb[1]

    def set_playback_start(self, v):
        self.pb[0] = int(v)
        self._d()

    def set_playback_end(self, v):
        self.pb[1] = int(v)
        self._d()

    def get_tracks(self):
        return list(self.tracks)

    def add_track(self, cls):
        t = track_cls(cls.__name__)(self, cls.__name__)
        self.tracks.append(t)
        self._d()
        return t

    def remove_track(self, t):
        self.tracks.remove(t)
        self._d()
        return None                                     # memory: return values lie -> the tool must re-read

    def get_bindings(self):
        return list(self.bindings)

    def add_possessable(self, actor):
        b = Binding(self, str(actor.get_actor_label()), actor=actor)
        self.bindings.append(b)
        self._d()
        self.U.calls.append(("add_possessable", self.path, actor.get_path_name()))
        return b

    def add_spawnable_from_class(self, cls):
        b = Binding(self, cls.__name__, spawnable=True)
        b.tracks.append(track_cls("MovieSceneSpawnTrack")(b, "MovieSceneSpawnTrack"))   # UE adds one itself
        self.bindings.append(b)
        self._d()
        return b

    def make_range(self, start, duration):
        tpf = self.tick.numerator * self.fps.denominator / float(self.tick.denominator * self.fps.numerator)
        if self.U.range_trap:                            # the 60000-fps default-range trap: ~1 value
            return NS(lo=start, hi=start + duration)
        return NS(lo=start * tpf, hi=(start + duration) * tpf)

    def locate_bound_objects(self, binding, context):
        if binding.actor is not None and binding.actor in context.actors:
            return [binding.actor]
        return []


class StaticMeshActor(Obj):
    def __init__(self, U, pkg, name, label, mesh, pose, scale):
        self.U, self.pkg, self.name, self.label, self.pose, self.scale = U, pkg, name, label, pose, scale
        self.comp = Component(None)
        self.comp.props["static_mesh"] = mesh

    def get_name(self):
        return self.name

    def get_actor_label(self):
        return self.label

    def get_outermost(self):
        return NS(get_name=lambda: self.pkg)

    def get_path_name(self):
        return "%s.%s:PersistentLevel.%s" % (self.pkg, self.pkg.rsplit("/", 1)[-1], self.name)

    def get_editor_property(self, n):
        if n == "static_mesh_component":
            return self.comp
        raise AttributeError(n)

    def get_actor_location(self):
        return Vector(*self.pose[:3])

    def get_actor_rotation(self):
        return Rotator(roll=self.pose[3], pitch=self.pose[4], yaw=self.pose[5])

    def get_actor_scale3d(self):
        return Vector(*self.scale)


class MaterialInterface(Obj):
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return "%s.%s" % (self.path, self.path.rsplit("/", 1)[-1])


class StaticMesh(Obj):
    def __init__(self, path, box, slots):
        self.path, self.box, self.slots = path, box, slots

    def get_path_name(self):
        return "%s.%s" % (self.path, self.path.rsplit("/", 1)[-1])

    def get_bounding_box(self):
        return NS(min=Vector(*self.box[0]), max=Vector(*self.box[1]))

    def get_editor_property(self, n):
        assert n == "static_materials"
        return [NS(get_editor_property=lambda k, s=s: s) for s in self.slots]


class FakeUnreal(types.ModuleType):
    def __init__(self, project):
        super().__init__("unreal")
        U = self
        self.project, self.assets, self.dirty_content, self.dirty_maps = project, {}, set(), set()
        self.calls, self.logs, self.saved, self.pie, self.seq_open = [], [], [], False, None
        self.range_trap = False
        self.FrameRate = FrameRate
        self.MovieSceneScriptingDoubleChannel = Channel
        self.world = World(self, C.WORLD)
        self.MovieSceneTimeUnit = NS(TICK_RESOLUTION=Enum("TICK_RESOLUTION"), DISPLAY_RATE=Enum("DISPLAY_RATE"))
        self.MovieSceneKeyInterpolation = NS(LINEAR=Enum("LINEAR"), AUTO=Enum("AUTO"), CONSTANT=Enum("CONSTANT"))
        self.MovieSceneLevelVisibilitySection = Section
        self.MovieSceneCompletionMode = NS(RESTORE_STATE=Enum("RESTORE_STATE"), KEEP_STATE=Enum("KEEP_STATE"))
        self.ComponentMobility = NS(MOVABLE=Enum("MOVABLE"), STATIC=Enum("STATIC"))
        self.FrameNumber, self.Vector, self.Rotator = FrameNumber, Vector, Rotator
        self.LevelSequence, self.MovieSceneBindingProxy = Sequence, Binding
        self.MovieSceneSection, self.StaticMeshActor, self.MaterialInterface = Section, StaticMeshActor, MaterialInterface
        for n in ("MovieSceneSubTrack", "MovieSceneVisibilityTrack", "MovieScene3DTransformTrack",
                  "MovieSceneSpawnTrack", "MovieSceneCinematicShotTrack", "MovieSceneAudioTrack",
                  "MovieSceneLevelVisibilityTrack"):
            setattr(self, n, track_cls(n))
        self.UnrealEditorSubsystem = object
        self.get_editor_subsystem = lambda cls: NS(get_game_world=lambda: object() if U.pie else None,
                                                   get_editor_world=lambda: U.world,
                                                   request_end_play=lambda: U.calls.append(("END_PIE",)))
        self.LevelSequenceEditorBlueprintLibrary = NS(get_current_level_sequence=lambda: U.seq_open)
        self.GuidLibrary = NS(conv_guid_to_string=lambda g: str(g))
        self.EditorLoadingAndSavingUtils = NS(
            get_dirty_content_packages=lambda: [NS(get_name=lambda p=p: p) for p in sorted(U.dirty_content)],
            get_dirty_map_packages=lambda: [NS(get_name=lambda p=p: p) for p in sorted(U.dirty_maps)],
            save_map=lambda *a: U.calls.append(("SAVE_MAP",)))
        self.EditorAssetLibrary = NS(does_asset_exist=lambda p: p.split(".")[0] in U.assets, save_asset=self._save)
        self.GameplayStatics = NS(get_all_actors_of_class=lambda w, cls: [a for a in w.actors if isinstance(a, cls)])
        self.MovieSceneSectionExtensions = NS(get_parent_sequence_frame=self._parent_frame)
        self.LevelSequenceFactoryNew = lambda: None
        self.AssetToolsHelpers = NS(get_asset_tools=lambda: NS(create_asset=self._create))
        self.log = lambda m: U.logs.append(("I", m))
        self.log_error = lambda m: U.logs.append(("E", m))
        self.log_warning = lambda m: U.logs.append(("W", m))
        self.load_asset = lambda p: U.assets.get(str(p).split(".")[0])

    def _save(self, path, only_if_is_dirty=False):
        p = path.split(".")[0]
        if p not in self.assets:
            return False
        self.dirty_content.discard(p)
        self.saved.append(p)
        f = os.path.join(self.project, "Content", *p[len("/Game/"):].split("/")) + ".uasset"
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, "w").write("saved %s" % p)
        return True

    def _create(self, name, folder, cls, factory):
        p = folder + "/" + name
        if p in self.assets:
            return None
        s = Sequence(self, p, 30)
        self.assets[p] = s
        s._d()
        return s

    def _parent_frame(self, sec, frame, parent):
        child = sec.sequence
        cf = child.fps.numerator / child.fps.denominator
        pf = parent.fps.numerator / parent.fps.denominator
        return int(math.floor(sec.start + frame / cf * pf))


def build_env(tmp):
    """Fake editor state: LS_DevScene_02 (hookin section, foreign bindings), the hookin copy with her 15 wing bindings,
    her 15 actors in her streamed level, our meshes + MIs, a manifest.  -> (U, args)."""
    random.seed(11)
    os.makedirs(tmp, exist_ok=True)
    U = FakeUnreal(tmp)
    scene = Sequence(U, C.SCENE_SEQ, 25, 24000, (0, 3891))
    copy = Sequence(U, C.HOOKIN_COPY, 30, 24000, (0, 4217))
    shrine = Sequence(U, "/Game/Scenes/LS_Shrine", 25)
    for s in (scene, copy, shrine):
        U.assets[s.path] = s
    shots = scene.add_track(U.MovieSceneCinematicShotTrack)
    shots.name = "Shots"
    s0 = shots.add_section()
    s0.set_range(0, 375)
    s0.sequence, s0.active = shrine, False
    hk = scene.add_track(U.MovieSceneSubTrack)
    hk.name = C.HOOKIN_TRACK
    hs = hk.add_section()
    hs.set_range(376, 3891)
    hs.sequence, hs.completion = copy, Enum("RESTORE_STATE")
    nar = scene.add_track(U.MovieSceneAudioTrack)
    nar.name = "Narration (stand-in)"
    nar.add_section().set_range(104, 1973)
    for pref, nm in ((C.EXPECTED_FOREIGN_PREFIXES[0], "Moon"), (C.EXPECTED_FOREIGN_PREFIXES[1], "SkyLight2"),
                     (C.EXPECTED_FOREIGN_PREFIXES[2], "Lattice"), (C.EXPECTED_FOREIGN_PREFIXES[3], "Ghost")):
        b = Binding(scene, pref + nm)
        scene.bindings.append(b)
        t = b.add_track(U.MovieSceneVisibilityTrack)
        t.prop = "bHidden"
        sec = t.add_section()
        sec.set_range(376, 3891)
        sec.channels[0].default = False
    other = Binding(scene, "S2 Hangar Root")
    scene.bindings.append(other)
    tt = other.add_track(U.MovieScene3DTransformTrack)
    ts = tt.add_section()
    ts.set_range(0, 3891)
    ts.channels[2].keys = [Key(0, -3300.0), Key(24000 * 4, 0.0)]
    cam = Binding(copy, "CineCameraActor")
    copy.bindings.append(cam)
    her_level = C.HER_LEVEL
    wings = C.her_wings_from_census(CENSUS)
    for w in wings:
        b = Binding(copy, w["label"])
        copy.bindings.append(b)
        tr = b.add_track(U.MovieScene3DTransformTrack)
        sec = tr.add_section()
        sec.set_range(0, 4217)
        chans = cubic_channels(w["label"])
        for i, n in enumerate(C.CHANNELS):
            sec.channels[i].keys = [Key(k[0], k[1], k[2], k[4], k[5]) for k in chans[n]["keys"]]
        for i in (6, 7, 8):
            sec.channels[i].default = 1.0
        rest = [chans[n]["keys"][-1][1] for n in C.CHANNELS]
        her_mesh = StaticMesh(w["mesh"].split(".")[0], HER_LOCAL_BOX[w["type"]], ["Front", "Back", "Edge"])
        U.assets[her_mesh.path] = her_mesh
        a = StaticMeshActor(U, her_level, w["actor_name"], w["label"], her_mesh, rest, HER_SCALE[w["type"]])
        U.world.actors.append(a)
    decoy = StaticMeshActor(U, C.WORLD, "StaticMeshActor_10", "SM_S2_L_Wing_Shrine2", None, [0] * 6, [1, 1, 1])
    U.world.actors.append(decoy)                         # same object name in the PERSISTENT level: must be ignored
    res, probs = C.resolve_types({}, KIT_JSON["manifest_path"], KIT_JSON["pivot_path"], KIT_JSON["rzimport_plan_path"])
    assert not probs, probs
    key = {"L": "shrine_L", "R": "shrine_R", "C": "ceiling_C"}
    for t in C.TYPES:
        fb = KIT_JSON["pivot_path"]["wings"][key[t]]["our_front_slot_bounds_fbx_m"]     # FBX m -> UE cm (x, -y, z)
        ys = sorted([-fb[0][1] * 100.0, -fb[1][1] * 100.0])
        box = [[-15.0, ys[0], fb[0][2] * 100.0], [0.0, ys[1], fb[1][2] * 100.0]]
        U.assets[res[t]["mesh"]] = StaticMesh(res[t]["mesh"], box, ["Front", "Flap", "Timber", "Edge"])
        for mp in res[t]["variants"]["A"].values():
            U.assets[mp] = MaterialInterface(mp)                # B's MIs are NOT there yet (a later Unreal step)
    lvt = scene.add_track(U.MovieSceneLevelVisibilityTrack)
    lvt.name = C.LEVELS_TRACK
    lvs = lvt.add_section()
    lvs.set_range(104, 3891)
    lvs.level_names = ["Japanese_Alley"]
    os.makedirs(os.path.join(tmp, "Content", "InfinityStage", "Dev", "Sequences"), exist_ok=True)
    open(os.path.join(tmp, "Content", "InfinityStage", "Dev", "Sequences", "LS_DevScene_02.uasset"), "w").write("x")
    U.dirty_content.clear()
    args = json.load(open(os.path.join(HERE, "s2v3_overlay_args.json"), encoding="utf-8"))
    args.update(kit=dict(REAL_KIT), decided_by="harness")
    return U, args


def add_b_materials(U):
    res, _p = C.resolve_types({}, KIT_JSON["manifest_path"], KIT_JSON["pivot_path"], KIT_JSON["rzimport_plan_path"])
    for t in C.TYPES:
        for mp in res[t]["variants"]["B"].values():
            U.assets[mp] = MaterialInterface(mp)


def tool_for(U, tmp):
    sys.modules["unreal"] = U
    T = load("s2v3_tool_test_%d" % random.getrandbits(32), os.path.join(HERE, "s2v3_overlay.py"))
    here = os.path.join(tmp, "overlay")
    os.makedirs(here, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "s2v3_overlay_core.py"), here)
    T.HERE, T.PROJECT = here, tmp
    T.RECORD, T.ORIGINALS = os.path.join(here, "s2v3_overlay_record.json"), os.path.join(here, "s2v3_overlay_originals.json")
    T.CENSUS_JSON = os.path.join(S2K, "her_wings_census.json")
    return T


def run(T, U, args, mode, **kw):
    a = dict(args, mode=mode, confirm="%s %s" % (mode, C.CONFIRM_WORD), run="H-%s-%d" % (mode, len(U.logs)), **kw)
    T.S2V3OV_ARGS = a
    n0 = len(U.logs)
    try:
        T.main()
        err = None
    except Exception as exc:  # noqa: BLE001
        err = exc
    new = [m for _l, m in U.logs[n0:]]
    ok = [m for m in new if "_%s_OK|" % mode in m or "_RESYNC_NOOP|" in m]
    return a["run"], ok, new, err


def marker(new, key):
    return next((m for m in new if key in m), None)


def part_b():
    tmp = tempfile.mkdtemp(prefix="s2v3ov_")
    dirs = [tmp]

    def fresh(tag):
        d = tmp + "_" + tag
        dirs.append(d)
        U, args = build_env(d)
        return U, args, tool_for(U, d)

    try:
        U, args, T = fresh("1")
        scene = U.assets[C.SCENE_SEQ]
        fp_orig = T._fingerprint(T._core(), scene)

        r, ok, new, err = run(T, U, args, "DRY")
        dry = marker(new, "_DRY_OK|")
        check("B1+ DRY ok, apply_ready, mutated=0, census clean", dry and "apply_ready=True" in dry and
              not U.dirty_content and not U.dirty_maps, (err, new[-3:]))
        dry_name = "s2v3_overlay_dry_%s.json" % r
        dj = json.load(open(os.path.join(T.HERE, dry_name), encoding="utf-8"))
        check("B1+ DRY: coverage scene [104, 3891), pre-roll 261120 ticks, overlay playback [0, 4544)",
              dj["section"] == [104, 3891] and dj["coverage"]["pre_ticks"] == 261120 and
              dj["overlay_playback"] == [0, 4544], (dj["section"], dj["coverage"], dj["overlay_playback"]))
        check("B1+ DRY: her pre-section pose measured REST for all 15 (her saved actors sit at the rest pose)",
              all(w.get("pre_pose_measured") == "rest" and w.get("pre_pose") == "rest" for w in dj["wings"]))
        check("B1+ DRY records 15 source key hashes (z + all)", sum(1 for w in dj["wings"]
                                                                    if w.get("source_hashes", {}).get("z")) == 15)
        check("B1+ DRY: persistent-level decoy with the same object name ignored", all(
            w["her_actor_path"].startswith(C.HER_LEVEL) for w in dj["wings"]))
        worst = max(w["box_alignment"]["max_yz_cm"] for w in dj["wings"])
        check("B1+ DRY: REAL pivot offsets put our (FBX-measured) boxes on hers within 25 cm (max %.1f cm)" % worst,
              worst < 25.0, worst)
        check("B1+ DRY: variant B MIs not yet made -> WARNING only (A is being applied)",
              any(x.startswith("NOT_APPLIED_VARIANT_NOT_READY") for x in dj["warnings"]) and
              not any(".B|" in x for x in dj["refusals"]), dj["warnings"][:2])

        U.pie = True
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        check("B2- PIE running: APPLY refused, PIE NOT ended", err and "PIE_RUNNING" in str(err) and
              ("END_PIE",) not in U.calls and not U.dirty_content, err)
        U.pie = False
        U.seq_open = scene
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        check("B2- Sequencer open: refused", err and "SEQUENCER_OPEN" in str(err) and not U.dirty_content, err)
        U.seq_open = None
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name, coverage="cinematic", expected_coverage=None)
        check("B2- plan changed since DRY (coverage) refused before any write", err and "PLAN_CHANGED_SINCE_DRY" in
              str(err) and not U.dirty_content and not os.path.exists(T.RECORD), err)

        orig_add_hide = T._add_hide

        def evil_hide(Cm, ov, actor, rng):
            scene.bindings[-1].tracks[0].sections[0].channels[2].keys[1].value = 1.0   # 'S2 Hangar Root' Z key
            return orig_add_hide(Cm, ov, actor, rng)
        T._add_hide = evil_hide
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        T._add_hide = orig_add_hide
        check("B3- foreign edit during APPLY -> FINGERPRINT_VIOLATIONS, nothing saved, record -> .failed",
              err and "FINGERPRINT_VIOLATIONS" in str(err) and not U.saved and not os.path.exists(T.RECORD) and
              os.path.exists(T.RECORD + ".failed-" + r2), err)

        U, args, T = fresh("2")
        r, ok, new, err = run(T, U, args, "DRY")
        dry_name = "s2v3_overlay_dry_%s.json" % r
        orig_poss = Sequence.add_possessable

        def dirty_her(self, actor):
            U.dirty_maps.add(C.HER_LEVEL)
            return orig_poss(self, actor)
        Sequence.add_possessable = dirty_her
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        Sequence.add_possessable = orig_poss
        check("B4- Klara level dirtied during APPLY -> KLARA_PACKAGE_DIRTY, nothing saved",
              err and "KLARA_PACKAGE_DIRTY" in str(err) and not U.saved, err)

        U, args, T = fresh("3")
        scene = U.assets[C.SCENE_SEQ]
        fp_orig = T._fingerprint(T._core(), scene)
        r, ok, new, err = run(T, U, args, "DRY")
        dry_name = "s2v3_overlay_dry_%s.json" % r
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        check("B5+ APPLY ok (scene coverage)", bool(ok) and err is None, (err, new[-2:]))
        check("B5+ APPLY saved exactly [overlay, LS_DevScene_02] in that order, census clean",
              U.saved == [args["overlay_asset"], C.SCENE_SEQ] and not U.dirty_content and not U.dirty_maps, U.saved)
        check("B5+ APPLY never saved a map / her packages", ("SAVE_MAP",) not in U.calls and
              not any(C.is_klara_package(p) for p in U.saved))
        check("B5+ originals logged before any change", marker(new, "_ORIGINALS|") is not None)
        ov = U.assets[args["overlay_asset"]]
        tr = [t for t in scene.tracks if t.name == C.OVERLAY_TRACK]
        sec = tr[0].sections[0] if tr else None
        check("B5+ our track: 1 section [104, 3891), seq == overlay, child start maps to 104, end to 3890 (= hookin's)",
              len(tr) == 1 and [sec.start, sec.end] == [104, 3891] and sec.sequence is ov and
              U._parent_frame(sec, 0, scene) == 104 and U._parent_frame(sec, ov.pb[1], scene) == 3890,
              (sec and [sec.start, sec.end], ov.pb))
        hides = [b for b in ov.bindings if b.name.startswith(C.HIDE_PREFIX)]
        check("B5+ 15 hide bindings, bHidden, default False (=hidden), RESTORE_STATE, over the WHOLE overlay [0, 4544)",
              len(hides) == 15 and all(b.tracks[0].prop == "bHidden" and b.tracks[0].sections[0].channels[0].default
                                       is False and b.tracks[0].sections[0].completion.name == "RESTORE_STATE" and
                                       [b.tracks[0].sections[0].start, b.tracks[0].sections[0].end] == [0, 4544]
                                       for b in hides))
        ours = [b for b in ov.bindings if b.name.startswith(C.OURS_PREFIX)]
        spawn_ok = all(len([t for t in b.tracks if t._cls_name == "MovieSceneSpawnTrack"]) == 1 for b in ours)
        check("B5+ 15 spawnables, one spawn track each (UE's own reused), mobility MOVABLE, scale 1",
              len(ours) == 15 and spawn_ok and all(b.template.comp.props["mobility"].name == "MOVABLE" and
                                                   b.template.comp.props["relative_scale3d"].x == 1.0 for b in ours))
        lw = next(b for b in ours if b.name.endswith("SM_S2_L_Wing_Shrine2"))
        tch = [t for t in lw.tracks if t._cls_name == "MovieScene3DTransformTrack"][0].sections[0].channels
        her_b = next(b for b in U.assets[C.HOOKIN_COPY].bindings if b.name == "SM_S2_L_Wing_Shrine2")
        her_ch = her_b.tracks[0].sections[0].channels
        her_z, zch = her_ch[2], tch[2]
        check("B5+ hold key: tick 0, CONSTANT, Z = her REST height (789)",
              zch.keys[0].tick == 0 and zch.keys[0].interp == "RCIM_CONSTANT" and abs(zch.keys[0].value - 789.0) < 1e-6,
              (zch.keys[0].tick, zch.keys[0].interp, zch.keys[0].value))
        rowL = T._core().resolve_types({}, KIT_JSON["manifest_path"], KIT_JSON["pivot_path"],
                                       KIT_JSON["rzimport_plan_path"])[0]["L"]
        check("B5+ fall keys: LINEAR, first at her first key tick + 261120, fewer keys than samples",
              all(k.interp == "RCIM_LINEAR" for k in zch.keys[1:]) and zch.keys[1].tick == her_z.keys[0].tick + 261120
              and 2 < len(zch.keys) < 2260, len(zch.keys))
        her_rows = [[[k.tick, k.value, k.interp, "", k.arrive, k.leave] for k in her_ch[i].keys] for i in range(6)]
        ours_rows = [[[k.tick, k.value, k.interp, "", 0, 0] for k in tch[i].keys] for i in range(6)]
        worst = 0.0
        for t in range(0, 24000 * 17, 960):              # every PARENT (25 fps) frame of the fall, in her time
            her_pose = [fake_eval(her_rows[i], t) for i in range(6)]
            want = C.compose_pose(her_pose, rowL)
            got = [fake_eval(ours_rows[i], t + 261120) for i in range(6)]
            worst = max(worst, math.sqrt(sum((got[i] - want[i]) ** 2 for i in range(3))))
        check("B5+ at every 25 fps Scene frame our wing == her CUBIC wing (x) child transform within 0.5 cm (%.4f)"
              % worst, worst <= 0.5, worst)
        her_actor = next(a for a in U.world.actors if a.label == "SM_S2_L_Wing_Shrine2" and a.pkg == C.HER_LEVEL)
        exp = C.compose_pose(her_actor.pose, T._core().resolve_types({}, KIT_JSON["manifest_path"], KIT_JSON[
            "pivot_path"], KIT_JSON["rzimport_plan_path"])[0]["L"])
        got = [tch[i].keys[0].value for i in range(6)]
        check("B5+ hold pose == her actor pose (x) child transform (Her * T * RotZ180)", all(
            abs(got[i] - exp[i]) < 1e-6 for i in range(3)) and all(C.angle_diff(got[i], exp[i]) < 1e-6
                                                                    for i in (3, 4, 5)), (got, exp))
        mats = lw.template.comp.props["override_materials"]
        check("B5+ variant A: Front/Flap = kit MIs, Timber/Edge None (mesh defaults)",
              mats[0].path.endswith("MI_FlatV3_S2K_shrine_L_Front") and mats[1].path.endswith(
                  "MI_FlatV3_S2K_shrine_L_Flap") and mats[2:] == [None, None], mats)
        fp_now = T._fingerprint(T._core(), scene)
        check("B5+ LS_DevScene_02: every pre-existing row unchanged", T._core().fingerprint_diff(
            fp_orig, fp_now, T._core().our_track_prefix(fp_now)[0]) == [])

        r3, ok, new, err = run(T, U, args, "VERIFY")
        check("B6+ VERIFY ok after APPLY (a later call)", bool(ok) and err is None, (err, new[-2:]))
        hides[3].actor = U.world.actors[0] if U.world.actors[0] is not hides[3].actor else U.world.actors[1]
        r3, ok, new, err = run(T, U, args, "VERIFY")
        check("B6- VERIFY fails when a hide binding resolves to the wrong actor", marker(new, "_VERIFY_FAILED|") and
              "HIDE_RESOLVES" in marker(new, "_VERIFY_FAILED|"), new[-2:])
        hides[3].actor = next(a for a in U.world.actors if a.label == hides[3].name[len(C.HIDE_PREFIX):]
                              and a.pkg == C.HER_LEVEL)
        lvs = next(t for t in scene.tracks if t.name == C.LEVELS_TRACK).sections[0]
        lvs.start = 120
        r3, ok, new, err = run(T, U, args, "VERIFY")
        f = marker(new, "_VERIFY_FAILED|")
        lvs.start = 104
        check("B6- VERIFY fails when her level's visibility start moves (coverage no longer matches)",
              f is not None and ("SECTION_VS_LIVE_COVERAGE" in f or "PRE_ROLL_CHANGED" in f), new[-2:])

        nsave = len(U.saved)
        r4, ok, new, err = run(T, U, args, "VARIANT", variant="B")
        check("B7- VARIANT B before B's MIs exist: refused, nothing changed or saved",
              err and "VARIANT_NOT_READY" in str(err) and len(U.saved) == nsave and not U.dirty_content and
              lw.template.comp.props["override_materials"][0].path.endswith("_Front"), err)
        add_b_materials(U)
        r4, ok, new, err = run(T, U, args, "VARIANT", variant="B")
        mats = lw.template.comp.props["override_materials"]
        check("B7+ VARIANT B: only the overlay saved; Front/Flap = KlaraS2 LacqWet copies",
              bool(ok) and U.saved[-1] == args["overlay_asset"] and mats[0].path.endswith("_Front_LacqWet") and
              mats[1].path.endswith("_Flap_LacqWet") and mats[2:] == [None, None], (err, mats))
        r5, ok, new, err = run(T, U, args, "VERIFY", variant="B")
        check("B7+ VERIFY ok after VARIANT B", bool(ok) and err is None, (err, new[-2:]))

        nsave = len(U.saved)
        r6, ok, new, err = run(T, U, args, "RESYNC", variant="B")
        check("B8+ RESYNC with unchanged source -> NOOP, nothing saved", marker(new, "_RESYNC_NOOP|") and
              len(U.saved) == nsave, (err, new[-2:]))
        sha_before = json.load(open(T.RECORD, encoding="utf-8"))["wings"][1]["keys_sha"]
        her_z.keys[10].value += 37.0                    # simulate a re-ingest that changed her keys (saved on disk)
        r7, ok, new, err = run(T, U, args, "VERIFY", variant="B")
        f = marker(new, "_VERIFY_FAILED|")
        check("B8- VERIFY detects changed source keys (SOURCE_KEYS_CHANGED)", f and "SOURCE_KEYS_CHANGED" in json.dumps(
            json.load(open(os.path.join(T.HERE, "s2v3_overlay_verify_%s.json" % r7), encoding="utf-8"))["problems"]), f)
        r8, ok, new, err = run(T, U, args, "RESYNC", variant="B")
        check("B8+ RESYNC re-copies the changed wing only (hold key kept) and saves only the overlay",
              marker(new, "_RESYNC_OK|") and "SM_S2_L_Wing_Shrine2" in marker(new, "_RESYNC_OK|") and
              U.saved[-1] == args["overlay_asset"] and zch.keys[0].interp == "RCIM_CONSTANT" and
              json.load(open(T.RECORD, encoding="utf-8"))["wings"][1]["keys_sha"] != sha_before, (err, new[-2:]))
        r9, ok, new, err = run(T, U, args, "VERIFY", variant="B")
        check("B8+ VERIFY ok after RESYNC", bool(ok) and err is None, (err, new[-3:]))

        r10, ok, new, err = run(T, U, args, "REVERT")
        fp_back = T._fingerprint(T._core(), scene)
        check("B9+ REVERT: LS_DevScene_02 fingerprint == pre-APPLY exactly; only LS_DevScene_02 saved",
              bool(ok) and T._core().fingerprint_diff(fp_orig, fp_back) == [] and U.saved[-1] == C.SCENE_SEQ and
              not U.dirty_content, (err, T._core().fingerprint_diff(fp_orig, fp_back)[:2]))
        check("B9+ REVERT keeps the overlay asset (unreferenced) and renames the record",
              args["overlay_asset"] in U.assets and os.path.exists(T.RECORD + ".reverted-" + r10))
        r11, ok, new, err = run(T, U, args, "REVERT")
        check("B9- second REVERT refused (no applied record)", err and "NO_APPLIED_RECORD" in str(err), err)

        U, args, T = fresh("4")
        a4 = _copy.deepcopy(args)
        res, _p = C.resolve_types({}, KIT_JSON["manifest_path"], KIT_JSON["pivot_path"], KIT_JSON["rzimport_plan_path"])
        a4["types"]["L"]["pivot_offset_cm"] = [res["L"]["pivot_offset_cm"][0], -res["L"]["pivot_offset_cm"][1], 0.0]
        r, ok, new, err = run(T, U, a4, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B10- wrong pivot sign (args override) -> DRY apply_ready False, BOX_ALIGN for the 5 L wings",
              not dj["apply_ready"] and sum(x.startswith("BOX_ALIGN") for x in dj["refusals"]) == 5, dj["refusals"][:2])
        r2, ok, new, err = run(T, U, a4, "APPLY", dry_report="s2v3_overlay_dry_%s.json" % r)
        check("B10- ... and APPLY refuses (PLAN_REFUSED), nothing dirty", err and "PLAN_REFUSED" in str(err) and
              not U.dirty_content, err)

        U, args, T = fresh("5")
        a5 = dict(args, kit=dict(REAL_KIT, manifest_path=os.path.join(tmp, "no_such_manifest.json")))
        r, ok, new, err = run(T, U, a5, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B11- kit manifest missing: DRY completes, apply_ready False, KIT_FILE_MISSING named",
              marker(new, "_DRY_OK|") and not dj["apply_ready"] and any(x.startswith("KIT_FILE_MISSING")
                                                                         for x in dj["refusals"]), (err, dj["refusals"][:3]))

        U, args, T = fresh("6")
        a6 = next(a for a in U.world.actors if a.label == "SM_S2_ceiling_wing3" and a.pkg == C.HER_LEVEL)
        a6.pose = list(a6.pose)
        a6.pose[2] += 2500.0                             # an evaluated mid-fall pose left in the editor
        r, ok, new, err = run(T, U, args, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B12- her actor in a mid-fall pose -> PRE_POSE_UNCLEAR refusal (no guess)",
              not dj["apply_ready"] and any(x.startswith("PRE_POSE_UNCLEAR|SM_S2_ceiling_wing3") for x in dj["refusals"]),
              dj["refusals"][:2])
        r, ok, new, err = run(T, U, args, "DRY", pre_section_pose="rest")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B12+ ... forcing pre_section_pose=rest clears it, with a PRE_POSE_FORCED warning",
              dj["apply_ready"] and any(x.startswith("PRE_POSE_FORCED|SM_S2_ceiling_wing3") for x in dj["warnings"]),
              (dj["refusals"][:2], dj["warnings"][:2]))

        U, args, T = fresh("7")
        sc = U.assets[C.SCENE_SEQ]
        sc.tracks = [t for t in sc.tracks if t.name != C.LEVELS_TRACK]
        r, ok, new, err = run(T, U, args, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B13- no 'Klara Levels (hookin)' section -> scene coverage refused (LEVEL_VIS_SECTION_COUNT)",
              not dj["apply_ready"] and any("LEVEL_VIS_SECTION_COUNT" in x for x in dj["refusals"]), dj["refusals"][:3])

        U, args, T = fresh("9")
        U.range_trap = True
        r, ok, new, err = run(T, U, args, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B15- default-range trap (~1 value per channel) -> SAMPLE_COUNT refusal for every wing, no keys",
              not dj["apply_ready"] and sum(x.split("|")[1].startswith("SAMPLE_COUNT") for x in dj["refusals"]) == 15,
              dj["refusals"][:2])
        U.range_trap = False
        r, ok, new, err = run(T, U, args, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        smp = [w["sampling"] for w in dj["wings"]]
        check("B15+ DRY reports per-wing sampling: 150 fps, alignment 0 at every key, gate within 0.5 cm",
              dj["apply_ready"] and all(s_["rate"] == [150, 1] and s_["alignment"]["max_err"] < 1e-6 and
                                        s_["max_dev_cm"] <= 0.5 for s_ in smp),
              [(s_["keys"], s_["samples"], s_["max_dev_cm"]) for s_ in smp[:3]])

        U, args, T = fresh("8")
        a8 = dict(args, coverage="cinematic", expected_coverage=None)
        r, ok, new, err = run(T, U, a8, "DRY")
        r2, ok, new, err = run(T, U, a8, "APPLY", dry_report="s2v3_overlay_dry_%s.json" % r)
        if err:
            print("B14 APPLY error:", err)
        ov = U.assets.get(a8["overlay_asset"])
        sec = [t for t in U.assets[C.SCENE_SEQ].tracks if t.name == C.OVERLAY_TRACK]
        lw = next(b for b in ov.bindings if b.name == C.OURS_PREFIX + "SM_S2_L_Wing_Shrine2") if ov else None
        z0 = [t for t in lw.tracks if t._cls_name == "MovieScene3DTransformTrack"][0].sections[0].channels[2] if lw else None
        check("B14+ coverage=cinematic: section [376, 3891), playback = the copy's, no hold key (first key = sky)",
              bool(ok) and [sec[0].sections[0].start, sec[0].sections[0].end] == [376, 3891] and ov.pb == [0, 4217]
              and z0.keys[0].interp == "RCIM_LINEAR" and z0.keys[0].value > 4000, (err, new[-2:]))
        r3, ok, new, err = run(T, U, a8, "VERIFY")
        check("B14+ VERIFY ok (cinematic)", bool(ok) and err is None, (err, new[-2:]))
    except Exception:  # noqa: BLE001
        check("B harness crashed", False, traceback.format_exc())
    finally:
        sys.modules.pop("unreal", None)
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)


# ===================================================================================================== PART C
FORBIDDEN = ("save_map", "save_dirty_packages", "save_packages", "reload_packages", "get_bound_objects",
             "delete_asset", "request_end_play", "end_play_map", "save_all", "load_map", "open_level_sequence",
             "set_current_time", "play_in_editor")


def static_problems(src):
    tree = ast.parse(src)
    probs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN:
            probs.append("FORBIDDEN:%s@%d" % (node.attr, node.lineno))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for sub in ast.walk(node.value if node.value is not None else node):
                if isinstance(sub, ast.Name) and sub.id == "unreal":
                    probs.append("MODULE_LEVEL_UNREAL@%d" % node.lineno)
                    break
    return probs


def part_c():
    src = open(os.path.join(HERE, "s2v3_overlay.py"), encoding="utf-8").read()
    p = static_problems(src)
    check("C1+ tool: no forbidden calls, no module-level unreal objects", p == [], p)
    bad = src + "\nX = unreal.load_asset('/Game/x')\ndef f():\n    unreal.EditorLoadingAndSavingUtils.save_map(1, 2)\n"
    p2 = static_problems(bad)
    check("C1- checker flags an injected save_map and a module-level unreal object",
          any(x.startswith("FORBIDDEN:save_map") for x in p2) and any(x.startswith("MODULE_LEVEL") for x in p2), p2)
    core = open(os.path.join(HERE, "s2v3_overlay_core.py"), encoding="utf-8").read()
    check("C2+ core imports no unreal", "import unreal" not in core)
    run_src = open(os.path.join(HERE, "s2v3_overlay_run.py"), encoding="utf-8").read()
    check("C3+ runner purges the Saved module cache before running the tool",
          run_src.index("runpy.run_path(\"E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py") < run_src.rindex("s2v3_overlay.py"))
    req = json.load(open(os.path.join(HERE, "s2v3_overlay_request.json")))
    a = req["arguments"]
    check("C3+ request: MCPBlueprintsGenerator toolset / ExecuteProjectPythonFile / runner path",
          a["toolset_name"] == "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset" and
          a["tool_name"] == "ExecuteProjectPythonFile" and
          a["arguments"]["relativeSavedPath"] == "CodexFlatV3/s2klara/overlay/s2v3_overlay_run.py")


def main():
    for part in (part_a, part_a15, part_b, part_c):
        try:
            part()
        except Exception:  # noqa: BLE001
            check("%s crashed" % part.__name__, False, traceback.format_exc())
    n_ok = sum(r["ok"] for r in RESULTS)
    out = {"passed": n_ok, "failed": len(RESULTS) - n_ok, "results": RESULTS,
           "tier": "measured-offline against a FAKE unreal module; UE behaviour itself is not proven here"}
    json.dump(out, open(os.path.join(HERE, "test_s2v3_overlay_offline_report.json"), "w"), indent=1)
    print("TOTAL %d passed, %d failed" % (n_ok, len(RESULTS) - n_ok))
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
