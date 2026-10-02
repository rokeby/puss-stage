"""Import only P06 beat 1-3 assets; do not touch the Show or level."""
import ast
import json
import os
from pathlib import Path
import sys
import traceback
import types

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
import p02_import


def load_slot_a_library():
    path = os.path.join(os.path.dirname(HERE), "slot_a_import.py")
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
        isinstance(node.value.func, ast.Name) and node.value.func.id == "main")]
    module = types.ModuleType("flatv3_slot_a_p06_library")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)
    module.RUN = "P06_LIBRARY_ONLY"
    module.TARGETS = {"P06": "/Game/Scenes/Wings/FlatV3/Passage06"}
    module.EXPECTED_COUNTS = {"P06": 6}
    module.SOURCE_ROOTS = (c._project_path("DerivedAssets/FlatV3/Overnight/P06/flats"),)
    module.SAVED = HERE
    return module


def load_layout(config):
    with open(config["mapping_file"], encoding="utf-8") as handle:
        doc = json.load(handle)
    used = {row["left_family"] for row in doc["occurrences"]
            if row.get("action") == "swap"}
    families = doc["family_catalog"]
    for name in used:
        family = families.get(name)
        if family is None or family.get("pair_status") != "true_pair":
            raise RuntimeError("P06_IMPORT_FAMILY_NOT_TRUE_PAIR|" + str(name))
    return doc, {name: families[name] for name in sorted(used)}


def flat_inventory(config, slot_a, used_families):
    tools_dir = os.path.join(PROJECT, "Tools", "FlatV3")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import socket_contract

    wanted = {family[side] for family in used_families.values()
              if family["kind"] == "p06_flat"
              for side in ("left_asset", "right_asset")}
    root = c._project_path(config["import_flat_source_root"])
    rows = []
    contracts = {}
    for folder in sorted(path for path in Path(root).iterdir() if path.is_dir()):
        status_path = folder / "status.json"
        if not status_path.is_file():
            continue
        status = slot_a.load_json(str(status_path))
        mesh_name = str(status.get("asset_name", ""))
        if mesh_name not in wanted:
            continue
        if (status.get("passage") != "P06" or status.get("status") != "built" or
                not bool(status.get("validation_pass"))):
            raise RuntimeError("P06_FLAT_SOURCE_NOT_BUILT|asset=" + mesh_name)
        owner = str(status["asset_suffix"])
        validation_path = folder / "validation.json"
        validation = slot_a.load_json(str(validation_path))
        lod_gate = validation.get("checks", {}).get("fbx_lod_group", {})
        if (not bool(validation.get("pass")) or not bool(lod_gate.get("pass")) or
                lod_gate.get("mechanism") != "FBX LodGroup NodeAttribute"):
            raise RuntimeError("P06_FLAT_LODGROUP_GATE_FAIL|asset=" + mesh_name)
        manifest_path = Path(str(status.get("build_manifest", "")))
        if not manifest_path.is_file():
            matches = sorted(folder.glob("*_build.json"))
            if len(matches) != 1:
                raise RuntimeError("P06_FLAT_BUILD_MANIFEST_FAIL|asset=" + mesh_name)
            manifest_path = matches[0]
        manifest = slot_a.load_json(str(manifest_path))
        socket_path = folder / ("sockets_" + mesh_name + ".json")
        expected_socket = socket_contract.make_socket_payload(
            asset=mesh_name, side=str(status["build_side"]), mount=str(status["mount"]),
            height_cm=float(status["height_cm"]),
            width_m=float(manifest["dimensions_m"]["width"]),
            pole_positions_y_m=socket_contract.as_pole_list(manifest.get("pole_positions_y_m")))
        failures = socket_contract.validate_socket_payload(
            socket_contract.load_json(socket_path), expected_socket)
        if failures:
            raise RuntimeError("P06_FLAT_SOCKET_CONTRACT_FAIL|asset=%s|failures=%s" %
                               (mesh_name, json.dumps(failures)))
        sources = {
            "mesh": str(folder / (mesh_name + ".fbx")),
            "socket": str(socket_path),
            "validation": str(validation_path),
            "mi_params": str(folder / "skin" / (owner + "_mi_params.json")),
            "SkinColor": str(folder / "skin" / ("T_%s_SkinColor.png" % owner)),
            "SkinMask": str(folder / "skin" / ("T_%s_SkinMask.png" % owner)),
            "SkinNormal": str(folder / "skin" / ("T_%s_SkinNormal.png" % owner)),
            "AgedStencil": str(folder / "aged" / "T_FlatV3_AgedPlywood_Stencil_Color.png"),
        }
        for name in slot_a.COMMON_AGED:
            sources[name] = str(folder / "aged" / (name + ".png"))
        missing = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing:
            raise RuntimeError("P06_FLAT_FILES_MISSING|asset=%s|missing=%s" %
                               (mesh_name, json.dumps(missing)))
        target = config["destination_root"]
        destinations = {
            "mesh": target + "/StaticMeshes/" + mesh_name,
            "SkinColor": target + "/Textures/%s/T_%s_SkinColor" % (owner, owner),
            "SkinMask": target + "/Textures/%s/T_%s_SkinMask" % (owner, owner),
            "SkinNormal": target + "/Textures/%s/T_%s_SkinNormal" % (owner, owner),
            "AgedStencil": target + "/Textures/Aged/%s/T_%s_AgedPlywood_Stencil_Color" %
                            (owner, owner),
            "Front": target + "/Materials/Instances/MI_FlatV3_%s_Front" % owner,
            "Flap": target + "/Materials/Instances/MI_FlatV3_%s_Flap" % owner,
        }
        rows.append({"passage": "P06", "folder": str(folder), "owner": owner,
                     "mesh_name": mesh_name, "side": str(status["build_side"]),
                     "mount": str(status["mount"]),
                     "baked_poles": bool(status["baked_poles"]),
                     "sources": sources, "destinations": destinations,
                     "validation": validation})
        contracts[owner] = {"sidecar": str(socket_path), "failures": failures,
                            "fbx_lod_group": lod_gate}
    expected = int(config["import_flat_expected_count"])
    found = {row["mesh_name"] for row in rows}
    if len(rows) != expected or found != wanted:
        raise RuntimeError("P06_FLAT_SOURCE_COUNT_FAIL|expected=%d|actual=%d|missing=%s" %
                           (expected, len(rows), json.dumps(sorted(wanted - found))))
    return rows, contracts


def industrial_inventory(config, slot_a, used_families):
    wanted = {family[side] for family in used_families.values()
              if family["kind"] == "p02_industrial"
              for side in ("left_asset", "right_asset")}
    root = c._project_path(config["import_industrial_source_root"])
    validation = slot_a.load_json(os.path.join(root, "validation.json"))
    manifest = slot_a.load_json(os.path.join(root, "manifest.json"))
    if not validation.get("all_pass"):
        raise RuntimeError("P06_INDUSTRIAL_VALIDATION_FAIL")
    validation_by_asset = {row["asset"]: row for row in validation["assets"]}
    rows = []
    for item in manifest.get("assets", []):
        asset = str(item["asset"])
        if asset not in wanted:
            continue
        gate = validation_by_asset.get(asset)
        if gate is None or not bool(gate.get("pass")):
            raise RuntimeError("P06_INDUSTRIAL_ASSET_GATE_FAIL|asset=" + asset)
        sources = {"mesh": os.path.join(root, str(item["fbx"])),
                   "socket": os.path.join(root, "sockets_" + asset + ".json")}
        missing = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing:
            raise RuntimeError("P06_INDUSTRIAL_FILES_MISSING|asset=%s|missing=%s" %
                               (asset, json.dumps(missing)))
        rows.append({"owner": asset, "mesh_name": asset, "side": str(item["side"]),
                     "baked_poles": True, "sources": sources, "validation": gate})
    expected = int(config["import_industrial_expected_count"])
    found = {row["mesh_name"] for row in rows}
    if len(rows) != expected or found != wanted:
        raise RuntimeError("P06_INDUSTRIAL_SOURCE_COUNT_FAIL|expected=%d|actual=%d|missing=%s" %
                           (expected, len(rows), json.dumps(sorted(wanted - found))))
    return rows


def industrial_strategy(config, rows):
    p02_root = config["industrial_reuse_root"].rstrip("/")
    p06_root = config["destination_root"].rstrip("/")
    p02_paths = [p02_root + "/StaticMeshes/" + row["mesh_name"] for row in rows]
    p06_paths = [p06_root + "/StaticMeshes/" + row["mesh_name"] for row in rows]
    p02_state = [unreal.EditorAssetLibrary.does_asset_exist(path) for path in p02_paths]
    p06_state = [unreal.EditorAssetLibrary.does_asset_exist(path) for path in p06_paths]
    if all(p02_state):
        if any(p06_state):
            raise RuntimeError("P06_INDUSTRIAL_DUPLICATE_ROOTS")
        return "reuse_passage02", p02_root
    if any(p02_state):
        raise RuntimeError("P06_INDUSTRIAL_PARTIAL_P02_STATE")
    return "import_or_resume_passage06", p06_root


def main(config_path=None):
    config = c.load_config(config_path)
    run = config["import_run_id"]
    report = {"run": run, "mode": "p06_import", "status": "RUNNING"}
    final_status = "FAIL"
    saved_roots = []
    try:
        c.assert_context(config, clean=True)
        slot_a = load_slot_a_library()
        slot_a.RUN = run
        slot_a.SAVED = HERE
        _, used_families = load_layout(config)
        flats, contracts = flat_inventory(config, slot_a, used_families)
        industrial = industrial_inventory(config, slot_a, used_families)
        strategy, industrial_root = industrial_strategy(config, industrial)
        for row in industrial:
            row["destination"] = industrial_root + "/StaticMeshes/" + row["mesh_name"]

        common, common_hashes = slot_a.common_inventory(flats)
        existing_flats, existing_common = slot_a.destination_state(flats, common)
        planned = sorted(set(slot_a.all_planned_paths(flats, common) +
                             [row["destination"] for row in industrial]))
        report.update({"flat_source_count": len(flats),
                       "industrial_source_count": len(industrial),
                       "industrial_strategy": strategy,
                       "industrial_root": industrial_root,
                       "socket_contracts": contracts,
                       "common_hashes": common_hashes,
                       "planned_packages": planned})

        common_reports, common_paths, failures = slot_a.import_common_textures(
            common, existing_common)
        if failures:
            raise RuntimeError("P06_COMMON_IMPORT_FAIL|" + json.dumps(failures))
        new_flats = []
        flat_reports = {}
        for row in flats:
            owner = row["owner"]
            if owner in existing_flats:
                flat_reports[owner] = {"strategy": "verified_existing_saved",
                                       "readback": slot_a.verify_asset_fresh(row)}
            else:
                flat_reports[owner] = slot_a.import_asset(row)
                flat_reports[owner]["strategy"] = "imported_new"
                new_flats.append(row)

        new_industrial = []
        industrial_reports = {}
        for row in industrial:
            exists = unreal.EditorAssetLibrary.does_asset_exist(row["destination"])
            if exists:
                mesh = unreal.EditorAssetLibrary.load_asset(row["destination"])
                industrial_reports[row["owner"]] = {
                    "strategy": "verified_existing_saved",
                    "readback": p02_import.verify_industrial(mesh, row, slot_a)}
            elif strategy == "reuse_passage02":
                raise RuntimeError("P06_REUSE_ASSET_DISAPPEARED|" + row["mesh_name"])
            else:
                industrial_reports[row["owner"]] = {
                    "strategy": "imported_new",
                    "readback": p02_import.import_industrial(row, slot_a)}
                new_industrial.append(row)

        save_paths = sorted(common_paths +
                            [path for row in new_flats for path in slot_a.asset_paths(row)] +
                            [row["destination"] for row in new_industrial])
        if save_paths:
            slot_a.save_narrow(save_paths)
            saved_roots.extend(save_paths)
            slot_a.pilot.reload_new_packages(save_paths)
        fresh_flats = {row["owner"]: slot_a.verify_asset_fresh(row) for row in flats}
        fresh_industrial = {row["owner"]: p02_import.verify_industrial(
            unreal.EditorAssetLibrary.load_asset(row["destination"]), row, slot_a)
            for row in industrial}
        fresh_common = slot_a.verify_common_fresh(common, {"P06"})
        if c.census() != c.CLEAN:
            raise RuntimeError("P06_DIRTY_AFTER_FRESH_READBACK|census=" +
                               json.dumps(c.census(), sort_keys=True))
        report.update({"status": "PASS", "common_reports": common_reports,
                       "flat_reports": flat_reports,
                       "industrial_reports": industrial_reports,
                       "fresh_flats": fresh_flats,
                       "fresh_industrial": fresh_industrial,
                       "fresh_common": fresh_common,
                       "save_packages": save_paths,
                       "saved_roots": sorted(set(saved_roots)),
                       "dirty_after_fresh_readback": c.census()})
        path = c.write_json(config, "p06_import", report, run=run)
        unreal.log("FLATV3_P06_IMPORT_OK run=%s flat_assets=%d industrial_assets=%d "
                   "industrial_strategy=%s saved_count=%d saved_roots=%s report=%s" %
                   (run, len(flats), len(industrial), strategy, len(set(saved_roots)),
                    json.dumps(sorted(set(saved_roots)), separators=(",", ":")), path))
        final_status = "OK"
        return report
    except Exception as exc:
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": traceback.format_exc(), "census": c.census(),
                       "saved_roots": sorted(set(saved_roots))})
        c.write_json(config, "p06_import", report, run=run, failure=True)
        unreal.log_error("FLATV3_P06_IMPORT_FAIL run=%s reason=%s census=%s" %
                         (run, str(exc).replace("\n", "\\n"),
                          json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
        raise
    finally:
        unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
                   (run, final_status, len(set(saved_roots)),
                    json.dumps(sorted(set(saved_roots)), separators=(",", ":")),
                    json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))

