"""S3 waves v3 -> Flat V3 pieces: PLAN (default) or CROP+BUILD (--run). Offline only; never touches Unreal.

Each layer strip (22 m, from s3_waves_v3_design.py) is cut into two 12.5 m pieces that overlap ~3 m:
  P1 = u [-1100, cut+150]   mounted at layer x        (front)
  P2 = u [cut-150, +1100]   mounted at layer x + 15   (behind; identical art in the overlap)
`cut` is the lowest point of the top profile within u in [-120, +120] (a trough), so P1's end edge stands in a trough.
Both pieces of a layer are keyed with the SAME offsets, so the union never opens.

  --variant A|B  --plan (default)  writes Saved/CodexConductor/S3Waves/build_plan_<v>.json with commands
  --run          crops piece mask/art under waves_v3/<v>/pieces/<asset>/ and runs build_skin -> build_v3_flat ->
                 --validate-fbx per piece (headless Blender; check no other agent's Blender runs first).
Names are NEW (no in-place reimport): SM_FlatV3_S3_WaveV3_<Layer>_<P1|P2>.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parents[3]
ROOT = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "waves_v3"
HERE = Path(__file__).resolve().parent
PY = r"D:\PussStageTools\FlatV3\venv\Scripts\python.exe"
BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
TEX = PROJECT / "DerivedAssets" / "TextureLibrary"
PAPER = TEX / "Paper" / "Paper003"
OLDER = Path(r"D:\PussStageSources\FlatV3\P04\met_377854\original.jpg")
PIECE_CM = 1250.0
OVERLAP_HALF = 150.0
DEPTH_STEP = 15.0
SKIRT = 20.0


def plan_variant(v):
    d = json.loads((ROOT / v / ("design_%s.json" % v)).read_text(encoding="utf-8"))
    res = d["res_px_per_cm"]
    out = {"variant": v, "res_px_per_cm": res, "pieces": [], "rules": {
        "mount_z_local": 115.0 - SKIRT, "why_z": "mask bottom = skirt bottom (20 cm below floor top); origin is bottom-centre",
        "rotation": [0, 0, 0], "scale": [1, 1, 1], "front_faces": "-X (toward the cameras)"}}
    for L in d["layers"]:
        mask = cv2.imread(str(PROJECT / L["files"]["mask"]), cv2.IMREAD_GRAYSCALE)
        top_px = np.argmax(mask > 127, axis=0)
        u = (np.arange(mask.shape[1]) + 0.5) / res - 1100.0
        win = (u >= -120) & (u <= 120)
        cut = float(u[win][np.argmax(top_px[win])])          # largest row index = lowest top = trough
        for name, (u0, u1), dx in (("P1", (-1100.0, cut + OVERLAP_HALF), 0.0), ("P2", (cut - OVERLAP_HALF, 1100.0), DEPTH_STEP)):
            c0, c1 = int(round((u0 + 1100) * res)), int(round((u1 + 1100) * res))
            sub = mask[:, c0:c1]
            rows = np.nonzero(sub.max(1) > 127)[0]
            h_cm = (mask.shape[0] - rows.min()) / res
            layer = L["id"].replace("_", "")
            asset = "S3_WaveV3_%s_%s" % (layer, name)
            out["pieces"].append({
                "layer": L["id"], "piece": name, "asset": "SM_FlatV3_" + asset, "u_range_cm": [round(u0, 1), round(u1, 1)],
                "cut_u_cm": round(cut, 1), "width_cm": round(u1 - u0, 1), "height_cm_incl_skirt": round(h_cm, 1),
                "px_cols": [c0, c1], "mount_local": [L["x"] + dx, round((u0 + u1) / 2, 1), 115.0 - SKIRT],
                "color_px": [4096, 1024], "seed": int(L["seed"]) * 10 + (1 if name == "P1" else 2),
            })
    return out


def commands(p, v):
    folder = ROOT / v / "pieces" / p["asset"][len("SM_FlatV3_"):]
    a = p["asset"][len("SM_FlatV3_"):]
    return folder, [
        [PY, str(PROJECT / "Tools/FlatV3/build_skin.py"), "--mask", str(folder / "mask.png"), "--art", str(folder / "art.png"),
         "--older-poster", str(OLDER), "--paper-displacement", str(PAPER / "Paper003_4K-JPG_Displacement.jpg"),
         "--paper-roughness", str(PAPER / "Paper003_4K-JPG_Roughness.jpg"), "--texture-root", str(TEX),
         "--aged-output", str(folder / "Aged"), "--stencil-text", "PUSS S3 " + a[-14:], "--height-cm", str(p["height_cm_incl_skirt"]),
         "--width-cm", str(p["width_cm"]), "--color-width", "4096", "--color-height", "1024", "--asset-name", a,
         "--output", str(folder), "--seed", str(p["seed"]), "--peel-percent", "1.0", "--peel-profile", "bottom-heavy"],
        [BLENDER, "--background", "--factory-startup", "--python", str(PROJECT / "Tools/FlatV3/build_v3_flat.py"), "--",
         "--mask", str(folder / "mask.png"), "--art", str(folder / ("T_%s_SkinColor.png" % a)),
         "--skin-mask", str(folder / ("T_%s_SkinMask.png" % a)), "--skin-normal", str(folder / ("T_%s_SkinNormal.png" % a)),
         "--flaps", str(folder / ("%s_flaps.json" % a)), "--aged-texture-dir", str(folder / "Aged"),
         "--height-cm", str(p["height_cm_incl_skirt"]), "--side", "L", "--name", a, "--asset-name", a, "--mount", "wave-row",
         "--deterministic-triangulation", "--triangulate-export", "--output-dir", str(folder), "--texture-root", str(TEX)],
        [BLENDER, "--background", "--factory-startup", "--python", str(PROJECT / "Tools/FlatV3/build_v3_flat.py"), "--",
         "--validate-fbx", str(folder / (p["asset"] + ".fbx")), "--kind", "wave", "--skin-color", str(folder / ("T_%s_SkinColor.png" % a)),
         "--expected-height-cm", str(p["height_cm_incl_skirt"]), "--minimum-width-m", "12.0",
         "--validation-out", str(folder / (p["asset"] + "_validation.json"))],
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=("A", "B"))
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    plan = plan_variant(a.variant)
    for p in plan["pieces"]:
        p["commands"] = [" ".join('"%s"' % x if " " in x else x for x in c) for c in commands(p, a.variant)[1]]
    path = HERE / ("build_plan_%s.json" % a.variant)
    path.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print("S3WAVESV3_BUILD_PLAN", path, len(plan["pieces"]))
    if not a.run:
        return
    d = json.loads((ROOT / a.variant / ("design_%s.json" % a.variant)).read_text(encoding="utf-8"))
    by_id = {L["id"]: L for L in d["layers"]}
    for p in plan["pieces"]:
        folder, cmds = commands(p, a.variant)
        folder.mkdir(parents=True, exist_ok=True)
        L = by_id[p["layer"]]
        c0, c1 = p["px_cols"]
        cv2.imwrite(str(folder / "mask.png"), cv2.imread(str(PROJECT / L["files"]["mask"]), cv2.IMREAD_GRAYSCALE)[:, c0:c1])
        cv2.imwrite(str(folder / "art.png"), cv2.imread(str(PROJECT / L["files"]["art"]))[:, c0:c1])
        for c in cmds:
            r = subprocess.run(c, cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode:
                sys.exit("FAILED %s\n%s" % (c[:3], (r.stdout + r.stderr)[-3000:]))
        val = json.loads((folder / (p["asset"] + "_validation.json")).read_text(encoding="utf-8"))
        if not val.get("pass"):
            sys.exit("VALIDATION FAIL " + p["asset"])
    print("S3WAVESV3_BUILD_OK", a.variant)


if __name__ == "__main__":
    main()
