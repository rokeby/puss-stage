"""Grease v2 validator (OFFLINE).  Reads the v2 outputs + the live sources; writes gv2_validate_report.json next to
the outputs.  Every check is an assertion that can fail; prints GV2_VALIDATE_PASS only if all pass.

Checks
  1 R byte-identical to the live atlas; B byte-identical; G identical wherever R == 0.  Same size/mode as live.
  2 per element: mean G on the ridge band < mean G in the centre (elements with >= 20 centre texels); the same
    numbers for the LIVE G (expected the other way round: that is the defect being fixed).
  3 per confident element: share of glossy texels (G < 0.25, roughness < 0.3625) in the END edge zone (boundary
    normal within 30 deg of the smear axis) vs the SIDE zone (within 30 deg of perpendicular), edge zone = 0..6 mm in.
  4 per confident element: structure-tensor line angle of the streak field and of the high-passed v2 G inside the
    body vs the estimated smear direction (axial error, deg).
  5 PrintNormal v2: same size/mode as live; decoded length; texels farther than 2 px (1024) from any element rect
    are exactly flat (128,128,255) [island-border seam check]; max |xy| in the 2-px ring just inside each rect.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gv2_lib as L  # noqa: E402

ROOT = "E:/PussStage"
OUT = ROOT + "/DerivedAssets/S3Marble/GreaseV2_20261008"
LIVE_ATLAS = ROOT + "/DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png"
LIVE_NORMAL = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_Normal.png"
ATLAS_JSON = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/atlas.json"
GLOSSY_G = 0.25
STREAK_MAX_ERR_DEG = 10.0


def end_side(G, dist_mm, endness, body):
    zone = body & (dist_mm >= 0) & (dist_mm <= 6.0)
    ends = zone & (endness >= math.cos(math.radians(30)) ** 2)
    sides = zone & (endness <= math.sin(math.radians(30)) ** 2)
    if ends.sum() < 20 or sides.sum() < 20:
        return None
    return {"end_glossy_share": round(float((G[ends] < GLOSSY_G).mean()), 4),
            "side_glossy_share": round(float((G[sides] < GLOSSY_G).mean()), 4),
            "end_mean_G": round(float(G[ends].mean()), 4), "side_mean_G": round(float(G[sides].mean()), 4),
            "n_end": int(ends.sum()), "n_side": int(sides.sum())}


def check_atlas(live, v2):
    return {"same_shape_mode": live.shape == v2.shape and v2.dtype == np.uint8,
            "R_identical": L.r_identical(live, v2),
            "B_identical": bool(np.array_equal(live[..., 2], v2[..., 2])),
            "G_identical_where_R0": bool(np.array_equal(live[..., 1][live[..., 0] == 0], v2[..., 1][live[..., 0] == 0])),
            "G_changed_texels": int((live[..., 1] != v2[..., 1]).sum())}


def main():
    meta = json.load(open(ATLAS_JSON))
    els = meta["elements"]
    live = np.asarray(Image.open(LIVE_ATLAS))
    v2 = np.asarray(Image.open(OUT + "/T_HP_S03_GreaseAtlas_v2.png"))
    livn = np.asarray(Image.open(LIVE_NORMAL))
    v2n = np.asarray(Image.open(OUT + "/T_HP_S03_PrintNormal_v2.png"))
    F = np.load(OUT + "/gv2_fields.npz")
    dirs = json.load(open(OUT + "/gv2_directions.json"))
    rep = {"atlas": check_atlas(live, v2), "modes": [Image.open(LIVE_ATLAS).mode, Image.open(OUT + "/T_HP_S03_GreaseAtlas_v2.png").mode,
                                                    Image.open(LIVE_NORMAL).mode, Image.open(OUT + "/T_HP_S03_PrintNormal_v2.png").mode]}
    G2, G1 = v2[..., 1] / 255.0, live[..., 1] / 255.0
    rim, centre, body = F["rim2048"], F["centre2048"], F["body2048"]
    owner, endness, streak = F["owner2048"], F["endness2048"], F["streak2048"]
    per = {}
    for idx, e in enumerate(els):
        x, y, w, h = [v // 2 for v in e["atlas_rect_px"]]
        win = (slice(y, y + h), slice(x, x + w))
        pxmm = (e["atlas_rect_px"][2] / e["width_cm"]) / 10.0 / 2.0           # at 2048
        own = owner[win] == idx
        dmm = F["dist2048"][win] / pxmm
        d = dirs[e["id"]]
        r = {"kind": e["kind"], "theta_deg": d["theta_deg"], "conf": d["conf"], "low_conf": d["low_confidence"]}
        outer = own & (dmm >= -2.5) & (dmm <= -0.5) & (live[..., 0][win] > 0)
        t2 = L.ridge_test(G2[win], rim[win] & own, centre[win] & own, outer)
        t1 = L.ridge_test(G1[win], rim[win] & own, centre[win] & own, outer)
        if t2:
            r["v2_rim_G"], r["v2_centre_G"], r["v2_outer_flank_G"] = round(t2["rim"], 4), round(t2["centre"], 4), round(t2["outer"], 4)
            r["v1_rim_G"], r["v1_centre_G"], r["v1_outer_flank_G"] = round(t1["rim"], 4), round(t1["centre"], 4), round(t1["outer"], 4)
            r["ridge_lower_than_centre"] = t2["rim_lt_centre"]
            r["v2_crest_local_min"], r["v1_crest_local_min"] = t2["crest_local_min"], t1["crest_local_min"]
        r["end_side_v2"] = end_side(G2[win], dmm, endness[win], body[win] & own)
        if not d["low_confidence"]:
            th = math.radians(d["theta_deg"])
            bw = body[win] & own
            serr, scoh = L.orientation_error(streak[win], bw, th)
            gerr, gcoh = L.orientation_error(G2[win], bw & (F["dist2048"][win] > 3 * pxmm), th, hp_sigma=3)
            r["streak_angle_err_deg"] = round(serr, 2)
            r["streak_coherence"] = round(scoh, 3)
            r["G_hp_angle_err_deg"] = round(gerr, 2)
            r["G_hp_coherence"] = round(gcoh, 3)
        per[e["id"]] = r
    rep["per_element"] = per
    withc = [r for r in per.values() if "ridge_lower_than_centre" in r]
    rep["ridge_vs_centre"] = {
        "elements_tested": len(withc), "elements_without_centre": len(per) - len(withc),
        "v2_ridge_lower_count": sum(r["ridge_lower_than_centre"] for r in withc),
        "v2_mean_rim_G": round(float(np.mean([r["v2_rim_G"] for r in withc])), 4),
        "v2_mean_centre_G": round(float(np.mean([r["v2_centre_G"] for r in withc])), 4),
        "v1_mean_rim_G": round(float(np.mean([r["v1_rim_G"] for r in withc])), 4),
        "v1_mean_centre_G": round(float(np.mean([r["v1_centre_G"] for r in withc])), 4),
        "v1_ridge_lower_count": sum(r["v1_rim_G"] < r["v1_centre_G"] for r in withc),
        "crest_tested": sum("v2_crest_local_min" in r for r in withc),
        "v2_crest_local_min_count": sum(bool(r.get("v2_crest_local_min")) for r in withc),
        "v1_crest_local_min_count": sum(bool(r.get("v1_crest_local_min")) for r in withc),
        "v2_mean_outer_flank_G": round(float(np.mean([r["v2_outer_flank_G"] for r in withc if "v2_outer_flank_G" in r])), 4),
        "v1_mean_outer_flank_G": round(float(np.mean([r["v1_outer_flank_G"] for r in withc if "v1_outer_flank_G" in r])), 4)}
    conf = [r for r in per.values() if not r["low_conf"] and r["end_side_v2"]]
    lowc = [r for r in per.values() if r["low_conf"] and r["end_side_v2"]]
    rep["end_vs_side"] = {
        "confident_n": len(conf),
        "confident_mean_end_glossy": round(float(np.mean([r["end_side_v2"]["end_glossy_share"] for r in conf])), 4),
        "confident_mean_side_glossy": round(float(np.mean([r["end_side_v2"]["side_glossy_share"] for r in conf])), 4),
        "confident_end_ge_side_count": sum(r["end_side_v2"]["end_glossy_share"] >= r["end_side_v2"]["side_glossy_share"] for r in conf),
        "lowconf_n": len(lowc),
        "lowconf_mean_end_glossy": round(float(np.mean([r["end_side_v2"]["end_glossy_share"] for r in lowc])), 4) if lowc else None,
        "lowconf_mean_side_glossy": round(float(np.mean([r["end_side_v2"]["side_glossy_share"] for r in lowc])), 4) if lowc else None}
    sc = [r for r in per.values() if "streak_angle_err_deg" in r]
    rep["streak_orientation"] = {
        "n": len(sc), "streak_err_deg_max": max(r["streak_angle_err_deg"] for r in sc),
        "streak_err_deg_median": float(np.median([r["streak_angle_err_deg"] for r in sc])),
        "G_hp_err_deg_median": float(np.median([r["G_hp_angle_err_deg"] for r in sc])),
        "G_hp_err_deg_p90": float(np.percentile([r["G_hp_angle_err_deg"] for r in sc], 90)),
        "G_hp_err_deg_max": max(r["G_hp_angle_err_deg"] for r in sc)}
    # ---- normal
    n = v2n.astype(np.float64) / 255.0 * 2 - 1
    ln = np.linalg.norm(n, axis=-1)
    inrect = np.zeros((1024, 1024), bool)
    ring = np.zeros((1024, 1024), bool)
    for e in els:
        x, y, w, h = [v // 4 for v in e["atlas_rect_px"]]
        inrect[y:y + h, x:x + w] = True
        rr = np.zeros_like(ring)
        rr[y:y + h, x:x + w] = True
        rr[y + 2:y + h - 2, x + 2:x + w - 2] = False
        ring |= rr
    far = ~ndi.binary_dilation(inrect, iterations=2)
    gutter = ndi.binary_dilation(inrect, iterations=2) & ~inrect
    flat = np.all(np.abs(v2n.astype(int) - np.array([128, 128, 255])) <= 1, -1)
    live_flat = np.all(np.abs(livn.astype(int) - np.array([128, 128, 255])) <= 1, -1)
    xy2 = np.hypot(n[..., 0], n[..., 1])
    livxy = np.hypot(livn[..., 0] / 255.0 * 2 - 1, livn[..., 1] / 255.0 * 2 - 1)
    rep["normal"] = {"same_shape": livn.shape == v2n.shape, "length_min": round(float(ln.min()), 4),
                     "length_max": round(float(ln.max()), 4), "length_p01_p99": [round(float(v), 4) for v in np.percentile(ln, [1, 99])],
                     "z_min": round(float(n[..., 2].min()), 4),
                     "far_from_islands_texels": int(far.sum()), "far_flat_share_v2": round(float(flat[far].mean()), 6),
                     "far_flat_share_live": round(float(live_flat[far].mean()), 6),
                     "gutter_texels": int(gutter.sum()),
                     "gutter_nonflat_v2": int((~flat & gutter).sum()), "gutter_nonflat_live": int((~live_flat & gutter).sum()),
                     "gutter_max_xy_v2": round(float(xy2[gutter].max()), 4), "gutter_max_xy_live": round(float(livxy[gutter].max()), 4),
                     "rect_ring_max_xy_v2": round(float(xy2[ring].max()), 4), "rect_ring_max_xy_live": round(float(livxy[ring].max()), 4),
                     "inside_p99_xy_v2": round(float(np.percentile(xy2[inrect], 99)), 4),
                     "inside_p99_xy_live": round(float(np.percentile(livxy[inrect], 99)), 4)}
    a = rep["atlas"]
    checks = {
        "R_identical": a["R_identical"], "B_identical": a["B_identical"], "G_kept_where_R0": a["G_identical_where_R0"],
        "atlas_shape_mode": a["same_shape_mode"] and rep["modes"][0] == rep["modes"][1],
        "ridge_lower_all": rep["ridge_vs_centre"]["v2_ridge_lower_count"] == rep["ridge_vs_centre"]["elements_tested"],
        "ends_ge_sides_mean": rep["end_vs_side"]["confident_mean_end_glossy"] >= rep["end_vs_side"]["confident_mean_side_glossy"],
        "streak_orientation": rep["streak_orientation"]["streak_err_deg_max"] <= STREAK_MAX_ERR_DEG,
        "normal_shape_mode": rep["normal"]["same_shape"] and rep["modes"][2] == rep["modes"][3],
        "normal_unit": abs(rep["normal"]["length_min"] - 1) < 0.02 and abs(rep["normal"]["length_max"] - 1) < 0.02,
        "normal_flat_off_islands": rep["normal"]["far_flat_share_v2"] == 1.0,
        "crest_local_min_most": rep["ridge_vs_centre"]["v2_crest_local_min_count"] >= 0.9 * rep["ridge_vs_centre"]["crest_tested"],
        "normal_gutter_not_worse": rep["normal"]["gutter_nonflat_v2"] <= rep["normal"]["gutter_nonflat_live"]
        and rep["normal"]["gutter_max_xy_v2"] <= 1.25 * rep["normal"]["gutter_max_xy_live"]}
    rep["checks"] = checks
    json.dump(rep, open(OUT + "/gv2_validate_report.json", "w"), indent=1)
    summ = {k: v for k, v in rep.items() if k not in ("per_element",)}
    print(json.dumps(summ, indent=1))
    ok = all(checks.values())
    print("GV2_VALIDATE_" + ("PASS" if ok else "FAIL"), [k for k, v in checks.items() if not v])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
