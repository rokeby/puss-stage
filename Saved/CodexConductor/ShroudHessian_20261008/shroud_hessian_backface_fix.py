"""Job 121: guarded additive back-face normal fix for M_Shroud_Hessian.

Modes are DRY / APPLY / REVERT.  This file must be executed inside UE 5.8 by
the conductor; importing it offline does not import ``unreal``.  APPLY never
deletes a material expression.  It records the original Normal terminal, adds
a TwoSidedSign and marked Custom expression, and rewires only MP_NORMAL.
REVERT reconnects the recorded terminal and intentionally leaves added nodes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time


HERE = os.path.dirname(os.path.abspath(__file__)) + os.sep
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", "..")) + os.sep
ARGS = os.environ.get("SHROUD_BACKFACE_ARGS", HERE + "shroud_hessian_backface_args.json")
RECORD = HERE + "shroud_hessian_backface_record.json"
TARGET = "/Game/Metahuman/ShoreCast_20260910/ShroudHessian/Materials/M_Shroud_Hessian"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MODES = ("DRY", "APPLY", "REVERT")
CONFIRM = {"APPLY": "APPLY SHROUD HESSIAN BACKFACE",
           "REVERT": "REVERT SHROUD HESSIAN BACKFACE"}
NODE_MARKER = "JOB121_SHROUD_BACKFACE_NORMAL_FLIP"
NORMAL_CODE = "return N * float3(1.0,1.0,TwoSided);"
DEFAULT_COMPILE_WAIT_SECONDS = 20.0


class Job121Error(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Job121Error(message)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args(data, record_exists=False):
    mode = str(data.get("mode", "")).upper()
    require(mode in MODES, "MODE|" + mode)
    run = str(data.get("run", ""))
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,79}", run)), "RUN_ID|" + run)
    require(run not in ("CONDUCTOR_SUPPLIES_RUN_ID", "NO_RUN"), "RUN_ID_PLACEHOLDER")
    wait = float(data.get("compile_wait_seconds", DEFAULT_COMPILE_WAIT_SECONDS))
    require(5.0 <= wait <= 120.0, "COMPILE_WAIT|%s" % wait)
    if mode in CONFIRM:
        require(data.get("confirm") == CONFIRM[mode], "CONFIRM|expected " + CONFIRM[mode])
    if mode == "APPLY":
        require(not record_exists, "ACTIVE_RECORD_EXISTS")
    if mode == "REVERT":
        require(record_exists, "NO_APPLY_RECORD")
    return {"mode": mode, "run": run, "compile_wait_seconds": wait}


def compile_log_errors(lines):
    """Return post-marker LogMaterial errors; unrelated categories do not fail."""
    bad = []
    for line in lines:
        lower = line.lower()
        if "logmaterial" not in lower:
            continue
        if (re.search(r"logmaterial:\s*(error|fatal):", lower) or
                "failed to compile" in lower or "default material will be used" in lower):
            bad.append(line.strip())
    return bad


def state_problems(state, expected):
    problems = []
    for key, value in expected.get("flags", {}).items():
        if state.get("flags", {}).get(key) != value:
            problems.append("FLAG|%s|got=%r|want=%r" % (key, state.get("flags", {}).get(key), value))
    terminal = state.get("normal", {}).get("terminal") or {}
    want_terminal = expected.get("terminal") or {}
    for key in ("name", "class", "output"):
        if want_terminal.get(key) is not None and terminal.get(key) != want_terminal.get(key):
            problems.append("NORMAL_TERMINAL|%s|got=%r|want=%r" % (key, terminal.get(key), want_terminal.get(key)))
    if "upstream" in expected:
        got = {x.get("pin"): x for x in state.get("normal", {}).get("upstream", [])}
        for pin, want in expected["upstream"].items():
            row = got.get(pin) or {}
            for key, value in want.items():
                if row.get(key) != value:
                    problems.append("NORMAL_UPSTREAM|%s.%s|got=%r|want=%r" % (pin, key, row.get(key), value))
    return problems


def _u():
    import unreal
    return unreal


def _asset_path(obj):
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def _node_ref(node, output=None):
    if node is None:
        return None
    return {"name": str(node.get_name()), "path": str(node.get_path_name()),
            "class": str(node.get_class().get_name()), "output": output}


def _census():
    u = _u()
    lib = u.EditorLoadingAndSavingUtils
    return {"content": sorted(str(x.get_name()) for x in lib.get_dirty_content_packages()),
            "maps": sorted(str(x.get_name()) for x in lib.get_dirty_map_packages())}


def _guard(write=False):
    u = _u()
    require(not list(u.EditorLevelLibrary.get_pie_worlds(False)), "PIE_RUNNING_STOP_AND_REPORT")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    require(world is not None and _asset_path(world) == WORLD, "WORLD|%s" % _asset_path(world))
    if write:
        require(_census() == {"content": [], "maps": []}, "DIRTY_BEFORE|%s" % json.dumps(_census()))


def _package_file():
    u = _u()
    root = str(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    return os.path.join(root, TARGET[len("/Game/"):].replace("/", os.sep) + ".uasset")


def _backup(tag, run):
    src = _package_file()
    require(os.path.isfile(src), "BACKUP_SOURCE|" + src)
    folder = os.path.join(PROJECT, "Backups", "Pre%s-%s" % (tag, run))
    require(not os.path.exists(folder), "BACKUP_EXISTS|" + folder)
    os.makedirs(folder)
    dst = os.path.join(folder, os.path.basename(src))
    shutil.copy2(src, dst)
    require(sha256_file(src) == sha256_file(dst), "BACKUP_HASH|" + src)
    manifest = {"run": run, "target": TARGET, "source": src, "copy": dst, "sha256": sha256_file(src)}
    write_json(os.path.join(folder, "backup_manifest.json"), manifest)
    return manifest


def _node_description(node):
    for prop in ("description", "desc"):
        try:
            value = str(node.get_editor_property(prop))
            if value:
                return value
        except Exception:
            pass
    return ""


def _marked_nodes(mat):
    u = _u()
    return [n for n in u.MaterialEditingLibrary.get_material_expressions(mat)
            if NODE_MARKER in _node_description(n)]


def _readback(mat):
    u, mel = _u(), _u().MaterialEditingLibrary
    mp = u.MaterialProperty.MP_NORMAL
    terminal = mel.get_material_property_input_node(mat, mp)
    output = None if terminal is None else str(mel.get_material_property_input_node_output_name(mat, mp))
    upstream = []
    if terminal is not None:
        names = [str(x) for x in mel.get_material_expression_input_names(terminal)]
        nodes = list(mel.get_inputs_for_material_expression(mat, terminal))
        if len(names) == len(nodes):
            for pin, node in zip(names, nodes):
                row = _node_ref(node) or {"name": None, "path": None, "class": None, "output": None}
                row["pin"] = pin
                upstream.append(row)
    return {"asset": _asset_path(mat),
            "flags": {k: bool(mat.get_editor_property(k)) for k in
                      ("two_sided", "used_with_clothing", "used_with_skeletal_mesh")},
            "normal": {"terminal": _node_ref(terminal, output), "upstream": upstream,
                       "marked_nodes": [_node_ref(n) for n in _marked_nodes(mat)]},
            "dirty_census": _census()}


def _find_node(mat, ref):
    u = _u()
    hits = [n for n in u.MaterialEditingLibrary.get_material_expressions(mat)
            if str(n.get_name()) == ref.get("name") and str(n.get_class().get_name()) == ref.get("class")]
    require(len(hits) == 1, "RECORDED_NODE|%s|hits=%d" % (ref, len(hits)))
    return hits[0]


def _compile_and_check(mat, run, mode, wait):
    u, mel = _u(), _u().MaterialEditingLibrary
    marker = "JOB121_COMPILE_START|run=%s|mode=%s|asset=%s" % (run, mode, TARGET)
    u.log(marker)
    immediate = [str(x) for x in (mel.recompile_material(mat) or [])]
    require(not immediate, "COMPILE_RETURN|%r" % immediate)
    time.sleep(wait)
    log_path = os.path.join(PROJECT, "Saved", "Logs", "PussStage.log")
    require(os.path.isfile(log_path), "LOG_MISSING|" + log_path)
    with open(log_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    pos = text.rfind(marker)
    require(pos >= 0, "COMPILE_MARKER_NOT_IN_LOG|" + marker)
    lines = text[pos:].splitlines()
    bad = compile_log_errors(lines)
    require(not bad, "LOGMATERIAL_ERRORS|%s" % json.dumps(bad[:12]))
    return {"marker": marker, "wait_seconds": wait, "logmaterial_errors": bad,
            "lines_scanned": len(lines)}


def _save_only_target():
    u = _u()
    want = {"content": [TARGET], "maps": []}
    before = _census()
    require(before == want, "DIRTY_SCOPE|got=%s|want=%s" % (json.dumps(before), json.dumps(want)))
    require(u.EditorAssetLibrary.save_asset(TARGET, only_if_is_dirty=False), "SAVE_ASSET|" + TARGET)
    require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(_census()))
    return before


def _write_report(mode, run, payload):
    path = HERE + "job121_%s_%s.json" % (mode.lower(), run)
    write_json(path, payload)
    return path


def _dry(opts):
    u = _u()
    require(u.EditorAssetLibrary.does_asset_exist(TARGET), "TARGET_MISSING|" + TARGET)
    mat = u.load_asset(TARGET)
    result = {"run": opts["run"], "mode": "DRY", "target": TARGET,
              "active_record": os.path.isfile(RECORD), "readback": _readback(mat)}
    result["report"] = _write_report("DRY", opts["run"], result)
    u.log("JOB121_DRY_OK|run=%s|target=%s|record=%s" % (opts["run"], TARGET, result["active_record"]))
    return result


def _apply(opts):
    u, mel = _u(), _u().MaterialEditingLibrary
    require(u.EditorAssetLibrary.does_asset_exist(TARGET), "TARGET_MISSING|" + TARGET)
    mat = u.load_asset(TARGET)
    before = _readback(mat)
    require(before["normal"]["terminal"] is not None, "NORMAL_UNCONNECTED")
    require(before["flags"]["two_sided"], "TWO_SIDED_NOT_TRUE")
    require(before["flags"]["used_with_clothing"], "CLOTHING_NOT_TRUE")
    require(not before["normal"]["marked_nodes"], "MARKED_NODES_ALREADY_EXIST")
    rec = {"run": opts["run"], "target": TARGET, "status": "recorded", "before": before,
           "saved": False, "normal_original": before["normal"]["terminal"]}
    write_json(RECORD, rec, exclusive=True)
    rec["backup"] = _backup("ShroudHessianBackface", opts["run"])
    write_json(RECORD, rec)

    mat.modify()
    original = _find_node(mat, rec["normal_original"])
    sign = mel.create_material_expression(mat, u.MaterialExpressionTwoSidedSign, 250, -650)
    flip = mel.create_material_expression(mat, u.MaterialExpressionCustom, 520, -650)
    require(sign is not None and flip is not None, "CREATE_NODES")
    sign.set_editor_property("desc", NODE_MARKER + "|TwoSidedSign")
    flip.set_editor_property("description", NODE_MARKER + "|NormalFlip")
    flip.set_editor_property("code", NORMAL_CODE)
    flip.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = []
    for name in ("N", "TwoSided"):
        pin = u.CustomInput()
        pin.set_editor_property("input_name", name)
        pins.append(pin)
    flip.set_editor_property("inputs", pins)
    # UE editor setters can report false despite succeeding.  Do not gate on
    # their return values; the explicit terminal/upstream read-back below is
    # the authority.
    mel.connect_material_expressions(original, rec["normal_original"].get("output") or "", flip, "N")
    mel.connect_material_expressions(sign, "", flip, "TwoSided")
    mel.connect_material_property(flip, "", u.MaterialProperty.MP_NORMAL)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_clothing", True)
    mat.set_editor_property("used_with_skeletal_mesh", True)
    compile_result = _compile_and_check(mat, opts["run"], "APPLY", opts["compile_wait_seconds"])
    expected = {"flags": {"two_sided": True, "used_with_clothing": True, "used_with_skeletal_mesh": True},
                "terminal": {"class": "MaterialExpressionCustom"},
                "upstream": {"N": {"name": rec["normal_original"]["name"], "class": rec["normal_original"]["class"]},
                             "TwoSided": {"class": "MaterialExpressionTwoSidedSign"}}}
    live = _readback(mat)
    require(NODE_MARKER in _node_description(mel.get_material_property_input_node(mat, u.MaterialProperty.MP_NORMAL)),
            "NORMAL_TERMINAL_NOT_MARKED")
    require(not state_problems(live, expected), "APPLY_READBACK|%s" % state_problems(live, expected))
    rec["dirty_before_save"] = _save_only_target()
    # Persist the targeted save before the second read-back.  If that gate
    # fails, REVERT must remain available with the recorded original terminal.
    rec.update({"status": "saved_pending_readback", "saved": True, "compile": compile_result})
    write_json(RECORD, rec)
    after = _readback(u.load_asset(TARGET))
    require(not state_problems(after, expected), "APPLY_AFTER_SAVE|%s" % state_problems(after, expected))
    rec.update({"status": "applied", "saved": True, "compile": compile_result, "after": after})
    write_json(RECORD, rec)
    report = _write_report("APPLY", opts["run"], rec)
    u.log("JOB121_APPLY_OK|run=%s|saved=%s|normal=%s|skeletal=1|clothing=1|report=%s" %
          (opts["run"], TARGET, after["normal"]["terminal"]["name"], report))
    return rec


def _revert(opts):
    u, mel = _u(), _u().MaterialEditingLibrary
    rec = read_json(RECORD)
    require(rec.get("saved") and rec.get("status") in ("applied", "saved_pending_readback"), "RECORD_NOT_APPLIED")
    require(rec.get("target") == TARGET, "RECORD_TARGET|%r" % rec.get("target"))
    mat = u.load_asset(TARGET)
    current = _readback(mat)
    require(current["normal"]["terminal"] and
            current["normal"]["terminal"]["class"] == "MaterialExpressionCustom", "CURRENT_NORMAL_NOT_FIX")
    require(current["normal"]["marked_nodes"], "CURRENT_MARKER_MISSING")
    backup = _backup("ShroudHessianBackfaceRevert", opts["run"])
    original = _find_node(mat, rec["normal_original"])
    mat.modify()
    # As in APPLY, the setter return is not authoritative; verify below.
    mel.connect_material_property(original, rec["normal_original"].get("output") or "",
                                  u.MaterialProperty.MP_NORMAL)
    for key, value in rec["before"]["flags"].items():
        mat.set_editor_property(key, bool(value))
    require(bool(mat.get_editor_property("used_with_clothing")), "REVERT_WOULD_DISABLE_CLOTHING")
    compile_result = _compile_and_check(mat, opts["run"], "REVERT", opts["compile_wait_seconds"])
    expected = {"flags": rec["before"]["flags"], "terminal": rec["normal_original"]}
    live = _readback(mat)
    require(not state_problems(live, expected), "REVERT_READBACK|%s" % state_problems(live, expected))
    dirty = _save_only_target()
    after = _readback(u.load_asset(TARGET))
    require(not state_problems(after, expected), "REVERT_AFTER_SAVE|%s" % state_problems(after, expected))
    rec.update({"status": "reverted", "revert_run": opts["run"], "revert_backup": backup,
                "revert_compile": compile_result, "revert_dirty_before_save": dirty, "revert_after": after})
    write_json(RECORD, rec)
    report = _write_report("REVERT", opts["run"], rec)
    archived = RECORD + ".reverted-" + opts["run"]
    require(not os.path.exists(archived), "REVERT_ARCHIVE_EXISTS|" + archived)
    os.replace(RECORD, archived)
    u.log("JOB121_REVERT_OK|run=%s|saved=%s|normal=%s|clothing=1|record=%s|report=%s" %
          (opts["run"], TARGET, after["normal"]["terminal"]["name"], archived, report))
    return rec


def main():
    u = _u()
    run, mode = "NO_RUN", "NO_MODE"
    try:
        opts = parse_args(read_json(ARGS), os.path.isfile(RECORD))
        run, mode = opts["run"], opts["mode"]
        u.log("JOB121_START|run=%s|mode=%s|target=%s" % (run, mode, TARGET))
        _guard(write=mode in ("APPLY", "REVERT"))
        return _dry(opts) if mode == "DRY" else (_apply(opts) if mode == "APPLY" else _revert(opts))
    except Exception as exc:
        # Archive, never delete, an unsaved failed attempt.  A saved record
        # stays active so its recorded original terminal can still be reverted.
        if mode == "APPLY" and os.path.isfile(RECORD):
            try:
                failed = read_json(RECORD)
                if not failed.get("saved"):
                    archived = RECORD + ".failed-" + run
                    if not os.path.exists(archived):
                        os.replace(RECORD, archived)
            except Exception:
                pass
        census = {}
        try:
            census = _census()
        except Exception:
            pass
        u.log_error("JOB121_FAILED|run=%s|mode=%s|%s|census=%s|NOTHING SAVED unless JOB121_*_OK printed" %
                    (run, mode, str(exc).replace("\n", " "), json.dumps(census)))
        raise


if __name__ == "__main__":
    main()
