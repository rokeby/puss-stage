"""Rebuild the 12 S3 WaveV3 pieces at thick5 (5 cm board) with outward Edge walls -> *_t5o.  OFFLINE ONLY.

Gary 8 Oct (own answers): rebuild at 5 cm with outward V3 edges (black-sliver edge + 'waves thicker ~5 cm').
NEVER reruns build_skin (memory flatv3-skin-rebuild-rerolls-peel): it reuses the EXISTING, live skins and
flaps_v3.json in DerivedAssets/FlatV3/Scene3/waves_v3/B_build/pieces/<suffix>/ and only re-runs the geometry
builder, exactly as s3_waves_v3_B_build.py:251-259 did, plus --geometry-profile thick5 --board-thickness-cm 5.0
--edge-walls-outward (the args of the proven Saved/CodexFlatV3/s3waves/fixed_L1P1 rebuild).

Per piece, every gate must pass (else exit non-zero, nothing later runs):
  G0 inputs are the LIVE inputs: every B_build deliverable sha256 == hashes_run2.json, and the live FBX sha256 ==
     the UE import record's fbx_sha256 (Saved/CodexConductor/S3Waves/s3_waves_v3_import_<suffix>.json);
  G1 build (pinned FBX time, PYTHONHASHSEED=0) writes a NEW fbx;
  G2 clean re-import validator (--validate-fbx, thick5) pass;
  G3 edge probe (measure_edge_family_blender.py): Front x = -15, Edge x -15..-10, inward area fraction 0.0 (LOD0/1);
  G4 Front/Flap UV0 registration identical to the LIVE fbx (compare_front_flap_uv0_blender.py), LOD0 and LOD1.
ONE headless Blender at a time (refuses to start while another --background blender.exe runs).

Run:  D:/PussStageTools/FlatV3/venv/Scripts/python.exe Saved/CodexFlatV3/s3waves/build_t5o.py [--pieces L1Breakers_P1 ...]
Out:  DerivedAssets/FlatV3/Scene3/WavesV3_t5o/<suffix>_t5o/ + DerivedAssets/FlatV3/Scene3/WavesV3_t5o/build_report_t5o.json
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
S3W = PROJECT / "Saved" / "CodexConductor" / "S3Waves"
B_BUILD = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "waves_v3" / "B_build"
OUT = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "WavesV3_t5o"
BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
PINNED = S3W / "s3_waves_v3_blender_pinned.py"
BUILD_FLAT = PROJECT / "Tools" / "FlatV3" / "build_v3_flat.py"
EDGE_PROBE = PROJECT / "Saved" / "CodexFlatV3" / "edge" / "measure_edge_family_blender.py"
UVCMP = HERE / "compare_front_flap_uv0_blender.py"
TEX = PROJECT / "DerivedAssets" / "TextureLibrary"
PROFILE_ARGS = ["--geometry-profile", "thick5", "--board-thickness-cm", "5.0"]
SUFFIX = "_t5o"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def other_headless_blender():
    try:
        out = subprocess.run(["wmic", "process", "where", "name='blender.exe'", "get", "ProcessId,CommandLine"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return []
    return [l.strip() for l in out.splitlines() if "--background" in l or " -b " in l]


def wait_slot(limit_s=1800):
    t0 = time.time()
    while other_headless_blender():
        if time.time() - t0 > limit_s:
            sys.exit("BLENDER_SLOT_BUSY")
        print("WAITING_FOR_HEADLESS_BLENDER", flush=True)
        time.sleep(15)


def blender_env():
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def run(cmd, log, env=None):
    wait_slot()
    r = subprocess.run([str(c) for c in cmd], cwd=PROJECT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    log.write("\n$ " + " ".join(str(c) for c in cmd) + "\n" + r.stdout[-8000:] + r.stderr[-4000:])
    log.flush()
    if r.returncode:
        raise RuntimeError("RC_%d|%s|%s" % (r.returncode, cmd[:4], (r.stdout + r.stderr)[-1500:]))
    return r.stdout


def load_plan():
    spec = importlib.util.spec_from_file_location("s3wv3_build_t5o", S3W / "s3_waves_v3_build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plan = mod.plan_variant("B")
    return [dict(p, suffix=p["asset"][len("SM_FlatV3_"):]) for p in plan["pieces"]]


def g0_live_inputs(suffix, hashes):
    folder = B_BUILD / "pieces" / suffix
    want = hashes[suffix]
    got = {n: sha(folder / n) for n in want}
    bad = sorted(n for n in want if got[n] != want[n])
    imp = json.loads((S3W / ("s3_waves_v3_import_%s.json" % suffix)).read_text(encoding="utf-8"))
    live_fbx = folder / ("SM_FlatV3_%s.fbx" % suffix)
    fbx_ok = sha(live_fbx) == imp["fbx_sha256"]
    return {"pass": not bad and fbx_ok, "mismatched": bad, "live_fbx_sha_matches_import_record": fbx_ok,
            "files_checked": len(want), "import_run": imp.get("run")}


def edge_gate(probe_rows):
    row = probe_rows[0]
    out = {"pass": True, "lods": {}}
    for name, o in row["objects"].items():
        lod = name.rsplit("_", 1)[-1]
        s = o["slots"]
        front = s.get("Front", {})
        edge = s.get("Edge", {})
        ok = (abs(front.get("x_min", 99) + 15.0) < 0.01 and abs(front.get("x_max", 99) + 15.0) < 0.01 and
              abs(edge.get("x_min", 99) + 15.0) < 0.01 and abs(edge.get("x_max", 99) + 10.0) < 0.01 and
              o["edge_inward_area_fraction"] <= 1e-6 and edge.get("x_facing", 1) == 0)
        out["lods"][lod] = {"front_x": [front.get("x_min"), front.get("x_max")],
                            "edge_x": [edge.get("x_min"), edge.get("x_max")],
                            "edge_inward_area_fraction": o["edge_inward_area_fraction"],
                            "timber_x": [s.get("Timber", {}).get("x_min"), s.get("Timber", {}).get("x_max")],
                            "flap_x": [s.get("Flap", {}).get("x_min"), s.get("Flap", {}).get("x_max")],
                            "pass": ok}
        out["pass"] = out["pass"] and ok
    return out


def build_one(p, hashes, log):
    a = p["suffix"]
    src = B_BUILD / "pieces" / a
    name = a + SUFFIX
    dst = OUT / name
    dst.mkdir(parents=True, exist_ok=True)
    rep = {"suffix": a, "name": name, "out_dir": str(dst)}
    rep["G0_live_inputs"] = g0_live_inputs(a, hashes)
    if not rep["G0_live_inputs"]["pass"]:
        raise RuntimeError("G0_INPUTS_NOT_LIVE|%s|%s" % (a, rep["G0_live_inputs"]))
    br = json.loads((B_BUILD / "build_report_B.json").read_text(encoding="utf-8"))["pieces"][a]
    height = br["crop"]["height_cm"]
    fbx = dst / ("SM_FlatV3_%s.fbx" % name)
    before = fbx.stat().st_mtime_ns if fbx.exists() else None
    t0 = time.time()
    run([BLENDER, "--background", "--factory-startup", "--python-use-system-env", "--python", PINNED, "--",
         "--mask", src / "mask.png", "--art", src / ("T_%s_SkinColor.png" % a),
         "--skin-mask", src / ("T_%s_SkinMask.png" % a), "--skin-normal", src / ("T_%s_SkinNormal.png" % a),
         "--flaps", src / ("%s_flaps_v3.json" % a), "--aged-texture-dir", src / "Aged",
         "--height-cm", "%.3f" % height, "--side", "L", "--name", name, "--asset-name", name,
         "--mount", "wave-row", "--deterministic-triangulation", "--triangulate-export",
         *PROFILE_ARGS, "--edge-walls-outward",
         "--output-dir", dst, "--texture-root", TEX], log, env=blender_env())
    if not fbx.is_file() or (before is not None and fbx.stat().st_mtime_ns <= before):
        raise RuntimeError("G1_STALE_OR_MISSING_FBX|%s" % fbx)
    rep["G1_build_s"] = round(time.time() - t0, 1)
    bj = json.loads((dst / ("%s_L_build.json" % name)).read_text(encoding="utf-8"))
    rep["geometry_profile"] = bj["geometry_profile"]
    rep["triangle_counts_build"] = bj["triangle_counts"]
    val = dst / ("SM_FlatV3_%s_validation.json" % name)
    run([BLENDER, "--background", "--factory-startup", "--python", BUILD_FLAT, "--",
         "--validate-fbx", fbx, "--kind", "wave", "--skin-color", src / ("T_%s_SkinColor.png" % a),
         "--expected-height-cm", "%.3f" % height, "--minimum-width-m", "11.0", *PROFILE_ARGS,
         "--validation-out", val], log)
    v = json.loads(val.read_text(encoding="utf-8"))
    checks = v.get("checks", {})
    rep["G2_validation"] = {"pass": bool(v.get("pass")), "checks_passed": sum(1 for c in checks.values()
                                                                             if isinstance(c, dict) and c.get("pass")),
                            "checks_total": len(checks), "bounds_m": v.get("bounds_m"),
                            "triangle_counts": v.get("triangle_counts"),
                            "board_thickness": checks.get("board_thickness_profile")}
    if not v.get("pass"):
        raise RuntimeError("G2_VALIDATION_FAIL|%s|%s" % (a, [k for k, c in checks.items()
                                                             if isinstance(c, dict) and not c.get("pass")]))
    lst = dst / "probe_list.txt"
    lst.write_text(str(fbx).replace("\\", "/") + "\n", encoding="utf-8")
    probe = dst / "edge_probe.json"
    run([BLENDER, "-b", "--factory-startup", "--python", EDGE_PROBE, "--", probe, lst], log)
    rep["G3_edge"] = edge_gate(json.loads(probe.read_text(encoding="utf-8")))
    if not rep["G3_edge"]["pass"]:
        raise RuntimeError("G3_EDGE_FAIL|%s|%s" % (a, rep["G3_edge"]))
    cmp_out = dst / "uv0_registration_vs_live.json"
    run([BLENDER, "-b", "--factory-startup", "--python", UVCMP, "--", src / ("SM_FlatV3_%s.fbx" % a), fbx, cmp_out],
        log)
    c = json.loads(cmp_out.read_text(encoding="utf-8"))
    rep["G4_uv0_registration"] = {"pass": c["pass"], "lods": {
        k: {"Front_identical": r.get("Front", {}).get("identical"), "Front_loops": r.get("Front", {}).get("loops_new"),
            "Flap_identical": r.get("Flap", {}).get("identical"), "Flap_loops": r.get("Flap", {}).get("loops_new"),
            "triangles_live": r.get("live_triangles"), "triangles_new": r.get("new_triangles"),
            "by_slot_live": r.get("live_by_slot"), "by_slot_new": r.get("new_by_slot")}
        for k, r in c["lods"].items()}}
    if not c["pass"]:
        raise RuntimeError("G4_UV0_REGISTRATION_FAIL|%s" % a)
    rep["fbx_sha256"] = sha(fbx)
    rep["live_fbx_sha256"] = sha(src / ("SM_FlatV3_%s.fbx" % a))
    rep["pass"] = True
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces", nargs="*")
    a = ap.parse_args()
    plan = load_plan()
    sel = [p for p in plan if not a.pieces or p["suffix"][len("S3_WaveV3_"):] in a.pieces]
    hashes = json.loads((B_BUILD / "hashes_run2.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "build_report_t5o.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"pieces": {}}
    report["builder_args"] = PROFILE_ARGS + ["--edge-walls-outward", "--mount", "wave-row", "--side", "L",
                                             "--deterministic-triangulation", "--triangulate-export"]
    report["builder_sha256"] = sha(BUILD_FLAT)
    with open(OUT / "build_log_t5o.txt", "a", encoding="utf-8") as log:
        for p in sel:
            print("BUILD", p["suffix"], flush=True)
            try:
                r = build_one(p, hashes, log)
            except Exception as exc:  # noqa: BLE001
                report["pieces"][p["suffix"]] = {"pass": False, "error": str(exc)[:1500]}
                report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
                print("S3T5O_BUILD_FAIL|%s|%s" % (p["suffix"], str(exc)[:400]), flush=True)
                sys.exit(2)
            r["mount_local_live"] = p["mount_local"]
            r["layer"], r["piece"] = p["layer"], p["piece"]
            report["pieces"][p["suffix"]] = r
            report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
            print("S3T5O_PIECE_OK|%s|tris=%s|val=%d/%d" % (p["suffix"], r["G2_validation"]["triangle_counts"],
                                                            r["G2_validation"]["checks_passed"],
                                                            r["G2_validation"]["checks_total"]), flush=True)
    ok = [k for k, v in report["pieces"].items() if v.get("pass")]
    report["all_pass"] = len(ok) == 12
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("S3T5O_BUILD_DONE|ok=%d/12|report=%s" % (len(ok), report_path), flush=True)


if __name__ == "__main__":
    main()
