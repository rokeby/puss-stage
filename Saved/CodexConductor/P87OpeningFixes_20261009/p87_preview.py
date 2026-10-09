"""Generate offline P87 timeline and stage-front placement previews (PIL only)."""
from __future__ import annotations

import json
import os

from PIL import Image, ImageDraw, ImageFont

import p87_opening_common as C


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "DerivedAssets", "P87OpeningFixes")


def _font():
    return ImageFont.load_default()


def timeline(path, plan):
    image = Image.new("RGB", (1500, 620), (18, 18, 22)); d = ImageDraw.Draw(image); font = _font()
    d.text((35, 22), "P87 OPENING — PROPOSED, NOT APPLIED", fill=(245, 225, 180), font=font)
    left, right, y = 80, 1440, 180
    end = plan["camera"]["keys"][-1]["frame"]
    x = lambda frame: left + (right - left) * frame / end
    d.line((left, y, right, y), fill=(180, 180, 190), width=3)
    fall = plan["camera"]["hold_end_frame"]
    landed = plan["curtain"]["sections"][1]["end"]
    for frame, label, color in ((0, "Opening start", (160, 160, 170)),
                                (fall, "first flurry / ONE fall / move begins", (255, 110, 90)),
                                (landed, "curtain landed; pile holds", (210, 160, 100)),
                                (end, "exact existing end pose", (90, 220, 160))):
        xx = x(frame); d.line((xx, y - 65, xx, y + 150), fill=color, width=3)
        d.text((max(15, min(xx - 60, 1320)), y - 90), "%s\nf%d / %.2fs" % (label, frame, frame / 25.0), fill=color, font=font)
    d.rectangle((x(fall), y + 35, x(end), y + 80), fill=(45, 80, 120))
    d.text((x(fall) + 12, y + 50), "very slow smootherstep camera move", fill="white", font=font)
    d.rectangle((x(fall), y + 100, x(fall + 20), y + 140), fill=(230, 175, 85))
    d.text((x(fall + 20) + 10, y + 112), "six shadowless stage-front uplights fade on", fill=(230, 195, 120), font=font)
    d.text((35, 545), "Clock warning: Gary 00:37:50 is ambiguous at Opening 25 fps. Live DRY must pin the local frame.",
           fill=(255, 140, 110), font=font)
    os.makedirs(os.path.dirname(path), exist_ok=True); image.save(path)


def stage_front(path, plan):
    image = Image.new("RGB", (1400, 800), (24, 21, 19)); d = ImageDraw.Draw(image); font = _font()
    d.text((30, 20), "P87 STAGE FRONT — TOP VIEW / PROPOSAL", fill=(245, 225, 180), font=font)
    cx, cy, scale = 700, 380, 0.45
    d.rectangle((cx - 1050 * scale, cy - 30, cx + 1050 * scale, cy + 30), outline=(185, 140, 90), width=4)
    d.text((cx - 100, cy - 55), "paper proscenium/front", fill=(210, 170, 110), font=font)
    for row in plan["uplights"]["rows"]:
        x = cx + row["location"][1] * scale; y = cy + 90
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 185, 80))
        d.line((x, y, x, cy), fill=(255, 195, 95), width=2)
    for row in plan["bulbs"]["rows"]:
        x = cx + row["location_xy_proposal"][1] * 0.25
        y = cy + 180 + row["location_xy_proposal"][0] * 0.04
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(185, 220, 255))
    d.text((30, 720), "Orange: 6 x 3200 K, 350 lm default, zero new shadow casters. Blue: seeded bulb scatter; floor Z is live-traced.",
           fill=(220, 220, 225), font=font)
    d.text((30, 750), "Creative values are args and require Gary's rendered acceptance.", fill=(255, 150, 115), font=font)
    os.makedirs(os.path.dirname(path), exist_ok=True); image.save(path)


def main():
    raw = json.load(open(os.path.join(HERE, "p87_opening_args.json"), encoding="utf-8"))
    raw["first_flurry_frame"] = 950  # preview hypothesis only; live APPLY stays null until DRY resolves it
    p = C.merge_args(raw, True)
    bulbs = [{"id": "PREVIEW-%02d" % i, "wing_location": [i * 350.0, (-1) ** i * (500 + i * 25), 0.0],
              "floor_z_cm": 0.0, "side_sign": (-1) ** i} for i in range(12)]
    live = {"show_path": "Show", "level_path": "Level", "sequence_path": "LS_Opening_Curtain_Baked",
            "clock": {"status": "PREVIEW_HYPOTHESIS"},
            "camera_end_pose": {"location": [0, 0, 150], "rotation": [0, 0, 0], "focal_mm": 25, "focus_cm": 600},
            "curtain_sections": [{"role": "FALL", "start": 1900, "end": 2150},
                                 {"role": "FALL", "start": 2200, "end": 2400}], "bulbs": bulbs}
    plan = C.build_plan(p, live)
    a = os.path.join(OUT, "p87_timeline.png"); b = os.path.join(OUT, "p87_stage_front.png")
    timeline(a, plan); stage_front(b, plan)
    print("P87_PREVIEW_OK|timeline=%s|stage_front=%s|frame=950_PREVIEW_ONLY" % (a, b))


if __name__ == "__main__":
    main()
