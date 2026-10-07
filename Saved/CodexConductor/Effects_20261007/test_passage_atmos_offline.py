"""Offline harness for passage_atmos.py (no Unreal). Every property has a + case and a - control that must FAIL (or
raise), so each check is shown able to fail. Fixtures: lighting_scores_record_P01/P05/P06.json after_rows (the live
records of 5-6 Oct). Run: python Saved/CodexConductor/Effects_20261007/test_passage_atmos_offline.py"""
import ast
import copy
import json
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
CORE_DIR = HERE.parent
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(HERE))
import passage_atmos as W  # noqa: E402

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


def plain_for(passage):
    rec = json.loads((CORE_DIR / ("lighting_scores_record_%s.json" % passage)).read_text(encoding="utf-8"))
    cues = [{"guid": t["cue_guid"], "label": t["cue_label"], "show_index": t["show_index"],
             "attachments": copy.deepcopy(t["after_rows"])} for t in rec["plan"]["targets"]]
    return {"cues": cues, "bay_guids": [c["guid"] for c in cues], "passage_guid": "X"}


SEL_ALL = {"bays": None, "stride": 1, "phase": 0, "max": 64}

# ---------------------------------------------------------------- A. core pin + private load
check("core sha pinned and current", W.file_sha256(W.CORE_PATH) == W.CORE_SHA256)
mods_before = set(sys.modules)
c1 = W.load_core("P01", SEL_ALL)
c5 = W.load_core("P05", dict(SEL_ALL, stride=10))
check("private load: no new sys.modules entry for the core",
      not any("p03_atmos" in m for m in set(sys.modules) - mods_before))
check("private load: two passages are independent modules", c1 is not c5 and c1.PASSAGE == "P01" and c5.PASSAGE == "P05")
import p03_atmos as P3  # noqa: E402  (the real module, imported AFTER the private loads)
check("p03_atmos itself stays P03 (not mutated by the wrapper)",
      P3.PASSAGE == "P03" and P3.MARK == "P03ATMOS" and P3.RECORD_PATH.endswith("p03_atmos_record.json"))
tmp = pathlib.Path(tempfile.mkdtemp())
drift = tmp / "p03_atmos.py"
shutil.copy2(W.CORE_PATH, drift)
with open(drift, "a", encoding="utf-8") as h:
    h.write("\n# drift\n")
check("core -control: an edited core refuses CORE_DRIFT", raises(lambda: W.load_core("P01", SEL_ALL, str(drift)),
                                                                   "CORE_DRIFT"))

# ---------------------------------------------------------------- B. re-pointing
check("repoint: marks/tags/confirm = P01ATMOS", c1.MARK == c1.CONFIRM_TOKEN == c1.ACTOR_TAG == "P01ATMOS")
check("repoint: record in Effects_20261007", pathlib.Path(c1.RECORD_PATH) == HERE / "p01_atmos_record.json")
check("repoint: report path", pathlib.Path(c1.report_path("DRY", "R1")).name == "p01_atmos_report_DRY_R1.json")
check("repoint: backup prefixes", c1.backup_prefix() == "PreP01Atmos-" and c1.backup_prefix(True) == "PreP01AtmosRevert-")
check("repoint: smoke MI per passage", c1.MI_SMOKE.endswith("/MI_Vol_SmokeTest_P01"))
check("args: APPLY P01ATMOS accepted by the re-pointed core",
      c1.check_args({"mode": "APPLY", "confirm": "APPLY P01ATMOS"})["mode"] == "APPLY")
check("args -control: the P03 token is refused for P01",
      raises(lambda: c1.check_args({"mode": "APPLY", "confirm": "APPLY P03ATMOS"}), "CONFIRM_MISSING"))

# Every P03/p03 string literal in the core: re-pointed above, or text-only (messages, docs, report prose).
REPOINTED_NAMES = {"RECORD_PATH", "MARK", "CONFIRM_TOKEN", "PASSAGE", "ACTOR_TAG", "MI_SMOKE"}
REPOINTED_FUNCS = {"report_path", "backup_prefix"}
TEXT_ONLY_FUNCS = {"plan_lfv", "_plan_spawn_guard", "fog_source_table", "_gather", "main", "load_rig_pattern",
                   "_floors", "_materialized_by_attachment", "spawn_guard"}


def classify(src):
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    parents = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            parents[ch] = node
    unclassified = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if ("P03" not in node.value and "p03" not in node.value) or node.value == doc:
            continue
        p, ok = parents.get(node), False
        chain = []
        while p is not None:
            chain.append(p)
            p = parents.get(p)
        for anc in chain:
            if isinstance(anc, ast.Assign) and any(isinstance(t, ast.Name) and t.id in REPOINTED_NAMES
                                                   for t in anc.targets):
                ok = True
            if isinstance(anc, ast.FunctionDef) and anc.name in REPOINTED_FUNCS:
                ok = True
            if isinstance(anc, ast.Call) and getattr(anc.func, "id", None) in ("require", "_log") :
                ok = True                                          # stop/log message text
            if isinstance(anc, ast.Expr) and isinstance(getattr(anc, "value", None), ast.Constant):
                ok = True                                          # function docstring
            if isinstance(anc, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "INFERRED" for t in anc.targets):
                ok = True
            if isinstance(anc, ast.Dict) and any(isinstance(k, ast.Constant) and k.value in ("source", "scope",
                                                                                             "evidence")
                                                 for k in anc.keys):
                ok = True                                          # fog-source table prose
            if isinstance(anc, ast.Compare) or (isinstance(anc, ast.Call)
                                                and getattr(anc.func, "attr", None) == "get"
                                                and node.value == "P03ATMOS_ARGS"):
                ok = True                                          # the main guard / args global (never set here)
            if isinstance(anc, ast.Call) and getattr(anc.func, "id", None) == "load_without_main":
                ok = True                                          # private module name for the rig pattern
        if not ok:
            unclassified.append((node.lineno, node.value[:60]))
    return unclassified


CORE_SRC = pathlib.Path(W.CORE_PATH).read_text(encoding="utf-8")
left = classify(CORE_SRC)
check("literals: every P03 literal in the core is re-pointed or text-only (%s)" % left, not left)
check("literals -control: a new hard-coded P03 asset path is caught",
      classify(CORE_SRC + '\nNEW_PATH = "/Game/InfinityStage/Lighting/BeamLook/MI_Thing_P03"\n') != [])

# ---------------------------------------------------------------- C. wrapper args
ok = W.check_wrapper_args({"mode": "DRY", "passage": "P01", "beam_bays": [20]})
check("wargs: P01 bay 20 accepted, wrapper keys stripped from core args",
      ok[0] == "P01" and ok[1]["bays"] == [20] and not set(W.WRAPPER_KEYS) & set(ok[2]))
check("wargs: rollout defaults switch the P03 fog cut and smoke off",
      ok[2]["params"]["vs_scale"] == 1.0 and ok[2]["params"]["lfv_extinction_scale"] == 1.0
      and ok[2]["params"]["smoke"] is False)
check("wargs: core accepts the stripped args", c1.check_args(ok[2])["params"]["smoke"] is False)
check("wargs -: P03 refused (own tool)", raises(lambda: W.check_wrapper_args({"passage": "P03"}), "PASSAGE_INVALID"))
check("wargs -: P07 refused", raises(lambda: W.check_wrapper_args({"passage": "P07"}), "PASSAGE_INVALID"))
check("wargs -: bays + stride refused", raises(lambda: W.check_wrapper_args(
    {"passage": "P01", "beam_bays": [4], "beam_stride": 3}), "BEAM_BAYS_AND_STRIDE"))
check("wargs -: phase >= stride refused", raises(lambda: W.check_wrapper_args(
    {"passage": "P01", "beam_stride": 3, "beam_phase": 3}), "BEAM_PHASE_GE_STRIDE"))
check("wargs -: APPLY without reuse refused", raises(lambda: W.check_wrapper_args(
    {"mode": "APPLY", "passage": "P01", "beam_bays": [20]}), "REUSE_REQUIRED"))
check("wargs: APPLY with reuse ok", W.check_wrapper_args(
    {"mode": "APPLY", "passage": "P01", "beam_bays": [20], "reuse_existing_assets": True})[0] == "P01")
check("wargs -control: the core still refuses an unknown param (no silent pass-through)",
      raises(lambda: c1.check_args({"mode": "DRY", "params": {"beam_stride": 2}}), "PARAMS_UNKNOWN"))

# ---------------------------------------------------------------- D. beam selection on real records
P01 = plain_for("P01")
p = c1.check_params(dict(W.ROLLOUT_PARAMS))
c1_all = W.load_core("P01", SEL_ALL)
rows_all = c1_all.beam_rows(P01, p)
check("select: P01 record has 28 BEAM_R rows", len(rows_all) == 28)
c1_20 = W.load_core("P01", {"bays": [20], "stride": 1, "phase": 0, "max": 8})
r20 = c1_20.beam_rows(P01, p)
check("select: bay 20 (Gary's 'flickers nicely' beam) -> exactly that row",
      len(r20) == 1 and r20[0]["bay"] == 20 and r20[0]["row"]["label"].startswith("P01 SCORE B20 "))
c1_s4 = W.load_core("P01", {"bays": None, "stride": 4, "phase": 0, "max": 8})
check("select: stride 4 -> 7 of 28", len(c1_s4.beam_rows(P01, p)) == 7)
c1_cap = W.load_core("P01", {"bays": None, "stride": 2, "phase": 0, "max": 8})
check("select -: stride 2 (14 beams) over the cap of 8 refused", raises(lambda: c1_cap.beam_rows(P01, p),
                                                                        "TOO_MANY_BEAMS"))
c1_bad = W.load_core("P01", {"bays": [2], "stride": 1, "phase": 0, "max": 8})
check("select -: a non-beam bay refused", raises(lambda: c1_bad.beam_rows(P01, p), "BEAM_BAY_NOT_FOUND"))
P05 = plain_for("P05")
c5_all = W.load_core("P05", SEL_ALL)
check("select: P05 record has 51 beams; stride 10 -> 6", len(c5_all.beam_rows(P05, c5_all.check_params(
    dict(W.ROLLOUT_PARAMS)))) == 51 and len(c5.beam_rows(P05, c5.check_params(dict(W.ROLLOUT_PARAMS)))) == 6)
check("select -control: P01 rows fed to the P05 core are refused (bay label prefix)",
      raises(lambda: c5_all.beam_rows(P01, p), "BAY_NOT_P05"))

# ---------------------------------------------------------------- E. fog plan is a no-op at rollout defaults
fog, untouched = c1_20.plan_fog(P01, p)
check("fog: rollout defaults target nothing on P01", fog == [])
fog_c, _u = c1_20.plan_fog(P01, c1_20.check_params(dict(W.ROLLOUT_PARAMS, vs_scale=0.5)))
check("fog -control: vs_scale 0.5 does target P01 lights", len(fog_c) > 0)
check("lfv: scale 1.0 targets nothing", c1_20.plan_lfv(
    [{"id": 1, "label": "LFV", "loc": [0, 0, 0], "radial_fog_extinction": 0.5, "height_fog_extinction": 0.5}],
    {"min": [-1, -1, -1], "max": [1, 1, 1]}, p)[0] == [])

# ---------------------------------------------------------------- F. light-function plan with carried flicker (P06 Buzz)
P06 = plain_for("P06")
c6 = W.load_core("P06", {"bays": None, "stride": 3, "phase": 0, "max": 8})
p6 = c6.check_params(dict(W.ROLLOUT_PARAMS))
b6 = c6.beam_rows(P06, p6)
BUZZ = "/Game/InfinityStage/Lighting/MI_LF_Flicker_Buzz.MI_LF_Flicker_Buzz"
live = {BUZZ: {"parent": c6.FLICKER_PARENT, "params": {"Speed": 7.0, "SpeedRatio": 1.7, "Depth": 0.3, "Phase": 0.4,
                                                        "Hardness": 0.6, "OnBias": 0.5}}}
lf_t, mi, lf_rows, lf_w = c6.plan_lf(b6, live, p6)
check("lf: P06 Buzz beams carry flicker via MI_LF_SoftSlats_Buzz", c6.ASSET_DIR + "/MI_LF_SoftSlats_Buzz" in mi)
check("lf: only selected P06 beams get a light function",
      {t["attachment_label"] for t in lf_t} <= {b["row"]["label"] for b in b6} and len(b6) == 6)

# ---------------------------------------------------------------- G. leftovers
ACT = [("P03 BeamLook Noise B04", ["InfinityStage.BeamLook", "P03ATMOS"]),
       ("P03 Smoke Test 1", ["InfinityStage.SmokeTest", "P03ATMOS"]),
       ("Lamp", ["InfinityStage.Attachment.x|y"])]
check("leftovers: P03's live boxes are not P01 leftovers",
      W.leftovers_from(ACT, "P01ATMOS", "InfinityStage.BeamLook", "InfinityStage.SmokeTest") == [])
check("leftovers -control: the core's own rule WOULD refuse them",
      sorted(l for l, t in ACT if "P01ATMOS" in t or "InfinityStage.BeamLook" in t or "InfinityStage.SmokeTest" in t)
      == ["P03 BeamLook Noise B04", "P03 Smoke Test 1"])
check("leftovers -: an orphan BeamLook box is a leftover",
      W.leftovers_from(ACT + [("Orphan", ["InfinityStage.BeamLook"])], "P01ATMOS", "InfinityStage.BeamLook",
                       "InfinityStage.SmokeTest") == ["Orphan"])
check("leftovers -: this passage's own box is a leftover",
      W.leftovers_from(ACT + [("P01 BeamLook Noise B20", ["InfinityStage.BeamLook", "P01ATMOS"])], "P01ATMOS",
                       "InfinityStage.BeamLook", "InfinityStage.SmokeTest") == ["P01 BeamLook Noise B20"])

# ---------------------------------------------------------------- H. files
for name in ("passage_atmos.py", "passage_atmos_run.py"):
    try:
        ast.parse((HERE / name).read_text(encoding="utf-8"))
        good = True
    except SyntaxError:
        good = False
    check("ast.parse %s" % name, good)
ARGS = json.loads((HERE / "passage_atmos_args.json").read_text(encoding="utf-8"))
check("args file: DRY, P01, valid", ARGS["mode"] == "DRY" and W.check_wrapper_args(ARGS)[0] == "P01")
REQ = json.loads((HERE / "passage_atmos_request.json").read_text(encoding="utf-8"))
check("request: ExecuteProjectPythonFile on the runner",
      REQ["arguments"]["tool_name"] == "ExecuteProjectPythonFile"
      and REQ["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/Effects_20261007/passage_atmos_run.py")

failed = [n for n, good in RESULTS if not good]
print("\nPASSAGEATMOS_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
