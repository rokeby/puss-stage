"""OFFLINE ONLY. Derive MORE flap descriptors from an existing live skin's SkinMask R (peel amount) without
re-running build_skin (so the skin textures stay bit-identical; no RNG is drawn).

Control: rebuilding the N=5 descriptors from the same mask must reproduce the skin's saved *_flaps.json exactly
(same outlines) -- otherwise the reconstruction is not faithful and N>5 output must not be trusted.
Writes only under Saved/CodexFlatV3/flutter/.
"""
import json, math, sys, os
from pathlib import Path
import numpy as np, cv2
sys.path.insert(0, r"E:\PussStage\Tools\FlatV3")
import build_skin as bs  # sheet_fields, flap_descriptors (read-only use)

OUT = Path(r"E:\PussStage\Saved\CodexFlatV3\flutter")

def flaps_n(peeled, seam, pw, ph, name, n, min_area=18, curl0=0.55, dcurl=0.08):
    """build_skin.flap_descriptors (build_skin.py:622-686) with the [:5] cap and 3..6 contract lifted to n."""
    seam_peel = (peeled & (seam < 8.0)).astype(np.uint8)
    count, labels, stats, cents = cv2.connectedComponentsWithStats(seam_peel, 8)
    cands = [(int(s[4]), int(s[0]), int(s[1]), int(s[2]), int(s[3]), cents[i], i) for i, s in enumerate(stats) if i and s[4] >= min_area]
    cands.sort(reverse=True, key=lambda c: c[0])
    if len(cands) < n:   # top up from all peel components (not only seam-adjacent), largest first, no duplicates
        c2, l2, s2, ce2 = cv2.connectedComponentsWithStats(peeled.astype(np.uint8), 8)
        used = set()
        for c in cands:
            used.add(int(np.bincount(l2[labels == c[6]]).argmax()))
        extra = [(int(s[4]), int(s[0]), int(s[1]), int(s[2]), int(s[3]), ce2[i], ("all", i)) for i, s in enumerate(s2) if i and s[4] >= min_area and i not in used]
        extra.sort(reverse=True, key=lambda c: c[0])
        cands = cands + extra
    out = []
    H, W = peeled.shape
    c2l = None
    for index, (area, x, y, w, h, _, label) in enumerate(cands[:n], start=1):
        if isinstance(label, tuple):
            if c2l is None: c2l = cv2.connectedComponentsWithStats(peeled.astype(np.uint8), 8)[1]
            comp = (c2l == label[1]).astype(np.uint8)
        else:
            comp = (labels == label).astype(np.uint8)
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        per = cv2.arcLength(contour, True)
        contour = cv2.approxPolyDP(contour, max(1.0, per * 0.012), True).reshape(-1, 2)
        if len(contour) > 40: contour = contour[:: int(math.ceil(len(contour) / 40))]
        outline = [[round(float(px / W), 8), round(float(1.0 - py / H), 8)] for px, py in contour]
        u0, u1 = x / W, (x + w) / W; v0, v1 = 1.0 - (y + h) / H, 1.0 - y / H
        pw_, ph_ = (u1 - u0) * pw, (v1 - v0) * ph
        out.append({"name": f"{name}_Flap_{index}", "component_pixels": area, "outline_uv_bottom_left": outline,
                    "orientation": "horizontal" if pw_ >= ph_ else "vertical", "size_cm": [round(pw_, 1), round(ph_, 1)],
                    "curl_cm": round(curl0 + dcurl * index, 3), "seam_adjacent": not isinstance(label, tuple)})
    return out

def run(skin_dir, owner, suffix, n):
    man = json.loads((skin_dir / f"{owner}_skin_manifest.json").read_text())
    pw, ph = man["panel_size_cm"]
    mask = cv2.imread(str(skin_dir / man["textures"]["SkinMask"]["file"]), cv2.IMREAD_UNCHANGED)
    peel = mask[:, :, 2]
    peeled = peel >= 26          # build_skin.py:581 floors peeled texels at 0.12 (=30.6/255); unpeeled = 0
    H, W = peeled.shape
    fields = bs.sheet_fields(W, H, pw, ph)
    saved = json.loads((skin_dir / f"{owner}_flaps.json").read_text())["flaps"]
    ctrl = flaps_n(peeled, fields["seam_distance_cm"], pw, ph, owner, len(saved))
    same = [a["outline_uv_bottom_left"] == b["outline_uv_bottom_left"] for a, b in zip(ctrl, saved)]
    more = flaps_n(peeled, fields["seam_distance_cm"], pw, ph, owner, n)
    return {"owner": owner, "skin": suffix, "panel_cm": [pw, ph], "saved_flaps": len(saved), "control_identical": same,
            "control_pass": all(same) and len(ctrl) == len(saved), "n_requested": n, "n_made": len(more),
            "sizes_cm": [f["size_cm"] for f in more], "flaps": more}

if __name__ == "__main__":
    st = Path(r"E:\PussStage\DerivedAssets\FlatV3\Realism_20261007\P04_gothic_blasted_trees\13_gothic_arch_ruin\stage1\P04_real_13_gothic_arch_ruin_R")
    owner = st.name
    res = {}
    for sub, suffix in (("skin", "pilot"), ("skin_v3", "_o2 live")):
        r = run(st / sub, owner, suffix, 12)
        res[sub] = r
        print(sub, "control_pass", r["control_pass"], r["control_identical"], "made", r["n_made"], "sizes", r["sizes_cm"])
    (OUT / "more_flaps_P04_real_13.json").write_text(json.dumps({"schema_version": 1, "asset": owner, "flaps": res["skin_v3"]["flaps"],
        "provenance": "derived offline from skin_v3 SkinMask_o2 R; NOT a build input yet", "control": {k: v["control_pass"] for k, v in res.items()}}, indent=1))
