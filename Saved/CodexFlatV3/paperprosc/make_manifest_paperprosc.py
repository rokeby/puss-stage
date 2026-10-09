"""Reproducibly generate the paper-proscenium thick5 RZIMPORT manifest and adapters.

Offline only.  The rebuilt Build/ may be read from the active E:\\PussStage tree while every output is written to
this worktree.  Modes and confirms:

  DRY    / "DRY PAPERPROSC MANIFEST"    - build and validate payloads in memory, write nothing
  APPLY  / "APPLY PAPERPROSC MANIFEST"  - backup existing outputs, record, write, hash-read-back
  REVERT / "REVERT PAPERPROSC MANIFEST" - restore one named APPLY record; displaced outputs remain in its backup

No Unreal package is loaded or saved.  The combined Blender edge probe is an explicit input and must be regenerated
from the same three FBXs before APPLY.
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
import shutil
from pathlib import Path


MARK = "PAPERPROSC_MANIFEST"
MANIFEST_REL = "DerivedAssets/StageFront_PaperProscenium/IMPORT_MANIFEST_PaperProsc.json"
PROBE_REL = "Saved/CodexFlatV3/paperprosc/edge_probe.json"
HERE_REL = "Saved/CodexFlatV3/paperprosc"
SLOTS = ["Front", "Flap", "Timber", "Edge"]
PARENTS = {
    "Front": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front",
    "Flap": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap",
}
AGED_NAMES = [
    "T_FlatV3_AgedPlywood_NormalDX.png",
    "T_FlatV3_AgedPlywood_Roughness.png",
    "T_FlatV3_AgedPlywood_Stencil_Color.png",
    "T_FlatV3_AgedSoftwood_Color.png",
    "T_FlatV3_AgedSoftwood_NormalDX.png",
    "T_FlatV3_AgedSoftwood_Roughness.png",
    "T_FlatV3_AgedSteel_Color.png",
]
PIECES = (
    {
        "source": "PaperProsc_Side_L", "owner": "PRO_side_L", "asset": "SM_FlatV3_PRO_side_L_t5j",
        "side": "L", "mount": "wing", "height_cm": 1080.0, "pick_n": 1,
        "build_json": "PaperProsc_Side_L_L_build.json", "location_cm": [-60.0, -1231.0, 0.0],
    },
    {
        "source": "PaperProsc_Side_R", "owner": "PRO_side_R", "asset": "SM_FlatV3_PRO_side_R_t5j",
        "side": "R", "mount": "wing", "height_cm": 1080.0, "pick_n": 2,
        "build_json": "PaperProsc_Side_R_R_build.json", "location_cm": [-60.0, 1198.0, 0.0],
    },
    {
        "source": "PaperProsc_Valance_C", "owner": "PRO_valance_C", "asset": "SM_FlatV3_PRO_valance_C_t5j",
        "side": "L", "mount": "top-border", "height_cm": 400.0, "pick_n": 3,
        "build_json": "PaperProsc_Valance_C_L_build.json", "location_cm": [-45.0, 0.0, 930.0],
    },
)


class ManifestError(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise ManifestError(reason)


def norm_rel(value):
    return str(value).replace("\\", "/").lstrip("/")


def absolute(root, rel):
    return Path(root) / Path(norm_rel(rel))


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def piece_paths(piece):
    folder = "DerivedAssets/StageFront_PaperProscenium/Build/%s" % piece["source"]
    return {
        "folder": folder,
        "fbx": "%s/SM_FlatV3_%s.fbx" % (folder, piece["source"]),
        "build": "%s/%s" % (folder, piece["build_json"]),
        "validation": "%s/validation.json" % folder,
        "socket": "%s/sockets_SM_FlatV3_%s.json" % (folder, piece["source"]),
        "source_jpg": "%s/stage1_colour_key_art.png" % folder,
        "skin_manifest": "%s/skin/%s_skin_manifest.json" % (folder, piece["source"]),
        "source_mi": "%s/skin/%s_mi_params.json" % (folder, piece["source"]),
        "SkinColor": "%s/skin/T_%s_SkinColor.png" % (folder, piece["source"]),
        "SkinMask": "%s/skin/T_%s_SkinMask.png" % (folder, piece["source"]),
        "SkinNormal": "%s/skin/T_%s_SkinNormal.png" % (folder, piece["source"]),
        "aged": ["%s/aged/%s" % (folder, name) for name in AGED_NAMES],
    }


def find_probe_row(probe, fbx_rel):
    suffix = norm_rel(fbx_rel).lower()
    hits = [row for row in probe if norm_rel(row.get("fbx", "")).lower().endswith(suffix)]
    require(len(hits) == 1, "EDGE_PROBE_ROW_COUNT|%s|%d" % (fbx_rel, len(hits)))
    require(not hits[0].get("error"), "EDGE_PROBE_IMPORT_ERROR|%s|%s" % (fbx_rel, hits[0].get("error")))
    return hits[0]


def edge_gate_errors(row):
    errors = []
    objects = row.get("objects") or {}
    if len(objects) != 2:
        errors.append("EDGE_PROBE_LOD_COUNT_%d" % len(objects))
    for name, obj in sorted(objects.items()):
        slots = obj.get("slots") or {}
        edge, front = slots.get("Edge"), slots.get("Front")
        if edge is None:
            errors.append("%s_NO_EDGE" % name)
            continue
        if abs(float(edge["x_min"]) + 15.0) > 0.05 or abs(float(edge["x_max"]) + 10.0) > 0.05:
            errors.append("%s_EDGE_X_%.3f_%.3f_NOT_-15_-10" % (name, edge["x_min"], edge["x_max"]))
        if int(edge.get("x_facing", -1)) != 0:
            errors.append("%s_EDGE_HAS_X_FACING_%s" % (name, edge.get("x_facing")))
        inward = obj.get("edge_inward_area_fraction")
        if inward is None or float(inward) > 1e-6:
            errors.append("%s_EDGE_INWARD_%s_GT_0" % (name, inward))
        if front is None or abs(float(front["x_min"]) + 15.0) > 0.05 or abs(float(front["x_max"]) + 15.0) > 0.05:
            errors.append("%s_FRONT_NOT_X_-15" % name)
    return errors


def source_gate_errors(piece, build, validation, sidecar, probe_row):
    errors = []
    profile = build.get("geometry_profile") or {}
    checks = validation.get("checks") or {}
    if profile.get("name") != "thick5" or abs(float(profile.get("board_thickness_cm", -1)) - 5.0) > 1e-6:
        errors.append("GEOMETRY_PROFILE_NOT_THICK5_5CM")
    if build.get("mount") != piece["mount"]:
        errors.append("MOUNT_MISMATCH")
    if not validation.get("pass"):
        errors.append("VALIDATION_NOT_PASS")
    measured = ((checks.get("board_thickness_profile") or {}).get("measured_edge_slot_m"))
    if measured is None or abs(float(measured) - 0.05) > 0.0001:
        errors.append("VALIDATED_BOARD_NOT_5CM")
    if (checks.get("material_slots_exact") or {}).get("value") != SLOTS:
        errors.append("SLOTS_NOT_EXACT")
    if (checks.get("fbx_lod_group") or {}).get("mechanism") != "FBX LodGroup NodeAttribute":
        errors.append("LOD_GROUP_NOT_FBX")
    if piece["mount"] == "wing":
        poles = (checks.get("baked_poles_lod0") or {}).get("details") or {}
        if not poles or not sidecar.get("baked_pole_geometry"):
            errors.append("WING_BAKED_POLES_MISSING")
        if str(validation.get("kind")) != "flat":
            errors.append("WING_VALIDATION_KIND_NOT_FLAT")
    else:
        if sidecar.get("sockets") or sidecar.get("baked_pole_geometry") is not None:
            errors.append("TOP_BORDER_HAS_POLE_CONTRACT")
        if str(validation.get("kind")) != "wave":
            errors.append("TOP_BORDER_VALIDATION_KIND_NOT_WAVE")
    errors.extend(edge_gate_errors(probe_row))
    return errors


def probe_summary(row):
    return {
        name: {
            "edge_x_cm": [obj["slots"]["Edge"]["x_min"], obj["slots"]["Edge"]["x_max"]],
            "front_x_cm": [obj["slots"]["Front"]["x_min"], obj["slots"]["Front"]["x_max"]],
            "edge_x_facing_polygons": obj["slots"]["Edge"].get("x_facing"),
            "edge_inward_area_fraction": obj.get("edge_inward_area_fraction"),
        }
        for name, obj in sorted((row.get("objects") or {}).items())
    }


def build_payloads(source_root, output_root, probe_rel=PROBE_REL):
    source_root, output_root = Path(source_root).resolve(), Path(output_root).resolve()
    probe_path = absolute(output_root, probe_rel)
    require(probe_path.is_file(), "EDGE_PROBE_MISSING|%s" % probe_path)
    probe = read_json(probe_path)
    payloads, entries, failures, edge_report = {}, [], [], {}
    for piece in PIECES:
        paths = piece_paths(piece)
        required = [paths[k] for k in ("fbx", "build", "validation", "socket", "source_jpg", "skin_manifest", "source_mi",
                                             "SkinColor", "SkinMask", "SkinNormal")] + paths["aged"]
        missing = [rel for rel in required if not absolute(source_root, rel).is_file()]
        require(not missing, "SOURCE_MISSING|%s" % missing)
        build = read_json(absolute(source_root, paths["build"]))
        validation = read_json(absolute(source_root, paths["validation"]))
        source_sidecar = read_json(absolute(source_root, paths["socket"]))
        skin_manifest = read_json(absolute(source_root, paths["skin_manifest"]))
        source_mi = read_json(absolute(source_root, paths["source_mi"]))
        row = find_probe_row(probe, paths["fbx"])
        gate_errors = source_gate_errors(piece, build, validation, source_sidecar, row)
        edge_report[piece["owner"]] = probe_summary(row)

        item_dir = "%s/import_meta/%s" % (HERE_REL, piece["owner"])
        socket_rel = "%s/sockets_%s.json" % (item_dir, piece["asset"])
        report_rel = "%s/RZ_BUILD_REPORT.json" % item_dir
        mi_rel = "%s/stage1/%s/skin_v3/%s_mi_params.json" % (item_dir, piece["owner"], piece["owner"])

        socket_adapter = copy.deepcopy(source_sidecar)
        socket_adapter["asset"] = piece["asset"]
        socket_adapter["source_asset"] = source_sidecar.get("asset")
        socket_bytes = json_bytes(socket_adapter)
        payloads[socket_rel] = socket_bytes

        mi_adapter = copy.deepcopy(source_mi)
        mi_adapter["asset"] = piece["owner"]
        mi_adapter["source_asset"] = piece["source"]
        mi_adapter["parents"] = dict(PARENTS)
        payloads[mi_rel] = json_bytes(mi_adapter)

        report = {
            "schema_version": 2,
            "status": "PASS" if not gate_errors else "FAIL",
            "owner": piece["owner"],
            "fbx": paths["fbx"],
            "fbx_sha256": sha_file(absolute(source_root, paths["fbx"])),
            "source_build_report": paths["build"],
            "source_validation": paths["validation"],
            "edge_gate": {
                "pass": not edge_gate_errors(row), "probe": probe_rel,
                "expected": "Front x=-15 cm; Edge x=-15..-10 cm; no x-facing Edge polygons; inward area fraction 0",
                "measured": probe_summary(row),
            },
            "gate_errors": gate_errors,
        }
        payloads[report_rel] = json_bytes(report)

        aged = [{"path": rel, "sha256": sha_file(absolute(source_root, rel))} for rel in paths["aged"]]
        dims = validation["dimensions_m"]
        entry = {
            "asset": piece["asset"], "intended_passage": "PRO",
            "placement_note": "Hyper3D thick5 stage-frame transform: location %s cm, identity rotation, scale 1; optional KEEP_WORLD attach to Infinity Stage - Structure 01." % piece["location_cm"],
            "folder": "StageFront_PaperProscenium", "pick_n": piece["pick_n"], "side": piece["side"],
            "mount": piece["mount"], "height_cm": piece["height_cm"],
            "dimensions_m": {"height": piece["height_cm"] / 100.0, "width": float(dims[1]), "flat_depth": float(dims[0])},
            "handedness": ({"chosen": piece["side"], "rule": "validated Flat V3 %s wing; Interchange-reflected import extends from the backbone toward the stage opening" % piece["side"]}
                             if piece["mount"] == "wing" else {"rule": "centred top border; validated bounds symmetric about Y=0"}),
            "source_jpg": paths["source_jpg"], "source_jpg_sha256": sha_file(absolute(source_root, paths["source_jpg"])),
            "fbx": paths["fbx"], "fbx_sha256": report["fbx_sha256"],
            "socket_sidecar": socket_rel, "socket_sidecar_sha256": sha_bytes(socket_bytes),
            "variant": "t5j (direct validated thick5 Flat V3 build; no HF rebuild)", "t5j_fbx": paths["fbx"],
            "build_manifest": paths["build"], "validation": paths["validation"], "validation_pass": bool(validation.get("pass")),
            "aspect_sidecar": None,
            "textures": {
                "SkinColor": {"path": paths["SkinColor"], "sha256": sha_file(absolute(source_root, paths["SkinColor"])), "import": "sRGB"},
                "SkinMask": {"path": paths["SkinMask"], "sha256": sha_file(absolute(source_root, paths["SkinMask"])), "import": "TC_Masks, sRGB off"},
                "SkinNormal": {"path": paths["SkinNormal"], "sha256": sha_file(absolute(source_root, paths["SkinNormal"])), "import": "normal map (BC5)"},
            },
            "aged_textures": aged, "slots": list(SLOTS),
            "edge_slot_material": "M_Wing_CanvasEdge_Master_v3 (assign at import)",
            "edge_walls_outward": not edge_gate_errors(row),
            "edge_inward_area_fraction": {name: data["edge_inward_area_fraction"] for name, data in probe_summary(row).items()},
            "hf": {"status": report["status"], "frame_mode": "thick5", "gate_errors": list(gate_errors)},
            "gates": {
                "board_5cm": "VALIDATED_BOARD_NOT_5CM" not in gate_errors,
                "edge_uv1_metric": bool((validation.get("checks", {}).get("uv1_metres_all_slots") or {}).get("pass")),
                "four_slots_exact": "SLOTS_NOT_EXACT" not in gate_errors,
                "lod1": bool((validation.get("checks", {}).get("lod1_present") or {}).get("pass")),
                "reachouts_inside": bool((build.get("visibility") or {}).get("pass")),
                "socket_contract": bool((validation.get("checks", {}).get("socket_contract") or {}).get("pass")),
                "baked_poles": piece["mount"] != "wing" or "WING_BAKED_POLES_MISSING" not in gate_errors,
                "triangulated": bool((validation.get("checks", {}).get("triangulated_export") or {}).get("pass")),
                "validation_pass": bool(validation.get("pass")),
                "edge_probe_outward": not edge_gate_errors(row),
            },
            "proof_pass": not gate_errors,
            "flaps": {"pilot_flap_count": int((skin_manifest.get("peel") or {}).get("flap_count", 0)), "pass": True},
            "build_report": report_rel,
        }
        entries.append(entry)
        failures.extend("%s: %s" % (piece["asset"], error) for error in gate_errors)

    manifest = {
        "run": "PRO-PAPERPROSC-THICK5-V2", "unreal_imported": False,
        "note": "Generated from the rebuilt thick5 Build/ by make_manifest_paperprosc.py; no hand edits. Blender edge probe and all source validation gates are embedded. Nothing was imported into Unreal.",
        "edge_probe": {"path": probe_rel, "sha256": sha_file(absolute(output_root, probe_rel)), "pieces": edge_report},
        "meshes": entries, "failures": failures,
    }
    payloads[MANIFEST_REL] = json_bytes(manifest)
    plan = {
        "mark": MARK, "source_root": str(source_root), "output_root": str(output_root),
        "probe": probe_rel, "outputs": {rel: sha_bytes(data) for rel, data in sorted(payloads.items())},
        "gates_ok": not failures, "failures": failures,
    }
    plan["hash"] = canonical_hash({k: v for k, v in plan.items() if k not in ("source_root", "output_root")})
    plan["hash8"] = plan["hash"][:8]
    return payloads, plan


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(path) + ".tmp")
    with open(temporary, "wb") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def apply_payloads(output_root, payloads, plan, run):
    output_root = Path(output_root).resolve()
    backup = output_root / "Backups" / ("PrePaperProscManifest-" + run)
    record_path = output_root / HERE_REL / "manifest_records" / ("manifest_record_%s.json" % run)
    require(not backup.exists(), "BACKUP_EXISTS|%s" % backup)
    require(not record_path.exists(), "RECORD_EXISTS|%s" % record_path)
    backup.mkdir(parents=True)
    originals = {}
    for rel in sorted(payloads):
        target = absolute(output_root, rel)
        row = {"existed": target.is_file(), "sha256": sha_file(target) if target.is_file() else None}
        if target.is_file():
            copied = backup / "originals" / Path(rel)
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, copied)
            row["backup_rel"] = norm_rel(copied.relative_to(backup))
        originals[rel] = row
    record = {
        "schema_version": 1, "mode": "APPLY", "run": run, "plan_hash": plan["hash"], "plan": plan,
        "backup": str(backup), "originals": originals, "applied": False,
        "dirty_package_census": {"content": [], "maps": [], "basis": "offline generator; Unreal not imported"},
    }
    write_atomic(record_path, json_bytes(record))
    shutil.copy2(record_path, backup / "record_before_change.json")
    for rel, data in sorted(payloads.items()):
        write_atomic(absolute(output_root, rel), data)
    readback = {rel: sha_file(absolute(output_root, rel)) for rel in sorted(payloads)}
    require(readback == plan["outputs"], "OUTPUT_READBACK_MISMATCH")
    record.update({"applied": True, "readback": readback})
    write_atomic(record_path, json_bytes(record))
    print("PAPERPROSC_MANIFEST_APPLY_OK|run=%s|plan=%s|outputs=%d|gates_ok=%s|backup=%s" %
          (run, plan["hash8"], len(payloads), str(plan["gates_ok"]).lower(), backup))
    return record_path


def revert_record(output_root, record_file, run):
    output_root = Path(output_root).resolve()
    record_path = Path(record_file).resolve()
    record = read_json(record_path)
    require(record.get("applied") and record.get("mode") == "APPLY", "APPLY_RECORD_INVALID")
    backup = output_root / "Backups" / ("PrePaperProscManifestRevert-" + run)
    require(not backup.exists(), "REVERT_BACKUP_EXISTS|%s" % backup)
    backup.mkdir(parents=True)
    shutil.copy2(record_path, backup / "apply_record.json")
    original_backup = Path(record["backup"])
    for rel, row in sorted(record["originals"].items()):
        current = absolute(output_root, rel)
        if current.is_file():
            displaced = backup / "displaced_outputs" / Path(rel)
            displaced.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(current), str(displaced))
        if row["existed"]:
            source = original_backup / row["backup_rel"]
            require(source.is_file() and sha_file(source) == row["sha256"], "ORIGINAL_BACKUP_INVALID|%s" % rel)
            current.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, current)
    print("PAPERPROSC_MANIFEST_REVERT_OK|run=%s|apply_run=%s|outputs=%d|backup=%s" %
          (run, record["run"], len(record["originals"]), backup))


def default_project_root():
    return Path(__file__).resolve().parents[3]


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("DRY", "APPLY", "REVERT"))
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--source-root", default=str(default_project_root()))
    parser.add_argument("--output-root", default=str(default_project_root()))
    parser.add_argument("--probe", default=PROBE_REL)
    parser.add_argument("--run")
    parser.add_argument("--record")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    want = "%s PAPERPROSC MANIFEST" % args.mode
    require(args.confirm == want, "CONFIRM_MISMATCH|got=%r|want=%r" % (args.confirm, want))
    run = args.run or datetime.datetime.now().strftime("PPMAN-%Y%m%d-%H%M%S")
    if args.mode == "REVERT":
        require(args.record, "REVERT_RECORD_REQUIRED")
        revert_record(args.output_root, args.record, run)
        return 0
    payloads, plan = build_payloads(args.source_root, args.output_root, args.probe)
    if args.mode == "DRY":
        print("PAPERPROSC_MANIFEST_DRY_OK|run=%s|plan=%s|outputs=%d|gates_ok=%s|failures=%d" %
              (run, plan["hash8"], len(payloads), str(plan["gates_ok"]).lower(), len(plan["failures"])))
        for failure in plan["failures"]:
            print("  REFUSAL " + failure)
        return 0 if plan["gates_ok"] else 2
    require(plan["gates_ok"], "SOURCE_GATES_FAILED|%s" % plan["failures"])
    apply_payloads(args.output_root, payloads, plan, run)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ManifestError as exc:
        print("PAPERPROSC_MANIFEST_STOPPED|%s" % exc)
        raise SystemExit(2)
