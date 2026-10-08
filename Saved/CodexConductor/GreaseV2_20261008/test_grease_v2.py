"""Harness for grease v2 (OFFLINE).  Each test returns (passed, detail); NEGATIVE controls must make the shared test
functions FAIL (a verifier that cannot fail proves nothing).  Writes test_grease_v2_report.json here.

Positive
  P1 the real v2 atlas: R byte-identical to the live atlas (gv2_lib.r_identical), B identical, same size/mode
  P2 synthetic elongated smear blob (built by gv2_build.build, ridge profile): crest is a local minimum of G
  P3 synthetic blob: estimated direction within 5 deg of the truth, confidence high
  P4 synthetic blob: streak field orientation error < 10 deg (structure tensor)
  P5 synthetic blob: END edge zone glossier than SIDE zone
  P6 the real v2 outputs reproduce: re-running gv2_build in-process gives byte-identical G
  P7 the real PrintNormal v2 decodes to unit length (+-2 %) and uses the live encoding (RGB8 1024)
Negative (each must FAIL its test)
  N1 dome profile (thickest in the centre) on the same blob -> ridge test FAILS
  N2 streak field rotated 60 deg off the smear axis -> orientation test FAILS
  N3 one R byte altered in the v2 atlas -> r_identical FAILS
  N4 an isotropic (round) blob -> low confidence (no streaks), so the direction gate rejects it
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gv2_build as B  # noqa: E402
import gv2_lib as L  # noqa: E402

PXCM = 12.2
TRUE_THETA = math.radians(60.0)


def synth_blob(theta, n=512, a_cm=14.0, b_cm=4.0, streaks=True, seed=1):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    cx = cy = n / 2
    u = (xx - cx) * math.cos(theta) + (yy - cy) * math.sin(theta)
    v = -(xx - cx) * math.sin(theta) + (yy - cy) * math.cos(theta)
    a, b = a_cm * PXCM / 2, b_cm * PXCM / 2
    r = (u / a) ** 2 + (v / b) ** 2
    blob = np.clip(1.2 - r, 0, 1) ** 0.7
    if streaks:
        st = L.oriented_streaks((n, n), theta, 8, 14, np.random.default_rng(seed))
        blob = blob * np.clip(0.65 + 0.25 * st, 0, 1)
    alpha = ndi.gaussian_filter(blob, 1.0).astype(np.float32)
    el = [{"id": "SYN", "kind": "smear", "atlas_rect_px": [8, 8, n - 16, n - 16], "width_cm": (n - 16) / PXCM}]
    return alpha, el


def fields_2048(f):
    d = lambda a: B.down2(a.astype(np.float32))          # noqa: E731
    return {"rim": d(f["rimband"]) > 0.5, "centre": d(f["centre"]) > 0.5, "body": d(f["body"]) > 0.5,
            "dist": d(f["dist"]) / 2.0, "endness": d(f["endness"]), "streak": d(f["streak"])}


def g_of(f):
    breakup = np.full((f["gloss"].shape[0] // 2, f["gloss"].shape[1] // 2), 0.775, np.float32)
    return B.g_field(f, breakup)


def ridge_on(alpha, el, profile):
    f = B.build(alpha, el, profile=profile)
    G = g_of(f)
    s = fields_2048(f)
    pxmm = PXCM / 10 / 2
    dmm = s["dist"] / pxmm
    outer = (dmm >= -2.5) & (dmm <= -0.5)
    return L.ridge_test(G, s["rim"], s["centre"], outer), f, G, s


def main():
    res = {}
    live = np.asarray(Image.open(B.LIVE_ATLAS))
    v2 = np.asarray(Image.open(B.OUT + "/T_HP_S03_GreaseAtlas_v2.png"))
    res["P1_R_identical_real"] = (L.r_identical(live, v2) and np.array_equal(live[..., 2], v2[..., 2])
                                  and v2.dtype == np.uint8 and v2.shape == (2048, 2048, 3), {})
    alpha, el = synth_blob(TRUE_THETA)
    t, f, G, s = ridge_on(alpha, el, "ridge")
    res["P2_ridge_crest_local_min"] = (bool(t and t["crest_local_min"]), t)
    d = f["dirs"]["SYN"]
    err = L.axial_diff_deg(math.radians(d["theta_deg"]), TRUE_THETA)
    res["P3_direction_estimate"] = (err < 5.0 and not d["low_confidence"], {"err_deg": round(err, 2), "conf": d["conf"]})
    serr, scoh = L.orientation_error(s["streak"], s["body"], TRUE_THETA)
    res["P4_streaks_aligned"] = (serr < 10.0, {"err_deg": round(serr, 2), "coherence": round(scoh, 3)})
    es = __import__("gv2_validate").end_side(G, s["dist"] / (PXCM / 20), s["endness"], s["body"])
    res["P5_ends_glossier_than_sides"] = (bool(es and es["end_glossy_share"] > es["side_glossy_share"]), es)
    # P6 determinism on the real atlas
    meta = json.load(open(B.ATLAS_JSON))
    A = np.asarray(Image.open(B.BASE).getchannel("A")).astype(np.float32) / 255.0
    fr = np.load(os.path.join(HERE, "repro_fields.npz"))
    Gn = B.g_field(B.build(A, meta["elements"]), B.down2(fr["breakup"]))
    again = B.compose(live, Gn)
    res["P6_rebuild_byte_identical"] = (bool(np.array_equal(again, v2)), {})
    n = np.asarray(Image.open(B.OUT + "/T_HP_S03_PrintNormal_v2.png"))
    ln = np.linalg.norm(n / 255.0 * 2 - 1, axis=-1)
    res["P7_normal_unit_and_format"] = (n.shape == (1024, 1024, 3) and abs(ln.min() - 1) < 0.02 and abs(ln.max() - 1) < 0.02,
                                        {"len_min": round(float(ln.min()), 4), "len_max": round(float(ln.max()), 4)})
    # ---- negatives: the test must FAIL
    td, _, _, _ = ridge_on(alpha, el, "dome")
    res["N1_dome_fails_ridge_test"] = (bool(td) and not td["crest_local_min"], td)
    bad_streak = L.oriented_streaks(s["streak"].shape, TRUE_THETA + math.radians(60), 4, 7, np.random.default_rng(3))
    berr, _ = L.orientation_error(bad_streak, s["body"], TRUE_THETA)
    res["N2_misaligned_streaks_fail"] = (berr >= 10.0, {"err_deg": round(berr, 2)})
    tampered = v2.copy()
    tampered[1000, 1000, 0] ^= 1
    res["N3_altered_R_fails"] = (not L.r_identical(live, tampered), {})
    ra, rel = synth_blob(0.0, a_cm=8.0, b_cm=8.0, streaks=False)
    rd = B.estimate_direction(ra[8:-8, 8:-8], "print")
    res["N4_round_blob_low_confidence"] = (rd["low_confidence"], {"conf": rd["conf"]})
    out = {k: {"passed": bool(v[0]), "detail": v[1]} for k, v in res.items()}
    npass = sum(v["passed"] for v in out.values())
    json.dump({"passed": npass, "total": len(out), "tests": out}, open(os.path.join(HERE, "test_grease_v2_report.json"), "w"),
              indent=1, default=float)
    for k, v in out.items():
        print(("PASS " if v["passed"] else "FAIL ") + k, json.dumps(v["detail"], default=float)[:200])
    print("GV2_HARNESS %d/%d" % (npass, len(out)))
    sys.exit(0 if npass == len(out) else 1)


if __name__ == "__main__":
    main()
