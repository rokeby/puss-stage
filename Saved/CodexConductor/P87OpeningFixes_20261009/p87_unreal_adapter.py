"""UE 5.8 adapter for P87.  Imported only by the project-Python run wrapper.

This composes, rather than duplicates, the proven P13 Geometry Cache / Show
attachment binding helpers.  It never opens Sequencer and saves named packages
only.  The offline harness does not import this file.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import shutil

import unreal

import p87_opening_common as C


SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LEVEL = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OPENING = "Opening — Curtain"
P01_PASSAGE = "Passage 1"
CAMERA = "Opening — Stalls Camera"
P87_TRACK = "P87 Opening Camera"
P87_PREFIX = "P87 Stage Front Uplight "


def _load_p13_helpers():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "opening_lighting_p13.py")
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            keep.append(node)
        elif isinstance(node, ast.Assign):
            keep.append(node)
    scope = {"__file__": path, "__name__": "p87_p13_helpers", "unreal": unreal}
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), scope)
    return scope


P13 = _load_p13_helpers()


def _guid(value):
    # FGuid str may change formatting per call: keep hex only and compare normalized.
    return "".join(ch for ch in str(value).upper() if ch in "0123456789ABCDEF")


def _enum_name(value):
    text = str(value).upper()
    for sep in ("::", "."):
        if sep in text:
            text = text.rsplit(sep, 1)[-1]
    return text.split(":", 1)[0].strip(" <>0123456789")


def _dirty():
    return {"content": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _package_file(package):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    base = os.path.join(root, package[len("/Game/"):].replace("/", os.sep))
    for ext in (".uasset", ".umap"):
        if os.path.isfile(base + ext):
            return base + ext
    raise C.P87Error("PACKAGE_FILE|" + package)


def _channels(section):
    return {str(ch.channel_name).split(".")[-2] + "." + str(ch.channel_name).split(".")[-1]
            if str(ch.channel_name).count(".") >= 1 else str(ch.channel_name): ch
            for ch in section.get_all_channels()}


def _channel_snapshot(ch):
    default = ch.get_default()
    return {"name": str(ch.channel_name), "default": None if default is None else float(default),
            "keys": [[int(k.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value), float(k.get_value())]
                     for k in ch.get_keys()]}


def _track_snapshot(track):
    return {"class": track.get_class().get_name(), "display": str(track.get_display_name()),
            "property": str(track.get_property_name()) if hasattr(track, "get_property_name") else None,
            "sections": [{"range": [s.get_start_frame(), s.get_end_frame()],
                          "channels": [_channel_snapshot(c) for c in s.get_all_channels()]}
                         for s in track.get_sections()]}


def _value_at(channel, frame):
    keys = sorted(channel.get_keys(), key=lambda k: k.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value)
    chosen = None
    for key in keys:
        if key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value <= frame:
            chosen = float(key.get_value())
    if chosen is not None:
        return chosen
    default = channel.get_default()
    if default is None:
        raise C.P87Error("CHANNEL_NO_VALUE|" + str(channel.channel_name))
    return float(default)


class P87UnrealBackend:
    def __init__(self):
        self.saved = False
        self._resolve()

    def _resolve(self):
        self.show = unreal.load_asset(SHOW)
        if self.show is None:
            raise C.P87Error("SHOW_LOAD")
        cues = list(self.show.get_editor_property("cues"))
        opening = [c for c in cues if str(c.get_editor_property("label")) == OPENING]
        if len(opening) != 1:
            raise C.P87Error("OPENING_CUE_COUNT|%d" % len(opening))
        self.sequence = opening[0].get_editor_property("scene").get_editor_property("sequence")
        if self.sequence is None:
            raise C.P87Error("OPENING_SEQUENCE_NULL")
        self.sequence_path = self.sequence.get_path_name().split(".")[0]
        self.cues = cues
        # "Passage 1" is a PassageSettings label, not a live cue label.  Live
        # P01 cues are the individual wing-pair rows (for example P01 Wing
        # 001).  Resolve the owning PassageSettings row, then select its
        # engine-minted first cue GUID.  Keep the uniqueness guard on both
        # hops; only the selector was wrong in the pass-1 tool.
        passages = [p for p in self.show.get_editor_property("passages")
                    if str(p.get_editor_property("label")) == P01_PASSAGE]
        if len(passages) != 1:
            raise C.P87Error("P01_PASSAGE_COUNT|%d" % len(passages))
        first_guid = _guid(passages[0].get_editor_property("first_cue_guid"))
        p01 = [(i, c) for i, c in enumerate(cues)
               if _guid(c.get_editor_property("cue_guid")) == first_guid]
        if len(p01) != 1:
            raise C.P87Error("P01_FIRST_CUE_COUNT|%d" % len(p01))
        self.p01_index, self.p01 = p01[0]

    def context(self):
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        path = world.get_path_name().split(".")[0] if world else ""
        return {"pie": unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None,
                "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
                "world": path, "dirty": _dirty()}

    def _camera_bindings(self):
        rows = [b for b in self.sequence.get_bindings() if str(b.get_display_name()) == CAMERA]
        if len(rows) != 1:
            raise C.P87Error("CAMERA_BINDING_COUNT|%d" % len(rows))
        actor = rows[0]
        transforms = [t for t in actor.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
        if len(transforms) != 1:
            raise C.P87Error("CAMERA_TRANSFORM_TRACK_COUNT|%d" % len(transforms))
        focal = []
        for b in self.sequence.get_bindings():
            for t in b.get_tracks():
                if t.get_class().get_name() == "MovieSceneFloatTrack" and str(t.get_property_name()) == "CurrentFocalLength":
                    focal.append((b, t))
        if len(focal) != 1:
            raise C.P87Error("CAMERA_FOCAL_TRACK_COUNT|%d" % len(focal))
        return actor, transforms[0], focal[0][0], focal[0][1]

    def _camera_state(self):
        actor, transform, focal_binding, focal = self._camera_bindings()
        return {"actor_binding_guid": _guid(actor.get_id()), "focal_binding_guid": _guid(focal_binding.get_id()),
                "transform": _track_snapshot(transform), "focal": _track_snapshot(focal)}

    def _camera_end(self):
        unused, transform, unused2, focal = self._camera_bindings()
        ts = list(transform.get_sections())
        fs = list(focal.get_sections())
        if len(ts) != 1 or len(fs) != 1:
            raise C.P87Error("CAMERA_SECTION_COUNT")
        ch = {str(c.channel_name): c for c in ts[0].get_all_channels()}
        def get(suffix):
            hits = [v for k, v in ch.items() if k.endswith(suffix)]
            if len(hits) != 1: raise C.P87Error("CAMERA_CHANNEL|" + suffix)
            return _value_at(hits[0], 2409)
        fch = list(fs[0].get_all_channels())
        if len(fch) != 1: raise C.P87Error("FOCAL_CHANNEL_COUNT")
        return {"location": [get("Location.X"), get("Location.Y"), get("Location.Z")],
                "rotation": [get("Rotation.Y"), get("Rotation.Z"), get("Rotation.X")],
                "focal_mm": _value_at(fch[0], 2409), "focus_cm": 600.0}

    def _curtain_state(self):
        unused, secs, asset = P13["_gc"](self.sequence)
        return {"asset": asset, "sections": P13["_gc_state"](secs)}

    def _pair_rows(self):
        return P13["_pair_attachments"](self.p01)

    def _bulbs(self):
        rows = []
        for a in self._pair_rows():
            label = str(a.get_editor_property("label"))
            if "BULB" not in label.upper():
                continue
            xf = a.get_editor_property("relative_transform")
            loc = xf.translation
            rows.append({"id": _guid(a.get_editor_property("attachment_guid")), "label": label,
                         "wing_location": [float(loc.x), float(loc.y), float(loc.z)],
                         "floor_z_cm": float(loc.z), "side_sign": -1 if loc.y < 0 else 1})
        if not rows:
            raise C.P87Error("P01_BULBS_NOT_FOUND")
        return rows

    def _bulb_state(self):
        out = []
        for a in self._pair_rows():
            label = str(a.get_editor_property("label"))
            if "BULB" not in label.upper(): continue
            xf = a.get_editor_property("relative_transform"); r = xf.rotation.rotator(); l = xf.translation
            out.append({"id": _guid(a.get_editor_property("attachment_guid")), "label": label,
                        "location": [l.x, l.y, l.z], "rotation": [r.pitch, r.yaw, r.roll]})
        return sorted(out, key=lambda v: v["id"])

    def _uplight_state(self):
        return sorted([{"id": _guid(a.get_editor_property("attachment_guid")),
                        "label": str(a.get_editor_property("label"))}
                       for a in self._pair_rows() if str(a.get_editor_property("label")).startswith(P87_PREFIX)],
                      key=lambda v: v["id"])

    def _clock(self):
        markers = [{"label": str(m.label), "frame": int(m.frame_number.value)}
                   for m in unreal.MovieSceneSequenceExtensions.get_marked_frames(self.sequence)]
        flurries = [m for m in markers if "FLURRY" in m["label"].upper()]
        return {"status": "RESOLVED" if flurries else "UNRESOLVED", "gary_note": "00:37:50",
                "opening_fps": 25.0, "opening_frames": [self.sequence.get_playback_start(), self.sequence.get_playback_end()],
                "opening_flurry_markers": flurries,
                "master_section": "live Master offset must be reported by conductor; no Master mutation"}

    def snapshot(self, parts):
        live = {"show_path": SHOW, "level_path": LEVEL, "sequence_path": self.sequence_path,
                "clock": self._clock(), "camera_end_pose": self._camera_end(),
                "curtain_sections": [{"role": role, "start": row[0], "end": row[1]}
                                     for role, row in zip(("HOLD", "FALL", "PILE_HOLD"), self._curtain_state()["sections"])],
                "bulbs": self._bulbs()}
        return {"live": live, "owned": self.owned_state(parts), "packages": [SHOW, self.sequence_path, LEVEL]}

    def owned_state(self, parts):
        out = {}
        if "CURTAIN" in parts: out["curtain"] = self._curtain_state()
        if "CAMERA" in parts: out["camera"] = self._camera_state()
        if "UPLIGHTS" in parts: out["uplights"] = self._uplight_state()
        if "BULBS" in parts: out["bulbs"] = self._bulb_state()
        return out

    def foreign_records(self, parts):
        roots = [os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), n)
                 for n in os.listdir(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
                 if n.startswith("Codex")]
        own = os.path.normcase(os.path.join(os.path.dirname(__file__), "p87_opening_record.json"))
        hits = []
        for root in roots:
            for base, unused, files in os.walk(root):
                for name in files:
                    path = os.path.join(base, name)
                    if name.lower().endswith("record.json") and os.path.normcase(path) != own:
                        try: text = open(path, encoding="utf-8").read()
                        except Exception: continue
                        if any(word in text for word in ("LS_Opening_Curtain_Baked", "P01 Wing", "BULB")):
                            hits.append(path)
        return sorted(set(hits))

    def previews(self, plan, run_id):
        # Offline PNGs are generated by p87_preview.py; live DRY records the expected paths only.
        root = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                            "DerivedAssets", "P87OpeningFixes")
        return {"timeline": os.path.join(root, "p87_timeline.png"),
                "stage_front": os.path.join(root, "p87_stage_front.png"),
                "stills_plan": ["wide hold before first flurry", "curtain mid-fall", "uplights established",
                                "final P01 end pose", "floor-bulb top and grazing views"]}

    def backup(self, label, packages):
        root = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Backups", label)
        os.makedirs(root, exist_ok=False)
        rows = []
        for package in packages:
            src = _package_file(package)
            dst = os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(src)[1])
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)
            a = hashlib.sha256(open(src, "rb").read()).hexdigest(); b = hashlib.sha256(open(dst, "rb").read()).hexdigest()
            if a != b: raise C.P87Error("BACKUP_HASH|" + package)
            rows.append({"package": package, "source": src, "backup": dst, "sha256": a})
        return {"folder": root, "packages": rows, "hash_verified": True}

    def _write_track(self, track, channels_by_suffix, end=2409):
        secs = list(track.get_sections())
        if len(secs) != 1: raise C.P87Error("TRACK_SECTION_COUNT|" + str(track.get_display_name()))
        sec = secs[0]; sec.set_range(0, end + 1)
        for channel in sec.get_all_channels():
            suffix = next((s for s in channels_by_suffix if str(channel.channel_name).endswith(s)), None)
            if suffix is None: continue
            for key in list(channel.get_keys()): channel.remove_key(key)
            for frame, value in channels_by_suffix[suffix]:
                channel.add_key(unreal.FrameNumber(int(frame)), float(value),
                                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=unreal.MovieSceneKeyInterpolation.AUTO)

    def _apply_camera(self, plan):
        unused, transform, unused2, focal = self._camera_bindings()
        keys = plan["keys"]
        series = {"Location.X": [], "Location.Y": [], "Location.Z": [],
                  "Rotation.X": [], "Rotation.Y": [], "Rotation.Z": []}
        for row in keys:
            f = row["frame"]
            for name, value in zip(("Location.X", "Location.Y", "Location.Z"), row["location"]): series[name].append([f, value])
            pitch, yaw, roll = row["rotation"]
            for name, value in zip(("Rotation.X", "Rotation.Y", "Rotation.Z"), (roll, pitch, yaw)): series[name].append([f, value])
        self._write_track(transform, series)
        self._write_track(focal, {"CurrentFocalLength": [[r["frame"], r["focal_mm"]] for r in keys]})

    def _apply_curtain(self, plan):
        unused, secs, unused2 = P13["_gc"](self.sequence)
        rows = []
        for role in plan["sections"]:
            end_off = 0 if role["role"] != "HOLD" else 240000
            rows.append([role["start"], role["end"], role["start_offset_ticks"], end_off])
        P13["_set_gc"](secs, rows)

    def _apply_uplights(self, plan):
        if self._uplight_state(): raise C.P87Error("UPLIGHTS_ALREADY_EXIST")
        fixtures = []
        for row in plan["rows"]:
            pitch, yaw, roll = row["rotation"]
            fixtures.append({"label": row["label"], "relative_location_cm": row["location"],
                             "start_rotation_rpy_deg": [roll, pitch, yaw], "rotation_keys": [],
                             "intensity_keys": row["intensity_keys"], "intensity_cd": row["lumens"],
                             "inner_cone_deg": row["inner_cone_deg"], "outer_cone_deg": row["outer_cone_deg"],
                             "falloff_exponent": 12.0, "source_radius_cm": 2.0, "soft_source_radius_cm": 6.0,
                             "temperature_kelvin": row["kelvin"], "color_rgb_linear": [1.0, .78, .54],
                             "attenuation_cm": row["attenuation_cm"], "volumetric_scattering": .3,
                             "cast_shadows": False, "cast_volumetric_shadows": False})
        P13["_mint"](self.show, self.p01_index, {"fixtures": fixtures}, "P87")
        passage = [a for a in _actors() if a.get_class().get_name() == "InfinityStagePassageActor"
                   and a.get_editor_property("show_asset") == self.show and str(a.get_actor_label()).startswith("Passage 01")]
        if len(passage) != 1 or not bool(passage[0].materialize_passage()): raise C.P87Error("P01_MATERIALIZE")

    def _apply_bulbs(self, plan):
        by_id = {r["id"]: r for r in plan["rows"]}; rows = self._pair_rows(); seen = set()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        cat = unreal.SystemLibrary.convert_to_trace_type(unreal.CollisionChannel.ECC_CAT_FLOOR)
        for a in rows:
            gid = _guid(a.get_editor_property("attachment_guid"))
            if gid not in by_id: continue
            want = by_id[gid]; x, y = want["location_xy_proposal"]
            start = unreal.Vector(x, y, want["trace"]["start_z"]); end = unreal.Vector(x, y, want["trace"]["end_z"])
            result = unreal.SystemLibrary.line_trace_single(world, start, end, cat, False, [], unreal.DrawDebugTrace.NONE, True)
            hit = result[1] if isinstance(result, tuple) and result[0] else None
            if hit is None: raise C.P87Error("BULB_FLOOR_TRACE|" + gid)
            fields = hit.to_tuple(); point = fields[5]
            xf = a.get_editor_property("relative_transform"); xf.set_editor_property("translation", unreal.Vector(x, y, point.z))
            pitch, yaw, roll = want["rotation_pyr"]
            xf.set_editor_property("rotation", unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw).quaternion())
            a.set_editor_property("relative_transform", xf); seen.add(gid)
        if seen != set(by_id): raise C.P87Error("BULB_IDS|missing=%s" % sorted(set(by_id) - seen))
        P13["_set_pair_attachments"](self.show, self.p01_index, rows)
        passage = [a for a in _actors() if a.get_class().get_name() == "InfinityStagePassageActor"
                   and a.get_editor_property("show_asset") == self.show and str(a.get_actor_label()).startswith("Passage 01")]
        if len(passage) != 1 or not bool(passage[0].materialize_passage()): raise C.P87Error("P01_MATERIALIZE_BULBS")

    def apply(self, plan):
        if "CURTAIN" in plan["parts"]: self._apply_curtain(plan["curtain"])
        if "CAMERA" in plan["parts"]: self._apply_camera(plan["camera"])
        if "UPLIGHTS" in plan["parts"]: self._apply_uplights(plan["uplights"])
        if "BULBS" in plan["parts"]: self._apply_bulbs(plan["bulbs"])

    def _restore_track(self, track, snapshot):
        sec = list(track.get_sections())[0]; spec = snapshot["sections"][0]; sec.set_range(*spec["range"])
        live = list(sec.get_all_channels())
        for ch, saved in zip(live, spec["channels"]):
            for key in list(ch.get_keys()): ch.remove_key(key)
            if saved["default"] is not None: ch.set_default(saved["default"])
            for f, value in saved["keys"]:
                ch.add_key(unreal.FrameNumber(f), value, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                           interpolation=unreal.MovieSceneKeyInterpolation.AUTO)

    def restore(self, before):
        if "curtain" in before:
            unused, secs, unused2 = P13["_gc"](self.sequence); P13["_set_gc"](secs, before["curtain"]["sections"])
        if "camera" in before:
            unused, transform, unused2, focal = self._camera_bindings()
            self._restore_track(transform, before["camera"]["transform"]); self._restore_track(focal, before["camera"]["focal"])
        if "bulbs" in before:
            saved = {r["id"]: r for r in before["bulbs"]}; rows = self._pair_rows()
            for a in rows:
                gid = _guid(a.get_editor_property("attachment_guid"))
                if gid not in saved: continue
                row = saved[gid]; xf = a.get_editor_property("relative_transform")
                xf.set_editor_property("translation", unreal.Vector(*row["location"]))
                pitch, yaw, roll = row["rotation"]
                xf.set_editor_property("rotation", unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw).quaternion())
                a.set_editor_property("relative_transform", xf)
            P13["_set_pair_attachments"](self.show, self.p01_index, rows)
        if "uplights" in before:
            keep_ids = {r["id"] for r in before["uplights"]}; rows = self._pair_rows()
            rows = [a for a in rows if not (str(a.get_editor_property("label")).startswith(P87_PREFIX)
                                            and _guid(a.get_editor_property("attachment_guid")) not in keep_ids)]
            P13["_set_pair_attachments"](self.show, self.p01_index, rows)
        if "bulbs" in before or "uplights" in before:
            passage = [a for a in _actors() if a.get_class().get_name() == "InfinityStagePassageActor"
                       and a.get_editor_property("show_asset") == self.show and str(a.get_actor_label()).startswith("Passage 01")]
            if len(passage) != 1 or not bool(passage[0].materialize_passage()): raise C.P87Error("RESTORE_MATERIALIZE")

    def assert_plan(self, after, plan):
        if "curtain" in after and len(after["curtain"]["sections"]) != 3: raise C.P87Error("CURTAIN_READBACK")
        if "uplights" in after and len(after["uplights"]) != len(plan["uplights"]["rows"]): raise C.P87Error("UPLIGHT_READBACK")
        if "bulbs" in after and len(after["bulbs"]) != len(plan["bulbs"]["rows"]): raise C.P87Error("BULB_READBACK")

    def save_named(self, packages):
        if packages != [SHOW, self.sequence_path, LEVEL]: raise C.P87Error("SAVE_SCOPE")
        census = _dirty()
        if set(census["content"]) - {SHOW, self.sequence_path} or set(census["maps"]) - {LEVEL}:
            raise C.P87Error("DIRTY_SCOPE|" + C.canonical(census))
        if not unreal.EditorAssetLibrary.save_asset(SHOW, only_if_is_dirty=False): raise C.P87Error("SHOW_SAVE")
        if not unreal.EditorAssetLibrary.save_asset(self.sequence_path, only_if_is_dirty=False): raise C.P87Error("SEQUENCE_SAVE")
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(): raise C.P87Error("LEVEL_SAVE")
        self.saved = True

    def readback(self, parts):
        self._resolve()
        return self.owned_state(parts)

    @staticmethod
    def assert_equivalent(a, b):
        if C.changed_paths(a, b): raise C.P87Error("READBACK|" + ",".join(C.changed_paths(a, b)[:20]))

    @staticmethod
    def log(line): unreal.log(line)
    @staticmethod
    def log_error(line): unreal.log_error(line)
