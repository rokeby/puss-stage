"""Grease v2 fake-spec previews (OFFLINE; a calibrated sketch, NOT a renderer of record).

Per print, the decal over a flat light marble at the atlas's 2048 resolution:
  opacity  a = GreaseMask.R x GreaseGain (1.0)                                  (hp_grease_assets.py:70)
  rough    = lerp(MARBLE_R, saturate(0.30 + 0.25 G), a)                          (hp_grease_assets.py:71, :60)
  normal   = normalize(lerp(+Z, StainNormal(PrintNormal, 0.25), a))             (hp_grease_assets.py:72-77)
  shading  = albedo/pi * N.L + GGX(D, alpha = rough^2) * Schlick(F0 0.04) * smith-G / (4 N.L N.V) * N.L
  strips   columns 3-4: reflection of a bright strip light sweeping across the tile, blurred by sigma = 2 alpha
           (the s3mg_preview.py mirror-strip rule): where the strip crosses a print the crisp vs smeared edge IS the
           roughness map; the normal shifts the reflection by 2 x tilt.
  lights   columns 1-2: point light, raking (polar 70 deg from the wall normal) at three azimuths, camera in the MIRROR direction (flat-wall
           half-vector = the normal: the in-highlight view, peak brightness ~ 1/roughness^4, so glossy = bright) and
           Marble roughness MARBLE_R = 0.08 is inferred from s3mg_build_textures.py:48 (live 0.05..0.12); the
           marble is glossier than any grease value, so it reads brightest in the mirror columns.
  frame    x right, y DOWN (image), z out of the wall; normal decoded DX (x = -dh/du, y = -dh/dv).
Rows: v1 (live G + live PrintNormal) / v2.  Columns: 3 light azimuths + the decoded roughness.
Writes DerivedAssets/S3Marble/GreaseV2_20261008/previews/<id>.png and contact_sheet.png.
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

ROOT = "E:/PussStage"
OUT = ROOT + "/DerivedAssets/S3Marble/GreaseV2_20261008"
PV = OUT + "/previews"
LIVE_ATLAS = ROOT + "/DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png"
LIVE_NORMAL = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_Normal.png"
ATLAS_JSON = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/atlas.json"
PICKS = ["S005", "S001", "S032", "P041", "P087", "P001"]      # P001 = a low-confidence (isotropic) print
MARBLE_R, ALBEDO, NSTR = 0.08, 0.62, 0.25
AZ = [("point, mirror, top", -90.0, 0.0), ("point, mirror, left", 180.0, 0.0),
      ("strip refl, horizontal", "h", None), ("strip refl, vertical", "v", None)]
SPEC_K = 0.035
TILE_H = 520


def bilinear_up(img, scale_y, scale_x, y0, x0, h, w):
    """Sample a smaller texture at 2048-texel centres (bilinear, clamp)."""
    yy = (np.arange(y0, y0 + h) + 0.5) * scale_y - 0.5
    xx = (np.arange(x0, x0 + w) + 0.5) * scale_x - 0.5
    y0i = np.clip(np.floor(yy).astype(int), 0, img.shape[0] - 2)
    x0i = np.clip(np.floor(xx).astype(int), 0, img.shape[1] - 2)
    fy = np.clip(yy - y0i, 0, 1)[:, None, None]
    fx = np.clip(xx - x0i, 0, 1)[None, :, None]
    a = img[y0i][:, x0i]
    b = img[y0i][:, x0i + 1]
    c = img[y0i + 1][:, x0i]
    d = img[y0i + 1][:, x0i + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def shade(a, rough, nrm, az_deg, off_deg):
    pl, pv = math.radians(70), math.radians(70 - off_deg)
    az = math.radians(az_deg)
    Lv = np.array([math.sin(pl) * math.cos(az), math.sin(pl) * math.sin(az), math.cos(pl)])
    Vv = np.array([-math.sin(pv) * math.cos(az), -math.sin(pv) * math.sin(az), math.cos(pv)])
    Hv = (Lv + Vv) / np.linalg.norm(Lv + Vv)
    nl = np.clip(nrm @ Lv, 0, 1)
    nv = np.clip(nrm @ Vv, 1e-3, 1)
    nh = np.clip(nrm @ Hv, 0, 1)
    al = np.maximum(rough ** 2, 1e-3)
    a2 = al * al
    D = a2 / (math.pi * (nh * nh * (a2 - 1) + 1) ** 2)
    k = al / 2
    Gs = (nl / (nl * (1 - k) + k)) * (nv / (nv * (1 - k) + k))
    F = 0.04 + 0.96 * (1 - float(Hv @ Vv)) ** 5
    spec = D * Gs * F / np.maximum(4 * nl * nv, 1e-3) * nl
    col = ALBEDO / math.pi * nl * 0.6 + spec * SPEC_K
    col = col / (1 + col)
    return np.clip(col, 0, 1) ** (1 / 2.2)


def strip(rough, nrm, orient):
    """Reflection of a bright strip light (angular half-width 3 deg) whose image sweeps across the tile; the lobe
    blur is sigma = 2 alpha (radians), the same width rule as s3mg_preview.py's mirror strips.  Normal tilt shifts
    the reflected direction by 2 x tilt."""
    from scipy.special import erf
    h, w = rough.shape
    al = np.maximum(rough ** 2, 1e-3)
    sig = 2.0 * al + 0.004
    if orient == "h":
        pos = (np.arange(h)[:, None] / h - 0.5) * 0.30 + 2.0 * np.arcsin(np.clip(nrm[..., 1], -1, 1))
    else:
        pos = (np.arange(w)[None, :] / max(w, 1) - 0.5) * 0.30 + 2.0 * np.arcsin(np.clip(nrm[..., 0], -1, 1))
    hw = math.radians(3.0)
    lum = 0.5 * (erf((pos + hw) / (sig * math.sqrt(2))) - erf((pos - hw) / (sig * math.sqrt(2))))
    col = 0.08 + 0.9 * lum
    return np.clip(col, 0, 1) ** (1 / 2.2)


def surface(atlas, nmap, y, x, h, w):
    R = atlas[y:y + h, x:x + w, 0] / 255.0
    G = atlas[y:y + h, x:x + w, 1] / 255.0
    rough_d = np.clip(0.30 + 0.25 * G, 0, 1)
    rough = MARBLE_R * (1 - R) + rough_d * R
    n = bilinear_up(nmap.astype(np.float64) / 255.0 * 2 - 1, 0.5, 0.5, y, x, h, w)
    n[..., :2] *= NSTR
    n[..., 2] = np.maximum(n[..., 2], 1e-3)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    n = n * R[..., None] + np.array([0, 0, 1.0]) * (1 - R[..., None])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return R, rough, n


def label(img, text):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 14], fill=(0, 0, 0))
    d.text((3, 1), text, fill=(255, 255, 255))
    return img


def tile_for(eid, el, dirs, A1, N1, A2, N2):
    x, y, w, h = [v // 2 for v in el["atlas_rect_px"]]
    sc = TILE_H / h
    tw = max(8, int(w * sc))
    cols_lab = [c[0] for c in AZ] + ["decal rough 0.30(blk)-0.55(wht), R>0"]
    cw = max(tw, 150)
    W, H = 34 + len(cols_lab) * (cw + 4), 34 + 2 * (TILE_H + 4)
    sheet = Image.new("RGB", (W, H), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    d = dirs[eid]
    dr.text((3, 2), "%s %s  theta=%.1f deg (90 = vertical)  conf=%.2f%s" % (
        eid, el["kind"], d["theta_deg"], d["conf"], "  LOW-CONF: isotropic rim, no streaks" if d["low_confidence"] else ""),
        fill=(255, 220, 120))
    for c, lab in enumerate(cols_lab):
        dr.text((34 + c * (cw + 4), 18), lab, fill=(220, 220, 220))
    for r, (name, A, N) in enumerate((("v1", A1, N1), ("v2", A2, N2))):
        R, rough, n = surface(A, N, y, x, h, w)
        imgs = [shade(R, rough, n, az, off) if off is not None else strip(rough, n, az) for _, az, off in AZ]
        Gd = A[y:y + h, x:x + w, 1] / 255.0
        imgs.append(np.where(R > 0.02, 0.15 + 0.85 * Gd, 0.0))
        dr.text((4, 34 + r * (TILE_H + 4) + TILE_H // 2), name, fill=(255, 255, 255))
        for c, im in enumerate(imgs):
            pim = Image.fromarray((im * 255 + 0.5).astype(np.uint8), "L").convert("RGB").resize((tw, TILE_H), Image.LANCZOS)
            sheet.paste(pim, (34 + c * (cw + 4), 34 + r * (TILE_H + 4)))
    return sheet


def main():
    os.makedirs(PV, exist_ok=True)
    els = {e["id"]: e for e in json.load(open(ATLAS_JSON))["elements"]}
    dirs = json.load(open(OUT + "/gv2_directions.json"))
    A1 = np.asarray(Image.open(LIVE_ATLAS)).astype(np.float64)
    N1 = np.asarray(Image.open(LIVE_NORMAL))
    A2 = np.asarray(Image.open(OUT + "/T_HP_S03_GreaseAtlas_v2.png")).astype(np.float64)
    N2 = np.asarray(Image.open(OUT + "/T_HP_S03_PrintNormal_v2.png"))
    sheets = []
    for eid in PICKS:
        s = tile_for(eid, els[eid], dirs, A1, N1, A2, N2)
        s.save(PV + "/%s.png" % eid)
        sheets.append(s)
    # contact sheet: 2 per row
    pad = 8
    rows = [sheets[i:i + 2] for i in range(0, len(sheets), 2)]
    W = max(sum(s.width for s in r) + pad * (len(r) + 1) for r in rows)
    H = sum(max(s.height for s in r) + pad for r in rows) + pad + 20
    cs = Image.new("RGB", (W, H), (20, 20, 20))
    ImageDraw.Draw(cs).text((pad, 4), "S3 grease v1 (live) vs v2 (ridge rim + drag streaks): fake-spec raking light, not a renderer of record",
                            fill=(255, 255, 255))
    yy = 20 + pad
    for r in rows:
        xx = pad
        for s in r:
            cs.paste(s, (xx, yy))
            xx += s.width + pad
        yy += max(s.height for s in r) + pad
    cs.save(PV + "/contact_sheet.png")
    print("GV2_PREVIEW_DONE", PV + "/contact_sheet.png", cs.size)


if __name__ == "__main__":
    main()
