"""Job 97 / E18 in-place revision of the already-applied Nap interlude.

Offline-authored: importing this module does not import Unreal.  The live adapter
is created only by main() when no fake backend is supplied.  It edits existing
assets; it never rebuilds the Nap from scratch.
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


TOOL = "E18_NAP_REVISION"
VERSION = "2026-10-09a"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
LEVEL = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
NAP_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_Nap_BatteryChange"
OLD_LABEL = "Nap — battery change"
NEW_LABEL = "Interlude: Puss Sleep/Wet Tennis Ball/Battery"
NAP_GUID = "211B6129497610E7977707AA939D7763"
CAT_LABEL = "P79_Nap_Puss"
CAMERA_LABEL = "P79_Nap_Camera"
LIGHT_LABELS = ("P79_Nap_Warm", "P79_Nap_Cool")
SPOT_NAMES = ("Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)")
INTERACTION_PATHS = {
    1: "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy",
    2: "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips",
    3: "/Game/InfinityStage/Interactions/LS_Interaction_03_ForgetsHisName",
    4: "/Game/InfinityStage/Interactions/LS_Interaction_04_GetsAName",
    5: "/Game/InfinityStage/Interactions/LS_Interaction_05_BecomesKing",
}
AUDIT_ORDER = (4, 1, 2, 3, 5)
OWNER_TAG = "P79_NAP_OWNED"
PLAN_FILE = "e18_nap_revision_plan.json"


class PlanError(ValueError):
    pass


class Stop(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def norm_guid(value):
    return re.sub(r"[^0-9A-F]", "", str(value).upper())


def enum_tail(value):
    """UE 5.8 str(enum) is '<E.V: n>'; return V without trusting formatting."""
    text = str(value)
    hit = re.search(r"\.([A-Z0-9_]+)(?::|>)", text, re.I)
    return hit.group(1) if hit else text.split(".")[-1].split(":")[0].strip(" <>" )


def channel_semantic(value):
    """Normalise UE channel suffixes such as 'Location.Z_0' or 'Roll 1'."""
    text = re.sub(r"[_ ]\d+$", "", str(value)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def read_json(path):
    if not os.path.isfile(path):
        raise PlanError("JSON_MISSING|%s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def normalise_args(raw):
    p = copy.deepcopy(raw or {})
    p.setdefault("show_package", SHOW)
    p.setdefault("master_package", MASTER)
    p.setdefault("level_package", LEVEL)
    p.setdefault("nap_sequence", NAP_SEQUENCE)
    p.setdefault("recorded_nap_guid", NAP_GUID)
    p.setdefault("old_label", OLD_LABEL)
    p.setdefault("new_label", NEW_LABEL)
    p.setdefault("go_number", "45")
    p.setdefault("camera_ground_z_cm", 45.0)
    p.setdefault("camera_breath_amplitude_cm", 1.25)
    p.setdefault("camera_breath_roll_deg", 0.20)
    p.setdefault("camera_breath_period_seconds", 4.0)
    p.setdefault("expected_master_start_seconds", 1490.64)
    p.setdefault("expected_master_end_seconds", 1511.64)
    p.setdefault("nap_light_intensities", {LIGHT_LABELS[0]: 18.0, LIGHT_LABELS[1]: 8.0})
    p["recorded_nap_guid"] = norm_guid(p["recorded_nap_guid"])
    if len(p["recorded_nap_guid"]) != 32:
        raise PlanError("RECORDED_GUID_INVALID")
    if p["old_label"] != OLD_LABEL or p["new_label"] != NEW_LABEL:
        raise PlanError("LABEL_CONTRACT_DRIFT")
    for key in ("camera_ground_z_cm", "camera_breath_amplitude_cm", "camera_breath_roll_deg",
                "camera_breath_period_seconds", "expected_master_start_seconds", "expected_master_end_seconds"):
        p[key] = float(p[key])
    if p["camera_breath_period_seconds"] <= 0 or p["camera_breath_amplitude_cm"] < 0:
        raise PlanError("CAMERA_BREATH_ARGS")
    if set(p["nap_light_intensities"]) != set(LIGHT_LABELS):
        raise PlanError("LIGHT_LABEL_SET")
    p["nap_light_intensities"] = {k: float(v) for k, v in p["nap_light_intensities"].items()}
    if any(v < 0 for v in p["nap_light_intensities"].values()):
        raise PlanError("LIGHT_INTENSITY_NEGATIVE")
    return p


def breath_keys(loop_frames, total_frames, fps, period_seconds, base_z, amplitude, base_roll, roll_amplitude):
    period = int(round(float(period_seconds) * int(fps)))
    if period < 4 or period % 4 or loop_frames % period:
        raise PlanError("BREATH_PERIOD_NOT_SEAMLESS|loop=%d|period=%d" % (loop_frames, period))
    quarter = period // 4
    wave = (0.0, 1.0, 0.0, -1.0)
    z, roll = [], []
    for frame in range(0, loop_frames + 1, quarter):
        phase = wave[(frame // quarter) % 4]
        z.append([frame, float(base_z) + float(amplitude) * phase])
        roll.append([frame, float(base_roll) + float(roll_amplitude) * phase])
    z.append([total_frames, float(base_z)])
    roll.append([total_frames, float(base_roll)])
    return z, roll


def terminal_spot_failures(rows):
    failures = []
    for row in rows:
        if row["count"] not in (0, 2):
            failures.append("I%d_SPOT_COUNT_%d" % (row["interaction"], row["count"]))
        for spot in row.get("spots", []):
            if abs(float(spot["intensity_at_end"])) > 1.0e-4:
                failures.append("I%d_%s_INTENSITY" % (row["interaction"], spot["name"]))
            if bool(spot["spawned_at_end"]):
                failures.append("I%d_%s_SPAWN" % (row["interaction"], spot["name"]))
    return failures


def build_plan(snapshot, raw_args):
    p = normalise_args(raw_args)
    required = ("cue", "segment", "tick_resolution", "markers", "loop_frames", "total_frames", "fps", "actors", "spots")
    missing = [x for x in required if x not in snapshot]
    if missing:
        raise PlanError("SNAPSHOT_MISSING|%s" % ",".join(missing))
    cue = snapshot["cue"]
    if norm_guid(cue.get("guid")) != p["recorded_nap_guid"] or cue.get("label") != OLD_LABEL:
        raise PlanError("RECORDED_CUE_IDENTITY_DRIFT|%s|%s" % (cue.get("guid"), cue.get("label")))
    segment = snapshot["segment"]
    start_s = float(segment["start"]) / float(snapshot["tick_resolution"])
    end_s = float(segment["end"]) / float(snapshot["tick_resolution"])
    if abs(start_s - p["expected_master_start_seconds"]) > 1.0e-4 or \
            abs(end_s - p["expected_master_end_seconds"]) > 1.0e-4:
        raise PlanError("MASTER_RANGE_DRIFT|got=%.6f-%.6f" % (start_s, end_s))
    old_marker = "GO %s PASS %s" % (p["go_number"], OLD_LABEL)
    new_marker = "GO %s PASS %s" % (p["go_number"], NEW_LABEL)
    marks = snapshot["markers"]
    if sum(1 for f, label in marks if label == old_marker) != 1:
        raise PlanError("OLD_GO_MARKER_COUNT")
    if any(label == new_marker for f, label in marks):
        raise PlanError("NEW_GO_MARKER_ALREADY_EXISTS")
    old_frame = [int(f) for f, label in marks if label == old_marker][0]
    if old_frame != int(snapshot["loop_frames"]):
        raise PlanError("GO_NOT_AT_VAMP_END")
    actors = {x["label"]: x for x in snapshot["actors"]}
    if set(actors) != set((CAT_LABEL, CAMERA_LABEL) + LIGHT_LABELS):
        raise PlanError("NAP_OWNED_ACTOR_SET|%s" % sorted(actors))
    camera = actors[CAMERA_LABEL]
    z, roll = breath_keys(int(snapshot["loop_frames"]), int(snapshot["total_frames"]), int(snapshot["fps"]),
                          p["camera_breath_period_seconds"], p["camera_ground_z_cm"],
                          p["camera_breath_amplitude_cm"], float(camera["rotation"][0]),
                          p["camera_breath_roll_deg"])
    if terminal_spot_failures(snapshot["spots"]):
        # DRY must still be able to plan the repair; cardinality errors remain fatal.
        cardinality = [x for x in terminal_spot_failures(snapshot["spots"]) if "_SPOT_COUNT_" in x]
        if cardinality:
            raise PlanError("SHADOW_SPOT_CARDINALITY|%s" % cardinality)
    named = [p["show_package"], p["master_package"], p["level_package"], p["nap_sequence"]]
    named += [row["sequence"] for row in snapshot["spots"] if row["count"]]
    named = list(dict.fromkeys(named))
    return {
        "schema_version": 1, "tool": TOOL, "version": VERSION, "params": p,
        "cue": {"guid": p["recorded_nap_guid"], "old_label": OLD_LABEL, "new_label": NEW_LABEL},
        "master_segment_before": copy.deepcopy(segment),
        "marker": {"frame": old_frame, "old": old_marker, "new": new_marker},
        "vamp_markers_before": [[int(f), label] for f, label in marks if label.startswith("InfinityStage.Vamp")],
        "cat_visibility": {"label": CAT_LABEL, "visible": False},
        "fps": int(snapshot["fps"]),
        "camera": {"label": CAMERA_LABEL, "ground_z_cm": p["camera_ground_z_cm"],
                   "z_keys": z, "roll_keys": roll},
        "lights": copy.deepcopy(p["nap_light_intensities"]),
        "spots_before": copy.deepcopy(snapshot["spots"]), "spot_audit_order": list(AUDIT_ORDER),
        "named_packages": named, "backup_packages": named,
    }


def verify_after(plan, facts):
    failures = []
    cue = facts.get("cue", {})
    if norm_guid(cue.get("guid")) != plan["cue"]["guid"] or cue.get("label") != NEW_LABEL:
        failures.append("CUE_IDENTITY")
    segment = facts.get("segment", {})
    before_segment = plan["master_segment_before"]
    if norm_guid(segment.get("guid")) != plan["cue"]["guid"] or segment.get("label") != NEW_LABEL or \
            int(segment.get("start", -1)) != int(before_segment["start"]) or \
            int(segment.get("end", -1)) != int(before_segment["end"]):
        failures.append("MASTER_SEGMENT_TIMING")
    markers = facts.get("markers", [])
    if sum(1 for f, label in markers if label == plan["marker"]["new"] and int(f) == plan["marker"]["frame"]) != 1:
        failures.append("NEW_MARKER")
    if any(label == plan["marker"]["old"] for f, label in markers):
        failures.append("OLD_MARKER_SURVIVES")
    vamp = [[int(f), label] for f, label in markers if label.startswith("InfinityStage.Vamp")]
    if vamp != plan["vamp_markers_before"]:
        failures.append("VAMP_MARKERS_CHANGED")
    actors = {x["label"]: x for x in facts.get("actors", [])}
    if bool(actors.get(CAT_LABEL, {}).get("visible", True)) or not bool(
            actors.get(CAT_LABEL, {}).get("actor_hidden_in_game", False)):
        failures.append("CAT_VISIBLE")
    camera = actors.get(CAMERA_LABEL, {})
    for key in ("z_keys", "roll_keys"):
        got, want = camera.get(key, []), plan["camera"][key]
        if len(got) != len(want) or any(int(a[0]) != int(b[0]) or abs(float(a[1])-float(b[1])) > 1.0e-3
                                        for a, b in zip(got, want)):
            failures.append("CAMERA_%s" % key.upper())
    for label, value in plan["lights"].items():
        if abs(float(actors.get(label, {}).get("intensity", -1)) - value) > 1.0e-3:
            failures.append("LIGHT_%s" % label)
    failures += terminal_spot_failures(facts.get("spots", []))
    return failures


def _png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_preview(plan, path):
    """Analytical preview: camera height/roll and the retained vamp/GO seam."""
    width, height = 960, 320
    pixels = [bytearray([12, 16, 24] * width) for _ in range(height)]

    def line(x0, y0, x1, y1, color):
        steps = max(abs(x1-x0), abs(y1-y0), 1)
        for i in range(steps + 1):
            x = int(round(x0 + (x1-x0) * i / float(steps)))
            y = int(round(y0 + (y1-y0) * i / float(steps)))
            if 0 <= x < width and 0 <= y < height:
                pixels[y][3*x:3*x+3] = bytes(color)

    total = int(plan["camera"]["z_keys"][-1][0])
    loop = int(plan["marker"]["frame"])
    xof = lambda frame: 45 + int(860 * int(frame) / float(total))
    for y in range(38, 78):
        for x in range(xof(0), xof(loop)):
            pixels[y][3*x:3*x+3] = bytes((28, 46, 70))
    for y in range(38, 78):
        for x in range(xof(loop), xof(total)):
            pixels[y][3*x:3*x+3] = bytes((72, 44, 31))
    for rows, baseline, scale, color in ((plan["camera"]["z_keys"], 170, 25, (90, 190, 220)),
                                         (plan["camera"]["roll_keys"], 260, 90, (220, 160, 90))):
        base = float(rows[0][1])
        points = [(xof(frame), int(round(baseline - (float(value)-base) * scale))) for frame, value in rows]
        for a, b in zip(points, points[1:]):
            line(a[0], a[1], b[0], b[1], color)
    line(xof(loop), 25, xof(loop), 290, (220, 70, 65))
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    data = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


class UnrealBackend(object):
    """Live UE 5.8 adapter.  No instance is created by the offline harness."""
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
        clean = lambda x: str(x.get_path_name()).split(".", 1)[0]
        return {"content": sorted(clean(x) for x in lib.get_dirty_content_packages()),
                "maps": sorted(clean(x) for x in lib.get_dirty_map_packages())}

    def preflight(self, args):
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

    def _cue(self, show, wanted_guid):
        rows = [c for c in show.get_editor_property("cues")
                if self._guid(c.get_editor_property("cue_guid")) == wanted_guid]
        if len(rows) != 1:
            raise PlanError("NAP_GUID_COUNT|%d" % len(rows))
        return rows[0]

    def _segment(self, show, wanted_guid):
        tr = self.ue.InfinityStageTransportController()
        if not tr.build_segments(show):
            raise PlanError("BUILD_SEGMENTS_FAILED")
        rows = []
        for row in tr.get_editor_property("segments"):
            if self._guid(row.get_editor_property("segment_guid")) == wanted_guid:
                rows.append({"guid": wanted_guid, "label": str(row.get_editor_property("label")),
                             "type": enum_tail(row.get_editor_property("type")),
                             "start": int(row.get_editor_property("start_frame").value),
                             "end": int(row.get_editor_property("end_frame").value)})
        if len(rows) != 1:
            raise PlanError("NAP_SEGMENT_COUNT|%d" % len(rows))
        return rows[0]

    def _binding(self, seq, name):
        rows = [b for b in seq.get_bindings() if str(b.get_display_name()) == name]
        if len(rows) != 1:
            raise PlanError("BINDING_COUNT|%s|%d" % (name, len(rows)))
        return rows[0]

    def _track(self, binding, class_name, prop=None):
        rows = [t for t in binding.get_tracks() if t.get_class().get_name() == class_name]
        if prop is not None:
            rows = [t for t in rows if str(t.get_property_name()) == prop]
        if len(rows) != 1:
            raise PlanError("TRACK_COUNT|%s|%s|%d" % (binding.get_display_name(), class_name, len(rows)))
        return rows[0]

    def _channel(self, section, wanted):
        rows = [c for c in section.get_all_channels()
                if wanted in channel_semantic(c.get_editor_property("channel_name"))]
        if len(rows) != 1:
            raise PlanError("CHANNEL_COUNT|%s|%d" % (wanted, len(rows)))
        return rows[0]

    def _keys(self, channel):
        ue = self.ue
        return [[int(k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value),
                 k.get_value()] for k in channel.get_keys()]

    def _eval(self, channel, frame, seq):
        ue = self.ue
        rate = seq.get_display_rate()
        values = list(channel.evaluate_keys(seq.make_range(int(frame), 1), rate))
        if len(values) != 1:
            raise PlanError("EVALUATE_COUNT|frame=%d|got=%d" % (frame, len(values)))
        return values[0]

    def _nap_actors(self, seq):
        ue = self.ue
        actors = ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
        owned = [a for a in actors if OWNER_TAG in [str(t) for t in a.get_editor_property("tags")]]
        out = []
        for actor in owned:
            label = actor.get_actor_label()
            row = {"label": label, "location": [actor.get_actor_location().x, actor.get_actor_location().y,
                                                   actor.get_actor_location().z],
                   "rotation": [actor.get_actor_rotation().roll, actor.get_actor_rotation().pitch,
                                actor.get_actor_rotation().yaw],
                   "actor_hidden_in_game": bool(actor.get_editor_property("hidden"))}
            binding = self._binding(seq, label)
            if label == CAT_LABEL:
                track = self._track(binding, "MovieSceneVisibilityTrack")
                if str(track.get_property_name()) != "bHidden" or str(track.get_property_path()) != "bHidden":
                    raise PlanError("CAT_VISIBILITY_NOT_BHIDDEN|%s|%s" %
                                    (track.get_property_name(), track.get_property_path()))
                chan = track.get_sections()[0].get_all_channels()[0]
                row["visible"] = bool(self._eval(chan, 0, seq))
                row["visibility_keys"] = self._keys(chan)
            elif label == CAMERA_LABEL:
                track = self._track(binding, "MovieScene3DTransformTrack")
                sec = track.get_sections()[0]
                row["z_keys"] = self._keys(self._channel(sec, "locationz"))
                row["roll_keys"] = self._keys(self._channel(sec, "rotationx"))
            elif label in LIGHT_LABELS:
                row["intensity"] = float(actor.get_editor_property("rect_light_component").get_editor_property("intensity"))
            out.append(row)
        return sorted(out, key=lambda row: row["label"])

    def _spot_rows(self):
        output = []
        for n in AUDIT_ORDER:
            path = INTERACTION_PATHS[n]
            seq = self.ue.load_asset(path)
            if seq is None:
                raise PlanError("INTERACTION_SEQUENCE_MISSING|I%d" % n)
            bindings = [b for b in seq.get_bindings() if str(b.get_display_name()) in SPOT_NAMES]
            spots = []
            for binding in bindings:
                name = str(binding.get_display_name())
                ft = self._track(binding, "MovieSceneFloatTrack", "Intensity")
                st = self._track(binding, "MovieSceneSpawnTrack")
                end = int(seq.get_playback_end())
                fchan, schan = ft.get_sections()[0].get_all_channels()[0], st.get_sections()[0].get_all_channels()[0]
                spots.append({"name": name, "binding_guid": self._guid(binding.get_id()),
                              "end": end, "intensity_at_end": float(self._eval(ft.get_sections()[0].get_all_channels()[0], end, seq)),
                              "spawned_at_end": bool(self._eval(st.get_sections()[0].get_all_channels()[0], end, seq)),
                              "intensity_keys": self._keys(fchan), "spawn_keys": self._keys(schan)})
            output.append({"interaction": n, "sequence": path, "count": len(bindings), "spots": spots})
        return output

    def inspect(self, args):
        ue = self.ue
        show, seq = ue.load_asset(args["show_package"]), ue.load_asset(args["nap_sequence"])
        cue = self._cue(show, args["recorded_nap_guid"])
        markers = sorted([[int(m.frame_number.value), str(m.label)] for m in
                          seq.get_marked_frames_from_sequence(ue.MovieSceneTimeUnit.DISPLAY_RATE)])
        fps = int(round(float(seq.get_display_rate().numerator) / seq.get_display_rate().denominator))
        vamp_end = [f for f, label in markers if label == "InfinityStage.VampEnd"]
        if len(vamp_end) != 1:
            raise PlanError("VAMP_END_COUNT")
        tick = float(show.get_editor_property("tick_resolution").numerator) / show.get_editor_property("tick_resolution").denominator
        return {"cue": {"guid": self._guid(cue.get_editor_property("cue_guid")),
                        "label": str(cue.get_editor_property("label")), "type": enum_tail(cue.get_editor_property("type"))},
                "segment": self._segment(show, args["recorded_nap_guid"]), "tick_resolution": tick,
                "markers": markers, "loop_frames": int(vamp_end[0]), "total_frames": int(seq.get_playback_end()),
                "fps": fps, "actors": self._nap_actors(seq), "spots": self._spot_rows()}

    def backup(self, run, packages, prefix):
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
            target = os.path.join(root, "%02d_%s" % (len(files), os.path.basename(source)))
            shutil.copy2(source, target)
            if os.path.getsize(source) != os.path.getsize(target):
                raise PlanError("BACKUP_SIZE|%s" % package)
            files.append({"package": package, "source": source, "backup": target,
                          "bytes": os.path.getsize(target)})
        write_json(os.path.join(root, "manifest.json"), {"run": run, "files": files}, exclusive=True)
        return {"root": root, "files": files}

    def _replace_keys(self, channel, rows, interpolation=None):
        ue = self.ue
        for key in list(channel.get_keys()):
            channel.remove_key(key)
        for frame, value in rows:
            kwargs = {"time_unit": ue.MovieSceneTimeUnit.DISPLAY_RATE}
            if interpolation is not None:
                kwargs["interpolation"] = interpolation
            channel.add_key(ue.FrameNumber(int(frame)), value, **kwargs)

    def apply(self, plan):
        ue, p = self.ue, plan["params"]
        show, master, seq = ue.load_asset(p["show_package"]), ue.load_asset(p["master_package"]), ue.load_asset(p["nap_sequence"])
        cues = list(show.get_editor_property("cues"))
        hits = [i for i, cue in enumerate(cues) if self._guid(cue.get_editor_property("cue_guid")) == plan["cue"]["guid"]]
        if len(hits) != 1:
            raise PlanError("NAP_GUID_COUNT_DURING_APPLY|%d" % len(hits))
        cues[hits[0]].set_editor_property("label", NEW_LABEL)
        show.set_editor_property("cues", cues)
        # cue_guid is intentionally never assigned: it is read-only/minted.
        if not ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master):
            raise PlanError("MASTER_REBUILD_FAILED")
        old = plan["marker"]["old"]
        found = seq.find_marked_frame_by_label(old)
        if int(found) < 0:
            raise PlanError("OLD_MARKER_NOT_FOUND")
        seq.delete_marked_frame(int(found))
        marked = ue.MovieSceneMarkedFrame(); marked.frame_number = ue.FrameNumber(plan["marker"]["frame"]); marked.label = plan["marker"]["new"]
        ue.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(seq, marked, ue.MovieSceneTimeUnit.DISPLAY_RATE)
        cat = self._binding(seq, CAT_LABEL)
        vis = self._track(cat, "MovieSceneVisibilityTrack")
        vchan = vis.get_sections()[0].get_all_channels()[0]
        self._replace_keys(vchan, [[0, False], [plan["camera"]["z_keys"][-1][0], False]])
        camera = self._binding(seq, CAMERA_LABEL)
        tsec = self._track(camera, "MovieScene3DTransformTrack").get_sections()[0]
        self._replace_keys(self._channel(tsec, "locationz"), plan["camera"]["z_keys"],
                           ue.MovieSceneKeyInterpolation.AUTO)
        self._replace_keys(self._channel(tsec, "rotationx"), plan["camera"]["roll_keys"],
                           ue.MovieSceneKeyInterpolation.AUTO)
        actors = ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
        by_label = {a.get_actor_label(): a for a in actors}
        by_label[CAT_LABEL].set_actor_hidden_in_game(True)
        for label, intensity in plan["lights"].items():
            by_label[label].get_editor_property("rect_light_component").set_editor_property("intensity", float(intensity))
        for row in plan["spots_before"]:  # I4 first by plan construction.
            if not row["count"]:
                continue
            iseq = ue.load_asset(row["sequence"])
            for name in SPOT_NAMES:
                binding = self._binding(iseq, name)
                end = int(iseq.get_playback_end())
                ft = self._track(binding, "MovieSceneFloatTrack", "Intensity")
                st = self._track(binding, "MovieSceneSpawnTrack")
                ft.get_sections()[0].get_all_channels()[0].add_key(ue.FrameNumber(end), 0.0, time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
                st.get_sections()[0].get_all_channels()[0].add_key(ue.FrameNumber(end), False, time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)

    def save(self, packages):
        dirty = sorted(set(self.census()["content"] + self.census()["maps"]))
        if dirty != sorted(packages):
            raise PlanError("EXACT_DIRTY_CENSUS|got=%s|want=%s" % (dirty, sorted(packages)))
        saved = []
        for package in packages:
            ok = (self.ue.get_editor_subsystem(self.ue.LevelEditorSubsystem).save_current_level()
                  if package == self.args["level_package"] else
                  self.ue.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True))
            if not ok:
                raise PlanError("SAVE_FAILED|%s" % package)
            saved.append(package)
        if self.census() != {"content": [], "maps": []}:
            raise PlanError("DIRTY_AFTER_SAVE|%s" % canonical(self.census()))
        return saved

    def revert(self, record):
        """Semantically restore the recorded pre-APPLY state, then let the caller save/read back."""
        ue, plan, before = self.ue, record["plan"], record["snapshot_before"]
        p = plan["params"]
        show, master, seq = ue.load_asset(p["show_package"]), ue.load_asset(p["master_package"]), ue.load_asset(p["nap_sequence"])
        cues = list(show.get_editor_property("cues"))
        hits = [i for i, cue in enumerate(cues) if self._guid(cue.get_editor_property("cue_guid")) == plan["cue"]["guid"]]
        if len(hits) != 1:
            raise PlanError("REVERT_NAP_GUID_COUNT|%d" % len(hits))
        cues[hits[0]].set_editor_property("label", OLD_LABEL)
        show.set_editor_property("cues", cues)
        if not ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master):
            raise PlanError("REVERT_MASTER_REBUILD_FAILED")
        index = seq.find_marked_frame_by_label(plan["marker"]["new"])
        if int(index) < 0:
            raise PlanError("REVERT_NEW_MARKER_NOT_FOUND")
        seq.delete_marked_frame(int(index))
        marked = ue.MovieSceneMarkedFrame(); marked.frame_number = ue.FrameNumber(plan["marker"]["frame"]); marked.label = plan["marker"]["old"]
        ue.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(seq, marked, ue.MovieSceneTimeUnit.DISPLAY_RATE)
        actors_before = {row["label"]: row for row in before["actors"]}
        actors = ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
        by_label = {a.get_actor_label(): a for a in actors}
        cat = self._binding(seq, CAT_LABEL)
        vchan = self._track(cat, "MovieSceneVisibilityTrack").get_sections()[0].get_all_channels()[0]
        self._replace_keys(vchan, actors_before[CAT_LABEL]["visibility_keys"])
        by_label[CAT_LABEL].set_actor_hidden_in_game(actors_before[CAT_LABEL]["actor_hidden_in_game"])
        camera = self._binding(seq, CAMERA_LABEL)
        tsec = self._track(camera, "MovieScene3DTransformTrack").get_sections()[0]
        self._replace_keys(self._channel(tsec, "locationz"), actors_before[CAMERA_LABEL]["z_keys"],
                           ue.MovieSceneKeyInterpolation.LINEAR)
        self._replace_keys(self._channel(tsec, "rotationx"), actors_before[CAMERA_LABEL]["roll_keys"],
                           ue.MovieSceneKeyInterpolation.LINEAR)
        for label in LIGHT_LABELS:
            by_label[label].get_editor_property("rect_light_component").set_editor_property(
                "intensity", float(actors_before[label]["intensity"]))
        for row in before["spots"]:
            if not row["count"]:
                continue
            iseq = ue.load_asset(row["sequence"])
            old_spots = {x["name"]: x for x in row["spots"]}
            for name in SPOT_NAMES:
                binding = self._binding(iseq, name)
                ft = self._track(binding, "MovieSceneFloatTrack", "Intensity")
                st = self._track(binding, "MovieSceneSpawnTrack")
                self._replace_keys(ft.get_sections()[0].get_all_channels()[0], old_spots[name]["intensity_keys"],
                                   ue.MovieSceneKeyInterpolation.LINEAR)
                self._replace_keys(st.get_sections()[0].get_all_channels()[0], old_spots[name]["spawn_keys"])
        return {"restored_packages": list(plan["named_packages"])}


def _confirm(mode, run, source):
    return "REVERT E18 %s" % source if mode == "REVERT" else "%s E18 %s" % (mode, run)


def _stop(backend, run, reason):
    msg = "%s_STOPPED|run=%s|reason=%s" % (TOOL, run, reason)
    backend.stop(msg)
    raise Stop(msg)


def run_dry(run, args, backend, root):
    backend.preflight(args)
    snapshot = backend.inspect(args)
    plan = build_plan(snapshot, args)
    report = os.path.join(root, "e18_nap_revision_dry_%s.json" % run)
    preview = write_preview(plan, os.path.join(root, "e18_nap_revision_preview_%s.png" % run))
    write_json(report, {"mode": "DRY", "run": run, "writes": 0, "snapshot": snapshot, "plan": plan,
                        "dirty_package_census": backend.census(), "stills_plan": stills_plan(plan),
                        "preview": preview})
    write_json(os.path.join(root, PLAN_FILE), {"run": run, "snapshot_digest": digest(snapshot),
                                               "plan_digest": digest(plan), "plan": plan})
    backend.log("E18_NAP_REVISION_DRY_OK|run=%s|guid=%s|packages=%d|spots=%s|writes=0|report=%s" %
                (run, plan["cue"]["guid"], len(plan["named_packages"]),
                 ",".join("I%d:%d" % (x["interaction"], x["count"]) for x in plan["spots_before"]), report))
    return plan


def run_apply(run, args, backend, root):
    backend.preflight(args)
    snapshot = backend.inspect(args)
    plan = build_plan(snapshot, args)
    dry = read_json(os.path.join(root, PLAN_FILE))
    if dry.get("snapshot_digest") != digest(snapshot) or dry.get("plan_digest") != digest(plan):
        _stop(backend, run, "CHANGED_SINCE_DRY")
    backup = backend.backup(run, plan["backup_packages"], "PreE18NapRevision")
    path = os.path.join(root, "e18_nap_revision_record_%s.json" % run)
    record = {"schema_version": 1, "tool": TOOL, "run": run, "status": "prepared", "args": args,
              "plan": plan, "snapshot_before": snapshot, "backup": backup}
    write_json(path, record, exclusive=True)
    backend.apply(plan)
    facts = backend.inspect(args)
    failures = verify_after(plan, facts)
    dirty = sorted(set(backend.census()["content"] + backend.census()["maps"]))
    if failures or dirty != sorted(plan["named_packages"]):
        _stop(backend, run, "PRESAVE_READBACK|failures=%s|dirty=%s|NOTHING_SAVED" % (failures, dirty))
    saved = backend.save(plan["named_packages"])
    facts = backend.inspect(args)
    failures = verify_after(plan, facts)
    if failures or backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "POSTSAVE_READBACK|%s|restore=%s" % (failures, backup["root"]))
    record.update({"status": "saved_readback_verified", "snapshot_after": facts, "saved": saved,
                   "stills_plan": stills_plan(plan)})
    write_json(path, record)
    backend.log("E18_NAP_REVISION_APPLY_OK|run=%s|guid=%s|saved=%s|backup=%s|record=%s" %
                (run, plan["cue"]["guid"], ",".join(saved), backup["root"], path))
    return record


def run_revert(run, source, args, backend, root):
    backend.preflight(args)
    path = os.path.join(root, "e18_nap_revision_record_%s.json" % source)
    record = read_json(path)
    if record.get("status") != "saved_readback_verified":
        _stop(backend, run, "SOURCE_RECORD_NOT_APPLIED")
    current = backend.inspect(args)
    failures = verify_after(record["plan"], current)
    if failures:
        _stop(backend, run, "APPLIED_STATE_DRIFT|%s" % failures)
    backup = backend.backup(run, record["plan"]["named_packages"], "PreE18NapRevisionRevert")
    txn = os.path.join(root, "e18_nap_revision_revert_%s.json" % run)
    write_json(txn, {"status": "prepared", "run": run, "source": source, "backup": backup}, exclusive=True)
    result = backend.revert(record)
    dirty = sorted(set(backend.census()["content"] + backend.census()["maps"]))
    if dirty != sorted(record["plan"]["named_packages"]):
        _stop(backend, run, "REVERT_DIRTY_CENSUS|got=%s|want=%s|NOTHING_SAVED" %
              (dirty, sorted(record["plan"]["named_packages"])))
    saved = backend.save(record["plan"]["named_packages"])
    final = backend.inspect(args)
    if digest(final) != digest(record["snapshot_before"]) or backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "REVERT_READBACK_MISMATCH|restore=%s" % backup["root"])
    write_json(txn, {"status": "saved_readback_verified", "run": run, "source": source,
                     "backup": backup, "result": result, "saved": saved})
    backend.log("E18_NAP_REVISION_REVERT_OK|run=%s|source=%s|saved=%s|backup=%s|record=%s" %
                (run, source, ",".join(saved), backup["root"], txn))
    return result


def stills_plan(plan):
    loop = int(plan["marker"]["frame"])
    quarter = int(round(plan["params"]["camera_breath_period_seconds"] * plan["fps"] / 4.0))
    return [
        {"name": "nap_entry_ground_pov", "frame": 0, "prove": "ground-level CAT'S VIEW; cat absent; near-dark"},
        {"name": "nap_breath_peak", "frame": quarter, "prove": "camera rise plus tiny roll; no cat"},
        {"name": "nap_seam_before", "frame": loop - 1, "prove": "pre-vamp seam state"},
        {"name": "nap_seam_after", "frame": 0, "after_one_loop": True, "prove": "seam continuity"},
        {"name": "i4_terminal_dark", "interaction": 4, "frame": "last", "prove": "both shadow spots 0 and unspawned"},
    ]


def main(raw, backend=None, root=None):
    raw = copy.deepcopy(raw or {})
    mode = str(raw.get("mode", "DRY")).upper()
    run = str(raw.get("run_id") or datetime.datetime.now().strftime("E18-%Y%m%d-%H%M%S"))
    source = str(raw.get("source_run_id") or "")
    backend = backend or UnrealBackend()
    root = os.path.abspath(root or os.path.dirname(__file__))
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
        _stop(backend, run, "MODE_OR_SOURCE")
    except PlanError as error:
        _stop(backend, run, "PLAN_REFUSED|%s" % error)
