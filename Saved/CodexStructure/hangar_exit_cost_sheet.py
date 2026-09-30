"""Hangar exit cost sheet (30 Sep, conductor: cost docking each Passage N+1 at Hangar N's far wall).
Offline: hangar records/plans, the transition-mouth survey, and the builder's own swing formula (hangar_build.py:
x = apron + x_b cos(t) - z_b sin(t), t from -90 to 0, roof upright at rest). Writes
Captures/HangarExit_DockingCost.png. No editor, no Unreal import."""
import json, math, os
from PIL import Image, ImageDraw, ImageFont
S = "E:/PussStage/Saved"
mouths = json.load(open(f"{S}/CodexCameraPilot/survey_transition_mouths.json", encoding="utf-8"))["passages"]
starts = {i: (mouths[f"Passage {i}"]["route_start"][0] / 100, mouths[f"Passage {i}"]["route_start"][1] / 100, mouths[f"Passage {i}"]["yaw"]) for i in range(1, 7)}
dock, far, hang = {}, {}, {}
for n in range(1, 7):
    for f in (f"{S}/CodexStructure/hangar_s{n}_record.json", f"{S}/CodexStructure/hangar_s{n}_plan.json"):
        if os.path.exists(f):
            d = json.load(open(f, encoding="utf-8"))
            break
    dock[n] = (d["dock"]["loc"][0] / 100, d["dock"]["loc"][1] / 100, d["dock"]["yaw"])
    h = d["hangar"]
    hang[n] = h
    far[n] = (h["apron"] + h["depth"] + h["wall_t"]) / 100


def comp(a, b):
    x, y, t = a
    bx, by, bt = b
    c, s = math.cos(math.radians(t)), math.sin(math.radians(t))
    return (x + c * bx - s * by, y + s * bx + c * by, t + bt)


def inv(a):
    x, y, t = a
    c, s = math.cos(math.radians(t)), math.sin(math.radians(t))
    return (-(c * x + s * y), -(-s * x + c * y), -t)


def chain(G, docked):
    """docked: passages i (2..6) docked behind hangar i-1; the others stay where they are."""
    new = {1: starts[1]}
    rows = []
    dnew = None
    for i in range(1, 7):
        if i > 1:
            new[i] = comp(dnew, (far[i - 1] + G, 0, 0)) if i in docked else starts[i]
        rel = comp(inv(starts[i]), dock[i])
        dnew = comp(new[i], rel)
        rows.append((i, new[i], dnew, math.hypot(new[i][0] - starts[i][0], new[i][1] - starts[i][1]), new[i][2] - starts[i][2]))
    return rows


def tip_path(xb, zb, apron=5.0):
    # the root turns from -90 (box hanging in its pit, its "up" pointing away from the camera) to 0
    out = []
    for k in range(91):
        t = math.radians(-90 + k)
        out.append((apron + xb * math.cos(t) - zb * math.sin(t), xb * math.sin(t) + zb * math.cos(t)))
    return out


rt = tip_path(60.25, 90.3)          # roof tip: roof upright above the far wall at rest (S1-S4)
wt_ = tip_path(60.25, 30.0)         # far wall top
max_roof, max_wall = max(rt), max(wt_)
max_s5 = max(tip_path(150.25, 200.5))


W, H = 1900, 1960
im = Image.new("RGB", (W, H), (18, 18, 20))
dr = ImageDraw.Draw(im)


def font(sz, bold=False):
    try:
        return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", sz)
    except OSError:
        return ImageFont.load_default()


F, FB, FS, FT = font(22), font(24, True), font(18), font(34, True)
GREY, WARM, RED, GREEN, BLUE, DIM = (200, 200, 205), (255, 205, 120), (255, 120, 90), (120, 220, 140), (120, 200, 255), (110, 110, 120)
dr.text((40, 24), "Hangar exit: what docking the next Passage behind the far wall costs", font=FT, fill=(240, 240, 240))
dr.text((40, 70), "From the hangar records, the builder's own geometry and the transition-mouth survey. No editor run. 30 Sep.", font=FS, fill=(160, 160, 160))

# ---- 1. side elevation ----
dr.text((40, 118), "1.  THE RISE AS BUILT SWEEPS THE SPACE WHERE THE NEXT PROSCENIUM WOULD STAND   (side view, Scenes 1-4 hangar)", font=FB, fill=WARM)
ax0, ay0, sc = 110, 560, 4.2


def P(x, z):
    return (ax0 + x * sc, ay0 - z * sc)


mx = max_roof[0]
dr.rectangle([P(65.5, 91), P(mx, 0)], fill=(52, 26, 22))                     # the clear zone above ground
dr.rectangle([P(5, 0), P(mx + 1, -61)], outline=(70, 70, 80), width=1)        # the pit
dr.text(P(8, -55), f"pit the rise swings up out of (to {mx + 1:.0f} m)", font=FS, fill=DIM)
dr.line([P(-15, 0), P(245, 0)], fill=(120, 120, 120), width=2)
dr.line([P(x, z) for x, z in wt_], fill=(255, 190, 120), width=3)
dr.line([P(x, z) for x, z in rt], fill=RED, width=3)
dr.line([P(5, 0), P(65.25, 0)], fill=(200, 160, 110), width=6)
dr.line([P(65.25, 0), P(65.25, 30)], fill=(175, 175, 190), width=6)
dr.line([P(65.25, 30), P(65.25, 90.3)], fill=RED, width=4)
dr.line([P(5, 0), P(5, 30)], fill=(90, 90, 100), width=2)
dr.ellipse([P(-1.5, 3.2), P(1.5, 0.2)], fill=BLUE)
dr.text(P(-14, 9), "camera stop", font=FS, fill=BLUE)
dr.text(P(22, 36), "hangar box, 60 m", font=F, fill=GREY)
dr.text(P(67, 88), "at the end of the swing the roof stands 90 m tall on the far wall, then folds over the box", font=FS, fill=RED)
dr.ellipse([P(mx - 1.4, 1.4), P(mx + 1.4, -1.4)], fill=(255, 80, 50))
dr.text(P(mx + 3, -4), f"roof tip crosses ground level {mx:.0f} m out", font=FS, fill=RED)
dr.text(P(mx + 3, -9), f"= {mx - 65.5:.0f} m past the far wall", font=FS, fill=RED)
px = 65.5 + 2
dr.rectangle([P(px, 11), P(px + 0.8, 0)], fill=GREEN)
dr.line([P(px, 11), P(px + 45, 11)], fill=GREEN, width=2)
dr.line([P(px - 1.5, 0.5), P(px + 170, 0.5)], fill=GREEN, width=4)
dr.text(P(px + 3, 22), "next Passage docked 2 m behind the far wall:", font=FS, fill=GREEN)
dr.text(P(px + 3, 17), "proscenium, gridiron, wings, boards", font=FS, fill=GREEN)
tx, ty = 1110, 200
lines = [(f"Clear zone the rise needs past the far wall:", WARM, F),
         (f"   Scenes 1-4:  {mx - 65.5:.0f} m     Scene 5:  {max_s5[0] - 155.5:.0f} m", WARM, F),
         (f"   the box alone, without the upright roof:  {max_wall[0] - 65.5:.0f} m", GREY, F),
         ("", GREY, F),
         ("So docking needs a NEW ROOF BEAT, e.g. two leaves", GREY, F),
         ("hinged on the side-wall tops (they sweep sideways,", GREY, F),
         ("not forward), and a far-wall panel that falls as a", GREY, F),
         (f"drawbridge across the ~{max_wall[0] - 65.5 + 3:.0f} m gap onto the forestage.", GREY, F),
         ("", GREY, F),
         ("Or keep the rise and dock 50 m (Scene 5: 100 m) off:", GREY, F),
         ("the stalls seat is then outside the hangar - no longer", GREY, F),
         ("'the house' - and the open pit lies between.", GREY, F)]
for i, (t, c, f) in enumerate(lines):
    dr.text((tx, ty + i * 30), t, font=f, fill=c)


# ---- 2. maps ----
def draw_map(x0, y0, w, h, ext, title, note, docked, G):
    rows = chain(G, docked)
    lo_x, hi_x, lo_y, hi_y = ext
    k = min(w / (hi_x - lo_x), h / (hi_y - lo_y))

    def M(x, y):
        return (x0 + (x - lo_x) * k, y0 + (hi_y - y) * k)

    dr.rectangle([x0 - 10, y0 - 10, x0 + w + 10, y0 + h + 10], outline=(60, 60, 70))
    dr.text((x0 - 10, y0 - 88), title, font=FB, fill=WARM)
    dr.text((x0 - 10, y0 - 52), note, font=FS, fill=(185, 185, 185))
    for i in range(1, 7):
        sx, sy, _ = starts[i]
        dx, dy, _ = dock[i]
        if lo_y <= sy <= hi_y and i in docked:
            dr.line([M(sx, sy), M(dx, dy)], fill=(75, 75, 85), width=4)
            dr.text((M(sx, sy)[0] + 4, M(sx, sy)[1] + 8), f"P0{i} today", font=FS, fill=DIM)
    table = []
    for i, st, dn, mv, turn in rows:
        moved = i in docked
        col = GREEN if (moved and abs(turn) < 0.1) else (RED if moved else GREY)
        dr.line([M(st[0], st[1]), M(dn[0], dn[1])], fill=col, width=5)
        hx = comp(dn, (far[i], 0, 0))
        dr.line([M(dn[0], dn[1]), M(hx[0], hx[1])], fill=(175, 175, 190), width=11)
        mxp, myp = M((st[0] + dn[0]) / 2, (st[1] + dn[1]) / 2)
        dr.text((mxp + 8, myp - 26), f"P0{i}", font=FB, fill=col)
        table.append((f"P0{i}", "stays" if not moved else f"moves {mv:,.0f} m" + (f", turns {turn:+.1f} deg" if abs(turn) > 0.1 else ", no turn"), col))
    for j, (a, b, col) in enumerate(table):
        dr.text((x0, y0 + h + 22 + j * 28), f"{a}   {b}", font=F, fill=col)
    return rows


draw_map(80, 1010, 800, 560, (-60, 1100, -1380, 60), "2a.  FULL CHAIN, as proposed",
         "all five move and all five TURN, because P02's route bends 66.5 deg", {2, 3, 4, 5, 6}, 11.0)
draw_map(1020, 1010, 800, 560, (-60, 1420, -80, 1720), "2b.  CHEAPEST 'PLACE': dock only where headings agree",
         "P04-P06 slide into P03's lane: no turn. S1->P02 and S2->P03 stay cloth cuts.", {4, 5, 6}, 11.0)
dr.text((80, 1790), "grey bar = hangar, to its far wall.   green = moved, not turned: the sun and the dusk horizon keep their angle to the set.", font=FS, fill=(160, 160, 160))
dr.text((80, 1818), "red = moved AND turned: relit, because the sun is one world-fixed azimuth for the whole show (CelestialRig SunAzimuthDegrees).", font=FS, fill=(160, 160, 160))
dr.text((80, 1846), "11 m far-wall-to-portal gap assumed (drawbridge across the new rise's ~10 m pit).  P02-P06 today sit in parallel lanes 800 m apart.", font=FS, fill=(160, 160, 160))
dr.text((80, 1874), "Not yet counted (needs a read-only editor probe): level actors and world-space sequence keys riding in each moved lane.", font=FS, fill=(160, 160, 160))
out = f"{S}/CodexStructure/Captures/HangarExit_DockingCost.png"
im.save(out)
print(out)
