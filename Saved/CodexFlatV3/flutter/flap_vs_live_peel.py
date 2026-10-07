"""Read-only: for realism items, measure live _o2 SkinMask R (peel amount) under each pilot-skin flap,
and count candidate peel components in the live _o2 mask (capacity for more flaps without a re-roll)."""
import json, glob, os, sys
import numpy as np, cv2
ROOT = r"E:\PussStage\DerivedAssets\FlatV3\Realism_20261007"
rows = []
for skin_flaps in sorted(glob.glob(os.path.join(ROOT, r"P0[46]_*\*\stage1\*\skin\*_flaps.json"))):
    st = os.path.dirname(os.path.dirname(skin_flaps))
    owner = os.path.basename(st)
    o2 = glob.glob(os.path.join(st, "skin_v3", f"T_{owner}_SkinMask_o2.png"))
    pilot = glob.glob(os.path.join(st, "skin", f"T_{owner}_SkinMask.png"))
    if not o2: continue
    m = cv2.imread(o2[0], cv2.IMREAD_UNCHANGED)  # BGRA; R = peel amount
    peel_o2 = m[:, :, 2].astype(np.float32) / 255.0
    pm = cv2.imread(pilot[0], cv2.IMREAD_UNCHANGED)[:, :, 2].astype(np.float32) / 255.0 if pilot else None
    h, w = peel_o2.shape
    flaps = json.load(open(skin_flaps))["flaps"]
    per = []
    for f in flaps:
        pts = np.array([[u * (w - 1), (1 - v) * (h - 1)] for u, v in f["outline_uv_bottom_left"]], np.int32)
        mk = np.zeros((h, w), np.uint8); cv2.fillPoly(mk, [pts], 1); mk = mk.astype(bool)
        per.append({"name": f["name"].rsplit("_", 1)[-1], "o2_peel_mean": round(float(peel_o2[mk].mean()), 3) if mk.any() else None,
                    "pilot_peel_mean": round(float(pm[mk].mean()), 3) if (pm is not None and mk.any()) else None, "px": int(mk.sum())})
    peeled = (peel_o2 > 0.1).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(peeled, 8)
    comps = sorted([int(s[4]) for s in stats[1:] if s[4] >= 18], reverse=True)
    rows.append({"owner": owner, "flaps": per, "o2_peel_components_ge18px": len(comps), "o2_top_component_px": comps[:12],
                 "o2_peeled_percent": round(100.0 * float((peel_o2 > 0.1).mean()), 3)})
json.dump(rows, open(r"E:\PussStage\Saved\CodexFlatV3\flutter\flap_vs_live_peel.json", "w"), indent=1)
for r in rows:
    print(r["owner"], "o2comps", r["o2_peel_components_ge18px"], "o2%", r["o2_peeled_percent"], [(x["o2_peel_mean"], x["pilot_peel_mean"]) for x in r["flaps"]])
