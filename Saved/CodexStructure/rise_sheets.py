"""Offline (plain Python + PIL): compose the two sheets from rise_compare_bench.py's frames
(30 Sep), for Gary's two judgements. Numbers in the captions are measured from these frames
(rise_sheets prints them) or read from the bench's logged pitches.
  Captures/RiseSpeed_S5_vs_S4_Sheet.png   is Scene 5's rise thrilling or absurd?
  Captures/RoofBeat_S6_vs_S4_Sheet.png    what the empty roof beat looks like
The 1-second exposures average 11 frames over +-0.5 s around each rise's fastest moment in
LINEAR light, so the smear is what a 1 s shutter would record."""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "Captures", "RiseBench")
OUT = os.path.join(HERE, "Captures")
BG, FG, DIM, ACC = (18, 18, 22), (235, 235, 235), (160, 160, 170), (255, 200, 90)


def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(os.path.join("C:/Windows/Fonts", name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def img(name, size):
    return Image.open(os.path.join(SRC, name)).convert("RGB").resize(size, Image.LANCZOS)


def lum(name):
    return np.asarray(Image.open(os.path.join(SRC, name)).convert("L"), dtype=np.int16)


def smear(s, v):
    fr = [np.asarray(Image.open(os.path.join(SRC, f"S{s}_smear_{v}_{i:02d}.png")).convert("RGB"), dtype=np.float32) / 255.0 for i in range(11)]
    lin = np.mean([np.where(f <= 0.04045, f / 12.92, ((f + 0.055) / 1.055) ** 2.4) for f in fr], axis=0)
    out = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))


def pitches(s, which):
    meta = json.load(open(os.path.join(SRC, f"S{s}_{which}_meta.json"), encoding="utf-8"))
    return {round(float(p.split(":")[0]), 2): float(p.split(":")[1]) for p in meta["pitches"]}


def wrap(draw, text, x, y, width, f, fill):
    line = ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=f) > width:
            draw.text((x, y), line, font=f, fill=fill)
            y += f.size + 6
            line = word
        else:
            line = trial
    draw.text((x, y), line, font=f, fill=fill)
    return y + f.size + 6


def grid(draw, sheet, rows, cols, x0, y0, tw, th, label_w, fsmall, flab):
    y = y0
    for label, fn, sub in rows:
        draw.text((12, y + th // 2 - 22), label[0], font=flab, fill=FG)
        draw.text((12, y + th // 2 + 4), label[1], font=fsmall, fill=DIM)
        for i, c in enumerate(cols):
            name = fn(c)
            x = x0 + i * (tw + 6)
            if name and os.path.exists(os.path.join(SRC, name)):
                sheet.paste(img(name, (tw, th)), (x, y))
            if sub:
                draw.text((x + 6, y + th - 24), sub(c), font=fsmall, fill=ACC)
        y += th + 8
    return y


def speed_sheet():
    ts = [0.0, 3.0, 6.0, 9.0, 12.0, 16.0, 20.0, 25.3]
    p4, p5 = pitches(4, "speed"), pitches(5, "speed")
    tw, th, lw = 232, 131, 190
    W = lw + len(ts) * (tw + 6) + 10
    sheet = Image.new("RGB", (W, 1560), BG)
    d = ImageDraw.Draw(sheet)
    ft, fl, fs, fb = font(30, True), font(19, True), font(15), font(18)
    d.text((12, 12), "Scene 5's rise vs Scene 4's, at the same clock times", font=ft, fill=FG)
    d.text((12, 52), "Scene time from the cut. Both rises start 3.6 s before the cut (the Passage end). Scene 4 lands at 16 s; Scene 5 (150 x 200 x 50 m, K 1.58) at 25.3 s. "
                     "No exposure override: these are the show's frames.", font=fs, fill=DIM)
    for i, t in enumerate(ts):
        d.text((lw + i * (tw + 6) + 6, 82), f"{t:g} s", font=fl, fill=FG)
    fmt = lambda s, which: (lambda t: f"S{s}_speed_{which}_p{t:05.2f}.png")
    rows = [(("Scene 4", "outside, side"), fmt(4, "side"), lambda t: f"{p4.get(t, 0):.0f}°"),
            (("Scene 5", "outside, side"), fmt(5, "side"), lambda t: f"{p5.get(t, 0):.0f}°"),
            (("Scene 4", "from the stop (cat)"), fmt(4, "cam"), None),
            (("Scene 5", "from the stop (cat)"), fmt(5, "cam"), None)]
    y = grid(d, sheet, rows, ts, lw, 110, tw, th, lw, fs, fl) + 14
    lit = {s: [100 * (lum(f"S{s}_speed_cam_p{t:05.2f}.png") > 40).mean() for t in ts] for s in (4, 5)}
    d.text((12, y), "A 1-second exposure at each rise's fastest moment", font=fl, fill=FG)
    y += 30
    sw, sh = (W - 24 - 18) // 4, int((W - 24 - 18) // 4 * 9 / 16)
    for i, (s, v, lab) in enumerate(((4, "side", "Scene 4, outside"), (5, "side", "Scene 5, outside"),
                                      (4, "cam", "Scene 4, from the stop"), (5, "cam", "Scene 5, from the stop"))):
        x = 12 + i * (sw + 6)
        sheet.paste(smear(s, v).resize((sw, sh), Image.LANCZOS), (x, y))
        d.text((x + 6, y + 6), lab, font=fs, fill=ACC)
    y += sh + 14
    facts = [
        "The smear is the distance moved in one second. Scene 4 sweeps 6.9° in that second (its far end moves 7.2 m); Scene 5 sweeps 4.7° (its far end moves 12.2 m).",
        "From the stop the cat stands almost on the hinge, so the eye reads the SWEEP, not the far wall's speed: Scene 5 reads about 1.5x slower and heavier than Scene 4, not faster. "
        "Its bulb streaks are shorter.",
        f"From the stop Scene 5 is black until about 12 s (p99 1 to 2 of 255), and after landing only {lit[5][-1]:.1f}% of the frame is lit, against Scene 4's {lit[4][-1]:.1f}%. "
        "Its lights did scale with its size, but at 150 m they are points. From the cat's position the rise is mostly unseen.",
        "Judgement for Gary: is a slower, darker, much bigger rise the right Scene 5? These are the builder's K law and budgeted lights, not a design.",
    ]
    for f_ in facts:
        y = wrap(d, "- " + f_, 12, y, W - 24, fb, FG)
    sheet = sheet.crop((0, 0, W, y + 10))
    sheet.save(os.path.join(OUT, "RiseSpeed_S5_vs_S4_Sheet.png"))
    return lit


def roof_sheet():
    ts = [12.0, 16.0, 18.5, 20.5, 22.5, 24.5, 26.5, 29.0]
    tw, th, lw = 232, 131, 190
    W = lw + len(ts) * (tw + 6) + 10
    sheet = Image.new("RGB", (W, 1100), BG)
    d = ImageDraw.Draw(sheet)
    ft, fl, fs, fb = font(30, True), font(19, True), font(15), font(18)
    d.text((12, 12), "Scene 6 has no roof: the roof beat with and without it", font=ft, fill=FG)
    d.text((12, 52), "Scene time. Both boxes land at 16 s. In Scene 4 the roof swings shut from 18.5 to 24.5 s; then the lattice flies in (24.5 to 28.5 s) in both. "
                     "No exposure override.", font=fs, fill=DIM)
    for i, t in enumerate(ts):
        beat = {18.5: "roof starts", 24.5: "roof shut / lattice"}.get(t, "")
        d.text((lw + i * (tw + 6) + 6, 82), f"{t:g} s  {beat}", font=fl if not beat else fs, fill=ACC if beat else FG)
    fmt = lambda s, which, view: (lambda t: f"S{s}_{which}_{view}_p{t:05.2f}.png")
    rows = [(("Scene 4", "outside, whole arc"), fmt(4, "roofarc", "arc"), None),
            (("Scene 6", "outside, whole arc"), fmt(6, "roofarc", "arc"), None),
            (("Scene 4", "stop, looking up 25°"), fmt(4, "roof", "up"), None),
            (("Scene 6", "stop, looking up 25°"), fmt(6, "roof", "up"), None)]
    y = grid(d, sheet, rows, ts, lw, 110, tw, th, lw, fs, fl) + 14

    def change(s, which, view, a, b):
        return 100 * (np.abs(lum(f"S{s}_{which}_{view}_p{b:05.2f}.png") - lum(f"S{s}_{which}_{view}_p{a:05.2f}.png")) > 8).mean()

    still6 = max(change(6, "roofarc", "arc", a, b) for a, b in ((18.5, 20.5), (20.5, 22.5), (22.5, 24.5)))
    moving4 = [change(4, "roofarc", "arc", a, b) for a, b in ((18.5, 20.5), (20.5, 22.5), (22.5, 24.5))]
    same_up = [100 * (np.abs(lum(f"S4_roof_up_p{t:05.2f}.png") - lum(f"S6_roof_up_p{t:05.2f}.png")) > 8).mean() for t in (26.5, 29.0)]
    peak_up = max(100 * (np.abs(lum(f"S4_roof_up_p{t:05.2f}.png") - lum(f"S6_roof_up_p{t:05.2f}.png")) > 8).mean() for t in (20.5, 22.5, 24.5))
    facts = [
        f"Outside, Scene 6 does NOTHING for six seconds: from 18.5 to 24.5 s its frame changes {still6:.2f}% (Scene 4's changes "
        f"{min(moving4):.1f} to {max(moving4):.1f}% every 2 s as the roof comes over). Light escapes upward from the open top.",
        f"From the stop looking up, Scene 4's roof shows only as a glint at about 22.5 s and a faintly lit ceiling behind the lattice at 24.5 s "
        f"(at most {peak_up:.1f}% of the frame). Once shut, the two scenes are the SAME frame ({max(same_up):.1f}% differ). "
        "Looking level from the stop, the roof never enters the frame in either scene.",
        "So the missing roof is a missing piece from outside and a quiet held breath from the cat's position. Scene 4's own roof barely reads from the stop either.",
        "Also visible: at 12 s Scene 6's box is still rising through its flat ground plane (a known fault, as for Scenes 1 and 5).",
        "Judgement for Gary: is 18.5 to 24.5 s in Scene 6 a held breath or a gap to fill? And does Scene 4's roof beat need to read from the cat's position at all?",
    ]
    for f_ in facts:
        y = wrap(d, "- " + f_, 12, y, W - 24, fb, FG)
    sheet = sheet.crop((0, 0, W, y + 10))
    sheet.save(os.path.join(OUT, "RoofBeat_S6_vs_S4_Sheet.png"))
    return still6, moving4, same_up, peak_up


if __name__ == "__main__":
    print("speed: lit% from the stop by time", speed_sheet())
    print("roof: S6 still, S4 moving, same-after-shut, peak up diff", roof_sheet())
