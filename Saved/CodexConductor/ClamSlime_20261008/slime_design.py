"""PURE design of SK_PearlClam_Slime (numpy only; imported by build_slime.py inside headless Blender and by
validate_slime.py offline).  No bpy, no unreal.

FRAME: the PearlClam assembly frame, Blender cm, Z up, front (zigzag) = -Y, hinge = +Y [decl PearlClam_manifest.json
"frame"].  The lid pivot is PIVOT (Blender (0, 47.86, 30.02) cm) and opening by `deg` = rotation by -deg about +X
through PIVOT (clam_geo.lid_world; hinge_render.py:21,32).

RIG (one skeleton):
  root                      identity, at the bottom origin.  Every bone below is its child.
  lid                       head at PIVOT, identity rest rotation (bone +Y along world +Y, roll 0 -> bone X = world X),
                            animated by a pure rotation about its local X = the hinge.
  s<i>_lo<k>, s<i>_up<k>    strand i, lower half (bottom side) / upper half (lid side), stations k = 0..5 from the
                            anchor to the half's tip.  Rest frame: local Y along the strand's rest direction.
                            Animated by translation + rotation + RADIAL scale (local X = local Z, Y = 1): no shear.
LIGAMENT vertices weight root (1 - w) + lid (w), w = 0 on the bottom attachment face, 1 on the lid attachment face.
STRAND vertices weight the two stations bracketing them (linear in the strand parameter s) of their own half.

ANIM: frame i of A_PearlClam_SlimeOpen = Scene frame OPEN_START + i.  The lid angle is the piecewise-LINEAR curve
through clam_open.plan_keys (the very keys applied to the live lid, CLAMOPEN-20261008-032251), i.e. what Sequencer
evaluates between the live LINEAR keys.  The anim runs to the Scene's playback end (HOLD) so the section never loops.
"""
import importlib.util
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
CLAM_OPEN_PY = HERE + "../ClamOpen_20261008/clam_open.py"
CLAM_OPEN_RECORD = HERE + "../ClamOpen_20261008/clam_open_record.json"
PIVOT = np.array([0.0, 47.86, 30.02])

FPS = 24
OPEN_START = 1446                 # Scene frame where the anim's frame 0 plays (clam_open args open_start_frame)
OPEN_END = 1746
OPEN_DEG = 55.0
PLAYBACK_END = 6240               # LS_DevScene_03 playback end (clam_open args expected_playback_end) [meas 8 Oct]
EXISTING_ROLL_FRAMES = [1080, 1440]
ANIM_LAST = PLAYBACK_END - OPEN_START          # 4794 -> anim frames 0..4794 (section [1446, 6240))
ANIM_NAME = "A_PearlClam_SlimeOpen"
MESH_NAME = "SK_PearlClam_Slime"
ARMATURE_OBJECT = "Armature"      # Blender convention: an FBX Null named "Armature" is not made a bone [inf; IMPORT gates it]
SLOT_LIGAMENT = "M_PearlClam_Ligament"
SLOT_SLIME = "M_PearlClam_Slime"

# ------------------------------------------------------------------------------------------------ ligament
LIG_X_STEP = 0.5                  # station spacing along the hinge (cm)
LIG_BAND_DEPTH = 2.5              # cm inward (-Y) from the seam's outer edge
LIG_BAND_SAMPLES = 11
LIG_LAYERS = 8                    # wall subdivisions between the two attachment faces
LIG_EMBED = 0.25                  # cm: the attachment faces sit this far INSIDE their shell (no seam)
LIG_CONTACT_GAP = 1.5             # cm: a cell is "seam" if lid underside - bottom top < this when closed
LIG_SEAM_MIN_Y = 28.0             # the hinge zone: seam cells with y >= this (within ~20 cm of the axis)
LIG_INNER_GAP = 2.0               # cm: the band stops inward where the closed shells are further apart than this
GRID = 0.5                        # cm cell for the shell height grids

# ------------------------------------------------------------------------------------------------ strands
STRAND_RING = 10                  # vertices per ring
STRAND_RINGS_PER_HALF = 22
STRAND_STATIONS = 6               # per half: 5 along the half + the tip (overlap) station
STRAND_OVERLAP = 0.08             # each half runs this far past the neck (in s) so the closed strand reads continuous
STRAND_REST_RADIUS = 0.5          # cm, geometry radius; the bones' radial scale gives the shown radius
# per strand: x (cm), break angle (deg), neck position s_n, end radius, mid radius at a short stretch, bow sign
STRANDS = [
    {"x": -21.0, "break_deg": 14.0, "neck": 0.52, "r_end": 1.05, "r_mid": 0.55, "bow": 1.0},
    {"x": -11.0, "break_deg": 8.5, "neck": 0.45, "r_end": 0.85, "r_mid": 0.45, "bow": -1.0},
    {"x": -1.0, "break_deg": 23.0, "neck": 0.57, "r_end": 1.2, "r_mid": 0.6, "bow": 1.0},
    {"x": 10.0, "break_deg": 30.0, "neck": 0.48, "r_end": 1.0, "r_mid": 0.5, "bow": -1.0},
    {"x": 23.0, "break_deg": 18.0, "neck": 0.55, "r_end": 0.9, "r_mid": 0.45, "bow": 1.0},
]
STRAND_EMBED = 0.4                # cm, anchors sit this far inside their lip
STRAND_INSET = 0.75               # cm, anchors this far outward (-Y) of the lip's inner edge
MIN_RADIUS = 0.32               # cm floor of the strand body before the neck forms (spec range 0.3-1.2)
NECK_MIN_RATIO = 0.06             # neck radius / body radius at the break angle
RECOIL_TAU = 0.09                 # s, elastic recoil of each half after the break
RECOIL_HZ = 3.5                   # jiggle frequency
DROOP_TAU = 0.45                  # s, the halves bend toward their droop direction
DRIP_TAU = 2.2                    # s, slow drip lengthening of the upper half
DOWN_UP = np.array([0.0, 0.18, -1.0])      # upper half hangs down (slightly toward the hinge, away from the lid lip)
DOWN_LO = np.array([0.0, 0.55, -0.85])     # lower half slumps over the lip INTO the mouth (+Y) and down


def unit(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def rot_x(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def lid_point(p_closed, deg):
    """A point fixed to the lid, given at the closed pose, at opening `deg`."""
    return rot_x(-deg) @ (np.asarray(p_closed, float) - PIVOT) + PIVOT


# ================================================================================================ anim curve
def load_clam_open():
    """clam_open.py imported under the name that skips its main() (clam_open.py:733)."""
    spec = importlib.util.spec_from_file_location("clam_open_offline", CLAM_OPEN_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def plan_args():
    """The args of the APPLIED run (clam_open_record.json "args"), so the slime follows what is live."""
    with open(CLAM_OPEN_RECORD, encoding="utf-8") as h:
        rec = json.load(h)
    return rec


def lid_curve():
    """-> (planned [(scene_frame, roll_deg)], all_keys incl. the 2 existing, roll(scene_frame) function).
    roll is the LIVE convention (negative = open); opening angle = -roll."""
    co = load_clam_open()
    rec = plan_args()
    a = co.merged_args(dict(rec["args"], mode="DRY", confirm=""))
    planned = co.plan_keys(a, EXISTING_ROLL_FRAMES, PLAYBACK_END, (None, None))
    if [list(map(float, p)) for p in planned] != [list(map(float, p)) for p in rec["planned"]]:
        raise ValueError("PLAN_DIFFERS_FROM_APPLIED_RECORD")
    allk = [(f, 0.0) for f in EXISTING_ROLL_FRAMES] + list(planned)
    return planned, allk, (lambda f: co.curve_at(allk, f))


def anim_angles():
    """-> np.array of OPENING degrees (positive) for anim frames 0..ANIM_LAST."""
    _p, _a, roll = lid_curve()
    return np.array([-roll(OPEN_START + i) for i in range(ANIM_LAST + 1)])


def break_frames(angles):
    """strand index -> first anim frame whose angle >= its break angle."""
    out = []
    for s in STRANDS:
        idx = np.nonzero(angles >= s["break_deg"] - 1e-9)[0]
        out.append(int(idx[0]))
    return out


# ================================================================================================ shells -> design
def height_grids(bv, lv_closed, x_lim=(-40.0, 40.0), y_lim=(-52.0, 52.0)):
    """zB = bottom max z per cell (rim TOP), zL = closed lid min z per cell (rim UNDERSIDE)."""
    nx = int(round((x_lim[1] - x_lim[0]) / GRID))
    ny = int(round((y_lim[1] - y_lim[0]) / GRID))

    def grid(v, fn, init):
        m = (v[:, 0] >= x_lim[0]) & (v[:, 0] < x_lim[1]) & (v[:, 1] >= y_lim[0]) & (v[:, 1] < y_lim[1])
        v = v[m]
        i = np.floor((v[:, 0] - x_lim[0]) / GRID).astype(int)
        j = np.floor((v[:, 1] - y_lim[0]) / GRID).astype(int)
        g = np.full((nx, ny), init)
        fn.at(g, (i, j), v[:, 2])
        g[g == init] = np.nan
        return g
    zb = grid(bv, np.maximum, -1e9)
    zl = grid(lv_closed, np.minimum, 1e9)
    xs = x_lim[0] + (np.arange(nx) + 0.5) * GRID
    ys = y_lim[0] + (np.arange(ny) + 0.5) * GRID
    return xs, ys, zb, zl


def _nanmed_filter(a, r):
    out = np.copy(a)
    for i in range(len(a)):
        w = a[max(0, i - r):i + r + 1]
        w = w[np.isfinite(w)]
        out[i] = np.median(w) if len(w) else np.nan
    return out


def _smooth2(g, r=1):
    """nan-aware box mean (radius r cells)."""
    out = np.full_like(g, np.nan)
    nx, ny = g.shape
    for i in range(nx):
        for j in range(ny):
            w = g[max(0, i - r):i + r + 1, max(0, j - r):j + r + 1]
            w = w[np.isfinite(w)]
            if len(w):
                out[i, j] = w.mean()
    return out


def _sample(xs, ys, g, x, y):
    """bilinear with nan fallback to the nearest finite cell in the same column, then neighbours."""
    fi = (x - xs[0]) / GRID
    fj = (y - ys[0]) / GRID
    i0, j0 = int(math.floor(fi)), int(math.floor(fj))
    ti, tj = fi - i0, fj - j0
    acc, wsum = 0.0, 0.0
    for di, wi in ((0, 1 - ti), (1, ti)):
        for dj, wj in ((0, 1 - tj), (1, tj)):
            ii, jj = i0 + di, j0 + dj
            if 0 <= ii < len(xs) and 0 <= jj < len(ys) and np.isfinite(g[ii, jj]):
                acc += wi * wj * g[ii, jj]
                wsum += wi * wj
    if wsum > 1e-9:
        return acc / wsum
    for rr in range(1, 8):
        w = g[max(0, i0 - rr):i0 + rr + 2, max(0, j0 - rr):j0 + rr + 2]
        w = w[np.isfinite(w)]
        if len(w):
            return float(np.median(w))
    return float("nan")


def seam_profile(xs, ys, zb, zl):
    """Hinge-zone seam: per x column, the OUTER edge (max y) of the closed contact band within y >= LIG_SEAM_MIN_Y.
    -> dict(x_span, rows=[{x, y_out}], columns_with_contact)."""
    gap = zl - zb
    contact = np.isfinite(gap) & (gap < LIG_CONTACT_GAP) & (gap > -1.5)
    yo = np.full(len(xs), np.nan)
    for i in range(len(xs)):
        js = np.nonzero(contact[i] & (ys >= LIG_SEAM_MIN_Y))[0]
        if len(js):
            yo[i] = ys[js].max()
    # longest run of columns with contact containing x=0, bridging holes up to 2 cm
    have = np.isfinite(yo)
    i0 = int(np.argmin(np.abs(xs)))
    if not have[i0]:
        near = np.nonzero(have)[0]
        i0 = int(near[np.argmin(np.abs(near - i0))])
    hole = int(round(2.0 / GRID))
    lo = i0
    while True:
        nxt = [k for k in range(lo - 1, max(-1, lo - hole - 2), -1) if k >= 0 and have[k]]
        if not nxt:
            break
        lo = nxt[0]
    hi = i0
    while True:
        nxt = [k for k in range(hi + 1, min(len(xs), hi + hole + 2)) if have[k]]
        if not nxt:
            break
        hi = nxt[0]
    idx = np.arange(lo, hi + 1)
    y = yo[idx]
    good = np.isfinite(y)
    y = np.interp(xs[idx], xs[idx][good], y[good])
    y = _nanmed_filter(y, 4)
    return {"x": xs[idx], "y_out": y, "x_span": [float(xs[lo]), float(xs[hi])]}


def ligament_design(bv, lv_closed, surfaces=None):
    """surfaces = (bottom Solid, lid Solid in the lid's hinge-relative frame) -> the attachment faces are PROJECTED
    onto the true shell surfaces and pushed LIG_EMBED inside along the outward normal (without surfaces: grid only)."""
    xs, ys, zb, zl = height_grids(bv, lv_closed, x_lim=(-40.0, 40.0), y_lim=(15.0, 52.0))
    seam = seam_profile(xs, ys, zb, zl)
    zbs, zls = _smooth2(zb, 1), _smooth2(zl, 1)
    stations = []
    for x, y_out in zip(seam["x"], seam["y_out"]):
        # inward extent: up to LIG_BAND_DEPTH, but stop where the closed shells part (the lips' inner edge), min 1 cm
        depth = LIG_BAND_DEPTH
        for dy in np.arange(1.0, LIG_BAND_DEPTH + 1e-9, 0.25):
            gl = _sample(xs, ys, zls, x, y_out - dy) - _sample(xs, ys, zbs, x, y_out - dy)
            if not np.isfinite(gl) or gl > LIG_INNER_GAP:
                depth = max(1.0, dy - 0.25)
                break
        yy = np.linspace(y_out - depth, y_out, LIG_BAND_SAMPLES)
        lo = np.array([_sample(xs, ys, zbs, x, y) for y in yy])
        up = np.array([_sample(xs, ys, zls, x, y) for y in yy])
        lo_e, up_e = lo - LIG_EMBED, up + LIG_EMBED
        bad = up_e < lo_e + 0.3
        mid = 0.5 * (lo + up)
        lo_e[bad], up_e[bad] = mid[bad] - 0.15, mid[bad] + 0.15
        stations.append({"x": float(x), "y": yy, "lo": lo_e, "up": up_e})
    out = {"seam": seam, "stations": stations}
    if surfaces is not None:
        project_attachments(out, *surfaces)
    return out


def project_attachments(design, bottom_solid, lid_solid_rel):
    """Replace each station's lower/upper attachment polyline by points ON the shells, LIG_EMBED inside.
    Stored as full 3D points (lo3 / up3, shape (M,3)); the walls interpolate between them."""
    for s in design["stations"]:
        lo = np.stack([np.full(len(s["y"]), s["x"]), s["y"], s["lo"] + LIG_EMBED], axis=1)
        up = np.stack([np.full(len(s["y"]), s["x"]), s["y"], s["up"] - LIG_EMBED], axis=1)
        s["lo3"] = embed(bottom_solid, lo)
        s["up3"] = embed(lid_solid_rel, up - PIVOT) + PIVOT


def embed(solid, pts, depth=None, iters=4):
    """Points placed `depth` inside the solid measured to its NEAREST surface point (iterated: the first push
    follows the face normal, later ones the true nearest direction)."""
    depth = LIG_EMBED if depth is None else depth
    _u, _s, cp, n = solid.closest(pts)
    p = cp - depth * n
    for _ in range(iters):
        u, sd, cp, n = solid.closest(p)
        dirn = (p - cp) / np.maximum(u, 1e-9)[:, None]
        dirn = np.where((sd < 0)[:, None], dirn, -dirn)          # unit vector pointing INTO the material
        p = cp + depth * dirn
    return p


def ligament_mesh(design):
    """-> verts (N,3) cm, quads/tris list, w (N,) lid weight, uv (per-loop handled by builder: per-vertex uv here)."""
    st = design["stations"]
    M, NL = LIG_BAND_SAMPLES, LIG_LAYERS
    ring_len = 2 * M + 2 * (NL - 1)
    verts, w, uv = [], [], []
    for k, s in enumerate(st):
        ring, rw = [], []
        if "lo3" in s:
            lo3, up3 = s["lo3"], s["up3"]
        else:
            lo3 = np.stack([np.full(M, s["x"]), s["y"], s["lo"]], axis=1)
            up3 = np.stack([np.full(M, s["x"]), s["y"], s["up"]], axis=1)
        for j in range(M):                                   # lower face, inner -> outer
            ring.append(tuple(lo3[j])); rw.append(0.0)
        for l in range(1, NL):                               # outer wall, up
            t = l / float(NL)
            ring.append(tuple((1 - t) * lo3[-1] + t * up3[-1])); rw.append(t)
        for j in range(M - 1, -1, -1):                       # upper face, outer -> inner
            ring.append(tuple(up3[j])); rw.append(1.0)
        for l in range(NL - 1, 0, -1):                       # inner wall, down
            t = l / float(NL)
            ring.append(tuple((1 - t) * lo3[0] + t * up3[0])); rw.append(t)
        assert len(ring) == ring_len
        for q, (p, ww) in enumerate(zip(ring, rw)):
            verts.append(p); w.append(ww); uv.append((k / float(len(st) - 1), q / float(ring_len)))
    faces = []
    for k in range(len(st) - 1):
        a0, b0 = k * ring_len, (k + 1) * ring_len
        for q in range(ring_len):
            q1 = (q + 1) % ring_len
            faces.append((a0 + q, a0 + q1, b0 + q1, b0 + q))
    # end caps: fan to a centre vertex per end (weight 0.5)
    for k, flip in ((0, True), (len(st) - 1, False)):
        base = k * ring_len
        c = np.mean(np.asarray(verts[base:base + ring_len]), axis=0)
        ci = len(verts)
        verts.append(tuple(c)); w.append(0.5); uv.append((k / float(len(st) - 1), 0.5))
        for q in range(ring_len):
            q1 = (q + 1) % ring_len
            faces.append((ci, base + q1, base + q) if flip else (ci, base + q, base + q1))
    return np.asarray(verts), faces, np.asarray(w), np.asarray(uv)


# ------------------------------------------------------------------------------------------------ strand anchors
def strand_anchors(bv, lv_closed):
    """Per strand: B (bottom inner lip, embedded) and A0 (lid inner lip at the CLOSED pose, embedded)."""
    xs, ys, zb, zl = height_grids(bv, lv_closed, x_lim=(-40.0, 40.0), y_lim=(-52.0, -20.0))
    zbs, zls = _smooth2(zb, 1), _smooth2(zl, 1)
    out = []
    for s in STRANDS:
        i = int(np.argmin(np.abs(xs - s["x"])))
        cols = range(max(0, i - 1), min(len(xs), i + 2))
        y_in = []
        for c in cols:
            gap = zl[c] - zb[c]
            ok = np.isfinite(gap) & (gap < 3.0)
            js = np.nonzero(ok)[0]
            if not len(js):
                continue
            j = js[0]                                        # front-most contact
            while j + 1 < len(ys) and ok[j + 1]:
                j += 1                                       # walk inward to the lip's INNER edge
            y_in.append(ys[j])
        if not y_in:
            raise ValueError("NO_FRONT_LIP|x=%s" % s["x"])
        y = float(np.median(y_in)) - STRAND_INSET
        x = s["x"]
        zB = _sample(xs, ys, zbs, x, y)
        zL = _sample(xs, ys, zls, x, y)
        out.append({"x": x, "y_inner_edge": float(np.median(y_in)), "B": np.array([x, y, zB - STRAND_EMBED]),
                    "A0": np.array([x, y, zL + STRAND_EMBED]), "closed_gap": float(zL - zB)})
    return out


# ------------------------------------------------------------------------------------------------ strand geometry
def strand_half_params(si, half):
    """-> list of station s values (anchor first, tip last) and ring s values for one half."""
    n = STRANDS[si]["neck"]
    if half == "lo":
        st = [n * k / (STRAND_STATIONS - 2) for k in range(STRAND_STATIONS - 1)] + [n + STRAND_OVERLAP]
        rings = list(np.linspace(0.0, n + STRAND_OVERLAP, STRAND_RINGS_PER_HALF))
    else:
        st = [1.0 - (1.0 - n) * k / (STRAND_STATIONS - 2) for k in range(STRAND_STATIONS - 1)] + [n - STRAND_OVERLAP]
        rings = list(np.linspace(1.0, n - STRAND_OVERLAP, STRAND_RINGS_PER_HALF))
    return st, rings


def rest_frame(B, A0):
    """Strand rest frame: Y along B->A0, X ~ world X, Z = X x Y."""
    Y = unit(A0 - B)
    X = unit(np.array([1.0, 0.0, 0.0]) - Y[0] * Y)
    Z = np.cross(X, Y)
    return X, Y, Z


def bone_name(si, half, k):
    return "s%d_%s%d" % (si, half, k)


def strand_bones():
    return [bone_name(si, h, k) for si in range(len(STRANDS)) for h in ("lo", "up") for k in range(STRAND_STATIONS)]


LIG_HELPERS = ["lig_1", "lig_2", "lig_3"]       # rotate by 1/4, 2/4, 3/4 of the lid angle about the same hinge axis
LIG_CHAIN = [("root", 0.0), ("lig_1", 0.25), ("lig_2", 0.5), ("lig_3", 0.75), ("lid", 1.0)]


def all_bones():
    return ["root", "lid"] + LIG_HELPERS + strand_bones()


def ligament_weights(w):
    """lid weight w in [0, 1] -> [(bone, weight)] along root -> lig_1 -> lig_2 -> lig_3 -> lid (piecewise linear), so a
    wall point sweeps an ARC about the hinge (4 chords) instead of one chord."""
    for (b0, f0), (b1, f1) in zip(LIG_CHAIN, LIG_CHAIN[1:]):
        if f0 - 1e-12 <= w <= f1 + 1e-12:
            t = (w - f0) / (f1 - f0)
            return [x for x in ((b0, 1.0 - t), (b1, t)) if x[1] > 1e-9]
    raise ValueError(w)


def strand_mesh(anchors):
    """-> verts, faces, weights {vertex: [(bone, w)]}, uv, and per-strand ring bookkeeping (for the validation)."""
    verts, faces, wts, uv, tags = [], [], [], [], []
    for si, an in enumerate(anchors):
        B, A0 = an["B"], an["A0"]
        X, Y, Z = rest_frame(B, A0)
        L0 = np.linalg.norm(A0 - B)
        for h in ("lo", "up"):
            st, rings = strand_half_params(si, h)
            base = len(verts)
            # anchor cap centre (buried) first
            for r_i, s in enumerate(rings):
                c = B + s * L0 * Y
                # bracketing stations along this half (stations are monotone in the half's direction)
                pos = [abs(x - st[0]) for x in st]
                d = abs(s - st[0])
                k = max(0, min(len(st) - 2, int(np.searchsorted(pos, d, side="right") - 1)))
                f = (d - pos[k]) / max(pos[k + 1] - pos[k], 1e-9)
                f = min(1.0, max(0.0, f))
                for q in range(STRAND_RING):
                    a = 2 * math.pi * q / STRAND_RING
                    p = c + STRAND_REST_RADIUS * (math.cos(a) * X + math.sin(a) * Z)
                    verts.append(tuple(p))
                    wl = [(bone_name(si, h, k), 1.0 - f), (bone_name(si, h, k + 1), f)]
                    wts.append([x for x in wl if x[1] > 1e-6])
                    uv.append((q / float(STRAND_RING), r_i / float(len(rings) - 1)))
                    tags.append((si, h, r_i))
            nr = len(rings)
            for r_i in range(nr - 1):
                for q in range(STRAND_RING):
                    q1 = (q + 1) % STRAND_RING
                    a0 = base + r_i * STRAND_RING
                    b0 = base + (r_i + 1) * STRAND_RING
                    faces.append((a0 + q, a0 + q1, b0 + q1, b0 + q) if h == "lo" else (a0 + q, b0 + q, b0 + q1, a0 + q1))
            # caps: anchor (ring 0) and tip (last ring) closed with a centre vertex
            for r_i, sign in ((0, -1.0), (nr - 1, 1.0)):
                s = rings[r_i]
                ring0 = base + r_i * STRAND_RING
                c = B + s * L0 * Y + (sign if h == "lo" else -sign) * 0.35 * STRAND_REST_RADIUS * Y
                ci = len(verts)
                verts.append(tuple(c))
                kk = 0 if r_i == 0 else STRAND_STATIONS - 1
                wts.append([(bone_name(si, h, kk), 1.0)])
                uv.append((0.5, 0.0 if r_i == 0 else 1.0))
                tags.append((si, h, -1 if r_i == 0 else -2))
                outward = (r_i == nr - 1) == (h == "lo")
                for q in range(STRAND_RING):
                    q1 = (q + 1) % STRAND_RING
                    faces.append((ci, ring0 + q, ring0 + q1) if outward else (ci, ring0 + q1, ring0 + q))
    return np.asarray(verts), faces, wts, np.asarray(uv), tags


def strand_rest_bones(anchors):
    """bone -> (head cm, X, Y, Z) at rest (armature space, Blender cm)."""
    out = {}
    for si, an in enumerate(anchors):
        B, A0 = an["B"], an["A0"]
        X, Y, Z = rest_frame(B, A0)
        L0 = np.linalg.norm(A0 - B)
        for h in ("lo", "up"):
            st, _r = strand_half_params(si, h)
            for k, s in enumerate(st):
                out[bone_name(si, h, k)] = (B + s * L0 * Y, X, Y, Z)
    return out


# ------------------------------------------------------------------------------------------------ strand motion
def _integrate(P0, d0, d1, L, n):
    """Points along a curve from P0 whose direction blends d0 -> d1 linearly in arc length, total length L."""
    pts = [np.asarray(P0, float)]
    steps = 64
    acc = np.asarray(P0, float).copy()
    sub = [acc.copy()]
    for k in range(steps):
        t = (k + 0.5) / steps
        acc = acc + unit((1 - t) * d0 + t * d1) * (L / steps)
        sub.append(acc.copy())
    sub = np.asarray(sub)
    out = []
    for a in np.linspace(0.0, 1.0, n):
        f = a * steps
        i = min(int(f), steps - 1)
        out.append(sub[i] + (sub[i + 1] - sub[i]) * (f - i))
    return np.asarray(out), unit(d0), unit(d1)


def _pre_curve(si, B, A, deg):
    """Pre-break strand: chord B->A with a slight bow; -> fn(s) point, fn(s) tangent, radius fn(s)."""
    sd = STRANDS[si]
    d = A - B
    L = float(np.linalg.norm(d))
    dh = unit(d)
    g = np.array([0.0, 0.0, -1.0]) + 0.5 * np.array([0.0, 1.0, 0.0])
    wdir = g - np.dot(g, dh) * dh
    xa = np.array([sd["bow"], 0.0, 0.0])
    wdir = unit(wdir + 0.6 * (xa - np.dot(xa, dh) * dh))
    amp = 0.06 * L
    p_break = min(1.0, max(0.0, deg / sd["break_deg"]))
    r_mid = max(MIN_RADIUS, sd["r_mid"] * math.sqrt(6.0 / max(L, 6.0)))

    def pt(s):
        return B + s * d + amp * 4.0 * s * (1.0 - s) * wdir

    def tan(s):
        return unit(d + amp * 4.0 * (1.0 - 2.0 * s) * wdir)

    r_end = r_mid + (sd["r_end"] - r_mid) * min(1.0, max(0.3, (L - 2.0) / 6.0))   # thin film when barely open

    def rad(s):
        r = r_mid + (r_end - r_mid) * (math.exp(-(s / 0.14) ** 2) + math.exp(-((1.0 - s) / 0.14) ** 2))
        r *= 1.0 - (1.0 - NECK_MIN_RATIO) * (p_break ** 2.5) * math.exp(-((s - sd["neck"]) / 0.1) ** 2)
        r *= 0.35 + 0.65 * min(1.0, deg / EMERGE_DEG)      # the film draws out into strands over the first degrees
        return r
    return pt, tan, rad, L


def _frame_from_tangent(T, X_rest):
    Y = unit(T)
    X = unit(X_rest - np.dot(X_rest, Y) * Y)
    Z = np.cross(X, Y)
    return X, Y, Z


def strand_pose(si, anchors, deg, t_after_break, state):
    """-> {bone: (centre, X, Y, Z, radius)} for strand si at opening `deg`; t_after_break None = intact.
    `state` keeps the curve at the break frame (filled on the break frame)."""
    an = anchors[si]
    sd = STRANDS[si]
    B, A = an["B"], lid_point(an["A0"], deg)
    Xr, _Yr, _Zr = rest_frame(an["B"], an["A0"])
    out = {}
    pt, tan, rad, L = _pre_curve(si, B, A, deg)
    if t_after_break is None:
        for h in ("lo", "up"):
            st, _r = strand_half_params(si, h)
            for k, s in enumerate(st):
                X, Y, Z = _frame_from_tangent(tan(s), Xr)
                r = rad(s) * (0.5 if k == len(st) - 1 else 1.0)
                out[bone_name(si, h, k)] = (pt(s), X, Y, Z, r)
        state["r"] = {b: v[4] for b, v in out.items()}
        state["L_lo"] = L * (sd["neck"] + STRAND_OVERLAP)
        state["L_up"] = L * (1.0 - sd["neck"] + STRAND_OVERLAP)
        state["d_lo"] = unit(pt(sd["neck"]) - B)
        state["d_up"] = unit(pt(sd["neck"]) - A)
        return out
    t = float(t_after_break)
    for h in ("lo", "up"):
        st, _r = strand_half_params(si, h)
        Lb = state["L_" + h]
        if h == "up":
            Ld = min(9.0, max(2.5, 0.32 * Lb)) * (1.0 + 0.35 * (1.0 - math.exp(-t / DRIP_TAU)))
            dn = unit(an.get("down_up", DOWN_UP))
            sway = math.radians(7.0) * math.exp(-t / 1.4) * math.sin(2 * math.pi * 0.8 * t)
            dn = rot_x(math.degrees(sway)) @ dn
            P0 = A
        else:
            Ld = min(an.get("lo_len_max", 4.0), max(1.5, 0.28 * Lb))
            dn = unit(an.get("down_lo", DOWN_LO))
            P0 = B
        # elastic recoil to the droop length, then a small bounded jiggle (never shorter than 0.75 Ld: no collapse
        # into the lip)
        Lt = Ld + (Lb - Ld) * math.exp(-t / RECOIL_TAU) + 0.25 * Ld * math.exp(-t / 0.3) * math.sin(2 * math.pi * RECOIL_HZ * t)
        Lt = max(0.75 * Ld, Lt)
        b = 1.0 - math.exp(-t / DROOP_TAU)
        d0 = unit((1.0 - 0.45 * b) * state["d_" + h] + 0.45 * b * dn)
        d1 = unit((1.0 - b) * state["d_" + h] + b * dn)
        pts, _a, _b = _integrate(P0, d0, d1, Lt, len(st))
        for k in range(len(st)):
            a = k / float(len(st) - 1)
            T = pts[min(k + 1, len(st) - 1)] - pts[max(k - 1, 0)]
            X, Y, Z = _frame_from_tangent(T, Xr)
            if h == "up":   # the half's +Y must still run from the strand's B side to its A side (rest convention)
                Y, Z = -Y, -Z
            bulb = 0.5 if h == "up" else 0.42
            r_foot = state["r"][bone_name(si, h, 0)]            # the meniscus keeps its size at the snap
            r = r_foot * math.exp(-(a / 0.22) ** 2) + 0.36 * (1 - math.exp(-(a / 0.22) ** 2))
            r += bulb * math.exp(-((a - 0.8) / 0.13) ** 2) * min(1.0, t / 0.25)
            if k == len(st) - 1:
                r *= 0.35
            u = min(1.0, t / 0.25)
            u = u * u * (3.0 - 2.0 * u)
            r = state["r"][bone_name(si, h, k)] + (r - state["r"][bone_name(si, h, k)]) * u   # no radius pop at the snap
            out[bone_name(si, h, k)] = (pts[k], X, Y, Z, r)
    return out


EMERGE_DEG = 3.0   # strands reach full thickness once the lid has opened this far (thin film inside the closed lips)
FOOT_S = 0.12      # strand rings within this strand-parameter distance of their anchor = the meniscus foot on the lip


def strand_ring_s(si, half, ring_index):
    _st, rings = strand_half_params(si, half)
    return rings[ring_index] if ring_index >= 0 else (rings[0] if ring_index == -1 else rings[-1])


def foot_mask(tags):
    """True for strand vertices in the meniscus foot (buried in / spread on the lip by design) and the anchor caps."""
    out = []
    for t in tags:
        if t is None:
            out.append(False)
            continue
        si, h, r = t
        if r == -1:
            out.append(True)
            continue
        if r == -2:
            out.append(False)
            continue
        s = strand_ring_s(si, h, r)
        anchor = 0.0 if h == "lo" else 1.0
        out.append(abs(s - anchor) < FOOT_S)
    return np.array(out)


DROOP_CANDIDATES_LO = [(0.0, 0.55, -0.85), (0.0, 0.8, -0.6), (0.0, 1.0, -0.35), (0.0, 0.35, -0.95),
                       (0.3, 0.7, -0.65), (-0.3, 0.7, -0.65), (0.0, 0.95, 0.1)]
DROOP_CANDIDATES_UP = [(0.0, 0.18, -1.0), (0.0, 0.4, -0.9), (0.0, -0.1, -1.0), (0.25, 0.2, -0.95),
                       (-0.25, 0.2, -0.95), (0.0, 0.6, -0.8)]
LO_LEN_CANDIDATES = [4.0, 3.0, 2.2, 1.6]


def tune_droops(anchors, angles, solids, limit=0.2, tail=360):
    """Per strand, the first droop direction (and lower-half length) whose post-break vertices (foot excluded) stay
    within `limit` of every obstacle surface over `tail` frames after the break.  solids = {name: (Solid, to_local)}
    with to_local(points, deg).  Records the choice and the residual depth in the anchor dict."""
    bf = break_frames(angles)
    sv, _sf, sw, _suv, tags = strand_mesh(anchors)
    foot = foot_mask(tags)
    which = np.array([t[0] for t in tags])
    halves = np.array([t[1] for t in tags])
    rest = {b: rest_world_matrix(*v) for b, v in strand_rest_bones(anchors).items()}
    bones = list(rest)
    W = weight_matrix(sw, bones)
    for si, an in enumerate(anchors):
        frames = list(range(bf[si], min(len(angles), bf[si] + tail), 3))
        for half, cands, key in (("lo", DROOP_CANDIDATES_LO, "down_lo"), ("up", DROOP_CANDIDATES_UP, "down_up")):
            m = (which == si) & (halves == half) & ~foot
            best = None
            lens = LO_LEN_CANDIDATES if half == "lo" else [None]
            for ln in lens:
                for c in cands:
                    an[key] = np.array(c, float)
                    if ln is not None:
                        an["lo_len_max"] = ln
                    st = {}
                    worst = 0.0
                    for i in range(bf[si] - 1, frames[-1] + 1):
                        tab = None if i < bf[si] else (i - bf[si]) / float(FPS)
                        if tab is not None and "L_lo" not in st:
                            strand_pose(si, anchors, angles[i], None, st)
                        pose = strand_pose(si, anchors, angles[i], tab, st)
                        if i not in frames:
                            continue
                        pm = {b: bone_world_matrix(*v) for b, v in pose.items()}
                        for b in bones:
                            pm.setdefault(b, rest[b])
                        P = skin(sv[m], W[m], bones, rest, pm)
                        for _n, (solid, to_local) in solids.items():
                            worst = max(worst, float(solid.depth(to_local(P, angles[i])).max()))
                        if worst > limit:
                            break
                    if best is None or worst < best[0]:
                        best = (worst, c, ln)
                    if worst <= limit:
                        break
                if best[0] <= limit:
                    break
            an[key] = np.array(best[1], float)
            if half == "lo":
                an["lo_len_max"] = best[2]
            an["droop_%s_residual_cm" % half] = round(best[0], 3)
    return anchors


def all_strand_poses(anchors, angles):
    """-> list over anim frames of {bone: (c, X, Y, Z, r)}; also the break frame per strand."""
    bf = break_frames(angles)
    states = [dict() for _ in STRANDS]
    frames = []
    for i, deg in enumerate(angles):
        fr = {}
        for si in range(len(STRANDS)):
            tab = None if i < bf[si] else (i - bf[si]) / float(FPS)
            if tab is not None and "L_lo" not in states[si]:
                strand_pose(si, anchors, deg, None, states[si])
            fr.update(strand_pose(si, anchors, deg, tab, states[si]))
        frames.append(fr)
    return frames, bf


def bone_world_matrix(c, X, Y, Z, r):
    """4x4 armature-space matrix of a strand bone: T(c) [X Y Z] diag(rho, 1, rho), rho = r / rest radius."""
    rho = r / STRAND_REST_RADIUS
    M = np.eye(4)
    M[:3, 0] = X * rho
    M[:3, 1] = Y
    M[:3, 2] = Z * rho
    M[:3, 3] = c
    return M


def rest_world_matrix(c, X, Y, Z):
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = X, Y, Z, c
    return M


def lid_world_matrix(deg):
    M = np.eye(4)
    M[:3, :3] = rot_x(-deg)
    M[:3, 3] = PIVOT
    return M


def lid_rest_matrix():
    M = np.eye(4)
    M[:3, 3] = PIVOT
    return M


# ================================================================================================ assembly
def relax_walls(V, W, bottom_solid, lid_solid_rel, cap=None, iters=3):
    """Ligament WALL vertices (0 < w < 1) that sit deeper than LIG_EMBED inside a shell at the closed pose are moved
    back to exactly LIG_EMBED inside it (nearest-surface direction).  The attachment faces are already there."""
    V = np.array(V, float)
    wall = (W > 0) & (W < 1)
    if cap is not None:
        wall &= ~cap
    for _ in range(iters):
        for solid, off in ((bottom_solid, np.zeros(3)), (lid_solid_rel, PIVOT)):
            idx = np.nonzero(wall)[0]
            d = solid.depth(V[idx] - off)
            deep = idx[d > LIG_EMBED + 1e-6]
            if len(deep):
                V[deep] = embed(solid, V[deep] - off, iters=2) + off
    return V


RELAX_ANGLES = tuple(float(a) for a in range(0, 56, 5))     # 0, 5, ... 55: validate_slime tests every 2.5 deg


def relax_walls_open(V, lw, bottom_solid, lid_solid_rel, cap, angles=RELAX_ANGLES, rounds=6,
                     limit=None):
    """Wall vertices that the hinge motion carries INTO a shell at some opening angle are moved (in the rest pose)
    so that, posed by their own blended ligament transform at that angle, they sit at most `limit` inside it."""
    limit = LIG_EMBED if limit is None else limit
    V = np.array(V, float)
    wall = (lw > 0) & (lw < 1)          # walls AND the two end-cap centres (w = 0.5): both are visible surface
    idx = np.nonzero(wall)[0]
    rest = lid_rest_matrix()
    for _ in range(rounds):
        moved = 0
        for deg in angles:
            # blended LBS matrix per vertex: sum of (pose_b rest_b^-1) weighted (rest_b identical for all lig bones
            # except root, which is identity)
            D = []
            for i in idx:
                M = np.zeros((4, 4))
                for b, wt in ligament_weights(float(lw[i])):
                    Pb = np.eye(4) if b == "root" else lid_world_matrix(deg * dict(LIG_CHAIN)[b])
                    Rb = np.eye(4) if b == "root" else rest
                    M += wt * (Pb @ np.linalg.inv(Rb))
                D.append(M)
            D = np.asarray(D)
            P = np.einsum("nij,nj->ni", D, np.hstack([V[idx], np.ones((len(idx), 1))]))[:, :3]
            for solid, toloc, fromloc in ((bottom_solid, lambda q: q, lambda q: q),
                                          (lid_solid_rel, lambda q: (q - PIVOT) @ rot_x(-deg),
                                           lambda q: q @ rot_x(-deg).T + PIVOT)):
                Q = toloc(P)
                dep = solid.depth(Q)
                bad = np.nonzero(dep > limit + 1e-6)[0]
                if not len(bad):
                    continue
                u, sd, cp, n = solid.closest(Q[bad])
                target_local = cp + (limit - 0.02) * (Q[bad] - cp) / np.maximum(u, 1e-9)[:, None]
                target = fromloc(target_local)
                for k, j in enumerate(bad):
                    dP = target[k] - P[j]
                    V[idx[j]] += np.linalg.solve(D[j][:3, :3], dP)
                    P[j] = target[k]
                moved += len(bad)
        if not moved:
            break
    return V


def assemble(bv, lv_closed, solids=None):
    """The whole skinned mesh in Blender cm.  -> dict:
       verts (N,3), faces [tuple], face_mat [0 ligament | 1 slime], weights [[(bone, w)]], uv (N,2) per vertex,
       part (N,) 0 ligament / 1 strand, lig_w (N,) lid weight (nan for strands), strand_tag [(si, half, ring)|None],
       bones_rest {bone: 4x4}, anchors, ligament design."""
    lig = ligament_design(bv, lv_closed, surfaces=solids)
    lv, lf, lw, luv = ligament_mesh(lig)
    if solids is not None:
        cap = np.abs(lw - 0.5) < 1e-9
        lv = relax_walls(lv, lw, solids[0], solids[1], cap=cap)
        lv = relax_walls_open(lv, lw, solids[0], solids[1], cap=cap)
    an = strand_anchors(bv, lv_closed)
    sv, sf, sw, suv, stags = strand_mesh(an)
    n0 = len(lv)
    verts = np.vstack([lv, sv])
    faces = [tuple(f) for f in lf] + [tuple(i + n0 for i in f) for f in sf]
    face_mat = [0] * len(lf) + [1] * len(sf)
    weights = []
    for w in lw:
        weights.append(ligament_weights(float(w)))
    weights += sw
    uv = np.vstack([luv, suv])
    part = np.array([0] * n0 + [1] * len(sv))
    lig_w = np.concatenate([lw, np.full(len(sv), np.nan)])
    tags = [None] * n0 + list(stags)
    bones = {"root": np.eye(4), "lid": lid_rest_matrix()}
    for b in LIG_HELPERS:
        bones[b] = lid_rest_matrix()
    for b, (c, X, Y, Z) in strand_rest_bones(an).items():
        bones[b] = rest_world_matrix(c, X, Y, Z)
    return {"verts": verts, "faces": faces, "face_mat": face_mat, "weights": weights, "uv": uv, "part": part,
            "lig_w": lig_w, "strand_tag": tags, "bones_rest": bones, "anchors": an, "ligament": lig}


def pose_mats(deg, strand_frame):
    """{bone: 4x4 armature-space pose matrix} for one frame (strand_frame = all_strand_poses()[0][i])."""
    out = {"root": np.eye(4), "lid": lid_world_matrix(deg)}
    for b, f in LIG_CHAIN[1:-1]:
        out[b] = lid_world_matrix(deg * f)
    for b, (c, X, Y, Z, r) in strand_frame.items():
        out[b] = bone_world_matrix(c, X, Y, Z, r)
    return out


def weight_matrix(weights, bones):
    idx = {b: i for i, b in enumerate(bones)}
    W = np.zeros((len(weights), len(bones)))
    for v, row in enumerate(weights):
        for b, w in row:
            W[v, idx[b]] += w
    return W


def skin(verts, W, bones, rest, pose):
    """Linear blend skinning: v' = sum_b w_b (P_b R_b^-1) v."""
    vh = np.hstack([verts, np.ones((len(verts), 1))])
    out = np.zeros((len(verts), 3))
    for i, b in enumerate(bones):
        col = W[:, i]
        m = col > 0
        if not m.any():
            continue
        D = pose[b] @ np.linalg.inv(rest[b])
        out[m] += col[m, None] * (vh[m] @ D.T)[:, :3]
    return out


# ================================================================================================ design file
DESIGN_NPZ = HERE + "build/slime_design.npz"
DESIGN_JSON = HERE + "build/slime_design.json"


def solids_map():
    """{name: (Solid, to_local(points, deg))} for the obstacles (needs scipy: system Python, not Blender)."""
    import clam_geo as cg
    from surface_dist import Solid
    bv, bt = cg.bottom()
    lrel, lt = cg.lid_rel()
    mv, mt = cg.mantle()
    pv, pt = cg.pearl()
    return {"bottom": (Solid(bv, bt), lambda q, a: q),
            "lid": (Solid(lrel, lt), lambda q, a: (np.asarray(q) - PIVOT) @ rot_x(-a)),
            "mantle": (Solid(mv, mt), lambda q, a: q),
            "pearl": (Solid(pv, pt), lambda q, a: q)}


def make():
    """System Python (numpy + scipy): shells -> design -> build/slime_design.npz/.json (the ONLY input of
    build_slime.py inside Blender, and of validate_slime.py)."""
    import time
    import clam_geo as cg
    t0 = time.time()
    os.makedirs(HERE + "build", exist_ok=True)
    bv, _bt = cg.bottom()
    lv0, _lt = cg.lid(0.0)
    sol = solids_map()
    A = assemble(bv, lv0, solids=(sol["bottom"][0], sol["lid"][0]))
    angles = anim_angles()
    tune_droops(A["anchors"], angles, sol)
    frames, bf = all_strand_poses(A["anchors"], angles)
    bones = all_bones()
    W = weight_matrix(A["weights"], bones)
    rest = np.array([A["bones_rest"][b] for b in bones])
    poses = np.zeros((len(angles), len(bones), 4, 4))
    for i, deg in enumerate(angles):
        pm = pose_mats(deg, frames[i])
        for j, b in enumerate(bones):
            poses[i, j] = pm[b]
    faces = A["faces"]
    fsize = np.array([len(f) for f in faces])
    fidx = np.concatenate([np.asarray(f) for f in faces])
    tags = A["strand_tag"]
    tag_arr = np.array([(-1, -1, -9) if t is None else (t[0], 0 if t[1] == "lo" else 1, t[2]) for t in tags])
    np.savez_compressed(DESIGN_NPZ, verts=A["verts"], face_size=fsize, face_index=fidx,
                        face_mat=np.array(A["face_mat"]), uv=A["uv"], part=A["part"], lig_w=A["lig_w"],
                        weights=W, bones=np.array(bones), rest=rest, angles=angles, poses=poses,
                        strand_tag=tag_arr, foot=foot_mask(tags), break_frames=np.array(bf))
    an_out = []
    for a in A["anchors"]:
        an_out.append({k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in a.items()})
    lig = A["ligament"]
    info = {"tool": "slime_design.make", "seconds": round(time.time() - t0, 1), "npz": DESIGN_NPZ,
            "vertices": int(len(A["verts"])), "faces": int(len(faces)), "bones": bones,
            "ligament": {"x_span_cm": lig["seam"]["x_span"], "stations": len(lig["stations"]),
                         "band_depth_cm": [round(float(s["y"][-1] - s["y"][0]), 2) for s in lig["stations"]][::10]},
            "anchors": an_out, "strands": STRANDS, "break_frames_anim": bf,
            "break_frames_scene": [OPEN_START + b for b in bf],
            "break_angle_at_frame_deg": [round(float(angles[b]), 4) for b in bf],
            "anim": {"frames": int(len(angles)), "fps": FPS, "scene_start": OPEN_START, "open_end_scene": OPEN_END,
                     "playback_end": PLAYBACK_END, "last_frame": ANIM_LAST,
                     "lid_open_deg_every_6th": [[i, float(angles[i])] for i in range(0, OPEN_END - OPEN_START + 1, 6)]
                     + [[ANIM_LAST, float(angles[ANIM_LAST])]]},
            "rest_bounds_cm_blender": {"min": A["verts"].min(axis=0).tolist(), "max": A["verts"].max(axis=0).tolist()},
            "frame0_bounds_cm_blender": {"min": skin(A["verts"], W, bones, A["bones_rest"], pose_mats(angles[0], frames[0])).min(axis=0).tolist(),
                                         "max": skin(A["verts"], W, bones, A["bones_rest"], pose_mats(angles[0], frames[0])).max(axis=0).tolist()},
            "lid_bone_rest_cm_blender": PIVOT.tolist(), "slots": [SLOT_LIGAMENT, SLOT_SLIME],
            "strand_vertices": int((A["part"] == 1).sum()), "ligament_vertices": int((A["part"] == 0).sum())}
    with open(DESIGN_JSON, "w", encoding="utf-8") as h:
        json.dump(info, h, indent=1)
    print("SLIME_DESIGN_OK|verts=%d|bones=%d|frames=%d|breaks_scene=%s|%.0fs" % (
        len(A["verts"]), len(bones), len(angles), info["break_frames_scene"], time.time() - t0))
    return info


def load_design(path=None):
    z = np.load(path or DESIGN_NPZ)
    faces, k = [], 0
    for n in z["face_size"]:
        faces.append(tuple(int(x) for x in z["face_index"][k:k + n]))
        k += n
    out = {key: z[key] for key in z.files}
    out["faces"] = faces
    out["bones"] = [str(b) for b in z["bones"]]
    return out


if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, HERE)
    make()
