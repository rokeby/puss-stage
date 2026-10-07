"""Review images for the GREASE SHEEN table (OFFLINE sketch; not a renderer of record).

  python hp_grease_preview.py [PLACEMENT]

Writes to previews_grease/:
  sheen_L.png, sheen_R.png      wall elevations as seen from the room, 1 px = 1 cm, z 0..950.  Marble021-grime colour
                                and roughness (T_S3MG_*), lit by a REVIEW light: three rows of feathered window panels
                                (z 110-270, 310-480, 520-700; 300 cm panels, 40 cm gaps; the same 22 % feather as
                                T_S3MG_StripFeather) reflected with a GGX-like blur sigma = k * roughness^2 (k from
                                geometry.json mirror_light, as s3mg_preview.py).  Grease = roughness only:
                                r = r_marble (1 - op) + (0.30 + 0.25 G) op, op = GreaseAtlas.R x gain (bench GREASE
                                params).  Overlays: set-B sand, floor rule (red dashes), envelope (blue), lamps (amber).
  mask_L.png, mask_R.png        the grease opacity alone (white = op 1), for reading the distribution.
  sheen_both_small.png          both sheen walls at 40 %.
  main_cam_*.png, sheet_main_cam.png
                                the S3 main camera: dunes ray-marched (hp_clamber_preview), R wall re-shaded with the
                                C_soft model of s3mg_preview_soft.py (Ls and spill read from its calibrated report;
                                exposure re-fitted on the floathold still exactly as there):
                                  sheen      = C_soft strips + grease, NO albedo (proposed)
                                  faint      = sheen + albedo x (1 - 0.06 B op) (the 'faint' option)
                                  room_only  = no strips: shows that without a reflection the grease almost vanishes
  preview_grease_report.json    numbers + sha256 of every output.
"""
from __future__ import annotations

import hashlib
import json
import math
import runpy
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hp_clamber_preview as cp  # noqa: E402
import hp_clamber_layout as base  # noqa: E402

hp = base.hp
PROJECT = base.PROJECT
GDIR = PROJECT / "DerivedAssets/S3Marble/Grime_20261007"
MG = PROJECT / "Saved/CodexConductor/S3MarbleGrime"
OUT = HERE / "previews_grease"
Z_MAX = 950
REPEAT = 150.0
R_MIN, R_RANGE = 0.30, 0.25                # bench GREASE (s3mg_bench.py:112)
FAINT = 0.06
REVIEW_ROWS = ((110.0, 270.0), (310.0, 480.0), (520.0, 700.0))   # review light rows (z above floor), 300 cm panels, 40 gaps


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p, mode):
    return np.asarray(Image.open(p).convert(mode), np.float32) / 255.0


def s2l(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def l2s(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def aces(x):
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


def raster_grease(decs, X, Z, gatlas):
    """op (1-prod(1-a)), height G (max), albedo weight B (max) on a world (X, Z) grid of one wall plane."""
    H, W = X.shape
    op = np.zeros((H, W), np.float32)
    gh = np.zeros((H, W), np.float32)
    gb = np.zeros((H, W), np.float32)
    x0g, dxg = X[0, 0], X[0, 1] - X[0, 0]
    z0g, dzg = Z[0, 0], Z[1, 0] - Z[0, 0]
    ah, aw = gatlas.shape[:2]
    for d in decs:
        U0, V0, US, VS = d["grease_uv_rect"]
        hy, hz = d["decal_size"][1], d["decal_size"][2]
        ext = math.hypot(hy, hz)
        cx, cz = d["location"][0], d["location"][2]
        ia = sorted(((cx - ext - x0g) / dxg, (cx + ext - x0g) / dxg))
        ib = sorted(((cz - ext - z0g) / dzg, (cz + ext - z0g) / dzg))
        x0, x1 = max(0, int(ia[0])), min(W, int(ia[1]) + 2)
        z0, z1 = max(0, int(ib[0])), min(H, int(ib[1]) + 2)
        if x1 <= x0 or z1 <= z0:
            continue
        sx, sz = X[z0:z1, x0:x1] - cx, Z[z0:z1, x0:x1] - cz
        ay, az = d["axes"]["y"], d["axes"]["z"]
        ly = sx * ay[0] + sz * ay[2]
        lz = sx * az[0] + sz * az[2]
        u = 0.5 + lz / (2 * hz)
        v = 0.5 + ly / (2 * hy)
        inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
        if d["flip"]:
            u = 1 - u
        au = np.clip(U0 + np.clip(u, 0, 1) * US, 0, 1 - 1e-6)
        av = np.clip(V0 + np.clip(v, 0, 1) * VS, 0, 1 - 1e-6)
        s = gatlas[(av * ah).astype(int), (au * aw).astype(int)] * inside[..., None]
        sl = (slice(z0, z1), slice(x0, x1))
        a = np.clip(s[..., 0] * d["gain"], 0, 1)
        op[sl] = 1 - (1 - op[sl]) * (1 - a)
        gh[sl] = np.maximum(gh[sl], s[..., 1])
        gb[sl] = np.maximum(gb[sl], s[..., 2] * d["gain"])
    return op, gh, gb


def tile(img, A, Z):
    h, w = img.shape[:2]
    return img[((((-Z) / REPEAT) % 1.0) * h).astype(int) % h, (((A / REPEAT) % 1.0) * w).astype(int) % w]


def feather_1d(t, f=0.22):
    def ss(e0, e1, x):
        x = np.clip((x - e0) / (e1 - e0), 0, 1)
        return x * x * (3 - 2 * x)
    return ss(0, f, t) * ss(0, f, 1 - t)


def review_light(A, Zr):
    """Three rows of feathered panels (review light only, REVIEW_ROWS), 300 cm panels, 40 cm gaps."""
    L = np.zeros_like(A)
    for z0, z1 in REVIEW_ROWS:
        v = (Zr - z0) / (z1 - z0)
        u = (A % 340.0) / 300.0
        L = np.maximum(L, np.where((u <= 1) & (v >= 0) & (v <= 1), feather_1d(np.clip(u, 0, 1)) * feather_1d(np.clip(v, 0, 1)), 0))
    return L


def blur_sample(L, rough, sig_k, sigmas=(0.5, 1.5, 4, 10, 25, 60, 150)):
    sig = sig_k * np.maximum(rough, 0.02) ** 2
    stack = [ndi.gaussian_filter(L, max(s, 0.3)) for s in sigmas]
    ls = np.log(np.array(sigmas))
    t = np.clip(np.interp(np.log(np.maximum(sig, sigmas[0])), ls, np.arange(len(ls))), 0, len(ls) - 1)
    i0 = np.floor(t).astype(int)
    i1 = np.minimum(i0 + 1, len(ls) - 1)
    f = t - i0
    S = np.stack(stack, 0)
    return np.take_along_axis(S, i0[None], 0)[0] * (1 - f) + np.take_along_axis(S, i1[None], 0)[0] * f


def elevation(doc, wall, decs, gatlas, mcol, mrough, sig_k, prof_fine, pm, cfg, boxes):
    length = int(wall["length_cm"])
    A, Zr = np.meshgrid(np.arange(length, dtype=np.float32) + 0.5, Z_MAX - np.arange(Z_MAX, dtype=np.float32) - 0.5)
    X = wall["origin_cm"][0] + A
    Zw = wall["floor_z_cm"] + Zr
    op, gh, gb = raster_grease(decs, X, Zw, gatlas)
    alb = tile(mcol, A, Zr)
    r = 0.04 + 0.56 * tile(mrough, A, Zr)
    r = r * (1 - op) + (R_MIN + R_RANGE * gh) * op
    L = review_light(A, Zr)
    hl = blur_sample(L, r, sig_k)
    lin = alb * 0.45 + 0.03 + (0.75 * hl)[..., None]
    img = l2s(aces(lin))
    mask = np.clip(op, 0, 1)
    mirror = hp.decal_axes(wall["inward_normal"], 0.0)[2][0] < 0
    if mirror:
        img, mask = img[:, ::-1], mask[:, ::-1]
    im = Image.fromarray((img * 255 + 0.5).astype(np.uint8)).convert("RGBA")
    mk = Image.fromarray((np.stack([mask] * 3, -1) * 255 + 0.5).astype(np.uint8))

    def px(a):
        return (length - a) if mirror else a

    for target in (im, mk):
        d = ImageDraw.Draw(target, "RGBA")
        sand = [(px(a), Z_MAX - z) for a, z in enumerate(prof_fine)]
        d.polygon(sand + [(px(length - 1), Z_MAX), (px(0), Z_MAX)], fill=(214, 188, 140, 255))
        for i, v in enumerate(pm):
            for x0 in range(i * 100, i * 100 + 100, 20):
                d.line([(px(x0), Z_MAX - v - 20), (px(min(x0 + 10, i * 100 + 100)), Z_MAX - v - 20)], fill=(220, 0, 0, 255), width=2)
        prof = base.Profile(pm, wall["length_cm"], cfg, doc["stats"][wall["id"]]["envelope_knots"])
        d.line([(px(a), Z_MAX - prof.top(a)) for a in range(0, length, 5)], fill=(30, 60, 220, 200), width=2)
        for b in boxes:
            if b["kind"] == "practical":
                a0, a1 = b["min"][0] - wall["origin_cm"][0], b["max"][0] - wall["origin_cm"][0]
                xs = sorted((px(a0), px(a1)))
                d.rectangle([xs[0], Z_MAX - (b["max"][2] + 5), xs[1], Z_MAX - (b["min"][2] + 5)], outline=(235, 160, 20, 255), width=2)
        d.rectangle([0, 0, 1900, 44], fill=(255, 255, 255, 220))
        d.text((8, 4), "S3 wall %s GREASE SHEEN (roughness-only decals) seen from the room, 1 px = 1 cm; %d decals; "
               "REVIEW light = 3 rows of feathered window panels reflected (not the show lighting)"
               % (wall["id"], len(decs)), fill=(0, 0, 0, 255))
        d.text((8, 22), "sand = set-B dune at the face; red dashes = floor rule (dune + 20); blue = envelope; amber = "
               "practical lamps (skipped); grease reads only where it breaks a reflection", fill=(0, 0, 0, 255))
    return im.convert("RGB"), mk, float(op.mean())


def main_cam(doc, gatlas):
    """C_soft re-shade of the R wall over the ray-marched set-B dunes."""
    P = runpy.run_path(str(MG / "s3mg_preview.py"))
    FTH = runpy.run_path(str(MG / "s3mg_build_feather.py"))
    soft = json.loads((GDIR / "preview_soft_report.json").read_text(encoding="utf-8"))
    geo = json.loads((GDIR / "geometry.json").read_text(encoding="utf-8"))
    XR, ZR, PXCM, LIVE, MARBLE, HPD = P["XR"], P["ZR"], P["PXCM"], P["LIVE"], P["MARBLE"], P["HP"]
    pose = geo["main_pose"]
    C = np.array(pose["loc"], float)
    wall_y = geo["wall"]["plane_y_cm"]
    # dunes + waves + wall mask from the clamber composite machinery (empty decal layer)
    walls = {w["id"]: w for w in json.loads((base.HP_DIR / "walls_S03.json").read_text(encoding="utf-8"))["walls"]}
    empty = Image.new("RGBA", (int(walls["R"]["length_cm"]), cp.Z_MAX), (0, 0, 0, 0))
    probe = json.loads(hp.PROBE_DEFAULT.read_text(encoding="utf-8"))
    cp.composite({"decals": []}, walls, {"R": (empty, True)}, probe["decal_receivers_within_slab"])
    M = cp.LAST
    res = M["res"]
    H_, W_ = res[1], res[0]
    d = P["cam_rays"](pose)
    tw = (wall_y - C[1]) / d[..., 1]
    Pw = C + tw[..., None] * d
    flo_ = load(P["STILL"], "RGB")
    xg_ = np.arange(W_)[None, :].repeat(H_, 0)
    yg_ = np.arange(H_)[:, None].repeat(W_, 1)
    # grey flats in the floathold still (lum 0.31-0.46 vs wall 0.57+, frame left; s3mg_preview_soft's mask)
    in_wave_box = M["is_wave"].reshape(H_, W_)
    flats = ndi.binary_opening(in_wave_box & (xg_ < 520) & (yg_ > 200) &
                               ((flo_ @ np.array([0.2126, 0.7152, 0.0722])) < 0.47), iterations=1)
    not_dune = ~M["is_dune"].reshape(H_, W_)
    hits_R = (M["which"] == 0).reshape(H_, W_)
    wall_px = not_dune & hits_R & ~flats & (Pw[..., 2] >= ZR[0]) & (Pw[..., 2] < ZR[1]) & \
        (Pw[..., 0] > XR[0]) & (Pw[..., 0] < XR[1])
    flats_px = not_dune & flats
    X, Z = P["wall_grid"]()
    mcol = s2l(load(MARBLE + "Color.jpg", "RGB"))
    mrgh = load(MARBLE + "Roughness.jpg", "L")
    ncol = s2l(load(str(GDIR / "T_S3MG_Marble021_Color_Grime_sRGB.png"), "RGB"))
    nrt = load(str(GDIR / "T_S3MG_Marble021_RoughGrime.png"), "L")
    atlas = load(HPD + "T_S03_HandPrints_BaseColor.png", "RGBA")
    ratlas = load(HPD + "T_S03_HandPrints_Roughness.png", "L")
    elements = {e["id"]: e for e in json.load(open(HPD + "atlas.json"))["elements"]}
    flo = load(P["STILL"], "RGB")
    # exposure exactly as s3mg_preview(_soft): baseline = live marble + the OLD live stain decals, floathold still
    old = json.loads((base.HP_DIR / "placement_S03.json").read_text(encoding="utf-8"))["decals"]
    olds = sorted([x for x in old if x["wall"] == "R" and XR[0] - 100 < x["location"][0] < XR[1] + 100],
                  key=lambda x: x.get("sort_order", 0))
    dcol, da, drg, _, _, _ = P["raster_decals"](olds, X, Z, wall_y, atlas, ratlas, elements, None)

    def marble_albedo(colmap):
        bc = P["tile_sample"](colmap, X, Z)
        lumm = bc @ np.array([0.2126, 0.7152, 0.0722])
        return np.clip((lumm[..., None] + (bc - lumm[..., None]) * LIVE["Saturation"]) * LIVE["Brightness"], 0, 1)

    alb_live = marble_albedo(mcol)
    r_live = LIVE["MinR"] + (LIVE["MaxR"] - LIVE["MinR"]) * P["tile_sample"](mrgh, X, Z)
    alb_base = alb_live * (1 - da[..., None]) + dcol * da[..., None]
    r_base = r_live * (1 - da) + drg * da
    decs = [x for x in doc["decals"] if x["wall"] == "R" and XR[0] - 150 < x["location"][0] < XR[1] + 150]
    gop, ght, galb = raster_grease(decs, X, Z, gatlas)
    alb_new = marble_albedo(ncol)
    r_new = 0.04 + 0.56 * P["tile_sample"](nrt, X, Z)
    rG = r_new * (1 - gop) + (R_MIN + R_RANGE * ght) * gop
    Pt = np.stack([X, np.full_like(X, wall_y), Z], -1)
    v_in = Pt - C
    cos_t = np.abs(v_in[..., 1]) / np.linalg.norm(v_in, axis=-1)
    F0 = 0.08 * LIVE["Specular"]
    F = F0 + (1 - F0) * (1 - cos_t) ** 5
    ml = geo["mirror_light"]
    ly = ml["strips_proposal"][0]["location_cm"][1]
    rr = v_in.copy()
    rr[..., 1] *= -1
    Q = Pt + ((ly - wall_y) / rr[..., 1])[..., None] * rr
    soft_m = np.zeros_like(X)
    for st in ml["strips_proposal"]:
        lx, lz = st["location_cm"][0], st["location_cm"][2]
        w, h = st["source_width_cm"], st["source_height_cm"]
        soft_m = np.maximum(soft_m, FTH["feather_profile"]((Q[..., 0] - (lx - w / 2)) / w,
                                                           (Q[..., 2] - (lz - h / 2)) / h).astype(np.float32))
    sig_k = 2 * ml["dist_light_to_wall_cm"] / ml["magnification_wall_to_light"]
    sigmas = [0.5, 1.5, 4, 10, 25, 60, 150, 400]
    st_soft = P["blur_stack"](soft_m, sigmas)

    def to_screen(m):
        xi = np.clip(((Pw[..., 0] - XR[0]) * PXCM).astype(int), 0, X.shape[1] - 1)
        zi = np.clip(((ZR[1] - Pw[..., 2]) * PXCM).astype(int), 0, X.shape[0] - 1)
        return m[zi, xi]

    spec_env = F * np.mean(alb_live)
    k_room = np.ones(3)

    def lin(alb, rgh, Ls=0.0, spill=0.0):
        room = (alb + spec_env[..., None]) * k_room
        white = alb * spill
        if Ls > 0:
            white = white + (F * Ls * P["sample_stack"](st_soft, sigmas, sig_k * np.maximum(rgh, 0.02) ** 2))[..., None]
        return to_screen(room + white * k_room.mean())

    # floathold wall for exposure: geometric wall minus the grey flats (as s3mg_preview_soft)
    tw0 = (wall_y - C[1]) / d[..., 1]
    tf = np.where(d[..., 2] < 0, (geo["wall"]["floor_z_cm"] - C[2]) / np.minimum(d[..., 2], -1e-9), np.inf)
    geo_wall = (tw0 > 0) & (tw0 < tf) & (Pw[..., 2] >= ZR[0]) & (Pw[..., 2] < ZR[1]) & (Pw[..., 0] > XR[0]) & (Pw[..., 0] < XR[1])
    xg = np.arange(W_)[None, :].repeat(H_, 0)
    yg = np.arange(H_)[:, None].repeat(W_, 1)
    lum_f = flo @ np.array([0.2126, 0.7152, 0.0722])
    occl = ndi.binary_dilation(ndi.binary_opening(geo_wall & (xg < 520) & (yg > 200) & (lum_f < 0.52), iterations=1), iterations=1)
    clean = geo_wall & ~occl & (to_screen(da) < 0.02)
    target = np.median(flo[clean], axis=0)
    base_scr = lin(alb_base, r_base)
    k = []
    for ch in range(3):
        med = np.median(base_scr[clean][:, ch])
        lo, hi = 0.01, 100.0
        for _ in range(60):
            m = math.sqrt(lo * hi)
            lo, hi = (m, hi) if s2l(l2s(aces(m * med))) < s2l(target[ch]) else (lo, m)
        k.append(m)
    k_room = np.array(k)
    Ls500 = soft["Ls_500"]
    spill500 = soft["spill_4000_fit"] / 8.0 * 0.6084
    ground = M["ground"].reshape(H_, W_, 3)
    out = {}
    for name, alb, Ls, sp in (("sheen", alb_new, Ls500, spill500),
                              ("faint", alb_new * (1 - FAINT * galb)[..., None], Ls500, spill500),
                              ("room_only", alb_new, 0.0, 0.0)):
        img = ground.copy()
        img[flats_px] = flo_[flats_px]
        img[wall_px] = l2s(aces(lin(alb, rG, Ls, sp)))[wall_px]
        # wall pixels outside the shaded window (above z 330): keep a plain re-shade without strips
        out[name] = img
    # numbers: grease pixels inside the highlights vs clean highlight
    hl_scr = to_screen(P["sample_stack"](st_soft, sigmas, sig_k * np.maximum(r_new, 0.02) ** 2))
    g_scr = to_screen(gop)
    lum = out["sheen"] @ np.array([0.2126, 0.7152, 0.0722])
    inhl = wall_px & (hl_scr > 0.3)
    rep = {"wall_px": int(wall_px.sum()), "decals_rasterised": len(decs),
           "highlight_px": int(inhl.sum()),
           "lum_highlight_clean_p50": round(float(np.median(lum[inhl & (g_scr < 0.05)])), 4) if (inhl & (g_scr < 0.05)).any() else None,
           "lum_highlight_grease_p50": round(float(np.median(lum[inhl & (g_scr > 0.1)])), 4) if (inhl & (g_scr > 0.1)).any() else None,
           "grease_px_in_highlight": int((inhl & (g_scr > 0.1)).sum()),
           "lum_outside_highlight_clean_vs_grease_p50": [
               round(float(np.median(lum[wall_px & (hl_scr < 0.02) & (g_scr < 0.05)])), 4),
               round(float(np.median(lum[wall_px & (hl_scr < 0.02) & (g_scr > 0.1)])), 4) if (wall_px & (hl_scr < 0.02) & (g_scr > 0.1)).any() else None],
           "Ls_500": Ls500, "spill_500": spill500, "exposure_k": [round(float(v), 4) for v in k_room]}
    return out, rep


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    placement = Path(argv[0]) if argv else HERE / "placement_S03_grease.json"
    doc = json.loads(placement.read_text(encoding="utf-8"))
    cfg = doc["config"]
    OUT.mkdir(exist_ok=True)
    gatlas = load(str(GDIR / "T_S3MG_GreaseAtlas.png"), "RGB")
    mcol = s2l(load(str(GDIR / "T_S3MG_Marble021_Color_Grime_sRGB.png"), "RGB"))
    mrough = load(str(GDIR / "T_S3MG_Marble021_RoughGrime.png"), "L")
    geo = json.loads((GDIR / "geometry.json").read_text(encoding="utf-8"))
    sig_k = 2 * geo["mirror_light"]["dist_light_to_wall_cm"] / geo["mirror_light"]["magnification_wall_to_light"]
    walls = {w["id"]: w for w in json.loads((base.HP_DIR / doc["walls_file"]).read_text(encoding="utf-8"))["walls"]}
    sets = json.loads((PROJECT / doc["dune"]["file"]).read_text(encoding="utf-8"))
    pm_all = sets["sets"][cfg["height_set"]]["wall_profile_max_per_metre_cm"]
    boxes, _ = hp.load_exclusions(hp.PROBE_DEFAULT)
    xs, ys, h = cp.grid()
    outputs, smalls, rep = {}, [], {"placement_sha256": sha(placement), "walls": {}}
    for wid in cfg["walls"]:
        w = walls[wid]
        prof = cp.face_profile(xs, ys, h, w["origin_cm"][1] - cp.ROOT_LANDED[1], np.arange(int(w["length_cm"]), dtype=float))
        decs = [r for r in doc["decals"] if r["wall"] == wid]
        img, mk, mean_op = elevation(doc, w, decs, gatlas, mcol, mrough, sig_k, prof,
                                     pm_all[cfg["wall_dune_profile"][wid]], cfg, boxes.get(wid, []))
        for nm, im in (("sheen_%s.png" % wid, img), ("mask_%s.png" % wid, mk)):
            im.save(OUT / nm)
            outputs[nm] = sha(OUT / nm)
        smalls.append(img.resize((int(img.width * 0.4), int(img.height * 0.4)), Image.LANCZOS))
        rep["walls"][wid] = {"mean_grease_opacity_on_wall_0_950": round(mean_op, 4), "decals": len(decs)}
    full = Image.new("RGB", (max(s.width for s in smalls), sum(s.height + 10 for s in smalls)), (40, 40, 40))
    y = 0
    for s in smalls:
        full.paste(s, (0, y))
        y += s.height + 10
    full.save(OUT / "sheen_both_small.png")
    outputs["sheen_both_small.png"] = sha(OUT / "sheen_both_small.png")
    imgs, mrep = main_cam(doc, gatlas)
    rep["main_cam"] = mrep
    for name, im in imgs.items():
        p = OUT / ("main_cam_%s.png" % name)
        Image.fromarray((np.clip(im, 0, 1) * 255 + 0.5).astype(np.uint8)).save(p)
        outputs[p.name] = sha(p)
    th = (800, 450)
    sheet = Image.new("RGB", (th[0] * 2, th[1] * 2))
    tiles = [("SHEEN (proposed): C_soft strips + grease, no albedo", imgs["sheen"]),
             ("FAINT option: + albedo x (1 - 0.06 B)", imgs["faint"]),
             ("ROOM LIGHT ONLY (no strips): grease nearly vanishes", imgs["room_only"]),
             ("SHEEN crop 2x (strip band)", imgs["sheen"][0:450, 400:1200])]
    for i, (lab, im) in enumerate(tiles):
        t = Image.fromarray((np.clip(im, 0, 1) * 255 + 0.5).astype(np.uint8)).resize(th)
        dd = ImageDraw.Draw(t)
        dd.rectangle([0, 0, 470, 18], fill=(255, 255, 255))
        dd.text((6, 3), lab, fill=(0, 0, 0))
        sheet.paste(t, ((i % 2) * th[0], (i // 2) * th[1]))
    sheet.save(OUT / "sheet_main_cam.png")
    outputs["sheet_main_cam.png"] = sha(OUT / "sheet_main_cam.png")
    rep["outputs"] = outputs
    (OUT / "preview_grease_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("HP_GREASE_PREVIEW_OK|%s" % json.dumps(mrep))


if __name__ == "__main__":
    main()
