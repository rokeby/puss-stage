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
    p = copy.deepcopy(F.PARAMS); p["wave_notch_halfwidth_cm"] = 0.0; p["wave_notch_blend_cm"] = 1.0
    fp2 = copy.deepcopy(fp)
    for row in fp2["wave_rows"]["rows"]:
        row["x"] = [row["x"][0] - 400.0, row["x"][1] + 400.0]   # flats wider than the notch
    case("NEG wave base buried", p, fp2, expect_fail="WAVE_BASE_NOT_FLUSH")
    p = copy.deepcopy(F.PARAMS); p["pad_blend_cm"] = 1.0
    fp3 = copy.deepcopy(fp); fp3["figures"]["pad_radius_cm"] = 0.0
    case("NEG figure pad removed", p, fp3, expect_fail="PAD_NOT_FLAT")
    p = copy.deepcopy(F.PARAMS); p["camera_min_vertical_clearance_cm"] = 500.0
    case("NEG camera clearance", p, expect_fail="CAMERA_LOW")

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
