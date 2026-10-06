"""Offline harness for s3_shore_skin.py (no Unreal). Every gate has a NEGATIVE CONTROL that must fail.

Synthetic parents mirror the baked skin MIs: post-bake multipliers 1.0, offsets 0.0, micro tiling 32, normal
strength 1.0 (values INVENTED for the maths; the live DRY reads the real ones).
Run: python Saved/CodexConductor/test_s3_shore_skin_offline.py   -> exit 0 and S3SKIN_OFFLINE_OK
"""
import ast
import importlib.util
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("_t_s3_shore_skin", os.path.join(HERE, "s3_shore_skin.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"check": name, "pass": bool(cond), "detail": str(detail)[:300]})


def raises(fn, *a, contains=None, **kw):
    try:
        fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001
        return contains is None or contains in str(exc)
    return False


PARENT_S = {"Basecolor Global Value Post-Bake": 1.0, "Basecolor Global Saturation Post-Bake": 1.0,
            "Basecolor Global Hue Post-Bake": 0.0, "Roughness Global Multiply Post-Bake": 1.0,
            "Roughness Global Offset Post-Bake": 0.0, "Specular Global Multiply Post-Bake": 1.0,
            "Scatter Distance Global Multiply Post-Bake": 1.0, "Normal Global Strength Post-Bake": 1.0,
            "Micro Skin Normal Strength": 1.0, "Micro Skin Tiling": 32.0, "Micro Skin Roughess": 0.5,
            "Micro Skin Cavity Specular Multiply": 1.0, "Fake SSS Strength": 1.0, "Material AO Power": 1.0}
PARENT_V = {"Basecolor Global Multiply Post-Bake": [1.0, 1.0, 1.0, 1.0]}


def t_table():
    check("six figures", sorted(S.FIGURES) == ["Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55",
                                               "Shore05_M53", "Shore06_F25"])
    check("knobs in [0,1]", all(0.0 <= v <= 1.0 for k in S.FIGURES.values() for v in k.values()))
    vecs = [tuple(k[x] for x in "PSA") for k in S.FIGURES.values()]
    gaps = [max(abs(a[i] - b[i]) for i in range(3)) for a, b in itertools.combinations(vecs, 2)]
    check("every pair differs by >= 0.1 on some knob (variation)", min(gaps) >= 0.1, min(gaps))
    check("Shore06 (25) is the least aged", min(S.FIGURES, key=lambda f: S.FIGURES[f]["A"]) == "Shore06_F25")
    check("Shore03 (59) is the most aged", max(S.FIGURES, key=lambda f: S.FIGURES[f]["A"]) == "Shore03_M59")
    check("strength clamps to 1", S.knobs_for("Shore03_M59", 1.5)["A"] == 1.0)
    check("NEG strength out of range refuses", raises(S.knobs_for, "Shore01_M56", 3.0, contains="STRENGTH"))
    check("NEG unknown figure refuses", raises(S.knobs_for, "Shore07_X", contains="FIGURE"))


def t_values():
    rows = {}
    for f in S.FIGURES:
        v = S.plan_values(S.knobs_for(f), PARENT_S, PARENT_V)
        rows[f] = v
        check("no problems " + f, not v["problems"], v["problems"])
        s = v["scalars"]
        check("paler: value up %s" % f, s["Basecolor Global Value Post-Bake"] > 1.0, s)
        check("sallow: saturation down %s" % f, 0.5 <= s["Basecolor Global Saturation Post-Bake"] < 1.0, s)
        check("dry: roughness up %s" % f, s["Roughness Global Multiply Post-Bake"] > 1.0)
        check("dry: specular down %s" % f, s["Specular Global Multiply Post-Bake"] < 1.0)
        check("less SSS %s" % f, s["Scatter Distance Global Multiply Post-Bake"] < 1.0)
        check("creases: normal up %s" % f, s["Normal Global Strength Post-Bake"] > 1.0)
        check("crepe: micro tiling finer %s" % f, s["Micro Skin Tiling"] > 32.0)
        t = v["vectors"]["Basecolor Global Multiply Post-Bake"]
        check("tint R>=G>=B %s" % f, t[0] >= t[1] >= t[2], t)
        check("alpha kept %s" % f, t[3] == 1.0)
        check("hue untouched by default %s" % f, "Basecolor Global Hue Post-Bake" not in s)
        check("offset param never touched %s" % f, "Roughness Global Offset Post-Bake" not in s)
    # relative to the parent: a parent at 0.8 saturation gives 0.8 * factor
    k = S.knobs_for("Shore05_M53")
    p2 = dict(PARENT_S, **{"Basecolor Global Saturation Post-Bake": 0.8})
    v2 = S.plan_values(k, p2, PARENT_V)
    f = 1.0 - 0.30 * k["S"] - 0.10 * k["P"]
    check("relative to live parent", abs(v2["scalars"]["Basecolor Global Saturation Post-Bake"] - 0.8 * f) < 1e-4)
    check("most jaundiced figure has the strongest blue cut",
          min(S.FIGURES, key=lambda x: rows[x]["vectors"]["Basecolor Global Multiply Post-Bake"][2]) == "Shore05_M53")
    # hue opt-in
    vh = S.plan_values(k, PARENT_S, PARENT_V, hue_turns=0.02)
    check("hue opt-in applies", abs(vh["scalars"]["Basecolor Global Hue Post-Bake"] - 0.02 * k["S"]) < 1e-5)
    check("NEG hue too large refuses", any("HUE_RANGE" in p for p in S.plan_values(k, PARENT_S, PARENT_V, 0.2)["problems"]))
    # skips and refusals
    vs = S.plan_values(k, dict(PARENT_S, **{"Basecolor Global Multiply Post-Bake": 1.0}), {})
    check("multiply as scalar -> skipped, not guessed", any("IS_SCALAR" in x for x in vs["skipped"])
          and "Basecolor Global Multiply Post-Bake" not in vs["scalars"])
    vz = S.plan_values(k, dict(PARENT_S, **{"Fake SSS Strength": 0.0}), PARENT_V)
    check("parent zero multiply -> skipped", any("PARENT_ZERO" in x for x in vz["skipped"]))
    vm = S.plan_values(k, {"Micro Skin Tiling": 32.0}, {})
    check("NEG core params missing refuses", any("CORE_PARAMS_MISSING" in p for p in vm["problems"]))
    old = S.RULES["Roughness Global Multiply Post-Bake"]
    S.RULES["Roughness Global Multiply Post-Bake"] = ("mul", lambda kk: 3.0)
    vr = S.plan_values(k, PARENT_S, PARENT_V)
    S.RULES["Roughness Global Multiply Post-Bake"] = old
    check("NEG factor out of range refuses", any("FACTOR_RANGE" in p for p in vr["problems"]))
    check("NEG pink tint refuses", bool(S.tint_problems("x", [0.9, 0.95, 0.8])))
    check("NEG dark tint refuses", bool(S.tint_problems("x", [0.7, 0.7, 0.7])))
    check("sallow tint at S=1 passes gates", not S.tint_problems("x", S.sallow_tint(1.0)), S.sallow_tint(1.0))


def t_switch():
    sets, pr = S.switch_plan({S.POST_BAKE_SWITCH: False}, True)
    check("switch off + enable -> child sets it", sets == {S.POST_BAKE_SWITCH: True} and not pr)
    sets, pr = S.switch_plan({S.POST_BAKE_SWITCH: False}, False)
    check("NEG switch off + disabled -> POST_BAKE_INERT", any("POST_BAKE_INERT" in p for p in pr))
    sets, pr = S.switch_plan({S.POST_BAKE_SWITCH: None}, True)
    check("NEG switch unreadable refuses", any("UNREADABLE" in p for p in pr))
    sets, pr = S.switch_plan({S.POST_BAKE_SWITCH: True}, True)
    check("switch already on -> no override (no new permutation)", sets == {} and not pr)


def face_slots(fig):
    pp = S.parent_paths(fig)
    names = ["head_shader_shader", "teeth_shader_shader", "saliva_shader_shader", "eyeLeft_shader_shader",
             "eyeRight_shader_shader", "eyeshell_shader_shader", "eyelashes_shader_shader", "eyeEdge_shader_shader",
             "cartilage_shader_shader", "head_LOD1_shader_shader", "head_LOD2_shader_shader",
             "eyelashes_HiLOD_shader_shader", "head_LOD3_shader_shader", "head_LOD4_shader_shader",
             "head_LOD57_shader_shader"]
    mats = {"head_LOD3_shader_shader": pp["face"][0], "head_LOD57_shader_shader": pp["face"][1],
            "teeth_shader_shader": "/Game/x/MI_Teeth_Baked"}
    return [{"index": i, "name": n, "material": mats.get(n)} for i, n in enumerate(names)]


def t_slots():
    f = "Shore02_F52"
    pp = S.parent_paths(f)
    p2c = {p: S.child_path(f, p, "v1") for p in pp["face"] + pp["body"]}
    rows, arr, pr = S.plan_slots(face_slots(f), [], p2c)
    check("face: exactly the two skin slots", sorted(r["slot"] for r in rows) ==
          ["head_LOD3_shader_shader", "head_LOD57_shader_shader"] and not pr, rows)
    check("face: other slots stay None", [i for i, m in enumerate(arr) if m] == [12, 14], arr)
    check("teeth untouched", arr[1] is None)
    rows, arr, pr = S.plan_slots([{"index": 0, "name": "body_shader_shader", "material": pp["body"][0]}], [], p2c)
    check("body: slot 0", arr == [p2c[pp["body"][0]]] and not pr)
    rows, arr, pr = S.plan_slots(face_slots(f), [None] * 12 + ["/Game/Other/MI_X"], p2c)
    check("NEG foreign override refuses", any("FOREIGN_OVERRIDE" in p for p in pr))
    rows, arr, pr = S.plan_slots([{"index": 0, "name": "x", "material": "/Game/Not/Skin"}], [], p2c)
    check("NEG no skin slot refuses", any("NO_SKIN_SLOT" in p for p in pr))
    rows, arr, pr = S.plan_slots(face_slots(f), [None] * 12 + [p2c[pp["face"][0]]], p2c)
    check("idempotent: our own override is not foreign", not pr)


def t_paths():
    allp = [S.child_path(f, p, "v1") for f in S.FIGURES for ps in S.parent_paths(f).values() for p in ps]
    check("18 children, unique", len(allp) == 18 and len(set(allp)) == 18)
    check("children under Skin/", all(p.startswith(S.SKIN_DIR + "/MI_S3Skin_") for p in allp))
    check("children never overwrite a parent path", not set(allp) & {p for f in S.FIGURES
                                                                      for ps in S.parent_paths(f).values() for p in ps})
    check("version in the name", S.child_path("Shore01_M56", S.parent_paths("Shore01_M56")["body"][0], "v2")
          .endswith("_Body_Baked_VT_v2"))
    check("NEG bad version refuses", raises(S.child_path, "Shore01_M56", "/a/MI_B", "v 1", contains="LOOK_VERSION"))
    check("bp file mapping", S.bp_file("Shore01_M56") ==
          "E:/PussStage/Content/Metahuman/ShoreCast_20260910/SceneCharacters/BP_Shore01_M56_Draped.uasset")
    on_disk = [S.bp_file(f) for f in S.FIGURES]
    check("the six BP files exist on disk", all(os.path.isfile(p) for p in on_disk), on_disk)
    parents = [S.CONTENT + p[len("/Game/"):] + ".uasset" for f in S.FIGURES
               for ps in S.parent_paths(f).values() for p in ps]
    check("the 18 parent MI files exist on disk", all(os.path.isfile(p) for p in parents))
    check("no child exists yet on disk", not any(os.path.isfile(S.CONTENT + p[len("/Game/"):] + ".uasset")
                                                 for p in allp))


def t_census_mode():
    figs = sorted(S.FIGURES)
    created = [S.child_path(f, p, "v1") for f in figs for ps in S.parent_paths(f).values() for p in ps]
    pb = S.planned_packages("bp", figs, created)
    check("bp plan = 18 MIs + 6 BPs, no map", len(pb["content"]) == 24 and pb["maps"] == [])
    pl = S.planned_packages("level", figs, created)
    check("level plan = 18 MIs + the map", len(pl["content"]) == 18 and pl["maps"] == [S.WORLD])
    check("census exact passes", S.census_ok({"content": list(pb["content"]), "maps": []}, pb))
    check("NEG extra package fails", not S.census_ok({"content": pb["content"] + ["/Game/X"], "maps": []}, pb))
    check("NEG missing package fails", not S.census_ok({"content": pb["content"][1:], "maps": []}, pb))
    check("NEG map dirty under bp fails", not S.census_ok({"content": pb["content"], "maps": [S.WORLD]}, pb))
    check("map dirty under bp allowed only with the flag",
          S.census_ok({"content": pb["content"], "maps": [S.WORLD]}, pb, allow_map=True))
    check("NEG other map never allowed",
          not S.census_ok({"content": pb["content"], "maps": ["/Game/Other"]}, pb, allow_map=True))
    check("DRY default ok", S.check_mode({"mode": "DRY"}, False)[0] == "DRY")
    check("NEG APPLY without confirm", raises(S.check_mode, {"mode": "APPLY"}, False, contains="CONFIRM"))
    check("NEG APPLY wrong word", raises(S.check_mode, {"mode": "APPLY", "confirm": "APPLY S3MARBLE"}, False))
    check("APPLY confirm ok", S.check_mode({"mode": "APPLY", "confirm": "APPLY S3SKIN"}, False)[0] == "APPLY")
    check("NEG APPLY twice", raises(S.check_mode, {"mode": "APPLY", "confirm": "APPLY S3SKIN"}, True,
                                    contains="ALREADY"))
    check("NEG REVERT without record", raises(S.check_mode, {"mode": "REVERT", "confirm": "REVERT S3SKIN"}, False))
    check("NEG bad target", raises(S.check_mode, {"mode": "DRY", "target": "mesh"}, False, contains="TARGET"))
    check("NEG bad figure", raises(S.check_mode, {"mode": "DRY", "figures": ["Shore09"]}, False))
    check("subset ok", S.check_mode({"mode": "DRY", "figures": ["Shore03_M59"]}, False)[2] == ["Shore03_M59"])


def t_source():
    src = open(os.path.join(HERE, "s3_shore_skin.py"), encoding="utf-8").read()
    ast.parse(src)
    check("never deletes assets or nodes", not any(t in src for t in ("delete_asset", "delete_all_material",
                                                                       "delete_material_expression")))
    check("never edits a parent MI (setters only inside _make_child)",
          src.count("set_material_instance_scalar_parameter_value") == 1)
    check("no Save All", "save_dirty_packages" not in src and "save_directory" not in src)
    check("never touches the MHC asset or re-assembles", "BuildMetaHuman" not in src and "commit_skin" not in src
          and "build_meta_human" not in src)


def main():
    for t in (t_table, t_values, t_switch, t_slots, t_paths, t_census_mode, t_source):
        try:
            t()
        except Exception as exc:  # noqa: BLE001
            check(t.__name__ + " crashed", False, repr(exc))
    fails = [r for r in RESULTS if not r["pass"]]
    table = {f: S.plan_values(S.knobs_for(f), PARENT_S, PARENT_V) for f in S.FIGURES}
    with open(os.path.join(HERE, "test_s3_shore_skin_offline_report.json"), "w", encoding="utf-8") as h:
        json.dump({"checks": len(RESULTS), "fails": fails, "results": RESULTS,
                   "unit_parent_table": {f: {"scalars": v["scalars"], "vectors": v["vectors"]}
                                         for f, v in table.items()}}, h, indent=1)
    print("%s %d/%d" % ("S3SKIN_OFFLINE_OK" if not fails else "S3SKIN_OFFLINE_FAIL",
                        len(RESULTS) - len(fails), len(RESULTS)))
    for r in fails:
        print("FAIL", r["check"], r["detail"])
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
