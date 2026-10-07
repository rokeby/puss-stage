"""S3 waves v3, VARIANT B (Gary 7 Oct): build the 12 pieces as Flat V3 flats.  OFFLINE ONLY (never touches Unreal).

Run with the FlatV3 venv python (cv2 + numpy):
  D:/PussStageTools/FlatV3/venv/Scripts/python.exe Saved/CodexConductor/S3Waves/s3_waves_v3_B_build.py --build
  ... --build --pieces L1Breakers_P1            (subset; names = the suffix after S3_WaveV3_)
  ... --hashes <out.json>                        (hash every deliverable; used for the two-build determinism gate)
  ... --flaps-only                               (write the flap JSONs, no skin/Blender; needs the skins on disk)

Per piece (cuts, mounts and seeds = s3_waves_v3_build.plan_variant('B'), unchanged):
  1. crop mask + art to the piece COLUMNS and to the subject ROWS (top of the art .. skirt bottom), so the skin's
     panel metric = the real piece size (the uncropped canvas has 40-60 cm of empty sky above the crest, which would
     stretch the paper grain / sheet grid vertically by up to 1.46x);
  2. Tools/FlatV3/build_skin.py (4096x1024 SkinColor, 1024x2048 SkinMask/Normal; 2 % bottom-heavy peel = the minimum build_skin accepts for bottom-heavy, the plan's 1 % is refused by build_skin; seeded);
  3. flaps: L1 Breakers and L6 Foam get FOAM flaps (Gary 7 Oct: foam flicker via the Flap slot) = the 3 largest
     peel flaps + up to 3 crest-foam flaps (create_flaps accepts 3..6, build_v3_flat.py:1640-1641 [decl]);
     the other layers keep build_skin's peel flaps unchanged;
  4. Tools/FlatV3/build_v3_flat.py --mount wave-row --side L --deterministic-triangulation --triangulate-export
     (four slots Front/Flap/Timber/Edge, LOD1 = board only through the FBX LodGroup), run through
     s3_waves_v3_blender_pinned.py, which pins the FBX header CreationTimeStamp (the only wall-clock field Blender's
     FBX writer emits: io_scene_fbx/export_fbx_bin.py:3146 [decl]), under PYTHONHASHSEED=0 + --python-use-system-env
     (the FBX object UIDs are salted Python string hashes, see blender_env) so two builds can be byte-identical;
  5. --validate-fbx --kind wave in a FRESH factory-startup Blender (clean re-import), must pass.
Writes DerivedAssets/FlatV3/Scene3/waves_v3/B_build/pieces/<S3_WaveV3_...>/ and B_build/build_report_B.json.
ONE Blender at a time: refuses to start while any other headless blender.exe (command line has --background) runs.
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

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
V3 = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "waves_v3"
OUT = V3 / "B_build"
PIECES = OUT / "pieces"
PY = r"D:\PussStageTools\FlatV3\venv\Scripts\python.exe"
BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
BUILD_SKIN = PROJECT / "Tools" / "FlatV3" / "build_skin.py"
BUILD_FLAT = PROJECT / "Tools" / "FlatV3" / "build_v3_flat.py"
PINNED = HERE / "s3_waves_v3_blender_pinned.py"
TEX = PROJECT / "DerivedAssets" / "TextureLibrary"
PAPER = TEX / "Paper" / "Paper003"
OLDER = Path(r"D:\PussStageSources\FlatV3\P04\met_377854\original.jpg")
COLOR_W, COLOR_H = 4096, 1024
FOAM_LAYERS = ("L1_Breakers", "L6_Foam")
FOAM = {"depth_cm": 16.0, "width_cm": 50.0, "step_cm": 10.0, "end_margin_cm": 40.0, "spacing_cm": 150.0,
        "max_crest_drop_cm": 30.0, "count": 3, "keep_peel": 3, "curl_cm": 0.45, "inset_cm": 0.6,
        "min_luma": 140.0}
DELIVERABLE_SUFFIXES = (".fbx", "_SkinColor.png", "_SkinMask.png", "_SkinNormal.png", "_flaps.json",
                        "_flaps_v3.json", "_mi_params.json", "_sheet_grid.json")


def load_plan():
    spec = importlib.util.spec_from_file_location("s3wv3_build", HERE / "s3_waves_v3_build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plan = mod.plan_variant("B")
    plan["pieces"] = [dict(p, suffix=p["asset"][len("SM_FlatV3_"):]) for p in plan["pieces"]]
    return plan


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def other_headless_blender():
    """Command lines of running blender.exe processes that are headless (--background / -b)."""
    try:
        out = subprocess.run(["wmic", "process", "where", "name='blender.exe'", "get", "ProcessId,CommandLine"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return []
    return [line.strip() for line in out.splitlines() if "--background" in line or " -b " in line]


def wait_for_blender_slot(limit_s=3600):
    t0 = time.time()
    while True:
        busy = other_headless_blender()
        if not busy:
            return
        if time.time() - t0 > limit_s:
            sys.exit("BLENDER_SLOT_BUSY " + json.dumps(busy))
        print("WAITING_FOR_HEADLESS_BLENDER", busy, flush=True)
        time.sleep(20)


def blender_env():
    """Blender's FBX writer derives every object UID from Python hash(str) (io_scene_fbx/fbx_utils.py:815-831 [decl]),
    which is salted per process.  Measured here: two otherwise identical builds differed ONLY in those UIDs.  Blender
    ignores PYTHONHASHSEED unless --python-use-system-env is given (measured: hash('abc') differs run to run without it,
    is equal with it + PYTHONHASHSEED=0).  PYTHONPATH / user site stay OFF so the flag admits nothing else."""
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def run(cmd, log, env=None):
    r = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    log.write("\n$ " + " ".join(cmd) + "\n" + r.stdout[-6000:] + r.stderr[-6000:])
    log.flush()
    if r.returncode:
        sys.exit("FAILED rc=%d %s\n%s" % (r.returncode, cmd[:4], (r.stdout + r.stderr)[-3000:]))
    return r.stdout


# ------------------------------------------------------------------------------------------------ crop
def crop_piece(p, res, design_by_id):
    """-> (mask, art, crop) with mask/art cropped to the piece columns and subject rows."""
    L = design_by_id[p["layer"]]
    mask = cv2.imread(str(PROJECT / L["files"]["mask"]), cv2.IMREAD_GRAYSCALE)
    art = cv2.imread(str(PROJECT / L["files"]["art"]), cv2.IMREAD_COLOR)
    if mask is None or art is None or mask.shape != art.shape[:2]:
        raise RuntimeError("MASK_ART_EXTENT|%s" % p["layer"])
    c0, c1 = p["px_cols"]
    sub = mask[:, c0:c1]
    rows = np.nonzero(sub.max(1) > 127)[0]
    r0 = int(rows.min())
    if int(rows.max()) != mask.shape[0] - 1:
        raise RuntimeError("SKIRT_NOT_AT_CANVAS_BOTTOM|%s" % p["suffix"])
    m, a = sub[r0:, :].copy(), art[r0:, c0:c1].copy()
    crop = {"rows": [r0, int(mask.shape[0])], "cols": [int(c0), int(c1)],
            "width_cm": round((c1 - c0) / res, 3), "height_cm": round((mask.shape[0] - r0) / res, 3)}
    if abs(crop["height_cm"] - p["height_cm_incl_skirt"]) > 0.11:
        raise RuntimeError("HEIGHT_VS_PLAN|%s|%s|%s" % (p["suffix"], crop["height_cm"], p["height_cm_incl_skirt"]))
    return m, a, crop


# ------------------------------------------------------------------------------------------------ foam flaps
def foam_flap_descriptors(mask, art, res, u_range_cm, avoid_u_cm, asset, cfg=FOAM):
    """Deterministic crest-foam flaps (no RNG).  mask/art = the cropped piece (row 0 = top).  A flap is a band under
    the crest: top edge = the crest (inset), bottom edge = ONE horizontal hinge line, so the build's horizontal weight
    (by v, build_v3_flat.py:1555-1577) runs 0 at the hinge to 1 at the crest.  A window qualifies only if every
    column is solid paint from the crest down to the hinge (no curl mouth), the crest drops <= max_crest_drop_cm
    inside it, it is >= end_margin from the piece ends and outside avoid_u (the P1/P2 overlap), and its foam band
    mean luma >= min_luma.  Highest-luma windows win, >= spacing apart."""
    h, w = mask.shape
    solid = mask > 127
    top = np.where(solid.any(0), np.argmax(solid, axis=0), h)
    luma = cv2.cvtColor(art, cv2.COLOR_BGR2GRAY).astype(np.float64)
    d_px = int(round(cfg["depth_cm"] * res))
    w_px = int(round(cfg["width_cm"] * res))
    step = max(1, int(round(cfg["step_cm"] * res)))
    margin = int(round(cfg["end_margin_cm"] * res))
    drop_px = cfg["max_crest_drop_cm"] * res
    inset = cfg["inset_cm"] * res
    u0 = u_range_cm[0]

    def u_of(col):
        return u0 + col / res

    cands = []
    for c0 in range(margin, w - margin - w_px, step):
        cols = np.arange(c0, c0 + w_px)
        t = top[cols]
        if (t >= h).any() or float(t.max() - t.min()) > drop_px:
            continue
        hinge = int(t.max()) + d_px
        if hinge >= h - int(round(25 * res)):       # keep the hinge clear of the skirt / peel zone
            continue
        if avoid_u_cm and not (u_of(c0 + w_px) <= avoid_u_cm[0] or u_of(c0) >= avoid_u_cm[1]):
            continue
        if not all(solid[t[i]:hinge + 1, cols[i]].all() for i in range(len(cols))):
            continue
        band = np.concatenate([luma[t[i]:t[i] + d_px, cols[i]] for i in range(0, len(cols), 3)])
        score = float(band.mean())
        if score < cfg["min_luma"]:
            continue
        cands.append((score, c0, hinge))
    cands.sort(key=lambda r: (-r[0], r[1]))
    picked = []
    for score, c0, hinge in cands:
        if all(abs(c0 - q[1]) >= cfg["spacing_cm"] * res for q in picked):
            picked.append((score, c0, hinge))
        if len(picked) == cfg["count"]:
            break
    picked.sort(key=lambda r: r[1])
    out = []
    for i, (score, c0, hinge) in enumerate(picked, start=1):
        n_top = 30
        xs = [c0 + round(k * (w_px - 1) / (n_top - 1)) for k in range(n_top)]
        pts = [(x + 0.5, float(top[x]) + inset) for x in xs]           # crest, left -> right (pixel y down)
        pts += [(xs[-1] + 0.5, float(hinge)), (xs[0] + 0.5, float(hinge))]
        outline = [[round(px / w, 8), round(1.0 - py / h, 8)] for px, py in pts]
        us = [o[0] for o in outline]
        vs = [o[1] for o in outline]
        out.append({"name": "%s_FoamFlap_%d" % (asset, i), "kind": "foam_crest", "foam_luma": round(score, 2),
                    "u_range_cm": [round(u_of(c0), 2), round(u_of(c0 + w_px), 2)],
                    "uv_bounds_bottom_left": [min(us), min(vs), max(us), max(vs)], "orientation": "horizontal",
                    "curl_cm": cfg["curl_cm"], "outline_uv_bottom_left": outline})
    return out


def merged_flaps(skin_flaps, foam, cfg=FOAM):
    keep = list(skin_flaps)[:cfg["keep_peel"]]
    allf = keep + list(foam)
    if not 3 <= len(allf) <= 6:
        raise RuntimeError("FLAP_COUNT|%d" % len(allf))
    names = [f["name"] for f in allf]
    if len(set(names)) != len(names):
        raise RuntimeError("FLAP_NAMES_DUP")
    return allf


# ------------------------------------------------------------------------------------------------ build
def piece_folder(p):
    return PIECES / p["suffix"]


def build_piece(p, res, design_by_id, log, flaps_only=False):
    folder = piece_folder(p)
    folder.mkdir(parents=True, exist_ok=True)
    a = p["suffix"]
    mask, art, crop = crop_piece(p, res, design_by_id)
    cv2.imwrite(str(folder / "mask.png"), mask)
    cv2.imwrite(str(folder / "art.png"), art)
    if not flaps_only:
        run([PY, str(BUILD_SKIN), "--mask", str(folder / "mask.png"), "--art", str(folder / "art.png"),
             "--older-poster", str(OLDER), "--paper-displacement", str(PAPER / "Paper003_4K-JPG_Displacement.jpg"),
             "--paper-roughness", str(PAPER / "Paper003_4K-JPG_Roughness.jpg"), "--texture-root", str(TEX),
             "--aged-output", str(folder / "Aged"), "--stencil-text", "PUSS S3 WAVE " + a[len("S3_WaveV3_"):],
             "--height-cm", "%.3f" % crop["height_cm"], "--width-cm", "%.3f" % crop["width_cm"],
             "--color-width", str(COLOR_W), "--color-height", str(COLOR_H), "--asset-name", a,
             "--output", str(folder), "--seed", str(p["seed"]), "--peel-percent", "2.0",
             "--peel-profile", "bottom-heavy"], log)
    skin_flaps = json.loads((folder / ("%s_flaps.json" % a)).read_text(encoding="utf-8"))["flaps"]
    foam = []
    if p["layer"] in FOAM_LAYERS:
        cut = p["cut_u_cm"]
        avoid = [cut - 150.0 - 30.0, cut + 150.0 + 30.0]           # the P1/P2 overlap, plus 30 cm
        foam = foam_flap_descriptors(mask, art, res, p["u_range_cm"], avoid, a)
        if len(foam) < 2:
            raise RuntimeError("FOAM_FLAPS_TOO_FEW|%s|%d" % (a, len(foam)))
        flaps = merged_flaps(skin_flaps, foam)
    else:
        flaps = list(skin_flaps)
    (folder / ("%s_flaps_v3.json" % a)).write_text(
        json.dumps({"schema_version": 1, "asset": a, "flaps": flaps,
                    "source": "build_skin peel flaps" + (" (3 largest) + crest foam flaps" if foam else " (unchanged)")},
                   indent=2), encoding="utf-8")
    if flaps_only:
        return {"suffix": a, "crop": crop, "foam_flaps": len(foam), "flaps": len(flaps)}
    fbx = folder / ("SM_FlatV3_%s.fbx" % a)
    before = fbx.stat().st_mtime_ns if fbx.exists() else None
    wait_for_blender_slot()
    run([BLENDER, "--background", "--factory-startup", "--python-use-system-env", "--python", str(PINNED), "--",
         "--mask", str(folder / "mask.png"), "--art", str(folder / ("T_%s_SkinColor.png" % a)),
         "--skin-mask", str(folder / ("T_%s_SkinMask.png" % a)), "--skin-normal", str(folder / ("T_%s_SkinNormal.png" % a)),
         "--flaps", str(folder / ("%s_flaps_v3.json" % a)), "--aged-texture-dir", str(folder / "Aged"),
         "--height-cm", "%.3f" % crop["height_cm"], "--side", "L", "--name", a, "--asset-name", a,
         "--mount", "wave-row", "--deterministic-triangulation", "--triangulate-export",
         "--output-dir", str(folder), "--texture-root", str(TEX)], log, env=blender_env())
    if not fbx.is_file() or (before is not None and fbx.stat().st_mtime_ns <= before):
        raise RuntimeError("STALE_OR_MISSING_FBX|%s" % fbx)
    val = folder / ("SM_FlatV3_%s_validation.json" % a)
    wait_for_blender_slot()
    run([BLENDER, "--background", "--factory-startup", "--python", str(BUILD_FLAT), "--",
         "--validate-fbx", str(fbx), "--kind", "wave", "--skin-color", str(folder / ("T_%s_SkinColor.png" % a)),
         "--expected-height-cm", "%.3f" % crop["height_cm"], "--minimum-width-m", "11.0",
         "--validation-out", str(val)], log)
    v = json.loads(val.read_text(encoding="utf-8"))
    if not v.get("pass"):
        raise RuntimeError("VALIDATION_FAIL|%s" % a)
    return {"suffix": a, "crop": crop, "foam_flaps": len(foam), "flaps": len(flaps), "validation_pass": True,
            "bounds_m": v["bounds_m"], "triangle_counts": v["triangle_counts"]}


def deliverables(folder, a):
    out = {}
    for name in sorted(os.listdir(folder)):
        full = folder / name
        if full.is_file() and name.endswith(DELIVERABLE_SUFFIXES):
            out[name] = sha(full)
    return out


def hashes(plan):
    return {p["suffix"]: deliverables(piece_folder(p), p["suffix"]) for p in plan["pieces"]
            if piece_folder(p).is_dir()}


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    import struct
    return list(struct.unpack(">II", head[16:24]))


def texture_memory(plan):
    """GPU bytes with full mips (x4/3): SkinColor BC7 1 B/px, SkinMask BC7 (TC_Masks) 1 B/px, SkinNormal BC5 1 B/px."""
    rows, total = [], 0.0
    for p in plan["pieces"]:
        f, a = piece_folder(p), p["suffix"]
        sizes = {k: png_size(f / ("T_%s_%s.png" % (a, k))) for k in ("SkinColor", "SkinMask", "SkinNormal")}
        b = sum(w * h for w, h in sizes.values()) * 4.0 / 3.0
        total += b
        rows.append({"piece": a, "sizes": sizes, "gpu_mb": round(b / 2 ** 20, 2),
                     "max_dim_ok": all(max(s) <= 4096 for s in sizes.values())})
    return {"pieces": rows, "total_gpu_mb": round(total / 2 ** 20, 1),
            "rule": "BC7/BC5 = 1 byte/texel, full mip chain x4/3 [inf: UE block sizes, not read from the editor]"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--flaps-only", action="store_true")
    ap.add_argument("--pieces", nargs="*")
    ap.add_argument("--hashes")
    a = ap.parse_args()
    plan = load_plan()
    design = json.loads((V3 / "B" / "design_B.json").read_text(encoding="utf-8"))
    by_id = {L["id"]: L for L in design["layers"]}
    res = float(design["res_px_per_cm"])
    sel = [p for p in plan["pieces"] if not a.pieces or p["suffix"][len("S3_WaveV3_"):] in a.pieces]
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build or a.flaps_only:
        report_path = OUT / "build_report_B.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"pieces": {}}
        with open(OUT / "build_log_B.txt", "a", encoding="utf-8") as log:
            for p in sel:
                t0 = time.time()
                row = build_piece(p, res, by_id, log, flaps_only=a.flaps_only)
                row.update({"seconds": round(time.time() - t0, 1), "seed": p["seed"], "mount_local": p["mount_local"],
                            "u_range_cm": p["u_range_cm"], "layer": p["layer"], "piece": p["piece"],
                            "asset": p["asset"]})
                report["pieces"][p["suffix"]] = row
                report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
                print("S3WAVESV3B_PIECE_OK", p["suffix"], row["seconds"], flush=True)
        if not a.flaps_only and all(piece_folder(p).joinpath("SM_FlatV3_%s.fbx" % p["suffix"]).exists()
                                    for p in plan["pieces"]):
            report["texture_memory"] = texture_memory(plan)
            report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if a.hashes:
        Path(a.hashes).write_text(json.dumps(hashes(plan), indent=1, sort_keys=True), encoding="utf-8")
        print("S3WAVESV3B_HASHES", a.hashes)


if __name__ == "__main__":
    main()
