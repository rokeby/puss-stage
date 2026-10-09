"""Generate analytical P39 timing/boundary cards (not Unreal renders)."""

from PIL import Image, ImageDraw, ImageFont
import os


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "preview_i2_polish_timeline.png")
W, H = 1400, 620
image = Image.new("RGB", (W, H), (19, 20, 25))
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()


def text(x, y, value, fill=(230, 231, 236)):
    draw.text((x, y), value, font=font, fill=fill)


text(44, 30, "P39 Interaction 2 polish - analytical timing card (NOT a render)", (255, 230, 170))
text(44, 55, "25 fps | post-P24 playback [0,1950) | Gary judges all visual changes in PIE", (175, 180, 195))

x0, x1 = 80, 1320
y = 165
draw.line((x0, y, x1, y), fill=(205, 210, 220), width=3)


def xpos(frame):
    return int(x0 + (x1 - x0) * frame / 1950.0)


events = [
    (0, "I2 start", (170, 210, 255)),
    (1250, "sleight cut / F17\n50.00 s", (255, 160, 120)),
    (1652, "GO 20 target\n1:06.09", (250, 220, 100)),
    (1675, "drape FALL starts\n67.00 s", (150, 230, 175)),
    (1925, "drape FALL ends\n77.00 s", (150, 230, 175)),
    (1950, "P24 end\n78.00 s", (210, 170, 255)),
]
for index, (frame, label, colour) in enumerate(events):
    x = xpos(frame)
    draw.line((x, y - 18, x, y + 22), fill=colour, width=3)
    tx = min(W - 135, max(12, x - 45))
    ty = y + 35 + (index % 2) * 42
    text(tx, ty, "%s\nf%d" % (label, frame), colour)

draw.rectangle((xpos(1675), y - 12, xpos(1925), y + 12), fill=(60, 115, 82), outline=(150, 230, 175))
text(xpos(1675) + 8, y - 48, "curtain fall [1675,1925)", (150, 230, 175))

text(80, 310, "F18 DRY inventories ALL transform movement in last 30 s: [1200,1950).", (210, 215, 225))
text(80, 335, "APPLY changes only explicit f18_target_ids; default list is empty.", (210, 215, 225))
text(80, 360, "Candidate policies: end at release f1675 (P24-owned), hold from f1675, or hold after fall f1925.", (210, 215, 225))

text(80, 430, "Scene tail boundary strategy", (255, 230, 170))
draw.rectangle((80, 475, 580, 525), outline=(190, 195, 210), width=2)
draw.rectangle((110, 486, 520, 514), fill=(62, 85, 120), outline=(170, 210, 255))
text(120, 493, "nested final camera ends exactly at playback end", (225, 235, 250))
draw.line((550, 463, 550, 537), fill=(255, 160, 120), width=3)
text(510, 545, "boundary frame", (255, 160, 120))

draw.rectangle((760, 475, 1260, 525), outline=(190, 195, 210), width=2)
draw.rectangle((790, 486, 1215, 514), fill=(60, 110, 85), outline=(150, 230, 175))
draw.line((1190, 463, 1190, 537), fill=(255, 160, 120), width=3)
text(800, 493, "planned: nested coverage +1 display frame", (225, 240, 230))
text(850, 545, "PIE probe must prove/refute before APPLY", (255, 205, 150))

image.save(OUT)
print("PREVIEW_OK|file=%s|size=%dx%d" % (OUT, W, H))

