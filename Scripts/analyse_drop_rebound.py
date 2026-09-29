"""Where does the landing rebound live? Per-frame, per-region centre of mass from a baked Alembic (headless Blender).

    set ABC=Saved\\CodexSoftGoods\\DropBake\\final2_stage_v2.abc & set COLLIDERS=...|v2 & blender -b --python Scripts/analyse_drop_rebound.py

Regions (Blender metres; y = UE X / 100, + upstage): FRONT y < -0.9 (over the trough / lip housings), MID -0.9..0.5,
BACK > 0.5; and across the width LEFT x < -3, CENTRE, RIGHT x > 3. Per frame: COM overall and per region, the top,
and a CONTACT count (vertices within 3 cm of the floor or of any listed collider box / housing AABB). The rebound of
a region = its COM rise after its own collapse minimum. Writes <ABC stem>_rebound.json. Reads only.
"""
import json
import os
from pathlib import Path

import bpy

ROOT = Path(os.environ.get("PUSS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
ABC = ROOT / os.environ["ABC"]
F0, F1 = int(os.environ.get("F0", "150")), int(os.environ.get("F1", "260"))
COLLIDERS = os.environ.get("COLLIDERS", "")


def rebound(series):
    """Rise after the collapse minimum (the first local minimum after the COM drops below 60% of its start)."""
    start = series[0]
    down = next((i for i, v in enumerate(series) if v < 0.6 * start), None)
    if down is None:
        return 0.0, None
    j = down
    while j + 1 < len(series) and series[j + 1] <= series[j]:
        j += 1
    peak = max(series[j:j + 30])
    return round(peak - series[j], 4), j


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    bpy.ops.wm.alembic_import(filepath=str(ABC))
    cloth = next(o for o in scene.objects if o.type == "MESH")
    boxes = []
    if COLLIDERS:
        data = json.loads((ROOT / COLLIDERS.split("|")[0]).read_text(encoding="utf-8"))
        for b in data.get("boxes", []) + data.get("lamp_housings", []):
            lo = (b["min_cm"][1] / 100 - 0.03, b["min_cm"][0] / 100 - 0.03, b["min_cm"][2] / 100 - 0.03)
            hi = (b["max_cm"][1] / 100 + 0.03, b["max_cm"][0] / 100 + 0.03, b["max_cm"][2] / 100 + 0.03)
            if b["name"].startswith(("Stage floor", "House floor")):
                continue                                   # the floor itself is counted by height
            boxes.append((lo, hi))
    regions = {"front": lambda p: p.y < -0.9, "mid": lambda p: -0.9 <= p.y <= 0.5, "back": lambda p: p.y > 0.5,
               "left": lambda p: p.x < -3, "centre": lambda p: -3 <= p.x <= 3, "right": lambda p: p.x > 3}
    rows = []
    for f in range(F0, F1 + 1):
        scene.frame_set(f)
        ev = cloth.evaluated_get(bpy.context.evaluated_depsgraph_get())
        pts = [ev.matrix_world @ v.co for v in ev.data.vertices]
        row = {"f": f, "com": sum(p.z for p in pts) / len(pts), "top": max(p.z for p in pts)}
        for name, test in regions.items():
            sel = [p.z for p in pts if test(p)]
            row[name] = (sum(sel) / len(sel)) if sel else None
        floor = sum(1 for p in pts if abs(p.z) < 0.03 or abs(p.z + 1.2) < 0.03)
        near = sum(1 for p in pts if any(lo[0] < p.x < hi[0] and lo[1] < p.y < hi[1] and lo[2] < p.z < hi[2] for lo, hi in boxes))
        row["contact_floor"], row["contact_boxes"] = floor, near
        rows.append(row)
    out = {"abc": str(ABC.name), "frames": [F0, F1], "rows": rows}
    summary = {}
    for key in ("com", "front", "mid", "back", "left", "centre", "right"):
        series = [r[key] for r in rows if r[key] is not None]
        rise, j = rebound(series)
        summary[key] = {"rise_m": rise, "min_frame": (F0 + j) if j is not None else None}
    summary["peak_contact_boxes"] = max(r["contact_boxes"] for r in rows)
    summary["peak_contact_floor"] = max(r["contact_floor"] for r in rows)
    out["summary"] = summary
    (ABC.parent / f"{ABC.stem}_rebound.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("CURTAIN_REBOUND|" + json.dumps(summary))


main()
