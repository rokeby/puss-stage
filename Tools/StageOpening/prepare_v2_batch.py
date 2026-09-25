#!/usr/bin/env python3
"""Select active Stage Opening concepts and prepare a deterministic v2 batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image


DEFAULT_NAMES = [
    "BambooScaffold_01_L.png",
    "BambooScaffold_01_R.png",
    "CeramicTotem_01_L.png",
    "CeramicTotem_01_R.png",
    "CoveredPillar_01_L.png",
    "CoveredPillar_01_R.png",
    "GauzeLattice_01_L.png",
    "GauzeLattice_01_R.png",
    "SteelScaffold_01_L.png",
    "SteelScaffold_01_R.png",
    "SaltFormation_01_R.png",
    "MutatedPeltFlora_01_L_v2.png",
    "CoveredBiomechCeramic_01_L_rococo-painterly.png",
    "CoveredBiomechCeramic_01_L_exposed-rococo-painterly.png",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def with_black_removed(source: Path, target: Path) -> None:
    rgba = np.asarray(Image.open(source).convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.float32)
    luminance = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    ramp = np.clip((luminance - 7.0) / 17.0, 0.0, 1.0)
    rgba[:, :, 3] = np.uint8(rgba[:, :, 3].astype(np.float32) * ramp)
    Image.fromarray(rgba, "RGBA").save(target)


def main() -> int:
    args = parse_args()
    args.batch_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, object]] = {"images": {}}
    for name in DEFAULT_NAMES:
        source = args.source_dir / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = args.batch_dir / name
        image = Image.open(source)
        alpha_extrema = image.convert("RGBA").getchannel("A").getextrema()
        if alpha_extrema[0] == 255:
            with_black_removed(source, target)
        else:
            shutil.copy2(source, target)

        simplify_px = 2.5 if "Scaffold" in name or "Lattice" in name else 1.75
        manifest["images"][name] = {
            "height_m": 2.0,
            "thickness_cm": 10.0,
            "ue_panel_scale": 5.0,
            "trace_max_size": 768,
            "simplify_px": simplify_px,
            "islands": "largest",
        }

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        "STAGEOPENING_V2_BATCH_PREPARED",
        f"count={len(DEFAULT_NAMES)}",
        f"batch_dir={args.batch_dir}",
        f"manifest={args.manifest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
