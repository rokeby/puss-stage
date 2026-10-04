"""READ-ONLY whole-Show attachment audit (light GUIDs, counts, values).

Dumps, for every cue in the Show, its index, label, cue GUID, type, and every
Wing Pair attachment as:
  * ``state``  - the exact ``_infinity_attachment_state.attachment_state`` row
                 (the same row lighting_looks_apply.py hashes, so its
                 ``outside_before_hash`` can be recomputed offline);
  * ``export_text`` - the struct export text (same form as the Flat V3
                 swapkit preflights' ``pair_invariants.attachments``);
  * ``summary`` - guid, label, kind, is_light, enabled, intensity, colour,
                 temperature, location.

Writes Saved/CodexConductor/light_guid_audit_<stamp>.json (exclusive create)
and logs LIGHT_GUID_AUDIT_OK|run=<stamp>|... only after the dirty census is
asserted unchanged. No saves, no modify(), no setters, no replication, no
materialize: a static token check over this file refuses to run if any such
call name appears in it.

Optional init global (runpy / MCP prelude): LIGHT_GUID_AUDIT_SHOW_PATH to dump
a different Show asset (e.g. a staged copy of a Backups/ snapshot). Default is
the live Show.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline import for the static check / harness
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MARKER = "LIGHT_GUID_AUDIT"

# Built by concatenation so the table itself never matches the scan.
_FORBIDDEN = tuple(a + b for a, b in (
    ("save_", "asset"), ("save_", "current_level"), ("save_", "packages"),
    ("save_", "dirty"), ("save_", "map"), ("save_", "loaded"),
    (".mod", "ify("), ("set_editor_", "property"), ("set_editor_", "properties"),
    ("replicate_", "light"), ("materialize_", "passage"), ("materialize_", "structure"),
    ("reload_", "packages"), ("delete_", "asset"), ("delete_", "loaded"),
    ("execute_console_", "command"), ("call_", "method"), ("import_", "text("),
    ("rename_", "asset"), ("duplicate_", "asset"),
))


class AuditError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise AuditError(str(message))


def static_token_check(path=None):
    path = path or os.path.abspath(__file__)
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    hits = sorted({token for token in _FORBIDDEN if token in source})
    require(not hits, "FORBIDDEN_TOKENS_IN_AUDIT_SCRIPT|" + ",".join(hits))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _load_state_module():
    # Always load fresh from disk: editor Python keeps stale imports across runs.
    path = os.path.join(HERE, "_infinity_attachment_state.py")
    spec = importlib.util.spec_from_file_location("_light_guid_audit_state", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return module, digest


def _guid_text(value):
    # Identical to lighting_looks_apply._guid_text, so hashes are comparable.
    if unreal is not None:
        try:
            return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()
        except Exception:  # noqa: BLE001 - wrapper variants differ.
            pass
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def _asset_id(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name()).split(".", 1)[0]
    return str(value).split(".", 1)[0]


def _dirty_census():
    return {
        "content": sorted(_asset_id(p) for p in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(_asset_id(p) for p in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _export_text(value):
    exporter = getattr(value, "export_text", None)
    if callable(exporter):
        try:
            return str(exporter())
        except Exception as error:  # noqa: BLE001
            return "EXPORT_TEXT_FAILED:%s" % type(error).__name__
    return None


def _summary(state):
    lighting = state["lighting"]
    is_light = "LIGHT" in state["kind"].upper()
    return {
        "guid": state["guid"],
        "label": state["label"],
        "kind": state["kind"],
        "is_light": is_light,
        "enabled": state["enabled"],
        "intensity": lighting.get("intensity") if is_light else None,
        "color": lighting.get("color") if is_light else None,
        "temperature_kelvin": lighting.get("temperature_kelvin") if is_light else None,
        "location": state["relative_transform"]["location"],
    }


def _write_exclusive(path, value):
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def main():
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(HERE, "light_guid_audit_%s.json" % stamp)
    report = {"marker": MARKER, "run": stamp, "ok": False, "read_only": True}
    try:
        report["script_sha256"] = static_token_check()
        require(unreal is not None, "UNREAL_REQUIRED")
        state_module, state_sha = _load_state_module()
        report["attachment_state_module_sha256"] = state_sha
        show_path = str(globals().get("LIGHT_GUID_AUDIT_SHOW_PATH") or DEFAULT_SHOW_PATH)
        report["show_path"] = show_path

        census_before = _dirty_census()
        report["census_before"] = census_before
        report["show_dirty_at_start"] = show_path in census_before["content"]
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        report["pie_active"] = editor.get_game_world() is not None
        world = editor.get_editor_world()
        report["editor_world"] = _asset_id(world)

        show = unreal.EditorAssetLibrary.load_asset(show_path)
        require(show is not None, "SHOW_ASSET_MISSING|" + show_path)
        cues_out = []
        totals = {"cues": 0, "attachments": 0, "lights": 0}
        for index, cue in enumerate(list(show.get_editor_property("cues"))):
            pair = cue.get_editor_property("wing_pair")
            attachments = list(pair.get_editor_property("attachments"))
            rows = []
            for attachment in attachments:
                state = state_module.attachment_state(attachment, _guid_text)
                summary = _summary(state)
                rows.append({"state": state, "export_text": _export_text(attachment),
                             "summary": summary})
                totals["attachments"] += 1
                totals["lights"] += 1 if summary["is_light"] else 0
            cues_out.append({
                "index": index,
                "label": str(cue.get_editor_property("label")),
                "cue_guid": _guid_text(cue.get_editor_property("cue_guid")),
                "type": str(cue.get_editor_property("type")),
                "enabled": bool(cue.get_editor_property("enabled")),
                "attachment_count": len(rows),
                "light_count": sum(1 for row in rows if row["summary"]["is_light"]),
                "attachments": rows,
            })
            totals["cues"] += 1
            del pair, attachments
        del show

        census_after = _dirty_census()
        report["census_after"] = census_after
        require(census_after == census_before,
                "DIRTY_CENSUS_CHANGED|before=%s|after=%s" %
                (json.dumps(census_before, sort_keys=True),
                 json.dumps(census_after, sort_keys=True)))
        report.update({"ok": True, "totals": totals, "cues": cues_out,
                       "saved_state": not report["show_dirty_at_start"]})
        _write_exclusive(out_path, report)
        unreal.log("%s_OK|run=%s|cues=%d|attachments=%d|lights=%d|census_unchanged=1|"
                   "show_dirty_at_start=%d|output=%s" %
                   (MARKER, stamp, totals["cues"], totals["attachments"], totals["lights"],
                    int(report["show_dirty_at_start"]), out_path.replace("\\", "/")))
        return report
    except Exception as error:  # noqa: BLE001 - always leave a report.
        report["error"] = "%s: %s" % (type(error).__name__, error)
        report.pop("cues", None)
        try:
            _write_exclusive(out_path.replace(".json", "_STOPPED.json"), report)
        except Exception:  # noqa: BLE001
            pass
        if unreal is not None:
            unreal.log_error("%s_STOPPED|run=%s|%s" % (MARKER, stamp, report["error"]))
        raise


if unreal is not None:
    main()
else:
    print("static_token_check sha256=" + static_token_check())
