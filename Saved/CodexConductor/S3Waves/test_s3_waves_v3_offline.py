"""Offline harness for the S3 waves v3 (B) tools.  Plain Python (no Unreal).  Every gate has a + control (passes on the
real plan) and a - control (a deliberately broken input that the gate MUST refuse) -- a gate that cannot fail is not a
gate (memory puss-assert-dont-print).

  python Saved/CodexConductor/S3Waves/test_s3_waves_v3_offline.py            -> test_s3_waves_v3_offline_report.json
Needs: B_build/build_report_B.json (the validated build), build_plan_B.json, s3_waves_v3_motion_plan.json.
Optional: B_build/hashes_run1.json + hashes_run2.json (two-build determinism) and the FlatV3 venv for the foam test.
"""
import copy
import importlib.util
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
B_BUILD = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Scene3", "waves_v3", "B_build")
RESULTS = []


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = load("s3wv3_core_test", "s3_waves_v3_core.py")


def check(name, cond, detail=""):
    RESULTS.append({"test": name, "pass": bool(cond), "detail": str(detail)[:400]})
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)[:300]))


def refuses(name, fn, needle):
    try:
        fn()
    except C.PlanError as exc:
        check(name, needle in str(exc), "refused with %s" % exc)
        return
    except Exception as exc:  # noqa: BLE001
        check(name, needle in str(exc), "raised %r" % exc)
        return
    check(name, False, "did NOT refuse (expected %s)" % needle)


def jload(p):
    with open(p, encoding="utf-8") as h:
        return json.load(h)


REPORT = jload(os.path.join(B_BUILD, "build_report_B.json"))
PLAN = jload(os.path.join(HERE, "build_plan_B.json"))
MOTION = jload(os.path.join(HERE, "s3_waves_v3_motion_plan.json"))
ROWS = C.piece_table(REPORT, PLAN)
LANDED = {"location": list(C.ROOT_LANDED_WORLD), "rotation": [0, 0, 0], "scale": [1, 1, 1]}
SEQ = {"fps": 24.0, "playback": [0, 6240], "strike": {"frame": 240}}


def apply_state(**over):
    split = [{"label": l, "count": 1, "parent": C.ROOT_LABEL, "tool_owned_v3": False, "object_path": "P." + l,
              "flags": {"actor_hidden": False, "comp_visible": True, "comp_hidden_in_game": False},
              "rise_visibility": []} for l in C.SPLIT_LABELS]
    st = {"root": {"world": copy.deepcopy(LANDED), "object_path": "P.Root"}, "split": split,
          "assets": {r["suffix"]: {"verified": True} for r in ROWS}, "label_count": {}, "temp_actors": []}
    st.update(over)
    return st


# ------------------------------------------------------------------------------------------------ modes
def t_modes():
    rec0 = {"apply": False, "motion": False, "light": False}
    check("mode+ DRY needs no confirm", C.check_mode({"mode": "DRY"}, False, rec0) == "DRY")
    refuses("mode- APPLY without confirm", lambda: C.check_mode({"mode": "APPLY"}, False, rec0), "CONFIRM_MISSING")
    check("mode+ IMPORT one piece", C.check_mode({"mode": "IMPORT", "confirm": "IMPORT S3WAVESV3",
                                                  "pieces": ["L1Breakers_P1"]}, False, rec0) == "IMPORT")
    refuses("mode- IMPORT two pieces in one call", lambda: C.check_mode(
        {"mode": "IMPORT", "confirm": "IMPORT S3WAVESV3", "pieces": ["L1Breakers_P1", "L1Breakers_P2"]}, False, rec0), "BATCH")
    refuses("mode- BUILD_MAT five pieces", lambda: C.check_mode(
        {"mode": "BUILD_MAT", "confirm": "BUILD_MAT S3WAVESV3", "pieces": ["a", "b", "c", "d", "e"]}, False, rec0), "BATCH")
    check("mode+ VERIFY allowed in PIE", C.check_mode({"mode": "VERIFY"}, True, rec0) == "VERIFY")
    refuses("mode- IMPORT refused in PIE", lambda: C.check_mode(
        {"mode": "IMPORT", "confirm": "IMPORT S3WAVESV3", "pieces": ["x"]}, True, rec0), "PIE_ACTIVE")
    refuses("mode- DRY refused in PIE (no editor world)", lambda: C.check_mode({"mode": "DRY"}, True, rec0), "PIE_ACTIVE")
    refuses("mode- APPLY twice", lambda: C.check_mode({"mode": "APPLY", "confirm": "APPLY S3WAVESV3"}, False,
                                                       dict(rec0, apply=True)), "ALREADY_APPLIED")
    refuses("mode- REVERT while motion keyed", lambda: C.check_mode({"mode": "REVERT", "confirm": "REVERT S3WAVESV3"},
                                                                     False, dict(rec0, apply=True, motion=True)),
            "MOTION_RECORD_PRESENT")
    check("mode+ REVERT after MOTION_REVERT", C.check_mode({"mode": "REVERT", "confirm": "REVERT S3WAVESV3"}, False,
                                                           dict(rec0, apply=True)) == "REVERT")
    refuses("mode- MOTION_APPLY before APPLY", lambda: C.check_mode(
        {"mode": "MOTION_APPLY", "confirm": "MOTION_APPLY S3WAVESV3"}, False, rec0), "NO_APPLY_RECORD")
    refuses("mode- LIGHT_REVERT without record", lambda: C.check_mode(
        {"mode": "LIGHT_REVERT", "confirm": "LIGHT_REVERT S3WAVESV3"}, False, rec0), "NO_LIGHT_RECORD")


# ------------------------------------------------------------------------------------------------ table + apply
def t_table():
    check("table+ 12 validated pieces", len(ROWS) == 12 and all(r["mesh"].startswith(C.ASSET_ROOT) for r in ROWS),
          [r["suffix"] for r in ROWS])
    names = [r["mesh"].rsplit("/", 1)[1] for r in ROWS]
    check("table+ NEW names SM_FlatV3_S3_WaveV3_*", all(n.startswith("SM_FlatV3_S3_WaveV3_") for n in names) and
          len(set(names)) == 12)
    bad = copy.deepcopy(REPORT)
    k = next(iter(bad["pieces"]))
    bad["pieces"][k]["mount_local"] = [0, 0, 0]
    refuses("table- mount drift between build and plan", lambda: C.piece_table(bad, PLAN), "MOUNT_DRIFT")
    bad2 = copy.deepcopy(REPORT)
    bad2["pieces"][k]["validation_pass"] = False
    refuses("table- unvalidated piece", lambda: C.piece_table(bad2, PLAN), "PIECE_NOT_BUILT")
    b = ROWS[0]["bounds_cm"]
    check("table+ UE bounds: front at x~-15.9, origin bottom-centre (y symmetric, z from 0)",
          abs(b["min"][2]) < 0.01 and abs(b["min"][1] + b["max"][1]) < 0.01 and -16.5 < b["min"][0] < -15.0, b)


def t_apply():
    plan = C.plan_apply(apply_state(), ROWS)
    check("apply+ 12 spawns, 9 hides, no reveal, map-only save", len(plan["spawns"]) == 12 and len(plan["hides"]) == 9
          and plan["reveal"]["mode"] == "none" and plan["content_saves"] == [])
    check("apply+ every spawn inside the wave guard (rest pose)",
          all(C.box_inside(s["local_box"], C.WAVE_GUARD_LOCAL) for s in plan["spawns"]))
    sunk = apply_state(root={"world": {"location": [11421.97, 160000, -3620], "rotation": [0, -90, 0], "scale": [1, 1, 1]}})
    refuses("apply- root not landed (sunk REST pose)", lambda: C.plan_apply(sunk, ROWS), "ROOT_NOT_LANDED")
    refuses("apply- label exists", lambda: C.plan_apply(apply_state(label_count={ROWS[0]["label"]: 1}), ROWS), "LABEL_EXISTS")
    st = apply_state()
    st["assets"][ROWS[3]["suffix"]]["verified"] = False
    refuses("apply- assets not verified", lambda: C.plan_apply(st, ROWS), "ASSETS_NOT_VERIFIED")
    st = apply_state()
    st["split"] = st["split"][:8]
    refuses("apply- only 8 split pieces", lambda: C.plan_apply(st, ROWS), "SPLIT_PIECES")
    refuses("apply- ZZ_ temp actor present", lambda: C.plan_apply(apply_state(temp_actors=["ZZ_TEMP_x"]), ROWS),
            "TEMP_ACTORS_PRESENT")
    rows = copy.deepcopy(ROWS)
    rows[0]["mount_local"][0] = 6200.0
    refuses("apply- piece outside the landed wave box", lambda: C.plan_apply(apply_state(), rows), "GUARD_LOCAL_BOX")
    sec = {"range_s": [0.0, 31.0], "completion_mode": "PROJECT_DEFAULT", "channels": 1, "keys": [[0, False], [139, True]],
           "fps": 30.0}
    st = apply_state()
    for s in st["split"]:
        s["rise_visibility"] = [dict(sec)]
    p2 = C.plan_apply(st, ROWS)
    check("reveal+ identical rise sections -> copy, rise saved", p2["reveal"]["mode"] == "copy" and
          p2["content_saves"] == [C.RISE])
    st["split"][4]["rise_visibility"] = []
    refuses("reveal- mixed (one split piece has none)", lambda: C.plan_apply(st, ROWS), "REVEAL_MIXED")
    st = apply_state()
    for i, s in enumerate(st["split"]):
        s["rise_visibility"] = [dict(sec, keys=[[0, False], [139 + i, True]])]
    refuses("reveal- sections differ", lambda: C.plan_apply(st, ROWS), "REVEAL_SECTIONS_DIFFER")
    st = apply_state()
    st["split"][0]["rise_visibility"] = "UNREAD"
    refuses("reveal- unreadable rise", lambda: C.plan_apply(st, ROWS), "REVEAL_UNREAD")
    # revert exactness on the world model
    world = {s["object_path"]: {"label": s["label"], "flags": dict(s["flags"])} for s in apply_state()["split"]}
    world["__bindings__"] = {}
    for reveal in ("none", "copy"):
        st = apply_state()
        if reveal == "copy":
            for s in st["split"]:
                s["rise_visibility"] = [dict(sec)]
        plan = C.plan_apply(st, ROWS)
        after = C.simulate(world, C.apply_ops(plan))
        rec = C.record_from_sim(plan)
        back = C.simulate(after, C.revert_ops(rec))
        check("revert+ exact (%s reveal): world identical after APPLY->REVERT" % reveal, back == world)
        check("apply+ changes the world (%s): 12 actors, 9 hidden" % reveal, len(after) == len(world) + 12 and
              all(after["P." + l]["flags"]["comp_visible"] is False for l in C.SPLIT_LABELS))
    drift = copy.deepcopy(after)
    del drift["NEW_" + ROWS[0]["label"]]
    refuses("revert- drift (an actor already gone) refuses", lambda: C.simulate(drift, C.revert_ops(rec)),
            "SIM_DESTROY_MISSING")


# ------------------------------------------------------------------------------------------------ motion
def t_motion():
    plan = C.plan_motion(SEQ, ROWS, MOTION)
    L5 = next(L for L in plan["layers"] if L["id"] == "L5_Rollers")
    check("motion+ L5 sway clamped 110 -> 100 cm", L5["sway_cm"] == 100.0 and L5["clamped_from"] == 110.0, L5)
    check("motion+ only L5 clamped", [L["id"] for L in plan["layers"] if L["clamped_from"]] == ["L5_Rollers"])
    check("motion+ overhang <= 200 cm", plan["worst"]["overhang_cm"] <= 200.0 + 1e-6, plan["worst"])
    refuses("motion- clamp off -> L5 overhang 210 refused", lambda: C.plan_motion(SEQ, ROWS, MOTION, clamp=False),
            "OVERHANG")
    pf = {L["id"]: L["period_s"] * 24 for L in plan["layers"]}
    check("motion+ every period divides the 720-frame vamp", all(720 % int(v) == 0 for v in pf.values()), pf)
    bad = copy.deepcopy(MOTION)
    bad["layers"][2]["period_s"] = 7.0
    refuses("motion- a 7 s period does not divide 30 s", lambda: C.plan_motion(SEQ, ROWS, bad), "PERIODS_DO_NOT_DIVIDE")
    refuses("motion- vamp moved off the divisible length", lambda: C.plan_motion(SEQ, ROWS, MOTION, vamp=(3480, 4190)),
            "PERIODS_DO_NOT_DIVIDE")
    f = plan["frames"]
    check("motion+ keys span strike-1 .. Scene end 6240 (past the 744 rise end)",
          f["first"] == 239 and f["last"] == 6240 and f["count"] == 2002, f)
    refuses("motion- Scene playback 0..744 (keys would end at 31 s)", lambda: C.plan_motion(
        dict(SEQ, playback=[0, 744]), ROWS, MOTION), "PLAYBACK")
    refuses("motion- strike not +10 s", lambda: C.plan_motion(dict(SEQ, strike={"frame": 300}), ROWS, MOTION), "STRIKE")
    check("motion+ vamp seam identical (< 1e-6 cm)", plan["worst"]["seam_cm"] < 1e-6, plan["worst"])
    check("motion+ P1/P2 never split (rigid layer)", plan["worst"]["split_cm"] < 1e-6, plan["worst"])
    check("motion+ skirt never lifts clear (< 20 cm)", plan["worst"]["skirt_lift_cm"] < 20.0, plan["worst"])
    k0 = plan["pieces"][0]["keys"]
    check("motion+ rest before the strike and smooth start (|dy| < 1 cm at strike+1 key)",
          k0[0]["location"] == ROWS[0]["mount_local"] or C.near(k0[0]["location"], ROWS[0]["mount_local"], 1e-9) and
          abs(k0[2]["location"][1] - ROWS[0]["mount_local"][1]) < 1.0, k0[:3])
    # - control for the split check: a piece rolling about its OWN origin (not the layer centre) must split
    orig = C.piece_key

    def naive(row, L, t):
        dy, dz, roll = C.layer_offsets(L, t)
        x, yc, z0 = row["mount_local"]
        return {"location": [x, yc + dy, z0 + dz], "rotation": [roll, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
    C.piece_key = naive
    try:
        refuses("motion- naive per-piece roll is caught (P1/P2 split)", lambda: C.plan_motion(SEQ, ROWS, MOTION),
                "P1_P2_SPLIT")
    finally:
        C.piece_key = orig
    # bob is down-only, two dips per sway
    L = plan["layers"][0]
    zs = [C.layer_offsets(L, t / 10.0)[1] for t in range(30, 300)]
    check("motion+ bob is down-only (dz <= 0)", max(zs) <= 1e-9 and min(zs) >= -L["bob_cm"] - 1e-9)
    fl = C.flicker_verdict({"a": {"foam": True, "lod0_flap_triangles": 30, "flap_r_range": [0.0, 1.0], "flutter_switch": True,
                                  "flutter_amp": 4.0, "lod1_screen_size": 0.3},
                            "b": {"foam": True, "lod0_flap_triangles": 30, "flap_r_range": [0.0, 1.0],
                                  "flutter_switch": False, "flutter_amp": 4.0, "lod1_screen_size": 0.3},
                            "c": {"foam": True, "lod0_flap_triangles": 0, "flap_r_range": None, "flutter_switch": True,
                                  "flutter_amp": 4.0, "lod1_screen_size": 0.3}})
    check("flicker+ live when Flap section + weights + switch + amp", fl["a"].startswith("LIVE"), fl)
    check("flicker- refused when the Flutter switch is off", fl["b"].startswith("REFUSED"), fl)
    check("flicker- refused with no Flap section", fl["c"].startswith("REFUSED"), fl)


# ------------------------------------------------------------------------------------------------ light
def light_state(**over):
    st = {"root": {"world": copy.deepcopy(LANDED)}, "fps": 24.0, "playback": [0, 6240], "strike": {"frame": 240},
          "rake": {"count": 1, "object_path": "P.Rake", "colour": {"use_temperature": True, "temperature": 5800.0},
                   "animated_properties": ["Intensity"]},
          "ehf": [], "label_count": {}, "local_fog_class": True}
    st.update(over)
    return st


def t_light():
    p = C.plan_light(light_state())
    check("light+ 6 ground rows + warm side", len(p["lights"]) == 7 and p["lights"][-1]["kind"] == "warm_side")
    check("light+ haze SPEC_ONLY without an ExponentialHeightFog in S3", p["haze"]["mode"] == "SPEC_ONLY", p["haze"])
    check("light+ rake retint only (temperature 5800 -> 7500, intensity untouched)",
          p["rake"]["after"]["temperature"] == 7500.0 and "UNCHANGED" in p["rake"]["intensity"])
    k = p["lights"][0]["keys"]
    check("light+ keys 0 -> strike -> ramp -> held to 6240 (whole Scene)",
          k[0] == [0, 0.0] and k[1] == [240, 0.0] and k[2][0] == 245 and k[-1][0] == 6240, k)
    refuses("light- Scene ends at 744 (rise boundary) refused", lambda: C.plan_light(light_state(playback=[0, 744])),
            "PLAYBACK")
    refuses("light- rake colour keyed somewhere", lambda: C.plan_light(light_state(rake={
        "count": 1, "object_path": "P", "colour": {}, "animated_properties": ["Intensity", "Temperature"]})),
        "RAKE_COLOUR_IS_KEYED")
    refuses("light- label already exists", lambda: C.plan_light(light_state(label_count={"S3 WaveV3 Warm Side": 1})),
            "LABEL_EXISTS")
    ph = C.plan_light(light_state(ehf=[{"label": "S3 Fog", "in_s3": True}]))
    sc = ph["haze"]["relative"]["scale"] if ph["haze"]["mode"] == "APPLY" else None
    check("haze+ APPLY with an EHF in S3: box -> scale (2.44, 1.99, 0.60)",
          ph["haze"]["mode"] == "APPLY" and C.near(sc, [2.44, 1.99, 0.6], 1e-6), ph["haze"])
    check("haze- an EHF outside S3 does not count", C.plan_light(light_state(ehf=[{"label": "Global Fog", "in_s3": False}]))
          ["haze"]["mode"] == "SPEC_ONLY")
    refuses("haze- EHF in S3 but no LocalFogVolume class", lambda: C.plan_light(light_state(
        ehf=[{"label": "S3 Fog", "in_s3": True}], local_fog_class=False)), "LOCAL_FOG_CLASS_MISSING")
    bands = [(3639, 3745), (4439, 4545), (5239, 5342)]                     # redesign s1 flat notch bands [inf there]
    xs = sorted(C.LAYER_X.values())
    ok = True
    for i, g in enumerate(p["lights"][:6]):
        x = g["location"][0]
        behind_p2 = x > xs[i] + 12.0                                       # P2 frame back ~ layer x + 15 - 3.2
        before_next = i == 5 or x < xs[i + 1] - 15.0                       # next layer's board front
        in_band = any(a <= x <= b for a, b in bands)
        ok = ok and behind_p2 and before_next and in_band and g["shadows"] is False
    check("ground rows+ behind each layer, in front of the next, inside the notch bands, shadows off", ok,
          [g["location"] for g in p["lights"][:6]])
    w = p["lights"][6]
    check("warm side+ left wall (y -980, inside the box), 3200 K", w["location"][1] == -980.0 and w["temperature_k"] == 3200.0)


# ------------------------------------------------------------------------------------------------ readiness
def t_ready():
    rep = {"written_mtime": 200.0, "pieces": {r["suffix"]: {"status": "READY"} for r in ROWS}}
    check("ready+ fresh complete VERIFY", C.verify_ready(rep, ROWS, 100.0) is True)
    refuses("ready- VERIFY older than the last IMPORT/BUILD_MAT", lambda: C.verify_ready(rep, ROWS, 300.0), "VERIFY_STALE")
    bad = copy.deepcopy(rep)
    bad["pieces"][ROWS[5]["suffix"]]["status"] = "INCOMPLETE"
    refuses("ready- one piece incomplete", lambda: C.verify_ready(bad, ROWS, 100.0), "PIECES_NOT_READY")
    refuses("ready- no VERIFY report", lambda: C.verify_ready(None, ROWS, 1.0), "NO_VERIFY_REPORT")


# ------------------------------------------------------------------------------------------------ static scan of the UE tool
def t_static():
    src = open(os.path.join(HERE, "s3_waves_v3_ue.py"), encoding="utf-8").read()
    compile(src, "s3_waves_v3_ue.py", "exec")
    names = sorted(set(re.findall(r"\bC\.([A-Za-z_][A-Za-z0-9_]*)", src)))
    missing = [n for n in names if not hasattr(C, n)]
    check("static+ every C.<name> the UE tool uses exists in the core", not missing, missing)
    fake = "x = C.NOT_A_REAL_NAME"
    fmiss = [n for n in re.findall(r"\bC\.([A-Za-z_][A-Za-z0-9_]*)", fake) if not hasattr(C, n)]
    check("static- the scan catches a missing name", fmiss == ["NOT_A_REAL_NAME"])
    ue = load("s3wv3_ue_offline", "s3_waves_v3_ue.py")
    check("static+ UE tool imports offline without running (unreal None)", ue.unreal is None and hasattr(ue, "main"))
    bad_globals = [l for l in src.splitlines() if re.match(r"^[A-Za-z_]+\s*=\s*unreal\.", l)]
    check("static+ no unreal object in a module global", not bad_globals, bad_globals)
    for needle, why in (("get_bound_objects", "never get_bound_objects"), ("reload_packages", "never reload the open world"),
                        ("delete_material_expression", "never delete material nodes")):
        check("static+ %s" % why, not re.search(r"\." + needle + r"\s*\(", src))
    check("static- the call scan sees a real call", bool(re.search(r"\.get_bound_objects\s*\(", "x.get_bound_objects(w)")))


# ------------------------------------------------------------------------------------------------ build-side
def t_build():
    h1, h2 = os.path.join(B_BUILD, "hashes_run1.json"), os.path.join(B_BUILD, "hashes_run2.json")
    if os.path.exists(h1) and os.path.exists(h2):
        a, b = jload(h1), jload(h2)
        n = sum(len(v) for v in a.values())
        check("determinism+ two builds byte-identical (%d deliverables, 12 pieces)" % n, a == b and len(a) == 12 and n >= 12 * 8,
              [k for k in a if a[k] != b.get(k)])
        neg = os.path.join(B_BUILD, "hashes_negative_seed.json")
        if os.path.exists(neg):
            c = jload(neg)
            k = "T_S3_WaveV3_L1Breakers_P1_SkinColor.png"
            check("determinism- a seed+1 skin differs (the gate can fail)", c.get(k) and c[k] != a["S3_WaveV3_L1Breakers_P1"][k])
    else:
        check("determinism (hash files present)", False, "run the two builds first")
    venv = r"D:\PussStageTools\FlatV3\venv\Scripts\python.exe"
    if os.path.exists(venv):
        code = r'''
import sys, json, cv2, numpy as np
sys.path.insert(0, r"%s")
import s3_waves_v3_B_build as B
f = B.PIECES / "S3_WaveV3_L1Breakers_P1"
m = cv2.imread(str(f / "mask.png"), 0); a = cv2.imread(str(f / "art.png"))
real = B.foam_flap_descriptors(m, a, 3.2768, [-1100.0, 52.3], [-277.7, 82.3], "X")
inside = all(m[min(m.shape[0]-1, int(round((1-v)*m.shape[0]))) , min(m.shape[1]-1, int(u*m.shape[1]))] > 127
             for fl in real for u, v in fl["outline_uv_bottom_left"][:-2])
syn_m = np.zeros((300, 1000), np.uint8); syn_m[100:, :] = 255; syn_m[110:200, :] = 0    # crest lip over an open mouth
syn_a = np.full((300, 1000, 3), 230, np.uint8)
mouth = B.foam_flap_descriptors(syn_m, syn_a, 3.2768, [0.0, 305.0], None, "S")
syn_m2 = syn_m.copy(); syn_m2[110:200, :] = 255
solid = B.foam_flap_descriptors(syn_m2, syn_a, 3.2768, [0.0, 305.0], None, "S")
fl = json.load(open(f / "S3_WaveV3_L1Breakers_P1_flaps_v3.json"))["flaps"]
print(json.dumps({"real": len(real), "inside": inside, "mouth": len(mouth), "solid": len(solid), "merged": len(fl),
                  "foam_in_file": sum(1 for x in fl if x.get("kind") == "foam_crest")}))
''' % HERE
        r = subprocess.run([venv, "-c", code], capture_output=True, text=True, cwd=PROJECT)
        try:
            d = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            check("foam flaps (venv run)", False, r.stdout[-300:] + r.stderr[-600:])
            return
        check("foam+ L1 P1 gets 3 crest flaps, outlines on paint", d["real"] == 3 and d["inside"], d)
        check("foam+ built flaps file = 3 peel + 3 foam (create_flaps 3..6)", d["merged"] == 6 and d["foam_in_file"] == 3, d)
        check("foam- a crest over an open curl mouth gets NO flap", d["mouth"] == 0, d)
        check("foam+ the same crest made solid does get flaps (control)", d["solid"] >= 1, d)
    tm = REPORT.get("texture_memory", {})
    check("textures+ every texture <= 4096 px", tm and all(r["max_dim_ok"] for r in tm["pieces"]), tm.get("pieces", [])[:2])
    check("textures+ total GPU memory reported", tm.get("total_gpu_mb", 0) > 0, tm.get("total_gpu_mb"))


def main():
    for t in (t_modes, t_table, t_apply, t_motion, t_light, t_ready, t_static, t_build):
        try:
            t()
        except Exception as exc:  # noqa: BLE001
            check("%s crashed" % t.__name__, False, repr(exc))
    n_fail = sum(1 for r in RESULTS if not r["pass"])
    out = {"total": len(RESULTS), "failed": n_fail, "results": RESULTS}
    with open(os.path.join(HERE, "test_s3_waves_v3_offline_report.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    print("S3WAVESV3_OFFLINE_%s %d/%d" % ("PASS" if not n_fail else "FAIL", len(RESULTS) - n_fail, len(RESULTS)))
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
