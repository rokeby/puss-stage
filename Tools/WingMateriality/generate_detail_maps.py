"""Generate the tiling close-range detail maps for M_Wing_PaintedSurface_Master.

The wing images carry the far read; these carry what the camera sees at 1-2 m:
canvas tooth, brush direction and grime breakup. Every map is periodic (built in
the frequency domain or on an integer thread grid), so it tiles without seams
under raking light.

Outputs, in DerivedAssets/WingMateriality/DetailMaps/:
  T_WingDetail_WeaveN.png   plain-weave canvas normal map (DirectX green, as Unreal expects)
  T_WingDetail_BrushH.png   directional brush-stroke height, 16-bit grayscale
  T_WingDetail_BrushN.png   normal map derived from BrushH
  T_WingDetail_Grime.png    1/f grime and dust breakup, 16-bit grayscale; also the default burn mask

Deterministic: fixed seeds, so rerunning reproduces the same files.
Usage: python Tools/WingMateriality/generate_detail_maps.py [--size 1024]
"""
import argparse
import json
import pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "DerivedAssets" / "WingMateriality" / "DetailMaps"


def periodic_noise(size, rng, spectrum):
    """Real, periodic noise with the given radial/anisotropic amplitude spectrum."""
    white = rng.standard_normal((size, size))
    f = np.fft.fft2(white) * spectrum
    out = np.real(np.fft.ifft2(f))
    out -= out.mean()
    return out / (out.std() + 1e-9)


def freq_grid(size):
    k = np.fft.fftfreq(size) * size  # cycles per tile
    return np.meshgrid(k, k)  # (kx, ky)


def normalise01(a, lo_pct=0.5, hi_pct=99.5):
    lo, hi = np.percentile(a, [lo_pct, hi_pct])
    return np.clip((a - lo) / (hi - lo + 1e-9), 0.0, 1.0)


def height_to_normal(h, strength):
    """Tileable central-difference normal; DirectX convention (green = -dy)."""
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * strength
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5 * strength
    n = np.stack([-dx, dy, np.ones_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def save_normal(n, path):
    rgb = np.clip((n * 0.5 + 0.5) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(rgb, "RGB").save(path)


def save_gray16(a, path):
    Image.fromarray(np.clip(a * 65535.0 + 0.5, 0, 65535).astype(np.uint16)).save(path)


def weave_height(size, threads, rng):
    """Plain weave: warp over weft on alternating cells, with a rounded thread profile
    and fibre noise so it doesn't read as a perfect grid."""
    y, x = np.mgrid[0:size, 0:size] / size * threads
    ci, cj = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - ci, y - cj
    warp_profile = np.sin(np.pi * fx) ** 0.6  # warp runs vertically, profile across x
    weft_profile = np.sin(np.pi * fy) ** 0.6
    # Undulation: each thread rises where it passes over and dips where it passes under.
    warp_over = ((ci + cj) % 2 == 0)
    warp_h = warp_profile * np.where(warp_over, 1.0, 0.45) * (0.75 + 0.25 * np.sin(np.pi * fy))
    weft_h = weft_profile * np.where(~warp_over, 1.0, 0.45) * (0.75 + 0.25 * np.sin(np.pi * fx))
    h = np.maximum(warp_h, weft_h)
    kx, ky = freq_grid(size)
    fibre = periodic_noise(size, rng, np.exp(-((kx / (threads * 6)) ** 2 + (ky / (threads * 1.5)) ** 2)))
    fibre2 = periodic_noise(size, rng, np.exp(-((kx / (threads * 1.5)) ** 2 + (ky / (threads * 6)) ** 2)))
    slub = periodic_noise(size, rng, np.exp(-(kx ** 2 + ky ** 2) / (threads * 0.5) ** 2))
    h = h + 0.06 * np.where(warp_h >= weft_h, fibre2, fibre) + 0.05 * slub
    return normalise01(h)


def brush_height(size, rng):
    """Brushwork: stroke patches laid in two wandering directions, bristle grooves
    running along each stroke, and a raised lip where paint was pushed to the
    stroke's edge. Kept low-contrast; the material scales it."""
    kx, ky = freq_grid(size)

    def along(angle_deg, len_cycles, width_cycles):
        a = np.deg2rad(angle_deg)
        u = kx * np.cos(a) + ky * np.sin(a)
        v = -kx * np.sin(a) + ky * np.cos(a)
        spec = np.exp(-(u / len_cycles) ** 2 - (v / width_cycles) ** 2)
        spec[0, 0] = 0.0
        return spec

    # Which direction dominates where: a slow mask so strokes change heading in patches.
    r = np.sqrt(kx ** 2 + ky ** 2)
    heading = 0.5 + 0.5 * np.tanh(1.5 * periodic_noise(size, rng, np.exp(-(r / 3.0) ** 2)))
    body_a = periodic_noise(size, rng, along(72.0, 1.6, 12.0))
    body_b = periodic_noise(size, rng, along(104.0, 1.6, 12.0))
    body = heading * body_a + (1.0 - heading) * body_b
    patches = 0.5 + 0.5 * np.tanh(2.2 * body)          # soft-edged stroke patches
    bristle_a = periodic_noise(size, rng, along(72.0, 3.0, 110.0))
    bristle_b = periodic_noise(size, rng, along(104.0, 3.0, 110.0))
    bristle = heading * bristle_a + (1.0 - heading) * bristle_b
    gy, gx = np.gradient(patches)
    lip = np.sqrt(gx ** 2 + gy ** 2)
    lip = lip / (lip.max() + 1e-9)
    h = 0.55 * patches + 0.18 * bristle * (0.4 + 0.6 * patches) + 0.35 * lip
    return normalise01(h)


def grime(size, rng):
    kx, ky = freq_grid(size)
    r = np.sqrt(kx ** 2 + ky ** 2)
    r[0, 0] = 1.0
    spec = 1.0 / r ** 1.15
    spec[0, 0] = 0.0
    g = periodic_noise(size, rng, spec)
    # A little cellular clumping so dust gathers rather than fogging evenly.
    clump = periodic_noise(size, rng, np.exp(-(r / 24.0) ** 2))
    return normalise01(g + 0.35 * np.maximum(clump, 0.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--threads", type=int, default=16, help="threads per tile along each axis")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    size = args.size

    weave = weave_height(size, args.threads, np.random.default_rng(1701))
    save_normal(height_to_normal(weave, strength=size / args.threads * 0.3), OUT / "T_WingDetail_WeaveN.png")

    brush = brush_height(size, np.random.default_rng(1702))
    save_gray16(brush, OUT / "T_WingDetail_BrushH.png")
    save_normal(height_to_normal(brush, strength=size / 96.0), OUT / "T_WingDetail_BrushN.png")

    save_gray16(grime(size, np.random.default_rng(1703)), OUT / "T_WingDetail_Grime.png")

    manifest = {
        "generator": "Tools/WingMateriality/generate_detail_maps.py",
        "size": size,
        "threads_per_tile": args.threads,
        "seeds": {"weave": 1701, "brush": 1702, "grime": 1703},
        "import": {
            "T_WingDetail_WeaveN": {"compression": "TC_NORMALMAP", "srgb": False},
            "T_WingDetail_BrushN": {"compression": "TC_NORMALMAP", "srgb": False},
            "T_WingDetail_BrushH": {"compression": "TC_GRAYSCALE", "srgb": False},
            "T_WingDetail_Grime": {"compression": "TC_GRAYSCALE", "srgb": False},
        },
        "unreal_destination": "/Game/Scenes/Wings/PaintedSurface/Textures",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("WING_DETAIL_MAPS_OK", OUT)


if __name__ == "__main__":
    main()
