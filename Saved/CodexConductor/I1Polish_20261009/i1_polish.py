"""Job 90: I1 curtain framing, sleight lighting audit/fix, and P02-entry hold.

Offline-authored.  The conductor runs this through ExecuteProjectPythonFile.
DRY never mutates. APPLY requires the exact DRY plan and makes only the three
explicit parts below. REVERT restores recorded keys/tracks; no asset is deleted.
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

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BASE = _load("job90_i2_polish", os.path.join(PARENT, "I2Polish_20261009", "i2_polish.py"))
TOOL = "I1_POLISH"
VERSION = 1
MAP_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
I1_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy"
CUT_FRAME = 1250
RELEASE_FRAME = 1675
EXPECTED_END = 2183
FPS = 25.0
CONFIRMS = {"DRY": "DRY I1POLISH", "APPLY": "APPLY I1POLISH", "REVERT": "REVERT I1POLISH"}
PLAN = "i1_polish_plan.json"
RECORD = "i1_polish_record.json"
POSE = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")
DEFAULTS = {
    "camera_fit": True,
    "camera_fit_margin": 1.03,
    "curtain_bounds_cm": [1880.0, 1000.0],
    "curtain_bounds_source": "GC_CurtainDrop_Opening final13_opening_a06_w188 hang AABB",
    "current_matched_distance_cm": 1200.0,
    "camera_center_z_adjust_cm": 10.0,
    "f17_fix_steps": [],
    "f18_hold_frame": RELEASE_FRAME,
    "f18_auto_bindings": ["I1 Sleight Mouth Camera", "I1 Sleight Mouth Camera/CameraComponent"],
    "numeric_tolerance": 1.0e-4,
    "stills_frames": [274, 1249, 1250, 1674, 1675, 1701, 2182],
}


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


def enum_token(value):
    """Normalise UE 5.8 enum strings such as '<RichCurve...RCIM_LINEAR: 1>'."""
    text = str(value).strip("<> ")
    text = text.split(":", 1)[0]
    return text.rsplit(".", 1)[-1].upper()


def channel_base(value):
    """UE channel display names may carry numeric/type suffixes."""
    text = str(value).strip()
    for name in POSE:
        if text == name or text.startswith(name + "_") or text.startswith(name + " "):
            return name
    return re.sub(r"(?:_[0-9]+|\s*\([^)]*\))$", "", text)


def merged_params(raw):
    out = dict(DEFAULTS)
    out.update(raw or {})
    out["camera_fit_margin"] = float(out["camera_fit_margin"])
    out["curtain_bounds_cm"] = [float(v) for v in out["curtain_bounds_cm"]]
    out["current_matched_distance_cm"] = float(out["current_matched_distance_cm"])
    out["camera_center_z_adjust_cm"] = float(out["camera_center_z_adjust_cm"])
    out["f18_hold_frame"] = int(out["f18_hold_frame"])
    out["numeric_tolerance"] = float(out["numeric_tolerance"])
    out["stills_frames"] = [int(v) for v in out["stills_frames"]]
    if len(out["curtain_bounds_cm"]) != 2 or min(out["curtain_bounds_cm"]) <= 0:
        raise PlanError("CURTAIN_BOUNDS_INVALID")
    if not 1.0 <= out["camera_fit_margin"] <= 1.25:
        raise PlanError("CAMERA_MARGIN_OUTSIDE_1_TO_1_25")
    if not 0 <= out["f18_hold_frame"] < EXPECTED_END:
        raise PlanError("F18_HOLD_OUTSIDE_PLAYBACK")
    if not isinstance(out["f17_fix_steps"], list) or not isinstance(out["f18_auto_bindings"], list):
        raise PlanError("FIX_AND_BINDING_LISTS_REQUIRED")
    return out


def fit_distance(bounds_cm, focal_mm, filmback_mm, margin):
    width, height = [float(v) for v in bounds_cm]
    fw, fh = [float(v) for v in filmback_mm]
    return max(width * focal_mm / fw, height * focal_mm / fh) * float(margin)


def rotate_z(point, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [point[0] * c - point[1] * s, point[0] * s + point[1] * c, point[2]]


def fitted_camera(camera, current_distance, distance, center_z_adjust=0.0):
    """Pull back in the camera track's own coordinate frame; keep lens/orientation."""
    pull = float(distance) - float(current_distance)
    yaw = math.radians(float(camera["yaw"]))
    delta = [-pull * math.cos(yaw), -pull * math.sin(yaw), float(center_z_adjust)]
    target = [float(camera["loc"][i]) + delta[i] for i in range(3)]
    return {"before": camera, "after": dict(camera, loc=target),
            "delta": [target[i] - float(camera["loc"][i]) for i in range(3)]}


def hold_plan(keys, frame, end, tolerance=1.0e-4):
    return BASE.hold_key_plan(keys, frame, end, tolerance)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _json(path, value=None, required=False, exclusive=False):
    if value is None:
        if not os.path.isfile(path):
            if required:
                raise Stop("MISSING_JSON|%s" % path)
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")


class UnrealBackend(BASE.UnrealBackend):
    def preflight(self, mode, run, confirm):
        if confirm != CONFIRMS[mode]:
            self.fail("%s_FAILED|run=%s|CONFIRM|expected=%s" % (TOOL, run, CONFIRMS[mode]))
        world = self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem).get_editor_world()
        if world is None or str(world.get_path_name()).split(".")[0] != MAP_PATH:
            self.fail("%s_FAILED|run=%s|WORLD|%s" % (TOOL, run, world))
        if self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem).get_game_world() is not None:
            self.fail("%s_FAILED|run=%s|PIE_OR_SIE_RUNNING" % (TOOL, run))
        if self.census() != {"content": [], "maps": []}:
            self.fail("%s_FAILED|run=%s|DIRTY_AT_START|%s" % (TOOL, run, json.dumps(self.census())))

    def _binding(self, seq, name):
        rows = [b for b in seq.get_bindings() if str(b.get_display_name()) == name]
        if len(rows) != 1:
            raise PlanError("BINDING_COUNT|%s|%d" % (name, len(rows)))
        return rows[0]

    def _channel_rows_all(self, seq):
        rows = []
        for binding in seq.get_bindings():
            bname = str(binding.get_display_name())
            for ti, track in enumerate(binding.get_tracks()):
                tclass = track.get_class().get_name()
                prop = ""
                try:
                    prop = str(track.get_property_name())
                except Exception:
                    pass
                for si, section in enumerate(track.get_sections()):
                    for ci, channel in enumerate(section.get_all_channels()):
                        cname = channel_base(channel.channel_name)
                        keys, interp = [], []
                        for key in channel.get_keys():
                            try:
                                value = float(key.get_value())
                            except (TypeError, ValueError):
                                continue
                            keys.append([int(key.get_time().frame_number.value), value])
                            try:
                                interp.append(enum_token(key.get_interpolation_mode()))
                            except Exception:
                                interp.append("UNREADABLE")
                        if not keys:
                            continue
                        ident = "%s|%d|%d|%d|%s" % (BASE._guid(binding.get_id()), ti, si, ci, cname)
                        rows.append({"id": ident, "binding_guid": BASE._guid(binding.get_id()), "binding": bname,
                                     "track_index": ti, "section_index": si, "channel_index": ci,
                                     "track_class": tclass, "property": prop, "channel": cname,
                                     "raw_channel": str(channel.channel_name), "keys": sorted(keys),
                                     "interpolation": sorted(set(interp)), "sequence": I1_PATH})
        return rows

    def _pose(self, seq, name, frame):
        binding = self._binding(seq, name)
        tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
        if len(tracks) != 1:
            raise PlanError("TRANSFORM_TRACK_COUNT|%s|%d" % (name, len(tracks)))
        values = {}
        for channel in list(tracks[0].get_sections())[0].get_all_channels():
            base = channel_base(channel.channel_name)
            if base not in POSE:
                continue
            got = list(channel.evaluate_keys(seq.make_range(int(frame), 1), seq.get_display_rate()))
            if len(got) != 1:
                raise PlanError("EVALUATE_COUNT|%s|%s|%d" % (name, base, len(got)))
            values[base] = float(got[0])
        return {"loc": [values.get("Location.X", 0.0), values.get("Location.Y", 0.0), values.get("Location.Z", 0.0)],
                "roll": values.get("Rotation.X", 0.0), "pitch": values.get("Rotation.Y", 0.0),
                "yaw": values.get("Rotation.Z", 0.0)}

    def _filmback_focal(self, seq, camera_name):
        self._binding(seq, camera_name)  # exact Sequencer identity first
        actors = [a for a in self._actors() if str(a.get_actor_label()) == camera_name]
        if len(actors) != 1:
            raise PlanError("CAMERA_ACTOR_COUNT|%s|%d" % (camera_name, len(actors)))
        camera = actors[0].get_component_by_class(self.u.CineCameraComponent)
        if camera is None:
            raise PlanError("CINE_CAMERA_COMPONENT_MISSING|%s" % camera_name)
        film = camera.get_editor_property("filmback")
        return [float(film.sensor_width), float(film.sensor_height)], float(camera.get_editor_property("current_focal_length"))

    def _camera_fit_report(self, seq, params):
        film, focal = self._filmback_focal(seq, "I1 Sleight Mouth Camera")
        distance = fit_distance(params["curtain_bounds_cm"], focal, film, params["camera_fit_margin"])
        sides = []
        for camera_name, drape_name, frame in (
                ("S1 Sleight Hangar Camera", "Sleight Hangar Drape", CUT_FRAME - 1),
                ("I1 Sleight Mouth Camera", "Transition Drape (baked)", CUT_FRAME)):
            camera = self._pose(seq, camera_name, frame)
            fit = fitted_camera(camera, params["current_matched_distance_cm"], distance,
                                params["camera_center_z_adjust_cm"])
            fit.update({"camera": camera_name, "drape": drape_name, "frame": frame})
            sides.append(fit)
        match = max(abs(sides[0]["after"]["loc"][i] - sides[1]["after"]["loc"][i]) for i in range(3))
        return {"enabled": bool(params["camera_fit"]), "focal_mm": focal, "filmback_mm": film,
                "bounds_cm": params["curtain_bounds_cm"], "bounds_source": params["curtain_bounds_source"],
                "margin": params["camera_fit_margin"], "distance_cm": distance, "sides": sides,
                "current_matched_distance_cm": params["current_matched_distance_cm"],
                "camera_center_z_adjust_cm": params["camera_center_z_adjust_cm"],
                "world_position_delta_is_not_match_metric": match,
                "note": "Both cameras retain focal/orientation and get the same curtain-local fit."}

    def _lighting_report(self, seq):
        order = _load("job90_i2_order", os.path.join(PARENT, "I2Order_20261008", "i2_order.py"))
        order.NAMES.update({"hangar_cam": "S1 Sleight Hangar Camera", "mouth_cam": "I1 Sleight Mouth Camera",
                            "drape": "Sleight Hangar Drape", "mouth_drape": "Transition Drape (baked)",
                            "root": "S1 Hangar Root"})
        order.CAMERAS = (order.NAMES["hangar_cam"], order.NAMES["mouth_cam"])
        order.DRAPE_OF_CAMERA = {order.NAMES["hangar_cam"]: order.NAMES["drape"],
                                 order.NAMES["mouth_cam"]: order.NAMES["mouth_drape"]}
        snap, actors = order._snapshot(seq), order._actors()
        names = {b["guid"]: b["name"] for b in snap["bindings"]}
        before_name, _ = order.live_camera_at(snap["cuts"], CUT_FRAME - 1, names)
        after_name, _ = order.live_camera_at(snap["cuts"], CUT_FRAME, names)
        if (before_name, after_name) != order.CAMERAS:
            raise PlanError("F17_CUT_CAMERAS|%s|%s" % (before_name, after_name))
        by_label = {}
        for actor in actors:
            by_label.setdefault(str(actor.get_actor_label()), []).append(actor)

        def side(camera_name, drape_name, frame):
            pose, drape = self._pose(seq, camera_name, frame), self._binding(seq, drape_name)
            root = drape.get_object_template().get_editor_property("root_component")
            loc, rot = root.get_editor_property("relative_location"), root.get_editor_property("relative_rotation")
            point, normal = [float(loc.x), float(loc.y), float(loc.z)], order.rot_z([-1.0, 0.0, 0.0], float(rot.yaw))
            lights = order._light_rows(actors, snap, frame) + order._spawned_spot_rows(snap, frame)
            lights = [r for r in lights if r["kind"] == "directional" or not r.get("radius") or math.dist(r["loc"], point) < float(r["radius"])]
            volumes = order._ppv_rows(actors, pose["loc"])
            cameras = by_label.get(camera_name, [])
            if len(cameras) != 1:
                raise PlanError("F17_CAMERA_ACTOR_COUNT|%s|%d" % (camera_name, len(cameras)))
            exposure = order.effective_exposure(volumes, order._camera_pp(cameras[0]))
            return {"camera": camera_name, "frame": frame, "pose": pose, "point": point,
                    "light": order.side_summary(lights, point, normal), "exposure": exposure,
                    "fog": order._fog_rows(actors, pose["loc"], point)}

        before = side(before_name, order.NAMES["drape"], CUT_FRAME - 1)
        after = side(after_name, order.NAMES["mouth_drape"], CUT_FRAME)
        spots = {}
        for label in (order.NAMES["spot_hangar"], order.NAMES["spot_mouth"]):
            b = [r for r in order._spawned_spot_rows(snap, CUT_FRAME - 1) if r["label"] == label]
            a = [r for r in order._spawned_spot_rows(snap, CUT_FRAME) if r["label"] == label]
            spots[label] = (b[0]["intensity"], a[0]["intensity"]) if len(b) == 1 and len(a) == 1 else (None, None)
        ranked = order.rank_cut(before, after, CUT_FRAME, self._rate(seq), spots, before["fog"], after["fog"])
        return {"frame": CUT_FRAME, "seconds": CUT_FRAME / self._rate(seq), "before": before, "after": after,
                "ranked": ranked, "proposals": order.proposals_for_cut(ranked, before, after, CUT_FRAME, RELEASE_FRAME, EXPECTED_END),
                "shared_math": "Saved/CodexConductor/I2Order_20261008/i2_order.py"}

    def build_report(self, params, run):
        seq = self.u.load_asset(I1_PATH)
        if seq is None:
            self.fail("LOAD_I1")
        playback = [int(seq.get_playback_start()), int(seq.get_playback_end())]
        common = [] if playback == [0, EXPECTED_END] else ["I1_PLAYBACK_DRIFT|%s|expected=[0,%d]" % (playback, EXPECTED_END)]
        rows = self._channel_rows_all(seq)
        window = [params["f18_hold_frame"], playback[1]]
        moving = BASE.movement_inventory(rows, window[0], window[1], params["numeric_tolerance"])
        selected = []
        f18_refusals = []
        for row in rows:
            if row["binding"] not in params["f18_auto_bindings"]:
                continue
            hp = hold_plan(row["keys"], window[0], window[1], params["numeric_tolerance"])
            if hp["changed"]:
                modes = set(row["interpolation"])
                if modes - {"LINEAR", "RCIM_LINEAR"}:
                    f18_refusals.append("F18_NONLINEAR_TARGET|%s|%s" % (row["id"], sorted(modes)))
                copy = dict(row)
                copy["hold_plan"] = hp
                selected.append(copy)
        fit_refusals = []
        if params["camera_fit"]:
            for camera_name in ("S1 Sleight Hangar Camera", "I1 Sleight Mouth Camera"):
                for axis in ("Location.X", "Location.Y", "Location.Z"):
                    hits = [r for r in rows if r["binding"] == camera_name and r["channel"] == axis]
                    if len(hits) != 1:
                        fit_refusals.append("FIT_CHANNEL_COUNT|%s|%s|%d" % (camera_name, axis, len(hits)))
                    elif set(hits[0]["interpolation"]) - {"LINEAR", "RCIM_LINEAR"}:
                        fit_refusals.append("FIT_NONLINEAR_CHANNEL|%s|%s|%s" %
                                            (camera_name, axis, hits[0]["interpolation"]))
        fit = self._camera_fit_report(seq, params)
        try:
            lighting = self._lighting_report(seq)
        except Exception as exc:
            lighting = {"status": "UNCLEAR", "error": "%s: %s" % (type(exc).__name__, exc),
                        "searched": "I1 cameras, curtain points, lights, spot keys, PPV/camera exposure and fog at f1249/f1250"}
        fixes = BASE.validate_fix_steps(params["f17_fix_steps"], playback[1])
        refusals = list(common)
        refusals += fit_refusals
        refusals += f18_refusals
        if params["f17_fix_steps"] and lighting.get("status") == "UNCLEAR":
            refusals.append("F17_AUDIT_UNAVAILABLE|%s" % lighting["error"])
        if not params["camera_fit"] and not fixes and not selected:
            refusals.append("NO_ENABLED_PARTS")
        guarded = {"params": params, "playback": playback, "fit": fit if params["camera_fit"] else None,
                   "fixes": fixes, "selected": [{"id": r["id"], "before": r["hold_plan"]["before"],
                                                   "after": r["hold_plan"]["after"]} for r in selected]}
        return {"schema_version": 1, "tool_version": VERSION, "run": run, "params": params,
                "apply_ready": not refusals, "refusals": refusals, "playback": playback, "camera_fit": fit,
                "f17": lighting, "f17_fix_steps": fixes,
                "f18": {"window": window, "inventory": moving, "selected": selected,
                         "searched_bindings": params["f18_auto_bindings"], "refusals": f18_refusals},
                "stills_plan": [{"frame": f, "seconds": round(f / FPS, 2), "purpose": "before/after framing, cut, release and P02 handover"}
                                for f in params["stills_frames"]],
                "exact_census": self.census(), "input_digest": digest(guarded), "digest_inputs": guarded,
                "proof": {"tier": "measured", "scope": "live editor DRY/read-back only; stills are a plan, not rendered acceptance"}}

    def _locate(self, seq, row):
        bindings = [b for b in seq.get_bindings() if BASE._guid(b.get_id()) == row["binding_guid"]]
        if len(bindings) != 1:
            raise Stop("BINDING_DRIFT|%s" % row["id"])
        track = list(bindings[0].get_tracks())[row["track_index"]]
        section = list(track.get_sections())[row["section_index"]]
        channel = list(section.get_all_channels())[row["channel_index"]]
        if channel_base(channel.channel_name) != row["channel"]:
            raise Stop("CHANNEL_DRIFT|%s|%s" % (row["id"], channel.channel_name))
        return channel

    def _keys(self, channel):
        return sorted([[int(k.get_time().frame_number.value), float(k.get_value())] for k in channel.get_keys()])

    def _rewrite(self, channel, keys):
        for key in list(channel.get_keys()):
            channel.remove_key(key)
        for frame, value in keys:
            channel.add_key(self.u.FrameNumber(int(frame)), float(value), time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=self.u.MovieSceneKeyInterpolation.LINEAR)

    def _fit_rows(self, seq, report):
        rows = self._channel_rows_all(seq)
        out = []
        for side in report["camera_fit"]["sides"]:
            for axis, delta in zip(("Location.X", "Location.Y", "Location.Z"), side["delta"]):
                hits = [r for r in rows if r["binding"] == side["camera"] and r["channel"] == axis]
                if len(hits) != 1:
                    raise Stop("FIT_CHANNEL_COUNT|%s|%s|%d" % (side["camera"], axis, len(hits)))
                row = dict(hits[0])
                # F18 will remove the mouth route; translate its remaining held pose. Hangar is already held after push-in.
                start = 275 if side["camera"].startswith("S1 ") else 0
                before = row["keys"]
                after = [[f, v + delta if f >= start else v] for f, v in before]
                row.update({"before": before, "after": after, "fit_start": start, "delta": delta})
                out.append(row)
        return out

    def _asset_file(self):
        root = self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_content_dir())
        return os.path.join(root, *I1_PATH[len("/Game/"):].split("/")) + ".uasset"

    def _backup(self, run, suffix=""):
        project = self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_dir())
        folder = os.path.join(project, "Backups", "PreI1Polish%s-%s" % (suffix, run))
        os.makedirs(folder)
        src, dst = self._asset_file(), os.path.join(folder, os.path.basename(self._asset_file()))
        shutil.copy2(src, dst)
        return folder, {"package": I1_PATH, "source": src, "backup": dst,
                        "sha256": hashlib.sha256(open(dst, "rb").read()).hexdigest()}

    def _readback(self, seq, record, applied):
        checks = []
        fitted_ids = {row["id"] for row in record["camera_fit"]}
        for group in ("camera_fit", "f18"):
            for row in record[group]:
                if applied and group == "f18" and row["id"] in fitted_ids:
                    # The later fit adds a constant to the already-held channel;
                    # the camera_fit record below is the authoritative final check.
                    continue
                got = self._keys(self._locate(seq, row))
                want = row["after"] if applied else row["before"]
                if not BASE.UnrealBackend._keys_match(self, got, want, 1.0e-4):
                    raise Stop("READBACK_%s|%s" % (group.upper(), row["id"]))
                checks.append("%s:%s=%dkeys" % (group, row["id"], len(got)))
        for row in record["f17"]:
            bindings = [b for b in seq.get_bindings() if BASE._guid(b.get_id()) == row["binding_guid"]]
            if applied:
                if len(bindings) != 1:
                    raise Stop("READBACK_F17_BINDING|%s" % row["step"]["id"])
                tracks = list(bindings[0].get_tracks())
                if row["track_index"] >= len(tracks) or tracks[row["track_index"]].get_class().get_name() != row["track_class"]:
                    raise Stop("READBACK_F17_TRACK|%s" % row["step"]["id"])
                got = self._keys(list(tracks[row["track_index"]].get_sections())[0].get_all_channels()[0])
                if not BASE.UnrealBackend._keys_match(self, got, row["step"]["keys"], 1.0e-4):
                    raise Stop("READBACK_F17_KEYS|%s|%s" % (row["step"]["id"], got))
                checks.append("f17:%s=%dkeys" % (row["step"]["id"], len(got)))
            elif row["binding_guid"] not in row["created_bindings"] and len(bindings) == 1:
                if len(list(bindings[0].get_tracks())) != row["track_count_before"]:
                    raise Stop("READBACK_F17_REVERT|%s" % row["step"]["id"])
            elif row["binding_guid"] in row["created_bindings"] and bindings:
                raise Stop("READBACK_F17_CREATED_BINDING_REMAINS|%s" % row["step"]["id"])
        return checks

    def apply(self, report, run):
        backup, copied = self._backup(run)
        path = os.path.join(self.root, RECORD)
        if os.path.exists(path):
            raise Stop("RECORD_EXISTS|REVERT_FIRST")
        seq = self.u.load_asset(I1_PATH)
        record = {"run": run, "applied": False, "backup": backup, "backup_file": copied, "package": I1_PATH,
                  "input_digest": report["input_digest"], "camera_fit": [], "f18": [], "f17": []}
        _json(path, record, exclusive=True)
        seq.modify()
        # Hold first, then calculate/apply the fit against the same locators; fit rows see pre-hold state but only add a constant.
        for row in report["f18"]["selected"]:
            channel = self._locate(seq, row)
            before, after = self._keys(channel), row["hold_plan"]["after"]
            self._rewrite(channel, after)
            record["f18"].append(dict(row, before=before, after=after))
        if report["params"]["camera_fit"]:
            for row in self._fit_rows(seq, report):
                channel = self._locate(seq, row)
                self._rewrite(channel, row["after"])
                record["camera_fit"].append(row)
        BASE.EXPECTED_I2_END = EXPECTED_END
        for step in report["f17_fix_steps"]:
            record["f17"].append(self._new_fix_track(seq, step))
        if self.census() != {"content": [I1_PATH], "maps": []}:
            raise Stop("DIRTY_SCOPE|expected=%s|actual=%s|NOTHING_SAVED" % (I1_PATH, json.dumps(self.census())))
        if not self.u.EditorAssetLibrary.save_asset(I1_PATH, only_if_is_dirty=True):
            raise Stop("SAVE_FAILED|%s" % I1_PATH)
        if self.census() != {"content": [], "maps": []}:
            raise Stop("DIRTY_AFTER_SAVE|%s" % json.dumps(self.census()))
        record["readback"] = self._readback(seq, record, True)
        record["applied"], record["report"] = True, report
        _json(path, record)
        return record

    def revert(self, run):
        path = os.path.join(self.root, RECORD)
        record = _json(path, required=True)
        if not record.get("applied"):
            raise Stop("RECORD_NOT_APPLIED")
        backup, copied = self._backup(run, "Revert")
        seq = self.u.load_asset(I1_PATH)
        seq.modify()
        # Fit was applied after hold, therefore restore fit first, then the original pre-hold channels.
        for row in record["camera_fit"]:
            self._rewrite(self._locate(seq, row), row["before"])
        for row in record["f18"]:
            self._rewrite(self._locate(seq, row), row["before"])
        for row in reversed(record["f17"]):
            bindings = [b for b in seq.get_bindings() if BASE._guid(b.get_id()) == row["binding_guid"]]
            if len(bindings) != 1:
                raise Stop("REVERT_F17_BINDING_DRIFT|%s" % row["step"]["id"])
            tracks = list(bindings[0].get_tracks())
            if len(tracks) != row["track_count_before"] + 1:
                raise Stop("REVERT_F17_OTHER_TRACK_DRIFT|%s" % row["step"]["id"])
            got = self._keys(list(tracks[row["track_index"]].get_sections())[0].get_all_channels()[0])
            if not BASE.UnrealBackend._keys_match(self, got, row["step"]["keys"], 1.0e-4):
                raise Stop("REVERT_F17_KEYS_DRIFT|%s|%s" % (row["step"]["id"], got))
            bindings[0].remove_track(tracks[row["track_index"]])
            for guid in reversed(row["created_bindings"]):
                made = [b for b in seq.get_bindings() if BASE._guid(b.get_id()) == guid]
                if len(made) == 1:
                    made[0].remove()
        if self.census() != {"content": [I1_PATH], "maps": []}:
            raise Stop("REVERT_DIRTY_SCOPE|%s" % json.dumps(self.census()))
        if not self.u.EditorAssetLibrary.save_asset(I1_PATH, only_if_is_dirty=True):
            raise Stop("REVERT_SAVE_FAILED")
        if self.census() != {"content": [], "maps": []}:
            raise Stop("REVERT_DIRTY_AFTER_SAVE")
        readback = self._readback(seq, record, False)
        archived = path + ".reverted-" + run
        os.rename(path, archived)
        return {"backup": backup, "backup_file": copied, "archived_record": archived, "readback": readback}


def _run_id():
    return "I1POLISH-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def main(args, backend=None, tool_root=None):
    mode, run = str(args.get("mode", "DRY")).upper(), str(args.get("run_id") or _run_id())
    backend = backend or UnrealBackend(tool_root=tool_root or HERE)
    if mode not in CONFIRMS:
        backend.fail("I1_POLISH_FAILED|run=%s|MODE|%s" % (run, mode))
    try:
        params = merged_params(args.get("params") or {})
        backend.preflight(mode, run, args.get("confirm"))
        if mode == "DRY":
            report = backend.build_report(params, run)
            report_path = os.path.join(backend.root, "i1_polish_dry_%s.json" % run)
            _json(report_path, report)
            _json(os.path.join(backend.root, PLAN), {"run": run, "params": params,
                                                      "input_digest": report["input_digest"], "report": report_path})
            if backend.census() != {"content": [], "maps": []}:
                raise Stop("DRY_DIRTIED|%s" % json.dumps(backend.census()))
            backend.log("I1_POLISH_DRY_OK|run=%s|mutated=0|apply_ready=%d|fit_cm=%.2f|f17=%s|f18_candidates=%d|f18_selected=%d|census=0/0|report=%s" %
                        (run, int(report["apply_ready"]), report["camera_fit"]["distance_cm"], report["f17"].get("status", "OK"),
                         len(report["f18"]["inventory"]), len(report["f18"]["selected"]), report_path))
            return report
        if mode == "APPLY":
            plan = _json(os.path.join(backend.root, PLAN), required=True)
            report = backend.build_report(params, run)
            if not report["apply_ready"]:
                raise Stop("APPLY_NOT_READY|%s" % json.dumps(report["refusals"]))
            if plan["params"] != params:
                raise Stop("DRY_ARGS_DRIFT|RERUN_DRY")
            if plan["input_digest"] != report["input_digest"]:
                raise Stop("DRY_STATE_DRIFT|RERUN_DRY")
            record = backend.apply(report, run)
            backend.log("I1_POLISH_APPLY_OK|run=%s|camera=%d|f17=%d|f18=%d|saved=%s|backup=%s|record=%s|dirty=0" %
                        (run, len(record["camera_fit"]), len(record["f17"]), len(record["f18"]), I1_PATH,
                         record["backup"], os.path.join(backend.root, RECORD)))
            return record
        result = backend.revert(run)
        backend.log("I1_POLISH_REVERT_OK|run=%s|saved=%s|backup=%s|record=%s|dirty=0" %
                    (run, I1_PATH, result["backup"], result["archived_record"]))
        return result
    except (PlanError, Stop, BASE.PlanError, BASE.Stop) as exc:
        backend.fail("I1_POLISH_%s_FAILED|run=%s|%s" % (mode, run, exc))
