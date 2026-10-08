"""Pure helpers shared by the P12 offline harness and the conductor-run editor tool."""
from __future__ import annotations

import hashlib
import json


SCHEMA = "hp_dense_placement/1"
LEVEL = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MODES = ("ASSET_DRY", "ASSET_APPLY", "ASSET_VERIFY", "DRY", "APPLY", "REVERT_DRY", "REVERT")


class DenseError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def confirm_text(mode):
    return {"ASSET_APPLY": "APPLY P12 DENSE MATERIALS", "APPLY": "APPLY P12 DENSE HANDPRINTS",
            "REVERT": "REVERT P12 DENSE HANDPRINTS"}.get(mode)


def check_confirm(mode, supplied):
    if mode not in MODES:
        raise DenseError("MODE|" + str(mode))
    expected = confirm_text(mode)
    if expected and supplied != expected:
        raise DenseError("CONFIRM_MISSING|" + expected)


def validate_table(doc):
    if doc.get("schema") != SCHEMA:
        raise DenseError("TABLE_SCHEMA")
    if doc.get("level") != LEVEL or doc.get("placeholder") is not False:
        raise DenseError("TABLE_LEVEL")
    band = doc["band"]
    alo, ahi = band["along_cm"]
    zlo, zhi = band["height_cm"]
    rows = doc.get("decals") or []
    if not rows:
        raise DenseError("TABLE_EMPTY")
    labels = set()
    for row in rows:
        if row.get("wall") != "R":
            raise DenseError("OUTSIDE_WALL|" + row.get("label", "?"))
        if not (alo <= row["along_extent_cm"][0] and row["along_extent_cm"][1] <= ahi):
            raise DenseError("OUTSIDE_ALONG_BAND|" + row.get("label", "?"))
        if not (zlo <= row["low_extent_cm"] and row["high_extent_cm"] <= zhi):
            raise DenseError("OUTSIDE_HEIGHT_BAND|" + row.get("label", "?"))
        if row["label"] in labels:
            raise DenseError("DUP_LABEL|" + row["label"])
        labels.add(row["label"])
    expected = round(doc["source_band_count"] * doc["density"])
    if len(rows) != expected:
        raise DenseError("DENSITY_COUNT|%d|%d" % (len(rows), expected))
    return True


def simulate_apply(existing, rows):
    """Small fake-world model: replace both legacy layers with sheen/core twins."""
    if not existing or any(x.get("tag") not in ("HP_S03G", "HP_S03T") for x in existing):
        raise DenseError("FOREIGN_OR_EMPTY_SOURCE")
    snap = json.loads(json.dumps(existing))
    made = []
    for row in rows:
        made.append({"tag": "HP_S03D", "label": row["label"], "material": row["material_instance"]})
        made.append({"tag": "HP_S03D_CORE", "label": row["core_label"], "material": row["dark_material_instance"]})
    return snap, made


def simulate_revert(snapshot, dense):
    if any(x.get("tag") not in ("HP_S03D", "HP_S03D_CORE") for x in dense):
        raise DenseError("FOREIGN_DENSE_LAYER")
    return json.loads(json.dumps(snapshot))
