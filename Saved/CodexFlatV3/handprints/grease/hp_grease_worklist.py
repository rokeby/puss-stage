"""OFFLINE: the material-instance worklist for the grease layer, derived ONLY from the pinned grease table.

  python hp_grease_worklist.py            writes hp_grease_mi_worklist.json (refuses to overwrite a different one)

One instance per table `material_instance` actually used (142): parent M_HP_S03_Grease, per-instance scalars
AtlasU0/V0/USize/VSize = the row's grease_uv_rect (element uv_rect + crop sub-rect, unflipped), FlipU, GreaseGain.
Every row that uses an instance must agree on those values (checked).  Batches of <= 20 are fixed here, so a
batch number names the same 20 assets on every run.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE.parent / "clamber" / "placement_S03_grease.json"
OUT = HERE / "hp_grease_mi_worklist.json"
BATCH = 20
ROOT = "/Game/Scenes/Scene3/HandPrints"
MASTER = ROOT + "/Materials/Grease/M_HP_S03_Grease"


def build(table_path: Path = TABLE) -> dict:
    raw = table_path.read_bytes()
    doc = json.loads(raw)
    if doc.get("schema") != "hp_grease_placement/1":
        raise SystemExit("HP_GREASE_WORKLIST_FAIL|SCHEMA")
    mi_dir = doc["material"]["mi_dir"]
    by = {}
    for r in doc["decals"]:
        v = {"AtlasU0": r["grease_uv_rect"][0], "AtlasV0": r["grease_uv_rect"][1],
             "AtlasUSize": r["grease_uv_rect"][2], "AtlasVSize": r["grease_uv_rect"][3],
             "FlipU": 1.0 if r["flip"] else 0.0, "GreaseGain": float(r["gain"])}
        name = r["material_instance"]
        if name in by and by[name]["scalars"] != v:
            raise SystemExit("HP_GREASE_WORKLIST_FAIL|INCONSISTENT|" + name)
        by[name] = {"name": name, "path": mi_dir + "/" + name, "element": r["element_id"], "crop": r["crop_name"],
                    "flip": r["flip"], "gain": r["gain"], "scalars": v}
    items = [by[k] for k in sorted(by)]
    for i, it in enumerate(items):
        it["batch"] = i // BATCH
    return {"schema": "hp_grease_mi_worklist/1", "placement": str(table_path.name),
            "placement_sha256": hashlib.sha256(raw).hexdigest(), "master": MASTER, "mi_dir": mi_dir,
            "batch_max": BATCH, "batches": (len(items) + BATCH - 1) // BATCH, "count": len(items),
            "master_scalar_defaults": {"GreaseRoughMin": doc["material"]["grease_rough_min"],
                                       "GreaseRoughRange": doc["material"]["grease_rough_range"],
                                       "NormalStrength": doc["material"]["normal_strength"]},
            "instances": items}


def dumps(doc) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")


if __name__ == "__main__":
    data = dumps(build())
    if OUT.exists() and OUT.read_bytes() != data:
        print("HP_GREASE_WORKLIST_FAIL|EXISTS_AND_DIFFERS|%s" % OUT, file=sys.stderr)
        raise SystemExit(2)
    OUT.write_bytes(data)
    print("HP_GREASE_WORKLIST_OK|count=%d|batches=%d|sha256=%s" % (json.loads(data)["count"], json.loads(data)["batches"],
                                                                hashlib.sha256(data).hexdigest()))
