"""Offline-only set-D build, measurements, grease audit, and technical PNG previews.

Modes:
  DRY                         compute and print the report; write nothing.
  APPLY --confirm "APPLY S3 DUNES X2"
                              back up existing outputs, write the record first, then height-set JSON/report/PNGs.
  REVERT --confirm "REVERT S3 DUNES X2"
                              back up the current outputs, then restore the APPLY pre-state exactly.

This never imports Blender or Unreal.  The APPLY outputs are planning artefacts, not a rebuildable FBX: Gary's
hand-painted vertex-G wet patches on SM_S3_ShoreGround_B must first be harvested with
s3_shore_wet_paint_run.py in the editor (DRY only).
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
import shutil

import numpy as np
from PIL import Image, ImageDraw

import s3_shore_field as F

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GREASE = os.path.join(PROJECT, "Saved", "CodexFlatV3", "handprints", "clamber", "placement_S03_grease.json")
PREVIEW_DIR = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "previews", "sets")
HEIGHTMAP = os.path.join(PREVIEW_DIR, "D_heightmap_16bit.png")
RELIEF = os.path.join(PREVIEW_DIR, "D_relief_preview.png")
REPORT = os.path.join(HERE, "s3_shore_dunes_x2_report.json")
RECORD = os.path.join(HERE, "s3_shore_dunes_x2_record.json")
TARGETS = (F.HEIGHT_SETS_JSON, HEIGHTMAP, RELIEF, REPORT)
CONFIRMS = {"APPLY": "APPLY S3 DUNES X2", "REVERT": "REVERT S3 DUNES X2"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json(path):
    with open(path, "r", encoding="utf-8") as src:
        return json.load(src)


def grease_burial_report(grid, fp, placement=None, face_strip_cm=10.0, clearance_cm=20.0):
    """Count a placement as buried when set-D sand overlaps its rotated low extent.

    Decals project 10 cm into the room, so each sample is the maximum surface from the marble face through that
    strip.  `clearance_violations` additionally counts prints that survive but do not retain the specified gap.
    """
    placement = placement or _json(GREASE)
    decals = placement.get("decals") or []
    if len(decals) != 1034:
        raise RuntimeError("GREASE_COUNT|expected=1034|got=%d" % len(decals))
    yl = fp["walls"]["left_inner_face_y"]["value"]
    yr = fp["walls"]["right_inner_face_y"]["value"]
    strip = np.linspace(0.0, face_strip_cm, 5)
    rows = []
    partial = full = clearance_bad = 0
    by_wall = {"L": 0, "R": 0}
    for d in decals:
        wall = d.get("wall")
        if wall not in ("L", "R"):
            raise RuntimeError("GREASE_WALL|%s|%r" % (d.get("id"), wall))
        x = np.full(strip.shape, float(d["along_cm"]))
        y = yl + strip if wall == "L" else yr - strip
        sand = float(F.interp2(grid["xs"], grid["ys"], grid["h"], x, y).max())
        low, high = float(d["low_extent_cm"]), float(d["high_extent_cm"])
        is_partial = sand >= low
        is_full = sand >= high
        is_clearance = sand + clearance_cm > low
        partial += int(is_partial)
        full += int(is_full)
        clearance_bad += int(is_clearance)
        by_wall[wall] += int(is_partial)
        if is_partial:
            rows.append({"id": d["id"], "wall": wall, "along_cm": round(float(d["along_cm"]), 3),
                         "sand_h_cm": round(sand, 2), "low_extent_cm": round(low, 2),
                         "high_extent_cm": round(high, 2), "fully_buried": is_full})
    return {"placement_file": os.path.relpath(GREASE, PROJECT).replace("\\", "/"),
            "placement_sha256": sha256(GREASE), "placements": len(decals),
            "criterion": "buried when max set-D surface in 10 cm receiver strip >= rotated low extent",
            "partly_or_fully_buried": partial, "fully_buried": full,
            "clearance_violations_at_20cm": clearance_bad, "buried_by_wall": by_wall,
            "buried": rows}


def _set_d_payload(fp, grid, failures, checks):
    out = _json(F.HEIGHT_SETS_JSON)
    if set(out.get("sets", {})) not in ({"A", "B", "C"}, {"A", "B", "C", "D"}):
        raise RuntimeError("HEIGHT_SET_BASE|%r" % sorted(out.get("sets", {})))
    summary = F.height_set_summary(fp, F.with_set("D"), grid)
    summary["checks_failures"] = failures
    summary["realism"] = checks["realism"]
    summary["cameras_min_vertical_clearance_cm"] = min(r["vertical_clearance_cm"] for r in checks["cameras"])
    summary["grid_sha256"] = checks["grid"]["sha256"]
    out["sets"]["D"] = summary
    out["set_d_status"] = "offline planning only; wet-paint vertex G harvest required before Blender rebuild"
    return out, summary


def build():
    fp = F.load_footprint()
    p = F.with_set("D")
    grid = F.build_grid(fp, p)
    failures, checks = F.checks(fp, p, grid)
    payload, summary = _set_d_payload(fp, grid, failures, checks)
    burial = grease_burial_report(grid, fp)
    report = {"schema": "s3_shore_dunes_x2_report/1", "height_set": "D",
              "status": "OFFLINE_ONLY_NO_BLENDER_NO_UNREAL",
              "wet_paint_gate": "BLOCKED until editor DRY harvest of SM_S3_ShoreGround_B vertex colour G",
              "params": copy.deepcopy(p["height_sets"]["D"]), "summary": summary,
              "checks_failures": failures, "checks": checks, "grease": burial,
              "outputs": {"height_sets": os.path.relpath(F.HEIGHT_SETS_JSON, PROJECT).replace("\\", "/"),
                          "heightmap": os.path.relpath(HEIGHTMAP, PROJECT).replace("\\", "/"),
                          "relief": os.path.relpath(RELIEF, PROJECT).replace("\\", "/")}}
    return grid, payload, report


def heightmap_image(grid, max_cm):
    h = np.clip(grid["h"], 0.0, max_cm)
    a = np.rint(h / max_cm * 65535.0).astype(np.uint16).T[::-1]
    return Image.fromarray(a)


def relief_image(grid, max_cm):
    h = grid["h"]
    dx = grid["xs"][1] - grid["xs"][0]
    dy = grid["ys"][1] - grid["ys"][0]
    gx, gy = np.gradient(h, dx, dy)
    # Northwest light, 35 degree elevation.
    lx, ly, lz = -0.579, -0.579, 0.574
    nx, ny, nz = -gx, -gy, np.ones_like(h)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    shade = np.clip((nx * lx + ny * ly + nz * lz) / norm, -0.25, 1.0)
    t = np.clip(h / max_cm, 0.0, 1.0)
    # Wet charcoal floor -> ochre sand -> pale crest.
    stops = np.array([[38, 45, 43], [112, 83, 48], [194, 151, 88], [239, 218, 165]], dtype=float)
    q = t * (len(stops) - 1)
    i = np.minimum(q.astype(int), len(stops) - 2)
    f = (q - i)[..., None]
    rgb = stops[i] * (1.0 - f) + stops[i + 1] * f
    rgb *= (0.48 + 0.62 * ((shade + 0.25) / 1.25))[..., None]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2)[::-1]
    im = Image.fromarray(rgb, mode="RGB").resize((1606, 540), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 1605, 34), fill=(12, 14, 13))
    draw.text((12, 10), "S3 Shore set D — offline relief; x mouth 0 m → back 60 m; y ±10 m", fill=(238, 238, 228))
    return im


def _write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as dst:
        json.dump(value, dst, indent=1)
        dst.flush()
        os.fsync(dst.fileno())


def _backup(run, suffix):
    root = os.path.join(PROJECT, "Backups", "PreS3DunesX2-%s-%s" % (run, suffix))
    if os.path.exists(root):
        raise RuntimeError("BACKUP_EXISTS|" + root)
    os.makedirs(root)
    rows = []
    for path in TARGETS + (RECORD,):
        rel = os.path.relpath(path, PROJECT)
        row = {"path": rel.replace("\\", "/"), "existed": os.path.isfile(path)}
        if row["existed"]:
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(path, dst)
            row["sha256"] = sha256(path)
        rows.append(row)
    _write_json(os.path.join(root, "backup_manifest.json"), rows)
    return root, rows


def apply(run):
    grid, payload, report = build()
    if report["checks_failures"]:
        raise RuntimeError("SET_D_GATES|%s" % report["checks_failures"])
    backup, pre = _backup(run, "APPLY")
    record = {"schema": "s3_shore_dunes_x2_record/1", "run": run, "mode": "APPLY",
              "utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
              "backup": backup.replace("\\", "/"),
              "pre": pre, "targets": [os.path.relpath(p, PROJECT).replace("\\", "/") for p in TARGETS],
              "status": "PREPARED"}
    _write_json(RECORD, record)  # record exists before any target changes
    _write_json(F.HEIGHT_SETS_JSON, payload)
    _write_json(REPORT, report)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    max_cm = float(F.active_set(F.with_set("D"))["target_wall_max_cm"])
    heightmap_image(grid, max_cm).save(HEIGHTMAP)
    relief_image(grid, max_cm).save(RELIEF)
    record["status"] = "APPLIED"
    record["post"] = {os.path.relpath(p, PROJECT).replace("\\", "/"): sha256(p) for p in TARGETS}
    _write_json(RECORD, record)
    return report, backup


def revert(run):
    if not os.path.isfile(RECORD):
        raise RuntimeError("RECORD_MISSING")
    rec = _json(RECORD)
    if rec.get("status") != "APPLIED":
        raise RuntimeError("RECORD_STATUS|%r" % rec.get("status"))
    backup_now, _ = _backup(run, "REVERT")
    source = rec["backup"]
    for row in rec["pre"]:
        target = os.path.join(PROJECT, row["path"])
        prior = os.path.join(source, row["path"])
        if row["existed"]:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(prior, target)
            if sha256(target) != row["sha256"]:
                raise RuntimeError("RESTORE_HASH|" + row["path"])
        elif os.path.exists(target):
            os.remove(target)
    return {"restored_from": source, "current_backup": backup_now}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), default="DRY")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--run", default="S3DUNESX2-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S"))
    ns = ap.parse_args(argv)
    if ns.mode in CONFIRMS and ns.confirm != CONFIRMS[ns.mode]:
        raise RuntimeError("CONFIRM_MISSING|%s needs %r" % (ns.mode, CONFIRMS[ns.mode]))
    if ns.mode == "DRY":
        _grid, _payload, report = build()
        print(json.dumps({"summary": report["summary"], "grease": {k: v for k, v in report["grease"].items()
                         if k != "buried"}, "checks_failures": report["checks_failures"]}, indent=1))
        print("S3DUNESX2_DRY_OK|run=%s|buried=%d|print_line_cm=%.1f" %
              (ns.run, report["grease"]["partly_or_fully_buried"],
               report["summary"]["min_print_line_cm_above_floor_top"]))
    elif ns.mode == "APPLY":
        report, backup = apply(ns.run)
        print("S3DUNESX2_APPLY_OK|run=%s|buried=%d|print_line_cm=%.1f|backup=%s" %
              (ns.run, report["grease"]["partly_or_fully_buried"],
               report["summary"]["min_print_line_cm_above_floor_top"], backup.replace("\\", "/")))
    else:
        out = revert(ns.run)
        print("S3DUNESX2_REVERT_OK|run=%s|restored_from=%s|backup=%s" %
              (ns.run, out["restored_from"], out["current_backup"]))


if __name__ == "__main__":
    main()
