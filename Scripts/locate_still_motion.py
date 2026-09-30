"""WHERE does a baked cloth move during its hold window? Offline and read-only (headless Blender 4.4 on the exported .abc).

    set ABC=...\\final3_settled.abc & set WIN_START=540 & set WIN_END=570 & blender -b --factory-startup --python Scripts/locate_still_motion.py

30 Sep, the Conductor: "If a bake fails its stillness target, do not re-bake blind. Report the number and what moved."
The bake records only the worst single-vertex move per frame. This reads the cache back and says WHERE the motion is:
  - per frame: the worst move and where it is (world metres; +y upstage, z up);
  - by height band (1 m) and by across-track band (2 m): the worst per-frame move, and the NET drift from the window's
    first to its last frame. A swing shows large per-frame moves with little net drift; a creep shows the reverse;
  - the 20 worst movers' positions.
Window is [WIN_START, WIN_END) in the bake's own frame numbers (the .abc keeps them). Writes <abc stem>_still_locate.json.
"""
import json
import os
from pathlib import Path

import bpy
import numpy as np

ABC = Path(os.environ["ABC"])
START, END = int(os.environ["WIN_START"]), int(os.environ["WIN_END"])


def coords(scene, obj, f):
    scene.frame_set(f)
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    n = len(ev.data.vertices)
    a = np.empty(n * 3, dtype=np.float32)
    ev.data.vertices.foreach_get("co", a)
    m = np.array(ev.matrix_world)
    return a.reshape(n, 3).astype(np.float64) @ m[:3, :3].T + m[:3, 3]


def bands(values, key, width, lo, hi):
    out = {}
    for b0 in np.arange(np.floor(lo / width) * width, hi, width):
        m = (key >= b0) & (key < b0 + width)
        if m.any():
            out[f"{b0:+.0f}..{b0 + width:+.0f}"] = round(float(values[m].max()), 2)
    return out


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30                                   # the bake's rate: the .abc times are frame / 30
    bpy.ops.wm.alembic_import(filepath=str(ABC))
    obj = next(o for o in scene.objects if o.type == "MESH")
    first = coords(scene, obj, START)
    prev, worst_move = first, np.zeros(len(first))
    per_frame = []
    for f in range(START + 1, END):
        co = coords(scene, obj, f)
        move = np.sqrt(((co - prev) ** 2).sum(axis=1)) * 1000.0
        i = int(move.argmax())
        per_frame.append({"frame": f, "max_mm": round(float(move[i]), 2), "at_m": [round(float(v), 2) for v in co[i]]})
        worst_move = np.maximum(worst_move, move)
        prev = co
    drift = np.sqrt(((prev - first) ** 2).sum(axis=1)) * 1000.0
    z, x = first[:, 2], first[:, 0]
    top = np.argsort(worst_move)[-20:][::-1]
    report = {"abc": str(ABC), "window": [START, END], "vertices": len(first),
              "window_max_mm": round(float(worst_move.max()), 2), "per_frame": per_frame,
              "by_height_worst_mm_per_frame": bands(worst_move, z, 1.0, z.min(), z.max() + 1e-6),
              "by_height_net_drift_mm": bands(drift, z, 1.0, z.min(), z.max() + 1e-6),
              "by_across_worst_mm_per_frame": bands(worst_move, x, 2.0, x.min(), x.max() + 1e-6),
              "by_across_net_drift_mm": bands(drift, x, 2.0, x.min(), x.max() + 1e-6),
              "worst_20": [{"mm": round(float(worst_move[i]), 2), "at_m": [round(float(v), 2) for v in first[i]]} for i in top]}
    out = ABC.with_name(ABC.stem + "_still_locate.json")
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"STILL_LOCATE|{out}|window_max_mm={report['window_max_mm']}")
    print("by height (worst mm/frame):", report["by_height_worst_mm_per_frame"])
    print("by height (net drift mm):  ", report["by_height_net_drift_mm"])
    print("by across (worst mm/frame):", report["by_across_worst_mm_per_frame"])


main()
