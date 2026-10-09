"""P79 guarded authoring tool for the post-I4 Nap interlude.

The pure planner imports no Unreal module.  The live backend is isolated behind
an injectable interface so ``test_nap_interlude.py`` can exercise DRY, APPLY and
REVERT without opening Unreal.  This file was authored offline and has not been
run in an editor.

The tool inserts one Sequence cue immediately after I4 and before P05, builds a self-contained
sleeping-cat sequence, rebuilds the managed Master, verifies the exact downstream
shift (including Passage keys carried by patch-K source behaviour), and emits a
one-loop MRQ capture specification.  Creative values are arguments with defaults.
"""

from __future__ import division

import copy
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import struct
import zlib


TOOL = "P79_NAP"
VERSION = "2026-10-09b"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
LEVEL = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
NAP_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_Nap_BatteryChange"
PLAN_NAME = "nap_interlude_plan.json"
MARK_VAMP_START = "InfinityStage.VampStart"
MARK_VAMP_END = "InfinityStage.VampEnd"
MASTER_CUE_LABEL = "Nap — battery change"
OWNER_TAG = "P79_NAP_OWNED"
DEFAULT_GUID = "79579A60416749D3B77E0F58A87C986B"
REQUIRED_TESTS = (
    "InfinityStage.Editor.SavedMasterMatchesShow",
    "InfinityStage.Editor.SceneCutBindingsResolve",
)


class PlanError(ValueError):
    pass


class Stop(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_json(path):
    if not os.path.isfile(path):
        raise PlanError("JSON_MISSING|%s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def norm_guid(value):
    return re.sub(r"[^0-9A-F]", "", str(value).upper())


def identity_label(value):
    text = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    return re.sub(r"\b0+([1-9][0-9]*)\b", r"\1", text)


def parse_go_marker(text):
    """Pure-Python mirror of InfinityStageGoCues::ParseMarkerLabel."""
    words = str(text).strip().split()
    if len(words) < 2 or words[0] != "GO":
        return None
    candidate = words[1]
    if not any(char.isdigit() for char in candidate) or any(
            not (char.isdigit() or char == ".") for char in candidate):
        return None
    mode = -1
    label_start = 2
    if len(words) > 2 and words[2] == "HOLD":
        mode, label_start = 1, 3
    elif len(words) > 2 and words[2] == "PASS":
        mode, label_start = 0, 3
    return candidate, " ".join(words[label_start:]), mode


def _int(value, name):
    if isinstance(value, bool):
        raise PlanError("%s_NOT_INTEGER" % name)
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise PlanError("%s_NOT_INTEGER" % name)
    if float(value) != float(result):
        raise PlanError("%s_NOT_INTEGER" % name)
    return result


def normalise_args(raw):
    p = copy.deepcopy(raw or {})
    p.setdefault("show_package", SHOW)
    p.setdefault("master_package", MASTER)
    p.setdefault("level_package", LEVEL)
    p.setdefault("sequence_package", NAP_SEQUENCE)
    p.setdefault("nap_cue_guid", DEFAULT_GUID)
    p.setdefault("nap_label", MASTER_CUE_LABEL)
    p.setdefault("scene4_label", "Scene 4")
    p.setdefault("interaction4_label", "Interaction 4")
    p.setdefault("passage5_label", "Passage 5")
    p.setdefault("placement_after_label", "Interaction 4")
    p.setdefault("expected_interaction4_guid", "")
    p.setdefault("expected_passage5_guid", "")
    p.setdefault("display_rate", 25)
    p.setdefault("loop_seconds", 20.0)
    p.setdefault("wake_tail_seconds", 1.0)
    p.setdefault("breath_amplitude_cm", 1.5)
    p.setdefault("breath_period_seconds", 4.0)
    p.setdefault("sleep_pose_fraction", 0.85)
    p.setdefault("go_number", "45")
    p.setdefault("cat_mesh", "/Game/CharacterPacks/AnimX/Cats/Realistic/Mesh/SK_Cat_R")
    p.setdefault("sleep_animation", "/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Rest/A_Cat_Rest_Sleep_to")
    p.setdefault("cat_label", "P79_Nap_Puss")
    p.setdefault("camera_label", "P79_Nap_Camera")
    p.setdefault("light_labels", ["P79_Nap_Warm", "P79_Nap_Cool"])
    p.setdefault("cat_transform", {"location": [0.0, 0.0, 100.0], "rotation": [0.0, 0.0, 0.0]})
    p.setdefault("camera_transform", {"location": [-350.0, 0.0, 155.0], "rotation": [0.0, -5.0, 0.0]})
    p.setdefault("camera_drift_cm", [0.0, 0.0, 4.0])
    p.setdefault("camera_focal_length_mm", 65.0)
    p.setdefault("lights", [
        {"label": p["light_labels"][0], "location": [-100.0, -160.0, 260.0],
         "rotation": [0.0, -25.0, 35.0], "color": [255, 181, 118], "intensity": 280.0},
        {"label": p["light_labels"][1], "location": [80.0, 180.0, 220.0],
         "rotation": [0.0, -20.0, -145.0], "color": [125, 170, 255], "intensity": 140.0},
    ])
    p.setdefault("allow_new_shadow_casters", False)
    p.setdefault("fallback_output", "Renders/Fallbacks/Nap_BatteryChange")
    p["display_rate"] = _int(p["display_rate"], "DISPLAY_RATE")
    p["loop_seconds"] = float(p["loop_seconds"])
    p["wake_tail_seconds"] = float(p["wake_tail_seconds"])
    p["breath_amplitude_cm"] = float(p["breath_amplitude_cm"])
    p["breath_period_seconds"] = float(p["breath_period_seconds"])
    p["sleep_pose_fraction"] = float(p["sleep_pose_fraction"])
    p["camera_focal_length_mm"] = float(p["camera_focal_length_mm"])
    p["nap_cue_guid"] = norm_guid(p["nap_cue_guid"])
    p["expected_interaction4_guid"] = norm_guid(p["expected_interaction4_guid"])
    p["expected_passage5_guid"] = norm_guid(p["expected_passage5_guid"])
    if p["nap_label"] != MASTER_CUE_LABEL:
        raise PlanError("CUE_LABEL_MISMATCH|expected=%s|got=%s" % (MASTER_CUE_LABEL, p["nap_label"]))
    if identity_label(p["placement_after_label"]) == identity_label(p["scene4_label"]):
        raise PlanError("PLACEMENT_BETWEEN_S4_I4_REFUSED")
    if identity_label(p["placement_after_label"]) != identity_label(p["interaction4_label"]):
        raise PlanError("PLACEMENT_ANCHOR_NOT_I4|%s" % p["placement_after_label"])
    if p["display_rate"] <= 0 or p["loop_seconds"] <= 0 or p["wake_tail_seconds"] <= 0:
        raise PlanError("TIME_ARGUMENT_NONPOSITIVE")
    if p["breath_period_seconds"] <= 0 or p["breath_amplitude_cm"] < 0:
        raise PlanError("BREATH_ARGUMENT_INVALID")
    if not 0.0 <= p["sleep_pose_fraction"] <= 1.0:
        raise PlanError("SLEEP_POSE_FRACTION")
    if len(p["nap_cue_guid"]) != 32:
        raise PlanError("NAP_GUID_INVALID")
    if len(p["lights"]) > 2:
        raise PlanError("LIGHT_COUNT_GT_2")
    labels = [p["cat_label"], p["camera_label"]] + [x["label"] for x in p["lights"]]
    if len(labels) != len(set(labels)):
        raise PlanError("ACTOR_LABELS_NOT_UNIQUE")
    p["named_packages"] = [p["show_package"], p["master_package"], p["level_package"], p["sequence_package"]]
    return p


def _unique_segment(segments, wanted):
    key = identity_label(wanted)
    rows = [row for row in segments if identity_label(row.get("label", "")) == key]
    if len(rows) != 1:
        raise PlanError("SEGMENT_LABEL_COUNT|%s|%d" % (wanted, len(rows)))
    return rows[0]


def breathing_keys(loop_frames, period_frames, base_z, amplitude):
    if period_frames < 4 or period_frames % 4:
        raise PlanError("BREATH_PERIOD_MUST_BE_WHOLE_AND_DIVISIBLE_BY_4_FRAMES")
    if loop_frames % period_frames:
        raise PlanError("LOOP_NOT_WHOLE_BREATH_CYCLES|loop=%d|period=%d" % (loop_frames, period_frames))
    values = (0.0, 1.0, 0.0, -1.0)
    step = period_frames // 4
    rows = []
    for frame in range(0, loop_frames + 1, step):
        rows.append([frame, float(base_z) + float(amplitude) * values[(frame // step) % 4]])
    return rows


def seam_failures(keys, loop_frames, tolerance=1.0e-4):
    by_frame = {int(row[0]): float(row[1]) for row in keys}
    failures = []
    if 0 not in by_frame or loop_frames not in by_frame:
        return ["SEAM_ENDPOINT_MISSING"]
    if abs(by_frame[0] - by_frame[loop_frames]) > tolerance:
        failures.append("SEAM_VALUE")
    frames = sorted(by_frame)
    if len(frames) < 4:
        failures.append("SEAM_TOO_FEW_KEYS")
    else:
        first_slope = (by_frame[frames[1]] - by_frame[frames[0]]) / (frames[1] - frames[0])
        last_slope = (by_frame[frames[-1]] - by_frame[frames[-2]]) / (frames[-1] - frames[-2])
        if abs(first_slope - last_slope) > tolerance:
            failures.append("SEAM_SLOPE")
    return failures


def expected_segments(before, insert_after_index, nap, delta_ticks):
    start = int(before[insert_after_index]["end"])
    output = []
    for index, row in enumerate(before):
        output.append(copy.deepcopy(row) if index <= insert_after_index else
                      dict(copy.deepcopy(row), start=int(row["start"]) + delta_ticks,
                           end=int(row["end"]) + delta_ticks))
        if index == insert_after_index:
            output.append({"guid": nap["guid"], "label": nap["label"], "type": "Sequence",
                           "start": start, "end": start + delta_ticks,
                           "first_show_index": nap["show_index"]})
    return output


def downstream_timing_failures(before, after, insert_after_index, nap_guid, delta_ticks):
    failures = []
    nap_rows = [row for row in after if norm_guid(row.get("guid")) == norm_guid(nap_guid)]
    if len(nap_rows) != 1:
        return ["NAP_SEGMENT_COUNT|%d" % len(nap_rows)]
    stripped = [row for row in after if norm_guid(row.get("guid")) != norm_guid(nap_guid)]
    if len(stripped) != len(before):
        return ["SEGMENT_COUNT_EXCLUDING_NAP"]
    for index, (old, now) in enumerate(zip(before, stripped)):
        if norm_guid(old["guid"]) != norm_guid(now["guid"]) or old["label"] != now["label"]:
            failures.append("IDENTITY|%d" % index)
            continue
        want = 0 if index <= insert_after_index else int(delta_ticks)
        if int(now["start"]) - int(old["start"]) != want or int(now["end"]) - int(old["end"]) != want:
            failures.append("SHIFT|%s|want=%d" % (old["label"], want))
        if int(now["end"]) - int(now["start"]) != int(old["end"]) - int(old["start"]):
            failures.append("DURATION|%s" % old["label"])
    return failures


def exact_segment_failures(wanted, actual):
    failures = []
    if len(wanted) != len(actual):
        return ["SEGMENT_COUNT|%d!=%d" % (len(actual), len(wanted))]
    for index, (a, b) in enumerate(zip(wanted, actual)):
        for key in ("guid", "label", "type", "start", "end"):
            av, bv = a.get(key), b.get(key)
            if key == "guid":
                av, bv = norm_guid(av), norm_guid(bv)
            if av != bv:
                failures.append("SEGMENT_%s|%d" % (key.upper(), index))
    return failures


def passage_key_failures(before, after, threshold_tick, delta_tick, tolerance=1.0e-4):
    failures = []
    if set(before) != set(after):
        return ["PASSAGE_GUID_SET"]
    for guid, old in before.items():
        now = after[guid]
        shift = delta_tick if int(old["section_start_tick"]) >= threshold_tick else 0
        if int(now["section_start_tick"]) - int(old["section_start_tick"]) != shift:
            failures.append("PASSAGE_SECTION_SHIFT|%s" % guid)
        if set(old.get("channels", {})) != set(now.get("channels", {})):
            failures.append("PASSAGE_CHANNEL_SET|%s" % guid)
            continue
        for name, keys in old.get("channels", {}).items():
            got = now["channels"][name]
            if len(keys) != len(got):
                failures.append("PASSAGE_KEY_COUNT|%s|%s" % (guid, name))
                continue
            for index, (a, b) in enumerate(zip(keys, got)):
                if int(b[0]) - int(a[0]) != shift or abs(float(b[1]) - float(a[1])) > tolerance:
                    failures.append("PASSAGE_KEY|%s|%s|%d" % (guid, name, index))
    return failures


def build_plan(snapshot, raw_args):
    p = normalise_args(raw_args)
    required = ("segments", "passage_keys", "asset_exists", "actor_labels", "tick_resolution")
    missing = [name for name in required if name not in snapshot]
    if missing:
        raise PlanError("SNAPSHOT_MISSING|%s" % ",".join(missing))
    segments = copy.deepcopy(snapshot["segments"])
    s4 = _unique_segment(segments, p["scene4_label"])
    i4 = _unique_segment(segments, p["interaction4_label"])
    p05 = _unique_segment(segments, p["passage5_label"])
    i4_guid, p05_guid = norm_guid(i4["guid"]), norm_guid(p05["guid"])
    if p["expected_interaction4_guid"] and p["expected_interaction4_guid"] != i4_guid:
        raise PlanError("I4_GUID_DRIFT|expected=%s|got=%s" % (p["expected_interaction4_guid"], i4_guid))
    if p["expected_passage5_guid"] and p["expected_passage5_guid"] != p05_guid:
        raise PlanError("P05_GUID_DRIFT|expected=%s|got=%s" % (p["expected_passage5_guid"], p05_guid))
    # Canonicalise discovery into the plan so DRY-with-empty-identities and an
    # APPLY that pins the discovered identities have the same plan digest.
    p["expected_interaction4_guid"] = i4_guid
    p["expected_passage5_guid"] = p05_guid
    s4_index, i4_index, p05_index = segments.index(s4), segments.index(i4), segments.index(p05)
    if i4_index != s4_index + 1 or p05_index != i4_index + 1:
        raise PlanError("PLACEMENT_ORDER_DRIFT|expected=S4,I4,P05|got=%d,%d,%d" %
                        (s4_index, i4_index, p05_index))
    if int(s4["end"]) != int(i4["start"]) or int(i4["end"]) != int(p05["start"]):
        raise PlanError("PLACEMENT_BOUNDARY_DRIFT|s4_end=%s|i4_start=%s|i4_end=%s|p05_start=%s" %
                        (s4["end"], i4["start"], i4["end"], p05["start"]))
    if any(norm_guid(row.get("guid")) == p["nap_cue_guid"] or row.get("label") == p["nap_label"] for row in segments):
        raise PlanError("NAP_ALREADY_COMPILED")
    if snapshot["asset_exists"]:
        raise PlanError("NAP_SEQUENCE_ASSET_EXISTS")
    collisions = sorted(set(snapshot["actor_labels"]) &
                        set([p["cat_label"], p["camera_label"]] + [x["label"] for x in p["lights"]]))
    if collisions:
        raise PlanError("ACTOR_LABEL_COLLISION|%s" % collisions)
    fps = p["display_rate"]
    loop_frames = int(round(p["loop_seconds"] * fps))
    tail_frames = int(round(p["wake_tail_seconds"] * fps))
    period_frames = int(round(p["breath_period_seconds"] * fps))
    total_frames = loop_frames + tail_frames
    if abs(loop_frames / float(fps) - p["loop_seconds"]) > 1.0e-9 or \
            abs(tail_frames / float(fps) - p["wake_tail_seconds"]) > 1.0e-9:
        raise PlanError("TIME_NOT_DISPLAY_FRAME_REPRESENTABLE")
    base_z = float(p["cat_transform"]["location"][2])
    breath = breathing_keys(loop_frames, period_frames, base_z, p["breath_amplitude_cm"])
    seam = seam_failures(breath, loop_frames)
    if seam:
        raise PlanError("LOOP_SEAM|%s" % seam)
    tick = float(snapshot["tick_resolution"])
    delta_ticks_f = total_frames * tick / fps
    delta_ticks = int(round(delta_ticks_f))
    if abs(delta_ticks_f - delta_ticks) > 1.0e-7:
        raise PlanError("DURATION_NOT_SHOW_TICK_REPRESENTABLE")
    nap = {"guid": p["nap_cue_guid"], "label": p["nap_label"], "show_index": int(i4["first_show_index"]) + 1}
    after_segments = expected_segments(segments, i4_index, nap, delta_ticks)
    wake_marker = "GO %s PASS %s" % (p["go_number"], p["nap_label"])
    parsed_wake = parse_go_marker(wake_marker)
    if parsed_wake != (str(p["go_number"]), p["nap_label"], 0):
        raise PlanError("WAKE_MARKER_PARSE|%s|%s" % (wake_marker, parsed_wake))
    markers = [[0, MARK_VAMP_START], [loop_frames, MARK_VAMP_END],
               [loop_frames, wake_marker]]
    return {
        "schema_version": 1, "tool": TOOL, "tool_version": VERSION,
        "anchors": {"interaction4_guid": i4_guid, "passage5_guid": p05_guid,
                    "interaction4_segment_index": i4_index, "passage5_segment_index": p05_index,
                    "interaction4_end_tick": int(i4["end"]), "passage5_start_tick": int(p05["start"]),
                    "insert_show_index": nap["show_index"]},
        "nap": nap, "fps": fps, "loop_frames": loop_frames, "wake_tail_frames": tail_frames,
        "total_frames": total_frames, "delta_ticks": delta_ticks, "markers": markers,
        "breathing_z_keys": breath, "seam_failures": seam,
        "content": {"cat_mesh": p["cat_mesh"], "sleep_animation": p["sleep_animation"],
                    "sleep_pose_fraction": p["sleep_pose_fraction"], "cat_transform": p["cat_transform"],
                    "camera_transform": p["camera_transform"], "camera_drift_cm": p["camera_drift_cm"],
                    "camera_focal_length_mm": p["camera_focal_length_mm"], "lights": p["lights"],
                    "allow_new_shadow_casters": bool(p["allow_new_shadow_casters"])},
        "actor_labels": [p["cat_label"], p["camera_label"]] + [x["label"] for x in p["lights"]],
        "segments_before": segments, "segments_expected_after": after_segments,
        "passage_keys_before": copy.deepcopy(snapshot["passage_keys"]),
        "downstream_threshold_tick": int(i4["end"]),
        "named_packages": p["named_packages"],
        "backup_packages": [p["show_package"], p["master_package"], p["level_package"]],
        "fallback_job": {"kind": "sequence_segment_loop", "segment_guid": p["nap_cue_guid"],
                         "master_range_relative_ticks": [0, int(round(loop_frames * tick / fps))],
                         "frames": loop_frames, "fps": fps, "output": p["fallback_output"],
                         "registry_gate": "Cue Desk currently accepts Scene ordinals only"},
        "transition_plan_only": [
            {"option": "fade-through", "note": "fade the held sleeping image through black into P05"},
            {"option": "clouds-rising", "note": "P05 clouds rise over the sleeping silhouette as the dream"},
            {"option": "camera-drift-up", "note": "continue the near-still camera upward into the P05 cloud field"},
        ],
        "params": p,
    }


def verify_after(plan, facts):
    failures = []
    failures += seam_failures(facts.get("breathing_z_keys", []), plan["loop_frames"])
    labels = {row[1]: int(row[0]) for row in facts.get("markers", [])}
    for frame, label in plan["markers"]:
        if labels.get(label) != frame:
            failures.append("MARKER|%s" % label)
    failures += downstream_timing_failures(plan["segments_before"], facts.get("segments", []),
                                           plan["anchors"]["interaction4_segment_index"],
                                           plan["nap"]["guid"], plan["delta_ticks"])
    failures += passage_key_failures(plan["passage_keys_before"], facts.get("passage_keys", {}),
                                     plan["downstream_threshold_tick"], plan["delta_ticks"])
    if sorted(facts.get("owned_actor_labels", [])) != sorted(plan["actor_labels"]):
        failures.append("OWNED_ACTORS")
    if facts.get("sequence_package") != plan["params"]["sequence_package"]:
        failures.append("SEQUENCE_PACKAGE")
    if facts.get("camera_cut_range") != [0, plan["total_frames"]]:
        failures.append("CAMERA_CUT_COVERAGE")
    return failures


def _png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_preview(plan, path):
    width, height = 960, 280
    pixels = [bytearray([244, 239, 228] * width) for _ in range(height)]
    def line(x0, y0, x1, y1, color):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for n in range(steps + 1):
            x = int(round(x0 + (x1 - x0) * n / float(steps)))
            y = int(round(y0 + (y1 - y0) * n / float(steps)))
            if 0 <= x < width and 0 <= y < height:
                pixels[y][3*x:3*x+3] = bytes(color)
    x = lambda f: 50 + int(850 * f / float(plan["total_frames"]))
    for yy in range(55, 105):
        for xx in range(x(0), x(plan["loop_frames"])):
            pixels[yy][3*xx:3*xx+3] = bytes((55, 79, 112))
    for yy in range(55, 105):
        for xx in range(x(plan["loop_frames"]), x(plan["total_frames"])):
            pixels[yy][3*xx:3*xx+3] = bytes((184, 124, 70))
    keys = plan["breathing_z_keys"]
    lo, hi = min(v for _, v in keys), max(v for _, v in keys)
    pts = [(x(f), 220 - int(70 * (v - lo) / max(1.0e-9, hi - lo))) for f, v in keys]
    for a, b in zip(pts, pts[1:]):
        line(a[0], a[1], b[0], b[1], (75, 115, 145))
    for frame, unused_label in plan["markers"]:
        line(x(frame), 40, x(frame), 235, (165, 50, 45))
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    data = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


class UnrealBackend(object):
    """Live-only Unreal adapter; not instantiated by the offline harness."""
    def __init__(self):
        import unreal
        self.ue = unreal
        self.args = None

    def log(self, text):
        self.ue.log(text)

    def stop(self, text):
        self.ue.log_error(text)

    def census(self):
        lib = self.ue.EditorLoadingAndSavingUtils
        clean = lambda p: str(p.get_path_name()).split(".", 1)[0]
        return {"content": sorted(clean(x) for x in lib.get_dirty_content_packages()),
                "maps": sorted(clean(x) for x in lib.get_dirty_map_packages())}

    def preflight(self, args, unused_mode):
        self.args = args
        editor = self.ue.get_editor_subsystem(self.ue.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            raise PlanError("PIE_OR_SIE_ACTIVE")
        if self.ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
            raise PlanError("SEQUENCER_OPEN")
        world = editor.get_editor_world()
        if world is None or str(world.get_outermost().get_name()) != args["level_package"]:
            raise PlanError("WRONG_WORLD")
        if self.census() != {"content": [], "maps": []}:
            raise PlanError("DIRTY_CENSUS|%s" % canonical(self.census()))

    def _guid(self, value):
        return norm_guid(self.ue.GuidLibrary.conv_guid_to_string(value))

    def _segments(self, show):
        ue = self.ue
        cues = list(show.get_editor_property("cues"))
        cue_index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        passage_first = {}
        for row in show.get_editor_property("passage_settings"):
            passage_first[self._guid(row.get_editor_property("passage_guid"))] = cue_index.get(
                self._guid(row.get_editor_property("first_cue_guid")), -1)
        tr = ue.InfinityStageTransportController()
        if not tr.build_segments(show):
            raise PlanError("BUILD_SEGMENTS_FAILED")
        output = []
        for row in tr.get_editor_property("segments"):
            guid = self._guid(row.get_editor_property("segment_guid"))
            kind = str(row.get_editor_property("type")).split(".")[-1]
            output.append({"guid": guid, "label": str(row.get_editor_property("label")), "type": kind,
                           "start": int(row.get_editor_property("start_frame").value),
                           "end": int(row.get_editor_property("end_frame").value),
                           "first_show_index": passage_first.get(guid, cue_index.get(guid, -1))})
        if any(x["first_show_index"] < 0 for x in output):
            raise PlanError("SEGMENT_SHOW_INDEX_UNRESOLVED")
        return output

    def _passage_keys(self, master):
        ue = self.ue
        tick = float(master.get_tick_resolution().numerator) / master.get_tick_resolution().denominator
        output = {}
        for track in master.get_tracks():
            if "InfinityPassage" not in track.get_class().get_name():
                continue
            for section in track.get_sections():
                guid = self._guid(section.get_editor_property("passage_guid"))
                channels = {}
                for channel in section.get_all_channels():
                    name = str(channel.get_editor_property("channel_name"))
                    channels[name] = [[int(k.get_time(time_unit=ue.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                                       float(k.get_value())] for k in channel.get_keys()]
                output[guid] = {"section_start_tick": int(round(section.get_start_frame_seconds() * tick)),
                                "channels": channels}
        return output

    def inspect(self, args, plan=None):
        ue = self.ue
        show, master = ue.load_asset(args["show_package"]), ue.load_asset(args["master_package"])
        actors = ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
        base = {"segments": self._segments(show), "passage_keys": self._passage_keys(master),
                "asset_exists": ue.EditorAssetLibrary.does_asset_exist(args["sequence_package"]),
                "actor_labels": [a.get_actor_label() for a in actors],
                "tick_resolution": float(show.get_editor_property("tick_resolution").numerator) /
                                   show.get_editor_property("tick_resolution").denominator}
        if plan is None or not base["asset_exists"]:
            return base
        seq = ue.load_asset(args["sequence_package"])
        markers = [[int(m.frame_number.value), str(m.label)] for m in
                   seq.get_marked_frames_from_sequence(ue.MovieSceneTimeUnit.DISPLAY_RATE)]
        owned = [a.get_actor_label() for a in actors if OWNER_TAG in [str(x) for x in a.get_editor_property("tags")]]
        cuts = [s for t in seq.find_tracks_by_type(ue.MovieSceneCameraCutTrack) for s in t.get_sections()]
        return dict(base, markers=markers, breathing_z_keys=self._read_breath_keys(seq, plan),
                    owned_actor_labels=owned, sequence_package=args["sequence_package"],
                    camera_cut_range=[int(cuts[0].get_start_frame()), int(cuts[0].get_end_frame())]
                    if len(cuts) == 1 else None)

    def _read_breath_keys(self, seq, plan):
        ue = self.ue
        bindings = [b for b in seq.get_bindings() if str(b.get_display_name()) == plan["params"]["cat_label"]]
        if len(bindings) != 1:
            return []
        for track in bindings[0].get_tracks():
            if track.get_class().get_name() != "MovieScene3DTransformTrack":
                continue
            for channel in track.get_sections()[0].get_all_channels():
                name = re.sub(r"[_ ]\d+$", "", str(channel.get_editor_property("channel_name"))).lower()
                if "location" in name and name.endswith("z"):
                    return [[int(k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value),
                             float(k.get_value())] for k in channel.get_keys()]
        return []

    def backup(self, run, packages, prefix="PreNapInterlude"):
        project = os.path.abspath(self.ue.Paths.project_dir())
        root = os.path.join(project, "Backups", "%s-%s" % (prefix, run))
        os.makedirs(root, exist_ok=False)
        files = []
        for package in packages:
            rel = package[len("/Game/"):].split("/")
            candidates = [os.path.join(project, "Content", *rel) + ext for ext in (".uasset", ".umap")]
            source = next((x for x in candidates if os.path.isfile(x)), None)
            if source is None:
                raise PlanError("BACKUP_SOURCE_MISSING|%s" % package)
            target = os.path.join(root, os.path.basename(source))
            shutil.copy2(source, target)
            files.append({"package": package, "source": source, "backup": target,
                          "bytes": os.path.getsize(target)})
        write_json(os.path.join(root, "manifest.json"), {"run": run, "files": files}, exclusive=True)
        return {"root": root, "files": files}

    def _parse_guid(self, text):
        result = self.ue.GuidLibrary.parse_string_to_guid(text)
        guid, ok = result if isinstance(result, tuple) else (result, True)
        if not ok or self._guid(guid) != norm_guid(text):
            raise PlanError("GUID_PARSE|%s" % text)
        return guid

    def _spawn_content(self, seq, plan):
        ue, p = self.ue, plan["params"]
        eas = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        loc = lambda x: ue.Vector(*[float(v) for v in x])
        rot = lambda x: ue.Rotator(roll=float(x[0]), pitch=float(x[1]), yaw=float(x[2]))
        cat_t, cam_t = p["cat_transform"], p["camera_transform"]
        cat = eas.spawn_actor_from_class(ue.SkeletalMeshActor, loc(cat_t["location"]), rot(cat_t["rotation"]), False)
        camera = eas.spawn_actor_from_class(ue.CineCameraActor, loc(cam_t["location"]), rot(cam_t["rotation"]), False)
        if cat is None or camera is None:
            raise PlanError("SPAWN_CAT_OR_CAMERA")
        cat.set_actor_label(p["cat_label"]); camera.set_actor_label(p["camera_label"])
        actors = [cat, camera]
        comp = cat.get_editor_property("skeletal_mesh_component")
        mesh, anim = ue.load_asset(p["cat_mesh"]), ue.load_asset(p["sleep_animation"])
        if mesh is None or anim is None:
            raise PlanError("CAT_ASSET_MISSING")
        comp.set_skeletal_mesh_asset(mesh)
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(ue.CollisionEnabled.NO_COLLISION)
        comp.set_animation_mode(ue.AnimationMode.ANIMATION_SINGLE_NODE)
        comp.set_animation(anim)
        comp.set_position(float(anim.get_editor_property("sequence_length")) * p["sleep_pose_fraction"], False)
        comp.set_play_rate(0.0)
        camera.get_cine_camera_component().set_editor_property(  # [meas NAP-20261009-144707-APPLY1] no cine_camera_component property in 5.8 Python
            "current_focal_length", p["camera_focal_length_mm"])
        for light in p["lights"]:
            actor = eas.spawn_actor_from_class(ue.RectLight, loc(light["location"]), rot(light["rotation"]), False)
            if actor is None:
                raise PlanError("SPAWN_LIGHT|%s" % light["label"])
            actor.set_actor_label(light["label"])
            lc = actor.get_editor_property("rect_light_component")
            lc.set_editor_property("intensity", float(light["intensity"]))
            lc.set_light_color(ue.Color(*[int(x) for x in light["color"]]))
            lc.set_editor_property("cast_shadows", bool(p["allow_new_shadow_casters"]))
            actors.append(actor)
        for actor in actors:
            actor.set_editor_property("tags", list(actor.get_editor_property("tags")) + [ue.Name(OWNER_TAG)])
            actor.set_actor_hidden_in_game(True)
        bindings = {}
        if list(seq.get_bindings()):
            raise PlanError("NEW_SEQUENCE_ALREADY_HAS_BINDINGS")
        for actor in actors:
            binding = seq.add_possessable(actor)
            if binding is None or not binding.is_valid():
                raise PlanError("ADD_POSSESSABLE|%s" % actor.get_actor_label())
            binding.set_display_name(actor.get_actor_label())
            bindings[actor.get_actor_label()] = binding
            self._visibility(binding, seq, plan["total_frames"])
            self._transform(binding, seq, actor, plan)
        cut = seq.add_track(ue.MovieSceneCameraCutTrack)
        section = cut.add_section(); section.set_range(0, plan["total_frames"])
        section.set_camera_binding_id(seq.get_binding_id(bindings[p["camera_label"]]))
        return actors

    def _visibility(self, binding, seq, end):
        ue = self.ue
        track = binding.add_track(ue.MovieSceneVisibilityTrack)
        track.set_property_name_and_path("bHidden", "bHidden")
        section = track.add_section(); section.set_range(0, end)
        section.set_completion_mode(ue.MovieSceneCompletionMode.RESTORE_STATE)
        channel = list(section.get_all_channels())[0]
        # Despite the bHidden binding, MovieSceneVisibilityTrack's bool channel
        # uses visible semantics (True = visible).  This was live-proven by the
        # Klara hook-in probe and is deliberately not inverted here.
        channel.add_key(ue.FrameNumber(0), True, time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        channel.add_key(ue.FrameNumber(end), True, time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)

    def _transform(self, binding, seq, actor, plan):
        ue = self.ue
        track = binding.add_track(ue.MovieScene3DTransformTrack)
        section = track.add_section(); section.set_range(0, plan["total_frames"])
        tr = actor.get_actor_transform(); loc, q, scale = tr.translation, tr.rotation, tr.scale3d
        euler = q.euler()
        base = {"location.x": loc.x, "location.y": loc.y, "location.z": loc.z,
                "rotation.x": euler.x, "rotation.y": euler.y, "rotation.z": euler.z,
                "scale.x": scale.x, "scale.y": scale.y, "scale.z": scale.z}
        labels = {}
        for channel in section.get_all_channels():
            raw = str(channel.get_editor_property("channel_name"))
            key = re.sub(r"[^a-z0-9.]", "", re.sub(r"[_ ]\d+$", "", raw).lower())
            labels.setdefault(key, []).append(channel)
        for semantic, value in base.items():
            hits = [channel for key, rows in labels.items() if semantic.replace(".", "") in key.replace(".", "") for channel in rows]
            if len(hits) != 1:
                raise PlanError("TRANSFORM_CHANNEL|%s|%d" % (semantic, len(hits)))
            rows = [[0, value], [plan["total_frames"], value]]
            if actor.get_actor_label() == plan["params"]["cat_label"] and semantic == "location.z":
                rows = plan["breathing_z_keys"] + [[plan["total_frames"], value]]
            if actor.get_actor_label() == plan["params"]["camera_label"] and semantic.startswith("location."):
                axis = {"location.x": 0, "location.y": 1, "location.z": 2}[semantic]
                rows[-1][1] += float(plan["params"]["camera_drift_cm"][axis])
            for frame, keyed in rows:
                hits[0].add_key(ue.FrameNumber(int(frame)), float(keyed),
                                time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=ue.MovieSceneKeyInterpolation.LINEAR)

    def apply(self, plan, args):
        ue = self.ue
        tools = ue.AssetToolsHelpers.get_asset_tools()
        folder, name = args["sequence_package"].rsplit("/", 1)
        seq = tools.create_asset(name, folder, ue.LevelSequence, ue.LevelSequenceFactoryNew())
        if seq is None:
            raise PlanError("CREATE_SEQUENCE_FAILED")
        seq.set_display_rate(ue.FrameRate(plan["fps"], 1))
        seq.set_tick_resolution(ue.FrameRate(int(round(self.inspect(args)["tick_resolution"])), 1))
        seq.set_playback_start(0); seq.set_playback_end(plan["total_frames"])
        for frame, label in plan["markers"]:
            marked = ue.MovieSceneMarkedFrame(); marked.frame_number = ue.FrameNumber(int(frame)); marked.label = label
            ue.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(seq, marked, ue.MovieSceneTimeUnit.DISPLAY_RATE)
        self._spawn_content(seq, plan)
        show, master = ue.load_asset(args["show_package"]), ue.load_asset(args["master_package"])
        cues = list(show.get_editor_property("cues"))
        cue = ue.InfinityShowCue(); cue.set_editor_property("cue_guid", self._parse_guid(plan["nap"]["guid"]))
        cue.set_editor_property("type", ue.InfinityCueType.SEQUENCE); cue.set_editor_property("label", plan["nap"]["label"])
        cue.set_editor_property("enabled", True)
        scene = cue.get_editor_property("scene"); scene.set_editor_property("sequence", seq)
        scene.set_editor_property("use_sequence_length", True); scene.set_editor_property("camera_owner", ue.InfinityCameraOwner.TIMELINE)
        cue.set_editor_property("scene", scene)
        cues.insert(plan["nap"]["show_index"], cue); show.set_editor_property("cues", cues)
        if not ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master):
            raise PlanError("REBUILD_MANAGED_MASTER_FAILED")
        return {"affected_passages_materialized": [], "reason": "no Passage authoring data changed"}

    def save(self, packages):
        dirty = sorted(set(self.census()["content"] + self.census()["maps"]))
        if dirty != sorted(packages):
            raise PlanError("UNEXPECTED_DIRTY_PACKAGES|got=%s|want=%s" % (dirty, sorted(packages)))
        for package in packages:
            ok = (self.ue.get_editor_subsystem(self.ue.LevelEditorSubsystem).save_current_level()
                  if package == self.args["level_package"] else
                  self.ue.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True))
            if not ok:
                raise PlanError("SAVE_FAILED|%s" % package)
        if self.census() != {"content": [], "maps": []}:
            raise PlanError("DIRTY_AFTER_SAVE|%s" % canonical(self.census()))
        return list(packages)

    def revert(self, record, args):
        ue, plan = self.ue, record["plan"]
        show, master = ue.load_asset(args["show_package"]), ue.load_asset(args["master_package"])
        cues = list(show.get_editor_property("cues"))
        kept = [c for c in cues if self._guid(c.get_editor_property("cue_guid")) != plan["nap"]["guid"]]
        if len(cues) - len(kept) != 1:
            raise PlanError("REVERT_NAP_CUE_COUNT")
        show.set_editor_property("cues", kept)
        eas = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        owned = [a for a in eas.get_all_level_actors() if OWNER_TAG in [str(x) for x in a.get_editor_property("tags")]]
        if sorted(a.get_actor_label() for a in owned) != sorted(plan["actor_labels"]):
            raise PlanError("REVERT_OWNED_ACTOR_SET")
        for actor in owned:
            eas.destroy_actor(actor)
        if not ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master):
            raise PlanError("REVERT_REBUILD_FAILED")
        archive = "/Game/InfinityStage/Dev/Sequences/_Reverted/LS_Nap_BatteryChange_%s" % record["run_id"]
        if not ue.EditorAssetLibrary.rename_asset(args["sequence_package"], archive):
            raise PlanError("REVERT_ARCHIVE_SEQUENCE_FAILED")
        return {"archived_sequence": archive}


def _root(root=None):
    return os.path.abspath(root or os.path.dirname(__file__))


def _record_path(root, run):
    return os.path.join(root, "nap_interlude_record_%s.json" % run)


def _confirm(mode, run, source):
    return "REVERT NAP %s" % source if mode == "REVERT" else "%s NAP %s" % (mode, run)


def _stop(backend, run, reason):
    message = "%s_STOPPED|run=%s|reason=%s" % (TOOL, run, reason)
    backend.stop(message)
    raise Stop(message)


def run_dry(run, args, backend, root):
    backend.preflight(args, "DRY")
    snapshot = backend.inspect(args)
    plan = build_plan(snapshot, args)
    report = os.path.join(root, "nap_interlude_dry_%s.json" % run)
    preview = write_preview(plan, os.path.join(root, "nap_interlude_preview_%s.png" % run))
    write_json(report, {"run_id": run, "mode": "DRY", "apply_ready": True, "plan": plan,
                        "dirty_package_census": backend.census(), "preview": preview})
    write_json(os.path.join(root, PLAN_NAME), {"run_id": run, "snapshot_digest": digest(snapshot),
                                               "plan_digest": digest(plan), "plan": plan, "report": report})
    backend.log("P79_NAP_DRY_OK|run=%s|i4=%s|p05=%s|loop_frames=%d|writes=0|report=%s|preview=%s" %
                (run, plan["anchors"]["interaction4_guid"], plan["anchors"]["passage5_guid"],
                 plan["loop_frames"], report, preview))
    return plan


def run_apply(run, args, backend, root):
    backend.preflight(args, "APPLY")
    snapshot = backend.inspect(args)
    plan = build_plan(snapshot, args)
    dry = read_json(os.path.join(root, PLAN_NAME))
    if dry.get("snapshot_digest") != digest(snapshot) or dry.get("plan_digest") != digest(plan):
        _stop(backend, run, "CHANGED_SINCE_DRY")
    if args.get("expected_interaction4_guid") != plan["anchors"]["interaction4_guid"] or \
            args.get("expected_passage5_guid") != plan["anchors"]["passage5_guid"]:
        _stop(backend, run, "EXPECTED_GUIDS_REQUIRED_FROM_DRY")
    backup = backend.backup(run, plan["backup_packages"])
    record_path = _record_path(root, run)
    record = {"schema_version": 1, "tool": TOOL, "run_id": run, "status": "prepared",
              "args": args, "plan": plan, "snapshot_before": snapshot, "backup": backup}
    write_json(record_path, record, exclusive=True)
    backend.apply(plan, args)
    facts = backend.inspect(args, plan)
    failures = verify_after(plan, facts)
    expected_dirty = sorted(plan["named_packages"])
    dirty = sorted(set(backend.census()["content"] + backend.census()["maps"]))
    if failures or dirty != expected_dirty:
        _stop(backend, run, "PRESAVE_READBACK|failures=%s|dirty=%s|NOTHING SAVED" % (failures, dirty))
    saved = backend.save(plan["named_packages"])
    facts = backend.inspect(args, plan)
    failures = verify_after(plan, facts)
    if failures or backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "POSTSAVE_READBACK|%s|restore=%s" % (failures, backup["root"]))
    fallback_path = os.path.join(root, "nap_fallback_job_%s.json" % run)
    write_json(fallback_path, plan["fallback_job"])
    record.update({"status": "saved_readback_verified", "snapshot_after": facts, "saved": saved,
                   "fallback_job": fallback_path})
    write_json(record_path, record)
    backend.log("P79_NAP_APPLY_OK|run=%s|saved=%s|backup=%s|record=%s|fallback_job=%s|tests_required_singly=%s" %
                (run, ",".join(saved), backup["root"], record_path, fallback_path, ",".join(REQUIRED_TESTS)))
    return record


def run_revert(run, source, args, backend, root):
    backend.preflight(args, "REVERT")
    record_path = _record_path(root, source)
    record = read_json(record_path)
    if record.get("status") != "saved_readback_verified":
        _stop(backend, run, "SOURCE_RECORD_NOT_APPLIED")
    current = backend.inspect(args, record["plan"])
    failures = verify_after(record["plan"], current)
    if failures:
        _stop(backend, run, "APPLIED_STATE_DRIFT|%s" % failures)
    backup = backend.backup(run, record["plan"]["named_packages"], "PreNapInterludeRevert")
    txn = os.path.join(root, "nap_interlude_revert_%s.json" % run)
    write_json(txn, {"status": "prepared", "run_id": run, "source_run_id": source, "backup": backup}, exclusive=True)
    result = backend.revert(record, args)
    saved = backend.save([args["show_package"], args["master_package"], args["level_package"], result["archived_sequence"]])
    final = backend.inspect(args)
    timing = exact_segment_failures(record["plan"]["segments_before"], final["segments"])
    if timing or final["asset_exists"] or backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "REVERT_READBACK|timing=%s|asset=%s" % (timing, final["asset_exists"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    write_json(txn, {"status": "saved_readback_verified", "run_id": run, "source_run_id": source,
                     "backup": backup, "archived_record": archived, "saved": saved, "result": result})
    backend.log("P79_NAP_REVERT_OK|run=%s|source=%s|saved=%s|backup=%s|record=%s|tests_required_singly=%s" %
                (run, source, ",".join(saved), backup["root"], archived, ",".join(REQUIRED_TESTS)))
    return result


def main(raw, backend=None, root=None):
    raw = copy.deepcopy(raw or {})
    mode = str(raw.get("mode", "DRY")).upper()
    run = str(raw.get("run_id") or datetime.datetime.now().strftime("NAP-%Y%m%d-%H%M%S"))
    source = str(raw.get("source_run_id") or "")
    backend = backend or UnrealBackend()
    root = _root(root)
    try:
        want = _confirm(mode, run, source)
        if raw.get("confirm") != want:
            _stop(backend, run, "CONFIRM_MISMATCH|want=%r|got=%r" % (want, raw.get("confirm")))
        args = normalise_args(raw.get("params") or {})
        if mode == "DRY":
            return run_dry(run, args, backend, root)
        if mode == "APPLY":
            return run_apply(run, args, backend, root)
        if mode == "REVERT" and source:
            return run_revert(run, source, args, backend, root)
        _stop(backend, run, "MODE_OR_SOURCE|%s" % mode)
    except PlanError as error:
        _stop(backend, run, "PLAN_REFUSED|%s" % error)
