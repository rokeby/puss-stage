"""Offline positive/negative harness for make_manifest_paperprosc.py."""
import ast
import copy
import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []
spec = importlib.util.spec_from_file_location("paperprosc_manifest_test", os.path.join(HERE, "make_manifest_paperprosc.py"))
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)


def check(kind, name, condition, detail=""):
    row = {"kind": kind, "name": name, "pass": bool(condition), "detail": str(detail)[:500]}
    RESULTS.append(row)
    print("%s %s %s%s" % ("PASS" if condition else "FAIL", kind, name,
                           "" if condition else " | " + row["detail"]))


def main():
    source_root = os.environ.get("PAPERPROSC_SOURCE_ROOT", r"E:\PussStage")
    output_root = T.default_project_root()
    payloads, plan = T.build_payloads(source_root, output_root)
    manifest = json.loads(payloads[T.MANIFEST_REL].decode("utf-8"))
    check("POS", "real rebuilt source produces exactly three manifest entries", len(manifest["meshes"]) == 3)
    check("POS", "all real source gates pass", plan["gates_ok"] and not plan["failures"], plan["failures"])
    check("POS", "all entries are proof-pass thick5", all(x["proof_pass"] and x["hf"]["frame_mode"] == "thick5" for x in manifest["meshes"]))
    check("POS", "generator is byte-deterministic", payloads == T.build_payloads(source_root, output_root)[0])
    check("POS", "three socket, MI and build-report adapters are emitted",
          sum("/RZ_BUILD_REPORT.json" in p for p in payloads) == 3 and
          sum("_mi_params.json" in p for p in payloads) == 3 and
          sum("/sockets_" in p for p in payloads) == 3)
    first_report = json.loads(payloads["%s/import_meta/PRO_side_L/RZ_BUILD_REPORT.json" % T.HERE_REL].decode("utf-8"))
    check("POS", "edge gate records x -15..-10 and zero inward area", first_report["edge_gate"]["pass"] and
          all(v["edge_x_cm"] == [-15.0, -10.0] and v["edge_inward_area_fraction"] == 0.0
              for v in first_report["edge_gate"]["measured"].values()))

    row = T.find_probe_row(T.read_json(T.absolute(output_root, T.PROBE_REL)), T.piece_paths(T.PIECES[0])["fbx"])
    bad = copy.deepcopy(row)
    next(iter(bad["objects"].values()))["slots"]["Edge"]["x_max"] = -13.2
    check("NEG", "legacy 1.8 cm edge profile is refused", any("NOT_-15_-10" in x for x in T.edge_gate_errors(bad)))
    bad = copy.deepcopy(row)
    next(iter(bad["objects"].values()))["edge_inward_area_fraction"] = 1.0
    check("NEG", "inward edge walls are refused", any("EDGE_INWARD" in x for x in T.edge_gate_errors(bad)))
    bad = copy.deepcopy(row)
    next(iter(bad["objects"].values()))["slots"]["Edge"]["x_facing"] = 1
    check("NEG", "x-facing polygons in Edge slot are refused", any("X_FACING" in x for x in T.edge_gate_errors(bad)))
    try:
        T.require(False, "SENTINEL")
        stopped = False
    except T.ManifestError as exc:
        stopped = str(exc) == "SENTINEL"
    check("NEG", "failed requirements stop deterministically", stopped)

    source = open(os.path.join(HERE, "make_manifest_paperprosc.py"), encoding="utf-8").read()
    check("STATIC", "generator parses as Python 3.11", ast.parse(source, feature_version=(3, 11)) is not None)
    check("STATIC", "generator exposes DRY APPLY REVERT and exact confirms",
          all(token in source for token in ('"DRY"', '"APPLY"', '"REVERT"', '"%s PAPERPROSC MANIFEST"')))
    check("STATIC", "generator has no Unreal or Blender imports", "import unreal" not in source and "import bpy" not in source)
    check("STATIC", "revert preserves displaced outputs instead of deleting them", "displaced_outputs" in source and "unlink(" not in source)

    report = {"checks": RESULTS, "passed": sum(x["pass"] for x in RESULTS), "failed": sum(not x["pass"] for x in RESULTS),
              "by_kind": {kind: sum(x["kind"] == kind for x in RESULTS) for kind in ("POS", "NEG", "STATIC")},
              "plan_hash": plan["hash"]}
    with open(os.path.join(HERE, "test_make_manifest_paperprosc_report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    print("PAPERPROSC_MANIFEST_HARNESS_RESULT|passed=%d|failed=%d|positive=%d|negative=%d|static=%d|plan=%s" %
          (report["passed"], report["failed"], report["by_kind"]["POS"], report["by_kind"]["NEG"],
           report["by_kind"]["STATIC"], plan["hash8"]))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
