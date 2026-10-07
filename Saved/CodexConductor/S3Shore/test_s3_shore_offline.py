"""Offline harness for the S3 shore ground (no Unreal, no Blender needed).

python Saved/CodexConductor/S3Shore/test_s3_shore_offline.py
Each check is run on the shipped PARAMS (must pass) and on a broken copy (must FAIL),
so a verifier that cannot fail is caught.  Writes test_s3_shore_offline_report.json.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s3_shore_field as F  # noqa: E402

PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MANIFEST = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "SM_S3_ShoreGround_manifest.json")


def run():
    fp = F.load_footprint()
    results = []

    def case(name, params=None, footprint=None, expect_fail=None):
        p = params or F.PARAMS
        f = footprint or fp
        fails, _ = F.checks(f, p)
        if expect_fail is None:
            ok = not fails
        else:
            ok = any(x.startswith(expect_fail) for x in fails)
        results.append({"case": name, "ok": ok, "failures": fails[:6]})

    case("shipped params pass")
    p = copy.deepcopy(F.PARAMS); p["drift_cap_cm"] = 175.0; p["drift_side_cm"] = [150.0, 175.0]
    case("NEG drift over prints", p, expect_fail="DRIFT_HITS_PRINTS")
    p = copy.deepcopy(F.PARAMS); p["door_gap_y"] = [0.0, 1.0]
    case("NEG door blocked", p, expect_fail="DOOR_GAP_BLOCKED")
    p = copy.deepcopy(F.PARAMS); p["wave_notch"] = False
    case("NEG wave notch off -> drifts/relief under the flats detected", p, expect_fail="WAVE_BASE_NOT_FLUSH")
    # Gary 7 Oct: cast area re-sculpted, no v2 preservation, no pads.
    def cast_absent(params):
        _, rep = F.checks(fp, params)
        return rep["cast_area_vs_v2"]["fraction_within_0p5cm_of_v2"] <= 0.05, rep["cast_area_vs_v2"]
    ok, info = cast_absent(F.PARAMS)
    results.append({"case": "+ v2 cast preservation ABSENT in shipped field", "ok": ok and not F.PARAMS["preserve_v2_cast"]
                    and not F.PARAMS["use_pads"], "info": info})
    p = copy.deepcopy(F.PARAMS); p["preserve_v2_cast"] = True; p["use_pads"] = True
    ok, info = cast_absent(p)
    results.append({"case": "- control: old preservation switched on IS detected", "ok": not ok, "info": info})

    # seat report: real report + synthetic controls
    import numpy as np
    import s3_shore_seat_report as SR
    grid = F.build_grid(fp)
    surf = SR.Surface(grid)
    box = {"min": [3000.0, -100.0, 0.0], "max": [3060.0, -40.0, 50.0]}
    X, Y = np.meshgrid(np.linspace(3000, 3060, 13), np.linspace(-100, -40, 13), indexing="ij")
    Z = surf(X, Y)
    synth = [{"label": "SYN float", "kind": "synthetic", "base_local_z": float(Z.max()) + 10.0, "aabb": box},
             {"label": "SYN buried", "kind": "synthetic", "base_local_z": float(Z.min()) - 10.0, "aabb": box},
             {"label": "SYN ok", "kind": "synthetic", "base_local_z": float(Z.mean()) + 0.5, "aabb": box}]
    got = {r["label"]: r["verdict"] for r in SR.seat_rows(synth, surf)}
    results.append({"case": "- control: synthetic floating object flagged FLOATING", "ok": got["SYN float"] == "FLOATING"})
    results.append({"case": "- control: synthetic buried object flagged BURIED", "ok": got["SYN buried"] == "BURIED"})
    results.append({"case": "+ control: synthetic seated object OK", "ok": got["SYN ok"] == "OK"})
    rep = SR.build(grid=grid)
    rows = {r["label"]: r for r in rep["rows"]}
    results.append({"case": "seat report from LIVE reads (run, 15 objects, Shore03 foot 130.454 local = 10.45 dock)",
                    "ok": rep["live_reads_run"] == "S3SHORE-20261007-181646" and len(rows) == 15
                    and abs(rows["Shore03_M59 Clam"]["base_local_z"] - 130.454) < 0.01, "counts": rep["counts"]})
    p = copy.deepcopy(F.PARAMS); p["camera_min_vertical_clearance_cm"] = 500.0
    case("NEG camera clearance", p, expect_fail="CAMERA_LOW")

    # editor script (offline-checkable parts)
    import ast
    import s3_shore_ground_ue as U
    results.append({"case": "+ material graph spec has no problems", "ok": not U.graph_problems(), "info": U.graph_problems()})
    saved_edges = list(U.EDGES)
    try:
        U.EDGES[:] = [e for e in U.EDGES if not (e[2] == "SH_Base" and e[3] == "WetD")]
        results.append({"case": "- control: dropping an edge is detected", "ok": bool(U.graph_problems()),
                        "info": U.graph_problems()})
    finally:
        U.EDGES[:] = saved_edges
    src = open(os.path.join(HERE, "s3_shore_ground_run.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    consts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("ENABLED", "REFUSED"):
            consts[node.targets[0].id] = ast.literal_eval(node.value)
    en, rf = consts.get("ENABLED", {}), consts.get("REFUSED", ())
    ok = (set(en) == {"DRY", "IMPORT", "BUILD_MAT", "BENCH", "BENCH_RESTORE"} and en["DRY"] is None
          and all(en[m] == m + " S3SHORE" for m in en if m != "DRY")
          and set(rf) >= {"APPLY", "REVERT"} and not (set(rf) & set(en)))
    results.append({"case": "runner: IMPORT/BUILD_MAT/BENCH(+RESTORE) need '<MODE> S3SHORE'; APPLY/REVERT refused",
                    "ok": ok, "info": {"enabled": en, "refused": rf}})
    results.append({"case": "runner: no save call in BENCH path",
                    "ok": all(k not in open(os.path.join(HERE, "s3_shore_ground_ue.py"), encoding="utf-8").read()
                              .split("def run_bench(")[1].split("def run_bench_restore(")[0]
                              for k in ("save_asset", "save_map", "save_current_level", "save_packages"))})

    # manifest (built artefact) gates
    if os.path.isfile(MANIFEST):
        m = json.load(open(MANIFEST, encoding="utf-8"))
        b = m["expected_ue_local_bounds_cm"]
        results.append({"case": "manifest bounds asymmetric in Y (mirror detectable)",
                        "ok": abs(b["min"][1] + 1012.0) < 0.5 and abs(b["max"][1] - 1008.0) < 0.5, "bounds": b})
        results.append({"case": "manifest footprint hash matches current footprint",
                        "ok": m["footprint_sha256"] == __import__("hashlib").sha256(
                            open(F.FOOTPRINT, "rb").read()).hexdigest()})
        results.append({"case": "fbx exists and hash matches manifest",
                        "ok": os.path.isfile(m["fbx"]) and __import__("hashlib").sha256(
                            open(m["fbx"], "rb").read()).hexdigest() == m["fbx_sha256"]})
        results.append({"case": "manifest built with no field failures", "ok": not m["checks_failures"]})
    else:
        results.append({"case": "manifest present", "ok": False})
    report = {"passed": sum(r["ok"] for r in results), "total": len(results), "results": results}
    with open(os.path.join(HERE, "test_s3_shore_offline_report.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    print("S3SHORE_OFFLINE %d/%d" % (report["passed"], report["total"]))
    for r in results:
        print(("PASS " if r["ok"] else "FAIL ") + r["case"])
    return report["passed"] == report["total"]


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
