"""Offline paper-proscenium fringe repair.

Reads the three immutable production SkinColor PNGs, clamps green excess only
inside a narrow alpha-edge band, and colour-dilates corrected RGB beneath zero
alpha for safer mip filtering.  Outputs are always new files.  Alpha erosion is
available but defaults to zero because the Flat V3 Front material is opaque and
the existing alpha is registration metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


ASSETS = {
    "PRO_side_L": "PaperProsc_Side_L",
    "PRO_side_R": "PaperProsc_Side_R",
    "PRO_valance_C": "PaperProsc_Valance_C",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def edge_metrics(rgba: np.ndarray, width: int) -> dict:
    rgb = rgba[:, :, :3].astype(np.int16)
    inside = rgba[:, :, 3] > 0
    distance = ndimage.distance_transform_edt(inside)
    band = inside & (distance <= width)
    excess = rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])
    values = excess[band]
    return {
        "band_width_px": width,
        "band_texels": int(values.size),
        "green_excess_gt_8_texels": int(np.count_nonzero(values > 8)),
        "green_excess_gt_20_texels": int(np.count_nonzero(values > 20)),
        "green_excess_gt_20_percent": round(float(np.mean(values > 20) * 100.0), 6),
        "green_excess_mean": round(float(np.mean(values)), 6),
        "green_excess_p99": round(float(np.percentile(values, 99)), 6),
        "global_green_excess_gt_20_texels": int(np.count_nonzero(inside & (excess > 20))),
    }


def repair_rgba(
    rgba: np.ndarray,
    despill_width_px: int = 32,
    dilate_px: int = 32,
    alpha_erode_px: int = 0,
    green_excess_threshold: int = 8,
) -> tuple[np.ndarray, dict]:
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("RGBA_REQUIRED")
    if min(despill_width_px, dilate_px, alpha_erode_px, green_excess_threshold) < 0:
        raise ValueError("NONNEGATIVE_PARAMETERS_REQUIRED")
    result = rgba.copy()
    rgb = result[:, :, :3]
    inside = result[:, :, 3] > 0
    if not inside.any() or inside.all():
        raise ValueError("ALPHA_MUST_HAVE_INSIDE_AND_OUTSIDE")

    inside_distance = ndimage.distance_transform_edt(inside)
    green_cap = np.maximum(rgb[:, :, 0], rgb[:, :, 2]).astype(np.int16)
    green = rgb[:, :, 1].astype(np.int16)
    candidate = inside & (green > green_cap + green_excess_threshold)
    labels, _ = ndimage.label(candidate, structure=np.ones((3, 3), dtype=np.uint8))
    seed_labels = np.unique(labels[candidate & (inside_distance <= min(8, despill_width_px))])
    seed_labels = seed_labels[seed_labels > 0]
    connected_residue = candidate & np.isin(labels, seed_labels)
    despill = candidate & ((inside_distance <= despill_width_px) | connected_residue)
    rgb[:, :, 1][despill] = green_cap[despill].astype(np.uint8)

    # Nearest corrected opaque colour is copied under alpha. Alpha stays zero,
    # so the padding affects texture filtering only, not the silhouette metadata.
    outside_distance, nearest = ndimage.distance_transform_edt(
        ~inside, return_indices=True
    )
    padding = (~inside) & (outside_distance <= dilate_px)
    for channel in range(3):
        plane = rgb[:, :, channel]
        plane[padding] = plane[nearest[0][padding], nearest[1][padding]]

    if alpha_erode_px:
        eroded = ndimage.binary_erosion(inside, iterations=alpha_erode_px)
        result[:, :, 3] = eroded.astype(np.uint8) * 255

    return result, {
        "despilled_texels": int(np.count_nonzero(despill)),
        "edge_connected_despilled_texels": int(np.count_nonzero(connected_residue)),
        "padded_transparent_texels": int(np.count_nonzero(padding)),
        "alpha_eroded_texels": int(np.count_nonzero(inside) - np.count_nonzero(result[:, :, 3])),
    }


def crop_center(rgba: np.ndarray, band_width: int) -> tuple[int, int]:
    rgb = rgba[:, :, :3].astype(np.int16)
    inside = rgba[:, :, 3] > 0
    distance = ndimage.distance_transform_edt(inside)
    excess = rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])
    score = np.where(inside & (distance <= band_width), excess, -10000)
    y, x = np.unravel_index(int(np.argmax(score)), score.shape)
    return int(x), int(y)


def checker_composite(rgba: np.ndarray) -> Image.Image:
    h, w = rgba.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    checker = np.where(((xx // 16 + yy // 16) & 1)[:, :, None], 184, 224)
    checker = np.repeat(checker, 3, axis=2).astype(np.float32)
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    out = rgba[:, :, :3].astype(np.float32) * alpha + checker * (1.0 - alpha)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def make_crop(rgba: np.ndarray, centre: tuple[int, int], size: int) -> Image.Image:
    image = checker_composite(rgba)
    x, y = centre
    half = size // 2
    return image.crop((x - half, y - half, x - half + size, y - half + size))


def labelled(image: Image.Image, text: str) -> Image.Image:
    out = Image.new("RGB", (image.width, image.height + 28), (28, 28, 28))
    out.paste(image, (0, 28))
    ImageDraw.Draw(out).text((8, 7), text, fill=(245, 245, 245))
    return out


def run(args: argparse.Namespace) -> dict:
    source_root = args.source_root.resolve()
    output = args.output_dir.resolve()
    texture_dir = output / "textures"
    crop_dir = output / "crops"
    texture_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    contact_rows = []
    for owner, source_name in ASSETS.items():
        source = source_root / ("Build/PaperProsc_%s/skin/T_PaperProsc_%s_SkinColor.png" % (
            source_name.removeprefix("PaperProsc_"), source_name.removeprefix("PaperProsc_")
        ))
        if not source.is_file():
            raise FileNotFoundError(source)
        before = np.asarray(Image.open(source).convert("RGBA"))
        source_inside = before[:, :, 3] > 0
        source_outer_distance = ndimage.distance_transform_edt(~source_inside)
        source_near_transparent = (~source_inside) & (source_outer_distance <= args.dilate_px)
        after, counts = repair_rgba(
            before,
            args.despill_width_px,
            args.dilate_px,
            args.alpha_erode_px,
            args.green_excess_threshold,
        )
        stem = source.stem + "_FringeFix_v1"
        target = texture_dir / (stem + ".png")
        Image.fromarray(after, "RGBA").save(target, optimize=True)
        centre = crop_center(before, args.despill_width_px)
        before_crop = crop_dir / (owner + "_BEFORE.png")
        after_crop = crop_dir / (owner + "_AFTER.png")
        b = labelled(make_crop(before, centre, args.crop_size), owner + " BEFORE")
        a = labelled(make_crop(after, centre, args.crop_size), owner + " AFTER")
        b.save(before_crop, optimize=True)
        a.save(after_crop, optimize=True)
        pair = Image.new("RGB", (b.width * 2, b.height), (20, 20, 20))
        pair.paste(b, (0, 0)); pair.paste(a, (b.width, 0))
        pair_path = crop_dir / (owner + "_BEFORE_AFTER.png")
        pair.save(pair_path, optimize=True)
        contact_rows.append(pair)
        rows.append({
            "owner": owner,
            "source": str(source),
            "source_sha256": sha256(source),
            "output": str(target),
            "output_sha256": sha256(target),
            "size_px": [int(after.shape[1]), int(after.shape[0])],
            "crop_center_px": list(centre),
            "before_crop": str(before_crop),
            "after_crop": str(after_crop),
            "pair_crop": str(pair_path),
            "before": edge_metrics(before, args.despill_width_px),
            "after": edge_metrics(after, args.despill_width_px),
            "source_diagnosis": {
                "alpha_unique_values": [int(x) for x in np.unique(before[:, :, 3])],
                "partial_alpha_texels": int(np.count_nonzero((before[:, :, 3] > 0) & (before[:, :, 3] < 255))),
                "near_edge_transparent_nonblack_rgb_texels": int(np.count_nonzero(
                    source_near_transparent & np.any(before[:, :, :3] != 0, axis=2)
                )),
            },
            **counts,
        })
    sheet = Image.new("RGB", (contact_rows[0].width, sum(x.height for x in contact_rows)), (20, 20, 20))
    y = 0
    for row in contact_rows:
        sheet.paste(row, (0, y)); y += row.height
    sheet_path = crop_dir / "PAPERPROSC_FRINGE_BEFORE_AFTER.png"
    sheet.save(sheet_path, optimize=True)
    manifest = {
        "schema_version": 1,
        "tool": "fix_paperprosc_fringe",
        "operation": "new-file narrow edge despill, topology-following keyed-residue despill, and under-alpha colour dilation",
        "parameters": {
            "despill_width_px": args.despill_width_px,
            "dilate_px": args.dilate_px,
            "alpha_erode_px": args.alpha_erode_px,
            "green_excess_threshold": args.green_excess_threshold,
        },
        "alpha_policy": "unchanged" if args.alpha_erode_px == 0 else "eroded",
        "contact_sheet": str(sheet_path),
        "rows": rows,
    }
    manifest_path = output / "fringe_fix_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("PAPERPROSC_FRINGE_BUILD_OK|assets=%d|manifest=%s" % (len(rows), manifest_path))
    return manifest


def parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, default=Path(r"E:\PussStage\DerivedAssets\StageFront_PaperProscenium"))
    p.add_argument("--output-dir", type=Path, default=here)
    p.add_argument("--despill-width-px", type=int, default=32)
    p.add_argument("--dilate-px", type=int, default=32)
    p.add_argument("--alpha-erode-px", type=int, choices=(0, 1, 2), default=0)
    p.add_argument("--green-excess-threshold", type=int, default=8)
    p.add_argument("--crop-size", type=int, default=320)
    return p


if __name__ == "__main__":
    run(parser().parse_args())
