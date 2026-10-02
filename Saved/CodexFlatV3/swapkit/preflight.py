"""Read-only identity census for one configured Flat V3 passage swap."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    # purge this folder's cached modules: the editor's Python keeps modules across
    # scripts, so a stale verify/common ran (P06, 2 Oct). Entry scripts only.
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
c = importlib.reload(c)


def run(config_path=None):
    config = c.load_config(config_path)
    report = {"run": config["run_id"], "slot": config["slot"],
              "passage": config["passage"], "mode": "preflight"}
    if c.log_has("FLATV3_SLOT_RELEASED run=" + config["run_id"]):
        raise RuntimeError("RUN_ALREADY_RELEASED")
    c.assert_context(config, clean=True)
    if config["required_previous_marker"] and not c.log_has(config["required_previous_marker"]):
        raise RuntimeError("PREVIOUS_MARKER_NOT_FOUND|" + config["required_previous_marker"])
    mapping = c.load_mapping(config)
    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    c.passage_actor(config, show)
    cues = list(show.get_editor_property("cues"))
    targets = [(index, cue) for index, cue in enumerate(cues)
               if str(cue.get_editor_property("label")).startswith(config["passage_label_prefix"])]
    expected_count = int(config.get("expected_occurrence_count", 0))
    if not targets:
        raise RuntimeError("PASSAGE_IDENTITY_GATE_FAIL|prefix=" + config["passage_label_prefix"])
    if expected_count and len(targets) != expected_count:
        raise RuntimeError("PASSAGE_OCCURRENCE_COUNT_FAIL|expected=%d|actual=%d" %
                           (expected_count, len(targets)))
    guids = [c.cue_guid(cue) for _, cue in targets]
    if any(not guid for guid in guids) or len(guids) != len(set(guids)):
        raise RuntimeError("DUPLICATE_PASSAGE_GUID")
    unknown_keep_guids = sorted({entry["cue_guid"] for entry in config["keep_old_sides"]} -
                                set(guids))
    if unknown_keep_guids:
        raise RuntimeError("UNKNOWN_KEEP_OLD_GUID|" + json.dumps(unknown_keep_guids))

    rows = []
    for index, cue in targets:
        label = str(cue.get_editor_property("label"))
        pair = cue.get_editor_property("wing_pair")
        rows.append({
            "cue_index": index, "cue_label": label,
            "cue_guid": c.cue_guid(cue),
            "left": c.panel_plain(pair.get_editor_property("left")),
            "right": c.panel_plain(pair.get_editor_property("right")),
            "top": c.panel_plain(pair.get_editor_property("top")),
            "occurrence_offset": c.transform_plain(pair.get_editor_property("occurrence_offset")),
            "mechanism": c.mechanism_plain(pair.get_editor_property("mechanism")),
        })
    end = c.census()
    if end != c.CLEAN:
        raise RuntimeError("PREFLIGHT_DIRTIED_EDITOR|census=" + json.dumps(end, sort_keys=True))
    report.update({"status": "PASS", "world": c.WORLD, "show": c.SHOW,
                   "config_path": config["_path"], "mapping_file": config["mapping_file"],
                   "mapping_kind": mapping["kind"], "rows": rows,
                   "overreach_tolerance_cm": config["overreach_tolerance_cm"],
                   "keep_old_sides": config["keep_old_sides"],
                   "row_count": len(rows), "dirty_at_start": c.CLEAN, "dirty_after": end})
    path = c.write_json(config, "preflight", report)
    unreal.log("%s run=%s rows=%d census=%s report=%s" %
               (c.marker(config, "PREFLIGHT_OK"), config["run_id"], len(rows),
                json.dumps(end, separators=(",", ":"), sort_keys=True), path))
    return report


def main(config_path=None):
    config = None
    try:
        config = c.load_config(config_path)
        return run(config["_path"])
    except Exception as exc:
        if config is not None:
            report = {"run": config["run_id"], "mode": "preflight", "status": "FAIL",
                      "reason": str(exc), "traceback": traceback.format_exc(),
                      "census": c.census()}
            c.write_json(config, "preflight", report, failure=True)
            c.log_release(config, "FAIL", [], "preflight:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
