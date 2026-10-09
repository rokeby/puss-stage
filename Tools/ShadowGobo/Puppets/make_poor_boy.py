"""Shadow-puppet boy v2: child proportions, bowl cut / hood variants sharing one face profile."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from puppet_cut import chain, slit, punch, render  # noqa: E402
import puppet_cut as boy  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
boy.OUT = OUT

# Shared face profile, forehead (712,388) -> under-jaw (620,680).
FACE = [
    ((722, 405), (728, 425), (724, 442)),     # big round forehead to soft brow
    ((722, 450), (719, 455), (716, 460)),     # nose root
    ((728, 476), (746, 488), (754, 500)),     # button nose, upturned
    ((756, 512), (744, 520), (728, 520)),     # nose underside
    ((729, 530), (733, 538), (732, 546)),     # upper lip, pouting a little
    ((727, 549), (723, 551), (722, 553)),     # mouth
    ((729, 558), (731, 568), (724, 576)),     # lower lip
    ((718, 580), (716, 582), (716, 584)),
    ((723, 594), (722, 610), (707, 619)),     # small round chin
    ((698, 630), (700, 642), (690, 653)),     # jowl
    ((670, 670), (642, 678), (620, 680)),     # under-jaw back to neck
]
FACE_CUTS = [
    slit((664, 448), (672, 440), (684, 440), (694, 447), 13),    # eye (almond)
    slit((656, 424), (668, 414), (686, 414), (700, 422), 6),     # brow
    slit((652, 474), (600, 510), (612, 580), (676, 594), 11),    # chubby cheek ball
    slit((733, 507), (737, 505), (741, 502), (744, 498), 4),     # nostril
    slit((712, 562), (716, 558), (718, 553), (718, 548), 4),     # mouth corner
    slit((702, 630), (686, 648), (660, 662), (636, 664), 8),     # double-chin crease
    punch(640, 520, 4.2), punch(654, 508, 3.8), punch(632, 536, 3.4), punch(658, 526, 3.0),  # freckles
]
BODY_FRONT = [  # from under-jaw (620,680) down the front to the base, then base to back shoulder (272,905)
    ((632, 690), (640, 700), (632, 706)),     # ragged neckline teeth
    ((646, 708), (652, 716), (648, 724)),
    ((684, 770), (702, 840), (708, 905)),     # chest
    ((560, 916), (400, 916), (272, 905)),     # base cut
]


def stitches(cuts, x, y, s, n=3, tilt=6):
    corners = [(x, y), (x + s, y - tilt), (x + s + 4, y + s - tilt), (x + 2, y + s), (x, y)]
    for a, b in zip(corners, corners[1:]):
        for k in range(n):
            t0, t1 = k / n + 0.05, (k + 1) / n - 0.09
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p3 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            cuts.append(slit(p0, p0, p3, p3, 5))


def lacing(cuts, x, y):
    for k in range(3):
        yy = y + k * 26
        cuts.append(slit((x - 12, yy), (x - 4, yy + 6), (x + 4, yy + 10), (x + 12, yy + 16), 6))
        cuts.append(slit((x + 12, yy), (x + 4, yy + 6), (x - 4, yy + 10), (x - 12, yy + 16), 6))


# ---------------------------------------------------------------- C: bowl cut
outline = [[735, 345], [722, 362], [734, 371], [716, 384], [712, 388]]          # chopped fringe tufts
outline += chain((712, 388), FACE)[1:]
outline += chain((620, 680), BODY_FRONT)[1:]
outline += chain((272, 905), [
    ((272, 830), (300, 762), (350, 722)),     # narrow back shoulder
])[1:]
outline += [[340, 706], [362, 699], [352, 685], [378, 680]]                       # ragged back collar
outline += chain((378, 680), [((385, 660), (381, 640), (372, 620))])[1:]          # nape
outline += [[360, 633], [352, 612], [338, 623], [334, 601], [318, 606]]           # hair hem tufts at the back
outline += chain((318, 606), [
    ((268, 540), (260, 420), (300, 330)),     # back of the bowl
    ((340, 232), (440, 182), (540, 182)),     # crown
    ((640, 182), (712, 250), (730, 320)),     # front of the bowl
    ((733, 330), (735, 338), (735, 345)),
])[1:]
cuts = list(FACE_CUTS) + [
    # bowl hem across the side of the head, chopped into three cuts, over the ear and down to the nape
    slit((702, 394), (660, 398), (610, 402), (560, 414), 9),
    slit((552, 418), (510, 430), (470, 446), (436, 474), 9),
    slit((428, 482), (404, 520), (392, 560), (388, 598), 9),
    # ear: C plus inner curl
    slit((520, 470), (470, 470), (462, 548), (522, 560), 13),
    slit((508, 494), (488, 500), (488, 528), (508, 534), 7),
    # hair strands from the crown
    slit((560, 200), (590, 250), (610, 310), (612, 370), 7),
    slit((500, 196), (500, 260), (490, 320), (470, 380), 7),
    slit((430, 214), (400, 270), (380, 330), (372, 400), 7),
    slit((360, 270), (330, 330), (318, 400), (320, 470), 6),
    slit((640, 220), (670, 260), (690, 300), (700, 340), 6),
]
lacing(cuts, 650, 748)
stitches(cuts, 400, 800, 64)
cuts.append(slit((300, 860), (340, 840), (400, 846), (440, 870), 7))  # tunic fold
render(outline, cuts, [(480, 910), (400, 1000)], "boyC_bowlcut")

# ---------------------------------------------------------------- D: hood (chaperon) with liripipe, same face
outline = [[728, 330], [722, 352], [716, 372], [712, 388]]                        # hood rim over the forehead
outline += chain((712, 388), FACE)[1:]
outline += chain((620, 680), [
    ((650, 690), (676, 700), (690, 716)),     # cowl front under the chin
    ((700, 780), (706, 850), (708, 905)),
    ((560, 916), (400, 916), (250, 905)),     # base
    ((248, 840), (262, 770), (300, 700)),     # cowl back
    ((292, 640), (290, 590), (300, 540)),
    ((240, 570), (170, 620), (110, 700)),     # liripipe tail
    ((170, 600), (232, 500), (288, 440)),
    ((262, 360), (300, 240), (400, 196)),     # hood crown
    ((520, 150), (680, 200), (728, 330)),
])[1:]
cuts = list(FACE_CUTS) + [
    slit((716, 340), (610, 330), (555, 500), (630, 676), 14),     # hood opening around the face
    slit((708, 352), (690, 362), (676, 378), (668, 396), 7),      # fringe wisps under the rim
    slit((690, 352), (668, 362), (650, 380), (642, 398), 6),
    slit((470, 220), (430, 300), (420, 400), (440, 480), 9),      # hood folds
    slit((360, 330), (340, 420), (350, 520), (380, 590), 8),
    slit((330, 700), (400, 730), (480, 740), (560, 730), 8),      # cowl fold
]
stitches(cuts, 500, 600, 62)
render(outline, cuts, [(480, 910), (400, 1000)], "boyD_hood")
print("ok")
