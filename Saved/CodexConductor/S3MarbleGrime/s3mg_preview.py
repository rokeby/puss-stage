"""S3 marble grime prep (OFFLINE, 7 Oct): fake-spec camera renders of the S3 main camera.

NOT a renderer of record. A calibrated sketch to compare variants against the live still:
  - camera pose = PSTILLS-S3-20261007-173228-floathold still 0 (geometry.json main_pose)
  - non-wall pixels are the live still itself; wall pixels (R wall, y = 160999) are re-shaded
  - diffuse:  albedo * Kd     (Kd calibrated so the BASELINE render matches the still's clean wall)
  - specular: F_schlick(F0 = 0.08 * Specular) * reflected radiance, where reflected radiance is
      A/B: a uniform environment (the room as reflected today: inferred ~ the wall's own luminance)
      C:   uniform env + the three mirror strips (geometry.json), blurred in wall space by
           sigma_cm = 2 * alpha * D_lightwall / magnification, alpha = roughness^2 (GGX-like width)
  - tonemap: Narkowicz ACES fit + sRGB, exposure k calibrated once on the baseline
Variants: baseline (live decals: atlas colour at alpha, atlas roughness), A, B, C (see report).
Writes DerivedAssets/S3Marble/Grime_20261007/preview_*.png, sheet_ABC.png, preview_report.json
"""
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = "E:/PussStage"
G = ROOT + "/DerivedAssets/S3Marble/Grime_20261007"
STILL = ROOT + "/Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-173228-floathold/00_f300.png"
MARBLE = ROOT + "/DerivedAssets/S3Marble/Marble021/Marble021_2K-JPG_"
HP = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/"
RES = (1600, 900)
PXCM = 2.0                                   # wall-space map resolution
XR = (14150.0, 15700.0)
ZR = (-5.0, 330.0)
LIVE = {"Brightness": 1.15, "Saturation": 0.8, "MinR": 0.05, "MaxR": 0.12, "Specular": 0.7}   # record "look"
REPEAT = 150.0
U_OFF = 317.0                                 # R0 UOffsetCm (s3_marble_tiling_record.json plan)


def s2l(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def l2s(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def aces(x):
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


def load(p, mode=None):
    im = Image.open(p)
    if mode:
        im = im.convert(mode)
    return np.asarray(im).astype(np.float32) / 255.0


def cam_rays(pose):
    y, p = math.radians(pose["rot"]["yaw"]), math.radians(pose["rot"]["pitch"])
    fwd = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    right = np.array([-math.sin(y), math.cos(y), 0.0])
    up = np.cross(right, fwd)
    up /= np.linalg.norm(up)
    if up[2] < 0:
        up = -up
    th = math.tan(math.radians(pose["fov_deg"]) / 2)
    tv = th / pose["aspect"]
    px, py = np.meshgrid(np.arange(RES[0]) + 0.5, np.arange(RES[1]) + 0.5)
    sx = (2 * px / RES[0] - 1) * th
    sy = (1 - 2 * py / RES[1]) * tv
    d = fwd[None, None] + sx[..., None] * right + sy[..., None] * up
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def wall_grid():
    xs = np.arange(XR[0], XR[1], 1 / PXCM)
    zs = np.arange(ZR[1], ZR[0], -1 / PXCM)         # row 0 = top
    X, Z = np.meshgrid(xs, zs)
    return X, Z


def tile_sample(img, X, Z):
    """Planar tiling at REPEAT cm (object frame approximated by world x/z + U offset); breakup blend omitted."""
    h, w = img.shape[:2]
    u = ((X - XR[0] + U_OFF) / REPEAT) % 1.0
    v = ((-Z) / REPEAT) % 1.0
    iy = (v * h).astype(int) % h
    ix = (u * w).astype(int) % w
    return img[iy, ix]


def raster_decals(decals, X, Z, wall_y, atlas, rough_atlas, elements, grease=None):
    H, W = X.shape
    col = np.zeros((H, W, 3), np.float32)
    a_col = np.zeros((H, W), np.float32)
    rgh = np.zeros((H, W), np.float32)
    g_op = np.zeros((H, W), np.float32)
    g_ht = np.zeros((H, W), np.float32)
    g_alb = np.zeros((H, W), np.float32)
    ah, aw = atlas.shape[:2]
    for d in decals:
        el = elements[d["element_id"]]
        U0, V0, US, VS = el["uv_rect"]
        hy, hz = d["decal_size"][1], d["decal_size"][2]
        ext = math.hypot(hy, hz)
        cx, cz = d["location"][0], d["location"][2]
        x0 = int(max(0, (cx - ext - XR[0]) * PXCM)); x1 = int(min(W, (cx + ext - XR[0]) * PXCM) + 1)
        z0 = int(max(0, (ZR[1] - (cz + ext)) * PXCM)); z1 = int(min(H, (ZR[1] - (cz - ext)) * PXCM) + 1)
        if x1 <= x0 or z1 <= z0:
            continue
        sx, sz = X[z0:z1, x0:x1] - cx, Z[z0:z1, x0:x1] - cz
        ay, az = np.array(d["axes"]["y"]), np.array(d["axes"]["z"])
        ly = sx * ay[0] + sz * ay[2]
        lz = sx * az[0] + sz * az[2]
        u = 0.5 + lz / (2 * hz)
        v = 0.5 + ly / (2 * hy)
        inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
        if d.get("flip"):
            u = 1 - u
        au = np.clip(U0 + u * US, 0, 1 - 1e-6)
        av = np.clip(V0 + v * VS, 0, 1 - 1e-6)
        iy, ix = (av * ah).astype(int), (au * aw).astype(int)
        smp = atlas[iy, ix]
        a = smp[..., 3] * inside
        sl = (slice(z0, z1), slice(x0, x1))
        # "over" compositing in sort order (translucent DBuffer decals blend one over another)
        col[sl] = col[sl] * (1 - a[..., None]) + s2l(smp[..., :3]) * a[..., None]
        a_col[sl] = a_col[sl] * (1 - a) + a
        rr = rough_atlas[(av * rough_atlas.shape[0]).astype(int), (au * rough_atlas.shape[1]).astype(int)]
        rgh[sl] = rgh[sl] * (1 - a) + rr * a
        if grease is not None:
            gs = grease[(av * grease.shape[0]).astype(int), (au * grease.shape[1]).astype(int)] * inside[..., None]
            g_op[sl] = 1 - (1 - g_op[sl]) * (1 - gs[..., 0])
            g_ht[sl] = np.maximum(g_ht[sl], gs[..., 1])
            g_alb[sl] = np.maximum(g_alb[sl], gs[..., 2])
    # un-premultiply the composite colour
    col = np.where(a_col[..., None] > 1e-4, col / np.maximum(a_col[..., None], 1e-4), 0)
    rgh = np.where(a_col > 1e-4, rgh / np.maximum(a_col, 1e-4), 0)
    return col, a_col, rgh, g_op, g_ht, g_alb


def blur_stack(mask, sigmas_cm):
    return [ndi.gaussian_filter(mask, max(s * PXCM, 0.3)) for s in sigmas_cm]


def sample_stack(stack, sigmas_cm, sig):
    ls = np.log(np.array(sigmas_cm))
    t = np.clip(np.interp(np.log(np.maximum(sig, sigmas_cm[0])), ls, np.arange(len(ls))), 0, len(ls) - 1)
    i0 = np.floor(t).astype(int)
    i1 = np.minimum(i0 + 1, len(ls) - 1)
    f = t - i0
    S = np.stack(stack, 0)
    a = np.take_along_axis(S, i0[None], 0)[0]
    b = np.take_along_axis(S, i1[None], 0)[0]
    return a * (1 - f) + b * f


def main():
    geo = json.load(open(G + "/geometry.json"))
    pose = geo["main_pose"]
    wall_y = geo["wall"]["plane_y_cm"]
    C = np.array(pose["loc"], float)
    still = load(STILL, "RGB")
    d = cam_rays(pose)
    tw = (wall_y - C[1]) / d[..., 1]
    Pw = C + tw[..., None] * d
    tf = np.where(d[..., 2] < 0, (geo["wall"]["floor_z_cm"] - C[2]) / np.minimum(d[..., 2], -1e-9), np.inf)
    wall_px = (tw > 0) & (tw < tf) & (Pw[..., 2] >= ZR[0]) & (Pw[..., 2] < ZR[1]) & \
              (Pw[..., 0] > XR[0]) & (Pw[..., 0] < XR[1])
    # occluders in front of the wall (the grey cut-out flats at frame left): bluish-grey, not brown prints
    lum = still @ np.array([0.2126, 0.7152, 0.0722])
    xg = np.arange(RES[0])[None, :].repeat(RES[1], 0)
    yg = np.arange(RES[1])[:, None].repeat(RES[0], 1)
    occl = wall_px & (xg < 520) & (yg > 200) & (lum < 0.50)    # measured: flats lum 0.31-0.46, clean wall ~0.59
    occl = ndi.binary_dilation(ndi.binary_opening(occl, iterations=2), iterations=2)
    wall_px &= ~occl

    # wall-space maps
    X, Z = wall_grid()
    mcol = s2l(load(MARBLE + "Color.jpg", "RGB"))
    mrgh = load(MARBLE + "Roughness.jpg", "L")
    ncol = s2l(load(G + "/T_S3MG_Marble021_Color_Grime_sRGB.png", "RGB"))
    nrt = load(G + "/T_S3MG_Marble021_RoughGrime.png", "L")
    band = load(G + "/T_S3MG_GrimeBand.png", "RGB")
    atlas = load(HP + "T_S03_HandPrints_BaseColor.png", "RGBA")
    ratlas = load(HP + "T_S03_HandPrints_Roughness.png", "L")
    grease = load(G + "/T_S3MG_GreaseAtlas.png", "RGB")
    elements = {e["id"]: e for e in json.load(open(HP + "atlas.json"))["elements"]}
    placement = json.load(open(ROOT + "/DerivedAssets/FlatV3/HandPrints/placement_S03.json"))["decals"]
    decs = [x for x in placement if x["wall"] == "R" and XR[0] - 100 < x["location"][0] < XR[1] + 100]
    decs.sort(key=lambda x: x.get("sort_order", 0))
    dcol, da, drg, gop, ght, galb = raster_decals(decs, X, Z, wall_y, atlas, ratlas, elements, grease)

    def marble_albedo(colmap):
        bc = tile_sample(colmap, X, Z)
        lumm = bc @ np.array([0.2126, 0.7152, 0.0722])
        c = (lumm[..., None] + (bc - lumm[..., None]) * LIVE["Saturation"]) * LIVE["Brightness"]
        return np.clip(c, 0, 1)

    alb_live = marble_albedo(mcol)
    r_live = LIVE["MinR"] + (LIVE["MaxR"] - LIVE["MinR"]) * tile_sample(mrgh, X, Z)
    alb_new = marble_albedo(ncol)
    r_new = 0.04 + 0.56 * tile_sample(nrt, X, Z)

    variants = {}
    # baseline = live: v3 decals OpacityGain 1, tint 1
    variants["baseline"] = (alb_live * (1 - da[..., None]) + dcol * da[..., None], r_live * (1 - da) + drg * da)
    # A: new marble tile + grease decal (roughness/normal only) + v3 colour at OpacityGain 0.15
    a15 = np.clip(da * 0.22, 0, 1)
    albA = alb_new * (1 - a15[..., None]) + dcol * a15[..., None]
    albA = albA * (1 - 0.15 * galb[..., None])
    rA = r_new * (1 - a15) + drg * a15
    rA = rA * (1 - gop) + (0.30 + 0.25 * ght) * gop
    variants["A"] = (albA, rA)
    # B: A + low-wall band decal (800 cm tiled, z 0..200)
    bu = ((X - XR[0]) / 800.0) % 1.0
    bv = np.clip((200 - Z) / 200.0, 0, 1)
    inb = (Z >= -5) & (Z <= 200)
    bs = band[(bv * (band.shape[0] - 1)).astype(int), (bu * band.shape[1]).astype(int)] * inb[..., None]
    bop = bs[..., 0] * 0.85
    albB = albA * (1 - 0.30 * bs[..., 2:3])
    rB = rA * (1 - bop) + (0.2 + 0.5 * bs[..., 1]) * bop
    variants["B"] = (albB, rB)
    variants["C"] = variants["A"]

    # geometry per wall pixel
    P = np.stack([X, np.full_like(X, wall_y), Z], -1)
    v_in = P - C
    dist = np.linalg.norm(v_in, axis=-1)
    cos_t = np.abs(v_in[..., 1]) / dist
    F0 = 0.08 * LIVE["Specular"]
    F = F0 + (1 - F0) * (1 - cos_t) ** 5
    # mirror strip mask on the wall (crisp), C only
    ml = geo["mirror_light"]
    ly = ml["strips_proposal"][0]["location_cm"][1]
    r = v_in.copy()
    r[..., 1] *= -1
    s = (ly - wall_y) / r[..., 1]
    Q = P + s[..., None] * r
    strip = np.zeros_like(X)
    for st in ml["strips_proposal"]:
        lx, lz = st["location_cm"][0], st["location_cm"][2]
        wx, hz_ = st["source_width_cm"] / 2, st["source_height_cm"] / 2
        strip = np.maximum(strip, ((np.abs(Q[..., 0] - lx) <= wx) & (np.abs(Q[..., 2] - lz) <= hz_)).astype(np.float32))
    sig_k = 2 * ml["dist_light_to_wall_cm"] / ml["magnification_wall_to_light"]
    sigmas = [0.5, 1.5, 4, 10, 25, 60, 150, 400]
    stack = blur_stack(strip, sigmas)

    # calibration on baseline: clean wall in the still (wall pixels, no decal, rows < junction)
    def to_screen(m):
        xi = np.clip(((Pw[..., 0] - XR[0]) * PXCM).astype(int), 0, X.shape[1] - 1)
        zi = np.clip(((ZR[1] - Pw[..., 2]) * PXCM).astype(int), 0, X.shape[0] - 1)
        return m[zi, xi]
    clean = wall_px & (to_screen(da) < 0.02)
    target = np.median(still[clean], axis=0)                       # display sRGB of the clean wall
    env = 1.0                                                      # uniform env radiance, in units of Kd (inferred)

    def shade(alb, rgh, with_strip, Ls=0.0):
        diffuse = alb                                              # * Kd (Kd folded into exposure k)
        spec_env = F * env * np.mean(alb_live)                     # uniform room reflection ~ its own luminance
        out = diffuse + spec_env[..., None]
        if with_strip:
            alpha = np.maximum(rgh, 0.02) ** 2
            sig = sig_k * alpha
            hl = sample_stack(stack, sigmas, sig)
            out = out + (F * Ls * hl)[..., None]
        return out

    base_lin = shade(*variants["baseline"], False)
    base_scr = to_screen(base_lin)
    # exposure: match the median clean-wall display value
    # per-channel exposure (white balance of the warm S3 light folded in)
    kk = []
    for ch in range(3):
        tgt_l = s2l(target[ch])
        med = np.median(base_scr[clean][:, ch])
        lo, hi = 0.01, 100.0
        for _ in range(60):
            k_ = math.sqrt(lo * hi)
            if s2l(l2s(aces(k_ * med))) < tgt_l:
                lo = k_
            else:
                hi = k_
        kk.append(k_)
    k = np.array(kk)
    rep = {"tool": "s3mg_preview.py", "exposure_k_rgb": [round(float(v), 4) for v in k], "clean_wall_target_srgb": target.round(4).tolist(),
           "visible_decals_rendered": len(decs), "sigma_cm_per_alpha": round(sig_k, 1), "variants": {}}
    Ls = 18.0 / F0 * 0.056   # strip radiance in Kd units: clean highlight ~ +18x the diffuse (pre-tonemap)
    rep["strip_radiance_rel"] = Ls
    imgs = {}
    for name in ("baseline", "A", "B", "C"):
        alb, rgh = variants[name]
        lin = shade(alb, rgh, name == "C", Ls)
        disp = l2s(aces(k * to_screen(lin)))
        out = still.copy()
        out[wall_px] = disp[wall_px]
        imgs[name] = out
        Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(G + "/preview_%s.png" % name)
        w = wall_px
        rep["variants"][name] = {"wall_mean_srgb": round(float(out[w].mean()), 4),
                                 "wall_p1_p99_luma": [round(float(v), 4) for v in np.percentile(out[w].mean(-1), [1, 99])],
                                 "decal_px_mean_rough": round(float(to_screen(rgh)[w & (to_screen(da) > 0.3)].mean()), 3),
                                 "clean_px_mean_rough": round(float(to_screen(rgh)[clean].mean()), 3)}
    # baseline fidelity vs the still (wall pixels only)
    rep["baseline_vs_still_mean_abs_srgb"] = round(float(np.abs(imgs["baseline"][wall_px] - still[wall_px]).mean()), 4)
    # contact sheet: still | baseline / A | B / C | C crop
    th = (800, 450)
    sheet = Image.new("RGB", (th[0] * 2, th[1] * 3), (0, 0, 0))
    tiles = [("still (live, floathold)", still), ("baseline (re-render)", imgs["baseline"]), ("A", imgs["A"]),
             ("B", imgs["B"]), ("C", imgs["C"]), ("C crop 2x", None)]
    from PIL import ImageDraw
    for i, (lab, im) in enumerate(tiles):
        if im is None:
            crop = Image.fromarray((imgs["C"][0:450, 500:1300] * 255).astype(np.uint8))
            t = crop.resize(th)
        else:
            t = Image.fromarray((im * 255 + 0.5).astype(np.uint8)).resize(th)
        ImageDraw.Draw(t).text((10, 10), lab, fill=(255, 0, 0))
        sheet.paste(t, ((i % 2) * th[0], (i // 2) * th[1]))
    sheet.save(G + "/sheet_ABC.png")
    Image.fromarray((wall_px * 255).astype(np.uint8)).save(G + "/masks/preview_wall_mask.png")
    json.dump(rep, open(G + "/preview_report.json", "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
