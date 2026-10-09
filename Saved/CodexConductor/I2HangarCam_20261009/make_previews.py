"""Generate two offline framing cards from i2_hangar_cam_args.json (PIL only)."""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont


HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "i2_hangar_cam_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)["params"]


def font(size):
    for path in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text(draw, xy, value, size=28, fill=(230, 223, 204)):
    draw.text(xy, value, font=font(size), fill=fill)


def plan_card():
    image = Image.new("RGB", (1600, 900), (18, 20, 22))
    draw = ImageDraw.Draw(image)
    text(draw, (70, 55), "I2 HANGAR HOLD CAMERA — OFFLINE PLAN VIEW", 36)
    text(draw, (70, 112), "Analytical preview only; Gary's 18:02 stills remain the rendered look reference.", 23,
         (175, 179, 174))
    cx, cy = 620, 500
    yaw = math.radians(float(args["rotation_deg"]["yaw"]))
    focus = float(args["focus_distance_cm"])
    scale = 0.14
    length = focus * scale
    dx, dy = math.cos(yaw) * length, -math.sin(yaw) * length
    draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=(235, 181, 54), outline=(255, 240, 188), width=3)
    draw.line((cx, cy, cx + dx, cy + dy), fill=(235, 181, 54), width=8)
    draw.polygon([(cx + dx, cy + dy), (cx + dx - 25, cy + dy + 10), (cx + dx - 9, cy + dy + 27)],
                 fill=(235, 181, 54))
    draw.arc((cx - 145, cy - 145, cx + 145, cy + 145), 0, 44, fill=(106, 167, 196), width=5)
    text(draw, (70, 720), "World location  %.1f, %.1f, %.1f cm" % tuple(args["location_cm"]), 28)
    text(draw, (70, 765), "Rotation  pitch %.2f°  yaw %.2f°  roll %.2f°" %
         (args["rotation_deg"]["pitch"], args["rotation_deg"]["yaw"], args["rotation_deg"]["roll"]), 28)
    text(draw, (980, 430), "Focus fallback %.0f cm" % focus, 27)
    text(draw, (980, 475), "DRY replaces this with the", 25, (175, 179, 174))
    text(draw, (980, 510), "record-derived drape distance", 25, (175, 179, 174))
    image.save(os.path.join(HERE, "preview_plan.png"))


def frame_card():
    image = Image.new("RGB", (1600, 900), (6, 7, 8))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 1560, 860), outline=(235, 181, 54), width=5)
    draw.line((800, 40, 800, 860), fill=(54, 63, 68), width=2)
    draw.line((40, 450, 1560, 450), fill=(54, 63, 68), width=2)
    hfov, width = float(args["horizontal_fov_deg"]), float(args["sensor_width_mm"])
    focal = width / (2.0 * math.tan(math.radians(hfov) / 2.0))
    text(draw, (90, 90), "I2 HANGAR HOLD — 16:9 FRAMING CARD", 37)
    text(draw, (90, 150), "HFOV %.2f°   sensor %.2f × %.2f mm   focal %.3f mm" %
         (hfov, width, float(args["sensor_height_mm"]), focal), 29)
    text(draw, (90, 720), "Target content: hangar drape + boy-rub gobo", 31)
    text(draw, (90, 770), "Not rendered acceptance — compare the post-APPLY I2 stills.", 25, (175, 179, 174))
    text(draw, (760, 415), "+", 56, (235, 181, 54))
    image.save(os.path.join(HERE, "preview_frame.png"))


plan_card()
frame_card()
print("I2_HANGAR_CAM_PREVIEWS_OK|files=preview_plan.png,preview_frame.png")

