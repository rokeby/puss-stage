"""RECT_FIT checks (8 Oct): angle formula, rectangle inside the disc, negative control on the fit guard."""
import importlib.util
import math
import sys

spec = importlib.util.spec_from_file_location("g", __file__.replace("test_gobo_spot_rectfit.py", "gobo_spot.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ok = 0
fails = []


def check(name, cond):
    global ok
    if cond:
        ok += 1
    else:
        fails.append(name)


D, W = 3000.0, 1692.0
outer = m.variant_props("RECT_FIT", D, W, 100000.0, 4500.0)["outer_cone_angle"]
check("angle_formula", abs(math.tan(math.radians(outer)) - W / (2 * D * m.RECT_FIT_SCALE)) < 1e-9)
R = D * math.tan(math.radians(outer))
half_diag = (W / 2.0) * math.sqrt(1 + 1 / m.RECT_ASPECT ** 2)
check("rect_inside_disc", half_diag <= R + 1e-6)
check("tighter_than_inscribed", outer < m.variant_props("INSCRIBED", D, W, 100000.0, 4500.0)["outer_cone_angle"])
check("gobo_scale", abs(m.GOBO_SCALE["RECT_FIT"] - 0.85) < 1e-12)
# negative control: a scale of 0.9 would put the rectangle's corners outside the disc
check("neg_scale_090_violates", 0.9 * math.sqrt(1 + 1 / m.RECT_ASPECT ** 2) > 1.0)
check("inner_is_outer_minus_1", abs(m.variant_props("RECT_FIT", D, W, 100000.0, 4500.0)["inner_cone_angle"] - (outer - 1.0)) < 1e-9)
print("GOBOSPOT_RECTFIT|passed=%d|failed=%d|%s|outer=%.3f" % (ok, len(fails), fails, outer))
sys.exit(1 if fails else 0)
