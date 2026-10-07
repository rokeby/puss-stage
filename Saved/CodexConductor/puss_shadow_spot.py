"""Puss shadow spot: DRY / APPLY / REVERT. Occasional bright spot behind the shadow cat (Gary, 7 Oct).

Gary 7 Oct: "a Puss walking shadow spotlight which lights Puss from behind, very occasionally appearing (doesn't
matter if it's kind of floating as it's not visible) and shining a long bright light that creates a longish shadow
in front of the camera, only for a few seconds."

MECHANISM (needs held patch Scripts/patches/2026-10-07_PS_puss_shadow_spot.patch BUILT; this tool refuses
APPLY otherwise and DRY reports it):
* declaration-proven (patch): AInfinityStageCameraRig gains ShadowSpotCues (TArray<FInfinityShadowSpotCue>
  {PassageSeconds, AttackSeconds, HoldSeconds, ReleaseSeconds, Intensity, Label}), ShadowSpotOffset and
  ShadowSpotRotation. Empty cues = the follow light behaves exactly as before. Non-empty: the rig's existing
  FollowLight spot is placed at ShadowSpotOffset/Rotation, casts shadows, keeps the component's own units/cone/colour/
  radii, and is visible only while
  the envelope (smoothstep attack, hold, smoothstep release) is > 0 and the rig is live. Evaluated in
  EvaluateAtMasterFrame from (MasterFrame - Passage.SegmentStartFrame) - a pure function of Master time, so
  play/pause/scrub/reverse agree and a Master rebuild that moves the Passage moves the cues with it.
* declaration-proven (current tree): FollowLight is attached to SceneRoot = the rig (InfinityStageCameraRig.cpp:
  118-125); the rig follows the camera (incl. gait bob and Camera.HeightOffsetCm keys). The shadow cat sits at
  ShadowFigureOffset (-200,0,0) under it, casts shadows with its body out of the main pass in game (cpp:183-236).
  The rig is NOT a Master binding: the Passage track finds it by Passage GUID (MovieSceneInfinityPassageTrack.cpp:
  166-189), so keying the light in the Master would need a new possessable that RebuildManagedMaster never
  maintains and whose keys sit at ABSOLUTE frames (puss-passage-keys-absolute) - not used.

DATA: rig properties in the level (never the Show, never the Master). Times are Passage-relative seconds.
  passage_seconds = song_seconds - music_offset_s, music_offset_s = (rail.SourceInFrame + RailOffsetFrames)/tick
  because the Master's music section starts at the Passage segment start with that start offset
  (InfinityStageSequenceBuilderLibrary.cpp:538-540).

CUE CHOICE (pure, choose_cues): majorChangeProposals of the Passage's analysis; score = strength x
(0.4 + meanIntensity of the section that STARTS at the change); changes into near-silence (mean < 0.05) are endings,
excluded; the light peaks ON the change (attack ends at it), snapped to the most salient notable note within
+-0.35 s when a notes file exists (P01_notes.json); not in the first min_start_s, must finish before the music ends
minus end_margin_s; 2 cues when the music is >= 60 s, else 1; >= min_spacing_s apart.

GEOMETRY (pure, spot_geometry): light x_L behind the camera, cat at x_C (=ShadowFigureOffset.x), cat top h above the
floor, eye E above the floor. Shadow from the cat's feet of length Lc = h*d/(H-h), d = x_C - x_L; tip ahead of the
camera = Lc + x_C. For a target tip ahead T: Lc = T - x_C, H = h*(d+Lc)/Lc, offset.z = H - E; pitch aims the cone
axis at the floor aim_fraction of the way along the shadow. LIVE: h and E are measured per rig (cat skeletal mesh
bounds and the camera pose at each cue), offline they are args (inferred).

REFERENCE (Gary 7 Oct): he placed and saved a level SpotLight labelled "PussFollowSpot" in P03 at the distance that
gives the shadow he wants. geometry_source "reference" (default): DRY READS it (never moves/edits/deletes it):
transform, cone angles, intensity + units, attenuation, source radius/length, colour/temperature, shadows, attach
parent; and the P03 rig's and shadow cat's world transforms as saved (same moment, no evaluation). The spot is
expressed in the rig frame (inverse_transform_location/rotation) -> ShadowSpotOffset/Rotation; z is re-based per rig
so the light keeps the same height ABOVE THE FLOOR (eye heights differ: P01 150, others 180 measured 26 Sep).
Its light settings are copied onto each rig's FollowLight component; its intensity becomes the cue peak (same units).
Why drive the rig's FollowLight and not his actor: his actor is fixed in the world in P03 while the camera walks on,
so the shadow would shorten, swing and leave; the rig light travels with the cat in every Passage. His actor is
reported (visibility, hidden-in-game) because if it stays visible it keeps lighting P03 all the time - Gary's call.
geometry_source "computed": spot_geometry below (used offline and as a cross-check).

Args (puss_shadow_spot_args.json via puss_shadow_spot_run.py):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> PUSSSHADOWSPOT", "passages": {"Passage 1": {"analysis": ..,
   "notes": ..|null}, ...}, "target_tip_ahead_cm": 400, "light_x_cm": -600, "intensity_cd": 15000, "attack_s": 0.5,
   "hold_s": 3.0, "release_s": 1.0, ..., "allow_dirty": []}
Markers: PUSSSHADOWSPOT_DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|...; any stop PUSSSHADOWSPOT_STOPPED.
Writes (APPLY/REVERT): the level only (rig properties); Backups/PrePussShadowSpot-<run> first; record
puss_shadow_spot_record.json written BEFORE the first write; narrow save (any other dirty package stops it).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import shutil

MARK = "PUSSSHADOWSPOT"
VALID_MODES = ("DRY", "APPLY", "REVERT")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORD_NAME = "puss_shadow_spot_record.json"
SNAP_WINDOW_S = 0.35
SILENCE_MEAN = 0.05
MIN_CLEARANCE_CM = 40.0
EYE_SPREAD_TOL_CM = 10.0


class SpotError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise SpotError(message)


def _finite(value, label):
    value = float(value)
    require(math.isfinite(value), "ARG_NOT_FINITE|" + label)
    return value


DEFAULTS = {
    "target_tip_ahead_cm": 400.0, "light_x_cm": -600.0, "cat_x_cm": -200.0, "aim_fraction": 0.6,
    "intensity_cd": 15000.0, "attack_s": 0.5, "hold_s": 3.0, "release_s": 1.0,
    "min_start_s": 6.0, "end_margin_s": 4.0, "min_spacing_s": 20.0, "two_cue_min_music_s": 60.0, "latest_cue_end_s": {},
    "offline_cat_top_cm": 200.0, "offline_eye_cm": {}, "offline_passage_start_s": {},
}
GEOMETRY_SOURCES = ("reference", "computed")
LIGHT_PROPS = ("intensity_units", "outer_cone_angle", "inner_cone_angle", "attenuation_radius", "source_radius",
               "soft_source_radius", "source_length", "light_color", "use_temperature", "temperature", "cast_shadows")


def check_args(args):
    args = dict(args or {})
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(args.get("confirm") == "%s %s" % (mode, MARK), "CONFIRM_MISSING|need='%s %s'" % (mode, MARK))
    out = {"mode": mode, "confirm": args.get("confirm"),
           "allow_dirty": sorted(str(x) for x in (args.get("allow_dirty") or []))}
    for key, default in DEFAULTS.items():
        value = args.get(key, default)
        out[key] = value if isinstance(default, dict) else _finite(value, key)
    out["geometry_source"] = str(args.get("geometry_source", "reference"))
    require(out["geometry_source"] in GEOMETRY_SOURCES, "GEOMETRY_SOURCE_INVALID|" + out["geometry_source"])
    out["reference_label"] = str(args.get("reference_label", "PussFollowSpot"))
    out["reference_passage"] = str(args.get("reference_passage", "Passage 3"))
    passages = args.get("passages") or {}
    require(isinstance(passages, dict) and passages, "PASSAGES_MISSING")
    out["passages"] = {str(k): {"analysis": str(v["analysis"]), "notes": v.get("notes")} for k, v in passages.items()}
    require(0.0 <= out["attack_s"] <= 3.0 and 0.0 <= out["release_s"] <= 5.0, "ENVELOPE_OUT_OF_RANGE")
    require(0.5 <= out["hold_s"] <= 8.0, "HOLD_OUT_OF_RANGE|%r" % out["hold_s"])
    require(0.0 < out["intensity_cd"] <= 200000.0, "INTENSITY_OUT_OF_RANGE|%r" % out["intensity_cd"])
    require(out["light_x_cm"] < out["cat_x_cm"] < 0.0, "LIGHT_MUST_BE_BEHIND_CAT")
    require(100.0 <= out["target_tip_ahead_cm"] <= 1200.0, "TIP_OUT_OF_RANGE")
    require(0.1 <= out["aim_fraction"] <= 1.0, "AIM_FRACTION_OUT_OF_RANGE")
    return out


# ----------------------------------------------------------------------------------------------- pure maths
def smoothstep(u):
    u = min(1.0, max(0.0, float(u)))
    return u * u * (3.0 - 2.0 * u)


def envelope(cues, t):
    """Mirror of AInfinityStageCameraRig::EvaluateShadowSpot (patch PS). Returns (weight, candelas)."""
    best_w, best_i = 0.0, 0.0
    for c in cues:
        a, h, r = max(0.0, c["attack_s"]), max(0.0, c["hold_s"]), max(0.0, c["release_s"])
        local = t - c["passage_s"]
        if local < 0.0 or local >= a + h + r:
            w = 0.0
        elif local < a:
            w = smoothstep(local / a)
        elif local <= a + h:
            w = 1.0
        else:
            w = 1.0 - smoothstep((local - a - h) / r)
        best_w = max(best_w, w)
        best_i = max(best_i, w * max(0.0, c["intensity_cd"]))
    return min(1.0, max(0.0, best_w)), best_i


def score_moments(analysis):
    """[(score, time_s, strength, section)] for each major change, best first. Changes into near-silence excluded."""
    sections = analysis.get("expressiveSections") or []
    rows = []
    for change in analysis.get("majorChangeProposals") or []:
        t = float(change["timeSeconds"])
        after = [s for s in sections if abs(float(s["startSeconds"]) - t) < 1e-3]
        require(len(after) <= 1, "SECTION_AMBIGUOUS|%r" % t)
        if not after:
            continue
        mean = float(after[0]["meanIntensity"])
        if mean < SILENCE_MEAN:
            continue
        strength = float(change["strength"])
        rows.append((strength * (0.4 + mean), t, strength, after[0]["label"]))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return rows


def snap_to_note(t, notes):
    """Most salient notable note within SNAP_WINDOW_S of t (song seconds); t itself when none."""
    if not notes:
        return t, None
    near = [n for n in notes.get("notes", []) if n.get("notable") and abs(float(n["song_s"]) - t) <= SNAP_WINDOW_S]
    if not near:
        return t, None
    best = max(near, key=lambda n: (float(n["salience"]), -abs(float(n["song_s"]) - t)))
    return float(best["song_s"]), best


def choose_cues(analysis, notes, music_offset_s, args, latest_end_s=None):
    """Passage-relative cues. The light reaches full at the musical moment (attack ends there).
    latest_end_s: a cue must be fully released by this passage time (args latest_cue_end_s per passage; P06 dark 7 Oct)."""
    duration = float(analysis["durationSeconds"])
    want = 2 if duration >= args["two_cue_min_music_s"] else 1
    total = args["attack_s"] + args["hold_s"] + args["release_s"]
    chosen = []
    for score, t, strength, label in score_moments(analysis):
        if len(chosen) >= want:
            break
        moment, note = snap_to_note(t, notes)
        start = moment - args["attack_s"]
        if start < args["min_start_s"] or start + total > duration - args["end_margin_s"]:
            continue
        if latest_end_s is not None and start - music_offset_s + total > float(latest_end_s):
            continue
        if any(abs(moment - c["song_moment_s"]) < args["min_spacing_s"] for c in chosen):
            continue
        chosen.append({"song_change_s": t, "song_moment_s": moment, "snapped_to_note": note is not None,
                       "passage_s": round(start - music_offset_s, 4), "attack_s": args["attack_s"],
                       "hold_s": args["hold_s"], "release_s": args["release_s"], "intensity_cd": args["intensity_cd"],
                       "score": round(score, 4), "strength": strength, "section_after": label,
                       "label": "PS %s change %.2fs (%s, str %.2f)%s" % (
                           analysis.get("sourceName", "?"), t, label, strength,
                           " snapped %.3fs" % moment if note else "")})
    chosen.sort(key=lambda c: c["passage_s"])
    require(chosen, "NO_CUE_FITS|%s" % analysis.get("sourceName"))
    return chosen


def spot_geometry(eye_cm, cat_top_cm, args):
    """Offset (relative to the rig = the camera) and pitch for a target shadow tip ahead of the camera."""
    x_l, x_c, tip = args["light_x_cm"], args["cat_x_cm"], args["target_tip_ahead_cm"]
    h, eye = float(cat_top_cm), float(eye_cm)
    require(h > 10.0 and eye > 10.0, "GEOMETRY_INPUT|h=%r|eye=%r" % (h, eye))
    d = x_c - x_l
    lc = tip - x_c
    light_h = h * (d + lc) / lc
    require(light_h - h >= MIN_CLEARANCE_CM, "LIGHT_TOO_GRAZING|H=%.1f|h=%.1f" % (light_h, h))
    aim_x = x_c + args["aim_fraction"] * lc
    pitch = -math.degrees(math.atan2(light_h, aim_x - x_l))
    return {"offset": [x_l, 0.0, round(light_h - eye, 2)], "pitch_deg": round(pitch, 2),
            "light_floor_height_cm": round(light_h, 2), "shadow_from_cat_cm": round(lc, 2),
            "tip_ahead_of_camera_cm": round(tip, 2), "cat_top_cm": h, "eye_cm": eye,
            "light_to_aim_cm": round(math.hypot(light_h, aim_x - x_l), 1)}


def rebase_reference(ref_offset, ref_eye_cm, rig_eye_cm):
    """Same light height above the floor on a rig whose eye differs from the reference rig's."""
    x, y, z = ref_offset
    return [float(x), float(y), round(float(z) + float(ref_eye_cm) - float(rig_eye_cm), 3)]


def implied_tip(light_rel, cat_rel_xy, eye_cm, cat_top_cm):
    """Floor point (rig frame, x ahead / y right) of the shadow of the cat's top point under a light at light_rel
    (rig frame, z relative to the eye). None when the light is not above the cat top."""
    lx, ly, lz = light_rel
    cx, cy = cat_rel_xy
    light_h = lz + eye_cm
    if light_h <= cat_top_cm:
        return None
    k = light_h / (light_h - cat_top_cm)
    tx, ty = lx + (cx - lx) * k, ly + (cy - ly) * k
    return {"x_ahead_cm": round(tx, 1), "y_cm": round(ty, 1), "light_floor_height_cm": round(light_h, 1),
            "shadow_len_from_cat_cm": round(math.hypot(tx - cx, ty - cy), 1)}


def tip_ahead(light_h, cat_top_cm, args):
    """Shadow tip ahead of the camera for a given cat top (sensitivity). None when the light is not above it."""
    d = args["cat_x_cm"] - args["light_x_cm"]
    if light_h <= cat_top_cm:
        return None
    return cat_top_cm * d / (light_h - cat_top_cm) + args["cat_x_cm"]


def plan_passage(label, analysis, notes, music_offset_s, eye_cm, cat_top_cm, args, reference=None):
    cues = choose_cues(analysis, notes, music_offset_s, args, (args.get("latest_cue_end_s") or {}).get(label))
    geo = spot_geometry(eye_cm, cat_top_cm, args)
    geo["source"] = "computed"
    geo["rotation"] = [geo["pitch_deg"], 0.0, 0.0]
    if reference is not None:
        offset = rebase_reference(reference["offset"], reference["eye_cm"], eye_cm)
        lx, ly, lz = offset
        geo = {"source": "reference", "offset": offset, "rotation": list(reference["rotation"]),
               "implied_tip": implied_tip(offset, reference["cat_rel_xy"], eye_cm, cat_top_cm),
               "computed_cross_check": geo, "eye_cm": eye_cm, "cat_top_cm": cat_top_cm,
               "light_floor_height_cm": round(lz + eye_cm, 2),
               "light_to_aim_cm": geo["light_to_aim_cm"]}
        for c in cues:
            c["intensity_cd"] = float(reference["light"]["intensity"])
    sens = {str(dh): tip_ahead(geo["light_floor_height_cm"], cat_top_cm + dh, args) for dh in (-20, 0, 20)}
    lux = cues[0]["intensity_cd"] / ((geo["light_to_aim_cm"] / 100.0) ** 2)  # meaningful only in candelas
    return {"passage": label, "cues": cues, "geometry": geo, "tip_ahead_sensitivity_cm": sens,
            "aim_illuminance_lux": round(lux, 1), "music_offset_s": music_offset_s}


def show_times(plan, passage_start_s):
    if passage_start_s is None:
        return None
    return [{"attack_start_show_s": round(passage_start_s + c["passage_s"], 3),
             "full_show_s": round(passage_start_s + c["passage_s"] + c["attack_s"], 3),
             "off_show_s": round(passage_start_s + c["passage_s"] + c["attack_s"] + c["hold_s"] + c["release_s"], 3)}
            for c in plan["cues"]]


def cue_rows(plan):
    """What is written into ShadowSpotCues (property names of FInfinityShadowSpotCue)."""
    return [{"passage_seconds": c["passage_s"], "attack_seconds": c["attack_s"], "hold_seconds": c["hold_s"],
             "release_seconds": c["release_s"], "intensity": c["intensity_cd"], "label": c["label"]}
            for c in plan["cues"]]


def same_rows(a, b, tol=1e-4):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        for k in ("passage_seconds", "attack_seconds", "hold_seconds", "release_seconds", "intensity"):
            if abs(float(x[k]) - float(y[k])) > tol * max(1.0, abs(float(x[k]))):
                return False
        if str(x["label"]) != str(y["label"]):
            return False
    return True


def same_vec(a, b, tol=1e-3):
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def load_json(path, root):
    full = path if os.path.isabs(path) else os.path.join(root, path)
    with open(full, encoding="utf-8") as handle:
        return json.load(handle)


def offline_plan(args, project_root):
    """Everything DRY can know without Unreal: assumed eye/cat top, known passage starts (provenance in args)."""
    rows = []
    for label, src in sorted(args["passages"].items()):
        analysis = load_json(src["analysis"], project_root)
        notes = load_json(src["notes"], project_root) if src.get("notes") else None
        eye = float(args["offline_eye_cm"].get(label, 180.0))
        plan = plan_passage(label, analysis, notes, 0.0, eye, args["offline_cat_top_cm"], args)
        start = args["offline_passage_start_s"].get(label)
        plan["show_times"] = show_times(plan, None if start is None else float(start))
        plan["inferred"] = ["music_offset_s assumed 0", "eye %.0f cm assumed" % eye,
                            "cat top %.0f cm assumed" % args["offline_cat_top_cm"],
                            "passage start from args offline_passage_start_s (may be stale)"]
        rows.append(plan)
    return rows


# ----------------------------------------------------------------------------------------------- Unreal side
def _u():
    import unreal  # noqa: PLC0415 - only inside the editor
    return unreal


def _here():
    u = _u()
    return os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor")


def _project():
    u = _u()
    return u.Paths.convert_relative_path_to_full(u.Paths.project_dir())


def _log(text):
    _u().log(text)


def unwrap(result, count):
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    if count == 1 and not isinstance(result, tuple):
        return (result,)
    return result if isinstance(result, tuple) and len(result) == count else None


def _guid(value):
    return _u().GuidLibrary.conv_guid_to_string(value)


def _census():
    u = _u()
    return {"maps": sorted(p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": sorted(p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def _package_file(package):
    base = os.path.join(_project(), "Content", *package[len("/Game/"):].split("/"))
    for ext in (".uasset", ".umap"):
        if os.path.isfile(base + ext):
            return base + ext
    raise SpotError("PACKAGE_FILE_MISSING|" + package)


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _backup(run, prefix):
    root = os.path.join(_project(), "Backups", prefix + run)
    os.makedirs(root, exist_ok=False)
    src = _package_file(EXPECTED_WORLD)
    dst = os.path.join(root, EXPECTED_WORLD[len("/Game/"):].replace("/", os.sep) + os.path.splitext(src)[1])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    require(_sha(src) == _sha(dst), "BACKUP_HASH_MISMATCH")
    return {"root": root, "packages": [{"package": EXPECTED_WORLD, "backup": dst, "sha256": _sha(dst)}]}


def _patch_built():
    u = _u()
    return hasattr(u, "InfinityShadowSpotCue")


def _context(args):
    u = _u()
    require(os.path.normcase(os.path.normpath(_project())).rstrip("\\/")
            == os.path.normcase(os.path.normpath("E:/PussStage")), "WRONG_PROJECT")
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and world.get_path_name().split(".")[0] == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_ACTIVE")
    census = _census()
    if args["mode"] != "DRY":
        require(_patch_built(), "PS_PATCH_NOT_BUILT|apply+build Scripts/patches/2026-10-07_PS_puss_shadow_spot.patch")
        dirty = set(census["maps"]) | set(census["content"])
        require(dirty <= set(args["allow_dirty"]), "DIRTY_BEFORE|" + json.dumps(census))
    return world, census


def _passage(show, label):
    u = _u()
    rows = [p for p in show.get_editor_property("passage_settings") if str(p.get_editor_property("label")) == label]
    require(len(rows) == 1, "PASSAGE_ROW_COUNT|%s|%d" % (label, len(rows)))
    guid = rows[0].get_editor_property("passage_guid")
    rigs = []
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class().get_name() != "InfinityStageCameraRig":
            continue
        pa = actor.get_editor_property("passage_actor")
        if pa is not None and _guid(pa.get_editor_property("passage_guid")) == _guid(guid):
            rigs.append(actor)
    require(len(rigs) == 1, "RIG_COUNT|%s|%d" % (label, len(rigs)))
    rng = unwrap(u.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid), 2)
    require(rng is not None, "FRAME_RANGE_FAILED|" + label)
    music = rows[0].get_editor_property("music")
    rail_guid = _guid(music.get_editor_property("primary_rail_guid"))
    rails = [r for r in show.get_editor_property("music_rails") if _guid(r.get_editor_property("rail_guid")) == rail_guid]
    require(len(rails) == 1, "RAIL_COUNT|%s|%d" % (label, len(rails)))
    in_frame = rails[0].get_editor_property("source_in_frame").value
    off_frame = music.get_editor_property("rail_offset_frames").value
    sound = rails[0].get_editor_property("sound")
    sound_path = str(u.SystemLibrary.conv_soft_object_reference_to_string(sound))
    return {"label": label, "guid": guid, "rig": rigs[0], "seg": (int(rng[0]), int(rng[1])),
            "music_frames": int(in_frame) + int(off_frame), "sound_path": sound_path}


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rig_state(rig):
    rot = rig.get_editor_property("shadow_spot_rotation")
    rows = []
    for c in rig.get_editor_property("shadow_spot_cues"):
        rows.append({"passage_seconds": float(c.get_editor_property("passage_seconds")),
                     "attack_seconds": float(c.get_editor_property("attack_seconds")),
                     "hold_seconds": float(c.get_editor_property("hold_seconds")),
                     "release_seconds": float(c.get_editor_property("release_seconds")),
                     "intensity": float(c.get_editor_property("intensity")),
                     "label": str(c.get_editor_property("label"))})
    return {"cues": rows, "offset": _vec(rig.get_editor_property("shadow_spot_offset")),
            "rotation": [float(rot.pitch), float(rot.yaw), float(rot.roll)]}


def _write_rig(rig, state):
    u = _u()
    rig.modify()
    cues = []
    for row in state["cues"]:
        c = u.InfinityShadowSpotCue()
        for key, value in row.items():
            c.set_editor_property(key, value)
        cues.append(c)
    rig.set_editor_property("shadow_spot_cues", cues)
    rig.set_editor_property("shadow_spot_offset", u.Vector(*state["offset"]))
    p, y, r = state["rotation"]
    rig.set_editor_property("shadow_spot_rotation", u.Rotator(roll=r, pitch=p, yaw=y))
    got = _rig_state(rig)
    require(same_rows(state["cues"], got["cues"]) and same_vec(state["offset"], got["offset"])
            and same_vec(state["rotation"], got["rotation"]), "RIG_READBACK|" + json.dumps(got))


def _measure(ctx, tick_rate, plan_cues):
    """Eye above the floor at each cue's full point and the cat's top, from one rig evaluation (restored after)."""
    u = _u()
    rig = ctx["rig"]
    restore = rig.get_actor_transform()
    s = ctx["seg"][0]
    eyes = []
    top = None
    try:
        for c in plan_cues:
            tick = s + int(round((c["passage_s"] + c["attack_s"] + 0.5 * c["hold_s"]) * tick_rate))
            require(bool(rig.evaluate_at_master_frame(u.FrameNumber(tick))), "RIG_EVAL_FAILED|%d" % tick)
            cat = rig.get_editor_property("shadow_cat").get_editor_property("child_actor")
            require(cat is not None, "NO_CAT_ACTOR")
            meshes = cat.get_components_by_class(u.SkeletalMeshComponent)
            require(meshes, "NO_CAT_MESH")
            b_origin, b_extent, _r = u.SystemLibrary.get_component_bounds(meshes[0])   # no .bounds in Python
            floor = float(b_origin.z - b_extent.z)
            eyes.append(float(rig.get_actor_location().z) - floor)
            top = max(top or 0.0, float(2.0 * b_extent.z))
    finally:
        rig.set_actor_transform(restore, False, False)
    return eyes, top


def _plain(value):
    if hasattr(value, "r") and hasattr(value, "a"):
        return [int(value.r), int(value.g), int(value.b), int(value.a)]
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _light_settings(comp):
    out = {k: _plain(comp.get_editor_property(k)) for k in LIGHT_PROPS}
    out["intensity"] = float(comp.get_editor_property("intensity"))
    return out


def _read_reference(args, show):
    """Read-only. Gary's PussFollowSpot + the reference rig and cat as saved (no evaluation, nothing written)."""
    u = _u()
    hits = [a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
            if a.get_actor_label() == args["reference_label"]]
    require(len(hits) == 1, "REFERENCE_COUNT|%s|%d" % (args["reference_label"], len(hits)))
    spot = hits[0]
    comps = spot.get_components_by_class(u.SpotLightComponent)
    require(len(comps) == 1, "REFERENCE_NOT_A_SPOT|%d" % len(comps))
    light = comps[0]
    ctx = _passage(show, args["reference_passage"])
    rig = ctx["rig"]
    rig_tf = rig.get_actor_transform()
    spot_loc, spot_rot = light.get_world_location(), light.get_world_rotation()
    rel_loc = u.MathLibrary.inverse_transform_location(rig_tf, spot_loc)
    rel_rot = u.MathLibrary.inverse_transform_rotation(rig_tf, spot_rot)
    back = u.MathLibrary.transform_location(rig_tf, rel_loc)
    require(u.MathLibrary.vector_distance(back, spot_loc) < 0.1, "REFERENCE_RECOMPOSE|%s" % back)
    back_rot = u.MathLibrary.transform_rotation(rig_tf, rel_rot)
    fwd_a, fwd_b = u.MathLibrary.get_forward_vector(back_rot), u.MathLibrary.get_forward_vector(spot_rot)
    require(u.MathLibrary.dot_vector_vector(fwd_a, fwd_b) > 0.99999, "REFERENCE_RECOMPOSE_ROT")
    cat = rig.get_editor_property("shadow_cat").get_editor_property("child_actor")
    require(cat is not None, "NO_CAT_ACTOR")
    mesh = cat.get_components_by_class(u.SkeletalMeshComponent)
    require(mesh, "NO_CAT_MESH")
    # SkeletalMeshComponent has no .bounds in Python (live AttributeError 7 Oct); SystemLibrary returns (origin, extent, r)
    b_origin, b_extent, _r = u.SystemLibrary.get_component_bounds(mesh[0])
    floor = float(b_origin.z - b_extent.z)
    top = float(2.0 * b_extent.z)
    cat_rel = u.MathLibrary.inverse_transform_location(rig_tf, cat.get_actor_location())
    parent = spot.get_attach_parent_actor()
    eye = float(rig_tf.translation.z) - floor
    rr = rig_tf.rotation.rotator()
    offset = [round(float(rel_loc.x), 3), round(float(rel_loc.y), 3), round(float(rel_loc.z), 3)]
    return {"label": args["reference_label"], "actor_path": spot.get_path_name(),
            "attach_parent": parent.get_actor_label() if parent else None,
            "hidden_in_game": bool(spot.get_editor_property("hidden")), "visible": bool(light.is_visible()),
            "world_location": _vec(spot_loc),
            "world_rotation": [float(spot_rot.pitch), float(spot_rot.yaw), float(spot_rot.roll)],
            "rig_label": rig.get_actor_label(), "rig_world_location": _vec(rig_tf.translation),
            "rig_world_rotation": [float(rr.pitch), float(rr.yaw), float(rr.roll)],
            "cat_world_location": _vec(cat.get_actor_location()), "cat_rel": _vec(cat_rel),
            "cat_rel_xy": [float(cat_rel.x), float(cat_rel.y)], "cat_top_cm": top, "floor_z": floor, "eye_cm": eye,
            "offset": offset,
            "rotation": [round(float(rel_rot.pitch), 4), round(float(rel_rot.yaw), 4), round(float(rel_rot.roll), 4)],
            "light": _light_settings(light),
            "implied_tip_at_reference": implied_tip(offset, [float(cat_rel.x), float(cat_rel.y)], eye, top)}


def _write_light(rig, settings):
    """Copy light settings onto the rig's FollowLight component; read back."""
    u = _u()
    comp = rig.get_editor_property("follow_light")
    comp.modify()
    for k in LIGHT_PROPS:
        if k == "intensity_units":
            m = re.search(r"LightUnits\.(\w+)", str(settings[k]))
            require(m is not None, "UNITS_UNPARSED|%r" % settings[k])
            v = getattr(u.LightUnits, m.group(1))
        elif k == "light_color":
            r, g, b, a = settings[k]
            v = u.Color(r=r, g=g, b=b, a=a)
        else:
            v = settings[k]
        comp.set_editor_property(k, v)
    got = _light_settings(comp)
    bad = [k for k in LIGHT_PROPS
           if not (got[k] == settings[k] or (isinstance(got[k], float) and abs(got[k] - float(settings[k])) < 1e-3))]
    require(not bad, "LIGHT_READBACK|%s" % bad)


def _probe_light(ctx, tick_rate, cue):
    """Evaluate mid-hold (light on) then before the cue (off); return readings. Leaves the light OFF."""
    u = _u()
    rig = ctx["rig"]
    restore = rig.get_actor_transform()
    light = rig.get_editor_property("follow_light")
    s = ctx["seg"][0]
    out = {}
    try:
        for name, sec in (("on", cue["passage_seconds"] + cue["attack_seconds"] + 0.5 * cue["hold_seconds"]),
                          ("off", max(0.0, cue["passage_seconds"] - 1.0))):
            rig.evaluate_at_master_frame(u.FrameNumber(s + int(round(sec * tick_rate))))
            out[name] = {"visible": bool(light.is_visible()), "intensity": float(light.get_editor_property("intensity")),
                         "weight": float(rig.get_editor_property("current_shadow_spot_weight"))}
    finally:
        rig.set_actor_transform(restore, False, False)
    return out


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)


def _save_narrow():
    u = _u()
    census = _census()
    require(not census["content"] and not (set(census["maps"]) - {EXPECTED_WORLD}),
            "OUT_OF_SCOPE_DIRTY_BEFORE_SAVE|" + json.dumps(census))
    require(u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
    require(_census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|" + json.dumps(_census()))


def _same_wav_by_swap_record(root, analysis_sha, rail_sound_path):
    """True only when a walking_music_swap record says the rail's asset was imported from a WAV whose sha256 equals the
    analysis source sha256 (the analyses predate the 5 Oct Cameron swap and still carry the old asset path; measured
    7 Oct: walking_music_swap_record_P01.json passages.1 sha256 == P01 analysis source.sha256)."""
    if not analysis_sha or not rail_sound_path:
        return False
    asset = rail_sound_path.split(".")[-1].split("/")[-1]
    folder = os.path.join(root, "Saved", "CodexConductor")
    for name in ("walking_music_swap_record_P01.json", "walking_music_swap_record_P02-P03-P04-P05.json"):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        rec = load_json(path, root)
        rows = ((rec.get("args") or {}).get("passages") or rec.get("passages") or {})
        for row in (rows.values() if isinstance(rows, dict) else []):
            if isinstance(row, dict) and row.get("asset_name") == asset and row.get("sha256") == analysis_sha:
                return True
    return False


def _live_plans(args, show, tick_rate, reference):
    root = _project()
    plans = []
    for label, src in sorted(args["passages"].items()):
        ctx = _passage(show, label)
        analysis = load_json(src["analysis"], root)
        notes = load_json(src["notes"], root) if src.get("notes") else None
        want_sound = (analysis.get("source") or {}).get("unrealSoundPath")
        refusals = []
        if (want_sound and want_sound.split(".")[0] != ctx["sound_path"].split(".")[0]
                and not _same_wav_by_swap_record(root, (analysis.get("source") or {}).get("sha256"), ctx["sound_path"])):
            refusals.append("ANALYSIS_SOUND_MISMATCH|analysis=%s|rail=%s" % (want_sound, ctx["sound_path"]))
        offset_s = ctx["music_frames"] / tick_rate
        draft = choose_cues(analysis, notes, offset_s, args, (args.get("latest_cue_end_s") or {}).get(label))
        eyes, top = _measure(ctx, tick_rate, draft)
        if max(eyes) - min(eyes) > EYE_SPREAD_TOL_CM:
            refusals.append("EYE_VARIES_ACROSS_CUES|%s" % eyes)
        plan = plan_passage(label, analysis, notes, offset_s, sum(eyes) / len(eyes), top, args, reference)
        plan["light_before"] = _light_settings(ctx["rig"].get_editor_property("follow_light"))
        plan["show_times"] = show_times(plan, ctx["seg"][0] / tick_rate)
        plan["segment"] = list(ctx["seg"])
        plan["measured"] = {"eyes_cm": eyes, "cat_top_cm": top, "sound": ctx["sound_path"]}
        plan["refusals"] = refusals
        plan["rig_label"] = ctx["rig"].get_actor_label()
        plan["before"] = _rig_state(ctx["rig"]) if _patch_built() else None
        plans.append((ctx, plan))
    return plans


def _run(raw):
    run = datetime.datetime.now().strftime("PSS-%Y%m%d-%H%M%S")
    report = {"run": run, "ok": False}
    try:
        u = _u()
        args = check_args(raw)
        report["args"] = args
        world, census_before = _context(args)
        show = u.load_asset(SHOW_PATH)
        require(show is not None, "SHOW_LOAD_FAILED")
        tick = show.get_editor_property("tick_resolution")
        tick_rate = tick.numerator / float(tick.denominator)
        record_path = os.path.join(_here(), RECORD_NAME)
        mode = args["mode"]
        if mode == "REVERT":
            require(os.path.isfile(record_path), "NO_RECORD")
            with open(record_path, encoding="utf-8") as handle:
                record = json.load(handle)
            require(record.get("status") in ("APPLIED", "WRITING"), "RECORD_STATUS|%r" % record.get("status"))
            rows = []
            for row in record["rigs"]:
                ctx = _passage(show, row["passage"])
                live = _rig_state(ctx["rig"])
                if record["status"] == "APPLIED":
                    require(same_rows(row["after"]["cues"], live["cues"]) and same_vec(row["after"]["offset"], live["offset"]),
                            "REVERT_DRIFT|%s|%s" % (row["passage"], json.dumps(live)))
                rows.append((ctx, row))
            backup = _backup(run, "PrePussShadowSpotRevert-")
            for ctx, row in rows:
                _write_rig(ctx["rig"], row["before"])
                if row.get("light_after"):
                    _write_light(ctx["rig"], row["light_before"])
            _save_narrow()
            record.update({"status": "REVERTED", "revert_run": run, "revert_backup": backup})
            done = record_path.replace(".json", ".reverted-%s.json" % run)
            os.replace(record_path, done)
            _write_json(done, record)
            _log("%s_REVERT_OK|run=%s|rigs=%d|backup=%s" % (MARK, run, len(rows), backup["root"]))
            return
        reference = None
        if args["geometry_source"] == "reference":
            reference = _read_reference(args, show)
            report["reference"] = reference
            _log("%s_REFERENCE|run=%s|rig=%s|offset=%s|rotation=%s|light=%s|tip=%s|attach=%s|visible=%s" % (
                MARK, run, reference["rig_label"], reference["offset"], reference["rotation"],
                json.dumps(reference["light"], default=str), reference["implied_tip_at_reference"],
                reference["attach_parent"], reference["visible"]))
        plans = _live_plans(args, show, tick_rate, reference)
        report["plans"] = [p for _, p in plans]
        report["patch_built"] = _patch_built()
        refusals = [r for _, p in plans for r in p["refusals"]]
        if mode == "DRY":
            require(_census() == census_before, "DRY_CENSUS_CHANGED|evaluation dirtied the map: Don't-Save")
            report.update({"ok": True, "apply_ready": not refusals and report["patch_built"]})
            path = os.path.join(_here(), "puss_shadow_spot_report_DRY_%s.json" % run)
            _write_json(path, report)
            for _, p in plans:
                for c, st in zip(p["cues"], p["show_times"]):
                    _log("%s_CUE|run=%s|%s|passage_s=%.3f|full_show_s=%.3f|off_show_s=%.3f|%s" % (
                        MARK, run, p["passage"], c["passage_s"], st["full_show_s"], st["off_show_s"], c["label"]))
            _log("%s_DRY_OK|run=%s|passages=%d|cues=%d|patch_built=%s|refusals=%d|report=%s" % (
                MARK, run, len(plans), sum(len(p["cues"]) for _, p in plans), report["patch_built"], len(refusals), path))
            return
        require(not refusals, "REFUSED|" + json.dumps(refusals))
        require(not os.path.exists(record_path), "RECORD_EXISTS|revert first|" + record_path)
        backup = _backup(run, "PrePussShadowSpot-")
        record = {"version": 1, "run": run, "args": args, "backup": backup, "status": "WRITING", "rigs": []}
        for ctx, p in plans:
            after = {"cues": cue_rows(p), "offset": p["geometry"]["offset"], "rotation": p["geometry"]["rotation"]}
            record["rigs"].append({"passage": p["passage"], "rig_label": p["rig_label"], "before": p["before"],
                                   "after": after, "light_before": p["light_before"],
                                   "light_after": reference["light"] if reference else None, "plan": p})
        with open(record_path, "x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True, default=str)
        probes = {}
        try:
            for (ctx, p), row in zip(plans, record["rigs"]):
                _write_rig(ctx["rig"], row["after"])
                if row["light_after"]:
                    _write_light(ctx["rig"], row["light_after"])
                probe = _probe_light(ctx, tick_rate, row["after"]["cues"][0])
                want = row["after"]["cues"][0]["intensity"]
                require(probe["on"]["visible"] and abs(probe["on"]["intensity"] - want) <= 0.01 * want
                        and probe["on"]["weight"] > 0.999, "LIGHT_ON_PROBE|%s|%s" % (p["passage"], probe))
                require(not probe["off"]["visible"] and probe["off"]["weight"] == 0.0,
                        "LIGHT_OFF_PROBE|%s|%s" % (p["passage"], probe))
                probes[p["passage"]] = probe
        except Exception:
            for (ctx, p), row in zip(plans, record["rigs"]):
                try:
                    _write_rig(ctx["rig"], row["before"])
                    _write_light(ctx["rig"], row["light_before"])
                except Exception as error:  # keep restoring the others
                    _u().log_error("%s_RESTORE_FAILED|%s|%s" % (MARK, p["passage"], error))
            _log("%s_ROLLED_BACK_IN_MEMORY|run=%s|NOTHING SAVED|if census stays dirty: Don't-Save restart" % (MARK, run))
            raise
        _save_narrow()
        record.update({"status": "APPLIED", "probes": probes})
        _write_json(record_path, record)
        _log("%s_APPLY_OK|run=%s|rigs=%d|cues=%d|backup=%s|record=%s" % (
            MARK, run, len(plans), sum(len(r["after"]["cues"]) for r in record["rigs"]), backup["root"], record_path))
    except Exception as error:
        _u().log_error("%s_STOPPED|run=%s|%s" % (MARK, run, error))
        raise


if __name__ == "__puss_shadow_spot_runner__":
    _run(globals().get("PUSSSHADOWSPOT_ARGS") or {})

if __name__ == "__main__":  # offline DRY: python puss_shadow_spot.py
    _here_dir = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.normpath(os.path.join(_here_dir, "..", ".."))
    with open(os.path.join(_here_dir, "puss_shadow_spot_args.json"), encoding="utf-8") as _h:
        _args = check_args(dict(json.load(_h), mode="DRY", confirm=None))
    for _p in offline_plan(_args, _root):
        g = _p["geometry"]
        print("%s  offset=(%.0f,0,%.1f) pitch=%.1f  H=%.0f  tip(h-20/h/h+20)=%s  ~%.0f lux at aim" % (
            _p["passage"], g["offset"][0], g["offset"][2], g["pitch_deg"], g["light_floor_height_cm"],
            "/".join("%.0f" % v if v is not None else "none" for v in _p["tip_ahead_sensitivity_cm"].values()),
            _p["aim_illuminance_lux"]))
        for _c, _st in zip(_p["cues"], _p["show_times"] or [None] * len(_p["cues"])):
            print("   passage_s=%7.3f  full@show %s  %s" % (
                _c["passage_s"], "%.2f s" % _st["full_show_s"] if _st else "?", _c["label"]))
