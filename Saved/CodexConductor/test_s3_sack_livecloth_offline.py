"""Offline harness for s3_sack_livecloth.py (no Unreal). Every gate has a NEGATIVE CONTROL that must fail.

Part A  pure helpers: params, modes, census, the sheet (isometric 2D pattern, winding, pin disc, torn edge, UV1,
        determinism), the component-frame geometry (upright eyes / Shore02 recorded back pin), the Dataflow spec, the
        BP / PIE gates; cross-checked against the REAL files (Blender finals, the BP and cloth .uasset bytes, the UE 5.8
        Chaos Cloth headers) where those carry the fact.
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


def t_files():
    """The paths the tool names exist on disk today (declaration: Content listing, 6 Oct)."""
    for f in S.FIGURES:
        check("BP on disk: %s" % f, os.path.exists(content_file(S.names(f, 1)["bp"])))
        check("old cloth asset on disk: %s" % S.OLD_ASSET[f], os.path.exists(content_file(S.OLD_ASSET[f])))
    for p in (S.SRC_MASTER["masked"], S.SRC_MASTER["opaque"], S.SRC_MI, S.OLD_MATERIAL):
        check("source material on disk: %s" % p, os.path.exists(content_file(p)))
    check("umap on disk", os.path.exists(S.UMAP))
    check("Shore02 record on disk", os.path.exists(S.SHORE02_RECORD))
    taken = [S.names(f, 1)[k] for f in S.FIGURES for k in ("mesh", "dataflow", "cloth")] + \
            [S.names("Shore01_M56", 1)[k] for k in ("master", "mi")]
    check("v1 targets are free (create-only)", not [p for p in taken if os.path.exists(content_file(p))],
          [p for p in taken if os.path.exists(content_file(p))])
    check("targets live under ShoreCast Cloth/LiveSack or Sack/Materials",
          all(p.startswith(S.LIVE_DIR + "/") or p.startswith(S.MAT_DIR + "/") for p in taken))


def t_binary_facts():
    """Binary-proven facts the design leans on (strings in the saved .uasset)."""
    for f in S.FIGURES:
        s = strings(content_file(S.names(f, 1)["bp"]))
        check("BP %s: ConfigureShoreDrape attaches + collides (K2_AttachToComponent, AddCollisionSource)" % f,
              {"ConfigureShoreDrape", "K2_AttachToComponent", "AddCollisionSource", "ResetCollisionSources"} <= s)
        check("BP %s: no SetMaterial/SetAsset/SetSkinnedAsset symbol (construction cannot reset our material/asset)" % f,
              not any(x in s for x in ("SetMaterial", "SetAsset", "SetSkinnedAssetAndUpdate", "SetClothAsset")))
        check("BP %s: template references the old asset + M_ShoreLinen + OverrideMaterials" % f,
              S.OLD_ASSET[f] in s and S.OLD_MATERIAL in s and "OverrideMaterials" in s)
        check("BP %s: collision = the drape PHYS" % f, "%s/Cloth/PHYS_%s_Drape" % (S.ROOT, f) in s)
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
    pa = S.planned_packages("APPLY", list(S.FIGURES), 1, "masked")
    check("APPLY plans the six BPs exactly", pa["exact"] and len(pa["content"]) == 6)
    check("APPLY census: exact + level allowed", S.census_ok({"content": pa["content"], "maps": [S.WORLD]}, pa))
    check("APPLY census: exact without the level", S.census_ok({"content": pa["content"], "maps": []}, pa))
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
        self.own["asset"] = a.path

    def modify(self):
        if self.template is None:
            self.U.dirty_content.add(self.bp)

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
        nm = S.names(f, 1)
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
    build = {"versions": {"1": {"figures": {f: {"names": S.names(f, 1)} for f in S.FIGURES},
                                "params": dict(S.PARAMS), "materials_created": []}}}
    with open(S.RECORDS["BUILD"], "w") as h:
        json.dump(build, h)


class _Ed:
    def get_editor_world(self):
        return object()


def fake_run(quirks=None, between=None, figs=None):
    tmp = tempfile.mkdtemp(prefix="livesack_")
    U = make_fake(quirks)
    real = {k: getattr(S, k) for k in ("unreal", "RECORDS", "_template", "_figure_actors", "_backup", "_temp_actor_guard")}
    out = {"U": U, "tmp": tmp}
    try:
        bind(U, tmp)
        figs = figs or list(S.FIGURES)
        try:
            out["apply"] = S.run_apply("RUN-A", figs, 1, dict(S.PARAMS), _Ed())
        except Exception as exc:  # noqa: BLE001
            out["apply_error"] = str(exc)
            return out
        out["after_apply"] = {f: dict(U.templates[f].own) for f in figs}
        out["instances_after_apply"] = {f: S._instance_state(U.actors[f]) for f in figs}
        if between:
            between(U)
        try:
            out["revert"] = S.run_revert("RUN-R", _Ed())
        except Exception as exc:  # noqa: BLE001
            out["revert_error"] = str(exc)
        out["after_revert"] = {f: dict(U.templates[f].own) for f in figs}
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
        check("APPLY: the level instance sees the new asset + MI via the template", i["asset"] == nm["cloth"] and
              i["override_materials"] == [nm["mi"]] and i["parent_is_this_body"], i)
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

    def break_instance(U):   # an instance that stopped following the template (e.g. a level edit after APPLY)
        U.actors["Shore05_M53"].cloth.own["asset"] = "/Game/Elsewhere"
    r = fake_run(between=break_instance)
    check("NEG REVERT: an instance that does not come back -> REVERT_INSTANCE",
          "REVERT_INSTANCE" in r.get("revert_error", ""), r.get("revert_error"))

    r = fake_run({"save_fails": S.names("Shore02_F52", 1)["bp"]})
    check("NEG a failed save -> SAVE_ASSET_FAILED, the record stays unsaved", "SAVE_ASSET_FAILED" in r.get("apply_error", ""),
          r.get("apply_error"))


def main():
    for t in (t_params, t_modes, t_files, t_binary_facts, t_sheet, t_frames, t_blender_frame, t_dataflow, t_census,
              t_gates, t_fake):
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
