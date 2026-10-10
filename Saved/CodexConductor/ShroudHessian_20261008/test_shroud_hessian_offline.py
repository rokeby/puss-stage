"""Offline harness for P22.  Positive + negative controls and seeded mutations."""
from __future__ import annotations

import copy
import importlib.util
import inspect
import json
from pathlib import Path
import random
import sys

import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
RESULTS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


U = load("shroud_hessian_ue", HERE / "shroud_hessian_ue.py")
G = load("generate_shroud_hessian", HERE / "generate_shroud_hessian.py")


def check(name, ok, detail=None):
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})


def rejects(name, fn, token):
    try:
        fn()
        check(name, False, "accepted")
    except Exception as exc:
        check(name, token in str(exc), str(exc))


def good_args(mode="DRY"):
    d = {"mode": mode, "run": "HARNESS-001", "seed": U.DEFAULT_SEED, "figures": list(U.FIGURES),
         "material": dict(U.SCALAR_DEFAULTS, **{k: list(v) for k, v in U.VECTOR_DEFAULTS.items()}), "confirm": ""}
    if mode in U.WRITE_MODES:
        d["confirm"] = U.CONFIRM[mode]
    if mode == "IMPORT_TEX":
        d["texture"] = "WeaveBC"
    return d


def records(texture=False, material=False, apply=False):
    return {"texture": texture, "material": material, "apply": apply}


def base_component(material="/Game/Old"):
    return {"class": "ChaosClothComponent", "asset": "/Game/Cloth/CA", "override_materials": [material],
            "relative_location": [21.0, 0.0, 0.0], "relative_rotation": [0.0, -90.0, 0.0],
            "relative_scale": [1.0, 1.0, 1.0], "absolute_rotation": False, "attach_socket": "head",
            "attach_parent": "Body", "parent_is_this_body": True, "teleport_distance_threshold": 300.0,
            "teleport_rotation_threshold": 0.0, "use_attached_parent_as_pose_component": False,
            "visible": True, "hidden_in_game": False, "suspend_simulation": False, "enable_simulation": True}


def base_figure(material="/Game/Old"):
    return {"template": base_component(material), "instance": base_component(material)}


def t_import_and_contract():
    check("import is offline-safe: no unreal module loaded", "unreal" not in sys.modules)
    cat = U.texture_catalog()
    check("catalog has exactly 14 textures", len(cat) == 14, sorted(cat))
    check("tile 2 is never in the import catalog", not any("-2-" in row[0] for row in cat.values()))
    check("weave texture roles", cat["WeaveBC"][2:] == ("TC_DEFAULT", True, "SAMPLERTYPE_COLOR") and
          cat["WeaveN"][2:] == ("TC_NORMALMAP", False, "SAMPLERTYPE_NORMAL"))
    check("all tint maps are sRGB colour", all(cat["Stain%02dTint" % n][2:] ==
          ("TC_DEFAULT", True, "SAMPLERTYPE_COLOR") for n in range(3, 9)))
    check("all mask maps are linear masks", all(cat["Stain%02dMask" % n][2:] ==
          ("TC_MASKS", False, "SAMPLERTYPE_MASKS") for n in range(3, 9)))
    check("six numbered MIs", sorted(U.MATERIAL_INSTANCES) == list(range(3, 9)))
    check("master and MIs stay in new create-only root",
          U.MASTER.startswith(U.ASSET_ROOT) and all(p.startswith(U.ASSET_ROOT) for p in U.MATERIAL_INSTANCES.values()))


def t_args():
    for mode in U.MODES:
        if mode == "MAT_CHECK":
            got = U.parse_args(good_args(mode), records(texture=True))
        elif mode == "REVERT":
            got = U.parse_args(good_args(mode), records(apply=True))
        else:
            got = U.parse_args(good_args(mode), records())
        check("args positive " + mode, got["mode"] == mode)
    bad = good_args("APPLY"); bad["confirm"] = ""
    rejects("negative: APPLY needs exact confirm", lambda: U.parse_args(bad, records()), "CONFIRM")
    bad = good_args("IMPORT_TEX"); bad["texture"] = "Stain02Tint"
    rejects("negative: rejected source 2 has no key", lambda: U.parse_args(bad, records()), "TEXTURE_KEY")
    bad = good_args("BUILD_MAT")
    rejects("negative: pending texture blocks material build", lambda: U.parse_args(bad, records(texture=True)), "PENDING")
    bad = good_args("MAT_CHECK")
    rejects("negative: MAT_CHECK needs exactly one pending stage", lambda: U.parse_args(bad, records()), "REQUIRES")
    rejects("negative: MAT_CHECK refuses ambiguous two-pending state",
            lambda: U.parse_args(bad, records(texture=True, material=True)), "REQUIRES")
    bad = good_args("APPLY")
    rejects("negative: existing apply record blocks APPLY", lambda: U.parse_args(bad, records(apply=True)), "ALREADY")
    bad = good_args("REVERT")
    rejects("negative: REVERT needs apply record", lambda: U.parse_args(bad, records()), "NO_APPLY")
    bad = good_args(); bad["run"] = "CONDUCTOR_SUPPLIES_RUN_ID"
    rejects("negative: placeholder run id", lambda: U.parse_args(bad, records()), "RUN_ID")
    bad = good_args(); bad["figures"] = [U.FIGURES[0], U.FIGURES[0]]
    rejects("negative: duplicate figures", lambda: U.parse_args(bad, records()), "FIGURES")
    bad = good_args(); bad["material"]["Surprise"] = 1
    rejects("negative: unknown look parameter", lambda: U.parse_args(bad, records()), "MATERIAL_KEY")
    bad = good_args(); bad["material"]["RoughnessWet"] = 0.90
    rejects("negative: roughness ordering", lambda: U.parse_args(bad, records()), "ROUGHNESS_ORDER")


def t_material_spec():
    spec = U.material_spec()
    check("all values are parameters", set(spec["scalar_parameters"]) == set(U.SCALAR_DEFAULTS) and
          set(spec["vector_parameters"]) == set(U.VECTOR_DEFAULTS))
    check("four texture parameters", set(spec["texture_parameters"]) ==
          {"WeaveBase", "WeaveNormal", "StainTint", "StainMask"})
    check("four required material properties", {p[2] for p in spec["properties"]} ==
          {"MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_SPECULAR"})
    check("base colour custom multiplies weave and tint", "W.rgb * C.rgb" in U.BASE_CODE and "T.rgb" in U.BASE_CODE)
    check("stain UV rotates and offsets without tiling", "6.283185" in U.UV_CODE and "+O.xy" in U.UV_CODE)
    check("roughness wet lowers and soot raises via two lerps", U.ROUGH_CODE.count("lerp") == 2)
    check("normal strength is parameterised", "max(S,0.0)" in U.NORMAL_CODE)
    check("normal flips only Z for back faces", "float3(1.0,1.0,TwoSided)" in U.NORMAL_CODE)
    check("builder declares a TwoSidedSign node", spec["nodes"].get("TwoSidedSign") == ("twosided", None))
    connected = {(e[0], e[2], e[3]) for e in spec["edges"]}
    for expected in (("WeaveUV", "WeaveBase", "UVs"), ("StainUV", "StainTint", "UVs"),
                     ("StainMask", "RoughOut", "M"), ("WeaveNormal", "NormalOut", "N"),
                     ("TwoSidedSign", "NormalOut", "TwoSided")):
        check("graph edge " + "/".join(expected), expected in connected)
    check("master defaults match brief roughness", U.SCALAR_DEFAULTS["RoughnessDry"] == 0.85 and
          U.SCALAR_DEFAULTS["RoughnessWet"] == 0.45 and U.SCALAR_DEFAULTS["RoughnessSoot"] > 0.85)


def t_seed_and_transitions():
    a = U.seeded_assignments(list(U.FIGURES), U.DEFAULT_SEED)
    b = U.seeded_assignments(list(U.FIGURES), U.DEFAULT_SEED)
    c = U.seeded_assignments(list(U.FIGURES), U.DEFAULT_SEED + 1)
    check("seeded assignment deterministic", a == b, a)
    check("seeded assignment is one MI per figure", len(set(a.values())) == 6, a)
    check("different seed changes assignment", a != c, (a, c))
    before = base_figure()
    expected = U.MATERIAL_INSTANCES[a[U.FIGURES[0]]]
    after = copy.deepcopy(before)
    after["template"]["override_materials"] = [expected]
    after["instance"]["override_materials"] = [expected]
    check("positive: material-only transition passes", U.transition_problems(before, after, expected) == [])
    check("positive: exact revert passes", U.revert_problems(before, copy.deepcopy(before)) == [])
    for scope in ("template", "instance"):
        wrong = copy.deepcopy(after); wrong[scope]["override_materials"] = ["/Game/Wrong"]
        check("negative: wrong material " + scope,
              any(x.startswith("MATERIAL|" + scope) for x in U.transition_problems(before, wrong, expected)))
    # Seeded mutation sweep: every protected property, in both scopes, must trip UNTOUCHED_CHANGED.
    rng = random.Random(81008)
    caught = 0
    for scope in ("template", "instance"):
        for key in U.STATE_KEYS:
            mutant = copy.deepcopy(after)
            value = mutant[scope][key]
            mutant[scope][key] = (not value) if isinstance(value, bool) else (value + rng.random() if isinstance(value, (int, float))
                                                                            else str(value) + "_MUT")
            problems = U.transition_problems(before, mutant, expected)
            hit = any("UNTOUCHED_CHANGED|%s|%s" % (scope, key) in x for x in problems)
            caught += int(hit)
            check("seeded mutation caught %s.%s" % (scope, key), hit, problems)
    check("seeded transition mutations all caught", caught == len(U.STATE_KEYS) * 2, caught)
    mutant = copy.deepcopy(before); mutant["instance"]["asset"] += "_MUT"
    check("negative: revert catches asset drift", bool(U.revert_problems(before, mutant)))


def t_generated_outputs():
    report = json.loads((HERE / "shroud_hessian_validation.json").read_text(encoding="utf-8"))
    check("generated validation report PASS", report["status"] == "PASS", report.get("failures"))
    check("six metric rows", sorted(report["metrics"]) == ["03", "04", "05", "06", "07", "08"])
    for number, row in report["metrics"].items():
        check("FFT >=10x stain " + number, row["fft_reduction_x"] >= 10.0, row["fft_reduction_x"])
        check("edge >=90% stain " + number, row["edge_sharpness_retained"] >= 0.90,
              row["edge_sharpness_retained"])
        check("neutral <=0.03 stain " + number, row["unstained_max_abs_from_one"] <= 0.03,
              row["unstained_max_abs_from_one"])
        tint = Image.open(HERE / row["tint"]); mask = Image.open(HERE / row["mask"])
        check("texture dimensions stain " + number, tint.size == (2912, 1440) and mask.size == tint.size)
        check("texture modes stain " + number, tint.mode == "RGB" and mask.mode == "RGBA")
        arr = np.asarray(mask)
        check("mask B=0 and A=1 stain " + number, int(arr[..., 2].max()) == 0 and int(arr[..., 3].min()) == 255)
        check("exactly four preview composites stain " + number,
              len(row["previews"]) == 4 and all((HERE / p).is_file() for p in row["previews"]))
    check("contact sheet exists", (HERE / "Shroud_Hessian_ContactSheet.png").is_file())
    # Seeded gate mutations: each required metric has an independent negative control.
    for field, value, token in (("fft_reduction_x", 9.99, "FFT_LT_10X"),
                                ("edge_sharpness_retained", 0.899, "EDGE_LT_90PCT"),
                                ("unstained_max_abs_from_one", 0.031, "NEUTRAL_GT_003")):
        mutant = copy.deepcopy(report["metrics"])
        mutant["05"][field] = value
        failures = G.validation_failures(mutant)
        check("seeded validation mutation caught " + field, any(x.startswith(token + "|05") for x in failures), failures)


def t_static_safety():
    src = (HERE / "shroud_hessian_ue.py").read_text(encoding="utf-8")
    check("no material node deletion call", "delete_material_expression" not in src and "delete_all_material" not in src)
    check("no Save All call", "save_all" not in src.lower() and "save_dirty_packages" not in src)
    check("no editor stop/quit/relaunch", all(x not in src for x in
          ("editor_request_end_play", "request_exit", "quit_editor", "open_editor_for_asset")))
    check("PIE guard says stop and report", "PIE_RUNNING_STOP_AND_REPORT" in src)
    check("success markers are after later readback functions", src.index("SHROUD_HESSIAN_IMPORT_TEX_OK") >
          src.index("def _mat_check") and src.index("SHROUD_HESSIAN_BUILD_MAT_OK") > src.index("def _mat_check"))
    apply_src = inspect.getsource(U._apply)
    check("APPLY record and backup precede first material write",
          apply_src.index("write_json(APPLY_RECORD") < apply_src.index("_backup(") < apply_src.index("_set_template_material"))
    revert_src = inspect.getsource(U._revert)
    check("REVERT backup precedes first material write", revert_src.index("_backup(") < revert_src.index("cloth.modify()"))
    check("APPLY saves only BPs plus named level", "_save_exact(content, maps)" in apply_src and "[WORLD]" in apply_src)
    build_src = inspect.getsource(U._build_master)
    check("regeneration keeps skeletal and clothing usage flags",
          'set_editor_property("used_with_skeletal_mesh", True)' in build_src and
          'set_editor_property("used_with_clothing", True)' in build_src)


def main():
    for test in (t_import_and_contract, t_args, t_material_spec, t_seed_and_transitions,
                 t_generated_outputs, t_static_safety):
        try:
            test()
        except Exception as exc:
            check(test.__name__ + " crashed", False, repr(exc))
    failures = [row for row in RESULTS if not row["pass"]]
    out = {"checks": len(RESULTS), "passes": len(RESULTS) - len(failures), "fails": len(failures),
           "failures": failures, "results": RESULTS}
    (HERE / "test_shroud_hessian_offline_report.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for row in failures:
        print("FAIL", row["check"], row["detail"])
    print("SHROUD_HESSIAN_OFFLINE_%s|checks=%d|passes=%d|fails=%d" %
          ("OK" if not failures else "FAILED", len(RESULTS), len(RESULTS) - len(failures), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
