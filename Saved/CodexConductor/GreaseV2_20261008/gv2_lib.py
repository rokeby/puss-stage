"""Grease v2 shared pure functions (numpy/scipy only).  Used by gv2_build.py, gv2_preview.py, test_grease_v2.py.

Angle convention: radians in ATLAS IMAGE space, x right, y DOWN; theta = direction of the smear axis
(axial, mod pi).  theta = pi/2 means a vertical (top-bottom) smear.
"""
import math

import numpy as np
from scipy import ndimage as ndi

ATLAS_PX_PER_CM_4096 = 12.1943          # atlas.json density_px_per_cm (declaration-proven)


def structure_tensor_angle(img, weight, sigma_d=1.0, hp_sigma=None):
    """Dominant LINE orientation (axial, radians) of `img` integrated over `weight`, and its coherence in [0,1].
    Lines run perpendicular to the dominant gradient.  hp_sigma: optional high-pass (remove the blob's own outline)."""
    f = img.astype(np.float64)
    if hp_sigma:
        f = f - ndi.gaussian_filter(f, hp_sigma)
    gx = ndi.gaussian_filter(f, sigma_d, order=(0, 1))
    gy = ndi.gaussian_filter(f, sigma_d, order=(1, 0))
    w = weight.astype(np.float64)
    jxx, jyy, jxy = (w * gx * gx).sum(), (w * gy * gy).sum(), (w * gx * gy).sum()
    tr = jxx + jyy
    if tr <= 1e-12:
        return 0.0, 0.0
    grad_ang = 0.5 * math.atan2(2 * jxy, jxx - jyy)
    coh = math.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / tr
    return (grad_ang + math.pi / 2) % math.pi, coh


def shape_pca(alpha):
    """Alpha-weighted second moments: major-axis angle (axial), elongation 1 - l2/l1, and the 3rd-moment skew
    along the major axis (sign: + = the tail is towards +axis)."""
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    m = alpha.astype(np.float64)
    s = m.sum()
    if s <= 0:
        return 0.0, 0.0, 0.0
    cx, cy = (m * xx).sum() / s, (m * yy).sum() / s
    dx, dy = xx - cx, yy - cy
    cxx, cyy, cxy = (m * dx * dx).sum() / s, (m * dy * dy).sum() / s, (m * dx * dy).sum() / s
    ev, evec = np.linalg.eigh(np.array([[cxx, cxy], [cxy, cyy]]))
    l2, l1 = ev
    vx, vy = evec[:, 1]
    ang = math.atan2(vy, vx) % math.pi
    proj = dx * math.cos(ang) + dy * math.sin(ang)
    skew = float((m * proj ** 3).sum() / s / max(l1, 1e-9) ** 1.5)
    return ang, float(1.0 - l2 / max(l1, 1e-12)), skew


def axial_diff_deg(a, b):
    d = abs((a - b) % math.pi)
    return math.degrees(min(d, math.pi - d))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def oriented_streaks(shape, theta, period_px_lo, period_px_hi, rng, ang_spread_deg=6.0):
    """Band-limited anisotropic noise whose crests run ALONG theta: spectral energy only at wave-vectors
    perpendicular to theta (+- ang_spread), |k| in [1/period_hi, 1/period_lo].  Returns zero-mean, unit-std field."""
    h, w = shape
    H, W = int(2 ** math.ceil(math.log2(h + 64))), int(2 ** math.ceil(math.log2(w + 64)))
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.fftfreq(W)[None, :]
    r = np.hypot(fx, fy)
    kang = np.arctan2(fy, fx)
    perp = theta + math.pi / 2
    d = np.abs(((kang - perp + math.pi / 2) % math.pi) - math.pi / 2)    # axial distance to the perpendicular
    sp = math.radians(ang_spread_deg)
    flo, fhi = 1.0 / period_px_hi, 1.0 / period_px_lo
    band = smoothstep(flo * 0.8, flo, r) * (1 - smoothstep(fhi, fhi * 1.15, r))
    filt = band * np.exp(-0.5 * (d / sp) ** 2)
    noise = rng.standard_normal((H, W))
    f = np.real(np.fft.ifft2(np.fft.fft2(noise) * filt))[:h, :w]
    f -= f.mean()
    sd = f.std()
    return f / sd if sd > 0 else f


def dome_profile(dist_in, scale):
    """The NEGATIVE control: a dome (thickest in the centre)."""
    return smoothstep(0.0, scale, dist_in)


def edge_orientation_weight(nx, ny, theta, conf, w_end=1.0, w_side=0.8, w_floor=0.3):
    """Rim weight from the outward boundary normal (nx, ny): ends (normal along the smear) w_end, side edges
    (normal across) w_side; blended to a constant isotropic 0.8 as confidence -> 0."""
    c2 = (nx * math.cos(theta) + ny * math.sin(theta)) ** 2
    s2 = 1.0 - c2
    aniso = w_floor + (1 - w_floor) * np.maximum(w_end * c2, w_side * s2)
    return conf * aniso + (1 - conf) * 0.8, c2


# ------------------------------------------------------------------ tests shared by gv2_validate.py and the harness
def ridge_test(G, rim, centre, outer, min_px=20):
    """The ridge criterion: mean G on the crest band is a LOCAL MINIMUM (below the centre AND below the outer flank).
    Returns None if a region is too small to judge."""
    if rim.sum() < min_px or centre.sum() < min_px or outer.sum() < min_px:
        return None
    r, c, o = float(G[rim].mean()), float(G[centre].mean()), float(G[outer].mean())
    return {"rim": r, "centre": c, "outer": o, "rim_lt_centre": r < c, "crest_local_min": r < c and r < o}


def orientation_error(field, mask, theta, sigma_d=0.8, hp_sigma=None):
    """Axial error (deg) between the structure-tensor line angle of `field` over `mask` and theta (radians)."""
    ang, coh = structure_tensor_angle(field, mask, sigma_d=sigma_d, hp_sigma=hp_sigma)
    return axial_diff_deg(ang, theta), coh


def r_identical(live_rgb, new_rgb):
    return live_rgb.shape == new_rgb.shape and bool(np.array_equal(live_rgb[..., 0], new_rgb[..., 0]))
