"""Pure/offline contract for Job 131 stage-front import and placement."""
from __future__ import annotations

import hashlib
import json
import os


MARK = "STAGEFRONT3D"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MAP_RELATIVE = "InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
DEST = "/Game/Scenes/Props/StageFront3D"
MASTER_DEFAULT = DEST + "/Materials/M_StageFront_Baked_Master"
MI_DIR = DEST + "/Materials/Instances"
MESH_DIR = DEST + "/Meshes"
TEX_DIR = DEST + "/Textures"
FOLDER = "StageFront/3D"
TAG = "PussStage.StageFront3D"
PARENT_LABEL = "Infinity Stage - Structure 01"
SOURCE_REL = "DerivedAssets/StageFrontBuild/BakedStageFront"
CONFIRMS = {
    "IMPORT": "IMPORT STAGEFRONT3D",
    "MATERIAL": "MATERIAL STAGEFRONT3D",
    "REVERT": "REVERT STAGEFRONT3D",
    "APPLY": "APPLY STAGEFRONT3D",
    "PLACE_REVERT": "REVERT STAGEFRONT3D PLACE",
}

# These FBXs must contain one mesh object. Architecture files already exist. The
# three hero FBXs are deliberately named future requirements: raw Rodin GLBs do
# not contain the normalized/baked object-space geometry used for the texture bake.
PIECES = {
    "arch": {"fbx": "SM_StageFront_Arch.fbx", "mesh": "SM_StageFront_Arch",
             "bake": "StageFront_Arch", "instances": [("Stage Front Architecture", [0, 0, 0], [0, 0, 0])]},
    "wall": {"fbx": "SM_StageFront_Wall.fbx", "mesh": "SM_StageFront_Wall",
             "bake": "StageFront_Wall", "instances": [("Stage Front Wall", [0, 0, 0], [0, 0, 0])]},
    "gilt": {"fbx": "SM_StageFront_Gilt.fbx", "mesh": "SM_StageFront_Gilt",
             "bake": "StageFront_Gilt", "instances": [("Stage Front Gilt", [0, 0, 0], [0, 0, 0])]},
    "crest": {"fbx": "SM_StageFront_Crest.fbx", "mesh": "SM_StageFront_Crest",
              "bake": "Crest", "instances": [("Stage Front Crest", [-500.0, 0, 1260.0], [0, 0, 0])]},
    "column": {"fbx": "SM_StageFront_Column.fbx", "mesh": "SM_StageFront_Column",
               "bake": "Column", "instances": [
                   ("Stage Front Column L", [-405.0, -1432.4, 0], [0, 0, 0]),
                   ("Stage Front Column R", [-405.0, 1432.4, 0], [0, 0, 0])]},
    "cat": {"fbx": "SM_StageFront_CatCandelabra.fbx", "mesh": "SM_StageFront_CatCandelabra",
            "bake": "CatCandelabra", "instances": [
                ("Stage Front Cat Candelabra L", [-104.7, -1090.0, 0], [0, 0, 0]),
                ("Stage Front Cat Candelabra R", [-104.7, 1090.0, 0], [0, 0, 180.0])]},
}
MAP_KINDS = (
    ("BaseColor_Dusty", True, "TC_DEFAULT", "BaseColorDusty"),
    ("BaseColor_Clean", True, "TC_DEFAULT", "BaseColorClean"),
    ("Masks", False, "TC_MASKS", "Masks"),
    ("N", False, "TC_NORMALMAP", "Normal"),
    ("Roughness", False, "TC_MASKS", "Roughness"),
)


class PlanError(RuntimeError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def package_for(kind, piece=None, map_kind=None):
    row = PIECES[piece] if piece else None
    if kind == "mesh":
        return MESH_DIR + "/" + row["mesh"]
    if kind == "mi":
        return MI_DIR + "/MI_" + row["bake"]
    return TEX_DIR + "/T_%s_%s" % (row["bake"], map_kind)


def selectors():
    out = []
    for key, row in PIECES.items():
        out.append("mesh:" + key)
        out.extend("tex:%s:%s" % (key, m[0]) for m in MAP_KINDS)
    return tuple(out)


def build_plan(project, hash_sources=False):
    source_root = os.path.join(project, *SOURCE_REL.split("/"))
    imports, missing = [], []
    for key, row in PIECES.items():
        mesh_source = os.path.join(source_root, row["fbx"])
        mesh = {"selector": "mesh:" + key, "kind": "mesh", "piece": key,
                "source": mesh_source, "dest": package_for("mesh", key)}
        imports.append(mesh)
        if not os.path.isfile(mesh_source):
            missing.append(os.path.relpath(mesh_source, project).replace("\\", "/"))
        for map_kind, srgb, compression, parameter in MAP_KINDS:
            name = "T_%s_%s.png" % (row["bake"], map_kind)
            source = os.path.join(source_root, name)
            item = {"selector": "tex:%s:%s" % (key, map_kind), "kind": "texture", "piece": key,
                    "map_kind": map_kind, "source": source, "dest": package_for("texture", key, map_kind),
                    "srgb": srgb, "compression": compression, "parameter": parameter}
            imports.append(item)
            if not os.path.isfile(source):
                missing.append(os.path.relpath(source, project).replace("\\", "/"))
    hashes = ({os.path.relpath(x["source"], project).replace("\\", "/"): sha256(x["source"])
               for x in imports if os.path.isfile(x["source"])} if hash_sources else {})
    actors = []
    for key, row in PIECES.items():
        for index, (label, loc, rot) in enumerate(row["instances"]):
            actors.append({"piece": key, "index": index, "label": label,
                           "mesh": package_for("mesh", key), "material": package_for("mi", key),
                           "location_cm": loc, "rotation_rpy_deg": rot, "scale": [1, 1, 1],
                           "tags": [TAG, TAG + "." + key]})
    return {"source_root": source_root, "imports": imports, "missing": sorted(missing),
            "hashes": hashes, "actors": actors, "packages": sorted(x["dest"] for x in imports),
            "material_packages": sorted(package_for("mi", k) for k in PIECES)}


def find_import(plan, selector):
    hits = [row for row in plan["imports"] if row["selector"] == selector]
    if len(hits) != 1:
        raise PlanError("ASSET_ONE_REQUIRED|%s" % selector)
    return hits[0]


def validate_import_args(doc, record=None):
    mode = str(doc.get("mode", "DRY")).upper()
    if mode not in ("DRY", "IMPORT", "MATERIAL", "VERIFY", "REVERT"):
        raise PlanError("MODE")
    if mode in CONFIRMS and doc.get("confirm") != CONFIRMS[mode]:
        raise PlanError("CONFIRM|%s" % CONFIRMS[mode])
    cap = int(doc.get("max_texture_size", 4096))
    if cap < 1 or cap > 4096:
        raise PlanError("TEXTURE_CAP_MAX_4096")
    selector = doc.get("asset")
    if mode == "IMPORT" and (not isinstance(selector, str) or selector not in selectors()):
        raise PlanError("ASSET_ONE_REQUIRED")
    piece = doc.get("piece")
    if mode == "MATERIAL" and piece not in PIECES:
        raise PlanError("PIECE_ONE_REQUIRED")
    if mode in ("VERIFY", "REVERT") and not record:
        raise PlanError("RECORD_REQUIRED")
    return mode, {"asset": selector, "piece": piece, "max_texture_size": cap,
                  "master_path": str(doc.get("master_path") or MASTER_DEFAULT),
                  "dust_strength": float(doc.get("dust_strength", 1.0)),
                  "soot_strength": float(doc.get("soot_strength", 1.0)),
                  "peel_strength": float(doc.get("peel_strength", 1.0))}


def validate_place_args(doc, record=None):
    mode = str(doc.get("mode", "DRY")).upper()
    if mode not in ("DRY", "APPLY", "VERIFY", "REVERT"):
        raise PlanError("MODE")
    confirm = "DRY STAGEFRONT3D" if mode == "DRY" else (CONFIRMS["PLACE_REVERT"] if mode == "REVERT" else "%s STAGEFRONT3D" % mode)
    if doc.get("confirm") != confirm:
        raise PlanError("CONFIRM|" + confirm)
    if mode in ("VERIFY", "REVERT") and not record:
        raise PlanError("RECORD_REQUIRED")
    return mode, {"attach": bool(doc.get("attach", True)),
                  "parent_label": str(doc.get("parent_label", PARENT_LABEL))}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def existing_target_problems(targets, existing):
    return ["TARGET_EXISTS|" + p for p in targets if p in set(existing)]


def import_delta_problems(expected, actual):
    return [] if set(actual) == {expected} else ["IMPORT_DELTA|want=%s|got=%s" % (expected, sorted(actual))]
