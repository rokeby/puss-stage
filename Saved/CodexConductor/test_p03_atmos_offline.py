"""Offline harness for p03_atmos.py (no Unreal). Every property has a + case and a - control that must FAIL (or
raise), so each check is shown able to fail. Real data: lighting_scores_record_P03.json after_rows (21 P03 cues,
6 Oct 02:34 saved_readback_verified). Run: python Saved/CodexConductor/test_p03_atmos_offline.py"""
import ast
import copy
import json
import math
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p03_atmos as A  # noqa: E402
import beam_texture_bench as btb  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def raises(fn, token=None):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        return token is None or token in str(exc)
    return False


P = A.check_params({})

# ---------------------------------------------------------------- fixture: the live P03 Show rows of 6 Oct
REC = json.loads((HERE / "lighting_scores_record_P03.json").read_text(encoding="utf-8"))
CUES = []
for t in REC["plan"]["targets"]:
    CUES.append({"guid": t["cue_guid"], "label": t["cue_label"], "show_index": t["show_index"],
                 "attachments": copy.deepcopy(t["after_rows"])})
FOREIGN = {"guid": "F" * 32, "label": "P01 Wing 001", "show_index": 3,
           "attachments": [copy.deepcopy(CUES[0]["attachments"][0])]}
FOREIGN["attachments"][0]["guid"] = "E" * 32
FOREIGN["attachments"][0]["label"] = "P01 SCORE B01 P01_WARM_THEATRICAL BEAM_R"
PLAIN = {"cues": CUES + [FOREIGN], "bay_guids": [c["guid"] for c in CUES], "passage_guid": "X"}
ALL = {c["guid"]: c["attachments"] for c in PLAIN["cues"]}

# ---------------------------------------------------------------- A. params / args
check("params: defaults valid", P["vs_scale"] == 0.5 and P["beam_vs_scale"] == 1.0 and P["lfv_extinction_scale"] == 0.35)
check("params -: vs_scale 1.5 refused (tool only reduces)", raises(lambda: A.check_params({"vs_scale": 1.5}), "PARAM_SCALE"))
check("params -: unknown key refused", raises(lambda: A.check_params({"vs_scal": 0.5}), "PARAMS_UNKNOWN"))
check("params -: smoke drift 0 refused", raises(lambda: A.check_params({"smoke_drift_cm_s": 0.0}), "PARAM_SMOKE_DRIFT"))
check("params -: bad gobo value refused (btb validator)", raises(lambda: A.check_params({"g_floor": 0.0}), "PARAM_GOBO_VALUES"))
check("args: DRY needs no confirm", A.check_args({"mode": "DRY"})["mode"] == "DRY")
check("args -: APPLY without confirm refused", raises(lambda: A.check_args({"mode": "APPLY"}), "CONFIRM_MISSING"))
check("args: APPLY with confirm ok", A.check_args({"mode": "APPLY", "confirm": "APPLY P03ATMOS"})["mode"] == "APPLY")
check("args -: REVERT with APPLY token refused",
      raises(lambda: A.check_args({"mode": "REVERT", "confirm": "APPLY P03ATMOS"}), "CONFIRM_MISSING"))
DRY_ARGS = json.loads((HERE / "p03_atmos_args.json").read_text(encoding="utf-8"))
check("args file: DRY and valid", DRY_ARGS["mode"] == "DRY" and A.check_args(DRY_ARGS)["mode"] == "DRY")
REQ = json.loads((HERE / "p03_atmos_request.json").read_text(encoding="utf-8"))
check("request: ExecuteProjectPythonFile p03_atmos_run.py",
      REQ["arguments"]["tool_name"] == "ExecuteProjectPythonFile"
      and REQ["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/p03_atmos_run.py")

# ---------------------------------------------------------------- B. fog plan (VS + medium)
fog, untouched = A.plan_fog(PLAIN, P)
beams = A.beam_rows(PLAIN, P)
lights = [r for c in CUES for r in c["attachments"] if A._enum_name(r["kind"]) == "LIGHT"]
enabled_nonbeam = [r for r in lights if r["enabled"] and not A.beam_regex(P).match(r["label"])
                   and r["lighting"]["volumetric_scattering_intensity"] > 0]
check("beams: 4 P03 BEAM_R (B04 B08 B13 B18)", [b["bay"] for b in beams] == [4, 8, 13, 18])
check("fog: every enabled non-beam light with VS>0 targeted", len(fog) == len(enabled_nonbeam) and len(fog) > 0)
check("fog: all targets x0.5", all(abs(t["after"] - 0.5 * t["before"]) < 1e-12 for t in fog))
check("fog: no beam targeted (beams kept at 1.0)", not any(t.get("beam") for t in fog)
      and sum(1 for u in untouched if u["why"] == "BEAM_KEPT") == 4)
check("fog: no disabled light targeted", not any(not r["enabled"] for c in CUES for r in c["attachments"]
                                                 if r["guid"] in {t["attachment_guid"] for t in fog}))
check("fog: foreign P01 cue never targeted", all(t["cue_guid"] != FOREIGN["guid"] for t in fog))
fog_b, _u = A.plan_fog(PLAIN, A.check_params({"beam_vs_scale": 0.8}))
check("fog -control: beam_vs_scale 0.8 does target the 4 beams", sum(1 for t in fog_b if t.get("beam")) == 4)
fog_d, _u = A.plan_fog(PLAIN, A.check_params({"vs_enabled_only": False}))
check("fog -control: vs_enabled_only False targets disabled lights too", len(fog_d) > len(fog))
check("fog: no EFFECT rows in P03 (record) -> 0 medium targets", sum(1 for t in fog if t["kind"] == "medium") == 0)
eff_plain = copy.deepcopy(PLAIN)
eff_row = eff_plain["cues"][0]["attachments"][0]
eff_row["kind"] = "<InfinityAttachmentKind.EFFECT: 3>"
eff_row["effect"]["feeds_local_medium"] = True
eff_row["effect"]["medium_density"] = 0.25
fog_e, _u = A.plan_fog(eff_plain, P)
med = [t for t in fog_e if t["kind"] == "medium"]
check("fog: a feeding EFFECT row gets medium_density x0.35", len(med) == 1 and abs(med[0]["after"] - 0.0875) < 1e-12)
eff_row["effect"]["feeds_local_medium"] = False
check("fog -control: a non-feeding EFFECT row is not targeted",
      not [t for t in A.plan_fog(eff_plain, P)[0] if t["kind"] == "medium"])
bad_plain = copy.deepcopy(PLAIN)
bad_plain["bay_guids"].append(FOREIGN["guid"])
check("fog -: a P01 cue among the bays refused", raises(lambda: A.plan_fog(bad_plain, P), "BAY_NOT_P03"))

# ---------------------------------------------------------------- C. beam light function plan
BREATH = {"Speed": 0.45, "SpeedRatio": 1.23, "Depth": 0.5, "Phase": 2.1, "Hardness": 0.15, "OnBias": 0.5}
BREATH_PATH = "/Game/InfinityStage/Lighting/MI_LF_Flicker_Breath.MI_LF_Flicker_Breath"
LIVE = {BREATH_PATH: {"parent": A.FLICKER_PARENT, "params": dict(BREATH)}}
lf_t, mi, lf_rows, lf_w = A.plan_lf(beams, LIVE, P)
mats = {t["attachment_label"].split()[2]: t["after"] for t in lf_t if t["path"] == A.F_LF}
check("lf: B04 (no LF) -> M_LF_SoftSlats", mats.get("B04") == A.obj_path(A.MAT_SLATS))
check("lf: B08/B13/B18 (Breath) -> MI_LF_SoftSlats_Breath",
      all(mats.get(b) == A.obj_path(A.ASSET_DIR + "/MI_LF_SoftSlats_Breath") for b in ("B08", "B13", "B18")))
check("lf: one MI spec, parent the flicker slats, live Breath params",
      list(mi) == [A.ASSET_DIR + "/MI_LF_SoftSlats_Breath"] and mi[A.ASSET_DIR + "/MI_LF_SoftSlats_Breath"]["parent"]
      == A.MAT_SLATS_FLK and mi[A.ASSET_DIR + "/MI_LF_SoftSlats_Breath"]["params"] == BREATH)
check("lf: disabled brightness 0 -> 0.6 on all 4", sum(1 for t in lf_t if t["path"] == A.F_LF_DB) == 4
      and all(t["after"] == 0.6 for t in lf_t if t["path"] == A.F_LF_DB))
check("lf: scale untouched when lf_scale None", not [t for t in lf_t if t["path"] == A.F_LF_SCALE])
lf_s, _m, _r, _w = A.plan_lf(beams, LIVE, A.check_params({"lf_scale": [2.0, 1.0, 1.0]}))
check("lf -control: lf_scale given writes 4 scale targets", sum(1 for t in lf_s if t["path"] == A.F_LF_SCALE) == 4)
lf_r, mi_r, _r, w_r = A.plan_lf(beams, LIVE, A.check_params({"lf_conflict": "replace"}))
check("lf replace: 4 base materials, 0 MIs, 3 FLICKER_DROPPED warnings",
      sum(1 for t in lf_r if t["path"] == A.F_LF and t["after"] == A.obj_path(A.MAT_SLATS)) == 4 and not mi_r
      and sum(1 for w in w_r if w.startswith("LF_FLICKER_DROPPED")) == 3)
lf_k, mi_k, _r, w_k = A.plan_lf(beams, LIVE, A.check_params({"lf_conflict": "skip"}))
check("lf skip: only B04 written", {t["attachment_label"].split()[2] for t in lf_k} == {"B04"} and len(w_k) == 3)
lf_x, mi_x, rows_x, w_x = A.plan_lf(beams, {}, P)
check("lf -control: flicker not read live -> the 3 are SKIPPED, not guessed",
      {t["attachment_label"].split()[2] for t in lf_x} == {"B04"} and not mi_x
      and sum(1 for w in w_x if w.startswith("LF_NOT_STAGEFLICKER")) == 3)
lf_g, _m, _r, _w = A.plan_lf(beams, LIVE, A.check_params({"gobo": "soft"}))
check("lf gobo soft: B04 -> M_LF_SoftGobo, MI_LF_SoftGobo_Breath",
      any(t["after"] == A.obj_path(A.MAT_GOBO) for t in lf_g)
      and any(t["after"] == A.obj_path(A.ASSET_DIR + "/MI_LF_SoftGobo_Breath") for t in lf_g))
conflict_beams = copy.deepcopy(beams)
conflict_live = dict(LIVE)
other = "/Game/InfinityStage/Lighting/Other/MI_LF_Flicker_Breath.MI_LF_Flicker_Breath"
conflict_beams[1]["row"]["lighting"]["light_function_material"] = other
conflict_live[other] = {"parent": A.FLICKER_PARENT, "params": dict(BREATH, Speed=0.9)}
check("lf -: same profile name with different params refused",
      raises(lambda: A.plan_lf(conflict_beams, conflict_live, P), "FLICKER_PROFILE_CONFLICT"))
done = copy.deepcopy(beams)
for b in done:
    b["row"]["lighting"]["light_function_material"] = A.obj_path(A.ASSET_DIR + "/MI_LF_SoftSlats_Breath")
check("lf: idempotent (already BeamLook -> no target)", not A.plan_lf(done, LIVE, P)[0])

# ---------------------------------------------------------------- D. assets
assets = A.asset_plan(P, mi, True, 12.5)
paths = [a["path"] for a in assets]
check("assets: production set under BeamLook, materials before instances",
      paths == [A.MAT_SLATS, A.MAT_GOBO, A.MAT_SLATS_FLK, A.ASSET_DIR + "/MI_LF_SoftSlats_Breath", A.MAT_NOISE,
                A.MAT_SMOKE, A.MI_SMOKE])
check("assets: smoke MI carries FloorZ + drift",
      assets[-1]["params"]["FloorZ"] == 12.5 and assets[-1]["params"]["Drift"] == P["smoke_drift_cm_s"])
check("assets: no flicker parent when no MI needs it", A.MAT_SLATS_FLK not in [a["path"] for a in A.asset_plan(P, {}, False)])
check("assets -: an MI whose parent is not created first refused", raises(lambda: A.asset_plan(P, mi, False), "ASSET_ORDER"))
check("assets: smoke off -> no smoke assets", A.MAT_SMOKE not in
      [a["path"] for a in A.asset_plan(A.check_params({"smoke": False}), {}, False)])

# ---------------------------------------------------------------- E. material code
gs = A.graph_spec("gobo_slats", P)
check("code: slats graph IS the bench's code", gs["code"] is btb.CODE_GOBO_SLATS and gs["inputs"] == btb.GOBO_SLATS_INPUTS)
check("code: slats baked with the good run (count 3, soft 0.2, floor 0.2, axis u)",
      gs["params"]["Count"][1] == 3.0 and gs["params"]["Soft"][1] == 0.2 and gs["params"]["FloorV"][1] == 0.2
      and gs["params"]["Axis"][1] == 0.0)
check("code: soft gobo IS the bench's code (contrast 3.5)", A.graph_spec("gobo_soft", P)["code"] is btb.CODE_GOBO_SOFT
      and A.graph_spec("gobo_soft", P)["params"]["Contrast"][1] == 3.5)
gn = A.graph_spec("noise", P)
check("code: noise IS CODE_NOISE3 with peak 0.12, 60 cm, contrast 3, floor 0.05",
      gn["code"] is btb.CODE_NOISE3 and gn["params"]["Peak"][1] == 0.12 and gn["params"]["NoiseCm"][1] == 60.0
      and gn["params"]["Contrast"][1] == 3.0 and gn["params"]["FloorFrac"][1] == 0.05)
gf = A.graph_spec("gobo_slats_flicker", P)
check("code: flicker variant = bench code minus its return + flicker + 'return g * fl'",
      gf["code"].startswith(btb.CODE_GOBO_SLATS.rstrip()[:-len(A.GOBO_RETURN)]) and gf["code"].rstrip().endswith("return g * fl;")
      and set(A.FLICKER_PIN) <= set(gf["inputs"]) and gf["params"]["FDepth"] == ("Depth", 0.0))
sm = A.graph_spec("smoke", P)
check("code: smoke = CODE_NOISE3 minus its return + the height fade",
      sm["code"].startswith(btb.CODE_NOISE3.rstrip()[:-len(A.NOISE_RETURN)]) and "pow(1.0 - hgt" in sm["code"])
check("code -: a code without the expected return refused", raises(lambda: A.with_flicker("return 1.0;"), "CODE_RETURN_SHAPE"))
for k in ("gobo_slats", "gobo_soft", "gobo_slats_flicker", "noise", "smoke"):
    g = A.graph_spec(k, P)
    check("code: %s every param pin is a Custom input" % k, set(g["params"]) <= set(g["inputs"]))
# the flicker mirror against lighting_scores_apply.lf_level (the scores tool's model of M_LF_StageFlicker)
try:
    import lighting_scores_apply as lsa  # unreal None -> no main()
    lf_level = lsa.lf_level
except Exception as exc:  # noqa: BLE001
    lf_level = None
    print("note: lighting_scores_apply not importable offline: %s" % exc)
profiles = {"Slow": (0.2, 1.31, 0.45, 0.7, 0.0, 0.5), "Breath": (0.45, 1.23, 0.5, 2.1, 0.15, 0.5),
            "Hum": (8.0, 1.9, 0.3, 4.4, 0.3, 0.5), "Fault": (0.8, 1.43, 1.0, 3.8, 1.0, 0.45)}   # rebuild_flicker_master.py:40-47
if lf_level is not None:
    worst = 0.0
    for prof in profiles.values():
        pr = dict(zip(A.FLICKER_PARAMS, prof))
        for i in range(400):
            worst = max(worst, abs(A.flicker_level(i * 0.037, pr) - lf_level(i * 0.037, pr)))
    check("flicker mirror == lighting_scores_apply.lf_level (4 profiles x 400 t)", worst < 1e-6)
    pr = dict(zip(A.FLICKER_PARAMS, profiles["Breath"]))
    shifted = dict(pr, Phase=pr["Phase"] + 0.3)
    check("flicker -control: a shifted phase differs",
          max(abs(A.flicker_level(i * 0.037, shifted) - lf_level(i * 0.037, pr)) for i in range(400)) > 1e-2)
check("flicker: steady params -> 1.0 everywhere", all(abs(A.flicker_level(t * 0.1, A.FLICKER_STEADY) - 1.0) < 1e-12
                                                      for t in range(200)))
check("flicker: Breath dips (min < 0.6) and peaks 1.0", min(A.flicker_level(t * 0.01, BREATH) for t in range(2000)) < 0.6
      and max(A.flicker_level(t * 0.01, BREATH) for t in range(2000)) > 0.999)
sp = A.smoke_material_params(P, 100.0)
base_np = {"b_drift_cm_s": sp["Drift"], "b_noise_cm": sp["NoiseCm"], "b_noise_contrast": sp["Contrast"],
           "b_extinction_peak": sp["Peak"], "b_noise_floor": sp["FloorFrac"]}
pts = [(37.0 * i, 11.0 * i, 100.0) for i in range(50)]
check("smoke ref: at the floor = the bench noise", all(abs(A.smoke_reference(w, 1.0, sp) - btb.noise3_reference(w, 1.0, base_np))
                                                       < 1e-12 for w in pts))
check("smoke ref: at floor + HeightCm = 0", all(A.smoke_reference((w[0], w[1], 100.0 + sp["HeightCm"]), 1.0, sp) == 0.0
                                                for w in pts))
mid = [A.smoke_reference((w[0], w[1], 100.0 + 0.5 * sp["HeightCm"]), 1.0, sp) for w in pts]
full = [btb.noise3_reference((w[0], w[1], 100.0 + 0.5 * sp["HeightCm"]), 1.0, base_np) for w in pts]
check("smoke ref: half height = (0.5)^1.5 of the noise there", all(abs(m - f * 0.5 ** 1.5) < 1e-12 for m, f in zip(mid, full)))
check("smoke ref -control: drift moves the pattern", any(abs(A.smoke_reference(w, 0.0, sp) - A.smoke_reference(w, 3.0, sp)) > 1e-4
                                                         for w in pts))

# ---------------------------------------------------------------- F. rows model, scope, drift (record / revert maths)
targets = fog + lf_t
A.check_targets(targets)
after_all = A.apply_rows(ALL, targets, "after")
back = A.apply_rows(after_all, targets, "before")
check("model: after -> before round trip is exact", back == ALL)
check("model: scope after == []", A.scope_problems(ALL, after_all, targets, "after") == [])
check("model: scope before on the base == []", A.scope_problems(ALL, ALL, targets, "before") == [])
f32 = copy.deepcopy(after_all)
t0 = fog[0]
[r for r in f32[t0["cue_guid"]] if r["guid"] == t0["attachment_guid"]][0]["lighting"][
    "volumetric_scattering_intensity"] = t0["after"] * (1 + 3e-8)
check("model: a float32 round trip of a written value is accepted", A.scope_problems(ALL, f32, targets, "after") == [])
extra = copy.deepcopy(after_all)
[r for r in extra[t0["cue_guid"]] if r["guid"] == t0["attachment_guid"]][0]["lighting"]["intensity"] += 1.0
check("model -: an extra change on a target row is caught", A.scope_problems(ALL, extra, targets, "after") != [])
wrong = copy.deepcopy(after_all)
[r for r in wrong[t0["cue_guid"]] if r["guid"] == t0["attachment_guid"]][0]["lighting"][
    "volumetric_scattering_intensity"] = t0["before"]
check("model -: a target left at its before value is caught", A.scope_problems(ALL, wrong, targets, "after") != [])
outside = copy.deepcopy(after_all)
outside[FOREIGN["guid"]][0]["enabled"] = not outside[FOREIGN["guid"]][0]["enabled"]
check("model -: a change outside the target cues is caught", A.scope_problems(ALL, outside, targets, "after") != [])
reorder = copy.deepcopy(after_all)
reorder[t0["cue_guid"]].reverse()
check("model -: reordered rows caught", A.scope_problems(ALL, reorder, targets, "after") != [])
check("drift: none on the after state", A.field_drifts(after_all, targets, "after") == [])
check("drift -: every field drifts on the before state", len(A.field_drifts(ALL, targets, "after")) == len(targets))
check("targets -: duplicate field refused", raises(lambda: A.check_targets(targets + [targets[0]]), "TARGET_FIELD_DUPLICATE"))
check("targets -: a non-writable path refused",
      raises(lambda: A.check_targets([dict(targets[0], path="lighting.intensity")]), "NOT_WRITABLE"))
lf_only = [t for t in lf_t if t["path"] == A.F_LF]
lf_after = A.apply_rows(ALL, lf_only, "after")
check("model: LF None -> path -> None round trip", A.apply_rows(lf_after, lf_only, "before") == ALL
      and [r for r in lf_after[beams[0]["cue"]["guid"]] if r["guid"] == beams[0]["row"]["guid"]][0]["lighting"][
          "light_function_material"] == A.obj_path(A.MAT_SLATS))

# ---------------------------------------------------------------- G. LFVs
BOX = A.footprint([(0.0, 0.0, 0.0), (10000.0, 500.0, 300.0)], 1500.0)
lfvs = [{"id": "a", "label": "LFV_in", "loc": [5000.0, 0.0, 100.0], "radial_fog_extinction": 0.4, "height_fog_extinction": 0.2},
        {"id": "b", "label": "LFV_out", "loc": [5000.0, 9000.0, 100.0], "radial_fog_extinction": 0.4, "height_fog_extinction": 0.0},
        {"id": "c", "label": "ZZ_P02FOG_MIST_0", "loc": [5000.0, 0.0, 100.0], "radial_fog_extinction": 0.4,
         "height_fog_extinction": 0.4}]
lt, lo = A.plan_lfv(lfvs, BOX, P)
check("lfv: only the inside, non-ZZ volume, both non-zero fields x0.35",
      [(t["id"], t["field"]) for t in lt] == [("a", "radial_fog_extinction"), ("a", "height_fog_extinction")]
      and abs(lt[0]["after"] - 0.14) < 1e-12)
check("lfv -control: outside + ZZ listed as untouched", sorted(o["why"] for o in lo) == ["OUTSIDE", "ZZ_BENCH"])
live_after = {(t["id"], t["field"]): t["after"] for t in lt}
check("lfv drift: none at after", A.lfv_drifts(live_after, lt) == [])
check("lfv drift -: before values drift", len(A.lfv_drifts({k: v / 0.35 for k, v in live_after.items()}, lt)) == 2)

# ---------------------------------------------------------------- H. geometry
BEAM = {"label": "P03 SCORE B04 P03_STIFF_BRIGHT_SIDES BEAM_R", "bay": 4, "show_index": 79,
        "location": [1000.0, 200.0, 450.0], "rotation": {"roll": 0.0, "pitch": -10.0, "yaw": 90.0},
        "outer_cone_deg": 7.0, "attenuation_cm": 2600.0}
nb = A.noise_box_spec(BEAM, P)
u = btb.beam_axis(BEAM["rotation"])
want_mid = btb.vadd(BEAM["location"], btb.vmul(u, 0.5 * (60.0 + 1200.0)))
check("noise box: centre on the beam axis at mid-span", math.dist(nb["loc"], want_mid) < 1e-3)
check("noise box: length 11.4 m, side 2 x (1200 tan 7 + 80)",
      abs(nb["scale"][0] - 11.4) < 1e-9 and abs(nb["side_cm"] - 2 * (1200 * math.tan(math.radians(7)) + 80)) < 1e-9)
check("noise box: aligned to the beam (pitch -10, yaw 90)",
      abs(nb["rot"]["pitch"] + 10.0) < 1e-9 and abs(nb["rot"]["yaw"] - 90.0) < 1e-9)
check("noise box: label/tags", nb["label"] == "P03 BeamLook Noise B04" and nb["tags"] == [A.BEAMLOOK_TAG, A.ACTOR_TAG])
check("noise box: span clipped by attenuation", A.noise_box_spec(dict(BEAM, attenuation_cm=800.0), P)["s1"] == 800.0)
check("noise box -: attenuation inside the start refused",
      raises(lambda: A.noise_box_spec(dict(BEAM, attenuation_cm=50.0), P), "NOISE_SPAN_EMPTY"))
sb = A.smoke_box_spec(1, BEAM, 0.5, P)
check("smoke box: bottom = floor - sink, 1.2 m tall", abs(sb["bottom_z"] - (0.5 - 10.0)) < 1e-9
      and abs(sb["top_z"] - sb["bottom_z"] - 120.0) < 1e-9 and abs(sb["scale"][2] - 1.2) < 1e-12)
pt = btb.vadd(BEAM["location"], btb.vmul(u, 600.0))
check("smoke box: centred under the beam 6 m along it, yawed with it",
      abs(sb["loc"][0] - pt[0]) < 1e-9 and abs(sb["loc"][1] - pt[1]) < 1e-9 and abs(sb["rot"]["yaw"] - 90.0) < 1e-9
      and sb["rot"]["pitch"] == 0.0)
check("smoke box -: a vertical beam refused",
      raises(lambda: A.smoke_box_spec(1, dict(BEAM, rotation={"roll": 0.0, "pitch": -90.0, "yaw": 0.0}), 0.0, P),
             "BEAM_VERTICAL"))
check("floor: trace within 150 cm wins", A.choose_floor(3.0, 0.0, P) == (3.0, "trace"))
check("floor -control: a trace 400 cm off is rejected", A.choose_floor(400.0, 0.0, P) == (0.0, "station_trace_rejected"))
check("floor: no trace -> station fallback", A.choose_floor(None, 7.0, P) == (7.0, "station_fallback"))
check("smoke floor: median when within spread", A.smoke_floor([0.0, 10.0, 20.0], P) == 10.0)
check("smoke floor -: spread > 30 cm refused", raises(lambda: A.smoke_floor([0.0, 100.0, 5.0], P), "SMOKE_FLOOR_SPREAD"))
BW = []
for i, (bay, y) in enumerate(((4, 200.0), (8, -200.0), (13, 200.0), (18, -200.0))):
    BW.append(dict(BEAM, label="P03 SCORE B%02d X BEAM_R" % bay, bay=bay, show_index=79 + bay,
                   location=[1000.0 + 500.0 * bay, y, 450.0],
                   rotation={"roll": 0.0, "pitch": -10.0, "yaw": 90.0 if y > 0 else -90.0}))
FLOORS = {b["label"]: (0.5, "trace") for b in BW}
WIDE = A.footprint([b["location"] for b in BW], 1500.0)
nz, sk, fz = A.plan_spawns(BW, FLOORS, WIDE, P)
check("spawns: 4 noise boxes + 3 smoke (first 3 beam bays)", len(nz) == 4 and [s["label"] for s in sk]
      == ["P03 Smoke Test 1", "P03 Smoke Test 2", "P03 Smoke Test 3"] and fz == 0.5)
check("spawns: smoke under B04 B08 B13", [s["beam"].split()[2] for s in sk] == ["B04", "B08", "B13"])
_n, sk2, _f = A.plan_spawns(BW, FLOORS, WIDE, A.check_params({"smoke_bays": [8, 18], "smoke_count": 2}))
check("spawns: smoke_bays picks B08 B18", [s["beam"].split()[2] for s in sk2] == ["B08", "B18"])
check("spawns -: a smoke bay without a beam refused",
      raises(lambda: A.plan_spawns(BW, FLOORS, WIDE, A.check_params({"smoke_bays": [5]})), "SMOKE_BAY_HAS_NO_BEAM"))
TINY = A.footprint([(0.0, 0.0, 0.0)], 10.0)
check("spawns -: boxes outside P03's footprint refused (frame-trap guard)",
      raises(lambda: A.plan_spawns(BW, FLOORS, TINY, P), "SPAWN_OUTSIDE_P03"))
check("spawns: smoke off -> none", A.plan_spawns(BW, FLOORS, WIDE, A.check_params({"smoke": False}))[1] == [])
live_sp = {s["label"]: {"count": 1, "loc": list(s["loc"])} for s in nz + sk}
check("spawn drift: none when in place", A.spawn_drifts(live_sp, nz + sk) == [])
moved = copy.deepcopy(live_sp)
moved[nz[0]["label"]]["loc"][0] += 50.0
check("spawn drift -: a moved box is drift", len(A.spawn_drifts(moved, nz + sk)) == 1)
missing = dict(live_sp)
missing.pop(sk[0]["label"])
check("spawn drift -: a missing box is drift", len(A.spawn_drifts(missing, nz + sk)) == 1)
check("expected: matching counts pass", A.check_expected({"noise": 4}, {"noise": 4}) is None)
check("expected -: mismatch refused", raises(lambda: A.check_expected({"noise": 3}, {"noise": 4}), "EXPECTED_COUNTS"))

# ---------------------------------------------------------------- I. static scans of the tool
SRC = (HERE / "p03_atmos.py").read_text(encoding="utf-8")
FORBIDDEN = ("save_all", "save_directory", "save_packages", "delete_all_material_expressions",
             "delete_material_expression", "set_fog_density", "set_second_fog_density",
             "set_volumetric_fog_scattering_distribution", "set_actor_label(\"ZZ_", "ExecuteConsoleCommand", "execute_console_command")


def scan(text):
    return [f for f in FORBIDDEN if f in text]


check("scan: no Save All / node delete / height-fog write / console write in the tool", scan(SRC) == [])
check("scan -control: the scanner catches a save_directory call", scan("eal.save_directory('/Game')") == ["save_directory"])
tree = ast.parse(SRC)
deletes = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "delete_asset"]
revert_fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_revert"][0]
inside_revert = [n for n in ast.walk(revert_fn) if isinstance(n, ast.Attribute) and n.attr == "delete_asset"]
check("scan: delete_asset only inside _revert (remove_assets)", len(deletes) == 1 and len(inside_revert) == 1)
globals_unreal = [n for n in tree.body if isinstance(n, ast.Assign) and "unreal." in ast.unparse(n.value)]
check("scan: no Unreal object in a module global", globals_unreal == [])
check("scan: save only via _save_narrow + per-asset save_asset",
      SRC.count("save_asset(") == 1 and "_save_narrow()" in SRC and "save_current_level" not in SRC)

# ---------------------------------------------------------------- J. the rig-pattern loader offline
rp = A.load_rig_pattern()
cfg = rp.passage_config("P03")
check("loader: p01_rig_pattern loads without main; P03 config", cfg["label"] == "Passage 3"
      and cfg["actor_prefix"] == "Passage 03" and cfg["structure_label"] == "Infinity Stage - Structure 03")
check("loader -: a file without the main guard refused",
      raises(lambda: A.load_without_main(str(HERE / "p03_atmos.py"), "x"), "MAIN_GUARD_SHAPE"))

# ---------------------------------------------------------------- K. parse every new file
for name in ("p03_atmos.py", "p03_atmos_run.py", "test_p03_atmos_offline.py"):
    try:
        ast.parse((HERE / name).read_text(encoding="utf-8"))
        ok = True
    except SyntaxError:
        ok = False
    check("ast.parse %s" % name, ok)
for name in ("p03_atmos_args.json", "p03_atmos_request.json"):
    try:
        json.loads((HERE / name).read_text(encoding="utf-8"))
        ok = True
    except ValueError:
        ok = False
    check("json %s" % name, ok)

failed = [n for n, ok in RESULTS if not ok]
print("\nP03ATMOS_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
