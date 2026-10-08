"""Sample the colour the wave FRONT shows right at its cut edge (the band the Edge wall continues), all 12 live pieces.
OFFLINE.  Inputs = the LIVE skins (B_build/pieces/<suffix>/T_<suffix>_SkinColor.png + mask.png; SkinColor spans the
mask extent: validator front_skincolor_background_coverage = 0 background texels [decl, validation json]).
Band = mask minus mask eroded by BAND_CM, resampled to SkinColor size.  k-means (k=6, Lab, seeded) over all bands.
Sea cluster = largest MID-tone cool cluster: 30 <= L* <= 60 and b* <= 0 (blue-green side).  Not the darkest trough
tone: a near-black edge is the 'black sliver' Gary asked to fix.  Lip (CanvasColor) = the next lighter non-foam
cluster with b* <= 2 (a painted highlight on the wrap); TimberDark = 0.8 x TimberLight (subtle brush grain only).
Writes edge_sea_colour.json + a swatch PNG.  Values: sRGB 8-bit and LINEAR (UE LinearColor params are linear).
Run: D:/PussStageTools/FlatV3/venv/Scripts/python.exe Saved/CodexFlatV3/s3waves/sample_edge_sea_colour.py
"""
import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
PIECES = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "waves_v3" / "B_build" / "pieces"
OUT = HERE / "edge_sea_colour.json"
SWATCH = HERE / "edge_sea_colour_swatch.png"
RES_PX_PER_CM = 3.2768            # design_B.json res_px_per_cm [decl]
BAND_CM = 3.0
K = 6


def s2l(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055) * 255.0


def main():
    samples, per_piece = [], {}
    for d in sorted(PIECES.iterdir()):
        a = d.name
        mask = cv2.imread(str(d / "mask.png"), cv2.IMREAD_GRAYSCALE)
        col = cv2.imread(str(d / ("T_%s_SkinColor.png" % a)), cv2.IMREAD_COLOR)
        h, w = col.shape[:2]
        m = (cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST) > 127).astype(np.uint8)
        kx = max(1, int(round(BAND_CM * RES_PX_PER_CM * w / mask.shape[1])))
        ky = max(1, int(round(BAND_CM * RES_PX_PER_CM * h / mask.shape[0])))
        er = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * kx + 1, 2 * ky + 1)))
        band = (m > 0) & (er == 0)
        px = col[band][:, ::-1]                               # BGR -> RGB
        rng = np.random.default_rng(1)
        take = px[rng.choice(len(px), size=min(len(px), 40000), replace=False)]
        samples.append(take)
        per_piece[a] = {"band_px": int(band.sum()), "median_srgb": [int(v) for v in np.median(px, 0)]}
    allpx = np.concatenate(samples).astype(np.float32)
    lab = cv2.cvtColor(allpx.reshape(-1, 1, 3) / 255.0, cv2.COLOR_RGB2LAB).reshape(-1, 3)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.1)
    cv2.setRNGSeed(7)
    _, lbl, cen = cv2.kmeans(lab, K, None, crit, 5, cv2.KMEANS_PP_CENTERS)
    lbl = lbl.ravel()
    clusters = []
    for i in range(K):
        sel = allpx[lbl == i]
        srgb = np.median(sel, 0)
        L, A, B = cen[i]
        clusters.append({"share": round(float((lbl == i).mean()), 4), "srgb": [int(round(v)) for v in srgb],
                         "linear": [round(float(v), 4) for v in s2l(srgb)], "lab": [round(float(L), 1),
                                                                                    round(float(A), 1),
                                                                                    round(float(B), 1)],
                         "foam": bool(L >= 78.0), "mid_cool": bool(30.0 <= L <= 60.0 and B <= 0.0)})
    clusters.sort(key=lambda c: -c["share"])
    sea = [c for c in clusters if c["mid_cool"]]
    pick = sea[0] if sea else None
    lighter = sorted([c for c in clusters if not c["foam"] and c["lab"][2] <= 2.0 and c["lab"][0] > pick["lab"][0]],
                     key=lambda c: c["lab"][0])
    lip = lighter[0] if lighter else pick
    dark = [round(v * 0.8, 4) for v in pick["linear"]]
    rec = {"band_cm": BAND_CM, "k": K, "clusters": clusters, "pick": pick, "per_piece": per_piece,
           "mi_vectors_linear": {"TimberLight": pick["linear"], "TimberDark": dark, "CanvasColor": lip["linear"]},
           "mi_vectors_srgb8": {"TimberLight": pick["srgb"], "TimberDark": [int(round(v)) for v in l2s(dark)],
                                "CanvasColor": lip["srgb"]},
           "tier": "measured (offline pixel statistics of the live skins); the choice of cluster is [inf] = Gary's "
                   "look call, adjustable on the MI"}
    OUT.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    sw = np.zeros((120, 120 * K, 3), np.uint8)
    for i, c in enumerate(clusters):
        sw[:, i * 120:(i + 1) * 120] = c["srgb"][::-1]
        cv2.putText(sw, "%.0f%%" % (100 * c["share"]), (i * 120 + 6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 0, 255) if c is pick else (255, 255, 255), 2)
    cv2.imwrite(str(SWATCH), sw)
    print("S3T5O_EDGE_COLOUR_OK|pick_srgb=%s|linear=%s|out=%s" % (pick["srgb"], pick["linear"], OUT))


if __name__ == "__main__":
    main()
