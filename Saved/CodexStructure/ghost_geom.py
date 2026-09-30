"""Why the Scene 4 hold is dark from the stop (30 Sep diagnosis for the conductor / Look & camera).

The box during the hold, in the hinge frame (world x - 11168.47, z): the camera at the stop
(-500, 0, 180) looks down -15 deg; the box (floor, side walls, far wall; the roof is upright on
the far wall and the lattice is flown, so the trough is OPEN on its roof side) at the rise's
pitch. The ghost lamp: box (2500, -400, 188), point, 60 cd, attenuation 1500 cm, shadowed
(live facts: ghost_light_facts.json; dimensions: hangar_build.py's Scene 4 defaults).

Pure geometry: planes for floor, side walls and far wall, no GI, a ~60 x 34 deg frame around the
-15 deg look. It proves geometric visibility, NOT that anything reads on screen.
Counterfactuals:  python ghost_geom.py [reach_cm] [lamp_box_x_cm]
    python ghost_geom.py            as built (nothing lit is visible until about +6 s)
    python ghost_geom.py 1e9        reach removed: occlusion alone (max 0.08 lux visible at +3 s)
    python ghost_geom.py 1500 300   lamp 3 m inside the mouth (bulb in view from +6 s, not +9.5 s)
Offline: plain Python, touches nothing in Unreal."""
import math
import sys

D, W, H = 6000.0, 1000.0, 3000.0
R = float(sys.argv[1]) if len(sys.argv) > 1 else 1500.0
LAMP = (float(sys.argv[2]) if len(sys.argv) > 2 else 2500.0, -400.0, 188.0)
CD = 60.0
CAM = (-500.0, 0.0, 180.0)
START, LAND = -3.5667, 16.0   # LS_S4_HangarRise root pitch keys (-90 -> 0), AUTO = smoothstep


def pitch(t):
    u = min(1.0, max(0.0, (t - START) / (LAND - START)))
    return -90.0 + 90.0 * (3 * u * u - 2 * u ** 3)


def to_box(p, P):
    """Hinge-frame world vector -> box coordinates (x into the box, y, z off the floor)."""
    a = math.radians(p)
    d, n = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    return (P[0] * d[0] + P[2] * d[1], P[1], P[0] * n[0] + P[2] * n[1])


# (axis, value, bounds on the other two box axes, the interior side of the face)
PLANES = [(2, 0.0, ((0, D), (-W, W)), +1),                                  # floor, top face
          (1, -W, ((0, D), (0, H)), +1), (1, W, ((0, D), (0, H)), -1),      # side walls, inner faces
          (0, D, ((-W, W), (0, H)), -1)]                                    # far wall, inner face


def first_hit(p, v):
    c, dv = to_box(p, CAM), to_box(p, v)
    best = None
    for ax, val, bnds, side in PLANES:
        if abs(dv[ax]) < 1e-9:
            continue
        t = (val - c[ax]) / dv[ax]
        if t <= 1:
            continue
        q = [c[i] + t * dv[i] for i in range(3)]
        o = [i for i in range(3) if i != ax]
        if all(bnds[k][0] <= q[o[k]] <= bnds[k][1] for k in range(2)):
            front = (c[ax] - val) * side > 0          # the camera is on the interior side
            if best is None or t < best[0]:
                best = (t, q, ax, side, front)
    return best


def lamp_lux(q, ax, side, front):
    """Illuminance from the lamp at a hit point (UE inverse square x the attenuation window)."""
    if not front:
        return 0.0                                     # the camera sees the outside (underside)
    d = math.dist(q, LAMP)
    ln = (LAMP[ax] - q[ax]) * side                     # the lamp on the lit side of that face?
    if d >= R or ln <= 0:
        return 0.0
    return CD / (d / 100.0) ** 2 * (ln / d) * (1 - (d / R) ** 4) ** 2


def bulb_visible(p, Q=LAMP):
    c = to_box(p, CAM)
    if c[2] > 0:
        return True                                    # camera above the floor plane
    s = -c[2] / (Q[2] - c[2])
    return c[0] + s * (Q[0] - c[0]) < 0                # the sight line clears the lip first


def main():
    print(f"reach {R:g} cm, lamp at box x {LAMP[0]:g}")
    print("t_s   pitch  cam_vs_floor_plane  bulb_visible  frame_lit%  max_lux  where the -15 deg look lands")
    for t in (0, 3, 6, 8, 9.5, 11, 12, 14, 16):
        p = pitch(t)
        lit = tot = 0
        mx = 0.0
        for i in range(-20, 21):
            for j in range(-12, 13):
                yaw, pit = math.radians(i * 30 / 20), math.radians(-15 + j * 17 / 12)
                v = (math.cos(pit) * math.cos(yaw), math.cos(pit) * math.sin(yaw), math.sin(pit))
                h = first_hit(p, v)
                tot += 1
                if h:
                    e = lamp_lux(h[1], h[2], h[3], h[4])
                    mx = max(mx, e)
                    lit += e > 0.05
        h = first_hit(p, (math.cos(math.radians(-15)), 0, math.sin(math.radians(-15))))
        where = ("passes out of the open trough" if not h else
                 f"{('far wall', 'side wall', 'floor')[h[2]]} {'inside' if h[4] else 'OUTSIDE/underside'} at box ({h[1][0]:.0f},{h[1][2]:.0f})")
        print(f"{t:5.1f} {p:6.1f}  {to_box(p, CAM)[2]:+7.0f} cm  {str(bulb_visible(p)):5}  {100 * lit / tot:5.1f}%  {mx:6.3f}  {where}")


if __name__ == "__main__":
    main()
