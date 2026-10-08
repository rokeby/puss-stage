"""P20 editor tool: DRY/APPLY/REVERT the Scene 3 chorus sway in LS_Clams.

Offline only until the conductor runs it through ExecuteProjectPythonFile.
The tool never opens Sequencer, PIE, or a viewport.  APPLY records and backs up
LS_Clams before mutation, saves only /Game/Scenes/LS_Clams, and reads every
affected section back.  REVERT removes only sections named in the record and
restores each original section's recorded range/easing.

Args: E:/PussStage/Saved/CodexConductor/s3_chorus_sway_args.json
Confirm strings: APPLY S3CHORUSSWAY / REVERT S3CHORUSSWAY
Markers: S3_CHORUS_SWAY_<MODE>_OK|run=... / S3_CHORUS_SWAY_FAILED|run=...
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import traceback

HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS = HERE + "s3_chorus_sway_args.json"
PLAN_DEFAULT = HERE + "s3_chorus_sway_plan.json"
RECORD = HERE + "s3_chorus_sway_record.json"
SEQUENCE = "/Game/Scenes/LS_Clams"
ASSET_FILE = "E:/PussStage/Content/Scenes/LS_Clams.uasset"
EXPECTED_PACKAGE = "/Game/Scenes/LS_Clams"
RUN = {"value": "?"}


def validate_phase_nudge(value, period):
    value = float(value)
    if abs(value) > float(period) / 2.0 + 1e-8:
        raise ValueError("PHASE_NUDGE_EXCEEDS_HALF_PERIOD|%.6f" % value)
    return value


def build_schedule(window, fps, spans, nudge_s, loop_blend_s, ease_s, target_period_s):
    """Pure schedule helper, also exercised by the offline harness."""
    if not spans or int(window[1]) <= int(window[0]) or fps <= 0 or loop_blend_s <= 0 or ease_s <= 0:
        raise ValueError("BAD_SCHEDULE_ARGUMENTS")
    nudge_s = validate_phase_nudge(nudge_s, target_period_s)
    overlap = int(round(loop_blend_s * fps))
    cursor = int(window[0])
    rows = []
    index = 0
    wrapped_advance_s = nudge_s % target_period_s
    while cursor < int(window[1]):
        span = spans[index % len(spans)]
        source_in = float(span["source_in"])
        if not rows:
            source_in += wrapped_advance_s * float(span["play_rate"])
        source_out = float(span["source_out"])
        if source_in >= source_out - 0.1:
            raise ValueError("PHASE_ADVANCE_EXHAUSTS_SPAN")
        duration = int(round((source_out - source_in) / float(span["play_rate"]) * fps))
        if duration <= overlap * 2:
            raise ValueError("LOOP_TOO_SHORT_FOR_BLEND")
        end = min(int(window[1]), cursor + duration)
        rows.append({"range": [cursor, end], "source_in": source_in, "source_out": source_out,
                     "play_rate": float(span["play_rate"]), "signal": span["signal"],
                     "span_index": index % len(spans)})
        if end == int(window[1]):
            break
        cursor = end - overlap
        index += 1
        if len(rows) > 32:
            raise RuntimeError("SCHEDULE_DID_NOT_TERMINATE")
    for i, row in enumerate(rows):
        row["ease_in"] = int(round((ease_s if i == 0 else loop_blend_s) * fps))
        row["ease_out"] = int(round((ease_s if i == len(rows) - 1 else loop_blend_s) * fps))
    return rows


def continuation_first_loop_offset(section_start, at_frame, fps, play_rate, animation_ticks,
                                   start_offset, end_offset, first_loop_offset, tick_rate):
    """Offset for a cloned right-hand section that continues the original pose."""
    available = int(animation_ticks) - int(start_offset) - int(end_offset)
    if available <= 0:
        raise ValueError("NO_PLAYABLE_ANIMATION_TICKS")
    first_loop_offset = int(first_loop_offset)
    if first_loop_offset < 0 or first_loop_offset >= available:
        raise ValueError("BAD_FIRST_LOOP_OFFSET")
    elapsed = int(round((float(at_frame) - float(section_start)) / float(fps)
                        * float(play_rate) * float(tick_rate)))
    if elapsed < 0:
        raise ValueError("CONTINUATION_BEFORE_SECTION")
    first_remaining = available - first_loop_offset
    if elapsed < first_remaining:
        return first_loop_offset + elapsed
    return (elapsed - first_remaining) % available


def snapshot_matches(actual, expected, rate_tolerance=1e-4):
    """Strict-enough comparison for REVERT preflight and saved read-back."""
    exact = ("name", "range", "animation", "start_offset", "end_offset", "first_loop_offset",
             "reverse", "row", "active", "ease", "weight")
    for key in exact:
        if actual.get(key) != expected.get(key):
            return False, "%s|actual=%r|expected=%r" % (key, actual.get(key), expected.get(key))
    if abs(float(actual.get("play_rate", 0.0)) - float(expected.get("play_rate", 0.0))) > rate_tolerance:
        return False, "play_rate|actual=%r|expected=%r" % (actual.get("play_rate"), expected.get("play_rate"))
    return True, ""


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_value(value):
    return int(value.value if hasattr(value, "value") else value)


def _get_property(obj, names):
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as exc:  # property spelling differs across UE versions
            last = exc
    raise RuntimeError("PROPERTY_NOT_FOUND|%s|%r" % (names, last))


def _set_property(obj, names, value):
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return
        except Exception as exc:
            last = exc
    raise RuntimeError("PROPERTY_NOT_SETTABLE|%s|%r" % (names, last))


def _fixed_play_rate(unreal, params):
    warp = params.get_editor_property("play_rate")
    for call in (
        lambda: float(warp.to_fixed_play_rate()),
        lambda: float(unreal.MovieSceneTimeWarpExtensions.to_fixed_play_rate(warp)),
        lambda: float(warp),
    ):
        try:
            return call()
        except Exception:
            pass
    raise RuntimeError("PLAY_RATE_NOT_CONSTANT")


def _set_fixed_play_rate(unreal, params, value):
    warp = params.get_editor_property("play_rate")
    for call in (
        lambda: warp.set_fixed_play_rate(float(value)),
        lambda: unreal.MovieSceneTimeWarpExtensions.set_fixed_play_rate(warp, float(value)),
    ):
        try:
            call()
            params.set_editor_property("play_rate", warp)
            if abs(_fixed_play_rate(unreal, params) - float(value)) <= 1e-4:
                return
        except Exception:
            pass
    try:
        params.set_editor_property("play_rate", float(value))
        return
    except Exception as exc:
        raise RuntimeError("PLAY_RATE_SET_FAILED|%r" % (exc,))


def _easing_snapshot(section):
    easing = section.get_editor_property("easing")
    return {
        "manual_in": bool(_get_property(easing, ("manual_ease_in", "b_manual_ease_in"))),
        "manual_out": bool(_get_property(easing, ("manual_ease_out", "b_manual_ease_out"))),
        "manual_in_frames": int(_get_property(easing, ("manual_ease_in_duration",))),
        "manual_out_frames": int(_get_property(easing, ("manual_ease_out_duration",))),
        "auto_in_frames": int(_get_property(easing, ("auto_ease_in_duration",))),
        "auto_out_frames": int(_get_property(easing, ("auto_ease_out_duration",))),
    }


def _restore_easing(section, state):
    easing = section.get_editor_property("easing")
    _set_property(easing, ("manual_ease_in", "b_manual_ease_in"), bool(state["manual_in"]))
    _set_property(easing, ("manual_ease_out", "b_manual_ease_out"), bool(state["manual_out"]))
    _set_property(easing, ("manual_ease_in_duration",), int(state["manual_in_frames"]))
    _set_property(easing, ("manual_ease_out_duration",), int(state["manual_out_frames"]))
    _set_property(easing, ("auto_ease_in_duration",), int(state["auto_in_frames"]))
    _set_property(easing, ("auto_ease_out_duration",), int(state["auto_out_frames"]))
    section.set_editor_property("easing", easing)


def _configure_easing(section, ease_in=None, ease_out=None):
    state = _easing_snapshot(section)
    if ease_in is not None:
        state["manual_in"] = True
        state["manual_in_frames"] = int(ease_in)
    if ease_out is not None:
        state["manual_out"] = True
        state["manual_out_frames"] = int(ease_out)
    _restore_easing(section, state)


def _weight_snapshot(section):
    rows = []
    for channel in section.get_all_channels():
        name = str(channel.get_name())
        if "weight" not in name.lower():
            continue
        try:
            default = channel.get_default()
        except Exception:
            default = None
        try:
            keys = [[int(key.get_time().frame_number.value), float(key.get_value())] for key in channel.get_keys()]
        except Exception:
            keys = []
        rows.append({"name": name, "default": None if default is None else float(default), "keys": keys})
    return rows


def _ensure_unit_weight(section):
    channels = [channel for channel in section.get_all_channels() if "weight" in str(channel.get_name()).lower()]
    if len(channels) != 1:
        raise RuntimeError("WEIGHT_CHANNEL_COUNT|%d" % len(channels))
    channel = channels[0]
    if list(channel.get_keys()):
        raise RuntimeError("NEW_WEIGHT_CHANNEL_HAS_KEYS")
    channel.set_default(1.0)


def _section_snapshot(unreal, section):
    params = section.get_editor_property("params")
    animation = params.get_editor_property("animation")
    return {
        "name": str(section.get_name()),
        "range": [int(section.get_start_frame()), int(section.get_end_frame())],
        "animation": animation.get_path_name() if animation else None,
        "start_offset": _frame_value(params.get_editor_property("start_frame_offset")),
        "end_offset": _frame_value(params.get_editor_property("end_frame_offset")),
        "first_loop_offset": _frame_value(params.get_editor_property("first_loop_start_frame_offset")),
        "play_rate": round(_fixed_play_rate(unreal, params), 8),
        "reverse": bool(_get_property(params, ("reverse", "b_reverse"))),
        "row": int(section.get_row_index()),
        "active": bool(section.is_active()),
        "ease": _easing_snapshot(section),
        "weight": _weight_snapshot(section),
    }


def _binding_path(binding):
    names = [str(binding.get_display_name())]
    parent = binding.get_parent()
    while parent is not None and parent.is_valid():
        names.append(str(parent.get_display_name()))
        parent = parent.get_parent()
    return "/".join(reversed(names))


def _census(unreal):
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(package.get_name() for package in lib.get_dirty_content_packages()),
        "maps": sorted(package.get_name() for package in lib.get_dirty_map_packages()),
    }


def _assert_clean(census, label):
    if census != {"content": [], "maps": []}:
        raise RuntimeError("%s_DIRTY|%s" % (label, census))


def _discover(unreal, sequence, plan, local_window, ease_frames):
    found = {}
    for binding in sequence.get_bindings():
        for track in binding.get_tracks():
            if track.get_class().get_name() != "MovieSceneSkeletalAnimationTrack":
                continue
            for section in track.get_sections():
                snap = _section_snapshot(unreal, section)
                asset_name = snap["animation"].rsplit("/", 1)[-1].split(".")[-1] if snap["animation"] else ""
                spec = next((row for row in plan["figures"] if row["animation"] == asset_name), None)
                if spec is None:
                    continue
                if snap["range"][0] <= local_window[0] - ease_frames and snap["range"][1] >= local_window[1] + ease_frames:
                    found.setdefault(spec["id"], []).append((binding, track, section, snap))
    missing = [row["id"] for row in plan["figures"] if len(found.get(row["id"], [])) != 1]
    if missing:
        counts = {row["id"]: len(found.get(row["id"], [])) for row in plan["figures"]}
        raise RuntimeError("SOURCE_SECTION_DISCOVERY|missing_or_nonunique=%s|counts=%s" % (missing, counts))
    result = {}
    for figure_id, rows in found.items():
        binding, track, section, snap = rows[0]
        if snap["reverse"]:
            raise RuntimeError("REVERSE_SOURCE_UNSUPPORTED|%s" % figure_id)
        if len(snap["weight"]) != 1:
            raise RuntimeError("SOURCE_WEIGHT_CHANNEL_COUNT|%s|%d" % (figure_id, len(snap["weight"])))
        if any(channel["keys"] for channel in snap["weight"]):
            raise RuntimeError("SOURCE_WEIGHT_KEYS_UNSUPPORTED|%s" % figure_id)
        result[figure_id] = {"binding": binding, "track": track, "section": section, "snapshot": snap,
                             "binding_path": _binding_path(binding),
                             "binding_guid": binding.get_id().export_text(),
                             "track_name": str(track.get_name())}
    return result


def _clone_params(unreal, source_section, target_section):
    target_section.set_editor_property("params", source_section.get_editor_property("params"))
    target_section.set_row_index(source_section.get_row_index())
    target_section.set_is_active(source_section.is_active())
    _restore_easing(target_section, _easing_snapshot(source_section))
    _ensure_unit_weight(target_section)


def _make_calm_section(unreal, track, source_section, animation, tick_rate, animation_ticks, row):
    section = track.add_section()
    if section is None:
        raise RuntimeError("ADD_CALM_SECTION_NONE")
    _clone_params(unreal, source_section, section)
    section.set_range(int(row["range"][0]), int(row["range"][1]))
    params = section.get_editor_property("params")
    params.set_editor_property("animation", animation)
    params.set_editor_property("start_frame_offset", unreal.FrameNumber(int(round(row["source_in"] * tick_rate))))
    params.set_editor_property("end_frame_offset", unreal.FrameNumber(max(0, animation_ticks - int(round(row["source_out"] * tick_rate)))))
    params.set_editor_property("first_loop_start_frame_offset", unreal.FrameNumber(0))
    _set_property(params, ("reverse", "b_reverse"), False)
    _set_fixed_play_rate(unreal, params, row["play_rate"])
    section.set_editor_property("params", params)
    _configure_easing(section, row["ease_in"], row["ease_out"])
    return section


def _find_section_by_name(track, name):
    hits = [section for section in track.get_sections() if str(section.get_name()) == name]
    if len(hits) != 1:
        raise RuntimeError("SECTION_NAME_NOT_UNIQUE|%s|hits=%d" % (name, len(hits)))
    return hits[0]


def _write_record(record):
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _backup(run, prefix):
    directory = "E:/PussStage/Backups/%s-%s" % (prefix, run)
    if os.path.exists(directory):
        raise RuntimeError("BACKUP_EXISTS|%s" % directory)
    os.makedirs(directory)
    saved = directory + "/LS_Clams.uasset"
    shutil.copy2(ASSET_FILE, saved)
    if _sha256(saved) != _sha256(ASSET_FILE):
        raise RuntimeError("BACKUP_HASH_MISMATCH")
    return directory


def _read_plan(args):
    path = args.get("plan_path", PLAN_DEFAULT)
    with open(path, encoding="utf-8") as handle:
        plan = json.load(handle)
    if plan.get("schema") != "p20_chorus_sway/1" or len(plan.get("figures", [])) != 6:
        raise RuntimeError("PLAN_SCHEMA_OR_FIGURE_COUNT")
    return path, plan


def _effective(args, plan):
    fps = float(plan["fps"])
    start = int(args.get("window_start", plan["window_scene_frames"][0]))
    end = int(args.get("window_end", plan["window_scene_frames"][1]))
    offset = int(plan["scene_to_ls_clams_frames"])
    target_period = float(args.get("target_period_s", plan["target_period_s"]))
    ease = float(args.get("ease_seconds", plan["ease_seconds"]))
    blend = float(args.get("loop_blend_seconds", plan["loop_blend_seconds"]))
    if end <= start or fps <= 0 or ease <= 0 or blend <= 0:
        raise RuntimeError("BAD_EFFECTIVE_ARGS")
    overrides = args.get("phase_nudges_seconds", {})
    schedules = {}
    for figure in plan["figures"]:
        nudge = validate_phase_nudge(overrides.get(figure["id"], figure["default_phase_nudge_s"]), target_period)
        schedules[figure["id"]] = {
            "nudge": nudge,
            "phase_deg": (float(figure["base_phase_deg"]) + nudge / target_period * 360.0) % 360.0,
            "rows": build_schedule((start + offset, end + offset), fps, figure["spans"], nudge,
                                   blend, ease, target_period),
        }
    return {"fps": fps, "scene_window": [start, end], "local_window": [start + offset, end + offset],
            "target_period": target_period, "ease": ease, "blend": blend,
            "ease_frames": int(round(ease * fps)), "schedules": schedules}


def _verify_saved(unreal, sequence, record, expect_applied):
    rows = {}
    bindings = {binding.get_id().export_text(): binding for binding in sequence.get_bindings()}
    for figure in record["figures"]:
        binding = bindings.get(figure["binding_guid"])
        if binding is None:
            raise RuntimeError("READBACK_BINDING_MISSING|%s" % figure["id"])
        tracks = [track for track in binding.get_tracks() if str(track.get_name()) == figure["track_name"]]
        if len(tracks) != 1:
            raise RuntimeError("READBACK_TRACK_MISSING|%s" % figure["id"])
        track = tracks[0]
        if expect_applied:
            expected = figure["applied_sections"]
            actual = []
            for snapshot in expected:
                section = _find_section_by_name(track, snapshot["name"])
                read = _section_snapshot(unreal, section)
                ok, why = snapshot_matches(read, snapshot)
                if not ok:
                    raise RuntimeError("READBACK_SECTION|%s|%s|%s" % (figure["id"], snapshot["name"], why))
                actual.append(read)
            rows[figure["id"]] = actual
        else:
            section = _find_section_by_name(track, figure["original"]["name"])
            read = _section_snapshot(unreal, section)
            ok, why = snapshot_matches(read, figure["original"])
            if not ok:
                raise RuntimeError("REVERT_READBACK|%s|%s" % (figure["id"], why))
            rows[figure["id"]] = [read]
    return rows


def main():
    import unreal
    with open(ARGS, encoding="utf-8") as handle:
        args = json.load(handle)
    run, mode = str(args["run"]), str(args["mode"]).upper()
    RUN["value"] = run
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise RuntimeError("MODE|%s" % mode)
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise RuntimeError("SEQUENCER_OPEN")
    c0 = _census(unreal)
    _assert_clean(c0, "START")
    plan_path, plan = _read_plan(args)
    effective = _effective(args, plan)
    extra_count = int(args.get("extra_crowd_count", 0))
    sequence = unreal.load_asset(SEQUENCE)
    if sequence is None:
        raise RuntimeError("SEQUENCE_MISSING|%s" % SEQUENCE)

    if mode == "DRY" and os.path.exists(RECORD):
        with open(RECORD, encoding="utf-8") as handle:
            existing = json.load(handle)
        if existing.get("state") == "applied":
            readback = _verify_saved(unreal, sequence, existing, True)
            if _census(unreal) != c0:
                raise RuntimeError("DRY_DIRTY_CHANGED")
            for figure in existing["figures"]:
                unreal.log("S3_CHORUS_SWAY_PHASE|run=%s|figure=%s|phase_deg=%.3f|nudge_s=%+.3f|binding=%s" %
                           (run, figure["id"], figure["phase_deg"], figure["nudge_s"], figure["binding_path"]))
            unreal.log("S3_CHORUS_SWAY_DRY_OK|run=%s|state=applied|packages=%s|sections=%d" %
                       (run, list(readback), sum(len(value) for value in readback.values())))
            return

    if mode == "REVERT":
        if args.get("confirm") != "REVERT S3CHORUSSWAY":
            raise RuntimeError("CONFIRM_REQUIRED|REVERT S3CHORUSSWAY")
        if not os.path.exists(RECORD):
            raise RuntimeError("RECORD_MISSING")
        with open(RECORD, encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("state") != "applied":
            raise RuntimeError("RECORD_NOT_APPLIED|%s" % record.get("state"))
        _verify_saved(unreal, sequence, record, True)
        backup = _backup(run, "PreS3ChorusSwayRevert")
        bindings = {binding.get_id().export_text(): binding for binding in sequence.get_bindings()}
        sequence.modify()
        for figure in record["figures"]:
            binding = bindings[figure["binding_guid"]]
            track = next(track for track in binding.get_tracks() if str(track.get_name()) == figure["track_name"])
            original_name = figure["original"]["name"]
            for created_name in figure["created_names"]:
                track.remove_section(_find_section_by_name(track, created_name))
            original = _find_section_by_name(track, original_name)
            original.set_range(*figure["original"]["range"])
            _restore_easing(original, figure["original"]["ease"])
        c1 = _census(unreal)
        if c1 != {"content": [EXPECTED_PACKAGE], "maps": []}:
            raise RuntimeError("REVERT_CENSUS|%s|NOTHING SAVED; Don't-Save restart" % c1)
        if not unreal.EditorAssetLibrary.save_asset(SEQUENCE, only_if_is_dirty=False):
            raise RuntimeError("REVERT_SAVE_FAILED")
        _assert_clean(_census(unreal), "REVERT_AFTER_SAVE")
        record["state"] = "reverted"
        record["revert_run"] = run
        record["revert_backup"] = backup
        record["revert_readback"] = _verify_saved(unreal, unreal.load_asset(SEQUENCE), record, False)
        _write_record(record)
        unreal.log("S3_CHORUS_SWAY_REVERT_OK|run=%s|package=%s|backup=%s|dirty=0" %
                   (run, EXPECTED_PACKAGE, backup))
        return

    discovered = _discover(unreal, sequence, plan, effective["local_window"], effective["ease_frames"])
    if _census(unreal) != c0:
        raise RuntimeError("DISCOVERY_DIRTIED_PACKAGES")
    for figure in plan["figures"]:
        item = discovered[figure["id"]]
        schedule = effective["schedules"][figure["id"]]
        unreal.log("S3_CHORUS_SWAY_PHASE|run=%s|figure=%s|base_phase_deg=%.3f|phase_deg=%.3f|nudge_s=%+.3f|binding=%s|guid=%s|sections=%d" %
                   (run, figure["id"], figure["base_phase_deg"], schedule["phase_deg"], schedule["nudge"],
                    item["binding_path"], item["binding_guid"], len(schedule["rows"])))
    if mode == "DRY":
        if extra_count:
            unreal.log_warning("S3_CHORUS_SWAY_EXTRA_DESIGN_ONLY|run=%s|count=%d|APPLY refuses extras" % (run, extra_count))
        unreal.log("S3_CHORUS_SWAY_DRY_OK|run=%s|sequence=%s|package_census=%s|figures=6|extra_design_only=%d|writes=0" %
                   (run, SEQUENCE, c0, extra_count))
        return
    if args.get("confirm") != "APPLY S3CHORUSSWAY":
        raise RuntimeError("CONFIRM_REQUIRED|APPLY S3CHORUSSWAY")
    if extra_count:
        raise RuntimeError("EXTRA_CROWD_DESIGN_ONLY|count=%d" % extra_count)
    prior_record = None
    if os.path.exists(RECORD):
        with open(RECORD, encoding="utf-8") as handle:
            prior_record = json.load(handle)
        if prior_record.get("state") != "reverted":
            raise RuntimeError("RECORD_EXISTS|state=%s|%s" % (prior_record.get("state"), RECORD))

    backup = _backup(run, "PreS3ChorusSway")
    if prior_record is not None:
        shutil.copy2(RECORD, backup + "/prior_reverted_record.json")
    record = {"schema": "p20_chorus_sway_record/1", "run": run, "state": "applying",
              "plan_path": plan_path, "plan_run": plan["run"], "backup": backup,
              "asset_sha256_before": _sha256(ASSET_FILE), "package": EXPECTED_PACKAGE,
              "dirty_before": c0, "effective": effective, "figures": []}
    for figure in plan["figures"]:
        item = discovered[figure["id"]]
        schedule = effective["schedules"][figure["id"]]
        record["figures"].append({"id": figure["id"], "binding_guid": item["binding_guid"],
                                  "binding_path": item["binding_path"], "track_name": item["track_name"],
                                  "original": item["snapshot"], "nudge_s": schedule["nudge"],
                                  "phase_deg": schedule["phase_deg"], "planned_rows": schedule["rows"],
                                  "created_names": [], "applied_sections": []})
    _write_record(record)

    sequence.modify()
    by_id = {row["id"]: row for row in record["figures"]}
    local_start, local_end = effective["local_window"]
    for figure in plan["figures"]:
        item = discovered[figure["id"]]
        track, original = item["track"], item["section"]
        original_snap = item["snapshot"]
        animation = original.get_editor_property("params").get_editor_property("animation")
        tick = sequence.get_tick_resolution()
        tick_rate = float(tick.numerator) / float(tick.denominator)
        animation_ticks = int(round(float(animation.get_play_length()) * tick_rate))
        right_start = local_end - effective["ease_frames"]
        continuation = continuation_first_loop_offset(
            original_snap["range"][0], right_start, effective["fps"], original_snap["play_rate"],
            animation_ticks, original_snap["start_offset"], original_snap["end_offset"],
            original_snap["first_loop_offset"], tick_rate)
        right = track.add_section()
        if right is None:
            raise RuntimeError("ADD_RIGHT_SECTION_NONE|%s" % figure["id"])
        _clone_params(unreal, original, right)
        right.set_range(right_start, original_snap["range"][1])
        right_params = right.get_editor_property("params")
        right_params.set_editor_property("first_loop_start_frame_offset", unreal.FrameNumber(continuation))
        right.set_editor_property("params", right_params)
        _configure_easing(right, effective["ease_frames"], None)
        original.set_range(original_snap["range"][0], local_start + effective["ease_frames"])
        _configure_easing(original, None, effective["ease_frames"])
        created = [right]
        for row in effective["schedules"][figure["id"]]["rows"]:
            created.append(_make_calm_section(unreal, track, original, animation, tick_rate,
                                              animation_ticks, row))
        record_row = by_id[figure["id"]]
        record_row["created_names"] = [str(section.get_name()) for section in created]
        record_row["applied_sections"] = [_section_snapshot(unreal, original)] + [
            _section_snapshot(unreal, section) for section in created]

    c1 = _census(unreal)
    if c1 != {"content": [EXPECTED_PACKAGE], "maps": []}:
        raise RuntimeError("APPLY_CENSUS|%s|NOTHING SAVED; Don't-Save restart" % c1)
    _write_record(record)
    if not unreal.EditorAssetLibrary.save_asset(SEQUENCE, only_if_is_dirty=False):
        raise RuntimeError("APPLY_SAVE_FAILED")
    _assert_clean(_census(unreal), "APPLY_AFTER_SAVE")
    record["asset_sha256_after"] = _sha256(ASSET_FILE)
    if record["asset_sha256_after"] == record["asset_sha256_before"]:
        raise RuntimeError("ASSET_HASH_UNCHANGED_AFTER_SAVE")
    record["readback"] = _verify_saved(unreal, unreal.load_asset(SEQUENCE), record, True)
    record["state"] = "applied"
    _write_record(record)
    count = sum(len(row["applied_sections"]) for row in record["figures"])
    unreal.log("S3_CHORUS_SWAY_APPLY_OK|run=%s|package=%s|figures=6|sections_read_back=%d|backup=%s|dirty=0" %
               (run, EXPECTED_PACKAGE, count, backup))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            import unreal
            unreal.log_error("S3_CHORUS_SWAY_FAILED|run=%s|%r|%s" %
                             (RUN["value"], exc, traceback.format_exc()[-900:].replace("\n", " / ")))
        except Exception:
            raise
