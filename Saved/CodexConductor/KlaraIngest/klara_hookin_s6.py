"""KLARA HOOK-IN S6 (7 Oct): Klara's Void streamed in, no hangar - "we just arrive to it" from Passage 6.
Offline-written, NEVER RUN IN UNREAL. Sibling of klara_hookin.py (S1/S4, live-applied 6-7 Oct; that tool, its records
and its harness are NOT touched). Harness: test_klara_hookin_s6_offline.py (system Python, pure maths only).

Gary 7 Oct (via the conductor): "import void - there's no hangar to worry about so we just arrive to it. It goes where
our current audio is, replacing it. It is incomplete and needs work."

Tiers per claim: [decl] header/source we read (file:line), [bin] installed-DLL symbol/strings, [prec] in-repo precedent
(cited), [meas] bytes/record read, [inf] inferred (why stated). Every [inf] API is probed by DRY into report["api_table"].

FACTS READ OFFLINE (bytes of the copied Content, 7 Oct) [meas]
  LS_Void: tick 24000, display 30 fps, playback [0, 5585600) ticks = 232.7333 s. Ten contiguous camera-cut-shaped
  ranges [9600 .. 5168800) ticks = 0.4 .. 215.37 s; one [0, 4512000) = 0 .. 188.0 s (= the audio, the same length as
  our S06 score, 188.0 s [meas scene_audio_import_S6_record.json]); one [420800, 5150400). Which range is which track is
  [inf] from shape; DRY reads them live.
  L_KK_Void: DirectionalLight_1, SkyAtmosphere_1, SpotLight_1/_3, CineCameraActor(_0..), BP_MHC_Elder_Female_C_1,
  LevelSequenceActor_2 -> LS_Void. No 'PlaybackSettings'/'bAutoPlay' in its name table => that actor's PlaybackSettings
  are at defaults (no auto-play) [meas: tagged properties only serialise non-default values].

MECHANISM
  PLACE  L_KK_Void is a NON-instanced LevelStreamingDynamic (as klara_hookin.py:977) with LevelTransform T chosen so her
         FIRST CUT camera pose lands ON our live "Scene 6 - ... - Entry Handoff Camera" (label [decl
         InfinityStageSceneHandoffBuilder.cpp:361]; that its pose is P06's arrival pose is [inf]: the handoff match,
         extend_scene_playback.py step 4). placement "match_entry_yaw" = translation
         + yaw (position AND heading continuous); "match_entry_translation" = translation only (heading residual
         reported). Pitch/roll/lens residuals are reported, never fixed (tilting her world is not offered).
  KEYS   her absolute keys do not follow a LevelTransform [inf: standard]; a RE-KEYED COPY (/Game/InfinityStage/
         KlaraHookin/LS_Void_S6) gets every top-level unattached Location keyed by T and Rotation.Z += yaw.
         Translation: exact for any key (constant offset). Yaw: X/Y values AND arrive/leave tangents are rotated as
         vectors and the keys set to USER/BREAK tangents, so the rotated curve is the original curve rotated, exactly,
         when X/Y share key times, interpolation, extrapolation and are unweighted; anything else REFUSES (then use
         match_entry_translation). Key API [decl SequencerScripting/Private/KeysAndChannels/MovieSceneScriptingDouble.h
         :72-218]. Rotation.Z += yaw is exact (world-Z yaw composes additively on FRotator yaw [inf: UE yaw is the
         outermost rotation]).
  TIME   shot section [S, S + her length) on the existing "Shots" track (was /Game/Scenes/LS_Void [meas CodexScene
         Transitions/inspection.json, 14 Sep]); S = 0 ("scene_start", the P06 arrival) by default. Until her first cut
         (0.4 s) and after her last cut (215.37 s) our root cuts (Entry / Exit Handoff) show [inf: nested shot cuts
         outrank root cuts only where they exist - memory puss-camera-handover-facts].
  AUDIO  our score section(s) playing SW_S6_The_Void_Live are DEACTIVATED (never deleted); her audio plays from her
         copy. Our five S6 markers are kept; DRY reports their offset from her audio.
  LIGHT  /Game/L_KK_Void is appended to the rig's ForeignLightingExemptLevels (celestial_exempt_set.py pattern; field
         [decl InfinityStageCelestialRig.h:114-121], check [decl InfinityStageCelestialRig.cpp:256-276, 314-337]).
         OURS (the rig's sun/moon/sky/fog, klara_hookin.py:81) hidden over [S, end) - P06's planned sunset ends in total
         dark into S6 (P06_SUNSET_PLAN.md), consistent. Her level is visible [0, end) via a Level Visibility track.
  HANGAR S6 still has a built hangar + LS_S6_HangarRise ("Hangar Fold") [meas Saved/CodexStructure/hangar_s6_record.
         json; scene_audio_import_S6_record.json tracks_before]. hangar_rule "hide" (proposed reading of "no hangar")
         hides every actor tagged RigAtmos.Scene6Hangar over [0, end) and disables its PPV; the rise is NOT edited.
  MEMORY initially_loaded False for L_KK_Void (APPLY_STREAM) and, in APPLY_LOAD, for S1/S4/S2's levels. The Level
         Visibility system imports ULevelStreaming::SetShouldBeVisible/SetShouldBeVisibleInEditor and UWorld::
         FlushLevelStreaming/BlockTillLevelStreamingCompleted [bin UnrealEditor-MovieSceneTracks.dll import names];
         SetShouldBeLoaded is virtual (LevelStreaming.h:447) so its use cannot be seen in imports. That 'Visible' loads
         an unloaded level with a BLOCKING flush, and that 'Hidden' does NOT unload it, is [inf] (no engine .cpp here).
         MEASURE in PIE before relying on it.

STAGES (args "mode"; confirm "<MODE> KLARAVOID"):
  DRY            read-only -> klara_hookin_s6_dry.json; KLARAVOID_DRY_OK|run=..|apply_ready=..
  APPLY_STREAM   add L_KK_Void at T (initially_loaded per args, hidden) + exempt list append; saves ONLY the map
  APPLY_SEQ      copy + re-key, retarget the shot, mute our score, Level Visibility, Ours Off, Hangar Off; saves ONLY
                 LS_DevScene_06 + the copy; prints the extend_scene_playback mode
  APPLY_LOAD     initially_loaded False (and hidden) on args.on_demand.levels; saves ONLY the map
  REVERT_SEQ / REVERT_STREAM / REVERT_LOAD restore the recorded before-state (REVERT_SEQ first, then extend back).
Never: Save All, reload a level, open/scrub Sequencer, touch Show/Master, end PIE; no unreal objects in module globals.
Importing without `unreal` runs nothing.
"""
import datetime
import hashlib
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "klara_hookin_s6"
CONFIRM_WORD = "KLARAVOID"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                     # klara_hookin.py:62
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # klara_hookin.py:64
ARGS_NAME = "klara_hookin_s6_args.json"
DRY_NAME = "klara_hookin_s6_dry.json"
STREAM_RECORD = "klara_hookin_s6_stream_record.json"
SEQ_RECORD = "klara_hookin_s6_seq_record.json"
LOAD_RECORD = "klara_hookin_s6_load_record.json"
MODES = ("DRY", "APPLY_STREAM", "REVERT_STREAM", "APPLY_SEQ", "REVERT_SEQ", "APPLY_LOAD", "REVERT_LOAD")
PLACEMENTS = ("match_entry_yaw", "match_entry_translation", "identity")
START_OPTIONS = ("scene_start", "land", "at_s")
END_RULES = ("her_playback", "her_last_cut")
HANGAR_RULES = ("hide", "keep")
VIS_TRACK_NAME = "Klara Void (hookin S6)"
OURS_OFF_PREFIX = "Klara Void S6 - Ours Off: "
HANGAR_OFF_PREFIX = "Klara Void S6 - Hangar Off: "
RIG_BINDINGS = ("sun_light_actor", "moon_light_actor", "sky_light_actor", "height_fog_actor")   # CelestialRig.h:42-52
CHOREO_TRACK_CLASS = "MovieSceneInfinityChoreoTrack"
ROOT_BINDING = "S%s Hangar Root"          # klara_hookin.py:76 [prec]
ROOT_CHANNEL_NAME = "Rotation.Y"          # klara_hookin.py:78 [prec]
USER, BREAK = "RCTM_USER", "RCTM_BREAK"
UNWEIGHTED = ("RCTWM_WEIGHTED_NONE", "NONE", "", None)
FRAME_EPS = 1.0e-6
POS_TOL_CM, ANG_TOL_DEG = 0.5, 0.01


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: time
# =====================================================================================================================

def ceil_frames(seconds, fps):                    # klara_hookin.py:96-98 [prec]
    return int(math.ceil(float(seconds) * float(fps) - FRAME_EPS))


def her_length(lower_tick, upper_tick, tick, last_cut_tick=None, rule="her_playback"):
    """Her playable length in seconds from her playback start: whole range, or up to the end of her last cut."""
    if rule not in END_RULES:
        raise PlanError("END_RULE_INVALID: %r" % rule)
    hi = upper_tick if rule == "her_playback" else last_cut_tick
    if hi is None or hi <= lower_tick:
        raise PlanError("HER_RANGE_EMPTY: [%r, %r)" % (lower_tick, hi))
    return (float(hi) - float(lower_tick)) / float(tick)


def outer_frames(len_s, fps):                     # klara_hookin.py:114-119 [prec]: ceiled, never truncates her
    exact = float(len_s) * float(fps)
    frames = int(math.ceil(exact - FRAME_EPS))
    return {"exact": exact, "frames": frames, "on_grid": abs(exact - round(exact)) <= 1e-6,
            "hold_s": (frames - exact) / float(fps)}


def choose_start(option, facts, row):
    if option == "scene_start":
        return int(facts["playback"][0]), "Scene playback start = the P06 arrival (no hangar)"
    if option == "land":
        f = facts.get("land_frame")
        return f, "S6 hangar land key (keeps our score markers aligned if her audio is ours)"
    if option == "at_s":
        if not isinstance(row.get("at_s"), (int, float)):
            return None, "at_s missing"
        return ceil_frames(row["at_s"], facts["fps"]), "args at_s"
    return None, "unknown option %r" % option


def marker_alignment(markers, track_s_by_label, her_audio_scene_s, fps, tol_frames=0.5):
    """Each of our markers vs the moment her audio reaches the same point of the music (if her audio IS our track,
    which is [inf]: same name stem, both exactly 188.0 s). delta_s > 0: the marker is LATE vs her music."""
    rows = []
    for m in markers:
        ts = track_s_by_label.get(m["label"])
        if ts is None:
            rows.append(dict(m, track_s=None, lines_up=None, note="not a score marker"))
            continue
        music_s = float(her_audio_scene_s) + float(ts)
        d = float(m["scene_s"]) - music_s
        rows.append(dict(m, track_s=ts, music_scene_s=music_s, delta_s=d, delta_frames=d * fps,
                         lines_up=abs(d * fps) <= tol_frames))
    return rows


def plan_s6(facts, row, lighting, hangar_rule):
    """facts (plain data) + args row -> plan. Content problems are refusals, never exceptions."""
    refusals, warnings = [], []
    fps = float(facts["fps"])
    her = facts.get("her") or {}
    plan = {"scene": "6", "label": facts.get("label"), "fps": fps, "refusals": refusals, "warnings": warnings}
    if not her.get("exists"):
        refusals.append("HER_LS_MISSING: %s" % row.get("her_sequence"))
        return plan
    tgt = facts.get("target")
    if not tgt:
        refusals.append("TARGET_SECTION_NOT_FOUND: no root shot section plays %s" % row.get("current_nested"))
        return plan
    if tgt.get("count", 1) != 1:
        refusals.append("TARGET_SECTION_COUNT: %d" % tgt["count"])
    cuts = sorted(her.get("cuts_tick") or [])
    try:
        len_s = her_length(her["lower_tick"], her["upper_tick"], her["tick"], cuts[-1][1] if cuts else None,
                           row.get("end_rule", "her_playback"))
    except PlanError as exc:
        refusals.append(str(exc))
        return plan
    length = outer_frames(len_s, fps)
    if not length["on_grid"]:
        warnings.append("LENGTH_OFF_GRID: %.3f frames ceiled to %d (holds %.4f s)" % (length["exact"], length["frames"],
                                                                                    length["hold_s"]))
    start, why = choose_start(row.get("start_option", "scene_start"), facts, row)
    cands = {}
    for opt in START_OPTIONS:
        f, _w = choose_start(opt, facts, row)
        if f is not None:
            cands[opt] = {"start": f, "start_s": f / fps, "end": f + length["frames"], "end_s": (f + length["frames"]) / fps}
    plan.update(her_len_s=len_s, length=length, start_why=why, start_candidates=cands)
    if start is None:
        refusals.append("START_UNKNOWN: %s" % why)
        return plan
    pb0, pb1 = int(facts["playback"][0]), int(facts["playback"][1])
    if start < pb0:
        refusals.append("START_BEFORE_PLAYBACK: %d < %d" % (start, pb0))
    section = [int(start), int(start) + length["frames"]]
    tail = row.get("tail_s", 0.0)
    if not isinstance(tail, (int, float)) or tail < 0:
        refusals.append("TAIL_INVALID: %r" % tail)
        tail = 0.0
    end = section[1] + (ceil_frames(tail, fps) if tail else 0)
    plan.update(section=section, section_s=[section[0] / fps, section[1] / fps], planned_end=end,
                planned_end_s=end / fps, end_change_s=(end - pb1) / fps)
    if cuts:
        first, last = cuts[0][0], cuts[-1][1]
        plan["her_cut_span_scene_s"] = [section[0] / fps + (first - her["lower_tick"]) / her["tick"],
                                        section[0] / fps + (last - her["lower_tick"]) / her["tick"]]
        if section[1] / fps - plan["her_cut_span_scene_s"][1] > 1.0:
            warnings.append("HER_TAIL_WITHOUT_CUTS: her cuts end at %.2f s, her section at %.2f s - our root cut "
                            "(Entry Handoff camera) shows for %.2f s" % (plan["her_cut_span_scene_s"][1], section[1] / fps,
                                                                        section[1] / fps - plan["her_cut_span_scene_s"][1]))
    else:
        refusals.append("HER_NO_CAMERA_CUTS")
    # audio: hers in, ours muted
    her_audio = []
    for a in her.get("audio") or []:
        her_audio.append(dict(a, scene_start_s=section[0] / fps + (a["start_tick"] - her["lower_tick"]) / her["tick"],
                              scene_end_s=section[0] / fps + (a["end_tick"] - her["lower_tick"]) / her["tick"]))
    plan["her_audio"] = her_audio
    if not her_audio:
        warnings.append("HER_LS_HAS_NO_AUDIO: our score is muted and nothing replaces it")
    mute = [s for s in facts.get("root_sections") or [] if s.get("sound") in (row.get("mute_sounds") or [])]
    plan["mute"] = [[s["track"], s["start"], s["end"], s["sound"]] for s in mute]
    if not mute:
        refusals.append("NOTHING_TO_MUTE: no root audio section plays %s" % row.get("mute_sounds"))
    if her_audio:
        plan["markers"] = marker_alignment(facts.get("markers") or [], row.get("marker_track_s") or {},
                                           her_audio[0]["scene_start_s"], fps)
        off = [m["label"] for m in plan["markers"] if m.get("lines_up") is False]
        if off:
            warnings.append("MARKERS_OFF_HER_AUDIO: %s (kept, not moved)" % off)
    # windows, all ending at the planned end
    vis0 = 0 if row.get("level_visible_from") == "scene_start" else section[0]
    plan["timeline"] = {"level_visible": [vis0, end], "cinematic": section,
                        "ours_off": [vis0, end] if lighting.get("ours_off", True) else None,
                        "hangar_off": [pb0, end] if hangar_rule == "hide" else None}
    allow = set(row.get("allow_past_end") or [])
    past = []
    for s in facts.get("root_sections") or []:
        if s.get("is_target") or s.get("track") == VIS_TRACK_NAME or s.get("cls") == CHOREO_TRACK_CLASS:
            continue
        if s.get("end") is not None and s["end"] > end:
            past.append(s)
            msg = "SECTION_PAST_PLANNED_END: %s %r [%s, %s) > %d" % (s.get("cls"), s.get("track"), s.get("start"),
                                                                     s.get("end"), end)
            (warnings if s.get("track") in allow else refusals).append(msg)
    plan["sections_past_end"] = past
    if facts.get("camera_owner") not in (None, "TIMELINE"):
        warnings.append("CAMERA_OWNER_%s: the dog can turn the view off her framing (Show field; not edited here)"
                        % facts["camera_owner"])
    plan["extend_mode"] = {"scene_label": facts.get("label"), "new_end_s": round(end / fps, 6), "dry_run": True}
    return plan


# =====================================================================================================================
# Pure: placement (her first cut camera onto our Entry Handoff camera)
# =====================================================================================================================

def wrap(deg):
    d = math.fmod(float(deg), 360.0)
    if d <= -180.0:
        d += 360.0
    elif d > 180.0:
        d -= 360.0
    return d


def rot2(x, y, yaw_deg):
    a = math.radians(yaw_deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def rigid_point(t, p):
    """{loc, yaw} applied to a point: R_z(yaw) p + loc (the LevelTransform convention, klara_hookin.py:280-283)."""
    x, y = rot2(p[0], p[1], t["yaw"])
    return [x + t["loc"][0], y + t["loc"][1], p[2] + t["loc"][2]]


def solve_arrival(her_cam, entry_cam, mode, lead_cm=0.0):
    """her_cam / entry_cam: {"loc": [x,y,z], "rot": [roll, pitch, yaw], "focal": mm|None, "sensor_w": mm|None}.
    Her cam is in HER level coordinates. Returns T = {loc, yaw} and the residuals at the seam (after T)."""
    if mode not in PLACEMENTS:
        raise PlanError("PLACEMENT_INVALID: %r" % mode)
    if mode == "identity":
        t = {"loc": [0.0, 0.0, 0.0], "yaw": 0.0}
    else:
        yaw = wrap(entry_cam["rot"][2] - her_cam["rot"][2]) if mode == "match_entry_yaw" else 0.0
        target = list(entry_cam["loc"])
        if lead_cm:
            fx, fy = rot2(1.0, 0.0, entry_cam["rot"][2])
            target = [target[0] + fx * lead_cm, target[1] + fy * lead_cm, target[2]]
        hx, hy = rot2(her_cam["loc"][0], her_cam["loc"][1], yaw)
        t = {"loc": [target[0] - hx, target[1] - hy, target[2] - her_cam["loc"][2]], "yaw": yaw}
    w = rigid_point(t, her_cam["loc"])
    res = {"pos_cm": math.sqrt(sum((a - b) ** 2 for a, b in zip(w, entry_cam["loc"]))),
           "yaw_deg": wrap(entry_cam["rot"][2] - (her_cam["rot"][2] + t["yaw"])),
           "pitch_deg": wrap(entry_cam["rot"][1] - her_cam["rot"][1]),
           "roll_deg": wrap(entry_cam["rot"][0] - her_cam["rot"][0])}
    if her_cam.get("hfov") is not None and entry_cam.get("hfov") is not None:
        res["hfov_deg"] = float(entry_cam["hfov"]) - float(her_cam["hfov"])
    seamless = res["pos_cm"] <= max(POS_TOL_CM, abs(lead_cm) + POS_TOL_CM) and abs(res["yaw_deg"]) <= ANG_TOL_DEG
    return {"mode": mode, "transform": t, "her_cam_world": w, "residual": res, "seamless_pos_yaw": seamless}


def hfov_deg(focal_mm, sensor_w_mm):
    if not focal_mm or not sensor_w_mm:
        return None
    return math.degrees(2.0 * math.atan(float(sensor_w_mm) / (2.0 * float(focal_mm))))


# =====================================================================================================================
# Pure: rigid re-key of one transform section
# =====================================================================================================================

def _k(row):
    return {"t": int(row["t"]), "v": float(row["v"]), "interp": row.get("interp", "RCIM_CUBIC"),
            "tmode": row.get("tmode", "RCTM_AUTO"), "arrive": float(row.get("arrive", 0.0)),
            "leave": float(row.get("leave", 0.0)), "wmode": row.get("wmode")}


def rekey_rigid(ch, t):
    """ch = {"x"|"y"|"z"|"yaw": {"keys": [{"t","v","interp","tmode","arrive","leave","wmode"}...], "default": v|None,
    "pre": extrap, "post": extrap}}. Returns {"x","y","z","yaw": {"keys": [...], "default": ...}, "problems": [...]}.
    Translation: values + loc (tangents/modes unchanged). Yaw: X/Y values and tangents rotated, modes set USER/BREAK."""
    problems = []
    yaw = float(t["yaw"])
    out = {}
    for ax in ("x", "y", "z", "yaw"):
        c = ch.get(ax) or {}
        out[ax] = {"keys": [_k(r) for r in c.get("keys") or []], "default": c.get("default")}
    if abs(yaw) > 1e-9:
        xs, ys = out["x"]["keys"], out["y"]["keys"]
        if [k["t"] for k in xs] != [k["t"] for k in ys]:
            problems.append("XY_KEY_TIMES_DIFFER: x %d keys, y %d keys" % (len(xs), len(ys)))
        else:
            for a, b in zip(xs, ys):
                if a["interp"] != b["interp"]:
                    problems.append("XY_INTERP_DIFFERS at %d: %s / %s" % (a["t"], a["interp"], b["interp"]))
                if a["wmode"] not in UNWEIGHTED or b["wmode"] not in UNWEIGHTED:
                    problems.append("WEIGHTED_TANGENT at %d" % a["t"])
        for side in ("pre", "post"):
            if (ch.get("x") or {}).get(side) != (ch.get("y") or {}).get(side):
                problems.append("XY_EXTRAPOLATION_DIFFERS: %s" % side)
        if not problems:
            c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            nx, ny = [], []
            for a, b in zip(xs, ys):
                mode = BREAK if (a["tmode"] == BREAK or b["tmode"] == BREAK) else USER
                nx.append(dict(a, v=c * a["v"] - s * b["v"], arrive=c * a["arrive"] - s * b["arrive"],
                               leave=c * a["leave"] - s * b["leave"], tmode=mode))
                ny.append(dict(b, v=s * a["v"] + c * b["v"], arrive=s * a["arrive"] + c * b["arrive"],
                               leave=s * a["leave"] + c * b["leave"], tmode=mode))
            out["x"]["keys"], out["y"]["keys"] = nx, ny
            dx, dy = out["x"]["default"], out["y"]["default"]
            if dx is not None and dy is not None:
                out["x"]["default"], out["y"]["default"] = c * dx - s * dy, s * dx + c * dy
            elif (dx is None) != (dy is None) and not xs:
                problems.append("XY_DEFAULT_HALF_SET: one axis has a default, the other is unset and unkeyed")
        for k in out["yaw"]["keys"]:
            k["v"] += yaw
        if out["yaw"]["default"] is not None:
            out["yaw"]["default"] = float(out["yaw"]["default"]) + yaw
    for i, ax in enumerate("xyz"):
        d = float(t["loc"][i])
        for k in out[ax]["keys"]:
            k["v"] += d
        if out[ax]["default"] is not None:
            out[ax]["default"] = float(out[ax]["default"]) + d
    out["problems"] = problems
    return out


def eval_hermite(k0, k1, frame):
    """Cubic segment value between two keys (unweighted; tangents per frame) - for the harness' exactness check."""
    dt = float(k1["t"] - k0["t"])
    s = (float(frame) - k0["t"]) / dt
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return h00 * k0["v"] + h10 * dt * k0["leave"] + h01 * k1["v"] + h11 * dt * k1["arrive"]


# =====================================================================================================================
# Pure: load-on-demand, exempt list, args, gates
# =====================================================================================================================

def plan_load(now, levels, want_loaded=False):
    """now = {pkg: {"streamed": bool, "initially_loaded": b, "initially_visible": b}} -> changes, refusals."""
    changes, refusals = [], []
    for pkg in levels:
        n = now.get(pkg)
        if not n or not n.get("streamed"):
            refusals.append("NOT_STREAMED: %s" % pkg)
            continue
        if n["initially_loaded"] != want_loaded or n["initially_visible"]:
            changes.append({"level": pkg, "before": {"initially_loaded": n["initially_loaded"],
                                                     "initially_visible": n["initially_visible"]},
                            "after": {"initially_loaded": want_loaded, "initially_visible": False}})
    return {"changes": changes, "refusals": refusals}


def exempt_after(before, add):
    """Append `add` (a long package name) unless already present (case-insensitive, by package)."""
    pk = [str(x).split(".")[0].lower() for x in before]
    return list(before) + ([add] if add.lower() not in pk else [])


def validate_args(args):
    r = []
    if str(args.get("mode") or "").upper() not in MODES:
        r.append("MODE_INVALID: %r" % args.get("mode"))
    row = args.get("scene") or {}
    for f in ("scene_sequence", "current_nested", "her_sequence", "level_package", "copy_path", "mute_sounds"):
        if f not in row:
            r.append("SCENE_MISSING_%s" % f.upper())
    for f in ("scene_sequence", "current_nested", "her_sequence", "level_package", "copy_path"):
        if f in row and not str(row[f]).startswith("/Game/"):
            r.append("%s_NOT_GAME_PATH" % f.upper())
    if "Master" in str(row.get("scene_sequence", "")):
        r.append("TARGET_IS_THE_MASTER")
    if row.get("copy_path") in (row.get("her_sequence"), row.get("current_nested")):
        r.append("COPY_PATH_IS_AN_ORIGINAL")
    if row.get("start_option", "scene_start") not in START_OPTIONS:
        r.append("START_OPTION_INVALID: %r" % row.get("start_option"))
    if row.get("end_rule", "her_playback") not in END_RULES:
        r.append("END_RULE_INVALID: %r" % row.get("end_rule"))
    if row.get("placement") not in PLACEMENTS:
        r.append("PLACEMENT_INVALID: %r" % row.get("placement"))
    if args.get("hangar_rule") not in HANGAR_RULES:
        r.append("HANGAR_RULE_INVALID: %r" % args.get("hangar_rule"))
    od = args.get("on_demand") or {}
    if not isinstance(od.get("levels"), list):
        r.append("ON_DEMAND_LEVELS_NOT_A_LIST")
    elif any(not str(p).startswith("/Game/") for p in od["levels"]):
        r.append("ON_DEMAND_LEVEL_NOT_GAME_PATH")
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
    if mode.startswith("APPLY") and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
    if mode.startswith("REVERT") and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    if mode == "APPLY_SEQ" and not state.get("stream_applied"):
        r.append("STREAM_NOT_APPLIED (APPLY_STREAM first)")
    if mode == "REVERT_STREAM" and state.get("seq_applied"):
        r.append("SEQ_STILL_APPLIED (REVERT_SEQ first)")
    return r


def census_gate(census, want_content, want_maps):  # klara_hookin.py:501-507 [prec]
    out = []
    if sorted(census.get("content") or []) != sorted(want_content):
        out.append("CONTENT_CENSUS: got %s want %s" % (sorted(census.get("content") or []), sorted(want_content)))
    if sorted(census.get("maps") or []) != sorted(want_maps):
        out.append("MAP_CENSUS: got %s want %s" % (sorted(census.get("maps") or []), sorted(want_maps)))
    return out


def record_path(mode):
    return LOAD_RECORD if "LOAD" in mode else STREAM_RECORD if "STREAM" in mode else SEQ_RECORD


def write_record_exclusive(path, data):           # klara_hookin.py:526-531 [prec]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):                     # klara_hookin.py:534-540 [prec]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_record(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def channel_base(name):                            # klara_reveal.py:593-595 [prec]: 'Location.X_183' -> 'Location.X'
    return re.sub(r"_\d+$", "", str(name))


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraIngest")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _stop(run, reason):
    unreal.log_error("KLARAVOID_STOPPED|run=%s|reason=%s" % (run, reason))
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


def _enum_name(v):                                 # klara_reveal.py:1134-1135 [prec]
    return str(getattr(v, "name", v)).split(".")[-1]


def _gs(guid):
    return unreal.GuidLibrary.conv_guid_to_string(guid)   # memory: str(Guid) carries an address


def _v(v):
    return [float(v.x), float(v.y), float(v.z)]


def _sequencer_open():
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    return _path(cur) if cur is not None else None


def _streaming(world):
    """{package: True} for streamed sublevels (klara_hookin.py:806-813 [prec])."""
    out = {}
    for lv in unreal.EditorLevelUtils.get_levels(world):
        pkg = _path(lv.get_outer()) if lv.get_outer() is not None else None
        if pkg and pkg != EXPECTED_WORLD:
            out[pkg] = True
    return out


def _level_actors(world, pkg):                     # klara_hookin.py:816-820 [prec]
    for lv in unreal.EditorLevelUtils.get_levels(world):
        if lv.get_outer() is not None and _path(lv.get_outer()) == pkg:
            return [a for a in _actors() if a.get_level() == lv]
    return []


def _streaming_flags(world, pkg):
    ls = unreal.GameplayStatics.get_streaming_level(world, unreal.Name(pkg))       # decl GameplayStatics.h:322
    if ls is None:
        return None, {"streamed": False}
    return ls, {"streamed": True, "initially_loaded": bool(ls.get_editor_property("initially_loaded")),
                "initially_visible": bool(ls.get_editor_property("initially_visible")),
                "level_transform": [*_v(ls.get_editor_property("level_transform").translation),
                                    float(ls.get_editor_property("level_transform").rotation.rotator().yaw)]}


def _backup(run, tag, files):                      # klara_hookin.py:828-843 [prec]
    folder = os.path.join(_project(), "Backups", "PreKlaraVoid-%s-%s" % (tag, run))
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


def _api_table():
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001 - a probe failure is a finding
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("MovieSceneScriptingDoubleKey tangent/mode getters+setters", "decl MovieSceneScriptingDouble.h:72-218",
          lambda: all(hasattr(u.MovieSceneScriptingDoubleKey, n) for n in (
              "get_tangent_mode", "set_tangent_mode", "get_arrive_tangent", "set_arrive_tangent", "get_leave_tangent",
              "set_leave_tangent", "get_interpolation_mode", "get_tangent_weight_mode")))
    probe("RichCurveTangentMode.RCTM_USER / RCTM_BREAK", "inf (enum names)",
          lambda: [repr(u.RichCurveTangentMode.RCTM_USER), repr(u.RichCurveTangentMode.RCTM_BREAK)])
    probe("GameplayStatics.get_streaming_level", "decl GameplayStatics.h:322",
          lambda: hasattr(u.GameplayStatics, "get_streaming_level"))
    probe("LevelStreamingDynamic initially_loaded / initially_visible", "prec klara_hookin.py:981-982 (live 6 Oct)",
          lambda: [u.LevelStreamingDynamic.get_default_object().get_editor_property(n)
                   for n in ("initially_loaded", "initially_visible")])
    probe("MovieSceneLevelVisibilityTrack / section set_level_names", "decl MovieSceneLevelVisibilitySection.h:43,49",
          lambda: [hasattr(u, "MovieSceneLevelVisibilityTrack"),
                   hasattr(u.MovieSceneLevelVisibilitySection, "set_level_names")])
    probe("MovieSceneBoolTrack.set_property_name_and_path", "prec CodexCurtainAuthoring/add_curtain_active_tracks.py:128-131",
          lambda: hasattr(u.MovieSceneBoolTrack, "set_property_name_and_path"))
    probe("MovieSceneDoubleChannel get_pre/post_infinity_extrapolation", "decl MovieSceneScriptingDouble.h:316-366",
          lambda: hasattr(u.MovieSceneScriptingDoubleChannel, "get_pre_infinity_extrapolation"))
    probe("channel.evaluate (between-key camera pose)", "inf (klara_reveal.py:837-844 falls back without it)",
          lambda: hasattr(u.MovieSceneScriptingDoubleChannel, "evaluate"))
    probe("CelestialRig foreign_lighting_exempt_levels", "decl InfinityStageCelestialRig.h:121",
          lambda: [a for a in _actors() if a.get_class().get_name() == "InfinityStageCelestialRig"][0]
          .get_editor_property("foreign_lighting_exempt_levels") is not None)
    return rows


# ---- her sequence -----------------------------------------------------------------------------------------------------

def _chan_map(section):
    return {channel_base(c.channel_name if hasattr(c, "channel_name") else c.get_name()): c
            for c in section.get_all_channels()}


def _key_rows(ch):
    rows = []
    for k in ch.get_keys():
        rows.append({"t": int(k.get_time().frame_number.value), "v": float(k.get_value()),
                     "interp": _enum_name(k.get_interpolation_mode()), "tmode": _enum_name(k.get_tangent_mode()),
                     "arrive": float(k.get_arrive_tangent()), "leave": float(k.get_leave_tangent()),
                     "wmode": _enum_name(k.get_tangent_weight_mode())})
    return rows


def _chan_rows(ch):
    return {"keys": _key_rows(ch), "default": float(ch.get_default()) if ch.has_default() else None,
            "pre": _enum_name(ch.get_pre_infinity_extrapolation()), "post": _enum_name(ch.get_post_infinity_extrapolation())}


def _ch_eval(ch, frame):                           # klara_reveal.py:837-844 [prec]
    try:
        if hasattr(ch, "evaluate"):
            return float(ch.evaluate(unreal.FrameTime(unreal.FrameNumber(int(frame)))))
    except Exception:  # noqa: BLE001
        pass
    keys = sorted([[r["t"], r["v"]] for r in _key_rows(ch)])
    if not keys:
        return float(ch.get_default()) if ch.has_default() else None
    for t, v in keys:
        if t == frame:
            return v
    if frame < keys[0][0]:
        return keys[0][1]
    if frame > keys[-1][0]:
        return keys[-1][1]
    return None


def _her_facts(path, world, level_pkg):
    her = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if her is None:
        return {"exists": False, "path": path}
    tick, fps = _rate(her.get_tick_resolution()), _rate(her.get_display_rate())
    tpf = int(round(tick / fps))
    out = {"exists": True, "path": path, "fps": fps, "tick": tick,
           "lower_tick": int(her.get_playback_start()) * tpf, "upper_tick": int(her.get_playback_end()) * tpf,
           "audio": [], "cuts_tick": [], "cut_rows": []}
    for t in her.get_tracks():
        if isinstance(t, unreal.MovieSceneAudioTrack):
            for a in t.get_sections():
                out["audio"].append({"sound": _path(a.get_sound()), "active": bool(a.is_active()),
                                     "start_tick": (int(a.get_start_frame()) * tpf) if a.has_start_frame() else out["lower_tick"],
                                     "end_tick": (int(a.get_end_frame()) * tpf) if a.has_end_frame() else out["upper_tick"]})
        elif isinstance(t, unreal.MovieSceneCameraCutTrack):
            for c in t.get_sections():
                g = _gs(c.get_camera_binding_id().get_editor_property("guid"))
                out["cut_rows"].append({"frames": [int(c.get_start_frame()), int(c.get_end_frame())], "guid": g})
                out["cuts_tick"].append([int(c.get_start_frame()) * tpf, int(c.get_end_frame()) * tpf])
    out["cut_rows"].sort(key=lambda r: r["frames"][0])
    out["cuts_tick"].sort()
    out["first_camera"] = _her_first_camera(her, out, world, level_pkg) if out["cut_rows"] else {"error": "NO_CUTS"}
    return out


def _her_first_camera(her, facts, world, level_pkg):
    """Her FIRST CUT camera pose in HER coordinates (before any LevelTransform): keyed channels when the camera binding
    has a transform track, else the level actor (needs the level streamed at a KNOWN transform, which is inverted)."""
    row = facts["cut_rows"][0]
    frame = row["frames"][0]
    b = [x for x in her.get_bindings() if _gs(x.get_id()) == row["guid"]]
    if len(b) != 1:
        return {"error": "HER_CAMERA_BINDING_COUNT %d" % len(b)}
    b = b[0]
    pose = {"binding": str(b.get_display_name()), "frame": frame}
    tr = [s for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack) for s in t.get_sections()]
    if len(tr) > 1:
        return dict(pose, error="HER_CAMERA_TRANSFORM_SECTIONS %d" % len(tr))
    if tr:
        cm = _chan_map(tr[0])
        vals = {}
        for n in ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z"):
            vals[n] = _ch_eval(cm[n], frame) if n in cm else None
        if all(v is not None for v in vals.values()):
            pose.update(source="keys", loc=[vals["Location." + a] for a in "XYZ"],
                        rot=[vals["Rotation." + a] for a in "XYZ"])             # roll, pitch, yaw
    actors = [a for a in _level_actors(world, level_pkg) if str(a.get_actor_label()) == pose["binding"]
              or str(a.get_name()) == pose["binding"]] if world is not None else []
    if len(actors) == 1:
        a = actors[0]
        comp = a.get_cine_camera_component() if hasattr(a, "get_cine_camera_component") else None
        if comp is not None:
            pose["focal"] = float(comp.get_editor_property("current_focal_length"))
            pose["sensor_w"] = float(comp.get_editor_property("filmback").get_editor_property("sensor_width"))
            pose["hfov"] = hfov_deg(pose["focal"], pose["sensor_w"])
        if a.get_attach_parent_actor() is not None:
            pose["error"] = "HER_CAMERA_ATTACHED: keys are relative to %s" % a.get_attach_parent_actor().get_actor_label()
        if "loc" not in pose:
            _ls, fl = _streaming_flags(world, level_pkg)
            lt = fl.get("level_transform")
            if lt is None:
                pose["error"] = "HER_CAMERA_UNKEYED_LEVEL_TRANSFORM_UNKNOWN"
            else:
                inv = {"loc": [0.0, 0.0, 0.0], "yaw": -lt[3]}
                p = rigid_point(inv, [a.get_actor_location().x - lt[0], a.get_actor_location().y - lt[1],
                                      a.get_actor_location().z - lt[2]])
                r = a.get_actor_rotation()
                pose.update(source="level_actor (inverted LevelTransform %s)" % lt, loc=p,
                            rot=[float(r.roll), float(r.pitch), wrap(float(r.yaw) - lt[3])])
    elif "loc" not in pose:
        pose["error"] = "HER_CAMERA_UNKEYED_AND_LEVEL_NOT_STREAMED (APPLY_STREAM at identity first, then DRY)"
    return pose


# ---- our Scene ----------------------------------------------------------------------------------------------------------

def _scene_cue(row):
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if c.get_editor_property("type") == unreal.InfinityCueType.SCENE
            and _path(c.get_editor_property("scene").get_editor_property("sequence")) == row["scene_sequence"]]
    return show, cues


def _land_frame(seq, problems):
    """Land key of the S6 HangarRise root (klara_hookin.py:670-701 [prec], land only)."""
    fps = _rate(seq.get_display_rate())
    hits = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            for s in t.get_sections() if s.get_sequence() is not None and "HangarRise" in _path(s.get_sequence())]
    if len(hits) != 1:
        problems.append("RISE_SUBSECTION_COUNT: %d" % len(hits))
        return None
    s = hits[0]
    rise = s.get_sequence()
    rres, rfps = _rate(rise.get_tick_resolution()), _rate(rise.get_display_rate())
    secs = [x for b in rise.get_bindings() if str(b.get_display_name()) == ROOT_BINDING % "6"
            for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack) for x in t.get_sections()]
    if len(secs) != 1:
        problems.append("ROOT_SHAPE: sections %d" % len(secs))
        return None
    ch = _chan_map(secs[0]).get(ROOT_CHANNEL_NAME)
    if ch is None:
        problems.append("ROOT_CHANNEL_MISSING")
        return None
    keys = sorted(int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value)
                  for k in ch.get_keys())
    if len(keys) < 2:
        problems.append("ROOT_KEYS: %d" % len(keys))
        return None
    lower = int(round(rise.get_playback_start() * rres / rfps))
    off = int(s.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
    return ceil_frames(s.get_start_frame_seconds() + (keys[-1] - lower - off) / rres, fps)


def _section_row(track, s):                        # klara_hookin.py:658-667 [prec]
    row = {"track": str(track.get_display_name()), "cls": track.get_class().get_name(),
           "start": int(s.get_start_frame()) if s.has_start_frame() else None,
           "end": int(s.get_end_frame()) if s.has_end_frame() else None, "active": bool(s.is_active())}
    if isinstance(s, unreal.MovieSceneSubSection):
        row["sequence"] = _path(s.get_sequence())
        row["start_offset_tick"] = int(s.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
    if isinstance(s, unreal.MovieSceneAudioSection):
        row["sound"] = _path(s.get_sound())
    return row


def _entry_camera(label):
    want = "%s — Entry Handoff Camera" % label                   # InfinityStageSceneHandoffBuilder.cpp:361 [decl]
    hits = [a for a in _actors() if str(a.get_actor_label()) == want]
    if len(hits) != 1:
        return {"error": "ENTRY_CAMERA_COUNT %d (%s)" % (len(hits), want)}
    a = hits[0]
    r = a.get_actor_rotation()
    comp = a.get_cine_camera_component()
    focal = float(comp.get_editor_property("current_focal_length"))
    sw = float(comp.get_editor_property("filmback").get_editor_property("sensor_width"))
    return {"label": want, "loc": _v(a.get_actor_location()), "rot": [float(r.roll), float(r.pitch), float(r.yaw)],
            "focal": focal, "sensor_w": sw, "hfov": hfov_deg(focal, sw)}


def _scene_facts(args, world):
    row = args["scene"]
    problems = []
    seq = unreal.load_asset(row["scene_sequence"])
    if seq is None:
        return None, ["SCENE_SEQUENCE_MISSING"], None
    fps, tick = _rate(seq.get_display_rate()), _rate(seq.get_tick_resolution())
    facts = {"scene_sequence": row["scene_sequence"], "fps": fps, "tick": tick,
             "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())], "root_sections": []}
    targets = []
    for t in seq.get_tracks():
        if t.get_class().get_name() == CHOREO_TRACK_CLASS:
            continue
        for s in t.get_sections():
            r = _section_row(t, s)
            if r.get("sequence") in (row["current_nested"], row["her_sequence"], row["copy_path"]):
                r["is_target"] = True
                targets.append(r)
            facts["root_sections"].append(r)
    facts["target"] = dict(targets[0], count=len(targets)) if targets else None
    pb0 = seq.get_playback_start_seconds()
    facts["markers"] = [{"label": str(m.get_editor_property("label")),
                         "scene_s": m.get_editor_property("frame_number").value / tick - pb0}
                        for m in seq.get_marked_frames()]                         # scene_audio_import.py:654-656 [prec]
    facts["land_frame"] = _land_frame(seq, problems)
    show, cues = _scene_cue(row)
    if len(cues) != 1:
        problems.append("SCENE_CUE_COUNT: %d" % len(cues))
        facts["label"] = None
    else:
        facts["label"] = str(cues[0].get_editor_property("label"))
        facts["camera_owner"] = _enum_name(cues[0].get_editor_property("scene").get_editor_property("camera_owner"))
        facts["entry_camera"] = _entry_camera(facts["label"])
    facts["her"] = _her_facts(row["her_sequence"], world, row["level_package"])
    return facts, problems, seq


def _rig():
    rigs = [a for a in _actors() if a.get_class().get_name() == "InfinityStageCelestialRig"]
    if len(rigs) != 1:
        raise PlanError("CELESTIAL_RIG_COUNT: %d" % len(rigs))
    return rigs[0]


def _ours(rig):                                     # klara_hookin.py:896-904 [prec]
    return [a for a in (rig.get_editor_property(n) for n in RIG_BINDINGS) if a is not None]


def _hangar_actors(tag):
    return sorted([a for a in _actors() if tag in [str(t) for t in a.get_editor_property("tags")]],
                  key=lambda a: str(a.get_actor_label()))          # hangar_build.py:339 [prec]


def _placement(facts, row):
    her_cam = (facts.get("her") or {}).get("first_camera") or {}
    entry = facts.get("entry_camera") or {}
    if her_cam.get("error") or "loc" not in her_cam:
        return None, ["HER_FIRST_CAMERA: %s" % her_cam.get("error", "no pose")]
    if entry.get("error"):
        return None, ["ENTRY_CAMERA: %s" % entry["error"]]
    out = {k: solve_arrival(her_cam, entry, k, float(row.get("lead_cm", 0.0))) for k in PLACEMENTS}
    return out, []


def _plan(args, world):
    facts, problems, seq = _scene_facts(args, world)
    if facts is None:
        return None, None, None, problems, [], seq
    plan = plan_s6(facts, args["scene"], args.get("lighting") or {}, args.get("hangar_rule"))
    placements, p2 = _placement(facts, args["scene"])
    deferred = [x for x in p2 if "UNKEYED_AND_LEVEL_NOT_STREAMED" in x]   # APPLY_STREAM reads it at identity
    plan["warnings"] += ["PLACEMENT_DEFERRED_TO_APPLY_STREAM: %s" % x for x in deferred]
    refusals = problems + plan["refusals"] + [x for x in p2 if x not in deferred]
    if placements and not placements[args["scene"]["placement"]]["seamless_pos_yaw"]:
        plan["warnings"].append("PLACEMENT_NOT_SEAMLESS: %s residual %s" % (
            args["scene"]["placement"], placements[args["scene"]["placement"]]["residual"]))
    return facts, plan, placements, refusals, plan["warnings"], seq


def run_dry(args, run, world):
    facts, plan, placements, refusals, warnings, _seq = _plan(args, world)
    row = args["scene"]
    rig_info = {}
    try:
        rig = _rig()
        ex = [str(x) for x in rig.get_editor_property("foreign_lighting_exempt_levels")]
        rig_info = {"exempt_before": ex, "exempt_after": exempt_after(ex, row["level_package"]),
                    "suppress_foreign": bool(rig.get_editor_property("suppress_foreign_environment_lighting")),
                    "ours": [str(a.get_actor_label()) for a in _ours(rig)]}
    except PlanError as exc:
        refusals.append(str(exc))
    hangar = [str(a.get_actor_label()) for a in _hangar_actors(args["hangar_tag"])]
    load_now = {p: _streaming_flags(world, p)[1] for p in list(args["on_demand"]["levels"]) + [row["level_package"]]}
    rekey_preview = None
    if facts and placements and unreal.EditorAssetLibrary.does_asset_exist(row["her_sequence"]):
        rekey_preview = _rekey_preview(unreal.load_asset(row["her_sequence"]), placements[row["placement"]]["transform"])
        bad = [r for r in rekey_preview if r.get("problems")]
        if bad:
            refusals.append("REKEY_NOT_EXACT for %s: %s (use placement match_entry_translation)"
                            % (row["placement"], [(r["binding"], r["problems"][:2]) for r in bad[:4]]))
    report = {"tool": TOOL, "run": run, "args": args, "api_table": _api_table(), "facts": facts, "plan": plan,
              "placements": placements, "rig": rig_info, "hangar_actors": hangar, "streaming_now": sorted(_streaming(world)),
              "load_now": load_now, "load_plan": plan_load(load_now, args["on_demand"]["levels"]),
              "rekey_preview": rekey_preview, "refusals": refusals, "warnings": warnings, "apply_ready": not refusals,
              "extend_mode": (plan or {}).get("extend_mode")}
    if os.path.exists(os.path.join(_here(), SEQ_RECORD)):
        report["seam_after"] = _seam_after(args, world)
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    for r in report["api_table"]:
        unreal.log("KLARAVOID_API|run=%s|ok=%d|%s|%s|%s" % (run, int(r["ok"]), r["api"], r["tier"], r["result"]))
    for t in refusals:
        unreal.log_warning("KLARAVOID_REFUSAL|run=%s|%s" % (run, t))
    for t in warnings:
        unreal.log("KLARAVOID_WARNING|run=%s|%s" % (run, t))
    for k, p in sorted((placements or {}).items()):
        unreal.log("KLARAVOID_PLACE|run=%s|%s|T=%s|residual=%s" % (run, k, p["transform"], p["residual"]))
    if plan:
        unreal.log("KLARAVOID_ROW|run=%s|section=%s|end_s=%s|timeline=%s|mute=%s|extend_mode=%s"
                   % (run, plan.get("section"), plan.get("planned_end_s"), plan.get("timeline"), plan.get("mute"),
                      json.dumps(plan.get("extend_mode"), ensure_ascii=False)))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("KLARAVOID_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|report=%s"
               % (run, int(not refusals), len(refusals), len(warnings), out))


def _rekey_preview(seq, t):
    """Pure re-key over every top-level transform section of `seq` (no writes) -> per-binding problems."""
    rows = []
    for b in seq.get_bindings():
        parent = b.get_parent()
        if parent is not None and hasattr(parent, "is_valid") and parent.is_valid():
            continue
        for tr in [x for x in b.get_tracks() if isinstance(x, unreal.MovieScene3DTransformTrack)]:
            for s in tr.get_sections():
                cm = _chan_map(s)
                if not all("Location." + a in cm for a in "XYZ"):
                    continue
                ch = {ax: _chan_rows(cm["Location." + ax.upper()]) for ax in "xyz"}
                if "Rotation.Z" in cm:
                    ch["yaw"] = _chan_rows(cm["Rotation.Z"])
                rows.append({"binding": str(b.get_display_name()), "problems": rekey_rigid(ch, t)["problems"],
                             "keys": {ax: len(ch[ax]["keys"]) for ax in ch}})
    return rows


def _ftransform(t):
    return unreal.Transform(unreal.Vector(*t["loc"]), unreal.Rotator(0.0, 0.0, float(t["yaw"])), unreal.Vector(1, 1, 1))


def _add_level(world, pkg, t, loaded, run):
    ls = unreal.EditorLevelUtils.add_level_to_world_with_transform(world, pkg, unreal.LevelStreamingDynamic,
                                                                 _ftransform(t))      # decl EditorLevelUtils.h:276-277
    if ls is None:
        _stop(run, "ADD_LEVEL_NONE|NOTHING SAVED; Don't-Save restart")
    ls.set_editor_property("initially_loaded", bool(loaded))
    ls.set_editor_property("initially_visible", False)
    lt = ls.get_editor_property("level_transform")
    got = [lt.translation.x, lt.translation.y, lt.translation.z, lt.rotation.rotator().yaw]
    if max(abs(a - b) for a, b in zip(got[:3], t["loc"])) > POS_TOL_CM or abs(wrap(got[3] - t["yaw"])) > ANG_TOL_DEG:
        _stop(run, "LEVEL_TRANSFORM_READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    if [bool(ls.get_editor_property(n)) for n in ("initially_loaded", "initially_visible")] != [bool(loaded), False]:
        _stop(run, "LEVEL_FLAGS_READBACK|NOTHING SAVED; Don't-Save restart")
    return got


def _remove_level(world, pkg, run):                 # klara_hookin.py:1014-1020 [prec]
    lv = [x for x in unreal.EditorLevelUtils.get_levels(world) if x.get_outer() is not None and _path(x.get_outer()) == pkg]
    if len(lv) != 1:
        _stop(run, "REMOVE_LEVEL_COUNT|%d|NOTHING SAVED; Don't-Save restart" % len(lv))
    if not unreal.EditorLevelUtils.remove_level_from_world(lv[0], True, False):
        _stop(run, "REMOVE_LEVEL_FAILED|NOTHING SAVED; Don't-Save restart")


def _set_exempt(rig, want, run):                    # celestial_exempt_set.py [prec]
    rig.modify()
    rig.set_editor_property("foreign_lighting_exempt_levels", [unreal.load_asset(p.split(".")[0]) for p in want])
    got = [str(x) for x in rig.get_editor_property("foreign_lighting_exempt_levels")]
    if len(got) != len(want) or any(w.split(".")[0].split("/")[-1] not in g for w, g in zip(want, got)):
        _stop(run, "EXEMPT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    return got


def run_apply_stream(args, run, world):
    row = args["scene"]
    pkg = row["level_package"]
    if not unreal.EditorAssetLibrary.does_asset_exist(pkg):
        _stop(run, "LEVEL_ASSET_MISSING|%s" % pkg)
    if pkg in _streaming(world):
        _stop(run, "ALREADY_STREAMED|%s" % pkg)
    rig = _rig()
    ex_before = [str(x) for x in rig.get_editor_property("foreign_lighting_exempt_levels")]
    rpath = os.path.join(_here(), STREAM_RECORD)
    backup = _backup(run, "Stream", [_file(EXPECTED_WORLD, ".umap")])
    rec = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY_STREAM", "level": pkg, "backup": backup,
           "exempt_before": ex_before, "levels_before": sorted(_streaming(world)), "decided_by": args.get("decided_by"),
           "applied": False, "written": datetime.datetime.now().isoformat(timespec="seconds")}
    write_record_exclusive(rpath, rec)
    loaded = bool(args["scene"].get("initially_loaded", False))
    identity = {"loc": [0.0, 0.0, 0.0], "yaw": 0.0}
    _add_level(world, pkg, identity, loaded, run)    # her level at HER coordinates, so an unkeyed camera can be read
    facts, plan, placements, refusals, _w, _seq = _plan(args, world)
    if refusals or not placements:
        _stop(run, "PLAN_REFUSED|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (" || ".join(refusals), backup))
    chosen = placements[row["placement"]]
    t = chosen["transform"]
    if row["placement"] != "identity":
        _remove_level(world, pkg, run)              # move = remove + re-add (klara_reveal.py:1672-1696 [prec])
        got = _add_level(world, pkg, t, loaded, run)
    else:
        got = [0.0, 0.0, 0.0, 0.0]
    ex_after = _set_exempt(rig, exempt_after(ex_before, pkg), run) if (args.get("lighting") or {}).get("hers_on") else ex_before
    gate = census_gate(_census(), [], [EXPECTED_WORLD])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):      # klara_hookin.py:992 [prec]
        _stop(run, "SAVE_MAP_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    rec.update(applied=True, placement=chosen, all_placements=placements, level_transform=got, exempt_after=ex_after,
               initially_loaded=loaded, her_first_camera=facts["her"]["first_camera"], entry_camera=facts["entry_camera"])
    update_record(rpath, rec)
    unreal.log("KLARAVOID_APPLY_STREAM_OK|run=%s|level=%s|T=%s|residual=%s|exempt=%s|backup=%s|record=%s"
               % (run, pkg, t, chosen["residual"], ex_after, backup, rpath))


def run_revert_stream(args, run, world):
    rpath = os.path.join(_here(), STREAM_RECORD)
    rec = load_record(rpath)
    _remove_level(world, rec["level"], run)
    if sorted(_streaming(world)) != sorted(rec["levels_before"]):
        _stop(run, "REVERT_READBACK|NOTHING SAVED; Don't-Save restart")
    rig = _rig()
    if [str(x) for x in rig.get_editor_property("foreign_lighting_exempt_levels")] != rec["exempt_before"]:
        _set_exempt(rig, rec["exempt_before"], run)
    gate = census_gate(_census(), [], [EXPECTED_WORLD])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        _stop(run, "SAVE_MAP_FAILED")
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAVOID_REVERT_STREAM_OK|run=%s" % run)


# ---- APPLY_SEQ ---------------------------------------------------------------------------------------------------------

def _find_target(seq, row):
    paths = (row["current_nested"], row["her_sequence"], row["copy_path"])
    hits = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
            and t.get_class().get_name() != CHOREO_TRACK_CLASS for s in t.get_sections() if _path(s.get_sequence()) in paths]
    if len(hits) != 1:
        raise PlanError("TARGET_SECTION_COUNT: %d" % len(hits))
    return hits[0]


def _our_bindings(seq):
    out = []
    for b in seq.get_bindings():
        n = str(b.get_display_name())
        if n.startswith(OURS_OFF_PREFIX) or n.startswith(HANGAR_OFF_PREFIX):
            out.append({"name": n, "sections": sorted([int(s.get_start_frame()), int(s.get_end_frame())]
                                                      for t in b.get_tracks() for s in t.get_sections())})
    return sorted(out, key=lambda r: r["name"]) or None


def _live_state(seq, row):
    sec = _find_target(seq, row)
    muted = [[str(t.get_display_name()), int(s.get_start_frame()), int(s.get_end_frame()), _path(s.get_sound()),
              bool(s.is_active())]
             for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneAudioTrack) for s in t.get_sections()
             if _path(s.get_sound()) in row["mute_sounds"]]
    vis = [t for t in seq.get_tracks() if str(t.get_display_name()) == VIS_TRACK_NAME]
    return {"target": {"sequence": _path(sec.get_sequence()), "start": int(sec.get_start_frame()),
                       "end": int(sec.get_end_frame()),
                       "start_offset_tick": int(sec.get_editor_property("parameters")
                                                .get_editor_property("start_frame_offset").value)},
            "score": muted or None,
            "vis_track": [{"levels": [str(n) for n in s.get_level_names()],
                           "range": [int(s.get_start_frame()), int(s.get_end_frame())]}
                          for t in vis for s in t.get_sections()] or None,
            "bindings": _our_bindings(seq)}


def _set_target(seq, row, path, start, end, offset_tick):      # klara_hookin.py:1058-1068 [prec]
    sec = _find_target(seq, row)
    child = unreal.load_asset(path)
    if child is None:
        raise PlanError("SEQUENCE_NOT_LOADED: %s" % path)
    sec.set_sequence(child)
    sec.set_range(int(start), int(end))
    p = sec.get_editor_property("parameters")
    p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(offset_tick)))
    sec.set_editor_property("parameters", p)
    return sec


def _apply_keys(ch, want, run, label):
    keys = list(ch.get_keys())
    if len(keys) != len(want["keys"]):
        _stop(run, "REKEY_KEYCOUNT|%s|NOTHING SAVED; Don't-Save restart" % label)
    for k, w in zip(keys, want["keys"]):
        if _enum_name(k.get_tangent_mode()) != w["tmode"]:
            k.set_tangent_mode(getattr(unreal.RichCurveTangentMode, w["tmode"]))   # freeze before any value moves
    for k, w in zip(keys, want["keys"]):
        k.set_value(w["v"])
        if w["tmode"] in (USER, BREAK):
            k.set_arrive_tangent(w["arrive"])
            k.set_leave_tangent(w["leave"])
    if want["default"] is not None:
        ch.set_default(want["default"])
    got = _key_rows(ch)
    for g, w in zip(got, want["keys"]):
        if g["t"] != w["t"] or abs(g["v"] - w["v"]) > 1e-2 or (w["tmode"] in (USER, BREAK) and (
                abs(g["arrive"] - w["arrive"]) > 1e-3 * max(1.0, abs(w["arrive"]))
                or abs(g["leave"] - w["leave"]) > 1e-3 * max(1.0, abs(w["leave"])))):
            _stop(run, "REKEY_READBACK|%s|t=%s|NOTHING SAVED; Don't-Save restart" % (label, g["t"]))


def _make_copy(args, t, world, run):
    """Duplicate her LS to copy_path and re-key every top-level UNATTACHED transform binding rigidly by `t`
    (rules of klara_hookin.py:1087-1139 [prec]; actor lookup in HER level only)."""
    row = args["scene"]
    dst = row["copy_path"]
    if unreal.EditorAssetLibrary.does_asset_exist(dst):
        _stop(run, "COPY_EXISTS|%s" % dst)
    copy = unreal.EditorAssetLibrary.duplicate_asset(row["her_sequence"], dst)       # prec klara_hookin.py:1076 (live)
    if copy is None:
        _stop(run, "DUPLICATE_FAILED|%s" % dst)
    names = {}
    for a in _level_actors(world, row["level_package"]):
        names.setdefault(str(a.get_actor_label()), []).append(a)
        if str(a.get_name()) != str(a.get_actor_label()):
            names.setdefault(str(a.get_name()), []).append(a)
    log = []
    for b in copy.get_bindings():
        parent = b.get_parent()
        if parent is not None and hasattr(parent, "is_valid") and parent.is_valid():
            continue
        tracks = [x for x in b.get_tracks() if isinstance(x, unreal.MovieScene3DTransformTrack)]
        if not tracks:
            continue
        nm = str(b.get_display_name())
        acts = names.get(nm, [])
        if len(acts) > 1:
            _stop(run, "REKEY_ACTOR_AMBIGUOUS|%s|NOTHING SAVED; Don't-Save restart" % nm)
        if acts and acts[0].get_attach_parent_actor() is not None:
            log.append({"binding": nm, "skipped": "attached (keys are relative)"})
            continue
        for tr in tracks:
            for s in tr.get_sections():
                cm = _chan_map(s)
                if not all("Location." + a in cm for a in "XYZ"):
                    log.append({"binding": nm, "skipped": "no Location channels", "channels": sorted(cm)})
                    continue
                ch = {ax: _chan_rows(cm["Location." + ax.upper()]) for ax in "xyz"}
                if "Rotation.Z" in cm:
                    ch["yaw"] = _chan_rows(cm["Rotation.Z"])
                want = rekey_rigid(ch, t)
                if want["problems"]:
                    _stop(run, "REKEY_NOT_EXACT|%s|%s|NOTHING SAVED; Don't-Save restart" % (nm, want["problems"]))
                for ax in "xyz":
                    _apply_keys(cm["Location." + ax.upper()], want[ax], run, "%s Location.%s" % (nm, ax.upper()))
                if abs(t["yaw"]) > 1e-9 and "Rotation.Z" in cm:
                    _apply_keys(cm["Rotation.Z"], want["yaw"], run, "%s Rotation.Z" % nm)
                log.append({"binding": nm, "keys": {ax: len(ch[ax]["keys"]) for ax in ch},
                            "actor": "level" if acts else "none (spawnable/free: keys absolute)"})
    return dst, copy, log


def _add_vis_binding(seq, actor, prefix, frames):   # klara_hookin.py:1143-1159 [prec, live 7 Oct]
    b = seq.add_possessable(actor)
    b.set_display_name(prefix + str(actor.get_actor_label()))
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    if str(t.get_property_name()) in ("None", ""):
        t.set_property_name_and_path("bHiddenInGame", "bHiddenInGame")
    if str(t.get_property_name()) != "bHiddenInGame":
        raise PlanError("VISIBILITY_TRACK_PROPERTY: %r" % str(t.get_property_name()))
    s = t.add_section()
    s.set_range(int(frames[0]), int(frames[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    list(s.get_all_channels())[0].set_default(True)
    if actor.get_class().get_name() == "PostProcessVolume":
        # a hidden PPV may still blend [inf]; disable it too (bool track precedent add_curtain_active_tracks.py:128-131)
        bt = b.add_track(unreal.MovieSceneBoolTrack)
        bt.set_property_name_and_path(unreal.Name("bEnabled"), "bEnabled")
        bs = bt.add_section()
        bs.set_range(int(frames[0]), int(frames[1]))
        bs.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        list(bs.get_all_channels())[0].set_default(False)
    return b


def run_apply_seq(args, run, world):
    row = args["scene"]
    srec = load_record(os.path.join(_here(), STREAM_RECORD))
    facts, plan, placements, refusals, _w, seq = _plan(args, world)
    if row["level_package"] not in _streaming(world):
        refusals.append("LEVEL_NOT_STREAMED")
    _ls, fl = _streaming_flags(world, row["level_package"])
    t = srec["placement"]["transform"]
    if fl.get("level_transform") is None or max(abs(a - b) for a, b in zip(fl["level_transform"][:3], t["loc"])) > \
            POS_TOL_CM or abs(wrap(fl["level_transform"][3] - t["yaw"])) > ANG_TOL_DEG:
        refusals.append("LIVE_LEVEL_TRANSFORM_NOT_RECORDED: live %s recorded %s" % (fl.get("level_transform"), t))
    rig = _rig()
    if (args.get("lighting") or {}).get("hers_on"):
        ex = [str(x) for x in rig.get_editor_property("foreign_lighting_exempt_levels")]
        if exempt_after(ex, row["level_package"]) != ex:
            refusals.append("HER_LEVEL_NOT_EXEMPT (APPLY_STREAM sets it)")
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    rpath = os.path.join(_here(), SEQ_RECORD)
    backup = _backup(run, "Seq", [_file(row["scene_sequence"], ".uasset")])
    rec = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY_SEQ", "backup": backup, "applied": False,
           "decided_by": args.get("decided_by"), "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "row": row, "scene_sequence": row["scene_sequence"], "playback_before": facts["playback"],
           "label": facts["label"], "plan": plan, "transform": t, "copy": None, "before": _live_state(seq, row)}
    write_record_exclusive(rpath, rec)
    dst, copy, rekey_log = _make_copy(args, t, world, run)
    rec.update(copy=dst, rekey=rekey_log)
    update_record(rpath, rec)
    sec = _set_target(seq, row, dst, plan["section"][0], plan["section"][1], 0)
    child = sec.get_sequence()
    mapped = [int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(sec, int(child.get_playback_start()), seq)),
              int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(sec, int(child.get_playback_end()), seq))]
    if mapped[0] != plan["section"][0] or abs(mapped[1] - plan["section"][1]) > 1:
        _stop(run, "MAPPING_READBACK|%s vs %s|NOTHING SAVED; Don't-Save restart" % (mapped, plan["section"]))
    for tr in seq.get_tracks():
        if isinstance(tr, unreal.MovieSceneAudioTrack):
            for s in tr.get_sections():
                if _path(s.get_sound()) in row["mute_sounds"]:
                    s.set_is_active(False)                       # deactivate, never delete (read back below)
    tl = plan["timeline"]
    track = seq.add_track(unreal.MovieSceneLevelVisibilityTrack)                     # prec klara_hookin.py:1213-1218
    track.set_display_name(VIS_TRACK_NAME)
    vs = track.add_section()
    vs.set_range(int(tl["level_visible"][0]), int(tl["level_visible"][1]))
    vs.set_visibility(unreal.LevelVisibility.VISIBLE)
    vs.set_level_names([unreal.Name(row["level_package"].rsplit("/", 1)[-1])])
    if tl.get("ours_off"):
        for a in _ours(rig):
            _add_vis_binding(seq, a, OURS_OFF_PREFIX, tl["ours_off"])
    hidden = []
    if tl.get("hangar_off"):
        for a in _hangar_actors(args["hangar_tag"]):
            _add_vis_binding(seq, a, HANGAR_OFF_PREFIX, tl["hangar_off"])
            hidden.append(str(a.get_actor_label()))
    after = _live_state(seq, row)
    bad = []
    if after["target"] != {"sequence": dst, "start": plan["section"][0], "end": plan["section"][1], "start_offset_tick": 0}:
        bad.append("target %s" % after["target"])
    if not after["score"] or any(m[4] for m in after["score"]):
        bad.append("score still active %s" % after["score"])
    if not (after["vis_track"] and after["vis_track"][0]["range"] == tl["level_visible"]):
        bad.append("vis %s" % after["vis_track"])
    want_b = len(_ours(rig)) * bool(tl.get("ours_off")) + len(hidden)
    if len(after["bindings"] or []) != want_b:
        bad.append("bindings %d want %d" % (len(after["bindings"] or []), want_b))
    if bad:
        _stop(run, "APPLY_READBACK|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (bad, backup))
    gate = census_gate(_census(), [row["scene_sequence"], dst], [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    for p in (row["scene_sequence"], dst):
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % p)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    if _live_state(unreal.load_asset(row["scene_sequence"]), row) != after:
        _stop(run, "POST_SAVE_READBACK")
    rec.update(applied=True, after=after, mapped_inner_range=mapped, hangar_hidden=hidden)
    update_record(rpath, rec)
    unreal.log("KLARAVOID_EXTEND_NEXT|run=%s|extend_scene_playback_mode=%s"
               % (run, json.dumps(plan["extend_mode"], ensure_ascii=False)))
    unreal.log("KLARAVOID_APPLY_SEQ_OK|run=%s|copy=%s|section=%s|muted=%d|hangar_hidden=%d|backup=%s|record=%s"
               % (run, dst, plan["section"], len(after["score"]), len(hidden), backup, rpath))


def _seam_after(args, world):
    """After APPLY_SEQ: her first cut camera read from the COPY (world coords now) vs the LIVE Entry Handoff camera."""
    row = args["scene"]
    try:
        rec = load_record(os.path.join(_here(), SEQ_RECORD))
        copy = unreal.load_asset(rec["copy"])
        f = {"exists": True, "cut_rows": []}
        for t in copy.get_tracks():
            if isinstance(t, unreal.MovieSceneCameraCutTrack):
                f["cut_rows"] += [{"frames": [int(c.get_start_frame()), int(c.get_end_frame())],
                                   "guid": _gs(c.get_camera_binding_id().get_editor_property("guid"))}
                                  for c in t.get_sections()]
        f["cut_rows"].sort(key=lambda r: r["frames"][0])
        cam = _her_first_camera(copy, f, None, row["level_package"])
        _show, cues = _scene_cue(row)
        entry = _entry_camera(str(cues[0].get_editor_property("label")))
        if "loc" not in cam or entry.get("error"):
            return {"error": cam.get("error") or entry.get("error")}
        ident = solve_arrival(cam, entry, "identity")
        return {"her_first_cam_world": cam, "entry": entry, "residual": ident["residual"],
                "seamless_pos_yaw": ident["seamless_pos_yaw"]}
    except Exception as exc:  # noqa: BLE001 - a report row, never a stop
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def run_revert_seq(args, run, world):
    rpath = os.path.join(_here(), SEQ_RECORD)
    rec = load_record(rpath)
    row = rec["row"]
    seq = unreal.load_asset(rec["scene_sequence"])
    live = _live_state(seq, row)
    if live != rec["after"]:
        _stop(run, "STATE_DRIFTED|live %s|nothing changed" % json.dumps(live, default=str)[:600])
    b = rec["before"]["target"]
    _set_target(seq, row, b["sequence"], b["start"], b["end"], b["start_offset_tick"])
    was = {(m[0], m[1], m[2], m[3]): m[4] for m in rec["before"]["score"] or []}
    for tr in seq.get_tracks():
        if isinstance(tr, unreal.MovieSceneAudioTrack):
            for s in tr.get_sections():
                key = (str(tr.get_display_name()), int(s.get_start_frame()), int(s.get_end_frame()), _path(s.get_sound()))
                if key in was:
                    s.set_is_active(bool(was[key]))
    for tr in [x for x in seq.get_tracks() if str(x.get_display_name()) == VIS_TRACK_NAME]:
        seq.remove_track(tr)                      # return value ignored (memory: return values lie); re-listed below
    for bnd in seq.get_bindings():
        n = str(bnd.get_display_name())
        if n.startswith(OURS_OFF_PREFIX) or n.startswith(HANGAR_OFF_PREFIX):
            bnd.remove()                                                         # prec klara_hookin.py:1282
    if _live_state(seq, row) != rec["before"]:
        _stop(run, "REVERT_READBACK|NOTHING SAVED; Don't-Save restart")
    gate = census_gate(_census(), [rec["scene_sequence"]], [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    if not unreal.EditorAssetLibrary.save_asset(rec["scene_sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s" % rec["scene_sequence"])
    deleted = []
    c = rec.get("copy")
    if c and unreal.EditorAssetLibrary.does_asset_exist(c):
        refs = [str(x) for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(c, False)]
        if refs:
            unreal.log_warning("KLARAVOID_COPY_KEPT|run=%s|%s|referenced by %s" % (run, c, refs))
        elif unreal.EditorAssetLibrary.delete_asset(c) and not unreal.EditorAssetLibrary.does_asset_exist(c):
            deleted.append(c)
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAVOID_EXTEND_NEXT|run=%s|restore: extend_scene_playback new_end_frame=%d"
               % (run, rec["playback_before"][1]))
    unreal.log("KLARAVOID_REVERT_SEQ_OK|run=%s|copies_deleted=%s" % (run, deleted))


# ---- APPLY_LOAD (memory: Klara levels load on demand) --------------------------------------------------------------------

def _set_load(world, changes, key, run):
    for c in changes:
        ls, _f = _streaming_flags(world, c["level"])
        if ls is None:
            _stop(run, "STREAMING_LEVEL_NONE|%s|NOTHING SAVED; Don't-Save restart" % c["level"])
        for n in ("initially_loaded", "initially_visible"):
            ls.set_editor_property(n, bool(c[key][n]))
        got = {n: bool(ls.get_editor_property(n)) for n in ("initially_loaded", "initially_visible")}
        if got != c[key]:
            _stop(run, "LOAD_FLAGS_READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (c["level"], got))


def _save_map_only(world, run, backup):
    gate = census_gate(_census(), [], [EXPECTED_WORLD])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        _stop(run, "SAVE_MAP_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))


def run_apply_load(args, run, world):
    levels = list(args["on_demand"]["levels"])
    now = {p: _streaming_flags(world, p)[1] for p in levels}
    lp = plan_load(now, levels)
    if lp["refusals"]:
        _stop(run, "LOAD_REFUSED|" + " || ".join(lp["refusals"]))
    if not lp["changes"]:
        unreal.log("KLARAVOID_APPLY_LOAD_NOOP|run=%s|already on demand: %s" % (run, levels))
        return
    rpath = os.path.join(_here(), LOAD_RECORD)
    backup = _backup(run, "Load", [_file(EXPECTED_WORLD, ".umap")])
    rec = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY_LOAD", "backup": backup, "changes": lp["changes"],
           "decided_by": args.get("decided_by"), "applied": False,
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    write_record_exclusive(rpath, rec)
    _set_load(world, lp["changes"], "after", run)
    _save_map_only(world, run, backup)
    rec["applied"] = True
    update_record(rpath, rec)
    unreal.log("KLARAVOID_APPLY_LOAD_OK|run=%s|levels=%s|backup=%s|record=%s"
               % (run, [c["level"] for c in lp["changes"]], backup, rpath))


def run_revert_load(args, run, world):
    rpath = os.path.join(_here(), LOAD_RECORD)
    rec = load_record(rpath)
    for c in rec["changes"]:
        _ls, f = _streaming_flags(world, c["level"])
        if {n: f.get(n) for n in ("initially_loaded", "initially_visible")} != c["after"]:
            _stop(run, "LOAD_DRIFTED|%s|%s|nothing changed" % (c["level"], f))
    _set_load(world, rec["changes"], "before", run)
    _save_map_only(world, run, rec["backup"])
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAVOID_REVERT_LOAD_OK|run=%s" % run)


def main():
    args = globals().get("KLARAVOID_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAVOID-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = editor.get_game_world() is not None
    world = None if pie else editor.get_editor_world()
    wname = str(world.get_outermost().get_name()) if world is not None else None
    rpath = os.path.join(_here(), record_path(mode))

    def applied(name):
        p = os.path.join(_here(), name)
        return os.path.exists(p) and bool(load_record(p).get("applied"))

    state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie,
             "wrong_world": None if wname == EXPECTED_WORLD else str(wname),
             "sequencer_open": None if pie else _sequencer_open(), "census": _census(),
             "decided_by": args.get("decided_by"), "record_exists": rpath if os.path.exists(rpath) else None,
             "record_applied": applied(record_path(mode)), "stream_applied": applied(STREAM_RECORD),
             "seq_applied": applied(SEQ_RECORD)}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        {"DRY": run_dry, "APPLY_STREAM": run_apply_stream, "REVERT_STREAM": run_revert_stream,
         "APPLY_SEQ": run_apply_seq, "REVERT_SEQ": run_revert_seq, "APPLY_LOAD": run_apply_load,
         "REVERT_LOAD": run_revert_load}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None:
    main()
