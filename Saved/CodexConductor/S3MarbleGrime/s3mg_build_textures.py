"""S3 marble grime prep (OFFLINE, 7 Oct): photo-derived grime / scratch / grease textures + previews.

NO Unreal. Reads only; writes only DerivedAssets/S3Marble/Grime_20261007/.

Sources (read-only):
  DerivedAssets/S3Marble/RefPhotos_MetalDoor_20261006/metal_door_ref_01..04.jpg   (Gary's references)
  DerivedAssets/S3Marble/Marble021/Marble021_2K-JPG_{Color,Roughness,NormalDX}.jpg (live marble B source)
  DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_BaseColor.png     (live print atlas, alpha)
  DerivedAssets/S3Marble/Grime_20261007/geometry.json  (s3mg_geometry.py)

Textures written (all power of two <= 2048; LINEAR unless named _sRGB):
  T_S3MG_Marble021_RoughGrime.png   2048 L8   LINEAR  -> RoughnessTexture of a NEW child MI (TC_GRAYSCALE, sRGB off,
                                    same compression as T_Marble021_Roughness so the master's LINEAR_GRAYSCALE sampler fits)
                                    encodes rt for the master's  roughness = lerp(MinR, MaxR, rt)  with MinR=0.04 MaxR=0.60
  T_S3MG_Marble021_NormalDX_Scratch.png 2048 RGB8 LINEAR (TC_NORMALMAP) marble normal + scratch grooves
  T_S3MG_Marble021_Color_Grime_sRGB.png 2048 RGB8 sRGB (TC_DEFAULT) marble colour x faint ambient grime (<= 7 %)
  T_S3MG_GreaseAtlas.png            2048 RGB8 LINEAR (TC_MASKS) same UV layout as the 4096 print atlas:
                                    R = feathered grease opacity, G = smear height (normal), B = faint albedo weight
  T_S3MG_GrimeBand.png              2048x512 RGB8 LINEAR (TC_MASKS) low-wall band, tileable in U:
                                    R = grime opacity, G = roughness target, B = albedo darkening
  T_S3MG_SeamStrip.png              512x2048 RGB8 LINEAR (TC_MASKS) seam/corner strip, tileable in V, edge at u=0
  masks/*.png                       intermediate photo masks (for review)
Previews: preview_{baseline,A,B,C}.png  (fake-spec camera render of the S3 main camera), sheet_ABC.png
"""
import hashlib
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = "E:/PussStage"
OUT = ROOT + "/DerivedAssets/S3Marble/Grime_20261007"
REF = ROOT + "/DerivedAssets/S3Marble/RefPhotos_MetalDoor_20261006"
MARBLE = ROOT + "/DerivedAssets/S3Marble/Marble021/Marble021_2K-JPG_"
ATLAS = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_BaseColor.png"
ATLAS_ROUGH = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_Roughness.png"
ATLAS_JSON = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/atlas.json"
STILL = ROOT + "/Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-173228-floathold/00_f300.png"
SEED = 20261007
TILE = 2048
REPEAT_CM = 150.0                    # live RepeatCm (s3_marble_tiling_material.py:53)
PHOTO_PX_PER_CM = 1932 / 90.0        # INFERRED: a door leaf ~90 cm across the photo width
TEX_PX_PER_CM = TILE / REPEAT_CM     # 13.65
MIN_R, MAX_R = 0.04, 0.60            # proposed child-MI Min/Max Roughness for the new rt encoding
LIVE_MIN_R, LIVE_MAX_R = 0.05, 0.12  # live (s3_marble_tiling_record.json "look", look_source live)

rng = np.random.default_rng(SEED)


def srgb_to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def save(a, name, mode=None):
    a = np.clip(a, 0, 1)
    img = Image.fromarray((a * 255 + 0.5).astype(np.uint8), mode)
    p = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p)
    return p


# --------------------------------------------------------------------------------------------- photo masks
# Object exclusions (fractions of width/height), from looking at the four photos: keypads, handle, tape, letter,
# hinge/bracket, the door seam in 04 and the frame edges.
EXCLUDE = {
    1: [(0.0, 0.0, 0.03, 1.0), (0.96, 0.0, 1.0, 1.0)],
    2: [(0.0, 0.0, 0.04, 1.0), (0.96, 0.7, 1.0, 1.0), (0.0, 0.72, 0.08, 0.9)],
    3: [(0.0, 0.85, 0.08, 1.0), (0.0, 0.55, 0.03, 0.62), (0.97, 0.0, 1.0, 1.0)],
    4: [(0.31, 0.62, 0.48, 0.92), (0.0, 0.0, 0.02, 1.0)],
}


def photo_layers(i):
    im = Image.open("%s/metal_door_ref_%02d.jpg" % (REF, i)).convert("RGB")
    s = TEX_PX_PER_CM / PHOTO_PX_PER_CM
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    rgb = np.asarray(im).astype(np.float32) / 255.0
    lin = srgb_to_lin(rgb)
    g = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    h, w = g.shape
    bad = np.zeros_like(g, bool)
    for x0, y0, x1, y1 in EXCLUDE[i]:
        bad[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = True
    sat = rgb.max(-1) - rgb.min(-1)
    bad |= sat > 0.18                                   # blue tape, brass lock
    illum = ndi.gaussian_filter(g, 40)                  # ~3 cm.. large-scale lighting
    bright = g > illum * 1.6                            # white letter, specular hot spots
    bad |= ndi.binary_dilation(bright, iterations=4)
    if i == 4:                                          # door seam: darkest vertical line near x 0.45
        col = ndi.gaussian_filter1d(g.mean(0), 2)
        xs = int(0.40 * w) + int(np.argmin(col[int(0.40 * w):int(0.50 * w)]))
        bad[:, max(0, xs - 8):xs + 8] = True
    bad = ndi.binary_dilation(bad, iterations=6)
    ratio = g / np.maximum(illum, 1e-4)
    dark = np.clip((1.0 - ratio) / 0.35, 0, 1)          # grime: darker than local plate
    grease = np.clip(np.abs(1.0 - ratio) / 0.30, 0, 1)  # roughness change either way
    # fine scratches: thin ridge/valley lines (Hessian, sigma ~1 px = 0.07 cm), elongated only
    hp = g - ndi.gaussian_filter(g, 3)
    sc = np.zeros_like(g)
    for sig in (0.8, 1.4):
        hxx = ndi.gaussian_filter(hp, sig, order=(0, 2))
        hyy = ndi.gaussian_filter(hp, sig, order=(2, 0))
        hxy = ndi.gaussian_filter(hp, sig, order=(1, 1))
        tmp = np.sqrt((hxx - hyy) ** 2 + 4 * hxy ** 2)
        l1 = 0.5 * (hxx + hyy + tmp)
        l2 = 0.5 * (hxx + hyy - tmp)
        big = np.maximum(np.abs(l1), np.abs(l2))
        small = np.minimum(np.abs(l1), np.abs(l2))
        line = np.where(big > 3.0 * small, big - small, 0.0) * sig ** 2
        sc = np.maximum(sc, line)
    sc = sc / max(np.percentile(sc[~bad], 99.7), 1e-6)
    sc = np.clip((sc - 0.35) / 0.65, 0, 1)
    keep = np.clip(1.0 - ndi.gaussian_filter(bad.astype(np.float32), 10) * 1.6, 0, 1)   # feathered exclusion
    def fill(a, sig=30):        # normalized-convolution inpaint: excluded objects become local average grime, not holes
        num = ndi.gaussian_filter(a * keep, sig)
        den = ndi.gaussian_filter(keep, sig)
        return a * keep + (num / np.maximum(den, 1e-3)) * (1 - keep)
    dark, grease = fill(dark), fill(grease)
    sc = sc * keep              # scratches are lines: absence is fine, no fill
    return {"dark": dark, "grease": grease, "scratch": sc, "bad": bad, "g": g}


# --------------------------------------------------------------------------------------------- tiling splats
def window(n):
    t = np.linspace(0, 1, n)
    w = np.minimum(1.0, np.minimum(t, 1 - t) / 0.22)
    w = 0.5 - 0.5 * np.cos(np.pi * np.clip(w, 0, 1))
    return w


def splat_tile(layers, key, shape, n, size_px, combine="screen", amp=(0.6, 1.0), weight_fn=None):
    """Toroidal splat of feathered photo patches -> seamlessly tileable canvas."""
    H, W = shape
    canvas = np.zeros(shape, np.float32)
    for _ in range(n):
        L = layers[rng.integers(len(layers))]
        src = L[key]
        bad = L["bad"]
        ph, pw = min(size_px[0], src.shape[0] - 2), min(size_px[1], src.shape[1] - 2)
        for _try in range(20):
            y0 = rng.integers(0, src.shape[0] - ph)
            x0 = rng.integers(0, src.shape[1] - pw)
            if bad[y0:y0 + ph, x0:x0 + pw].mean() < 0.15:
                break
        p = src[y0:y0 + ph, x0:x0 + pw].copy()
        k = rng.integers(4)
        p = np.rot90(p, k)
        if rng.random() < 0.5:
            p = p[:, ::-1]
        p = p * np.outer(window(p.shape[0]), window(p.shape[1])) * rng.uniform(*amp)
        cy, cx = rng.integers(0, H), rng.integers(0, W)
        if weight_fn is not None:
            p = p * weight_fn(cy, cx, p.shape)
        ys = (np.arange(p.shape[0]) + cy) % H
        xs = (np.arange(p.shape[1]) + cx) % W
        sub = canvas[np.ix_(ys, xs)]
        if combine == "max":
            sub = np.maximum(sub, p)
        else:
            sub = 1 - (1 - sub) * (1 - p)
        canvas[np.ix_(ys, xs)] = sub
    return canvas


def tile_check(a):
    """Seam metric: mean |edge difference| across the wrap vs across an interior line (both ~equal if tileable)."""
    du = np.abs(np.diff(a, axis=1)).mean(0)
    dv = np.abs(np.diff(a, axis=0)).mean(1)
    return {"u_wrap": round(float(np.abs(a[:, 0] - a[:, -1]).mean()), 5),
            "u_interior_mean_p99": [round(float(du.mean()), 5), round(float(np.percentile(du, 99)), 5)],
            "v_wrap": round(float(np.abs(a[0, :] - a[-1, :]).mean()), 5),
            "v_interior_mean_p99": [round(float(dv.mean()), 5), round(float(np.percentile(dv, 99)), 5)],
            "seamless_u": bool(abs(float(np.abs(a[:, 0] - a[:, -1]).mean())) <= float(np.percentile(du, 99.5)) * 1.05),
            "seamless_v": bool(abs(float(np.abs(a[0, :] - a[-1, :]).mean())) <= float(np.percentile(dv, 99.5)) * 1.05)}


def main():
    os.makedirs(OUT + "/masks", exist_ok=True)
    layers = [photo_layers(i) for i in range(1, 5)]
    for i, L in enumerate(layers, 1):
        save(L["dark"], "masks/photo%02d_dark.png" % i, "L")
        save(L["scratch"], "masks/photo%02d_scratch.png" % i, "L")
    report = {"tool": "s3mg_build_textures.py", "seed": SEED, "photo_px_per_cm_inferred": PHOTO_PX_PER_CM,
              "tex_px_per_cm": TEX_PX_PER_CM, "outputs": {}}

    # ---- marble tile layers (sparse ambient, 150 cm repeat)
    amb = splat_tile(layers, "grease", (TILE, TILE), 26, (520, 520), amp=(0.25, 0.6))
    amb = ndi.gaussian_filter(amb, 1.2, mode="wrap")
    amb_dark = splat_tile(layers, "dark", (TILE, TILE), 18, (520, 520), amp=(0.2, 0.5))
    scr = splat_tile(layers, "scratch", (TILE, TILE), 60, (600, 600), combine="max", amp=(0.5, 1.0))
    save(amb, "masks/tile_ambient_grease.png", "L")
    save(scr, "masks/tile_scratch.png", "L")

    mrough = np.asarray(Image.open(MARBLE + "Roughness.jpg").convert("L")).astype(np.float32) / 255.0
    mcol = np.asarray(Image.open(MARBLE + "Color.jpg").convert("RGB")).astype(np.float32) / 255.0
    mnor = np.asarray(Image.open(MARBLE + "NormalDX.jpg").convert("RGB")).astype(np.float32) / 255.0
    # target roughness: clean 0.05..0.09 from the marble's own variation, + scratches, + ambient smudge
    mr_n = np.clip((mrough - np.percentile(mrough, 2)) / (np.percentile(mrough, 98) - np.percentile(mrough, 2)), 0, 1)
    r_target = 0.045 + 0.035 * mr_n + 0.12 * scr + 0.24 * amb ** 1.3
    r_target = np.clip(r_target, MIN_R, MAX_R)
    rt = (r_target - MIN_R) / (MAX_R - MIN_R)
    report["outputs"]["T_S3MG_Marble021_RoughGrime.png"] = {
        "path": save(rt, "T_S3MG_Marble021_RoughGrime.png", "L"), "linear": True, "compression": "TC_GRAYSCALE",
        "mi_scalars": {"Min Roughness": MIN_R, "Max Roughness": MAX_R, "RoughnessTextureWeight": 1.0},
        "roughness_pcts_p5_p50_p95_p99": [round(float(v), 3) for v in np.percentile(r_target, [5, 50, 95, 99])],
        "tile": tile_check(rt)}
    live_eff = LIVE_MIN_R + (LIVE_MAX_R - LIVE_MIN_R) * mrough
    report["live_effective_roughness_p5_p50_p95"] = [round(float(v), 4) for v in np.percentile(live_eff, [5, 50, 95])]

    # normal: marble DX normal + scratch grooves (height = -scratch), small tilt
    h = -ndi.gaussian_filter(scr, 0.7, mode="wrap")
    gx = 0.5 * (np.roll(h, -1, 1) - np.roll(h, 1, 1))
    gy = 0.5 * (np.roll(h, -1, 0) - np.roll(h, 1, 0))
    k = 2.2
    n = np.stack([mnor[..., 0] * 2 - 1, mnor[..., 1] * 2 - 1, mnor[..., 2] * 2 - 1], -1)
    n[..., 0] += -gx * k
    n[..., 1] += gy * k          # DirectX: +Y down in image -> green flips vs OpenGL; height gradient in image rows
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    report["outputs"]["T_S3MG_Marble021_NormalDX_Scratch.png"] = {
        "path": save(n * 0.5 + 0.5, "T_S3MG_Marble021_NormalDX_Scratch.png", "RGB"), "linear": True,
        "compression": "TC_NORMALMAP", "flip_green": False, "tile": tile_check(n[..., 0])}

    col_lin = srgb_to_lin(mcol) * (1.0 - 0.07 * amb_dark[..., None])
    report["outputs"]["T_S3MG_Marble021_Color_Grime_sRGB.png"] = {
        "path": save(lin_to_srgb(col_lin), "T_S3MG_Marble021_Color_Grime_sRGB.png", "RGB"), "linear": False,
        "compression": "TC_DEFAULT", "max_darkening": 0.07}

    # ---- grease atlas from the live print atlas alpha (same UV layout, half resolution)
    at = Image.open(ATLAS)
    alpha = np.asarray(at.getchannel("A")).astype(np.float32) / 255.0
    core = ndi.gaussian_filter(alpha, 3.0)                 # feather ~0.25 cm at 12.2 px/cm
    bloom = ndi.gaussian_filter(alpha, 14.0)               # soft dark bloom ~1.1 cm
    gtex = splat_tile(layers, "grease", alpha.shape, 90, (700, 700), amp=(0.6, 1.0))
    breakup = 0.55 + 0.45 * ndi.gaussian_filter(gtex, 2.0)
    # partial fingers: low-frequency dropout so some prints lose a finger / heel
    drop = ndi.gaussian_filter(rng.random((alpha.shape[0] // 32, alpha.shape[1] // 32)).astype(np.float32), 1.0)
    drop = np.kron(drop, np.ones((32, 32), np.float32))[:alpha.shape[0], :alpha.shape[1]]
    drop = ndi.gaussian_filter(drop, 12)
    drop = np.clip((drop - drop.min()) / (drop.max() - drop.min()) * 1.6 - 0.15, 0, 1)
    grease_op = np.clip((0.85 * core + 0.35 * bloom) * breakup * (0.35 + 0.65 * drop), 0, 1)
    height = ndi.gaussian_filter(alpha * breakup, 4.0)
    albedo_w = np.clip(core ** 1.5 * 0.6 * breakup, 0, 1)
    ga = np.stack([grease_op, height, albedo_w], -1)
    ga = np.asarray(Image.fromarray((ga * 255).astype(np.uint8), "RGB").resize((2048, 2048), Image.LANCZOS))
    report["outputs"]["T_S3MG_GreaseAtlas.png"] = {
        "path": os.path.join(OUT, "T_S3MG_GreaseAtlas.png"), "linear": True, "compression": "TC_MASKS",
        "uv_layout": "identical normalized uv_rect to atlas_job24d/atlas.json (4096 -> 2048 resample)",
        "channels": {"R": "grease opacity (feathered)", "G": "smear height for normal", "B": "albedo weight (faint)"}}
    Image.fromarray(ga, "RGB").save(report["outputs"]["T_S3MG_GreaseAtlas.png"]["path"])

    # ---- low-wall grime band (U tileable, V = height: row 0 = TOP of band (200 cm), last row = floor)
    BH, BW = 512, 2048      # 2.56 px/cm: band 800 cm long x 200 cm high
    zcm = np.linspace(200, 0, BH)[:, None]
    grad = np.clip(np.exp(-zcm / 35.0) * 0.9 + 0.35 * np.exp(-((zcm - 110) / 28.0) ** 2), 0, 1)  # floor kick + hand height
    small = [{k_: (ndi.zoom(L[k_], 0.19, order=1) if k_ != "bad" else ndi.zoom(L[k_].astype(np.float32), 0.19, order=0) > 0.5)
              for k_ in ("dark", "grease", "bad")} for L in layers]
    clusters = splat_tile(small, "dark", (BH, BW), 40, (220, 220), amp=(0.5, 1.0))
    gre = splat_tile(small, "grease", (BH, BW), 40, (220, 220), amp=(0.5, 1.0))
    band_op = np.clip(grad * (0.35 + 0.9 * clusters), 0, 1)
    band = np.stack([band_op, np.clip(0.25 + 0.45 * gre, 0, 1), np.clip(band_op * 0.5, 0, 1)], -1)
    report["outputs"]["T_S3MG_GrimeBand.png"] = {
        "path": save(band, "T_S3MG_GrimeBand.png", "RGB"), "linear": True, "compression": "TC_MASKS",
        "size": [BW, BH], "covers_cm": [800, 200], "tileable": "U only", "tile": tile_check(band_op)}

    # ---- seam / corner strip (V tileable; dense at u=0 = the seam/corner, fading over 60 cm)
    SH, SW = 2048, 512      # 512 px = 100 cm wide, 2048 = 400 cm tall
    ucm = np.linspace(0, 100, SW)[None, :]
    fall = np.exp(-ucm / 22.0)
    sc_cl = splat_tile(small, "dark", (SH, SW), 50, (220, 220), amp=(0.5, 1.0))
    seam_op = np.clip(fall * (0.3 + 0.9 * sc_cl), 0, 1)
    seam = np.stack([seam_op, np.clip(0.3 + 0.4 * sc_cl, 0, 1), seam_op * 0.5], -1)
    report["outputs"]["T_S3MG_SeamStrip.png"] = {
        "path": save(seam, "T_S3MG_SeamStrip.png", "RGB"), "linear": True, "compression": "TC_MASKS",
        "size": [SW, SH], "covers_cm": [100, 400], "tileable": "V only"}

    for k_, v in report["outputs"].items():
        v["sha256"] = hashlib.sha256(open(v["path"], "rb").read()).hexdigest()
    json.dump(report, open(OUT + "/textures_report.json", "w"), indent=1)
    print(json.dumps(report, indent=1)[:3000])


if __name__ == "__main__":
    main()
