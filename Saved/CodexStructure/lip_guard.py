"""Shared LIP GUARD for floor builders (30 Sep). The generator fault it closes: every floor slab laid by
floors_to_stage_apply.py (29 Sep) and landscape_floors_apply.py (30 Sep) ignored the stage-front lip, except P01's (the
only TRIM_P01_AT_LIP case), so four mouths had a slab at -5 cm burying the fascia and house floor that the shared curtain
pile hangs down (to z -71.3, Soft goods). Fixed at P03/P05/P06 by mouth_floor_apply.py; P02 needs a notch.

Rule: a floor slab may not overlap, in any enabled portal's frame (the Passage route start), the house-side band
x in [lip - 2600, lip - 1] cm, |y| <= the portal's house-floor half-width, while its top is above -72 cm. The overlap is a
true 2D separating-axis test between the slab's rotated rectangle and the band, so a slab laid in another frame (P02's
floors sit in S2's dock frame, 66.5 deg off P02's mouth) is caught too.

Loaded with runpy.run_path (no module caching, no UE objects at module level):
    guard = runpy.run_path(os.path.join(HERE, "lip_guard.py"))
    bad = guard["violations"](guard["mouth_frames"](actors), pieces)   # pieces: [{"label","loc","size","yaw"}] cm, cube slabs
"""
import math

import unreal

PILE_Z_CM = -72.0
BAND_DEPTH_CM = 2600.0


def mouth_frames(actors):
    frames = []
    for a in actors:
        if a.get_class().get_name() != "InfinityStageStructureActor":
            continue
        portal = a.get_editor_property("portal")
        if not portal.get_editor_property("enabled"):
            continue
        route = a.get_editor_property("passage").get_editor_property("route")
        st = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
        t = st.translation
        frames.append({"structure": a.get_actor_label(), "x": t.x, "y": t.y, "z": t.z, "yaw": st.rotation.rotator().yaw,
                       "lip": -float(portal.get_editor_property("forestage_depth_cm")),
                       "half": float(portal.get_editor_property("house_floor_half_width_cm"))})
    return frames


def _to_frame(f, x, y):
    c, s = math.cos(math.radians(f["yaw"])), math.sin(math.radians(f["yaw"]))
    dx, dy = x - f["x"], y - f["y"]
    return (c * dx + s * dy, -s * dx + c * dy)


def _overlap(poly, rect):
    """Separating-axis test between a convex quad (4 points) and an axis-aligned rectangle (x0, x1, y0, y1)."""
    x0, x1, y0, y1 = rect
    rpts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    axes = [(1.0, 0.0), (0.0, 1.0)]
    for i in range(2):
        ex, ey = poly[i + 1][0] - poly[i][0], poly[i + 1][1] - poly[i][1]
        n = math.hypot(ex, ey) or 1.0
        axes.append((-ey / n, ex / n))
    for ax, ay in axes:
        a = [px * ax + py * ay for px, py in poly]
        b = [px * ax + py * ay for px, py in rpts]
        if max(a) <= min(b) or max(b) <= min(a):
            return False
    return True


def violations(frames, pieces):
    out = []
    for p in pieces:
        (lx, ly, lz), (sx, sy, sz), yaw = p["loc"], p["size"], p.get("yaw", 0.0)
        top = lz + sz / 2.0
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        world = [(lx + c * u - s * v, ly + s * u + c * v) for u, v in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2))]
        for f in frames:
            if top - f["z"] <= PILE_Z_CM:
                continue
            poly = [_to_frame(f, x, y) for x, y in world]
            if _overlap(poly, (f["lip"] - BAND_DEPTH_CM, f["lip"] - 1.0, -f["half"], f["half"])):
                out.append(f"{p['label']} reaches downstage of {f['structure']}'s lip (top {top:.1f} cm)")
    return out
