"""Jointed cut-paper shadow puppet: the poor boy (Cagliuso), full body, side profile facing right.

Parts (each an outline + its own knife cuts, in local coordinates with a pivot):
  body (torso + legs, root, pivots at the feet), head (neck pivot), near/far upper arm (shoulder), near/far forearm
  (elbow).  A part only lets light through where ITS cut is not covered by another part, so overlapping parts are
  combined as a product of transmissions, like real card.

Face = replacement parts: eyes {open, squint, shut, wide}, brows {neutral, worried, raised},
mouth {pout, blubber, surprised, sad} (the lips are part of the head OUTLINE), tears = list of 0..1 positions
down the cheek.

Motion = two layers (see Docs note): stepped POSES when a joint moves, plus a smooth handheld drift (main rod,
arm rods, head) that UE can do live; this script can bake it for previews.

    python boy_rig.py <out_dir>            # expression sheet + 12 s demo GIF at 8 fps + frames
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from puppet_cut import chain, slit, punch  # noqa: E402
from clip_render import (DEFAULT_DISPLAY_FPS, clip_frames as shared_clip_frames,
                         scaled_render_size,
                         render_clip as shared_render_clip)  # noqa: E402

# ------------------------------------------------------------------------------------------------ head (local)
NECK = (520.0, 740.0)
FACE_TOP = [
    ((722, 405), (728, 425), (724, 442)),     # big round forehead
    ((722, 450), (719, 455), (716, 460)),     # nose root
    ((728, 476), (746, 488), (754, 500)),     # button nose
    ((756, 512), (744, 520), (728, 520)),     # nose underside
]
LIPS = {  # (728,520) -> ... -> (716,584)
    "pout": [((729, 530), (733, 538), (732, 546)), ((727, 549), (723, 551), (722, 553)),
             ((729, 558), (731, 568), (724, 576)), ((718, 580), (716, 582), (716, 584))],
    "blubber": [((730, 530), (733, 538), (730, 546)), ((724, 549), (716, 551), (714, 554)),
                ((732, 558), (744, 570), (734, 582)), ((724, 588), (716, 588), (716, 584))],
    "surprised": [((736, 528), (746, 536), (746, 544)), ((742, 548), (738, 550), (736, 551)),
                  ((744, 556), (744, 568), (730, 578)), ((720, 582), (716, 583), (716, 584))],
    "sad": [((727, 530), (729, 540), (726, 548)), ((722, 551), (720, 552), (719, 553)),
            ((724, 560), (724, 570), (719, 578)), ((717, 581), (716, 582), (716, 584))],
}
FACE_BOTTOM = [
    ((723, 594), (722, 610), (707, 619)),     # small round chin
    ((698, 630), (700, 642), (690, 653)),     # jowl
    ((670, 670), (642, 678), (620, 680)),     # under-jaw
    ((616, 694), (610, 708), (606, 722)),     # neck front, tucked into the tunic
    ((600, 742), (598, 758), (596, 772)),
    ((540, 780), (480, 780), (452, 770)),     # neck base (hidden by the body)
    ((442, 744), (440, 712), (424, 690)),     # back of the neck
    ((408, 672), (390, 656), (372, 646)),     # nape into the hair
]
HAIR_BACK = [[360, 633], [352, 612], [338, 623], [334, 601], [318, 606]]
HAIR_BOWL = [((268, 540), (260, 420), (300, 330)), ((340, 232), (440, 182), (540, 182)),
             ((640, 182), (712, 250), (730, 320)), ((733, 330), (735, 338), (735, 345))]
FRINGE = [[735, 345], [722, 362], [734, 371], [716, 384], [712, 388]]


def head_outline(mouth):
    pts = [list(p) for p in FRINGE]
    pts += chain((712, 388), FACE_TOP)[1:]
    pts += chain((728, 520), LIPS[mouth])[1:]
    pts += chain((716, 584), FACE_BOTTOM)[1:]
    pts += [list(p) for p in HAIR_BACK]
    pts += chain((318, 606), HAIR_BOWL)[1:]
    return pts


HEAD_FIXED_CUTS = [
    slit((702, 394), (660, 398), (610, 402), (560, 414), 9),       # bowl hem, chopped into three
    slit((552, 418), (510, 430), (470, 446), (436, 474), 9),
    slit((428, 482), (404, 520), (392, 560), (388, 598), 9),
    slit((520, 470), (470, 470), (462, 548), (522, 560), 13),      # ear C
    slit((508, 494), (488, 500), (488, 528), (508, 534), 7),       # ear curl
    slit((560, 200), (590, 250), (610, 310), (612, 370), 7),       # hair strands
    slit((500, 196), (500, 260), (490, 320), (470, 380), 7),
    slit((430, 214), (400, 270), (380, 330), (372, 400), 7),
    slit((360, 270), (330, 330), (318, 400), (320, 470), 6),
    slit((640, 220), (670, 260), (690, 300), (700, 340), 6),
    slit((652, 474), (600, 510), (612, 580), (676, 594), 11),      # chubby cheek (kept)
    slit((733, 507), (737, 505), (741, 502), (744, 498), 4),       # nostril
]
EYES = {
    "open": [slit((664, 448), (672, 440), (684, 440), (694, 447), 13)],
    "squint": [slit((662, 438), (672, 441), (682, 445), (694, 450), 7),     # squeezed chevron
               slit((662, 460), (672, 457), (682, 453), (694, 450), 7),
               slit((660, 470), (668, 476), (680, 478), (690, 474), 5)],    # puffy crease under
    "shut": [slit((662, 444), (670, 454), (686, 454), (695, 445), 7),      # lid curved down
             slit((668, 456), (666, 462), (664, 466), (662, 470), 4)],      # lash
    "wide": [punch(679, 446, 10)],
}
BROWS = {
    "neutral": [slit((656, 424), (668, 414), (686, 414), (700, 422), 6)],
    "worried": [slit((652, 430), (668, 424), (686, 414), (702, 404), 6)],   # front end raised
    "raised": [slit((654, 414), (666, 402), (686, 400), (702, 408), 6)],
}
MOUTH_CUTS = {
    "pout": [slit((712, 562), (716, 558), (718, 553), (718, 548), 4)],
    "blubber": [slit((718, 556), (712, 562), (706, 566), (700, 566), 5),
                slit((728, 590), (720, 596), (712, 598), (704, 596), 5)],   # wobble under the lip
    "surprised": [punch(722, 553, 3.5)],
    "sad": [slit((718, 554), (712, 560), (706, 566), (700, 570), 5)],
}
TEAR_PATH = ((672, 466), (668, 500), (682, 560), (694, 612))       # from under the eye down the cheek


def bez1(p0, p1, p2, p3, t):
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3


def teardrop(cx, cy, r=8.0, n=28):
    """Drop with a point upward."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        x = r * math.sin(a)
        y = r * math.cos(a)
        if y < 0:  # upper half pulled into a point
            y *= 2.1
            x *= (1 + y / (2.1 * r)) ** 1.2 if y > -2.1 * r else 0
        pts.append([cx + x, cy - y])
    return pts


def head_part(face):
    cuts = list(HEAD_FIXED_CUTS) + EYES[face["eyes"]] + BROWS[face["brows"]] + MOUTH_CUTS[face["mouth"]]
    for t in face.get("tears", []):
        x, y = bez1(*TEAR_PATH, min(max(t, 0.0), 1.0))
        cuts.append(teardrop(x, y))
    return head_outline(face["mouth"]), cuts


# ------------------------------------------------------------------------------------------------ body (local)
FEET = (520.0, 1418.0)
SHOULDER_NEAR = (512.0, 780.0)
SHOULDER_FAR = (470.0, 772.0)


def body_part():
    torso = chain((600, 706), [
        ((640, 740), (650, 780), (652, 830)),        # chest
        ((700, 870), (712, 930), (690, 968)),        # round little belly
        ((690, 1040), (690, 1100), (684, 1150)),     # tunic flares to the hem
    ])
    torso += [[660, 1136], [640, 1160], [612, 1140], [612, 1158], [590, 1140], [566, 1160], [540, 1142], [514, 1162], [488, 1142],
              [462, 1160], [438, 1140], [412, 1158], [386, 1140], [366, 1156], [356, 1146]]   # ragged hem
    torso += chain((356, 1146), [
        ((358, 1060), (362, 990), (372, 940)),       # back
        ((380, 860), (392, 790), (430, 740)),        # back of shoulder
        ((470, 712), (540, 700), (600, 706)),
    ])[1:]
    near_leg = chain((560, 1130), [((572, 1240), (590, 1330), (584, 1430)), ((582, 1460), (582, 1470), (588, 1478)),
                                   ((620, 1486), (652, 1494), (654, 1504)), ((610, 1510), (570, 1510), (542, 1506)),
                                   ((536, 1480), (532, 1440), (530, 1400)), ((524, 1320), (514, 1230), (500, 1130))])
    far_leg = chain((486, 1130), [((496, 1240), (512, 1330), (506, 1430)), ((504, 1460), (504, 1470), (510, 1478)),
                                  ((540, 1486), (570, 1494), (572, 1504)), ((530, 1510), (490, 1510), (464, 1506)),
                                  ((458, 1480), (454, 1440), (452, 1400)), ((446, 1320), (436, 1230), (424, 1130))])
    cuts_t = [slit((380, 962), (450, 976), (560, 980), (664, 966), 9),      # rope belt
              slit((600, 984), (612, 1010), (606, 1040), (596, 1060), 6),   # knot tail
              slit((420, 1020), (440, 1070), (450, 1110), (452, 1140), 6),  # tunic folds
              slit((560, 1000), (566, 1050), (570, 1100), (574, 1130), 6),
              slit((610, 760), (600, 800), (600, 840), (612, 880), 6)]
    cuts_l = [slit((548, 1452), (560, 1462), (576, 1466), (590, 1462), 5),  # rag wraps at the ankles
              slit((470, 1452), (482, 1462), (498, 1466), (512, 1462), 5)]
    def kid(poly, cx):  # shorter, chunkier legs
        return [[cx + (x - cx) * 1.3, 1130 + (y - 1130) * 0.74] for x, y in poly]
    near_leg, far_leg = kid(near_leg, 556), kid(far_leg, 478)
    cuts_l = [kid(cuts_l[0], 556), kid(cuts_l[1], 478)]
    return [(torso, cuts_t), (near_leg, cuts_l[:1]), (far_leg, cuts_l[1:])]


UPPER_ARM_LEN, FOREARM_LEN = 195.0, 180.0
HAND_REACH = FOREARM_LEN + 20.0
EYE = (679.0, 446.0)


def angle_of(v):
    """Absolute rotation (deg) that turns the local +y arm axis onto world direction v."""
    return math.degrees(math.atan2(-v[0], v[1]))


def ik(shoulder, target, elbow_down=True):
    """Two-link IK; returns absolute (upper, fore) angles.  The elbow takes the FORWARD (+x) solution: in shadow an
    arm only reads where it crosses empty space, so a hand-to-face gesture needs the elbow out in front."""
    S, T = np.asarray(shoulder, float), np.asarray(target, float)
    D = T - S
    d = min(np.linalg.norm(D), UPPER_ARM_LEN + HAND_REACH - 1.0)
    u = D / (np.linalg.norm(D) + 1e-9)
    ca = (UPPER_ARM_LEN ** 2 + d * d - HAND_REACH ** 2) / (2 * UPPER_ARM_LEN * d)
    a = math.acos(max(-1.0, min(1.0, ca)))
    best = None
    for sgn in (1, -1):
        c, s_ = math.cos(sgn * a), math.sin(sgn * a)
        dir_u = np.array([u[0] * c - u[1] * s_, u[0] * s_ + u[1] * c])
        E = S + dir_u * UPPER_ARM_LEN
        if best is None or E[0] > best[1][0]:
            best = (dir_u, E)
    dir_u, E = best
    return angle_of(dir_u), angle_of(T - E)


def upper_arm_part():
    """Local: pivot at (0,0) shoulder, arm hangs along +y. Sleeve with a ragged cuff."""
    out = chain((-40, -10), [((-44, 60), (-42, 130), (-36, 186)), ])
    out += [[-26, 198], [-14, 186], [-2, 200], [10, 186], [22, 198], [34, 184]]
    out += chain((34, 184), [((40, 120), (44, 50), (36, -14)), ((20, -40), (-24, -38), (-40, -10))])[1:]
    return out, [slit((-20, 40), (-24, 90), (-20, 130), (-14, 170), 6)]


def forearm_part():
    """Local: pivot at elbow (0,0), forearm along +y, mitten hand with a thumb at the end."""
    out = chain((-22, -6), [((-24, 60), (-22, 120), (-26, 150)),
                            ((-36, 176), (-28, 206), (-4, 210)),       # mitten back
                            ((18, 212), (30, 196), (26, 176)),
                            ((40, 170), (44, 152), (30, 146)),         # thumb
                            ((22, 146), (22, 120), (22, 60)),
                            ((22, 20), (16, -14), (-22, -6))])
    return out, [slit((-8, 170), (-6, 182), (-2, 192), (4, 198), 4)]   # finger line


# ------------------------------------------------------------------------------------------------ transforms
def rot(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def place(poly, R, t):
    P = np.asarray(poly, dtype=float)
    return (P @ R.T + t).tolist()


def pose_parts(pose):
    """Returns a list of (outline, cuts, z) in world coords and the rod lines."""
    parts = []
    lean = pose.get("lean", 0.0)
    R0 = rot(lean)
    base = np.array(FEET) + np.array(pose.get("offset", (0.0, 0.0)))
    to_world = lambda p: (np.asarray(p) - np.array(FEET)) @ R0.T + base  # noqa: E731
    for outline, cuts in body_part():
        parts.append((place(np.asarray(outline) - FEET, R0, base), [place(np.asarray(c) - FEET, R0, base) for c in cuts], 1))
    # head
    neck_w = to_world(NECK)
    Rh = rot(lean + pose.get("neck", 0.0))
    ho, hc = head_part(pose["face"])
    parts.append((place(np.asarray(ho) - NECK, Rh, neck_w), [place(np.asarray(c) - NECK, Rh, neck_w) for c in hc], 2))
    rods = [[to_world((440, 1000)).tolist(), (to_world((440, 1000)) + np.array([-60, 900])).tolist()]]
    for side, shoulder, z in (("far", SHOULDER_FAR, 0), ("near", SHOULDER_NEAR, 3)):
        sh_w = to_world(shoulder)
        tgt = pose.get(side + "_hand_on_head")
        if tgt is not None:   # head-local point -> world, then IK; jitter rides on top as joint offsets
            T = (np.asarray(tgt, float) - NECK) @ Rh.T + neck_w
            up_abs, fo_abs = ik(sh_w, T)
            pose = dict(pose)
            pose[side + "_shoulder"] = up_abs - lean + pose.get(side + "_shoulder_jit", 0.0)
            pose[side + "_elbow"] = fo_abs - up_abs + pose.get(side + "_elbow_jit", 0.0)
        Ru = rot(lean + pose.get(side + "_shoulder", 0.0))
        uo, uc = upper_arm_part()
        parts.append((place(uo, Ru, sh_w), [place(c, Ru, sh_w) for c in uc], z))
        el_w = sh_w + np.array([0.0, UPPER_ARM_LEN]) @ Ru.T
        Rf = rot(lean + pose.get(side + "_shoulder", 0.0) + pose.get(side + "_elbow", 0.0))
        fo, fc = forearm_part()
        parts.append((place(fo, Rf, el_w), [place(c, Rf, el_w) for c in fc], z))
        hand = el_w + np.array([0.0, HAND_REACH]) @ Rf.T
        if pose.get("arm_rods", True):
            rods.append([hand.tolist(), (hand + np.array([-30 if side == "near" else -80, 900])).tolist()])
    return parts, rods


# ------------------------------------------------------------------------------------------------ rendering
VIEW = dict(x0=170.0, y0=120.0, scale=0.68, w=700, h=900)  # world window -> image


def render_pose(pose, ss=2, view=VIEW):
    W, H = view["w"] * ss, view["h"] * ss
    k = view["scale"] * ss
    tx = lambda poly: [((x - view["x0"]) * k, (y - view["y0"]) * k) for x, y in poly]  # noqa: E731
    trans = np.ones((H, W), dtype=np.float64)
    parts, rods = pose_parts(pose)
    for outline, cuts, _z in parts:
        m = Image.new("L", (W, H), 255)
        d = ImageDraw.Draw(m)
        d.polygon(tx(outline), fill=0)
        for c in cuts:
            d.polygon(tx(c), fill=255)
        trans *= np.asarray(m, dtype=np.float64) / 255.0
    m = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(m)
    for a, b in rods:
        d.line(tx([a, b]), fill=0, width=max(1, int(5 * k)))
    trans *= np.asarray(m, dtype=np.float64) / 255.0
    img = Image.fromarray((trans * 255).astype(np.uint8)).resize((view["w"], view["h"]), Image.LANCZOS)
    return img


def projected(img, blur=1.4):
    sh = np.asarray(img.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float64) / 255.0
    h, w = sh.shape
    x = np.linspace(0, 1, w)[None, :, None]
    bg = np.array([196, 228, 236]) * (1 - x) + np.array([236, 178, 168]) * x
    bg = np.repeat(bg, h, axis=0)
    out = bg * sh[..., None] + np.array([28, 26, 30]) * (1 - sh[..., None])
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


# ------------------------------------------------------------------------------------------------ motion
REST = {"near_hand_on_head": None, "far_hand_on_head": None, "lean": 0.0, "neck": 0.0, "near_shoulder": 4.0, "near_elbow": -6.0, "far_shoulder": 8.0, "far_elbow": -10.0,
        "face": {"eyes": "open", "brows": "neutral", "mouth": "pout", "tears": []}}


def P(**kw):
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in REST.items()}
    face = dict(p["face"])
    face.update(kw.pop("face", {}))
    p.update(kw)
    p["face"] = face
    return p


HEAD_IN_HANDS = dict(lean=8.0, neck=26.0, near_hand_on_head=(772.0, 470.0), far_hand_on_head=(758.0, 520.0))

# Demo script: (seconds, pose).  Poses are HELD; the puppeteer moves joints over a few frames between them.
DEMO = [
    (0.0, P()),
    (1.5, P(face={"brows": "worried", "mouth": "sad"})),
    (3.0, P(neck=8.0, face={"eyes": "squint", "brows": "worried", "mouth": "blubber"})),
    (4.2, P(neck=10.0, face={"eyes": "squint", "brows": "worried", "mouth": "blubber", "tears": [0.0]})),
    (6.0, P(**HEAD_IN_HANDS, face={"eyes": "shut", "brows": "worried", "mouth": "blubber", "tears": [0.4]})),
    (8.5, P(neck=-6.0, face={"eyes": "wide", "brows": "raised", "mouth": "surprised", "tears": [0.9]})),
    (10.0, P(neck=4.0, face={"eyes": "shut", "brows": "worried", "mouth": "sad", "tears": []})),
]


def lerp_pose(a, b, t):
    out = dict(b)
    for k in ("lean", "neck", "near_shoulder", "near_elbow", "far_shoulder", "far_elbow"):
        out[k] = a[k] + (b[k] - a[k]) * t
    out["face"] = dict(b["face"]) if t >= 0.5 else dict(a["face"])
    for side in ("near", "far"):
        key = side + "_hand_on_head"
        out[key] = b.get(key) if t >= 0.5 else a.get(key)
        for k2 in (side + "_shoulder", side + "_elbow"):
            out[k2] = a.get(k2, 0.0) + (b.get(k2, 0.0) - a.get(k2, 0.0)) * t
    return out


def handheld(t, seed=7):
    """Slow wobble of a hand holding rods: sum of incommensurate sines (deterministic)."""
    rng = np.random.default_rng(seed)
    def n(amp, f0):
        ph = rng.uniform(0, 2 * math.pi, 3)
        return amp * (math.sin(2 * math.pi * f0 * t + ph[0]) * 0.6 + math.sin(2 * math.pi * f0 * 1.73 * t + ph[1]) * 0.3
                      + math.sin(2 * math.pi * f0 * 2.9 * t + ph[2]) * 0.1)
    return {"dx": n(5.0, 0.31), "dy": n(4.0, 0.23), "lean": n(0.9, 0.27), "neck": n(1.6, 0.41),
            "near_shoulder": n(3.0, 0.37), "near_elbow": n(3.0, 0.53), "far_shoulder": n(2.5, 0.33),
            "far_elbow": n(2.5, 0.47)}


def demo_frames(fps=8, length=12.0, move_frames=3, wobble=True):
    frames = []
    keys = DEMO
    for i in range(int(length * fps)):
        t = i / fps
        k = max(j for j in range(len(keys)) if keys[j][0] <= t)
        a = keys[k - 1][1] if k > 0 else keys[0][1]
        b = keys[k][1]
        u = min(1.0, (t - keys[k][0]) * fps / move_frames + 1.0 / move_frames) if k > 0 else 1.0
        pose = lerp_pose(a, b, u)
        # tears slide while held
        if pose["face"].get("tears"):
            held = t - keys[k][0]
            pose["face"]["tears"] = [min(1.0, tt + held * 0.18) for tt in pose["face"]["tears"]]
        if wobble:
            h = handheld(t)
            pose = dict(pose)
            pose["offset"] = (h["dx"], h["dy"])
            for key in ("lean", "neck", "near_shoulder", "near_elbow", "far_shoulder", "far_elbow"):
                side = key.split("_")[0]
                if side in ("near", "far") and pose.get(side + "_hand_on_head") is not None:
                    pose[key + "_jit"] = h[key] * 0.4
                else:
                    pose[key] = pose[key] + h[key]
        frames.append(pose)
    return frames


def expression_sheet(out):
    combos = [("normal", {}), ("worried", {"brows": "worried", "mouth": "sad"}),
              ("blubber", {"eyes": "squint", "brows": "worried", "mouth": "blubber", "tears": [0.2]}),
              ("crying", {"eyes": "shut", "brows": "worried", "mouth": "blubber", "tears": [0.1, 0.6]}),
              ("surprised", {"eyes": "wide", "brows": "raised", "mouth": "surprised"}),
              ("sad", {"eyes": "shut", "brows": "worried", "mouth": "sad"})]
    view = dict(x0=430.0, y0=300.0, scale=1.0, w=360, h=360)
    tiles = []
    for name, face in combos:
        im = projected(render_pose(P(face=face), ss=3, view=view), blur=0.8)
        ImageDraw.Draw(im).text((10, 8), name, fill=(40, 40, 40))
        tiles.append(im)
    sheet = Image.new("RGB", (360 * 3, 360 * 2))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 3) * 360, (i // 3) * 360))
    sheet.save(out / "boy_expressions.png")
    poses = [("rest", P()), ("head in hands", P(**HEAD_IN_HANDS, face={"eyes": "shut", "brows": "worried",
                                                                       "mouth": "blubber", "tears": [0.4]})),
             ("arm out", P(near_shoulder=-70.0, near_elbow=-20.0, face={"brows": "raised", "mouth": "surprised",
                                                                        "eyes": "wide"}))]
    sheet = Image.new("RGB", (700 * 3, 900))
    for i, (name, pose) in enumerate(poses):
        im = projected(render_pose(pose))
        ImageDraw.Draw(im).text((12, 10), name, fill=(40, 40, 40))
        sheet.paste(im, (i * 700, 0))
    sheet.save(out / "boy_poses.png")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "rig_out")
    (out / "frames").mkdir(parents=True, exist_ok=True)
    expression_sheet(out)
    frames = [projected(render_pose(p)) for p in demo_frames()]
    for i, im in enumerate(frames):
        im.save(out / "frames" / f"boy_{i:03d}.png")
    small = [f.resize((350, 450), Image.LANCZOS) for f in frames]
    small[0].save(out / "boy_demo.gif", save_all=True, append_images=small[1:], duration=125, loop=0)
    print("frames", len(frames), "->", out)


# ------------------------------------------------------------------------------------------------ clips for the gobo
# A clip = list of (seconds, pose, move_frames).  Rendered at the clip fps WITHOUT wobble (the wobble is live in UE);
# identical frames are de-duplicated by the packer, so holds and repeated rub poses cost one atlas cell each.
RUB_A = dict(HEAD_IN_HANDS, near_hand_on_head=(772.0, 462.0), far_hand_on_head=(756.0, 512.0))
RUB_B = dict(HEAD_IN_HANDS, near_hand_on_head=(766.0, 486.0), far_hand_on_head=(762.0, 496.0))
SOB = {"eyes": "squint", "brows": "worried", "mouth": "blubber"}


def rubbing_eyes_clip():
    """The established nine-second beat sheet, now with real-time move durations."""
    keys = [(0.0, P(), 0.0, "snap"),
            (1.0, P(face={"brows": "worried", "mouth": "sad"}), 2.0 / 8.0, "ease_in_out"),
            (2.0, P(neck=8.0, face=dict(SOB)), 3.0 / 8.0, "ease_in_out"),
            (3.0, P(**RUB_A, face=dict(SOB, eyes="shut")), 3.0 / 8.0, "ease_in_out")]
    t = 3.5
    for k in range(8):                                  # rub, rub, rub...
        keys.append((t, P(**(RUB_B if k % 2 == 0 else RUB_A), face=dict(SOB, eyes="shut")),
                     2.0 / 8.0, "ease_in_out"))
        t += 0.25
    keys += [(5.5, P(neck=10.0, face=dict(SOB, eyes="shut", tears=[0.0])), 3.0 / 8.0, "ease_in_out"),
             (7.6, P(neck=14.0, face={"eyes": "shut", "brows": "worried", "mouth": "sad"}),
              3.0 / 8.0, "ease_in_out")]
    return keys, 9.0


def hand_world(pose, side):
    """Return the mitten centre for a pose, including point-target IK when active."""
    lean = pose.get("lean", 0.0)
    root_rotation = rot(lean)
    base = np.asarray(FEET) + np.asarray(pose.get("offset", (0.0, 0.0)))
    to_world = lambda point: (np.asarray(point) - np.asarray(FEET)) @ root_rotation.T + base  # noqa: E731
    shoulder = SHOULDER_NEAR if side == "near" else SHOULDER_FAR
    shoulder_world = to_world(shoulder)
    shoulder_angle = lean + pose.get(side + "_shoulder", 0.0)
    elbow_relative = pose.get(side + "_elbow", 0.0)
    target = pose.get(side + "_hand_on_head")
    if target is not None:
        neck_world = to_world(NECK)
        head_rotation = rot(lean + pose.get("neck", 0.0))
        target_world = (np.asarray(target) - NECK) @ head_rotation.T + neck_world
        upper_absolute, fore_absolute = ik(shoulder_world, target_world)
        shoulder_angle = upper_absolute
        elbow_relative = fore_absolute - upper_absolute
    upper_rotation = rot(shoulder_angle)
    elbow_world = shoulder_world + np.array([0.0, UPPER_ARM_LEN]) @ upper_rotation.T
    fore_rotation = rot(shoulder_angle + elbow_relative)
    return elbow_world + np.array([0.0, HAND_REACH]) @ fore_rotation.T


def hand_target_for_pose(pose, key):
    """Resolve a non-IK arm pose to the equivalent head-local target point."""
    existing = pose.get(key)
    if existing is not None:
        return tuple(existing)
    side = key.split("_", 1)[0]
    lean = pose.get("lean", 0.0)
    root_rotation = rot(lean)
    base = np.asarray(FEET) + np.asarray(pose.get("offset", (0.0, 0.0)))
    neck_world = (np.asarray(NECK) - np.asarray(FEET)) @ root_rotation.T + base
    head_rotation = rot(lean + pose.get("neck", 0.0))
    local = (hand_world(pose, side) - neck_world) @ head_rotation + np.asarray(NECK)
    return tuple(local)


def clip_frames(keys, length, fps=DEFAULT_DISPLAY_FPS, tear_speed=0.45, face_swap=0.5):
    return shared_clip_frames(
        keys, length, fps=fps, tear_speed=tear_speed, face_swap=face_swap,
        point_keys=("near_hand_on_head", "far_hand_on_head"), point_resolver=hand_target_for_pose,
    ).poses


def render_clip(keys, length, out, fps=DEFAULT_DISPLAY_FPS, window=(540.0, 560.0, 1450.0),
                cell_px=640, max_cells=None, tear_speed=0.45, face_swap=0.5, render_scale=1.0):
    """Sharp transmission frames (white = light passes) of a square world window, one PNG per clip frame."""
    cx, cy, size = window
    render_px = scaled_render_size(cell_px, render_scale)
    view = dict(x0=cx - size / 2, y0=cy - size / 2, scale=render_px / size, w=render_px, h=render_px)
    return shared_render_clip(
        keys, length, Path(out), lambda pose: render_pose(pose, ss=2, view=view), fps=fps,
        max_cells=max_cells, tear_speed=tear_speed, face_swap=face_swap,
        point_keys=("near_hand_on_head", "far_hand_on_head"), point_resolver=hand_target_for_pose,
    )
