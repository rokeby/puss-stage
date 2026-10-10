"""Job 144: stage I2 or I3 on the preceding scene's hangar back wall.

Offline-authored: do not run from this worktree.  DRY inventories live state;
APPLY/REVERT write only our scene-wrapper and Interaction Level Sequences.
Klara's streamed levels and the show level are never saved.
"""
from __future__ import print_function

import datetime
import hashlib
import json
import math
import os
import re
import shutil

from job144_core import PlanError, canonical_name, channel_name, digest, make_plan, merged_params

TOOL = "JOB144_INTERACTION_HANGAR"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQS = {2: "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips",
        3: "/Game/InfinityStage/Interactions/LS_Interaction_03_ForgetsHisName"}
SCENES = {2: "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02",
          3: "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"}
CONFIRMS = {mode: "%s JOB144" % mode for mode in ("DRY", "APPLY", "REVERT")}
POSE = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")


class Stop(RuntimeError):
    pass


def _read(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise Stop("MISSING_JSON|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")


def _guid(value, unreal):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").replace("{", "").replace("}", "").upper()


class UnrealBackend(object):
    def __init__(self, root=None):
        import unreal
        self.u = unreal
        self.root = root or os.path.dirname(os.path.abspath(__file__))

    def log(self, text): self.u.log(text)
    def fail(self, text): self.u.log_error(text); raise Stop(text)

    def census(self):
        lib = self.u.EditorLoadingAndSavingUtils
        return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}

    def preflight(self, mode, confirm):
        if confirm != CONFIRMS[mode]: raise Stop("CONFIRM|expected=%s" % CONFIRMS[mode])
        sub = self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem)
        world = sub.get_editor_world()
        if world is None or str(world.get_path_name()).split(".")[0] != WORLD: raise Stop("WORLD|%s" % world)
        if sub.get_game_world() is not None: raise Stop("PIE_OR_SIE_RUNNING")
        if self.census() != {"content": [], "maps": []}: raise Stop("DIRTY_AT_START|%s" % self.census())

    def _keys(self, channel):
        rows = []
        for key in channel.get_keys():
            frame = int(key.get_time(time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value)
            value = key.get_value()
            rows.append([frame, bool(value) if isinstance(value, bool) else float(value)])
        return sorted(rows)

    def _span(self, sec, seq):
        return [int(sec.get_start_frame()) if sec.has_start_frame() else int(seq.get_playback_start()),
                int(sec.get_end_frame()) if sec.has_end_frame() else int(seq.get_playback_end())]

    def _bindings(self, seq):
        out = []
        for binding in seq.get_bindings():
            tracks = []
            for ti, track in enumerate(binding.get_tracks()):
                sections = []
                for si, section in enumerate(track.get_sections()):
                    sections.append({"range": self._span(section, seq), "section_index": si,
                                     "channels": [{"name": str(ch.channel_name), "base": channel_name(ch.channel_name),
                                                   "channel_index": ci, "keys": self._keys(ch)}
                                                  for ci, ch in enumerate(section.get_all_channels())]})
                prop = None
                try: prop = str(track.get_property_name())
                except Exception: pass
                tracks.append({"class": track.get_class().get_name(), "track_index": ti,
                               "display": str(track.get_display_name()), "property": prop, "sections": sections})
            out.append({"guid": _guid(binding.get_id(), self.u), "name": str(binding.get_display_name()),
                        "spawnable": binding.get_object_template() is not None, "tracks": tracks})
        return out

    def _markers(self, seq):
        tick = seq.get_tick_resolution().numerator / float(seq.get_tick_resolution().denominator)
        fps = seq.get_display_rate().numerator / float(seq.get_display_rate().denominator)
        out = {}
        for marker in self.u.MovieSceneSequenceExtensions.get_marked_frames(seq):
            out[str(marker.label)] = int(round(int(marker.frame_number.value) / (tick / fps)))
        required = ("CST curtain hung", "CST sleight")
        for wanted in required:
            rows = [value for name, value in out.items() if wanted.lower() in name.lower()]
            if len(rows) != 1: raise Stop("MARKER_COUNT|%s|%d" % (wanted, len(rows)))
            out[wanted] = rows[0]
        return out

    def _cuts(self, seq):
        rows = []
        for track in seq.get_tracks():
            if track.get_class().get_name() != "MovieSceneCameraCutTrack": continue
            for section in track.get_sections():
                bid = section.get_camera_binding_id().get_editor_property("guid")
                rows.append({"range": self._span(section, seq), "active": bool(section.is_active()),
                             "guid": _guid(bid, self.u)})
        return rows

    def _actor_rows(self, n, seq):
        actors = list(self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors())
        actor_paths = {str(actor.get_path_name()): actor for actor in actors}
        binding_guids = {path: [] for path in actor_paths}
        world = self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem).get_editor_world()
        for binding in seq.get_bindings():
            guid = _guid(binding.get_id(), self.u)
            try:
                objects = list(seq.locate_bound_objects(binding, world))
            except Exception as exc:
                raise Stop("BINDING_OBJECT_RESOLUTION|%s|%r" % (guid, exc))
            for obj in objects:
                path = str(obj.get_path_name())
                if path in binding_guids:
                    binding_guids[path].append(guid)
        rows = []
        for actor in actors:
            label = str(actor.get_actor_label())
            path = str(actor.get_path_name())
            tags = [str(t) for t in actor.get_editor_property("tags")]
            outer = path.split(":PersistentLevel", 1)[0]
            candidate = (re.search(r"(^|\D)S%d(\D|$)" % n, label, re.I) is not None or
                         re.search(r"Scene[_ ]?0?%d|S%d" % (n, n), outer, re.I) is not None or
                         any(re.search(r"Scene.?%d|S%d" % (n, n), tag, re.I) for tag in tags))
            rows.append({"label": label, "path": path, "class": actor.get_class().get_name(),
                         "outer_level": outer, "tags": tags, "scene_candidate": bool(candidate),
                         "sequence_binding_guids": sorted(set(binding_guids[path]))})
        return actors, rows

    def _wall_rows(self, n, actors, root):
        out = []
        for actor in actors:
            label = str(actor.get_actor_label())
            if not (re.search(r"S%d.*(?:Wall|Backdrop)" % n, label, re.I) or
                    (n == 3 and label == "S3 Backdrop")): continue
            origin, extent = actor.get_actor_bounds(False)
            local = self.u.MathLibrary.inverse_transform_location(root.get_actor_transform(), origin)
            # The wall-facing direction is derived from the root's positive X axis;
            # the curtain sits just inside (negative root X from the far wall).
            root_forward = root.get_actor_forward_vector()
            out.append({"label": label, "path": str(actor.get_path_name()),
                        "root_local_center": [float(local.x), float(local.y), float(local.z)],
                        "bounds_min": [float(origin.x - extent.x), float(origin.y - extent.y), float(origin.z - extent.z)],
                        "bounds_max": [float(origin.x + extent.x), float(origin.y + extent.y), float(origin.z + extent.z)],
                        "interior_point": [float(origin.x), float(origin.y), float(origin.z - extent.z)],
                        "interior_normal": [-float(root_forward.x), -float(root_forward.y), 0.0],
                        "rear_clearance_cm": float(min(extent.x, extent.y) * 2.0)})
        # S2's far wall is deliberately split around the exit (left/right/above).
        # Treat those slabs as one wall plane for placement instead of allowing
        # AUTO selection to mistake the equal-X pieces for an ambiguity.
        far = [row for row in out if re.search(r"Hangar Far Wall", row["label"], re.I)]
        if len(far) > 1:
            minimum = [min(row["bounds_min"][i] for row in far) for i in range(3)]
            maximum = [max(row["bounds_max"][i] for row in far) for i in range(3)]
            centre = [(minimum[i] + maximum[i]) * 0.5 for i in range(3)]
            local = self.u.MathLibrary.inverse_transform_location(root.get_actor_transform(), self.u.Vector(*centre))
            composite = {"label": "S%d Hangar Far Wall (composite)" % n,
                         "paths": [row["path"] for row in far],
                         "members": [row["label"] for row in far],
                         "root_local_center": [float(local.x), float(local.y), float(local.z)],
                         "bounds_min": minimum, "bounds_max": maximum,
                         "interior_point": centre, "interior_normal": far[0]["interior_normal"],
                         "rear_clearance_cm": min(row["rear_clearance_cm"] for row in far)}
            out = [row for row in out if row not in far] + [composite]
        return out

    def _binding_one(self, seq, name):
        rows = [b for b in seq.get_bindings() if canonical_name(b.get_display_name()) == name]
        if len(rows) != 1: raise Stop("BINDING_COUNT|%s|%d" % (name, len(rows)))
        return rows[0]

    def _pose(self, binding):
        tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1: raise Stop("POSE_TRACK_COUNT|%s" % binding.get_display_name())
        section = tracks[0].get_sections()[0]
        channels = {channel_name(ch.channel_name): {"keys": self._keys(ch), "channel": ch}
                    for ch in section.get_all_channels()}
        if any(name not in channels for name in POSE): raise Stop("POSE_CHANNELS|%s" % binding.get_display_name())
        return {"locator": [_guid(binding.get_id(), self.u), list(binding.get_tracks()).index(tracks[0]), 0],
                "channels": {name: channels[name]["keys"] for name in POSE}}

    def _template_pose(self, binding):
        template = binding.get_object_template()
        if template is None: raise Stop("CURTAIN_NOT_SPAWNABLE")
        root = template.get_editor_property("root_component")
        loc = root.get_editor_property("relative_location"); rot = root.get_editor_property("relative_rotation")
        return {"loc": [float(loc.x), float(loc.y), float(loc.z)], "roll": float(rot.roll),
                "pitch": float(rot.pitch), "yaw": float(rot.yaw)}

    def snapshot(self, params):
        n = params["interaction"]; seq = self.u.load_asset(SEQS[n]); scene = self.u.load_asset(SCENES[n])
        if seq is None or scene is None: raise Stop("ASSET_LOAD|I%d" % n)
        actors, actor_rows = self._actor_rows(n, seq)
        labels = [str(a.get_actor_label()) for a in actors]
        roots = [a for a in actors if str(a.get_actor_label()) == "S%d Hangar Root" % n]
        if len(roots) != 1: raise Stop("HANGAR_ROOT_COUNT|I%d|%d" % (n, len(roots)))
        markers = self._markers(seq)
        curtain_binding = self._binding_one(seq, "Sleight Hangar Drape")
        camera_binding = self._binding_one(seq, "S%d Sleight Hangar Camera" % n)
        bindings = self._bindings(seq)
        puppets = [r["name"] for r in bindings if re.search(r"gobo|puppet|boy|cat|card", r["name"], re.I)
                   and not re.search(r"camera|component", r["name"], re.I)]
        curtain_transform = self._pose(curtain_binding)
        from job144_core import interp
        values = {name: interp(curtain_transform["channels"][name], markers["CST curtain hung"])
                  for name in POSE}
        curtain_pose = {"loc": [values["Location.X"], values["Location.Y"], values["Location.Z"]],
                        "roll": values["Rotation.X"], "pitch": values["Rotation.Y"],
                        "yaw": values["Rotation.Z"]}
        return {"sequence": SEQS[n], "scene_wrapper": SCENES[n],
                "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
                "scene_playback": [int(scene.get_playback_start()), int(scene.get_playback_end())],
                "markers": markers, "bindings": bindings, "cuts": self._cuts(seq),
                "world_labels": labels, "actors": actor_rows, "wall_candidates": self._wall_rows(n, actors, roots[0]),
                "root_transform": roots[0].get_actor_transform(), "curtain_pose": curtain_pose,
                "curtain_template_pose": self._template_pose(curtain_binding),
                "curtain_transform": curtain_transform, "camera_transform": self._pose(camera_binding),
                "fade_tracks": {"interaction": sum(1 for t in seq.get_tracks() if t.get_class().get_name() == "MovieSceneFadeTrack"),
                                "scene": sum(1 for t in scene.get_tracks() if t.get_class().get_name() == "MovieSceneFadeTrack")},
                "puppet_bindings": sorted(puppets),
                "existing_tools": {"job89": "P89CurtainBeforeShadow_20261009",
                                   "job90b": "Interaction90b_20261009", "i1": "I1Polish_20261009",
                                   "shadow_records": "shadow_play_spot_record_I2/I3.json"}}

    def build_report(self, params, run):
        snap = self.snapshot(params); plan = make_plan(snap, params)
        # Convert the computed world camera target into the hangar-root-relative
        # transform expected by the existing camera binding.
        p = plan["camera_target_world"]
        world_xf = self.u.Transform(location=self.u.Vector(*p["loc"]),
                                    rotation=self.u.Rotator(roll=p["roll"], pitch=p["pitch"], yaw=p["yaw"]),
                                    scale=self.u.Vector(1.0, 1.0, 1.0))
        rel = self.u.MathLibrary.make_relative_transform(world_xf, snap["root_transform"])
        rr = rel.rotation.rotator()
        plan["camera_target_relative"] = {"Location.X": float(rel.translation.x),
                                          "Location.Y": float(rel.translation.y), "Location.Z": float(rel.translation.z),
                                          "Rotation.X": float(rr.roll), "Rotation.Y": float(rr.pitch),
                                          "Rotation.Z": float(rr.yaw)}
        plan["digest"] = digest({k: v for k, v in plan.items() if k != "digest"})
        return {"schema": 1, "run": run, "proof": "measured live read-only; visual acceptance pending",
                "snapshot": {k: v for k, v in snap.items() if k != "root_transform"}, "plan": plan,
                "census": self.census()}

    def _asset_file(self, package):
        root = self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_content_dir())
        return os.path.join(root, *package[len("/Game/"):].split("/")) + ".uasset"

    def _backup(self, n, run, packages, suffix=""):
        root = self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_dir())
        folder = os.path.join(root, "Backups", "PreJob144I%d%s-%s" % (n, suffix, run))
        os.makedirs(folder)
        rows = []
        for package in packages:
            src = self._asset_file(package); dst = os.path.join(folder, os.path.basename(src))
            if not os.path.isfile(src): raise Stop("BACKUP_SOURCE|%s" % src)
            shutil.copy2(src, dst)
            with open(dst, "rb") as handle: sha = hashlib.sha256(handle.read()).hexdigest()
            rows.append({"package": package, "backup": dst, "sha256": sha})
        return folder, rows

    def _binding_guid(self, seq, guid):
        rows = [b for b in seq.get_bindings() if _guid(b.get_id(), self.u) == guid]
        if len(rows) != 1: raise Stop("LOCATOR_BINDING|%s" % guid)
        return rows[0]

    def _channel(self, seq, locator):
        binding = self._binding_guid(seq, locator[0])
        return list(list(list(binding.get_tracks())[locator[1]].get_sections())[locator[2]].get_all_channels())[locator[3]]

    def _rewrite(self, channel, keys):
        for key in list(channel.get_keys()): channel.remove_key(key)
        for frame, value in keys:
            channel.add_key(self.u.FrameNumber(int(frame)), value,
                            time_unit=self.u.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=self.u.MovieSceneKeyInterpolation.LINEAR)

    def _checkpoint(self, record):
        path = getattr(self, "active_record_path", None)
        if path:
            _write(path, record)

    def _record_channel(self, record, package, locator, channel, after, section=None,
                        before_range=None, after_range=None):
        before = self._keys(channel)
        row = {"package": package, "locator": locator, "before": before, "after": after}
        if section is not None:
            row["before_range"] = list(before_range)
            row["after_range"] = list(after_range)
        record["channels"].append(row); self._checkpoint(record)
        if section is not None:
            section.set_range(int(after_range[0]), int(after_range[1]))
        self._rewrite(channel, after)

    def _add_track(self, record, package, seq, binding, cls, prop, keys, start, end, path=None):
        track = binding.add_track(cls)
        track.set_property_name_and_path(prop, path or prop)
        section = track.add_section(); section.set_range(start, end + 1)
        channel = list(section.get_all_channels())[0]; self._rewrite(channel, keys)
        row = {"package": package, "binding_guid": _guid(binding.get_id(), self.u),
               "track_index": list(binding.get_tracks()).index(track), "class": track.get_class().get_name(),
               "property": prop, "keys": keys}
        record["created_tracks"].append(row); self._checkpoint(record); return row

    def _add_fade(self, record, package, seq, keys):
        if any(t.get_class().get_name() == "MovieSceneFadeTrack" for t in seq.get_tracks()):
            raise Stop("FADE_TRACK_EXISTS|%s" % package)
        track = seq.add_track(self.u.MovieSceneFadeTrack)
        section = track.add_section(); section.set_range(seq.get_playback_start(), seq.get_playback_end() + 1)
        self._rewrite(list(section.get_all_channels())[0], keys)
        record["created_root_tracks"].append({"package": package, "track_index": list(seq.get_tracks()).index(track),
                                              "class": "MovieSceneFadeTrack", "keys": keys})
        self._checkpoint(record)

    def _visibility(self, record, seq, plan, actors):
        by_path = {str(a.get_path_name()): a for a in actors}
        by_guid = {_guid(binding.get_id(), self.u): binding for binding in seq.get_bindings()}
        for row in plan["visibility"]["actors"]:
            path = row["path"]
            label = row["label"]
            actor = by_path.get(path)
            if actor is None: raise Stop("VIS_ACTOR_PATH_MISSING|%s" % path)
            matches = [by_guid[guid] for guid in row.get("sequence_binding_guids", []) if guid in by_guid]
            if len(matches) > 1: raise Stop("VIS_BINDING_AMBIGUOUS|%s|%s" % (path, row["sequence_binding_guids"]))
            if row.get("visibility_action") == "REUSE_EXISTING":
                locator = row["visibility_locator"]
                channel = self._channel(seq, locator)
                binding = self._binding_guid(seq, locator[0])
                track = list(binding.get_tracks())[locator[1]]
                if track.get_class().get_name() != "MovieSceneVisibilityTrack":
                    raise Stop("VIS_REUSE_TRACK_DRIFT|%s" % path)
                prop = str(track.get_property_name()) if hasattr(track, "get_property_name") else ""
                if prop not in ("bHidden", ""):
                    raise Stop("VIS_REUSE_PROPERTY_DRIFT|%s|%s" % (path, prop))
                section = list(track.get_sections())[locator[2]]
                before_range = self._span(section, seq)
                self._record_channel(record, plan["sequence"], locator, channel,
                                     row["visibility_keys"], section, before_range,
                                     row["visibility_section_range"])
                continue
            created = False
            if matches: binding = matches[0]
            else:
                before = set(by_guid)
                binding = seq.add_possessable(actor)
                guid = _guid(binding.get_id(), self.u)
                if guid in before:
                    raise Stop("VIS_EXISTING_BINDING_NOT_IN_SNAPSHOT|%s|%s" % (path, guid))
                binding.set_display_name(label); created = True
                record["created_bindings"].append({"package": plan["sequence"], "guid": _guid(binding.get_id(), self.u)})
                self._checkpoint(record)
            for track in binding.get_tracks():
                if track.get_class().get_name() == "MovieSceneVisibilityTrack":
                    prop = str(track.get_property_name()) if hasattr(track, "get_property_name") else ""
                    if prop in ("bHidden", "bHiddenInGame", ""):
                        raise Stop("VISIBILITY_TRACK_EXISTS|%s|%s" % (label, prop))
            self._add_track(record, plan["sequence"], seq, binding, self.u.MovieSceneVisibilityTrack,
                            "bHidden", plan["visibility"]["keys"], plan["playback"][0], plan["playback"][1])
            if created and canonical_name(binding.get_display_name()) != canonical_name(label):
                raise Stop("BINDING_RENAME_FAILED|%s|%s" % (path, label))

    def _spot(self, record, seq, plan):
        name = plan["spot"]["name"]
        old = [b for b in seq.get_bindings() if canonical_name(b.get_display_name()) in
               (name, "Shadow Play Spot (Hangar)")]
        if len(old) > 1: raise Stop("SHADOW_SPOT_AMBIGUOUS")
        if old:
            binding = old[0]
            created = False
        else:
            binding = seq.add_spawnable_from_class(self.u.SpotLight); binding.set_display_name(name)
            record["created_bindings"].append({"package": plan["sequence"], "guid": _guid(binding.get_id(), self.u)})
            self._checkpoint(record)
            created = True
        template = binding.get_object_template()
        if template is None: raise Stop("SHADOW_SPOT_NOT_SPAWNABLE")
        comp = template.get_editor_property("spot_light_component"); root = template.get_editor_property("root_component")
        if comp is None or root is None: raise Stop("SHADOW_SPOT_TEMPLATE")
        old_loc = root.get_editor_property("relative_location"); old_rot = root.get_editor_property("relative_rotation")
        props = ("intensity", "use_temperature", "temperature", "outer_cone_angle", "inner_cone_angle",
                 "attenuation_radius", "source_radius", "cast_shadows")
        template_row = {"package": plan["sequence"], "guid": _guid(binding.get_id(), self.u), "created": created,
                        "before": {"loc": [float(old_loc.x), float(old_loc.y), float(old_loc.z)],
                                   "rot": [float(old_rot.roll), float(old_rot.pitch), float(old_rot.yaw)],
                                   "props": {p: comp.get_editor_property(p) for p in props}}}
        record["templates"].append(template_row); self._checkpoint(record)
        sp = plan["spot"]
        root.set_editor_property("relative_location", self.u.Vector(*sp["loc"]))
        root.set_editor_property("relative_rotation", self.u.Rotator(roll=sp["roll"], pitch=sp["pitch"], yaw=sp["yaw"]))
        if created:
            comp.set_editor_property("mobility", self.u.ComponentMobility.MOVABLE)
            comp.set_editor_property("intensity_units", self.u.LightUnits.CANDELAS)
        elif (comp.get_editor_property("mobility") != self.u.ComponentMobility.MOVABLE or
              comp.get_editor_property("intensity_units") != self.u.LightUnits.CANDELAS):
            raise Stop("ADOPTED_SPOT_UNITS_OR_MOBILITY")
        comp.set_editor_property("intensity", float(plan["params"]["spot_intensity_cd"]))
        comp.set_editor_property("use_temperature", True); comp.set_editor_property("temperature", plan["params"]["spot_kelvin"])
        comp.set_editor_property("outer_cone_angle", plan["params"]["spot_outer_cone_deg"])
        comp.set_editor_property("inner_cone_angle", plan["params"]["spot_inner_cone_deg"])
        comp.set_editor_property("attenuation_radius", plan["params"]["spot_attenuation_radius_cm"])
        comp.set_editor_property("source_radius", plan["params"]["spot_source_radius_cm"])
        comp.set_editor_property("cast_shadows", True)
        # Adopt the established job-89/I1/I4/I5 hangar spot when present.  A new
        # I3 spot gets the identical component-property path.
        intensity = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneFloatTrack" and
                     str(t.get_property_name()) == "Intensity"]
        if len(intensity) > 1: raise Stop("SPOT_INTENSITY_TRACK_COUNT|%d" % len(intensity))
        if intensity:
            if len(intensity[0].get_sections()) != 1: raise Stop("SPOT_INTENSITY_SECTION_COUNT")
            channel = list(intensity[0].get_sections()[0].get_all_channels())[0]
            locator = [_guid(binding.get_id(), self.u), list(binding.get_tracks()).index(intensity[0]), 0, 0]
            self._record_channel(record, plan["sequence"], locator, channel, sp["intensity_keys"])
        else:
            self._add_track(record, plan["sequence"], seq, binding, self.u.MovieSceneFloatTrack, "Intensity",
                            sp["intensity_keys"], plan["playback"][0], plan["playback"][1],
                            "%s.Intensity" % comp.get_name())
        # Existing spot transform keys override its template, so adopt them too.
        transforms = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
        target = {"Location.X": sp["loc"][0], "Location.Y": sp["loc"][1], "Location.Z": sp["loc"][2],
                  "Rotation.X": sp["roll"], "Rotation.Y": sp["pitch"], "Rotation.Z": sp["yaw"]}
        if transforms:
            if len(transforms) != 1 or len(transforms[0].get_sections()) != 1: raise Stop("SPOT_TRANSFORM_COUNT")
            channels = list(transforms[0].get_sections()[0].get_all_channels())
            for ci, channel in enumerate(channels):
                base = channel_name(channel.channel_name)
                if base not in target: continue
                locator = [_guid(binding.get_id(), self.u), list(binding.get_tracks()).index(transforms[0]), 0, ci]
                keys = [[plan["playback"][0], target[base]], [plan["playback"][1], target[base]]]
                self._record_channel(record, plan["sequence"], locator, channel, keys)
        elif created:
            track = binding.add_track(self.u.MovieScene3DTransformTrack)
            section = track.add_section(); section.set_range(plan["playback"][0], plan["playback"][1] + 1)
            row = {"package": plan["sequence"], "binding_guid": _guid(binding.get_id(), self.u),
                   "track_index": list(binding.get_tracks()).index(track), "class": "MovieScene3DTransformTrack",
                   "property": "Transform", "keys": [], "pose": target}
            record["created_tracks"].append(row); self._checkpoint(record)
            for channel in section.get_all_channels():
                base = channel_name(channel.channel_name)
                if base in target: self._rewrite(channel, [[plan["playback"][0], target[base]],
                                                           [plan["playback"][1], target[base]]])
        # Reuse UE's auto-created spawn track if present.
        spawn = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
        if len(spawn) != 1: raise Stop("SPAWN_TRACK_COUNT|%d" % len(spawn))
        channel = list(spawn[0].get_sections()[0].get_all_channels())[0]
        locator = [_guid(binding.get_id(), self.u), list(binding.get_tracks()).index(spawn[0]), 0, 0]
        self._record_channel(record, plan["sequence"], locator, channel, sp["spawn_keys"])
        # Gary asked for one interaction shadow rig.  Disable every other
        # shadow-spot binding, including the legacy mouth-side spot.
        owner_guid = _guid(binding.get_id(), self.u)
        for other in seq.get_bindings():
            if _guid(other.get_id(), self.u) == owner_guid: continue
            if not ("shadow" in str(other.get_display_name()).lower() and
                    "spot" in str(other.get_display_name()).lower()): continue
            for track in other.get_tracks():
                cls = track.get_class().get_name()
                prop = str(track.get_property_name()) if hasattr(track, "get_property_name") else ""
                if cls == "MovieSceneFloatTrack" and prop == "Intensity":
                    channel = list(track.get_sections()[0].get_all_channels())[0]
                    loc = [_guid(other.get_id(), self.u), list(other.get_tracks()).index(track), 0, 0]
                    self._record_channel(record, plan["sequence"], loc, channel,
                                         [[plan["playback"][0], 0.0], [plan["playback"][1], 0.0]])
                elif cls == "MovieSceneSpawnTrack":
                    channel = list(track.get_sections()[0].get_all_channels())[0]
                    loc = [_guid(other.get_id(), self.u), list(other.get_tracks()).index(track), 0, 0]
                    self._record_channel(record, plan["sequence"], loc, channel,
                                         [[plan["playback"][0], False], [plan["playback"][1], False]])

    def _apply_pose_plans(self, record, report):
        from job144_core import merge_camera, offset_curtain
        plan = report["plan"]; snap = report["snapshot"]; seq = self.u.load_asset(plan["sequence"])
        start = plan["playback"][0]; settle = plan["beats"]["camera_settle"]; sleight = plan["beats"]["sleight"]
        camloc = snap["camera_transform"]["locator"]
        for ci, name in enumerate(POSE):
            loc = camloc + [ci]; channel = self._channel(seq, loc); before = self._keys(channel)
            after = merge_camera(before, start, settle, sleight, plan["camera_target_relative"][name], name.startswith("Rotation"))
            self._record_channel(record, plan["sequence"], loc, channel, after)
        curloc = snap["curtain_transform"]["locator"]
        old = snap["curtain_pose"]; new = plan["curtain_target"]
        deltas = {"Location.X": new["loc"][0]-old["loc"][0], "Location.Y": new["loc"][1]-old["loc"][1],
                  "Location.Z": new["loc"][2]-old["loc"][2], "Rotation.X": new["roll"]-old["roll"],
                  "Rotation.Y": new["pitch"]-old["pitch"], "Rotation.Z": new["yaw"]-old["yaw"]}
        # Translate the whole existing fly-in path, not only the final hung
        # keys; offsetting at the hung marker would create a one-frame jump.
        hung = start
        for ci, name in enumerate(POSE):
            loc = curloc + [ci]; channel = self._channel(seq, loc); before = self._keys(channel)
            after = offset_curtain(before, hung, sleight, deltas[name])
            self._record_channel(record, plan["sequence"], loc, channel, after)

    def apply(self, report, run):
        plan = report["plan"]; n = plan["interaction"]; packages = plan["save_packages"]
        folder, backups = self._backup(n, run, packages)
        path = os.path.join(self.root, "job144_record_I%d.json" % n)
        if os.path.exists(path): raise Stop("RECORD_EXISTS|%s" % path)
        record = {"schema": 1, "status": "applying", "run": run, "interaction": n, "plan_digest": plan["digest"],
                  "packages": packages, "plan_playback": plan["playback"], "backup": folder,
                  "backup_files": backups, "channels": [],
                  "created_tracks": [], "created_root_tracks": [], "created_bindings": [], "templates": []}
        _write(path, record, exclusive=True)
        self.active_record_path = path
        seq = self.u.load_asset(plan["sequence"]); scene = self.u.load_asset(plan["scene_wrapper"])
        seq.modify(); scene.modify(); actors = list(self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors())
        self._apply_pose_plans(record, report)
        self._visibility(record, seq, plan, actors)
        self._add_fade(record, plan["sequence"], seq, plan["blackout_keys"])
        self._add_fade(record, plan["scene_wrapper"], scene, plan["scene_tail_black_keys"])
        self._spot(record, seq, plan)
        _write(path, record)
        actual = sorted(self.census()["content"] + self.census()["maps"])
        if actual != sorted(packages): raise Stop("DIRTY_SCOPE|expected=%s|actual=%s|NOTHING_SAVED" % (packages, actual))
        for package in packages:
            if not self.u.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True): raise Stop("SAVE_FAILED|%s" % package)
        if self.census() != {"content": [], "maps": []}: raise Stop("DIRTY_AFTER_SAVE|%s" % self.census())
        self._verify_record(record, True)
        record["status"] = "applied"; record["dirty_after"] = self.census(); _write(path, record)
        self.active_record_path = None
        return record

    def _same(self, got, want, tol=1.0e-4):
        if len(got) != len(want): return False
        for left, right in zip(got, want):
            if int(left[0]) != int(right[0]): return False
            if isinstance(right[1], bool):
                if bool(left[1]) != bool(right[1]): return False
            elif abs(float(left[1])-float(right[1])) > tol * max(1.0, abs(float(right[1]))): return False
        return True

    def _verify_record(self, record, applied):
        for row in record["channels"]:
            seq = self.u.load_asset(row["package"]); got = self._keys(self._channel(seq, row["locator"]))
            if not self._same(got, row["after"] if applied else row["before"]): raise Stop("READBACK_CHANNEL|%s" % row["locator"])
            if "before_range" in row:
                binding = self._binding_guid(seq, row["locator"][0])
                section = list(list(binding.get_tracks())[row["locator"][1]].get_sections())[row["locator"][2]]
                want_range = row["after_range"] if applied else row["before_range"]
                if self._span(section, seq) != want_range:
                    raise Stop("READBACK_SECTION_RANGE|%s|got=%s|want=%s" %
                               (row["locator"], self._span(section, seq), want_range))
        if applied:
            for row in record["created_tracks"]:
                seq = self.u.load_asset(row["package"]); binding = self._binding_guid(seq, row["binding_guid"])
                tracks = list(binding.get_tracks())
                if row["track_index"] >= len(tracks) or tracks[row["track_index"]].get_class().get_name() != row["class"]:
                    raise Stop("READBACK_TRACK|%s" % row)
                track = tracks[row["track_index"]]
                if row["property"] == "bHidden" and str(track.get_property_name()) != "bHidden":
                    raise Stop("VISIBILITY_NOT_BHIDDEN")
                if row["class"] == "MovieScene3DTransformTrack":
                    for channel in track.get_sections()[0].get_all_channels():
                        base = channel_name(channel.channel_name)
                        if base in row["pose"]:
                            want = [[record["plan_playback"][0], row["pose"][base]],
                                    [record["plan_playback"][1], row["pose"][base]]]
                            if not self._same(self._keys(channel), want):
                                raise Stop("READBACK_TRANSFORM|%s" % base)
                else:
                    got = self._keys(list(track.get_sections()[0].get_all_channels())[0])
                    if not self._same(got, row["keys"]): raise Stop("READBACK_TRACK_KEYS|%s" % row)
            for row in record["created_root_tracks"]:
                seq = self.u.load_asset(row["package"]); tracks = list(seq.get_tracks())
                if row["track_index"] >= len(tracks) or tracks[row["track_index"]].get_class().get_name() != row["class"]:
                    raise Stop("READBACK_ROOT_TRACK|%s" % row)
                got = self._keys(list(tracks[row["track_index"]].get_sections()[0].get_all_channels())[0])
                if not self._same(got, row["keys"]): raise Stop("READBACK_ROOT_KEYS|%s" % row)
        return True

    def revert(self, n, run):
        path = os.path.join(self.root, "job144_record_I%d.json" % n); record = _read(path)
        if record.get("status") != "applied": raise Stop("RECORD_NOT_APPLIED")
        folder, backups = self._backup(n, run, record["packages"], "Revert")
        for row in record["channels"]:
            seq = self.u.load_asset(row["package"]); channel = self._channel(seq, row["locator"])
            if not self._same(self._keys(channel), row["after"]): raise Stop("REVERT_CHANNEL_DRIFT|%s" % row["locator"])
            if "after_range" in row:
                binding = self._binding_guid(seq, row["locator"][0])
                section = list(list(binding.get_tracks())[row["locator"][1]].get_sections())[row["locator"][2]]
                if self._span(section, seq) != row["after_range"]:
                    raise Stop("REVERT_SECTION_RANGE_DRIFT|%s" % row["locator"])
                section.set_range(int(row["before_range"][0]), int(row["before_range"][1]))
            self._rewrite(channel, row["before"])
        for row in reversed(record["created_root_tracks"]):
            seq = self.u.load_asset(row["package"]); tracks = list(seq.get_tracks())
            if row["track_index"] >= len(tracks) or tracks[row["track_index"]].get_class().get_name() != row["class"]:
                raise Stop("REVERT_ROOT_TRACK_DRIFT")
            seq.remove_track(tracks[row["track_index"]])
        for row in reversed(record["created_tracks"]):
            seq = self.u.load_asset(row["package"]); binding = self._binding_guid(seq, row["binding_guid"])
            tracks = list(binding.get_tracks())
            if row["track_index"] >= len(tracks) or tracks[row["track_index"]].get_class().get_name() != row["class"]:
                raise Stop("REVERT_TRACK_DRIFT")
            binding.remove_track(tracks[row["track_index"]])
        for row in record.get("templates", []):
            if row.get("created"): continue
            seq = self.u.load_asset(row["package"]); binding = self._binding_guid(seq, row["guid"])
            template = binding.get_object_template(); root = template.get_editor_property("root_component")
            comp = template.get_editor_property("spot_light_component"); before = row["before"]
            root.set_editor_property("relative_location", self.u.Vector(*before["loc"]))
            root.set_editor_property("relative_rotation", self.u.Rotator(roll=before["rot"][0],
                                                                           pitch=before["rot"][1], yaw=before["rot"][2]))
            for prop, value in before["props"].items(): comp.set_editor_property(prop, value)
        for row in reversed(record["created_bindings"]):
            seq = self.u.load_asset(row["package"]); binding = self._binding_guid(seq, row["guid"])
            if binding.get_object_template() is not None:
                seq.remove_spawnable(binding.get_id())
            else:
                if list(binding.get_tracks()): raise Stop("REVERT_CREATED_BINDING_HAS_TRACKS|%s" % row["guid"])
                seq.remove_possessable(binding.get_id())
        actual = sorted(self.census()["content"] + self.census()["maps"])
        if actual != sorted(record["packages"]): raise Stop("REVERT_DIRTY_SCOPE|%s" % actual)
        for package in record["packages"]:
            if not self.u.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True): raise Stop("REVERT_SAVE|%s" % package)
        if self.census() != {"content": [], "maps": []}: raise Stop("REVERT_DIRTY_AFTER_SAVE")
        self._verify_record(record, False)
        archived = path + ".reverted-" + run; os.rename(path, archived)
        return {"packages": record["packages"], "backup": folder, "backup_files": backups, "archived": archived}


def main(args, backend=None, root=None):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or ("J144-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    backend = backend or UnrealBackend(root)
    if mode not in CONFIRMS: backend.fail("%s_FAILED|run=%s|MODE|%s" % (TOOL, run, mode))
    try:
        params = merged_params(args.get("params")); backend.preflight(mode, args.get("confirm"))
        n = params["interaction"]
        if mode == "DRY":
            report = backend.build_report(params, run)
            report_path = os.path.join(backend.root, "job144_dry_I%d_%s.json" % (n, run))
            _write(report_path, report)
            _write(os.path.join(backend.root, "job144_plan_I%d.json" % n),
                   {"params": params, "plan_digest": report["plan"]["digest"], "report": report_path})
            if backend.census() != {"content": [], "maps": []}: raise Stop("DRY_DIRTIED")
            backend.log("JOB144_INTERACTION_HANGAR_DRY_OK|run=%s|interaction=I%d|mutated=0|actors=%d|hide=%d|warnings=%d|digest=%s|dirty=0|report=%s" %
                        (run, n, len(report["plan"]["inventory"]["all"]), len(report["plan"]["visibility"]["actors"]),
                         len(report["plan"]["warnings"]), report["plan"]["digest"], report_path))
            return report
        if mode == "APPLY":
            pinned = _read(os.path.join(backend.root, "job144_plan_I%d.json" % n))
            report = backend.build_report(params, run)
            if pinned["params"] != params: raise Stop("DRY_ARGS_DRIFT|RERUN_DRY")
            if pinned["plan_digest"] != report["plan"]["digest"]: raise Stop("DRY_STATE_DRIFT|RERUN_DRY")
            if not report["plan"]["visibility"]["actors"]: raise Stop("HIDE_LIST_EMPTY|REVIEW_DRY_CENSUS")
            if report["plan"]["warnings"]: raise Stop("PLAN_WARNINGS|%s" % report["plan"]["warnings"])
            record = backend.apply(report, run)
            backend.log("JOB144_INTERACTION_HANGAR_APPLY_OK|run=%s|interaction=I%d|saved=%s|hide=%d|backup=%s|record=%s|dirty=0" %
                        (run, n, ",".join(record["packages"]), len(report["plan"]["visibility"]["actors"]),
                         record["backup"], os.path.join(backend.root, "job144_record_I%d.json" % n)))
            return record
        result = backend.revert(n, run)
        backend.log("JOB144_INTERACTION_HANGAR_REVERT_OK|run=%s|interaction=I%d|saved=%s|backup=%s|record=%s|dirty=0" %
                    (run, n, ",".join(result["packages"]), result["backup"], result["archived"]))
        return result
    except (Stop, PlanError) as exc:
        backend.fail("%s_%s_FAILED|run=%s|%s" % (TOOL, mode, run, exc))
