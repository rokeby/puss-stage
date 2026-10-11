"""Measure linearized Rec.709 mean luminance of a captured seam frame."""
import argparse
from PIL import Image


def srgb_to_linear(value):
    value /= 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def mean_luminance(path):
    image = Image.open(path).convert("RGB")
    total = 0.0
    for red, green, blue in image.getdata():
        total += 0.2126 * srgb_to_linear(red) + 0.7152 * srgb_to_linear(green) + 0.0722 * srgb_to_linear(blue)
    return total / float(image.width * image.height)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--threshold", type=float, default=0.95)
    args = parser.parse_args()
    value = mean_luminance(args.image)
    passed = value > args.threshold
    print("JOB192_WHITEOUT_MEASURE|mean_linear_luminance=%.6f|threshold=%.6f|pass=%d" %
          (value, args.threshold, int(passed)))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
