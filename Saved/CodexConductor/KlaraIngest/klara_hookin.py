"""KLARA HOOK-IN v2 (7 Oct): Klara's dioramas placed INSIDE our landed hangars, her cinematics as re-keyed copies.
Offline-written, NEVER RUN IN UNREAL. Plan and evidence: HOOKIN_PLAN.md (same folder).

Gary 7 Oct (his words, via the coordinator):
  - "bring her dioramas into the hangar itself ... a wide shot of the animals, the shrine, the Pigeon/children as the
    light strikes on a dark hangar, before we go into her cinematic sequences";
  - shot start "After the hangar lands" (land_plus_strike; + a wide-shot hold before the cut);
  - S1 narration "Drop it for now" -> MUTE (deactivate, never delete);
  - S2 "Import, keep our S2" -> Japanese_Alley streamed into the S2 hangar for viewing; LS_DevScene_02 untouched;
  - lighting "Hers; ours off in her scenes".

Tiers per claim: [decl] header/source we can read, [prec] in-repo precedent (cited), [meas] bytes/record read, [inf]
inferred (why stated). Every [inf] API is probed by DRY into report["api_table"].

MECHANISM (HOOKIN_PLAN.md section 2)
  PLACE  each of her levels is a NON-instanced streaming sublevel with LevelTransform = the Scene's LANDED hangar
         (dock) frame composed with a fitted local placement [decl LevelStreaming.h:226-227 "Transform applied to
         actors after loading"]. Non-instanced streaming keeps her package name, so her full-path bindings
         (/Game/KK_S1_Animals/L_Animals.L_Animals:PersistentLevel.X [meas]) can still resolve [inf; measured by the
         live CheckSceneCutBindings verdicts recorded at APPLY_STREAM].
  KEYS   her absolute transform keys do NOT follow a LevelTransform [inf: standard]. Sub-section transform origins exist
         [decl MovieSceneSubSection.h:278-285; nested composition MovieSceneTransformOriginSystem.h:13-35] but the mask is
         a bare UPROPERTY() and SetMask is not a UFUNCTION [decl MovieSceneSubSection.h:168-175, 278-279], so Python
         cannot enable it [inf; probed]. So the tool makes a RE-KEYED COPY of her LS (her original is never edited) and
         shifts every top-level, unattached 3D-transform Location channel by the same rigid transform. Only
         TRANSLATION is supported (exact for cubic keys: tangents are unchanged by a constant offset); S1 and S4 docks
         have yaw 0 [meas hangar_s1_record.json, hangar_s4_plan.json], so local yaw 0 gives a translation-only
         transform. A non-zero world yaw refuses (S2 is import-only and needs no re-key).
  TIME   [0, land) dark hangar, her level hidden | [land, cut) her level visible, our hangar strike reveals it (wide shot,
         our root cuts) | [cut, end) her cinematic (re-keyed copy), her sun/sky/fog/PPV on, OURS off.
         cut = land + StrikeAfterLandSeconds + wide_hold_s. Scene end = cut + her length (narration muted).

STAGES (args "mode"): DRY | APPLY_STREAM | REVERT_STREAM | APPLY_SEQ | REVERT_SEQ, confirm "<MODE> KLARAHOOK".
  APPLY_STREAM adds the levels with their fitted LevelTransforms (initially loaded, hidden) and saves ONLY the map.
  APPLY_SEQ, per hooked Scene (S1, S4):
    - duplicate her LS to args.copy_folder and re-key it;
    - retarget the shot section to the COPY;
    - mute the narration;
    - add a Level Visibility track [land, end);
    - add Visibility tracks: OUR celestial actors hidden over [cut, end), HER env actors hidden over [land, cut);
    - save ONLY LS_DevScene_0N and the new copy.
  Relength afterwards via Saved/CodexSoftGoods/extend_scene_playback.py (mode bodies printed). The REVERT stages
  restore the recorded before-state; the copy is deleted only if nothing references it.
Never: Save All, reload a level, open/scrub Sequencer, touch Show/Master, end PIE; no unreal objects in module globals.
Importing without `unreal` runs nothing (test_klara_hookin_offline.py).
"""
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "klara_hookin"
CONFIRM_WORD = "KLARAHOOK"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                     # extend_scene_playback.py:44
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"            # extend_scene_playback.py:45
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # extend_scene_playback.py:46
ARGS_NAME = "klara_hookin_args.json"
DRY_NAME = "klara_hookin_dry.json"
STREAM_RECORD = "klara_hookin_stream_record.json"
SEQ_RECORD = "klara_hookin_seq_record.json"
MODES = ("DRY", "APPLY_STREAM", "REVERT_STREAM", "APPLY_SEQ", "REVERT_SEQ")
START_OPTIONS = ("keep", "land", "land_plus_strike", "at_s")
NARRATION_RULES = ("mute", "after_voices", "inside_shot", "none")
VIS_TRACK_NAME = "Klara Levels (hookin)"
OURS_OFF_PREFIX = "Klara Hookin - Ours Off: "
HERS_DARK_PREFIX = "Klara Hookin - Hers Dark: "
CHOREO_TRACK_CLASS = "MovieSceneInfinityChoreoTrack"
ROOT_BINDING = "S%s Hangar Root"          # scene_audio_import.py:74 [prec]
ROOT_CHANNEL_INDEX = 4                    # scene_audio_import.py:75 [prec]
ROOT_CHANNEL_NAME = "Rotation.Y"          # scene_audio_import.py:76 [prec]
ARRIVAL_LABEL = "S%s Arrival"             # scene_audio_import.py:77 [prec]
APRON_LABEL = "S%s Hangar Apron"          # hangar_build.py:433 [decl]: world-fixed, NOT on the rising root
RIG_BINDINGS = ("sun_light_actor", "moon_light_actor", "sky_light_actor", "height_fog_actor")   # CelestialRig.h:42-52
ENV_CLASSES = ("DirectionalLight", "SkyLight", "SkyAtmosphere", "ExponentialHeightFog", "VolumetricCloud",
               "PostProcessVolume")   # the rig's list (CelestialRig.cpp:272-276) + PPV (not in the rig's list)
FRAME_EPS = 1.0e-6
YAW_EPS = 1.0e-6


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: time maths
# =====================================================================================================================

def ceil_frames(seconds, fps):
    """First display frame at or after `seconds` (208.64 s x 25 is frame 5216, not 5217)."""
    return int(math.ceil(float(seconds) * float(fps) - FRAME_EPS))


def her_span(lower_frame, upper_frame, her_fps, her_tick):
    """Her playback range [lower, upper) in her display frames -> ticks and seconds (24000/30 = 800 ticks a frame)."""
    tpf = float(her_tick) / float(her_fps)
    if abs(tpf - round(tpf)) > 1e-9:
        raise PlanError("HER_TICKS_PER_FRAME_NOT_WHOLE: %r" % tpf)
    tpf = int(round(tpf))
    lo, hi = int(lower_frame) * tpf, int(upper_frame) * tpf
    if hi <= lo:
        raise PlanError("HER_RANGE_EMPTY: [%d, %d)" % (lower_frame, upper_frame))
    return {"lower_tick": lo, "upper_tick": hi, "len_tick": hi - lo, "len_s": (hi - lo) / float(her_tick),
            "lower_s": lo / float(her_tick), "upper_s": hi / float(her_tick), "ticks_per_frame": tpf}


def outer_frames(len_s, outer_fps):
    """Her length in OUR display frames, ceiled so her last frame is never cut; off-grid holds are reported."""
    exact = float(len_s) * float(outer_fps)
    frames = int(math.ceil(exact - FRAME_EPS))
    return {"exact": exact, "frames": frames, "on_grid": abs(exact - round(exact)) <= 1e-6,
            "hold_s": (frames - exact) / float(outer_fps)}


def inner_to_scene_s(inner_tick, her_tick, section_start_s, her_lower_tick, start_offset_tick=0, play_rate=1.0):
    """Her inner time -> Scene seconds, rate 1 [prec scene_audio_import.py:235-241]: the section start plays her
    playback START, so her negative start (S1 -10.333 s) needs nothing extra."""
    if play_rate <= 0:
        raise PlanError("PLAY_RATE_NONPOSITIVE: %r" % play_rate)
    return float(section_start_s) + (float(inner_tick) - float(her_lower_tick) - float(start_offset_tick)) / \
        float(her_tick) / float(play_rate)


def choose_start(option, facts, row):
    """Frame of the CUT into her cinematic. land / land_plus_strike are live frames; wide_hold_s is added to them (the
    wide shot of her diorama in our hangar, Gary 7 Oct). keep = current shot start; at_s = explicit."""
    hold = ceil_frames(row.get("wide_hold_s", 0.0), facts["fps"]) if row.get("wide_hold_s") else 0
    if option == "keep":
        return (facts.get("target") or {}).get("start"), "current nested section start"
    if option == "land":
        f = facts.get("land_frame")
        return (None if f is None else f + hold), "hangar land key + wide_hold_s"
    if option == "land_plus_strike":
        f = facts.get("strike_frame")
        return (None if f is None else f + hold), "hangar land + StrikeAfterLandSeconds + wide_hold_s"
    if option == "at_s":
        if not isinstance(row.get("at_s"), (int, float)):
            return None, "at_s missing"
        return ceil_frames(row["at_s"], facts["fps"]), "args at_s"
    return None, "unknown option"


def plan_narration(rule, facts, row, section, her, fps):
    """-> dict(action, frames, reason, refusals, covers_end). action: mute | move | keep | report | none."""
    out = {"rule": rule, "refusals": [], "warnings": []}
    narr_all = facts.get("narration_all") or ([facts["narration"]] if facts.get("narration") else [])
    narr = facts.get("narration")
    if rule == "none":
        out.update(action="none", reason="no narration rule for this Scene")
        return out
    if rule == "mute":
        out.update(action="mute", covers_end=False, sections=[[int(n["start"]), int(n["end"])] for n in narr_all],
                   reason="Gary 7 Oct 'Drop it for now': deactivate, never delete (REVERT re-activates)")
        if not narr_all:
            out["warnings"].append("NARRATION_TRACK_ABSENT: nothing to mute")
        return out
    if not narr:
        out.update(action="report", reason="no narration track %r in the Scene" % row.get("narration_track"))
        out["warnings"].append("NARRATION_TRACK_ABSENT")
        return out
    length = int(narr["end"]) - int(narr["start"])
    out["current"] = [int(narr["start"]), int(narr["end"])]
    if rule == "after_voices":
        pat = str(row.get("voices_pattern") or "Animal_Voices")
        voices = [a for a in her.get("audio") or [] if pat in str(a.get("sound"))]
        if voices:
            start = ceil_frames(max(a["scene_end_s"] for a in voices), fps)
            out.update(action="move", frames=[start, start + length], covers_end=True, reason="after her voices")
        elif isinstance(row.get("narration_override_start_s"), (int, float)):
            start = ceil_frames(row["narration_override_start_s"], fps)
            out.update(action="move", frames=[start, start + length], covers_end=True, reason="override")
        else:
            out.update(action="report", frames=out["current"], covers_end=False, reason="no voices: REPORT")
            out["warnings"].append("NO_VOICES_IN_HER_LS")
            if narr["end"] > section[1]:
                out["refusals"].append("NARRATION_PAST_HER_END: [%d, %d) vs shot end %d" % (narr["start"], narr["end"],
                                                                                            section[1]))
        return out
    if rule == "inside_shot":
        inside = section[0] <= narr["start"] and narr["end"] <= section[1]
        out.update(action="keep", frames=out["current"], covers_end=False, inside=inside)
        if not inside:
            out["refusals"].append("NARRATION_NOT_INSIDE_SHOT: narration [%d, %d) vs shot [%d, %d)"
                                   % (narr["start"], narr["end"], section[0], section[1]))
        return out
    out.update(action="report")
    out["refusals"].append("NARRATION_RULE_UNKNOWN: %r" % rule)
    return out


def plan_timeline(land, cut, end, ours_off=True, hers_dark_until_cut=True):
    """Scene-frame windows. level_visible [land, end); wide [land, cut); her cinematic [cut, end); OURS hidden over
    [cut, end); HER env actors hidden over [land, cut) so the diorama is revealed by our strike in a dark hangar."""
    out = {"refusals": []}
    if land is None:
        out["refusals"].append("TIMELINE_NO_LAND")
        return out
    if not (land <= cut < end):
        out["refusals"].append("TIMELINE_ORDER: land %r cut %r end %r" % (land, cut, end))
        return out
    out.update(level_visible=[land, end], wide=[land, cut], cinematic=[cut, end],
               ours_off=[cut, end] if ours_off else None,
               hers_dark=[land, cut] if (hers_dark_until_cut and cut > land) else None)
    return out


# =====================================================================================================================
# Pure: placement (her diorama inside the landed hangar)
# =====================================================================================================================

def _rot(x, y, yaw_deg):
    a = math.radians(yaw_deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def norm_yaw(y):
    y = float(y) % 360.0
    return 0.0 if abs(y) < YAW_EPS or abs(y - 360.0) < YAW_EPS else y


def fit_footprint(footprint, floor_z_her, hangar, dock, margin_cm=100.0, anchor="center", yaw_options=(0, 180, 90, 270)):
    """Place her diorama inside the landed hangar.
    footprint = [xmin, xmax, ymin, ymax] in HER level coords (cm); floor_z_her = her ground height.
    hangar = {apron, depth, half_w, height, lattice_z}; interior in dock-local coords is x in [apron, apron+depth],
    y in [-half_w, half_w], floor top z = 0 [decl hangar_build.py:211, 229, 435-440].
    dock = {"loc": [x, y, z], "yaw": deg} = the LANDED hangar frame.
    Returns the first yaw option (dock-local) that fits, else the best (least overhang) with fits=False.
    level_transform = {"loc": world cm, "yaw": world deg} to give ULevelStreaming.LevelTransform."""
    xmin, xmax, ymin, ymax = [float(v) for v in footprint]
    cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    hx, hy = (xmax - xmin) / 2.0, (ymax - ymin) / 2.0
    ix0, ix1 = float(hangar["apron"]) + margin_cm, float(hangar["apron"]) + float(hangar["depth"]) - margin_cm
    iy = float(hangar["half_w"]) - margin_cm
    if anchor == "center":
        tx = (ix0 + ix1) / 2.0
    elif anchor == "far":
        tx = None
    elif anchor == "near":
        tx = None
    elif isinstance(anchor, (int, float)):
        tx = float(anchor)
    else:
        raise PlanError("ANCHOR_INVALID: %r" % anchor)
    rows = []
    for yaw in yaw_options:
        ex, ey = (hx, hy) if norm_yaw(yaw) in (0.0, 180.0) else (hy, hx)
        if anchor == "far":
            x_target = ix1 - ex
        elif anchor == "near":
            x_target = ix0 + ex
        else:
            x_target = tx
        over = {"near": max(0.0, ix0 - (x_target - ex)), "far": max(0.0, (x_target + ex) - ix1),
                "side": max(0.0, ey - iy)}
        rcx, rcy = _rot(cx, cy, yaw)
        local = [x_target - rcx, 0.0 - rcy, 0.0 - float(floor_z_her)]
        wx, wy = _rot(local[0], local[1], dock["yaw"])
        loc = [dock["loc"][0] + wx, dock["loc"][1] + wy, dock["loc"][2] + local[2]]
        rows.append({"local_yaw": float(yaw), "fits": not any(v > 1e-6 for v in over.values()), "overhang_cm": over,
                     "local_offset": local, "footprint_cm": [2 * ex, 2 * ey],
                     "level_transform": {"loc": loc, "yaw": norm_yaw(float(dock["yaw"]) + float(yaw))}})
    fit = next((r for r in rows if r["fits"]), None)
    best = fit or min(rows, key=lambda r: sum(r["overhang_cm"].values()))
    return dict(best, candidates=rows, interior_cm=[ix1 - ix0, 2 * iy], margin_cm=margin_cm, anchor=anchor)


def height_report(z_top_her, floor_z_her, hangar):
    top = float(z_top_her) - float(floor_z_her)
    return {"height_cm": top, "under_lattice": top <= float(hangar.get("lattice_z", hangar["height"])),
            "under_roof": top <= float(hangar["height"])}


def world_point(transform, p):
    """Apply a {loc, yaw} rigid transform to a point."""
    x, y = _rot(p[0], p[1], transform["yaw"])
    return [x + transform["loc"][0], y + transform["loc"][1], p[2] + transform["loc"][2]]


def rekey_plan(channels, transform):
    """channels = {"x": {"keys": [[t, v]...], "default": v|None}, "y": ..., "z": ...} for ONE Location group.
    Translation-only: every key and default + loc. Non-zero world yaw is refused (exactness needs tangent rotation)."""
    if norm_yaw(transform["yaw"]) != 0.0:
        raise PlanError("REKEY_ROTATION_UNSUPPORTED: world yaw %r (translation-only re-key)" % transform["yaw"])
    out = {}
    for i, axis in enumerate(("x", "y", "z")):
        ch = channels.get(axis) or {"keys": [], "default": None}
        d = float(transform["loc"][i])
        out[axis] = {"keys": [[int(t), float(v) + d] for t, v in ch["keys"]],
                     "default": None if ch.get("default") is None else float(ch["default"]) + d}
    return out


def inside_box_local(p_world, dock, hangar, margin_cm=0.0):
    """Is a world point inside the landed hangar's interior box (dock-local)?"""
    lx, ly = _rot(p_world[0] - dock["loc"][0], p_world[1] - dock["loc"][1], -dock["yaw"])
    lz = p_world[2] - dock["loc"][2]
    return (float(hangar["apron"]) + margin_cm <= lx <= float(hangar["apron"]) + float(hangar["depth"]) - margin_cm
            and abs(ly) <= float(hangar["half_w"]) - margin_cm and 0.0 <= lz <= float(hangar["height"]))


# =====================================================================================================================
# Pure: the Scene plan
# =====================================================================================================================

def plan_scene(facts, row):
    """facts (plain data) + args row -> plan. Content problems are refusals, never exceptions."""
    refusals, warnings = [], []
    fps, tick = float(facts["fps"]), float(facts["tick"])
    her = facts.get("her") or {}
    plan = {"scene": facts.get("scene"), "label": facts.get("label"), "fps": fps, "refusals": refusals,
            "warnings": warnings}
    if not her.get("exists"):
        refusals.append("HER_LS_MISSING: %s" % row.get("her_sequence"))
        return plan
    tgt = facts.get("target")
    if not tgt:
        refusals.append("TARGET_SECTION_NOT_FOUND: no root sub-section plays %s" % row.get("current_nested"))
        return plan
    if tgt.get("count", 1) != 1:
        refusals.append("TARGET_SECTION_COUNT: %d" % tgt["count"])
    try:
        span = her_span(her["lower_frame"], her["upper_frame"], her["fps"], her["tick"])
    except PlanError as exc:
        refusals.append(str(exc))
        return plan
    if abs(float(her["tick"]) - tick) > 1e-9:
        warnings.append("TICK_RESOLUTIONS_DIFFER: hers %r ours %r" % (her["tick"], tick))
    length = outer_frames(span["len_s"], fps)
    if not length["on_grid"]:
        warnings.append("LENGTH_OFF_GRID: %.3f frames ceiled to %d (holds %.4f s)" % (length["exact"], length["frames"],
                                                                                    length["hold_s"]))
    option = row.get("start_option", "keep")
    start, why = choose_start(option, facts, row)
    cands = {}
    for opt in START_OPTIONS:
        f, _w = choose_start(opt, facts, row)
        if f is not None:
            cands[opt] = {"start": f, "start_s": f / fps, "end": f + length["frames"], "end_s": (f + length["frames"]) / fps}
    plan.update(her_span=span, her_fps=her["fps"], length=length, start_option=option, start_why=why,
                start_candidates=cands, wide_hold_s=row.get("wide_hold_s", 0.0))
    if start is None:
        refusals.append("START_UNKNOWN: option %r (%s); land problems %s" % (option, why, facts.get("land_problems")))
        return plan
    pb0, pb1 = int(facts["playback"][0]), int(facts["playback"][1])
    if start < pb0:
        refusals.append("START_BEFORE_PLAYBACK: %d < %d" % (start, pb0))
    section = [int(start), int(start) + length["frames"]]
    plan.update(section=section, section_s=[section[0] / fps, section[1] / fps], start_offset_tick=0)
    audio = []
    for a in her.get("audio") or []:
        tpf = span["ticks_per_frame"]
        s = inner_to_scene_s(a["start_frame"] * tpf, her["tick"], section[0] / fps, span["lower_tick"])
        e = inner_to_scene_s(a["end_frame"] * tpf, her["tick"], section[0] / fps, span["lower_tick"])
        audio.append(dict(a, scene_start_s=s, scene_end_s=e))
    her = dict(her, audio=audio)
    plan["her_audio_in_scene"] = audio
    narr = plan_narration(row.get("narration_rule", "none"), facts, row, section, her, fps)
    plan["narration"] = narr
    refusals += narr["refusals"]
    warnings += narr["warnings"]
    end = section[1]
    if narr.get("covers_end") and narr.get("frames"):
        end = max(end, int(narr["frames"][1]))
    tail = row.get("tail_s", 0.0)
    if not isinstance(tail, (int, float)) or tail < 0:
        refusals.append("TAIL_INVALID: %r" % tail)
        tail = 0.0
    end += ceil_frames(tail, fps) if tail else 0
    plan.update(planned_end=end, planned_end_s=end / fps, end_change_s=(end - pb1) / fps)
    land = facts.get("land_frame")
    tl = plan_timeline(land, section[0], end, ours_off=bool(row.get("ours_off", True)),
                       hers_dark_until_cut=bool(row.get("hers_dark_until_cut", True)))
    plan["timeline"] = tl
    if row.get("placed_in_hangar", True):
        refusals += tl["refusals"]
    if land is not None and section[0] < land:
        warnings.append("SHOT_STARTS_BEFORE_LAND: frame %d < land %d - her cuts outrank our root cuts" % (section[0], land))
    allow = set(row.get("allow_truncate") or [])
    rows = []
    for s in facts.get("root_sections") or []:
        if s.get("is_target") or s.get("is_narration") or s.get("track") == VIS_TRACK_NAME:
            continue
        if s.get("end") is not None and s["end"] > end:
            rows.append(s)
            msg = "SECTION_PAST_PLANNED_END: %s %r [%s, %s) > %d" % (s.get("cls"), s.get("track"), s.get("start"),
                                                                     s.get("end"), end)
            (warnings if s.get("track") in allow else refusals).append(msg + (" (allowed)" if s.get("track") in allow else ""))
    plan["sections_past_end"] = rows
    plan["extend_mode"] = {"scene_label": facts.get("label"), "new_end_s": round(end / fps, 6), "dry_run": True}
    return plan


def plan_placement(level, lrow, hangars, margin_cm):
    """One level's fitted LevelTransform + height report (pure; offline footprint or live bounds)."""
    h = hangars.get(str(lrow["scene"]))
    if not h:
        return {"refusals": ["NO_HANGAR_FOR_SCENE_%s" % lrow["scene"]]}
    fp = lrow.get("footprint_live") or lrow["footprint_her"]
    fit = fit_footprint(fp, lrow.get("floor_z_her", 0.0), h, h["dock"], margin_cm, lrow.get("anchor", "center"),
                        tuple(lrow.get("local_yaw_options") or (0, 180, 90, 270)))
    out = {"level": level, "scene": str(lrow["scene"]), "fit": fit, "footprint_source": "live" if lrow.get("footprint_live")
           else "offline pivots (HOOKIN_PLAN.md section 3)", "refusals": [], "warnings": []}
    if lrow.get("z_top_her") is not None:
        out["height"] = height_report(lrow["z_top_her"], lrow.get("floor_z_her", 0.0), h)
        if not out["height"]["under_lattice"]:
            out["warnings"].append("TALLER_THAN_LATTICE: %.0f cm > lattice %s cm" % (out["height"]["height_cm"],
                                                                                    h.get("lattice_z")))
    if not fit["fits"]:
        msg = ("NO_FIT: %s %.0f x %.0f cm vs interior %.0f x %.0f cm, overhang %s - choose which part of her set goes in "
               "(scaling breaks MetaHumans/physics)" % (level, fit["footprint_cm"][0], fit["footprint_cm"][1],
                                                         fit["interior_cm"][0], fit["interior_cm"][1], fit["overhang_cm"]))
        (out["warnings"] if lrow.get("import_only") else out["refusals"]).append(msg)
    if not lrow.get("import_only") and norm_yaw(fit["level_transform"]["yaw"]) != 0.0:
        out["refusals"].append("WORLD_YAW_NONZERO: %r - the re-keyed copy is translation-only" % fit["level_transform"]["yaw"])
    return out


# =====================================================================================================================
# Pure: args, gates, records
# =====================================================================================================================

def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in MODES:
        r.append("MODE_INVALID: %r" % args.get("mode"))
    scenes = args.get("scenes") or {}
    if not scenes:
        r.append("NO_SCENES")
    levels = args.get("levels") or {}
    if not isinstance(levels, dict) or not levels:
        r.append("LEVELS_MUST_BE_A_NONEMPTY_MAP")
        levels = {}
    hangars = args.get("hangars") or {}
    for key, row in sorted(scenes.items()):
        if not str(key).isdigit():
            r.append("SCENE_KEY_NOT_A_NUMBER: %r" % key)
        for field in ("scene_sequence", "current_nested", "her_sequence", "start_option", "narration_rule"):
            if field not in row:
                r.append("S%s_MISSING_%s" % (key, field.upper()))
        if row.get("start_option") not in START_OPTIONS:
            r.append("S%s_START_OPTION_INVALID: %r" % (key, row.get("start_option")))
        if row.get("narration_rule") not in NARRATION_RULES:
            r.append("S%s_NARRATION_RULE_INVALID: %r" % (key, row.get("narration_rule")))
        for f in ("scene_sequence", "current_nested", "her_sequence"):
            if f in row and not str(row[f]).startswith("/Game/"):
                r.append("S%s_%s_NOT_GAME_PATH" % (key, f.upper()))
        if "Master" in str(row.get("scene_sequence", "")):
            r.append("S%s_TARGET_IS_THE_MASTER" % key)
        if str(key) not in hangars:
            r.append("S%s_NO_HANGAR" % key)
        for lv in row.get("level_packages") or []:
            if lv not in levels:
                r.append("S%s_LEVEL_NOT_IN_LEVELS: %s" % (key, lv))
    for key in (args.get("import_only") or {}):
        if key in scenes:
            r.append("S%s_BOTH_HOOKED_AND_IMPORT_ONLY" % key)
    for lv, lrow in sorted(levels.items()):
        if not str(lv).startswith("/Game/"):
            r.append("LEVEL_NOT_GAME_PATH: %r" % lv)
        if str(lrow.get("scene")) not in hangars:
            r.append("LEVEL_%s_NO_HANGAR" % lv)
        fp = lrow.get("footprint_her")
        if not (isinstance(fp, list) and len(fp) == 4 and fp[0] < fp[1] and fp[2] < fp[3]):
            r.append("LEVEL_%s_FOOTPRINT_INVALID" % lv)
    if not str(args.get("copy_folder") or "").startswith("/Game/"):
        r.append("COPY_FOLDER_INVALID")
    return r


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode != "DRY" and state.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s %s" % (mode, CONFIRM_WORD)))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("wrong_world"):
        r.append("WRONG_WORLD: %s" % state["wrong_world"])
    if state.get("sequencer_open"):
        r.append("SEQUENCER_OPEN: %s (close it; opening/scrubbing dirties the map)" % state["sequencer_open"])
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode.startswith("APPLY") and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode in ("APPLY_STREAM", "APPLY_SEQ") and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
    if mode in ("REVERT_STREAM", "REVERT_SEQ") and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def census_gate(census, expected_content, expected_maps):
    out = []
    if sorted(census.get("content") or []) != sorted(expected_content):
        out.append("CONTENT_CENSUS: got %s want %s" % (sorted(census.get("content") or []), sorted(expected_content)))
    if sorted(census.get("maps") or []) != sorted(expected_maps):
        out.append("MAP_CENSUS: got %s want %s" % (sorted(census.get("maps") or []), sorted(expected_maps)))
    return out


def seq_drift(live, rec):
    """Failures unless the Scene is exactly the recorded AFTER state."""
    out = []
    for k in ("sequence", "start", "end", "start_offset_tick"):
        if live["target"].get(k) != rec["after"]["target"].get(k):
            out.append("TARGET_%s: live %r recorded %r" % (k.upper(), live["target"].get(k), rec["after"]["target"].get(k)))
    for k in ("narration", "vis_track", "hookin_bindings"):
        if live.get(k) != rec["after"].get(k):
            out.append("%s: live %r recorded %r" % (k.upper(), live.get(k), rec["after"].get(k)))
    return out


def copy_path(args, key, her_sequence):
    return "%s/%s_S%sHangar" % (args["copy_folder"].rstrip("/"), her_sequence.rsplit("/", 1)[-1], key)


def write_record_exclusive(path, data):           # scene_audio_import.py:470-475 [prec]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):                     # scene_audio_import.py:478-484 [prec]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_record(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraIngest")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    if unreal is not None:
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.dirname(os.path.dirname(os.path.dirname(_here())))


def _stop(run, reason):
    unreal.log_error("KLARAHOOK_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _file(path, ext):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ext


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _api_table():
    """[inf] APIs, probed without mutating."""
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001 - a probe failure is a finding
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("MovieSceneSubSection.set_sequence", "decl MovieSceneSubSection.h:161-162",
          lambda: hasattr(u.MovieSceneSubSection, "set_sequence"))
    probe("MovieSceneSectionExtensions.get_parent_sequence_frame", "decl MovieSceneSectionExtensions.h:255",
          lambda: hasattr(u.MovieSceneSectionExtensions, "get_parent_sequence_frame"))
    probe("MovieSceneSectionParameters.start_frame_offset", "decl MovieSceneSectionParameters.h:76",
          lambda: repr(u.MovieSceneSectionParameters().get_editor_property("start_frame_offset")))
    probe("SubSection origin override reachable from Python (expected NO)", "decl MovieSceneSubSection.h:278-279 bare "
          "UPROPERTY; inf: not script-visible", lambda: repr(u.MovieSceneSubSection.get_default_object()
                                                              .get_editor_property("origin_override_mask")))
    probe("LevelStreaming.level_transform (BlueprintReadWrite)", "decl LevelStreaming.h:226-227",
          lambda: repr(u.LevelStreamingDynamic.get_default_object().get_editor_property("level_transform")))
    probe("EditorLevelUtils.add_level_to_world_with_transform / remove_level_from_world / get_levels",
          "decl EditorLevelUtils.h:276-277, 260-261, 419-420",
          lambda: [hasattr(u.EditorLevelUtils, n) for n in ("add_level_to_world_with_transform",
                                                             "remove_level_from_world", "get_levels")])
    probe("LevelStreamingDynamic initially_loaded / initially_visible", "inf (property names)",
          lambda: [u.LevelStreamingDynamic.get_default_object().get_editor_property(n)
                   for n in ("initially_loaded", "initially_visible")])
    probe("MovieSceneLevelVisibilityTrack + section set_level_names/set_visibility",
          "decl MovieSceneLevelVisibilitySection.h:43,49; track class name inf",
          lambda: [hasattr(u, "MovieSceneLevelVisibilityTrack"),
                   hasattr(u.MovieSceneLevelVisibilitySection, "set_level_names")])
    probe("LevelVisibility.VISIBLE", "inf", lambda: repr(u.LevelVisibility.VISIBLE))
    probe("MovieSceneVisibilityTrack property name == bHiddenInGame", "inf; APPLY gates on the live track",
          lambda: hasattr(u, "MovieSceneVisibilityTrack"))
    probe("MovieSceneCompletionMode.RESTORE_STATE", "prec curtain_sleight.py:1875 (KEEP_STATE)",
          lambda: repr(u.MovieSceneCompletionMode.RESTORE_STATE))
    probe("EditorAssetLibrary.duplicate_asset / delete_asset", "inf / prec scene_audio_import.py:1066",
          lambda: [hasattr(u.EditorAssetLibrary, "duplicate_asset"), hasattr(u.EditorAssetLibrary, "delete_asset")])
    probe("MovieSceneSection.set_is_active", "inf (is_active is prec scene_audio_import.py:668)",
          lambda: hasattr(u.MovieSceneSection, "set_is_active"))
    probe("InfinityStageCelestialRig foreign_lighting_exempt_levels (proposed C++ flag)",
          "NOT IN SOURCE TODAY: CelestialRig.h:95-107 has only bSuppressForeignEnvironmentLighting",
          lambda: [a for a in _actors() if a.get_class().get_name() == "InfinityStageCelestialRig"][0]
          .get_editor_property("foreign_lighting_exempt_levels"))
    probe("InfinityStageCameraPilotLibrary.check_scene_cut_bindings", "decl CameraPilotLibrary.h:141-146; tuple inf",
          lambda: hasattr(u.InfinityStageCameraPilotLibrary, "check_scene_cut_bindings"))
    return rows


def _cut_bindings(show, cue_guid):
    """C++ CheckSceneCutBindings: LocateBoundObjects in the EDITOR world [decl CameraPilotLibrary.cpp:691, 777]."""
    res = unreal.InfinityStageCameraPilotLibrary.check_scene_cut_bindings(show, cue_guid)
    if isinstance(res, tuple):
        vals = list(res)
        # 7 Oct live: the tuple order is not (ok, lines, count) - classify by type instead of position
        ok = next((bool(v) for v in vals if isinstance(v, bool)), False)
        ints = [v for v in vals if isinstance(v, int) and not isinstance(v, bool)]
        seqs = [v for v in vals if not isinstance(v, (bool, int, float, str)) and hasattr(v, "__iter__")]
        return {"ok": ok, "lines": [str(x) for x in (seqs[0] if seqs else [])],
                "unresolved": ints[0] if ints else None, "raw_type": "tuple:" + ",".join(type(v).__name__ for v in vals)}
    return {"ok": bool(res), "lines": [], "unresolved": None, "raw_type": type(res).__name__}


def _section_row(track, s):
    row = {"track": str(track.get_display_name()), "cls": track.get_class().get_name(),
           "start": int(s.get_start_frame()) if s.has_start_frame() else None,
           "end": int(s.get_end_frame()) if s.has_end_frame() else None, "active": bool(s.is_active())}
    if isinstance(s, unreal.MovieSceneSubSection):
        row["sequence"] = _path(s.get_sequence())
        row["start_offset_tick"] = int(s.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
    if isinstance(s, unreal.MovieSceneAudioSection):
        row["sound"] = _path(s.get_sound())
    return row


def _land_frames(seq, scene_key, problems):
    """Port of scene_audio_import._root_land/plan_scene [prec :617-642, :261-283]."""
    fps = _rate(seq.get_display_rate())
    hits = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            for s in t.get_sections() if s.get_sequence() is not None and "HangarRise" in _path(s.get_sequence())]
    if len(hits) != 1:
        problems.append("RISE_SUBSECTION_COUNT: %d" % len(hits))
        return None, None
    s = hits[0]
    rise = s.get_sequence()
    rres, rfps = _rate(rise.get_tick_resolution()), _rate(rise.get_display_rate())
    rows = [b for b in rise.get_bindings() if str(b.get_display_name()) == ROOT_BINDING % scene_key]
    secs = [x for b in rows for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)
            for x in t.get_sections()]
    if len(rows) != 1 or len(secs) != 1:
        problems.append("ROOT_SHAPE: bindings %d sections %d" % (len(rows), len(secs)))
        return None, None
    chans = list(secs[0].get_all_channels())
    ch = chans[ROOT_CHANNEL_INDEX] if len(chans) > ROOT_CHANNEL_INDEX else None
    name = "" if ch is None else (str(ch.channel_name) if hasattr(ch, "channel_name") else str(ch.get_name()))
    if not (name == ROOT_CHANNEL_NAME or name.startswith(ROOT_CHANNEL_NAME + "_")):
        problems.append("ROOT_CHANNEL: %r" % name)
        return None, None
    keys = sorted(int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value)
                  for k in ch.get_keys())
    if len(keys) < 2:
        problems.append("ROOT_KEYS: %d" % len(keys))
        return None, None
    lower = int(round(rise.get_playback_start() * rres / rfps))
    off = int(s.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
    land_s = s.get_start_frame_seconds() + (keys[-1] - lower - off) / rres
    land = ceil_frames(land_s, fps)
    arr = [a for a in _actors() if str(a.get_actor_label()) == ARRIVAL_LABEL % scene_key]
    if len(arr) != 1:
        problems.append("ARRIVAL_COUNT: %d" % len(arr))
        return land, None
    timing = arr[0].get_editor_property("hangar_timing")
    return land, ceil_frames(land_s + float(timing.get_editor_property("strike_after_land_seconds")), fps)


def _her_facts(path):
    her = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if her is None:
        return {"exists": False, "path": path}
    out = {"exists": True, "path": path, "fps": _rate(her.get_display_rate()), "tick": _rate(her.get_tick_resolution()),
           "lower_frame": int(her.get_playback_start()), "upper_frame": int(her.get_playback_end()),
           "audio": [], "cuts": [], "bindings": []}
    for t in her.get_tracks():
        if isinstance(t, unreal.MovieSceneAudioTrack):
            for a in t.get_sections():
                out["audio"].append({"sound": _path(a.get_sound()), "active": bool(a.is_active()),
                                     "start_frame": int(a.get_start_frame()) if a.has_start_frame() else out["lower_frame"],
                                     "end_frame": int(a.get_end_frame()) if a.has_end_frame() else out["upper_frame"]})
        elif isinstance(t, unreal.MovieSceneCameraCutTrack):
            out["cuts"] += [[int(c.get_start_frame()), int(c.get_end_frame())] for c in t.get_sections()]
    for b in her.get_bindings():
        parent = b.get_parent()                                   # prec hangar_light_keys_probe.py:110
        out["bindings"].append({"name": str(b.get_display_name()),
                                "has_parent": bool(parent is not None and hasattr(parent, "is_valid") and parent.is_valid()),
                                "tracks": sorted(t.get_class().get_name() for t in b.get_tracks())})
    return out


def _dock_check(key, hangar):
    """The apron is world-fixed (hangar_build.py:432-441 [decl]); its centre = dock (apron/2, 0, -floor_t/2)."""
    found = [a for a in _actors() if str(a.get_actor_label()) == APRON_LABEL % key]
    if len(found) != 1:
        return {"ok": False, "reason": "APRON_COUNT %d" % len(found)}
    d = hangar["dock"]
    x, y = _rot(float(hangar["apron"]) / 2.0, 0.0, d["yaw"])
    want = [d["loc"][0] + x, d["loc"][1] + y, d["loc"][2] - float(hangar.get("floor_t", 20.0)) / 2.0]
    loc = found[0].get_actor_location()
    got = [loc.x, loc.y, loc.z]
    err = max(abs(a - b) for a, b in zip(got, want))
    yaw_err = abs(norm_yaw(found[0].get_actor_rotation().yaw - d["yaw"]))
    yaw_err = min(yaw_err, 360.0 - yaw_err)
    return {"ok": err <= 1.0 and yaw_err <= 0.01, "err_cm": err, "yaw_err": yaw_err, "want": want, "got": got}


def _scene_facts(key, row):
    problems = []
    seq = unreal.load_asset(row["scene_sequence"])
    if seq is None:
        return None, ["SCENE_SEQUENCE_MISSING"], None
    fps, tick = _rate(seq.get_display_rate()), _rate(seq.get_tick_resolution())
    facts = {"scene": key, "scene_sequence": row["scene_sequence"], "fps": fps, "tick": tick,
             "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())], "root_sections": []}
    targets, narr = [], []
    for t in seq.get_tracks():
        if t.get_class().get_name() == CHOREO_TRACK_CLASS:
            continue
        for s in t.get_sections():
            r = _section_row(t, s)
            copy = copy_path(ARGS_CACHE, key, row["her_sequence"]) if ARGS_CACHE else None
            if r.get("sequence") in (row["current_nested"], row["her_sequence"], copy):
                r["is_target"] = True
                targets.append(r)
            if r["track"] == row.get("narration_track") and r["cls"] == "MovieSceneAudioTrack":
                r["is_narration"] = True
                narr.append(r)
            facts["root_sections"].append(r)
    facts["target"] = dict(targets[0], count=len(targets)) if targets else None
    facts["narration_all"] = narr
    facts["narration"] = narr[0] if len(narr) == 1 else None
    land_problems = []
    facts["land_frame"], facts["strike_frame"] = _land_frames(seq, key, land_problems)
    facts["land_problems"] = land_problems
    facts["her"] = _her_facts(row["her_sequence"])
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if c.get_editor_property("type") == unreal.InfinityCueType.SCENE
            and _path(c.get_editor_property("scene").get_editor_property("sequence")) == row["scene_sequence"]]
    facts["label"] = str(cues[0].get_editor_property("label")) if len(cues) == 1 else None
    if len(cues) != 1:
        problems.append("SCENE_CUE_COUNT: %d" % len(cues))
    else:
        try:
            facts["cut_bindings"] = _cut_bindings(show, cues[0].get_editor_property("cue_guid"))
        except Exception as exc:  # noqa: BLE001
            facts["cut_bindings"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    return facts, problems, seq


ARGS_CACHE = None   # plain dict (never an unreal object), set by main()


def _find_target_section(seq, row, key):
    paths = [row["current_nested"], row["her_sequence"], copy_path(ARGS_CACHE, key, row["her_sequence"])]
    hits = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            and t.get_class().get_name() != CHOREO_TRACK_CLASS for s in t.get_sections()
            if _path(s.get_sequence()) in paths]
    if len(hits) != 1:
        raise PlanError("TARGET_SECTION_COUNT: %d" % len(hits))
    return hits[0]


def _streaming(world):
    """{package: ULevelStreaming-ish facts} for streamed sublevels [inf: GameplayStatics.get_streaming_level]."""
    out = {}
    for lv in unreal.EditorLevelUtils.get_levels(world):
        pkg = _path(lv.get_outer()) if lv.get_outer() is not None else None
        if pkg and pkg != EXPECTED_WORLD:
            out[pkg] = {"level": pkg}
    return out


def _level_actors(world, pkg):
    for lv in unreal.EditorLevelUtils.get_levels(world):
        if lv.get_outer() is not None and _path(lv.get_outer()) == pkg:
            return [a for a in _actors() if a.get_level() == lv]
    return []


def _sequencer_open():
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    return _path(cur) if cur is not None else None


def _backup(run, tag, files):
    folder = os.path.join(_project(), "Backups", "PreKlaraHookin-%s-%s" % (tag, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for src in files:
        if not os.path.isfile(src):
            _stop(run, "BACKUP_SOURCE_MISSING|" + src)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _placements(args, world=None):
    out, refusals, warnings = {}, [], []
    for lv, lrow in sorted(args["levels"].items()):
        lrow = dict(lrow)
        key = str(lrow["scene"])
        lrow["import_only"] = key in (args.get("import_only") or {})
        if world is not None and lv in _streaming(world):
            env = [a for a in _level_actors(world, lv) if a.get_class().get_name() not in ENV_CLASSES]
            if env:
                xs, ys = [], []
                for a in env:
                    o, e = a.get_actor_bounds(False)
                    if max(e.x, e.y) < 5000.0:            # sky spheres / landscapes excluded, listed below
                        xs += [o.x - e.x, o.x + e.x]
                        ys += [o.y - e.y, o.y + e.y]
                lrow["live_world_bounds"] = [min(xs), max(xs), min(ys), max(ys)] if xs else None
        p = plan_placement(lv, lrow, args["hangars"], float(args.get("margin_cm", 100.0)))
        if world is not None:
            p["dock_check"] = _dock_check(key, args["hangars"][key])
            if not p["dock_check"]["ok"]:
                p["refusals"].append("DOCK_MISMATCH: %s" % p["dock_check"])
        out[lv] = p
        refusals += ["%s %s" % (lv, x) for x in p.get("refusals", [])]
        warnings += ["%s %s" % (lv, x) for x in p.get("warnings", [])]
    return out, refusals, warnings


def _plan_all(args, world):
    facts, plans, refusals, warnings, handles = {}, {}, [], [], {}
    for key, row in sorted(args["scenes"].items()):
        f, problems, seq = _scene_facts(key, row)
        refusals += ["S%s %s" % (key, p) for p in problems]
        facts[key], handles[key] = f, seq
        if f is None:
            continue
        p = plan_scene(f, row)
        refusals += ["S%s %s" % (key, x) for x in p["refusals"]]
        warnings += ["S%s %s" % (key, x) for x in p["warnings"]]
        plans[key] = p
    placements, r2, w2 = _placements(args, world)
    return facts, plans, placements, refusals + r2, warnings + w2, handles


def _rig():
    rigs = [a for a in _actors() if a.get_class().get_name() == "InfinityStageCelestialRig"]
    if len(rigs) != 1:
        raise PlanError("CELESTIAL_RIG_COUNT: %d" % len(rigs))
    return rigs[0]


def _ours(rig):
    """OUR global lighting = the rig's bound actors [decl CelestialRig.h:42-52; the rig never hides them:
    ApplyCyclePhase writes intensity/colour/rotation only, CelestialRig.cpp:362-528]."""
    out = []
    for n in RIG_BINDINGS:
        a = rig.get_editor_property(n)
        if a is not None:
            out.append(a)
    return out


def _rig_exempt_support(rig):
    try:
        return list(rig.get_editor_property("foreign_lighting_exempt_levels"))
    except Exception:  # noqa: BLE001 - property absent: the proposed C++ flag is not built
        return None


def run_dry(args, run, world):
    facts, plans, placements, refusals, warnings, _h = _plan_all(args, world)
    rig_info = {}
    try:
        rig = _rig()
        rig_info = {"label": str(rig.get_actor_label()), "ours": [str(a.get_actor_label()) for a in _ours(rig)],
                    "suppress_foreign": bool(rig.get_editor_property("suppress_foreign_environment_lighting")),
                    "exempt_levels": _rig_exempt_support(rig)}
        if rig_info["suppress_foreign"] and rig_info["exempt_levels"] is None and args.get("lighting", {}).get("hers_on"):
            refusals.append("RIG_SUPPRESSES_HER_LIGHTING: CelestialRig.cpp:254-298 hides her sun/sky/fog on level add "
                            "and BeginPlay; build the proposed exemption (HOOKIN_PLAN.md section 4) or set "
                            "lighting.hers_on false")
    except PlanError as exc:
        refusals.append(str(exc))
    report = {"tool": TOOL, "run": run, "args": args, "api_table": _api_table(), "facts": facts, "plans": plans,
              "placements": placements, "rig": rig_info, "streaming_now": sorted(_streaming(world)),
              "refusals": refusals, "warnings": warnings, "apply_ready": not refusals,
              "extend_modes": {k: p.get("extend_mode") for k, p in plans.items()}}
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    for row in report["api_table"]:
        unreal.log("KLARAHOOK_API|run=%s|ok=%d|%s|%s|%s" % (run, int(row["ok"]), row["api"], row["tier"], row["result"]))
    for t in refusals:
        unreal.log_warning("KLARAHOOK_REFUSAL|run=%s|%s" % (run, t))
    for t in warnings:
        unreal.log("KLARAHOOK_WARNING|run=%s|%s" % (run, t))
    for lv, p in sorted(placements.items()):
        unreal.log("KLARAHOOK_PLACE|run=%s|%s|fits=%s|transform=%s|overhang=%s"
                   % (run, lv, p["fit"]["fits"], p["fit"]["level_transform"], p["fit"]["overhang_cm"]))
    for k, p in sorted(plans.items()):
        unreal.log("KLARAHOOK_ROW|run=%s|S%s|cut=%s|timeline=%s|end_s=%s|narration=%s"
                   % (run, k, p.get("section"), p.get("timeline"), p.get("planned_end_s"),
                      (p.get("narration") or {}).get("action")))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("KLARAHOOK_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|report=%s"
               % (run, int(not refusals), len(refusals), len(warnings), out))


def _ftransform(t):
    return unreal.Transform(unreal.Vector(*t["loc"]), unreal.Rotator(0.0, 0.0, float(t["yaw"])), unreal.Vector(1, 1, 1))


def run_apply_stream(args, run, world):
    placements, refusals, _w = _placements(args, world)
    if refusals:
        _stop(run, "PLACEMENT_REFUSED|" + " || ".join(refusals))
    levels = sorted(args["levels"])
    have = sorted(_streaming(world))
    if [l for l in levels if not unreal.EditorAssetLibrary.does_asset_exist(l)]:
        _stop(run, "LEVEL_ASSET_MISSING")
    if [l for l in levels if l in have]:
        _stop(run, "ALREADY_STREAMED")
    rpath = os.path.join(_here(), STREAM_RECORD)
    backup = _backup(run, "Stream", [_file(EXPECTED_WORLD, ".umap")])
    rec = {"schema": 2, "tool": TOOL, "run": run, "mode": "APPLY_STREAM", "levels": levels, "levels_before": have,
           "placements": placements, "backup": backup, "decided_by": args.get("decided_by"), "applied": False,
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    write_record_exclusive(rpath, rec)
    added = []
    for lv in levels:
        t = placements[lv]["fit"]["level_transform"]
        ls = unreal.EditorLevelUtils.add_level_to_world_with_transform(world, lv, unreal.LevelStreamingDynamic,
                                                                     _ftransform(t))       # decl :276-277
        if ls is None:
            _stop(run, "ADD_LEVEL_NONE|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (lv, backup))
        ls.set_editor_property("initially_loaded", True)                                   # [inf] probed
        ls.set_editor_property("initially_visible", False)
        lt = ls.get_editor_property("level_transform")
        got = [lt.translation.x, lt.translation.y, lt.translation.z, lt.rotation.rotator().yaw]
        if max(abs(a - b) for a, b in zip(got[:3], t["loc"])) > 0.5 or abs(norm_yaw(got[3] - t["yaw"])) > 0.01 and \
                abs(norm_yaw(got[3] - t["yaw"]) - 360.0) > 0.01:
            _stop(run, "LEVEL_TRANSFORM_READBACK|%s|%s|NOTHING SAVED" % (lv, got))
        added.append({"level": lv, "transform": got})
    gate = census_gate(_census(), [], [EXPECTED_WORLD])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):          # prec extend_scene_playback:406
        _stop(run, "SAVE_MAP_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    placements_live, _r, _w2 = _placements(args, world)          # live bounds now that the levels exist
    show = unreal.load_asset(SHOW_PATH)
    verdicts = {}
    for key, row in sorted(args["scenes"].items()):
        cues = [c for c in show.get_editor_property("cues")
                if c.get_editor_property("type") == unreal.InfinityCueType.SCENE
                and _path(c.get_editor_property("scene").get_editor_property("sequence")) == row["scene_sequence"]]
        if len(cues) == 1:
            verdicts[key] = _cut_bindings(show, cues[0].get_editor_property("cue_guid"))
    rec.update(applied=True, added=added, live_placements=placements_live, cut_bindings_after=verdicts)
    update_record(rpath, rec)
    unreal.log("KLARAHOOK_APPLY_STREAM_OK|run=%s|levels=%s|cut_ok=%s|backup=%s|record=%s"
               % (run, ",".join(levels), {k: v.get("ok") for k, v in verdicts.items()}, backup, rpath))


def run_revert_stream(args, run, world):
    rpath = os.path.join(_here(), STREAM_RECORD)
    rec = load_record(rpath)
    targets = [lv for lv in unreal.EditorLevelUtils.get_levels(world)
               if lv.get_outer() is not None and _path(lv.get_outer()) in rec["levels"]]
    if len(targets) != len(rec["levels"]):
        _stop(run, "REVERT_LEVEL_COUNT|%d of %d" % (len(targets), len(rec["levels"])))
    for lv in targets:
        if not unreal.EditorLevelUtils.remove_level_from_world(lv, True, False):          # decl :260-261; keep undo
            _stop(run, "REMOVE_LEVEL_FAILED|NOTHING SAVED; Don't-Save restart")
    if sorted(_streaming(world)) != sorted(rec["levels_before"]):
        _stop(run, "REVERT_READBACK|NOTHING SAVED")
    gate = census_gate(_census(), [], [EXPECTED_WORLD])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        _stop(run, "SAVE_MAP_FAILED")
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAHOOK_REVERT_STREAM_OK|run=%s" % run)


def _hookin_bindings(seq):
    out = []
    for b in seq.get_bindings():
        name = str(b.get_display_name())
        if name.startswith(OURS_OFF_PREFIX) or name.startswith(HERS_DARK_PREFIX):
            secs = [[int(s.get_start_frame()), int(s.get_end_frame())] for t in b.get_tracks() for s in t.get_sections()]
            out.append({"name": name, "sections": secs})
    return sorted(out, key=lambda r: r["name"]) or None


def _live_seq_state(seq, row, key):
    sec = _find_target_section(seq, row, key)
    narr = [s for t in seq.get_tracks() if str(t.get_display_name()) == row.get("narration_track")
            and isinstance(t, unreal.MovieSceneAudioTrack) for s in t.get_sections()]
    vis = [t for t in seq.get_tracks() if str(t.get_display_name()) == VIS_TRACK_NAME]
    return {"target": {"sequence": _path(sec.get_sequence()), "start": int(sec.get_start_frame()),
                       "end": int(sec.get_end_frame()),
                       "start_offset_tick": int(sec.get_editor_property("parameters")
                                                .get_editor_property("start_frame_offset").value)},
            "narration": [[int(s.get_start_frame()), int(s.get_end_frame()), bool(s.is_active())] for s in narr] or None,
            "vis_track": [{"levels": [str(n) for n in s.get_level_names()],
                           "range": [int(s.get_start_frame()), int(s.get_end_frame())]}
                          for t in vis for s in t.get_sections()] or None,
            "hookin_bindings": _hookin_bindings(seq)}


def _set_target(seq, row, key, sequence_path, start, end, offset_tick):
    sec = _find_target_section(seq, row, key)
    child = unreal.load_asset(sequence_path)
    if child is None:
        raise PlanError("SEQUENCE_NOT_LOADED: %s" % sequence_path)
    sec.set_sequence(child)                                   # decl MovieSceneSubSection.h:161-162
    sec.set_range(int(start), int(end))                       # decl MovieSceneSectionExtensions.h:145
    p = sec.get_editor_property("parameters")                 # struct copy: set back [inf]
    p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(offset_tick)))
    sec.set_editor_property("parameters", p)
    return sec


def _make_rekeyed_copy(args, key, row, transform, world, level_pkgs, run):
    """Duplicate her LS and shift every top-level, UNATTACHED binding's Location keys by `transform` (translation)."""
    dst = copy_path(args, key, row["her_sequence"])
    if unreal.EditorAssetLibrary.does_asset_exist(dst):
        _stop(run, "COPY_EXISTS|%s" % dst)
    copy = unreal.EditorAssetLibrary.duplicate_asset(row["her_sequence"], dst)           # [inf] probed
    if copy is None:
        _stop(run, "DUPLICATE_FAILED|%s" % dst)
    log = []
    own, other = {}, {}
    for pkg in sorted(args["levels"]):
        for a in _level_actors(world, pkg):
            bucket = own if pkg in level_pkgs else other
            bucket.setdefault(str(a.get_actor_label()), []).append(a)
            if str(a.get_name()) != str(a.get_actor_label()):      # 7 Oct: bindings may carry the object name
                bucket.setdefault(str(a.get_name()), []).append(a)
    for b in copy.get_bindings():
        parent = b.get_parent()
        if parent is not None and hasattr(parent, "is_valid") and parent.is_valid():
            continue                                      # component/child binding: relative to its parent
        tracks = [t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)]
        if not tracks:
            continue
        name = str(b.get_display_name())          # [inf] display name == actor label; ambiguity STOPS
        actors = own.get(name, [])
        if not actors and len(other.get(name, [])) == 1:
            # e.g. LS_Children's 5 L_Animals SpotLights [meas]: that level sits in ANOTHER hangar; not moved here
            log.append({"binding": name, "skipped": "cross-level binding (actor lives in another Scene's hangar)"})
            continue
        if len(actors) > 1:
            _stop(run, "S%s REKEY_ACTOR_AMBIGUOUS|%r matches %d actors in %s|NOTHING SAVED; Don't-Save restart"
                  % (key, name, len(actors), level_pkgs))
        if not actors:
            # 7 Oct live ('Pendulum' in LS_Children): no level actor -> a spawnable or a free binding whose keys are
            # absolute world positions; shift them with the set (an unbound possessable is unaffected either way)
            log.append({"binding": name, "note": "no level actor: keys shifted as absolute (spawnable/free)"})
        elif actors[0].get_attach_parent_actor() is not None:      # prec curtain_sleight.py:1405
            log.append({"binding": name, "skipped": "attached (keys are relative)"})
            continue
        for t in tracks:
            for s in t.get_sections():
                all_chans = list(s.get_all_channels())
                names = [str(c.channel_name) if hasattr(c, "channel_name") else str(c.get_name()) for c in all_chans]
                # 7 Oct live: sections can lead with a 'Weight' channel (Pig_anim_RM) - pick Location.X/Y/Z by NAME
                by_axis = {}
                for c, n in zip(all_chans, names):
                    for ax in "XYZ":
                        if n.startswith("Location.%s" % ax) and ax not in by_axis:
                            by_axis[ax] = c
                if not by_axis:
                    log.append({"binding": name, "skipped": "no Location channels in section", "channels": names})
                    continue
                if len(by_axis) != 3:
                    _stop(run, "S%s REKEY_CHANNEL_ORDER|%s|%s" % (key, name, names))   # memory: suffixed names
                chans = [by_axis[ax] for ax in "XYZ"]
                before = {ax: {"keys": [[int(k.get_time().frame_number.value), float(k.get_value())] for k in c.get_keys()],
                               "default": float(c.get_default()) if c.has_default() else None}
                          for ax, c in zip("xyz", chans[:3])}
                want = rekey_plan(before, transform)
                for ax, c in zip("xyz", chans[:3]):
                    for k, (_t, v) in zip(c.get_keys(), want[ax]["keys"]):
                        k.set_value(v)
                    if want[ax]["default"] is not None:
                        c.set_default(want[ax]["default"])
                got = {ax: [[int(k.get_time().frame_number.value), round(float(k.get_value()), 4)] for k in c.get_keys()]
                       for ax, c in zip("xyz", chans[:3])}
                if any(got[ax] != [[t2, round(v2, 4)] for t2, v2 in want[ax]["keys"]] for ax in "xyz"):
                    _stop(run, "S%s REKEY_READBACK|%s|NOTHING SAVED; Don't-Save restart" % (key, name))
                log.append({"binding": name, "keys": {ax: len(before[ax]["keys"]) for ax in "xyz"}})
    return dst, log


def _add_vis_binding(seq, actor, prefix, frames, hidden):
    """One possessable on a show/streamed actor + a Visibility track, one RESTORE_STATE section, value = hidden."""
    b = seq.add_possessable(actor)                                                     # prec scene_exit_block.py:936
    b.set_display_name(prefix + str(actor.get_actor_label()))
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    if str(t.get_property_name()) in ("None", ""):
        # 7 Oct live: a Python-added visibility track has no property bound yet (precedent for bound property tracks:
        # CodexStructure/hangar_build.py:491 set_property_name_and_path)
        t.set_property_name_and_path("bHiddenInGame", "bHiddenInGame")
    if str(t.get_property_name()) != "bHiddenInGame":                                   # [inf] gate: True = hidden
        raise PlanError("VISIBILITY_TRACK_PROPERTY: %r" % str(t.get_property_name()))
    s = t.add_section()
    s.set_range(int(frames[0]), int(frames[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    ch = list(s.get_all_channels())[0]
    ch.set_default(bool(hidden))
    return b


def run_apply_seq(args, run, world):
    facts, plans, placements, refusals, warnings, handles = _plan_all(args, world)
    lighting = args.get("lighting") or {}
    rig = _rig()
    if lighting.get("hers_on") and _rig_exempt_support(rig) is None and bool(
            rig.get_editor_property("suppress_foreign_environment_lighting")):
        refusals.append("RIG_SUPPRESSES_HER_LIGHTING (see DRY)")
    streamed = _streaming(world)
    for k, row in args["scenes"].items():
        missing = [l for l in row.get("level_packages") or [] if l not in streamed]
        if missing:
            refusals.append("S%s LEVELS_NOT_STREAMED: %s (APPLY_STREAM first)" % (k, missing))
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    rpath = os.path.join(_here(), SEQ_RECORD)
    keys = sorted(plans)
    paths = {k: args["scenes"][k]["scene_sequence"] for k in keys}
    backup = _backup(run, "Seq", [_file(p, ".uasset") for p in paths.values()])
    rec = {"schema": 2, "tool": TOOL, "run": run, "mode": "APPLY_SEQ", "backup": backup, "applied": False,
           "decided_by": args.get("decided_by"), "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "scenes": {k: {"row": args["scenes"][k], "scene_sequence": paths[k], "playback_before": facts[k]["playback"],
                          "label": facts[k]["label"], "plan": plans[k], "copy": None,
                          "before": _live_seq_state(handles[k], args["scenes"][k], k)} for k in keys}}
    write_record_exclusive(rpath, rec)
    ours = _ours(rig)
    copies = []
    for k in keys:
        row, plan, seq = args["scenes"][k], plans[k], handles[k]
        lvls = row.get("level_packages") or []
        transform = placements[lvls[0]]["fit"]["level_transform"]       # all of a Scene's levels share one placement
        if any(placements[l]["fit"]["level_transform"] != transform for l in lvls):
            _stop(run, "S%s LEVELS_PLACED_DIFFERENTLY|NOTHING SAVED; Don't-Save restart" % k)
        dst, rekey_log = _make_rekeyed_copy(args, k, row, transform, world, lvls, run)
        copies.append(dst)
        rec["scenes"][k]["copy"] = dst
        rec["scenes"][k]["rekey"] = rekey_log
        update_record(rpath, rec)
        sec = _set_target(seq, row, k, dst, plan["section"][0], plan["section"][1], 0)
        child = sec.get_sequence()
        mapped = [int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(sec, int(child.get_playback_start()), seq)),
                  int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(sec, int(child.get_playback_end()), seq))]
        if mapped != plan["section"]:
            _stop(run, "S%s MAPPING_READBACK|%s vs %s|NOTHING SAVED; Don't-Save restart" % (k, mapped, plan["section"]))
        if plan["narration"].get("action") == "mute":
            for t in seq.get_tracks():
                if str(t.get_display_name()) == row["narration_track"] and isinstance(t, unreal.MovieSceneAudioTrack):
                    for s in t.get_sections():
                        s.set_is_active(False)                                         # [inf] probed; read back
        tl = plan["timeline"]
        vis_levels = row.get("visible_levels") or []
        if vis_levels:
            track = seq.add_track(unreal.MovieSceneLevelVisibilityTrack)
            track.set_display_name(VIS_TRACK_NAME)
            vs = track.add_section()
            vs.set_range(int(tl["level_visible"][0]), int(tl["level_visible"][1]))
            vs.set_visibility(unreal.LevelVisibility.VISIBLE)                          # decl :43
            vs.set_level_names([unreal.Name(n) for n in vis_levels])                    # decl :49
        if tl.get("ours_off") and lighting.get("ours_off", True):
            for a in ours:
                _add_vis_binding(seq, a, OURS_OFF_PREFIX, tl["ours_off"], True)
        if tl.get("hers_dark") and lighting.get("hers_on"):
            for pkg in lvls:
                for a in _level_actors(world, pkg):
                    if a.get_class().get_name() in ENV_CLASSES:
                        _add_vis_binding(seq, a, HERS_DARK_PREFIX, tl["hers_dark"], True)
        after = _live_seq_state(seq, row, k)
        bad = []
        if after["target"] != {"sequence": dst, "start": plan["section"][0], "end": plan["section"][1],
                               "start_offset_tick": 0}:
            bad.append("target %s" % after["target"])
        if plan["narration"].get("action") == "mute" and any(n[2] for n in after["narration"] or []):
            bad.append("narration still active %s" % after["narration"])
        if vis_levels and not (after["vis_track"] and after["vis_track"][0]["levels"] == vis_levels):
            bad.append("vis %s" % after["vis_track"])
        if bad:
            _stop(run, "S%s APPLY_READBACK|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (k, bad, backup))
        rec["scenes"][k]["after"] = after
        rec["scenes"][k]["mapped_inner_range"] = mapped
    gate = census_gate(_census(), list(paths.values()) + copies, [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    for p in list(paths.values()) + copies:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % p)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    for k in keys:
        if _live_seq_state(unreal.load_asset(paths[k]), args["scenes"][k], k) != rec["scenes"][k]["after"]:
            _stop(run, "S%s POST_SAVE_READBACK" % k)
    rec["applied"] = True
    update_record(rpath, rec)
    for k in keys:
        unreal.log("KLARAHOOK_EXTEND_NEXT|run=%s|S%s|extend_scene_playback_mode=%s"
                   % (run, k, json.dumps(plans[k]["extend_mode"], ensure_ascii=False)))
    unreal.log("KLARAHOOK_APPLY_SEQ_OK|run=%s|scenes=%s|copies=%s|backup=%s|record=%s"
               % (run, ",".join("S" + k for k in keys), ",".join(copies), backup, rpath))


def run_revert_seq(args, run, world):
    rpath = os.path.join(_here(), SEQ_RECORD)
    rec = load_record(rpath)
    keys = sorted(rec["scenes"])
    for k in keys:
        r = rec["scenes"][k]
        seq = unreal.load_asset(r["scene_sequence"])
        drift = seq_drift(_live_seq_state(seq, r["row"], k), r)
        if drift:
            _stop(run, "S%s STATE_DRIFTED|%s|nothing changed" % (k, drift))
        b = r["before"]["target"]
        _set_target(seq, r["row"], k, b["sequence"], b["start"], b["end"], b["start_offset_tick"])
        for t in seq.get_tracks():
            if str(t.get_display_name()) == r["row"]["narration_track"] and isinstance(t, unreal.MovieSceneAudioTrack):
                for s, was in zip(t.get_sections(), r["before"]["narration"] or []):
                    s.set_is_active(bool(was[2]))
        if not r["before"]["vis_track"]:
            for t in [t for t in seq.get_tracks() if str(t.get_display_name()) == VIS_TRACK_NAME]:
                seq.remove_track(t)        # return value ignored (memory: return values lie); re-listed below
        for bnd in seq.get_bindings():
            n = str(bnd.get_display_name())
            if n.startswith(OURS_OFF_PREFIX) or n.startswith(HERS_DARK_PREFIX):
                bnd.remove()                                                         # prec curtain_sleight.py:2270
        if _live_seq_state(seq, r["row"], k) != r["before"]:
            _stop(run, "S%s REVERT_READBACK|NOTHING SAVED; Don't-Save restart" % k)
    gate = census_gate(_census(), [rec["scenes"][k]["scene_sequence"] for k in keys], [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    for k in keys:
        if not unreal.EditorAssetLibrary.save_asset(rec["scenes"][k]["scene_sequence"], only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % rec["scenes"][k]["scene_sequence"])
    deleted = []
    for k in keys:
        c = rec["scenes"][k].get("copy")
        if c and unreal.EditorAssetLibrary.does_asset_exist(c):
            refs = [str(x) for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(c, False)]
            if refs:
                unreal.log_warning("KLARAHOOK_COPY_KEPT|run=%s|%s|referenced by %s" % (run, c, refs))
            elif unreal.EditorAssetLibrary.delete_asset(c) and not unreal.EditorAssetLibrary.does_asset_exist(c):
                deleted.append(c)
    os.rename(rpath, rpath + ".reverted-" + run)
    for k in keys:
        unreal.log("KLARAHOOK_EXTEND_NEXT|run=%s|S%s|restore: extend_scene_playback new_end_frame=%d"
                   % (run, k, rec["scenes"][k]["playback_before"][1]))
    unreal.log("KLARAHOOK_REVERT_SEQ_OK|run=%s|scenes=%s|copies_deleted=%s" % (run, ",".join("S" + k for k in keys), deleted))


def main():
    global ARGS_CACHE
    g = globals()
    args = g.get("KLARAHOOK_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    ARGS_CACHE = args
    if args.get("seq_record"):    # 8 Oct conductor: S2 hooks in later than S1/S4 -> its own record, so S1/S4 stay applied
        global SEQ_RECORD
        SEQ_RECORD = str(args["seq_record"])
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAHOOK-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = editor.get_game_world() is not None
    world = None if pie else editor.get_editor_world()
    wname = str(world.get_outermost().get_name()) if world is not None else None
    rpath = os.path.join(_here(), STREAM_RECORD if "STREAM" in mode else SEQ_RECORD)
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie,
             "wrong_world": None if wname == EXPECTED_WORLD else str(wname),
             "sequencer_open": None if pie else _sequencer_open(), "census": _census(),
             "decided_by": args.get("decided_by"), "record_exists": rpath if os.path.exists(rpath) else None,
             "record_applied": os.path.exists(rpath) and bool(load_record(rpath).get("applied"))}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        {"DRY": run_dry, "APPLY_STREAM": run_apply_stream, "REVERT_STREAM": run_revert_stream,
         "APPLY_SEQ": run_apply_seq, "REVERT_SEQ": run_revert_seq}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None:
    main()
