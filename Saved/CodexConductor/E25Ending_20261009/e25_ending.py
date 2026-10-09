"""E25 guarded authoring tool: S6 black -> Opening-stage return.

Authored and tested offline.  The pure planner has no Unreal dependency; the
live adapter is instantiated only by the conductor inside the guarded project
Python route.
"""

from __future__ import division

import copy
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import zlib


TOOL = "E25_ENDING"
VERSION = "2026-10-09a"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
LEVEL = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_Ending_OpeningStage"
CUE_LABEL = "Ending — Opening Stage"
OWNER_TAG = "E25_ENDING_OWNED"
REQUIRED_TESTS = (
    "InfinityStage.Editor.SavedMasterMatchesShow",
    "InfinityStage.Editor.SceneCutBindingsResolve",
)


class PlanError(ValueError):
    pass


class Stop(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def norm_guid(value):
    return re.sub(r"[^0-9A-F]", "", str(value).upper())


def identity_label(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def enum_name(value):
    """Normalise UE 5.8 strings such as '<InfinityCueType.SCENE: 1>'."""
    text = str(value).split(".")[-1]
    return text.split(":", 1)[0].strip("<> ")


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_json(path):
    if not os.path.isfile(path):
        raise PlanError("JSON_MISSING|%s" % path)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _number(value, name, low, high):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise PlanError("%s_NOT_NUMBER" % name)
    if result < low or result > high:
        raise PlanError("%s_RANGE|%s" % (name, result))
    return result


def normalise_args(raw):
    p = copy.deepcopy(raw or {})
    p.setdefault("show_package", SHOW)
    p.setdefault("master_package", MASTER)
    p.setdefault("level_package", LEVEL)
    p.setdefault("sequence_package", SEQUENCE)
    p.setdefault("cue_label", CUE_LABEL)
    p.setdefault("scene6_label", "Scene 6 — External Sound")
    p.setdefault("closing_label", "Closing — Sweeping Up")
    p.setdefault("opening_label", "Opening — Curtain")
    p.setdefault("opening_camera_label", "Opening — Stalls Camera")
    p.setdefault("expected_scene6_guid", "")
    p.setdefault("expected_closing_guid", "")
    p.setdefault("expected_camera_path", "")
    p.setdefault("expected_stage_actor_paths", [])
    p.setdefault("expected_hidden_actor_paths", [])
    p.setdefault("display_rate", 25)
    p.setdefault("black_seconds", 2.0)
    p.setdefault("arrival_seconds", 10.0)
    p.setdefault("camera_start_pose", {
        "location": [-2400.0, 0.0, 150.0],
        "rotation": [9.0, 0.0, 0.0],
        "focal_mm": 15.0,
    })
    p.setdefault("mask_label", "E25_Ending_InfinityMask")
    p.setdefault("mask_mesh", "/Engine/BasicShapes/Cube.Cube")
    p.setdefault("mask_material", "/Engine/EngineMaterials/BlackUnlitMaterial.BlackUnlitMaterial")
    p.setdefault("mask_transform", {
        "location": [250.0, 0.0, 525.0],
        "rotation": [0.0, 0.0, 0.0],
        "scale": [0.25, 22.0, 12.0],
    })
    p.setdefault("stage_label_patterns", ["Opening", "Passage 01", "P01", "Stage Front", "Proscenium"])
    p.setdefault("hidden_label_patterns", ["Passage 02", "Passage 03", "Passage 04", "Passage 05", "Passage 06", "Hangar", "Sky", "Backdrop"])
    p.setdefault("optional_later_beats", [
        "stage being closed up",
        "lights going off",
        "happy animals settled onstage",
        "recurring animals from earlier scenes",
    ])
    if p["cue_label"] != CUE_LABEL:
        raise PlanError("CUE_LABEL_MISMATCH")
    try:
        p["display_rate"] = int(p["display_rate"])
    except (TypeError, ValueError):
        raise PlanError("DISPLAY_RATE")
    if p["display_rate"] <= 0:
        raise PlanError("DISPLAY_RATE")
    p["black_seconds"] = _number(p["black_seconds"], "BLACK_SECONDS", 0.25, 20.0)
    p["arrival_seconds"] = _number(p["arrival_seconds"], "ARRIVAL_SECONDS", 1.0, 120.0)
    p["expected_scene6_guid"] = norm_guid(p["expected_scene6_guid"])
    p["expected_closing_guid"] = norm_guid(p["expected_closing_guid"])
    p["expected_camera_path"] = str(p["expected_camera_path"])
    p["expected_stage_actor_paths"] = sorted(set(map(str, p["expected_stage_actor_paths"])))
    p["expected_hidden_actor_paths"] = sorted(set(map(str, p["expected_hidden_actor_paths"])))
    if set(p["expected_stage_actor_paths"]) & set(p["expected_hidden_actor_paths"]):
        raise PlanError("ACTOR_ROLE_OVERLAP")
    p.pop("ending_cue_guid", None)  # engine-minted, read only after rebuild
    p["named_packages"] = [p["show_package"], p["master_package"], p["level_package"], p["sequence_package"]]
    return p


def _unique(rows, label):
    wanted = identity_label(label)
    hits = [row for row in rows if identity_label(row.get("label", "")) == wanted]
    if len(hits) != 1:
        raise PlanError("CUE_COUNT|label=%s|count=%d" % (label, len(hits)))
    return hits[0]


def _matches(label, patterns):
    low = str(label).lower()
    return any(str(pattern).lower() in low for pattern in patterns)


def _discover_actors(snapshot, p):
    actors = snapshot["actors"]
    cameras = [a for a in actors if a["label"] == p["opening_camera_label"]]
    if len(cameras) != 1:
        raise PlanError("OPENING_CAMERA_COUNT|%d" % len(cameras))
    camera = cameras[0]
    stage_rows = [a for a in actors
                  if a["path"] != camera["path"] and _matches(a["label"], p["stage_label_patterns"])]
    stage = sorted(a["path"] for a in stage_rows)
    hidden = sorted(a["path"] for a in actors
                    if a["path"] != camera["path"] and _matches(a["label"], p["hidden_label_patterns"])
                    and a["path"] not in stage)
    if not stage:
        raise PlanError("NO_STAGE_ACTORS_DISCOVERED")
    if not any("curtain" in a["label"].lower() for a in stage_rows):
        raise PlanError("NO_OPENING_CURTAIN_IN_STAGE_CENSUS")
    if not any("passage 01" in a["label"].lower() or "p01" in a["label"].lower() for a in stage_rows):
        raise PlanError("NO_P01_STAGE_LIGHTING_IN_STAGE_CENSUS")
    if not any("sky" in a["label"].lower() for a in actors if a["path"] in hidden):
        raise PlanError("NO_SKY_ACTOR_IN_HIDDEN_CENSUS")
    return camera["path"], stage, hidden


def expected_segments(before, after_index, ending, delta):
    out = []
    for index, row in enumerate(before):
        item = copy.deepcopy(row)
        if index > after_index:
            item["start"] += delta
            item["end"] += delta
            item["first_show_index"] += 1
        out.append(item)
        if index == after_index:
            out.append({"guid": ending.get("guid"), "label": ending["label"], "type": "SEQUENCE",
                        "start": row["end"], "end": row["end"] + delta,
                        "first_show_index": ending["show_index"]})
    return out


def build_plan(snapshot, raw_args):
    p = normalise_args(raw_args)
    for key in ("segments", "actors", "asset_exists", "owned_mask_exists", "tick_resolution", "opening_end_pose"):
        if key not in snapshot:
            raise PlanError("SNAPSHOT_MISSING|%s" % key)
    segments = copy.deepcopy(snapshot["segments"])
    # Dedupe before interpreting placement.  A prior partial/live run should be
    # reported as such, not disguised as a boundary-order failure.
    if any(row["label"] == CUE_LABEL for row in segments):
        raise PlanError("ENDING_ALREADY_COMPILED")
    s6, closing = _unique(segments, p["scene6_label"]), _unique(segments, p["closing_label"])
    si, ci = segments.index(s6), segments.index(closing)
    if ci != si + 1 or int(s6["end"]) != int(closing["start"]):
        raise PlanError("S6_CLOSING_BOUNDARY_DRIFT|indices=%d,%d|ticks=%s,%s" %
                        (si, ci, s6["end"], closing["start"]))
    s6g, cg = norm_guid(s6["guid"]), norm_guid(closing["guid"])
    if p["expected_scene6_guid"] and p["expected_scene6_guid"] != s6g:
        raise PlanError("S6_GUID_DRIFT")
    if p["expected_closing_guid"] and p["expected_closing_guid"] != cg:
        raise PlanError("CLOSING_GUID_DRIFT")
    if snapshot["asset_exists"] or snapshot["owned_mask_exists"]:
        raise PlanError("ENDING_ARTIFACT_EXISTS")
    camera, stage, hidden = _discover_actors(snapshot, p)
    for name, supplied, found in (
            ("CAMERA", p["expected_camera_path"], camera),
            ("STAGE", p["expected_stage_actor_paths"], stage),
            ("HIDDEN", p["expected_hidden_actor_paths"], hidden)):
        if supplied and supplied != found:
            raise PlanError("%s_CENSUS_DRIFT|expected=%s|got=%s" % (name, supplied, found))
    # Canonicalise discovery so an APPLY with pinned DRY identities hashes identically.
    p["expected_scene6_guid"], p["expected_closing_guid"] = s6g, cg
    p["expected_camera_path"], p["expected_stage_actor_paths"], p["expected_hidden_actor_paths"] = camera, stage, hidden
    fps = p["display_rate"]
    black_frames = int(round(p["black_seconds"] * fps))
    arrival_frames = int(round(p["arrival_seconds"] * fps))
    total_frames = black_frames + arrival_frames
    if abs(black_frames / float(fps) - p["black_seconds"]) > 1e-9 or abs(arrival_frames / float(fps) - p["arrival_seconds"]) > 1e-9:
        raise PlanError("TIME_NOT_FRAME_REPRESENTABLE")
    tick = float(snapshot["tick_resolution"])
    delta_f = total_frames * tick / fps
    delta = int(round(delta_f))
    if abs(delta_f - delta) > 1e-6:
        raise PlanError("TIME_NOT_TICK_REPRESENTABLE")
    ending = {"guid": None, "label": CUE_LABEL, "show_index": int(s6["first_show_index"]) + 1}
    camera_keys = [
        {"frame": 0, **copy.deepcopy(p["camera_start_pose"])},
        {"frame": black_frames, **copy.deepcopy(p["camera_start_pose"])},
        {"frame": total_frames, **copy.deepcopy(snapshot["opening_end_pose"])},
    ]
    return {
        "schema_version": 1, "tool": TOOL, "tool_version": VERSION,
        "decision": "new Sequence cue after S6 and before Closing",
        "anchors": {"scene6_guid": s6g, "closing_guid": cg, "scene6_index": si,
                    "closing_index": ci, "boundary_tick": int(s6["end"]),
                    "insert_show_index": ending["show_index"]},
        "ending": ending, "fps": fps, "black_frames": black_frames,
        "arrival_frames": arrival_frames, "total_frames": total_frames, "delta_ticks": delta,
        "camera_actor_path": camera, "camera_keys": camera_keys,
        "stage_actor_paths": stage, "hidden_actor_paths": hidden,
        "visibility": {"stage": [[0, False], [black_frames, True], [total_frames, True]],
                       "hidden": [[0, False], [total_frames, False]],
                       "mask": [[0, True], [total_frames, True]]},
        "mask": {"label": p["mask_label"], "mesh": p["mask_mesh"],
                 "material": p["mask_material"], "transform": p["mask_transform"]},
        "segments_before": segments,
        "segments_expected_after": expected_segments(segments, si, ending, delta),
        "named_packages": p["named_packages"],
        "backup_packages": [p["show_package"], p["master_package"], p["level_package"]],
        "stills_plan": [
            {"frame": 0, "name": "01_total_black", "prove": "no stage, infinity, hangar or sky is visible"},
            {"frame": black_frames, "name": "02_stage_arrival_wide", "prove": "opening-stage-only reveal and mask coverage"},
            {"frame": black_frames + arrival_frames // 2, "name": "03_arrival_mid", "prove": "camera language and no scene-cut leak"},
            {"frame": total_frames - 1, "name": "04_opening_stage_home", "prove": "opening end pose, curtain, bulbs and uplights"},
        ],
        "optional_later_beats_not_built": p["optional_later_beats"],
        "params": p,
    }


def record_minted_guid(plan, value):
    minted = norm_guid(value)
    if len(minted) != 32 or minted == "0" * 32:
        raise PlanError("MINTED_GUID_INVALID|%s" % value)
    plan["ending"]["guid"] = minted
    plan["segments_expected_after"] = expected_segments(
        plan["segments_before"], plan["anchors"]["scene6_index"], plan["ending"], plan["delta_ticks"])
    return minted


def segment_failures(want, got):
    failures = []
    if len(want) != len(got):
        return ["SEGMENT_COUNT|%d|%d" % (len(want), len(got))]
    for i, (a, b) in enumerate(zip(want, got)):
        for key in ("guid", "label", "start", "end", "first_show_index"):
            av, bv = a.get(key), b.get(key)
            if key == "guid":
                av, bv = norm_guid(av), norm_guid(bv)
            if av != bv:
                failures.append("SEGMENT|%d|%s|%s|%s" % (i, key, av, bv))
    return failures


def verify_after(plan, facts):
    failures = segment_failures(plan["segments_expected_after"], facts.get("segments", []))
    if facts.get("sequence_package") != plan["params"]["sequence_package"]:
        failures.append("SEQUENCE_PACKAGE")
    if facts.get("camera_cut_range") != [0, plan["total_frames"]]:
        failures.append("CAMERA_CUT_RANGE")
    if facts.get("camera_cut_actor_path") != plan["camera_actor_path"]:
        failures.append("CAMERA_CUT_BINDING")
    if sorted(facts.get("stage_actor_paths", [])) != sorted(plan["stage_actor_paths"]):
        failures.append("STAGE_CENSUS")
    if sorted(facts.get("hidden_actor_paths", [])) != sorted(plan["hidden_actor_paths"]):
        failures.append("HIDDEN_CENSUS")
    if facts.get("visibility") != plan["visibility"]:
        failures.append("VISIBILITY_KEYS")
    if facts.get("mask_label") != plan["mask"]["label"]:
        failures.append("MASK")
    got_camera = facts.get("camera_keys", [])
    if len(got_camera) != len(plan["camera_keys"]):
        failures.append("CAMERA_KEY_COUNT")
    else:
        for index, (want, got) in enumerate(zip(plan["camera_keys"], got_camera)):
            if int(want["frame"]) != int(got.get("frame", -1)):
                failures.append("CAMERA_FRAME|%d" % index)
                continue
            for axis, (a, b) in enumerate(zip(want["location"], got.get("location", []))):
                if abs(float(a) - float(b)) > 0.01: failures.append("CAMERA_LOCATION|%d|%d" % (index, axis))
            for axis, (a, b) in enumerate(zip(want["rotation"], got.get("rotation", []))):
                if abs(float(a) - float(b)) > 0.001: failures.append("CAMERA_ROTATION|%d|%d" % (index, axis))
            if abs(float(want["focal_mm"]) - float(got.get("focal_mm", -1e9))) > 0.001:
                failures.append("CAMERA_FOCAL|%d" % index)
    return failures


def _png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)


def write_preview(plan, path):
    width, height = 960, 260
    pixels = [bytearray([238, 234, 224] * width) for _ in range(height)]
    split = 50 + int(850 * plan["black_frames"] / float(plan["total_frames"]))
    for y in range(55, 190):
        for x in range(50, split):
            pixels[y][3*x:3*x+3] = bytes((0, 0, 0))
        for x in range(split, 900):
            t = (x - split) / float(max(1, 900 - split))
            pixels[y][3*x:3*x+3] = bytes((int(25 + 110*t), int(18 + 65*t), int(15 + 35*t)))
    for y in range(45, 205):
        for x in (split - 1, split, split + 1):
            pixels[y][3*x:3*x+3] = bytes((198, 152, 73))
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    data = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


class UnrealBackend(object):
    """Live-only adapter; never instantiated by the offline harness."""
    def __init__(self):
        import unreal
        self.ue = unreal
        self.args = None

    def log(self, text): self.ue.log(text)
    def stop(self, text): self.ue.log_error(text)

    def census(self):
        lib = self.ue.EditorLoadingAndSavingUtils
        clean = lambda p: str(p.get_path_name()).split(".", 1)[0]
        return {"content": sorted(clean(x) for x in lib.get_dirty_content_packages()),
                "maps": sorted(clean(x) for x in lib.get_dirty_map_packages())}

    def preflight(self, args, unused_mode):
        self.args = args
        editor = self.ue.get_editor_subsystem(self.ue.UnrealEditorSubsystem)
        if editor.get_game_world() is not None: raise PlanError("PIE_OR_SIE_ACTIVE")
        if self.ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None: raise PlanError("SEQUENCER_OPEN")
        world = editor.get_editor_world()
        if world is None or str(world.get_outermost().get_name()) != args["level_package"]: raise PlanError("WRONG_WORLD")
        if self.census() != {"content": [], "maps": []}: raise PlanError("DIRTY_CENSUS|%s" % canonical(self.census()))

    def _guid(self, value):
        return norm_guid(self.ue.GuidLibrary.conv_guid_to_string(value))

    def _segments(self, show):
        ue = self.ue
        cues = list(show.get_editor_property("cues"))
        cue_index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        passage_first = {self._guid(r.get_editor_property("passage_guid")):
                         cue_index.get(self._guid(r.get_editor_property("first_cue_guid")), -1)
                         for r in show.get_editor_property("passage_settings")}
        tr = ue.InfinityStageTransportController()
        if not tr.build_segments(show): raise PlanError("BUILD_SEGMENTS_FAILED")
        out = []
        for row in tr.get_editor_property("segments"):
            gid = self._guid(row.get_editor_property("segment_guid"))
            out.append({"guid": gid, "label": str(row.get_editor_property("label")),
                        "type": enum_name(row.get_editor_property("type")),
                        "start": int(row.get_editor_property("start_frame").value),
                        "end": int(row.get_editor_property("end_frame").value),
                        "first_show_index": passage_first.get(gid, cue_index.get(gid, -1))})
        if any(r["first_show_index"] < 0 for r in out): raise PlanError("SEGMENT_SHOW_INDEX_UNRESOLVED")
        return out

    def _actors(self):
        return list(self.ue.get_editor_subsystem(self.ue.EditorActorSubsystem).get_all_level_actors())

    def _actor_rows(self):
        return sorted([{"path": str(a.get_path_name()), "label": str(a.get_actor_label()),
                        "class": str(a.get_class().get_name()), "hidden": bool(a.is_hidden_ed())}
                       for a in self._actors()], key=lambda x: x["path"])

    def _actor_by_path(self, path):
        hits = [a for a in self._actors() if str(a.get_path_name()) == path]
        if len(hits) != 1: raise PlanError("ACTOR_PATH_COUNT|%s|%d" % (path, len(hits)))
        return hits[0]

    def _channel_value(self, channel, frame):
        ue = self.ue
        keys = sorted(channel.get_keys(), key=lambda k: k.get_time(ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value)
        chosen = None
        for key in keys:
            if key.get_time(ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value <= frame:
                chosen = float(key.get_value())
        return chosen if chosen is not None else float(channel.get_default())

    def _opening_end_pose(self, show, args):
        ue = self.ue
        cues = [c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == args["opening_label"]]
        if len(cues) != 1: raise PlanError("OPENING_CUE_COUNT|%d" % len(cues))
        seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
        bindings = [b for b in seq.get_bindings() if str(b.get_display_name()) == args["opening_camera_label"]]
        if len(bindings) != 1: raise PlanError("OPENING_CAMERA_BINDING_COUNT|%d" % len(bindings))
        tracks = [t for t in bindings[0].get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1: raise PlanError("OPENING_CAMERA_TRANSFORM")
        end = int(seq.get_playback_end()) - 1
        channels = {re.sub(r"[_ ]\d+$", "", str(c.get_editor_property("channel_name"))): c
                    for c in tracks[0].get_sections()[0].get_all_channels()}
        def one(suffix):
            hits = [v for k, v in channels.items() if k.endswith(suffix)]
            if len(hits) != 1: raise PlanError("OPENING_CAMERA_CHANNEL|%s|%d" % (suffix, len(hits)))
            return self._channel_value(hits[0], end)
        focal = None
        for b in seq.get_bindings():
            for t in b.get_tracks():
                if t.get_class().get_name() == "MovieSceneFloatTrack" and str(t.get_property_name()) == "CurrentFocalLength":
                    sections = list(t.get_sections())
                    if len(sections) == 1:
                        ch = list(sections[0].get_all_channels())
                        if len(ch) == 1: focal = self._channel_value(ch[0], end)
        if focal is None: raise PlanError("OPENING_FOCAL_CHANNEL")
        return {"location": [one("Location.X"), one("Location.Y"), one("Location.Z")],
                "rotation": [one("Rotation.Y"), one("Rotation.Z"), one("Rotation.X")],
                "focal_mm": focal}

    def inspect(self, args, plan=None):
        ue = self.ue
        show = ue.load_asset(args["show_package"])
        actors = self._actor_rows()
        base = {"segments": self._segments(show), "actors": actors,
                "asset_exists": ue.EditorAssetLibrary.does_asset_exist(args["sequence_package"]),
                "owned_mask_exists": any(a["label"] == args["mask_label"] for a in actors),
                "tick_resolution": float(show.get_editor_property("tick_resolution").numerator) /
                                   show.get_editor_property("tick_resolution").denominator,
                "opening_end_pose": self._opening_end_pose(show, args)}
        if plan is None or not base["asset_exists"]: return base
        seq = ue.load_asset(args["sequence_package"])
        cuts = [s for t in seq.find_tracks_by_type(ue.MovieSceneCameraCutTrack) for s in t.get_sections()]
        camera_path = None
        if len(cuts) == 1:
            want = self._guid(cuts[0].get_camera_binding_id().get_editor_property("guid"))
            bindings = [b for b in seq.get_bindings() if self._guid(b.get_id()) == want]
            if len(bindings) == 1:
                world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
                objs = list(seq.locate_bound_objects(bindings[0], world))
                if len(objs) == 1: camera_path = str(objs[0].get_path_name())
        stage_keys = {path: self._read_visibility(seq, path) for path in plan["stage_actor_paths"]}
        hidden_keys = {path: self._read_visibility(seq, path) for path in plan["hidden_actor_paths"]}
        masks = [a for a in self._actors() if str(a.get_actor_label()) == args["mask_label"] and
                 OWNER_TAG in [str(t) for t in a.get_editor_property("tags")]]
        mask_label = str(masks[0].get_actor_label()) if len(masks) == 1 and self._read_visibility(seq, str(masks[0].get_path_name())) == plan["visibility"]["mask"] else None
        actual_visibility = {
            "stage": plan["visibility"]["stage"] if stage_keys and all(v == plan["visibility"]["stage"] for v in stage_keys.values()) else stage_keys,
            "hidden": plan["visibility"]["hidden"] if hidden_keys and all(v == plan["visibility"]["hidden"] for v in hidden_keys.values()) else hidden_keys,
            "mask": plan["visibility"]["mask"] if mask_label else None,
        }
        return dict(base, sequence_package=args["sequence_package"],
                    camera_cut_range=[int(cuts[0].get_start_frame()), int(cuts[0].get_end_frame())] if len(cuts) == 1 else None,
                    camera_cut_actor_path=camera_path,
                    stage_actor_paths=sorted(k for k, v in stage_keys.items() if v),
                    hidden_actor_paths=sorted(k for k, v in hidden_keys.items() if v),
                    visibility=actual_visibility, mask_label=mask_label,
                    camera_keys=self._read_camera_keys(seq, plan))

    def _binding_for_path(self, seq, path):
        world = self.ue.get_editor_subsystem(self.ue.UnrealEditorSubsystem).get_editor_world()
        rows = [b for b in seq.get_bindings()
                if any(str(obj.get_path_name()) == path for obj in seq.locate_bound_objects(b, world))]
        if len(rows) != 1: return None
        return rows[0]

    def _read_visibility(self, seq, path):
        ue = self.ue
        binding = self._binding_for_path(seq, path)
        if binding is None: return None
        tracks = [t for t in binding.get_tracks()
                  if t.get_class().get_name() == "MovieSceneVisibilityTrack" and str(t.get_property_name()) == "bHidden"]
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1: return None
        channels = list(tracks[0].get_sections()[0].get_all_channels())
        if len(channels) != 1: return None
        return [[int(k.get_time(ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value), bool(k.get_value())]
                for k in channels[0].get_keys()]

    def _read_camera_keys(self, seq, plan):
        ue = self.ue
        binding = self._binding_for_path(seq, plan["camera_actor_path"])
        if binding is None: return []
        tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1: return []
        channels = {re.sub(r"[_ ]\d+$", "", str(c.get_editor_property("channel_name"))): c
                    for c in tracks[0].get_sections()[0].get_all_channels()}
        def values(suffix):
            hits = [v for k, v in channels.items() if k.endswith(suffix)]
            if len(hits) != 1: return {}
            return {int(k.get_time(ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value): float(k.get_value())
                    for k in hits[0].get_keys()}
        loc = [values("Location.X"), values("Location.Y"), values("Location.Z")]
        rot = [values("Rotation.Y"), values("Rotation.Z"), values("Rotation.X")]
        focal_tracks = [t for b in seq.get_bindings() for t in b.get_tracks()
                        if t.get_class().get_name() == "MovieSceneFloatTrack" and str(t.get_property_name()) == "CurrentFocalLength"]
        if len(focal_tracks) != 1 or len(focal_tracks[0].get_sections()) != 1: return []
        fchannels = list(focal_tracks[0].get_sections()[0].get_all_channels())
        if len(fchannels) != 1: return []
        focal = {int(k.get_time(ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value): float(k.get_value())
                 for k in fchannels[0].get_keys()}
        out = []
        for row in plan["camera_keys"]:
            frame = row["frame"]
            if any(frame not in axis for axis in loc + rot) or frame not in focal: return []
            out.append({"frame": frame, "location": [axis[frame] for axis in loc],
                        "rotation": [axis[frame] for axis in rot], "focal_mm": focal[frame]})
        return out

    def backup(self, run, packages, prefix="PreE25Ending"):
        project = os.path.abspath(self.ue.Paths.project_dir())
        root = os.path.join(project, "Backups", "%s-%s" % (prefix, run))
        os.makedirs(root, exist_ok=False)
        files = []
        for package in packages:
            rel = package[len("/Game/"):].split("/")
            candidates = [os.path.join(project, "Content", *rel) + ext for ext in (".uasset", ".umap")]
            src = next((x for x in candidates if os.path.isfile(x)), None)
            if src is None: raise PlanError("BACKUP_SOURCE_MISSING|%s" % package)
            dst = os.path.join(root, os.path.basename(src)); shutil.copy2(src, dst)
            sha = hashlib.sha256(open(src, "rb").read()).hexdigest()
            if sha != hashlib.sha256(open(dst, "rb").read()).hexdigest(): raise PlanError("BACKUP_HASH|%s" % package)
            files.append({"package": package, "source": src, "backup": dst, "sha256": sha})
        write_json(os.path.join(root, "manifest.json"), {"run": run, "files": files}, exclusive=True)
        return {"root": root, "files": files}

    def _binding(self, seq, actor):
        ue = self.ue
        # UE 5.8 returns an existing binding from add_possessable; never rename it.
        world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
        for binding in seq.get_bindings():
            objs = list(seq.locate_bound_objects(binding, world))
            if actor in objs: return binding
        binding = seq.add_possessable(actor)
        if binding is None or not binding.is_valid(): raise PlanError("ADD_POSSESSABLE|%s" % actor.get_actor_label())
        binding.set_display_name(actor.get_actor_label())
        return binding

    def _visibility(self, binding, keys, end):
        ue = self.ue
        tracks = [t for t in binding.get_tracks()
                  if t.get_class().get_name() == "MovieSceneVisibilityTrack" and str(t.get_property_name()) == "bHidden"]
        if tracks: raise PlanError("OWNED_VISIBILITY_TRACK_ALREADY_EXISTS|%s" % binding.get_display_name())
        track = binding.add_track(ue.MovieSceneVisibilityTrack)
        track.set_property_name_and_path("bHidden", "bHidden")
        section = track.add_section(); section.set_range(0, end)
        section.set_completion_mode(ue.MovieSceneCompletionMode.RESTORE_STATE)
        channel = list(section.get_all_channels())[0]
        # Despite bHidden binding, this channel is visible semantics: True=shown.
        for frame, shown in keys:
            channel.add_key(ue.FrameNumber(int(frame)), bool(shown), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)

    def _transform(self, binding, keys, end):
        ue = self.ue
        track = binding.add_track(ue.MovieScene3DTransformTrack)
        section = track.add_section(); section.set_range(0, end)
        channels = {re.sub(r"[_ ]\d+$", "", str(c.get_editor_property("channel_name"))): c
                    for c in section.get_all_channels()}
        mapping = {"Location.X": lambda r: r["location"][0], "Location.Y": lambda r: r["location"][1],
                   "Location.Z": lambda r: r["location"][2], "Rotation.X": lambda r: r["rotation"][2],
                   "Rotation.Y": lambda r: r["rotation"][0], "Rotation.Z": lambda r: r["rotation"][1]}
        for suffix, getter in mapping.items():
            hits = [v for k, v in channels.items() if k.endswith(suffix)]
            if len(hits) != 1: raise PlanError("TRANSFORM_CHANNEL|%s|%d" % (suffix, len(hits)))
            for row in keys:
                hits[0].add_key(ue.FrameNumber(row["frame"]), float(getter(row)),
                                time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=ue.MovieSceneKeyInterpolation.AUTO)

    def _focal(self, seq, camera_binding, camera, keys, end):
        ue = self.ue
        comp = camera.get_cine_camera_component()
        binding = self._binding(seq, comp)
        binding.set_parent(camera_binding)
        track = binding.add_track(ue.MovieSceneFloatTrack)
        track.set_property_name_and_path("CurrentFocalLength", "CurrentFocalLength")
        section = track.add_section(); section.set_range(0, end)
        channel = list(section.get_all_channels())[0]
        for row in keys:
            channel.add_key(ue.FrameNumber(row["frame"]), float(row["focal_mm"]),
                            time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=ue.MovieSceneKeyInterpolation.AUTO)

    def apply(self, plan, args):
        ue = self.ue
        folder, name = args["sequence_package"].rsplit("/", 1)
        seq = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, ue.LevelSequence, ue.LevelSequenceFactoryNew())
        if seq is None: raise PlanError("CREATE_SEQUENCE")
        seq.set_display_rate(ue.FrameRate(plan["fps"], 1)); seq.set_playback_start(0); seq.set_playback_end(plan["total_frames"])
        camera = self._actor_by_path(plan["camera_actor_path"])
        camera_binding = self._binding(seq, camera)
        self._transform(camera_binding, plan["camera_keys"], plan["total_frames"])
        self._focal(seq, camera_binding, camera, plan["camera_keys"], plan["total_frames"])
        for path in plan["stage_actor_paths"]:
            self._visibility(self._binding(seq, self._actor_by_path(path)), plan["visibility"]["stage"], plan["total_frames"])
        for path in plan["hidden_actor_paths"]:
            self._visibility(self._binding(seq, self._actor_by_path(path)), plan["visibility"]["hidden"], plan["total_frames"])
        eas = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        xf = plan["mask"]["transform"]
        mask = eas.spawn_actor_from_class(ue.StaticMeshActor, ue.Vector(*xf["location"]),
                                          ue.Rotator(roll=xf["rotation"][2], pitch=xf["rotation"][0], yaw=xf["rotation"][1]), False)
        if mask is None: raise PlanError("MASK_SPAWN")
        mask.set_actor_label(plan["mask"]["label"]); mask.set_actor_scale3d(ue.Vector(*xf["scale"]))
        mask.set_editor_property("tags", list(mask.get_editor_property("tags")) + [ue.Name(OWNER_TAG)])
        comp = mask.get_editor_property("static_mesh_component")
        mesh, material = ue.load_asset(plan["mask"]["mesh"]), ue.load_asset(plan["mask"]["material"])
        if mesh is None or material is None: raise PlanError("MASK_ASSET")
        comp.set_static_mesh(mesh); comp.set_material(0, material); comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(ue.CollisionEnabled.NO_COLLISION)
        self._visibility(self._binding(seq, mask), plan["visibility"]["mask"], plan["total_frames"])
        cut = seq.add_track(ue.MovieSceneCameraCutTrack); section = cut.add_section(); section.set_range(0, plan["total_frames"])
        section.set_camera_binding_id(seq.get_binding_id(camera_binding))
        show, master = ue.load_asset(args["show_package"]), ue.load_asset(args["master_package"])
        cues = list(show.get_editor_property("cues")); cue = ue.InfinityShowCue()
        cue.set_editor_property("type", ue.InfinityCueType.SEQUENCE); cue.set_editor_property("label", CUE_LABEL); cue.set_editor_property("enabled", True)
        scene = cue.get_editor_property("scene"); scene.set_editor_property("sequence", seq); scene.set_editor_property("use_sequence_length", True)
        scene.set_editor_property("camera_owner", ue.InfinityCameraOwner.TIMELINE); cue.set_editor_property("scene", scene)
        cues.insert(plan["ending"]["show_index"], cue); show.set_editor_property("cues", cues)
        if not ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master): raise PlanError("REBUILD_MASTER")
        minted = list(show.get_editor_property("cues"))[plan["ending"]["show_index"]]
        return {"minted_guid": self._guid(minted.get_editor_property("cue_guid")),
                "label": str(minted.get_editor_property("label"))}

    def save(self, packages):
        dirty = sorted(set(self.census()["content"] + self.census()["maps"]))
        if dirty != sorted(packages): raise PlanError("UNEXPECTED_DIRTY|got=%s|want=%s" % (dirty, sorted(packages)))
        for package in packages:
            ok = (self.ue.get_editor_subsystem(self.ue.LevelEditorSubsystem).save_current_level()
                  if package == self.args["level_package"] else self.ue.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True))
            if not ok: raise PlanError("SAVE_FAILED|%s" % package)
        if self.census() != {"content": [], "maps": []}: raise PlanError("DIRTY_AFTER_SAVE")
        return list(packages)

    def revert(self, record, args):
        ue, plan = self.ue, record["plan"]
        show, master = ue.load_asset(args["show_package"]), ue.load_asset(args["master_package"])
        cues = list(show.get_editor_property("cues"))
        exact = [c for c in cues if self._guid(c.get_editor_property("cue_guid")) == plan["ending"]["guid"] and str(c.get_editor_property("label")) == CUE_LABEL]
        related = [c for c in cues if self._guid(c.get_editor_property("cue_guid")) == plan["ending"]["guid"] or str(c.get_editor_property("label")) == CUE_LABEL]
        if len(exact) != 1 or len(related) != 1: raise PlanError("REVERT_IDENTITY_DRIFT")
        show.set_editor_property("cues", [c for c in cues if c not in exact])
        owned = [a for a in self._actors() if OWNER_TAG in [str(t) for t in a.get_editor_property("tags")]]
        if len(owned) != 1 or owned[0].get_actor_label() != plan["mask"]["label"]: raise PlanError("REVERT_OWNED_SET")
        ue.get_editor_subsystem(ue.EditorActorSubsystem).destroy_actor(owned[0])
        if not ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master): raise PlanError("REVERT_REBUILD")
        archive = "/Game/InfinityStage/Dev/Sequences/_Reverted/LS_Ending_OpeningStage_%s" % record["run_id"]
        if not ue.EditorAssetLibrary.rename_asset(args["sequence_package"], archive): raise PlanError("REVERT_ARCHIVE")
        return {"archived_sequence": archive}


def _root(root=None): return os.path.abspath(root or os.path.dirname(__file__))
def _record_path(root, run): return os.path.join(root, "e25_ending_record_%s.json" % run)
def _confirm(mode, run, source): return "REVERT E25 %s" % source if mode == "REVERT" else "%s E25 %s" % (mode, run)


def _stop(backend, run, reason):
    line = "%s_STOPPED|run=%s|reason=%s" % (TOOL, run, reason)
    backend.stop(line)
    raise Stop(line)


def run_dry(run, args, backend, root):
    backend.preflight(args, "DRY"); snapshot = backend.inspect(args); plan = build_plan(snapshot, args)
    preview = write_preview(plan, os.path.join(root, "e25_ending_preview_%s.png" % run))
    report = os.path.join(root, "e25_ending_dry_%s.json" % run)
    write_json(report, {"run_id": run, "mode": "DRY", "writes": 0, "plan": plan,
                        "dirty_package_census": backend.census(), "preview": preview})
    write_json(os.path.join(root, "e25_ending_plan.json"), {"run_id": run, "snapshot_digest": digest(snapshot),
                                                            "plan_digest": digest(plan), "plan": plan})
    backend.log("E25_ENDING_DRY_OK|run=%s|s6=%s|closing=%s|stage=%d|hidden=%d|writes=0|report=%s" %
                (run, plan["anchors"]["scene6_guid"], plan["anchors"]["closing_guid"],
                 len(plan["stage_actor_paths"]), len(plan["hidden_actor_paths"]), report))
    return plan


def run_apply(run, args, backend, root):
    backend.preflight(args, "APPLY"); snapshot = backend.inspect(args); plan = build_plan(snapshot, args)
    dry = read_json(os.path.join(root, "e25_ending_plan.json"))
    if dry.get("snapshot_digest") != digest(snapshot) or dry.get("plan_digest") != digest(plan): _stop(backend, run, "CHANGED_SINCE_DRY")
    if not args.get("expected_scene6_guid") or not args.get("expected_closing_guid") or not args.get("expected_camera_path") or not args.get("expected_stage_actor_paths") or not args.get("expected_hidden_actor_paths"):
        _stop(backend, run, "PIN_DRY_IDENTITIES_REQUIRED")
    backup = backend.backup(run, plan["backup_packages"])
    path = _record_path(root, run)
    record = {"schema_version": 1, "tool": TOOL, "run_id": run, "status": "prepared", "args": args,
              "plan": plan, "snapshot_before": snapshot, "backup": backup}
    write_json(path, record, exclusive=True)
    result = backend.apply(plan, args)
    if result.get("label") != CUE_LABEL: _stop(backend, run, "MINTED_LABEL")
    minted = record_minted_guid(plan, result.get("minted_guid"))
    record.update({"status": "mutated_guid_recorded", "plan": plan, "mutation": result}); write_json(path, record)
    facts = backend.inspect(args, plan); failures = verify_after(plan, facts)
    dirty = sorted(set(backend.census()["content"] + backend.census()["maps"]))
    if failures or dirty != sorted(plan["named_packages"]): _stop(backend, run, "PRESAVE_READBACK|failures=%s|dirty=%s|NOTHING_SAVED" % (failures, dirty))
    saved = backend.save(plan["named_packages"]); facts = backend.inspect(args, plan); failures = verify_after(plan, facts)
    if failures or backend.census() != {"content": [], "maps": []}: _stop(backend, run, "POSTSAVE_READBACK|%s" % failures)
    record.update({"status": "saved_readback_verified", "snapshot_after": facts, "saved": saved}); write_json(path, record)
    backend.log("E25_ENDING_APPLY_OK|run=%s|guid=%s|saved=%s|backup=%s|record=%s|tests_required_singly=%s" %
                (run, minted, ",".join(saved), backup["root"], path, ",".join(REQUIRED_TESTS)))
    return record


def run_revert(run, source, args, backend, root):
    backend.preflight(args, "REVERT"); path = _record_path(root, source); record = read_json(path)
    if record.get("status") != "saved_readback_verified": _stop(backend, run, "SOURCE_NOT_APPLIED")
    current = backend.inspect(args, record["plan"]); failures = verify_after(record["plan"], current)
    if failures: _stop(backend, run, "APPLIED_STATE_DRIFT|%s" % failures)
    backup = backend.backup(run, record["plan"]["named_packages"], "PreE25EndingRevert")
    txn = os.path.join(root, "e25_ending_revert_%s.json" % run)
    write_json(txn, {"status": "prepared", "run_id": run, "source_run_id": source, "backup": backup}, exclusive=True)
    result = backend.revert(record, args)
    saved = backend.save([args["show_package"], args["master_package"], args["level_package"], result["archived_sequence"]])
    final = backend.inspect(args)
    if segment_failures(record["plan"]["segments_before"], final["segments"]) or final["asset_exists"] or backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "REVERT_READBACK")
    archived = path + ".reverted-" + run; os.rename(path, archived)
    write_json(txn, {"status": "saved_readback_verified", "run_id": run, "source_run_id": source,
                     "backup": backup, "saved": saved, "result": result, "archived_record": archived})
    backend.log("E25_ENDING_REVERT_OK|run=%s|source=%s|saved=%s|backup=%s|tests_required_singly=%s" %
                (run, source, ",".join(saved), backup["root"], ",".join(REQUIRED_TESTS)))
    return result


def main(raw, backend=None, root=None):
    raw = copy.deepcopy(raw or {}); mode = str(raw.get("mode", "DRY")).upper()
    run = str(raw.get("run_id") or datetime.datetime.now().strftime("E25-%Y%m%d-%H%M%S")); source = str(raw.get("source_run_id") or "")
    backend = backend or UnrealBackend(); root = _root(root)
    try:
        want = _confirm(mode, run, source)
        if raw.get("confirm") != want: _stop(backend, run, "CONFIRM_MISMATCH|want=%r|got=%r" % (want, raw.get("confirm")))
        args = normalise_args(raw.get("params") or {})
        if mode == "DRY": return run_dry(run, args, backend, root)
        if mode == "APPLY": return run_apply(run, args, backend, root)
        if mode == "REVERT" and source: return run_revert(run, source, args, backend, root)
        _stop(backend, run, "MODE_OR_SOURCE|%s" % mode)
    except PlanError as error:
        _stop(backend, run, "PLAN_REFUSED|%s" % error)
