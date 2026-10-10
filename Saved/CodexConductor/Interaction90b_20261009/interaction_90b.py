"""Job 90b: reconcile I2/I3 interaction camera and lighting transitions.

Offline-authored.  The conductor runs this module inside UE 5.8.  DRY is
read-only; APPLY/REVERT are transaction-recorded and save only named
Interaction Level Sequences.  No Show or level package is written.
"""
from __future__ import print_function

import copy
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil

TOOL = "INTERACTION_90B"
VERSION = "2026-10-10-job132"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SEQS = {
    1: "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy",
    2: "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips",
    3: "/Game/InfinityStage/Interactions/LS_Interaction_03_ForgetsHisName",
    4: "/Game/InfinityStage/Interactions/LS_Interaction_04_GetsAName",
    5: "/Game/InfinityStage/Interactions/LS_Interaction_05_BecomesKing",
}
CONFIRMS = {m: "%s INTERACTION90B" % m for m in ("DRY", "APPLY", "REVERT")}
PLAN = "interaction_90b_plan.json"
RECORD = "interaction_90b_record.json"
POSE = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")
DEFAULTS = {
    "i2_enabled": True,
    "i3_enabled": True,
    "lighting_audit_interactions": [1, 2, 3, 4, 5],
    "lighting_fix_steps": [],
    "i3_reveal_gap_frames": 2,
    "i3_spot_fade_frames": 100,
    "i3_missing_spots_policy": "refuse",
    "s3_black_fade_frames": 25,
    "through_plane_margin_cm": 1.0,
    "numeric_tolerance": 1.0e-4,
}


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def enum_name(value):
    """Normalise UE 5.8's '<E.V: n>', 'E.V' and plain-name enum strings."""
    text = str(value).strip().strip("<>")
    text = text.split(":", 1)[0].strip()
    return text.rsplit(".", 1)[-1]


def guid_text(value, converter=None):
    if converter is None:
        try:
            import unreal
            converter = unreal.GuidLibrary.conv_guid_to_string
        except (ImportError, AttributeError):
            converter = str
    return str(converter(value)).replace("-", "").replace("{", "").replace("}", "").upper()


def channel_base(value):
    """Channel display names may carry UE suffixes; return their semantic name."""
    text = str(value).strip()
    for name in POSE + ("CurrentFocalLength", "ManualFocusDistance", "Intensity", "Fade"):
        if text == name or text.startswith(name + " ") or text.startswith(name + "(") or text.startswith(name + "_"):
            return name
    return text


def plain_tree(value):
    if isinstance(value, dict): return {str(k): plain_tree(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [plain_tree(v) for v in value]
    if value is None or isinstance(value, (bool, int, float)): return value
    text = str(value)
    return enum_name(text) if text.startswith("<") and ":" in text else text


def canonical_binding(value):
    text = str(value).strip()
    return re.sub(r"\s*(?:\(\d+\)|_\d+|\s+\d+)$", "", text)


def lerp(a, b, t):
    return float(a) + (float(b) - float(a)) * float(t)


def smoothstep(t):
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


def angle_lerp(a, b, t):
    delta = (float(b) - float(a) + 180.0) % 360.0 - 180.0
    return float(a) + delta * float(t)


def interp(keys, frame, default=0.0):
    rows = sorted([[int(k[0]), float(k[1])] for k in keys])
    if not rows:
        return float(default)
    if frame <= rows[0][0]:
        return rows[0][1]
    if frame >= rows[-1][0]:
        return rows[-1][1]
    for left, right in zip(rows, rows[1:]):
        if left[0] <= frame <= right[0]:
            if right[0] == left[0]:
                return right[1]
            return lerp(left[1], right[1], (frame - left[0]) / float(right[0] - left[0]))
    raise AssertionError(frame)


def rewrite_i2_channel(keys, cut, release, end, target, rotation=False):
    """Preserve job-34's move-in, hold its cut pose, then land exactly at P03."""
    if not (0 < cut < release < end):
        raise PlanError("I2_FRAME_ORDER|cut=%d|release=%d|end=%d" % (cut, release, end))
    start = interp(keys, cut)
    out = [[int(f), float(v)] for f, v in keys if int(f) < cut]
    out.extend([[cut, start], [release, start]])
    for frame in range(release + 1, end + 1):
        t = smoothstep((frame - release) / float(end - release))
        value = angle_lerp(start, target, t) if rotation else lerp(start, target, t)
        out.append([frame, value])
    return out


def signed_plane_distance(point, plane_point, yaw_deg):
    r = math.radians(float(yaw_deg))
    normal = (-math.cos(r), -math.sin(r), 0.0)
    return sum((float(point[i]) - float(plane_point[i])) * normal[i] for i in range(3))


def plan_i2(snapshot, target, margin=1.0):
    cut, release, end = snapshot["cut"], snapshot["drop"], snapshot["playback"][1]
    channels = snapshot["mouth_transform"]["channels"]
    by = {row["base"]: row for row in channels}
    missing = [name for name in POSE if name not in by]
    if missing:
        raise PlanError("I2_POSE_CHANNELS_MISSING|%s" % missing)
    tmap = {"Location.X": "x", "Location.Y": "y", "Location.Z": "z",
            "Rotation.X": "roll", "Rotation.Y": "pitch", "Rotation.Z": "yaw"}
    after = {}
    for name in POSE:
        after[name] = rewrite_i2_channel(by[name]["keys"], cut, release, end, target[tmap[name]], name.startswith("Rotation"))
    start_point = [interp(by[n]["keys"], cut) for n in POSE[:3]]
    drape = snapshot["mouth_drape"]
    d0 = signed_plane_distance(start_point, drape["loc"], drape["yaw"])
    d1 = signed_plane_distance([target["x"], target["y"], target["z"]], drape["loc"], drape["yaw"])
    if abs(d0) < margin:
        raise PlanError("I2_START_NOT_CLEAR_OF_PLANE|start=%.3f|margin=%.3f" % (d0, margin))
    # The live P03 start is authored exactly on the transition-drape plane.
    # Accept that seam target (within tolerance) as well as a genuine sign
    # change, but continue to reject an endpoint that remains on the start side.
    lands_on_plane = abs(d1) <= margin
    if not lands_on_plane and d0 * d1 > 0.0:
        raise PlanError("I2_NOT_THROUGH_PLANE|start=%.3f|end=%.3f|margin=%.3f" % (d0, d1, margin))
    return {"cut": cut, "release": release, "end": end, "target": target, "channels": after,
            "plane_distance": {"cut": d0, "end": d1},
            "plane_result": "lands_on_plane" if lands_on_plane else "crosses_plane",
            "track": snapshot["mouth_transform"]["locator"]}


def plan_i3(snapshot, reference, gap, fade_frames, missing_spots_policy="refuse"):
    cut = snapshot["cut"]
    camera_rows = snapshot["hangar_transform"]["channels"]
    moving_frames = sorted({int(k[0]) for row in camera_rows for k in row["keys"] if int(k[0]) < cut})
    if len(moving_frames) < 2:
        raise PlanError("I3_CAMERA_MOVE_NOT_FOUND")
    settle = moving_frames[-1]
    loc_rows = {row["base"]: row for row in camera_rows if row["base"] in POSE[:3]}
    movement = math.sqrt(sum((interp(loc_rows[n]["keys"], settle) - interp(loc_rows[n]["keys"], 0)) ** 2
                             for n in POSE[:3]))
    if movement < 1.0:
        raise PlanError("I3_CAMERA_DOES_NOT_MOVE|cm=%.3f" % movement)
    spot_start = settle + int(gap)
    spot_end = spot_start + int(fade_frames)
    if spot_end >= cut:
        raise PlanError("I3_SPOT_AFTER_CUT|end=%d|cut=%d" % (spot_end, cut))
    spots = []
    for row in snapshot["spots"]:
        side = row["side"]
        target = float(reference.get(side, row["max_intensity"]))
        keys = [[0, 0.0], [spot_start, 0.0], [spot_end, target]]
        keys += [[int(f), float(v)] for f, v in row["keys"] if int(f) > spot_end]
        spots.append({"locator": row["locator"], "side": side, "before": row["keys"], "after": keys})
    if not spots:
        if missing_spots_policy != "blackout_only":
            raise PlanError("I3_SHADOW_SPOTS_NOT_FOUND|DECISION_REQUIRED|"
                            "Gary must choose i3_missing_spots_policy=blackout_only or author named hangar+mouth shadow spots")
    return {"settle": settle, "movement_cm": movement, "spot_start": spot_start, "spot_end": spot_end,
            "blackout": [[0, 1.0], [settle, 1.0], [spot_end, 0.0]], "spots": spots,
            "missing_spots_policy": missing_spots_policy,
            "creative_decision": ("blackout_only: reveal uses existing I3 lighting; no shadow spots are created"
                                  if not spots else "authored shadow spots")}


def lighting_audit(snapshot, tolerance=0.05):
    before, after = snapshot["cut"] - 1, snapshot["cut"]
    rows = []
    for spot in snapshot["spots"]:
        vb, va = interp(spot["keys"], before), interp(spot["keys"], after)
        rows.append({"binding": spot["binding"], "side": spot["side"], "before": vb, "after": va})
    hb = sum(r["before"] for r in rows if r["side"] == "hangar")
    ma = sum(r["after"] for r in rows if r["side"] == "mouth")
    stops = None if hb <= 0.0 or ma <= 0.0 else math.log(ma / hb, 2.0)
    return {"interaction": snapshot["interaction"], "cut": snapshot["cut"], "spot_rows": rows,
            "hangar_before": hb, "mouth_after": ma, "signed_stops": stops,
            "pop": (hb != ma) if stops is None else abs(stops) > tolerance,
            "scope": "authored shadow-spot intensity; F17 live census adds world lights, exposure and fog"}


def scene_tail_blackout(playback, fade_frames):
    start, end = int(playback[0]), int(playback[1])
    fade = int(fade_frames)
    if fade <= 0 or fade >= end - start:
        raise PlanError("SCENE_BLACK_FADE_RANGE|fade=%d|playback=%s" % (fade, playback))
    return [[end - fade, 0.0], [end - 1, 1.0]]


def merged_params(raw):
    out = copy.deepcopy(DEFAULTS)
    out.update(copy.deepcopy(raw or {}))
    out["lighting_audit_interactions"] = [int(v) for v in out["lighting_audit_interactions"]]
    out["i3_reveal_gap_frames"] = int(out["i3_reveal_gap_frames"])
    out["i3_spot_fade_frames"] = int(out["i3_spot_fade_frames"])
    out["s3_black_fade_frames"] = int(out["s3_black_fade_frames"])
    out["through_plane_margin_cm"] = float(out["through_plane_margin_cm"])
    out["numeric_tolerance"] = float(out["numeric_tolerance"])
    if out["i3_missing_spots_policy"] not in ("refuse", "blackout_only"):
        raise PlanError("I3_MISSING_SPOTS_POLICY|%s" % out["i3_missing_spots_policy"])
    if any(v not in SEQS for v in out["lighting_audit_interactions"]):
        raise PlanError("INTERACTION_RANGE")
    for step in out["lighting_fix_steps"]:
        if step.get("interaction") not in SEQS or step.get("kind") not in ("PPV_WEIGHT", "LIGHT_HIDE", "LIGHT_DIM", "ACTOR_HIDE"):
            raise PlanError("LIGHTING_STEP_SHAPE|%s" % step)
        if not step.get("actor_label") or not step.get("keys"):
            raise PlanError("LIGHTING_STEP_FIELDS|%s" % step)
    return out


def _json_write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")


def _json_read(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise Stop("MISSING_JSON|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class UnrealBackend(object):
    def __init__(self, root=None):
        import unreal
        self.u = unreal
        self.root = root or os.path.dirname(os.path.abspath(__file__))

    def log(self, text):
        self.u.log(text)

    def fail(self, text):
        self.u.log_error(text)
        raise Stop(text)

    def census(self):
        lib = self.u.EditorLoadingAndSavingUtils
        return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}

    def preflight(self, mode, confirm):
        if confirm != CONFIRMS[mode]:
            raise Stop("CONFIRM|expected=%s" % CONFIRMS[mode])
        world = self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem).get_editor_world()
        if world is None or str(world.get_path_name()).split(".")[0] != WORLD:
            raise Stop("WORLD|%s" % world)
        if self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem).get_game_world() is not None:
            raise Stop("PIE_OR_SIE_RUNNING")
        if self.census() != {"content": [], "maps": []}:
            raise Stop("DIRTY_AT_START|%s" % self.census())

    def _span(self, section, seq):
        return [int(section.get_start_frame() if section.has_start_frame() else seq.get_playback_start()),
                int(section.get_end_frame() if section.has_end_frame() else seq.get_playback_end())]

    def _keys(self, channel):
        return sorted([[int(k.get_time().frame_number.value), float(k.get_value())] for k in channel.get_keys()])

    def _track_snapshot(self, binding, track_index, track):
        sections = []
        for si, section in enumerate(track.get_sections()):
            channels = []
            for ci, channel in enumerate(section.get_all_channels()):
                channels.append({"name": str(channel.channel_name), "base": channel_base(channel.channel_name),
                                 "keys": self._keys(channel), "channel_index": ci})
            sections.append({"range": self._span(section, binding.get_sequence()), "section_index": si,
                             "channels": channels})
        return {"class": track.get_class().get_name(), "display": str(track.get_display_name()),
                "track_index": track_index, "sections": sections}

    def _binding_rows(self, seq):
        rows = []
        for binding in seq.get_bindings():
            tracks = []
            for ti, track in enumerate(binding.get_tracks()):
                sections = []
                for si, section in enumerate(track.get_sections()):
                    channels = [{"name": str(ch.channel_name), "base": channel_base(ch.channel_name),
                                 "keys": self._keys(ch), "channel_index": ci}
                                for ci, ch in enumerate(section.get_all_channels())]
                    sections.append({"range": self._span(section, seq), "section_index": si, "channels": channels})
                tracks.append({"class": track.get_class().get_name(), "display": str(track.get_display_name()),
                               "track_index": ti, "sections": sections})
            rows.append({"guid": guid_text(binding.get_id()), "name": str(binding.get_display_name()), "tracks": tracks})
        return rows

    def _cuts(self, seq, names):
        rows = []
        for ti, track in enumerate(seq.get_tracks()):
            if track.get_class().get_name() != "MovieSceneCameraCutTrack":
                continue
            for si, section in enumerate(track.get_sections()):
                value = section.get_camera_binding_id().get_editor_property("guid")
                guid = guid_text(value)
                rows.append({"range": self._span(section, seq), "active": bool(section.is_active()),
                             "guid": guid, "camera": names.get(guid, "?"), "locator": [ti, si]})
        return rows

    def _marker(self, seq, wanted):
        rows = []
        for marker in self.u.MovieSceneSequenceExtensions.get_marked_frames(seq):
            label = str(marker.label).strip().lower()
            if wanted in label:
                tick = seq.get_tick_resolution().numerator / float(seq.get_tick_resolution().denominator)
                fps = seq.get_display_rate().numerator / float(seq.get_display_rate().denominator)
                rows.append(int(round(int(marker.frame_number.value) / (tick / fps))))
        if len(rows) != 1:
            raise Stop("MARKER_COUNT|%s|%d" % (wanted, len(rows)))
        return rows[0]

    def snapshot(self, n):
        seq = self.u.load_asset(SEQS[n])
        if seq is None:
            raise Stop("LOAD_SEQUENCE|I%d" % n)
        bindings = self._binding_rows(seq)
        names = {r["guid"]: r["name"] for r in bindings}
        cuts = [r for r in self._cuts(seq, names) if r["active"]]
        boundaries = sorted(set(r["range"][1] for r in cuts) & set(r["range"][0] for r in cuts))
        if len(boundaries) != 1:
            raise Stop("SLEIGHT_BOUNDARY_COUNT|I%d|%s" % (n, boundaries))
        cut = boundaries[0]
        def binding_named(text):
            rows = [r for r in bindings if canonical_binding(r["name"]) == text]
            if len(rows) != 1:
                raise Stop("BINDING_COUNT|I%d|%s|%d" % (n, text, len(rows)))
            return rows[0]
        def transform(row):
            tracks = [t for t in row["tracks"] if t["class"] == "MovieScene3DTransformTrack"]
            if len(tracks) != 1 or len(tracks[0]["sections"]) != 1:
                raise Stop("TRANSFORM_COUNT|%s|%d" % (row["name"], len(tracks)))
            sec = tracks[0]["sections"][0]
            return {"locator": [row["guid"], tracks[0]["track_index"], sec["section_index"]], "channels": sec["channels"]}
        hangar = binding_named("S%d Sleight Hangar Camera" % n)
        mouth = binding_named("I%d Sleight Mouth Camera" % n)
        drape = binding_named("Transition Drape (baked)")
        template = None
        live_drape = [b for b in seq.get_bindings() if guid_text(b.get_id()) == drape["guid"]][0]
        try:
            template = live_drape.get_object_template().get_editor_property("root_component")
        except Exception:
            template = None
        if template is None:
            raise Stop("MOUTH_DRAPE_TEMPLATE|I%d" % n)
        loc = template.get_editor_property("relative_location")
        rot = template.get_editor_property("relative_rotation")
        spots = []
        for row in bindings:
            low = row["name"].lower()
            if "shadow" not in low or "spot" not in low:
                continue
            side = "hangar" if "hangar" in low else ("mouth" if "mouth" in low else None)
            for track in row["tracks"]:
                for sec in track["sections"]:
                    for ch in sec["channels"]:
                        if ch["base"] == "Intensity":
                            spots.append({"binding": row["name"], "side": side, "keys": ch["keys"],
                                          "max_intensity": max([v for _, v in ch["keys"]] or [0.0]),
                                          "locator": [row["guid"], track["track_index"], sec["section_index"], ch["channel_index"]]})
        return {"interaction": n, "path": SEQS[n], "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
                "cut": cut, "drop": self._marker(seq, "cst drop"), "cuts": cuts, "bindings": bindings,
                "hangar_transform": transform(hangar), "mouth_transform": transform(mouth),
                "mouth_drape": {"loc": [float(loc.x), float(loc.y), float(loc.z)], "yaw": float(rot.yaw)}, "spots": spots}

    def _show(self):
        show = self.u.load_asset(SHOW)
        if show is None: raise Stop("LOAD_SHOW")
        return show

    def scene_sequence(self, scene_number):
        rows = []
        for cue in self._show().get_editor_property("cues"):
            label = str(cue.get_editor_property("label"))
            if re.match(r"^Scene\s+%d(?:\D|$)" % scene_number, label) and bool(cue.get_editor_property("enabled")):
                seq = cue.get_editor_property("scene").get_editor_property("sequence")
                if seq is not None: rows.append(seq)
        if len(rows) != 1: raise Stop("SCENE_SEQUENCE_COUNT|S%d|%d" % (scene_number, len(rows)))
        return rows[0]

    def passage_pose(self, passage_number):
        show = self._show()
        rows = [p for p in show.get_editor_property("passage_settings")
                if str(p.get_editor_property("label")) == "Passage %d" % passage_number]
        if len(rows) != 1:
            raise Stop("PASSAGE_COUNT|%d|%d" % (passage_number, len(rows)))
        pguid = rows[0].get_editor_property("passage_guid")
        lib = self.u.InfinityStageCameraPilotLibrary
        fr = lib.get_passage_frame_range(show, pguid)
        if isinstance(fr, tuple) and len(fr) == 3 and isinstance(fr[0], bool):
            if not fr[0]: raise Stop("PASSAGE_RANGE_FALSE")
            fr = fr[1:]
        result = lib.get_passage_camera_pose(show, pguid, int(fr[0]))
        if isinstance(result, tuple) and len(result) == 4 and isinstance(result[0], bool):
            if not result[0]: raise Stop("PASSAGE_POSE_FALSE")
            result = result[1:]
        view, focal, focus = result
        rot = view.rotation.rotator()
        return {"x": float(view.translation.x), "y": float(view.translation.y), "z": float(view.translation.z),
                "roll": float(rot.roll), "pitch": float(rot.pitch), "yaw": float(rot.yaw),
                "focal": float(focal), "focus": float(focus), "passage": passage_number, "start_tick": int(fr[0])}

    def _load_i2_order(self):
        path = os.path.normpath(os.path.join(self.root, "..", "I2Order_20261008", "i2_order.py"))
        spec = importlib.util.spec_from_file_location("job90b_i2_order", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def _pose_from_snapshot(self, snapshot, side, frame):
        rows = snapshot["hangar_transform" if side == "hangar" else "mouth_transform"]["channels"]
        values = {r["base"]: interp(r["keys"], frame) for r in rows if r["base"] in POSE}
        return {"loc": [values["Location.X"], values["Location.Y"], values["Location.Z"]],
                "roll": values["Rotation.X"], "pitch": values["Rotation.Y"], "yaw": values["Rotation.Z"]}

    def world_lighting_audit(self, n, snapshot):
        """Generalise job-39 F17's live lights/exposure/fog census to I1-I5."""
        order = self._load_i2_order(); seq = self.u.load_asset(SEQS[n]); osnap = order._snapshot(seq)
        actors = order._actors(); by_label = {}
        for actor in actors: by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
        cut = snapshot["cut"]

        def side(which, frame, drape_name):
            pose = self._pose_from_snapshot(snapshot, which, frame)
            drapes = [b for b in seq.get_bindings() if canonical_binding(b.get_display_name()) == drape_name]
            if len(drapes) != 1: raise PlanError("F17_DRAPE_COUNT|I%d|%s|%d" % (n, drape_name, len(drapes)))
            root = drapes[0].get_object_template().get_editor_property("root_component")
            loc = root.get_editor_property("relative_location"); rot = root.get_editor_property("relative_rotation")
            point = [float(loc.x), float(loc.y), float(loc.z)]
            normal = order.rot_z([-1.0, 0.0, 0.0], float(rot.yaw))
            lights = order._light_rows(actors, osnap, frame) + order._spawned_spot_rows(osnap, frame)
            lights = [r for r in lights if r["kind"] == "directional" or not r.get("radius") or
                      math.dist(r["loc"], point) < float(r["radius"])]
            volumes = order._ppv_rows(actors, pose["loc"])
            camera_name = "S%d Sleight Hangar Camera" % n if which == "hangar" else "I%d Sleight Mouth Camera" % n
            cameras = by_label.get(camera_name, [])
            if len(cameras) != 1: raise PlanError("F17_CAMERA_ACTOR_COUNT|I%d|%s|%d" % (n, camera_name, len(cameras)))
            exposure = order.effective_exposure(volumes, order._camera_pp(cameras[0]))
            exposure["unbound"] = {v["id"]: v["unbound"] for v in volumes}; exposure["rows"] = volumes
            return {"camera": camera_name, "frame": frame, "pose": pose, "point": point,
                    "light": order.side_summary(lights, point, normal), "exposure": exposure,
                    "fog": order._fog_rows(actors, pose["loc"], point)}

        before = side("hangar", cut - 1, "Sleight Hangar Drape")
        after = side("mouth", cut, "Transition Drape (baked)")
        spots = {r["binding"]: (interp(r["keys"], cut - 1), interp(r["keys"], cut)) for r in snapshot["spots"]}
        rate = seq.get_display_rate(); fps = rate.numerator / float(rate.denominator)
        ranked = order.rank_cut(before, after, cut, fps, spots, before["fog"], after["fog"])
        proposals = order.proposals_for_cut(ranked, before, after, cut, snapshot["drop"], snapshot["playback"][1])
        return plain_tree({"status": "OK", "before": before, "after": after, "ranked": ranked,
                           "proposals": proposals, "shared_math": "I2Order_20261008/i2_order.py"})

    def build_report(self, params, run):
        snaps = {n: self.snapshot(n) for n in sorted(set(params["lighting_audit_interactions"] + [2, 3]))}
        target = self.passage_pose(3)
        i2 = plan_i2(snaps[2], target, params["through_plane_margin_cm"]) if params["i2_enabled"] else None
        ref = {r["side"]: r["max_intensity"] for r in snaps[2]["spots"] if r["side"]}
        i3 = plan_i3(snaps[3], ref, params["i3_reveal_gap_frames"], params["i3_spot_fade_frames"],
                     params["i3_missing_spots_policy"]) if params["i3_enabled"] else None
        scene3 = self.scene_sequence(3) if i3 else None
        if scene3:
            i3_seq = self.u.load_asset(SEQS[3])
            for label, candidate in (("S3", scene3), ("I3", i3_seq)):
                existing = [t for t in candidate.get_tracks() if t.get_class().get_name() == "MovieSceneFadeTrack"]
                if existing: raise Stop("%s_FADE_TRACK_EXISTS|count=%d" % (label, len(existing)))
            s3_end = int(scene3.get_playback_end())
            s3_playback = [int(scene3.get_playback_start()), s3_end]
            i3["scene3"] = {"path": scene3.get_path_name().split(".")[0],
                            "playback": s3_playback,
                            "blackout": scene_tail_blackout(s3_playback, params["s3_black_fade_frames"])}
        audits = []
        for n in params["lighting_audit_interactions"]:
            row = lighting_audit(snaps[n])
            try:
                row["f17"] = self.world_lighting_audit(n, snaps[n])
            except Exception as exc:
                row["f17"] = {"status": "UNCLEAR", "error": "%s: %s" % (type(exc).__name__, exc),
                              "searched": "cut cameras, world/spawned lights, PP exposure, fog at cut-1/cut"}
            audits.append(row)
        inputs = {"params": params, "snapshots": snaps, "target": target, "i2": i2, "i3": i3,
                  "lighting": audits}
        return {"schema": 1, "version": VERSION, "run": run, "input_digest": digest(inputs),
                "inputs": inputs, "packages": sorted(set(([SEQS[2]] if i2 else []) +
                                                       ([SEQS[3], i3["scene3"]["path"]] if i3 else []) +
                                                       [SEQS[s["interaction"]] for s in params["lighting_fix_steps"]])),
                "census": self.census(), "proof": "measured live read-only; rendered acceptance remains open"}

    def _locate_channel(self, seq, locator):
        guid, ti, si, ci = locator
        rows = [b for b in seq.get_bindings() if guid_text(b.get_id()) == guid]
        if len(rows) != 1: raise Stop("LOCATOR_BINDING|%s" % guid)
        return list(list(list(rows[0].get_tracks())[ti].get_sections())[si].get_all_channels())[ci]

    def _rewrite(self, channel, keys):
        for key in list(channel.get_keys()): channel.remove_key(key)
        for frame, value in keys:
            channel.add_key(self.u.FrameNumber(int(frame)), float(value),
                            time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=self.u.MovieSceneKeyInterpolation.LINEAR)

    def _asset_file(self, path):
        root = self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_content_dir())
        return os.path.join(root, *path[len("/Game/"):].split("/")) + ".uasset"

    def _backup(self, run, packages, suffix=""):
        project = self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_dir())
        folder = os.path.join(project, "Backups", "PreInteraction90b%s-%s" % (suffix, run))
        os.makedirs(folder)
        rows = []
        for package in packages:
            src = self._asset_file(package); dst = os.path.join(folder, os.path.basename(src))
            if not os.path.isfile(src): raise Stop("BACKUP_SOURCE|%s" % src)
            shutil.copy2(src, dst)
            rows.append({"package": package, "backup": dst, "sha256": hashlib.sha256(open(dst, "rb").read()).hexdigest()})
        return folder, rows

    def _add_fade(self, seq, keys):
        existing = [t for t in seq.get_tracks() if t.get_class().get_name() == "MovieSceneFadeTrack"]
        if existing: raise Stop("I3_FADE_TRACK_EXISTS")
        track = seq.add_master_track(self.u.MovieSceneFadeTrack)
        section = track.add_section(); section.set_range(seq.get_playback_start(), seq.get_playback_end())
        channel = list(section.get_all_channels())[0]
        self._rewrite(channel, keys)
        return {"track_index": list(seq.get_tracks()).index(track), "keys": keys}

    def _add_fix(self, seq, step):
        actors = [a for a in self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors()
                  if str(a.get_actor_label()) == step["actor_label"]]
        if len(actors) != 1: raise Stop("FIX_ACTOR_COUNT|%s|%d" % (step["actor_label"], len(actors)))
        bindings = [(b, canonical_binding(b.get_display_name())) for b in seq.get_bindings()]
        rows = [b for b, name in bindings if name == step["actor_label"]]
        if len(rows) > 1: raise Stop("FIX_BINDING_AMBIGUOUS|%s" % step["actor_label"])
        created = []
        actor_binding = rows[0] if len(rows) == 1 else seq.add_possessable(actors[0])
        if not rows:
            actor_binding.set_display_name(step["actor_label"]); created.append(guid_text(actor_binding.get_id()))
        binding = actor_binding
        kind = step["kind"]
        if kind == "LIGHT_DIM":
            component = actors[0].get_component_by_class(self.u.LightComponent)
            if component is None: raise Stop("FIX_LIGHT_COMPONENT|%s" % step["actor_label"])
            child_name = step["actor_label"] + "/LightComponent"
            children = [b for b in seq.get_bindings() if canonical_binding(b.get_display_name()) == child_name]
            if len(children) > 1: raise Stop("FIX_COMPONENT_BINDING_AMBIGUOUS|%s" % child_name)
            if children:
                binding = children[0]
            else:
                binding = seq.add_possessable(component); binding.set_parent(actor_binding); binding.set_display_name(child_name)
                created.append(guid_text(binding.get_id()))
        cls = self.u.MovieSceneVisibilityTrack if kind in ("LIGHT_HIDE", "ACTOR_HIDE") else self.u.MovieSceneFloatTrack
        class_name = "MovieSceneVisibilityTrack" if kind in ("LIGHT_HIDE", "ACTOR_HIDE") else "MovieSceneFloatTrack"
        prop = "bHidden" if kind in ("LIGHT_HIDE", "ACTOR_HIDE") else ("BlendWeight" if kind == "PPV_WEIGHT" else "Intensity")
        for old in binding.get_tracks():
            if old.get_class().get_name() != class_name: continue
            try: old_prop = str(old.get_property_name())
            except Exception: old_prop = ""
            if (prop == "bHidden") or old_prop == prop:
                raise Stop("FIX_TRACK_ALREADY_EXISTS|%s|%s" % (step["actor_label"], prop))
        track = binding.add_track(cls); track.set_property_name_and_path(prop, prop if prop != "BlendWeight" else "blend_weight")
        section = track.add_section(); section.set_range(seq.get_playback_start(), seq.get_playback_end())
        channel = list(section.get_all_channels())[0]
        for frame, value in step["keys"]:
            channel.add_key(self.u.FrameNumber(int(frame)), bool(value) if isinstance(value, bool) else float(value),
                            time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE)
        return {"binding_guid": guid_text(binding.get_id()), "track_index": list(binding.get_tracks()).index(track),
                "created_bindings": created, "track_class": track.get_class().get_name(), "step": step}

    def _keys_match(self, got, want, tol=1.0e-4):
        if len(got) != len(want): return False
        for left, right in zip(got, want):
            if int(left[0]) != int(right[0]) or abs(float(left[1]) - float(right[1])) > tol * max(1.0, abs(float(right[1]))):
                return False
        return True

    def _readback(self, record, applied):
        checks = []
        for row in record["channels"]:
            seq = self.u.load_asset(row["package"])
            got = self._keys(self._locate_channel(seq, row["locator"]))
            want = row["after"] if applied else row["before"]
            if not self._keys_match(got, want): raise Stop("READBACK_CHANNEL|%s" % row["locator"])
            checks.append("channel:%s:%d" % (row["package"], len(got)))
        for fade in record.get("fades", []):
            seq3 = self.u.load_asset(fade["package"])
            fades = [t for t in seq3.get_tracks() if t.get_class().get_name() == "MovieSceneFadeTrack"]
            if applied:
                idx = fade["track_index"]
                if idx >= len(list(seq3.get_tracks())) or list(seq3.get_tracks())[idx].get_class().get_name() != "MovieSceneFadeTrack":
                    raise Stop("READBACK_FADE_TRACK")
                got = self._keys(list(list(seq3.get_tracks())[idx].get_sections())[0].get_all_channels()[0])
                if not self._keys_match(got, fade["keys"]): raise Stop("READBACK_FADE_KEYS")
                checks.append("fade:%s:%d" % (fade["package"], len(got)))
            elif fades:
                raise Stop("READBACK_FADE_REVERT|%s|count=%d" % (fade["package"], len(fades)))
        for row in record["fixes"]:
            seq = self.u.load_asset(SEQS[int(row["step"]["interaction"])]); matches = [b for b in seq.get_bindings() if guid_text(b.get_id()) == row["binding_guid"]]
            if applied:
                if len(matches) != 1: raise Stop("READBACK_FIX_BINDING")
                tracks = list(matches[0].get_tracks()); idx = row["track_index"]
                if idx >= len(tracks) or tracks[idx].get_class().get_name() != row["track_class"]: raise Stop("READBACK_FIX_TRACK")
                got = self._keys(list(tracks[idx].get_sections())[0].get_all_channels()[0])
                if not self._keys_match(got, row["step"]["keys"]): raise Stop("READBACK_FIX_KEYS")
                checks.append("fix:%s" % row["step"].get("id", row["step"]["actor_label"]))
            elif matches and row["binding_guid"] not in row["created_bindings"]:
                tracks = list(matches[0].get_tracks())
                if len(tracks) > row["track_index"]: raise Stop("READBACK_FIX_REVERT")
        return checks

    def apply(self, report, run):
        packages = report["packages"]
        if not packages: raise Stop("NOTHING_SELECTED")
        folder, backups = self._backup(run, packages)
        record_path = os.path.join(self.root, RECORD)
        if os.path.exists(record_path): raise Stop("RECORD_EXISTS|REVERT_FIRST")
        record = {"applied": False, "run": run, "packages": packages, "backup": folder, "backup_files": backups,
                  "input_digest": report["input_digest"], "channels": [], "fades": [], "fixes": []}
        _json_write(record_path, record, exclusive=True)
        inputs = report["inputs"]
        if inputs["i2"]:
            seq = self.u.load_asset(SEQS[2]); seq.modify()
            snap = inputs["snapshots"][2] if 2 in inputs["snapshots"] else inputs["snapshots"]["2"]
            for row in snap["mouth_transform"]["channels"]:
                if row["base"] not in inputs["i2"]["channels"]: continue
                loc = snap["mouth_transform"]["locator"] + [row["channel_index"]]
                record["channels"].append({"package": SEQS[2], "locator": loc, "before": row["keys"],
                                           "after": inputs["i2"]["channels"][row["base"]]})
                self._rewrite(self._locate_channel(seq, loc), inputs["i2"]["channels"][row["base"]])
        if inputs["i3"]:
            seq = self.u.load_asset(SEQS[3]); seq.modify()
            fade = self._add_fade(seq, inputs["i3"]["blackout"]); fade["package"] = SEQS[3]; record["fades"].append(fade)
            scene3 = self.u.load_asset(inputs["i3"]["scene3"]["path"]); scene3.modify()
            fade = self._add_fade(scene3, inputs["i3"]["scene3"]["blackout"])
            fade["package"] = inputs["i3"]["scene3"]["path"]; record["fades"].append(fade)
            for row in inputs["i3"]["spots"]:
                record["channels"].append({"package": SEQS[3], "locator": row["locator"], "before": row["before"], "after": row["after"]})
                self._rewrite(self._locate_channel(seq, row["locator"]), row["after"])
        for step in inputs["params"]["lighting_fix_steps"]:
            seq = self.u.load_asset(SEQS[int(step["interaction"])]); seq.modify()
            record["fixes"].append(self._add_fix(seq, step))
        actual = sorted(self.census()["content"] + self.census()["maps"])
        if actual != sorted(packages): raise Stop("DIRTY_SCOPE|expected=%s|actual=%s|NOTHING_SAVED" % (packages, actual))
        for package in packages:
            if not self.u.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True): raise Stop("SAVE_FAILED|%s" % package)
        if self.census() != {"content": [], "maps": []}: raise Stop("DIRTY_AFTER_SAVE|%s" % self.census())
        record["readback"] = self._readback(record, True)
        record["applied"] = True; _json_write(record_path, record)
        return record

    def revert(self, run):
        path = os.path.join(self.root, RECORD); record = _json_read(path)
        if not record.get("applied"): raise Stop("RECORD_NOT_APPLIED")
        folder, backups = self._backup(run, record["packages"], "Revert")
        for row in record["channels"]:
            seq = self.u.load_asset(row["package"]); seq.modify()
            got = self._keys(self._locate_channel(seq, row["locator"]))
            if not self._keys_match(got, row["after"]): raise Stop("REVERT_CHANNEL_DRIFT|%s" % row["locator"])
            self._rewrite(self._locate_channel(seq, row["locator"]), row["before"])
        for fade in reversed(record.get("fades", [])):
            seq = self.u.load_asset(fade["package"]); tracks = list(seq.get_tracks()); idx = fade["track_index"]
            if idx >= len(tracks) or tracks[idx].get_class().get_name() != "MovieSceneFadeTrack": raise Stop("REVERT_FADE_DRIFT")
            seq.remove_master_track(tracks[idx])
        # F17-style fix tracks are deliberately required to be the last track on their binding.
        for row in reversed(record["fixes"]):
            seq = self.u.load_asset(SEQS[int(row["step"]["interaction"])]); matches = [b for b in seq.get_bindings() if guid_text(b.get_id()) == row["binding_guid"]]
            if len(matches) != 1: raise Stop("REVERT_FIX_BINDING")
            tracks = list(matches[0].get_tracks())
            if row["track_index"] != len(tracks) - 1: raise Stop("REVERT_FIX_TRACK_DRIFT")
            matches[0].remove_track(tracks[-1])
            for created_guid in reversed(row["created_bindings"]):
                made = [b for b in seq.get_bindings() if guid_text(b.get_id()) == created_guid]
                if len(made) != 1 or list(made[0].get_tracks()): raise Stop("REVERT_CREATED_BINDING_DRIFT|%s" % created_guid)
                seq.remove_possessable(made[0])
        actual = sorted(self.census()["content"] + self.census()["maps"])
        if actual != sorted(record["packages"]): raise Stop("REVERT_DIRTY_SCOPE|%s" % actual)
        for package in record["packages"]:
            if not self.u.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True): raise Stop("REVERT_SAVE|%s" % package)
        if self.census() != {"content": [], "maps": []}: raise Stop("REVERT_DIRTY_AFTER_SAVE")
        readback = self._readback(record, False)
        archived = path + ".reverted-" + run; os.rename(path, archived)
        return {"packages": record["packages"], "backup": folder, "backup_files": backups, "archived": archived,
                "readback": readback}


def main(args, backend=None, root=None):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or ("I90B-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    backend = backend or UnrealBackend(root)
    if mode not in CONFIRMS: backend.fail("%s_FAILED|run=%s|MODE|%s" % (TOOL, run, mode))
    try:
        params = merged_params(args.get("params"))
        backend.preflight(mode, args.get("confirm"))
        if mode == "DRY":
            report = backend.build_report(params, run)
            report_path = os.path.join(backend.root, "interaction_90b_dry_%s.json" % run)
            _json_write(report_path, report)
            _json_write(os.path.join(backend.root, PLAN), {"params": params, "input_digest": report["input_digest"], "report": report_path})
            if backend.census() != {"content": [], "maps": []}: raise Stop("DRY_DIRTIED")
            backend.log("INTERACTION_90B_DRY_OK|run=%s|mutated=0|packages=%s|lighting_pops=%d|dirty=0|report=%s" %
                        (run, ",".join(report["packages"]), sum(1 for r in report["inputs"]["lighting"] if r["pop"]), report_path))
            return report
        if mode == "APPLY":
            plan = _json_read(os.path.join(backend.root, PLAN)); report = backend.build_report(params, run)
            if plan["params"] != params: raise Stop("DRY_ARGS_DRIFT|RERUN_DRY")
            if plan["input_digest"] != report["input_digest"]: raise Stop("DRY_STATE_DRIFT|RERUN_DRY")
            record = backend.apply(report, run)
            backend.log("INTERACTION_90B_APPLY_OK|run=%s|saved=%s|backup=%s|record=%s|dirty=0" %
                        (run, ",".join(record["packages"]), record["backup"], os.path.join(backend.root, RECORD)))
            return record
        result = backend.revert(run)
        backend.log("INTERACTION_90B_REVERT_OK|run=%s|saved=%s|backup=%s|record=%s|dirty=0" %
                    (run, ",".join(result["packages"]), result["backup"], result["archived"]))
        return result
    except (Stop, PlanError) as exc:
        backend.fail("INTERACTION_90B_%s_FAILED|run=%s|%s" % (mode, run, exc))
