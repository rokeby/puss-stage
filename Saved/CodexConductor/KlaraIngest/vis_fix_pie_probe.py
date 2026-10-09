"""P26 PIE-only visibility proof (no saves; offline-written, never run here).

For every binding recorded by vis_fix APPLY, sample one display frame inside
each fixed section and one frame outside every fixed section on that binding.
The callback scrubs the running show, waits for Slate post-ticks, then reads the
PIE actor's AActor::bHidden. Inside expectations come from the fixed visibility
channel (True = visible); outside expectations are explicit in args.

Input: vis_fix_pie_probe_args.json or VIS_FIX_PIE_ARGS. Marker:
VISFIX_PIE_OK / VISFIX_PIE_FAILED. This probe never starts/stops PIE and never
saves a package.
"""
from __future__ import annotations

import datetime
import json
import os
import re

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness imports pure case planning.
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))


class ProbeError(ValueError):
    pass


def _frame(value):
    return int(value.value) if hasattr(value, "value") else int(value)


def _rate(value):
    numerator = float(value.numerator)
    denominator = float(value.denominator)
    if denominator == 0:
        raise ProbeError("ZERO_RATE_DENOMINATOR")
    return numerator / denominator


def value_at(section, frame):
    """Evaluate a recorded bool channel with constant key semantics."""
    value = section.get("default")
    for key in sorted(section.get("keys") or [], key=lambda row: int(row["time"])):
        if int(key["time"]) <= int(frame):
            value = bool(key["value"])
        else:
            break
    if value is None:
        raise ProbeError("NO_VALUE_AT|frame=%s" % frame)
    return bool(value)


def _covered(frame, ranges):
    return any(start <= frame < end for start, end in ranges)


def build_cases(targets, playback, outside_hidden=False):
    """Pure case planner; one inside/outside pair per fixed section."""
    lo, hi = [int(value) for value in playback]
    by_binding = {}
    for target in targets:
        ranges = []
        for section in target["expected_after"]["sections"]:
            start, end = section["range"]
            if start is None or end is None or int(end) <= int(start):
                raise ProbeError("FINITE_NONEMPTY_RANGE_REQUIRED|%s|%s" % (target["id"], section["range"]))
            ranges.append((int(start), int(end)))
        by_binding.setdefault(target["binding_guid"], []).extend(ranges)
    cases = []
    for target in targets:
        all_ranges = by_binding[target["binding_guid"]]
        for section in target["expected_after"]["sections"]:
            start, end = [int(value) for value in section["range"]]
            inside = start + max(0, (end - start - 1) // 2)
            outside = start - 1
            while outside >= lo and _covered(outside, all_ranges):
                outside -= 1
            if outside < lo:
                outside = end
                while outside < hi and _covered(outside, all_ranges):
                    outside += 1
            if outside >= hi:
                raise ProbeError("NO_OUTSIDE_FRAME|%s|playback=%s" % (target["id"], playback))
            visible = value_at(section, inside)
            cases.append({
                "id": "%s:s%d" % (target["id"], int(section["index"])),
                "target_id": target["id"],
                "binding_guid": target["binding_guid"],
                "binding": target["binding"],
                "section": int(section["index"]),
                "inside": {"frame": inside, "expected_hidden": not visible},
                "outside": {"frame": outside, "expected_hidden": bool(outside_hidden)},
            })
    return cases


def normalize_args(raw):
    allowed = {"confirm", "run", "sequence", "tag", "outside_hidden", "settle_ticks"}
    extra = sorted(set(raw) - allowed)
    if extra:
        raise ProbeError("UNKNOWN_ARGS|%s" % extra)
    tag = str(raw.get("tag") or "")
    if not re.fullmatch(r"S[0-9]+", tag):
        raise ProbeError("TAG|%r" % tag)
    sequence = str(raw.get("sequence") or "")
    if not sequence.startswith("/Game/"):
        raise ProbeError("SEQUENCE|%r" % sequence)
    if raw.get("confirm") != "PIE PROBE VISFIX":
        raise ProbeError("CONFIRM")
    outside_hidden = raw.get("outside_hidden", False)
    settle = raw.get("settle_ticks", 5)
    if type(outside_hidden) is not bool or type(settle) is not int or settle < 1:
        raise ProbeError("OUTSIDE_OR_SETTLE")
    return {"confirm": raw["confirm"], "run": str(raw.get("run") or
            "VISPIE-%s-%s" % (tag, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))),
            "sequence": sequence, "tag": tag, "outside_hidden": outside_hidden, "settle_ticks": settle}


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(package.get_name() for package in lib.get_dirty_content_packages()),
            "maps": sorted(package.get_name() for package in lib.get_dirty_map_packages())}


def _guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def _binding_map(sequence):
    return {_guid(binding.get_id()): binding for binding in sequence.get_bindings()}


def _evaluate_inside(sequence, binding, target, section_index, frame):
    tracks = list(binding.get_tracks())
    index = int(target["track_index"])
    if index >= len(tracks):
        raise ProbeError("TRACK_INDEX|%s" % target["id"])
    track = tracks[index]
    if not isinstance(track, unreal.MovieSceneVisibilityTrack) or str(track.get_property_name()) != "bHidden":
        raise ProbeError("TRACK_NOT_FIXED|%s|%s" % (target["id"], track.get_property_name()))
    section = list(track.get_sections())[int(section_index)]
    channel = list(section.get_all_channels())[0]
    values = list(channel.evaluate_keys(sequence.make_range(int(frame), 1), sequence.get_display_rate()))
    if len(values) != 1:  # A default SequencerScriptingRange is 60000 fps and gives the wrong count.
        raise ProbeError("EVALUATE_COUNT|%s|frame=%d|got=%d" % (target["id"], frame, len(values)))
    return bool(values[0])


def _stop(run, text):
    unreal.log_error("VISFIX_PIE_FAILED|run=%s|%s" % (run, text))
    raise RuntimeError(text)


def main(raw=None):
    raw = dict(raw if raw is not None else globals().get("VIS_FIX_PIE_ARGS") or
               _load(os.path.join(HERE, "vis_fix_pie_probe_args.json")))
    run = str(raw.get("run") or "UNKNOWN")
    try:
        args = normalize_args(raw)
        run = args["run"]
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_game_world()
        if world is None:
            _stop(run, "NO_PIE|start PIE first; probe never starts it")
        record_path = os.path.join(HERE, "vis_fix_record_%s.json" % args["tag"])
        record = _load(record_path)
        if not record.get("applied") or record.get("sequence") != args["sequence"]:
            _stop(run, "APPLIED_RECORD_REQUIRED|%s" % record_path)
        sequence = unreal.load_asset(args["sequence"])
        bindings = _binding_map(sequence)
        playback = [_frame(sequence.get_playback_start()), _frame(sequence.get_playback_end())]
        cases = build_cases(record["targets"], playback, args["outside_hidden"])
        targets = {target["id"]: target for target in record["targets"]}
        actors = {}
        for target in record["targets"]:
            binding = bindings.get(target["binding_guid"])
            if binding is None:
                _stop(run, "BINDING_MISSING|%s" % target["id"])
            found = [obj for obj in sequence.locate_bound_objects(binding, world)
                     if isinstance(obj, unreal.Actor)]
            if len(found) != 1:
                _stop(run, "PIE_ACTOR_COUNT|%s|%d" % (target["id"], len(found)))
            actors[target["binding_guid"]] = found[0]
        # Independently evaluate the fixed channel with an explicit sequence range/rate.
        for case in cases:
            target = targets[case["target_id"]]
            visible = _evaluate_inside(sequence, bindings[target["binding_guid"]], target, case["section"],
                                       case["inside"]["frame"])
            expected_hidden = not visible
            if expected_hidden != case["inside"]["expected_hidden"]:
                _stop(run, "RECORDED_CHANNEL_DIFF|%s" % case["id"])
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1:
            _stop(run, "SHOW_ROOTS|%d" % len(roots))
        root = roots[0]
        segments = [segment for segment in list(root.transport.segments)
                    if str(segment.label).startswith("Scene %d" % int(args["tag"][1:]))]
        if len(segments) != 1:
            _stop(run, "SEGMENTS|%d" % len(segments))
        segment = segments[0]
        display_fps = _rate(sequence.get_display_rate())
        master_ticks_per_second = 24000.0  # Master convention; segment start frames are Master ticks.
        samples = []
        for case in cases:
            for where in ("outside", "inside"):
                sample = dict(case[where])
                sample.update({"case": case["id"], "where": where, "binding": case["binding"],
                               "binding_guid": case["binding_guid"]})
                sample["master_frame"] = int(segment.start_frame.value +
                                             round(sample["frame"] / display_fps * master_ticks_per_second))
                samples.append(sample)
        census_before = _census()
        report = {"schema": 1, "tool": "VISFIX_PIE", "run": run, "tag": args["tag"], "args": args,
                  "record": record_path, "census_before": census_before, "rows": []}
        state = {"index": 0, "wait": -1, "handle": None, "done": False}

        def finish(error=None):
            if state["done"]:
                return
            state["done"] = True
            unreal.unregister_slate_post_tick_callback(state["handle"])
            report["census_after"] = _census()
            if report["census_after"] != census_before:
                error = error or "DIRTY_CENSUS_CHANGED|before=%s|after=%s" % (census_before, report["census_after"])
            report["passed"] = error is None and all(row["passed"] for row in report["rows"])
            report["error"] = error
            path = os.path.join(HERE, "vis_fix_pie_%s_%s.json" % (args["tag"], run))
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2, sort_keys=True)
                handle.write("\n")
            if report["passed"]:
                unreal.log("VISFIX_PIE_OK|run=%s|tag=%s|samples=%d|dirty_unchanged=1|json=%s" %
                           (run, args["tag"], len(report["rows"]), path))
            else:
                unreal.log_error("VISFIX_PIE_FAILED|run=%s|tag=%s|error=%s|json=%s" %
                                 (run, args["tag"], error or "ASSERTION", path))

        def tick(_delta):
            try:
                if state["done"]:
                    return
                if state["index"] >= len(samples):
                    finish()
                    return
                sample = samples[state["index"]]
                if state["wait"] < 0:
                    root.sequence_player.pause()
                    result = root.transport.scrub_to_master_frame(unreal.FrameNumber(sample["master_frame"]))
                    if result != unreal.InfinityTransportResult.SUCCEEDED:
                        finish("SCRUB|%s|%s" % (sample["case"], result))
                        return
                    state["wait"] = args["settle_ticks"]
                elif state["wait"] > 0:
                    state["wait"] -= 1
                else:
                    actor = actors[sample["binding_guid"]]
                    hidden = bool(actor.get_editor_property("hidden"))
                    row = dict(sample)
                    row.update({"actor": str(actor.get_actor_label()), "actual_hidden": hidden,
                                "passed": hidden == bool(sample["expected_hidden"])})
                    report["rows"].append(row)
                    unreal.log("VISFIX_PIE_ROW|run=%s|case=%s|where=%s|local=%d|master=%d|hidden=%s|want=%s|pass=%s" %
                               (run, row["case"], row["where"], row["frame"], row["master_frame"], hidden,
                                row["expected_hidden"], row["passed"]))
                    if not row["passed"]:
                        finish("ASSERT|%s|%s" % (row["case"], row["where"]))
                        return
                    state["index"] += 1
                    state["wait"] = -1
            except Exception as exc:  # noqa: BLE001
                finish("EXCEPTION|%r" % (exc,))

        state["handle"] = unreal.register_slate_post_tick_callback(tick)
        unreal.log("VISFIX_PIE_ARMED|run=%s|tag=%s|bindings=%d|samples=%d" %
                   (run, args["tag"], len(actors), len(samples)))
    except Exception as exc:  # noqa: BLE001
        if not isinstance(exc, RuntimeError):
            unreal.log_error("VISFIX_PIE_FAILED|run=%s|%r" % (run, exc))
        raise


if unreal is not None:
    main()
