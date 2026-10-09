"""Cue Book stills driver, copied by Cueing to ``Saved/CodexCueing/``.

Run only inside a PIE that the Conductor already started.  The driver imports
``Saved/CodexConductor/scene_stills.py`` and delegates every capture to its
``arm`` lifecycle, so the established scrub, settle, frame, file, camera, dirty
package, and restore gates remain authoritative.

Arguments: ``Saved/CodexCueing/cuebook_stills_args.json``::

  {"mode":"DRY"}
  {"mode":"APPLY", "confirm":"APPLY_CUEBOOK_STILLS", "fraction":0.5,
   "transition_fraction":0.3, "max_cue_stills":60}
  {"mode":"REVERT", "confirm":"REVERT_CUEBOOK_STILLS",
   "revert_run":"CBSTILLS-20261009-120000"}

APPLY creates only a new Saved capture run.  REVERT never deletes it: it moves
the named run into a new ``Backups/PreCueBookStillsRevert-<run>/`` record.
The driver never starts/ends PIE, saves a package, or changes an Unreal asset.
"""
from __future__ import annotations

import builtins
import datetime
import importlib.util
import json
import pathlib
import re
import shutil
import traceback


DRIVER_HANDLE = "CUEBOOK_STILLS_DRIVER_HANDLE"
DRIVER_STATE = "CUEBOOK_STILLS_DRIVER_STATE"
MANIFEST_NAME = "cuebook_stills_manifest.json"
APPLY_CONFIRM = "APPLY_CUEBOOK_STILLS"
REVERT_CONFIRM = "REVERT_CUEBOOK_STILLS"


class CueBookStillsRefused(RuntimeError):
    pass


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def find_project_root(start):
    here = pathlib.Path(start).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "PussStage.uproject").is_file():
            return candidate
    raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=project_root_not_found")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=module_load|path=%s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CueBookStillsRefused("CUEBOOK_STILLS_BAD_JSON|%s" % path)
    return data


def latest_cuebook_pull(project_root, explicit=None):
    if explicit:
        path = pathlib.Path(explicit)
        if not path.is_absolute():
            path = pathlib.Path(project_root) / path
        if not path.is_file():
            raise CueBookStillsRefused("CUEBOOK_STILLS_NO_CUEBOOK|%s" % path)
        return path
    paths = sorted((pathlib.Path(project_root) / "Docs" / "CueSheet" / "pulls").glob("cuebook_*.json"),
                   key=lambda p: p.name)
    if not paths:
        raise CueBookStillsRefused("CUEBOOK_STILLS_NO_CUEBOOK|Docs/CueSheet/pulls/cuebook_*.json")
    return paths[-1]


def parse_time(value, display_fps=25):
    raw = str(value or "").strip()
    fields = raw.split(":")
    if not raw or len(fields) < 1 or len(fields) > 4:
        return None
    if any(re.fullmatch(r"\+?(?:\d+(?:\.\d*)?|\.\d+)", field.strip()) is None for field in fields):
        return None
    numbers = [float(field) for field in fields]
    if len(numbers) == 4:
        if not numbers[3].is_integer() or numbers[3] >= display_fps:
            return None
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2] + numbers[3] / float(display_fps)
    if len(numbers) == 3:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    return numbers[0]


def cuebook_segments(cues):
    """Mirror the page: a non-cut cue with Video Cue starts the next segment."""
    ordered = sorted(list(cues), key=lambda cue: (float(cue.get("ord", 0) or 0), str(cue.get("key", ""))))
    segments = [{"name": "Prologue", "cues": []}]
    for cue in ordered:
        video = str(cue.get("videoCue", "") or "").strip()
        if video and not bool(cue.get("cut")):
            segments.append({"name": video.splitlines()[0].strip(), "cues": []})
        segments[-1]["cues"].append(cue)
    if segments and not segments[0]["cues"]:
        segments.pop(0)
    return segments


def _number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CueBookStillsRefused("CUEBOOK_STILLS_BAD_ARG|%s=%r" % (name, value))
    value = float(value)
    if not minimum <= value <= maximum:
        raise CueBookStillsRefused("CUEBOOK_STILLS_BAD_ARG|%s=%r" % (name, value))
    return value


def build_capture_plan(transport, mapping_api, scene_api, cues, map_config, args):
    fraction = _number(args.get("fraction", 0.5), "fraction", 0.0, 1.0)
    transition_fraction = _number(args.get("transition_fraction", 0.3), "transition_fraction", 0.0, 1.0)
    cap = args.get("max_cue_stills", 60)
    if isinstance(cap, bool) or not isinstance(cap, int) or not 0 <= cap <= 500:
        raise CueBookStillsRefused("CUEBOOK_STILLS_BAD_ARG|max_cue_stills=%r" % cap)

    segments = cuebook_segments(cues)
    mapping = mapping_api.map_segment_names([segment["name"] for segment in segments], map_config)
    items, skipped = [], []
    spans = {}
    for index, (segment, mapped) in enumerate(zip(segments, mapping)):
        key = mapped["key"]
        if key is None:
            skipped.append({"kind": "segment", "name": segment["name"], "reason": "unmapped"})
            continue
        start, end = transport.segment_span(key)
        start, end = int(start), int(end)
        if end - start <= int(scene_api.END_GUARD_TICKS):
            raise CueBookStillsRefused("CUEBOOK_STILLS_SHORT_SEGMENT|%s|%d..%d" % (key, start, end))
        spans[index] = (key, start, end)
        use_fraction = transition_fraction if re.fullmatch(r"I\d+", key) else fraction
        target = scene_api.fraction_to_frame(start, end, use_fraction)
        items.append({"kind": "segment", "id": key, "segment_key": key,
                      "segment_name": segment["name"], "unreal_id": key,
                      "fraction": use_fraction, "target_frame": int(target),
                      "segment_start": start, "segment_end": end,
                      "arm_start": start, "arm_end": end, "arm_fraction": use_fraction})

    timed = []
    for index, segment in enumerate(segments):
        if index not in spans:
            continue
        key, start, end = spans[index]
        for cue in segment["cues"]:
            at_raw = str(cue.get("at", "") or "").strip()
            if not at_raw:
                continue
            seconds = parse_time(at_raw, int(scene_api.DISPLAY_FPS))
            cue_key = str(cue.get("key", "") or "").strip()
            if seconds is None:
                skipped.append({"kind": "cue", "cue_key": cue_key, "segment_key": key,
                                "at": at_raw, "reason": "invalid_at"})
                continue
            target = start + int(round(seconds * int(scene_api.TICKS_PER_SECOND)))
            if target < start or target > end - int(scene_api.END_GUARD_TICKS):
                skipped.append({"kind": "cue", "cue_key": cue_key, "segment_key": key,
                                "at": at_raw, "reason": "at_outside_segment"})
                continue
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,63}", cue_key) is None:
                skipped.append({"kind": "cue", "cue_key": cue_key, "segment_key": key,
                                "at": at_raw, "reason": "bad_cue_key"})
                continue
            timed.append({"kind": "cue", "id": cue_key, "cue_key": cue_key,
                          "segment_key": key, "segment_name": segment["name"], "unreal_id": key,
                          "at": at_raw, "seconds": seconds, "target_frame": target,
                          "segment_start": start, "segment_end": end,
                          # A forced one-frame-at-zero span makes scene_stills.arm capture target exactly.
                          "arm_start": target, "arm_end": target + 2 * int(scene_api.END_GUARD_TICKS),
                          "arm_fraction": 0.0})
    items.extend(timed[:cap])
    for item in timed[cap:]:
        skipped.append({"kind": "cue", "cue_key": item["cue_key"],
                        "segment_key": item["segment_key"], "at": item["at"], "reason": "max_cue_stills"})
    return {"mapping": mapping, "items": items, "skipped": skipped,
            "segment_count": sum(item["kind"] == "segment" for item in items),
            "cue_count": sum(item["kind"] == "cue" for item in items),
            "max_cue_stills": cap, "fraction": fraction, "transition_fraction": transition_fraction}


class ForcedSpanAdapter:
    """Delegate the whole proven route; replace only the already-resolved span read."""
    def __init__(self, delegate, span):
        self.delegate = delegate
        self.span = tuple(span)

    def passage_segment(self, _label):
        return self.span

    def __getattr__(self, name):
        return getattr(self.delegate, name)


class RuntimeTransport:
    def __init__(self, unreal, scene_api, adapter):
        self.unreal, self.scene_api, self.adapter = unreal, scene_api, adapter

    def segment_span(self, key):
        if key != "Closing":
            _number_, label = self.scene_api.passage_label(key)
            return self.adapter.passage_segment(label)
        editor_sub = self.unreal.get_editor_subsystem(self.unreal.UnrealEditorSubsystem)
        world = editor_sub.get_game_world()
        if world is None or self.adapter.world_kind() != "game":
            raise CueBookStillsRefused("CUEBOOK_STILLS_NO_PIE|Closing")
        roots = list(self.unreal.GameplayStatics.get_all_actors_of_class(world, self.unreal.InfinityStageShowRoot))
        if len(roots) != 1 or not roots[0].sequence_player:
            raise CueBookStillsRefused("CUEBOOK_STILLS_NO_SHOW_ROOT|count=%d" % len(roots))
        matches = [segment for segment in list(roots[0].transport.segments)
                   if str(segment.label) == "Closing" or str(segment.label).startswith("Closing ")]
        if len(matches) != 1:
            raise CueBookStillsRefused("CUEBOOK_STILLS_NO_CLOSING|count=%d" % len(matches))
        return int(matches[0].start_frame.value), int(matches[0].end_frame.value)


def _public_run(run):
    return {key: value for key, value in run.items() if not key.startswith("_")}


def _write(scene_api, path, data):
    scene_api.write_verified(path, data)
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def revert_capture_run(unreal, scene_api, adapter, project_root, args):
    if args.get("confirm") != REVERT_CONFIRM:
        raise CueBookStillsRefused("CUEBOOK_STILLS_REVERT_REFUSED|reason=confirm")
    name = str(args.get("revert_run", "") or "")
    if re.fullmatch(r"CBSTILLS-[A-Za-z0-9_-]+", name) is None:
        raise CueBookStillsRefused("CUEBOOK_STILLS_REVERT_REFUSED|reason=bad_run")
    root = pathlib.Path(project_root) / "Saved" / "CodexCueing" / "CueBookStills"
    target = (root / name).resolve()
    if target.parent != root.resolve() or not target.is_dir():
        raise CueBookStillsRefused("CUEBOOK_STILLS_REVERT_REFUSED|reason=missing_run|run=%s" % name)
    run_id = "CBSTILLS-REVERT-%s" % utc_stamp()
    backup = pathlib.Path(project_root) / "Backups" / ("PreCueBookStillsRevert-%s" % run_id)
    if backup.exists():
        raise CueBookStillsRefused("CUEBOOK_STILLS_REVERT_REFUSED|reason=backup_exists|path=%s" % backup)
    before = adapter.census()
    backup.mkdir(parents=True, exist_ok=False)
    record = {"run_id": run_id, "mode": "REVERT", "target": target.as_posix(),
              "backup": backup.as_posix(), "census_before": before, "saved_packages": [],
              "started_utc": utc_iso()}
    record_path = backup / "record.json"
    _write(scene_api, record_path, record)
    shutil.move(str(target), str(backup / target.name))
    after = adapter.census()
    record.update(census_after=after, finished_utc=utc_iso(), status="passed" if after == before else "failed")
    _write(scene_api, record_path, record)
    if after != before:
        raise CueBookStillsRefused("CUEBOOK_STILLS_REVERT_FAILED|reason=census_changed|run=%s" % run_id)
    unreal.log("CUEBOOK_STILLS_REVERT_OK|run=%s|target=%s|backup=%s" % (run_id, name, backup.as_posix()))
    return record


def start_driver(unreal, project_root, args):
    scene_api = load_module(pathlib.Path(project_root) / "Saved" / "CodexConductor" / "scene_stills.py",
                            "cuebook_scene_stills")
    mapping_api = load_module(pathlib.Path(project_root) / "Tools" / "CueBook" / "segment_map.py",
                              "cuebook_segment_map")
    adapter = scene_api.make_pie_adapter(unreal)
    if adapter.world_kind() != "game":
        raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=no_pie")
    if scene_api.owner_active(pathlib.Path(project_root) / "Saved" / "CodexConductor" / "pie_recording_owner.json"):
        raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=pie_owner_active")
    handles = scene_api.armed_handles(builtins)
    if handles or hasattr(builtins, DRIVER_HANDLE):
        raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=tick_armed|handles=%s" %
                                  ",".join(handles + ([DRIVER_HANDLE] if hasattr(builtins, DRIVER_HANDLE) else [])))
    mode = str(args.get("mode", "DRY") or "DRY").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=bad_mode|mode=%s" % mode)
    if mode == "REVERT":
        return revert_capture_run(unreal, scene_api, adapter, project_root, args)
    if mode == "APPLY" and args.get("confirm") != APPLY_CONFIRM:
        raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=confirm")

    cue_path = latest_cuebook_pull(project_root, args.get("cuebook_json"))
    cuebook = load_json(cue_path)
    cues = cuebook.get("cues")
    if not isinstance(cues, list):
        raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=none|reason=bad_cues")
    map_path = pathlib.Path(project_root) / "Tools" / "CueBook" / "segment_map.json"
    map_config = mapping_api.load_segment_map(map_path)
    plan = build_capture_plan(RuntimeTransport(unreal, scene_api, adapter), mapping_api, scene_api,
                              cues, map_config, args)
    tag = re.sub(r"[^A-Za-z0-9_-]+", "", str(args.get("label", "") or ""))[:24]
    run_id = "CBSTILLS-%s%s" % (utc_stamp(), ("-" + tag) if tag else "")
    run_root = pathlib.Path(project_root) / "Saved" / "CodexCueing" / "CueBookStills"
    run_dir = run_root / run_id
    backup = pathlib.Path(project_root) / "Backups" / ("PreCueBookStillsCapture-%s" % run_id)
    before = adapter.census()
    original_frame = int(adapter.transport_frame())
    backup.mkdir(parents=True, exist_ok=False)
    pre_record = {"run_id": run_id, "mode": mode, "run_dir": run_dir.as_posix(),
                  "cuebook_json": cue_path.as_posix(), "segment_map": map_path.as_posix(),
                  "census_before": before, "original_frame": original_frame,
                  "saved_packages": [], "planned_segments": plan["segment_count"],
                  "planned_cues": plan["cue_count"], "created_utc": utc_iso()}
    _write(scene_api, backup / "record.json", pre_record)
    run_dir.mkdir(parents=True, exist_ok=False)
    run = dict(pre_record)
    run.update(status="planned" if mode == "DRY" else "capturing", plan=plan,
               captures=[], errors=[], backup=backup.as_posix())
    manifest = run_dir / MANIFEST_NAME
    _write(scene_api, manifest, run)
    unreal.log("CUEBOOK_STILLS_START|run=%s|mode=%s|segments=%d|cues=%d|unmapped=%d" % (
        run_id, mode, plan["segment_count"], plan["cue_count"],
        sum(row["key"] is None for row in plan["mapping"])))

    if mode == "DRY":
        after = adapter.census()
        run.update(status="dry", census_after=after, finished_utc=utc_iso())
        _write(scene_api, manifest, run)
        if after != before:
            raise CueBookStillsRefused("CUEBOOK_STILLS_FAILED|run=%s|reason=census_changed" % run_id)
        unreal.log("CUEBOOK_STILLS_DRY_OK|run=%s|segments=%d|cues=%d|dir=%s" %
                   (run_id, plan["segment_count"], plan["cue_count"], run_dir.as_posix()))
        return run

    state = {"index": 0, "child": None, "inside": False, "finished": False, "handle": None}
    run["_state"] = state

    def finish(ok, reason=""):
        if state["finished"]:
            return
        after = adapter.census()
        final_frame = int(adapter.transport_frame()) if adapter.world_kind() == "game" else None
        problems = []
        if after != before:
            problems.append("census_changed")
        if final_frame != original_frame:
            problems.append("frame_not_restored")
        if reason:
            problems.append(reason)
        run.update(census_after=after, final_frame=final_frame, problems=problems,
                   finished_utc=utc_iso(), status="passed" if ok and not problems else "failed")
        _write(scene_api, manifest, _public_run(run))
        if state["handle"] is not None:
            unreal.unregister_slate_post_tick_callback(state["handle"])
        if hasattr(builtins, DRIVER_HANDLE):
            delattr(builtins, DRIVER_HANDLE)
        state["finished"] = True
        if run["status"] == "passed":
            unreal.log("CUEBOOK_STILLS_OK|run=%s|segments=%d|cues=%d|dir=%s" %
                       (run_id, plan["segment_count"], plan["cue_count"], run_dir.as_posix()))
        else:
            unreal.log_error("CUEBOOK_STILLS_FAILED|run=%s|reason=%s|manifest=%s" %
                             (run_id, ";".join(problems) or "capture_failed", manifest.as_posix()))

    def collect_child(child, item):
        child_manifest = pathlib.Path(child["run_dir"]) / scene_api.MANIFEST_NAME
        saved = json.loads(child_manifest.read_text(encoding="utf-8"))
        if saved.get("status") != "passed" or len(saved.get("stills", [])) != 1:
            raise CueBookStillsRefused("child_failed|%s" % child_manifest)
        still = saved["stills"][0]
        if int(still.get("master_frame_at_capture", -1)) != int(item["target_frame"]):
            raise CueBookStillsRefused("child_frame_mismatch|%s|%s" %
                                      (still.get("master_frame_at_capture"), item["target_frame"]))
        row = dict(item)
        row.update(path=still["path"], captured=saved.get("finished_utc"),
                   master_frame=int(still["master_frame_at_capture"]), child_manifest=child_manifest.as_posix())
        run["captures"].append(row)
        _write(scene_api, manifest, _public_run(run))

    def arm_next():
        if state["index"] >= len(plan["items"]):
            finish(True)
            return
        item = plan["items"][state["index"]]
        forced = ForcedSpanAdapter(adapter, (item["arm_start"], item["arm_end"]))
        passage_arg = item["segment_key"] if item["segment_key"] != "Closing" else "Opening"
        child = scene_api.arm(
            forced, passage_arg, [item["arm_fraction"]], label=item["id"],
            params=dict(args.get("capture_params", {}) or {}), out_root=run_dir / "captures",
            owner_path=pathlib.Path(project_root) / "Saved" / "CodexConductor" / "pie_recording_owner.json",
            register=unreal.register_slate_post_tick_callback,
            unregister=unreal.unregister_slate_post_tick_callback, store=builtins)
        state["child"] = child

    def tick(_delta=0.0):
        if state["inside"] or state["finished"]:
            return
        state["inside"] = True
        try:
            child = state["child"]
            if child is None:
                arm_next()
            elif child.get("finished"):
                item = plan["items"][state["index"]]
                if child.get("status") != "passed":
                    finish(False, "child_failed_%s" % item["id"])
                else:
                    collect_child(child, item)
                    state["index"] += 1
                    state["child"] = None
                    arm_next()
        except Exception as exc:
            run["errors"].append(traceback.format_exc())
            finish(False, getattr(exc, "reason", type(exc).__name__))
        finally:
            state["inside"] = False

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    setattr(builtins, DRIVER_HANDLE, state["handle"])
    setattr(builtins, DRIVER_STATE, run)
    unreal.log("CUEBOOK_STILLS_ARMED|run=%s|captures=%d|dir=%s" %
               (run_id, len(plan["items"]), run_dir.as_posix()))
    return run


def main():
    import unreal
    project_root = find_project_root(pathlib.Path(__file__).parent)
    args_path = project_root / "Saved" / "CodexCueing" / "cuebook_stills_args.json"
    try:
        args = load_json(args_path)
        return start_driver(unreal, project_root, args)
    except Exception as exc:
        unreal.log_error("CUEBOOK_STILLS_FAILED|run=none|reason=%s|detail=%s" %
                         (getattr(exc, "reason", type(exc).__name__), exc))
        raise


if __name__ == "__main__":
    main()
