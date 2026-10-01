"""Generate sampler-compatible 64x64 placeholder maps for the billboard master."""
import argparse
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "DerivedAssets"
    / "WingMateriality"
    / "BillboardPlaceholders"
)


def generate(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    images = {
        "T_BB_Colour.png": Image.new("RGB", (64, 64), (128, 128, 128)),
        "T_BB_Mask.png": Image.new("RGBA", (64, 64), (0, 128, 128, 0)),
        "T_BB_Normal.png": Image.new("RGB", (64, 64), (128, 128, 255)),
    }
    for name, image in images.items():
        path = output_dir / name
        image.save(path, format="PNG")
        with Image.open(path) as saved:
            print(f"{name}: size={saved.size[0]}x{saved.size[1]} mode={saved.mode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="override the default DerivedAssets output (useful for an offline check)",
    )
    args = parser.parse_args()
    generate(args.output_dir.resolve())


if __name__ == "__main__":
    main()
