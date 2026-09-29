"""File-side (no editor): from wing001_footprint_probe.json, rasterise each Wing 001
card's front section in UV space against its alpha, map every opaque texel to
world space through the mesh's own UV-to-vertex layout, and report where the
card is opaque near the floor: the world-Y intervals, per side, in bands of
height a curtain pile could reach. Run with the system Python (PIL + numpy)
after wing001_footprint_probe_readonly.py has written the probe.

Opaque means alpha >= 1/3 (UE's default opacity-mask clip). The UV convention is
UE's: v = 0 at the image top. If a card uses a different texture or clip in its
material, the probe's material dump will show it and this must be revisited.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "wing001_footprint_probe.json")
OUT = os.path.join(HERE, "wing001_footprint.json")
BANDS_CM = (30.0, 60.0, 100.0)
CLIP = 1.0 / 3.0
BIN_CM = 10.0
COLLIDER_TOP_CM = 200.0   # the curtain pile stays well under this at the wing line
COLLIDER_STEP_CM = 10.0


def pick_section(panel):
    for m in panel["materials"]:
        if m.get("slot_name") and "front" in m["slot_name"].lower() and m["slot"] < len(panel["sections"]):
            return panel["sections"][m["slot"]], m
    return panel["sections"][0], (panel["materials"][0] if panel["materials"] else {})


# When a texture's recorded import source isn't on this machine (the Mac-era
# /private/tmp paths) or the probe couldn't read the parameter, use the wing's
# delivered base image in the repo, by mesh name. Same pixels, same handedness.
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SOURCE_OVERRIDES = {
    "SM_SaltFormation_01_L_v2": os.path.join(ROOT, "DerivedAssets", "GeneratedWingsV2", "SaltFormation_01_L_v2",
                                             "Textures", "SaltFormation_01_L_v2.png"),
    "SM_R__1_roccoco": os.path.join(ROOT, "DerivedAssets", "WingMateriality", "SourceExports", "R__1_roccoco.png"),
}


def alpha_source(material, mesh=""):
    candidates = [t.get("source") for t in material.get("textures", [])]
    stem = mesh.rsplit("/", 1)[-1].split(".")[0]
    if stem in SOURCE_OVERRIDES:
        candidates.append(SOURCE_OVERRIDES[stem])
    for src in candidates:
        if src and os.path.isfile(src):
            img = Image.open(src)
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                return src, np.asarray(img.convert("RGBA"))[:, :, 3].astype(np.float32) / 255.0
    return None, None


def intervals(ys):
    if len(ys) == 0:
        return []
    bins = np.unique(np.floor(np.asarray(ys) / BIN_CM).astype(int))
    out, start, prev = [], bins[0], bins[0]
    for b in bins[1:]:
        if b != prev + 1:
            out.append([float(start * BIN_CM), float((prev + 1) * BIN_CM)])
            start = b
        prev = b
    out.append([float(start * BIN_CM), float((prev + 1) * BIN_CM)])
    return out


probe = json.load(open(PROBE, encoding="utf-8"))
report = {"cue": probe["cue"], "flip_image_horizontally": probe["flip_image_horizontally"], "clip": CLIP, "sides": []}
for panel in probe["panels"]:
    section, material = pick_section(panel)
    src, alpha = alpha_source(material, panel["mesh"])
    rec = {"side": panel["side"], "mesh": panel["mesh"], "material": material.get("material"),
           "slot_name": material.get("slot_name"), "alpha_source": src}
    if alpha is None:
        rec["error"] = "no source image with alpha on disk for this material; see the probe's texture dump"
        report["sides"].append(rec)
        continue
    h, w = alpha.shape
    verts = np.asarray(section["verts"], dtype=np.float64)
    uvs = np.asarray(section["uvs"], dtype=np.float64) * np.array([w, h])
    tris = np.asarray(section["tris"], dtype=np.int64).reshape(-1, 3)
    points = []
    for a, b, c in tris:
        pa, pb, pc = uvs[a], uvs[b], uvs[c]
        lo = np.floor(np.minimum(np.minimum(pa, pb), pc)).astype(int).clip(0, [w - 1, h - 1])
        hi = np.ceil(np.maximum(np.maximum(pa, pb), pc)).astype(int).clip(0, [w - 1, h - 1])
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1) + 0.5, np.arange(lo[1], hi[1] + 1) + 0.5)
        det = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
        if abs(det) < 1e-12:
            continue
        l1 = ((pb[1] - pc[1]) * (xs - pc[0]) + (pc[0] - pb[0]) * (ys - pc[1])) / det
        l2 = ((pc[1] - pa[1]) * (xs - pc[0]) + (pa[0] - pc[0]) * (ys - pc[1])) / det
        l3 = 1.0 - l1 - l2
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        px = np.floor(xs[inside]).astype(int)
        py = np.floor(ys[inside]).astype(int)
        opaque = alpha[py, px] >= CLIP
        if not opaque.any():
            continue
        wts = np.stack([l1[inside][opaque], l2[inside][opaque], l3[inside][opaque]], axis=1)
        points.append(wts @ np.stack([verts[a], verts[b], verts[c]]))
    pts = np.concatenate(points) if points else np.zeros((0, 3))
    floor_z = float(verts[:, 2].min())
    rec["card_world_bounds"] = [verts.min(axis=0).round(1).tolist(), verts.max(axis=0).round(1).tolist()]
    rec["image"] = [w, h]
    rec["opaque_texels"] = int(len(pts))
    rec["bands"] = {}
    for band in BANDS_CM:
        near = pts[pts[:, 2] <= floor_z + band]
        rec["bands"][f"z<={band:.0f}"] = {
            "x_range": [round(float(near[:, 0].min()), 1), round(float(near[:, 0].max()), 1)] if len(near) else None,
            "y_intervals": intervals(near[:, 1])}
    # Collider boxes that follow the painted silhouette: one per opaque Y
    # interval per 10 cm course of height, up to COLLIDER_TOP_CM, through the
    # card's full thickness (all sections), merged where a course repeats the
    # one below it. Transparent parts of the card get no box, so the cloth is
    # never held up by visible air.
    all_verts = np.concatenate([np.asarray(sec["verts"], dtype=np.float64) for sec in panel["sections"]])
    x0, x1 = float(all_verts[:, 0].min()), float(all_verts[:, 0].max())
    runs = []
    for z0 in np.arange(0.0, COLLIDER_TOP_CM, COLLIDER_STEP_CM):
        band = pts[(pts[:, 2] >= floor_z + z0) & (pts[:, 2] < floor_z + z0 + COLLIDER_STEP_CM)]
        ivs = intervals(band[:, 1]) if len(band) else []
        if runs and runs[-1]["y_intervals"] == ivs:
            runs[-1]["z1"] = float(z0 + COLLIDER_STEP_CM)
        else:
            runs.append({"z0": float(z0), "z1": float(z0 + COLLIDER_STEP_CM), "y_intervals": ivs})
    side = panel["side"].split(".")[-1].split(":")[0]
    rec["collider_boxes"] = [
        {"name": f"Wing 001 {side} card {i + 1}", "min_cm": [round(x0, 1), y0, round(floor_z + r["z0"], 1)],
         "max_cm": [round(x1, 1), y1, round(floor_z + r["z1"], 1)]}
        for i, (r, (y0, y1)) in enumerate((r, iv) for r in runs for iv in r["y_intervals"])]
    report["sides"].append(rec)

json.dump(report, open(OUT, "w"), indent=1)
for s in report["sides"]:
    print(s["side"], s.get("error") or {k: v["y_intervals"] for k, v in s["bands"].items()})
print("WING001_FOOTPRINT_ANALYZE_OK" if all("error" not in s for s in report["sides"]) else "WING001_FOOTPRINT_ANALYZE_INCOMPLETE",
      file=sys.stderr)
