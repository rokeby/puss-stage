"""Pure planning and validation for the P80 chandelier importer.

This module deliberately imports no ``unreal`` symbols so its refusal gates can
be exercised by the offline harness.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re


MARK = "CHANDELIER_IMPORT"
DEST = "/Game/Scenes/Props/Chandelier"
BODY_NAME = "SM_Chandelier_Iron3"
CHAIN_NAME = "SM_Chandelier_Iron3_Chain"
MASTER_NAME = "M_AgedMaskedMetal_CreateOnly"
MI_NAME = "MI_Chandelier_Iron3"

SOURCE_MESH_REL = os.path.join("DerivedAssets", "ChandelierBuild", "Output", "Iron3")
SOURCE_TEX_REL = os.path.join("DerivedAssets", "StageFrontBuild", "BakedStageFront")

TEXTURE_SPECS = (
    ("MasksTexture", "Masks", "T_Chandelier_Iron3_Masks", False, "TC_MASKS", "SAMPLERTYPE_MASKS"),
    ("NormalTexture", "_N", "T_Chandelier_Iron3_N", False, "TC_NORMALMAP", "SAMPLERTYPE_NORMAL"),
    ("RoughnessTexture", "Roughness", "T_Chandelier_Iron3_Roughness", False, "TC_GRAYSCALE", "SAMPLERTYPE_LINEAR_GRAYSCALE"),
    ("BaseColorDusty", "BaseColor_Dusty", "T_Chandelier_Iron3_BaseColor_Dusty", True, "TC_DEFAULT", "SAMPLERTYPE_COLOR"),
    ("BaseColorClean", "BaseColor_Clean", "T_Chandelier_Iron3_BaseColor_Clean", True, "TC_DEFAULT", "SAMPLERTYPE_COLOR"),
)

IMPORT_ASSETS = (
    BODY_NAME,
    CHAIN_NAME,
    "T_Chandelier_Iron3_Masks",
    "T_Chandelier_Iron3_N",
    "T_Chandelier_Iron3_Roughness",
    "T_Chandelier_Iron3_BaseColor_Dusty",
    "T_Chandelier_Iron3_BaseColor_Clean",
)

TEXTURE_PARAMS = tuple(row[0] for row in TEXTURE_SPECS)
SCALAR_PARAMS = ("DustStrength", "SootStrength", "PeelStrength", "Metallic", "Specular")
SWITCH_PARAMS = ("UseClean",)
DEFAULTS = {
    "dust_strength": 1.0,
    "soot_strength": 1.0,
    "peel_strength": 1.0,
    "metallic": 0.85,
    "specular": 0.5,
    "use_clean": False,
}
CONFIRMS = {
    "IMPORT": "IMPORT CHANDELIER IRON3",
    "APPLY": "APPLY CHANDELIER IRON3",
    "REVERT": "REVERT CHANDELIER IRON3",
}


class PlanError(RuntimeError):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normal_convention() -> dict:
    """UE tangent-space normals and the supplied map are both DirectX (green/Y down)."""
    return {
        "source": "DirectX (green/Y down)",
        "unreal": "DirectX tangent-space (green/Y down)",
        "conversion": "none",
        "flip_green_channel": False,
        "compression": "TC_NORMALMAP",
    }


def texture_settings_problems(spec: dict, got: dict) -> list[str]:
    problems = []
    for key in ("srgb", "compression"):
        if got.get(key) != spec[key]:
            problems.append("%s=%r want %r" % (key, got.get(key), spec[key]))
    if spec["parameter"] == "NormalTexture" and got.get("flip_green_channel") is not False:
        problems.append("flip_green_channel=%r want False" % got.get("flip_green_channel"))
    return problems


def socket_problems(names: list[str]) -> list[str]:
    names = [str(n) for n in names]
    # [meas CHI-20261009-153452] UE strips the SOCKET_ prefix on FBX import
    candles = [n for n in names if re.fullmatch(r"(?:SOCKET_)?Candle_\d+", n)]
    problems = []
    if len(names) != len(set(names)):
        problems.append("DUPLICATE_SOCKET_NAMES")
    if len(candles) != 44:
        problems.append("CANDLE_SOCKET_COUNT=%d want 44" % len(candles))
    if names.count("ChainAttach") != 1:
        problems.append("CHAIN_ATTACH_COUNT=%d want 1" % names.count("ChainAttach"))
    foreign = sorted(n for n in names if n != "ChainAttach" and n not in candles)
    if foreign:
        problems.append("FOREIGN_SOCKETS=%s" % foreign)
    return problems


def chain_manifest_problems(doc: dict) -> list[str]:
    problems = []
    if doc.get("schema") != "chandelier_chain_v1":
        problems.append("SCHEMA")
    if doc.get("units") != "cm":
        problems.append("UNITS")
    links = doc.get("links")
    if not isinstance(links, list) or not links:
        problems.append("LINKS")
        links = []
    if doc.get("count") != len(links):
        problems.append("COUNT")
    if not isinstance(doc.get("length_cm"), (int, float)) or doc.get("length_cm", 0) <= 0:
        problems.append("LENGTH")
    body = doc.get("body")
    if not isinstance(body, dict) or not _vec3(body.get("attach_cm")):
        problems.append("BODY_ATTACH")
    for i, row in enumerate(links):
        if row.get("index") != i or not _vec3(row.get("pivot_cm")) or not isinstance(row.get("length_cm"), (int, float)):
            problems.append("LINK_%d" % i)
    return problems


def _vec3(value) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value)


def texture_specs(project: str) -> list[dict]:
    root = os.path.join(project, SOURCE_TEX_REL)
    rows = []
    for parameter, token, dest_name, srgb, compression, sampler in TEXTURE_SPECS:
        matches = []
        if os.path.isdir(root):
            for p in glob.glob(os.path.join(root, "*")):
                base = os.path.basename(p)
                if "Chandelier_Iron3" in base and token.lower() in base.lower() and os.path.isfile(p):
                    # `_N` must not accidentally match every occurrence of Iron3.
                    if token == "_N" and not re.search(r"(?:^|[_-])N(?:[_.-]|$)", base, re.I):
                        continue
                    matches.append(os.path.abspath(p))
        rows.append({"parameter": parameter, "token": token, "dest_name": dest_name,
                     "dest": DEST + "/" + dest_name, "matches": sorted(matches),
                     "srgb": srgb, "compression": compression, "sampler": sampler,
                     "flip_green_channel": False if parameter == "NormalTexture" else None})
    return rows


def build_plan(project: str) -> dict:
    project = os.path.abspath(project)
    mesh_root = os.path.join(project, SOURCE_MESH_REL)
    meshes = [
        {"name": BODY_NAME, "source": os.path.join(mesh_root, BODY_NAME + ".fbx"), "dest": DEST + "/" + BODY_NAME},
        {"name": CHAIN_NAME, "source": os.path.join(mesh_root, CHAIN_NAME + ".fbx"), "dest": DEST + "/" + CHAIN_NAME},
    ]
    manifest = os.path.join(mesh_root, "chandelier_Iron3_chain.json")
    textures = texture_specs(project)
    sources = [m["source"] for m in meshes] + [r["matches"][0] for r in textures if len(r["matches"]) == 1] + [manifest]
    missing = [m["source"] for m in meshes if not os.path.isfile(m["source"])]
    missing += ["%s: expected exactly one match, got %d" % (r["token"], len(r["matches"]))
                for r in textures if len(r["matches"]) != 1]
    if not os.path.isfile(manifest):
        missing.append(manifest)
    manifest_problems = []
    chain_doc = None
    if os.path.isfile(manifest):
        try:
            chain_doc = json.load(open(manifest, encoding="utf-8"))
            manifest_problems = chain_manifest_problems(chain_doc)
        except Exception as exc:  # noqa: BLE001 - becomes a deterministic refusal
            manifest_problems = ["JSON:%s" % exc]
    hashes = {os.path.relpath(p, project): sha256_file(p) for p in sources if os.path.isfile(p)}
    imported = [m["dest"] for m in meshes] + [r["dest"] for r in textures]
    return {"project": project, "meshes": meshes, "textures": textures, "chain_manifest": manifest,
            "chain": chain_doc, "missing": missing, "manifest_problems": manifest_problems,
            "hashes": hashes, "imported_packages": imported,
            "apply_packages": imported + [DEST + "/" + MASTER_NAME, DEST + "/" + MI_NAME],
            "normal_convention": normal_convention()}


def select_import_asset(plan: dict, value) -> dict:
    """Resolve exactly one public IMPORT selector to its mesh/texture plan row."""
    if not isinstance(value, str) or not value.strip():
        raise PlanError("ASSET_ONE_REQUIRED|allowed=%s" % list(IMPORT_ASSETS))
    name = value.strip()
    if "," in name or name not in IMPORT_ASSETS:
        raise PlanError("ASSET_UNKNOWN_OR_MANY|got=%r|allowed=%s" % (value, list(IMPORT_ASSETS)))
    rows = [dict(row, kind="mesh", selector=row["name"]) for row in plan["meshes"]]
    rows += [dict(row, kind="texture", selector=row["dest_name"]) for row in plan["textures"]]
    matches = [row for row in rows if row["selector"] == name]
    if len(matches) != 1:
        raise PlanError("ASSET_PLAN_COUNT|asset=%s|count=%d" % (name, len(matches)))
    return matches[0]


def master_contract_problems(info: dict) -> list[str]:
    problems = []
    for kind, want in (("textures", TEXTURE_PARAMS), ("scalars", SCALAR_PARAMS), ("switches", SWITCH_PARAMS)):
        missing = sorted(set(want) - set(info.get(kind, [])))
        if missing:
            problems.append("%s_missing=%s" % (kind, missing))
    samplers = info.get("samplers", {})
    wanted = {row[0]: row[5] for row in TEXTURE_SPECS}
    for name, sampler in wanted.items():
        got = str(samplers.get(name, ""))
        if sampler not in got:
            problems.append("sampler_%s=%r want %s" % (name, got, sampler))
    return problems


def overwrite_problems(targets: list[str], existing: set[str]) -> list[str]:
    """Create-only gate shared conceptually by IMPORT/APPLY and tested offline."""
    return ["TARGET_EXISTS|" + path for path in targets if path in existing]


def validate_args(args: dict, record_state: str | None = None) -> tuple[str, dict]:
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("DRY", "IMPORT", "MAT_CHECK", "APPLY", "REVERT"):
        raise PlanError("MODE|%s" % mode)
    if mode in CONFIRMS and args.get("confirm") != CONFIRMS[mode]:
        raise PlanError("CONFIRM|want %s" % CONFIRMS[mode])
    if mode == "IMPORT":
        asset = args.get("asset")
        if not isinstance(asset, str) or not asset.strip():
            raise PlanError("ASSET_ONE_REQUIRED|allowed=%s" % list(IMPORT_ASSETS))
        if "," in asset or asset.strip() not in IMPORT_ASSETS:
            raise PlanError("ASSET_UNKNOWN_OR_MANY|got=%r|allowed=%s" % (asset, list(IMPORT_ASSETS)))
        if record_state not in (None, "importing"):
            raise PlanError("IMPORT_STATE|state=%s" % record_state)
    if mode in ("MAT_CHECK", "APPLY") and record_state != "imported":
        raise PlanError("IMPORT_RECORD_REQUIRED")
    if mode == "REVERT" and record_state not in ("importing", "imported", "applied"):
        raise PlanError("REVERT_RECORD_REQUIRED")
    values = dict(DEFAULTS)
    values.update({k: args[k] for k in DEFAULTS if k in args})
    for key in ("dust_strength", "soot_strength", "peel_strength", "metallic", "specular"):
        try:
            values[key] = float(values[key])
        except (TypeError, ValueError):
            raise PlanError("VALUE|%s" % key)
        if not 0.0 <= values[key] <= 2.0:
            raise PlanError("RANGE|%s|0..2" % key)
    values["use_clean"] = bool(values["use_clean"])
    try:
        values["max_texture_size"] = int(args.get("max_texture_size", 4096))
    except (TypeError, ValueError):
        raise PlanError("VALUE|max_texture_size")
    if values["max_texture_size"] < 1 or values["max_texture_size"] > 16384:
        raise PlanError("RANGE|max_texture_size|1..16384")
    values["asset"] = args.get("asset")
    return mode, values
