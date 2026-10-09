"""P39 Interaction-2 polish authoring tool.

Offline-authored; the conductor runs this inside UE 5.8 through project Python.
The module deliberately imports ``unreal`` only in the live backend so its
planning functions can be exercised by the offline harness.

Modes: DRY / APPLY / REVERT, with exact confirmation strings.  DRY is read-only.
APPLY owns only terminal nested-section end frames, explicitly selected I2
transform channels, and explicitly selected F17 fix tracks.  REVERT restores
those exact edits from the transaction record; it never deletes an asset.
"""

from __future__ import print_function

import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil


TOOL = "I2_POLISH"
TOOL_VERSION = "2026-10-09a"
FOLDER = "I2Polish_20261009"
MAP_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
I2_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"
I2_LABEL_PREFIX = "Interaction 2"
EXPECTED_I2_END = 1950
SLEIGHT_FRAME = 1250
FALL_RELEASE_FRAME = 1675
FALL_END_FRAME = 1925
RECORD = "i2_polish_record.json"
PLAN = "i2_polish_plan.json"
CONFIRMS = {
    "DRY": "DRY I2POLISH",
    "APPLY": "APPLY I2POLISH",
    "REVERT": "REVERT I2POLISH",
}
TRANSFORM_CLASS = "MovieScene3DTransformTrack"
POSE_CHANNELS = (
    "Location.X", "Location.Y", "Location.Z",
    "Rotation.X", "Rotation.Y", "Rotation.Z",
    "Scale.X", "Scale.Y", "Scale.Z",
)
DEFAULTS = {
    "boundary_scenes": [1, 2, 3, 4, 5, 6],
    "boundary_extend_frames": 1,
    "boundary_apply": True,
    "boundary_probe_file": "",
    "f17_fix_steps": [],
    "f18_window_seconds": 30.0,
    "f18_hold_frame": 1675,
    "f18_target_ids": [],
    "runon_clock": "1:06.09",
    "runon_go_number": "20",
    "runon_window_seconds": 5.0,
    "numeric_tolerance": 1.0e-4,
}


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def merged_params(raw):
    out = dict(DEFAULTS)
    out.update(raw or {})
    out["boundary_scenes"] = [int(v) for v in out["boundary_scenes"]]
    out["boundary_extend_frames"] = int(out["boundary_extend_frames"])
    out["f18_hold_frame"] = int(out["f18_hold_frame"])
    out["f18_window_seconds"] = float(out["f18_window_seconds"])
    out["runon_window_seconds"] = float(out["runon_window_seconds"])
    out["numeric_tolerance"] = float(out["numeric_tolerance"])
    if out["boundary_extend_frames"] < 1:
        raise PlanError("BOUNDARY_EXTEND_MUST_BE_POSITIVE")
    if out["f18_hold_frame"] < 0:
        raise PlanError("F18_HOLD_FRAME_NEGATIVE")
    if not isinstance(out["f17_fix_steps"], list) or not isinstance(out["f18_target_ids"], list):
        raise PlanError("FIX_AND_TARGET_LISTS_REQUIRED")
    return out


def parse_clock(text):
    """Parse m:ss.cc (centiseconds), m:ss, or raw seconds."""
    value = str(text).strip()
    if ":" not in value:
        return float(value)
    minute, rest = value.split(":", 1)
    return int(minute) * 60.0 + float(rest)


_GO_RE = re.compile(r"^GO\s+([0-9]+(?:\.[0-9]+)?)(?:\s+(HOLD|PASS))?(?:\s+(.*))?$")


def parse_go_marker(label, default_hold=True):
    """Match the runtime's case-sensitive GO grammar."""
    match = _GO_RE.match(str(label).strip())
    if not match:
        return None
    mode = match.group(2)
    return {
        "number": match.group(1),
        "mode": mode or ("HOLD" if default_hold else "PASS"),
        "explicit": mode is not None,
        "label": match.group(3) or "",
    }


def runon_report(i2_markers, master_markers, fps, master_start, params, declared_unpausable=False):
    target_s = parse_clock(params["runon_clock"])
    target_local = int(round(target_s * float(fps)))
    window = int(round(params["runon_window_seconds"] * float(fps)))
    parsed = []
    vamps = []
    for row in i2_markers:
        label = str(row["label"])
        go = parse_go_marker(label, default_hold=True)
        item = dict(row)
        if go:
            item.update({"kind": "GO", "go": go})
            if declared_unpausable and go["mode"] == "HOLD":
                item["effective_mode"] = "PASS"
                item["demoted_by_declared_unpausable"] = True
            else:
                item["effective_mode"] = go["mode"]
            parsed.append(item)
        elif label.lower() in ("infinitystage.vampstart", "infinitystage.vampend"):
            item["kind"] = "VAMP_START" if label.lower().endswith("start") else "VAMP_END"
            parsed.append(item)
            vamps.append(item)
        elif "hold" in label.lower() or "vamp" in label.lower() or label.startswith("GO"):
            item["kind"] = "LOOKALIKE_NOT_RUNTIME_MARKER"
            parsed.append(item)
    stack = None
    ranges = []
    for row in sorted(vamps, key=lambda x: (int(x["frame"]), x["kind"])):
        if row["kind"] == "VAMP_START":
            stack = int(row["frame"])
        elif stack is not None and int(row["frame"]) > stack:
            ranges.append([stack, int(row["frame"])])
            stack = None
    master_target = int(master_start) + target_local
    master_near = [dict(row) for row in master_markers
                   if abs(int(row["frame"]) - master_target) <= window]
    go_near = [row for row in parsed if row.get("kind") == "GO"
               and row["go"]["number"] == str(params["runon_go_number"])
               and abs(int(row["frame"]) - target_local) <= window]
    exact_or_nearest = sorted(go_near, key=lambda x: abs(int(x["frame"]) - target_local))
    target_go = exact_or_nearest[0] if exact_or_nearest else None
    blockers = []
    if target_go is None:
        blockers.append("NO_GO_MARKER_NEAR_TARGET")
    elif target_go["effective_mode"] != "PASS":
        blockers.append("TARGET_GO_IS_HOLD")
    if any(a <= target_local < b for a, b in ranges):
        blockers.append("TARGET_INSIDE_VAMP")
    return {
        "clock": params["runon_clock"],
        "go_number": str(params["runon_go_number"]),
        "target_seconds": target_s,
        "target_local_frame": target_local,
        "target_master_frame": master_target,
        "i2_markers": parsed,
        "master_markers_near": master_near,
        "vamp_ranges": ranges,
        "target_go": target_go,
        "declared_unpausable": bool(declared_unpausable),
        "source_guaranteed": not blockers,
        "blockers": blockers,
        "note": "Source/marker guarantee only; live transport behaviour remains a conductor test.",
    }


def boundary_plan(scene, extend_frames=1):
    """Plan one-frame nested-tail coverage without rebinding a camera."""
    end = int(scene["playback"][1])
    tails = [row for row in scene.get("nested", [])
             if row.get("active") and int(row["range"][1]) == end and row.get("final_camera")]
    if not tails:
        return {"scene": scene["scene"], "sequence": scene["sequence"], "status": "NO_TERMINAL_NESTED_CAMERA"}
    if len(tails) != 1:
        return {"scene": scene["scene"], "sequence": scene["sequence"], "status": "AMBIGUOUS_TERMINAL_NESTED",
                "candidates": tails}
    row = tails[0]
    root_tail = [cut for cut in scene.get("root_cuts", []) if cut.get("active") and int(cut["range"][1]) == end]
    return {
        "scene": scene["scene"],
        "sequence": scene["sequence"],
        "status": "READY",
        "locator": row["locator"],
        "nested_sequence": row["sequence"],
        "nested_final_camera": row["final_camera"],
        "root_tail_cameras": [cut.get("camera") for cut in root_tail],
        "before_end": end,
        "after_end": end + int(extend_frames),
        "reason": "Keep the terminal nested camera evaluating on the parent boundary frame; no camera rebinding.",
    }


def boundary_probe_evidence(probe, scene_number):
    """A natural seam changes target once; two or more changes are a glitch candidate."""
    seams = list(probe.get("seams") or [])
    rows = list(probe.get("rows") or [])
    hits = [(index, seam) for index, seam in enumerate(seams)
            if str(seam.get("left", "")).startswith("Scene %d" % int(scene_number))
            and str(seam.get("right", "")).startswith("Interaction ")]
    if len(hits) != 1:
        return {"status": "SEAM_COUNT", "count": len(hits), "supports_fix": False}
    seam_index, seam = hits[0]
    samples = sorted([row for row in rows if int(row.get("seam_index", -1)) == seam_index],
                     key=lambda x: int(x.get("offset", 0)))
    if not samples:
        return {"status": "NO_ROWS", "supports_fix": False, "seam": seam}
    changes = []
    for index, row in enumerate(samples):
        if index == 0 or row.get("view_target") != samples[index - 1].get("view_target"):
            changes.append({"offset": int(row.get("offset", 0)), "view_target": row.get("view_target")})
    transition_count = max(0, len(changes) - 1)
    return {"status": "OK", "seam": seam, "samples": samples, "changes": changes,
            "transition_count": transition_count, "supports_fix": transition_count >= 2,
            "rule": "one target transition is normal; two or more inside the +/- probe pad supports boundary churn"}


def _linear_value(keys, frame):
    rows = sorted([[int(k[0]), float(k[1])] for k in keys], key=lambda x: x[0])
    if not rows:
        raise PlanError("CHANNEL_WITHOUT_KEYS")
    if frame <= rows[0][0]:
        return rows[0][1]
    if frame >= rows[-1][0]:
        return rows[-1][1]
    for left, right in zip(rows, rows[1:]):
        if left[0] <= frame <= right[0]:
            if right[0] == left[0]:
                return right[1]
            alpha = (frame - left[0]) / float(right[0] - left[0])
            return left[1] + (right[1] - left[1]) * alpha
    return rows[-1][1]


def hold_key_plan(keys, hold_frame, end_frame, tolerance=1.0e-4):
    rows = sorted([[int(k[0]), float(k[1])] for k in keys], key=lambda x: x[0])
    held = _linear_value(rows, int(hold_frame))
    before = [row for row in rows if row[0] < int(hold_frame)]
    after = before + [[int(hold_frame), held], [int(end_frame) - 1, held]]
    changed = any(abs(_linear_value(rows, f) - held) > tolerance
                  for f in sorted({int(hold_frame), int(end_frame) - 1} | {r[0] for r in rows if hold_frame <= r[0] < end_frame}))
    return {"before": rows, "after": after, "held_value": held, "changed": changed}


def movement_plan(channels, hold_frame, end_frame, selected_ids, tolerance=1.0e-4):
    candidates = []
    by_id = {row["id"]: row for row in channels}
    for row in channels:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        plan = hold_key_plan(keys, hold_frame, end_frame, tolerance)
        late_keys = [k for k in keys if hold_frame <= int(k[0]) < end_frame]
        if plan["changed"] or len(late_keys) > 1:
            item = dict(row)
            item.update({"late_keys": late_keys, "hold_plan": plan, "selected": row["id"] in selected_ids})
            candidates.append(item)
    unknown = sorted(set(selected_ids) - set(by_id))
    selected = [row for row in candidates if row["id"] in selected_ids]
    refused = []
    if unknown:
        refused.append("F18_UNKNOWN_TARGETS|%s" % json.dumps(unknown))
    for row in selected:
        modes = set(row.get("interpolation") or [])
        if modes - {"LINEAR", "RCIM_LINEAR", "RichCurveInterpMode.RCIM_LINEAR"}:
            refused.append("F18_NONLINEAR_TARGET|%s|%s" % (row["id"], sorted(modes)))
    return {"candidates": candidates, "selected": selected, "refusals": refused}


def movement_inventory(channels, start_frame, end_frame, tolerance=1.0e-4):
    """List every transform channel whose keyed linear value changes in a window."""
    rows = []
    for channel in channels:
        keys = channel.get("keys") or []
        if not keys:
            continue
        frames = sorted({int(start_frame), int(end_frame) - 1} |
                        {int(k[0]) for k in keys if start_frame <= int(k[0]) < end_frame})
        values = [_linear_value(keys, frame) for frame in frames]
        if max(values) - min(values) <= tolerance:
            continue
        row = dict(channel)
        row.update({"window": [int(start_frame), int(end_frame)],
                    "window_samples": [[frame, value] for frame, value in zip(frames, values)],
                    "delta": max(values) - min(values)})
        rows.append(row)
    return rows


def validate_fix_steps(steps, end_frame):
    allowed = {"PPV_WEIGHT", "LIGHT_HIDE", "LIGHT_DIM", "ACTOR_HIDE"}
    out = []
    for raw in steps:
        row = dict(raw)
        if row.get("kind") not in allowed or not row.get("id") or not row.get("actor_label"):
            raise PlanError("F17_FIX_STEP_SHAPE|%r" % raw)
        keys = row.get("keys")
        if not keys:
            raise PlanError("F17_FIX_STEP_KEYS|%s" % row["id"])
        clean = []
        for key in keys:
            if not isinstance(key, list) or len(key) != 2:
                raise PlanError("F17_FIX_KEY_SHAPE|%s" % row["id"])
            frame = int(key[0])
            if frame < 0 or frame > int(end_frame):
                raise PlanError("F17_FIX_KEY_OUTSIDE_I2|%s|%d" % (row["id"], frame))
            value = key[1]
            if row["kind"] in ("LIGHT_HIDE", "ACTOR_HIDE") and not isinstance(value, bool):
                raise PlanError("F17_VISIBILITY_VALUES_ARE_VISIBLE_BOOLS|%s" % row["id"])
            clean.append([frame, value])
        row["keys"] = clean
        out.append(row)
    return out


def _plain(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if hasattr(value, "to_tuple"):
        return list(value.to_tuple())
    return str(value)


def _guid(value):
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def _asset_file(path):
    import unreal
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.join(root, *path[len("/Game/"):].split("/")) + ".uasset"


def _json_read(path, required=False):
    if not os.path.isfile(path):
        if required:
            raise Stop("MISSING_JSON|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")


class UnrealBackend(object):
    def __init__(self, tool_root=None):
        import unreal
        self.u = unreal
        self.root = tool_root or os.path.dirname(os.path.abspath(__file__))

    def log(self, message):
        self.u.log(message)

    def fail(self, message):
        self.u.log_error(message)
        raise Stop(message)

    def census(self):
        lib = self.u.EditorLoadingAndSavingUtils
        return {
            "content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages()),
        }

    def preflight(self, mode, run, confirm):
        if confirm != CONFIRMS[mode]:
            self.fail("%s_FAILED|run=%s|CONFIRM|expected=%s" % (TOOL, run, CONFIRMS[mode]))
        world = self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem).get_editor_world()
        if world is None or str(world.get_path_name()).split(".")[0] != MAP_PATH:
            self.fail("%s_FAILED|run=%s|WORLD|%s" % (TOOL, run, world))
        game = self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem).get_game_world()
        if game is not None:
            self.fail("%s_FAILED|run=%s|PIE_OR_SIE_RUNNING" % (TOOL, run))
        census = self.census()
        if census != {"content": [], "maps": []}:
            self.fail("%s_FAILED|run=%s|DIRTY_AT_START|%s" % (TOOL, run, json.dumps(census)))

    def _rate(self, seq):
        value = seq.get_display_rate()
        return value.numerator / float(value.denominator)

    def _marker_rows(self, seq):
        ext = self.u.MovieSceneSequenceExtensions
        tick = seq.get_tick_resolution()
        display = seq.get_display_rate()
        ratio = (tick.numerator / float(tick.denominator)) / (display.numerator / float(display.denominator))
        return sorted([{"frame": int(round(int(m.frame_number.value) / ratio)), "label": str(m.label)}
                       for m in ext.get_marked_frames(seq)], key=lambda x: (x["frame"], x["label"]))

    def _section_range(self, section, seq):
        start = section.get_start_frame() if section.has_start_frame() else seq.get_playback_start()
        end = section.get_end_frame() if section.has_end_frame() else seq.get_playback_end()
        return [int(start), int(end)]

    def _binding_names(self, seq):
        return {_guid(binding.get_id()): str(binding.get_display_name()) for binding in seq.get_bindings()}

    def _camera_cuts(self, seq):
        names = self._binding_names(seq)
        rows = []
        for track_index, track in enumerate(seq.get_tracks()):
            if track.get_class().get_name() != "MovieSceneCameraCutTrack":
                continue
            for section_index, section in enumerate(track.get_sections()):
                try:
                    guid = _guid(section.get_camera_binding_id().get_editor_property("guid"))
                except Exception:
                    guid = "?"
                rows.append({"range": self._section_range(section, seq), "active": bool(section.is_active()),
                             "camera_guid": guid, "camera": names.get(guid, "?" + guid),
                             "locator": {"track_index": track_index, "section_index": section_index}})
        return rows

    def _final_camera(self, seq, depth=0):
        if seq is None or depth > 4:
            return None
        end = int(seq.get_playback_end())
        cuts = [row for row in self._camera_cuts(seq) if row["active"] and row["range"][0] <= end - 1 < row["range"][1]]
        if len(cuts) == 1:
            return cuts[0]["camera"]
        nested = self._nested(seq, depth + 1)
        tails = [row for row in nested if row["active"] and row["range"][0] <= end - 1 < row["range"][1]]
        return tails[0].get("final_camera") if len(tails) == 1 else None

    def _nested(self, seq, depth=0):
        rows = []
        for track_index, track in enumerate(seq.get_tracks()):
            if track.get_class().get_name() not in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
                continue
            for section_index, section in enumerate(track.get_sections()):
                sub = section.get_sequence()
                rows.append({
                    "range": self._section_range(section, seq),
                    "active": bool(section.is_active()),
                    "sequence": sub.get_path_name().split(".")[0] if sub else None,
                    "final_camera": self._final_camera(sub, depth + 1) if sub else None,
                    "locator": {"track_index": track_index, "section_index": section_index,
                                "track_class": track.get_class().get_name(),
                                "sub_sequence": sub.get_path_name().split(".")[0] if sub else None},
                })
        return rows

    def scene_rows(self, show):
        rows = []
        for cue in list(show.get_editor_property("cues")):
            label = str(cue.get_editor_property("label"))
            match = re.match(r"^Scene\s+(\d+)", label)
            if not match or not bool(cue.get_editor_property("enabled")):
                continue
            scene = cue.get_editor_property("scene")
            seq = scene.get_editor_property("sequence")
            if seq is None:
                continue
            rows.append({"scene": int(match.group(1)), "label": label,
                         "sequence": seq.get_path_name().split(".")[0],
                         "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
                         "root_cuts": self._camera_cuts(seq), "nested": self._nested(seq)})
        return sorted(rows, key=lambda x: x["scene"])

    def _channel_rows(self, seq):
        rows = []
        for binding in seq.get_bindings():
            for track_index, track in enumerate(binding.get_tracks()):
                if track.get_class().get_name() != TRANSFORM_CLASS:
                    continue
                for section_index, section in enumerate(track.get_sections()):
                    channels = list(section.get_all_channels())
                    for channel_index, channel in enumerate(channels):
                        name = str(channel.channel_name)
                        if name not in POSE_CHANNELS:
                            continue
                        keys, interp = [], []
                        for key in channel.get_keys():
                            keys.append([int(key.get_time().frame_number.value), float(key.get_value())])
                            try:
                                mode = str(key.get_interpolation_mode()).split(".")[-1]
                                interp.append(mode)
                            except Exception:
                                interp.append("UNREADABLE")
                        ident = "%s|%d|%d|%d|%s" % (_guid(binding.get_id()), track_index, section_index, channel_index, name)
                        rows.append({"id": ident, "binding_guid": _guid(binding.get_id()),
                                     "binding": str(binding.get_display_name()), "track_index": track_index,
                                     "track": str(track.get_display_name()), "section_index": section_index,
                                     "channel_index": channel_index, "channel": name, "keys": sorted(keys),
                                     "interpolation": sorted(set(interp)), "sequence": I2_PATH})
        return rows

    def _i2_cue(self, show):
        rows = []
        for cue in list(show.get_editor_property("cues")):
            if str(cue.get_editor_property("label")).startswith(I2_LABEL_PREFIX) and cue.get_editor_property("enabled"):
                rows.append(cue)
        if len(rows) != 1:
            self.fail("I2_CUE_COUNT|%d" % len(rows))
        return rows[0]

    def _master_i2_start(self, master):
        hits = []
        for track in master.get_tracks():
            if track.get_class().get_name() not in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
                continue
            for section in track.get_sections():
                sub = section.get_sequence()
                if sub and sub.get_path_name().split(".")[0] == I2_PATH and section.is_active():
                    hits.append(self._section_range(section, master)[0])
        if len(hits) != 1:
            self.fail("MASTER_I2_SECTION_COUNT|%d" % len(hits))
        return hits[0]

    def _load_i2_order(self):
        path = os.path.normpath(os.path.join(self.root, "..", "I2Order_20261008", "i2_order.py"))
        spec = importlib.util.spec_from_file_location("p39_i2_order", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _camera_pose(self, seq, binding_name, frame):
        matches = [b for b in seq.get_bindings() if str(b.get_display_name()) == binding_name]
        if len(matches) != 1:
            raise PlanError("F17_CAMERA_BINDING_COUNT|%s|%d" % (binding_name, len(matches)))
        tracks = [t for t in matches[0].get_tracks() if t.get_class().get_name() == TRANSFORM_CLASS]
        if len(tracks) != 1:
            raise PlanError("F17_CAMERA_TRANSFORM_COUNT|%s|%d" % (binding_name, len(tracks)))
        values = {}
        for channel in list(tracks[0].get_sections())[0].get_all_channels():
            name = str(channel.channel_name)
            if name not in POSE_CHANNELS:
                continue
            vals = list(channel.evaluate_keys(seq.make_range(int(frame), 1), seq.get_display_rate()))
            if len(vals) != 1:
                raise PlanError("F17_EVALUATE_COUNT|%s|%s|%d" % (binding_name, name, len(vals)))
            values[name] = float(vals[0])
        return {
            "loc": [values.get("Location.X", 0.0), values.get("Location.Y", 0.0), values.get("Location.Z", 0.0)],
            "roll": values.get("Rotation.X", 0.0), "pitch": values.get("Rotation.Y", 0.0),
            "yaw": values.get("Rotation.Z", 0.0),
        }

    def lighting_report(self, seq):
        """Reuse I2Order's already-reviewed light/exposure math, but read P34's tracks directly."""
        order = self._load_i2_order()
        snap = order._snapshot(seq)
        actors = order._actors()
        by_label = {}
        for actor in actors:
            by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
        names = {b["guid"]: b["name"] for b in snap["bindings"]}
        before_name, _ = order.live_camera_at(snap["cuts"], SLEIGHT_FRAME - 1, names)
        after_name, _ = order.live_camera_at(snap["cuts"], SLEIGHT_FRAME, names)
        if before_name is None or after_name is None or before_name == after_name:
            raise PlanError("F17_CUT_NOT_TWO_CAMERAS|%s|%s" % (before_name, after_name))
        drapes = {before_name: "Sleight Hangar Drape", after_name: "Transition Drape (baked)"}

        def side(camera_name, frame):
            pose = self._camera_pose(seq, camera_name, frame)
            drape_binding = [b for b in seq.get_bindings() if str(b.get_display_name()) == drapes[camera_name]]
            if len(drape_binding) != 1:
                raise PlanError("F17_DRAPE_BINDING_COUNT|%s|%d" % (drapes[camera_name], len(drape_binding)))
            template = drape_binding[0].get_object_template()
            root = template.get_editor_property("root_component")
            loc = root.get_editor_property("relative_location")
            point = [float(loc.x), float(loc.y), float(loc.z)]
            yaw = float(root.get_editor_property("relative_rotation").yaw)
            normal = order.rot_z([-1.0, 0.0, 0.0], yaw)
            lights = order._light_rows(actors, snap, frame) + order._spawned_spot_rows(snap, frame)
            lights = [row for row in lights if row["kind"] == "directional" or not row.get("radius")
                      or math.dist(row["loc"], point) < float(row["radius"])]
            volumes = order._ppv_rows(actors, pose["loc"])
            cameras = by_label.get(camera_name, [])
            if len(cameras) != 1:
                raise PlanError("F17_CAMERA_ACTOR_COUNT|%s|%d" % (camera_name, len(cameras)))
            exposure = order.effective_exposure(volumes, order._camera_pp(cameras[0]))
            exposure["unbound"] = {v["id"]: v["unbound"] for v in volumes}
            exposure["rows"] = volumes
            return {"camera": camera_name, "frame": frame, "pose": pose, "point": point,
                    "light": order.side_summary(lights, point, normal), "exposure": exposure,
                    "fog": order._fog_rows(actors, pose["loc"], point)}

        before = side(before_name, SLEIGHT_FRAME - 1)
        after = side(after_name, SLEIGHT_FRAME)
        spots = {}
        for label in (order.NAMES["spot_hangar"], order.NAMES["spot_mouth"]):
            b = [r for r in order._spawned_spot_rows(snap, SLEIGHT_FRAME - 1) if r["label"] == label]
            a = [r for r in order._spawned_spot_rows(snap, SLEIGHT_FRAME) if r["label"] == label]
            spots[label] = (b[0]["intensity"], a[0]["intensity"]) if len(b) == 1 and len(a) == 1 else (None, None)
        ranked = order.rank_cut(before, after, SLEIGHT_FRAME, self._rate(seq), spots, before["fog"], after["fog"])
        proposals = order.proposals_for_cut(ranked, before, after, SLEIGHT_FRAME,
                                           FALL_RELEASE_FRAME, int(seq.get_playback_end()))
        return {"frame": SLEIGHT_FRAME, "seconds": SLEIGHT_FRAME / self._rate(seq),
                "before": before, "after": after, "ranked": ranked, "proposals": proposals,
                "shared_math": "Saved/CodexConductor/I2Order_20261008/i2_order.py"}

    def build_report(self, params, run):
        show = self.u.load_asset(SHOW_PATH)
        master = self.u.load_asset(MASTER_PATH)
        i2 = self.u.load_asset(I2_PATH)
        if show is None or master is None or i2 is None:
            self.fail("LOAD_AUTHORITY")
        playback = [int(i2.get_playback_start()), int(i2.get_playback_end())]
        refusals = []
        if playback != [0, EXPECTED_I2_END]:
            refusals.append("P24_NOT_APPLIED|playback=%s|expected=[0,%d]" % (playback, EXPECTED_I2_END))
        scenes = self.scene_rows(show)
        plans = [boundary_plan(row, params["boundary_extend_frames"]) for row in scenes
                 if row["scene"] in params["boundary_scenes"]]
        if params["boundary_apply"]:
            for row in plans:
                if row["status"] == "AMBIGUOUS_TERMINAL_NESTED":
                    refusals.append("BOUNDARY_AMBIGUOUS|scene=%d" % row["scene"])
        probe = None
        probe_name = str(params.get("boundary_probe_file") or "").strip()
        if params["boundary_apply"]:
            if not probe_name or os.path.basename(probe_name) != probe_name:
                refusals.append("BOUNDARY_PROBE_FILE_REQUIRED|use a basename from this tool folder")
            else:
                probe = _json_read(os.path.join(self.root, probe_name), required=False)
                if not probe or not probe.get("census_unchanged"):
                    refusals.append("BOUNDARY_PROBE_INVALID_OR_DIRTY|%s" % probe_name)
        for row in plans:
            row["probe"] = boundary_probe_evidence(probe, row["scene"]) if probe else {
                "status": "NOT_SUPPLIED", "supports_fix": False}
        hold = movement_plan(self._channel_rows(i2), params["f18_hold_frame"], playback[1],
                             params["f18_target_ids"], params["numeric_tolerance"])
        window_start = max(playback[0], playback[1] - int(round(params["f18_window_seconds"] * self._rate(i2))))
        hold["window_start"] = window_start
        hold["window_inventory"] = movement_inventory(self._channel_rows(i2), window_start, playback[1],
                                                        params["numeric_tolerance"])
        hold["proposals"] = [
            {"id": "END_AT_FALL_RELEASE", "frame": FALL_RELEASE_FRAME,
             "note": "Would require changing P24's approved 1950 end; report only, not owned here."},
            {"id": "HOLD_FROM_FALL_RELEASE", "frame": FALL_RELEASE_FRAME,
             "note": "Freeze explicitly selected movement while the drape falls."},
            {"id": "HOLD_AFTER_FALL", "frame": FALL_END_FRAME,
             "note": "Freeze explicitly selected movement for P24's one-second tail."},
        ]
        refusals += hold["refusals"]
        cue = self._i2_cue(show)
        external = str(cue.get_editor_property("scene").get_editor_property("external_sound"))
        unpausable = "declaredunpausable" in re.sub(r"[^A-Za-z]", "", external).lower()
        runon = runon_report(self._marker_rows(i2), self._marker_rows(master), self._rate(i2),
                             self._master_i2_start(master), params, unpausable)
        try:
            lighting = self.lighting_report(i2)
        except Exception as exc:
            lighting = {"status": "UNCLEAR", "error": "%s: %s" % (type(exc).__name__, exc),
                        "searched": "I2 cut cameras, lights, PPVs, camera PP, fog at frames 1249/1250"}
            refusals.append("F17_AUDIT_UNAVAILABLE|%s" % lighting["error"])
        fixes = validate_fix_steps(params["f17_fix_steps"], playback[1])
        state = {"scenes": scenes, "i2_playback": playback, "movement_channels": self._channel_rows(i2),
                 "i2_markers": self._marker_rows(i2), "master_markers": self._marker_rows(master)}
        report = {"schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "params": params,
                  "apply_ready": not refusals, "refusals": refusals, "boundary": plans,
                  "f17": lighting, "f17_fix_steps": fixes, "f18": hold, "runon": runon,
                  "input_digest": digest(state), "census": self.census(),
                  "proof": {"tier": "measured", "scope": "live DRY reads only; no rendered acceptance"}}
        return report

    def _locate_nested_section(self, seq, locator):
        tracks = list(seq.get_tracks())
        if locator["track_index"] >= len(tracks):
            raise Stop("BOUNDARY_TRACK_GONE")
        track = tracks[locator["track_index"]]
        sections = list(track.get_sections())
        if locator["section_index"] >= len(sections):
            raise Stop("BOUNDARY_SECTION_GONE")
        section = sections[locator["section_index"]]
        sub = section.get_sequence()
        path = sub.get_path_name().split(".")[0] if sub else None
        if track.get_class().get_name() != locator["track_class"] or path != locator["sub_sequence"]:
            raise Stop("BOUNDARY_LOCATOR_DRIFT")
        return section

    def _locate_channel(self, seq, row):
        bindings = [b for b in seq.get_bindings() if _guid(b.get_id()) == row["binding_guid"]]
        if len(bindings) != 1:
            raise Stop("F18_BINDING_DRIFT|%s" % row["id"])
        tracks = list(bindings[0].get_tracks())
        track = tracks[row["track_index"]]
        sections = list(track.get_sections())
        channel = list(sections[row["section_index"]].get_all_channels())[row["channel_index"]]
        if str(channel.channel_name) != row["channel"]:
            raise Stop("F18_CHANNEL_DRIFT|%s" % row["id"])
        return channel

    def _rewrite_float_channel(self, channel, keys):
        for key in list(channel.get_keys()):
            channel.remove_key(key)
        for frame, value in keys:
            channel.add_key(self.u.FrameNumber(int(frame)), float(value),
                            time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=self.u.MovieSceneKeyInterpolation.LINEAR)

    def _actors(self):
        return list(self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors())

    def _new_fix_track(self, seq, step):
        actors = [a for a in self._actors() if str(a.get_actor_label()) == step["actor_label"]]
        if len(actors) != 1:
            raise Stop("F17_ACTOR_COUNT|%s|%d" % (step["actor_label"], len(actors)))
        actor = actors[0]
        names = [(b, str(b.get_display_name())) for b in seq.get_bindings()]
        targets = [b for b, name in names if name == step["actor_label"]]
        created = []
        if len(targets) > 1:
            raise Stop("F17_BINDING_AMBIGUOUS|%s" % step["actor_label"])
        if targets:
            binding = targets[0]
        else:
            before = {_guid(b.get_id()) for b in seq.get_bindings()}
            binding = seq.add_possessable(actor)
            if _guid(binding.get_id()) not in before:
                binding.set_display_name(step["actor_label"])
                created.append(_guid(binding.get_id()))
        kind = step["kind"]
        if kind == "LIGHT_DIM":
            component = actor.get_component_by_class(self.u.LightComponent)
            child_name = step["actor_label"] + "/LightComponent"
            children = [b for b, name in names if name == child_name]
            if children:
                binding = children[0]
            else:
                child = seq.add_possessable(component)
                child.set_parent(binding)
                child.set_display_name(child_name)
                binding = child
                created.append(_guid(child.get_id()))
        if kind in ("LIGHT_HIDE", "ACTOR_HIDE"):
            cls = self.u.MovieSceneVisibilityTrack
            class_name = "MovieSceneVisibilityTrack"
            prop, path = "bHidden", "bHidden"
        else:
            cls = self.u.MovieSceneFloatTrack
            class_name = "MovieSceneFloatTrack"
            prop, path = ("BlendWeight", "blend_weight") if kind == "PPV_WEIGHT" else ("Intensity", "intensity")
        existing = []
        for track in binding.get_tracks():
            if track.get_class().get_name() != class_name:
                continue
            try:
                tprop = str(track.get_property_name())
            except Exception:
                tprop = ""
            if kind in ("LIGHT_HIDE", "ACTOR_HIDE") or tprop == prop:
                existing.append(track)
        if existing:
            raise Stop("F17_TRACK_ALREADY_EXISTS|%s|%s" % (step["actor_label"], prop))
        track_count_before = len(list(binding.get_tracks()))
        track = binding.add_track(cls)
        track.set_property_name_and_path(prop, path)
        section = track.add_section()
        section.set_range(0, EXPECTED_I2_END)
        channel = list(section.get_all_channels())[0]
        for frame, value in step["keys"]:
            if isinstance(value, bool):
                channel.add_key(self.u.FrameNumber(frame), value, time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE)
            else:
                channel.add_key(self.u.FrameNumber(frame), float(value),
                                time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=self.u.MovieSceneKeyInterpolation.LINEAR)
        return {"binding_guid": _guid(binding.get_id()), "track_index": list(binding.get_tracks()).index(track),
                "track_class": track.get_class().get_name(), "track_count_before": track_count_before,
                "created_bindings": created, "step": step}

    def _packages(self, report):
        paths = []
        if report["params"]["boundary_apply"]:
            paths += [row["sequence"] for row in report["boundary"]
                      if row["status"] == "READY" and row.get("probe", {}).get("supports_fix")]
        if report["f17_fix_steps"] or report["f18"]["selected"]:
            paths.append(I2_PATH)
        return sorted(set(paths))

    def _backup(self, run, packages, suffix=""):
        project = self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_dir())
        name = "PreI2Polish%s-%s" % (suffix, run)
        folder = os.path.join(project, "Backups", name)
        os.makedirs(folder)
        copied = []
        for path in packages:
            src = _asset_file(path)
            dst = os.path.join(folder, os.path.basename(src))
            if not os.path.isfile(src):
                raise Stop("BACKUP_SOURCE_MISSING|%s" % src)
            shutil.copy2(src, dst)
            copied.append({"package": path, "source": src, "backup": dst,
                           "sha256": hashlib.sha256(open(dst, "rb").read()).hexdigest()})
        return folder, copied

    def _save(self, packages):
        for path in packages:
            if not self.u.EditorAssetLibrary.save_asset(path, only_if_is_dirty=True):
                raise Stop("SAVE_FAILED|%s" % path)

    def _key_rows(self, channel):
        rows = []
        for key in channel.get_keys():
            value = key.get_value()
            rows.append([int(key.get_time().frame_number.value), bool(value) if isinstance(value, bool) else float(value)])
        return sorted(rows, key=lambda x: x[0])

    def _keys_match(self, got, want, tolerance=1.0e-4):
        if len(got) != len(want):
            return False
        for left, right in zip(got, want):
            if int(left[0]) != int(right[0]):
                return False
            if isinstance(right[1], bool):
                if bool(left[1]) != bool(right[1]):
                    return False
            elif abs(float(left[1]) - float(right[1])) > tolerance:
                return False
        return True

    def _readback(self, record, applied):
        checks = []
        for row in record["boundary"]:
            seq = self.u.load_asset(row["sequence"])
            section = self._locate_nested_section(seq, row["locator"])
            want = int(row["after_end"] if applied else row["before_end"])
            got = int(section.get_end_frame())
            if got != want:
                raise Stop("READBACK_BOUNDARY|scene=%d|got=%d|want=%d" % (row["scene"], got, want))
            checks.append("boundary:S%d=%d" % (row["scene"], got))
        i2 = self.u.load_asset(I2_PATH)
        for row in record["f18"]:
            channel = self._locate_channel(i2, row["locator"])
            got = self._key_rows(channel)
            want = row["after"] if applied else row["before"]
            if not self._keys_match(got, want):
                raise Stop("READBACK_F18|%s|got=%s|want=%s" % (row["locator"]["id"], got, want))
            checks.append("f18:%s=%dkeys" % (row["locator"]["id"], len(got)))
        for row in record["f17"]:
            bindings = [b for b in i2.get_bindings() if _guid(b.get_id()) == row["binding_guid"]]
            if applied:
                if len(bindings) != 1:
                    raise Stop("READBACK_F17_BINDING|%s" % row["step"]["id"])
                tracks = list(bindings[0].get_tracks())
                if row["track_index"] >= len(tracks) or tracks[row["track_index"]].get_class().get_name() != row["track_class"]:
                    raise Stop("READBACK_F17_TRACK|%s" % row["step"]["id"])
                got = self._key_rows(list(tracks[row["track_index"]].get_sections())[0].get_all_channels()[0])
                if not self._keys_match(got, row["step"]["keys"]):
                    raise Stop("READBACK_F17_KEYS|%s|got=%s" % (row["step"]["id"], got))
                checks.append("f17:%s=%dkeys" % (row["step"]["id"], len(got)))
            elif row["binding_guid"] not in row["created_bindings"]:
                if len(bindings) != 1 or len(list(bindings[0].get_tracks())) != int(row["track_count_before"]):
                    raise Stop("READBACK_F17_REVERT|%s" % row["step"]["id"])
                checks.append("f17-revert:%s=absent" % row["step"]["id"])
            else:
                if bindings:
                    raise Stop("READBACK_F17_CREATED_BINDING_REMAINS|%s" % row["step"]["id"])
                checks.append("f17-revert:%s=binding-absent" % row["step"]["id"])
        return checks

    def apply(self, report, run):
        packages = self._packages(report)
        if not packages:
            raise Stop("NOTHING_SELECTED_TO_APPLY")
        backup, copied = self._backup(run, packages)
        record_path = os.path.join(self.root, RECORD)
        if os.path.exists(record_path):
            raise Stop("RECORD_EXISTS|REVERT_FIRST")
        record = {"run": run, "applied": False, "backup": backup, "backup_files": copied,
                  "packages": packages, "input_digest": report["input_digest"],
                  "boundary": [], "f18": [], "f17": []}
        _json_write(record_path, record, exclusive=True)
        for row in report["boundary"]:
            if (not report["params"]["boundary_apply"] or row["status"] != "READY"
                    or not row.get("probe", {}).get("supports_fix")):
                continue
            seq = self.u.load_asset(row["sequence"])
            section = self._locate_nested_section(seq, row["locator"])
            if int(section.get_end_frame()) != int(row["before_end"]):
                raise Stop("BOUNDARY_END_DRIFT|scene=%d" % row["scene"])
            seq.modify()
            section.set_end_frame(int(row["after_end"]))
            record["boundary"].append(row)
        i2 = self.u.load_asset(I2_PATH)
        if report["f18"]["selected"] or report["f17_fix_steps"]:
            i2.modify()
        for row in report["f18"]["selected"]:
            channel = self._locate_channel(i2, row)
            self._rewrite_float_channel(channel, row["hold_plan"]["after"])
            record["f18"].append({"locator": {k: row[k] for k in ("id", "binding_guid", "track_index", "section_index", "channel_index", "channel")},
                                  "before": row["hold_plan"]["before"], "after": row["hold_plan"]["after"]})
        for step in report["f17_fix_steps"]:
            record["f17"].append(self._new_fix_track(i2, step))
        dirty = self.census()
        expected = sorted(path for path in packages)
        actual = sorted(dirty["content"] + dirty["maps"])
        if actual != expected:
            raise Stop("DIRTY_SCOPE|expected=%s|actual=%s|NOTHING_SAVED" % (expected, actual))
        self._save(packages)
        final = self.census()
        if final != {"content": [], "maps": []}:
            raise Stop("DIRTY_AFTER_SAVE|%s" % json.dumps(final))
        record["readback"] = self._readback(record, True)
        record["applied"] = True
        record["report"] = report
        _json_write(record_path, record)
        return record

    def revert(self, run):
        record_path = os.path.join(self.root, RECORD)
        record = _json_read(record_path, required=True)
        if not record.get("applied"):
            raise Stop("RECORD_NOT_APPLIED")
        backup, copied = self._backup(run, record["packages"], suffix="Revert")
        for row in record["boundary"]:
            seq = self.u.load_asset(row["sequence"])
            section = self._locate_nested_section(seq, row["locator"])
            if int(section.get_end_frame()) != int(row["after_end"]):
                raise Stop("REVERT_BOUNDARY_DRIFT|scene=%d" % row["scene"])
            seq.modify()
            section.set_end_frame(int(row["before_end"]))
        i2 = self.u.load_asset(I2_PATH)
        if record["f18"] or record["f17"]:
            i2.modify()
        for row in record["f18"]:
            live = dict(row["locator"])
            channel = self._locate_channel(i2, live)
            got = self._key_rows(channel)
            if not self._keys_match(got, row["after"]):
                raise Stop("REVERT_F18_STATE_DRIFT|%s|got=%s" % (row["locator"]["id"], got))
            self._rewrite_float_channel(channel, row["before"])
        for row in reversed(record["f17"]):
            bindings = [b for b in i2.get_bindings() if _guid(b.get_id()) == row["binding_guid"]]
            if len(bindings) != 1:
                raise Stop("REVERT_F17_BINDING_DRIFT|%s" % row["step"]["id"])
            tracks = list(bindings[0].get_tracks())
            if row["track_index"] >= len(tracks) or tracks[row["track_index"]].get_class().get_name() != row["track_class"]:
                raise Stop("REVERT_F17_TRACK_DRIFT|%s" % row["step"]["id"])
            got = self._key_rows(list(tracks[row["track_index"]].get_sections())[0].get_all_channels()[0])
            if not self._keys_match(got, row["step"]["keys"]):
                raise Stop("REVERT_F17_KEYS_DRIFT|%s|got=%s" % (row["step"]["id"], got))
            if len(tracks) != int(row["track_count_before"]) + 1:
                raise Stop("REVERT_F17_OTHER_TRACK_DRIFT|%s" % row["step"]["id"])
            bindings[0].remove_track(tracks[row["track_index"]])
            for guid in reversed(row["created_bindings"]):
                made = [b for b in i2.get_bindings() if _guid(b.get_id()) == guid]
                if len(made) == 1:
                    made[0].remove()
        dirty = self.census()
        actual = sorted(dirty["content"] + dirty["maps"])
        if actual != sorted(record["packages"]):
            raise Stop("REVERT_DIRTY_SCOPE|%s" % json.dumps(dirty))
        self._save(record["packages"])
        if self.census() != {"content": [], "maps": []}:
            raise Stop("REVERT_DIRTY_AFTER_SAVE")
        readback = self._readback(record, False)
        archived = record_path + ".reverted-" + run
        os.rename(record_path, archived)
        return {"backup": backup, "backup_files": copied, "archived_record": archived,
                "packages": record["packages"], "readback": readback}


def _run_id(prefix="I2POLISH"):
    return "%s-%s" % (prefix, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))


def main(args, backend=None, tool_root=None):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or _run_id())
    backend = backend or UnrealBackend(tool_root=tool_root)
    if mode not in CONFIRMS:
        backend.fail("%s_FAILED|run=%s|MODE|%s" % (TOOL, run, mode))
    try:
        params = merged_params(args.get("params") or {})
        backend.preflight(mode, run, args.get("confirm"))
        if mode == "DRY":
            report = backend.build_report(params, run)
            path = os.path.join(backend.root, "i2_polish_dry_%s.json" % run)
            _json_write(path, report)
            _json_write(os.path.join(backend.root, PLAN), {"run": run, "input_digest": report["input_digest"],
                                                            "params": params, "report": path})
            if backend.census() != {"content": [], "maps": []}:
                raise Stop("DRY_DIRTIED|%s" % json.dumps(backend.census()))
            backend.log("I2_POLISH_DRY_OK|run=%s|mutated=0|apply_ready=%d|boundary_ready=%d|f17=%s|f18_candidates=%d|f18_selected=%d|runon_guaranteed=%d|refusals=%d|report=%s" % (
                run, int(report["apply_ready"]), sum(1 for r in report["boundary"] if r["status"] == "READY"),
                report["f17"].get("status", "OK"), len(report["f18"]["candidates"]), len(report["f18"]["selected"]),
                int(report["runon"]["source_guaranteed"]), len(report["refusals"]), path))
            return report
        if mode == "APPLY":
            plan = _json_read(os.path.join(backend.root, PLAN), required=True)
            report = backend.build_report(params, run)
            if not report["apply_ready"]:
                raise Stop("APPLY_NOT_READY|%s" % json.dumps(report["refusals"]))
            if plan["input_digest"] != report["input_digest"] or plan["params"] != params:
                raise Stop("DRY_STATE_OR_ARGS_DRIFT|RERUN_DRY")
            record = backend.apply(report, run)
            backend.log("I2_POLISH_APPLY_OK|run=%s|boundary=%d|f17=%d|f18=%d|saved=%s|backup=%s|record=%s|dirty=0" % (
                run, len(record["boundary"]), len(record["f17"]), len(record["f18"]),
                ",".join(record["packages"]), record["backup"], os.path.join(backend.root, RECORD)))
            return record
        result = backend.revert(run)
        backend.log("I2_POLISH_REVERT_OK|run=%s|saved=%s|backup=%s|record=%s|dirty=0" % (
            run, ",".join(result["packages"]), result["backup"], result["archived_record"]))
        return result
    except (PlanError, Stop) as exc:
        backend.fail("I2_POLISH_%s_FAILED|run=%s|%s" % (mode, run, exc))
