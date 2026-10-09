"""Read-only string audit for P02 assets; package bytes are never modified."""
from __future__ import annotations

import json
import datetime
import os
import re
import struct

CONTENT = "E:/PussStage/Content"
MESHES = ["FenceTarp_L", "FenceTarp_R", "FenceOpen_L", "FenceOpen_R", "RollerShutter_L", "RollerShutter_R"]


def strings(path):
    data = open(path, "rb").read(); values = [x.decode("ascii", "replace") for x in re.findall(rb"[ -~]{4,}", data)]
    values += [x.decode("utf-16le", "replace") for x in re.findall(rb"(?:[ -~]\x00){4,}", data)]
    keep = ("/Game/", "DerivedAssets", ".fbx", ".png", "MI_Billboard", "M_Wing_")
    return sorted(set(x for x in values if any(token in x for token in keep)))


def png_size(path):
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n": raise ValueError("NOT_PNG|" + path)
    return list(struct.unpack(">II", header[16:24]))


def audit():
    rows = []
    for name in MESHES:
        path = "%s/Scenes/Wings/FlatV3/Passage02/StaticMeshes/SM_FlatV3_P02_IND_%s.uasset" % (CONTENT, name)
        rows.append({"asset": "/Game/Scenes/Wings/FlatV3/Passage02/StaticMeshes/SM_FlatV3_P02_IND_" + name, "file": path, "bytes": os.path.getsize(path), "strings": strings(path)})
    for rel in ("Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front.uasset", "Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap.uasset",
                "Scenes/Wings/PaintedSurface/Billboard/Textures/T_BB_Colour.uasset", "Scenes/Wings/PaintedSurface/Billboard/Textures/T_BB_Mask.uasset", "Scenes/Wings/PaintedSurface/Billboard/Textures/T_BB_Normal.uasset"):
        path = CONTENT + "/" + rel; row = {"asset": "/Game/" + rel[:-7], "file": path, "bytes": os.path.getsize(path), "strings": strings(path)}
        if "/Textures/" in rel:
            png = "E:/PussStage/DerivedAssets/WingMateriality/BillboardPlaceholders/" + os.path.basename(rel).replace(".uasset", ".png")
            row["source_png"] = png; row["source_pixels"] = png_size(png)
        rows.append(row)
    return {"mode": "DRY", "run": "P02UASSET-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "tier": "binary-proven", "assets": rows, "marker": "P02_UASSET_STRING_AUDIT_OK"}


if __name__ == "__main__":
    result = audit(); out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p02_uasset_string_audit.json")
    with open(out, "w", encoding="utf-8") as handle: json.dump(result, handle, indent=2)
    print(result["marker"] + "|assets=" + str(len(result["assets"])))
