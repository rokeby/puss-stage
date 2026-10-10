from PIL import Image, ImageDraw, ImageFont
import os

HERE = os.path.dirname(os.path.abspath(__file__))
font = ImageFont.load_default()

img = Image.new("RGB", (1200, 700), (20, 22, 27))
d = ImageDraw.Draw(img)
d.text((40, 28), "JOB 171 - S3 LONG HAIR VARIATION (LOOK PREVIEW, NOT A RENDER)", fill=(235, 235, 235), font=font)
palettes = [("DARK BROWN / STRAIGHT BANGS", (55, 35, 25), "hairMelanin 0.72 | WhiteAmount 0.03"),
            ("GREY / LONG STRAIGHT", (125, 128, 132), "hairMelanin 0.30 | WhiteAmount 0.72")]
for row, (name, color, note) in enumerate(palettes):
    y = 100 + row * 260
    d.rounded_rectangle((50, y, 1150, y + 210), 18, fill=(35, 38, 45), outline=(100, 104, 112), width=2)
    d.ellipse((90, y + 35, 250, y + 195), fill=(170, 135, 112))
    d.pieslice((70, y + 5, 270, y + 210), 175, 365, fill=color)
    d.rectangle((130, y + 80, 210, y + 200), fill=color)
    d.text((320, y + 55), name, fill=(245, 245, 245), font=font)
    d.text((320, y + 95), note, fill=(210, 210, 215), font=font)
    d.text((320, y + 130), "Cards: two groups LOD0-4 | helmets LOD5-7", fill=(170, 180, 195), font=font)
img.save(os.path.join(HERE, "job171_hair_palette_preview.png"))

img = Image.new("RGB", (1200, 520), (15, 18, 24))
d = ImageDraw.Draw(img)
d.text((40, 28), "JOB 171 - S3 COOL FIRE PALETTE (LOOK PREVIEW, NOT A RENDER)", fill=(235, 235, 235), font=font)
warm = (255, 110, 25); cool = tuple(round(x * 255) for x in (0.35, 0.42, 0.5))
for x in range(1200):
    t = x / 1199.0
    c = tuple(round(warm[i] * (1-t) + cool[i] * t) for i in range(3))
    d.line((x, 95, x, 360), fill=c)
d.text((45, 390), "CURRENT WARM", fill=warm, font=font)
d.text((925, 390), "TARGET COOL BLUE-GREY", fill=cool, font=font)
d.text((45, 430), "Linear light colour: 0.35, 0.42, 0.50 | temperature: 9000 K | intensity unchanged", fill=(220, 220, 225), font=font)
img.save(os.path.join(HERE, "job171_fire_palette_preview.png"))
print("JOB171_PREVIEWS_OK|count=2")
