"""Which of Scene 4's 24 lattice bulbs a -15 deg look-down from the stop can see during the hold
(30 Sep). The lattice is flown at box z 2811 on the trough's OPEN side, outside the floor's
shadow, so unlike the ghost lamp it is in view from the cut. Geometry only: whether 20 cd on
these bulbs READS at the show's exposure is a bench question. Offline: plain Python.
Rails at y -800, 0, 800 and 8 bulbs per rail every 750 cm (hangar_build.py, Scene 4)."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ghost_geom import CAM, bulb_visible, pitch  # noqa: E402

BULBS = [(375 + 750 * i, y, 2811.0) for y in (-800, 0, 800) for i in range(8)]


def world(p, Q):
    a = math.radians(p)
    return (Q[0] * math.cos(a) - Q[2] * math.sin(a), Q[1], Q[0] * math.sin(a) + Q[2] * math.cos(a))


def main():
    print("t_s  pitch  bulbs_clear_of_lip  in_-15deg_frame(+-17 v, +-30 h)  elevation_range_deg")
    for t in (0, 1.5, 3, 4.5, 6, 8):
        p = pitch(t)
        vis = [b for b in BULBS if bulb_visible(p, b)]
        inframe = []
        for b in vis:
            w = world(p, b)
            dx, dy, dz = w[0] - CAM[0], w[1] - CAM[1], w[2] - CAM[2]
            el = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
            if -32 <= el <= 2 and abs(math.degrees(math.atan2(dy, dx))) <= 30:
                inframe.append(el)
        rng = f"{min(inframe):.0f}..{max(inframe):.0f}" if inframe else "-"
        print(f"{t:4.1f} {p:6.1f}  {len(vis):2d}/24  {len(inframe):2d}/24  {rng}")


if __name__ == "__main__":
    main()
