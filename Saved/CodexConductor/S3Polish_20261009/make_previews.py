"""Create analytical P28 cards.  These are not Unreal renders."""
import json
import os

from PIL import Image, ImageDraw, ImageFont


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "s3_polish_args.json")
BG = (19, 22, 29)
INK = (232, 235, 240)
MUTED = (150, 158, 171)
FIRE = (244, 137, 45)
COLD = (92, 180, 242)
GREEN = (98, 201, 143)


def font(size, bold=False):
    names = ["arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def timeline(args):
    p = args["params"]
    image = Image.new("RGB", (1400, 760), BG)
    draw = ImageDraw.Draw(image)
    draw.text((60, 42), "S3 POLISH — TIMING PLAN", fill=INK, font=font(40, True))
    draw.text((60, 94), "Analytical preview only · live DRY reads the actual channels", fill=MUTED, font=font(22))
    x0, x1 = 150, 1320
    common, ramp = p["common_ignite_frame"], p["fire_ramp_frames"]
    for row, label in enumerate(("Fire B", "Fire C")):
        y = 200 + row * 120
        draw.text((60, y - 10), label, fill=INK, font=font(24, True))
        draw.line((x0, y + 30, x1, y + 30), fill=(69, 75, 86), width=4)
        draw.rectangle((x0, y + 12, x0 + 320, y + 48), fill=(66, 46, 36))
        draw.polygon([(x0, y + 48), (x0 + 320, y + 48), (x0 + 320, y + 12)], fill=FIRE)
        draw.text((x0, y - 25), "ignite f%d" % common, fill=FIRE, font=font(20, True))
        draw.text((x0 + 330, y + 14), "%d-frame envelope → full flicker" % ramp, fill=MUTED, font=font(20))
    y = 505
    draw.text((60, y - 10), "B11 cold wave light", fill=INK, font=font(24, True))
    draw.line((x0, y + 30, x1, y + 30), fill=(69, 75, 86), width=4)
    draw.polygon([(x0, y + 12), (x0 + 160, y + 48), (x1, y + 48), (x1, y + 12)], fill=COLD)
    draw.text((x0, y - 25), "B11 f5181", fill=COLD, font=font(20, True))
    draw.text((x0 + 175, y + 14), "%d-frame ramp → %.0f%% through f6253" %
              (p["b11_ramp_frames"], p["b11_factor"] * 100), fill=MUTED, font=font(20))
    draw.text((60, 675), "A and Ghost are untouched by fires_together · Stylish swap remains DRY-only", fill=GREEN, font=font(22, True))
    image.save(os.path.join(HERE, "preview_timing.png"))


def candidates(args):
    labels = args["params"]["b11_candidate_labels"]
    image = Image.new("RGB", (1400, 820), BG)
    draw = ImageDraw.Draw(image)
    draw.text((60, 42), "B11 — COLD-LIGHT CANDIDATE CALL", fill=INK, font=font(40, True))
    draw.text((60, 94), "The card names candidates; live camera-space DRY decides the second-left ranking", fill=MUTED, font=font(22))
    draw.rectangle((70, 165, 1330, 700), outline=(73, 80, 92), width=3)
    draw.polygon([(150, 430), (260, 375), (260, 485)], fill=(214, 219, 225))
    draw.text((105, 515), "B11 camera", fill=INK, font=font(21, True))
    xs = [520, 780, 1040]
    for x, label in zip(xs, labels):
        draw.ellipse((x - 65, 365, x + 65, 495), fill=(33, 79, 112), outline=COLD, width=5)
        draw.line((260, 430, x - 65, 430), fill=(47, 99, 137), width=3)
        draw.text((x - 115, 530), label.replace("S3 WaveV3 ", ""), fill=INK, font=font(21, True))
        draw.text((x - 62, 408), "9000 K", fill=COLD, font=font(18, True))
    draw.text((80, 735), "No row is accepted by this offline card. Inspect DRY ranking + Gary's B11 frame before APPLY.",
              fill=GREEN, font=font(22, True))
    image.save(os.path.join(HERE, "preview_b11_candidates.png"))


def main():
    with open(ARGS, "r", encoding="utf-8") as handle:
        args = json.load(handle)
    timeline(args)
    candidates(args)
    print("PREVIEWS_OK|2")


if __name__ == "__main__":
    main()
