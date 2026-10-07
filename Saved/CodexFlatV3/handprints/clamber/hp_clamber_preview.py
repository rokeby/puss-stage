"""Review images for the CLAMBER hand-print table (OFFLINE sketch, not a renderer of record).

  python hp_clamber_preview.py [PLACEMENT]

Writes to previews/ next to this file:
  elev_L.png, elev_R.png     flat wall elevations as seen from INSIDE the room, 1 px = 1 cm, z 0..950 cm above the
                             floor top.  Marble021 colour tiled at 150 cm (RepeatCm default), the set-B dune
                             surface at the face (sand fill, from SM_S3_ShoreGround_grid_h.npy), the per-metre dune
                             max (black steps), the floor rule = per-metre max + 20 (red dashes), the top envelope
                             (blue), practical lamps (amber) and wave flats (blue boxes) from the 6 Oct probe, the
                             base-liner / upper-tile seam (z 605, grey dots), every decal pasted from the atlas.
  elev_both_small.png        both walls at 40 %.
  composite_main_cam.png     the S3 main camera (PassageStills floathold still 0 pose) re-rendered: the set-B dune
                             heightfield is ray-marched and shaded; wall pixels are the live still with its old
                             prints removed by a 70th-percentile filter, modulated by Marble021, with the new decals
                             sampled from elev_R; pixels whose ray meets a wave flat's probed AABB first keep the
                             still.  Everything else in the old still (deck, rocks, plants) is replaced by sand.
  composite_vs_still.png     the live still (old 449-print table, flat deck) above the composite.
  preview_report.json        decals in frame / visible (centre ray reaches the wall), sha256 of every output.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
sys.path.insert(0, str(PROJECT / "Tools/FlatV3/handprints"))
import build_handprint_placement as hp  # noqa: E402

HP_DIR = PROJECT / "DerivedAssets/FlatV3/HandPrints"
ATLAS_DIR = HP_DIR / "atlas_job24d"
GRID_H = PROJECT / "DerivedAssets/S3Shore/SM_S3_ShoreGround_grid_h.npy"
SHORE_MANIFEST = PROJECT / "DerivedAssets/S3Shore/SM_S3_ShoreGround_manifest.json"
MARBLE = PROJECT / "DerivedAssets/S3Marble/Grime_20261007/T_S3MG_Marble021_Color_Grime_sRGB.png"
STILL_DIR = PROJECT / "Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-173228-floathold"
OUT = HERE / "previews"
Z_MAX = 950
ROOT_LANDED = np.array([11421.97275, 160000.0, -120.0])
FLOOR_TOP_WORLD_Z = -5.0
REPEAT_CM = 150.0
SEAM_Z = 605.0                     # base liner top: world 600 = 605 above the floor top
STAIN_GAIN = 0.9                   # sketch opacity on the atlas alpha (live OpacityGain not read)
STAIN_RGB = (62.0, 46.0, 36.0)     # sketch stain colour, eyeballed from the old prints in the 17:32 still


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def grid():
    h = np.load(GRID_H)
    man = json.loads(SHORE_MANIFEST.read_text(encoding="utf-8"))
    p = man["params"]
    xs = np.linspace(p["x_range"][0], p["x_range"][1], h.shape[0])
    ys = np.linspace(p["y_range"][0], p["y_range"][1], h.shape[1])
    return xs, ys, h


def interp2(xs, ys, A, x, y):
    x = np.clip(np.asarray(x, float), xs[0], xs[-1])
    y = np.clip(np.asarray(y, float), ys[0], ys[-1])
    i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    j = np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2)
    tx = (x - xs[i]) / (xs[i + 1] - xs[i])
    ty = (y - ys[j]) / (ys[j + 1] - ys[j])
    return ((A[i, j] * (1 - tx) + A[i + 1, j] * tx) * (1 - ty) + (A[i, j + 1] * (1 - tx) + A[i + 1, j + 1] * tx) * ty)


def face_profile(xs, ys, h, face_y_local, along):
    """Max over the 10 cm strip in front of the face (the decal box reaches 8 cm into the room)."""
    sgn = 1.0 if face_y_local > 0 else -1.0
    prof = None
    for dy in (0.0, 2.5, 5.0, 7.5, 10.0):
        v = interp2(xs, ys, h, along, np.full_like(along, face_y_local - sgn * dy))
        prof = v if prof is None else np.maximum(prof, v)
    return prof


def decal_layer(doc, wall, sheet, elements):
    """RGBA layer of one wall's decals, 1 px = 1 cm, as seen from the room."""
    length = int(wall["length_cm"])
    mirror = hp.decal_axes(wall["inward_normal"], 0.0)[2][0] < 0
    layer = Image.new("RGBA", (length, Z_MAX), (0, 0, 0, 0))
    for r in sorted((r for r in doc["decals"] if r["wall"] == wall["id"]), key=lambda r: (r["sort_order"], r["id"])):
        x, y, ew, eh = elements[r["element_id"]]["atlas_rect_px"]
        crop = sheet.crop((x, y, x + ew, y + eh))
        if r["flip"]:
            crop = crop.transpose(Image.FLIP_LEFT_RIGHT)
        crop = crop.resize((max(1, int(round(r["size_cm"][0]))), max(1, int(round(r["size_cm"][1])))), Image.LANCZOS)
        crop = crop.rotate(r["roll_on_wall_deg"], expand=True, resample=Image.BICUBIC)
        a = np.asarray(crop).astype(np.float32)
        a[..., :3] = STAIN_RGB          # live prints read dark brown (old still); atlas RGB x StainTint not read
        a[..., 3] *= STAIN_GAIN
        crop = Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")
        cx = (length - r["along_cm"]) if mirror else r["along_cm"]
        layer.alpha_composite(crop, (int(round(cx - crop.width / 2.0)), int(round(Z_MAX - r["height_cm"] - crop.height / 2.0))))
    return layer, mirror


def marble_tile(length):
    tex = Image.open(MARBLE).convert("RGB").resize((int(REPEAT_CM), int(REPEAT_CM)), Image.LANCZOS)
    bg = Image.new("RGB", (length, Z_MAX))
    for x0 in range(0, length, int(REPEAT_CM)):
        for y0 in range(0, Z_MAX, int(REPEAT_CM)):
            bg.paste(tex, (x0, y0))
    return bg


def elevation(doc, wall, layer, mirror, prof_fine, pm, cfg, boxes):
    length = int(wall["length_cm"])
    img = marble_tile(length).convert("RGBA")

    def px(a):
        return (length - a) if mirror else a

    def py(z):
        return Z_MAX - z

    d = ImageDraw.Draw(img, "RGBA")
    for b in boxes:
        a0, a1 = b["min"][0] - wall["origin_cm"][0], b["max"][0] - wall["origin_cm"][0]
        z0, z1 = b["min"][2] - wall["floor_z_cm"], b["max"][2] - wall["floor_z_cm"]
        if b["kind"] not in ("practical", "wave"):
            continue
        col = (235, 160, 20, 255) if b["kind"] == "practical" else (50, 100, 230, 255)
        xs_ = sorted((px(a0), px(a1)))
        d.rectangle([xs_[0], py(z1), xs_[1], py(z0)], outline=col, width=3)
    for x0 in range(0, length, 12):
        d.point([(x0, py(SEAM_Z))], fill=(110, 110, 110, 255))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img, "RGBA")
    # sand at the face
    sand = [(px(a), py(z)) for a, z in enumerate(prof_fine)]
    d.polygon(sand + [(px(length - 1), Z_MAX), (px(0), Z_MAX)], fill=(214, 188, 140, 235))
    d.line(sand, fill=(120, 95, 55, 255), width=2)
    # per-metre dune max (black steps) and the floor rule (red dashes)
    clear = cfg["min_clearance_cm"]
    for i, v in enumerate(pm):
        d.line([(px(i * 100), py(v)), (px(i * 100 + 100), py(v))], fill=(0, 0, 0, 255), width=2)
        for x0 in range(i * 100, i * 100 + 100, 20):
            d.line([(px(x0), py(v + clear)), (px(min(x0 + 10, i * 100 + 100)), py(v + clear))],
                   fill=(220, 0, 0, 255), width=2)
    # envelope: rebuild exactly as the generator does
    sys.path.insert(0, str(HERE))
    import hp_clamber_layout as lay
    knots = doc["stats"][wall["id"]]["envelope_knots"]
    prof = lay.Profile(pm, wall["length_cm"], cfg, knots)
    env = [(px(a), py(prof.top(a))) for a in range(0, length, 5)]
    d.line(env, fill=(30, 60, 220, 255), width=3)
    n = sum(1 for r in doc["decals"] if r["wall"] == wall["id"])
    no = sum(1 for r in doc["decals"] if r["wall"] == wall["id"] and r["outlier"])
    d.rectangle([0, 0, 1650, 64], fill=(255, 255, 255, 215))
    d.text((8, 4), "S3 wall %s seen from the room (%s), 1 px = 1 cm, z 0..950 above floor top.  %d decals (%d outlier-climb)."
           % (wall["id"], "+X / back corner to the LEFT" if mirror else "+X / back corner to the RIGHT", n, no),
           fill=(0, 0, 0, 255))
    d.text((8, 22), "sand = set B dune at the face; black = per-metre dune max; red dashes = floor rule (+%d cm, no "
           "decal extent below); blue = top envelope (outliers may exceed, <= 900)" % clear, fill=(0, 0, 0, 255))
    d.text((8, 40), "amber boxes = practical lamps (+30 cm, skipped); blue boxes = wave flats (skipped); grey dots = "
           "base liner / upper tile seam (z 605)", fill=(0, 0, 0, 255))
    return img.convert("RGB")


# ----------------------------------------------------------------------------- main camera composite

def cam_pose():
    man = json.loads((STILL_DIR / "passage_stills_manifest.json").read_text(encoding="utf-8"))
    s = [s for s in man["stills"] if s["i"] == 0][0]["pose"]
    return {"loc": np.array(s["loc"], float), "yaw": s["rot"]["yaw"], "pitch": s["rot"]["pitch"],
            "fov": s["fov_deg"], "aspect": s.get("aspect", 16 / 9)}


def cam_rays(pose, res):
    y, p = math.radians(pose["yaw"]), math.radians(pose["pitch"])
    fwd = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    right = np.array([-math.sin(y), math.cos(y), 0.0])
    up = np.cross(right, fwd)
    up /= np.linalg.norm(up)
    if up[2] < 0:
        up = -up
    th = math.tan(math.radians(pose["fov"]) / 2)
    tv = th / pose["aspect"]
    W, H = res
    sx = (2 * (np.arange(W) + 0.5) / W - 1) * th
    sy = (1 - 2 * (np.arange(H) + 0.5) / H) * tv
    SX, SY = np.meshgrid(sx, sy)
    d = fwd[None, None] + SX[..., None] * right[None, None] + SY[..., None] * up[None, None]
    return d / np.linalg.norm(d, axis=-1, keepdims=True), (fwd, right, up, th, tv)


def project(basis, C, P, res):
    fwd, right, up, th, tv = basis
    v = np.asarray(P, float) - C
    z = v @ fwd
    return ((v @ right) / z / th + 1) / 2 * res[0], (1 - (v @ up) / z / tv) / 2 * res[1], z


def composite(doc, walls, layers, boxes_all, res=(1600, 900)):
    pose = cam_pose()
    C = pose["loc"]
    D, basis = cam_rays(pose, res)
    H_, W_ = res[1], res[0]
    xs, ys, h = grid()
    Cl = C - ROOT_LANDED                       # local cm; local z of floor top = 115
    D2 = D.reshape(-1, 3)
    n = D2.shape[0]
    # planes (local): R wall y=999, L wall y=-999, far x=5997, roof z = 3000
    with np.errstate(divide="ignore", invalid="ignore"):
        tR = np.where(D2[:, 1] > 0, (999.0 - Cl[1]) / D2[:, 1], np.inf)
        tL = np.where(D2[:, 1] < 0, (-999.0 - Cl[1]) / D2[:, 1], np.inf)
        tB = np.where(D2[:, 0] > 0, (5997.0 - Cl[0]) / D2[:, 0], np.inf)
        tT = np.where(D2[:, 2] > 0, (3000.0 - Cl[2]) / D2[:, 2], np.inf)
    t_wall = np.minimum.reduce([tR, tL, tB, tT])
    which = np.argmin(np.stack([tR, tL, tB, tT]), axis=0)          # 0 = R wall
    # heightfield march (surface z_local = 115 + h)
    t_hit = np.full(n, np.inf)
    t = np.zeros(n)
    step = 6.0
    hmax = float(h.max()) + 115.0
    active = np.ones(n, bool)
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    prev_t = np.zeros(n)
    while active.any():
        idx = np.nonzero(active)[0]
        tt = t[idx] + step
        P = Cl[None] + D2[idx] * tt[:, None]
        ii = np.clip(np.round((P[:, 0] - xs[0]) / dx).astype(int), 0, len(xs) - 1)
        jj = np.clip(np.round((P[:, 1] - ys[0]) / dy).astype(int), 0, len(ys) - 1)
        below = P[:, 2] <= 115.0 + h[ii, jj]
        done_wall = tt >= t_wall[idx]
        escaped = (P[:, 2] > hmax) & (D2[idx, 2] >= 0)
        hit = below & ~done_wall
        t_hit[idx[hit]] = tt[hit]
        prev_t[idx] = t[idx]
        t[idx] = tt
        active[idx[hit | done_wall | escaped]] = False
    # refine hits by bisection on the bilinear surface
    hi_ = np.nonzero(np.isfinite(t_hit))[0]
    a, b = prev_t[hi_], t_hit[hi_]
    for _ in range(8):
        m = (a + b) / 2
        P = Cl[None] + D2[hi_] * m[:, None]
        under = P[:, 2] <= 115.0 + interp2(xs, ys, h, P[:, 0], P[:, 1])
        b = np.where(under, m, b)
        a = np.where(under, a, m)
    t_hit[hi_] = b
    # wave flats (probed AABBs, no margin) -> keep the still's pixel
    t_wave = np.full(n, np.inf)
    seen = set()
    for wid, rows in boxes_all.items():
        for row in rows:
            if not row["label"].startswith("S3 Wave") or row["label"] in seen:
                continue
            seen.add(row["label"])
            lo = np.array(row["aabb"]["min"]) - ROOT_LANDED
            hi2 = np.array(row["aabb"]["max"]) - ROOT_LANDED
            with np.errstate(divide="ignore", invalid="ignore"):
                t1 = (lo[None] - Cl[None]) / D2
                t2 = (hi2[None] - Cl[None]) / D2
            tn = np.nanmax(np.minimum(t1, t2), axis=1)
            tf = np.nanmin(np.maximum(t1, t2), axis=1)
            ok = (tf >= np.maximum(tn, 0))
            t_wave = np.where(ok & (tn < t_wave), np.maximum(tn, 0), t_wave)
    still = np.asarray(Image.open(STILL_DIR / "00_f300.png").convert("RGB").resize(res), np.float32) / 255.0
    # clean wall: 70th-percentile at quarter res (prints are darker than the marble), then upsampled
    small = np.asarray(Image.fromarray((still * 255).astype(np.uint8)).resize((W_ // 4, H_ // 4), Image.BOX),
                       np.float32) / 255.0
    clean_small = np.stack([ndimage.percentile_filter(small[..., c], 75, size=13) for c in range(3)], -1)
    clean = np.asarray(Image.fromarray((clean_small * 255).astype(np.uint8)).resize(res, Image.BICUBIC),
                       np.float32) / 255.0
    out = np.zeros((n, 3), np.float32)
    first = np.minimum.reduce([t_hit, t_wave, t_wall])
    is_dune = np.isfinite(t_hit) & (t_hit <= first + 1e-6)
    is_wave = ~is_dune & np.isfinite(t_wave) & (t_wave <= first + 1e-6)
    is_wall = ~is_dune & ~is_wave
    # sand shading
    P = Cl[None] + D2[is_dune] * t_hit[is_dune][:, None]
    e = 7.5
    gx = (interp2(xs, ys, h, P[:, 0] + e, P[:, 1]) - interp2(xs, ys, h, P[:, 0] - e, P[:, 1])) / (2 * e)
    gy = (interp2(xs, ys, h, P[:, 0], P[:, 1] + e) - interp2(xs, ys, h, P[:, 0], P[:, 1] - e)) / (2 * e)
    nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    L = np.array([-0.35, -0.45, 0.82])
    L /= np.linalg.norm(L)
    lam = np.clip(nrm @ L, 0, 1)
    mudw = np.clip((2900.0 - P[:, 0]) / 1400.0, 0, 1)
    base = np.array([0.80, 0.70, 0.54])[None] * (1 - mudw[:, None]) + np.array([0.45, 0.39, 0.32])[None] * mudw[:, None]
    out[is_dune] = base * (0.38 + 0.62 * lam)[:, None]
    out[is_wave] = still.reshape(-1, 3)[is_wave]
    # walls
    marble = np.asarray(Image.open(MARBLE).convert("L"), np.float32) / 255.0
    mmean = marble.mean()
    wl = np.nonzero(is_wall)[0]
    Pw = C[None] + D2[wl] * t_wall[wl][:, None]                     # world
    col = clean.reshape(-1, 3)[wl]
    u = ((Pw[:, 0] % REPEAT_CM) / REPEAT_CM * (marble.shape[1] - 1)).astype(int)
    v = (((Pw[:, 2] - FLOOR_TOP_WORLD_Z) % REPEAT_CM) / REPEAT_CM * (marble.shape[0] - 1)).astype(int)
    col = col * (1.0 + 0.6 * (marble[v, u] - mmean))[:, None]
    onR = which[wl] == 0
    lay = np.asarray(layers["R"][0], np.float32) / 255.0
    mirror = layers["R"][1]
    wR = walls["R"]
    along = Pw[onR, 0] - wR["origin_cm"][0]
    cx = np.clip(np.round((wR["length_cm"] - along) if mirror else along).astype(int), 0, lay.shape[1] - 1)
    cz = np.clip(np.round(Z_MAX - (Pw[onR, 2] - wR["floor_z_cm"])).astype(int), 0, lay.shape[0] - 1)
    s = lay[cz, cx]
    sub = col[onR]
    col[onR] = sub * (1 - s[:, 3:4]) + s[:, :3] * s[:, 3:4]
    out[wl] = col
    img = (np.clip(out.reshape(H_, W_, 3), 0, 1) * 255).astype(np.uint8)
    # stats: decals of R whose centre projects in frame and whose centre ray reaches the wall first
    in_frame = visible = 0
    for r in doc["decals"]:
        if r["wall"] != "R":
            continue
        X, Y, Z = project(basis, C, r["location"], res)
        if Z > 0 and 0 <= X < W_ and 0 <= Y < H_:
            in_frame += 1
            k = int(Y) * W_ + int(X)
            if is_wall[k] and which[k] == 0:
                visible += 1
    frame = {"in_frame": in_frame, "centre_visible": visible,
             "wall_px": int(is_wall.sum()), "dune_px": int(is_dune.sum()), "wave_px": int(is_wave.sum())}
    return Image.fromarray(img), Image.fromarray((still * 255).astype(np.uint8)), frame, pose


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    placement = Path(argv[0]) if argv else HERE / "placement_S03_clamber.json"
    doc = json.loads(placement.read_text(encoding="utf-8"))
    cfg = doc["config"]
    walls = {w["id"]: w for w in json.loads((HP_DIR / doc["walls_file"]).read_text(encoding="utf-8"))["walls"]}
    atlas = json.loads((ATLAS_DIR / "atlas.json").read_text(encoding="utf-8"))
    elements = {e["id"]: e for e in atlas["elements"]}
    sheet = Image.open(ATLAS_DIR / "T_S03_HandPrints_BaseColor.png").convert("RGBA")
    boxes, _ = hp.load_exclusions(hp.PROBE_DEFAULT)
    probe = json.loads(hp.PROBE_DEFAULT.read_text(encoding="utf-8"))
    sets = json.loads((PROJECT / doc["dune"]["file"]).read_text(encoding="utf-8"))
    pm_all = sets["sets"][cfg["height_set"]]["wall_profile_max_per_metre_cm"]
    xs, ys, h = grid()
    OUT.mkdir(exist_ok=True)
    outputs, layers, smalls = {}, {}, []
    for wid in cfg["walls"]:
        w = walls[wid]
        along = np.arange(int(w["length_cm"]), dtype=float)
        face = w["origin_cm"][1] - ROOT_LANDED[1]
        prof = face_profile(xs, ys, h, face, along)
        layer, mirror = decal_layer(doc, w, sheet, elements)
        layers[wid] = (layer, mirror)
        img = elevation(doc, w, layer, mirror, prof, pm_all[cfg["wall_dune_profile"][wid]], cfg, boxes.get(wid, []))
        p = OUT / ("elev_%s.png" % wid)
        img.save(p)
        outputs[p.name] = sha(p)
        smalls.append(img.resize((int(img.width * 0.4), int(img.height * 0.4)), Image.LANCZOS))
    full = Image.new("RGB", (max(s.width for s in smalls), sum(s.height + 10 for s in smalls)), (40, 40, 40))
    y = 0
    for s in smalls:
        full.paste(s, (0, y))
        y += s.height + 10
    p = OUT / "elev_both_small.png"
    full.save(p)
    outputs[p.name] = sha(p)
    comp, still, frame, pose = composite(doc, walls, layers, probe["decal_receivers_within_slab"])
    p = OUT / "composite_main_cam.png"
    comp.save(p)
    outputs[p.name] = sha(p)
    pair = Image.new("RGB", (comp.width, comp.height * 2 + 10), (40, 40, 40))
    pair.paste(still, (0, 0))
    pair.paste(comp, (0, comp.height + 10))
    dd = ImageDraw.Draw(pair)
    dd.rectangle([0, 0, 520, 20], fill=(255, 255, 255))
    dd.text((6, 4), "LIVE still 17:32 (old 449-print table, flat deck)", fill=(0, 0, 0))
    dd.rectangle([0, comp.height + 10, 700, comp.height + 30], fill=(255, 255, 255))
    dd.text((6, comp.height + 14), "SKETCH: set-B dunes ray-marched + clamber table (offline, not a render)",
            fill=(0, 0, 0))
    p = OUT / "composite_vs_still.png"
    pair.save(p)
    outputs[p.name] = sha(p)
    rep = {"placement": str(placement), "placement_sha256": sha(placement), "camera_pose": {
        "loc": pose["loc"].tolist(), "yaw": pose["yaw"], "pitch": pose["pitch"], "fov": pose["fov"]},
        "main_camera_R_wall": frame, "outputs": outputs, "grid_h_sha256": sha(GRID_H)}
    (OUT / "preview_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("HP_CLAMBER_PREVIEW_OK|%s" % json.dumps(frame))


if __name__ == "__main__":
    main()
