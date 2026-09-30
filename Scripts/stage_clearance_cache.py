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
# The cloth's own collision margin (bake_curtain_drop: collision distance_min 0.01 m). Deeper than that is a collision
# failure, not resting contact. final13 measured 0.12 cm (one vertex, stage floor, frame 518) against v4, 30 Sep.
CONTACT_MAX_CM = float(os.environ.get("CLEAR_CONTACT_MAX_CM") or 1.0)
# CLEAR_PROBE_FOOTPRINT "x0,x1,y0,y1" (UE cm): also record the HIGHEST cloth point inside that footprint in any frame,
# e.g. the border's (45,50,-990,990): the lowest its bottom could go without the hang or the FALL touching it.
PROBE = [float(v) for v in os.environ["CLEAR_PROBE_FOOTPRINT"].split(",")] if os.environ.get("CLEAR_PROBE_FOOTPRINT") else None
NON_CONTACT = ("Post", "Header", "border", "Border")


def boxes():
    """Every stage box as (centre, axes, half-sizes) in UE cm. Plain boxes are axis-aligned; lamp housings use their
    exact ORIENTED box (bake_curtain_drop.ue_oriented_corners' convention: yaw about Z, then pitch, roll 0), because
    their AABB overstates contact depth (30 Sep: 13.6 cm into an AABB that the housing itself does not fill)."""
    import math
    path = COLLIDERS.split("|")[0]
    raw = (ROOT / path).read_bytes()
    spec = json.loads(raw)
    out = []
    for b in list(spec["boxes"]) + list(spec.get("lamp_housings", [])):
        o = b.get("oriented")
        if o:
            cy, sy = math.cos(math.radians(o["yaw_deg"])), math.sin(math.radians(o["yaw_deg"]))
            cp, sp = math.cos(math.radians(o["pitch_deg"])), math.sin(math.radians(o["pitch_deg"]))
            axes = np.array([[cp * cy, cp * sy, sp], [-sy, cy, 0.0], [-sp * cy, -sp * sy, cp]])
            centre, half = np.array(o["centre_cm"], float), np.array(o["size_cm"], float) / 2.0
        else:
            lo, hi = np.array(b["min_cm"], float), np.array(b["max_cm"], float)
            axes, centre, half = np.eye(3), (lo + hi) / 2.0, (hi - lo) / 2.0
        out.append({"name": b["name"], "contact": not any(k in b["name"] for k in NON_CONTACT),
                    "oriented": bool(o), "axes": axes, "centre": centre, "half": half})
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
    rows = {x["name"]: {"contact": x["contact"], "oriented": x["oriented"], "max_inside": 0, "max_depth_cm": 0.0, "frame": None} for x in bx}
    n_frames = 0
    probe = {"footprint_cm": PROBE, "max_z_cm": float("-inf"), "frame": None, "vertices": 0}
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
        ue = np.stack([co[:, 1], co[:, 0], co[:, 2]], axis=1) * 100.0      # Blender m -> UE cm (UE_X = By, UE_Y = Bx)
        n_frames += 1
        if PROBE:
            sel = (ue[:, 0] >= PROBE[0]) & (ue[:, 0] <= PROBE[1]) & (ue[:, 1] >= PROBE[2]) & (ue[:, 1] <= PROBE[3])
            if sel.any():
                zmax = float(ue[sel, 2].max())
                if zmax > probe["max_z_cm"]:
                    probe.update({"max_z_cm": round(zmax, 2), "frame": f, "vertices": int(sel.sum())})
        for x in bx:
            local = (ue - x["centre"]) @ x["axes"].T
            slack = x["half"] - np.abs(local)                               # > 0 on every axis = inside
            inside = np.all(slack > 0.0, axis=1)
            k = int(inside.sum())
            if not k:
                continue
            depth = float(slack[inside].min(axis=1).max())                  # the deepest vertex, to its nearest face
            r = rows[x["name"]]
            r["max_inside"] = max(r["max_inside"], k)
            if depth > r["max_depth_cm"]:
                r["max_depth_cm"], r["frame"] = round(depth, 2), f
    non_contact_hits = {n: r for n, r in rows.items() if not r["contact"] and r["max_inside"]}
    contact_worst = max(((n, r) for n, r in rows.items() if r["contact"]), key=lambda nr: nr[1]["max_depth_cm"],
                        default=(None, {"max_depth_cm": 0.0}))
    verdict = not non_contact_hits and contact_worst[1]["max_depth_cm"] <= CONTACT_MAX_CM
    report = {"abc": ABC, "frames": [a, b], "frames_checked": n_frames, "colliders": COLLIDERS,
              "colliders_sha256": stage_sha, "contact_max_cm": CONTACT_MAX_CM, "clear": verdict,
              "non_contact_hits": non_contact_hits,
              "contact_worst": {"box": contact_worst[0], **contact_worst[1]},
              "boxes": {n: r for n, r in rows.items() if r["max_inside"]},
              "probe": (probe if probe["frame"] is not None else {"footprint_cm": PROBE, "max_z_cm": None,
                                                                 "note": "no cloth ever inside the footprint"})
              if PROBE else None}
    (OUT / f"{OUT_ID}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"STAGE_CLEARANCE|clear={verdict}|frames={n_frames}|non_contact_hits={list(non_contact_hits)}"
          f"|contact_worst={report['contact_worst']}|probe={report['probe']}", flush=True)


main()
