"""Offline top-down P38 handprint preview from the pinned 8 Oct placement."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import p38_core as core
from p38_editor import write_topdown_png

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
ARGS = HERE / "p38_args.json"
SOURCE = PROJECT / "Saved/CodexFlatV3/handprints/clamber/placement_S03_grease.json"
PNG = HERE / "handprints_topdown_offline.png"
REPORT = HERE / "handprints_topdown_offline.json"


def wall_bounds(source, wall):
    rows = [r for r in source["decals"] if r["wall"] == wall]
    xs = [r["location"][0] for r in rows]; ys = [r["location"][1] for r in rows]; zs = [r["location"][2] for r in rows]
    return {"label": rows[0]["attach_actor_label"],
            "centre": [(min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2],
            "extent": [max(1.0,(max(xs)-min(xs))/2), max(1.0,(max(ys)-min(ys))/2), max(1.0,(max(zs)-min(zs))/2)]}


def build():
    cfg = json.loads(ARGS.read_text(encoding="utf-8"))["handprints"]
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    points = cfg["offline_camera_points_world_cm"]
    walls = [wall_bounds(source, "L"), wall_bounds(source, "R")]
    selection = core.select_camera_wall(points, walls, cfg["max_camera_wall_distance_cm"], cfg["min_wall_margin_cm"])
    tangent = core.unit((points[-1][0]-points[0][0], points[-1][1]-points[0][1], 0.0))
    rows = []
    for row in source["decals"]:
        rows.append({"label": row["label"], "wall_label": row["attach_actor_label"], "location": row["location"],
                     "rotation": [row["rotation"]["roll"],row["rotation"]["pitch"],row["rotation"]["yaw"]],
                     "scale": [1.0,1.0,1.0], "wall_tangent": tangent,
                     "material": "/Game/Scenes/Scene3/HandPrints/Materials/Grease/"+row["material_instance"],
                     "decal_size": row["decal_size"], "fade_screen_size": row["fade_screen_size"],
                     "sort_order": row["sort_order"], "twin_label": row["label"].replace("HP_S03G","HP_S03T",1)})
    plan = core.plan_handprint_additions(rows, selection["selected"], cfg["increase_fraction"], cfg["seed"],
                                        cfg["tangent_jitter_cm"], cfg["vertical_jitter_cm"])
    existing = [r for r in rows if r["wall_label"] == selection["selected"]]
    return cfg, walls, points, selection, plan, existing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    ns = parser.parse_args(argv)
    if (PNG.exists() or REPORT.exists()) and not ns.overwrite:
        raise SystemExit("P38_PREVIEW_FAIL|OUTPUT_EXISTS|use --overwrite")
    cfg, walls, points, selection, plan, existing = build()
    write_topdown_png(str(PNG), walls, points, existing, plan["additions"])
    report = {"schema": core.SCHEMA, "tier": "measured offline analytical preview; not an Unreal render",
              "source": str(SOURCE.relative_to(PROJECT)).replace(os.sep,"/"), "wall_selection": selection,
              "source_count": plan["source_count"], "increase_fraction": plan["fraction"],
              "target_additions": plan["target_additions"], "seed": plan["seed"],
              "plan_digest": plan["plan_digest"], "png": PNG.name}
    REPORT.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("P38_HANDPRINTS_PREVIEW_OK|wall=%s|current=%d|add=%d|fraction=%.3f|png=%s" %
          (selection["selected"],plan["source_count"],plan["target_additions"],plan["fraction"],PNG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
