"""INTERACTION CURTAIN PROBE (6 Oct, offline-written, NOT RUN): READ-ONLY census of the curtain sleight in I1-I5.

Why: Gary (6 Oct) sees each Interaction push the camera into the hangar's back wall. Per curtain_sleight.py:8-23 each
Interaction should fly in "Sleight Hangar Drape" (a spawnable GeometryCacheActor, GC_CurtainDrop_Opening, HOLD sample)
at 3-7 s while "S<N> Sleight Hangar Camera" (a level CineCamera attached to "S<N> Hangar Root", keyed root-RELATIVE)
pushes in to frame it at 3-11 s. The drape is keyed in WORLD space (curtain_sleight.py:2059-2079, shadow_play_spot.py:16).

Per Interaction N it reads (load_asset only; the sequences are never opened in Sequencer, never evaluated/scrubbed):
  - playback range, display/tick rate, CST markers, every binding (spawnable or possessable, parent, tracks);
  - the drape binding: spawnable?, template class, template root relative loc/rot/scale, actor/component hidden flags,
    GeometryCacheComponent geometry_cache / running / looping / visible / hidden_in_game / override_materials /
    material slot 0; its spawn-track bool keys + default; GC track sections (range, start/end offsets, play rate,
    reverse, asset); transform channel keys + DEFAULTS (an unkeyed scale channel evaluates 0, scene_exit_block.py:775
    via curtain_sleight.py:1790-1791);
  - the cache asset: exists, loads, start/end frame, materials;
  - the hangar camera: level actor, attach parent (the hangar root) live transform vs the sleight record's root_pose
    (ROOT_MOVED: the camera follows the root, the world-keyed drape does not), filmback, transform + focal keys;
  - the twin lantern: level actor, light props, intensity keys;
  - camera-cut sections and the camera each resolves to (resolve_binding_id, memory ue58-geometrycache-sequencer-traps);
  - GEOMETRY at sampled frames 0..sleight (every 0.5 s + the CST beats): camera world pose (keys composed with the live
    root), drape world pose (keys), the drape centre/card corners in camera space (in frame? off-axis deg), the camera's
    x in the drape frame (>= -50 cm = at/through the curtain plane), spawned?, GC section active?;
  - Master: the Interaction's Scene-track section (by the record's cue_guid) and the preceding Scene's, completion mode,
    and inside that Scene sequence any HangarRise sub-section's completion mode (curtain plan G12 [inf]).
Never saves, never GetBoundObjects (open-range crash, memory puss-mcp-python-crashes-the-editor), never opens/scrubs the
Master, never pokes a spawned actor or template (reads only), no unreal objects in module globals.
Output: Saved/CodexConductor/interaction_curtain_probe_<run>.json and ONE marker
  INTERACTION_CURTAIN_PROBE_OK|run=<id>|json=<path>|census_unchanged=<bool>|I<n>=<flags>...
or INTERACTION_CURTAIN_PROBE_FAILED|run=<id>|reason=... ; per-read failures INTERACTION_CURTAIN_PROBE_READ_ERROR (warning).
Interpolation of transform keys between key frames is LINEAR here (curtain_sleight keys every frame with LINEAR
interpolation, curtain_sleight.py:1792-1797) - an approximation, not a Sequencer evaluation.
"""
import datetime
import json
import math
import os
import re
import traceback

import unreal

TOOL = "interaction_curtain_probe"
MARK = "INTERACTION_CURTAIN_PROBE"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SEQ_DIR = "/Game/InfinityStage/Interactions"
SEQS = {1: "LS_Interaction_01_WashingTheBoy", 2: "LS_Interaction_02_Turnips", 3: "LS_Interaction_03_ForgetsHisName",
        4: "LS_Interaction_04_GetsAName", 5: "LS_Interaction_05_BecomesKing"}            # curtain_sleight.py:65-66
GC_PATH = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"                           # curtain_sleight.py:67
DRAPE = "Sleight Hangar Drape"                                                           # curtain_sleight.py:95
HANGAR_CAMERA = "S%d Sleight Hangar Camera"                                              # curtain_sleight.py:92
MOUTH_CAMERA = "I%d Sleight Mouth Camera"
LANTERN = "S%d Sleight Twin Lantern"
ROOT_LABEL = "S%d Hangar Root"                                                           # curtain_sleight.py:72
RECORD = "curtain_sleight_record_I%d.json"
CACHE_FPS = 30.0                                                                         # curtain_sleight.py:100
POSE = {"Location.X": "x", "Location.Y": "y", "Location.Z": "z", "Rotation.X": "roll", "Rotation.Y": "pitch",
        "Rotation.Z": "yaw", "Scale.X": "sx", "Scale.Y": "sy", "Scale.Z": "sz"}           # curtain_sleight.py:104-105
DEFAULT_CARD = {"rel": [-42.8, 0.0, 510.0], "w": 480.0, "h": 270.0}                      # record plan.hangar_card


def _here():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


class Probe(object):
    def __init__(self, run):
        self.run = run
        self.errors = []

    def read(self, what, fn, default=None):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - logged and reported, never raised
            msg = "%s: %r" % (what, exc)
            self.errors.append(msg)
            unreal.log_warning("%s_READ_ERROR|run=%s|%s" % (MARK, self.run, msg))
            return default


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _plain(v):
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    if isinstance(v, unreal.Vector):
        return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]
    if isinstance(v, unreal.Rotator):
        return {"roll": round(float(v.roll), 4), "pitch": round(float(v.pitch), 4), "yaw": round(float(v.yaw), 4)}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if hasattr(v, "get_path_name"):
        return _path(v)
    return str(v)


def _xf_plain(xf):
    r = xf.rotation.rotator()
    return {"loc": _plain(xf.translation), "rot": _plain(r), "scale": _plain(xf.scale3d)}


def _norm_channel(name):
    return re.sub(r"_\d+$", "", str(name))     # memory ue58-sequencer-read-traps: Location.Y_183


def _channels(section):
    """{normalised name: {"keys": [[display_frame, value]], "default": v|None}}."""
    out = {}
    for ch in section.get_all_channels():
        name = _norm_channel(ch.get_editor_property("channel_name"))
        row = {"keys": [], "default": None}
        try:
            for k in ch.get_keys():
                f = int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value)
                v = k.get_value()
                row["keys"].append([f, float(v) if not isinstance(v, bool) else bool(v)])
        except Exception:  # noqa: BLE001 - channel without keys
            pass
        try:
            if (not hasattr(ch, "has_default")) or ch.has_default():
                d = ch.get_default()
                row["default"] = float(d) if not isinstance(d, bool) else bool(d)
        except Exception:  # noqa: BLE001
            pass
        row["keys"].sort(key=lambda r: r[0])
        out[name] = row
    return out


def _span(sec):
    a = int(sec.get_start_frame()) if sec.has_start_frame() else None
    b = int(sec.get_end_frame()) if sec.has_end_frame() else None
    return [a, b]


def interp(keys, frame, default=None):
    """Linear between keys, hold outside (approximation; see module docstring)."""
    if not keys:
        return default
    if frame <= keys[0][0]:
        return keys[0][1]
    if frame >= keys[-1][0]:
        return keys[-1][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= frame <= f1:
            if isinstance(v0, bool):
                return v0 if frame < f1 else v1
            return v0 + (v1 - v0) * (frame - f0) / float(f1 - f0) if f1 != f0 else v1
    return keys[-1][1]


def step(keys, frame, default=None):
    v = default
    for f, val in keys:
        if f <= frame:
            v = val
    return v


def _track_rows(probe, binding, label):
    rows = []
    for t in binding.get_tracks():
        cls = t.get_class().get_name()
        row = {"class": cls, "name": str(t.get_display_name()), "sections": []}
        for s in t.get_sections():
            srow = {"range": probe.read("%s %s range" % (label, cls), lambda: _span(s)),
                    "active": probe.read("%s %s active" % (label, cls), lambda: bool(s.is_active()))}
            if cls == "MovieSceneGeometryCacheTrack":
                prm = s.get_editor_property("params")
                srow["gc"] = {
                    "asset": probe.read("gc asset", lambda: _path(prm.get_editor_property("geometry_cache_asset"))),
                    "start_frame_offset": probe.read("gc so", lambda: int(prm.get_editor_property("start_frame_offset").value)),
                    "end_frame_offset": probe.read("gc eo", lambda: int(prm.get_editor_property("end_frame_offset").value)),
                    "first_loop_start_frame_offset": probe.read("gc flo", lambda: int(
                        prm.get_editor_property("first_loop_start_frame_offset").value)),
                    "play_rate": probe.read("gc rate", lambda: float(prm.get_editor_property("play_rate"))),
                    "reverse": probe.read("gc reverse", lambda: bool(prm.get_editor_property("reverse")))}
            else:
                srow["channels"] = probe.read("%s %s channels" % (label, cls), lambda: _channels(s), {})
            row["sections"].append(srow)
        rows.append(row)
    return rows


def _template_facts(probe, binding):
    tmpl = binding.get_object_template()
    if tmpl is None:
        return {"template": None}
    out = {"class": tmpl.get_class().get_name()}
    root = probe.read("tmpl root", lambda: tmpl.get_editor_property("root_component"))
    if root is not None:
        for prop in ("relative_location", "relative_rotation", "relative_scale3d", "visible", "hidden_in_game"):
            out["root_" + prop] = probe.read("tmpl root " + prop, lambda: _plain(root.get_editor_property(prop)))
    for prop in ("hidden", "is_editor_only_actor"):
        out["actor_" + prop] = probe.read("tmpl actor " + prop, lambda: _plain(tmpl.get_editor_property(prop)))
    gc = probe.read("tmpl gc comp", lambda: tmpl.get_editor_property("geometry_cache_component"))
    if gc is not None:
        for prop in ("geometry_cache", "running", "looping", "visible", "hidden_in_game", "cast_shadow",
                     "start_time_offset", "play_back_speed", "override_materials"):
            out["gc_" + prop] = probe.read("tmpl gc " + prop, lambda: _plain(gc.get_editor_property(prop)))
        out["gc_material0"] = probe.read("tmpl gc material0", lambda: _path(gc.get_material(0)))
    return out


def _cache_facts(probe):
    out = {"path": GC_PATH,
           "exists": probe.read("cache exists", lambda: bool(unreal.EditorAssetLibrary.does_asset_exist(GC_PATH)))}
    cache = probe.read("cache load", lambda: unreal.load_asset(GC_PATH))
    out["loaded"] = cache is not None
    if cache is not None:
        out["start_frame"] = probe.read("cache start", lambda: int(cache.get_editor_property("start_frame")))
        out["end_frame"] = probe.read("cache end", lambda: int(cache.get_editor_property("end_frame")))
        out["materials"] = probe.read("cache materials", lambda: [_path(m) for m in cache.get_editor_property("materials")])
        if out.get("start_frame") is not None and out.get("end_frame") is not None:
            # [inf] 30 fps cache (CACHE_FPS); the sleight record's drape_cache.duration_ticks = 264000 for 330 frames
            out["duration_ticks_inferred"] = int(round((out["end_frame"] - out["start_frame"]) / CACHE_FPS * 24000.0))
    return out


def _actor_index():
    index = {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        index.setdefault(str(a.get_actor_label()), []).append(a)
    return index


def _light_facts(probe, actor):
    out = {"class": actor.get_class().get_name(), "world": _xf_plain(actor.get_actor_transform())}
    comp = probe.read("light comp", lambda: actor.get_component_by_class(unreal.LightComponent))
    if comp is not None:
        for prop in ("intensity", "intensity_units", "attenuation_radius", "inner_cone_angle", "outer_cone_angle",
                     "visible", "hidden_in_game", "cast_shadows", "affects_world", "mobility", "temperature",
                     "use_temperature"):
            out[prop] = probe.read("light " + prop, lambda: _plain(comp.get_editor_property(prop)))
    return out


def _xf(loc, roll, pitch, yaw):
    return unreal.Transform(location=unreal.Vector(*loc), rotation=unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw),
                            scale=unreal.Vector(1.0, 1.0, 1.0))


def _pose_at(ch, frame):
    def g(name, d=0.0):
        row = ch.get(name) or {}
        return interp(row.get("keys") or [], frame, row.get("default") if row.get("default") is not None else d)
    return {"loc": [g("Location.X"), g("Location.Y"), g("Location.Z")], "roll": g("Rotation.X"),
            "pitch": g("Rotation.Y"), "yaw": g("Rotation.Z"),
            "scale": [g("Scale.X", None), g("Scale.Y", None), g("Scale.Z", None)]}


def _first_channels(tracks, cls):
    for t in tracks:
        if t["class"] == cls and t["sections"]:
            return t["sections"][0].get("channels") or {}, t["sections"][0].get("range")
    return {}, None


def geometry(probe, n, fps, beats, cam_ch, focal_keys, root_xf, drape_ch, drape_spawn, gc_secs, filmback, card):
    """Per sampled frame: camera world (root-relative keys o live root), drape world (world keys), drape points in
    camera space, camera x in the drape frame."""
    hw = filmback[0] / 2.0 if filmback else 23.76 / 2.0
    hh = filmback[1] / 2.0 if filmback else 13.365 / 2.0
    last = beats.get("CST sleight", int(round(50 * fps)))
    frames = sorted(set(list(range(0, last + 1, max(1, int(round(fps / 2.0))))) +
                        [v for v in beats.values() if v <= last]))
    rows = []
    for f in frames:
        row = {"frame": f, "s": round(f / fps, 3)}
        try:
            cp = _pose_at(cam_ch, f)
            cam_rel = _xf(cp["loc"], cp["roll"], cp["pitch"], cp["yaw"])
            cam = unreal.MathLibrary.compose_transforms(cam_rel, root_xf) if root_xf is not None else cam_rel
            dp = _pose_at(drape_ch, f)
            drape = _xf(dp["loc"], dp["roll"], dp["pitch"], dp["yaw"])
            focal = interp(focal_keys, f, None) or 35.0
            pts = {"centre": [card["rel"][0], card["rel"][1], card["rel"][2]]}
            for nm, sy, sz in (("ul", -1, 1), ("ur", 1, 1), ("ll", -1, -1), ("lr", 1, -1)):
                pts[nm] = [card["rel"][0], card["rel"][1] + sy * card["w"] / 2.0, card["rel"][2] + sz * card["h"] / 2.0]
            vis = {}
            for nm, p in pts.items():
                w = unreal.MathLibrary.transform_location(drape, unreal.Vector(*p))
                c = unreal.MathLibrary.inverse_transform_location(cam, w)
                x, y, z = float(c.x), float(c.y), float(c.z)
                inside = x > 1.0 and abs(y) / x <= hw / focal and abs(z) / x <= hh / focal
                vis[nm] = {"cam_xyz": [round(x, 1), round(y, 1), round(z, 1)], "in_frame": inside,
                           "off_axis_deg": round(math.degrees(math.atan2(math.hypot(y, z), x)), 2)}
            cam_in_drape = unreal.MathLibrary.inverse_transform_location(drape, cam.translation)
            row.update({"cam_world": _xf_plain(cam), "drape_world": {"loc": [round(v, 1) for v in dp["loc"]],
                                                                     "yaw": round(dp["yaw"], 3), "scale": dp["scale"]},
                        "focal_mm": round(focal, 2), "drape_points": vis,
                        "cam_x_in_drape_cm": round(float(cam_in_drape.x), 1),
                        "cam_through_curtain": float(cam_in_drape.x) >= -50.0,
                        "drape_spawned": step(drape_spawn.get("keys") or [], f, drape_spawn.get("default")),
                        "gc_section_active": any(s["range"][0] is not None and s["range"][0] <= f
                                                 and (s["range"][1] is None or f < s["range"][1]) for s in gc_secs)})
        except Exception as exc:  # noqa: BLE001
            row["error"] = repr(exc)
            probe.errors.append("I%d geometry f=%d: %r" % (n, f, exc))
        rows.append(row)
    return rows


def _master_facts(probe, master, cue_guid, seq_path):
    out = {}
    tick = _rate(master.get_tick_resolution())
    secs = []
    for t in master.get_tracks():
        if t.get_class().get_name() != "MovieSceneInfinitySceneTrack":
            continue
        for s in t.get_sections():
            secs.append(s)
    secs.sort(key=lambda s: s.get_start_frame_seconds() if s.has_start_frame() else -1.0)
    for i, s in enumerate(secs):
        g = probe.read("scene block guid", lambda: _guid(s.get_editor_property("block_guid")))
        sub = probe.read("scene sub seq", lambda: s.get_sequence())
        if g != cue_guid and _path(sub) != seq_path:
            continue
        out["interaction_section"] = _section_row(probe, s, tick)
        if i > 0:
            prev = secs[i - 1]
            out["preceding_section"] = _section_row(probe, prev, tick)
            pseq = probe.read("prev sub seq", lambda: prev.get_sequence())
            if pseq is not None:
                out["preceding_rise_nests"] = _rise_nests(probe, pseq)
        break
    return out


def _section_row(probe, s, tick):
    row = {"block_guid": probe.read("block guid", lambda: _guid(s.get_editor_property("block_guid"))),
           "sequence": probe.read("sub seq path", lambda: _path(s.get_sequence())),
           "range_ticks_from_seconds": [int(round(s.get_start_frame_seconds() * tick)) if s.has_start_frame() else None,
                                        int(round(s.get_end_frame_seconds() * tick)) if s.has_end_frame() else None]}
    eo = probe.read("eval options", lambda: s.get_editor_property("eval_options"))
    if eo is not None:
        row["completion_mode"] = probe.read("completion", lambda: str(eo.get_editor_property("completion_mode")))
    return row


def _rise_nests(probe, seq):
    rows = []
    for t in seq.get_tracks():
        if t.get_class().get_name() not in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
            continue
        for s in t.get_sections():
            sub = probe.read("nest seq", lambda: s.get_sequence())
            name = _path(sub) or ""
            if "Hangar" not in name and "Rise" not in name:
                continue
            eo = probe.read("nest eval", lambda: s.get_editor_property("eval_options"))
            rows.append({"sequence": name, "range": probe.read("nest range", lambda: _span(s)),
                         "completion_mode": probe.read("nest completion", lambda: str(
                             eo.get_editor_property("completion_mode"))) if eo is not None else None})
    return rows


def probe_interaction(probe, n, index, master, cache_facts):
    out = {"n": n, "sequence": "%s/%s" % (SEQ_DIR, SEQS[n]), "flags": []}
    rec_path = os.path.join(_here(), RECORD % n)
    rec = json.load(open(rec_path, encoding="utf-8")) if os.path.exists(rec_path) else None
    out["record"] = {"exists": rec is not None, "run": rec.get("run") if rec else None,
                     "root_pose": rec.get("root_pose") if rec else None}
    seq = probe.read("I%d load" % n, lambda: unreal.load_asset(out["sequence"]))
    if seq is None:
        out["flags"].append("SEQUENCE_DID_NOT_LOAD")
        return out
    fps = probe.read("I%d fps" % n, lambda: _rate(seq.get_display_rate()), 25.0)
    out["display_fps"] = fps
    out["tick_rate"] = probe.read("I%d tick" % n, lambda: _rate(seq.get_tick_resolution()))
    out["playback"] = probe.read("I%d playback" % n, lambda: [int(seq.get_playback_start()), int(seq.get_playback_end())])
    markers = probe.read("I%d markers" % n, lambda: [
        [str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)]
        for m in seq.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)], [])
    out["markers"] = markers
    beats = {lab: f for lab, f in markers if lab.startswith("CST ")}
    spawn_guids = set(probe.read("I%d spawnables" % n, lambda: [_guid(b.get_id()) for b in seq.get_spawnables()], []))
    bindings = {}
    for b in probe.read("I%d bindings" % n, lambda: list(seq.get_bindings()), []):
        name = str(b.get_display_name())
        parent = probe.read("parent", lambda: b.get_parent())
        row = {"guid": _guid(b.get_id()), "spawnable": _guid(b.get_id()) in spawn_guids,
               "parent": str(parent.get_display_name()) if parent is not None and parent.is_valid() else "",
               "tracks": _track_rows(probe, b, "I%d %s" % (n, name))}
        if row["spawnable"]:
            row["template"] = probe.read("I%d %s template" % (n, name), lambda: _template_facts(probe, b), {})
        bindings.setdefault(name, []).append(row)
    out["binding_names"] = sorted(bindings)
    # --- drape
    drapes = bindings.get(DRAPE, [])
    out["drape_binding_count"] = len(drapes)
    drape = drapes[0] if len(drapes) == 1 else None
    if drape is None:
        out["flags"].append("DRAPE_BINDING_COUNT_%d" % len(drapes))
    else:
        out["drape"] = drape
        if not drape["spawnable"]:
            out["flags"].append("DRAPE_NOT_SPAWNABLE")
        tf = drape.get("template") or {}
        if tf.get("gc_running") is False:
            out["flags"].append("DRAPE_RUNNING_FALSE(frozen frame 0)")
        if tf.get("gc_geometry_cache") not in (GC_PATH,):
            out["flags"].append("DRAPE_TEMPLATE_CACHE=%s" % tf.get("gc_geometry_cache"))
        for k in ("gc_visible", "root_visible"):
            if tf.get(k) is False:
                out["flags"].append("DRAPE_%s_FALSE" % k.upper())
        for k in ("gc_hidden_in_game", "root_hidden_in_game", "actor_hidden"):
            if tf.get(k) is True:
                out["flags"].append("DRAPE_%s" % k.upper())
    d_tracks = drape["tracks"] if drape else []
    drape_ch, drape_rng = _first_channels(d_tracks, "MovieScene3DTransformTrack")
    for axis in ("Scale.X", "Scale.Y", "Scale.Z"):
        row = drape_ch.get(axis) or {}
        if drape and not row.get("keys") and not row.get("default"):
            out["flags"].append("DRAPE_%s_UNKEYED_NO_DEFAULT(evaluates 0)" % axis)
    spawn_ch, _r = _first_channels(d_tracks, "MovieSceneSpawnTrack")
    drape_spawn = next(iter(spawn_ch.values()), {}) if spawn_ch else {}
    gc_secs = [s for t in d_tracks if t["class"] == "MovieSceneGeometryCacheTrack" for s in t["sections"]]
    out["drape_gc_sections"] = gc_secs
    for s in gc_secs:
        gc = s.get("gc") or {}
        if gc.get("asset") != GC_PATH:
            out["flags"].append("DRAPE_SECTION_CACHE=%s" % gc.get("asset"))
        dur = cache_facts.get("duration_ticks_inferred")
        if dur and gc.get("start_frame_offset") is not None and gc.get("end_frame_offset") is not None:
            window = dur - gc["start_frame_offset"] - gc["end_frame_offset"]
            s["hold_window_ticks_inferred"] = window
            if window <= 0:
                out["flags"].append("DRAPE_GC_WINDOW_%d_TICKS" % window)
    if drape and not gc_secs:
        out["flags"].append("DRAPE_NO_GC_SECTION")
    # --- hangar camera (level actor + binding)
    cam_label = HANGAR_CAMERA % n
    cam_actors = index.get(cam_label, [])
    out["hangar_camera_actors"] = len(cam_actors)
    root_xf, filmback = None, None
    if len(cam_actors) == 1:
        cam = cam_actors[0]
        parent = probe.read("cam parent", lambda: cam.get_attach_parent_actor())
        out["hangar_camera"] = {"world_now": _xf_plain(cam.get_actor_transform()),
                                "attach_parent": str(parent.get_actor_label()) if parent is not None else None}
        comp = probe.read("cam comp", lambda: cam.get_cine_camera_component())
        if comp is not None:
            fb = probe.read("filmback", lambda: comp.get_editor_property("filmback"))
            if fb is not None:
                filmback = [float(fb.get_editor_property("sensor_width")), float(fb.get_editor_property("sensor_height"))]
            out["hangar_camera"]["filmback_mm"] = filmback
        if parent is not None:
            root_xf = parent.get_actor_transform()
            out["hangar_root_now"] = _xf_plain(root_xf)
            if str(parent.get_actor_label()) != ROOT_LABEL % n:
                out["flags"].append("CAMERA_PARENT_IS_%s" % parent.get_actor_label())
        else:
            out["flags"].append("HANGAR_CAMERA_NOT_ATTACHED(keys are root-relative)")
    else:
        out["flags"].append("HANGAR_CAMERA_ACTORS_%d" % len(cam_actors))
    roots = index.get(ROOT_LABEL % n, [])
    out["hangar_root_actors"] = len(roots)
    if roots and root_xf is None:
        out["hangar_root_now"] = _xf_plain(roots[0].get_actor_transform())
    rp = (rec or {}).get("root_pose")
    if rp and out.get("hangar_root_now"):
        now = out["hangar_root_now"]
        dl = math.sqrt(sum((now["loc"][i] - rp["loc"][i]) ** 2 for i in range(3)))
        dy = abs(((now["rot"]["yaw"] - rp["rot"][2]) + 180.0) % 360.0 - 180.0)
        dp = abs(now["rot"]["pitch"] - rp["rot"][1])
        out["root_vs_record"] = {"d_loc_cm": round(dl, 2), "d_yaw_deg": round(dy, 4), "d_pitch_deg": round(dp, 4)}
        if dl > 0.5 or dy > 0.05 or dp > 0.05:
            out["flags"].append("ROOT_MOVED_SINCE_SLEIGHT(%.1fcm,%.2fdeg)" % (dl, dy))
    if out.get("hangar_root_now") and (abs(out["hangar_root_now"]["rot"]["pitch"]) > 1.0
                                       or out["hangar_root_now"]["loc"][2] < -500.0):
        out["flags"].append("ROOT_NOT_LANDED_IN_LEVEL")
    cam_b = (bindings.get(cam_label) or [None])[0]
    cam_ch, _r = _first_channels(cam_b["tracks"] if cam_b else [], "MovieScene3DTransformTrack")
    if not cam_ch:
        out["flags"].append("HANGAR_CAMERA_NO_TRANSFORM_TRACK")
    focal_keys = []
    for nm, rows in bindings.items():
        if nm.startswith(cam_label) and nm != cam_label:
            for t in rows[0]["tracks"]:
                if t["class"] == "MovieSceneFloatTrack" and t["sections"]:
                    for cname, crow in (t["sections"][0].get("channels") or {}).items():
                        vals = [v for _f, v in crow.get("keys") or []]
                        if vals and min(vals) >= 5.0 and max(vals) <= 300.0:   # focal mm, not focus cm
                            focal_keys = crow["keys"]
    # --- cuts
    cuts = []
    for t in probe.read("cut tracks", lambda: list(seq.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)), []):
        for s in t.get_sections():
            proxy = probe.read("cut resolve", lambda: seq.resolve_binding_id(s.get_camera_binding_id()))
            cuts.append({"range": probe.read("cut range", lambda: _span(s)),
                         "camera": probe.read("cut name", lambda: str(proxy.get_display_name())) if proxy else None,
                         "active": probe.read("cut active", lambda: bool(s.is_active()))})
    out["cuts"] = cuts
    if not any(c.get("camera") == cam_label for c in cuts):
        out["flags"].append("NO_CUT_ON_HANGAR_CAMERA")
    # --- lantern
    lan = index.get(LANTERN % n, [])
    out["lantern_actors"] = len(lan)
    if len(lan) == 1:
        out["lantern"] = probe.read("lantern facts", lambda: _light_facts(probe, lan[0]), {})
    else:
        out["flags"].append("LANTERN_ACTORS_%d" % len(lan))
    lb = [nm for nm in bindings if nm.startswith(LANTERN % n)]
    out["lantern_bindings"] = {nm: bindings[nm][0]["tracks"] for nm in lb}
    # --- geometry
    card = DEFAULT_CARD
    if rec:
        hc = (rec.get("plan") or {}).get("hangar_card") or {}
        if hc.get("rel_drape") and hc.get("size"):
            card = {"rel": hc["rel_drape"], "w": float(hc["size"][1]), "h": float(hc["size"][2])}
    out["card_used"] = card
    if cam_ch and drape_ch:
        geo = geometry(probe, n, fps, beats, cam_ch, focal_keys, root_xf, drape_ch, drape_spawn, gc_secs, filmback, card)
        out["geometry"] = geo
        push_end = beats.get("CST curtain hung", int(round(7 * fps))) + int(round(4 * fps))   # 11 s
        at = [g for g in geo if "drape_points" in g and g["frame"] >= push_end]
        if at:
            g0 = at[0]
            out["at_push_end"] = {"frame": g0["frame"], "centre_in_frame": g0["drape_points"]["centre"]["in_frame"],
                                  "corners_in_frame": sum(1 for k in ("ul", "ur", "ll", "lr")
                                                          if g0["drape_points"][k]["in_frame"]),
                                  "cam_x_in_drape_cm": g0["cam_x_in_drape_cm"],
                                  "off_axis_deg": g0["drape_points"]["centre"]["off_axis_deg"],
                                  "drape_spawned": g0["drape_spawned"], "gc_active": g0["gc_section_active"]}
            if not g0["drape_points"]["centre"]["in_frame"]:
                out["flags"].append("DRAPE_CENTRE_OUT_OF_FRAME_AT_PUSH_END")
            if g0["cam_through_curtain"]:
                out["flags"].append("CAMERA_AT_OR_THROUGH_CURTAIN_PLANE")
            if g0["drape_spawned"] is False:
                out["flags"].append("DRAPE_NOT_SPAWNED_AT_PUSH_END")
    # --- master
    if master is not None and rec:
        out["master"] = probe.read("I%d master" % n, lambda: _master_facts(probe, master, rec.get("cue_guid"),
                                                                           out["sequence"]), {})
    return out


def main():
    run = "ICURT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    probe = Probe(run)
    census0 = probe.read("census before", _census)
    report = {"tool": TOOL, "run": run, "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "census_before": census0, "interactions": {}}
    report["pie_running"] = probe.read("pie", lambda: unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_game_world() is not None)
    cache_facts = probe.read("cache facts", lambda: _cache_facts(probe), {})
    report["cache"] = cache_facts
    index = probe.read("actor index", _actor_index, {})
    master = probe.read("load master", lambda: unreal.load_asset(MASTER_PATH))
    summary = []
    for n in sorted(SEQS):
        row = probe.read("I%d" % n, lambda: probe_interaction(probe, n, index, master, cache_facts),
                         {"n": n, "flags": ["PROBE_EXCEPTION"]})
        report["interactions"]["I%d" % n] = row
        ap = row.get("at_push_end") or {}
        summary.append("I%d=%s;centre_in_frame=%s;cam_x_drape=%s" % (
            n, ",".join(row.get("flags") or []) or "clean", ap.get("centre_in_frame"), ap.get("cam_x_in_drape_cm")))
    census1 = probe.read("census after", _census)
    report["census_after"] = census1
    report["census_unchanged"] = census0 == census1
    report["read_errors"] = probe.errors
    out = os.path.join(_here(), "%s_%s.json" % (TOOL, run))
    try:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, sort_keys=True, default=str)
    except Exception as exc:  # noqa: BLE001
        unreal.log_error("%s_FAILED|run=%s|reason=JSON_WRITE %r" % (MARK, run, exc))
        return
    unreal.log("%s_OK|run=%s|json=%s|census_unchanged=%s|read_errors=%d|cache_loaded=%s|%s" % (
        MARK, run, out, report["census_unchanged"], len(probe.errors), cache_facts.get("loaded"), "|".join(summary)))


try:
    main()
except Exception:  # noqa: BLE001 - one failure marker; nothing written to Unreal
    unreal.log_error("%s_FAILED|reason=%s" % (MARK, traceback.format_exc().replace("\n", " / ")))
