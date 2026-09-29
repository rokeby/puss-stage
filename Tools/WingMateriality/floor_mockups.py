"""Offline mockups of kit-floor options next to steel grooves, for Gary to choose from.

NOT an Unreal render. This is a small numpy ray-caster so the options can be compared
while the editor is busy. What it gets right: real texture (the pack's walnut strip,
exported from Unreal), real scale (24 cm lanes, 8 cm grooves with 0.5 cm steel lips,
the camera at 1.7 m), and GGX specular from stage lights, so a glossy floor shows its
reflections. What it approximates: the herringbone is SYNTHESISED from the same
walnut strip (the slab's own herringbone source can't be read offline), the lights are
generic, and there's no GI or volumetrics.

Panels:
  A   continuous walnut herringbone like the approved slab, no board seams
  A'  the same texture with the kit's current 0.8 cm board gaps kept
  B   subtle planks: true-scale walnut strip, low plank contrast, hairline gaps
  C   plain dark waxed lacquer, faint grain, high gloss

Usage: python Tools/WingMateriality/floor_mockups.py
Output: DerivedAssets/WingMateriality/FloorMockups/floor_options.png
"""
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "DerivedAssets/WingMateriality/SourceExports/KitWalnut/T_Walnut_Strp_02_D.png"
OUT = ROOT / "DerivedAssets/WingMateriality/FloorMockups"
W_PX, H_PX, SS = 1200, 675, 2
HFOV = np.radians(68.0)
CAM = np.array([0.0, 0.0, 170.0])
PITCH = np.radians(-11.0)
GROOVES_Y = (-500.0, -250.0, 250.0, 500.0)
GROOVE_HALF, LIP = 4.0, 0.5
MAX_DIST = 4500.0


def srgb_to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def pyramid(img):
    levels = [img]
    while levels[-1].shape[0] > 32:
        a = levels[-1]
        levels.append(0.25 * (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]))
    return levels


def sample(levels, u, v, lod):
    """Bilinear sample with wrap, at an integer mip level per sample."""
    out = np.zeros(u.shape + (3,))
    lod = np.clip(np.round(lod).astype(int), 0, len(levels) - 1)
    for L in np.unique(lod):
        m = lod == L
        tex = levels[L]
        h, w = tex.shape[:2]
        x = (u[m] % 1.0) * w - 0.5
        y = (v[m] % 1.0) * h - 0.5
        x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
        fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
        x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
        out[m] = ((tex[y0, x0] * (1 - fx) + tex[y0, x1] * fx) * (1 - fy)
                  + (tex[y1, x0] * (1 - fx) + tex[y1, x1] * fx) * fy)
    return out


def hash01(*ints):
    h = np.zeros_like(np.asarray(ints[0], dtype=np.float64))
    for k, a in enumerate(ints):
        h = h + np.asarray(a, dtype=np.float64) * (12.9898 + 31.7 * k)
    return np.modf(np.abs(np.sin(h) * 43758.5453))[0]


def camera_rays(pitch=None):
    pitch = PITCH if pitch is None else pitch
    w, h = W_PX * SS, H_PX * SS
    f = np.array([np.cos(pitch), 0.0, np.sin(pitch)])
    r = np.array([0.0, -1.0, 0.0])
    up = np.cross(r, f); up /= np.linalg.norm(up)
    tx = np.tan(HFOV / 2); ty = tx * h / w
    i = (np.arange(w) + 0.5) / w * 2 - 1
    j = 1 - (np.arange(h) + 0.5) / h * 2
    I, J = np.meshgrid(i, j)
    d = f[None, None] + I[..., None] * tx * r + J[..., None] * ty * up
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    return d, 2 * tx / w


LIGHTS = []  # (position, colour*intensity)
for x in (500.0, 1300.0, 2100.0, 2900.0):
    for y in (-650.0, 650.0):
        LIGHTS.append((np.array([x, y, 900.0]), np.array([1.0, 0.72, 0.45]) * 1.1e6))
for y in (-250.0, 250.0):  # back light: the source of the floor reflections the camera sees
    LIGHTS.append((np.array([3800.0, y, 450.0]), np.array([0.65, 0.75, 1.0]) * 2.4e6))


def ggx(nh, a):
    a2 = a * a
    return a2 / (np.pi * (nh * nh * (a2 - 1) + 1) ** 2 + 1e-9)


def shade(P, V, albedo, rough, f0, metal, aniso=None):
    """Point-light GGX plus Lambert on a flat floor (N = +Z)."""
    col = np.zeros_like(albedo)
    N = np.array([0.0, 0.0, 1.0])
    for pos, rad in LIGHTS:
        Lv = pos[None] - P
        dist2 = np.sum(Lv * Lv, -1, keepdims=True)
        L = Lv / np.sqrt(dist2)
        nl = np.clip(L[..., 2:3], 0, 1)
        H = L + V; H /= np.linalg.norm(H, axis=-1, keepdims=True)
        nh = np.clip(H[..., 2], 0, 1)
        vh = np.clip(np.sum(V * H, -1), 0, 1)
        if aniso is None:
            D = ggx(nh, rough)
        else:
            ax, ay = aniso
            D = 1.0 / (np.pi * ax * ay * ((H[..., 0] / ax) ** 2 + (H[..., 1] / ay) ** 2 + nh ** 2) ** 2 + 1e-9)
        F = f0 + (1 - f0) * (1 - vh)[..., None] ** 5
        nv = np.clip(V[..., 2:3], 1e-3, 1)
        k = (rough[..., None] if np.ndim(rough) else rough) ** 2 / 2 + 1e-4
        G = (nl / (nl * (1 - k) + k)) * (nv / (nv * (1 - k) + k))
        spec = D[..., None] * F * G / (4 * nl * nv + 1e-4)
        diff = albedo * (1 - metal) / np.pi
        col += (diff + spec) * rad[None] * nl / dist2
    ambient = albedo * np.array([0.020, 0.022, 0.028])
    return col + ambient


def render(option, levels, mean_col, cam=None, pitch=None):
    cam = CAM if cam is None else cam
    d, pix_ang = camera_rays(pitch)
    hit = d[..., 2] < -1e-4
    t = np.where(hit, -cam[2] / np.where(hit, d[..., 2], -1), np.inf)
    valid = hit & (t < MAX_DIST)
    t = np.where(valid, t, MAX_DIST)  # keep off-floor rays finite; they are masked out below
    P = cam[None, None] + d * t[..., None]
    P[..., 2] = 0.0
    x, y = P[..., 0], P[..., 1]
    foot = t * pix_ang / np.maximum(-d[..., 2], 0.06) ** 0.5
    V = -d
    img = np.zeros(d.shape)

    # ---- floor albedo, roughness and seams per option --------------------------------
    texel_cm_strip = None
    if option in ("A", "A'"):
        Wb, n = 9.0, 5  # parquet block 9 x 45 cm
        c, s = np.cos(np.pi / 4), np.sin(np.pi / 4)
        X, Y = (c * x - s * y) / Wb, (s * x + c * y) / Wb
        fy = np.floor(Y); q = X - fy; m = np.floor(q / (2 * n)); r = q - 2 * n * m
        isH = r < n
        Xt, Yt = X - m * n, Y + m * n
        iH = np.floor(Yt); iV = np.floor(Xt) - n
        along = np.where(isH, (Xt - iH) / n, (Yt - (iV - n + 1)) / n)
        across = np.where(isH, Yt - iH, Xt - np.floor(Xt))
        bid_i = np.where(isH, iH, iV); bid_t = isH.astype(float)
        row = np.floor(hash01(m, bid_i, bid_t) * 20)
        start = np.where(row % 2 > 0.5, 0.25, 0.0)
        u = start + 0.01 + hash01(bid_i, m, 7) * 0.23 + along * 0.25
        v = (row + 0.08 + 0.84 * across) / 20.0
        texel_cm = Wb / (4096 / 20.0)
        alb = sample(levels, u, v, np.log2(np.maximum(foot / texel_cm, 1.0)))
        tint = 1.0 + (hash01(bid_i, m, 3) - 0.5) * 0.10
        alb *= tint[..., None]
        seam = np.minimum(np.minimum(across, 1 - across) * Wb, np.minimum(along, 1 - along) * n * Wb)
        alb *= (0.72 + 0.28 * np.clip(seam / 0.12, 0, 1))[..., None]
        rough = np.full(x.shape, 0.24)
        gap_pitch, gap_w = (24.8, 0.8) if option == "A'" else (None, 0)
    elif option == "B":
        lane = np.floor((y + 12.4) / 24.8)
        ly = (y + 12.4) - lane * 24.8
        stagger = hash01(lane, 1) * 360
        board = np.floor((x + stagger) / 360.0)
        row = np.floor(hash01(lane, board) * 20)
        u = x / 480.0 + hash01(board, lane, 5)
        v = (row + 0.08 + 0.84 * np.clip(ly / 24.0, 0, 1)) / 20.0
        texel_cm = 24.0 / (4096 / 20.0)
        alb = sample(levels, u, v, np.log2(np.maximum(foot / texel_cm, 1.0)))
        alb = mean_col + (alb - mean_col) * 0.55  # far less plank-to-plank contrast
        rough = np.full(x.shape, 0.28)
        gap_pitch, gap_w = 24.8, 0.3
    else:  # C
        u = x / 480.0; v = y / 480.0
        texel_cm = 24.0 / (4096 / 20.0)
        grain = sample(levels, u, v, np.log2(np.maximum(foot / texel_cm, 1.0)) + 3)
        alb = mean_col * 0.55 + (grain - grain[valid].mean(axis=0)) * 0.08
        rough = np.full(x.shape, 0.12)
        gap_pitch, gap_w = None, 0

    if gap_pitch:
        ly = np.mod(y + gap_pitch / 2, gap_pitch)
        gap = ly > (gap_pitch - gap_w)
        edge = np.clip(np.minimum(ly, gap_pitch - gap_w - ly) / 0.6, 0, 1)
        alb = np.where(gap[..., None], alb * 0.08, alb * (0.8 + 0.2 * edge)[..., None])

    floor = shade(P, V, np.clip(alb, 0, 1), rough, 0.04, 0.0)

    # ---- steel grooves: recessed U-channel, worn lips --------------------------------
    gmask = np.zeros(x.shape, bool); lip = np.zeros(x.shape, bool); off = np.full(x.shape, 99.0)
    for gy in GROOVES_Y:
        dy = np.abs(y - gy)
        off = np.minimum(off, dy)
    gmask = off < GROOVE_HALF
    lip = (off >= GROOVE_HALF - LIP) & gmask
    inner = gmask & ~lip
    steel_alb = np.full(x.shape + (3,), 0.56) * np.array([0.98, 0.98, 1.0])
    # Recessed channel: the walls shade the bottom plate, so only a narrow sheen reaches it.
    ao = (0.10 + 0.35 * (1 - (off / GROOVE_HALF) ** 2))[..., None]
    steel = shade(P, V, steel_alb * 0.8, np.full(x.shape, 0.35), 0.5, 1.0, aniso=(0.12, 0.5)) * ao
    lip_col = shade(P, V, steel_alb * 1.1, np.full(x.shape, 0.18), 0.62, 1.0)
    img = np.where(inner[..., None], steel, floor)
    img = np.where(lip[..., None], lip_col, img)

    # ---- haze and background ----------------------------------------------------------
    fog = np.clip(t / MAX_DIST, 0, 1)[..., None] ** 1.6
    bg_col = np.array([0.010, 0.010, 0.014])
    glow = np.exp(-((d[..., 1] / 0.25) ** 2) - ((d[..., 2] - 0.02) / 0.06) ** 2)[..., None] * np.array([0.05, 0.035, 0.022])
    img = np.where(valid[..., None], img * (1 - fog) + bg_col * fog, bg_col + glow)

    # ---- tone map, downsample ----------------------------------------------------------
    exposure = 1.3
    img = img * exposure
    img = img / (1 + img)
    img = lin_to_srgb(img)
    img = img.reshape(H_PX, SS, W_PX, SS, 3).mean(axis=(1, 3))
    return Image.fromarray((img * 255 + 0.5).astype(np.uint8))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tex = srgb_to_lin(np.asarray(Image.open(SRC).convert("RGB"), dtype=np.float64) / 255.0)
    levels = pyramid(tex)
    mean_col = tex.reshape(-1, 3).mean(0)
    titles = {
        "A": "A  Continuous walnut herringbone, like the slab (no board seams)",
        "A'": "A' Same, but with the kit's current 0.8 cm board gaps kept",
        "B": "B  Subtle planks: true-scale walnut, low contrast, hairline gaps",
        "C": "C  Plain dark waxed lacquer, faint grain, high gloss",
    }
    panels = []
    for opt in ("A", "A'", "B", "C"):
        im = render(opt, levels, mean_col)
        dr = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
        dr.rectangle([0, 0, W_PX, 34], fill=(0, 0, 0))
        dr.text((12, 6), titles[opt], fill=(235, 235, 235), font=font)
        im.save(OUT / f"floor_option_{opt.replace(chr(39), 'p')}.png")
        panels.append(im)
    grid = Image.new("RGB", (W_PX * 2, H_PX * 2 + 40))
    for k, im in enumerate(panels):
        grid.paste(im, ((k % 2) * W_PX, (k // 2) * H_PX))
    dr = ImageDraw.Draw(grid)
    try:
        small = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        small = ImageFont.load_default()
    dr.text((12, H_PX * 2 + 10), "Offline mockup, not an Unreal render. Camera 1.7 m, 4 steel grooves "
            "(8 cm, recessed, worn 0.5 cm lips). Herringbone synthesised from the pack's walnut strip; "
            "generic stage lights.", fill=(200, 200, 200), font=small)
    grid.save(OUT / "floor_options.png")
    # Close-up at a groove: 1.2 m high, standing 1 m off the y=250 groove, looking down the run.
    close_cam, close_pitch = np.array([0.0, 150.0, 120.0]), np.radians(-32.0)
    pair = Image.new("RGB", (W_PX * 2, H_PX))
    for k, opt in enumerate(("A", "C")):
        im = render(opt, levels, mean_col, close_cam, close_pitch)
        dr = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
        dr.rectangle([0, 0, W_PX, 34], fill=(0, 0, 0))
        dr.text((12, 6), titles[opt] + ": close-up at a groove", fill=(235, 235, 235), font=font)
        pair.paste(im, (k * W_PX, 0))
    pair.save(OUT / "floor_options_closeup_A_C.png")
    print("FLOOR_MOCKUPS_OK", OUT / "floor_options.png")


if __name__ == "__main__":
    main()
