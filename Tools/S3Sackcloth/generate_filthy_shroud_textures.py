"""Deterministic, tileable 2K filthy-shroud textures for P1 (8 Oct 2026).

Offline only: PIL/numpy, no Unreal and no Blender. Modes:
  DRY     validate args and print the exact output/backup plan; writes nothing.
  APPLY   create a PreP1FilthyShroud backup record, then write three BaseColor/Roughness/NormalDX sets,
          a preview sheet and manifest. Refuses if the target exists.
  REVERT  hash-check the generated set, then MOVE it to Backups/RevertedP1FilthyShroud-<run> (no deletion).

The maps are periodic by construction (FFT fields + integer-frequency weave). Normal green follows DirectX/UE.
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

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "DerivedAssets" / "S3Sackcloth" / "P1_FilthyShroud_20261008"
RECORD = ROOT / "Saved" / "CodexConductor" / "P1MetaFabric_20261008" / "filthy_shroud_record.json"
VARIANTS = {
    "A_ash_grey": {
        "seed": 202610081, "cloth": (0.34, 0.32, 0.28), "dirt": (0.105, 0.085, 0.060),
        "mildew": (0.13, 0.15, 0.10), "rust": (0.25, 0.095, 0.035), "oil": 0.20,
    },
    "B_damp_brown": {
        "seed": 202610082, "cloth": (0.31, 0.265, 0.205), "dirt": (0.075, 0.055, 0.035),
        "mildew": (0.105, 0.125, 0.075), "rust": (0.30, 0.105, 0.030), "oil": 0.34,
    },
    "C_soot_salt": {
        "seed": 202610083, "cloth": (0.30, 0.30, 0.275), "dirt": (0.055, 0.052, 0.047),
        "mildew": (0.10, 0.12, 0.09), "rust": (0.23, 0.085, 0.032), "oil": 0.43,
    },
}


class TextureError(RuntimeError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise TextureError(message)


def run_id(prefix: str = "P1SHROUD") -> str:
    return prefix + "-" + _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def periodic_noise(size: int, rng: np.random.Generator, cycles: float) -> np.ndarray:
    """Periodic low-pass Gaussian field, normalized to 0..1."""
    white = rng.normal(0.0, 1.0, (size, size)).astype(np.float32)
    fy = np.fft.fftfreq(size).astype(np.float32)[:, None] * size
    fx = np.fft.rfftfreq(size).astype(np.float32)[None, :] * size
    filt = np.exp(-0.5 * (fx * fx + fy * fy) / max(cycles * cycles, 1e-6)).astype(np.float32)
    field = np.fft.irfft2(np.fft.rfft2(white) * filt, s=(size, size)).astype(np.float32)
    field -= field.min()
    field /= max(float(field.max()), 1e-8)
    return field


def soft_mask(field: np.ndarray, lo: float, hi: float) -> np.ndarray:
    t = np.clip((field - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def normal_dx(height: np.ndarray, strength: float = 5.0) -> np.ndarray:
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * strength
    # Tangent-space normal; DirectX/UE convention negates the OpenGL-style Y derivative.
    nx, ny, nz = -dx, dy, np.ones_like(height)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack((nx * inv * 0.5 + 0.5, ny * inv * 0.5 + 0.5, nz * inv * 0.5 + 0.5), axis=2)


def build_variant(size: int, spec: dict) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(int(spec["seed"]))
    macro = periodic_noise(size, rng, 7.0)
    blotch = periodic_noise(size, rng, 18.0)
    speck = periodic_noise(size, rng, 75.0)
    oil_field = periodic_noise(size, rng, 11.0)
    salt_field = periodic_noise(size, rng, 32.0)

    u = np.arange(size, dtype=np.float32) / float(size)
    warp = (macro - 0.5) * 0.13
    warp_threads = np.sin(2.0 * math.pi * (82.0 * u[None, :] + warp * 1.8))
    weft_threads = np.sin(2.0 * math.pi * (78.0 * u[:, None] - warp * 1.4))
    fine = 0.5 + 0.25 * warp_threads + 0.25 * weft_threads
    crossing = np.clip(0.5 + 0.5 * warp_threads * weft_threads, 0.0, 1.0)

    dirt = soft_mask(blotch, 0.43, 0.75) * (0.45 + 0.55 * soft_mask(speck, 0.40, 0.68))
    mildew = soft_mask(periodic_noise(size, rng, 14.0), 0.57, 0.78) * soft_mask(macro, 0.30, 0.70)
    rust = soft_mask(np.abs(periodic_noise(size, rng, 9.0) - 0.53), 0.10, 0.24)
    rust *= soft_mask(speck, 0.53, 0.78)
    oil = soft_mask(oil_field, 0.61, 0.80) * float(spec["oil"])
    salt = soft_mask(salt_field, 0.67, 0.86) * (1.0 - 0.45 * oil)

    cloth = np.array(spec["cloth"], dtype=np.float32)[None, None, :]
    dirt_c = np.array(spec["dirt"], dtype=np.float32)[None, None, :]
    mildew_c = np.array(spec["mildew"], dtype=np.float32)[None, None, :]
    rust_c = np.array(spec["rust"], dtype=np.float32)[None, None, :]
    base = cloth * (0.80 + 0.22 * macro[..., None]) * (0.89 + 0.16 * fine[..., None])
    base = base * (1.0 - 0.72 * dirt[..., None]) + dirt_c * (0.72 * dirt[..., None])
    base = base * (1.0 - 0.50 * mildew[..., None]) + mildew_c * (0.50 * mildew[..., None])
    base = base * (1.0 - 0.58 * rust[..., None]) + rust_c * (0.58 * rust[..., None])
    base *= 1.0 - 0.55 * oil[..., None]
    base += salt[..., None] * np.array((0.10, 0.095, 0.075), dtype=np.float32)
    base = np.clip(base, 0.012, 0.72)

    rough = 0.88 + 0.09 * (1.0 - crossing) + 0.04 * dirt + 0.03 * salt - 0.34 * oil
    rough = np.clip(rough, 0.54, 0.99)
    height = 0.50 + 0.105 * warp_threads + 0.095 * weft_threads + 0.035 * (speck - 0.5)
    height -= 0.035 * dirt + 0.022 * oil
    normal = normal_dx(height.astype(np.float32), strength=5.6)
    return {"BC": base, "R": rough, "N": normal}


def as_u8(a: np.ndarray) -> np.ndarray:
    return np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8)


def seam_metrics(a: np.ndarray) -> dict[str, float]:
    if a.ndim == 3:
        a = a.mean(axis=2)
    internal_x = np.abs(np.diff(a, axis=1)).mean()
    internal_y = np.abs(np.diff(a, axis=0)).mean()
    seam_x = np.abs(a[:, 0] - a[:, -1]).mean()
    seam_y = np.abs(a[0, :] - a[-1, :]).mean()
    baseline = max(float((internal_x + internal_y) * 0.5), 1e-8)
    return {"x": float(seam_x), "y": float(seam_y), "ratio": float(max(seam_x, seam_y) / baseline)}


def validate_args(mode: str, size: int, out: Path) -> None:
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE|" + mode)
    require(size >= 64 and size <= 4096 and size & (size - 1) == 0, "SIZE|must be power-of-two 64..4096")
    require(out.is_absolute(), "OUT|absolute path required")
    require(ROOT in out.parents, "OUT|must stay inside project root")


def write_set(out: Path, size: int) -> dict:
    files, stats = {}, {}
    thumbs: list[tuple[str, str, Image.Image]] = []
    for name, spec in VARIANTS.items():
        maps = build_variant(size, spec)
        files[name], stats[name] = {}, {}
        for kind, arr in maps.items():
            path = out / f"T_P1_Shroud_{name}_{kind}.png"
            image = Image.fromarray(as_u8(arr), "RGB" if arr.ndim == 3 else "L")
            image.save(path, optimize=True)
            files[name][kind] = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                                  "sha256": sha256(path), "mode": image.mode, "size": list(image.size)}
            stats[name][kind] = seam_metrics(arr)
            thumb = image.convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
            thumbs.append((name, kind, thumb))
    sheet = Image.new("RGB", (3 * 512, 3 * 552), (24, 22, 20))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for col, name in enumerate(VARIANTS):
        for row, kind in enumerate(("BC", "R", "N")):
            thumb = next(t for n, k, t in thumbs if n == name and k == kind)
            x, y = col * 512, row * 552
            sheet.paste(thumb, (x, y + 40))
            draw.text((x + 12, y + 10), f"{name} - {kind}", fill=(232, 226, 212), font=font)
    preview = out / "filthy_shroud_preview_sheet.png"
    sheet.save(preview, optimize=True)
    files["preview"] = {"path": preview.relative_to(ROOT).as_posix(), "bytes": preview.stat().st_size,
                        "sha256": sha256(preview), "mode": sheet.mode, "size": list(sheet.size)}
    return {"files": files, "seams": stats}


def apply(size: int, out: Path, run: str) -> dict:
    require(not out.exists(), "TARGET_EXISTS|" + str(out))
    require(not RECORD.exists(), "RECORD_EXISTS|run REVERT or choose a fresh versioned target")
    backup = ROOT / "Backups" / ("PreP1FilthyShroud-" + run)
    backup.mkdir(parents=True, exist_ok=False)
    pre = {"run": run, "target": str(out), "target_existed": False,
           "dirty_package_census": "not_applicable_offline", "named_outputs_only": True}
    (backup / "preflight.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    out.mkdir(parents=True, exist_ok=False)
    built = write_set(out, size)
    manifest = {"run": run, "mode": "APPLY", "size": size, "tileable": True, "normal_convention": "DirectX_UE",
                "variants": VARIANTS, "backup": str(backup), **built}
    require(all(v[k]["ratio"] < 4.0 for v in built["seams"].values() for k in ("BC", "R", "N")),
            "SEAM_GATE|ratio >= 4")
    mpath = out / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_sha256"] = sha256(mpath)
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def revert(out: Path, run: str) -> dict:
    require(RECORD.exists(), "NO_RECORD")
    rec = json.loads(RECORD.read_text(encoding="utf-8"))
    require(Path(rec["files"]["preview"]["path"]).name == "filthy_shroud_preview_sheet.png", "RECORD_SHAPE")
    recorded_out = (ROOT / rec["files"]["preview"]["path"]).resolve().parent
    require(out.exists() and out.resolve() == recorded_out, "TARGET_DRIFT")
    for group in rec["files"].values():
        rows = group.values() if "path" not in group else (group,)
        for row in rows:
            p = ROOT / row["path"]
            require(p.is_file() and sha256(p) == row["sha256"], "HASH_DRIFT|" + str(p))
    backup = ROOT / "Backups" / ("PreP1FilthyShroudRevert-" + run)
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(RECORD, backup / RECORD.name)
    moved = ROOT / "Backups" / ("RevertedP1FilthyShroud-" + run)
    require(not moved.exists(), "REVERT_TARGET_EXISTS")
    shutil.move(str(out), str(moved))
    result = {"run": run, "mode": "REVERT", "moved_to": str(moved), "recoverable": True}
    RECORD.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default="DRY", choices=("DRY", "APPLY", "REVERT"))
    p.add_argument("--size", type=int, default=2048)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = p.parse_args(argv)
    mode, out = a.mode.upper(), a.out.resolve()
    validate_args(mode, a.size, out)
    run = run_id()
    plan = {"run": run, "mode": mode, "size": a.size, "out": str(out), "variants": list(VARIANTS),
            "backup_prefix": "Backups/PreP1FilthyShroud-", "dirty_package_census": "not_applicable_offline"}
    if mode == "DRY":
        result = plan
    elif mode == "APPLY":
        result = apply(a.size, out, run)
    else:
        result = revert(out, run)
    print(f"P1SHROUD_{mode}_OK|run={run}|" + json.dumps({k: result[k] for k in result if k not in ("files", "variants")}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
