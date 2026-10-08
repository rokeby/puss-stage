"""OFFLINE spacing plan for the t5o waves: layout (bands, pitches, clear gaps), slide-path clearance at every keyed
frame (keys recomputed with the v3 motion formula, old vs shifted mounts), sightlines (design_B heights, the v3 design's
own shot eyes), the ground-row lights vs the new piece envelopes, and a top-down diagram.
Run: D:/PussStageTools/FlatV3/venv/Scripts/python.exe Saved/CodexFlatV3/s3waves/s3waves_t5o_spacing.py
Out: Saved/CodexFlatV3/s3waves/spacing_plan_t5o.json + spacing_topdown_t5o.png   Marker S3T5O_SPACING_OK
"""
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
S3W = PROJECT / "Saved" / "CodexConductor" / "S3Waves"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


T = load("t5o_core_sp", HERE / "s3waves_t5o_core.py")
V3 = load("v3_core_sp", S3W / "s3_waves_v3_core.py")
STATE = {"fps": 24.0, "playback": [0, 6240], "strike": {"frame": 240}}   # motion record: first key 239 = strike-1 [decl]
SHOT_EYES = {"B04": (3000.0, 125.0), "B05": (2700.0, 145.0), "B06": (2880.0, 120.0), "B07": (2800.0, 125.0),
             "B09": (2100.0, 175.0), "B11": (2920.0, 110.0)}            # s3_waves_v3_design.py:131-134 [decl]


def rows_all():
    plan = json.loads((S3W / "build_plan_B.json").read_text(encoding="utf-8"))
    rep = json.loads((PROJECT / "DerivedAssets/FlatV3/Scene3/WavesV3_t5o/build_report_t5o.json").read_text("utf-8"))
    rec = json.loads((S3W / "s3_waves_v3_apply_record.json").read_text(encoding="utf-8"))
    return T.piece_rows(plan, rep, rec)


def sightlines(heights, xs):
    out, prev = [], None
    for lid in sorted(xs, key=lambda k: xs[k]):
        row = {"id": lid, "x": xs[lid], "shots": {}}
        for k, (ex, ez) in SHOT_EYES.items():
            ang = math.degrees(math.atan2(heights[lid] - ez, xs[lid] - ex))
            clear = None if prev is None else ang - math.degrees(math.atan2(heights[prev] - ez, xs[prev] - ex))
            row["shots"][k] = round(clear, 3) if clear is not None else None
        out.append(row)
        prev = lid
    return out


def main():
    rows = rows_all()
    layout = T.plan_layout(rows)
    mp = json.loads((S3W / "s3_waves_v3_motion_plan.json").read_text(encoding="utf-8"))
    p_old = V3.plan_motion(STATE, rows, mp)
    p_new = V3.plan_motion(STATE, T.shifted_rows(rows), mp)
    path = T.path_clearance(p_old, p_new, rows)
    # also the OLD layout with t5o meshes (what a mesh swap WITHOUT the shift would do)
    try:
        T.path_clearance(p_old, p_old, rows, new_x={r["suffix"]: r["mount_local"][0] for r in rows})
        old_t5o = "no interpenetration"
    except T.PlanError as exc:
        old_t5o = str(exc)[:300]
    design = json.loads((PROJECT / "DerivedAssets/FlatV3/Scene3/waves_v3/B/design_B.json").read_text("utf-8"))
    heights = {L["id"]: L["max_height_cm"] for L in design["layers"]}
    xs_old = {L["id"]: float(L["x"]) for L in design["layers"]}
    p1 = {r["layer"]: T.NEW_X[r["suffix"]] for r in rows if r["piece"] == "P1"}
    sl_old, sl_new = sightlines(heights, xs_old), sightlines(heights, p1)
    worst_old = min(v for r in sl_old for v in r["shots"].values() if v is not None)
    worst_new = min(v for r in sl_new for v in r["shots"].values() if v is not None)
    light = json.loads((S3W / "s3_waves_v3_light_record.json").read_text(encoding="utf-8"))
    rows_light = []
    for L in light["plan"]["lights"]:
        if L["kind"] != "ground_row":
            continue
        lx = L["location"][0]
        p = math.radians(L["rotation"][1])
        half_x = 0.5 * L["rect_cm"][1] * abs(math.sin(p))       # rect height along the pitched local Z [inf geometry]
        inside = [q["suffix"] for q in layout["pieces"] if q["extent_new"][0] - half_x <= lx <= q["extent_new"][1] + half_x]
        inside_old = [q["suffix"] for q in layout["pieces"]
                      if q["extent_old_live"][0] - half_x <= lx <= q["extent_old_live"][1] + half_x]
        rows_light.append({"label": L["label"], "x": lx, "pitch_deg": round(L["rotation"][1], 2),
                           "rect_half_extent_x_cm": round(half_x, 2), "shadows": L["shadows"],
                           "inside_piece_envelope_new": inside, "inside_piece_envelope_old": inside_old})
    rep = {"layout": layout, "path_clearance_new": path, "old_layout_with_t5o_meshes": old_t5o,
           "sightlines": {"old": sl_old, "new": sl_new, "worst_clearance_deg_old": worst_old,
                          "worst_clearance_deg_new": worst_new,
                          "method": "s3_waves_v3_design.sightline_table, layer x = P1 origin [prec]"},
           "ground_rows": rows_light,
           "tiers": {"bands": "[meas] s3_shore_field.notch_half on s3_shore_footprint.json",
                     "piece_depths": "[meas] t5o validator bounds (clean Blender re-import)",
                     "keys": "[inf] recomputed from the v3 formula; live keys are re-read by APPLY/DRY",
                     "layout": "[inf] proposal, Gary's call"}}
    (HERE / "spacing_plan_t5o.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    diagram(layout, rows_light, HERE / "spacing_topdown_t5o.png")
    gaps = [(g["a"][10:], g["b"][10:], g["clear_old_live"], g["clear_new"]) for g in layout["layer_gaps"]]
    print("S3T5O_SPACING_OK|gaps=%s|path_min_x=%s|sight_worst_old=%.3f|new=%.3f" % (
        gaps, path["min_x_clearance_yz_overlapping"], worst_old, worst_new))


def diagram(layout, lights, out):
    """Three panels (one per band), x across (5 px / cm), y down (0.12 px / cm).  Grey = old live (legacy) footprint,
    colour = new t5o footprint; band = pale strip; ground rows = yellow ticks."""
    sx, sy = 5.0, 0.12
    panels = []
    for band, (b0, b1) in layout["bands"].items():
        x0, x1 = b0 - 25, b1 + 25
        W, H = int((x1 - x0) * sx) + 40, int(2400 * sy) + 90
        img = np.full((H, W, 3), 250, np.uint8)
        X = lambda x: int(20 + (x - x0) * sx)
        Y = lambda y: int(60 + (y + 1200) * sy)
        cv2.rectangle(img, (X(b0), Y(-1150)), (X(b1), Y(1150)), (225, 240, 225), -1)
        cv2.putText(img, "%s flat band %.0f..%.0f (root-local x cm)" % (band, b0, b1), (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.putText(img, "grey = live now (1.8 cm)   colour = t5o new x (5 cm)   yellow = ground row light", (10, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 60), 1)
        cols = {"P1": (200, 90, 30), "P2": (40, 120, 220)}
        for p in layout["pieces"]:
            if p["band"] != band:
                continue
            y0, y1 = p["y_range"]
            e = p["extent_old_live"]
            cv2.rectangle(img, (X(e[0]), Y(y0)), (X(e[1]), Y(y1)), (170, 170, 170), -1)
        for p in layout["pieces"]:
            if p["band"] != band:
                continue
            y0, y1 = p["y_range"]
            e = p["extent_new"]
            cv2.rectangle(img, (X(e[0]), Y(y0)), (X(e[1]), Y(y1)), cols[p["piece"]], 2)
            cv2.putText(img, "%s %+.0f" % (p["suffix"][10:].replace("_", " "), p["dx"]), (X(e[0]) - 10, Y(y1) + 14 +
                        (12 if p["piece"] == "P2" else 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.36, cols[p["piece"]], 1)
        for L in lights:
            if b0 - 25 <= L["x"] <= b1 + 25:
                cv2.line(img, (X(L["x"]), Y(-950)), (X(L["x"]), Y(950)), (0, 200, 230), 1)
        for g in layout["layer_gaps"]:
            if layout["pieces"][[q["suffix"] for q in layout["pieces"]].index(g["a"])]["band"] == band:
                cv2.putText(img, "layer gap %.1f -> %.1f cm" % (g["clear_old_live"], g["clear_new"]), (10, H - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160), 1)
        panels.append(img)
    w = max(p.shape[1] for p in panels)
    panels = [cv2.copyMakeBorder(p, 0, 6, 0, w - p.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for p in panels]
    cv2.imwrite(str(out), np.vstack(panels))


if __name__ == "__main__":
    main()
