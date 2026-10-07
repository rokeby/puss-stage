"""C_soft preview (OFFLINE, 7 Oct evening): what Gary's "500 cd, softer edges" should look like, CALIBRATED on the
live variant-C still (PIE p2 of S3MG-20261007-193429, 4000 cd, hard strips -> blown white rectangles).

Same fake-spec model as s3mg_preview.py (helpers imported from it), plus:
  - BASE IMAGE = the LIVE C still (it already has the shore ground); only wall pixels are re-shaded. Wall mask =
    geometric R wall, minus the grey flats (mask from the floathold still, same camera), minus the new brown ground
    (live still: r - b > 0.10).
  - Ls(4000 cd) is CALIBRATED: bisection on the strip radiance until the preview-C blown area (min channel >= 0.97,
    wall pixels) equals the live still's blown area [measured]. Then Ls(500) = Ls(4000) * 500 / 4000 (radiance is
    linear in intensity [decl: physical units]); C_soft multiplies the strip source by the SAME feather profile that
    s3mg_build_feather.py writes into T_S3MG_StripFeather (u, v across each light rectangle).
  - exposure: per-channel k from the floathold baseline (s3mg_preview.py); the live wall is ~ +0.1 brighter from the
    strips' diffuse spill (DiffuseScale 0.1), which this model omits for the wall [inferred small at 500 cd: 1/8].
Writes preview_C_live_calibrated.png, preview_C_soft.png, preview_C_soft_hardedge.png, sheet_C_soft.png,
preview_soft_report.json in DerivedAssets/S3Marble/Grime_20261007.
"""
import json
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/S3MarbleGrime/"
P = runpy.run_path(HERE + "s3mg_preview.py")            # helpers only (its main() is guarded)
FTH = runpy.run_path(HERE + "s3mg_build_feather.py")
G, ROOT, RES = P["G"], P["ROOT"], P["RES"]
LIVE_C = ROOT + "/Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-194207-s3mg_20261007-193429-p2/00_f300.png"
FLOAT = P["STILL"]
s2l, l2s, aces, load = P["s2l"], P["l2s"], P["aces"], P["load"]
XR, ZR, PXCM, LIVE, MARBLE, HP = P["XR"], P["ZR"], P["PXCM"], P["LIVE"], P["MARBLE"], P["HP"]


def main():
    geo = json.load(open(G + "/geometry.json"))
    pose = geo["main_pose"]
    wall_y = geo["wall"]["plane_y_cm"]
    C = np.array(pose["loc"], float)
    live = load(LIVE_C, "RGB")
    flo = load(FLOAT, "RGB")
    d = P["cam_rays"](pose)
    tw = (wall_y - C[1]) / d[..., 1]
    Pw = C + tw[..., None] * d
    tf = np.where(d[..., 2] < 0, (geo["wall"]["floor_z_cm"] - C[2]) / np.minimum(d[..., 2], -1e-9), np.inf)
    geo_wall = (tw > 0) & (tw < tf) & (Pw[..., 2] >= ZR[0]) & (Pw[..., 2] < ZR[1]) & \
               (Pw[..., 0] > XR[0]) & (Pw[..., 0] < XR[1])
    xg = np.arange(RES[0])[None, :].repeat(RES[1], 0)
    yg = np.arange(RES[1])[:, None].repeat(RES[0], 1)
    lum_l = live @ np.array([0.2126, 0.7152, 0.0722])
    lum_f = flo @ np.array([0.2126, 0.7152, 0.0722])
    # flats (grey cut-outs, frame left): measured on the live still, lum 0.35-0.46 vs the wall behind them 0.57+
    occl = geo_wall & (xg < 520) & (yg > 200) & (lum_l < 0.52)      # flats on the LIVE still: lum 0.35-0.46; wall there 0.57+
    occl = ndi.binary_dilation(ndi.binary_opening(occl, iterations=1), iterations=1)
    ground = (live[..., 0] - live[..., 2]) > 0.10
    ground = ndi.binary_dilation(ndi.binary_opening(ground, iterations=2), iterations=2)
    wall_px = geo_wall & ~occl & ~ground
    wall_f = geo_wall & ~occl                              # floathold wall (for exposure calibration)

    X, Z = P["wall_grid"]()
    mcol = s2l(load(MARBLE + "Color.jpg", "RGB"))
    mrgh = load(MARBLE + "Roughness.jpg", "L")
    ncol = s2l(load(G + "/T_S3MG_Marble021_Color_Grime_sRGB.png", "RGB"))
    nrt = load(G + "/T_S3MG_Marble021_RoughGrime.png", "L")
    atlas = load(HP + "T_S03_HandPrints_BaseColor.png", "RGBA")
    ratlas = load(HP + "T_S03_HandPrints_Roughness.png", "L")
    grease = load(G + "/T_S3MG_GreaseAtlas.png", "RGB")
    elements = {e["id"]: e for e in json.load(open(HP + "atlas.json"))["elements"]}
    placement = json.load(open(ROOT + "/DerivedAssets/FlatV3/HandPrints/placement_S03.json"))["decals"]
    decs = sorted([x for x in placement if x["wall"] == "R" and XR[0] - 100 < x["location"][0] < XR[1] + 100],
                  key=lambda x: x.get("sort_order", 0))
    dcol, da, drg, gop, ght, galb = P["raster_decals"](decs, X, Z, wall_y, atlas, ratlas, elements, grease)

    def marble_albedo(colmap):
        bc = P["tile_sample"](colmap, X, Z)
        lumm = bc @ np.array([0.2126, 0.7152, 0.0722])
        return np.clip((lumm[..., None] + (bc - lumm[..., None]) * LIVE["Saturation"]) * LIVE["Brightness"], 0, 1)

    alb_live = marble_albedo(mcol)
    r_live = LIVE["MinR"] + (LIVE["MaxR"] - LIVE["MinR"]) * P["tile_sample"](mrgh, X, Z)
    alb_base = alb_live * (1 - da[..., None]) + dcol * da[..., None]
    r_base = r_live * (1 - da) + drg * da
    # variant A/C surface (identical to s3mg_preview.py)
    alb_new = marble_albedo(ncol)
    r_new = 0.04 + 0.56 * P["tile_sample"](nrt, X, Z)
    a15 = np.clip(da * 0.22, 0, 1)
    albA = (alb_new * (1 - a15[..., None]) + dcol * a15[..., None]) * (1 - 0.15 * galb[..., None])
    rA = r_new * (1 - a15) + drg * a15
    rA = rA * (1 - gop) + (0.30 + 0.25 * ght) * gop

    Pt = np.stack([X, np.full_like(X, wall_y), Z], -1)
    v_in = Pt - C
    cos_t = np.abs(v_in[..., 1]) / np.linalg.norm(v_in, axis=-1)
    F0 = 0.08 * LIVE["Specular"]
    F = F0 + (1 - F0) * (1 - cos_t) ** 5
    ml = geo["mirror_light"]
    ly = ml["strips_proposal"][0]["location_cm"][1]
    r = v_in.copy()
    r[..., 1] *= -1
    Q = Pt + ((ly - wall_y) / r[..., 1])[..., None] * r
    hard = np.zeros_like(X)
    soft = np.zeros_like(X)
    for st in ml["strips_proposal"]:
        lx, lz = st["location_cm"][0], st["location_cm"][2]
        w, h = st["source_width_cm"], st["source_height_cm"]
        u = (Q[..., 0] - (lx - w / 2)) / w
        v = (Q[..., 2] - (lz - h / 2)) / h
        hard = np.maximum(hard, ((u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)).astype(np.float32))
        soft = np.maximum(soft, FTH["feather_profile"](u, v).astype(np.float32))
    sig_k = 2 * ml["dist_light_to_wall_cm"] / ml["magnification_wall_to_light"]
    sigmas = [0.5, 1.5, 4, 10, 25, 60, 150, 400]
    st_hard = P["blur_stack"](hard, sigmas)
    st_soft = P["blur_stack"](soft, sigmas)

    def to_screen(m):
        xi = np.clip(((Pw[..., 0] - XR[0]) * PXCM).astype(int), 0, X.shape[1] - 1)
        zi = np.clip(((ZR[1] - Pw[..., 2]) * PXCM).astype(int), 0, X.shape[0] - 1)
        return m[zi, xi]

    spec_env = F * np.mean(alb_live)

    def lin(alb, rgh, stack=None, Ls=0.0, spill=0.0):
        """Returns pre-exposure RGB already multiplied by exposure: warm room light uses the per-channel k (fitted on
        the floathold still); the strips are WHITE light, so their specular and their diffuse spill use mean(k)."""
        room = (alb + spec_env[..., None]) * k_room
        white = alb * spill
        if stack is not None and Ls > 0:
            hl = P["sample_stack"](stack, sigmas, sig_k * np.maximum(rgh, 0.02) ** 2)
            white = white + (F * Ls * hl)[..., None]
        return to_screen(room + white * k_room.mean())

    k_room = np.ones(3)

    # exposure from the floathold baseline (as s3mg_preview.py)
    clean = wall_f & (to_screen(da) < 0.02)
    target = np.median(flo[clean], axis=0)
    base_scr = lin(alb_base, r_base)          # k_room = 1 here -> raw
    k = []
    for ch in range(3):
        med = np.median(base_scr[clean][:, ch])
        lo, hi = 0.01, 100.0
        for _ in range(60):
            m = math.sqrt(lo * hi)
            lo, hi = (m, hi) if s2l(l2s(aces(m * med))) < s2l(target[ch]) else (lo, m)
        k.append(m)
    k_room = np.array(k)

    def disp(linimg):
        return l2s(aces(linimg))

    blown = lambda img: int(((img.min(-1) >= 0.97) & wall_px).sum())
    live_blown = blown(live)
    # spill (strips' diffuse at DiffuseScale 0.1, 4000 cd): fit on live wall pixels well below the highlights
    calm = wall_px & (yg > 180) & (to_screen(da) < 0.02)
    tgt_calm = float(np.median(live[calm].mean(-1)))
    lo, hi = 0.0, 5.0
    for _ in range(50):
        m = 0.5 * (lo + hi)
        if float(np.median(disp(lin(albA, rA, spill=m))[calm].mean(-1))) < tgt_calm:
            lo = m
        else:
            hi = m
    spill4000 = 0.5 * (lo + hi)
    # calibrate Ls(4000 cd) on the live C still
    lo, hi = 0.1, 1e5
    for _ in range(50):
        m = math.sqrt(lo * hi)
        if blown(disp(lin(albA, rA, st_hard, m, spill4000))) < live_blown:
            lo = m
        else:
            hi = m
    Ls4000 = math.sqrt(lo * hi)
    Ls500 = Ls4000 * 500.0 / 4000.0
    out = {}
    for name, stack, Ls, sp in (("C_live_calibrated", st_hard, Ls4000, spill4000),
                                ("C_soft", st_soft, Ls500, spill4000 / 8.0 * 0.6084),
                                ("C_soft_hardedge", st_hard, Ls500, spill4000 / 8.0)):
        img = live.copy()
        img[wall_px] = disp(lin(albA, rA, stack, Ls, sp))[wall_px]
        out[name] = img
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(G + "/preview_%s.png" % name)
    rep = {"tool": "s3mg_preview_soft.py", "live_still": LIVE_C, "live_blown_wall_px": live_blown,
           "Ls_4000_calibrated": round(Ls4000, 3), "Ls_500": round(Ls500, 3), "spill_4000_fit": round(spill4000, 4),
           "calm_wall_target_luma": round(tgt_calm, 4),
           "blown_wall_px": {n: blown(i) for n, i in out.items()},
           "wall_p99_luma": {n: round(float(np.percentile(i[wall_px].mean(-1), 99)), 4) for n, i in out.items()},
           "highlight_peak_luma": {n: round(float(i[wall_px & (yg < 200)].mean(-1).max()), 4) for n, i in out.items()},
           "live_vs_calibrated_mean_abs_wall": round(float(np.abs(out["C_live_calibrated"][wall_px] - live[wall_px]).mean()), 4),
           "feather": json.load(open(G + "/T_S3MG_StripFeather.json"))}
    th = (800, 450)
    sheet = Image.new("RGB", (th[0] * 2, th[1] * 2))
    tiles = [("LIVE C (4000 cd, hard) PIE p2", live), ("preview C calibrated to live", out["C_live_calibrated"]),
             ("preview C_soft: 500 cd + feathered strips", out["C_soft"]),
             ("C_soft crop 2x", out["C_soft"][0:450, 400:1200])]
    for i, (lab, im) in enumerate(tiles):
        t = Image.fromarray((np.clip(im, 0, 1) * 255 + 0.5).astype(np.uint8)).resize(th)
        ImageDraw.Draw(t).text((10, 10), lab, fill=(255, 0, 0))
        sheet.paste(t, ((i % 2) * th[0], (i // 2) * th[1]))
    sheet.save(G + "/sheet_C_soft.png")
    json.dump(rep, open(G + "/preview_soft_report.json", "w"), indent=1)
    print(json.dumps({k_: v for k_, v in rep.items() if k_ != "feather"}, indent=1))


if __name__ == "__main__":
    main()
