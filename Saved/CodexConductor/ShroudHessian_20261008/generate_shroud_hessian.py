"""Offline P22 texture preparation: DRY -> APPLY -> REVERT.

No Unreal imports are performed here.  The source is Fuser's image 1 (weave)
and images 3..8 (one non-tiling stain field per shroud).  APPLY is deliberately
guarded and writes only beside this script.  Existing generated files are copied
to Backups/PreShroudHessianPrep-<run> before the first output is replaced.

Tint encoding (sRGB PNG): neutral is RGB 1.0 (white); the material multiplies
the sampled tint into the weave BaseColor.  Values cannot brighten the weave.
Mask encoding (linear RGBA PNG): R=wet/greasy amount, G=soot amount,
B=holes/darns (zero: not reliably separable), A=one.

The stain is blurred in linear light with sigma ~= 0.55 of the measured weave
period.  Validation compares FFT energy in a weave-frequency annulus before and
after extraction, tide-line gradient p95 against the same de-woven reference,
and RGB neutrality on the robust plain-cloth sample.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
DEFAULT_INPUT_CANDIDATES = (
    PROJECT / "Saved/CodexConductor/fuser_specs/hessian_stains_20261008",
    Path("E:/PussStage/Saved/CodexConductor/fuser_specs/hessian_stains_20261008"),
)
GENERATED_PREFIXES = ("T_Shroud_", "Preview_", "Shroud_Hessian_")
MANIFEST = HERE / "shroud_hessian_prep_manifest.json"
REPORT = HERE / "shroud_hessian_validation.json"
CONTACT = HERE / "Shroud_Hessian_ContactSheet.png"
CONFIRM = "APPLY SHROUDHESSIAN PREP"
REVERT_CONFIRM = "REVERT SHROUDHESSIAN PREP"
STAIN_IDS = tuple(range(3, 9))
NORMAL_STRENGTH = 4.0
PREVIEW_WEAVE_TILES = 8
EDGE_UNSHARP_AMOUNT = 2.0


class PrepError(RuntimeError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise PrepError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_input_dir(explicit: str | None) -> Path:
    choices = (Path(explicit),) if explicit else DEFAULT_INPUT_CANDIDATES
    for p in choices:
        if p.is_dir():
            return p.resolve()
    raise PrepError("INPUT_DIR_MISSING|" + "|".join(str(p) for p in choices))


def source_files(input_dir: Path) -> tuple[Path, dict[int, Path]]:
    weave = sorted(input_dir.glob("hessian-stains-1-*.jpg"))
    require(len(weave) == 1, f"WEAVE_SOURCE_COUNT|{len(weave)}")
    stains: dict[int, Path] = {}
    for number in STAIN_IDS:
        hits = sorted(input_dir.glob(f"hessian-stains-{number}-*.jpg"))
        require(len(hits) == 1, f"STAIN_SOURCE_COUNT|{number}|{len(hits)}")
        stains[number] = hits[0]
    forbidden = sorted(input_dir.glob("hessian-stains-2-*.jpg"))
    require(len(forbidden) == 1, "REJECTED_TILE_2_MISSING (the rejected comparison must remain identifiable)")
    return weave[0], stains


def srgb_to_linear(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, np.float32) / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(a: np.ndarray) -> np.ndarray:
    a = np.clip(a, 0.0, 1.0)
    s = np.where(a <= 0.0031308, 12.92 * a, 1.055 * np.power(a, 1.0 / 2.4) - 0.055)
    return np.clip(np.rint(s * 255.0), 0, 255).astype(np.uint8)


def blur_channel(a: np.ndarray, radius: float) -> np.ndarray:
    # Pillow 12's GaussianBlur rejects mode F; scipy keeps the calculation in
    # linear-light float and uses reflection at the image edge.
    return gaussian_filter(np.asarray(a, np.float32), sigma=float(radius), mode="reflect")


def blur_rgb(a: np.ndarray, radius: float) -> np.ndarray:
    return np.stack([blur_channel(a[..., c], radius) for c in range(3)], axis=-1)


def luminance(a: np.ndarray) -> np.ndarray:
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def center_crop(a: np.ndarray, maximum: int = 1024) -> np.ndarray:
    h, w = a.shape[:2]
    side = min(h, w, maximum)
    y, x = (h - side) // 2, (w - side) // 2
    return a[y:y + side, x:x + side]


def fft_band_energy(gray: np.ndarray, cycles_per_px: float) -> float:
    """Mean windowed FFT power in a broad annulus around the weave frequency."""
    a = center_crop(np.asarray(gray, np.float32), 1024)
    h, w = a.shape
    win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    f = np.fft.fftshift(np.fft.fft2((a - float(a.mean())) * win))
    fy = np.fft.fftshift(np.fft.fftfreq(h))[:, None]
    fx = np.fft.fftshift(np.fft.fftfreq(w))[None, :]
    r = np.sqrt(fx * fx + fy * fy)
    band = (r >= cycles_per_px * 0.65) & (r <= cycles_per_px * 1.55)
    return float(np.mean(np.abs(f[band]) ** 2))


def estimate_weave_period(weave_linear: np.ndarray) -> float:
    """Dominant fibre repeat from the tile, constrained to 3..40 pixels."""
    a = center_crop(luminance(weave_linear), 1024)
    h, w = a.shape
    win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    power = np.abs(np.fft.fftshift(np.fft.fft2((a - a.mean()) * win))) ** 2
    fy = np.fft.fftshift(np.fft.fftfreq(h))[:, None]
    fx = np.fft.fftshift(np.fft.fftfreq(w))[None, :]
    r = np.sqrt(fx * fx + fy * fy)
    valid = (r >= 1.0 / 40.0) & (r <= 1.0 / 3.0)
    # Sum radial bins; this is less brittle than taking one compression/JPEG peak.
    bins = np.linspace(1.0 / 40.0, 1.0 / 3.0, 220)
    idx = np.digitize(r[valid], bins)
    sums = np.bincount(idx, weights=power[valid], minlength=len(bins) + 1)
    counts = np.bincount(idx, minlength=len(bins) + 1)
    means = sums / np.maximum(counts, 1)
    best = int(np.argmax(means[1:len(bins)]) + 1)
    freq = float((bins[best - 1] + bins[min(best, len(bins) - 1)]) * 0.5)
    return 1.0 / freq


def dominant_plain_colour(smooth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Robust dominant high-value cloth cluster; returns neutral RGB and sample mask."""
    h, w, _ = smooth.shape
    step = max(1, int(math.sqrt((h * w) / 60000.0)))
    small = smooth[::step, ::step]
    flat = small.reshape(-1, 3)
    lum = luminance(flat)
    chroma = flat / np.maximum(flat.sum(axis=1, keepdims=True), 1e-5)
    feat = np.column_stack((chroma * 2.2, lum[:, None]))
    # Deterministic quantile initialisation; no optional sklearn dependency.
    order = np.argsort(lum)
    seeds = feat[order[np.linspace(0, len(order) - 1, 8, dtype=int)]].copy()
    labels = np.zeros(len(feat), np.int32)
    for _ in range(14):
        dist = ((feat[:, None, :] - seeds[None, :, :]) ** 2).sum(axis=2)
        labels = np.argmin(dist, axis=1)
        for k in range(len(seeds)):
            hit = feat[labels == k]
            if len(hit):
                seeds[k] = np.median(hit, axis=0)
    scores = []
    for k in range(len(seeds)):
        hit = labels == k
        count = int(hit.sum())
        if not count:
            scores.append(-1.0)
            continue
        ml = float(np.median(lum[hit]))
        sat = float(np.median(np.max(chroma[hit], axis=1) - np.min(chroma[hit], axis=1)))
        scores.append(count * (0.2 + ml) ** 2 / (0.04 + sat))
    k = int(np.argmax(scores))
    cluster = flat[labels == k]
    cluster_lum = luminance(cluster)
    bright = cluster[cluster_lum >= np.percentile(cluster_lum, 55)]
    neutral = np.median(bright if len(bright) else cluster, axis=0)
    # Full-resolution sample around that colour, then retain its closest 20%.
    ratio = smooth / np.maximum(neutral, 1e-4)
    dist = np.sqrt(np.mean((ratio - 1.0) ** 2, axis=2))
    sample = dist <= np.percentile(dist, 20.0)
    return neutral.astype(np.float32), sample


def gradient_p95(gray: np.ndarray, sample: np.ndarray | None = None) -> float:
    gy, gx = np.gradient(np.asarray(gray, np.float32))
    g = np.hypot(gx, gy)
    if sample is not None and np.any(sample):
        g = g[sample]
    return float(np.percentile(g, 95.0))


def extract_stain(source: np.ndarray, period: float) -> tuple[np.ndarray, np.ndarray, dict]:
    linear = srgb_to_linear(source)
    sigma = max(2.5, period * 0.55)
    smooth_base = blur_rgb(linear, sigma)
    # Restore the large stain/tide-line transitions without restoring the
    # removed weave band.  Both terms are already de-woven.
    smooth = np.clip(smooth_base + EDGE_UNSHARP_AMOUNT *
                     (smooth_base - blur_rgb(smooth_base, sigma * 0.70)), 0.0, 1.0)
    neutral, plain0 = dominant_plain_colour(smooth)
    ratio = smooth / np.maximum(neutral, 1e-4)
    # Make the robust plain-cloth sample exactly neutral before the one-sided clamp.
    correction = np.median(ratio[plain0], axis=0)
    ratio = ratio / np.maximum(correction, 1e-4)
    tint = np.clip(ratio, 0.0, 1.0)
    dist = np.sqrt(np.mean((tint - 1.0) ** 2, axis=2))
    plain = dist <= np.percentile(dist, 20.0)

    tint_lum = luminance(tint)
    dark = np.clip((1.0 - tint_lum - 0.025) / 0.55, 0.0, 1.0)
    chroma = np.max(tint, axis=2) - np.min(tint, axis=2)
    colour = np.clip((chroma - 0.018) / 0.30, 0.0, 1.0)
    amount = np.clip(np.maximum(dark, colour * 0.85), 0.0, 1.0)
    soot = np.clip(dark * (1.0 - np.clip(chroma / 0.18, 0.0, 1.0)) * 1.15, 0.0, 1.0)
    mask = np.stack((amount, soot, np.zeros_like(amount), np.ones_like(amount)), axis=-1)

    source_energy = fft_band_energy(luminance(linear), 1.0 / period)
    output_energy = fft_band_energy(tint_lum, 1.0 / period)
    # Edge comparison excludes nearly neutral field and saturated stain interiors.
    edge_zone = (amount >= 0.08) & (amount <= 0.80)
    # A separately computed, still de-woven baseline (0.75 sigma) is the edge
    # reference; unlike comparing the output to itself, this can catch blur.
    edge_reference = blur_rgb(linear, sigma * 0.75)
    ref_ratio = np.clip(edge_reference / np.maximum(neutral * correction, 1e-4), 0.0, 1.0)
    ref_grad = gradient_p95(luminance(ref_ratio), edge_zone)
    out_grad = gradient_p95(tint_lum, edge_zone)
    plain_rgb = tint[plain].mean(axis=0)
    metrics = {
        "weave_period_px": float(period),
        "lowpass_sigma_px": float(sigma),
        "edge_unsharp_amount": EDGE_UNSHARP_AMOUNT,
        "fft_source_energy": source_energy,
        "fft_output_energy": output_energy,
        "fft_reduction_x": source_energy / max(output_energy, 1e-30),
        "edge_gradient_reference_p95": ref_grad,
        "edge_gradient_output_p95": out_grad,
        "edge_sharpness_retained": out_grad / max(ref_grad, 1e-12),
        "unstained_mean_rgb": [float(x) for x in plain_rgb],
        "unstained_max_abs_from_one": float(np.max(np.abs(plain_rgb - 1.0))),
        "neutral_linear_rgb": [float(x) for x in neutral],
        "wet_mask_mean": float(amount.mean()),
        "soot_mask_mean": float(soot.mean()),
        "holes_darns_channel": "zero_not_separable",
    }
    return tint, mask, metrics


def weave_normal(weave_linear: np.ndarray, strength: float = NORMAL_STRENGTH) -> np.ndarray:
    height = blur_channel(luminance(weave_linear), 0.55)
    lo, hi = np.percentile(height, (1.0, 99.0))
    height = np.clip((height - lo) / max(float(hi - lo), 1e-6), 0.0, 1.0)
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
    # DirectX tangent-space convention for Unreal: +Y points down texture V.
    n = np.stack((-dx * strength, dy * strength, np.ones_like(height)), axis=-1)
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    return np.clip(np.rint((n * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)


def tile_to_shape(tile: Image.Image, size: tuple[int, int], tiles_v: int = PREVIEW_WEAVE_TILES) -> Image.Image:
    w, h = size
    cell = max(1, int(round(h / tiles_v)))
    t = tile.resize((cell, cell), Image.Resampling.LANCZOS)
    out = Image.new("RGB", size)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            out.paste(t, (x, y))
    return out


def composite(weave: Image.Image, tint: Image.Image, size: tuple[int, int], rotate180: bool = False) -> Image.Image:
    base = tile_to_shape(weave, size)
    layer = tint.resize(size, Image.Resampling.LANCZOS)
    if rotate180:
        layer = layer.transpose(Image.Transpose.ROTATE_180)
    a = np.asarray(base, np.float32) / 255.0
    b = np.asarray(layer, np.float32) / 255.0
    return Image.fromarray(np.clip(np.rint(a * b * 255.0), 0, 255).astype(np.uint8), "RGB")


def preview_set(number: int, weave: Image.Image, tint: Image.Image) -> list[Path]:
    full_size = (1456, 720)
    full = composite(weave, tint, full_size)
    rotated = composite(weave, tint, full_size, rotate180=True)
    # 1:1 means source stain pixels and source weave pixels are multiplied without resampling.
    source_composite = composite(weave, tint, tint.size)
    crop = 1024
    x0, y0 = (tint.width - crop) // 2, (tint.height - crop) // 2
    center = source_composite.crop((x0, y0, x0 + crop, y0 + crop))
    ox = (number * 233) % (tint.width - crop + 1)
    oy = (number * 97) % (tint.height - crop + 1)
    offset = source_composite.crop((ox, oy, ox + crop, oy + crop))
    outputs = [
        (HERE / f"Preview_{number:02d}_1to1_Center.png", center),
        (HERE / f"Preview_{number:02d}_1to1_Offset.png", offset),
        (HERE / f"Preview_{number:02d}_FullShroud.png", full),
        (HERE / f"Preview_{number:02d}_FullShroud_Rot180.png", rotated),
    ]
    for path, image in outputs:
        image.save(path, optimize=True)
    return [p for p, _ in outputs]


def contact_sheet(full_previews: list[tuple[int, Image.Image]]) -> None:
    thumb = (720, 356)
    margin, label_h = 18, 28
    sheet = Image.new("RGB", (margin * 4 + thumb[0] * 3, margin * 3 + (thumb[1] + label_h) * 2), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (number, image) in enumerate(full_previews):
        col, row = index % 3, index // 3
        x = margin + col * (thumb[0] + margin)
        y = margin + row * (thumb[1] + label_h + margin)
        sheet.paste(image.resize(thumb, Image.Resampling.LANCZOS), (x, y + label_h))
        draw.text((x, y + 7), f"Stain {number:02d} | weave x tint | full shroud", fill=(235, 224, 192), font=font)
    sheet.save(CONTACT, optimize=True)


def generated_files() -> list[Path]:
    out = []
    for p in HERE.iterdir():
        if p.is_file() and (p.name.startswith(GENERATED_PREFIXES) or p in (MANIFEST, REPORT, CONTACT)):
            out.append(p)
    return sorted(set(out))


def backup_existing(run: str) -> tuple[Path, list[dict]]:
    backup = PROJECT / "Backups" / f"PreShroudHessianPrep-{run}"
    require(not backup.exists(), f"BACKUP_EXISTS|{backup}")
    backup.mkdir(parents=True)
    rows = []
    for src in generated_files():
        dst = backup / src.name
        shutil.copy2(src, dst)
        require(sha256(src) == sha256(dst), f"BACKUP_HASH|{src}")
        rows.append({"path": str(src.relative_to(PROJECT)), "sha256": sha256(src)})
    (backup / "backup_manifest.json").write_text(json.dumps({"run": run, "files": rows}, indent=2), encoding="utf-8")
    return backup, rows


def plan(input_dir: Path) -> dict:
    weave, stains = source_files(input_dir)
    return {
        "input_dir": str(input_dir),
        "weave": {"path": str(weave), "sha256": sha256(weave)},
        "rejected_tile_2": str(next(input_dir.glob("hessian-stains-2-*.jpg"))),
        "stains": {str(k): {"path": str(v), "sha256": sha256(v)} for k, v in stains.items()},
        "outputs": {
            "weave": ["T_Shroud_Weave_BC.png", "T_Shroud_Weave_N.png"],
            "per_stain": ["T_Shroud_Stain_0N_Tint.png", "T_Shroud_Stain_0N_Mask.png", "4 previews"],
            "contact_sheet": CONTACT.name,
        },
    }


def validation_failures(metrics: dict) -> list[str]:
    failures = []
    for number, row in metrics.items():
        if row["fft_reduction_x"] < 10.0:
            failures.append(f"FFT_LT_10X|{number}|{row['fft_reduction_x']:.3f}")
        if row["edge_sharpness_retained"] < 0.90:
            failures.append(f"EDGE_LT_90PCT|{number}|{row['edge_sharpness_retained']:.3f}")
        if row["unstained_max_abs_from_one"] > 0.03:
            failures.append(f"NEUTRAL_GT_003|{number}|{row['unstained_max_abs_from_one']:.5f}")
    return failures


def run_apply(input_dir: Path, run: str) -> dict:
    p = plan(input_dir)
    backup, backed_up = backup_existing(run)
    weave_path, stains = source_files(input_dir)
    weave_rgb = np.asarray(Image.open(weave_path).convert("RGB"))
    weave_linear = srgb_to_linear(weave_rgb)
    period = estimate_weave_period(weave_linear)
    require(3.0 <= period <= 40.0, f"WEAVE_PERIOD|{period}")
    Image.fromarray(weave_rgb, "RGB").save(HERE / "T_Shroud_Weave_BC.png", optimize=True)
    Image.fromarray(weave_normal(weave_linear), "RGB").save(HERE / "T_Shroud_Weave_N.png", optimize=True)

    metrics, preview_rows = {}, []
    weave_im = Image.fromarray(weave_rgb, "RGB")
    for number, src in stains.items():
        rgb = np.asarray(Image.open(src).convert("RGB"))
        tint_linear, packed_mask, row = extract_stain(rgb, period)
        tint_u8 = linear_to_srgb(tint_linear)
        mask_u8 = np.clip(np.rint(packed_mask * 255.0), 0, 255).astype(np.uint8)
        tint_path = HERE / f"T_Shroud_Stain_{number:02d}_Tint.png"
        mask_path = HERE / f"T_Shroud_Stain_{number:02d}_Mask.png"
        Image.fromarray(tint_u8, "RGB").save(tint_path, optimize=True)
        Image.fromarray(mask_u8, "RGBA").save(mask_path, optimize=True)
        previews = preview_set(number, weave_im, Image.fromarray(tint_u8, "RGB"))
        preview_rows.append((number, Image.open(HERE / f"Preview_{number:02d}_FullShroud.png").convert("RGB")))
        row.update({"source": str(src), "tint": tint_path.name, "mask": mask_path.name,
                    "previews": [x.name for x in previews]})
        metrics[f"{number:02d}"] = row
    contact_sheet(preview_rows)

    failures = validation_failures(metrics)
    validation = {
        "run": run,
        "status": "PASS" if not failures else "FAIL",
        "definitions": {
            "fft": "windowed luminance FFT annulus 0.65..1.55 x the tile's dominant weave frequency",
            "edge": "p95 gradient in wet-mask 0.08..0.80 versus an independent 0.75-sigma de-woven reference",
            "unstained": "mean RGB of the closest 20 percent to the robust dominant plain-cloth colour",
        },
        "normal": {"source": weave_path.name, "height": "linear luminance, 1..99 percentile normalised",
                   "strength": NORMAL_STRENGTH, "format": "DirectX tangent-space RGB"},
        "metrics": metrics,
        "failures": failures,
    }
    REPORT.write_text(json.dumps(validation, indent=2), encoding="utf-8")
    require(not failures, "VALIDATION_FAILED|" + json.dumps(failures))

    files = [{"path": x.name, "sha256": sha256(x), "bytes": x.stat().st_size} for x in generated_files()
             if x not in (MANIFEST,)]
    manifest = {"run": run, "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(), "plan": p,
                "backup": str(backup.relative_to(PROJECT)), "backed_up": backed_up,
                "encoding": {"tint": "sRGB multiply; white=neutral", "mask": "linear RGBA; R=wet, G=soot, B=0, A=1"},
                "files": files}
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def run_revert(run: str) -> dict:
    require(MANIFEST.is_file(), "NO_MANIFEST")
    rec = json.loads(MANIFEST.read_text(encoding="utf-8"))
    backup = PROJECT / rec["backup"]
    backup_manifest = backup / "backup_manifest.json"
    require(backup_manifest.is_file(), f"BACKUP_MANIFEST_MISSING|{backup_manifest}")
    old = json.loads(backup_manifest.read_text(encoding="utf-8"))
    current_names = [Path(row["path"]).name for row in rec.get("files", [])] + [MANIFEST.name]
    old_names = {Path(row["path"]).name for row in old.get("files", [])}
    # No permanent deletion: generated files absent before APPLY move into a recoverable Reverted folder.
    retired = PROJECT / "Backups" / f"RevertedShroudHessianPrep-{run}"
    retired.mkdir(parents=True, exist_ok=False)
    for name in current_names:
        src = HERE / name
        if src.exists() and name not in old_names:
            shutil.move(str(src), str(retired / name))
    for row in old.get("files", []):
        src, dst = backup / Path(row["path"]).name, PROJECT / row["path"]
        require(src.is_file() and sha256(src) == row["sha256"], f"BACKUP_BAD|{src}")
        shutil.copy2(src, dst)
    return {"run": run, "restored": len(old.get("files", [])), "retired": str(retired.relative_to(PROJECT))}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("DRY", "APPLY", "REVERT"))
    ap.add_argument("--input-dir")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--run", default=_dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.mode == "DRY":
            result = plan(find_input_dir(args.input_dir))
        elif args.mode == "APPLY":
            require(args.confirm == CONFIRM, f"CONFIRM|expected {CONFIRM!r}")
            result = run_apply(find_input_dir(args.input_dir), args.run)
        else:
            require(args.confirm == REVERT_CONFIRM, f"CONFIRM|expected {REVERT_CONFIRM!r}")
            result = run_revert(args.run)
        print(f"SHROUD_HESSIAN_PREP_{args.mode}_OK|run={args.run}|{json.dumps(result, default=str)}")
        return 0
    except Exception as exc:  # fail closed; never print an OK marker
        print(f"SHROUD_HESSIAN_PREP_FAILED|run={args.run}|mode={args.mode}|{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
