"""Scene 3 waves v3 - deterministic silhouette + painterly skin generator (OFFLINE, no Unreal, no Blender).

Gary 7 Oct: layered theatrical sea - front "wave-pattern shaped" breakers, staggered rolling swells behind,
foam/spray at the back; moody and cool but with contrast.

Run with the FlatV3 venv (numpy, opencv, scipy):
  D:/PussStageTools/FlatV3/venv/Scripts/python.exe s3_waves_v3_design.py [--res 2.0] [--variants A,B]

Writes only under DerivedAssets/FlatV3/Scene3/waves_v3/<variant>/:
  <layer>_mask.png        binary cut mask (white = board), bottom row solid; build_v3_flat --mask input
  <layer>_art.png         RGB painted art incl. bleed past the cut line; build_skin --art input
  <layer>_rgba.png        preview card (art + mask alpha)
  design_<variant>.json   layer table, palette, seeds, cut-rule gates, hashes
Every random draw comes from numpy Generator(PCG64(seed)) with ONE draw per statement (no two draws in one
expression, see memory puss-random-draw-order).
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

PROJECT = Path(__file__).resolve().parents[3]
OUT_ROOT = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "waves_v3"
BACKDROP = PROJECT / "DerivedAssets" / "FlatV3" / "Scene3" / "backdrop" / "textures" / "T_S3_OpalBeach_Backdrop_SkinColor.png"
SRC = Path(r"D:\PussStageSources\FlatV3\SEA_ROWS")
GRAIN_SOURCES = {  # read-only, CC0 / PD (source.json in each folder)
    "hollar": SRC / "met_361510" / "original.jpg",          # Hollar, Warship in the Trough of a Wave, 1665 (Met CC0)
    "bakhuysen": SRC / "rijks_200108177" / "original.jpg",  # Bakhuysen, Rough Sea, 1692 (Rijks PDM)
}

U_MIN, U_MAX = -1100.0, 1100.0   # strip spans the 20 m hangar + 100 cm controlled overhang each side (cm)
SKIRT_CM = 20.0                  # board continues 20 cm below floor top (into the notch/deck) so bob never opens a gap
PRODUCTION_RES = 4096.0 / 1250.0  # px/cm: a 12.5 m piece is exactly 4096 px wide (SkinColor width)
MIN_FEATURE_CM = 3.0             # Flat V3 jigsaw rule: no feature under ~3 cm at final size


# ----------------------------------------------------------------------------------------------- palette
def sample_backdrop_palette():
    """Anchors MEASURED from the built backdrop SkinColor (4096x8192 downsampled to 512x1024, INTER_AREA)."""
    im = cv2.imread(str(BACKDROP), cv2.IMREAD_UNCHANGED)
    im = cv2.resize(im, (512, 1024), interpolation=cv2.INTER_AREA)[:, :, :3][:, :, ::-1].astype(np.float64)

    def med(r0, r1, c0, c1):
        return np.median(im[int(r0 * 1024):int(r1 * 1024), int(c0 * 512):int(c1 * 512)].reshape(-1, 3), 0)

    sky = im[:940].reshape(-1, 3)
    coolness = sky[:, 2] - sky[:, 0]
    cool = np.median(sky[coolness >= np.percentile(coolness, 99.9)], 0)
    foot = im[860:930, 60:220].reshape(-1, 3)
    shadow = np.median(foot[foot.sum(1) <= np.percentile(foot.sum(1), 2)], 0)
    return {
        "paper": med(.05, .30, .10, .90).round().tolist(),          # sky / paper white -> foam
        "coolest_sky": cool.round().tolist(),                       # bluest 0.1% of sky (still near-neutral)
        "horizon_sea": med(776 / 1024, 784 / 1024, 20 / 512, 300 / 512).round().tolist(),
        "sand": med(.80, .88, .60, .90).round().tolist(),
        "figure_shadow": shadow.round().tolist(),
        "coolest_sky_B_minus_R": float(cool[2] - cool[0]),
    }


def hls_shift(rgb, hue_deg, sat, light):
    """Keep nothing but the target HLS - used to derive the cool sea from a measured anchor's lightness."""
    r, g, b = colorsys.hls_to_rgb(hue_deg / 360.0, light, sat)
    return [round(r * 255), round(g * 255), round(b * 255)]


def derive_palette(anchors, variant):
    """Derived (DESIGN CHOICE, not sampled): the skin has no blue (coolest sky B-R ~ -4), so the cool sea takes
    its HUE from a chosen slate / grey-green and its LIGHTNESS ladder from the measured anchors; foam IS the
    measured paper white so the sea's lights belong to the mural."""
    paper = anchors["paper"]
    cool_l = colorsys.rgb_to_hls(*[c / 255 for c in anchors["coolest_sky"]])[1]
    sea_l = colorsys.rgb_to_hls(*[c / 255 for c in anchors["horizon_sea"]])[1]
    shadow_l = colorsys.rgb_to_hls(*[c / 255 for c in anchors["figure_shadow"]])[1]
    if variant == "A":   # woodblock: slate-indigo troughs, hard white claws
        hue, sat = 208.0, 0.22
        trough = hls_shift(None, hue, sat + 0.06, shadow_l * 0.36)
        body = hls_shift(None, hue, sat, shadow_l * 0.62)
        light = hls_shift(None, hue - 14, sat * 0.75, sea_l * 0.66)
        glow = hls_shift(None, hue - 30, sat * 0.55, cool_l * 0.80)
        line = hls_shift(None, hue + 6, sat + 0.10, shadow_l * 0.24)
    else:                # nocturne: Whistler grey-green, softer but still lit crests
        hue, sat = 176.0, 0.12
        trough = hls_shift(None, hue + 20, sat + 0.04, shadow_l * 0.40)
        body = hls_shift(None, hue, sat, shadow_l * 0.68)
        light = hls_shift(None, hue - 20, sat * 0.8, sea_l * 0.70)
        glow = hls_shift(None, hue - 40, sat * 0.7, cool_l * 0.84)
        line = hls_shift(None, hue + 24, sat + 0.06, shadow_l * 0.30)
    foam_shadow = [round(0.62 * p + 0.38 * l) for p, l in zip(paper, light)]
    return {"trough": trough, "body": body, "light": light, "glow": glow, "line": line,
            "foam": paper, "foam_shadow": foam_shadow, "hue_deg": hue, "sat": sat}


# ----------------------------------------------------------------------------------------------- layers
# Root-local x positions sit INSIDE the three floor notches the shore re-sculpt already cuts
# (s3_shore_footprint.json wave_rows: Row1 3649..3735, Row2 4449..4535, Row3 5249..5332, flush half-width
# max(45, half+10)); every layer is two overlapping pieces 15 cm apart in x, frames <= 12 cm deep.
LAYOUTS = {
    # Heights are SOLVED, not guessed: the S3 shot cameras sit 110-175 cm above the floor top and only 6-15 m from
    # band 1, so a front crest above eye height hides every row behind it.  Each layer's top must clear the
    # sightline over the layer in front, from every shot (B04/B05/B06/B07/B09/B11 eyes), by a margin:
    # see heights_solver() and the report.  Front breaker tops therefore stay at ~1.1-1.25 m.
    # Variant A: "low sea" - margin ~0.3 deg; the back crest line stays at the mural figure-feet sightline from B04.
    "A": [
        dict(id="L1_Breakers", kind="breaker", x=3650, peak=100, trough=40, period=(230, 290), seed=71001, curl=+1),
        dict(id="L2_SwellNear", kind="swell", x=3695, peak=120, trough=76, period=(380, 460), seed=71002, caps=0.45, phase=0.31),
        dict(id="L3_SwellMid", kind="swell", x=4450, peak=138, trough=94, period=(460, 580), seed=71003, caps=0.35, phase=0.77),
        dict(id="L4_SwellFar", kind="swell", x=4495, peak=152, trough=106, period=(540, 660), seed=71004, caps=0.30, phase=0.12),
        dict(id="L5_Rollers", kind="breaker", x=5250, peak=172, trough=126, period=(400, 520), seed=71005, curl=-1, small=True),
        dict(id="L6_Foam", kind="foam", x=5295, peak=200, trough=142, period=(260, 380), seed=71006),
    ],
    # Variant B: "raked sea" - margin ~0.5 deg toward the old 2.6 m back row; the surf masks the mural foreground.
    "B": [
        dict(id="L1_Breakers", kind="breaker", x=3650, peak=106, trough=40, period=(250, 310), seed=72001, curl=+1, scroll=True),
        dict(id="L2_SwellNear", kind="swell", x=3695, peak=130, trough=80, period=(420, 520), seed=72002, caps=0.30, phase=0.55),
        dict(id="L3_SwellMid", kind="swell", x=4450, peak=160, trough=105, period=(500, 620), seed=72003, caps=0.25, phase=0.05),
        dict(id="L4_SwellFar", kind="swell", x=4495, peak=178, trough=122, period=(580, 720), seed=72004, caps=0.25, phase=0.62),
        dict(id="L5_Rollers", kind="breaker", x=5250, peak=218, trough=152, period=(460, 580), seed=72005, curl=-1, small=True, scroll=True),
        dict(id="L6_Foam", kind="foam", x=5295, peak=262, trough=180, period=(280, 400), seed=72006),
    ],
}

SHOT_EYES = {  # s3_shore_footprint.json cameras.rows: root-local x, eye height above the floor top (z - 115)
    "B04": (3000.0, 125.0), "B05": (2700.0, 145.0), "B06": (2880.0, 120.0), "B07": (2800.0, 125.0),
    "B09": (2100.0, 175.0), "B11": (2920.0, 110.0),
}


def sightline_table(layers):
    """Per layer and shot: elevation (deg) of the layer's max height, and its clearance over the layer in front."""
    rows = []
    prev = None
    for L in sorted(layers, key=lambda r: r["x"]):
        row = {"id": L["id"], "x": L["x"], "max_height_cm": L["max_height_cm"], "shots": {}}
        for k, (ex, ez) in SHOT_EYES.items():
            ang = math.degrees(math.atan2(L["max_height_cm"] - ez, L["x"] - ex))
            clear = None if prev is None else ang - math.degrees(math.atan2(prev["max_height_cm"] - ez, prev["x"] - ex))
            row["shots"][k] = {"elev_deg": round(ang, 2), "clears_front_by_deg": None if clear is None else round(clear, 2)}
        rows.append(row)
        prev = L
    return rows


class Canvas:
    def __init__(self, top_cm, res):
        self.res = float(res)
        self.top = float(top_cm)
        self.w = int(round((U_MAX - U_MIN) * self.res))
        self.h = int(round((self.top + SKIRT_CM) * self.res))

    def px(self, u, v):
        return (u - U_MIN) * self.res, (self.top - v) * self.res

    def uv_grid(self):
        xs = (np.arange(self.w) + 0.5) / self.res + U_MIN
        ys = self.top - (np.arange(self.h) + 0.5) / self.res
        return np.meshgrid(xs, ys)


def poly(canvas, img, pts_uv, value=255):
    p = np.array([canvas.px(u, v) for u, v in pts_uv], np.float64)
    cv2.fillPoly(img, [np.round(p * 8).astype(np.int32)], value, lineType=cv2.LINE_AA, shift=3)


def stroke(canvas, img, path_uv, radii_cm, value=255):
    """Union of discs along a path: a tapered brush stroke cut in plywood."""
    for (u, v), r in zip(path_uv, radii_cm):
        x, y = canvas.px(u, v)
        cv2.circle(img, (int(round(x * 8)), int(round(y * 8))), max(1, int(round(r * canvas.res * 8))), value,
                   -1, lineType=cv2.LINE_AA, shift=3)


def units(rng, period_range):
    """Wave unit boundaries along the strip; widths drawn one at a time."""
    edges = [U_MIN - 300.0]
    while edges[-1] < U_MAX + 300.0:
        width = float(rng.uniform(*period_range))
        edges.append(edges[-1] + width)
    return edges


def value_noise_1d(rng, n_knots, length_cm):
    knots = rng.standard_normal(n_knots)
    xs = np.linspace(U_MIN - 400, U_MAX + 400, n_knots)

    def f(u):
        return np.interp(u, xs, knots)
    return f


def curl_lip(canvas, img, uc, h, R, d, rng, scroll=False, claws=True):
    """A crest that curls FORWARD over an open mouth: a tapering spiral whose start overlaps the crest and
    whose end hangs in front of the face (woodblock / stage-sea profile). d=+1 curls toward +u."""
    C = (uc + d * 0.80 * R, h - 0.98 * R)
    a0 = math.radians(128.0)
    sweep = math.radians(380.0 if scroll else 225.0)
    n = 160
    path, radii = [], []
    lead = 10
    start = (C[0] + d * R * math.cos(a0), C[1] + R * math.sin(a0))
    for i in range(lead):            # joins the lip to the back slope just behind the crest
        f = i / lead
        path.append((uc - d * 0.55 * R + (start[0] - (uc - d * 0.55 * R)) * f, h - 0.42 * R + (start[1] - (h - 0.42 * R)) * f))
        radii.append(0.40 * R)
    for i in range(n + 1):
        f = i / n
        q = a0 - sweep * f
        r = R * (1.0 - (0.62 if scroll else 0.30) * f)
        path.append((C[0] + d * r * math.cos(q), C[1] + r * math.sin(q)))
        radii.append(R * ((0.34 - 0.20 * f ** 0.8) if scroll else (0.36 - 0.29 * f ** 0.7)))
    stroke(canvas, img, path, np.maximum(np.array(radii), MIN_FEATURE_CM * 0.7))
    if scroll:      # rolled volute end
        x, y = path[-1]
        stroke(canvas, img, [(x, y)], [max(0.17 * R, MIN_FEATURE_CM)])
    if claws:
        n_claw = int(rng.integers(5, 8))
        for k in range(n_claw):
            f = 0.05 + 0.85 * k / max(1, n_claw - 1)
            q = a0 - sweep * f
            r = R * (1.0 - 0.30 * f)
            bu, bv = C[0] + d * (r + 0.30 * R) * math.cos(q), C[1] + (r + 0.30 * R) * math.sin(q)
            tq = q - math.radians(70.0)               # point along the curl (clockwise), slightly outward
            length = R * float(rng.uniform(0.30, 0.55))
            bend = float(rng.uniform(0.15, 0.35))
            m = 14
            cpath, crad = [], []
            for i in range(m + 1):
                g = i / m
                qq = tq - bend * g * math.pi / 2
                cpath.append((bu + d * length * g * math.cos(qq), bv + length * g * math.sin(qq)))
                crad.append(max(MIN_FEATURE_CM * 0.7, R * (0.11 - 0.085 * g)))
            stroke(canvas, img, cpath, crad)
    return C


def breaker_shapes(L, canvas, rng):
    """Stylised breaking crests ("wave-pattern" profile): long back slope, near-vertical face under the crest,
    a lip curling forward over an OPEN mouth, claws (variant A) or a rolled scroll (scroll=True)."""
    body = np.zeros((canvas.h, canvas.w), np.uint8)
    curl = np.zeros_like(body)
    d = float(L["curl"])
    scale = 0.70 if L.get("small") else 1.0
    edges = units(rng, L["period"])
    for a, b in zip(edges[:-1], edges[1:]):
        P = b - a
        jitter_h = float(rng.uniform(-0.10, 0.08))
        h = L["trough"] + (L["peak"] - L["trough"]) * (1.0 + jitter_h)
        t = L["trough"]
        sc = float(rng.uniform(0.50, 0.60))
        R = scale * float(rng.uniform(0.27, 0.33)) * (h - t)
        # unit-local profile for d=+1 (x from 0..P), then mirrored for d=-1
        xs, ys = [], []
        xc = sc * P
        for i in range(60):                         # back slope: trough -> crest
            f = i / 59
            xs.append(xc * f)
            ys.append(t + (h - t) * (math.sin(0.5 * math.pi * f) ** 1.8))
        face = [(xc + 0.10 * R, h - 0.55 * R), (xc + 0.16 * R, h - 1.05 * R)]
        for x, y in face:
            xs.append(x)
            ys.append(y)
        x_end = min(P, xc + 2.6 * R)
        for i in range(1, 21):                      # concave sweep down into the next trough
            f = i / 20
            xs.append(xc + 0.16 * R + (x_end - xc - 0.16 * R) * f)
            ys.append(t + (h - 1.05 * R - t) * (1 - f) ** 2.2)
        xs.append(P)
        ys.append(t)
        us = [a + x if d > 0 else b - x for x in xs]
        pts = [(us[0], -SKIRT_CM - 5)] + list(zip(us, ys)) + [(us[-1], -SKIRT_CM - 5)]
        poly(canvas, body, pts)
        uc = a + xc if d > 0 else b - xc
        curl_lip(canvas, curl, uc, h, R, d, rng, scroll=bool(L.get("scroll")), claws=not L.get("scroll"))
    mask = cv2.max(body, curl)
    return mask, curl


def swell_shape(L, canvas, rng):
    """Staggered rolling swell: two trochoids + a slow envelope; small breaking caps on some crests."""
    U, _ = canvas.uv_grid()
    u = U[0]
    lam1 = float(rng.uniform(*L["period"]))
    lam2 = lam1 * float(rng.uniform(0.47, 0.58))
    env = value_noise_1d(rng, 9, U_MAX - U_MIN)

    def trochoid(u, lam, sharp, phase):
        k = 2 * math.pi / lam
        a = np.linspace(U_MIN - lam, U_MAX + lam, 6000)
        x = a - sharp / k * np.sin(k * a + phase)
        y = np.cos(k * a + phase)
        return np.interp(u, x, y)

    y = 0.68 * trochoid(u, lam1, 0.78, 2 * math.pi * L["phase"]) + 0.32 * trochoid(u, lam2, 0.55, float(rng.uniform(0, 6.28)))
    y = (y - y.min()) / (y.max() - y.min())
    e = 0.82 + 0.18 * np.tanh(env(u))
    v = L["trough"] + (L["peak"] - L["trough"]) * y * e
    mask = np.zeros((canvas.h, canvas.w), np.uint8)
    pts = [(u[0], -SKIRT_CM - 5)] + list(zip(u, v)) + [(u[-1], -SKIRT_CM - 5)]
    poly(canvas, mask, pts)
    curl = np.zeros_like(mask)
    # caps: little forward-curling whitecaps on a share of local maxima
    peaks = [i for i in range(1, len(v) - 1) if v[i] >= v[i - 1] and v[i] > v[i + 1]]
    d = 1.0 if L["phase"] < 0.5 else -1.0
    for i in peaks:
        roll = float(rng.random())
        if roll > L["caps"]:
            continue
        R = float(rng.uniform(10, 18))
        curl_lip(canvas, curl, u[i], v[i] + 0.25 * R, R, d, rng, scroll=False, claws=False)
    mask = cv2.max(mask, curl)
    return mask, curl


def foam_shape(L, canvas, rng):
    """Back foam/spray row: a swell base, a broken frothing crest band, spray plumes, lace holes."""
    base, _ = swell_shape(dict(L, caps=0.0, phase=0.4, peak=L["peak"] - 34, trough=L["trough"]), canvas, rng)
    U, V = canvas.uv_grid()
    u = U[0]
    top_idx = np.argmax(base > 127, axis=0)
    top_v = canvas.top - (top_idx + 0.5) / canvas.res
    n1 = value_noise_1d(rng, 140, 0)(u)
    n2 = value_noise_1d(rng, 420, 0)(u)
    froth = 14 + 9 * n1 + 5 * n2
    mask = base.copy()
    curl = np.zeros_like(base)
    # froth band: blobby discs riding the crest line
    for j in range(0, len(u), max(1, int(canvas.res * 6))):
        r = float(np.clip(froth[j], 6, 28))
        jitter = float(rng.uniform(-0.3, 0.5))
        stroke(canvas, curl, [(u[j], top_v[j] + jitter * r)], [r])
    # spray plumes: tapered upward-forward fingers from the crests
    edges = units(rng, L["period"])
    for a, b in zip(edges[:-1], edges[1:]):
        uc = float(rng.uniform(a + 0.2 * (b - a), b - 0.2 * (b - a)))
        if uc < U_MIN or uc > U_MAX:
            continue
        j = int(np.clip((uc - U_MIN) * canvas.res, 0, len(u) - 1))
        n_f = int(rng.integers(2, 5))
        for k in range(n_f):
            height = float(rng.uniform(18, 46))
            lean = float(rng.uniform(-0.5, 0.9))
            off = float(rng.uniform(-24, 24))
            n = 16
            path = [(uc + off + lean * height * (i / n) ** 1.4, top_v[j] + 6 + height * i / n) for i in range(n + 1)]
            stroke(canvas, curl, path, np.linspace(7.5, 2.0, n + 1))
    mask = cv2.max(mask, curl)
    # lace holes under the froth (each >= ~8 cm; ligaments enforced by the cut rules below)
    holes = np.zeros_like(mask)
    for j in range(0, len(u), max(1, int(canvas.res * 9))):
        roll = float(rng.random())
        if roll > 0.16:
            continue
        r = float(rng.uniform(5.0, 10.0))
        depth = float(rng.uniform(18, 34))
        stretch = float(rng.uniform(1.0, 2.6))
        stroke(canvas, holes, [(u[j] + k * r * 0.6, top_v[j] - depth + 0.25 * r * math.sin(k)) for k in range(int(stretch * 3))],
               [r * (1 - 0.12 * k) for k in range(int(stretch * 3))])
    mask = cv2.subtract(mask, holes)
    return mask, curl


def apply_cut_rules(mask, res):
    """Jigsaw-cuttable line: smooth, open/close at 3 cm, keep one connected board, drop sub-3 cm holes,
    bottom skirt solid. Returns (mask, gates)."""
    m = (cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 1.2 * res) > 0.5).astype(np.uint8)
    k = int(round(MIN_FEATURE_CM * res)) | 1
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, disc)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disc)
    lab, n = ndimage.label(m)
    if n > 1:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = (lab == (1 + int(np.argmax(sizes)))).astype(np.uint8)
    holes = ndimage.binary_fill_holes(m) & ~m.astype(bool)
    hl, hn = ndimage.label(holes)
    min_hole_px = (MIN_FEATURE_CM * res) ** 2
    small = 0
    if hn:
        hs = ndimage.sum(holes, hl, range(1, hn + 1))
        for i, s in enumerate(hs, 1):
            if s < min_hole_px:
                m[hl == i] = 1
                small += 1
    m[-int(SKIRT_CM * res * 0.9):, :] = 1
    lab, n = ndimage.label(m)
    holes = ndimage.binary_fill_holes(m) & ~m.astype(bool)
    _, kept_holes = ndimage.label(holes)
    # narrowest ligament: max inscribed radius check on the thinnest parts is approximated by an erosion test
    er = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(1, k - 2), max(1, k - 2))))
    lost = int(m.sum() - cv2.dilate(er, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(1, k - 2), max(1, k - 2)))).astype(np.uint8).clip(0, 1).sum())
    gates = {"components": int(n), "holes_kept": int(kept_holes), "sub3cm_holes_filled": small,
             "open_close_kernel_px": k, "erode_dilate_px_lost": lost,
             "pass": bool(n == 1)}
    return (m * 255).astype(np.uint8), gates


# ----------------------------------------------------------------------------------------------- painting
GRAIN_BOXES = {  # (x0, y0, x1, y1) fractions: sea only - no ships, rigging or figures (checked by eye)
    "hollar": (0.02, 0.62, 0.70, 0.90),
    "bakhuysen": (0.03, 0.80, 0.65, 0.94),
}


def grain(name, shape, seed):
    """High-passed luminance of an on-disk PD/CC0 sea engraving/painting (fixed sea-only crop box)."""
    src = cv2.imread(str(GRAIN_SOURCES[name]), cv2.IMREAD_GRAYSCALE)
    h, w = src.shape
    x0, y0, x1, y1 = GRAIN_BOXES[name]
    crop = src[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
    crop = cv2.medianBlur(crop, 5).astype(np.float32) / 255.0   # removes the 1 px scan seams in the Rijks file
    crop = cv2.resize(crop, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
    hp = crop - cv2.GaussianBlur(crop, (0, 0), 6)
    return np.clip(hp / (hp.std() + 1e-6), -3, 3)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def paint(L, mask, curl, canvas, pal, variant, seed):
    rng = np.random.Generator(np.random.PCG64(seed))
    res = canvas.res
    inside = mask > 127
    U, V = canvas.uv_grid()
    D = ndimage.distance_transform_edt(inside) / res                         # cm to nearest edge
    soft = cv2.GaussianBlur(inside.astype(np.float32), (0, 0), 2.5 * res)
    gy, gx = np.gradient(soft)
    up = np.clip(gy / (np.hypot(gx, gy) + 1e-6), 0, 1)                       # outward normal points UP (image y down)
    up = cv2.GaussianBlur(up, (0, 0), 3 * res)
    # nearest-edge "upness": propagate the edge-band upness inward along the distance field
    edge_band = (D < 2.0) & inside
    _, (iy, ix) = ndimage.distance_transform_edt(~edge_band, return_indices=True)
    up_near = up[iy, ix]
    span = max(1.0, L["peak"] - L["trough"])
    hf = np.clip((V - L["trough"] + 0.15 * span) / (1.15 * span), 0, 1.2)
    c = {k: np.array(v, np.float32) / 255.0 for k, v in pal.items() if isinstance(v, list)}
    img = (c["trough"][None, None] * (1 - smoothstep(0.0, 0.75, hf))[..., None]
           + c["body"][None, None] * smoothstep(0.0, 0.75, hf)[..., None])
    img = img * (1 - smoothstep(0.55, 1.05, hf))[..., None] + c["light"][None, None] * smoothstep(0.55, 1.05, hf)[..., None]
    # light through the crest: a glow band under up-facing edges
    glow_w = 14.0 + 6.0 * np.sin(U / 37.0)
    glow = (1 - smoothstep(0.0, glow_w, D)) * up_near * smoothstep(0.25, 0.7, hf)
    img = img * (1 - 0.75 * glow[..., None]) + c["glow"][None, None] * 0.75 * glow[..., None]
    # painted crest rim: a thin light line on every up-facing edge, so a crest reads against the darker row behind
    rim = (1 - smoothstep(0.6, 2.2, D)) * smoothstep(0.3, 0.8, up_near) * 0.7
    img = img * (1 - rim[..., None]) + c["foam"][None, None] * rim[..., None]
    # foam on up-facing edges and over the curl tongues/claws/caps
    fnoise = cv2.GaussianBlur(rng.standard_normal(mask.shape).astype(np.float32), (0, 0), 4 * res)
    fnoise = fnoise / (fnoise.std() + 1e-6)
    foam_w = np.clip(4.5 + 3.0 * fnoise, 0.8, 11)
    if L["kind"] == "foam":
        foam_w = foam_w * 2.4
    foam = (D < foam_w) * smoothstep(0.35, 0.8, up_near) * smoothstep(0.3, 0.75, hf)
    curl_soft = cv2.GaussianBlur((curl > 127).astype(np.float32), (0, 0), 1.0 * res)
    foam = np.maximum(foam, curl_soft * (0.55 + 0.45 * smoothstep(-0.5, 1.0, fnoise)))
    if L["kind"] == "foam":
        foam = np.maximum(foam, smoothstep(0.62, 0.95, hf) * smoothstep(-0.8, 0.6, fnoise))
    foam = np.clip(foam, 0, 1)
    # foam shadow: a thin cool line under the foam (woodblock edge)
    under = np.clip(cv2.GaussianBlur(foam, (0, 0), 1.6 * res) - foam, 0, 1) * 2.2
    img = img * (1 - np.clip(under, 0, 0.9)[..., None]) + c["foam_shadow"][None, None] * np.clip(under, 0, 0.9)[..., None]
    img = img * (1 - foam[..., None]) + c["foam"][None, None] * foam[..., None]

    # brush strokes along the flow (tangent to the distance-field contours)
    Dg = cv2.GaussianBlur(D.astype(np.float32), (0, 0), 3 * res)
    ty, tx = np.gradient(Dg)
    ys, xs = np.nonzero(inside)
    n_strokes = int(len(ys) / (res * res) / 55)
    canvas_img = img.astype(np.float32)
    for _ in range(n_strokes):
        k = int(rng.integers(0, len(ys)))
        y, x = int(ys[k]), int(xs[k])
        ang = math.atan2(-tx[y, x], ty[y, x]) if (abs(tx[y, x]) + abs(ty[y, x])) > 1e-4 else 0.0
        drift = float(rng.normal(0, 0.22))
        ang = ang + drift
        length = float(rng.uniform(6, 30)) * res
        width = float(rng.uniform(1.2, 4.0)) * res
        val = float(rng.normal(0, 0.075))
        alpha = float(rng.uniform(0.25, 0.6))
        dx, dy = 0.5 * length * math.cos(ang), 0.5 * length * math.sin(ang)
        x0, y0, x1, y1 = x - dx, y - dy, x + dx, y + dy
        pad = int(width) + 2
        bx0, by0 = max(0, int(min(x0, x1)) - pad), max(0, int(min(y0, y1)) - pad)
        bx1, by1 = min(canvas.w, int(max(x0, x1)) + pad + 1), min(canvas.h, int(max(y0, y1)) + pad + 1)
        if bx1 <= bx0 or by1 <= by0:
            continue
        patch = np.zeros((by1 - by0, bx1 - bx0), np.uint8)
        cv2.line(patch, (int(x0 - bx0), int(y0 - by0)), (int(x1 - bx0), int(y1 - by0)), 255, max(1, int(width)), cv2.LINE_AA)
        a = (patch.astype(np.float32) / 255.0 * alpha)[..., None]
        roi = canvas_img[by0:by1, bx0:bx1]
        colour = np.clip(canvas_img[y, x] * (1 + val), 0, 1)
        canvas_img[by0:by1, bx0:bx1] = roi * (1 - a) + colour[None, None] * a
    img = canvas_img

    # woodblock flow lines (A) / faint scumbled lines (B): broken iso-lines of the distance field
    lines = np.zeros(mask.shape, np.float32)
    spacing = 7.0 if variant == "A" else 11.0
    for lvl in np.arange(spacing, 60, spacing):
        band = (np.abs(D - lvl) < (0.45 if variant == "A" else 0.35)) & inside
        lines = np.maximum(lines, band.astype(np.float32))
    lines = cv2.GaussianBlur(lines, (0, 0), 0.5 * res)
    dash = smoothstep(-0.2, 0.6, cv2.GaussianBlur(rng.standard_normal(mask.shape).astype(np.float32), (0, 0), 6 * res) * 3)
    line_w = (0.55 if variant == "A" else 0.25) * lines * dash * smoothstep(0.15, 0.6, hf) * (1 - 0.7 * foam)
    img = img * (1 - line_w[..., None]) + c["line"][None, None] * line_w[..., None]

    # source grain: Hollar hatching (A) or Bakhuysen brushwork (B), as a gentle multiply
    g = grain("hollar" if variant == "A" else "bakhuysen", mask.shape, seed + 7)
    img = np.clip(img * (1 + (0.06 if variant == "A" else 0.05) * g[..., None]), 0, 1)

    # aerial perspective painted in: layers further back step toward the crest-light value (0 at x 3650, 0.18 at 5300)
    aerial = float(np.clip((L["x"] - 3650.0) / 1650.0, 0, 1)) * 0.18
    img = img * (1 - aerial) + c["light"][None, None] * aerial

    # bleed: outside the cut line take the nearest inside colour (art bleeds past the line)
    _, (iy, ix) = ndimage.distance_transform_edt(~inside, return_indices=True)
    img = img[iy, ix]
    return (np.clip(img, 0, 1) * 255).astype(np.uint8), {
        "foam_coverage": float(foam[inside].mean()), "strokes": n_strokes,
        "mean_luma_inside": float((img[inside] @ np.array([0.2126, 0.7152, 0.0722])).mean()),
    }


# ----------------------------------------------------------------------------------------------- main
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_variant(variant, res):
    out = OUT_ROOT / variant
    out.mkdir(parents=True, exist_ok=True)
    anchors = sample_backdrop_palette()
    pal = derive_palette(anchors, variant)
    layers = []
    for L in LAYOUTS[variant]:
        top = L["peak"] + 70.0
        canvas = Canvas(top, res)
        rng = np.random.Generator(np.random.PCG64(L["seed"]))
        if L["kind"] == "breaker":
            raw, curl = breaker_shapes(L, canvas, rng)
        elif L["kind"] == "swell":
            raw, curl = swell_shape(L, canvas, rng)
        else:
            raw, curl = foam_shape(L, canvas, rng)
        mask, gates = apply_cut_rules(raw, res)
        art, paint_stats = paint(L, mask, curl, canvas, pal, variant, L["seed"] + 500)
        rows = np.nonzero(mask.max(1) > 0)[0]
        top_v = canvas.top - rows.min() / res
        mp, ap, rp = (out / f"{L['id']}_{k}.png" for k in ("mask", "art", "rgba"))
        cv2.imwrite(str(mp), mask)
        cv2.imwrite(str(ap), art[:, :, ::-1])
        rgba = np.dstack([art[:, :, ::-1], mask])
        cv2.imwrite(str(rp), rgba)
        layers.append({
            **{k: v for k, v in L.items()}, "variant": variant,
            "canvas_cm": {"u": [U_MIN, U_MAX], "v": [-SKIRT_CM, top]}, "res_px_per_cm": res,
            "size_px": [canvas.w, canvas.h], "max_height_cm": round(float(top_v), 1),
            "cut_gates": gates, "paint": paint_stats,
            "files": {k: str(p.relative_to(PROJECT)) for k, p in (("mask", mp), ("art", ap), ("rgba", rp))},
            "sha256": {k: sha(p) for k, p in (("mask", mp), ("art", ap), ("rgba", rp))},
        })
        print("S3WAVESV3_LAYER", variant, L["id"], "h=%.1f" % top_v, json.dumps(gates), flush=True)
    design = {"schema": "s3_waves_v3_design/1", "variant": variant, "res_px_per_cm": res,
              "frame": "S3 Hangar Root local cm (LANDED); u = local Y, v = height above floor top (local z 115)",
              "palette_anchors_measured": anchors, "palette_derived": pal, "layers": layers,
              "sightlines": sightline_table(layers),
              "generator": str(Path(__file__).relative_to(PROJECT)), "generator_sha256": sha(__file__)}
    (out / f"design_{variant}.json").write_text(json.dumps(design, indent=1), encoding="utf-8")
    return design


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=float, default=PRODUCTION_RES)
    ap.add_argument("--variants", default="A,B")
    a = ap.parse_args()
    for v in a.variants.split(","):
        build_variant(v.strip(), a.res)
    print("S3WAVESV3_DESIGN_OK", a.variants)


if __name__ == "__main__":
    main()
