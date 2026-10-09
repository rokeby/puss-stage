"""Analytical cards only; not Unreal renders or visual acceptance."""
from PIL import Image, ImageDraw, ImageFont
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1500, 820
im = Image.new("RGB", (W, H), (18, 20, 25))
d = ImageDraw.Draw(im)
font = ImageFont.load_default()


def tx(x, y, value, colour=(228, 231, 238)):
    d.multiline_text((x, y), value, font=font, fill=colour, spacing=4)


tx(45, 28, "JOB 90 / I1 POLISH - ANALYTICAL PLAN (NOT AN UNREAL RENDER)", (255, 226, 160))
tx(45, 55, "35 mm lens | 23.76 x 13.365 mm filmback | curtain hang bounds 1880 x 1000 cm", (180, 190, 210))

# Before/after curtain framing diagrams, proportional in the camera plane.
for col, (title, distance, colour) in enumerate((("BEFORE: tracked I1 record", 1200.0, (255, 135, 110)),
                                                 ("PLANNED: 3% safety margin", 2852.44, (130, 230, 175)))):
    ox = 55 + col * 720
    tx(ox, 110, "%s\n35 mm | distance %.2f cm" % (title, distance), colour)
    frame_w = distance * 23.76 / 35.0
    frame_h = distance * 13.365 / 35.0
    scale = 0.28
    cx, cy = ox + 340, 360
    d.rectangle((cx-940*scale, cy-500*scale, cx+940*scale, cy+500*scale), outline=(195, 60, 65), width=4)
    d.rectangle((cx-frame_w*.5*scale, cy-frame_h*.5*scale, cx+frame_w*.5*scale, cy+frame_h*.5*scale),
                outline=colour, width=4)
    tx(ox, 530, "red = curtain bounds\ncoloured = camera frame at curtain plane\nframe %.0f x %.0f cm" % (frame_w, frame_h), colour)

tx(45, 620, "TIMELINE / 25 fps", (255, 226, 160))
x0, x1, y = 80, 1420, 690
d.line((x0, y, x1, y), fill=(210, 215, 225), width=3)
events = [(274, "fit reached"), (1249, "Hangar side"), (1250, "Mouth cut / light diff"),
          (1675, "GO 10 release / HOLD camera"), (1701, "old route began"), (2183, "I1 end")]
for i, (frame, label) in enumerate(events):
    x = int(x0 + (x1-x0) * frame / 2183.0)
    d.line((x, y-18, x, y+18), fill=(150, 205, 255), width=2)
    tx(max(10, x-55), y+28+(i%2)*33, "%s\nf%d / %.2fs" % (label, frame, frame/25.0), (170, 215, 255))

out = os.path.join(HERE, "preview_i1_polish_plan.png")
im.save(out)
print("PREVIEW_OK|file=%s|size=%dx%d" % (out, W, H))
