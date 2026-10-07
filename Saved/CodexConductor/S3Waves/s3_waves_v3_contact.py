"""Front-on silhouette contact sheets for the S3 waves v3 design (offline, deterministic, reads design_<v>.json).

Per variant writes DerivedAssets/FlatV3/Scene3/waves_v3/previews/:
  contact_<v>_silhouettes.png   each layer alone: black cut silhouette over its painted card, true scale, ruler
  contact_<v>_frontal_stack.png all layers overlaid back-to-front, orthographic front view, over the backdrop skin
"""
import json
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parents[3]
ROOT = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "waves_v3"
PREV = ROOT / "previews"
BACKDROP = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "backdrop" / "textures" / "T_S3_OpalBeach_Backdrop_SkinColor.png"
SCALE = 0.5   # px per cm on the sheet
FONT = cv2.FONT_HERSHEY_SIMPLEX


def label(img, text, xy, size=0.6, col=(235, 235, 235)):
    cv2.putText(img, text, xy, FONT, size, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, xy, FONT, size, col, 1, cv2.LINE_AA)


def load_layer(L):
    rgba = cv2.imread(str(PROJECT / L["files"]["rgba"]), cv2.IMREAD_UNCHANGED)
    h_cm = L["canvas_cm"]["v"][1] - L["canvas_cm"]["v"][0]
    w = int(2200 * SCALE)
    h = int(h_cm * SCALE)
    return cv2.resize(rgba, (w, h), interpolation=cv2.INTER_AREA)


def silhouettes(design):
    v = design["variant"]
    tiles = []
    for L in design["layers"]:
        card = load_layer(L)
        h, w = card.shape[:2]
        tile = np.full((h + 70, w + 40, 3), 58, np.uint8)
        a = card[:, :, 3:4].astype(np.float32) / 255
        region = tile[50:50 + h, 20:20 + w].astype(np.float32)
        tile[50:50 + h, 20:20 + w] = (card[:, :, :3] * a + region * (1 - a)).astype(np.uint8)
        # black silhouette strip (pure cut line) under the painted card
        sil = np.full((int(h * 0.45) + 10, w + 40, 3), 214, np.uint8)
        small = cv2.resize(card[:, :, 3], (w, int(h * 0.45)), interpolation=cv2.INTER_AREA)
        sil[5:5 + small.shape[0], 20:20 + w][small > 127] = (22, 22, 22)
        floor_y = 50 + int((L["canvas_cm"]["v"][1]) * SCALE)
        cv2.line(tile, (20, floor_y), (20 + w, floor_y), (60, 60, 200), 1)
        for m in range(0, 2201, 100):
            x = 20 + int(m * SCALE)
            cv2.line(tile, (x, floor_y), (x, floor_y + (8 if m % 500 == 0 else 4)), (200, 200, 200), 1)
        label(tile, "%s %s  %s  root-local x %d  max %.0f cm (peak %d / trough %d)  holes %d" % (
            v, L["id"], L["kind"], L["x"], L["max_height_cm"], L["peak"], L["trough"], L["cut_gates"]["holes_kept"]),
            (22, 30))
        tiles.append(np.vstack([tile, sil]))
    sheet = np.vstack(tiles)
    head = np.full((60, sheet.shape[1], 3), 30, np.uint8)
    label(head, "S3 waves v3 - variant %s - front-on silhouettes, 1 px = 2 cm; red = floor top; ticks 1 m; strip = 22 m "
          "(20 m hangar + 1 m overhang each side)" % v, (20, 38), 0.62)
    out = PREV / ("contact_%s_silhouettes.png" % v)
    cv2.imwrite(str(out), np.vstack([head, sheet]))
    return out


def frontal_stack(design):
    """Orthographic front view, 22 m x 6 m window above floor top; backdrop skin bottom 6 m (its root-local z
    -35..2965 after today's 150 cm lowering -> floor top 115 sits 150 cm up the skin)."""
    v = design["variant"]
    W, Hcm = int(2200 * SCALE), 600
    H = int(Hcm * SCALE)
    bd = cv2.imread(str(BACKDROP), cv2.IMREAD_UNCHANGED)[:, :, :3]
    # skin covers 20 m x 30 m; window z (above floor top) 0..600 -> skin from-bottom 150..750 cm
    px_per_cm = bd.shape[0] / 3000.0
    y1 = bd.shape[0] - int(150 * px_per_cm)
    y0 = bd.shape[0] - int(750 * px_per_cm)
    crop = cv2.resize(bd[y0:y1], (int(2000 * SCALE), H), interpolation=cv2.INTER_AREA)
    img = np.full((H, W, 3), 40, np.uint8)
    img[:, int(100 * SCALE):int(100 * SCALE) + crop.shape[1]] = crop
    for L in sorted(design["layers"], key=lambda r: -r["x"]):
        card = load_layer(L)
        top_cm = L["canvas_cm"]["v"][1]
        # card row r is at height top_cm - r/SCALE; window row y is at height Hcm - y/SCALE
        off = int((Hcm - top_cm) * SCALE)
        r0 = max(0, -off)
        y0, y1 = off + r0, min(H, off + card.shape[0])
        part = card[r0:r0 + (y1 - y0)]
        a = part[:, :, 3:4].astype(np.float32) / 255
        img[y0:y1] = (part[:, :, :3] * a + img[y0:y1] * (1 - a)).astype(np.uint8)
    for m in range(0, 601, 100):
        y = H - int(m * SCALE)
        cv2.line(img, (0, y), (12, y), (40, 40, 220), 1)
        label(img, "%d" % m, (14, max(12, y - 2)), 0.4)
    out = PREV / ("contact_%s_frontal_stack.png" % v)
    head = np.full((44, W, 3), 30, np.uint8)
    label(head, "variant %s - orthographic front view, all six layers back-to-front over the backdrop skin "
          "(0-6 m above floor top; cm ticks)" % v, (10, 28), 0.5)
    cv2.imwrite(str(out), np.vstack([head, img]))
    return out


def main():
    PREV.mkdir(parents=True, exist_ok=True)
    for v in ("A", "B"):
        d = json.loads((ROOT / v / ("design_%s.json" % v)).read_text(encoding="utf-8"))
        print(silhouettes(d))
        print(frontal_stack(d))
    print("S3WAVESV3_CONTACT_OK")


if __name__ == "__main__":
    main()
