"""Make an explicitly non-rendered scale/attachment preview for creative review."""
from PIL import Image, ImageDraw
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "p56_chandelier_candle_preview.png")
image = Image.new("RGB", (1200, 700), (18, 19, 23))
draw = ImageDraw.Draw(image)
draw.text((48, 35), "P56 CHANDELIER CANDLE FLAME - OFFLINE SCALE PREVIEW", fill=(235, 226, 201))
draw.text((48, 66), "Concept diagram only; rendered Niagara look remains Conductor acceptance.", fill=(160, 164, 172))

centres = [250, 600, 950]
for index, x in enumerate(centres, 1):
    draw.ellipse((x - 90, 505, x + 90, 555), fill=(52, 45, 40), outline=(125, 97, 67), width=4)
    draw.rectangle((x - 20, 405, x + 20, 520), fill=(218, 204, 171), outline=(246, 236, 204), width=2)
    draw.ellipse((x - 20, 393, x + 20, 417), fill=(234, 220, 184))
    draw.polygon([(x, 305), (x - 16, 390), (x, 405), (x + 16, 390)], fill=(255, 136, 32))
    draw.polygon([(x, 329), (x - 7, 389), (x, 398), (x + 7, 389)], fill=(255, 235, 115))
    draw.text((x - 42, 580), "Candle_%02d" % index, fill=(220, 220, 224))

draw.line((1050, 305, 1100, 305), fill=(244, 183, 65), width=2)
draw.line((1050, 405, 1100, 405), fill=(244, 183, 65), width=2)
draw.line((1080, 305, 1080, 405), fill=(244, 183, 65), width=2)
draw.text((1005, 345), "3.5 cm\n(default)", fill=(244, 183, 65))
draw.text((48, 645), "NS_Stylish_Fire_1 | child of BP_Effect_Candle | Auto Activate OFF | no point light", fill=(195, 198, 205))
image.save(OUT)
print("P56_PREVIEW_OK|" + OUT)
