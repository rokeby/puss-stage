"""Guarded Unreal tool for Job 122. Authored offline; do not run in this worktree.

PROBE and DRY are read-only. APPLY/REVERT can touch only the twelve named MIs.
No master graph is ever modified; MaterialEditingLibrary is used only to inventory
the master graph and to set/read instance overrides.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys
import traceback

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import j122_core as core  # noqa: E402

ARGS = os.path.join(HERE, "j122_args.json")
PROBE_OUT = os.path.join(HERE, "j122_probe_latest.json")
DRY_OUT = os.path.join(HERE, "j122_dry_latest.json")
VERIFY_OUT = os.path.join(HERE, "j122_verify_latest.json")
RECORD = os.path.join(HERE, "j122_apply_record.json")


class Stop(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Stop(message)


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def path_of(obj):
    return None if obj is None else str(obj.get_path_name()).split(".")[0]


def full_path(obj):
    return None if obj is None else str(obj.get_path_name())


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(x.get_name()) for x in lib.get_dirty_content_packages()),
            "maps": sorted(str(x.get_name()) for x in lib.get_dirty_map_packages())}


def clean_editor():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(subsystem.get_game_world() is None, "PIE_OR_SIE_RUNNING")
    require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|" + json.dumps(census()))


def parameter_name(row):
    info = row.get_editor_property("parameter_info")
    return str(info.get_editor_property("name"))


def color(value):
    return [float(value.r), float(value.g), float(value.b), float(value.a)]


def serialized(mi):
    return {
        "parent": path_of(prop(mi, "parent")),
        "textures": {parameter_name(x): path_of(x.get_editor_property("parameter_value"))
                     for x in (prop(mi, "texture_parameter_values", []) or [])},
        "scalars": {parameter_name(x): float(x.get_editor_property("parameter_value"))
                    for x in (prop(mi, "scalar_parameter_values", []) or [])},
        "vectors": {parameter_name(x): color(x.get_editor_property("parameter_value"))
                    for x in (prop(mi, "vector_parameter_values", []) or [])},
    }


def master_of(mi):
    seen = set()
    obj = mi
    chain = []
    while obj is not None and str(obj.get_class().get_name()) == "MaterialInstanceConstant":
        require(path_of(obj) not in seen, "PARENT_CYCLE|" + str(path_of(obj)))
        seen.add(path_of(obj)); chain.append(path_of(obj)); obj = prop(obj, "parent")
    require(obj is not None and str(obj.get_class().get_name()) == "Material", "MASTER_RESOLVE|" + path_of(mi))
    chain.append(path_of(obj))
    return obj, chain


def names(material):
    mel = unreal.MaterialEditingLibrary
    return {"texture": sorted(str(x) for x in mel.get_texture_parameter_names(material)),
            "vector": sorted(str(x) for x in mel.get_vector_parameter_names(material)),
            "scalar": sorted(str(x) for x in mel.get_scalar_parameter_names(material)),
            "static_switch": sorted(str(x) for x in mel.get_static_switch_parameter_names(material))}


def expression_inventory(master):
    """Read-only master/function graph evidence and direct parameter consumers."""
    mel = unreal.MaterialEditingLibrary
    rows, parameter_sources, edges, visited = [], {}, [], set()

    def visit(container, kind):
        key = (kind, full_path(container))
        if key in visited:
            return
        visited.add(key)
        expressions = list(mel.get_material_expressions(container) or []) if kind == "material" else list(
            mel.get_material_function_expressions(container) or [])
        for expression in expressions:
            pname = prop(expression, "parameter_name")
            row = {"container": path_of(container), "name": str(expression.get_name()),
                   "path": full_path(expression), "class": str(expression.get_class().get_name())}
            if pname is not None:
                row["parameter_name"] = str(pname)
                parameter_sources.setdefault(str(pname), []).append(full_path(expression))
            desc = prop(expression, "desc")
            if desc:
                row["description"] = str(desc)
            rows.append(row)
            try:
                inputs = list(mel.get_inputs_for_material_expression(container, expression) or []) if kind == "material" else list(
                    mel.get_inputs_for_material_function_expression(container, expression) or [])
            except Exception:
                inputs = []
            for source in inputs:
                edges.append({"source": full_path(source), "consumer": full_path(expression),
                              "consumer_name": str(expression.get_name()),
                              "consumer_class": str(expression.get_class().get_name()),
                              "channel": "".join(letter for letter, field in
                                                 (("R", "r"), ("G", "g"), ("B", "b"), ("A", "a"))
                                                 if bool(prop(expression, field, False)))
                              if str(expression.get_class().get_name()) == "MaterialExpressionComponentMask" else None,
                              "description": str(prop(expression, "desc", "")),
                              "container": path_of(container)})
            function = prop(expression, "material_function")
            if function is not None:
                visit(function, "function")

    visit(master, "material")
    parameter_consumers = {}
    for pname, sources in parameter_sources.items():
        source_set = set(sources)
        parameter_consumers[pname] = [{k: v for k, v in edge.items() if k != "source"}
                                      for edge in edges if edge["source"] in source_set]
    masks = parameter_sources.get("Masks", [])
    return {"expression_count": len(rows), "expressions": rows,
            "container_count": len(visited), "parameter_consumers": parameter_consumers,
            "masks": {"parameter_found": bool(masks), "parameter_count": len(masks),
                      "channel_consumers": parameter_consumers.get("Masks", [])}}


def effective_switches(mi, available):
    mel = unreal.MaterialEditingLibrary
    wanted = sorted(set(core.ACTIVE_SWITCHES) | {core.PRINT["switch"]} |
                    {x[key] for x in core.DETAIL.values() if x for key in ("color_switch", "normal_switch")})
    return {name: bool(mel.get_material_instance_static_switch_parameter_value(mi, name))
            for name in wanted if name in available}


def inspect_targets(cfg):
    before = census()
    rows, graph_cache = [], {}
    for target in core.targets():
        mi = unreal.load_asset(target)
        require(mi is not None and str(mi.get_class().get_name()) == "MaterialInstanceConstant", "TARGET_MISSING|" + target)
        master, chain = master_of(mi)
        master_path = path_of(master)
        if master_path not in graph_cache:
            parameter_names = names(master)
            graph = expression_inventory(master)
            graph_cache[master_path] = {"master": master_path, "parameter_names": parameter_names, "graph": graph}
        evidence = graph_cache[master_path]
        switches = effective_switches(mi, evidence["parameter_names"]["static_switch"])
        plan = core.plan(evidence["parameter_names"], switches, evidence["graph"])
        rows.append({"path": target, "figure": core.figure_from_path(target), "parent_chain": chain,
                     "overrides": serialized(mi), "effective_static_switches": switches, "plan": plan})
    after = census()
    require(before == after, "READ_ONLY_PROBE_DIRTIED|before=%s|after=%s" % (json.dumps(before), json.dumps(after)))
    return {"targets": rows, "masters": sorted(graph_cache.values(), key=lambda x: x["master"]),
            "census_before": before, "census_after": after,
            "apply_ready": len(rows) == 12 and all(x["plan"]["apply_ready"] for x in rows),
            "target_count": len(rows), "writes": 0,
            "proof_boundary": "switch selection and graph inventory are editor-read-back; rendered appearance is unproved"}


def probe(run, cfg, output=PROBE_OUT, mode="PROBE"):
    clean_editor()
    result = {"schema": core.SCHEMA, "run_id": run, "mode": mode, **inspect_targets(cfg)}
    result["fingerprint"] = core.fingerprint({"targets": result["targets"], "masters": result["masters"]})
    write_json(output, result)
    unreal.log("J122GARMENTS_%s_%s|run=%s|targets=12|apply_ready=%d|writes=0|report=%s" %
               (mode, "OK" if result["apply_ready"] else "STOPPED", run, result["apply_ready"], output))
    return result


def project_file(asset_path):
    relative = asset_path.removeprefix("/Game/").replace("/", os.sep) + ".uasset"
    return os.path.normpath(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), relative))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup(run, targets):
    root = os.path.normpath(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                                         "Backups", "PreJ122Garments-" + run))
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    rows = []
    for asset in targets:
        source = project_file(asset)
        require(os.path.isfile(source), "BACKUP_SOURCE_MISSING|" + source)
        relative = asset.removeprefix("/Game/").replace("/", os.sep) + ".uasset"
        destination = os.path.join(root, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        require(sha256(source) == sha256(destination), "BACKUP_HASH|" + asset)
        rows.append({"asset": asset, "source": source, "backup": destination,
                     "bytes": os.path.getsize(destination), "sha256": sha256(destination)})
    return {"root": root, "files": rows}


def effective_readback(mi, plan):
    mel = unreal.MaterialEditingLibrary
    detail = plan["detail"]; printing = plan["print"]
    layer = plan["active_layer"]["layer"]
    return {"detail_color": path_of(mel.get_material_instance_texture_parameter_value(mi, detail["color"])),
            "detail_normal": path_of(mel.get_material_instance_texture_parameter_value(mi, detail["normal"])),
            "detail_tiling": float(mel.get_material_instance_scalar_parameter_value(mi, detail["tiling"])),
            "detail_color_switch": bool(mel.get_material_instance_static_switch_parameter_value(mi, detail["color_switch"])),
            "detail_normal_switch": bool(mel.get_material_instance_static_switch_parameter_value(mi, detail["normal_switch"])),
            "print_map": path_of(mel.get_material_instance_texture_parameter_value(mi, printing["map"])),
            "print_color": color(mel.get_material_instance_vector_parameter_value(mi, printing["colors"][layer])),
            "print_tiling": float(mel.get_material_instance_scalar_parameter_value(mi, printing["tiling"])),
            "print_strength": float(mel.get_material_instance_scalar_parameter_value(mi, printing["strength"])),
            "print_switch": bool(mel.get_material_instance_static_switch_parameter_value(mi, printing["switch"]))}


def expected_values(row, cfg):
    stain = core.stain_paths(row["figure"])[cfg["print_texture_kind"]]
    return {"detail_color": core.WEAVE_BC, "detail_normal": core.WEAVE_N,
            "detail_tiling": cfg["weave_tiling"], "detail_color_switch": True,
            "detail_normal_switch": True, "print_map": stain, "print_color": cfg["print_color"],
            "print_tiling": 1.0, "print_strength": cfg["print_strength"], "print_switch": True}


def matches(got, expected):
    for key, value in expected.items():
        if isinstance(value, float):
            if abs(float(got.get(key, 1e30)) - value) > 1e-4:
                return False
        elif isinstance(value, list):
            if len(got.get(key, [])) != len(value) or max(abs(a-b) for a, b in zip(got[key], value)) > 1e-4:
                return False
        elif got.get(key) != value:
            return False
    return True


def set_expected(mi, row, cfg):
    mel = unreal.MaterialEditingLibrary; plan = row["plan"]; detail = plan["detail"]; printing = plan["print"]
    layer = plan["active_layer"]["layer"]; expected = expected_values(row, cfg)
    bc = unreal.load_asset(expected["detail_color"]); normal = unreal.load_asset(expected["detail_normal"])
    stain = unreal.load_asset(expected["print_map"])
    require(bc is not None and normal is not None and stain is not None, "TEXTURE_LOAD|" + row["path"])
    mel.set_material_instance_texture_parameter_value(mi, detail["color"], bc)
    mel.set_material_instance_texture_parameter_value(mi, detail["normal"], normal)
    mel.set_material_instance_scalar_parameter_value(mi, detail["tiling"], expected["detail_tiling"])
    mel.set_material_instance_static_switch_parameter_value(mi, detail["color_switch"], True)
    mel.set_material_instance_static_switch_parameter_value(mi, detail["normal_switch"], True)
    mel.set_material_instance_texture_parameter_value(mi, printing["map"], stain)
    mel.set_material_instance_vector_parameter_value(mi, printing["colors"][layer], unreal.LinearColor(*expected["print_color"]))
    mel.set_material_instance_scalar_parameter_value(mi, printing["tiling"], expected["print_tiling"])
    mel.set_material_instance_scalar_parameter_value(mi, printing["strength"], expected["print_strength"])
    mel.set_material_instance_static_switch_parameter_value(mi, printing["switch"], True)
    mel.update_material_instance(mi)
    return expected


def save_exact(paths):
    got = census(); allowed = set(paths)
    require(not got["maps"] and set(got["content"]) <= allowed,
            "DIRTY_SCOPE|got=%s|allowed=%s|NOTHING SAVED" % (json.dumps(got), json.dumps(sorted(allowed))))
    for path in got["content"]:
        require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), "SAVE|" + path)
    require(census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|" + json.dumps(census()))
    return got["content"]


def apply(run, cfg):
    clean_editor()
    require(os.path.isfile(DRY_OUT), "NO_DRY_REPORT")
    dry = read_json(DRY_OUT)
    current = inspect_targets(cfg)
    fingerprint = core.fingerprint({"targets": current["targets"], "masters": current["masters"]})
    require(dry.get("apply_ready") is True and dry.get("fingerprint") == fingerprint, "DRY_STALE_OR_NOT_READY")
    rows = current["targets"]
    require(all(row["plan"]["apply_ready"] for row in rows), "PLAN_NOT_READY")
    old = []
    for row in rows:
        mi = unreal.load_asset(row["path"])
        old.append({"path": row["path"], "figure": row["figure"], "plan": row["plan"],
                    "serialized_overrides": serialized(mi), "effective": effective_readback(mi, row["plan"])})
    record = {"schema": core.SCHEMA, "run_id": run, "state": "prepared", "saved": False,
              "config": cfg, "dry_fingerprint": fingerprint, "old": old}
    write_json(RECORD, record, exclusive=True)
    record["backup"] = backup(run, core.targets()); write_json(RECORD, record)
    changed = []
    for row in rows:
        mi = unreal.load_asset(row["path"]); expected = set_expected(mi, row, cfg)
        got = effective_readback(mi, row["plan"]); require(matches(got, expected), "APPLY_READBACK|" + row["path"])
        changed.append({"path": row["path"], "expected": expected, "readback_before_save": got})
    record["changed"] = changed; write_json(RECORD, record)
    saved = save_exact(core.targets())
    for changed_row, plan_row in zip(changed, rows):
        got = effective_readback(unreal.load_asset(changed_row["path"]), plan_row["plan"])
        require(matches(got, changed_row["expected"]), "AFTER_SAVE_READBACK|" + changed_row["path"])
        changed_row["readback_after_save"] = got
    settled = save_exact(core.targets())
    record.update({"state": "applied", "saved": True, "saved_packages": saved,
                   "readback_settle_saved_packages": settled, "changed": changed})
    write_json(RECORD, record)
    unreal.log("J122GARMENTS_APPLY_OK|run=%s|targets=12|saved=%d|settle_saved=%d|dirty=0|record=%s" %
               (run, len(saved), len(settled), RECORD))
    return record


def verify(run, cfg, record=None, emit=True):
    record = record or read_json(RECORD); clean_editor(); problems = []; rows = []
    for changed, old in zip(record["changed"], record["old"]):
        mi = unreal.load_asset(changed["path"])
        got = effective_readback(mi, old["plan"])
        if not matches(got, changed["expected"]):
            problems.append("DRIFT|" + changed["path"])
        rows.append({"path": changed["path"], "readback": got})
    dirty = census()
    if dirty != {"content": [], "maps": []}:
        problems.append("VERIFY_DIRTIED|" + json.dumps(dirty))
    result = {"schema": core.SCHEMA, "run_id": run, "mode": "VERIFY", "ok": not problems,
              "problems": problems, "rows": rows, "dirty_census": census(),
              "rendered_acceptance": "unproved"}
    write_json(VERIFY_OUT, result)
    if emit:
        unreal.log("J122GARMENTS_VERIFY_%s|run=%s|targets=12|problems=%d|report=%s" %
                   ("OK" if result["ok"] else "FAILED", run, len(problems), VERIFY_OUT))
    return result


def restore_touched_values(mi, old):
    """Restore only parameters APPLY touched; unrelated overrides remain byte-for-byte out of scope."""
    mel = unreal.MaterialEditingLibrary; plan = old["plan"]; detail = plan["detail"]; printing = plan["print"]
    layer = plan["active_layer"]["layer"]; values = old["effective"]
    for name, path in ((detail["color"], values["detail_color"]),
                       (detail["normal"], values["detail_normal"]),
                       (printing["map"], values["print_map"])):
        value = unreal.load_asset(path) if path else None
        require(path is None or value is not None, "RESTORE_TEXTURE_LOAD|" + str(path))
        mel.set_material_instance_texture_parameter_value(mi, name, value)
    mel.set_material_instance_scalar_parameter_value(mi, detail["tiling"], values["detail_tiling"])
    mel.set_material_instance_scalar_parameter_value(mi, printing["tiling"], values["print_tiling"])
    mel.set_material_instance_scalar_parameter_value(mi, printing["strength"], values["print_strength"])
    mel.set_material_instance_vector_parameter_value(
        mi, printing["colors"][layer], unreal.LinearColor(*values["print_color"]))
    mel.set_material_instance_static_switch_parameter_value(mi, detail["color_switch"], values["detail_color_switch"])
    mel.set_material_instance_static_switch_parameter_value(mi, detail["normal_switch"], values["detail_normal_switch"])
    mel.set_material_instance_static_switch_parameter_value(mi, printing["switch"], values["print_switch"])
    mel.update_material_instance(mi)


def revert(run, cfg):
    clean_editor(); record = read_json(RECORD)
    require(record.get("state") == "applied" and record.get("saved"), "RECORD_NOT_APPLIED")
    require(verify(run, cfg, record, emit=False)["ok"], "STATE_DRIFT")
    revert_backup = backup("REVERT-" + run, core.targets())
    for old in record["old"]:
        mi = unreal.load_asset(old["path"]); restore_touched_values(mi, old)
    saved = save_exact(core.targets())
    restored = []
    for old in record["old"]:
        mi = unreal.load_asset(old["path"]); got = effective_readback(mi, old["plan"])
        require(matches(got, old["effective"]), "REVERT_READBACK|" + old["path"])
        restored.append({"path": old["path"], "readback": got})
    settled = save_exact(core.targets())
    record["revert"] = {"run_id": run, "backup": revert_backup, "restored": restored,
                        "saved_packages": saved, "readback_settle_saved_packages": settled}
    record["state"] = "reverted"; write_json(RECORD, record)
    moved = RECORD + ".reverted-" + run; os.replace(RECORD, moved)
    unreal.log("J122GARMENTS_REVERT_OK|run=%s|targets=12|dirty=0|record=%s" % (run, moved))
    return record["revert"]


def main():
    run = datetime.datetime.now().strftime("J122GARMENTS-%Y%m%d-%H%M%S"); mode = "UNKNOWN"
    try:
        cfg = core.validate_args(read_json(ARGS), os.path.isfile(RECORD)); mode = cfg["mode"]
        unreal.log("J122GARMENTS_START|run=%s|mode=%s" % (run, mode))
        if mode == "PROBE": return probe(run, cfg)
        if mode == "DRY": return probe(run, cfg, DRY_OUT, "DRY")
        if mode == "APPLY": return apply(run, cfg)
        if mode == "VERIFY": return verify(run, cfg)
        return revert(run, cfg)
    except Exception as exc:
        dirty = {}
        try: dirty = census()
        except Exception: pass
        unreal.log_error("J122GARMENTS_FAILED|run=%s|mode=%s|%s|census=%s|NOTHING SAVED unless an *_OK marker printed|trace=%s" %
                         (run, mode, str(exc).replace("\n", " "), json.dumps(dirty),
                          traceback.format_exc().replace("\n", "\\n")))
        raise


if unreal is not None and __name__ == "<run_path>":
    main()
