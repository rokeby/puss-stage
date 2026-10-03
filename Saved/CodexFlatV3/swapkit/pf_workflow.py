"""Guarded Unreal phases for PF.  Invoked only through the purging entry scripts."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
import types

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pf_support as s
import common as c
import c3_compare as compare
import p05float_support as f
import verify as v


def load_pilot():
    path = os.path.join(os.path.dirname(HERE), "phase1_import.py")
    spec = importlib.util.spec_from_file_location("flatv3_pf_pilot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PILOT = load_pilot()


def load_slot_a_library(config):
    path = os.path.join(os.path.dirname(HERE), "slot_a_import.py")
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
        isinstance(node.value.func, ast.Name) and node.value.func.id == "main")]
    module = types.ModuleType("flatv3_pf_slot_a_library")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)
    module.RUN = "PF_LIBRARY_ONLY"
    # slot_a.common_inventory iterates TARGETS, so PF must narrow this before
    # asking it to gate shared aged sources.  Otherwise empty P01/P04 rows fail.
    module.TARGETS = {"P05": config["destination_root"]}
    module.EXPECTED_COUNTS = {"P05": config["expected_asset_count"]}
    module.SOURCE_ROOTS = (config["source_root"],)
    module.SAVED = os.path.dirname(HERE)
    return module


def load_build_report(config):
    with open(config["build_report"], encoding="utf-8") as handle:
        report = json.load(handle)
    assets = report.get("assets", [])
    if (not report.get("all_pass") or len(assets) != config["expected_asset_count"] or
            report.get("target_suffix") != config["target_suffix"] or
            abs(float(report.get("pole_extension_cm", -1)) - config["pole_extension_cm"]) > 0.001 or
            any(not row.get("pass") for row in assets)):
        raise RuntimeError("PF_BUILD_REPORT_FAIL|path=" + config["build_report"])
    by_source = {str(row["source_asset"]): row for row in assets}
    if len(by_source) != config["expected_asset_count"]:
        raise RuntimeError("PF_BUILD_REPORT_DUPLICATE_SOURCE")
    return report, by_source


def target_rows(config, show):
    cues = list(show.get_editor_property("cues"))
    rows = [(index, cue) for index, cue in enumerate(cues)
            if str(cue.get_editor_property("label")).startswith(config["passage_label_prefix"])]
    if len(rows) != int(config["expected_occurrence_count"]):
        raise RuntimeError("PF_OCCURRENCE_COUNT_FAIL|expected=%d|actual=%d" %
                           (config["expected_occurrence_count"], len(rows)))
    guids = [f.cue_guid(cue) for _, cue in rows]
    if any(not value for value in guids) or len(set(guids)) != len(guids):
        raise RuntimeError("PF_GUID_IDENTITY_FAIL")
    return rows


def library_entries(show):
    library_path = c.asset_path(show.get_editor_property("wing_library"))
    library = unreal.EditorAssetLibrary.load_asset(library_path) if library_path else None
    if library is None:
        raise RuntimeError("PF_WING_LIBRARY_LOAD_FAIL|path=" + str(library_path))
    result = {}
    for entry in library.get_editor_property("entries"):
        mesh = c.asset_path(entry.get_editor_property("mesh"))
        if mesh:
            result[mesh] = entry
    return result


def row_identity(row):
    return "%s:%s" % (row["cue_index"], row["cue_guid"])


def assert_live_rows(config, preflight, show, expected_after=False):
    live = target_rows(config, show)
    expected = {int(row["cue_index"]): row for row in preflight["rows"]}
    if [index for index, _ in live] != sorted(expected):
        raise RuntimeError("PF_FRESH_IDENTITY_INDEX_DRIFT")
    cues = list(show.get_editor_property("cues"))
    for index, cue in live:
        actual = f.occurrence_row(index, cue)
        wanted = copy.deepcopy(expected[index])
        if expected_after:
            for side in s.SIDES:
                if s.side_is_skipped(wanted, side):
                    continue
                wanted[side]["mesh"] = s.target_mesh_path(
                    wanted[side]["mesh"], config["destination_root"], config["target_suffix"])
        if not compare.occurrence_matches(actual, wanted):
            raise RuntimeError("PF_LIVE_ROW_DRIFT|after=%s|index=%d|guid=%s" %
                               (expected_after, index, wanted["cue_guid"]))
    return cues


def mesh_vertices(mesh):
    dynamic = PILOT.dynamic_lod(mesh, 0)
    raw = dynamic["_raw"]
    front = list(raw[0]["positions"])
    socket_report = PILOT.socket_report(mesh)
    pole_y = [float(value["location_cm"][1]) for name, value in socket_report.items()
              if name.startswith("SOCKET_Pole_")]
    if not front or not pole_y:
        raise RuntimeError("PF_VERTEX_CONTRACT_MISSING|mesh=" + mesh.get_path_name())
    timber = raw[2]
    poles = [position for color, position in zip(timber["colors"], timber["positions"])
             if float(color.r) >= 0.97 and abs(float(position.x)) <= 5.5 and
             any(abs(float(position.y) - y) <= 5.5 for y in pole_y)]
    if not poles:
        raise RuntimeError("PF_POLE_VERTICES_MISSING|mesh=" + mesh.get_path_name())
    return front, poles


def measure_mesh(mesh, transform, frame, side):
    front, poles = mesh_vertices(mesh)
    front_world = [transform.transform_location(point) for point in front]
    pole_world = [transform.transform_location(point) for point in poles]
    front_pair = [frame.inverse_transform_location(point) for point in front_world]
    inner = (max(float(point.y) for point in front_pair) if side == "left" else
             min(float(point.y) for point in front_pair))
    return {
        "mesh": c.asset_path(mesh),
        "panel_world_bottom_cm": min(float(point.z) for point in front_world),
        "pole_world_bottom_cm": min(float(point.z) for point in pole_world),
        "inner_edge_cm": inner,
        "panel_vertex_count": len(front),
        "pole_vertex_count": len(poles),
        "panel_local_bottom_cm": min(float(point.z) for point in front),
        "pole_local_bottom_cm": min(float(point.z) for point in poles),
    }


def measure_occurrence(config, actor, cue, record, mesh_overrides=None):
    refs = f.refs_for(actor, record["cue_guid"])
    pair = cue.get_editor_property("wing_pair")
    frame, source = v.pair_frame(
        actor, cue, refs, pair,
        {"cue_label": record["cue_label"], "changed_sides": ["left", "right"]},
        library_entries(unreal.EditorAssetLibrary.load_asset(s.SHOW)),
    )
    result = {}
    for side in s.SIDES:
        if s.side_is_skipped(record, side):
            panel = f.panel_plain(pair.get_editor_property(side))
            ref = refs[side]
            component = ref.get_editor_property("component")
            instance_index = int(ref.get_editor_property("instance_index"))
            bounds = f.world_bounds(ref)
            result[side] = {
                "status": "SKIPPED", "reason": s.SKIP_REASON, "mesh": panel["mesh"],
                "panel_local_transform": panel["local_transform"],
                "base_world_transform": f.transform_plain(
                    ref.get_editor_property("base_world_transform")),
                "instance_world_transform": f.transform_plain(
                    f.instance_transform(component, instance_index)),
                "world_bounds": {"world_min": bounds["world_min"],
                                 "world_max": bounds["world_max"]},
            }
            continue
        if mesh_overrides and side in mesh_overrides:
            mesh = mesh_overrides[side]
        else:
            mesh = refs[side].get_editor_property("component").get_editor_property("static_mesh")
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("PF_STATIC_MESH_MISSING|identity=%s|side=%s" %
                               (row_identity(record), side))
        result[side] = measure_mesh(
            mesh, refs[side].get_editor_property("base_world_transform"), frame, side)
    if all(not s.side_is_skipped(record, side) for side in s.SIDES):
        result["gap_cm"] = float(result["right"]["inner_edge_cm"] -
                                 result["left"]["inner_edge_cm"])
    else:
        result["gap_cm"] = None
        result["gap_status"] = {"status": "SKIPPED", "reason": s.SKIP_REASON}
    result["pair_frame_source"] = source
    return result


def preflight(config_path=None):
    config = s.load_config(config_path)
    try:
        if s.log_has("FLATV3_SLOT_RELEASED run=" + config["run_id"]):
            raise RuntimeError("PF_RUN_ALREADY_RELEASED")
        s.assert_context(config, clean=True)
        if not s.log_has(config["required_previous_marker"]):
            raise RuntimeError("PF_PREVIOUS_MARKER_NOT_FOUND|" + config["required_previous_marker"])
        report, by_source = load_build_report(config)
        show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
        if show is None:
            raise RuntimeError("PF_SHOW_LOAD_FAIL")
        actor = f.passage_actor(config, show)
        occurrences = target_rows(config, show)
        rows = []
        source_meshes = set()
        target_meshes = set()
        for index, cue in occurrences:
            record = f.occurrence_row(index, cue)
            for side in s.SIDES:
                policy = s.source_policy(
                    record[side], by_source, config["destination_root"], config["target_suffix"])
                record[side]["pf_action"] = policy["action"]
                if policy["action"] == "skip":
                    record[side]["skip_reason"] = policy["reason"]
                    continue
                source_meshes.add(policy["source"])
                target_meshes.add(policy["target_mesh"])
            record["measurements"] = measure_occurrence(config, actor, cue, record)
            rows.append(record)
        if len(source_meshes) != config["expected_asset_count"]:
            raise RuntimeError("PF_USED_SOURCE_COUNT_FAIL|actual=%d" % len(source_meshes))
        existing = [path for path in sorted(target_meshes)
                    if unreal.EditorAssetLibrary.does_asset_exist(path)]
        s.ensure_fresh_import(existing)
        if s.census() != s.CLEAN:
            raise RuntimeError("PF_PREFLIGHT_DIRTIED_EDITOR")
        skipped = s.skipped_entries(rows)
        payload = {
            "run": config["run_id"], "mode": "preflight", "status": "PASS",
            "world": s.WORLD, "show": s.SHOW, "row_count": len(rows),
            "fresh_index_range": [min(row["cue_index"] for row in rows),
                                  max(row["cue_index"] for row in rows)],
            "identity_source": "fresh read-only Show enumeration by P05 label prefix",
            "rows": rows, "source_meshes": sorted(source_meshes),
            "target_meshes": sorted(target_meshes), "build_report": config["build_report"],
            "build_assets": len(report["assets"]), "skipped_sides": skipped,
            "skipped_side_count": len(skipped), "dirty_after": s.census(),
        }
        path = s.write_json(config, "preflight", payload)
        unreal.log("%s run=%s rows=%d fresh_indices=%s assets=%d skipped=%s census=%s report=%s" %
                   (s.marker("PREFLIGHT_OK"), config["run_id"], len(rows),
                     payload["fresh_index_range"], len(source_meshes),
                     json.dumps(skipped, separators=(",", ":"), sort_keys=True),
                     json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
        return payload
    except Exception as exc:
        s.write_json(config, "preflight", {"run": config["run_id"], "mode": "preflight",
            "status": "FAIL", "reason": str(exc), "traceback": traceback.format_exc(),
            "census": s.census()}, failure=True)
        s.log_release(config, "FAIL", [], "preflight:" + str(exc))
        raise


def import_inventory(config, slot_a):
    tools_dir = os.path.join(s.PROJECT, "Tools", "FlatV3")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import socket_contract
    build_report, _ = load_build_report(config)
    rows = []
    for item in sorted(build_report["assets"], key=lambda value: value["asset"]):
        folder = os.path.dirname(item["fbx"])
        status = slot_a.load_json(os.path.join(folder, "status.json"))
        validation = slot_a.load_json(status["validation"])
        manifest = slot_a.load_json(status["build_manifest"])
        owner = str(status["asset_suffix"])
        mesh_name = str(status["asset_name"])
        if (status.get("status") != "built" or not status.get("validation_pass") or
                not validation.get("pass") or not validation["checks"]["triangulated_export"].get("enabled") or
                abs(float(status.get("pole_extension_cm", -1)) - config["pole_extension_cm"]) > 0.001):
            raise RuntimeError("PF_SOURCE_GATE_FAIL|asset=" + mesh_name)
        socket_path = status["socket_sidecar"]
        expected_socket = socket_contract.make_socket_payload(
            asset=mesh_name, side=status["build_side"], mount="wing",
            height_cm=float(status["height_cm"]), width_m=float(manifest["dimensions_m"]["width"]),
            pole_positions_y_m=manifest["pole_positions_y_m"],
            pole_extension_cm=config["pole_extension_cm"])
        socket_payload = socket_contract.load_json(Path(socket_path))
        failures = socket_contract.validate_socket_payload(socket_payload, expected_socket)
        if failures or socket_payload.get("baked_pole_geometry") != expected_socket["baked_pole_geometry"]:
            raise RuntimeError("PF_SOCKET_CONTRACT_FAIL|asset=%s|failures=%s" %
                               (mesh_name, json.dumps(failures)))
        original = status["source_folder"]
        if not owner.endswith(config["target_suffix"]) or not mesh_name.endswith(config["target_suffix"]):
            raise RuntimeError("PF_TARGET_SUFFIX_SOURCE_FAIL|asset=" + mesh_name)
        original_owner = owner.removesuffix(config["target_suffix"])
        sources = {
            "mesh": status["fbx"], "socket": socket_path, "validation": status["validation"],
        }
        for name in slot_a.COMMON_AGED:
            sources[name] = os.path.join(original, "aged", name + ".png")
        missing = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing:
            raise RuntimeError("PF_SOURCE_FILES_MISSING|asset=%s|missing=%s" %
                               (mesh_name, json.dumps(missing)))
        target = config["destination_root"]
        destinations = {"mesh": target + "/StaticMeshes/" + mesh_name}
        rows.append({"passage": "P05", "folder": folder, "owner": owner,
                     "source_owner": original_owner,
                     "source_mesh": target + "/StaticMeshes/" + str(item["source_asset"]),
                     "mesh_name": mesh_name, "side": status["build_side"], "mount": "wing",
                     "baked_poles": True, "sources": sources, "destinations": destinations,
                     "validation": validation})
    if len(rows) != config["expected_asset_count"]:
        raise RuntimeError("PF_IMPORT_SOURCE_COUNT_FAIL|actual=%d" % len(rows))
    return rows


def verify_material_binding(config, slot_a, mesh, row, label):
    """Read back the four slots and the reused source MIs' live _o2 parameters."""
    contract = s.source_material_contract(
        config["destination_root"], row["source_owner"], config["required_texture_suffix"])
    static_materials = list(mesh.get_editor_property("static_materials"))
    slot_names = [str(value.get_editor_property("material_slot_name"))
                  for value in static_materials]
    actual_paths = [slot_a.pilot.asset_package(
        value.get_editor_property("material_interface")) for value in static_materials]
    expected_paths = [contract["slot_materials"]["Front"],
                      contract["slot_materials"]["Flap"],
                      slot_a.PARENTS["Timber"], slot_a.PARENTS["Edge"]]
    if slot_names != list(slot_a.SLOTS) or actual_paths != expected_paths:
        raise RuntimeError("PF_POLES_SLOT_MI_READBACK_FAIL|label=%s|slots=%s|actual=%s|expected=%s" %
                           (label, json.dumps(slot_names), json.dumps(actual_paths),
                            json.dumps(expected_paths)))
    texture_readback = {}
    for index, material_slot in enumerate(("Front", "Flap")):
        instance = static_materials[index].get_editor_property("material_interface")
        if not isinstance(instance, unreal.MaterialInstanceConstant):
            raise RuntimeError("PF_SOURCE_MI_CLASS_FAIL|label=%s|slot=%s" %
                               (label, material_slot))
        actual = slot_a.pilot.serialized_texture_parameters(instance)
        texture_readback[material_slot] = s.validate_o2_material_parameters(
            actual, contract["texture_parameters"], "%s:%s" % (label, material_slot),
            config["required_texture_suffix"])
    return {"slots": slot_names, "slot_materials": actual_paths,
            "mi_texture_parameters": texture_readback}


def import_mesh_only(config, slot_a, row):
    """Import only the _poles2 mesh and bind the source flat's existing live materials."""
    destination = row["destinations"]["mesh"]
    mesh = slot_a.import_one(row["sources"]["mesh"], destination,
                             slot_a.pilot.fbx_options(True))
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("PF_MESH_CLASS_FAIL|path=" + destination)
    mesh.modify()
    nanite = mesh.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", nanite)
    socket_report, socket_rows = slot_a.apply_sockets(mesh, row)

    source_mesh = unreal.EditorAssetLibrary.load_asset(row["source_mesh"])
    if not isinstance(source_mesh, unreal.StaticMesh):
        raise RuntimeError("PF_SOURCE_MESH_LOAD_FAIL|path=" + row["source_mesh"])
    source_materials = list(source_mesh.get_editor_property("static_materials"))
    source_readback = verify_material_binding(
        config, slot_a, source_mesh, row, row["source_mesh"] + ":source")
    for index, material in enumerate(source_materials):
        mesh.set_material(index, material.get_editor_property("material_interface"))

    geometry = slot_a.verify_geometry(mesh, row, socket_rows)
    target_readback = verify_material_binding(config, slot_a, mesh, row, destination + ":import")
    return {"created": [destination], "geometry": geometry,
            "slot_materials": target_readback["slot_materials"],
            "source_material_readback": source_readback,
            "target_material_readback": target_readback,
            "socket_writeback": socket_report}


def verify_mesh_fresh(config, slot_a, row):
    destination = row["destinations"]["mesh"]
    mesh = unreal.EditorAssetLibrary.load_asset(destination)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("PF_FRESH_MESH_LOAD_FAIL|path=" + destination)
    socket_rows = slot_a.socket_payload(row["sources"]["socket"], row["mesh_name"])
    return {"geometry": slot_a.verify_geometry(mesh, row, socket_rows),
            "material_readback": verify_material_binding(
                config, slot_a, mesh, row, destination + ":fresh")}


def import_assets(config_path=None):
    config = s.load_config(config_path)
    run = config["import_run_id"]
    saved_roots = []
    tracker = None
    cleanup = {"status": "NOT_NEEDED", "created": [], "deleted": []}
    try:
        s.assert_context(config, clean=True)
        preflight_report = s.read_json(config, "preflight")
        if preflight_report.get("status") != "PASS":
            raise RuntimeError("PF_IMPORT_PREFLIGHT_NOT_PASS")
        slot_a = load_slot_a_library(config)
        slot_a.RUN = run
        assets = import_inventory(config, slot_a)
        # This remains a real hash gate for P05 aged inputs, even though the
        # preferred mesh-only path imports no textures or material instances.
        _, common_hashes = slot_a.common_inventory(assets)
        per_asset_paths = sorted({path for row in assets for path in slot_a.asset_paths(row)})
        existing = [path for path in per_asset_paths if unreal.EditorAssetLibrary.does_asset_exist(path)]
        s.ensure_fresh_import(existing)
        planned = per_asset_paths
        import import_failure_cleanup as ifc
        tracker = ifc.ImportRunTracker("PF", planned, s.census(), s.census)
        tracker.install_deferred_cleanup(slot_a)
        asset_reports = {}
        for row in assets:
            asset_reports[row["owner"]] = import_mesh_only(config, slot_a, row)
            tracker.observe_created()
            unreal.log("FLATV3_PF_IMPORT_ASSET_GATE_PASS run=%s asset=%s" %
                       (run, row["mesh_name"]))
        save_paths = per_asset_paths
        slot_a.save_narrow(save_paths)
        saved_roots.extend(save_paths)
        slot_a.pilot.reload_new_packages(save_paths)
        fresh_assets = {row["owner"]: verify_mesh_fresh(config, slot_a, row)
                        for row in assets}
        if s.census() != s.CLEAN:
            raise RuntimeError("PF_IMPORT_DIRTY_AFTER_READBACK|" + json.dumps(s.census()))
        skipped = preflight_report.get("skipped_sides", [])
        report = {"run": run, "mode": "import", "status": "PASS", "assets": len(assets),
                   "asset_reports": asset_reports, "fresh_assets": fresh_assets,
                   "common_aged_hashes": common_hashes,
                   "material_strategy": config["material_strategy"],
                   "new_texture_count": 0, "new_mi_count": 0,
                   "saved_roots": sorted(set(saved_roots)),
                   "skipped_side_count": len(skipped), "skipped_sides": skipped,
                   "reimport_policy": "all PF target packages must be absent"}
        path = s.write_json(config, "import", report, run=run)
        unreal.log("%s run=%s assets=%d saved_count=%d saved_roots=%s report=%s" %
                   (config["import_success_marker"], run, len(assets), len(set(saved_roots)),
                    json.dumps(sorted(set(saved_roots)), separators=(",", ":")), path))
        s.log_release(config, "OK_IMPORT_ONLY_CONTINUE_PF", sorted(set(saved_roots)),
                      run=run, skipped=skipped)
        return report
    except Exception as exc:
        original = traceback.format_exc()
        if tracker is not None:
            import import_failure_cleanup as ifc
            cleanup, cleanup_error = ifc.cleanup_after_failure("PF", run, tracker, s.census)
            if cleanup_error:
                s.log_release(config, "CLEANUP_FAIL", saved_roots, str(cleanup_error), run=run)
                raise cleanup_error from exc
        s.write_json(config, "import", {"run": run, "mode": "import", "status": "FAIL",
            "reason": str(exc), "traceback": original, "cleanup": cleanup,
            "saved_roots": sorted(set(saved_roots)), "census": s.census()}, run=run, failure=True)
        s.log_release(config, "FAIL_CLEANED", saved_roots, "import:" + str(exc), run=run)
        raise


def dry(config_path=None):
    config = s.load_config(config_path)
    try:
        s.assert_context(config, clean=True)
        if not s.log_has("%s run=%s" % (config["import_success_marker"], config["import_run_id"])):
            raise RuntimeError("PF_IMPORT_MARKER_MISSING")
        pre = s.read_json(config, "preflight")
        show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
        cues = assert_live_rows(config, pre, show, expected_after=False)
        actor = f.passage_actor(config, show)
        plan = []
        for record in pre["rows"]:
            index = int(record["cue_index"])
            overrides = {}
            new_panels = {}
            for side in s.SIDES:
                if s.side_is_skipped(record, side):
                    new_panels[side] = copy.deepcopy(record[side])
                    continue
                target_path = s.target_mesh_path(
                    record[side]["mesh"], config["destination_root"], config["target_suffix"])
                mesh = unreal.EditorAssetLibrary.load_asset(target_path)
                if not isinstance(mesh, unreal.StaticMesh):
                    raise RuntimeError("PF_IMPORTED_TARGET_MISSING|path=" + target_path)
                overrides[side] = mesh
                panel = copy.deepcopy(record[side])
                panel["mesh"] = target_path
                new_panels[side] = panel
            predicted = measure_occurrence(config, actor, cues[index], record, overrides)
            gates = {}
            for side in s.SIDES:
                if s.side_is_skipped(record, side):
                    gates[side] = s.validate_skipped_unchanged(
                        record["measurements"][side], predicted[side],
                        row_identity(record) + ":" + side)
                    continue
                gates[side] = s.validate_measurement(
                    record["measurements"][side], predicted[side], config,
                    row_identity(record) + ":" + side)
            if any(s.side_is_skipped(record, side) for side in s.SIDES):
                gap_delta = None
                gap_gate = {"status": "SKIPPED", "reason": s.SKIP_REASON}
            else:
                gap_delta = s.validate_gap(record["measurements"]["gap_cm"], predicted["gap_cm"],
                                           config, row_identity(record))
                gap_gate = {"status": "PASS", "delta_cm": gap_delta}
            plan.append({"cue_index": index, "cue_guid": record["cue_guid"],
                         "cue_label": record["cue_label"], "left": new_panels["left"],
                         "right": new_panels["right"], "before": record["measurements"],
                         "predicted": predicted, "gates": gates, "gap_delta_cm": gap_delta,
                         "gap_gate": gap_gate})
        skipped = s.skipped_entries(pre["rows"])
        changed_panels = sum(not s.side_is_skipped(record, side)
                             for record in pre["rows"] for side in s.SIDES)
        payload = {"run": config["run_id"], "mode": "dry_run", "status": "PASS",
                   "row_count": len(plan), "panel_count": len(plan) * 2,
                   "changed_panel_count": changed_panels,
                   "skipped_side_count": len(skipped), "skipped_sides": skipped,
                   "changed_field": "non-skipped left.mesh and right.mesh only", "rows": plan,
                   "dirty_after": s.census()}
        path = s.write_json(config, "dry_run", payload)
        unreal.log("%s run=%s rows=%d panels=%d skipped=%s pole_max_cm=%.3f census=%s report=%s" %
                   (s.marker("DRY_OK"), config["run_id"], len(plan), len(plan) * 2,
                     json.dumps(skipped, separators=(",", ":"), sort_keys=True),
                     max(row["predicted"][side]["pole_world_bottom_cm"]
                         for row in plan for side in s.SIDES
                         if not s.side_is_skipped(row, side)),
                    json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
        return payload
    except Exception as exc:
        s.write_json(config, "dry_run", {"run": config["run_id"], "mode": "dry_run",
            "status": "FAIL", "reason": str(exc), "traceback": traceback.format_exc(),
            "census": s.census()}, failure=True)
        s.log_release(config, "FAIL", [], "dry:" + str(exc))
        raise


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(config_path=None):
    config = s.load_config(config_path)
    try:
        s.assert_context(config, clean=True)
        if s.read_json(config, "dry_run").get("status") != "PASS":
            raise RuntimeError("PF_BACKUP_DRY_NOT_PASS")
        if os.path.exists(config["backup_path"]):
            raise RuntimeError("PF_BACKUP_PATH_EXISTS|" + config["backup_path"])
        os.makedirs(config["backup_path"])
        rows = []
        for name in config["backup_files"]:
            source = config["backup_sources"][name]
            target = os.path.join(config["backup_path"], name)
            shutil.copy2(source, target)
            if sha256_file(source) != sha256_file(target):
                raise RuntimeError("PF_BACKUP_HASH_FAIL|" + name)
            rows.append({"name": name, "source": source, "copy": target,
                         "sha256": sha256_file(target), "bytes": os.path.getsize(target)})
        manifest_path = os.path.join(config["backup_path"], "pf_backup_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump({"run": config["run_id"], "status": "PASS", "files": rows},
                      handle, indent=2, sort_keys=True); handle.write("\n")
        payload = {"run": config["run_id"], "mode": "backup", "status": "PASS",
                   "file_count": len(rows), "files": rows, "manifest": manifest_path}
        path = s.write_json(config, "backup", payload)
        unreal.log("%s run=%s files=2 path=%s report=%s" %
                   (s.marker("BACKUP_OK"), config["run_id"], config["backup_path"], path))
        return payload
    except Exception as exc:
        s.write_json(config, "backup", {"run": config["run_id"], "mode": "backup",
            "status": "FAIL", "reason": str(exc), "traceback": traceback.format_exc()},
            failure=True)
        s.log_release(config, "FAIL", [], "backup:" + str(exc))
        raise


def validate_backup(config):
    report = s.read_json(config, "backup")
    expected = set(config["backup_files"] + ["pf_backup_manifest.json"])
    if report.get("status") != "PASS" or set(os.listdir(config["backup_path"])) != expected:
        raise RuntimeError("PF_BACKUP_SCOPE_FAIL")
    with open(os.path.join(config["backup_path"], "pf_backup_manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    by_name = {row["name"]: row for row in manifest["files"]}
    for name in config["backup_files"]:
        if (sha256_file(config["backup_sources"][name]) != by_name[name]["sha256"] or
                sha256_file(os.path.join(config["backup_path"], name)) != by_name[name]["sha256"]):
            raise RuntimeError("PF_BACKUP_VALIDATION_FAIL|" + name)


def expected_after_rows(pre, plan):
    rows = {int(row["cue_index"]): copy.deepcopy(row) for row in pre["rows"]}
    for planned in plan["rows"]:
        for side in s.SIDES:
            if s.side_is_skipped(planned, side):
                continue
            rows[int(planned["cue_index"])][side] = copy.deepcopy(planned[side])
    return rows


def apply(config_path=None):
    config = s.load_config(config_path)
    saved = []
    try:
        s.assert_context(config, clean=True)
        pre = s.read_json(config, "preflight")
        plan = s.read_json(config, "dry_run")
        if pre.get("status") != "PASS" or plan.get("status") != "PASS":
            raise RuntimeError("PF_APPLY_PLAN_NOT_PASS")
        validate_backup(config)
        show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
        cues = assert_live_rows(config, pre, show, expected_after=False)
        for row in plan["rows"]:
            index = int(row["cue_index"])
            cue = cues[index]
            pair = cue.get_editor_property("wing_pair")
            for side in s.SIDES:
                if s.side_is_skipped(row, side):
                    continue
                panel = pair.get_editor_property(side)
                target = unreal.EditorAssetLibrary.load_asset(row[side]["mesh"])
                if not isinstance(target, unreal.StaticMesh):
                    raise RuntimeError("PF_APPLY_TARGET_MISSING|" + row[side]["mesh"])
                panel.set_editor_property("mesh", target)
                pair.set_editor_property(side, panel)
            cue.set_editor_property("wing_pair", pair)
            cues[index] = cue
        show.modify()
        show.set_editor_property("cues", cues)
        unreal.log("%s run=%s passage=P05 ordinal=1" %
                   (s.marker("MATERIALIZE_CALL"), config["run_id"]))
        if not f.passage_actor(config, show).materialize_passage():
            raise RuntimeError("PF_MATERIALIZE_FAIL")
        expected_dirty = {"content": [s.SHOW], "maps": [s.WORLD]}
        before_save = s.census()
        if before_save != expected_dirty:
            raise RuntimeError("PF_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                               (json.dumps(expected_dirty, sort_keys=True),
                                json.dumps(before_save, sort_keys=True)))
        if not unreal.EditorAssetLibrary.save_asset(s.SHOW, only_if_is_dirty=False):
            raise RuntimeError("PF_SHOW_SAVE_FAIL")
        saved.append(s.SHOW)
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise RuntimeError("PF_LEVEL_SAVE_FAIL")
        saved.append(s.WORLD)
        if s.census() != s.CLEAN:
            raise RuntimeError("PF_POST_SAVE_DIRTY|" + json.dumps(s.census()))
        assert_live_rows(config, pre, unreal.EditorAssetLibrary.load_asset(s.SHOW), expected_after=True)
        skipped = s.skipped_entries(plan["rows"])
        changed_panels = sum(not s.side_is_skipped(row, side)
                             for row in plan["rows"] for side in s.SIDES)
        payload = {"run": config["run_id"], "mode": "apply", "status": "PASS",
                   "rows": len(plan["rows"]), "panels": len(plan["rows"]) * 2,
                   "changed_panel_count": changed_panels,
                   "skipped_side_count": len(skipped), "skipped_sides": skipped,
                   "changed_field": "non-skipped mesh only", "materialize_calls": ["P05"],
                   "dirty_before_save": before_save, "dirty_after_save": s.census(),
                   "saved_roots": sorted(set(saved))}
        path = s.write_json(config, "apply", payload)
        unreal.log("%s run=%s rows=%d panels=%d changed_panels=%d skipped=%s saved_count=2 saved_roots=%s report=%s" %
                   (s.marker("APPLY_SAVED"), config["run_id"], len(plan["rows"]),
                     len(plan["rows"]) * 2, changed_panels,
                     json.dumps(skipped, separators=(",", ":"), sort_keys=True),
                     json.dumps(sorted(set(saved)), separators=(",", ":")), path))
        return payload
    except Exception as exc:
        s.write_json(config, "apply", {"run": config["run_id"], "mode": "apply",
            "status": "FAIL", "reason": str(exc), "traceback": traceback.format_exc(),
            "saved_roots": sorted(set(saved)), "census": s.census()}, failure=True)
        s.log_release(config, "FAIL", saved, "apply:" + str(exc))
        raise


def verify(config_path=None):
    config = s.load_config(config_path)
    try:
        s.assert_context(config, clean=True)
        if not s.log_has(config["verify_token"]):
            raise RuntimeError("PF_SAVED_MASTER_MATCH_TOKEN_MISSING")
        pre = s.read_json(config, "preflight")
        plan = s.read_json(config, "dry_run")
        applied = s.read_json(config, "apply")
        if applied.get("status") != "PASS" or sorted(applied.get("saved_roots", [])) != sorted(s.SAVED_ROOTS):
            raise RuntimeError("PF_APPLY_EVIDENCE_FAIL")
        show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
        cues = assert_live_rows(config, pre, show, expected_after=True)
        actor = f.passage_actor(config, show)
        slot_a = load_slot_a_library(config)
        import_rows = import_inventory(config, slot_a)
        material_readback = {}
        for row in import_rows:
            target = row["destinations"]["mesh"]
            mesh = unreal.EditorAssetLibrary.load_asset(target)
            if not isinstance(mesh, unreal.StaticMesh):
                raise RuntimeError("PF_VERIFY_TARGET_MISSING|path=" + target)
            material_readback[target] = verify_material_binding(
                config, slot_a, mesh, row, target + ":final_verify")
        plan_by_index = {int(row["cue_index"]): row for row in plan["rows"]}
        verified = []
        for record in pre["rows"]:
            index = int(record["cue_index"])
            measured = measure_occurrence(config, actor, cues[index], record)
            gates = {}
            for side in s.SIDES:
                if s.side_is_skipped(record, side):
                    gates[side] = s.validate_skipped_unchanged(
                        record["measurements"][side], measured[side],
                        row_identity(record) + ":" + side)
                    continue
                gates[side] = s.validate_measurement(
                    record["measurements"][side], measured[side], config,
                    row_identity(record) + ":" + side)
            if any(s.side_is_skipped(record, side) for side in s.SIDES):
                gap_delta = None
                gap_gate = {"status": "SKIPPED", "reason": s.SKIP_REASON}
            else:
                gap_delta = s.validate_gap(record["measurements"]["gap_cm"], measured["gap_cm"],
                                           config, row_identity(record))
                gap_gate = {"status": "PASS", "delta_cm": gap_delta}
            for side in s.SIDES:
                expected_mesh = (record[side]["mesh"] if s.side_is_skipped(record, side)
                                 else plan_by_index[index][side]["mesh"])
                if measured[side]["mesh"] != expected_mesh:
                    raise RuntimeError("PF_VERIFY_MESH_FAIL|identity=%s|side=%s" %
                                       (row_identity(record), side))
            verified.append({"cue_index": index, "cue_guid": record["cue_guid"],
                             "cue_label": record["cue_label"], "measurements": measured,
                             "gates": gates, "gap_delta_cm": gap_delta,
                             "gap_gate": gap_gate})
        if s.census() != s.CLEAN:
            raise RuntimeError("PF_VERIFY_DIRTIED_EDITOR")
        skipped = s.skipped_entries(pre["rows"])
        changed_panels = sum(not s.side_is_skipped(record, side)
                             for record in pre["rows"] for side in s.SIDES)
        payload = {"run": config["run_id"], "mode": "verify_read_only", "status": "PASS",
                    "rows": len(verified), "panels": len(verified) * 2,
                    "changed_panel_count": changed_panels,
                    "skipped_side_count": len(skipped), "skipped_sides": skipped,
                    "assertions": ["world panel bottom unchanged within 1 cm",
                        "world pole bottom <= floor z + 1 cm", "inner edges unchanged",
                        "centre gaps unchanged where both sides are V3",
                        "each _poles2 mesh reuses its source flat Front/Flap MIs",
                        "all reused Front/Flap MIs read back SkinColor/Mask/Normal _o2",
                        "kept-old non-V3 mesh, transforms, and world bounds unchanged",
                        "all non-mesh Show fields unchanged"],
                   "rows_verified": verified, "material_readback": material_readback,
                   "saved_roots": sorted(s.SAVED_ROOTS),
                   "census": s.census()}
        path = s.write_json(config, "verify", payload)
        unreal.log("%s run=%s rows=%d panels=%d changed_panels=%d skipped=%s saved_count=2 saved_roots=%s census=%s report=%s" %
                   (config["success_marker"], config["run_id"], len(verified), len(verified) * 2,
                     changed_panels,
                     json.dumps(skipped, separators=(",", ":"), sort_keys=True),
                     json.dumps(sorted(s.SAVED_ROOTS), separators=(",", ":")),
                    json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
        s.log_release(config, "OK", s.SAVED_ROOTS, skipped=skipped)
        return payload
    except Exception as exc:
        s.write_json(config, "verify", {"run": config["run_id"], "mode": "verify_read_only",
            "status": "FAIL", "reason": str(exc), "traceback": traceback.format_exc(),
            "census": s.census()}, failure=True)
        s.log_release(config, "FAIL", s.SAVED_ROOTS, "verify:" + str(exc))
        raise
