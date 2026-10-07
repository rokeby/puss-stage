"""Offline tests for the Unreal-free parts of barbed_apply.py and barbed_import.py (python test_barbed_apply.py).

Synthetic two-row stack in the C++'s own conventions (bounds-centre fit, -Y side local X = +X, +Y side rotated 180
about Z), with the measured-like import record. Each check has a negative control that must fail.
"""
import copy
import math
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = runpy.run_path(os.path.join(HERE, "barbed_apply.py"), run_name="__bw_offline_test__")
I = runpy.run_path(os.path.join(HERE, "barbed_import.py"), run_name="__bw_offline_test__")
SM = A["SM"]
FAILS = []


def expect(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


IMPORT_REC = {"readback": {
    "SM_FenceBay_short_open_bwc": {"post_axis_cm": [-162.92, 0.3247, 40], "y_centre_cm": 0.3247,
                                   "bounds_cm": {"min": [-168.0, -28.89, 0.0], "max": [168.0, 29.54, 302.676]}},
    "SM_FenceBay_short_door_gap_bw": {"bounds_cm": {"min": [-168.0, -28.89, 0.0], "max": [168.0, 29.54, 302.676]}},
    "SM_FencePost_short_bw": {"post_axis_cm": [0.0, 6.5, 32]}}}

# ---- offset
off = A["post_offset_cm"](IMPORT_REC)
expect(abs(off[0] + 5.08) < 1e-6 and abs(off[1] + 6.5) < 1e-6 and off[2] == 0.0, "offset = (-5.08, -6.5, 0) from the axes")
bad = copy.deepcopy(IMPORT_REC)
bad["readback"]["SM_FenceBay_short_open_bwc"]["post_axis_cm"][0] = 162.92
try:
    A["post_offset_cm"](bad)
    expect(False, "control: a post at local +X is refused")
except A["BWApplyError"]:
    expect(True, "control: a post at local +X is refused")

# ---- plan
variants = {"fence_variant_a": {"mesh": SM + "SM_FenceBay_short_open", "weight": 0.6, "top_row_mesh": None},
            "fence_variant_b": {"mesh": SM + "SM_FenceBay_short_open", "weight": 0.2, "top_row_mesh": None},
            "fence_variant_c": {"mesh": SM + "SM_FenceBay_short_open", "weight": 0.15, "top_row_mesh": None},
            "fence_variant_d": {"mesh": SM + "SM_FenceBay_short_door_gap", "weight": 0.05, "top_row_mesh": None}}
t = A["plan_targets"](variants, off)
expect(t["fence_variant_a.top_row_mesh"] == SM + "SM_FenceBay_short_open_bwc"
       and t["fence_variant_d.top_row_mesh"] == SM + "SM_FenceBay_short_door_gap_bw"
       and t["fence_post_joints"] == "LINE_END" and t["fence_post_mesh"] == SM + "SM_FencePost_short_bw",
       "plan maps A-C to _open_bwc, D to _door_gap_bw, LINE_END posts")
for k, v, why in (("fence_variant_b", {"mesh": SM + "SM_FenceBay_open_v2", "weight": 0.2, "top_row_mesh": None}, "unmapped mesh"),
                  ("fence_variant_c", {"mesh": SM + "SM_FenceBay_short_open", "weight": 0.2, "top_row_mesh": "x"}, "already set")):
    vv = copy.deepcopy(variants)
    vv[k] = v
    try:
        A["plan_targets"](vv, off)
        expect(False, "control: plan refuses " + why)
    except A["BWApplyError"]:
        expect(True, "control: plan refuses " + why)

# ---- quaternion
q180 = [0.0, 0.0, 1.0, 0.0]
r = A["qrot"](q180, [1.0, 2.0, 3.0])
expect(all(abs(a - b) < 1e-9 for a, b in zip(r, [-1.0, -2.0, 3.0])), "qrot: 180 deg about Z")


# ---- synthetic fence: 2 sides x 3 tiles x 2 rows, plain short_open, slot 360 cm (scale x 360/336)
def panel(side, tile, row, mesh, variant, top=False):
    sx = 360.0 / 336.0
    q = [0.0, 0.0, 0.0, 1.0] if side < 0 else q180
    centre = [360.0 * (tile + 0.5), side * 1000.0, row * 302.676 + 151.338]
    # bounds centre (0, 0.3247, 151.338) is put on `centre`: loc = centre - R*(c*scale)
    c = A["qrot"](q, [0.0, 0.3247, 151.338])
    return {"loc": [centre[i] - c[i] for i in range(3)], "quat": q, "scale": [sx, 1.0, 1.0],
            "variant": variant, "mesh": mesh, "top": top}


def fence(top_row):
    out = []
    for side in (-1, 1):
        for tile in range(3):
            for row in range(2):
                v = "D" if (tile == 1 and row == 0) else "A"
                plain = SM + ("SM_FenceBay_short_door_gap" if v == "D" else "SM_FenceBay_short_open")
                is_top = top_row and row == 1
                mesh = A["MESH_MAP"][plain] if is_top else plain
                out.append(panel(side, tile, row, mesh, v, is_top))
    return out


def post(side):
    q = [0.0, 0.0, 0.0, 1.0] if side < 0 else q180
    foot = [1080.0 if side < 0 else 0.0, side * 1000.0, 302.676]
    o = A["qrot"](q, off)
    return {"loc": [foot[i] + o[i] for i in range(3)], "quat": q, "scale": [1.0, 1.0, 1.0]}


others = {"tubes|cube": [{"loc": [1.0, 2.0, 620.0], "quat": [0, 0, 0, 1], "scale": [1, 1, 1]}]}
before = {"panels": fence(False), "overlays": [], "posts": [], "others": copy.deepcopy(others)}
after = {"panels": fence(True), "overlays": [], "posts": [post(-1), post(1)], "others": copy.deepcopy(others)}
bounds = {SM + "SM_FenceBay_short_open_bwc": IMPORT_REC["readback"]["SM_FenceBay_short_open_bwc"]["bounds_cm"],
          SM + "SM_FenceBay_short_door_gap_bw": IMPORT_REC["readback"]["SM_FenceBay_short_door_gap_bw"]["bounds_cm"]}
t_a = dict(t, **{"fence_variant_d.top_row_mesh": SM + "SM_FenceBay_short_door_gap_bw"})
p, tops = A["check_apply"](before, after, t_a, 2, 2, off, bounds)
expect(not p and tops == 6, "check_apply: a correct build passes (%s)" % p[:3])

bad = copy.deepcopy(after)
bad["posts"][0]["loc"][0] += 5.0
expect(any("post foot" in x for x in A["check_apply"](before, bad, t_a, 2, 2, off, bounds)[0]), "control: a post 5 cm off its joint fails")
bad = copy.deepcopy(after)
bad["posts"] = [post(-1)]
expect(any("posts 1" in x for x in A["check_apply"](before, bad, t_a, 2, 2, off, bounds)[0]), "control: a missing post fails")
bad = copy.deepcopy(after)
for e in bad["panels"]:
    if not e["top"] and e["variant"] == "A":
        e["mesh"] = SM + "SM_FenceBay_short_open_bwc"
        break
expect(any("plain panel mesh" in x for x in A["check_apply"](before, bad, t_a, 2, 2, off, bounds)[0]), "control: wire on a lower row fails")
bad = copy.deepcopy(after)
bad["panels"][0]["loc"][2] += 3.0
expect(any("no old twin" in x for x in A["check_apply"](before, bad, t_a, 2, 2, off, bounds)[0]), "control: a moved panel fails")
bad = copy.deepcopy(after)
bad["others"]["tubes|cube"][0]["loc"][2] += 2.0
expect(any("changed" in x for x in A["check_apply"](before, bad, t_a, 2, 2, off, bounds)[0]), "control: a moved tube fails")
bad = copy.deepcopy(after)
for e in bad["panels"]:
    e["top"] = False
    e["mesh"] = SM + ("SM_FenceBay_short_door_gap" if e["variant"] == "D" else "SM_FenceBay_short_open")
expect(any("top-row panels 0" in x for x in A["check_apply"](before, bad, t_a, 2, 2, off, bounds)[0]), "control: no top row fails")

# ---- revert
expect(not A["check_revert"](before, copy.deepcopy(before)), "check_revert: restored passes")
expect(A["check_revert"](before, after), "control: check_revert fails on the applied build")

# ---- import helpers
pts = [(-162.92 + 5.08 * math.cos(a), 0.3247 + 5.08 * math.sin(a), z, 0.0)
       for a in [i * math.pi / 8 for i in range(16)] for z in (30.0, 240.0)]
ax = I["axis_from"](pts, xpred=lambda x: x < -100.0)
expect(abs(ax[0] + 162.92) < 1e-6 and abs(ax[1] - 0.3247) < 1e-6, "axis_from: ring mean = axis")
expect(abs(I["least_squares"]([0, 1, 2], [1, -1, -3]) + 2.0) < 1e-9, "least_squares slope")

# ---- post UV / axis on a TWO-RING tube (live DRY 7 Oct: POST_UV_FEW|SM_FencePost_short|0)
def two_ring_post(v_of_z, sides=16, r=5.08, cx=0.0, cy=-6.5, z1=287.0, flat=True):
    """Upright tube with vertices only at z=0 and z=z1 (+ a top cap), flat-shaded like a render section."""
    pts, tris = [], []
    ring = lambda k, z: (cx + r * math.cos(2 * math.pi * k / sides), cy + r * math.sin(2 * math.pi * k / sides), z, v_of_z(z))
    for k in range(sides):
        a, b, c, d = ring(k, 0.0), ring(k + 1, 0.0), ring(k + 1, z1), ring(k, z1)
        for tri in ((a, b, c), (a, c, d)):
            tris += [len(pts), len(pts) + 1, len(pts) + 2]
            pts += list(tri)
    top = (cx, cy, z1, 0.0)
    for k in range(sides):  # cap: horizontal, must not count
        tris += [len(pts), len(pts) + 1, len(pts) + 2]
        pts += [top, ring(k, z1), ring(k + 1, z1)]
    # outrigger arm, 45 deg: must not count
    tris += [len(pts), len(pts) + 1, len(pts) + 2]
    pts += [(cx, cy, z1 - 30), (cx, cy + 26, z1 - 4), (cx + 1.6, cy + 26, z1 - 4)]
    return pts, tris

UVU_CM = 96.0
pts_dn, tris_dn = two_ring_post(lambda z: 1.0 - z / UVU_CM)   # UE V-down (FBX import flipped V)
pts_up, tris_up = two_ring_post(lambda z: z / UVU_CM)         # mirrored / upside-down V
old_band = [p for p in pts_dn if 20.0 < p[2] < 250.0 and abs(p[0]) < 15.0]
expect(len(old_band) == 0, "regression cause: Z-band filter finds 0 vertices on a two-ring post")
sl = I["edge_v_slope"](pts_dn, tris_dn, lambda x: abs(x) < 15.0)
expect(abs(sl + 1.0 / UVU_CM) < 1e-9, "edge_v_slope: two-ring post dV/dZ = -1/96 per cm")
expect(I["edge_v_slope"](pts_up, tris_up, lambda x: abs(x) < 15.0) > 0, "edge_v_slope: upside-down post reads positive")
ax = I["axis_from_edges"](pts_dn, tris_dn, lambda x: abs(x) < 15.0)
expect(abs(ax[0]) < 1e-9 and abs(ax[1] + 6.5) < 1e-9 and ax[2] == 64, "axis_from_edges: two-ring tube axis (0, -6.5)")
bay_pts, bay_tris = two_ring_post(lambda z: 1.0 - z / UVU_CM, cx=-162.92, cy=0.3247, z1=301.0)
ax = I["axis_from_edges"](bay_pts, bay_tris, lambda x: x < -100.0)
expect(abs(ax[0] + 162.92) < 1e-9 and abs(ax[1] - 0.3247) < 1e-9, "axis_from_edges: bay post at local -X")
for label, fn in (("too few edges", lambda: I["edge_v_slope"](pts_dn, tris_dn, lambda x: x > 100.0)),
                  ("mixed V signs", lambda: I["edge_v_slope"](pts_dn + pts_up, tris_dn + [i + len(pts_dn) for i in tris_up],
                                                               lambda x: abs(x) < 15.0)),
                  ("axis with no vertical edges", lambda: I["axis_from_edges"](pts_dn, tris_dn, lambda x: x > 100.0))):
    try:
        fn()
        expect(False, "control: refuses " + label)
    except I["BWError"]:
        expect(True, "control: refuses " + label)
V = I["post_v_verdict"]
expect(V(-0.01, -0.02)[0] and V(-0.01, None)[0], "verdict: V-down passes with live ref and with ref unavailable")
expect(not V(0.01, None)[0], "control: upside-down post FAILS with live ref unavailable")
expect(not V(0.01, -0.02)[0], "control: upside-down post FAILS against a V-down live ref")
expect(not V(-0.01, 0.02)[0], "control: sign disagreement with the live ref FAILS")

print("ALL PASS" if not FAILS else "FAILED %d" % len(FAILS))
sys.exit(1 if FAILS else 0)
