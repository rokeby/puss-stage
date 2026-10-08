"""P9 INTERACTION SHADOW TRANSITION (8 Oct 2026; offline-authored, never run in Unreal here).

One guarded DRY/APPLY/REVERT tool for I1..I5.  The Show asset resolves the selected
Interaction sequence.  The sequence is the only package this tool mutates:

* the two legacy white-card spawnables are made permanently unspawned; a missing
  card (I4 hangar today) is accepted.  Bindings are retained so REVERT can restore
  their exact GUIDs and tracks;
* the matched Shadow Play Spot pair is created when absent or rewritten in place;
* the pair copies its pose and light settings from a reference Interaction (I4 by
  default), fades up over ``fade_seconds`` (Gary-owned, default 4.0), and exposes
  ``light_function_material`` for the animated gobo;
* APPLY/REVERT back up the named sequence and write a transaction record before
  mutation, save only that sequence, then perform structural and semantic read-back.

Globals set by interaction_shadow_transition_run.py:
  IST_INTERACTION=1..5, IST_MODE=DRY|APPLY|REVERT,
  IST_CONFIRM="<MODE> I<n>", IST_PARAMS=dict, IST_RUN_ID optional.

Success markers: INTERACTION_SHADOW_TRANSITION_<MODE>_OK|run=... .
Importing under system Python never imports Unreal and never mutates project data.
"""
import copy
import datetime
import hashlib
import json
import math
import os
import shutil
import struct
import zlib

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None


def _here():
    if unreal is not None:
        saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        return os.path.join(saved, "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _load_definitions(filename, marker):
    path = os.path.join(_here(), filename)
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    cut = source.rindex(marker)
    ns = {"__name__": filename.replace(".py", "_lib_for_ist"), "__file__": path}
    exec(compile(source[:cut], path, "exec"), ns)  # reviewed project tool; definitions only
    ns["SOURCE_SHA256"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return ns


SPS = _load_definitions("shadow_play_spot.py", "if unreal is not None:")
CS = SPS["CS"]
SHOW_PATH = CS["SHOW_PATH"]
SEQ_DIR = CS["SEQ_DIR"]
SEQS = CS["SEQS"]
EXPECTED_WORLD = CS["EXPECTED_WORLD"]
CARD_NAMES = (CS["BINDING_NAMES"]["hangar_card"], CS["BINDING_NAMES"]["mouth_card"])
SPOT_NAMES = SPS["SPOT_NAMES"]
SIDES = SPS["SIDES"]
SPOT_TRACK = SPS["TRACK_NAME"]
MODES = ("DRY", "APPLY", "REVERT")
RECORD_PATTERN = "interaction_shadow_transition_record_I%d.json"
PLAN_PATTERN = "interaction_shadow_transition_plan_I%d.json"
DRY_PATTERN = "interaction_shadow_transition_I%d_dry.json"
REVERT_PATTERN = "interaction_shadow_transition_revert_%s.json"
LEGACY_SPOT_RECORD = "shadow_play_spot_record_I%d.json"
SLEIGHT_RECORD = "curtain_sleight_record_I%d.json"

DEFAULTS = {
    "reference_interaction": 4,
    "fade_seconds": 4.0,       # Gary-owned look value
    "fade_out_seconds": 1.0,   # Gary-owned look value
    "light_function_material": None,
    "spawn_lead_frames": 25,
}

CLAIMS = [
    {"tier": "declaration-proven", "claim": "Cards and spots are sequence spawnables; only the selected Interaction sequence is written.",
     "cite": "Saved/CodexConductor/curtain_sleight.py:95-96,2080-2083; Saved/CodexConductor/shadow_play_spot.py:7-10"},
    {"tier": "measured", "claim": "I4's hangar card was already absent on 7 Oct while its mouth card and spot pair remained.",
     "cite": "Docs/Conductor/SCENE_EXIT_SHADOW_CURTAIN_PLAN_2026-10-07.md:10-23"},
    {"tier": "declaration-proven", "claim": "The former spot fade-up was frames 175-187 at 25 fps.",
     "cite": "Docs/Conductor/SCENE_EXIT_SHADOW_CURTAIN_PLAN_2026-10-07.md:71-82"},
    {"tier": "inferred", "claim": "A disabled spawn track is the safest reversible meaning of remove: the card cannot render, while its binding GUID survives for exact REVERT.",
     "cite": "tool design; Unreal cannot recreate a removed spawnable with the same GUID through the reviewed API"},
]

API_TABLE = [
    ("Show.cues -> cue.scene.sequence", "declaration-proven", "curtain_sleight.py:1474-1488"),
    ("dirty package census", "measured", "curtain_sleight.py:1736-1739; APPLY_OK 5 Oct"),
    ("MovieScene binding/track/section reads", "measured", "curtain_sleight.py:1330-1343; records written 5 Oct"),
    ("reuse spawn track and replace its section", "measured", "curtain_sleight.py:1819-1834; fix measured 5 Oct"),
    ("replace transform/float track sections", "declaration-proven", "MovieSceneTrackExtensions remove_section/add_section; existing project precedent"),
    ("SpotLight template properties including light_function_material", "inferred", "LightComponent property exposed to Unreal Python; read-back is mandatory"),
    ("binding.remove for APPLY-created spots", "inferred", "shadow_play_spot.py:691,1070-1077; REVERT refuses on failure"),
    ("EditorAssetLibrary.save_asset named package", "measured", "curtain_sleight.py:2160-2167; APPLY_OK 5 Oct"),
]


class PlanError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def merged_params(params):
    unknown = sorted(set(params or {}) - set(DEFAULTS))
    if unknown:
        raise PlanError("UNKNOWN_PARAMS: %r" % unknown)
    out = dict(DEFAULTS)
    out.update(params or {})
    out["reference_interaction"] = int(out["reference_interaction"])
    out["fade_seconds"] = float(out["fade_seconds"])
    out["fade_out_seconds"] = float(out["fade_out_seconds"])
    out["spawn_lead_frames"] = int(out["spawn_lead_frames"])
    if out["reference_interaction"] not in SEQS:
        raise PlanError("REFERENCE_INTERACTION: %r" % out["reference_interaction"])
    if not (0.0 < out["fade_seconds"] <= 30.0):
        raise PlanError("FADE_SECONDS: %.3f is outside (0,30]" % out["fade_seconds"])
    if not (0.0 <= out["fade_out_seconds"] <= 30.0):
        raise PlanError("FADE_OUT_SECONDS: %.3f is outside [0,30]" % out["fade_out_seconds"])
    lf = out["light_function_material"]
    if lf is not None and (not isinstance(lf, str) or not lf.startswith("/Game/")):
        raise PlanError("LIGHT_FUNCTION_MATERIAL: use null or a /Game/... asset path")
    return out


def confirm_ok(mode, interaction, confirm):
    return mode in MODES and interaction in SEQS and str(confirm or "").strip() == "%s I%d" % (mode, interaction)


def preflight_refusals(mode, interaction, state):
    out = []
    if not confirm_ok(mode, interaction, state.get("confirm")):
        out.append("CONFIRM_MISMATCH")
    if state.get("pie"):
        out.append("PIE_OR_SIE_ACTIVE")
    if not state.get("world_ok"):
        out.append("WRONG_WORLD")
    if state.get("sequencer_open"):
        out.append("SEQUENCER_IS_OPEN")
    if state.get("census") != {"content": [], "maps": []}:
        out.append("DIRTY_CENSUS: %r" % state.get("census"))
    if state.get("zz"):
        out.append("ZZ_ACTORS_PRESENT")
    record = state.get("record")
    if mode in ("DRY", "APPLY") and record is not None:
        out.append("RECORD_EXISTS: applied=%s" % record.get("applied"))
    if mode == "REVERT" and not (record and record.get("applied") and int(record.get("interaction", -1)) == interaction):
        out.append("NOTHING_TO_REVERT")
    return out


def _interp_rows(keys, frame):
    """Linear interpolation for [(frame,value)] with constant ends."""
    rows = sorted((int(f), float(v)) for f, v in keys)
    if not rows:
        raise PlanError("EMPTY_KEYS")
    if frame <= rows[0][0]:
        return rows[0][1]
    if frame >= rows[-1][0]:
        return rows[-1][1]
    for (a, x), (b, y) in zip(rows, rows[1:]):
        if a <= frame <= b:
            return x if b == a else x + (y - x) * ((frame - a) / float(b - a))
    raise AssertionError(frame)


def plan_transition(target, reference, params):
    """Pure plan. target has beats/fps/end and drape frames; reference is an I4-derived relative-light profile."""
    p = merged_params(params)
    fps, beats = float(target["fps"]), target["beats"]
    up0 = int(beats["play0"])
    up1 = up0 + int(round(p["fade_seconds"] * fps))
    fade1 = int(beats["release"]) + max(1, int(round(p["fade_out_seconds"] * fps)))
    lead = up0 - p["spawn_lead_frames"]
    if lead < int(target["start"]):
        raise PlanError("SPAWN_LEAD_BEFORE_RANGE")
    if up1 >= int(beats["sleight"]):
        raise PlanError("FADE_OVERLAPS_SLEIGHT: %d >= %d" % (up1, beats["sleight"]))
    if fade1 > int(target["end"]):
        raise PlanError("FADE_OUTSIDE_RANGE: %d > %d" % (fade1, target["end"]))

    def world_pose(frame, rel):
        loc = SPS["to_world"](frame, rel["loc"])
        world_dir = SPS["rot_py"](rel["direction"], frame.get("pitch", 0.0), frame["yaw"])
        pitch, yaw = SPS["angles_of"](world_dir)
        return {"loc": loc, "pitch": pitch, "yaw": CS["wrap"](yaw), "roll": 0.0}

    spots = {}
    for side in SIDES:
        frame = target["drapes"][side]
        pose = world_pose(frame, reference["relative"])
        peak = float(reference["light"]["intensity"])
        keys = [(0, 0.0), (up0, 0.0), (up1, peak)]
        if side == "hangar":
            keys += [(int(beats["strike"]), peak), (int(beats["strike"]) + 1, 0.0)]
            spawn = [(lead, True), (int(beats["strike"]) + 2, False)]
        else:
            keys += [(int(beats["release"]), peak), (fade1, 0.0)]
            spawn = [(lead, True), (fade1 + 1, False)]
        row = (pose["loc"][0], pose["loc"][1], pose["loc"][2], pose["pitch"], pose["yaw"], 0.0)
        spots[side] = {"name": SPOT_NAMES[side], "pose": pose,
                       "transform_keys": [(0,) + row, (int(target["end"]),) + row],
                       "intensity_keys": keys, "spawn": spawn}
    light = copy.deepcopy(reference["light"])
    light["light_function_material"] = p["light_function_material"]
    plan = {"interaction": int(target["interaction"]), "reference_interaction": p["reference_interaction"],
            "sequence": target["sequence"], "cue_guid": target["cue_guid"], "fps": fps,
            "start": int(target["start"]), "end": int(target["end"]), "beats": copy.deepcopy(beats),
            "fade_up": [up0, up1], "fade_out": [int(beats["release"]), fade1],
            "cards": {name: "disable_if_present" for name in CARD_NAMES}, "spots": spots,
            "light": light, "relative": copy.deepcopy(reference["relative"]),
            "drapes": copy.deepcopy(target["drapes"]),
            "drape_ready_frame": int(target.get("drape_ready_frame", up0)), "params": p}
    plan["digest"] = digest({k: v for k, v in plan.items() if k != "digest"})
    return plan


def check_plan(plan):
    fail = []
    b, end = plan["beats"], int(plan["end"])
    if not (b["play0"] < plan["fade_up"][1] < b["sleight"] < b["strike"] < b["release"] < end):
        fail.append("BEAT_ORDER")
    if round(float(plan["light"]["intensity"])) != 7483:
        fail.append("REFERENCE_INTENSITY_NOT_7483: %.3f" % float(plan["light"]["intensity"]))
    if not bool(plan["light"].get("cast_shadows")):
        fail.append("CAST_SHADOWS_OFF")
    if int(plan["drape_ready_frame"]) > int(plan["fade_up"][0]):
        fail.append("DRAPE_NOT_READY_BEFORE_FADE: %d > %d" % (plan["drape_ready_frame"], plan["fade_up"][0]))
    for side in SIDES:
        sp = plan["spots"][side]
        if _interp_rows(sp["intensity_keys"], b["play0"]) != 0.0:
            fail.append("NOT_DARK_AT_PLAY_START_%s" % side.upper())
        if abs(_interp_rows(sp["intensity_keys"], plan["fade_up"][1]) - float(plan["light"]["intensity"])) > 1.0e-3:
            fail.append("NOT_AT_PEAK_%s" % side.upper())
        if max(f for f, _ in sp["spawn"]) > end + 1:
            fail.append("SPAWN_OUTSIDE_RANGE_%s" % side.upper())
        frame = plan["drapes"][side]
        rel_loc = SPS["to_local"](frame, sp["pose"]["loc"])
        world_dir = CS["direction"](sp["pose"]["pitch"], sp["pose"]["yaw"])
        rel_dir = SPS["rot_py_inv"](world_dir, frame.get("pitch", 0.0), frame["yaw"])
        dl = max(abs(rel_loc[i] - plan["relative"]["loc"][i]) for i in range(3))
        dot = sum(rel_dir[i] * plan["relative"]["direction"][i] for i in range(3))
        da = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        if dl > 0.5 or da > 0.05:
            fail.append("SPOT_RELATIVE_%s: %.3f cm / %.4f deg" % (side.upper(), dl, da))
    return fail


def structural_apply_model(snapshot, plan, existing_spot_guids, created_guids):
    out = copy.deepcopy(snapshot)
    span = [0, int(plan["end"]) + 1]
    present = {b["guid"] for b in out["bindings"]}
    for side in SIDES:
        name = SPOT_NAMES[side]
        guid = existing_spot_guids.get(name) or created_guids.get(name)
        if guid not in present:
            out["bindings"].append({"name": name, "guid": guid, "parent": "", "tracks": [
                {"class": "MovieSceneSpawnTrack", "name": "", "sections": [span]},
                {"class": "MovieScene3DTransformTrack", "name": SPOT_TRACK, "sections": [span]},
                {"class": "MovieSceneFloatTrack", "name": SPOT_TRACK, "sections": [span]},
            ]})
    return CS["normalize_snapshot"](out)


def structural_revert_model(snapshot_after, created_guids):
    out = copy.deepcopy(snapshot_after)
    gone = set(created_guids.values())
    out["bindings"] = [b for b in out["bindings"] if b["guid"] not in gone]
    return CS["normalize_snapshot"](out)


def write_preview_png(path, plan, width=1200, height=675):
    """Dependency-free PNG timeline preview: red=hangar, amber=mouth, vertical beats."""
    px = bytearray([18, 20, 25, 255] * width * height)

    def dot(x, y, color, radius=1):
        for yy in range(max(0, y-radius), min(height, y+radius+1)):
            for xx in range(max(0, x-radius), min(width, x+radius+1)):
                i = (yy * width + xx) * 4
                px[i:i+4] = bytes(color)

    left, right, top, bottom = 70, width - 35, 60, height - 70
    for x in range(left, right + 1):
        dot(x, bottom, (150, 155, 165, 255))
    for y in range(top, bottom + 1):
        dot(left, y, (150, 155, 165, 255))
    end = max(1, int(plan["end"]))
    for _, frame in sorted(plan["beats"].items()):
        x = left + int((right-left) * int(frame) / end)
        for y in range(top, bottom + 1, 3):
            dot(x, y, (70, 80, 95, 255))
    peak = max(1.0, float(plan["light"]["intensity"]))
    for side, color in (("hangar", (235, 80, 70, 255)), ("mouth", (255, 190, 55, 255))):
        keys = plan["spots"][side]["intensity_keys"]
        last = None
        for frame in range(end + 1):
            x = left + int((right-left) * frame / end)
            y = bottom - int((bottom-top) * max(0.0, _interp_rows(keys, frame)) / peak)
            if last is not None:
                x0, y0 = last
                steps = max(abs(x-x0), abs(y-y0), 1)
                for q in range(steps + 1):
                    dot(round(x0 + (x-x0)*q/steps), round(y0 + (y-y0)*q/steps), color, 2)
            last = (x, y)
    raw = b"".join(b"\x00" + bytes(px[y*width*4:(y+1)*width*4]) for y in range(height))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) \
          + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(png)
        handle.flush()
        os.fsync(handle.fileno())
    return {"path": path, "width": width, "height": height, "bytes": len(png), "sha256": hashlib.sha256(png).hexdigest()}


# ---------------------------------------------------------------------------------------------------------------------
# Unreal-side helpers

def _stop(run, reason):
    unreal.log_error("INTERACTION_SHADOW_TRANSITION_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


CS["_stop"] = _stop
SPS["_stop"] = _stop


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    text = json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=str)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text); handle.flush(); os.fsync(handle.fileno())
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text); handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)


def _guid(value):
    return CS["_guid"](value)


def _bindings(seq, name):
    return [b for b in seq.get_bindings() if str(b.get_display_name()) == name]


def _one_binding(seq, name, run, allow_missing=False):
    rows = _bindings(seq, name)
    if len(rows) > 1 or (not allow_missing and len(rows) != 1):
        _stop(run, "BINDING_COUNT|%s|%d" % (name, len(rows)))
    return rows[0] if rows else None


def _sequence_from_show(show, n, run):
    expected = "%s/%s" % (SEQ_DIR, SEQS[n])
    rows = []
    for cue in show.get_editor_property("cues"):
        if not cue.get_editor_property("enabled"):
            continue
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence")
        path = seq.get_path_name().split(".")[0] if seq is not None else None
        if path == expected:
            rows.append((cue, seq))
    if len(rows) != 1:
        _stop(run, "SHOW_SEQUENCE_COUNT|I%d|%s|%d" % (n, expected, len(rows)))
    cue, seq = rows[0]
    if str(cue.get_editor_property("type")) != str(unreal.InfinityCueType.SEQUENCE):
        _stop(run, "SHOW_CUE_NOT_SEQUENCE|I%d" % n)
    return cue, seq, expected


def _range(section):
    return [int(section.get_start_frame()), int(section.get_end_frame())]


def _keys(channel):
    unit = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    return [[int(k.get_time(time_unit=unit).frame_number.value), k.get_value()] for k in channel.get_keys()]


def _default(channel):
    try:
        return channel.get_default()
    except Exception:
        return None


def _track(binding, cls, run, display=None):
    rows = [t for t in binding.get_tracks() if t.get_class().get_name() == cls and
            (display is None or str(t.get_display_name()) == display)]
    if len(rows) != 1:
        _stop(run, "TRACK_COUNT|%s|%s|%s|%d" % (binding.get_display_name(), cls, display, len(rows)))
    return rows[0]


def _spawn_spec(binding, run):
    track = _track(binding, "MovieSceneSpawnTrack", run)
    sections = list(track.get_sections())
    if len(sections) != 1:
        _stop(run, "SPAWN_SECTION_COUNT|%s|%d" % (binding.get_display_name(), len(sections)))
    ch = sections[0].get_all_channels()[0]
    return {"range": _range(sections[0]), "default": bool(_default(ch)),
            "keys": [[f, bool(v)] for f, v in _keys(ch)]}


def _write_spawn(binding, spec, run):
    track = _track(binding, "MovieSceneSpawnTrack", run)
    for section in list(track.get_sections()):
        track.remove_section(section)
    section = track.add_section(); section.set_range(*spec["range"])
    ch = section.get_all_channels()[0]; ch.set_default(bool(spec["default"]))
    for frame, value in spec["keys"]:
        ch.add_key(unreal.FrameNumber(int(frame)), bool(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)


def _channel_spec(channel):
    return {"default": _default(channel), "keys": _keys(channel)}


def _transform_spec(binding, run):
    track = _track(binding, "MovieScene3DTransformTrack", run, SPOT_TRACK)
    sections = list(track.get_sections())
    if len(sections) != 1:
        _stop(run, "TRANSFORM_SECTION_COUNT|%s|%d" % (binding.get_display_name(), len(sections)))
    return {"range": _range(sections[0]), "channels": {str(c.channel_name): _channel_spec(c)
            for c in sections[0].get_all_channels()}}


def _write_transform(binding, spec, run):
    track = _track(binding, "MovieScene3DTransformTrack", run, SPOT_TRACK)
    for section in list(track.get_sections()):
        track.remove_section(section)
    section = track.add_section(); section.set_range(*spec["range"])
    channels = {str(c.channel_name): c for c in section.get_all_channels()}
    for name, row in spec["channels"].items():
        if name not in channels:
            _stop(run, "TRANSFORM_CHANNEL_MISSING|%s" % name)
        ch = channels[name]
        if row["default"] is not None:
            ch.set_default(row["default"])
        for frame, value in row["keys"]:
            ch.add_key(unreal.FrameNumber(int(frame)), value, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                       interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


def _float_spec(binding, run):
    track = _track(binding, "MovieSceneFloatTrack", run, SPOT_TRACK)
    sections = list(track.get_sections())
    if len(sections) != 1:
        _stop(run, "FLOAT_SECTION_COUNT|%s|%d" % (binding.get_display_name(), len(sections)))
    channels = list(sections[0].get_all_channels())
    if len(channels) != 1:
        _stop(run, "FLOAT_CHANNEL_COUNT|%s|%d" % (binding.get_display_name(), len(channels)))
    return {"range": _range(sections[0]), "property": str(track.get_property_name()),
            "path": str(track.get_property_path()), "display": str(track.get_display_name()),
            "channel": _channel_spec(channels[0])}


def _write_float(binding, spec, run):
    track = _track(binding, "MovieSceneFloatTrack", run, SPOT_TRACK)
    track.set_property_name_and_path(unreal.Name(spec["property"]), spec["path"])
    track.set_display_name(spec["display"])
    for section in list(track.get_sections()):
        track.remove_section(section)
    section = track.add_section(); section.set_range(*spec["range"])
    ch = section.get_all_channels()[0]
    if spec["channel"]["default"] is not None:
        ch.set_default(spec["channel"]["default"])
    for frame, value in spec["channel"]["keys"]:
        ch.add_key(unreal.FrameNumber(int(frame)), float(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                   interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


LIGHT_PROPS = ("intensity", "intensity_units", "use_temperature", "temperature", "outer_cone_angle",
               "inner_cone_angle", "attenuation_radius", "source_radius", "soft_source_radius", "cast_shadows")


def _asset_path(value):
    return value.get_path_name().split(".")[0] if value is not None else None


def _spot_semantic(binding, run):
    tmpl = binding.get_object_template(); root = tmpl.get_editor_property("root_component")
    comp = tmpl.get_editor_property("spot_light_component")
    loc, rot = root.get_editor_property("relative_location"), root.get_editor_property("relative_rotation")
    props = {}
    for name in LIGHT_PROPS:
        value = comp.get_editor_property(name)
        props[name] = str(value) if name == "intensity_units" else value
    props["light_function_material"] = _asset_path(comp.get_editor_property("light_function_material"))
    return {"guid": _guid(binding.get_id()), "root": {"loc": [loc.x, loc.y, loc.z],
            "rot": [rot.roll, rot.pitch, rot.yaw]}, "props": props, "spawn": _spawn_spec(binding, run),
            "transform": _transform_spec(binding, run), "float": _float_spec(binding, run)}


def _card_semantic(binding, run):
    return {"guid": _guid(binding.get_id()), "spawn": _spawn_spec(binding, run)}


def _semantic(seq, run):
    cards, spots = {}, {}
    for name in CARD_NAMES:
        b = _one_binding(seq, name, run, allow_missing=True)
        cards[name] = _card_semantic(b, run) if b else None
    for side in SIDES:
        name = SPOT_NAMES[side]
        b = _one_binding(seq, name, run, allow_missing=True)
        spots[name] = _spot_semantic(b, run) if b else None
    return {"cards": cards, "spots": spots}


def _plain(value):
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _semantic_diff(got, want):
    return [] if digest(_plain(got)) == digest(_plain(want)) else ["SEMANTIC_MISMATCH got=%s want=%s" % (digest(_plain(got)), digest(_plain(want)))]


def _pose_from_transform(binding, frame, run):
    ch = SPS["_transform_channels"](binding, SPOT_TRACK, run)
    return SPS["_pose_from_channels"](ch, frame)


def _reference_profile(ref_seq, ref_inputs, ref_n, run):
    rels, lights = [], []
    for side in SIDES:
        b = _one_binding(ref_seq, SPOT_NAMES[side], run)
        pose = _pose_from_transform(b, ref_inputs["beats"]["sleight"], run)
        frame = ref_inputs["hangar_drape_at"]["sleight"] if side == "hangar" else ref_inputs["mouth_drape"]
        rel_loc = SPS["to_local"](frame, pose["loc"])
        world_dir = CS["direction"](pose["pitch"], pose["yaw"])
        rel_dir = SPS["rot_py_inv"](world_dir, frame.get("pitch", 0.0), frame["yaw"])
        rels.append({"loc": rel_loc, "direction": rel_dir})
        sem = _spot_semantic(b, run)
        lights.append(sem["props"])
    if max(abs(rels[0]["loc"][i] - rels[1]["loc"][i]) for i in range(3)) > 0.5:
        _stop(run, "REFERENCE_SPOTS_NOT_MATCHED_LOCATION")
    if max(abs(rels[0]["direction"][i] - rels[1]["direction"][i]) for i in range(3)) > 1.0e-3:
        _stop(run, "REFERENCE_SPOTS_NOT_MATCHED_DIRECTION")
    for key in LIGHT_PROPS:
        if str(lights[0][key]) != str(lights[1][key]):
            _stop(run, "REFERENCE_SPOTS_LIGHT_MISMATCH|%s|%r|%r" % (key, lights[0][key], lights[1][key]))
    if round(float(lights[0]["intensity"])) != 7483 or not bool(lights[0]["cast_shadows"]):
        _stop(run, "REFERENCE_PHOTOMETRY|intensity=%s|cast_shadows=%s" %
              (lights[0]["intensity"], lights[0]["cast_shadows"]))
    return {"interaction": ref_n, "relative": rels[0], "light": lights[0]}


def _global_census(show, run):
    out = {}
    for n in sorted(SEQS):
        _, seq, path = _sequence_from_show(show, n, run)
        cards = {}
        for name in CARD_NAMES:
            rows = _bindings(seq, name)
            detail = {"count": len(rows), "present": bool(rows)}
            if len(rows) == 1:
                binding = rows[0]
                tmpl = binding.get_object_template()
                root = tmpl.get_editor_property("root_component")
                scale = root.get_editor_property("relative_scale3d")
                comp = tmpl.get_editor_property("static_mesh_component")
                spawn = _spawn_spec(binding, run)
                detail.update({"guid": _guid(binding.get_id()),
                    "mesh": _asset_path(comp.get_editor_property("static_mesh")),
                    "size_cm_from_cube_scale": [100.0 * scale.x, 100.0 * scale.y, 100.0 * scale.z],
                    "spawn": spawn, "can_spawn": bool(spawn["default"]) or any(v for _, v in spawn["keys"])})
            cards[name] = detail
        out["I%d" % n] = {"sequence": path,
            "cards": cards,
            "spots": {SPOT_NAMES[s]: len(_bindings(seq, SPOT_NAMES[s])) for s in SIDES}}
    return out


def _live_context(n, run, mode, confirm):
    here = _here(); editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world(); record = _load_json(os.path.join(here, RECORD_PATTERN % n))
    state = {"pie": editor.get_game_world() is not None,
             "world_ok": world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": CS["_census"](), "zz": any(str(a.get_actor_label()).startswith("ZZ_") for a in CS["_actors"]()),
             "record": record, "confirm": confirm}
    refusals = preflight_refusals(mode, n, state)
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    show = unreal.load_asset(SHOW_PATH)
    if show is None:
        _stop(run, "SHOW_LOAD")
    cue, seq, seq_path = _sequence_from_show(show, n, run)
    return here, show, cue, seq, seq_path, record


def _inputs(n, cue, seq, seq_path, run):
    sleight = _load_json(os.path.join(_here(), SLEIGHT_RECORD % n))
    doors = _load_json(os.path.join(_here(), CS["DOORS_RECORD"]))
    if not sleight or not sleight.get("applied") or sleight.get("sequence") != seq_path:
        _stop(run, "SLEIGHT_RECORD_CONTEXT|I%d" % n)
    if not doors or not doors.get("applied"):
        _stop(run, "DOORS_RECORD_CONTEXT")
    live = SPS["_live_inputs"](n, sleight, doors, seq, run)
    return {"interaction": n, "sequence": seq_path, "cue_guid": _guid(cue.get_editor_property("cue_guid")),
            "fps": live["fps"], "start": live["start"], "end": live["end"], "beats": live["beats"],
            "drapes": {"hangar": SPS["frame_of_pose"](live["hangar_drape_at"]["sleight"]),
                       "mouth": SPS["frame_of_pose"](live["mouth_drape"])},
            "drape_ready_frame": int(live["beats"]["play0"]), "_live": live}


def _report(n, run, params, show, cue, seq, seq_path):
    p = merged_params(params); target = _inputs(n, cue, seq, seq_path, run)
    ref_cue, ref_seq, ref_path = _sequence_from_show(show, p["reference_interaction"], run)
    ref_target = _inputs(p["reference_interaction"], ref_cue, ref_seq, ref_path, run)
    reference = _reference_profile(ref_seq, ref_target["_live"], p["reference_interaction"], run)
    plan = plan_transition(target, reference, p); failures = check_plan(plan)
    census = _global_census(show, run)
    warnings = []
    if _load_json(os.path.join(_here(), LEGACY_SPOT_RECORD % n)):
        warnings.append("LEGACY_SPOT_RECORD_PRESENT: old shadow_play_spot REVERT will drift-refuse after APPLY; use this tool's REVERT")
    warnings.append("VISUAL_ACCEPTANCE_PENDING: DRY/read-back cannot prove the slow discovery or gobo projection on the rendered curtain")
    return {"schema_version": 1, "run": run, "interaction": n, "apply_ready": not failures,
            "refusals": failures, "warnings": warnings, "plan": plan, "plan_digest": plan["digest"],
            "owner": {"show_authority": SHOW_PATH, "cue_guid": target["cue_guid"], "written_package": seq_path,
                      "show_level_master_written": False}, "global_census": census, "claims": CLAIMS,
            "api_table": [{"call": a, "tier": b, "cite": c} for a, b, c in API_TABLE],
            "sources": {"shadow_play_spot_sha256": SPS["SOURCE_SHA256"], "curtain_sleight_sha256": CS["SOURCE_SHA256"]}}


def _backup_sequence(seq_path, label, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "Pre%s-%s" % (label, run))
    os.makedirs(backup, exist_ok=False)
    src = CS["_content_file"](seq_path); dst = os.path.join(backup, os.path.basename(src))
    if not os.path.isfile(src):
        _stop(run, "BACKUP_SOURCE_MISSING|" + src)
    shutil.copy2(src, dst)
    if os.path.getsize(src) != os.path.getsize(dst):
        _stop(run, "BACKUP_SIZE_MISMATCH|" + src)
    return backup, dst


def _desired_transform(plan, side):
    channels = {}
    keys = plan["spots"][side]["transform_keys"]
    for name, idx in CS["POSE_CHANNELS"].items():
        channels[name] = {"default": 0.0, "keys": [[row[0], row[idx]] for row in keys]}
    for name in ("Scale.X", "Scale.Y", "Scale.Z"):
        channels[name] = {"default": 1.0, "keys": []}
    return {"range": [0, int(plan["end"]) + 1], "channels": channels}


def _desired_float(plan, side, component_name):
    return {"range": [0, int(plan["end"]) + 1], "property": "Intensity",
            "path": "%s.Intensity" % component_name, "display": SPOT_TRACK,
            "channel": {"default": None, "keys": [list(x) for x in plan["spots"][side]["intensity_keys"]]}}


def _apply_template(binding, plan, side, run):
    tmpl = binding.get_object_template(); root = tmpl.get_editor_property("root_component")
    pose = plan["spots"][side]["pose"]
    root.set_editor_property("relative_location", unreal.Vector(*pose["loc"]))
    root.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=pose["pitch"], yaw=pose["yaw"]))
    comp = tmpl.get_editor_property("spot_light_component"); light = plan["light"]
    comp.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    for prop in ("intensity", "use_temperature", "temperature", "outer_cone_angle", "inner_cone_angle",
                 "attenuation_radius", "source_radius", "soft_source_radius", "cast_shadows"):
        comp.set_editor_property(prop, light[prop])
    material = unreal.load_asset(light["light_function_material"]) if light["light_function_material"] else None
    if light["light_function_material"] and material is None:
        _stop(run, "LIGHT_FUNCTION_LOAD|%s|NOTHING SAVED; Don't-Save restart" % light["light_function_material"])
    comp.set_editor_property("light_function_material", material)
    return comp


def _make_spot(seq, plan, side, run):
    sp = plan["spots"][side]
    binding = seq.add_spawnable_from_class(unreal.SpotLight)
    if binding is None or not binding.is_valid():
        _stop(run, "SPAWNABLE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % sp["name"])
    binding.set_display_name(sp["name"])
    comp = _apply_template(binding, plan, side, run)
    CS["_spawn_track"](binding, sp["spawn"], int(plan["end"]))
    CS["_key_pose"](binding, sp["transform_keys"], int(plan["end"]), run, sp["name"])
    CS["_key_float"](binding, "Intensity", "%s.Intensity" % comp.get_name(), sp["intensity_keys"], int(plan["end"]), run, sp["name"])
    return binding


def _mutate_apply(seq, plan, before, run):
    created = {}; seq.modify()
    disabled = []
    for name in CARD_NAMES:
        binding = _one_binding(seq, name, run, allow_missing=True)
        if binding:
            _write_spawn(binding, {"range": [0, int(plan["end"]) + 1], "default": False,
                                   "keys": [[0, False]]}, run)
            disabled.append(name)
    for side in SIDES:
        name = SPOT_NAMES[side]; binding = _one_binding(seq, name, run, allow_missing=True)
        if binding is None:
            binding = _make_spot(seq, plan, side, run); created[name] = _guid(binding.get_id())
        else:
            comp = _apply_template(binding, plan, side, run)
            _write_spawn(binding, {"range": [0, int(plan["end"]) + 1], "default": False,
                                   "keys": [list(x) for x in plan["spots"][side]["spawn"]]}, run)
            _write_transform(binding, _desired_transform(plan, side), run)
            _write_float(binding, _desired_float(plan, side, comp.get_name()), run)
    return created, disabled


def _restore_existing(seq, semantic_before, created, run):
    for guid in created.values():
        rows = [b for b in seq.get_bindings() if _guid(b.get_id()) == guid]
        if len(rows) != 1:
            _stop(run, "CREATED_BINDING_COUNT|%s|%d|NOTHING SAVED; Don't-Save restart" % (guid, len(rows)))
        rows[0].remove()
    for name, spec in semantic_before["cards"].items():
        if spec is not None:
            binding = _one_binding(seq, name, run)
            if _guid(binding.get_id()) != spec["guid"]:
                _stop(run, "CARD_GUID_DRIFT|%s" % name)
            _write_spawn(binding, spec["spawn"], run)
    for name, spec in semantic_before["spots"].items():
        if spec is None:
            continue
        binding = _one_binding(seq, name, run)
        if _guid(binding.get_id()) != spec["guid"]:
            _stop(run, "SPOT_GUID_DRIFT|%s" % name)
        tmpl = binding.get_object_template(); root = tmpl.get_editor_property("root_component")
        root.set_editor_property("relative_location", unreal.Vector(*spec["root"]["loc"]))
        root.set_editor_property("relative_rotation", unreal.Rotator(roll=spec["root"]["rot"][0],
                                 pitch=spec["root"]["rot"][1], yaw=spec["root"]["rot"][2]))
        comp = tmpl.get_editor_property("spot_light_component")
        for prop, value in spec["props"].items():
            if prop == "intensity_units":
                value = unreal.LightUnits.CANDELAS
            elif prop == "light_function_material":
                value = unreal.load_asset(value) if value else None
            comp.set_editor_property(prop, value)
        _write_spawn(binding, spec["spawn"], run)
        _write_transform(binding, spec["transform"], run)
        _write_float(binding, spec["float"], run)


def run_dry(n, run, params, confirm):
    here, show, cue, seq, seq_path, _ = _live_context(n, run, "DRY", confirm)
    report = _report(n, run, params, show, cue, seq, seq_path)
    preview = write_preview_png(os.path.join(here, "interaction_shadow_transition_I%d_%s_preview.png" % (n, run)), report["plan"])
    report["preview"] = preview
    out = os.path.join(here, DRY_PATTERN % n); _write_json(out, report)
    _write_json(os.path.join(here, PLAN_PATTERN % n), {"run": run, "interaction": n,
                "cue_guid": report["owner"]["cue_guid"], "plan_digest": report["plan_digest"], "params": params})
    if CS["_census"]() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%r" % CS["_census"]())
    unreal.log("INTERACTION_SHADOW_TRANSITION_DRY_OK|run=%s|interaction=%d|mutated=0|apply_ready=%d|"
               "fade=%d-%d|reference=I%d|preview=%s|report=%s" % (run, n, int(report["apply_ready"]),
               report["plan"]["fade_up"][0], report["plan"]["fade_up"][1],
               report["plan"]["reference_interaction"], preview["path"], out))


def run_apply(n, run, params, confirm):
    here, show, cue, seq, seq_path, _ = _live_context(n, run, "APPLY", confirm)
    report = _report(n, run, params, show, cue, seq, seq_path)
    if report["refusals"]:
        _stop(run, "PLAN_REFUSED|%r" % report["refusals"])
    pf = _load_json(os.path.join(here, PLAN_PATTERN % n)) or {}
    if pf.get("plan_digest") != report["plan_digest"] or pf.get("cue_guid") != report["owner"]["cue_guid"]:
        _stop(run, "PLAN_CHANGED_SINCE_DRY|rerun DRY")
    before_struct = CS["_snapshot"](seq, n); before_sem = _plain(_semantic(seq, run))
    backup, copied = _backup_sequence(seq_path, "InteractionShadowTransition-I%d" % n, run)
    record_path = os.path.join(here, RECORD_PATTERN % n)
    record = {"schema_version": 1, "run": run, "interaction": n, "world": EXPECTED_WORLD,
              "sequence": seq_path, "cue_guid": report["owner"]["cue_guid"], "applied": False,
              "backup": backup, "backup_files": [copied], "params": params, "plan": report["plan"],
              "plan_digest": report["plan_digest"], "snapshot_before": before_struct,
              "semantic_before": before_sem, "dirty_before": CS["_census"]()}
    try:
        _write_json(record_path, record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|nothing mutated")
    existing = {name: spec["guid"] for name, spec in before_sem["spots"].items() if spec is not None}
    created, disabled = _mutate_apply(seq, report["plan"], before_sem, run)
    expected_struct = structural_apply_model(before_struct, report["plan"], existing, created)
    problems = CS["snapshot_diff"](CS["_snapshot"](seq, n), expected_struct)
    after_sem = _plain(_semantic(seq, run))
    for name in disabled:
        if any(value for _, value in after_sem["cards"][name]["spawn"]["keys"]):
            problems.append("CARD_STILL_SPAWNS|%s" % name)
    census = CS["_census"]()
    if census != {"content": [seq_path], "maps": []}:
        problems.append("UNEXPECTED_DIRTY|%r" % census)
    if problems:
        _stop(run, "PRESAVE_READBACK|%r|NOTHING SAVED; Don't-Save restart" % problems)
    record.update({"created_spot_guids": created, "disabled_cards": disabled,
                   "snapshot_after": expected_struct, "semantic_after": after_sem})
    _write_json(record_path, record)
    if not bool(unreal.EditorAssetLibrary.save_asset(seq_path, only_if_is_dirty=True)):
        _stop(run, "SAVE_FAILED|%s" % seq_path)
    seq = unreal.load_asset(seq_path)
    problems = CS["snapshot_diff"](CS["_snapshot"](seq, n), expected_struct)
    problems += _semantic_diff(_plain(_semantic(seq, run)), after_sem)
    if CS["_census"]() != {"content": [], "maps": []}:
        problems.append("DIRTY_AFTER_SAVE|%r" % CS["_census"]())
    if problems:
        _stop(run, "READBACK_FAILED_AFTER_SAVE|%r|restore from %s" % (problems, backup))
    record["applied"] = True; record["dirty_after"] = CS["_census"](); _write_json(record_path, record)
    unreal.log("INTERACTION_SHADOW_TRANSITION_APPLY_OK|run=%s|interaction=%d|reference=I%d|"
               "cards_disabled=%d|spots_created=%d|fade=%d-%d|saved=%s|backup=%s|record=%s" %
               (run, n, report["plan"]["reference_interaction"], len(disabled), len(created),
                report["plan"]["fade_up"][0], report["plan"]["fade_up"][1], seq_path, backup, record_path))


def run_revert(n, run, confirm):
    here, _, _, seq, seq_path, record = _live_context(n, run, "REVERT", confirm)
    live_struct = CS["_snapshot"](seq, n); live_sem = _plain(_semantic(seq, run))
    problems = CS["snapshot_diff"](live_struct, record["snapshot_after"])
    problems += _semantic_diff(live_sem, record["semantic_after"])
    if problems:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r|restore from %s" % (problems, record["backup"]))
    backup, copied = _backup_sequence(seq_path, "InteractionShadowTransition-I%d-Revert" % n, run)
    txn_path = os.path.join(here, REVERT_PATTERN % run)
    _write_json(txn_path, {"schema_version": 1, "run": run, "interaction": n, "sequence": seq_path,
                "source_record": os.path.join(here, RECORD_PATTERN % n), "backup": backup,
                "backup_files": [copied], "snapshot_before_revert": live_struct,
                "semantic_before_revert": live_sem}, exclusive=True)
    seq.modify(); _restore_existing(seq, record["semantic_before"], record.get("created_spot_guids", {}), run)
    problems = CS["snapshot_diff"](CS["_snapshot"](seq, n), record["snapshot_before"])
    problems += _semantic_diff(_plain(_semantic(seq, run)), record["semantic_before"])
    if CS["_census"]() != {"content": [seq_path], "maps": []}:
        problems.append("UNEXPECTED_DIRTY|%r" % CS["_census"]())
    if problems:
        _stop(run, "REVERT_PRESAVE|%r|NOTHING SAVED; Don't-Save restart" % problems)
    if not bool(unreal.EditorAssetLibrary.save_asset(seq_path, only_if_is_dirty=True)):
        _stop(run, "REVERT_SAVE_FAILED|%s" % seq_path)
    seq = unreal.load_asset(seq_path)
    problems = CS["snapshot_diff"](CS["_snapshot"](seq, n), record["snapshot_before"])
    problems += _semantic_diff(_plain(_semantic(seq, run)), record["semantic_before"])
    if CS["_census"]() != {"content": [], "maps": []}:
        problems.append("DIRTY_AFTER_REVERT|%r" % CS["_census"]())
    if problems:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (problems, backup))
    record_path = os.path.join(here, RECORD_PATTERN % n); archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    _write_json(txn_path, dict(_load_json(txn_path), completed=True, archived_record=archived))
    unreal.log("INTERACTION_SHADOW_TRANSITION_REVERT_OK|run=%s|interaction=%d|saved=%s|backup=%s|record=%s" %
               (run, n, seq_path, backup, archived))


def main():
    g = globals(); n = int(g.get("IST_INTERACTION", 0)); mode = str(g.get("IST_MODE", "DRY")).upper()
    run = str(g.get("IST_RUN_ID") or datetime.datetime.now().strftime("IST-%Y%m%d-%H%M%S"))
    confirm = g.get("IST_CONFIRM"); params = dict(g.get("IST_PARAMS") or {})
    if not confirm_ok(mode, n, confirm):
        _stop(run, "CONFIRM_MISMATCH|want '%s I%d'|got %r" % (mode, n, confirm))
    try:
        merged_params(params)
        if mode == "DRY":
            run_dry(n, run, params, confirm)
        elif mode == "APPLY":
            run_apply(n, run, params, confirm)
        else:
            run_revert(n, run, confirm)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
