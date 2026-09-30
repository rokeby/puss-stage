"""Does the curtain MASK the portal opening from the stalls? Offline ray test on the baked cloth (headless Blender 4.4).

    set ABC=...\\final9_opening_a06.abc & set MASK_FRAME=479 & set OUT_ID=mask_final9 & blender -b --factory-startup --python Scripts/mask_raycast_stalls.py

30 Sep. The criterion (agreed with the Conductor): every ray from the stalls eye that passes through the PORTAL OPENING
must meet the drape (or the stage) before the first Wing pair. Rig's survey: header underside z 10.50 m, x -20..+20 cm;
posts' inner faces at y +-9.50 m; lip z 0..25 at x -150. The bake hangs the heading at 10.20 m, pleated -39..+41 cm
about the curtain line, so rays that clear the drape top at an UPSTAGE pleat and still pass under the header's back
face may see into the Passage (inferred before this test).

Method: the cloth at MASK_FRAME with its render modifiers (subdivision, 6 mm thickness) plus Rig's stage colliders.
A ray per STEP pixels of a 1920x1080 frame from the stalls camera (14 m downstage, 1.5 m up, +14 deg, 15 mm on a
23.76 mm filmback). A ray is UNMASKED when it crosses the portal slab (By -0.20..+0.20) inside the opening (|Bx| < 9.50,
0 < Bz < 10.50 at both faces) and hits nothing before By = FIRST_STATION_M (2.50, where the Passage begins). Writes
<OUT_ID>.json (counts, the unmasked rays' pixel rows/cols and heights at the curtain line) and <OUT_ID>_NOT_SHOW_FRAME.png
(unmasked pixels in green over the matte render). Blender coordinates: Bx = UE_Y/100, By = UE_X/100, Bz = UE_Z/100.
"""
import importlib.util
import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(os.environ.get("PUSS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
os.environ.setdefault("CURTAIN_QUADS_PER_BOLT", "15")
os.environ.setdefault("RENDER_STYLE", "matte")
os.environ.setdefault("COLLIDERS", "Docs/StageFrontColliders_2026-09-28.json|v2")
_spec = importlib.util.spec_from_file_location("curtain_drop", ROOT / "Scripts" / "bake_curtain_drop.py")
drop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drop)

ABC = os.environ["ABC"]
FRAME = int(os.environ.get("MASK_FRAME", "479"))
OUT_ID = os.environ.get("OUT_ID", Path(ABC).stem + "_mask")
OUT = Path(os.environ.get("OUT_DIR", str(ROOT / "Saved" / "CodexSoftGoods" / "DropBake")))
STEP = int(os.environ.get("MASK_STEP", "2"))
W, H, FILMBACK_W_MM, LENS_MM = 1920, 1080, 23.76, 15.0
EYE, PITCH = Vector((0.0, -14.0, 1.5)), math.radians(14.0)
SLAB = (-0.20, 0.20)
HALF_OPEN, HEADER_UNDERSIDE, FIRST_STATION_M = 9.50, 10.50, 2.50


def ray_dir(px, py):
    """Pinhole ray for pixel centre (px, py), y down; camera looks +By, pitched up by PITCH."""
    fx = LENS_MM / FILMBACK_W_MM * W
    u, v = (px + 0.5 - W / 2) / fx, -(py + 0.5 - H / 2) / fx
    d = Vector((u, 1.0, v))
    c, s = math.cos(PITCH), math.sin(PITCH)
    return Vector((d.x, d.y * c - d.z * s, d.y * s + d.z * c)).normalized()


def at_y(d, y):
    t = (y - EYE.y) / d.y
    return EYE + d * t, t


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    bpy.ops.wm.alembic_import(filepath=ABC)
    cloth = next(o for o in scene.objects if o.type == "MESH")
    drop.add_render_modifiers(cloth)
    drop.add_stage_colliders()
    scene.frame_set(FRAME)
    dg = bpy.context.evaluated_depsgraph_get()
    unmasked, through, rows = 0, 0, []
    for py in range(0, H, STEP):
        for px in range(0, W, STEP):
            d = ray_dir(px, py)
            if d.y <= 0:
                continue
            front, _ = at_y(d, SLAB[0])
            back, _ = at_y(d, SLAB[1])
            if not all(abs(p.x) < HALF_OPEN and 0.0 < p.z < HEADER_UNDERSIDE for p in (front, back)):
                continue
            through += 1
            _, t_station = at_y(d, FIRST_STATION_M)
            hit, loc, _, _, obj, _ = scene.ray_cast(dg, EYE, d, distance=t_station)
            if not hit:
                unmasked += 1
                line, _ = at_y(d, 0.0)
                rows.append([px, py, round(line.x, 3), round(line.z, 3)])
    report = {"abc": ABC, "frame": FRAME, "step_px": STEP, "rays_through_opening": through, "unmasked": unmasked,
              "unmasked_fraction": round(unmasked / through, 6) if through else None,
              "unmasked_z_at_curtain_line_m": [min((r[3] for r in rows), default=None), max((r[3] for r in rows), default=None)],
              "unmasked_pixel_rows": [min((r[1] for r in rows), default=None), max((r[1] for r in rows), default=None)],
              "samples": rows[:400]}
    # Where each unmasked ray crosses the curtain line: SIDE (beside the drape, the track-width leak), TOP (over the
    # heading), BOTTOM (under the hem), INTERIOR (through the body: a hole or a pleat gap).
    edge = float(os.environ.get("MASK_SIDE_X_M", "8.85"))
    cat = {"side": 0, "top": 0, "bottom": 0, "interior": 0}
    for r in rows:
        cat["side" if abs(r[2]) > edge else "top" if r[3] > 9.5 else "bottom" if r[3] < 1.0 else "interior"] += 1
    report["by_region"] = cat
    report["side_x_m"] = edge
    tops = [r for r in rows if abs(r[2]) <= edge and r[3] > 9.5]
    report["top_rows_px"] = [min((r[1] for r in tops), default=None), max((r[1] for r in tops), default=None)]
    report["top_z_at_line_m"] = [min((r[3] for r in tops), default=None), max((r[3] for r in tops), default=None)]
    report["top_notch_columns"] = len({r[0] // 8 for r in tops})
    report["top_samples"] = tops[:300]
    report["all_unmasked"] = [r + ["side" if abs(r[2]) > edge else "top" if r[3] > 9.5 else "bottom" if r[3] < 1.0
                                   else "interior"] for r in rows]
    (OUT / f"{OUT_ID}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"MASK_RAYCAST|through={through}|unmasked={unmasked}|by_region={report['by_region']}"
          f"|top_rows_px={report['top_rows_px']}|top_z={report['top_z_at_line_m']}"
          f"|top_cols8={report['top_notch_columns']}", flush=True)


main()
