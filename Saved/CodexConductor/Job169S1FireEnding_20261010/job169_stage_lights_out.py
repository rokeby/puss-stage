"""Job 169 stage B: retime Job 29's applied S1 rig-fade to frames 3800-3838."""
import json
import os

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.normpath(os.path.join(HERE, "..", "S1RigFade_20261009", "s1_rig_fade.py"))
TAIL = "\nif unreal is not None:\n    main()"
SOURCE_RECORD = os.path.normpath(os.path.join(HERE, "..", "S1RigFade_20261009", "s1_rig_fade_record.json"))
SOURCE_SWITCH_FRAME = 783


def _asset_path(value):
    return "" if value is None else value.get_path_name().split(".", 1)[0]


def _load_legacy():
    with open(LEGACY, "r", encoding="utf-8") as handle:
        source = handle.read().rstrip()
    if source.endswith(TAIL.strip()):
        source = source[:-len(TAIL.strip())]
    elif "def main(args):" not in source:
        raise RuntimeError("LEGACY_SHAPE_CHANGED")
    namespace = {"__name__": "job169_s1_rig_fade_definitions", "__file__": LEGACY}
    exec(compile(source, LEGACY, "exec"), namespace)
    if any(name not in namespace for name in ("merged_params", "run_dry", "run_apply", "run_revert")):
        raise RuntimeError("LEGACY_HELPERS_MISSING")
    namespace["_here"] = lambda: HERE

    def live_local_clock(params, run):
        master = unreal.load_asset(params["master_sequence"])
        hits = []
        for track in master.get_tracks():
            for section in track.get_sections():
                try:
                    if _asset_path(section.get_sequence()) == namespace["SEQ_PATH"]:
                        hits.append(section)
                except Exception:
                    pass
        if len(hits) != 1:
            namespace["_stop"](run, "MASTER_S1_SECTION_COUNT|%d" % len(hits))
        section = hits[0]
        start, end = float(section.get_start_frame_seconds()), float(section.get_end_frame_seconds())
        frame = int(params["expected_target_scene_frame"])
        mapping = namespace["map_master_time"](
            start + frame / float(namespace["EXPECTED_FPS"]), start, namespace["EXPECTED_FPS"], end)
        mapping.update({"master_sequence": params["master_sequence"],
                        "scene_sequence": namespace["SEQ_PATH"], "job169_local_frame_authority": True})
        return mapping

    namespace["_master_clock"] = live_local_clock
    return namespace


def _params(args):
    end = int(round(int(args["lights_out_start_frame"]) + float(args["lights_out_fade_seconds"]) * 25.0))
    return {
        "review_time_seconds": 0.0,
        "master_sequence": "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master",
        "expected_master_section_start_seconds": 0.0,
        "expected_target_scene_frame": end,
        # Job 29 already moved the reviewed 269/282 switches to Master 3:44,
        # which is S1-local frame 783.  Job 169 must select that exact applied
        # transaction, not rescan the obsolete source window or add duplicates.
        "scene_local_switch_frame": SOURCE_SWITCH_FRAME,
        "search_radius_frames": 20,
        "fade_seconds": float(args["lights_out_fade_seconds"]),
        "min_fade_seconds": 1.0,
        "max_fade_seconds": 2.0,
        "value_tolerance": 0.0001,
        "bulb_prefix": "S1 Lattice Bulb ",
        "glow_prefix": "S1 Lattice Glow ",
    }


def _source_record(namespace, seq, params, run):
    if not os.path.isfile(SOURCE_RECORD):
        namespace["_stop"](run, "SOURCE_RIG_FADE_RECORD_MISSING|%s" % SOURCE_RECORD)
    with open(SOURCE_RECORD, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    plan = record.get("plan") or {}
    operations = list(record.get("operations") or [])
    targets = list(plan.get("targets") or [])
    visibility_ops = [row for row in operations if row.get("kind") == "retime_visibility"]
    ramp_ops = [row for row in operations if row.get("kind") == "new_track"]
    if (not record.get("applied") or plan.get("target_switch_frame") != SOURCE_SWITCH_FRAME
            or len(targets) != 28 or len(visibility_ops) != 28 or len(ramp_ops) != 28):
        namespace["_stop"](run, "SOURCE_RIG_FADE_RECORD_SHAPE|applied=%s|target=%s|targets=%d|visibility=%d|ramps=%d" %
                           (record.get("applied"), plan.get("target_switch_frame"), len(targets),
                            len(visibility_ops), len(ramp_ops)))
    bindings = namespace["_binding_map"](seq)
    for operation in operations:
        binding = bindings.get(operation.get("binding_guid"))
        if binding is None:
            namespace["_stop"](run, "SOURCE_RIG_FADE_BINDING_GONE|%s" % operation.get("binding_guid"))
        _locate_recorded_track(namespace, seq, binding, operation["track_after"], run)
    end = int(params["expected_target_scene_frame"])
    start = end - int(params["fade_frames"])
    retimed = []
    for row in targets:
        item = dict(row)
        item.update({"source_switch_frame": SOURCE_SWITCH_FRAME, "switch_frame": end,
                     "fade_start_frame": start, "fade_frames": int(params["fade_frames"])})
        retimed.append(item)
    return record, {
        "source_search_window": [SOURCE_SWITCH_FRAME, SOURCE_SWITCH_FRAME],
        "source_record": SOURCE_RECORD,
        "source_record_run": record.get("run"),
        "source_record_switch_frame": SOURCE_SWITCH_FRAME,
        "target_switch_frame": end,
        "fade_seconds": float(params["fade_seconds"]),
        "fade_frames": int(params["fade_frames"]),
        "targets": retimed,
        "unsupported": [],
    }


def _locate_track_identity(namespace, binding, spec, run):
    """Locate by stable binding/track identity without walking unrelated keys."""
    candidates = []
    for track in binding.get_tracks():
        if track.get_class().get_name() != spec.get("class"):
            continue
        if namespace["_track_property"](track) != (spec.get("property", ""), spec.get("path", "")):
            continue
        if str(track.get_display_name()) != str(spec.get("display_name", "")):
            continue
        candidates.append(track)
    if len(candidates) != 1:
        namespace["_stop"](run, "RECORDED_TRACK_IDENTITY_COUNT|binding=%s|property=%s|count=%d" %
                           (binding.get_display_name(), spec.get("property"), len(candidates)))
    return candidates[0]


def _locate_recorded_track(namespace, seq, binding, spec, run):
    track = _locate_track_identity(namespace, binding, spec, run)
    if namespace["_track_row"](track, seq) != spec:
        namespace["_stop"](run, "RECORDED_TRACK_DRIFT|binding=%s|property=%s" %
                           (binding.get_display_name(), spec.get("property")))
    return track


def _light_snapshot(namespace, seq, specs, run):
    """Strict bounded manifest: all identities plus full rows for the 56 owned tracks."""
    def rate(value):
        return [int(value.numerator), int(value.denominator)]
    binding_rows = []
    bindings = namespace["_binding_map"](seq)
    for binding in seq.get_bindings():
        identities = []
        for track in binding.get_tracks():
            prop, path = namespace["_track_property"](track)
            identities.append({"class": track.get_class().get_name(),
                               "display_name": str(track.get_display_name()),
                               "property": prop, "path": path,
                               "sections": len(list(track.get_sections()))})
        identities.sort(key=lambda row: (row["class"], row["property"], row["path"], row["display_name"]))
        parent = binding.get_parent()
        binding_rows.append({"guid": namespace["_guid"](binding.get_id()),
                             "name": str(binding.get_display_name()),
                             "parent": namespace["_guid"](parent.get_id()) if parent else None,
                             "tracks": identities})
    binding_rows.sort(key=lambda row: row["guid"])
    root_rows = []
    for track in seq.get_tracks():
        prop, path = namespace["_track_property"](track)
        root_rows.append({"class": track.get_class().get_name(), "display_name": str(track.get_display_name()),
                          "property": prop, "path": path, "sections": len(list(track.get_sections()))})
    root_rows.sort(key=lambda row: (row["class"], row["property"], row["path"], row["display_name"]))
    owned = []
    for index, item in enumerate(specs):
        binding = bindings.get(item["binding_guid"])
        if binding is None:
            namespace["_stop"](run, "OWNED_BINDING_GONE|%s" % item["binding_guid"])
        track = _locate_recorded_track(namespace, seq, binding, item["track"], run)
        owned.append({"index": index, "binding_guid": item["binding_guid"],
                      "track": namespace["_track_row"](track, seq)})
    return {"display_rate": rate(seq.get_display_rate()), "tick_resolution": rate(seq.get_tick_resolution()),
            "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
            "root_tracks": root_rows, "bindings": binding_rows, "owned_tracks": owned}


def _source_specs(source):
    return [{"binding_guid": row["binding_guid"], "track": row["track_after"]}
            for row in source["operations"]]


def _report(namespace, params, run):
    seq = namespace["_load_sequence"](run)
    source, plan = _source_record(namespace, seq, params, run)
    snapshot = _light_snapshot(namespace, seq, _source_specs(source), run)
    clock = namespace["_master_clock"](params, run)
    payload = {"schema_version": 2, "tool_version": "job169-existing-rig-fade-v1",
               "tool": "S1_RIG_FADE", "run": run, "mode": "DRY",
               "sequence": namespace["SEQ_PATH"], "params": params, "master_clock": clock,
               "plan": plan, "snapshot": snapshot, "snapshot_digest": namespace["digest"](snapshot),
               "source_record_digest": namespace["digest"](source), "census": namespace["_census"](),
               "apply_ready": True}
    payload["plan_digest"] = namespace["digest"]({"plan": plan, "master_clock": clock,
                                                    "source_record_digest": payload["source_record_digest"]})
    return seq, source, payload


def _dry_path(run):
    return os.path.join(HERE, "job169_lights_out_dry_%s.json" % run)


def _plan_path():
    return os.path.join(HERE, "job169_lights_out_plan.json")


def _record_path():
    return os.path.join(HERE, "s1_rig_fade_record.json")


def _run_dry(namespace, run, params):
    namespace["_preflight"]("DRY", run, "DRY S1RIGFADE")
    _seq, _source, report = _report(namespace, params, run)
    namespace["_json_write"](_dry_path(run), report)
    namespace["_json_write"](_plan_path(), {"run": run, "plan_digest": report["plan_digest"],
                                              "snapshot_digest": report["snapshot_digest"]})
    if namespace["_census"]() != {"content": [], "maps": []}:
        namespace["_stop"](run, "DRY_DIRTIED|%s" % json.dumps(namespace["_census"](), sort_keys=True))
    namespace["_print_targets"](run, report["plan"])
    namespace["_log"]("S1_RIG_FADE_DRY_OK|run=%s|mutated=0|apply_ready=1|targets=%d|source_frames=[783, 783]|target_frame=%d|fade_frames=%d|report=%s" %
                      (run, len(report["plan"]["targets"]), report["plan"]["target_switch_frame"],
                       report["plan"]["fade_frames"], _dry_path(run)))
    return report


def _retime_existing(namespace, seq, source, plan, run):
    ue = unreal
    bindings = namespace["_binding_map"](seq)
    operations = []
    for source_op in source["operations"]:
        binding = bindings.get(source_op["binding_guid"])
        if binding is None:
            namespace["_stop"](run, "SOURCE_RIG_FADE_BINDING_GONE|%s" % source_op["binding_guid"])
        track = _locate_recorded_track(namespace, seq, binding, source_op["track_after"], run)
        before = namespace["_track_row"](track, seq)
        if source_op["kind"] == "retime_visibility":
            sections = list(track.get_sections())
            index = int(source_op["section_index"])
            if index >= len(sections) or namespace["_section_range"](sections[index], seq) != source_op["range_after"]:
                namespace["_stop"](run, "SOURCE_VISIBILITY_RANGE_DRIFT|%s" % source_op["binding_guid"])
            old_range = list(source_op["range_after"])
            sections[index].set_range(int(plan["target_switch_frame"]), int(old_range[1]))
            subtype = "visibility"
        else:
            sections = list(track.get_sections())
            if len(sections) != 1 or len(list(sections[0].get_all_channels())) != 1:
                namespace["_stop"](run, "SOURCE_RAMP_SHAPE|%s" % source_op["binding_guid"])
            section = sections[0]
            keys = list(list(section.get_all_channels())[0].get_keys())
            rows = [namespace["_key_row"](key) for key in keys]
            if len(keys) != 2 or [row["frame"] for row in rows] != [745, SOURCE_SWITCH_FRAME]:
                namespace["_stop"](run, "SOURCE_RAMP_KEYS_DRIFT|%s|%s" %
                                   (source_op["binding_guid"], [row["frame"] for row in rows]))
            keys[0].set_time(ue.FrameNumber(int(plan["target_switch_frame"] - plan["fade_frames"])), 0.0,
                             ue.MovieSceneTimeUnit.DISPLAY_RATE)
            keys[1].set_time(ue.FrameNumber(int(plan["target_switch_frame"])), 0.0,
                             ue.MovieSceneTimeUnit.DISPLAY_RATE)
            section.set_range(int(plan["target_switch_frame"] - plan["fade_frames"]),
                              int(plan["target_switch_frame"] + 1))
            subtype = "ramp"
        operations.append({"kind": "retime", "subtype": subtype,
                           "binding_guid": source_op["binding_guid"],
                           "property": source_op.get("property"), "track_before": before,
                           "track_after": namespace["_track_row"](track, seq)})
    return operations


def _run_apply(namespace, run, params):
    namespace["_preflight"]("APPLY", run, "APPLY S1RIGFADE")
    seq, source, report = _report(namespace, params, run)
    state = namespace["_json_read"](_plan_path(), required=True)
    if state.get("plan_digest") != report["plan_digest"] or state.get("snapshot_digest") != report["snapshot_digest"]:
        namespace["_stop"](run, "CHANGED_SINCE_DRY|rerun DRY")
    backup = namespace["_backup"](run)
    transaction = os.path.join(HERE, "job169_lights_out_transaction_%s.json" % run)
    record = {"schema_version": 2, "tool": "S1_RIG_FADE", "run": run, "applied": False,
              "written_before_mutation": True, "sequence": namespace["SEQ_PATH"], "params": params,
              "plan": report["plan"], "source_record": SOURCE_RECORD,
              "source_record_digest": report["source_record_digest"], "backup": backup,
              "snapshot_before": report["snapshot"], "snapshot_before_digest": report["snapshot_digest"],
              "operations": []}
    namespace["_json_write"](transaction, record)
    record["operations"] = _retime_existing(namespace, seq, source, report["plan"], run)
    after_specs = [{"binding_guid": row["binding_guid"], "track": row["track_after"]}
                   for row in record["operations"]]
    after = _light_snapshot(namespace, seq, after_specs, run)
    for key in ("display_rate", "tick_resolution", "playback", "root_tracks", "bindings"):
        if report["snapshot"][key] != after[key]:
            namespace["_stop"](run, "UNSCOPED_MANIFEST_CHANGE|%s" % key)
    record.update({"snapshot_after": after, "snapshot_after_digest": namespace["digest"](after), "applied": True})
    namespace["_json_write"](transaction, record)
    saves = namespace["_save"](run)
    readback = _light_snapshot(namespace, namespace["_load_sequence"](run), after_specs, run)
    if readback != after:
        namespace["_stop"](run, "POSTSAVE_READBACK_MISMATCH|restore=%s" % backup["root"])
    record.update({"saves": saves, "census_after": namespace["_census"](), "saved_readback": readback,
                   "saved_readback_digest": namespace["digest"](readback)})
    namespace["_json_write"](_record_path(), record)
    namespace["_json_write"](transaction, dict(record, transaction_complete=True))
    namespace["_print_targets"](run, report["plan"])
    namespace["_log"]("S1_RIG_FADE_APPLY_OK|run=%s|targets=%d|saved=%s|backup=%s|record=%s|readback=%s" %
                      (run, len(report["plan"]["targets"]), ",".join(saves), backup["root"],
                       _record_path(), record["saved_readback_digest"][:16]))
    return record


def _run_revert(namespace, run, params):
    del params
    namespace["_preflight"]("REVERT", run, "REVERT S1RIGFADE")
    record = namespace["_json_read"](_record_path(), required=True)
    seq = namespace["_load_sequence"](run)
    after_specs = [{"binding_guid": row["binding_guid"], "track": row["track_after"]}
                   for row in record.get("operations", [])]
    live = _light_snapshot(namespace, seq, after_specs, run)
    if not record.get("applied") or namespace["digest"](live) != record.get("snapshot_after_digest"):
        namespace["_stop"](run, "STATE_DRIFTED_SINCE_APPLY")
    backup = namespace["_backup"](run, "Revert")
    bindings = namespace["_binding_map"](seq)
    for operation in reversed(record["operations"]):
        binding = bindings.get(operation["binding_guid"])
        track = _locate_recorded_track(namespace, seq, binding, operation["track_after"], run) if binding else None
        if track is None:
            namespace["_stop"](run, "REVERT_TRACK_GONE|%s" % operation["binding_guid"])
        sections = list(track.get_sections())
        if operation["subtype"] == "visibility":
            old_range = operation["track_before"]["sections"][0]["range"]
            sections[0].set_range(int(old_range[0]), int(old_range[1]))
        else:
            old_section = operation["track_before"]["sections"][0]
            keys = list(list(sections[0].get_all_channels())[0].get_keys())
            old_keys = old_section["channels"][0]["keys"]
            for key, old in zip(keys, old_keys):
                key.set_time(unreal.FrameNumber(int(old["frame"])), float(old.get("sub_frame", 0.0)),
                             unreal.MovieSceneTimeUnit.DISPLAY_RATE)
            sections[0].set_range(int(old_section["range"][0]), int(old_section["range"][1]))
    before_specs = [{"binding_guid": row["binding_guid"], "track": row["track_before"]}
                    for row in record["operations"]]
    restored = _light_snapshot(namespace, seq, before_specs, run)
    if restored != record["snapshot_before"]:
        namespace["_stop"](run, "REVERT_PRESAVE_NOT_EXACT|restore=%s" % backup["root"])
    saves = namespace["_save"](run)
    namespace["_log"]("S1_RIG_FADE_REVERT_OK|run=%s|saved=%s|backup=%s" %
                      (run, ",".join(saves), backup["root"]))
    return {"run": run, "reverted": True, "saves": saves, "backup": backup}


def run(args):
    namespace = _load_legacy()
    mode = str(args["mode"]).upper()
    params = namespace["merged_params"](_params(args))
    expected_start = int(args["lights_out_start_frame"])
    if params["expected_target_scene_frame"] - params["fade_frames"] != expected_start:
        raise RuntimeError("LIGHTS_OUT_START_ROUNDING")
    result = {"DRY": _run_dry, "APPLY": _run_apply, "REVERT": _run_revert}[mode](
        namespace, args["run_id"], params)
    unreal.log("JOB169_LIGHTS_OUT_%s_OK|run=%s|start=%d|end=%d|legacy=Job29-S1RigFade" %
               (mode, args["run_id"], expected_start, params["expected_target_scene_frame"]))
    return result
