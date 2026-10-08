"""Grease v2 builder (OFFLINE, numpy/scipy/PIL).  Gary 8 Oct: the highlight belongs at the EDGES in the direction of
the smear, not at the thickest part.

Inputs (read-only):
  DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png        live GreaseMask source (sha pinned)
  DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_Normal.png  live PrintNormal source (sha pinned)
  DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_BaseColor.png  4096 print alpha (sha pinned)
  DerivedAssets/FlatV3/HandPrints/atlas_job24d/atlas.json             per-element atlas_rect_px / width_cm
Outputs (DerivedAssets/S3Marble/GreaseV2_20261008/):
  T_HP_S03_GreaseAtlas_v2.png   2048 RGB8 linear (TC_MASKS): R = live R byte-identical, G = new roughness mask
                                (decoded 0.30 + 0.25 G: LOW on ridges/streaks, HIGH in the thin centre), B = live B
  T_HP_S03_PrintNormal_v2.png   1024 RGB8 tangent normal, same encoding as the live PrintNormal (DirectX green,
                                x = -dh/du, y = -dh/dv with image v DOWN, z = 1 before normalising; no baked U flip)
  gv2_fields.npz                float fields for the validator/preview (2048: G_new, ridge, streak, masks...)
  gv2_directions.json           per-element smear direction, confidence, skew, method
  gv2_build_report.json
"""
import hashlib
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gv2_lib as L  # noqa: E402

ROOT = "E:/PussStage"
OUT = ROOT + "/DerivedAssets/S3Marble/GreaseV2_20261008"
LIVE_ATLAS = ROOT + "/DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png"
LIVE_ATLAS_SHA = "8f85307b26db11725f31c8427381af46b5b4ea5507f6f50473d052333a553599"
LIVE_NORMAL = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_Normal.png"
LIVE_NORMAL_SHA = "d4d88af04c6efe564af2f7f248d77bd7028a6d8c9b7f3606fec0c9eca92dbf3b"
BASE = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_BaseColor.png"
BASE_SHA = "052a454c42d757be9c5832e65cd12627a53a12a67a3896285b7edcfcd46557cd"
ATLAS_JSON = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/atlas.json"
SEED = 20261008

# ---- physical parameters (mm; converted with each element's own px/cm = atlas_rect_px w / width_cm at 4096)
BODY_SIGMA_MM = 2.0          # smoothing that merges sub-2 mm gaps before the body threshold
BODY_THRESH = 0.10           # on the smoothed 4096 alpha
RIM_CENTER_MM = 2.5          # ridge crest this far inside the body edge
RIM_WIDTH_MM = 1.8           # crest sigma (inner flank); outer flank 0.6x
END_WIDEN = 0.6              # bow wave: ends get a crest (1 + END_WIDEN) wider and pushed further in
DISH_DEPTH = 0.12            # centre dished by 12 % of the crest height
DISH_START_MM = 6.0
STREAK_PERIOD_MM = (4.5, 7.0)   # brief asked 1-3 mm: below the 2048 Nyquist (3.3 mm) -> finest resolvable band
STREAK_HEIGHT = 0.30         # streak height amplitude (x conf) relative to the crest
CONF_LOW = 0.35              # below: isotropic rim, no streaks
# ---- G encoding targets (roughness = 0.30 + 0.25 G)
G_GLOSS = 0.06               # crest
G_SATIN = 0.62               # thin centre base (+ dish and breakup variation)
G_HALO = 0.55                # thin film outside the body where R > 0


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rgb(p):
    return np.asarray(Image.open(p).convert("RGB"))


def estimate_direction(a, kind):
    sa, el, skew = L.shape_pca(a)
    body = ndi.gaussian_filter(a, 3) > 0.1
    ta, coh = L.structure_tensor_angle(a, body, sigma_d=1.5, hp_sigma=6)
    conf_t = float(L.smoothstep(0.40, 0.65, coh))
    conf_s = float(L.smoothstep(0.75, 0.95, el))
    diff = L.axial_diff_deg(ta, sa)
    both = conf_t > 0 and conf_s > 0
    agree = 1.0 - 0.5 * math.sin(math.radians(diff)) ** 2 if both else 1.0
    wt, ws = conf_t + 1e-6, conf_s + 1e-6
    c2 = wt * math.cos(2 * ta) + ws * math.cos(2 * sa)
    s2 = wt * math.sin(2 * ta) + ws * math.sin(2 * sa)
    theta = (0.5 * math.atan2(s2, c2)) % math.pi if (conf_t + conf_s) > 0 else ta
    conf = max(conf_t, conf_s) * agree
    return {"theta_deg": round(math.degrees(theta), 2), "conf": round(conf, 3), "texture_angle_deg": round(math.degrees(ta), 2),
            "texture_coherence": round(coh, 3), "shape_angle_deg": round(math.degrees(sa), 2), "elongation": round(el, 3),
            "skew_along_axis": round(skew, 3), "shape_texture_diff_deg": round(diff, 1),
            "tail_towards": ("+axis" if skew > 0 else "-axis"), "low_confidence": conf < CONF_LOW, "kind": kind}


def build(alpha4096=None, elements=None, seed=SEED, profile="ridge"):
    """Returns the float fields at 4096.  alpha4096/elements injectable for the harness (synthetic blobs)."""
    A = alpha4096.astype(np.float32)
    n = A.shape[0]
    rng_master = np.random.default_rng(seed)
    seeds = rng_master.integers(0, 2 ** 31, len(elements))
    height = np.zeros_like(A)
    gloss = np.zeros_like(A)            # 0..1 glossiness target before the G mapping
    satin_mod = np.zeros_like(A)        # dish depth 0..1
    body_all = np.zeros(A.shape, bool)
    dist_all = np.full(A.shape, -1e3, np.float32)
    endness = np.zeros_like(A)          # c2 = cos^2(boundary normal, smear axis), for the validator
    rimband = np.zeros(A.shape, bool)
    centre = np.zeros(A.shape, bool)
    streak_all = np.zeros_like(A)
    owner = np.full(A.shape, -1, np.int16)
    dirs = {}
    for idx, e in enumerate(elements):
        x, y, w, h = e["atlas_rect_px"]
        pxmm = (w / e["width_cm"]) / 10.0
        a = A[y:y + h, x:x + w]
        d = estimate_direction(a, e.get("kind", "print"))
        d["px_per_cm_4096"] = round(pxmm * 10, 4)
        dirs[e["id"]] = d
        theta, conf = math.radians(d["theta_deg"]), d["conf"]
        if d["low_confidence"]:
            conf_eff = 0.0
        else:
            conf_eff = conf
        body = ndi.gaussian_filter(a, BODY_SIGMA_MM * pxmm) > BODY_THRESH
        body = ndi.binary_opening(body, iterations=1)
        lab, nl = ndi.label(body)
        if nl:
            sizes = ndi.sum(body, lab, range(1, nl + 1))
            keep = np.zeros(nl + 1, bool)
            keep[1:] = sizes >= (3.0 * pxmm) ** 2
            body = keep[lab]
        din = ndi.distance_transform_edt(body).astype(np.float32)
        dout = ndi.distance_transform_edt(~body).astype(np.float32)
        dist = np.where(body, din - 0.5, -(dout - 0.5))
        ds = ndi.gaussian_filter(dist, 1.5 * pxmm)
        gy, gx = np.gradient(ds)
        gm = np.maximum(np.hypot(gx, gy), 1e-6)
        nx, ny = -gx / gm, -gy / gm                 # outward normal
        wgt, c2 = L.edge_orientation_weight(nx, ny, theta, conf_eff)
        widen = 1.0 + END_WIDEN * conf_eff * c2
        rc, rw = RIM_CENTER_MM * pxmm * widen, RIM_WIDTH_MM * pxmm * widen
        thick = 0.6 + 0.4 * L.smoothstep(0.10, 0.50, ndi.gaussian_filter(a, 1.5 * pxmm))
        dish = L.smoothstep(DISH_START_MM * pxmm, DISH_START_MM * pxmm * 2.5, dist)
        if profile == "ridge":
            crest = np.exp(-0.5 * ((dist - rc) / np.where(dist < rc, 0.6 * rw, rw)) ** 2)
            rim = crest * wgt * thick
            hgt = rim - DISH_DEPTH * dish
        else:                                         # NEGATIVE control: dome, thickest in the centre
            hgt = L.dome_profile(dist, 10.0 * pxmm) * thick
            rim = np.zeros_like(hgt)
        if conf_eff > 0 and profile == "ridge":
            st = L.oriented_streaks(a.shape, theta, STREAK_PERIOD_MM[0] * pxmm, STREAK_PERIOD_MM[1] * pxmm,
                                    np.random.default_rng(int(seeds[idx])))
            lf = L.oriented_streaks(a.shape, theta, 15 * pxmm, 40 * pxmm, np.random.default_rng(int(seeds[idx]) + 1),
                                    ang_spread_deg=60)
            mod = np.clip(0.55 + 0.30 * lf, 0.1, 1.0)
            inside = L.smoothstep(0.0, rc, dist)
            st = st * mod * inside * conf_eff
        else:
            st = np.zeros_like(a)
        hgt = hgt + STREAK_HEIGHT * 0.5 * st
        if profile == "ridge":
            gl = np.clip(np.maximum(rim, 0) + 0.45 * np.clip(st, 0, None), 0, 1)
        else:                                          # dome: glossy at the thin edge, rough at the thick centre
            gl = 1.0 - np.clip(hgt, 0, 1)
        win = (slice(y, y + h), slice(x, x + w))
        height[win] = np.where(dist > -6 * pxmm, hgt, 0)
        gloss[win] = np.where(body | (dist > -4 * pxmm), gl, 0)
        satin_mod[win] = dish
        body_all[win] |= body
        dist_all[win] = dist
        endness[win] = c2
        rimband[win] = body & (np.abs(dist - rc) <= 0.8 * rw)
        centre[win] = body & (dist >= rc + 3.0 * rw) & (dist >= DISH_START_MM * pxmm)
        streak_all[win] = st
        owner[win] = idx
    return {"height": height, "gloss": gloss, "dish": satin_mod, "body": body_all, "dist": dist_all,
            "endness": endness, "rimband": rimband, "centre": centre, "streak": streak_all, "owner": owner,
            "dirs": dirs}


def down2(a):
    """Area (2x2 mean) downsample."""
    return a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2).mean((1, 3))


def g_field(f, breakup2048):
    gloss = np.clip(down2(f["gloss"]), 0, 1)
    dish = down2(f["dish"])
    body = down2(f["body"].astype(np.float32))
    bvar = (breakup2048 - 0.775) / 0.225               # breakup in [0.55,1] -> [-1,1]
    satin = G_SATIN + 0.10 * dish + 0.08 * bvar
    inside = np.clip(body, 0, 1)
    base = inside * satin + (1 - inside) * G_HALO
    return np.clip(base * (1 - gloss) + G_GLOSS * gloss, 0, 1)


def normal_from_height(h4096, scale):
    hh = np.asarray(Image.fromarray(h4096.astype(np.float32), mode="F").resize((1024, 1024), Image.BOX),
                    dtype=np.float64)
    hh = ndi.gaussian_filter(hh, 0.6)
    dy, dx = np.gradient(hh * scale)
    nrm = np.stack([-dx, -dy, np.ones_like(hh)], -1)          # same convention as build_handprint_atlas.py:503-507
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    return nrm


def compose(live, Gn):
    """R and B copied byte-for-byte; G = new field where R >= 2/255, blended over 1/255, live G where R == 0."""
    R, Gold, B = live[..., 0], live[..., 1], live[..., 2]
    b = np.clip(R.astype(np.float32) / 2.0, 0, 1)
    G = to_u8(Gn * b + (Gold / 255.0) * (1 - b))
    G = np.where(R == 0, Gold, G)
    return np.stack([R, G, B], -1)


def to_u8(x):
    return np.clip(np.floor(np.clip(x, 0, 1) * 255.0 + 0.5), 0, 255).astype(np.uint8)


def main():
    os.makedirs(OUT, exist_ok=True)
    for p, s in ((LIVE_ATLAS, LIVE_ATLAS_SHA), (LIVE_NORMAL, LIVE_NORMAL_SHA), (BASE, BASE_SHA)):
        assert sha(p) == s, "SOURCE_SHA_MISMATCH|" + p
    meta = json.load(open(ATLAS_JSON))
    live = rgb(LIVE_ATLAS)
    livn = rgb(LIVE_NORMAL)
    alpha = np.asarray(Image.open(BASE).getchannel("A")).astype(np.float32) / 255.0
    fields = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "repro_fields.npz"))
    assert np.array_equal(fields["alpha"], alpha), "REPRO_ALPHA_MISMATCH"
    breakup2048 = down2(fields["breakup"])
    f = build(alpha, meta["elements"])
    Gn = g_field(f, breakup2048)
    out = compose(live, Gn)
    assert L.r_identical(live, out) and np.array_equal(out[..., 2], live[..., 2]), "R_OR_B_CHANGED"
    pa = os.path.join(OUT, "T_HP_S03_GreaseAtlas_v2.png")
    Image.fromarray(out, "RGB").save(pa, format="PNG", optimize=False, compress_level=6)

    # normal: calibrate the slope so p99 |xy| inside covered texels matches the live map (same perceived strength)
    lvxy = np.hypot(livn[..., 0] / 255.0 * 2 - 1, livn[..., 1] / 255.0 * 2 - 1)
    cov1024 = np.asarray(Image.fromarray(alpha, "F").resize((1024, 1024), Image.BOX)) > 0.02
    live_p99 = float(np.percentile(lvxy[cov1024], 99))
    trial = normal_from_height(f["height"], 1.0)
    t99 = float(np.percentile(np.hypot(trial[..., 0], trial[..., 1])[cov1024], 99))
    tan_live, tan_t = math.tan(math.asin(min(live_p99, 0.999))), math.tan(math.asin(min(t99, 0.999)))
    scale = tan_live / max(tan_t, 1e-6)
    nrm = normal_from_height(f["height"], scale)
    pn = os.path.join(OUT, "T_HP_S03_PrintNormal_v2.png")
    Image.fromarray(to_u8(nrm * 0.5 + 0.5), "RGB").save(pn, format="PNG", optimize=False, compress_level=6)

    np.savez_compressed(os.path.join(OUT, "gv2_fields.npz"),
                        G_new=Gn.astype(np.float32), height1024=np.asarray(Image.fromarray(f["height"], "F").resize(
                            (1024, 1024), Image.BOX)),
                        height2048=down2(f["height"]).astype(np.float32), streak2048=down2(f["streak"]).astype(np.float32),
                        body2048=down2(f["body"].astype(np.float32)) > 0.5,
                        rim2048=down2(f["rimband"].astype(np.float32)) > 0.5,
                        centre2048=down2(f["centre"].astype(np.float32)) > 0.5,
                        endness2048=down2(f["endness"]).astype(np.float32),
                        dist2048=(down2(f["dist"]) / 2.0).astype(np.float32),
                        owner2048=f["owner"][::2, ::2])
    dirs = f["dirs"]
    json.dump(dirs, open(os.path.join(OUT, "gv2_directions.json"), "w"), indent=1, sort_keys=True)
    rep = {"tool": "Saved/CodexConductor/GreaseV2_20261008/gv2_build.py", "seed": SEED,
           "outputs": {"T_HP_S03_GreaseAtlas_v2.png": sha(pa), "T_HP_S03_PrintNormal_v2.png": sha(pn)},
           "sources": {"live_atlas": LIVE_ATLAS_SHA, "live_normal": LIVE_NORMAL_SHA, "basecolor": BASE_SHA},
           "normal_slope_scale": round(scale, 4), "live_normal_p99_xy": round(live_p99, 4),
           "params": {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float, tuple))}}
    json.dump(rep, open(os.path.join(OUT, "gv2_build_report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))
    print("GV2_BUILD_DONE")


if __name__ == "__main__":
    main()
