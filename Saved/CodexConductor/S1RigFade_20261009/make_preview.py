"""Generate the analytical timing preview; this is not an Unreal render."""
import json
import os

from PIL import Image, ImageDraw, ImageFont


HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "s1_rig_fade_args.json"), "r", encoding="utf-8") as handle:
    PARAMS = json.load(handle)["params"]

fps = 25.0
fade_frames = round(float(PARAMS["fade_seconds"]) * fps)
switches = [("Ours Off: sun / moon / skylight / fog", 269, (229, 163, 74)),
            ("24 bulb meshes -> paired lattice glows", 282, (103, 179, 204))]
width, height = 1400, 560
image = Image.new("RGB", (width, height), (17, 20, 25))
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()
draw.text((50, 36), "S1 RIG FADE - ANALYTICAL TIMING PREVIEW (NOT A RENDER)", fill=(245, 242, 231), font=font)
draw.text((50, 68), "25 fps | fade %.2f s = %d frames | Gary review timestamp 3:44; S1-local evidence below" %
          (float(PARAMS["fade_seconds"]), fade_frames), fill=(180, 186, 195), font=font)
x0, x1 = 95, 1320
frame_lo, frame_hi = 220, 305
for frame in range(frame_lo, frame_hi + 1, 5):
    x = x0 + (frame - frame_lo) * (x1 - x0) / (frame_hi - frame_lo)
    draw.line((x, 120, x, 490), fill=(42, 47, 55))
    draw.text((x - 10, 500), str(frame), fill=(135, 142, 151), font=font)
for index, (label, switch, color) in enumerate(switches):
    y = 195 + index * 145
    start = switch - fade_frames
    sx = x0 + (start - frame_lo) * (x1 - x0) / (frame_hi - frame_lo)
    ex = x0 + (switch - frame_lo) * (x1 - x0) / (frame_hi - frame_lo)
    draw.text((50, y - 38), label, fill=(235, 235, 230), font=font)
    draw.rectangle((sx, y, ex, y + 30), fill=color)
    draw.polygon([(sx, y), (ex, y), (ex, y + 30)], fill=(31, 34, 40))
    draw.line((sx, y, ex, y + 30), fill=color, width=4)
    draw.line((ex, y - 12, ex, y + 52), fill=(242, 96, 96), width=3)
    draw.text((sx, y + 42), "ramp starts f%d" % start, fill=color, font=font)
    draw.text((ex - 80, y + 62), "0 + visibility off f%d" % switch, fill=(242, 96, 96), font=font)
draw.text((50, 535), "Creative values live in s1_rig_fade_args.json. APPLY remains conductor-owned.",
          fill=(180, 186, 195), font=font)
image.save(os.path.join(HERE, "preview_timing.png"))
print("S1_RIG_FADE_PREVIEW_OK|%s" % os.path.join(HERE, "preview_timing.png"))

