"""P89 curtain-before-shadow ordering repair (offline-authored; never run in Unreal here).

DRY audits I1/I3/I4/I5 (or one requested Interaction). APPLY and REVERT are
single-Interaction operations.  The tool changes only the existing hangar
curtain's spawn/transform/Geometry Cache/working visibility tracks and, only if
the requested margin cannot otherwise be met, the existing hangar spot intensity
track.  It never creates or removes a binding or track.

Gary's rule, 9 Oct: the curtain is already hung and visible before the shadow
spot fades up.  I2Order_20261008 is the reference implementation.
"""
import copy
import datetime
import hashlib
import json
import math
import os
import shutil


MARK = "P89_CURTAIN_BEFORE_SHADOW"
TOOL_VERSION = "2026-10-09a"
FOLDER = "P89CurtainBeforeShadow_20261009"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_DIR = "/Game/InfinityStage/Interactions"
SEQS = {
    1: "LS_Interaction_01_WashingTheBoy",
    2: "LS_Interaction_02_Turnips",
    3: "LS_Interaction_03_ForgetsHisName",
    4: "LS_Interaction_04_GetsAName",
    5: "LS_Interaction_05_BecomesKing",
}
TARGETS = (1, 3, 4, 5)
DRAPE = "Sleight Hangar Drape"
SPOT = "Shadow Play Spot (Hangar)"
SLEIGHT_TRACK = "CurtainSleight (Conductor)"
SPOT_TRACK = "ShadowPlaySpot (Conductor)"
RECORD_PATTERN = "p89_curtain_before_shadow_record_I%d.json"
PLAN_PATTERN = "p89_curtain_before_shadow_plan_I%d.json"
DRY_PATTERN = "p89_curtain_before_shadow_dry_%s.json"
CONFIRMS = {"DRY": "DRY P89", "APPLY": "APPLY P89 I%d", "REVERT": "REVERT P89 I%d"}
DEFAULTS = {"margin_seconds": 0.5, "hung_tolerance_cm": 1.0, "intensity_epsilon": 1.0e-4}

CLAIMS = [
    {"tier": "declaration-proven", "claim": "The target curtain is the existing Sleight Hangar Drape and the target light is the existing Shadow Play Spot (Hangar).",
     "cite": "Saved/CodexConductor/curtain_sleight.py:90-96; Saved/CodexConductor/shadow_play_spot.py:84-87"},
    {"tier": "declaration-proven", "claim": "I1 was authored to descend 75-175 while its job-44 spot fade is patterned from 175.",
     "cite": "Saved/CodexConductor/curtain_sleight_record_I1.json plan.frames/plan.hangar_drape; interaction_shadow_transition.py:177-224"},
    {"tier": "measured", "claim": "I2Order's accepted rule holds the hangar drape from frame 0 before the spot fade.",
     "cite": "Saved/CodexConductor/I2Order_20261008/i2_order.py:1-16,536-580"},
    {"tier": "inferred", "claim": "A sequence that passes structural and evaluated read-back still needs rendered acceptance for wall occlusion and shadow placement.",
     "cite": "tool boundary; no Unreal or rendered run in this worktree"},
]


class PlanError(ValueError):
    pass


class Stop(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def enum_token(value):
    """Normalize UE 5.8 strings such as '<E.V: 2>' without depending on call-to-call spelling."""
    raw = str(value).strip()
    if raw.startswith("<") and raw.endswith(">") and ":" in raw:
        raw = raw[1:-1].split(":", 1)[0]
    return raw.split(".")[-1]


def norm_channel(raw):
    """UE appends unstable numeric suffixes: Location.Y_183 -> Location.Y."""
    raw = str(raw)
    head, sep, tail = raw.rpartition("_")
    return head if sep and tail.isdigit() else raw


def guid_text(value, converter=None):
    """FGuid stringification is unstable in 5.8; convert once and retain the returned text."""
    return str(converter(value) if converter else value)


def merged_params(raw):
    unknown = sorted(set(raw or {}) - set(DEFAULTS))
    if unknown:
        raise PlanError("UNKNOWN_PARAMS|%r" % unknown)
    out = dict(DEFAULTS)
    out.update(raw or {})
    out["margin_seconds"] = float(out["margin_seconds"])
    out["hung_tolerance_cm"] = float(out["hung_tolerance_cm"])
    out["intensity_epsilon"] = float(out["intensity_epsilon"])
    if not (0.0 <= out["margin_seconds"] <= 10.0):
        raise PlanError("MARGIN_SECONDS|%r" % out["margin_seconds"])
    if not (0.0 < out["hung_tolerance_cm"] <= 50.0):
        raise PlanError("HUNG_TOLERANCE_CM|%r" % out["hung_tolerance_cm"])
    if not (0.0 <= out["intensity_epsilon"] <= 1.0):
        raise PlanError("INTENSITY_EPSILON|%r" % out["intensity_epsilon"])
    return out


def enforce_apply_order(interaction, i1_needs_change):
    if int(interaction) != 1 and bool(i1_needs_change):
        raise PlanError("I1_MUST_BE_FIXED_FIRST")


def interp(keys, frame, default=None):
    rows = sorted((float(f), v) for f, v in keys)
    if not rows:
        return default
    if isinstance(rows[0][1], bool):
        return bool_at(keys, frame, default)
    if frame <= rows[0][0]:
        return float(rows[0][1])
    for (a, x), (b, y) in zip(rows, rows[1:]):
        if a <= frame <= b:
            return float(y) if a == b else float(x) + (float(y) - float(x)) * (float(frame) - a) / (b - a)
    return float(rows[-1][1])


def bool_at(keys, frame, default=False):
    value = bool(default) if default is not None else False
    for f, v in sorted(keys, key=lambda row: float(row[0])):
        if float(f) <= frame:
            value = bool(v)
    return value


def channels(spec):
    if len(spec.get("sections", [])) != 1:
        raise PlanError("ONE_SECTION_REQUIRED|%s|%d" % (spec.get("class"), len(spec.get("sections", []))))
    return {row["name"]: row for row in spec["sections"][0]["channels"]}


def _range_covers(spec, frame):
    return any(row["range"][0] <= frame < row["range"][1] for row in spec.get("sections", []))


def first_true_frame(spec, start, end):
    ch = list(channels(spec).values())[0]
    for frame in range(int(start), int(end)):
        if bool_at(ch["keys"], frame, ch["default"]):
            return frame
    return None


def first_positive_frame(rows, epsilon):
    for frame, value in rows:
        if float(value) > epsilon:
            return int(frame)
    raise PlanError("SPOT_NEVER_NONZERO")


def _pose_at(spec, frame):
    out = {}
    for name, row in channels(spec).items():
        if name.startswith(("Location.", "Rotation.", "Scale.")):
            out[name] = interp(row["keys"], frame, row["default"])
    return out


def _pose_error(a, b):
    loc = max(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in ("Location.X", "Location.Y", "Location.Z"))
    rot = max(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in ("Rotation.X", "Rotation.Y", "Rotation.Z"))
    scale = max(abs(float(a.get(k, 1.0)) - float(b.get(k, 1.0))) for k in ("Scale.X", "Scale.Y", "Scale.Z"))
    return loc, rot, scale


def visibility_at(specs, frame):
    working = []
    inert = []
    for spec in specs:
        prop = spec.get("prop")
        if prop == "bHiddenInGame":
            inert.append(spec.get("name"))
            continue
        if prop != "bHidden":
            raise PlanError("VISIBILITY_PROPERTY|%r (expected bHidden; bHiddenInGame is inert)" % prop)
        ch = list(channels(spec).values())[0]
        working.append(bool_at(ch["keys"], frame, ch["default"]))
    return all(working) if working else True, inert


def curtain_state(facts, frame, hung_pose, p):
    spawn = first_true_frame(facts["spawn"], frame, frame + 1) == frame
    gc = _range_covers(facts["gc"], frame)
    visible, inert = visibility_at(facts.get("visibility", []), frame)
    pose = _pose_at(facts["transform"], frame)
    loc, rot, scale = _pose_error(pose, hung_pose)
    hung = loc <= p["hung_tolerance_cm"] and rot <= 1.0e-3 and scale <= 1.0e-4
    return {"frame": int(frame), "spawned": spawn, "gc": gc, "visible_track": visible,
            "inert_visibility_tracks": inert, "hung": hung, "pose_error": {"cm": loc, "deg": rot, "scale": scale},
            "ready": spawn and gc and visible and hung}


def readiness_frame(facts, hung_pose, start, first_light, p):
    for frame in range(int(start), int(first_light) + 1):
        if curtain_state(facts, frame, hung_pose, p)["ready"]:
            # Require readiness to remain continuous up to the first lit frame.
            if all(curtain_state(facts, f, hung_pose, p)["ready"] for f in range(frame, first_light + 1)):
                return frame
    return None


def assert_order(facts, hung_pose, first_light, margin_frames, p):
    ready = readiness_frame(facts, hung_pose, facts["playback"][0], first_light, p)
    margin = None if ready is None else int(first_light) - ready
    if ready is None or margin < int(margin_frames):
        raise PlanError("CURTAIN_AFTER_SPOT_REFUSED|ready=%r|first_light=%d|margin=%d|want=%d" %
                        (ready, first_light, margin if margin is not None else -1, margin_frames))
    return ready, margin


def _preserve_later_bool(spec, frame, value, cutoff):
    out = copy.deepcopy(spec)
    ch = list(channels(out).values())[0]
    ch["keys"] = [[int(frame), bool(value)]] + [list(k) for k in ch["keys"] if float(k[0]) > cutoff]
    return out


def _hold_transform(spec, hung_pose, start, cutoff):
    out = copy.deepcopy(spec)
    for name, row in channels(out).items():
        if name not in hung_pose:
            continue
        later = [list(k) for k in row["keys"] if float(k[0]) > cutoff]
        row["keys"] = [[int(start), float(hung_pose[name])]] + later
    return out


def _extend_gc(spec, start, frame):
    out = copy.deepcopy(spec)
    hits = [row for row in out["sections"] if row["range"][0] <= frame < row["range"][1]]
    if len(hits) != 1:
        raise PlanError("GC_SECTION_AT_HUNG|frame=%d|count=%d" % (frame, len(hits)))
    hits[0]["range"][0] = int(start)
    return out


def _visibility_from_zero(spec, cutoff):
    if spec.get("prop") == "bHiddenInGame":
        return copy.deepcopy(spec)
    if spec.get("prop") != "bHidden":
        raise PlanError("VISIBILITY_PROPERTY|%r" % spec.get("prop"))
    return _preserve_later_bool(spec, 0, True, cutoff)


def shift_fade_if_needed(spec, evaluated, required_first, epsilon):
    """Shift only the initial dark->peak ramp; later plateau/fade-out keys stay fixed."""
    first = first_positive_frame(evaluated, epsilon)
    if first >= required_first:
        return copy.deepcopy(spec), 0
    out = copy.deepcopy(spec)
    ch = list(channels(out).values())[0]
    rows = [list(k) for k in ch["keys"]]
    dark_indices = [i for i, (_, v) in enumerate(rows) if float(v) <= epsilon and int(rows[i][0]) < first]
    if not dark_indices:
        raise PlanError("NO_DARK_KEY_BEFORE_FADE")
    dark_i = dark_indices[-1]
    peak = max(float(v) for _, v in rows)
    peak_indices = [i for i, (_, v) in enumerate(rows) if float(v) >= peak - epsilon and i > dark_i]
    if not peak_indices:
        raise PlanError("NO_PEAK_AFTER_DARK")
    peak_i = peak_indices[0]
    delta = int(required_first - first)
    new_dark = int(rows[dark_i][0]) + delta
    new_peak = int(rows[peak_i][0]) + delta
    next_frame = int(rows[peak_i + 1][0]) if peak_i + 1 < len(rows) else None
    if next_frame is not None and new_peak >= next_frame:
        raise PlanError("SHIFTED_FADE_OVERLAPS_NEXT_EVENT|%d >= %d" % (new_peak, next_frame))
    rows[dark_i][0] = new_dark
    rows[peak_i][0] = new_peak
    ch["keys"] = rows
    return out, delta


def build_plan(facts, params):
    """Pure plan used by Unreal and the +/- offline harness."""
    p = merged_params(params)
    fps = float(facts["fps"])
    if fps <= 0:
        raise PlanError("FPS_NONPOSITIVE")
    start, end = map(int, facts["playback"])
    margin_frames = int(math.ceil(p["margin_seconds"] * fps - 1.0e-9))
    first_light = first_positive_frame(facts["spot_evaluated"], p["intensity_epsilon"])
    if first_light <= start:
        raise PlanError("SPOT_LIT_FROM_START|%d" % first_light)

    # The held pose is the evaluated pose immediately before the first post-hang unspawn.
    sp = list(channels(facts["spawn"]).values())[0]
    ons = [int(f) for f, v in sp["keys"] if bool(v)]
    offs = sorted(int(f) for f, v in sp["keys"] if not bool(v) and ons and int(f) > min(ons))
    if not ons or not offs:
        raise PlanError("CURTAIN_SPAWN_SHAPE|%r" % sp["keys"])
    unspawn = offs[0]
    hung_ref = min(end - 1, unspawn - 1)
    hung_pose = facts.get("hung_pose") or _pose_at(facts["transform"], hung_ref)
    before_ready = readiness_frame(facts, hung_pose, start, first_light, p)
    before_margin = None if before_ready is None else first_light - before_ready
    compliant = before_ready is not None and before_margin >= margin_frames

    writes = {k: copy.deepcopy(facts[k]) for k in ("spawn", "transform", "gc")}
    writes["visibility"] = copy.deepcopy(facts.get("visibility", []))
    writes["spot_intensity"] = copy.deepcopy(facts["spot_intensity"])
    if not compliant:
        # I2 reference: same evaluated hung pose from frame 0; preserve events after the first lit frame.
        writes["spawn"] = _preserve_later_bool(facts["spawn"], start, True, first_light)
        writes["transform"] = _hold_transform(facts["transform"], hung_pose, start, first_light)
        writes["gc"] = _extend_gc(facts["gc"], start, hung_ref)
        writes["visibility"] = [_visibility_from_zero(v, first_light) for v in facts.get("visibility", [])]
        required_first = start + margin_frames
        writes["spot_intensity"], shifted = shift_fade_if_needed(
            facts["spot_intensity"], facts["spot_evaluated"], required_first, p["intensity_epsilon"])

    changed = []
    for key, label in (("spawn", "curtain_spawn"), ("transform", "curtain_transform"),
                       ("gc", "curtain_gc"), ("visibility", "curtain_visibility"),
                       ("spot_intensity", "spot_intensity")):
        if writes[key] != (facts.get(key, []) if key == "visibility" else facts[key]):
            changed.append(label)

    after = dict(facts)
    after.update({"spawn": writes["spawn"], "transform": writes["transform"], "gc": writes["gc"],
                  "visibility": writes["visibility"]})
    # Evaluate the planned float curve in the pure model for the timing table.
    spot_ch = list(channels(writes["spot_intensity"]).values())[0]
    after_eval = [[f, interp(spot_ch["keys"], f, spot_ch["default"] or 0.0)] for f in range(start, end)]
    after_first = first_positive_frame(after_eval, p["intensity_epsilon"])
    after_ready, after_margin = assert_order(after, hung_pose, after_first, margin_frames, p)

    timing = {
        "tier": "measured", "cite": "live sequence tracks plus channel.evaluate_keys over the display-rate range",
        "interaction": int(facts["interaction"]), "fps": fps, "margin_seconds": p["margin_seconds"],
        "margin_frames_required": margin_frames, "changed": bool(changed), "changed_tracks": changed,
        "before": {"curtain_ready": before_ready, "spot_first_nonzero": first_light,
                   "margin_frames": before_margin, "spawn_first_true": first_true_frame(facts["spawn"], start, end),
                   "gc_start": min(s["range"][0] for s in facts["gc"]["sections"]), "unspawn": unspawn},
        "after": {"curtain_ready": after_ready, "spot_first_nonzero": after_first,
                  "margin_frames": after_margin, "spawn_first_true": first_true_frame(writes["spawn"], start, end),
                  "gc_start": min(s["range"][0] for s in writes["gc"]["sections"]), "unspawn": unspawn},
    }
    plan = {"schema_version": 1, "tool_version": TOOL_VERSION, "interaction": int(facts["interaction"]),
            "sequence": facts["sequence"], "playback": [start, end], "fps": fps, "params": p,
            "hung_reference_frame": hung_ref, "hung_pose": hung_pose, "timing": timing,
            "writes": writes, "owned": facts["owned"], "needs_change": bool(changed)}
    plan["digest"] = digest({k: v for k, v in plan.items() if k != "digest"})
    return plan


def compare(got, want, path="", tol=1.0e-4):
    fail = []
    if isinstance(want, dict) and isinstance(got, dict):
        for key in want:
            if key in ("raw", "interp", "key_modes"):
                continue
            fail += compare(got.get(key), want[key], path + "/" + str(key), tol)
        return fail
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            return ["LEN%s|%d!=%d" % (path, len(got), len(want))]
        for i, (a, b) in enumerate(zip(got, want)):
            fail += compare(a, b, "%s[%d]" % (path, i), tol)
        return fail
    if isinstance(want, bool) or isinstance(got, bool) or want is None or got is None or isinstance(want, str):
        return [] if got == want else ["VALUE%s|%r!=%r" % (path, got, want)]
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return [] if abs(float(got) - float(want)) <= tol * max(1.0, abs(float(want))) else ["VALUE%s|%r!=%r" % (path, got, want)]
    return [] if got == want else ["VALUE%s|%r!=%r" % (path, got, want)]


def without_owned(snapshot, owned):
    """Remove only P89-owned track rows; the remainder must stay byte-for-byte equivalent as plain data."""
    out = copy.deepcopy(snapshot)
    rows = []
    for key in ("spawn", "transform", "gc", "spot_intensity"):
        rows.append(owned[key])
    rows += list(owned.get("visibility", []))
    for binding in out["bindings"]:
        remove = [row for row in rows if row["binding_guid"] == binding["guid"]]
        binding["tracks"] = [track for track in binding["tracks"] if not any(
            track["class"] == row["class"] and track["name"] == row["name"] and track["prop"] == row["prop"]
            for row in remove)]
    return out


# -------------------------------------------------------------------------------------------------- Unreal side

def _ue():
    import unreal  # deliberately local: system-Python import is offline-safe
    return unreal


def _here():
    ue = _ue()
    return os.path.join(ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir()), "CodexConductor", FOLDER)


def _log(text):
    _ue().log(text)


def _stop(run, reason):
    message = "%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason)
    _ue().log_error(message)
    raise Stop(message)


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=str)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text); handle.flush(); os.fsync(handle.fileno())
        return
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(text); handle.flush(); os.fsync(handle.fileno())
    os.replace(temp, path)


def _census():
    lib = _ue().EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _guid(value):
    return guid_text(value, _ue().GuidLibrary.conv_guid_to_string)


def _plain(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return enum_token(value)


def _content_file(path):
    ue = _ue()
    project = ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _preflight(mode, interaction, run, confirm):
    want = CONFIRMS["DRY"] if mode == "DRY" else CONFIRMS[mode] % interaction
    if str(confirm or "").strip() != want:
        _stop(run, "CONFIRM_MISMATCH|want=%r|got=%r" % (want, confirm))
    ue = _ue()
    editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    if ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(_census()))
    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
    if any(str(a.get_actor_label()).startswith("ZZ_") for a in actors):
        _stop(run, "ZZ_ACTORS_PRESENT")


def _sequences(run):
    ue = _ue()
    show = ue.load_asset(SHOW_PATH)
    if show is None:
        _stop(run, "SHOW_LOAD")
    out = {}
    for n in TARGETS:
        path = "%s/%s" % (SEQ_DIR, SEQS[n])
        rows = []
        for cue in show.get_editor_property("cues"):
            if not cue.get_editor_property("enabled"):
                continue
            scene = cue.get_editor_property("scene")
            seq = scene.get_editor_property("sequence")
            if seq is not None and seq.get_path_name().split(".")[0] == path:
                rows.append((cue, seq))
        if len(rows) != 1:
            _stop(run, "SHOW_SEQUENCE_COUNT|I%d|%d" % (n, len(rows)))
        out[n] = rows[0]
    return out


def _channel_row(channel):
    ue = _ue()
    keys, key_modes = [], []
    for key in channel.get_keys():
        time = key.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        frame = int(time.frame_number.value)
        sub = float(getattr(time, "sub_frame", 0.0) or 0.0)
        keys.append([frame if abs(sub) < 1.0e-6 else frame + sub, _plain(key.get_value())])
        try:
            key_modes.append([frame if abs(sub) < 1.0e-6 else frame + sub, enum_token(key.get_interpolation_mode())])
        except Exception:  # noqa: BLE001 - bool channels do not expose interpolation
            pass
    default = None
    try:
        if not hasattr(channel, "has_default") or channel.has_default():
            default = _plain(channel.get_default())
    except Exception:  # noqa: BLE001
        pass
    raw = str(channel.channel_name)
    return {"name": norm_channel(raw), "raw": raw, "default": default, "keys": keys, "key_modes": key_modes}


def effective_section_range(has_start, start, has_end, end, playback):
    """Represent infinite section endpoints by the sequence playback boundary."""
    if not isinstance(playback, (list, tuple)) or len(playback) != 2:
        raise PlanError("PLAYBACK_RANGE_REQUIRED")
    lo = int(start) if has_start else int(playback[0])
    hi = int(end) if has_end else int(playback[1])
    if hi <= lo:
        raise PlanError("SECTION_RANGE_EMPTY|%d|%d" % (lo, hi))
    return [lo, hi]


def _track_spec(track, playback):
    cls = track.get_class().get_name()
    prop = path = ""
    try:
        prop, path = str(track.get_property_name()), str(track.get_property_path())
    except Exception:  # noqa: BLE001
        pass
    sections = []
    for sec in track.get_sections():
        has_start, has_end = bool(sec.has_start_frame()), bool(sec.has_end_frame())
        row = {"range": effective_section_range(
                    has_start, sec.get_start_frame() if has_start else None,
                    has_end, sec.get_end_frame() if has_end else None, playback),
               "channels": [_channel_row(ch) for ch in sec.get_all_channels()]}
        try:
            row["completion"] = enum_token(sec.get_completion_mode())
        except Exception:  # noqa: BLE001
            row["completion"] = None
        if cls == "MovieSceneGeometryCacheTrack":
            prm = sec.get_editor_property("params")
            row.update({"start_offset": int(prm.get_editor_property("start_frame_offset").value),
                        "end_offset": int(prm.get_editor_property("end_frame_offset").value),
                        "asset": prm.get_editor_property("geometry_cache_asset").get_path_name().split(".")[0]})
        sections.append(row)
    return {"class": cls, "name": str(track.get_display_name()), "prop": prop, "path": path, "sections": sections}


def _one_binding(seq, name, run):
    rows = [b for b in seq.get_bindings() if str(b.get_display_name()) == name]
    if len(rows) != 1:
        _stop(run, "BINDING_COUNT|%s|%d" % (name, len(rows)))
    return rows[0]


def _one_track(binding, cls, run, display=None, prop=None):
    rows = []
    for track in binding.get_tracks():
        if track.get_class().get_name() != cls:
            continue
        if display is not None and str(track.get_display_name()) != display:
            continue
        if prop is not None:
            try:
                if str(track.get_property_name()) != prop:
                    continue
            except Exception:  # noqa: BLE001
                continue
        rows.append(track)
    if len(rows) != 1:
        _stop(run, "TRACK_COUNT|%s|%s|%s|%s|%d" % (binding.get_display_name(), cls, display, prop, len(rows)))
    return rows[0]


def _handles(seq, run):
    drape = _one_binding(seq, DRAPE, run)
    spot = _one_binding(seq, SPOT, run)
    vis = [t for t in drape.get_tracks() if t.get_class().get_name() == "MovieSceneVisibilityTrack"]
    for track in vis:
        prop = str(track.get_property_name())
        if prop not in ("bHidden", "bHiddenInGame"):
            _stop(run, "VISIBILITY_PROPERTY|%r" % prop)
    return {"drape_binding": drape, "spot_binding": spot,
            "spawn": _one_track(drape, "MovieSceneSpawnTrack", run),
            "transform": _one_track(drape, "MovieScene3DTransformTrack", run, SLEIGHT_TRACK),
            "gc": _one_track(drape, "MovieSceneGeometryCacheTrack", run),
            "visibility": vis,
            "spot_intensity": _one_track(spot, "MovieSceneFloatTrack", run, SPOT_TRACK, "Intensity")}


def _evaluate_one(seq, track, frame):
    values = {}
    rng = seq.make_range(int(frame), 1)
    rate = seq.get_display_rate()
    for channel in list(track.get_sections())[0].get_all_channels():
        rows = list(channel.evaluate_keys(rng, rate))
        if len(rows) != 1:
            raise PlanError("EVALUATE_KEYS_RETURNED_%d|%s" % (len(rows), channel.channel_name))
        values[norm_channel(str(channel.channel_name))] = _plain(rows[0])
    return values


def _evaluate_float_range(seq, track, start, count):
    rng = seq.make_range(int(start), int(count))
    rate = seq.get_display_rate()
    channels_live = list(list(track.get_sections())[0].get_all_channels())
    if len(channels_live) != 1:
        raise PlanError("FLOAT_CHANNEL_COUNT|%d" % len(channels_live))
    values = list(channels_live[0].evaluate_keys(rng, rate))
    if len(values) != int(count):
        raise PlanError("EVALUATE_RANGE_COUNT|%d!=%d" % (len(values), count))
    return [[int(start) + i, float(value)] for i, value in enumerate(values)]


def _snapshot(seq):
    playback = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    bindings = []
    for binding in seq.get_bindings():
        parent = binding.get_parent()
        bindings.append({"guid": _guid(binding.get_id()), "name": str(binding.get_display_name()),
                         "parent": _guid(parent.get_id()) if parent is not None and parent.is_valid() else "",
                         "tracks": sorted((_track_spec(t, playback) for t in binding.get_tracks()),
                                           key=lambda x: (x["class"], x["name"], x["prop"]))})
    bindings.sort(key=lambda x: (x["name"], x["guid"]))
    return {"playback": playback, "bindings": bindings}


def _facts(n, seq, run):
    handles = _handles(seq, run)
    rate = seq.get_display_rate()
    playback = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    specs = {key: _track_spec(handles[key], playback) for key in ("spawn", "transform", "gc", "spot_intensity")}
    specs["visibility"] = [_track_spec(t, playback) for t in handles["visibility"]]
    count = playback[1] - playback[0]
    spot_eval = _evaluate_float_range(seq, handles["spot_intensity"], playback[0], count)
    sp = list(channels(specs["spawn"]).values())[0]
    ons = [int(f) for f, v in sp["keys"] if v]
    offs = sorted(int(f) for f, v in sp["keys"] if not v and ons and int(f) > min(ons))
    if not ons or not offs:
        _stop(run, "CURTAIN_SPAWN_SHAPE|%r" % sp["keys"])
    hung_ref = min(playback[1] - 1, offs[0] - 1)
    hung_pose = _evaluate_one(seq, handles["transform"], hung_ref)
    path = "%s/%s" % (SEQ_DIR, SEQS[n])
    owned = {key: {"binding_guid": _guid(handles[("drape_binding" if key != "spot_intensity" else "spot_binding")].get_id()),
                   "class": specs[key]["class"], "name": specs[key]["name"], "prop": specs[key]["prop"]}
             for key in ("spawn", "transform", "gc", "spot_intensity")}
    owned["visibility"] = [{"binding_guid": _guid(handles["drape_binding"].get_id()), "class": row["class"],
                            "name": row["name"], "prop": row["prop"]} for row in specs["visibility"]]
    return {"interaction": n, "sequence": path, "fps": rate.numerator / float(rate.denominator), "playback": playback,
            "spot_evaluated": spot_eval, "hung_pose": hung_pose, "owned": owned, **specs}


def _write_spec(track, spec, run):
    ue = _ue()
    old = list(track.get_sections())
    if len(old) != len(spec["sections"]):
        _stop(run, "SECTION_COUNT_CHANGED|%s" % spec["class"])
    # GC retains its section and params; only range changes. Other owned tracks are recreated exactly.
    if spec["class"] == "MovieSceneGeometryCacheTrack":
        for live, want in zip(old, spec["sections"]):
            live.set_range(int(want["range"][0]), int(want["range"][1]))
        return
    for section in old:
        track.remove_section(section)
    for wanted in spec["sections"]:
        section = track.add_section(); section.set_range(int(wanted["range"][0]), int(wanted["range"][1]))
        completion = wanted.get("completion")
        if completion and hasattr(ue.MovieSceneCompletionMode, completion):
            section.set_completion_mode(getattr(ue.MovieSceneCompletionMode, completion))
        live_channels = {norm_channel(str(c.channel_name)): c for c in section.get_all_channels()}
        for row in wanted["channels"]:
            channel = live_channels.get(row["name"])
            if channel is None:
                _stop(run, "CHANNEL_MISSING|%s" % row["name"])
            if row["default"] is not None:
                channel.set_default(row["default"])
            modes = {float(f): mode for f, mode in row.get("key_modes", [])}
            for frame, value in row["keys"]:
                if isinstance(value, bool):
                    key = channel.add_key(ue.FrameNumber(int(frame)), bool(value), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
                else:
                    mode_name = modes.get(float(frame), "LINEAR")
                    mode = getattr(ue.MovieSceneKeyInterpolation, mode_name, ue.MovieSceneKeyInterpolation.LINEAR)
                    key = channel.add_key(ue.FrameNumber(int(frame)), float(value), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE,
                                          interpolation=mode)
                if key is None:
                    _stop(run, "ADD_KEY_NONE|%s|%s" % (row["name"], frame))


def _owned_live(seq, run):
    h = _handles(seq, run)
    playback = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    return {"spawn": _track_spec(h["spawn"], playback),
            "transform": _track_spec(h["transform"], playback),
            "gc": _track_spec(h["gc"], playback),
            "visibility": [_track_spec(t, playback) for t in h["visibility"]],
            "spot_intensity": _track_spec(h["spot_intensity"], playback)}


def _apply_owned(seq, wanted, run):
    h = _handles(seq, run)
    playback = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    seq.modify()
    if compare(_track_spec(h["spawn"], playback), wanted["spawn"]):
        _write_spec(h["spawn"], wanted["spawn"], run)
    if compare(_track_spec(h["transform"], playback), wanted["transform"]):
        _write_spec(h["transform"], wanted["transform"], run)
    if compare(_track_spec(h["gc"], playback), wanted["gc"]):
        _write_spec(h["gc"], wanted["gc"], run)
    if len(h["visibility"]) != len(wanted["visibility"]):
        _stop(run, "VISIBILITY_TRACK_COUNT_DRIFT")
    for track, spec in zip(h["visibility"], wanted["visibility"]):
        if compare(_track_spec(track, playback), spec):
            _write_spec(track, spec, run)
    if compare(_track_spec(h["spot_intensity"], playback), wanted["spot_intensity"]):
        _write_spec(h["spot_intensity"], wanted["spot_intensity"], run)


def _backup(path, label, run):
    ue = _ue()
    root = ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())
    folder = os.path.join(root, "Backups", "Pre%s-%s" % (label, run))
    os.makedirs(folder, exist_ok=False)
    src = _content_file(path); dst = os.path.join(folder, os.path.basename(src))
    if not os.path.isfile(src):
        _stop(run, "BACKUP_SOURCE_MISSING|%s" % src)
    shutil.copy2(src, dst)
    if os.path.getsize(src) != os.path.getsize(dst):
        _stop(run, "BACKUP_SIZE_MISMATCH")
    return folder, dst


def _save(path, run):
    if _census() != {"content": [path], "maps": []}:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(_census()))
    if not bool(_ue().EditorAssetLibrary.save_asset(path, only_if_is_dirty=True)):
        _stop(run, "SAVE_FAILED|%s" % path)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))


def _report_one(n, seq, p, run):
    facts = _facts(n, seq, run)
    plan = build_plan(facts, p)
    return {"interaction": n, "sequence": facts["sequence"], "plan": plan, "plan_digest": plan["digest"],
            "timing": plan["timing"], "needs_change": plan["needs_change"], "claims": CLAIMS,
            "warnings": ["VISUAL_ACCEPTANCE_PENDING: offline structure cannot prove the shadow lands on opaque cloth by eye"]}


def run_dry(run, interaction, p, confirm):
    _preflight("DRY", interaction if isinstance(interaction, int) else 1, run, confirm)
    rows = _sequences(run)
    selected = TARGETS if interaction == "ALL" else (int(interaction),)
    report = {"schema_version": 1, "run": run, "mode": "DRY", "mutated": False, "params": p, "rows": []}
    for n in selected:
        row = _report_one(n, rows[n][1], p, run)
        report["rows"].append(row)
        _write_json(os.path.join(_here(), PLAN_PATTERN % n), {"run": run, "interaction": n,
                    "plan_digest": row["plan_digest"], "params": p, "needs_change": row["needs_change"]})
    report["table"] = [row["timing"] for row in report["rows"]]
    out = os.path.join(_here(), DRY_PATTERN % run)
    _write_json(out, report)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % json.dumps(_census()))
    _log("%s_DRY_OK|run=%s|interactions=%s|changes=%d|mutated=0|dirty=0|report=%s" %
         (MARK, run, ",".join("I%d" % n for n in selected), sum(int(r["needs_change"]) for r in report["rows"]), out))
    return report


def run_apply(run, n, p, confirm):
    _preflight("APPLY", n, run, confirm)
    sequences = _sequences(run)
    if n != 1:
        enforce_apply_order(n, _report_one(1, sequences[1][1], p, run)["needs_change"])
    seq = sequences[n][1]
    row = _report_one(n, seq, p, run)
    plan = row["plan"]
    pf = _load_json(os.path.join(_here(), PLAN_PATTERN % n)) or {}
    if pf.get("plan_digest") != plan["digest"]:
        _stop(run, "PLAN_CHANGED_SINCE_DRY|rerun DRY")
    if not plan["needs_change"]:
        _log("%s_APPLY_OK|run=%s|interaction=I%d|changed=0|reason=already_compliant|saved=none" % (MARK, run, n))
        return row
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    if os.path.exists(record_path):
        _stop(run, "RECORD_EXISTS|%s|REVERT first" % record_path)
    before_snapshot = _snapshot(seq)
    originals = _owned_live(seq, run)
    backup, copied = _backup(plan["sequence"], "P89CurtainBeforeShadow-I%d" % n, run)
    record = {"schema_version": 1, "run": run, "interaction": n, "sequence": plan["sequence"], "applied": False,
              "backup": backup, "backup_files": [copied], "plan": plan, "plan_digest": plan["digest"],
              "originals": originals, "snapshot_before": before_snapshot, "dirty_before": _census()}
    _write_json(record_path, record, exclusive=True)
    _apply_owned(seq, plan["writes"], run)
    got = _owned_live(seq, run)
    problems = compare(got, plan["writes"])
    if problems:
        _stop(run, "PRESAVE_OWNED_READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(problems))
    after_snapshot = _snapshot(seq)
    if without_owned(after_snapshot, plan["owned"]) != without_owned(before_snapshot, plan["owned"]):
        problems.append("UNOWNED_SEQUENCE_STATE_CHANGED")
    if problems:
        _stop(run, "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(problems))
    record.update({"owned_after": got, "snapshot_after": after_snapshot})
    _write_json(record_path, record)
    _save(plan["sequence"], run)
    seq = _ue().load_asset(plan["sequence"])
    got2 = _owned_live(seq, run)
    problems = compare(got2, plan["writes"])
    if json.dumps(_snapshot(seq), sort_keys=True, default=str) != json.dumps(after_snapshot, sort_keys=True, default=str):
        problems.append("POSTSAVE_SNAPSHOT_DIFFERS")
    if problems:
        _stop(run, "POSTSAVE_READBACK|%s|restore from %s" % (json.dumps(problems), backup))
    # Re-plan from saved evaluated state: the positive safety invariant must now pass.
    verify_plan = build_plan(_facts(n, seq, run), p)
    if verify_plan["needs_change"]:
        _stop(run, "POSTSAVE_STILL_FAULTY|restore from %s" % backup)
    record.update({"applied": True, "dirty_after": _census(), "verify_timing": verify_plan["timing"]})
    _write_json(record_path, record)
    _log("%s_APPLY_OK|run=%s|interaction=I%d|changed=1|ready=%s|first_nonzero=%s|margin_frames=%s|saved=%s|backup=%s|record=%s" %
         (MARK, run, n, verify_plan["timing"]["before"]["curtain_ready"],
          verify_plan["timing"]["before"]["spot_first_nonzero"], verify_plan["timing"]["before"]["margin_frames"],
          plan["sequence"], backup, record_path))
    return record


def run_revert(run, n, p, confirm):
    _preflight("REVERT", n, run, confirm)
    seq = _sequences(run)[n][1]
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = _load_json(record_path)
    if not record or not record.get("applied"):
        _stop(run, "NOTHING_TO_REVERT")
    live = _owned_live(seq, run)
    problems = compare(live, record["owned_after"])
    if problems:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%s|restore from %s" % (json.dumps(problems), record["backup"]))
    backup, copied = _backup(record["sequence"], "P89CurtainBeforeShadow-I%d-Revert" % n, run)
    txn = os.path.join(_here(), "p89_curtain_before_shadow_revert_%s.json" % run)
    _write_json(txn, {"run": run, "interaction": n, "source_record": record_path, "backup": backup,
                      "backup_files": [copied], "snapshot_before_revert": _snapshot(seq)}, exclusive=True)
    _apply_owned(seq, record["originals"], run)
    problems = compare(_owned_live(seq, run), record["originals"])
    if problems:
        _stop(run, "REVERT_PRESAVE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(problems))
    _save(record["sequence"], run)
    seq = _ue().load_asset(record["sequence"])
    problems = compare(_owned_live(seq, run), record["originals"])
    if json.dumps(_snapshot(seq), sort_keys=True, default=str) != json.dumps(record["snapshot_before"], sort_keys=True, default=str):
        problems.append("REVERT_FULL_SNAPSHOT_MISMATCH")
    if problems:
        _stop(run, "REVERT_READBACK|%s|restore from %s" % (json.dumps(problems), backup))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    _write_json(txn, dict(_load_json(txn), completed=True, archived_record=archived))
    _log("%s_REVERT_OK|run=%s|interaction=I%d|saved=%s|backup=%s|record=%s" %
         (MARK, run, n, record["sequence"], backup, archived))


def main(args):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P89-%Y%m%d-%H%M%S"))
    try:
        interaction = args.get("interaction", "ALL")
        if isinstance(interaction, str) and interaction.upper() == "ALL":
            interaction = "ALL"
        else:
            interaction = int(str(interaction).upper().lstrip("I"))
            if interaction not in TARGETS:
                raise PlanError("INTERACTION|%r" % interaction)
        if mode not in ("DRY", "APPLY", "REVERT"):
            raise PlanError("MODE|%r" % mode)
        if mode != "DRY" and interaction == "ALL":
            raise PlanError("APPLY_REVERT_REQUIRE_ONE_INTERACTION")
        p = merged_params(args.get("params") or {})
        if mode == "DRY":
            return run_dry(run, interaction, p, args.get("confirm"))
        if mode == "APPLY":
            return run_apply(run, interaction, p, args.get("confirm"))
        return run_revert(run, interaction, p, args.get("confirm"))
    except PlanError as error:
        _stop(run, "PLAN_REFUSED|%s" % error)
