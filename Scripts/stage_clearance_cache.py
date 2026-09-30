"""STAGE CLEARANCE: does a baked cache intersect the stage AS BUILT? (30 Sep; the Conductor approved it as a gate.)

    set ABC=...\\final13_opening_a06_w188.abc & set COLLIDERS=Docs/StageFrontColliders_2026-09-28.json|v2 & set OUT_ID=clear_final13 & blender -b --factory-startup --python Scripts/stage_clearance_cache.py

Why: a cache knows only the colliders it was simulated against. final13 never knew Rig's border (its bake log: 18 boxes,
v3; the border is v4's 19th). A later stage edit (a border lowered, a post moved) is flagged by the stage hash only as
"the stage changed", not as "the cloth now intersects Portal border at frame N". This measures that.

For every frame of the cache (the Alembic's own range, or CLEAR_FRAMES "a-b"), the RAW simulated mesh (what Unreal draws;
no render subdivision or thickness), every vertex is tested against every stage box, in Blender metres:
Bx = UE_Y/100, By = UE_X/100, Bz = UE_Z/100 (the collider file's own convention).
  - CONTACT boxes: the ones the cloth may legitimately rest on or drape over, because it was simulated against them
    (floors, lip trough, fascia, returns, lamp housings). The maximum penetration depth, in cm, and its frame and box are
    RECORDED, and asserted at most CLEAR_CONTACT_MAX_CM. The assertion bounds a number that is recorded, so a change shows
    as a number moving, not as a pass against a guess (the Conductor's refinement).
  - NON-CONTACT boxes (Post, Header, border): ZERO vertices inside, in any frame.
Lamp housings are oriented boxes; their AABB is used, which is conservative (more contact depth, never less).
Writes <OUT_ID>.json (per box: max vertices inside, max depth cm, frame; the verdict; the stage's LF-normalised SHA-256)
and prints STAGE_CLEARANCE|... Offline and read-only.
"""
import hashlib
import json
import os
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(os.environ.get("PUSS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
ABC = os.environ["ABC"]
COLLIDERS = os.environ.get("COLLIDERS", "Docs/StageFrontColliders_2026-09-28.json|v2")
OUT_ID = os.environ.get("OUT_ID", Path(ABC).stem + "_clearance")
OUT = Path(os.environ.get("OUT_DIR", str(ROOT / "Saved" / "CodexSoftGoods" / "DropBake")))
CONTACT_MAX_CM = float(os.environ.get("CLEAR_CONTACT_MAX_CM") or 3.0)   # provisional until final13 is measured
NON_CONTACT = ("Post", "Header", "border", "Border")


def boxes():
    path = COLLIDERS.split("|")[0]
    raw = (ROOT / path).read_bytes()
    spec = json.loads(raw)
    out = []
    for b in list(spec["boxes"]) + list(spec.get("lamp_housings", [])):
        lo, hi = b["min_cm"], b["max_cm"]
        out.append({"name": b["name"], "contact": not any(k in b["name"] for k in NON_CONTACT),
                    "lo": np.array([lo[1], lo[0], lo[2]]) / 100.0, "hi": np.array([hi[1], hi[0], hi[2]]) / 100.0})
    return out, hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    bpy.ops.wm.alembic_import(filepath=ABC, set_frame_range=True)     # the scene range becomes the cache's own
    obj = next(o for o in scene.objects if o.type == "MESH")
    if os.environ.get("CLEAR_FRAMES"):
        a, b = (int(x) for x in os.environ["CLEAR_FRAMES"].split("-"))
    else:
        a, b = scene.frame_start, scene.frame_end
    bx, stage_sha = boxes()
    rows = {x["name"]: {"contact": x["contact"], "max_inside": 0, "max_depth_cm": 0.0, "frame": None} for x in bx}
    n_frames = 0
    for f in range(a, b + 1):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        me = obj.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        obj.evaluated_get(dg).to_mesh_clear()
        co = co.reshape(-1, 3)
        mw = np.array(obj.matrix_world)
        co = co @ mw[:3, :3].T + mw[:3, 3]
        n_frames += 1
        for x in bx:
            inside = np.all((co > x["lo"]) & (co < x["hi"]), axis=1)
            k = int(inside.sum())
            if not k:
                continue
            p = co[inside]
            depth = np.minimum(p - x["lo"], x["hi"] - p).min(axis=1).max() * 100.0   # deepest vertex, to its nearest face
            r = rows[x["name"]]
            if k > r["max_inside"]:
                r["max_inside"] = k
            if depth > r["max_depth_cm"]:
                r["max_depth_cm"], r["frame"] = round(float(depth), 2), f
    non_contact_hits = {n: r for n, r in rows.items() if not r["contact"] and r["max_inside"]}
    contact_worst = max(((n, r) for n, r in rows.items() if r["contact"]), key=lambda nr: nr[1]["max_depth_cm"],
                        default=(None, {"max_depth_cm": 0.0}))
    verdict = not non_contact_hits and contact_worst[1]["max_depth_cm"] <= CONTACT_MAX_CM
    report = {"abc": ABC, "frames": [a, b], "frames_checked": n_frames, "colliders": COLLIDERS,
              "colliders_sha256": stage_sha, "contact_max_cm": CONTACT_MAX_CM, "clear": verdict,
              "non_contact_hits": non_contact_hits,
              "contact_worst": {"box": contact_worst[0], **contact_worst[1]},
              "boxes": {n: r for n, r in rows.items() if r["max_inside"]}}
    (OUT / f"{OUT_ID}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"STAGE_CLEARANCE|clear={verdict}|frames={n_frames}|non_contact_hits={list(non_contact_hits)}"
          f"|contact_worst={report['contact_worst']}", flush=True)


main()
