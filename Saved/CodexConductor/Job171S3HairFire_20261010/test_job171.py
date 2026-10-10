import importlib.util
import json
import os
import random
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("job171_core_tested", os.path.join(HERE, "job171_core.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
tool_spec = importlib.util.spec_from_file_location("job171_tool_tested", os.path.join(HERE, "job171_s3_hair_fire.py"))
T = importlib.util.module_from_spec(tool_spec)
tool_spec.loader.exec_module(T)
checks = []


def check(name, value, control="positive"):
    checks.append({"name": name, "ok": bool(value), "control": control})
    if not value:
        raise AssertionError(name)


def rejects(name, fn, token):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        check(name, token in str(exc), "negative")
        return
    check(name, False, "negative")


def labels():
    out = ["%s Clam" % f for f in C.FIGURES]
    out += ["P40 Shore Variant 01 (Shore04_F55)", "P40 Shore Variant 02 (Shore02_F52)"]
    sources = ["Shore04_F55", "Shore06_F25", "Shore04_F55", "Shore06_F25", "Shore06_F25",
               "Shore06_F25", "Shore04_F55", "Shore06_F25", "Shore03_M59", "Shore06_F25",
               "Shore06_F25", "Shore04_F55", "Shore06_F25", "Shore06_F25", "Shore04_F55"]
    out += ["S3 Crowd %02d (from %s)" % (i + 1, f) for i, f in enumerate(sources)]
    out += ["S3 Hangar Float Hold: Shore05_M53 Clam"]
    return out


def main():
    rows = C.validate_target_labels(labels())
    check("P01.target_count", len(rows) == 24)
    check("P02.shore_count", sum(x["kind"] == "shore" for x in rows) == 6)
    check("P03.p40_count", sum(x["kind"] == "p40" for x in rows) == 2)
    check("P04.crowd_count", sum(x["kind"] == "crowd" for x in rows) == 15)
    check("P05.hangar_count", sum(x["kind"] == "hangar" for x in rows) == 1)
    check("P06.figure_parse", C.figure_from_label("S3 Crowd 09 (from Shore03_M59)") == "Shore03_M59")
    check("P07.parts_default", C.selected_parts(None) == ["hair", "fires"])
    check("P08.parts_subset", C.selected_parts(["fires"]) == ["fires"])
    check("P09.binding_unique", len({C.binding_path(x, s) for x in C.FIGURES for s in ("straight", "straight_bangs")}) == 12)
    variations = C.variation_plan(rows)
    check("P10.palette_coverage", {x["palette"] for x in variations} == {"dark_brown", "grey"})
    check("P11.variation_coverage", {x["style"] for x in variations} == {"straight", "straight_bangs"})
    check("P12.palette_stable", C.palette_for_label(labels()[0]) == C.palette_for_label(labels()[0]))
    fp = C.plan_fingerprint({"b": 2, "a": 1})
    check("P13.fingerprint_order", fp == C.plan_fingerprint({"a": 1, "b": 2}))
    check("P14.numeric_tolerance", not C.numeric_diff({"x": 1.0}, {"x": 1.00005}))
    check("P15.fire_count", len(C.FIRE_LABELS) == 4 and len(C.LIGHT_LABELS) == 4)
    params = T._params({})
    check("P16.look_defaults", params["fire_linear"] == [0.35, 0.42, 0.50, 1.0] and params["fire_temperature"] == 9000.0)
    rejects("N01.bad_parts", lambda: C.selected_parts(["smoke"]), "PARTS")
    rejects("N02.duplicate_parts", lambda: C.selected_parts(["hair", "hair"]), "PARTS")
    rejects("N03.missing_target", lambda: C.validate_target_labels(labels()[:-1]), "TARGET_CENSUS")
    rejects("N04.bad_figure", lambda: C.figure_from_label("S3 Crowd 01"), "FIGURE_LABEL")
    rejects("N05.bad_binding", lambda: C.binding_path("Shore99"), "FIGURE")
    rejects("N06.bad_style", lambda: C.binding_path("Shore01_M56", "mohawk"), "STYLE")
    rejects("N07.bad_hair_look", lambda: T._params({"grey": {"WhiteAmount": 1.5}}), "HAIR_LOOK_ARGS")
    rejects("N08.bad_fire_temp", lambda: T._params({"fire_temperature": 500.0}), "FIRE_LOOK_ARGS")
    check("N09.numeric_drift", bool(C.numeric_diff({"x": 1.0}, {"x": 1.01})), "negative")
    mutated = labels(); mutated[0] = "Other Actor"
    rejects("N10.mutated_label", lambda: C.validate_target_labels(mutated), "TARGET_CENSUS")
    rng = random.Random(171)
    state = {"rows": [[i, float(i)] for i in range(8)]}
    changed = json.loads(json.dumps(state)); changed["rows"][rng.randrange(8)][1] += 0.01
    check("N11.seeded_mutation", bool(C.numeric_diff(state, changed)), "negative")
    report = {"tool": C.TOOL, "tool_version": C.TOOL_VERSION,
              "passed": sum(x["ok"] for x in checks), "failed": sum(not x["ok"] for x in checks),
              "positive": sum(x["ok"] and x["control"] == "positive" for x in checks),
              "negative": sum(x["ok"] and x["control"] == "negative" for x in checks), "checks": checks}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True); handle.write("\n")
    print("JOB171_HARNESS_OK|passed=%d|failed=0|positive=%d|negative=%d" %
          (report["passed"], report["positive"], report["negative"]))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise
