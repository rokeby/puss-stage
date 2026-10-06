"""Offline harness for s3_sack_livecloth.py (no Unreal). Every gate has a NEGATIVE CONTROL that must fail.

Part A  pure helpers: params, modes, census, the sheet (isometric 2D pattern, winding, pin disc, torn edge, UV1,
        determinism), the component-frame geometry (upright eyes / Shore02 recorded back pin), the Dataflow spec, the
        BP / PIE gates; cross-checked against the REAL files (Blender finals, the BP and cloth .uasset bytes, the UE 5.8
        Chaos Cloth headers) where those carry the fact.
        v2 (6 Oct): the measured lean set, the crown+back pin geometry and its coverage gate, the v2 MI look, the
        Min-sampler Dataflow spec. Live-content checks are STATE-AWARE (the BUILD / APPLY records say what must exist
        and what the BP / level must reference), not hard-coded "before" assertions.
Part B  APPLY -> REVERT through the tool's OWN glue (_set_template, _template_state, _comp_state, _instance_state,
        _save, census) against a FAKE `unreal`: six BP templates whose compile propagates to level instances unless
        an instance overrides the property. It proves the tool's logic (records, read-back gates, census, drift,
        refusal before the first write), NOT UE behaviour (the live DRY's job). BUILD's glue (GeometryScript,
        Dataflow, materials) is not faked: its pure gates are Part A, its API names are DRY's _api_presence and the
        in-memory DynamicMesh probe.
Run: python Saved/CodexConductor/test_s3_sack_livecloth_offline.py   -> exit 0 and S3LIVESACK_OFFLINE_OK
"""
import copy
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
ENGINE = "D:/Unreal Engine/UE_5.8/Engine/Plugins/ChaosClothAssetDataflowNodes/Source/ChaosClothAssetDataflowNodes/Public/ChaosClothAsset/"
RESULTS = []


def load():
    spec = importlib.util.spec_from_file_location("_t_s3_sack_livecloth", os.path.join(HERE, "s3_sack_livecloth.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = load()


def check(name, cond, detail=""):
    RESULTS.append({"check": name, "pass": bool(cond), "detail": str(detail)[:300]})


def raises(fn, *a, contains=None, **kw):
    try:
        fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001
        return contains is None or contains in str(exc)
    return False


def strings(path, minlen=5):
    b = open(path, "rb").read()
    return set(m.decode() for m in re.findall(rb"[\x20-\x7e]{%d,}" % minlen, b))


def content_file(game_path, ext=".uasset"):
    return os.path.join(PROJECT, "Content", game_path[len("/Game/"):] + ext)


# ================================================================================================ Part A
def t_params():
    check("defaults validate", S.validate_params(dict(S.PARAMS)) == [], S.validate_params(dict(S.PARAMS)))
    for k, v, want in (("quad_cm", 1.0, "PARAM_RANGE"), ("pin_outer_cm", 8.0, "PIN_FALLOFF"),
                       ("max_iterations", 1, "ITERATIONS"), ("material_variant", "glossy", "PARAM_VARIANT"),
                       ("density_kg_m2", True, "PARAM_RANGE"), ("quad_cm", 8.0, "PIN_DISC")):
        p = dict(S.PARAMS)
        p[k] = v
        probs = S.validate_params(p)
        check("NEG params %s=%r fails (%s)" % (k, v, want), any(x.startswith(want) for x in probs), probs)
    p = dict(S.PARAMS)
    p["bogus"] = 1
    check("NEG unknown param fails", any(x.startswith("PARAM_UNKNOWN") for x in S.validate_params(p)))


def t_modes():
    none = {"BUILD": False, "APPLY": False}
    built = {"BUILD": True, "APPLY": False}
    applied = {"BUILD": True, "APPLY": True}
    m = S.check_mode({"mode": "DRY"}, none)
    check("DRY needs no confirm, all six, v1", m[0] == "DRY" and m[1] == list(S.FIGURES) and m[2] == 1)
    check("BUILD with confirm", S.check_mode({"mode": "BUILD", "confirm": "BUILD S3LIVESACK"}, none)[0] == "BUILD")
    check("NEG BUILD without confirm", raises(S.check_mode, {"mode": "BUILD"}, none, contains="CONFIRM_MISSING"))
    check("NEG APPLY with BUILD's confirm", raises(S.check_mode, {"mode": "APPLY", "confirm": "BUILD S3LIVESACK"}, built,
                                                   contains="CONFIRM_MISSING"))
    check("NEG APPLY before BUILD", raises(S.check_mode, {"mode": "APPLY", "confirm": "APPLY S3LIVESACK"}, none,
                                           contains="PREREQ"))
    check("NEG APPLY twice", raises(S.check_mode, {"mode": "APPLY", "confirm": "APPLY S3LIVESACK"}, applied,
                                    contains="ALREADY_APPLIED"))
    check("NEG REVERT with nothing applied", raises(S.check_mode, {"mode": "REVERT", "confirm": "REVERT S3LIVESACK"},
                                                    built, contains="NO_APPLY_RECORD"))
    check("NEG PIE_PROBE with nothing applied", raises(S.check_mode, {"mode": "PIE_PROBE"}, built, contains="NO_APPLY_RECORD"))
    check("NEG unknown figure", raises(S.check_mode, {"mode": "DRY", "figures": ["Shore07"]}, none, contains="FIGURES"))
    check("NEG version 0", raises(S.check_mode, {"mode": "DRY", "version": 0}, none, contains="VERSION"))
    check("NEG bad params via args", raises(S.check_mode, {"mode": "DRY", "params": {"substeps": 50}}, none,
                                            contains="PARAMS"))
    check("NEG malformed forward override", raises(S.check_mode, {"mode": "DRY", "forward_local_override":
                                                                  {"Shore01_M56": [1, 0]}}, none, contains="FORWARD"))
    check("pilot subset accepted", S.check_mode({"mode": "BUILD", "confirm": "BUILD S3LIVESACK",
                                                 "figures": ["Shore02_F52"]}, none)[1] == ["Shore02_F52"])
    m2 = S.check_mode({"mode": "DRY", "version": 2}, none)
    check("v2 DRY: default back-pin figures + the v2 look", m2[4]["back_pin_figures"] == ["Shore03_M59", "Shore05_M53"]
          and m2[4]["mi_look"] == S.mi_look(2), m2[4])
    check("NEG back_pin_figures with Shore02 (already back-pinned) -> BACK_PIN_FIGURES",
          raises(S.check_mode, {"mode": "DRY", "version": 2, "back_pin_figures": ["Shore02_F52"]}, none, contains="BACK_PIN_FIGURES"))
    check("NEG accept_editor_pose unknown figure", raises(S.check_mode, {"mode": "DRY", "accept_editor_pose": ["X"]}, none,
                                                         contains="ACCEPT_EDITOR_POSE"))
    check("REVERT needs no version (the record carries it)", S.check_mode({"mode": "REVERT", "confirm": "REVERT S3LIVESACK"},
                                                                         applied)[0] == "REVERT")


def live_state():
    """What the records say the project holds NOW: {"built": {version: {fig: names}}, "applied": record or None}."""
    built = {}
    if os.path.exists(S.RECORDS["BUILD"]):
        for ver, v in json.load(open(S.RECORDS["BUILD"], encoding="utf-8"))["versions"].items():
            built[int(ver)] = {f: row["names"] for f, row in v["figures"].items()}
    applied = json.load(open(S.RECORDS["APPLY"], encoding="utf-8")) if os.path.exists(S.RECORDS["APPLY"]) else None
    return {"built": built, "applied": applied}


def content_state_problems(state, exists, versions=(1, 2)):
    """State-aware create-only check: every asset a BUILD record lists must exist; every target of a version (or figure)
    that is NOT in the record must be free. Pure (exists = a path predicate) so it has negative controls."""
    probs = []
    for ver in versions:
        rec = state["built"].get(ver, {})
        for f in S.FIGURES:
            nm = S.names(f, ver)
            for k in ("mesh", "dataflow", "cloth"):
                if f in rec and not exists(nm[k]):
                    probs.append("BUILT_BUT_MISSING|v%d|%s" % (ver, nm[k]))
                if f not in rec and exists(nm[k]):
                    probs.append("NOT_BUILT_BUT_TAKEN|v%d|%s" % (ver, nm[k]))
        mi = S.names(S.FIGURES[0], ver)["mi"]
        if rec and not exists(mi):
            probs.append("BUILT_BUT_MISSING|v%d|%s" % (ver, mi))
        if not rec and exists(mi):
            probs.append("NOT_BUILT_BUT_TAKEN|v%d|%s" % (ver, mi))
    return probs


def t_files():
    """The paths the tool names exist on disk today (declaration: Content listing), STATE-AWARE: what a BUILD record
    lists must exist, what no record lists must be free (create-only)."""
    for f in S.FIGURES:
        check("BP on disk: %s" % f, os.path.exists(content_file(S.names(f, 1)["bp"])))
        check("old cloth asset on disk: %s" % S.OLD_ASSET[f], os.path.exists(content_file(S.OLD_ASSET[f])))
    for p in (S.SRC_MASTER["masked"], S.SRC_MASTER["opaque"], S.SRC_MI, S.OLD_MATERIAL):
        check("source material on disk: %s" % p, os.path.exists(content_file(p)))
    check("umap on disk", os.path.exists(S.UMAP))
    check("Shore02 record on disk", os.path.exists(S.SHORE02_RECORD))
    st = live_state()
    on_disk = lambda p: os.path.exists(content_file(p))
    probs = content_state_problems(st, on_disk)
    check("content matches the BUILD record (built -> exists, unbuilt -> free); built versions %s" % sorted(st["built"]),
          not probs, probs)
    fake = {"built": {1: {}}, "applied": None}
    check("NEG a record-less version whose assets exist -> NOT_BUILT_BUT_TAKEN",
          any(x.startswith("NOT_BUILT_BUT_TAKEN|v1") for x in content_state_problems(fake, lambda p: True, (1,))))
    fake = {"built": {2: {f: S.names(f, 2) for f in S.FIGURES}}, "applied": None}
    check("NEG a recorded version whose assets are gone -> BUILT_BUT_MISSING",
          any(x.startswith("BUILT_BUT_MISSING|v2") for x in content_state_problems(fake, lambda p: False, (2,))))
    if 2 not in st["built"]:
        check("v2 targets free (v2 not built yet)", not any(on_disk(S.names(f, 2)[k]) for f in S.FIGURES
                                                            for k in ("mesh", "dataflow", "cloth", "mi")))
    taken = [S.names(f, v)[k] for v in (1, 2) for f in S.FIGURES for k in ("mesh", "dataflow", "cloth")] + \
            [S.names("Shore01_M56", v)[k] for v in (1, 2) for k in ("master", "mi")]
    check("targets live under ShoreCast Cloth/LiveSack or Sack/Materials",
          all(p.startswith(S.LIVE_DIR + "/") or p.startswith(S.MAT_DIR + "/") for p in taken))
    check("v1 MI name unchanged (built 6 Oct), v2 MI versioned, master shared",
          S.names("Shore01_M56", 1)["mi"] == S.MAT_DIR + "/MI_Sackcloth_OldGrey_Cloth" and
          S.names("Shore01_M56", 2)["mi"] == S.MAT_DIR + "/MI_Sackcloth_OldGrey_Cloth_v2" and
          S.names("Shore01_M56", 1)["master"] == S.names("Shore01_M56", 2)["master"])


def bp_expected(f):
    """(want, other): what the saved BP must reference now (the active APPLY record, else today's drape)."""
    old = {"state": "old drape", "asset": S.OLD_ASSET[f], "mi": S.OLD_MATERIAL}
    a = live_state()["applied"]
    if a and f in a["figures"]:
        nm = S.names(f, a["version"], a["variant"])
        return {"state": "applied v%d" % a["version"], "asset": nm["cloth"], "mi": nm["mi"]}, old
    return old, {"state": "live sack v1", "asset": S.names(f, 1)["cloth"], "mi": S.names(f, 1)["mi"]}


def t_binary_facts():
    """Binary-proven facts the design leans on (strings in the saved .uasset)."""
    for f in S.FIGURES:
        s = strings(content_file(S.names(f, 1)["bp"]))
        check("BP %s: ConfigureShoreDrape attaches + collides (K2_AttachToComponent, AddCollisionSource)" % f,
              {"ConfigureShoreDrape", "K2_AttachToComponent", "AddCollisionSource", "ResetCollisionSources"} <= s)
        check("BP %s: no SetMaterial/SetAsset/SetSkinnedAsset symbol (construction cannot reset our material/asset)" % f,
              not any(x in s for x in ("SetMaterial", "SetAsset", "SetSkinnedAssetAndUpdate", "SetClothAsset")))
        want, other = bp_expected(f)
        check("BP %s: template references the %s asset + material + OverrideMaterials" % (f, want["state"]),
              want["asset"] in s and want["mi"] in s and "OverrideMaterials" in s, want)
        check("BP %s: and NOT the %s asset (the state is unambiguous)" % (f, other["state"]), other["asset"] not in s, other)
        check("BP %s: collision = the drape PHYS" % f, "%s/Cloth/PHYS_%s_Drape" % (S.ROOT, f) in s)
    # The level on disk carries NO cloth asset for the placed figures, before APPLY (the PreS3LiveSack backup) or after
    # the S3LSFIX save (binary, 6 Oct): ClothComponent.h:494-495 `Asset` is Transient (an alias of SkinnedAsset), and
    # an instance equal to its archetype writes no delta. So the "instance keeps its own asset" seen live is IN-MEMORY
    # state of the open editor [inferred]; on a reload the template governs. APPLY/REVERT still write the instance
    # (the open session and PIE use it) and save the level that write dirties.
    umap = open(S.UMAP, "rb").read()
    check("level on disk: no ShoreHeadCloth asset reference (neither old drape nor sack): the template governs on load",
          b"ShoreSack" not in umap and b"HeadDrape" not in umap)
    check("NEG control: the same byte scan finds the figures' BP class in the level", b"BP_Shore01_M56_Draped" in umap)
    cc = "D:/Unreal Engine/UE_5.8/Engine/Plugins/ChaosClothAsset/Source/ChaosClothAssetEngine/Public/ChaosClothAsset/ClothComponent.h"
    if os.path.exists(cc):
        t = open(cc, encoding="utf-8", errors="replace").read()
        check("header: UChaosClothComponent::Asset is Transient (Setter = SetAsset)",
              re.search(r"UPROPERTY\(EditAnywhere, Transient, Setter = SetAsset[^\n]*\)\s*TObjectPtr<UChaosClothAssetBase> Asset;", t) is not None)
    # material facts behind the v2 look (binary-proven: names in the saved assets)
    mst = strings(content_file(S.names("Shore01_M56", 1)["master"]), 4)
    check("cloth master: HemGrimeAmount + InnerDarken params, an ObjectPositionWS node, NO TwoSidedSign node "
          "(InnerDarken darkens BOTH faces; there is no back-face-only term)",
          {"HemGrimeAmount", "InnerDarken", "MaterialExpressionObjectPositionWS"} <= mst and
          "MaterialExpressionTwoSidedSign" not in mst)
    mi1 = strings(content_file(S.names("Shore01_M56", 1)["mi"]), 4)
    check("v1 cloth MI overrides Tint/Desaturate/HemGrimeHeightM but NOT HemGrimeAmount/InnerDarken (defaults 1.0)",
          {"Tint", "Desaturate", "HemGrimeHeightM"} <= mi1 and not ({"HemGrimeAmount", "InnerDarken"} & mi1))
    check("NEG control: the same scan finds a name that IS in the MI", "Desaturate" in mi1)
    eng = "D:/Unreal Engine/UE_5.8/Engine/"
    pu = eng + "Source/Runtime/Engine/Public/PrimitiveUniformShaderParametersBuilder.h"
    if os.path.exists(pu):
        check("header: ObjectPositionWS source = the primitive's WORLD BOUNDS origin "
              "(PrimitiveUniformShaderParametersBuilder.h: AbsoluteObjectWorldPosition = InWorldBounds.Origin)",
              "AbsoluteObjectWorldPosition = InWorldBounds.Origin;" in open(pu, encoding="utf-8", errors="replace").read())
    mn = eng + "Plugins/Dataflow/Source/DataflowNodes/Private/Dataflow/SamplerNodes/DataflowMinSamplerNode.h"
    mi_h = eng + "Plugins/Dataflow/Source/DataflowNodes/Private/Dataflow/SamplerNodes/DataflowSamplerMultiInput.h"
    if os.path.exists(mn) and os.path.exists(mi_h):
        t1, t2 = open(mn, encoding="utf-8").read(), open(mi_h, encoding="utf-8").read()
        check("header: FDataflowMinSamplerNode exists on the multi-input base (InputSamplers array, output Sampler)",
              "struct FDataflowMinSamplerNode : public FDataflowMultiInputSamplerNodeBase" in t1 and
              "TArray<FDataflowSamplerTypes> InputSamplers;" in t2 and "FDataflowSamplerTypes Sampler;" in t2)
        check("NEG header scan rejects a made-up sampler", "struct FDataflowUnionSamplerNode" not in t1)
    else:
        check("Min sampler header absent: UNCLEAR (skipped)", True)
    ca = strings(content_file(S.OLD_ASSET["Shore01_M56"]))
    for t in ("FDataflowDistanceFromSphereFloatSamplerNode", "FDataflowSmoothStepFloatSamplerNode",
              "FDataflowSamplerToAttributeNode", "DistanceFromSphereSampler", "SmoothStepSampler",
              "FChaosClothAssetStaticMeshImportNode_v2", "FChaosClothAssetTerminalNode_v2"):
        check("old CA carries %s (the sampler pin route ran in this project)" % t, t in ca)
    check("old CA had separate SIM and RENDER static-mesh imports (render/sim split is supported)",
          {"StaticMeshImport_SIM", "StaticMeshImport_RENDER", "FChaosClothAssetMergeClothCollectionsNode_v2"} <= ca)
    check("NEG control: a symbol that IS in the BP is found by the same scan",
          "AddCollisionSource" in strings(content_file(S.names("Shore01_M56", 1)["bp"])))


def t_sheet():
    p = dict(S.PARAMS)
    axes_sets = {"identity": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                 "pitch-90": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]}
    for f in S.FIGURES:
        s = S.build_sheet(S.DECISION[f]["size_m"], p["quad_cm"], p["fray_depth_cm"], p["seed"] + S.FIGURES.index(f))
        for tag, ax in axes_sets.items():
            fr, pr = S.upright_frame([0, 0, 0], ax, S.dir_to_world([30, 0, 5], ax), [0, 0, 1], None, p)
            pl = S.place_sheet(s, fr, S.DECISION[f]["pin_forward_m"])
            m = S.sheet_metrics(s, pl, p)
            probs = S.sheet_problems(m, p)
            check("sheet %s (%s): every gate passes" % (f, tag), not probs and not pr, (probs, pr, m))
        xs, ys = [x for x, _ in s["xy"]], [y for _, y in s["xy"]]
        check("sheet %s: 2.0 m less the torn inset" % f,
              2.0 - 2 * p["fray_depth_cm"] / 100 - 1e-6 <= max(xs) - min(xs) <= 2.0 + 1e-9 and
              2.0 - 2 * p["fray_depth_cm"] / 100 - 1e-6 <= max(ys) - min(ys) <= 2.0 + 1e-9, (max(xs) - min(xs), max(ys) - min(ys)))
        interior = [u for i, u in enumerate(s["uv1"]) if 0 < i % (s["n"] + 1) < s["n"] and 0 < i // (s["n"] + 1) < s["n"]]
        check("sheet %s: UV1.x > 0 inside, 0 on the cut" % f, min(u[0] for u in interior) > 0 and m["boundary_on_edge"] < 1e-9)
    a = S.build_sheet(2.0, 5.0, 3.5, 7)
    b = S.build_sheet(2.0, 5.0, 3.5, 7)
    c = S.build_sheet(2.0, 5.0, 3.5, 8)
    fr, _ = S.upright_frame([0, 0, 0], axes_sets["identity"], [30, 0, 0], [0, 0, 1], None, p)
    sha = lambda s_: S.buffers_sha(s_, S.place_sheet(s_, fr, 0.2))
    check("deterministic: same seed -> same buffers", sha(a) == sha(b))
    check("NEG different seed -> different buffers", sha(a) != sha(c))
    pl = S.place_sheet(a, fr, 0.2)
    cen = [sum(q[i] for q in pl["positions_cm"]) / len(pl["positions_cm"]) for i in range(3)]
    ahead = S._dot(S._sub(cen, pl["pin_local_cm"]), fr["fwd_local"])
    check("sheet centre ~20 cm AHEAD of the pin (Blender --pin-forward 0.2)", 17.0 < ahead < 23.0, ahead)
    # negative controls on the sheet gates
    bad = copy.deepcopy(a)
    bad["uv0"] = [(u * 1.02, v) for u, v in bad["uv0"]]
    check("NEG UV0 not metres (x1.02) -> PATTERN_NOT_ISOMETRIC",
          any(x.startswith("PATTERN_NOT_ISOMETRIC") for x in S.sheet_problems(S.sheet_metrics(bad, pl, p), p)))
    flip = dict(pl)
    flip["normal"] = S._mul(pl["normal"], -1)
    check("NEG flipped normal -> WINDING", any(x.startswith("WINDING") for x in S.sheet_problems(S.sheet_metrics(a, flip, p), p)))
    off = dict(pl)
    off["pin_local_cm"] = [500.0, 0.0, 0.0]
    check("NEG pin off the sheet -> PIN_TOO_FEW", any(x.startswith("PIN_TOO_FEW") for x in S.sheet_problems(S.sheet_metrics(a, off, p), p)))
    p2 = dict(p, max_distance_cm=150.0)
    check("NEG max distance 150 cm -> MAX_DISTANCE_LOW (the sheet could hang there and freeze)",
          any(x.startswith("MAX_DISTANCE_LOW") for x in S.sheet_problems(S.sheet_metrics(a, pl, p2), p2)))
    p3 = dict(p, pin_inner_cm=60.0, pin_outer_cm=70.0)
    check("NEG huge pin disc -> PIN_TOO_MANY", any(x.startswith("PIN_TOO_MANY") for x in S.sheet_problems(S.sheet_metrics(a, pl, p3), p3)))
    tilt = copy.deepcopy(pl)
    tilt["positions_cm"] = [[q[0], q[1], q[2] + 0.05 * q[0]] for q in pl["positions_cm"]]
    check("NEG tilted (non-flat) sheet -> NOT_FLAT", any(x.startswith("NOT_FLAT") for x in S.sheet_problems(S.sheet_metrics(a, tilt, p), p)))
    m = S.sheet_metrics(a, pl, p)
    check("particle count: 41 x 41 at 5 cm (old drape 21 x 21 = 441)", m["vertices"] == 1681, m["vertices"])


def _back_frame(back=(-28.0, 0.0, -38.0), down=(-0.5, 0.0, -0.87), p=None):
    """A Shore05-like crown+back frame in an identity component frame (cm): crown pin 2 cm up, eyes ahead (+X),
    upper back 28 cm behind and 38 cm below the crown, the back running down-and-back."""
    p = p or dict(S.PARAMS)
    fr, _ = S.upright_frame([0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [10, 0, -3], [0, 0, 1], None, p)
    fr["back"] = {"back_local_cm": list(back), "down_back_local": S._unit(list(down))}
    return fr


def t_lean():
    """Which figures lean (MEASURED: Tools/S3Sackcloth/lean_scan.py over the exported anims)."""
    check("leaning figures = Shore03_M59 + Shore05_M53 (Shore02 already back-pinned)",
          S.leaning_figures() == ["Shore03_M59", "Shore05_M53"] and S.BACK_PIN_FIGURES == ("Shore03_M59", "Shore05_M53"),
          S.leaning_figures())
    check("Shore05_M53 is the most bent crown-pinned figure (window lean p50 0.31 m, tilt p50 24 deg)",
          max((r["lean_p50_m"], f) for f, r in S.LEAN_SCAN.items() if S.DECISION[f]["pin"] == "crown")[1] == "Shore05_M53")
    check("NEG thresholds above every figure -> nobody leans", S.leaning_figures(lean_p90_m=0.6, tilt_p90_deg=80.0) == [])
    check("NEG Shore02 never in the set even at zero thresholds",
          "Shore02_F52" not in S.leaning_figures(lean_p90_m=0.0, tilt_p90_deg=0.0))
    summ = os.path.join(PROJECT, "DerivedAssets", "S3Sackcloth", "bodies", "lean_scan_summary.json")
    if os.path.exists(summ):
        d = json.load(open(summ, encoding="utf-8"))["figures"]
        diffs = []
        for f, r in S.LEAN_SCAN.items():
            w = d[f]["window"]
            for k, v in (("lean_p50_m", w["lean_m"]["p50"]), ("lean_p90_m", w["lean_m"]["p90"]),
                         ("tilt_p90_deg", w["torso_tilt_deg"]["p90"]), ("tilt_max_deg", w["torso_tilt_deg"]["max"])):
                if abs(r[k] - v) > 0.06:
                    diffs.append((f, k, r[k], v))
            hz = d[f]["pose_head_z_check"]
            if abs(hz[0] - hz[1]) > 0.003:
                diffs.append((f, "head_z", hz))
        check("LEAN_SCAN constants = the scan summary; scan head z = the export record (<3 mm) for all six", not diffs, diffs)
        bad = copy.deepcopy(d)
        bad["Shore05_M53"]["window"]["lean_m"]["p50"] = 0.05
        check("NEG a changed summary value is detected",
              abs(S.LEAN_SCAN["Shore05_M53"]["lean_p50_m"] - bad["Shore05_M53"]["window"]["lean_m"]["p50"]) > 0.06)
    else:
        check("lean scan summary absent: constants UNVERIFIED (skipped)", True)
    check("layout v1 = DECISION; v2 = crown+back for the leaning, v1 layout for the rest",
          [S.pin_layout(f, 1) for f in S.FIGURES] == [S.DECISION[f]["pin"] for f in S.FIGURES] and
          [S.pin_layout(f, 2) for f in S.FIGURES] == ["crown", "back", "crown+back", "crown", "crown+back", "crown"])
    check("NEG crown+back asked for Shore02 -> LAYOUT", raises(S.pin_layout, "Shore02_F52", 2, ("Shore02_F52",), contains="LAYOUT"))
    p = dict(S.PARAMS)
    pose_ok = {"tilt_deg": 24.0, "lean_m": 0.3}
    check("editor pose inside the scene motion -> no problem", not S.editor_pose_problems("Shore05_M53", pose_ok))
    check("NEG upright editor pose for bent Shore05 -> EDITOR_POSE_ATYPICAL",
          any(x.startswith("EDITOR_POSE_ATYPICAL") for x in S.editor_pose_problems("Shore05_M53", {"tilt_deg": 3.0, "lean_m": 0.02})))
    check("accept_editor_pose overrides it", not S.editor_pose_problems("Shore05_M53", {"tilt_deg": 3.0, "lean_m": 0.02}, ["Shore05_M53"]))
    tgt, info = S.back_target_world([0, -10, 140], [0, -14, 120], [0, -6, 150], [1, 0, 0], p)
    check("back target: behind the spine (against the facing) by depth + lift",
          tgt[0] < -10 and abs(S._norm(S._sub(tgt, [0, -10, 140])) - (p["back_pin_depth_cm"] + p["back_lift_cm"])) < 1e-6, tgt)
    check("back target: down_back points away from the head", info["down_back_world"][2] < 0, info)


def t_back_geometry():
    p = dict(S.PARAMS)
    fr = _back_frame(p=p)
    sheet, placed, m, probs = S.plan_geometry("Shore05_M53", fr, p, "crown+back")
    cov = m["coverage"]
    check("crown+back: every gate passes (isometric on EVERY triangle, winding, discs, coverage)", not probs, (probs, m))
    check("crown+back: kinematic particles at the crown AND the back disc (>= 3 each)", min(cov["per_pin"]) >= 3, cov)
    check("crown+back: MaxDistance-0 region spans the crown -> back arc",
          cov["rear_arc_min_cm"] <= p["pin_inner_cm"] and cov["rear_arc_max_cm"] >= cov["rear_len_cm"] - p["pin_inner_cm"], cov)
    check("crown+back: back disc centre is ON the sheet at the measured back point", cov["back_vs_target_cm"] < 0.01, cov)
    check("crown+back: crown pin kept at the v1 crown point", placed["pins"][0] == fr["pin_local_cm"])
    check("crown+back: the front panel is flat (v1 shape ahead of the crown)", m["plane_dev_cm"] < 0.01, m["plane_dev_cm"])
    check("crown+back: same particle count / pattern as v1 (1681)", m["vertices"] == 1681)
    s1 = S.buffers_sha(sheet, placed)
    _s, pl2, _m, _p = S.plan_geometry("Shore05_M53", _back_frame(p=p), p, "crown+back")
    check("crown+back: deterministic", S.buffers_sha(sheet, pl2) == s1)
    # negative controls on the coverage / geometry gates
    off = copy.deepcopy(placed)
    off["pins"] = [placed["pins"][0], [-300.0, 0.0, -38.0]]
    _c, cp = S.pin_coverage(sheet, off, p, fr["back"]["back_local_cm"])
    check("NEG back disc off the sheet -> BACK_PIN_COVERAGE + OFF_TARGET",
          any(x.startswith("BACK_PIN_COVERAGE") for x in cp) and any(x.startswith("BACK_PIN_OFF_TARGET") for x in cp), cp)
    crown_only = copy.deepcopy(placed)
    crown_only["pins"] = [placed["pins"][0], placed["pins"][0]]
    _c, cp = S.pin_coverage(sheet, crown_only, p)
    check("NEG a crown-only pin under the v2 layout -> coverage does not span + BACK_PIN_SPAN",
          any("does not span" in x for x in cp) and any(x.startswith("BACK_PIN_SPAN") for x in cp), cp)
    _s, _pl, _m, pr = S.plan_geometry("Shore05_M53", _back_frame(back=(6.0, 0.0, -40.0), p=p), p, "crown+back")
    check("NEG back point ahead of the crown -> BACK_PIN_NOT_BEHIND", any(x.startswith("BACK_PIN_NOT_BEHIND") for x in pr), pr)
    pt = dict(p, back_handle=0.6)
    _s, _pl, _m, pr = S.plan_geometry("Shore05_M53", _back_frame(p=pt), pt, "crown+back")
    check("NEG a tight bend (handle 0.6) -> BEND_TIGHT and PATTERN_NOT_ISOMETRIC",
          any(x.startswith("BEND_TIGHT") for x in pr) and any(x.startswith("PATTERN_NOT_ISOMETRIC") for x in pr), pr)
    fr2 = _back_frame(back=(-5.0, -40.0, -38.0), p=p)
    _s, _pl, _m, pr = S.plan_geometry("Shore05_M53", fr2, p, "crown+back")
    check("NEG back point 83 deg off the eyes -> BACK_FACING", any(x.startswith("BACK_FACING") for x in pr), pr)
    fr3 = _back_frame(down=(0.6, 0.0, 0.8), p=p)
    S.plan_geometry("Shore05_M53", fr3, p, "crown+back")
    check("back tangent pointing back at the crown -> chord fallback (recorded)",
          fr3["back"]["geometry"]["tangent_source"] == "chord")
    flat = S.plan_geometry("Shore01_M56", _back_frame(p=p), p, "crown")[3]
    check("upright crown layout under v2: v1 gates, no coverage problems", not flat, flat)
    c1, _ = S.pin_coverage(*S.plan_geometry("Shore01_M56", _back_frame(p=p), p, "crown")[:2], p)
    check("upright crown layout: one disc only", len(c1["pins_cm"]) == 1)


def t_material():
    l2 = S.mi_look(2)
    check("v2 look passes its gates", not S.material_problems(2, l2), S.material_problems(2, l2))
    v1t, v1h, v2 = S.predicted_albedo(S.MI_LOOK[1], hem=0.0), S.predicted_albedo(S.MI_LOOK[1], hem=1.0), S.predicted_albedo(l2, hem=1.0)
    check("v2 albedo = 2.0x v1's textured albedo (Gary: moderate, 1.8-2.2x)", 1.8 <= v2["lum"] / v1t["lum"] <= 2.2, (v1t, v2))
    check("v1 inside the hem band renders as GrimeColor (lum ~0.09): the near-black flat look [mechanism]",
          abs(v1h["lum"] - 0.0914) < 0.002 and v1h["rgb"] == [0.1, 0.09, 0.08], v1h)
    check("hem band: full grime at <= 0.10 m above the bounds centre, none above 0.35 m",
          abs(S.hem_weight(0.10) - 1.0) < 1e-9 and S.hem_weight(-1.0) == 1.0 and S.hem_weight(0.35) == 0.0 and
          0.0 < S.hem_weight(0.2) < 1.0)
    check("v2 keeps UV/tiling/normal/roughness (Gary: weave OK): not in the look",
          not ({"TileM", "NormalStrength", "RoughnessScale"} & set(l2["scalars"])))
    check("v1 look = the source MI (no overrides)", S.mi_look(1) == {"scalars": {}, "vectors": {}})
    for look, want in (({"scalars": {"HemGrimeAmount": 1.0}}, "HEM_GRIME_ON"),
                       ({"vectors": {"Tint": [1.86, 1.80, 1.68, 1.0]}}, "ALBEDO_STEP"),
                       ({"vectors": {"Tint": [0.62, 0.60, 0.56, 1.0]}}, "ALBEDO_STEP"),
                       ({"scalars": {"TileM": 0.1}}, "LOOK_KEY"),
                       ({"scalars": {"Desaturate": True}}, "LOOK_RANGE"),
                       ({"vectors": {"Tint": [1, 1, 1]}}, "LOOK_VECTOR")):
        lk = S.mi_look(2, look)
        check("NEG look %s -> %s" % (look, want), any(x.startswith(want) for x in S.material_problems(2, lk)),
              S.material_problems(2, lk))
    src = {"scalars": {"Desaturate": 0.75, "MottleAmount": 0.10000000149011612}, "vectors": {"Tint": [0.62, 0.6, 0.56, 1.0]},
           "textures": {}}
    want = S.look_target(src, l2)
    got = copy.deepcopy(want)
    got["scalars"]["Desaturate"] = 0.6000000238418579
    check("MI read-back: float32 jitter accepted", S.mi_values_match(want, got))
    got2 = copy.deepcopy(want)
    del got2["scalars"]["HemGrimeAmount"]
    check("NEG MI read-back: a look value that did not take -> mismatch", not S.mi_values_match(want, got2))
    got3 = copy.deepcopy(want)
    got3["vectors"]["Tint"] = [0.62, 0.6, 0.56, 1.0]
    check("NEG MI read-back: v1 tint on the v2 MI -> mismatch", not S.mi_values_match(want, got3))
    check("NEG mi_look in a v1 run is refused", raises(S.check_mode, {"mode": "DRY", "mi_look": {"scalars": {"Desaturate": 0.5}}},
                                                       {"BUILD": False, "APPLY": False}, contains="MI_LOOK"))
    check("NEG a bad look via args is refused", raises(S.check_mode, {"mode": "DRY", "version": 2,
                                                                      "mi_look": {"scalars": {"HemGrimeAmount": 1.0}}},
                                                       {"BUILD": False, "APPLY": False}, contains="MATERIAL"))
    tex = os.path.join(PROJECT, "DerivedAssets", "S3Sackcloth", "textures", "hessian_230", "hessian_230_diff_2k.png")
    try:
        from PIL import Image
        import numpy as np
        im = np.asarray(Image.open(tex).convert("RGB"), dtype=np.float64) / 255.0
        lin = np.where(im <= 0.04045, im / 12.92, ((im + 0.055) / 1.055) ** 2.4)
        mean = lin.reshape(-1, 3).mean(0)
        check("HESSIAN_DIFF_LINEAR = the texture's measured linear mean (<0.002)",
              all(abs(a - b) < 0.002 for a, b in zip(mean, S.HESSIAN_DIFF_LINEAR["mean_rgb"])), list(mean))
    except Exception as exc:  # noqa: BLE001
        check("texture mean UNVERIFIED (PIL/numpy or file missing: %s)" % exc, True)


def t_frames():
    p = dict(S.PARAMS)
    ax = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]          # component X up, Z back: a rotated head frame
    eye = S.dir_to_world([5, 0, 12], ax)              # eyes ahead along local +Z ... in world
    fr, pr = S.upright_frame([0, 0, 0], ax, eye, [0, 0, 1], None, p)
    check("upright: up_local = world up seen from the component", all(abs(a - b) < 1e-9 for a, b in zip(fr["up_local"], [1, 0, 0])), fr)
    check("upright: forward off up, toward the eyes", abs(S._dot(fr["fwd_local"], fr["up_local"])) < 1e-9 and fr["fwd_local"][2] > 0.99, fr)
    check("upright: pin = lift along up", all(abs(a - b) < 1e-9 for a, b in zip(fr["pin_local_cm"], [p["lift_cm"], 0, 0])))
    check("NEG no eyes, no override -> NO_EYES", raises(S.upright_frame, [0, 0, 0], ax, None, [0, 0, 1], None, p, contains="NO_EYES"))
    fo, _ = S.upright_frame([0, 0, 0], ax, None, [0, 0, 1], None, p, fwd_override=[0, 1, 0])
    check("override forward used", fo["fwd_source"] == "override" and fo["fwd_local"][1] > 0.99)
    _f, pr2 = S.upright_frame([0, 0, 0], ax, eye, [0, 0, 1], [-1, 0, 0], p)
    w = S.dir_to_world(fr["fwd_local"], ax)
    _f3, pr3 = S.upright_frame([0, 0, 0], ax, eye, [0, 0, 1], [w[0], w[1], 0], p)
    check("feet agreeing with the face: no problem", not pr3, pr3)
    check("NEG feet opposite the face -> FACING_DISAGREES", any(x.startswith("FACING_DISAGREES") for x in
                                                                S.upright_frame([0, 0, 0], ax, eye, [0, 0, 1], [-w[0], -w[1], 0], p)[1]))
    check("NEG non-orthonormal axes -> AXES problem", any(x.startswith("AXES_NOT_ORTHOGONAL") for x in
                                                          S.upright_frame([0, 0, 0], [[1, 0, 0], [1, 1, 0], [0, 0, 1]], [9, 0, 0],
                                                                          [0, 0, 1], None, p)[1]))
    fw, toes = S.facing_from_feet([0, 10, 90], [0, -10, 90], [12, 10, 2], [0, 10, 5], [12, -10, 2], [0, -10, 5])
    check("feet facing: toes along +X -> +X", fw[0] > 0.99 and toes > 1, (fw, toes))


def t_blender_frame():
    finals = [os.path.join(S.FINALS, n) for n in os.listdir(S.FINALS) if n.endswith(".json") and not n.endswith(".fbx.json")]
    rows = []
    for path in finals:
        d = json.load(open(path, encoding="utf-8"))
        if "pose" in d and "record_head_m_ue_component" in d["pose"]:
            rows.append((os.path.basename(path), d["pose"]["head_bone_m"], d["pose"]["record_head_m_ue_component"]))
    check("finals with both head frames found", len(rows) >= 6, len(rows))
    check("blender_to_ue maps every final's Blender head onto its UE-component head (<1 mm)",
          all(all(abs(a - b) < 1e-3 for a, b in zip(S.blender_to_ue(h), u)) for _n, h, u in rows), rows[:2])
    check("NEG identity mapping fails on at least one final",
          any(any(abs(a - b) > 1e-3 for a, b in zip(h, u)) for _n, h, u in rows))
    rec = json.load(open(S.SHORE02_RECORD, encoding="utf-8"))
    p = dict(S.PARAMS)
    ident = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    shift = lambda v: [v[0] + 3500.0, v[1] + 100.0, v[2] + 40.0]
    head_rec = shift(S._mul(rec["pose"]["record_head_m_ue_component"], 100.0))
    comp = S._add(head_rec, [6.18, 0.95, 0.0])
    fr, pr = S.shore02_frame(rec, shift, comp, head_rec, ident, [0, 0, 1], p)
    check("Shore02: back pin plausible, no problems", not pr, (pr, fr))
    check("Shore02: pin is BEHIND her (against the recorded facing)", S._dot(fr["pin_local_cm"], fr["fwd_local"]) < -10.0, fr)
    check("Shore02: pin above the component origin (mid-back crown is above the bowed head bone)", fr["pin_local_cm"][2] > 5.0, fr)
    bad = copy.deepcopy(rec)
    bad["args"]["crown"] = "head"
    check("NEG a crown-pin record is refused for Shore02", raises(S.shore02_frame, bad, shift, comp, head_rec, ident, [0, 0, 1], p,
                                                                   contains="SHORE02_RECORD"))
    _f, pr2 = S.shore02_frame(rec, shift, S._add(head_rec, [20.0, 0, 0]), head_rec, ident, [0, 0, 1], p)
    check("NEG component 20 cm off the head -> SHORE02_ORIGIN_OFFSET", any(x.startswith("SHORE02_ORIGIN_OFFSET") for x in pr2))
    s = S.build_sheet(2.0, p["quad_cm"], p["fray_depth_cm"], p["seed"] + 1)
    m = S.sheet_metrics(s, S.place_sheet(s, fr, 0.0), p)
    check("Shore02 sheet passes every gate at the back pin", not S.sheet_problems(m, p), (S.sheet_problems(m, p), m))


def t_dataflow():
    p = dict(S.PARAMS)
    nodes, links, term = S.dataflow_spec("/Game/X/SM", [0, 0, 2], p)
    check("spec passes its own gates", not S.dataflow_problems(nodes, links, term, p), S.dataflow_problems(nodes, links, term, p))

    def mutate(key, prop, value):
        n2 = [(k, t, dict(pp)) for k, t, pp in nodes]
        for k, t, pp in n2:
            if k == key:
                pp[prop] = value
        return n2

    for (key, prop, val, want) in (("Stretch", "bStretchUse3dRestLengths", "True", "REST_TRAP"),
                                   ("Bending", "RestAngleType", "Use3DRestAngles", "REST_TRAP"),
                                   ("MaxDistance", "MaxDistance", "(bIsAnimatable=True,Low=0,High=0)", "MAX_DISTANCE"),
                                   ("Import", "UVScale", "(X=1,Y=1)", "PATTERN_SCALE")):
        check("NEG %s.%s=%s -> %s" % (key, prop, val, want),
              any(x.startswith(want) for x in S.dataflow_problems(mutate(key, prop, val), links, term, p)))
    l2 = [x for x in links if x[3] != "MaxDistance.WeightMap"]
    check("NEG weight map unlinked -> WEIGHT_MAP_UNLINKED", "WEIGHT_MAP_UNLINKED" in S.dataflow_problems(nodes, l2, term, p))
    l3 = [x for x in links if not (x[0] == "Mass" and x[2] == "Stretch")]
    check("NEG chain broken -> CHAIN", any(x.startswith("CHAIN") for x in S.dataflow_problems(nodes, l3, term, p)))
    n4 = [x for x in nodes if x[0] != "MaxDistance"] + [x for x in nodes if x[0] == "MaxDistance"]
    check("NEG MaxDistance after the terminal/tethers -> ORDER", any(x.startswith("ORDER") for x in S.dataflow_problems(n4, links, term, p)))
    nb, lb, tb = S.dataflow_spec("/Game/X/SM", [0, 0, 2], p, [-28, 0, -38])
    check("crown+back spec passes its gates (two spheres -> Min -> one falloff)", not S.dataflow_problems(nb, lb, tb, p),
          S.dataflow_problems(nb, lb, tb, p))
    check("crown+back spec: v1 nodes unchanged + BackDistance + PinUnion(FDataflowMinSamplerNode)",
          [k for k, _t, _p in nb if k not in ("BackDistance", "PinUnion")] == [k for k, _t, _p in nodes] and
          dict((k, t) for k, t, _ in nb)["PinUnion"] == "FDataflowMinSamplerNode")
    check("v1 spec unchanged by the v2 code (no back -> same nodes and links as before)",
          ("CrownDistance", "Sampler", "CrownFalloff", "Sampler") in links and not any(k == "PinUnion" for k, _t, _p in nodes))
    lb2 = [x for x in lb if x[0] != "BackDistance"]
    check("NEG back sphere unlinked -> BACK_PIN_UNLINKED", any(x.startswith("BACK_PIN_UNLINKED") for x in S.dataflow_problems(nb, lb2, tb, p)))
    lb3 = lb + [("CrownDistance", "Sampler", "CrownFalloff", "Sampler")]
    check("NEG crown wired around the Min -> BACK_PIN_BYPASSED", any(x.startswith("BACK_PIN_BYPASSED") for x in S.dataflow_problems(nb, lb3, tb, p)))
    check("Min input pin candidates: array form first (CollectionLods[0] ran in v1 BUILD)",
          S._min_input_candidates("InputSamplers[1]") == ["InputSamplers[1]", "InputSamplers_1"] and
          S._min_input_candidates("Sampler") == ["Sampler"])
    ps = dict(p, self_collision=True)
    n5, l5, t5 = S.dataflow_spec("/Game/X/SM", [0, 0, 2], ps)
    check("self-collision variant adds the v2 node and still passes",
          any(k == "SelfCollision" for k, _t, _p in n5) and not S.dataflow_problems(n5, l5, t5, ps))
    # every property name the spec writes is a member of that node's struct in the 5.8 headers (declaration-proven)
    headers = {"FChaosClothAssetStaticMeshImportNode_v2": "StaticMeshImportNode.h",
               "FChaosClothAssetBindToRootBoneNode": "BindToRootBoneNode.h",
               "FChaosClothAssetSimulationMassConfigNode": "SimulationMassConfigNode.h",
               "FChaosClothAssetSimulationStretchConfigNode": "SimulationStretchConfigNode.h",
               "FChaosClothAssetSimulationBendingConfigNode": "SimulationBendingConfigNode.h",
               "FChaosClothAssetSimulationDampingConfigNode": "SimulationDampingConfigNode.h",
               "FChaosClothAssetSimulationAerodynamicsConfigNode": "SimulationAerodynamicsConfigNode.h",
               "FChaosClothAssetSimulationCollisionConfigNode": "SimulationCollisionConfigNode.h",
               "FChaosClothAssetSimulationSelfCollisionConfigNode_v2": "SimulationSelfCollisionConfigNode.h",
               "FChaosClothAssetSimulationSolverConfigNode": "SimulationSolverConfigNode.h",
               "FChaosClothAssetSimulationMaxDistanceConfigNode": "SimulationMaxDistanceConfigNode.h",
               "FChaosClothAssetSimulationLongRangeAttachmentConfigNode_v2": "SimulationLongRangeAttachmentConfigNode.h",
               "FChaosClothAssetTerminalNode_v2": "TerminalNode.h"}
    if os.path.isdir(ENGINE):
        for k, t, pp in n5:
            if t not in headers:
                continue
            text = open(ENGINE + headers[t], encoding="utf-8", errors="replace").read()
            body = text[text.find("struct " + t):]
            check("header: %s declared" % t, ("struct " + t) in text or ("struct UE_DEPRECATED" in text and t in text))
            for prop in pp:
                ok = re.search(r"\b%s\b\s*(=|;|\{)" % re.escape(prop), body[:20000]) is not None
                check("header: %s.%s is a member" % (t, prop), ok)
        text = open(ENGINE + "SimulationStretchConfigNode.h", encoding="utf-8").read()
        check("NEG header scan rejects a made-up member", re.search(r"\bbStretchUse4dRestLengths\b\s*(=|;)", text) is None)
        check("header: ProxyDeformer_v3 exists (render-shell route is declared, not used in v1)",
              "FChaosClothAssetProxyDeformerNode_v3" in open(ENGINE + "ProxyDeformerNode.h", encoding="utf-8").read())
    else:
        check("engine headers absent: member cross-check UNCLEAR (skipped)", True)


def t_census():
    pb = S.planned_packages("BUILD", ["Shore01_M56", "Shore02_F52"], 1, "masked")
    check("BUILD plans materials + 3 assets per figure", len(pb["content"]) == 8 and not pb["exact"], pb)
    pb2 = S.planned_packages("BUILD", ["Shore03_M59"], 1, "masked", existing=[S.names("Shore03_M59", 1)["master"],
                                                                               S.names("Shore03_M59", 1)["mi"]])
    check("BUILD of a later batch does not re-plan existing shared materials", len(pb2["content"]) == 3, pb2)
    check("BUILD census: subset passes", S.census_ok({"content": pb["content"][:3], "maps": []}, pb))
    check("NEG BUILD census: a foreign package fails", not S.census_ok({"content": pb["content"] + ["/Game/Other"], "maps": []}, pb))
    check("NEG BUILD census: the level dirty fails", not S.census_ok({"content": pb["content"], "maps": [S.WORLD]}, pb))
    pb3 = S.planned_packages("BUILD", list(S.FIGURES), 2, "masked", existing=[S.names("Shore01_M56", 2)["master"]])
    check("BUILD v2 plans the v2 MI (master exists) + 18 assets", len(pb3["content"]) == 19 and
          S.names("Shore01_M56", 2)["mi"] in pb3["content"] and S.names("Shore01_M56", 1)["mi"] not in pb3["content"], pb3)
    pa = S.planned_packages("APPLY", list(S.FIGURES), 1, "masked")
    check("APPLY plans the six BPs exactly + the level REQUIRED (instance writes)",
          pa["exact"] and len(pa["content"]) == 6 and pa["maps_required"] == [S.WORLD])
    check("APPLY census: exact + level", S.census_ok({"content": pa["content"], "maps": [S.WORLD]}, pa))
    check("NEG APPLY census: the level clean = the instance writes did not happen",
          not S.census_ok({"content": pa["content"], "maps": []}, pa))
    pr = S.planned_packages("REVERT", list(S.FIGURES), 1, "masked", instances=False)
    check("REVERT of a record without instance writes: the level allowed, not required",
          S.census_ok({"content": pr["content"], "maps": []}, pr) and S.census_ok({"content": pr["content"], "maps": [S.WORLD]}, pr))
    check("NEG APPLY census: one BP not dirty (a write that did not happen)", not S.census_ok({"content": pa["content"][1:], "maps": []}, pa))
    check("NEG APPLY census: an extra package", not S.census_ok({"content": pa["content"] + ["/Game/X"], "maps": []}, pa))
    check("NEG APPLY census: another map", not S.census_ok({"content": pa["content"], "maps": ["/Game/Other/Map"]}, pa))


def _tpl(f, **kw):
    st = {"class": "ChaosClothComponent", "asset": S.OLD_ASSET[f], "override_materials": [S.OLD_MATERIAL],
          "relative_location": [21.0, 0.0, 0.0], "relative_rotation": [0.0, -90.0, 0.0],
          "relative_scale": [S.OLD_SCALE] * 3, "absolute_rotation": False, "attach_socket": "head", "attach_parent": "Body"}
    st.update(kw)
    return st


def t_gates():
    f = "Shore01_M56"
    tpl, inst = _tpl(f), _tpl(f)
    check("before: today's drape passes", not S.before_problems(f, tpl, inst), S.before_problems(f, tpl, inst))
    check("NEG template is a PoseableMeshComponent -> TEMPLATE_CLASS (crash rule)",
          any(x.startswith("TEMPLATE_CLASS") for x in S.before_problems(f, _tpl(f, **{"class": "PoseableMeshComponent"}), inst)))
    check("NEG instance overrides the asset -> INSTANCE_OVERRIDE",
          any(x.startswith("INSTANCE_OVERRIDE") for x in S.before_problems(f, tpl, _tpl(f, asset="/Game/Other"))))
    check("NEG instance overrides materials -> INSTANCE_OVERRIDE",
          any(x.startswith("INSTANCE_OVERRIDE") for x in S.before_problems(f, tpl, _tpl(f, override_materials=["/Game/M"]))))
    check("NEG instance detached (the follower failure) -> INSTANCE_ATTACH",
          any(x.startswith("INSTANCE_ATTACH") for x in S.before_problems(f, tpl, _tpl(f, attach_parent=None))))
    check("NEG already switched template -> TEMPLATE_ASSET", any(x.startswith("TEMPLATE_ASSET") for x in
                                                                 S.before_problems(f, _tpl(f, asset="/Game/New"), inst)))
    after = S.template_target(tpl, "/Game/CA", "/Game/MI")
    d = S.template_diff(tpl, after)
    check("APPLY changes exactly asset, override, scale", set(d) == {"asset", "override_materials", "relative_scale"}, d)
    check("template_diff tolerates 1e-4", not S.template_diff({"relative_scale": [1, 1, 1]}, {"relative_scale": [1.00005, 1, 1]}, ("relative_scale",)))
    good = {"asset": "/Game/CA", "material0": "/Game/MI", "parent_is_this_body": True, "attach_socket": "head",
            "relative_scale": [1, 1, 1], "simulation_enabled": True, "follows_head_cm": 0.1}
    check("PIE: good reading passes", not S.pie_problems(f, good, "/Game/CA", "/Game/MI"))
    for k, v, want in (("asset", S.OLD_ASSET[f], "PIE_ASSET"), ("material0", None, "PIE_MATERIAL"),
                       ("parent_is_this_body", False, "PIE_PARENT"), ("relative_scale", [S.OLD_SCALE] * 3, "PIE_SCALE"),
                       ("simulation_enabled", False, "PIE_SIM_DISABLED"), ("follows_head_cm", 35.0, "PIE_NOT_RIDING"),
                       ("follows_head_cm", None, "PIE_NOT_RIDING")):
        r = dict(good)
        r[k] = v
        check("NEG PIE %s=%r -> %s" % (k, v, want), any(x.startswith(want) for x in S.pie_problems(f, r, "/Game/CA", "/Game/MI")))
    b = S.bounds_metrics([0, 0, 100], [40, 40, 60], 0.0, 160.0)
    check("bounds metric: bottom above feet / top above head", b["bounds_bottom_above_feet_cm"] == 40 and b["bounds_top_above_head_cm"] == 0)


# ================================================================================================ Part B (fake unreal)
class FV:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


class FR:
    def __init__(self, roll, pitch, yaw):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class FAsset:
    def __init__(self, path, cls):
        self.path, self.cls = path, cls

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]

    def get_class(self):
        return _Cls(self.cls)


class _Cls:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


KEYS = {"asset": "asset", "override_materials": "override_materials", "relative_scale3d": "relative_scale"}


class FComp:
    def __init__(self, U, name, cls, owner=None, template=None, parent=None):
        self.U, self.name, self.cls, self.owner, self.template, self.parent = U, name, cls, owner, template, parent
        self.own = {}          # template: all values; instance: overrides only

    def _val(self, k):
        if self.template is not None and k not in self.own:
            return self.template._val(k)
        return self.own[k]

    def get_name(self):
        return self.name

    def get_class(self):
        return _Cls(self.cls)

    def get_path_name(self):
        return "%s:%s" % (self.owner.path if self.owner else "TEMPLATE", self.name)

    def get_asset(self):
        return self.U.assets.get(self._val("asset"))

    def set_asset(self, a):
        if self.U.quirks.get("setter_lies"):
            return
        if self.template is not None and self.U.quirks.get("instance_setter_lies"):
            return
        self.own["asset"] = a.path

    def modify(self):
        if self.template is None:
            self.U.dirty_content.add(self.bp)
        elif not self.U.quirks.get("instance_modify_silent"):
            self.U.dirty_maps.add(S.WORLD)          # a level actor's component: its package is the map

    def get_editor_property(self, k):
        if k == "override_materials":
            return [self.U.assets.get(p) for p in self._val("override_materials")]
        if k == "relative_location":
            return FV(*self._val("relative_location"))
        if k == "relative_rotation":
            return FR(*self._val("relative_rotation"))
        if k == "relative_scale3d":
            return FV(*self._val("relative_scale"))
        if k == "absolute_rotation":
            return self._val("absolute_rotation")
        return 0.0

    def set_editor_property(self, k, v):
        if k == "override_materials":
            self.own["override_materials"] = [m.path if m else None for m in v]
        elif k == "relative_scale3d":
            self.own["relative_scale"] = [v.x, v.y, v.z]

    def get_attach_socket_name(self):
        return "head" if self.parent else "None"

    def get_attach_parent(self):
        return self.parent


class FActor:
    def __init__(self, U, fig):
        self.U, self.fig, self.path = U, fig, "/Game/Level.Level:PersistentLevel.BP_%s_Draped_C_0" % fig
        self.body = FComp(U, "Body", "SkeletalMeshComponent", owner=self)
        self.cloth = FComp(U, "ShoreHeadCloth", "ChaosClothComponent", owner=self, template=U.templates[fig], parent=self.body)

    def get_actor_label(self):
        return self.fig + " Clam"

    def get_class(self):
        return _Cls("BP_%s_Draped_C" % self.fig)

    def get_components_by_class(self, _c):
        return [self.body, self.cloth]


def make_fake(quirks=None):
    U = type("FakeUnreal", (), {})()
    U.quirks = dict(quirks or {})
    U.log_lines = []
    U.assets = {}
    for f in S.FIGURES:
        U.assets[S.OLD_ASSET[f]] = FAsset(S.OLD_ASSET[f], "ChaosClothAsset")
        for v in (1, 2):
            nm = S.names(f, v)
            U.assets[nm["cloth"]] = FAsset(nm["cloth"], "ChaosClothAsset")
            U.assets[nm["mi"]] = FAsset(nm["mi"], "MaterialInstanceConstant")
    U.assets[S.OLD_MATERIAL] = FAsset(S.OLD_MATERIAL, "Material")
    U.templates, U.bps = {}, {}
    for f in S.FIGURES:
        t = FComp(U, "ShoreHeadCloth", "ChaosClothComponent")
        t.own = {"asset": S.OLD_ASSET[f], "override_materials": [S.OLD_MATERIAL], "relative_location": [21.0, 0.0, 0.0],
                 "relative_rotation": [0.0, -90.0, 0.0], "relative_scale": [S.OLD_SCALE] * 3, "absolute_rotation": f == "Shore02_F52"}
        t.bp = S.names(f, 1)["bp"]
        t.template = None
        U.templates[f] = t
        U.bps[t.bp] = (FAsset(t.bp, "Blueprint"), t)
    U.actors = {f: FActor(U, f) for f in S.FIGURES}
    if U.quirks.get("instance_asset_pinned", True):
        # MEASURED 6 Oct: each placed figure carries its OWN asset value (create_pinned_shore_drape.py set it on the
        # level actor); APPLY v1 saved the templates and the level kept CA_ShoreHeadDrape (INSTANCE_READBACK refusal)
        for f in S.FIGURES:
            U.actors[f].cloth.own["asset"] = S.OLD_ASSET[f]
    for k, v in (U.quirks.get("instance_override") or {}).items():
        U.actors[k].cloth.own.update(v)
    U.dirty_content, U.dirty_maps = set(), set()
    U.log = lambda s: U.log_lines.append(s)
    U.log_error = lambda s: U.log_lines.append("ERR " + s)
    U.Vector = FV
    U.load_asset = lambda p: U.assets.get(p) or (U.bps[p][0] if p in U.bps else None)

    class EAL:
        @staticmethod
        def does_asset_exist(p):
            return p in U.assets or p in U.bps

        @staticmethod
        def save_asset(p, only_if_is_dirty=False):
            if U.quirks.get("save_fails") == p:
                return False
            U.dirty_content.discard(p)
            return True
    U.EditorAssetLibrary = EAL

    class BEL:
        @staticmethod
        def compile_blueprint(bp):
            if U.quirks.get("compile_dirties_map"):
                U.dirty_maps.add(S.WORLD)
            if U.quirks.get("compile_dirties_other"):
                U.dirty_content.add("/Game/Metahuman/Other")
            return True
    U.BlueprintEditorLibrary = BEL

    class ELSU:
        @staticmethod
        def get_dirty_content_packages():
            return [_Cls(p) for p in sorted(U.dirty_content)]

        @staticmethod
        def get_dirty_map_packages():
            return [_Cls(p) for p in sorted(U.dirty_maps)]

        @staticmethod
        def save_map(world, path):
            U.dirty_maps.discard(path)
            return True
    U.EditorLoadingAndSavingUtils = ELSU
    U.GameplayStatics = type("GS", (), {"get_all_actors_of_class": staticmethod(lambda w, c: list(U.actors.values()))})
    U.Actor = object
    U.ActorComponent = object
    return U


def bind(U, tmp):
    """Point the tool's glue at the fake: module `unreal`, records and backups in a temp dir. The functions that
    talk to UE object lookups (_template, _figure_actors, _backup) are the seam; everything above them is the tool's."""
    S.unreal = U
    S.RECORDS = {"BUILD": os.path.join(tmp, "build.json"), "APPLY": os.path.join(tmp, "apply.json")}
    S._template = lambda bp_path: U.bps[bp_path]
    S._figure_actors = lambda figs, world=None: {f: U.actors[f] for f in figs}
    S._backup = lambda run, figs: (os.path.join(tmp, "backup-" + run), [{"src": "x"}])
    S._temp_actor_guard = lambda world: None
    build = {"versions": {str(v): {"figures": {f: {"names": S.names(f, v)} for f in S.FIGURES},
                                   "params": dict(S.PARAMS), "materials_created": []} for v in (1, 2)}}
    with open(S.RECORDS["BUILD"], "w") as h:
        json.dump(build, h)


class _Ed:
    def get_editor_world(self):
        return object()


def fake_run(quirks=None, between=None, figs=None, version=1, record_hook=None, patch=None):
    """APPLY then REVERT through the tool's glue on the fake. record_hook(rec) may rewrite the APPLY record between
    them (e.g. into the shape the real 6 Oct v1 record has); patch = {tool attr: replacement} for the whole run."""
    tmp = tempfile.mkdtemp(prefix="livesack_")
    U = make_fake(quirks)
    keys = ("unreal", "RECORDS", "_template", "_figure_actors", "_backup", "_temp_actor_guard") + tuple(patch or {})
    real = {k: getattr(S, k) for k in keys}
    out = {"U": U, "tmp": tmp}
    try:
        bind(U, tmp)
        for k, v in (patch or {}).items():
            setattr(S, k, v)
        figs = figs or list(S.FIGURES)
        try:
            out["apply"] = S.run_apply("RUN-A", figs, version, dict(S.PARAMS), _Ed())
        except Exception as exc:  # noqa: BLE001
            out["apply_error"] = str(exc)
            out["record"] = json.load(open(S.RECORDS["APPLY"])) if os.path.exists(S.RECORDS["APPLY"]) else None
            out["instances_now"] = {f: dict(U.actors[f].cloth.own) for f in figs}
            return out
        out["record"] = json.load(open(S.RECORDS["APPLY"]))
        out["after_apply"] = {f: dict(U.templates[f].own) for f in figs}
        out["instances_after_apply"] = {f: S._instance_state(U.actors[f]) for f in figs}
        out["dirty_after_apply"] = (sorted(U.dirty_content), sorted(U.dirty_maps))
        if record_hook:
            rec = json.load(open(S.RECORDS["APPLY"]))
            record_hook(rec)
            with open(S.RECORDS["APPLY"], "w") as h:
                json.dump(rec, h)
        if between:
            between(U)
        try:
            out["revert"] = S.run_revert("RUN-R", _Ed())
        except Exception as exc:  # noqa: BLE001
            out["revert_error"] = str(exc)
        out["after_revert"] = {f: dict(U.templates[f].own) for f in figs}
        out["instances_after_revert"] = {f: S._instance_state(U.actors[f]) for f in figs}
        out["files"] = sorted(os.listdir(tmp))
        return out
    finally:
        for k, v in real.items():
            setattr(S, k, v)
        shutil.rmtree(tmp, ignore_errors=True)


def t_fake():
    r = fake_run()
    check("fake APPLY ok", "apply" in r, r.get("apply_error"))
    if "apply" in r:
        f = "Shore01_M56"
        nm = S.names(f, 1)
        a = r["after_apply"][f]
        check("APPLY: template asset/material/scale switched", a["asset"] == nm["cloth"] and a["override_materials"] == [nm["mi"]]
              and a["relative_scale"] == [1.0, 1.0, 1.0], a)
        check("APPLY: location/rotation/absolute kept", a["relative_location"] == [21.0, 0.0, 0.0] and
              a["relative_rotation"] == [0.0, -90.0, 0.0] and r["after_apply"]["Shore02_F52"]["absolute_rotation"] is True)
        i = r["instances_after_apply"][f]
        check("APPLY: the level instance (own asset value, as measured 6 Oct) gets the new asset by the INSTANCE write, "
              "the MI + scale via the template", i["asset"] == nm["cloth"] and
              i["override_materials"] == [nm["mi"]] and i["parent_is_this_body"], i)
        check("APPLY: record carries the instance before-values for REVERT",
              r["record"]["instance_asset_override"] == {g: S.OLD_ASSET[g] for g in S.FIGURES} and
              all(r["record"]["before"][g]["instance"]["asset"] == S.OLD_ASSET[g] for g in S.FIGURES))
        check("APPLY: one save scope: BPs + the level, nothing left dirty", r["dirty_after_apply"] == ([], []), r["dirty_after_apply"])
        check("REVERT: every instance asset back to the old drape",
              all(r["instances_after_revert"][g]["asset"] == S.OLD_ASSET[g] for g in S.FIGURES), r.get("revert_error"))
        check("REVERT ok and restores every template exactly", "revert" in r and
              all(r["after_revert"][g]["asset"] == S.OLD_ASSET[g] and r["after_revert"][g]["override_materials"] == [S.OLD_MATERIAL]
                  and abs(r["after_revert"][g]["relative_scale"][0] - S.OLD_SCALE) < 1e-9 for g in S.FIGURES), r.get("revert_error"))
        check("REVERT renames the record (.reverted-RUN-R)", any(x.startswith("apply.json.reverted-RUN-R") for x in r["files"]), r["files"])
        check("census empty after APPLY and REVERT", not r["U"].dirty_content and not r["U"].dirty_maps)

    r = fake_run({"compile_dirties_map": True})
    check("BP compile dirtying the level: allowed and saved", "apply" in r and not r["U"].dirty_maps, r.get("apply_error"))

    r = fake_run({"compile_dirties_other": True})
    check("NEG compile dirtying a foreign package -> DIRTY_SCOPE, nothing saved",
          "DIRTY_SCOPE" in r.get("apply_error", "") and r["U"].dirty_content, r.get("apply_error"))

    r = fake_run({"instance_override": {"Shore04_F55": {"asset": S.OLD_ASSET["Shore04_F55"] + "_X"}}})
    check("NEG level instance overriding the asset -> refused BEFORE any write",
          "INSTANCE_OVERRIDE" in r.get("apply_error", "") and
          all(r["U"].templates[g].own["asset"] == S.OLD_ASSET[g] for g in S.FIGURES), r.get("apply_error"))

    r = fake_run({"setter_lies": True})
    check("NEG a lying set_asset -> TEMPLATE_READBACK (never trusted)", "TEMPLATE_READBACK" in r.get("apply_error", ""), r.get("apply_error"))

    r = fake_run({"instance_override": {"Shore06_F25": {"relative_scale": [S.OLD_SCALE] * 3}}}, figs=["Shore01_M56"])
    check("pilot APPLY of one figure ignores the others' instances", "apply" in r, r.get("apply_error"))

    def drift(U):
        U.templates["Shore03_M59"].own["relative_scale"] = [2.0, 2.0, 2.0]
    r = fake_run(between=drift)
    check("NEG REVERT refuses on drift (template changed after APPLY) and writes nothing",
          "REVERT_REFUSED" in r.get("revert_error", "") and r["after_revert"]["Shore01_M56"]["asset"] == S.names("Shore01_M56", 1)["cloth"],
          r.get("revert_error"))

    def break_instance(U):   # a level edit after APPLY changed one placed figure's cloth
        U.actors["Shore05_M53"].cloth.own["asset"] = "/Game/Elsewhere"
    r = fake_run(between=break_instance)
    check("NEG REVERT: an instance asset changed after APPLY -> REVERT_REFUSED/INSTANCE_DRIFT, nothing written",
          "INSTANCE_DRIFT|Shore05_M53" in r.get("revert_error", "") and
          r["after_revert"]["Shore01_M56"]["asset"] == S.names("Shore01_M56", 1)["cloth"], r.get("revert_error"))

    def override_mats(U):    # an instance that will not come back (it overrides materials since APPLY)
        U.actors["Shore04_F55"].cloth.own["override_materials"] = ["/Game/Elsewhere/M"]
    r = fake_run(between=override_mats)
    check("NEG REVERT: an instance that does not come back -> REVERT_INSTANCE before the save (nothing saved)",
          "REVERT_INSTANCE|Shore04_F55" in r.get("revert_error", "") and r["U"].dirty_content, r.get("revert_error"))

    # ---- the instance-asset write (v2 tool: APPLY writes it; v1's APPLY did not and was refused live)
    r = fake_run(patch={"_set_instance_asset": lambda actor, path: None})
    check("NEG APPLY without the instance write (the v1 behaviour) -> INSTANCE_READBACK before any save",
          "INSTANCE_READBACK" in r.get("apply_error", "") and r["record"] and r["record"]["saved"] is False and
          r["U"].dirty_content, r.get("apply_error"))
    r = fake_run({"instance_setter_lies": True})
    check("NEG a lying instance set_asset -> INSTANCE_READBACK, nothing saved (BPs still dirty)",
          "INSTANCE_READBACK" in r.get("apply_error", "") and r["U"].dirty_content, r.get("apply_error"))
    r = fake_run({"instance_modify_silent": True})
    check("NEG the instance write does not dirty the level -> DIRTY_SCOPE (level REQUIRED in the save scope)",
          "DIRTY_SCOPE" in r.get("apply_error", ""), r.get("apply_error"))
    r = fake_run({"instance_asset_pinned": False})
    check("instances that DO follow the template: the instance write is harmless, APPLY + REVERT ok",
          "apply" in r and "revert" in r, (r.get("apply_error"), r.get("revert_error")))

    # ---- REVERT of the real 6 Oct v1 record shape (instance fix: no instance_write key, RECONSTRUCTED after.instance
    # with the OLD material/scale, which VERIFY S3LIVESACK-20261006-172851 contradicts: never compared)
    def v1_shape(rec):
        rec.pop("instance_write", None)
        for g in rec["figures"]:
            rec["after"][g]["instance"].update({"override_materials": [S.OLD_MATERIAL], "relative_scale": [S.OLD_SCALE] * 3})
            rec["after"][g]["note"] = "reconstructed 6 Oct from template_target (instance-fix run)"
    r = fake_run(record_hook=v1_shape)
    check("REVERT of the real v1 record shape: templates + instance assets restored, one save, record renamed",
          "revert" in r and all(r["instances_after_revert"][g]["asset"] == S.OLD_ASSET[g] for g in S.FIGURES) and
          not r["U"].dirty_content and not r["U"].dirty_maps and
          any(x.startswith("apply.json.reverted-RUN-R") for x in r["files"]), r.get("revert_error"))

    def no_inst_record(rec):
        rec.pop("instance_asset_override", None)
    r = fake_run(record_hook=no_inst_record)
    check("NEG REVERT of a record WITHOUT the instance map, on pinned instances -> REVERT_INSTANCE (instances would stay "
          "on the sack): the map is what makes REVERT complete", "REVERT_INSTANCE" in r.get("revert_error", ""), r.get("revert_error"))

    # ---- v2 round trip
    r = fake_run(version=2)
    f = "Shore05_M53"
    check("v2 APPLY: template + instance on CA_..._v2 and MI _v2; REVERT restores the old drape",
          "apply" in r and r["instances_after_apply"][f]["asset"] == S.names(f, 2)["cloth"] and
          r["instances_after_apply"][f]["override_materials"] == [S.names(f, 2)["mi"]] and
          "revert" in r and r["instances_after_revert"][f]["asset"] == S.OLD_ASSET[f], (r.get("apply_error"), r.get("revert_error")))

    r = fake_run({"save_fails": S.names("Shore02_F52", 1)["bp"]})
    check("NEG a failed save -> SAVE_ASSET_FAILED, the record stays unsaved", "SAVE_ASSET_FAILED" in r.get("apply_error", ""),
          r.get("apply_error"))


def main():
    for t in (t_params, t_modes, t_files, t_binary_facts, t_sheet, t_lean, t_back_geometry, t_material, t_frames,
              t_blender_frame, t_dataflow, t_census, t_gates, t_fake):
        try:
            t()
        except Exception as exc:  # noqa: BLE001 - a crashed test is a failed test
            import traceback
            check("%s crashed" % t.__name__, False, traceback.format_exc()[-600:])
    fails = [r for r in RESULTS if not r["pass"]]
    report = {"checks": len(RESULTS), "fails": fails, "results": RESULTS}
    with open(os.path.join(HERE, "test_s3_sack_livecloth_offline_report.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    for r in fails:
        print("FAIL", r["check"], r["detail"])
    print("S3LIVESACK_OFFLINE_%s|checks=%d|fails=%d" % ("OK" if not fails else "FAILED", len(RESULTS), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
