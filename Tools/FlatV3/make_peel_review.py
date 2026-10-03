#!/usr/bin/env python3
"""Create before | round 1 | round 2 Flat V3 peel comparisons at 1:1."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "DerivedAssets" / "FlatV3" / "Review_2026-10-03" / "peel"
REPRESENTATIVES = {
    "P04_coventry_ruin": ROOT / "DerivedAssets/FlatV3/Overnight/flats/P04_coventry_ruin_L_v1/skin/P04_coventry_ruin_L_v1_skin_manifest.json",
    "P01_roccoco": ROOT / "DerivedAssets/FlatV3/Overnight/Kept/flats/P01_L_1_roccoco_L/skin/P01_L_1_roccoco_L_skin_manifest.json",
    "P02_plant_set": ROOT / "DerivedAssets/FlatV3/Overnight/P02Sets/flats/P02_SET01_L/skin/P02_SET01_L_skin_manifest.json",
}
CROP_PX = 384
TILE_W = 384
TILE_H = 384
HEADER = 44


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load(path: Path) -> np.ndarray:
    value = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if value is None:
        raise RuntimeError(f"IMAGE_LOAD_FAIL|{path}")
    return value


def fit(image: np.ndarray, width: int, height: int) -> np.ndarray:
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(image, (max(1, int(image.shape[1] * scale)),
                                 max(1, int(image.shape[0] * scale))),
                         interpolation=cv2.INTER_AREA)
    canvas = np.full((height, width, 3), 28, np.uint8)
    x = (width - resized.shape[1]) // 2
    y = (height - resized.shape[0]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


def labelled(tile: np.ndarray, text: str) -> np.ndarray:
    canvas = np.full((HEADER + tile.shape[0], tile.shape[1], 3), 22, np.uint8)
    canvas[HEADER:] = tile
    cv2.putText(canvas, text, (10, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                (238, 238, 238), 1, cv2.LINE_AA)
    return canvas


def selected_centres(manifest: dict) -> list[list]:
    centres = manifest["peel"]["cluster_centres_cm"]
    result = []
    for wanted in ("seam", "corner", "base"):
        match = next((row for row in centres if row[2] == wanted and row not in result), None)
        if match is not None:
            result.append(match)
    for row in centres:
        if len(result) == 3:
            break
        if row not in result:
            result.append(row)
    return result


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    manifest_out = {"schema_version": 1, "crop_scale": "1:1 source texel", "assets": {}}
    for label, old_manifest_path in REPRESENTATIVES.items():
        old = read(old_manifest_path)
        round1_manifest_path = old_manifest_path.parent.parent / "skin_v2" / old_manifest_path.name
        round2_manifest_path = old_manifest_path.parent.parent / "skin_v3" / old_manifest_path.name
        round1 = read(round1_manifest_path)
        round2 = read(round2_manifest_path)
        old_path = old_manifest_path.parent / old["textures"]["SkinColor"]["file"]
        round1_path = round1_manifest_path.parent / round1["textures"]["SkinColor"]["file"]
        round2_path = round2_manifest_path.parent / round2["textures"]["SkinColor"]["file"]
        before, after1, after2 = load(old_path), load(round1_path), load(round2_path)
        if before.shape != after1.shape or before.shape != after2.shape:
            raise RuntimeError(f"REVIEW_SIZE_MISMATCH|{label}")
        panel_w_cm, panel_h_cm = old["panel_size_cm"]
        tiles = [labelled(fit(before, TILE_W, TILE_H), f"{label} | FULL before"),
                 labelled(fit(after1, TILE_W, TILE_H), f"{label} | FULL round1"),
                 labelled(fit(after2, TILE_W, TILE_H), f"{label} | FULL round2")]
        asset_rows = []
        for index, (x_cm, y_cm, kind) in enumerate(selected_centres(old), 1):
            x = float(x_cm) / panel_w_cm * (before.shape[1] - 1)
            y = (1.0 - float(y_cm) / panel_h_cm) * (before.shape[0] - 1)
            crop_before = cv2.getRectSubPix(before, (CROP_PX, CROP_PX), (x, y))
            crop_round1 = cv2.getRectSubPix(after1, (CROP_PX, CROP_PX), (x, y))
            crop_round2 = cv2.getRectSubPix(after2, (CROP_PX, CROP_PX), (x, y))
            before_name = f"{label}_cluster{index}_{kind}_before_1to1.png"
            round1_name = f"{label}_cluster{index}_{kind}_round1_1to1.png"
            round2_name = f"{label}_cluster{index}_{kind}_round2_1to1.png"
            cv2.imwrite(str(OUTPUT / before_name), crop_before)
            cv2.imwrite(str(OUTPUT / round1_name), crop_round1)
            cv2.imwrite(str(OUTPUT / round2_name), crop_round2)
            tiles.extend([labelled(crop_before, f"C{index} {kind} before 1:1"),
                          labelled(crop_round1, f"C{index} {kind} round1 1:1"),
                          labelled(crop_round2, f"C{index} {kind} round2 1:1")])
            asset_rows.append({"cluster": index, "kind": kind,
                               "centre_cm": [x_cm, y_cm],
                               "before": before_name, "round1": round1_name,
                               "round2": round2_name,
                               "size_px": [CROP_PX, CROP_PX], "resampled": False})
        full_triplet = np.hstack((labelled(fit(before, 720, 1080), "FULL before"),
                                  labelled(fit(after1, 720, 1080), "FULL round1"),
                                  labelled(fit(after2, 720, 1080), "FULL round2")))
        full_name = f"{label}_full_before_round1_round2.jpg"
        cv2.imwrite(str(OUTPUT / full_name), full_triplet, [cv2.IMWRITE_JPEG_QUALITY, 94])
        all_rows.append(np.hstack(tiles))
        manifest_out["assets"][label] = {
            "old_manifest": old_manifest_path.resolve().relative_to(ROOT).as_posix(),
            "round1_manifest": round1_manifest_path.resolve().relative_to(ROOT).as_posix(),
            "round2_manifest": round2_manifest_path.resolve().relative_to(ROOT).as_posix(),
            "full_before_round1_round2": full_name, "clusters": asset_rows,
        }
    sheet = np.vstack(all_rows)
    sheet_path = OUTPUT / "CONTACT_SHEET_peel_before_after.jpg"
    cv2.imwrite(str(sheet_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 95])
    manifest_out["contact_sheet"] = sheet_path.name
    (OUTPUT / "review_manifest.json").write_text(json.dumps(manifest_out, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "representatives": 3,
                      "states": ["before", "round1", "round2"],
                      "clusters_each": 3, "contact_sheet": str(sheet_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
