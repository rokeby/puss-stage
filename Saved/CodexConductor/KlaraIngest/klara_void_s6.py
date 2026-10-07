"""KLARA VOID S6 (7 Oct): Klara's Void action brought INTO our main stage level - no streamed level, no hangar.
Offline-written, NEVER RUN IN UNREAL. Supersedes klara_hookin_s6.py (also never run; it streamed L_KK_Void, which Gary
no longer wants). Plan + evidence: S6_VOID_PLAN.md. Harness: test_klara_void_s6_offline.py (system Python; it re-derives
every [meas] fact below from the package bytes on each run).

Tiers per claim: [decl] header/signature we read (file:line), [prec] in-repo precedent (cited), [meas] bytes/record read,
[inf] inferred (why stated). Every [inf] API is probed by DRY into report["api_table"].

FACTS (bytes of Content/Void_content/LS_Void.uasset + Content/L_KK_Void.umap, UE5 package 1018) [meas]
  * LS_Void has 14 POSSESSABLES and NO spawnables: 7 actors (NS_BeeSwarm -> NiagaraActor_29, CineCameraActor..5 ->
    CineCameraActor_1/_3/_0/_4/_5, BP_MHC_Elder_Female -> BP_MHC_Elder_Female_C_1) + 7 children (5 CameraComponent,
    Body, Face). Every actor binding resolves INTO L_KK_Void (PersistentLevel.* locators). Without her level, nothing
    binds - so the brief's "spawnable BP_MHC_Elder_Female" premise does not hold.
  * Tracks: the 5 cameras each carry ONE transform track with DEFAULTS ONLY (static, absolute world: no AttachParent on
    any root) + 3 lens float keys (35 mm, f/2.8, focus 100000) on CameraComponent; NS_BeeSwarm carries the only keyed
    transform (LINEAR keys, X/Y/Z key times differ); the woman has NO transform track - she stands where her level put
    her (1570, 100, -40) yaw 146; Body = ControlRig + AS_MHP_Void_woman, Face = ControlRig.
  * 10 cuts [9600 .. 5168800) ticks (0.4-215.37 s), first = CineCameraActor5 at (-1699, 80, 45) rot 0. Audio
    The_Void_Live_Stereo_1_ [0, 188.0 s). Playback [0, 5585600) ticks = 232.733 s at 30 fps.
  * Her level also holds what lights her: SpotLight_1/_3 (3 / 8 cd), DirectionalLight_1 (defaults), SkyAtmosphere_1,
    the BlackWater floor (StaticMeshActor_0). None is bound by her LS: a level-free import must bring them itself.

MECHANISM (APPLY saves ONLY LS_DevScene_06 + the copy; no map write)
  COPY   duplicate her LS to /Game/InfinityStage/KlaraHookin/LS_Void_S6 [prec klara_hookin.py:1076]. Each top-level
         possessable P is REBUILT as a spawnable S of the same class: add_spawnable_from_class [decl
         MovieSceneSequenceExtensions.h:435, prec curtain_sleight.py:1897 / fit_transition_drapes.py], template props
         from the measured level data, then MoveBindingContents(P, S) moves tracks AND child bindings [decl
         MovieSceneBindingExtensions.h:200-208]; children are re-parented if the move did not [decl :199]; cut sections
         re-pointed [prec curtain_sleight.py:2118]; P removed [prec klara_hookin.py:1282]. Her set pieces (spots, floor,
         directional; sky atmosphere off by default) are added as spawnables with constant transform tracks.
  PLACE  T = {loc, yaw} puts her FIRST CUT camera on our live "Scene 6 - ... - Entry Handoff Camera" [decl
         InfinityStageSceneHandoffBuilder.cpp:361 label]. Every absolute transform is re-keyed by T: translation exact;
         yaw rotates X/Y values+tangents (same key times) or, for all-LINEAR curves, re-keys on the UNION of X/Y key
         times (exact: piecewise-linear in, piecewise-linear out); Rotation.Z += yaw (world-Z yaw composes onto FRotator
         yaw [inf: UE rotator = Rz(yaw)Ry(pitch)Rx(roll); harness-proven numerically]).
  SCENE  LS_DevScene_06: Shots section -> the copy at [S, S + her length) (S = 104 f = our score land, so the five S6
         markers stay on her music, which is the same 188.0 s recording [inf: same name stem + duration; DRY compares]);
         our SW_S6_The_Void_Live section(s) DEACTIVATED (never deleted); the "Hangar Fold" sub-section (LS_S6_HangarRise:
         rise + practical wave + uplight strikes) DEACTIVATED; every RigAtmos.Scene6Hangar actor hidden [0, end)
         (bHiddenInGame, RESTORE_STATE [prec klara_hookin.py:1143-1159]), every hangar light component Intensity = 0
         [0, end), the hangar PPV bEnabled = false; our rig sun/moon/sky/fog hidden [0, end) [prec klara_hookin.py:896];
         the GLIMMER: a NiagaraActor spawnable (her /Game/FX/NS_BeeSwarm) spawned at glimmer.start_s at her swarm's
         first world pose, alive until S + overlap - a fresh system starts EMPTY and fills (WarmupTime unset [meas]) =
         the first glints growing; her own swarm spawns at S.
  LENGTH Scene 6 = S + her length; DRY/APPLY print the extend_scene_playback mode row (run that tool next).

STAGES (args "mode"; confirm "<MODE> KLARAVOIDS6"):
  DRY     read-only -> klara_void_s6_dry.json; KLARAVOIDS6_DRY_OK|run=..|apply_ready=..
  APPLY   copy + rebuild + re-key, scene edits; saves ONLY LS_DevScene_06 + the copy; KLARAVOIDS6_APPLY_OK
  REVERT  restore the recorded before-state of LS_DevScene_06, delete the copy if unreferenced; KLARAVOIDS6_REVERT_OK
Never: Save All, reload a level, open/scrub Sequencer, touch Show/Master/level, end PIE; no unreal objects in module
globals. Importing without `unreal` runs nothing.
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


TOOL = "klara_void_s6"
MARK = "KLARAVOIDS6"
CONFIRM_WORD = "KLARAVOIDS6"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                     # klara_hookin.py:62
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # klara_hookin.py:64
ARGS_NAME = "klara_void_s6_args.json"
DRY_NAME = "klara_void_s6_dry.json"
RECORD_NAME = "klara_void_s6_record.json"
MODES = ("DRY", "APPLY", "REVERT")
PLACEMENTS = ("match_entry_yaw", "match_entry_translation", "match_entry_floor", "identity")
START_OPTIONS = ("score_land", "scene_start", "at_frame")
END_RULES = ("her_playback", "her_last_cut")
GLIMMER_PLACES = ("her_first", "ahead")
PFX_HANGAR = "Klara Void S6 - Hangar Off: "
PFX_HLIGHT = "Klara Void S6 - Hangar Light Off: "
PFX_OURS = "Klara Void S6 - Ours Off: "
GLIMMER_NAME = "Klara Void S6 - Glimmer: Bee Swarm"
OUR_PREFIXES = (PFX_HANGAR, PFX_HLIGHT, PFX_OURS, GLIMMER_NAME)
SET_PREFIX = "Klara Set - "
RIG_BINDINGS = ("sun_light_actor", "moon_light_actor", "sky_light_actor", "height_fog_actor")   # CelestialRig.h:42-52
CHOREO_TRACK_CLASS = "MovieSceneInfinityChoreoTrack"
LINEAR, CUBIC, CONSTANT = "RCIM_LINEAR", "RCIM_CUBIC", "RCIM_CONSTANT"
USER, BREAK = "RCTM_USER", "RCTM_BREAK"
UNWEIGHTED = ("RCTWM_WEIGHTED_NONE", "NONE", "", None)
CONST_EXTRAP = ("RCCE_CONSTANT", "CONSTANT", 4)
FRAME_EPS = 1.0e-6
POS_TOL_CM, ANG_TOL_DEG = 0.5, 0.01


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: time
# =====================================================================================================================

def ceil_frames(seconds, fps):                    # klara_hookin.py:96-98 [prec]
    return int(math.ceil(float(seconds) * float(fps) - FRAME_EPS))


def outer_frames(len_s, fps):                     # klara_hookin.py:114-119 [prec]: ceiled, never truncates her
    exact = float(len_s) * float(fps)
    frames = int(math.ceil(exact - FRAME_EPS))
    return {"exact": exact, "frames": frames, "on_grid": abs(exact - round(exact)) <= 1e-6,
            "hold_s": (frames - exact) / float(fps)}


def her_length(her, rule):
    if rule not in END_RULES:
        raise PlanError("END_RULE_INVALID: %r" % rule)
    lo, hi = int(her["playback_tick"][0]), int(her["playback_tick"][1])
    if rule == "her_last_cut":
        cuts = sorted(c[0] for c in her.get("cuts") or [])
        if not cuts:
            raise PlanError("HER_NO_CUTS")
        hi = cuts[-1][1]
    if hi <= lo:
        raise PlanError("HER_RANGE_EMPTY: [%r, %r)" % (lo, hi))
    return (float(hi) - float(lo)) / float(her["tick"])


def marker_alignment(markers, track_s_by_label, her_audio_scene_s, fps, tol_frames=0.5):
    """Each of our markers vs the moment her music reaches the same point. delta_s > 0: the marker is LATE."""
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


# =====================================================================================================================
# Pure: poses. Rotations are [roll, pitch, yaw] degrees (transform-section channel order X, Y, Z).
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
    x, y = rot2(p[0], p[1], t["yaw"])
    return [x + t["loc"][0], y + t["loc"][1], p[2] + t["loc"][2]]


def compose_pose(t, loc, rot, scale=None):
    """World pose of a her-coordinates pose under T (yaw about world Z, then translate)."""
    out = {"loc": rigid_point(t, loc), "rot": [float(rot[0]), float(rot[1]), float(rot[2]) + float(t["yaw"])]}
    if scale is not None:
        out["scale"] = [float(s) for s in scale]
    return out


def rotator_matrix(roll, pitch, yaw):
    """UE FRotator -> 3x3 (columns = X, Y, Z axes): Rz(yaw) * Ry(-pitch) * Rx(-roll) in a right-handed frame with UE's
    sign conventions [inf: FRotationMatrix; only used by the harness to prove yaw composition numerically]."""
    sr, cr = math.sin(math.radians(roll)), math.cos(math.radians(roll))
    sp, cp = math.sin(math.radians(pitch)), math.cos(math.radians(pitch))
    sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    return [[cp * cy, sr * sp * cy - cr * sy, -(cr * sp * cy + sr * sy)],
            [cp * sy, sr * sp * sy + cr * cy, cy * sr - cr * sp * sy],
            [sp, -sr * cp, cr * cp]]


def solve_arrival(her_cam, entry_cam, mode, floor_z=0.0, her_floor_z=None):
    """T so her first-cut camera lands on our Entry Handoff camera. match_entry_floor: XY + yaw from the camera, Z puts
    her floor (her_floor_z, her coords) on floor_z (world). Residuals reported, never hidden."""
    if mode not in PLACEMENTS:
        raise PlanError("PLACEMENT_INVALID: %r" % mode)
    if mode == "identity":
        t = {"loc": [0.0, 0.0, 0.0], "yaw": 0.0}
    else:
        yaw = wrap(entry_cam["rot"][2] - her_cam["rot"][2]) if mode in ("match_entry_yaw", "match_entry_floor") else 0.0
        hx, hy = rot2(her_cam["loc"][0], her_cam["loc"][1], yaw)
        tz = entry_cam["loc"][2] - her_cam["loc"][2]
        if mode == "match_entry_floor":
            if her_floor_z is None:
                raise PlanError("HER_FLOOR_Z_UNKNOWN")
            tz = float(floor_z) - float(her_floor_z)
        t = {"loc": [entry_cam["loc"][0] - hx, entry_cam["loc"][1] - hy, tz], "yaw": yaw}
    w = rigid_point(t, her_cam["loc"])
    res = {"pos_cm": math.sqrt(sum((a - b) ** 2 for a, b in zip(w, entry_cam["loc"]))),
           "dz_cm": w[2] - entry_cam["loc"][2],
           "yaw_deg": wrap(entry_cam["rot"][2] - (her_cam["rot"][2] + t["yaw"])),
           "pitch_deg": wrap(entry_cam["rot"][1] - her_cam["rot"][1]),
           "roll_deg": wrap(entry_cam["rot"][0] - her_cam["rot"][0])}
    if her_cam.get("focal") is not None and entry_cam.get("focal") is not None:
        res["focal_mm"] = float(entry_cam["focal"]) - float(her_cam["focal"])
    seamless = res["pos_cm"] <= POS_TOL_CM and abs(res["yaw_deg"]) <= ANG_TOL_DEG \
        and abs(res["pitch_deg"]) <= ANG_TOL_DEG and abs(res["roll_deg"]) <= ANG_TOL_DEG
    return {"mode": mode, "transform": t, "her_cam_world": w, "residual": res, "seamless": seamless}


# =====================================================================================================================
# Pure: rigid re-key. ch = {"x"|"y"|"z"|"yaw": {"keys": [{"t","v","interp","tmode","arrive","leave","wmode"}], "default",
# "pre", "post"}}; t is in TICKS. Returns the same shape + "problems" + "method".
# =====================================================================================================================

def _k(row):
    return {"t": int(row["t"]), "v": float(row["v"]), "interp": row.get("interp", CUBIC),
            "tmode": row.get("tmode", "RCTM_AUTO"), "arrive": float(row.get("arrive", 0.0)),
            "leave": float(row.get("leave", 0.0)), "wmode": row.get("wmode")}


def eval_linear(keys, default, t):
    """Value of an all-LINEAR curve with constant extrapolation (her swarm curves [meas])."""
    if not keys:
        return default
    if t <= keys[0]["t"]:
        return keys[0]["v"]
    if t >= keys[-1]["t"]:
        return keys[-1]["v"]
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            s = (float(t) - a["t"]) / float(b["t"] - a["t"])
            return a["v"] + s * (b["v"] - a["v"])
    return None


def eval_hermite(k0, k1, frame):
    dt = float(k1["t"] - k0["t"])
    s = (float(frame) - k0["t"]) / dt
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return h00 * k0["v"] + h10 * dt * k0["leave"] + h01 * k1["v"] + h11 * dt * k1["arrive"]


def _all_linear_const(c):
    return all(k["interp"] == LINEAR for k in c["keys"]) and c.get("pre") in CONST_EXTRAP + (None,) \
        and c.get("post") in CONST_EXTRAP + (None,)


def rekey_rigid(ch, t):
    problems, method = [], "translate"
    yaw = float(t["yaw"])
    out = {}
    for ax in ("x", "y", "z", "yaw"):
        c = ch.get(ax) or {}
        out[ax] = {"keys": [_k(r) for r in c.get("keys") or []], "default": c.get("default"),
                   "pre": c.get("pre"), "post": c.get("post")}
    if abs(yaw) > 1e-9:
        xs, ys = out["x"]["keys"], out["y"]["keys"]
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        same_times = [k["t"] for k in xs] == [k["t"] for k in ys]
        if (xs or ys) and not same_times:
            if _all_linear_const(out["x"]) and _all_linear_const(out["y"]):
                method = "rotate_union_linear"
                times = sorted(set(k["t"] for k in xs) | set(k["t"] for k in ys))
                nx, ny = [], []
                for tt in times:
                    vx = eval_linear(xs, out["x"]["default"], tt)
                    vy = eval_linear(ys, out["y"]["default"], tt)
                    if vx is None or vy is None:
                        problems.append("UNION_AXIS_UNDEFINED at %d" % tt)
                        break
                    base = {"t": tt, "interp": LINEAR, "tmode": "RCTM_AUTO", "arrive": 0.0, "leave": 0.0, "wmode": None}
                    nx.append(dict(base, v=c * vx - s * vy))
                    ny.append(dict(base, v=s * vx + c * vy))
                out["x"]["keys"], out["y"]["keys"] = nx, ny
            else:
                problems.append("XY_KEY_TIMES_DIFFER_NOT_LINEAR: x %d keys, y %d keys" % (len(xs), len(ys)))
        elif xs:
            method = "rotate_same_times"
            for a, b in zip(xs, ys):
                if a["interp"] != b["interp"]:
                    problems.append("XY_INTERP_DIFFERS at %d: %s / %s" % (a["t"], a["interp"], b["interp"]))
                if a["wmode"] not in UNWEIGHTED or b["wmode"] not in UNWEIGHTED:
                    problems.append("WEIGHTED_TANGENT at %d" % a["t"])
            for side in ("pre", "post"):
                if out["x"][side] != out["y"][side]:
                    problems.append("XY_EXTRAPOLATION_DIFFERS: %s" % side)
            if not problems:
                nx, ny = [], []
                for a, b in zip(xs, ys):
                    mode = BREAK if (a["tmode"] == BREAK or b["tmode"] == BREAK) else USER
                    if a["interp"] == LINEAR and b["interp"] == LINEAR:
                        mode = a["tmode"]                       # linear ignores tangents: keep the mode as it was
                    nx.append(dict(a, v=c * a["v"] - s * b["v"], arrive=c * a["arrive"] - s * b["arrive"],
                                   leave=c * a["leave"] - s * b["leave"], tmode=mode))
                    ny.append(dict(b, v=s * a["v"] + c * b["v"], arrive=s * a["arrive"] + c * b["arrive"],
                                   leave=s * a["leave"] + c * b["leave"], tmode=mode))
                out["x"]["keys"], out["y"]["keys"] = nx, ny
        else:
            method = "rotate_defaults"
        if not xs and not ys:
            dx, dy = out["x"]["default"], out["y"]["default"]
            if dx is not None and dy is not None:
                out["x"]["default"], out["y"]["default"] = c * dx - s * dy, s * dx + c * dy
            elif (dx is None) != (dy is None):
                problems.append("XY_DEFAULT_HALF_SET")
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
    out["problems"], out["method"] = problems, method
    return out


# =====================================================================================================================
# Pure: plan
# =====================================================================================================================

def choose_start(option, scene, row):
    if option == "score_land":
        act = [s for s in scene.get("score") or [] if s.get("sound") in (row.get("mute_sounds") or [])]
        if len(act) != 1:
            return None, "score_land needs exactly 1 score section, found %d" % len(act)
        return int(act[0]["start"]), "our S6 score land frame (her music then sits where our markers expect it)"
    if option == "scene_start":
        return int(scene["playback"][0]), "Scene playback start (no lead, no glimmer window)"
    if option == "at_frame":
        f = row.get("at_frame")
        return (int(f), "args at_frame") if isinstance(f, int) else (None, "at_frame missing")
    return None, "unknown option %r" % option


def plan_void(facts, args):
    """facts (plain data) + args -> plan. Content problems are refusals, never exceptions."""
    row = args["scene"]
    refusals, warnings = [], []
    scene, her, entry = facts["scene"], facts["her"], facts.get("entry_camera") or {}
    fps = float(scene["fps"])
    plan = {"refusals": refusals, "warnings": warnings, "fps": fps}
    # --- bindings census: what the copy must rebuild ---
    tops = [b for b in her.get("bindings") or [] if not b.get("parent")]
    kids = [b for b in her.get("bindings") or [] if b.get("parent")]
    if any(b.get("kind") != "possessable" for b in her.get("bindings") or []):
        warnings.append("HER_HAS_NON_POSSESSABLES: %s" % [b["name"] for b in her["bindings"] if b.get("kind") != "possessable"])
    want = {p["name"] for p in (facts.get("offline") or {}).get("possessables") or [] if not p.get("parent")}
    got = {b["name"] for b in tops}
    if want and want != got:
        refusals.append("HER_BINDINGS_DRIFTED: live %s vs bytes %s" % (sorted(got), sorted(want)))
    classes = (facts.get("offline") or {}).get("her_class_paths") or {}
    rebuild = []
    for b in tops:
        cls = b.get("class")
        if cls not in classes and b["name"] not in classes:
            refusals.append("NO_CLASS_FOR: %s (%s)" % (b["name"], cls))
            continue
        rebuild.append({"name": b["name"], "class_path": classes.get(cls, classes.get(b["name"])),
                        "children": [k["name"] for k in kids if k.get("parent") == b["name"]],
                        "transform": b.get("transform")})
    plan["rebuild"] = rebuild
    # --- placement ---
    first = her.get("first_cut_camera") or {}
    if "loc" not in first or entry.get("error") or "loc" not in entry:
        refusals.append("PLACEMENT_INPUTS: her %s / entry %s" % (first.get("error", "ok"), entry.get("error", "ok")))
        return plan
    her_floor = (facts.get("offline") or {}).get("set_pieces", {}).get("floor", {}).get("loc", [0, 0, None])[2]
    placements = {k: solve_arrival(first, entry, k, row.get("floor_z_cm", 0.0), her_floor) for k in PLACEMENTS
                  if k != "match_entry_floor" or her_floor is not None}
    plan["placements"] = placements
    chosen = placements.get(row["placement"])
    if chosen is None:
        refusals.append("PLACEMENT_UNAVAILABLE: %s" % row["placement"])
        return plan
    t = chosen["transform"]
    plan["T"], plan["placement"] = t, chosen
    if not chosen["seamless"]:
        warnings.append("SEAM_NOT_EXACT: %s residual %s" % (row["placement"], chosen["residual"]))
    if her_floor is not None:
        plan["her_floor_world_z"] = her_floor + t["loc"][2]
        if abs(plan["her_floor_world_z"] - float(row.get("floor_z_cm", 0.0))) > 1.0:
            warnings.append("HER_FLOOR_OFF_OURS: her floor lands at z=%.1f, ours %.1f (placement match_entry_floor fixes "
                            "it at the cost of a %.1f cm camera drop at the seam)"
                            % (plan["her_floor_world_z"], row.get("floor_z_cm", 0.0),
                               plan["her_floor_world_z"] - float(row.get("floor_z_cm", 0.0))))
    # --- re-key previews of every transform she keys ---
    rk = []
    for r in rebuild:
        if r.get("transform"):
            res = rekey_rigid(r["transform"], t)
            rk.append({"binding": r["name"], "method": res["method"], "problems": res["problems"],
                       "keys": {ax: len((r["transform"].get(ax) or {}).get("keys") or []) for ax in ("x", "y", "z", "yaw")}})
            if res["problems"]:
                refusals.append("REKEY_NOT_EXACT: %s %s" % (r["name"], res["problems"]))
    plan["rekey"] = rk
    # --- time ---
    try:
        len_s = her_length(her, row.get("end_rule", "her_playback"))
    except PlanError as exc:
        refusals.append(str(exc))
        return plan
    length = outer_frames(len_s, fps)
    start, why = choose_start(row.get("start_option", "score_land"), scene, row)
    if start is None:
        refusals.append("START_UNKNOWN: %s" % why)
        return plan
    pb0, pb1 = int(scene["playback"][0]), int(scene["playback"][1])
    if start < pb0:
        refusals.append("START_BEFORE_PLAYBACK: %d < %d" % (start, pb0))
    section = [start, start + length["frames"]]
    end = section[1]
    plan.update(her_len_s=len_s, length=length, start_why=why, section=section,
                section_s=[section[0] / fps, section[1] / fps], planned_end=end, planned_end_s=end / fps,
                end_change_s=(end - pb1) / fps)
    if not length["on_grid"]:
        warnings.append("LENGTH_OFF_GRID: %.3f frames ceiled to %d (holds her last frame %.4f s)"
                        % (length["exact"], length["frames"], length["hold_s"]))
    alt = {}
    for rule in END_RULES:
        try:
            f = outer_frames(her_length(her, rule), fps)["frames"]
            alt[rule] = {"end": start + f, "end_s": (start + f) / fps}
        except PlanError:
            pass
    plan["end_alternatives"] = alt
    cuts = sorted(c[0] for c in her.get("cuts") or [])
    if cuts:
        lo = float(her["playback_tick"][0])
        span = [section[0] / fps + (cuts[0][0] - lo) / her["tick"], section[0] / fps + (cuts[-1][1] - lo) / her["tick"]]
        plan["her_cut_span_scene_s"] = span
        if section[1] / fps - span[1] > 1.0:
            warnings.append("HER_TAIL_WITHOUT_CUTS: her cuts end at %.2f s, the scene at %.2f s - our root cut (Entry/Exit "
                            "Handoff camera) shows for %.2f s" % (span[1], section[1] / fps, section[1] / fps - span[1]))
    else:
        refusals.append("HER_NO_CAMERA_CUTS")
    # --- audio + markers ---
    au = her.get("audio") or {}
    if au:
        a0 = section[0] / fps + (au["range_tick"][0] - her["playback_tick"][0]) / her["tick"]
        plan["her_audio"] = {"sound": au["sound"], "scene_s": [a0, a0 + (au["range_tick"][1] - au["range_tick"][0]) / her["tick"]]}
        plan["markers"] = marker_alignment(scene.get("markers") or [], row.get("marker_track_s") or {}, a0, fps)
        off = [m["label"] for m in plan["markers"] if m.get("lines_up") is False]
        if off:
            lead = None
            land = [m for m in plan["markers"] if m.get("track_s") == 0.0]
            if land:
                lead = int(round(land[0]["scene_s"] * fps))
            warnings.append("MARKERS_OFF_HER_AUDIO: %s (kept, not moved); start_option score_land / at_frame %s lines "
                            "them up" % (off, lead))
    else:
        warnings.append("HER_LS_HAS_NO_AUDIO")
    mute = [s for s in scene.get("score") or [] if s.get("sound") in (row.get("mute_sounds") or [])]
    plan["mute"] = mute
    if not mute:
        refusals.append("NOTHING_TO_MUTE: no root audio section plays %s" % row.get("mute_sounds"))
    rise = [s for s in scene.get("subs") or [] if row.get("rise_mark", "HangarRise") in str(s.get("sequence"))]
    hg = args.get("hangar") or {}
    if hg.get("mute_rise", True) and len(rise) != 1:
        refusals.append("RISE_SECTION_COUNT: %d" % len(rise))
    plan["rise"] = rise
    # --- glimmer ---
    gl = args.get("glimmer") or {}
    glim = None
    if gl.get("enabled"):
        g0 = ceil_frames(gl.get("start_s", 1.0), fps)
        g1 = section[0] + ceil_frames(gl.get("overlap_s", 0.0), fps)
        if g0 >= section[0]:
            refusals.append("GLIMMER_NO_LEAD: start %d >= her start %d (use start_option score_land / at_frame)"
                            % (g0, section[0]))
        sw = (facts.get("offline") or {}).get("swarm") or {}
        if gl.get("place", "her_first") == "her_first":
            pose = compose_pose(t, sw.get("first_loc", [0, 0, 0]), [0.0, 0.0, 0.0], sw.get("scale", [1, 1, 1]))
        else:
            fx, fy = rot2(1.0, 0.0, entry["rot"][2])
            a = float(gl.get("ahead_cm", 1200.0))
            pose = {"loc": [entry["loc"][0] + fx * a, entry["loc"][1] + fy * a, entry["loc"][2]], "rot": [0.0, 0.0, 0.0],
                    "scale": list(sw.get("scale", [1, 1, 1]))}
            warnings.append("GLIMMER_AHEAD_JUMPS: the glimmer sits %.0f cm ahead, her swarm at her own pose - it jumps at"
                            " the handoff" % a)
        dist = math.sqrt(sum((p - q) ** 2 for p, q in zip(pose["loc"], entry["loc"])))
        glim = {"spawn": [g0, g1], "spawn_s": [g0 / fps, g1 / fps], "pose": pose, "distance_cm": dist,
                "system": gl.get("system"), "scale_from": float(gl.get("scale_from", 1.0))}
        if g1 > section[0]:
            warnings.append("GLIMMER_OVERLAP: two swarm instances for %.2f s from her start (density doubles, then the "
                            "glimmer's half vanishes); overlap_s 0 makes it a clean empty-and-refill instead"
                            % ((g1 - section[0]) / fps))
    plan["glimmer"] = glim
    # --- windows ---
    plan["timeline"] = {"lead": [pb0, section[0]], "cinematic": section, "glimmer": glim["spawn"] if glim else None,
                        "hangar_off": [pb0, end] if hg.get("hide", True) else None,
                        "hangar_lights_zero": [pb0, end] if hg.get("zero_lights", True) else None,
                        "ours_off": [pb0, end] if args.get("ours_off", True) else None,
                        "set_pieces_lit": section}
    # --- set pieces (her coordinates -> world) ---
    sp = (facts.get("offline") or {}).get("set_pieces") or {}
    want_sp = args.get("set_pieces") or {}
    pieces = []
    for key in ("spots", "floor", "directional", "sky_atmosphere"):
        if not want_sp.get(key):
            continue
        for item in (sp.get(key) if isinstance(sp.get(key), list) else [sp.get(key)]):
            if not item:
                refusals.append("SET_PIECE_FACTS_MISSING: %s" % key)
                continue
            pieces.append(dict(item, kind=key, world=compose_pose(t, item["loc"], item["rot"], item.get("scale"))))
    if want_sp.get("directional"):
        warnings.append("HER_DIRECTIONAL_LIGHTS_OUR_WORLD: a directional light is global - for her section it lights "
                        "everything her cameras see, not only her set (Gary's look call)")
    plan["set_pieces"] = pieces
    wp = (facts.get("offline") or {}).get("woman_pose")
    if wp:
        plan["woman_world"] = compose_pose(t, wp["loc"], wp["rot"])
    # --- past-end check + extend row ---
    for s in scene.get("sections") or []:
        if s.get("end") is not None and s["end"] > end and not s.get("ours"):
            warnings.append("SECTION_PAST_PLANNED_END: %s %r [%s, %s) > %d" % (s.get("cls"), s.get("track"), s.get("start"),
                                                                           s.get("end"), end))
    if scene.get("camera_owner") not in (None, "TIMELINE"):
        warnings.append("CAMERA_OWNER_%s: the dog can turn the view off her framing (Show field; not edited here)"
                        % scene["camera_owner"])
    plan["extend_mode"] = {"scene_label": scene.get("label"), "new_end_s": round(end / fps, 6), "dry_run": True}
    return plan


# =====================================================================================================================
# Pure: args, gates, records
# =====================================================================================================================

def validate_args(args):
    r = []
    if str(args.get("mode") or "").upper() not in MODES:
        r.append("MODE_INVALID: %r" % args.get("mode"))
    row = args.get("scene") or {}
    for f in ("scene_sequence", "current_nested", "her_sequence", "copy_path", "mute_sounds", "placement"):
        if f not in row:
            r.append("SCENE_MISSING_%s" % f.upper())
    for f in ("scene_sequence", "current_nested", "her_sequence", "copy_path"):
        if f in row and not str(row[f]).startswith("/Game/"):
            r.append("%s_NOT_GAME_PATH" % f.upper())
    if "Master" in str(row.get("scene_sequence", "")):
        r.append("TARGET_IS_THE_MASTER")
    if row.get("copy_path") in (row.get("her_sequence"), row.get("current_nested")):
        r.append("COPY_PATH_IS_AN_ORIGINAL")
    if row.get("placement") not in PLACEMENTS:
        r.append("PLACEMENT_INVALID: %r" % row.get("placement"))
    if row.get("start_option", "score_land") not in START_OPTIONS:
        r.append("START_OPTION_INVALID: %r" % row.get("start_option"))
    if row.get("end_rule", "her_playback") not in END_RULES:
        r.append("END_RULE_INVALID: %r" % row.get("end_rule"))
    gl = args.get("glimmer") or {}
    if gl.get("enabled"):
        if gl.get("place", "her_first") not in GLIMMER_PLACES:
            r.append("GLIMMER_PLACE_INVALID: %r" % gl.get("place"))
        for f in ("start_s", "overlap_s", "scale_from"):
            if not isinstance(gl.get(f), (int, float)) or gl[f] < 0:
                r.append("GLIMMER_%s_INVALID" % f.upper())
        if not str(gl.get("system", "")).startswith("/Game/"):
            r.append("GLIMMER_SYSTEM_NOT_GAME_PATH")
    if not isinstance(args.get("her_offline_facts"), dict):
        r.append("HER_OFFLINE_FACTS_MISSING")
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
    if mode == "APPLY" and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode == "APPLY" and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
    if mode == "APPLY" and state.get("copy_exists"):
        r.append("COPY_EXISTS: %s" % state["copy_exists"])
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def census_gate(census, want_content, want_maps):  # klara_hookin.py:501-507 [prec]
    out = []
    if sorted(census.get("content") or []) != sorted(want_content):
        out.append("CONTENT_CENSUS: got %s want %s" % (sorted(census.get("content") or []), sorted(want_content)))
    if sorted(census.get("maps") or []) != sorted(want_maps):
        out.append("MAP_CENSUS: got %s want %s" % (sorted(census.get("maps") or []), sorted(want_maps)))
    return out


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


def is_ours(name):
    return any(str(name).startswith(p) for p in OUR_PREFIXES)


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
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
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


def _backup(run, files):                           # klara_hookin.py:828-843 [prec]
    folder = os.path.join(_project(), "Backups", "PreKlaraVoidS6-%s" % run)
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
    probe("LevelSequence.add_spawnable_from_class", "decl MovieSceneSequenceExtensions.h:435 (deprecated 5.5); prec "
          "curtain_sleight.py:1897", lambda: hasattr(u.LevelSequence, "add_spawnable_from_class"))
    probe("MovieSceneBindingExtensions.move_binding_contents", "decl MovieSceneBindingExtensions.h:208",
          lambda: hasattr(u.MovieSceneBindingExtensions, "move_binding_contents"))
    probe("MovieSceneBindingProxy.get_object_template / set_parent / get_parent", "decl MovieSceneBindingExtensions.h"
          ":172,190,199", lambda: all(hasattr(u.MovieSceneBindingProxy, n) for n in ("get_object_template", "set_parent",
                                                                                    "get_parent")))
    probe("LevelSequence.get_possessables / get_spawnables", "decl MovieSceneSequenceExtensions.h:392,401",
          lambda: hasattr(u.LevelSequence, "get_possessables") and hasattr(u.LevelSequence, "get_spawnables"))
    probe("MovieSceneCameraCutSection.set_camera_binding_id", "decl MovieSceneCameraCutSection.h:49; prec "
          "curtain_sleight.py:2118", lambda: hasattr(u.MovieSceneCameraCutSection, "set_camera_binding_id"))
    probe("MovieSceneScriptingDoubleChannel.add_key(time_unit, interpolation)", "decl Private/KeysAndChannels/"
          "MovieSceneScriptingDouble.h:245", lambda: hasattr(u.MovieSceneScriptingDoubleChannel, "add_key"))
    probe("MovieSceneSpawnTrack", "prec curtain_sleight.py:1819-1835", lambda: hasattr(u, "MovieSceneSpawnTrack"))
    probe("MovieSceneBoolTrack.set_property_name_and_path", "prec CodexCurtainAuthoring/add_curtain_active_tracks.py",
          lambda: hasattr(u.MovieSceneBoolTrack, "set_property_name_and_path"))
    probe("CameraFocusMethod.DISABLE", "inf (enum name)", lambda: repr(u.CameraFocusMethod.DISABLE))
    probe("PostProcessSettings override_color_saturation / color_saturation_shadows", "inf (property names)",
          lambda: [n for n in ("override_color_saturation", "color_saturation", "override_color_saturation_shadows",
                               "color_saturation_shadows") if u.PostProcessSettings().get_editor_property(n) is not None])
    probe("NiagaraComponent.set_asset", "inf", lambda: hasattr(u.NiagaraComponent, "set_asset"))
    probe("LightUnits.CANDELAS", "inf (enum name)", lambda: repr(u.LightUnits.CANDELAS))
    probe("MovieSceneTimeUnit.TICK_RESOLUTION", "prec klara_hookin_s6.py:_land_frame", lambda: repr(
        u.MovieSceneTimeUnit.TICK_RESOLUTION))
    return rows


# ---- channels --------------------------------------------------------------------------------------------------------

def _chan_map(section):
    return {channel_base(c.channel_name if hasattr(c, "channel_name") else c.get_name()): c
            for c in section.get_all_channels()}


def _key_rows(ch):
    rows = []
    for k in ch.get_keys():
        rows.append({"t": int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                     "v": float(k.get_value()), "interp": _enum_name(k.get_interpolation_mode()),
                     "tmode": _enum_name(k.get_tangent_mode()), "arrive": float(k.get_arrive_tangent()),
                     "leave": float(k.get_leave_tangent()), "wmode": _enum_name(k.get_tangent_weight_mode())})
    return rows


def _chan_rows(ch):
    return {"keys": _key_rows(ch), "default": float(ch.get_default()) if ch.has_default() else None,
            "pre": _enum_name(ch.get_pre_infinity_extrapolation()), "post": _enum_name(ch.get_post_infinity_extrapolation())}


def _transform_rows(binding):
    secs = [s for t in binding.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack) for s in t.get_sections()]
    if len(secs) != 1:
        return None, len(secs)
    cm = _chan_map(secs[0])
    if not all(n in cm for n in ("Location.X", "Location.Y", "Location.Z", "Rotation.Z")):
        return None, -1
    rows = {ax: _chan_rows(cm["Location." + ax.upper()]) for ax in "xyz"}
    rows["yaw"] = _chan_rows(cm["Rotation.Z"])
    rows["roll"] = _chan_rows(cm["Rotation.X"]) if "Rotation.X" in cm else None
    rows["pitch"] = _chan_rows(cm["Rotation.Y"]) if "Rotation.Y" in cm else None
    return rows, 1


def _pose_at(rows, tick):
    """Pose of a transform at `tick`: defaults, exact keys, or linear keys; else None (refused upstream)."""
    out = []
    for ax in ("x", "y", "z", "roll", "pitch", "yaw"):
        c = rows.get(ax)
        if c is None:
            out.append(0.0)
            continue
        if not c["keys"]:
            out.append(c["default"] if c["default"] is not None else 0.0)
            continue
        hit = [k["v"] for k in c["keys"] if k["t"] == tick]
        if hit:
            out.append(hit[0])
        elif all(k["interp"] == LINEAR for k in c["keys"]):
            out.append(eval_linear(sorted(c["keys"], key=lambda k: k["t"]), c["default"], tick))
        else:
            return None
    return {"loc": out[:3], "rot": out[3:]}


# ---- facts ----------------------------------------------------------------------------------------------------------

def _her_facts(path, offline):
    her = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if her is None:
        return {"exists": False, "path": path}
    tick, fps = _rate(her.get_tick_resolution()), _rate(her.get_display_rate())
    tpf = int(round(tick / fps))
    out = {"exists": True, "path": path, "fps": fps, "tick": tick,
           "playback_tick": [int(her.get_playback_start()) * tpf, int(her.get_playback_end()) * tpf],
           "cuts": [], "bindings": []}
    spawn_ids = {_gs(b.get_id()) for b in her.get_spawnables()}
    by_id = {}
    for b in her.get_bindings():
        par = b.get_parent()
        pid = _gs(par.get_id()) if par is not None and par.is_valid() else None
        tr, ntr = _transform_rows(b)
        row = {"name": str(b.get_display_name()), "id": _gs(b.get_id()),
               "kind": "spawnable" if _gs(b.get_id()) in spawn_ids else "possessable", "parent_id": pid,
               "class": b.get_possessed_object_class().get_name() if b.get_possessed_object_class() else None,
               "tracks": [[t.get_class().get_name(), str(t.get_display_name()), len(t.get_sections())] for t in b.get_tracks()],
               "transform": tr, "transform_sections": ntr}
        if tr:
            keyed = any((tr.get(a) or {}).get("keys") for a in ("x", "y", "z", "roll", "pitch", "yaw"))
            row["keys_absolute_world"] = pid is None    # top-level + no attach parent in her level [meas umap]
            row["transform_kind"] = "keyed" if keyed else "defaults only"
        by_id[row["id"]] = row
        out["bindings"].append(row)
    for r in out["bindings"]:
        r["parent"] = by_id[r["parent_id"]]["name"] if r["parent_id"] in by_id else None
    for t in her.get_tracks():
        if isinstance(t, unreal.MovieSceneAudioTrack):
            for a in t.get_sections():
                out["audio"] = {"sound": _path(a.get_sound()), "active": bool(a.is_active()),
                                "range_tick": [int(a.get_start_frame()) * tpf if a.has_start_frame() else out["playback_tick"][0],
                                               int(a.get_end_frame()) * tpf if a.has_end_frame() else out["playback_tick"][1]],
                                "duration_s": _duration(a.get_sound())}
        elif isinstance(t, unreal.MovieSceneCameraCutTrack):
            for c in t.get_sections():
                g = _gs(c.get_camera_binding_id().get_editor_property("guid"))
                out["cuts"].append([[int(c.get_start_frame()) * tpf, int(c.get_end_frame()) * tpf],
                                    by_id.get(g, {}).get("name", g)])
    out["cuts"].sort()
    if out["cuts"]:
        name, t0 = out["cuts"][0][1], out["cuts"][0][0][0]
        cam = [r for r in out["bindings"] if r["name"] == name and not r["parent"]]
        pose = _pose_at(cam[0]["transform"], t0) if len(cam) == 1 and cam[0]["transform"] else None
        out["first_cut_camera"] = dict(pose, binding=name, tick=t0, focal=35.0) if pose else \
            {"error": "FIRST_CUT_CAMERA_POSE_UNREADABLE (%s)" % name}
    else:
        out["first_cut_camera"] = {"error": "NO_CUTS"}
    return out


def _duration(sound):
    try:
        return float(sound.get_editor_property("duration")) if sound is not None else None   # [inf] property name
    except Exception as exc:  # noqa: BLE001 - a report field
        return "unreadable: %s" % exc


def _entry_camera(label):
    want = "%s — Entry Handoff Camera" % label            # InfinityStageSceneHandoffBuilder.cpp:361 [decl]
    hits = [a for a in _actors() if str(a.get_actor_label()) == want]
    if len(hits) != 1:
        return {"error": "ENTRY_CAMERA_COUNT %d (%s)" % (len(hits), want)}
    a = hits[0]
    r = a.get_actor_rotation()
    comp = a.get_cine_camera_component()
    return {"label": want, "loc": _v(a.get_actor_location()), "rot": [float(r.roll), float(r.pitch), float(r.yaw)],
            "focal": float(comp.get_editor_property("current_focal_length")),
            "sensor_w": float(comp.get_editor_property("filmback").get_editor_property("sensor_width"))}


def _section_row(track, s):                        # klara_hookin.py:658-667 [prec]
    row = {"track": str(track.get_display_name()), "cls": track.get_class().get_name(),
           "start": int(s.get_start_frame()) if s.has_start_frame() else None,
           "end": int(s.get_end_frame()) if s.has_end_frame() else None, "active": bool(s.is_active())}
    if isinstance(s, unreal.MovieSceneSubSection):
        row["sequence"] = _path(s.get_sequence())
        row["start_offset"] = int(s.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
    if isinstance(s, unreal.MovieSceneAudioSection):
        row["sound"] = _path(s.get_sound())
    return row


def _scene_facts(args):
    row = args["scene"]
    seq = unreal.load_asset(row["scene_sequence"])
    if seq is None:
        raise PlanError("SCENE_SEQUENCE_MISSING")
    fps, tick = _rate(seq.get_display_rate()), _rate(seq.get_tick_resolution())
    f = {"fps": fps, "tick": tick, "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
         "sections": [], "score": [], "subs": [], "shots": []}
    for t in seq.get_tracks():
        if t.get_class().get_name() == CHOREO_TRACK_CLASS:
            continue
        for s in t.get_sections():
            r = _section_row(t, s)
            f["sections"].append(r)
            if r.get("sound"):
                f["score"].append(r)
            if isinstance(t, unreal.MovieSceneCinematicShotTrack):
                f["shots"].append(r)
            elif isinstance(t, unreal.MovieSceneSubTrack):
                f["subs"].append(r)
    pb0 = seq.get_playback_start_seconds()
    f["markers"] = [{"label": str(m.get_editor_property("label")),
                     "scene_s": m.get_editor_property("frame_number").value / tick - pb0}
                    for m in seq.get_marked_frames()]                         # scene_audio_import.py:654-656 [prec]
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if c.get_editor_property("type") == unreal.InfinityCueType.SCENE
            and _path(c.get_editor_property("scene").get_editor_property("sequence")) == row["scene_sequence"]]
    if len(cues) == 1:
        f["label"] = str(cues[0].get_editor_property("label"))
        f["camera_owner"] = _enum_name(cues[0].get_editor_property("scene").get_editor_property("camera_owner"))
    else:
        f["label"] = None
        f["cue_count"] = len(cues)
    return f, seq


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


def _hangar_facts(tag):
    rows = []
    for a in _hangar_actors(tag):
        lc = a.get_component_by_class(unreal.LightComponent)
        r = {"label": str(a.get_actor_label()), "class": a.get_class().get_name()}
        try:
            r["hidden_in_game"] = bool(a.get_editor_property("hidden"))           # [inf] property name
        except Exception as exc:  # noqa: BLE001 - a report field
            r["hidden_in_game"] = "unreadable: %s" % exc
        if lc is not None:
            r["intensity"] = float(lc.get_editor_property("intensity"))
        if r["label"].endswith("Hangar Root"):
            rr = a.get_actor_rotation()
            r["rot"] = [float(rr.roll), float(rr.pitch), float(rr.yaw)]
        rows.append(r)
    return rows


def _facts(args):
    row = args["scene"]
    scene, seq = _scene_facts(args)
    facts = {"scene": scene, "offline": args["her_offline_facts"],
             "her": _her_facts(row["her_sequence"], args["her_offline_facts"]),
             "entry_camera": _entry_camera(scene["label"]) if scene.get("label") else {"error": "NO_SCENE_LABEL"}}
    if not facts["her"].get("exists"):
        raise PlanError("HER_LS_MISSING: %s" % row["her_sequence"])
    return facts, seq


# ---- DRY ------------------------------------------------------------------------------------------------------------

def run_dry(args, run, world):
    facts, _seq = _facts(args)
    plan = plan_void(facts, args)
    refusals, warnings = list(plan["refusals"]), list(plan["warnings"])
    off = args["her_offline_facts"]
    loads = {}
    for k, p in sorted((off.get("her_class_paths") or {}).items()):
        loads["class " + k] = unreal.load_class(None, p) is not None
    for p in [args["glimmer"]["system"], off["set_pieces"]["floor"]["mesh"]] + off["set_pieces"]["floor"]["override_materials"]:
        loads[p] = unreal.EditorAssetLibrary.does_asset_exist(p)
    loads["our swarm system /Game/Scenes/Effects/Swarm/NS_BeeSwarm (C++ actor's default)"] = \
        unreal.EditorAssetLibrary.does_asset_exist("/Game/Scenes/Effects/Swarm/NS_BeeSwarm")
    for k, ok in loads.items():
        if not ok and not k.startswith("our swarm"):
            refusals.append("ASSET_OR_CLASS_MISSING: %s" % k)
    hangar = _hangar_facts(args["hangar"]["tag"])
    if not hangar:
        refusals.append("HANGAR_ACTORS_NONE: %s" % args["hangar"]["tag"])
    lit = [h for h in hangar if h.get("intensity", 0.0) > 0.0]
    if lit:
        warnings.append("HANGAR_LIGHTS_LIT_NOW: %d (%s...) - visible from P06 unless hidden there too; S6 zeroes them"
                        % (len(lit), [h["label"] for h in lit[:4]]))
    rig_info = {}
    try:
        rig_info = {"ours": [str(a.get_actor_label()) for a in _ours(_rig())]}
    except PlanError as exc:
        refusals.append(str(exc))
    au = facts["her"].get("audio") or {}
    ours = unreal.load_asset(args["scene"]["mute_sounds"][0])
    audio_cmp = {"hers_s": au.get("duration_s"), "ours_s": _duration(ours)}
    report = {"tool": TOOL, "run": run, "args": args, "api_table": _api_table(), "facts": facts, "plan": plan,
              "loads": loads, "hangar": hangar, "rig": rig_info, "audio_compare": audio_cmp,
              "refusals": refusals, "warnings": warnings, "apply_ready": not refusals,
              "extend_mode": plan.get("extend_mode")}
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    for r in report["api_table"]:
        unreal.log("%s_API|run=%s|ok=%d|%s|%s|%s" % (MARK, run, int(r["ok"]), r["api"], r["tier"], r["result"]))
    for b in facts["her"]["bindings"]:
        unreal.log("%s_BINDING|run=%s|%s|kind=%s|parent=%s|class=%s|tracks=%s|transform=%s|absolute=%s"
                   % (MARK, run, b["name"], b["kind"], b["parent"], b["class"], b["tracks"], b.get("transform_kind"),
                      b.get("keys_absolute_world")))
    for t in refusals:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, t))
    for t in warnings:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, t))
    if plan.get("T"):
        unreal.log("%s_PLACE|run=%s|%s|T=%s|residual=%s" % (MARK, run, args["scene"]["placement"], plan["T"],
                                                           plan["placement"]["residual"]))
    unreal.log("%s_ROW|run=%s|section=%s|end_s=%s|timeline=%s|extend_mode=%s"
               % (MARK, run, plan.get("section"), plan.get("planned_end_s"), plan.get("timeline"),
                  json.dumps(plan.get("extend_mode"), ensure_ascii=False)))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|report=%s"
               % (MARK, run, int(not refusals), len(refusals), len(warnings), out))


# ---- APPLY helpers -----------------------------------------------------------------------------------------------

def _apply_channel(ch, want, run, label):
    """Make channel `ch` hold exactly want["keys"] (ticks) + default. Existing keys at wanted times are edited; missing
    times are ADDED (linear union); keys at unwanted times refuse (never deleted)."""
    have = {r["t"]: k for r, k in zip(_key_rows(ch), list(ch.get_keys()))}
    wt = [w["t"] for w in want["keys"]]
    extra = sorted(set(have) - set(wt))
    if extra:
        _stop(run, "REKEY_UNWANTED_KEYS|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, extra[:4]))
    for w in want["keys"]:
        k = have.get(w["t"])
        if k is None:
            if ch.add_key(unreal.FrameNumber(int(w["t"])), float(w["v"]), time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
                          interpolation=unreal.MovieSceneKeyInterpolation.LINEAR) is None:
                _stop(run, "ADD_KEY_NONE|%s|%d|NOTHING SAVED; Don't-Save restart" % (label, w["t"]))
            continue
        if w["tmode"] in (USER, BREAK) and _enum_name(k.get_tangent_mode()) != w["tmode"]:
            k.set_tangent_mode(getattr(unreal.RichCurveTangentMode, w["tmode"]))   # freeze before any value moves
    have = {r["t"]: k for r, k in zip(_key_rows(ch), list(ch.get_keys()))}
    for w in want["keys"]:
        k = have[w["t"]]
        k.set_value(float(w["v"]))
        if w["tmode"] in (USER, BREAK):
            k.set_arrive_tangent(float(w["arrive"]))
            k.set_leave_tangent(float(w["leave"]))
    if want["default"] is not None:
        ch.set_default(float(want["default"]))
    got = {r["t"]: r for r in _key_rows(ch)}
    for w in want["keys"]:
        g = got.get(w["t"])
        if g is None or abs(g["v"] - w["v"]) > 1e-3 * max(1.0, abs(w["v"])):
            _stop(run, "REKEY_READBACK|%s|t=%s|NOTHING SAVED; Don't-Save restart" % (label, w["t"]))
    if want["default"] is not None and abs(float(ch.get_default()) - float(want["default"])) > 1e-3 * max(1.0, abs(want["default"])):
        _stop(run, "DEFAULT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % label)


def _rekey_binding(b, t, run):
    secs = [s for tr in b.get_tracks() if isinstance(tr, unreal.MovieScene3DTransformTrack) for s in tr.get_sections()]
    if len(secs) != 1:
        _stop(run, "REKEY_SECTIONS|%s|%d|NOTHING SAVED; Don't-Save restart" % (b.get_display_name(), len(secs)))
    cm = _chan_map(secs[0])
    ch = {ax: _chan_rows(cm["Location." + ax.upper()]) for ax in "xyz"}
    ch["yaw"] = _chan_rows(cm["Rotation.Z"])
    want = rekey_rigid(ch, t)
    if want["problems"]:
        _stop(run, "REKEY_NOT_EXACT|%s|%s|NOTHING SAVED; Don't-Save restart" % (b.get_display_name(), want["problems"]))
    for ax in "xyz":
        _apply_channel(cm["Location." + ax.upper()], want[ax], run, "%s Location.%s" % (b.get_display_name(), ax.upper()))
    if abs(t["yaw"]) > 1e-9:
        _apply_channel(cm["Rotation.Z"], want["yaw"], run, "%s Rotation.Z" % b.get_display_name())
    return {"binding": str(b.get_display_name()), "method": want["method"],
            "keys": {ax: len(want[ax]["keys"]) for ax in ("x", "y", "z", "yaw")}}


def _const_transform(b, pose, rng, run, label):
    """A one-section transform track over rng holding a constant pose as DEFAULTS (no keys)."""
    tr = b.add_track(unreal.MovieScene3DTransformTrack)
    if tr is None:
        _stop(run, "ADD_TRANSFORM_TRACK|%s|NOTHING SAVED; Don't-Save restart" % label)
    s = tr.add_section()
    s.set_range(int(rng[0]), int(rng[1]))                            # explicit, as curtain_sleight.py:1785 [prec]
    cm = _chan_map(s)
    vals = {"Location.X": pose["loc"][0], "Location.Y": pose["loc"][1], "Location.Z": pose["loc"][2],
            "Rotation.X": pose["rot"][0], "Rotation.Y": pose["rot"][1], "Rotation.Z": pose["rot"][2]}
    sc = pose.get("scale") or [1.0, 1.0, 1.0]
    vals.update({"Scale.X": sc[0], "Scale.Y": sc[1], "Scale.Z": sc[2]})   # unkeyed scale would evaluate 0 [prec curtain_sleight.py:1791]
    for n, v in vals.items():
        if n not in cm:
            _stop(run, "CHANNEL_MISSING|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, n))
        cm[n].set_default(float(v))
        if abs(float(cm[n].get_default()) - float(v)) > 1e-3 * max(1.0, abs(v)):
            _stop(run, "CONST_POSE_READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, n))
    return s


def _spawn_track(b, rng, default_on, keys=()):    # prec curtain_sleight.py:1819-1835 (reuse UE's auto spawn track)
    existing = [t for t in b.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    st = existing[0] if existing else b.add_track(unreal.MovieSceneSpawnTrack)
    for extra in existing[1:]:
        b.remove_track(extra)
    for old in list(st.get_sections()):
        st.remove_section(old)
    ss = st.add_section()
    ss.set_range(int(rng[0]), int(rng[1]))
    ch = ss.get_all_channels()[0]
    ch.set_default(bool(default_on))
    for frame, value in keys:
        ch.add_key(unreal.FrameNumber(int(frame)), bool(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return ss


def _template_props(tmpl, name, off, run):
    """Measured per-instance settings of her level actors onto the spawnable template (the rest = class defaults)."""
    cam = (off.get("camera_template") or {}).get(name)
    if cam is not None and hasattr(tmpl, "get_cine_camera_component"):
        # on a spawnable template get_cine_camera_component() returns None (measured 7 Oct, run
        # KLARAVOIDS6-20261007-012328); the component is the 'camera_component' property (prec s3_beats_apply.py:310-319)
        comp = tmpl.get_cine_camera_component() or tmpl.get_editor_property("camera_component")
        if comp is None:
            _stop(run, "TEMPLATE_CAMERA_COMPONENT|%s|NOTHING SAVED; Don't-Save restart" % name)
        if cam.get("focus_method") == "DISABLE":
            fs = comp.get_editor_property("focus_settings")
            fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
            comp.set_editor_property("focus_settings", fs)
        pp = comp.get_editor_property("post_process_settings")
        for key, prop in (("color_saturation", "color_saturation"), ("color_saturation_shadows", "color_saturation_shadows")):
            if key in cam:
                pp.set_editor_property("override_" + prop, True)
                pp.set_editor_property(prop, unreal.Vector4(*cam[key]))
        comp.set_editor_property("post_process_settings", pp)
    if name == "NS_BeeSwarm":
        ns = unreal.load_asset(off.get("swarm_system", "/Game/FX/NS_BeeSwarm"))
        nc = tmpl.get_editor_property("niagara_component")
        if ns is None or nc is None:
            _stop(run, "SWARM_TEMPLATE|ns=%s|comp=%s|NOTHING SAVED; Don't-Save restart" % (ns, nc))
        nc.set_asset(ns)
        if _path(nc.get_asset()) != "/Game/FX/NS_BeeSwarm":
            _stop(run, "SWARM_TEMPLATE_READBACK|NOTHING SAVED; Don't-Save restart")


def _set_piece(seq, item, rng, run):
    cls = unreal.load_class(None, item["class"])
    b = seq.add_spawnable_from_class(cls) if cls is not None else None
    if b is None or not b.is_valid():
        _stop(run, "SET_PIECE_SPAWNABLE|%s|NOTHING SAVED; Don't-Save restart" % item["label"])
    b.set_display_name(SET_PREFIX + item["label"])
    tmpl = b.get_object_template()
    if item["kind"] == "spots":
        lc = tmpl.get_editor_property("spot_light_component")
        lc.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        lc.set_editor_property("intensity", float(item["intensity"]))
        lc.set_editor_property("light_color", unreal.Color(*[int(c) for c in item["color"]]))
        if abs(float(lc.get_editor_property("intensity")) - float(item["intensity"])) > 1e-3:
            _stop(run, "SPOT_TEMPLATE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % item["label"])
    elif item["kind"] == "floor":
        sm = tmpl.get_editor_property("static_mesh_component")
        mesh = unreal.load_asset(item["mesh"])
        mats = [unreal.load_asset(p) for p in item["override_materials"]]
        if mesh is None or any(m is None for m in mats):
            _stop(run, "FLOOR_ASSETS|NOTHING SAVED; Don't-Save restart")
        sm.set_editor_property("static_mesh", mesh)
        sm.set_editor_property("override_materials", mats)
        sm.set_editor_property("cast_shadow", bool(item.get("cast_shadow", True)))
        if sm.get_editor_property("static_mesh") is None:
            _stop(run, "FLOOR_TEMPLATE_READBACK|NOTHING SAVED; Don't-Save restart")
    _spawn_track(b, rng, True)
    _const_transform(b, item["world"], rng, run, item["label"])
    return b


def _add_vis(seq, actor, prefix, frames):           # klara_hookin.py:1143-1159 [prec, live 7 Oct]
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
        bt = b.add_track(unreal.MovieSceneBoolTrack)
        bt.set_property_name_and_path(unreal.Name("bEnabled"), "bEnabled")
        bs = bt.add_section()
        bs.set_range(int(frames[0]), int(frames[1]))
        bs.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        list(bs.get_all_channels())[0].set_default(False)
    return b


def _zero_light(seq, actor, parent, frames, run):   # prec curtain_sleight.py:1918-1928 _bind_light (+ _key_float)
    lc = actor.get_component_by_class(unreal.LightComponent)
    if lc is None:
        return None
    kb = seq.add_possessable(lc)
    if kb is None or not kb.is_valid():
        _stop(run, "BIND_LIGHT_COMPONENT|%s|NOTHING SAVED; Don't-Save restart" % actor.get_actor_label())
    kb.set_parent(parent)
    kb.set_display_name(PFX_HLIGHT + str(actor.get_actor_label()))
    tr = kb.add_track(unreal.MovieSceneFloatTrack)
    tr.set_property_name_and_path(unreal.Name("Intensity"), "Intensity")
    s = tr.add_section()
    s.set_range(int(frames[0]), int(frames[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    ch = list(s.get_all_channels())
    ch[0].set_default(0.0)
    if abs(float(ch[0].get_default())) > 1e-4:                     # float32 channel: tolerant read-back
        _stop(run, "ZERO_LIGHT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % actor.get_actor_label())
    return kb


def _shots_section(seq, row):
    paths = (row["current_nested"], row["her_sequence"], row["copy_path"])
    hits = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneCinematicShotTrack)
            for s in t.get_sections() if _path(s.get_sequence()) in paths]
    if len(hits) != 1:
        raise PlanError("SHOT_SECTION_COUNT: %d" % len(hits))
    return hits[0]


def _live_state(seq, row, rise_mark):
    sec = _shots_section(seq, row)
    out = {"shot": {"sequence": _path(sec.get_sequence()), "start": int(sec.get_start_frame()),
                    "end": int(sec.get_end_frame()), "active": bool(sec.is_active()),
                    "start_offset": int(sec.get_editor_property("parameters").get_editor_property("start_frame_offset").value)},
           "score": sorted([str(t.get_display_name()), int(s.get_start_frame()), int(s.get_end_frame()), _path(s.get_sound()),
                            bool(s.is_active())]
                           for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneAudioTrack) for s in t.get_sections()
                           if _path(s.get_sound()) in row["mute_sounds"]),
           "rise": sorted([str(t.get_display_name()), int(s.get_start_frame()), int(s.get_end_frame()), bool(s.is_active())]
                          for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack)
                          and t.get_class().get_name() != CHOREO_TRACK_CLASS
                          for s in t.get_sections() if s.get_sequence() is not None and rise_mark in _path(s.get_sequence())),
           "ours": sorted(str(b.get_display_name()) for b in seq.get_bindings() if is_ours(b.get_display_name()))}
    return out


def _rebuild_copy(copy, args, plan, run):
    """Every top-level possessable -> a spawnable of the same class (tracks + children moved), re-keyed by T."""
    off = args["her_offline_facts"]
    t = plan["T"]
    log = []
    top = [b for b in copy.get_possessables() if not (b.get_parent() is not None and b.get_parent().is_valid())]
    old_ids = {}
    for p in top:
        name = str(p.get_display_name())
        r = [x for x in plan["rebuild"] if x["name"] == name]
        if len(r) != 1:
            _stop(run, "REBUILD_ROW|%s|NOTHING SAVED; Don't-Save restart" % name)
        cls = unreal.load_class(None, r[0]["class_path"])
        s = copy.add_spawnable_from_class(cls) if cls is not None else None
        if s is None or not s.is_valid():
            _stop(run, "SPAWNABLE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % name)
        kids = [k for k in copy.get_bindings() if k.get_parent() is not None and k.get_parent().is_valid()
                and _gs(k.get_parent().get_id()) == _gs(p.get_id())]
        _template_props(s.get_object_template(), name, off, run)
        unreal.MovieSceneBindingExtensions.move_binding_contents(p, s)          # decl MovieSceneBindingExtensions.h:208
        for k in kids:
            if not (k.get_parent() is not None and k.get_parent().is_valid() and _gs(k.get_parent().get_id()) == _gs(s.get_id())):
                k.set_parent(s)                                                   # decl :199
            if _gs(k.get_parent().get_id()) != _gs(s.get_id()):
                _stop(run, "CHILD_REPARENT|%s/%s|NOTHING SAVED; Don't-Save restart" % (name, k.get_display_name()))
        if [x for x in p.get_tracks()]:
            _stop(run, "MOVE_LEFT_TRACKS|%s|NOTHING SAVED; Don't-Save restart" % name)
        old_ids[_gs(p.get_id())] = s
        s.set_display_name(name)
        log.append({"binding": name, "new_id": _gs(s.get_id()), "children": [str(k.get_display_name()) for k in kids]})
    # cut sections: old guid -> new spawnable
    for tr in copy.get_tracks():
        if isinstance(tr, unreal.MovieSceneCameraCutTrack):
            for c in tr.get_sections():
                g = _gs(c.get_camera_binding_id().get_editor_property("guid"))
                if g not in old_ids:
                    _stop(run, "CUT_BINDING_UNKNOWN|%s|NOTHING SAVED; Don't-Save restart" % g)
                c.set_camera_binding_id(copy.get_binding_id(old_ids[g]))
                if _gs(c.get_camera_binding_id().get_editor_property("guid")) != _gs(old_ids[g].get_id()):
                    _stop(run, "CUT_REPOINT_READBACK|NOTHING SAVED; Don't-Save restart")
    top_ids = set(_gs(p.get_id()) for p in top)
    for p in top:
        p.remove()                                                                # prec klara_hookin.py:1282
    # measured 7 Oct (probe_possessable_remove.py on the stopped copy): after remove(), get_possessables() still lists the
    # removed guids as is_valid()==False proxies with no name/tracks, while get_bindings() no longer has them -> skip invalid
    ghosts = [_gs(b.get_id()) for b in copy.get_possessables() if not b.is_valid()]
    live_ids = set(_gs(b.get_id()) for b in copy.get_bindings())
    if [g for g in top_ids if g in live_ids]:
        _stop(run, "TOP_BINDINGS_STILL_LIVE|NOTHING SAVED; Don't-Save restart")
    unreal.log("%s_GHOST_PROXIES|run=%s|n=%d|all_removed_top=%s" % (MARK, run, len(ghosts), set(ghosts) <= top_ids))
    left = []
    for b in [b for b in copy.get_possessables() if b.is_valid()]:
        par = b.get_parent()
        if not (par is not None and par.is_valid()):
            left.append({"name": str(b.get_display_name()), "guid": _gs(b.get_id()), "was_top": _gs(b.get_id()) in top_ids,
                         "parent": None if par is None else _gs(par.get_id())})
    if left:
        _stop(run, "TOP_POSSESSABLES_LEFT|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(left))
    n_kids = len([p for p in plan["rebuild"] for _k2 in p["children"]])
    n_live = len([b for b in copy.get_possessables() if b.is_valid()])      # ghost proxies skipped (see above)
    if n_live != n_kids:
        _stop(run, "CHILD_COUNT|%d want %d|NOTHING SAVED; Don't-Save restart" % (n_live, n_kids))
    # spawn throughout her range; re-key or pin a pose
    rng = [int(copy.get_playback_start()), int(copy.get_playback_end())]
    for s in copy.get_spawnables():
        name = str(s.get_display_name())
        if name.startswith(SET_PREFIX):
            continue
        _spawn_track(s, rng, True)
        has_tr = [x for x in s.get_tracks() if isinstance(x, unreal.MovieScene3DTransformTrack)]
        if has_tr:
            log.append(_rekey_binding(s, t, run))
        elif name == "BP_MHC_Elder_Female":
            _const_transform(s, plan["woman_world"], rng, run, name)
            log.append({"binding": name, "pinned": plan["woman_world"]})
        else:
            _stop(run, "UNPLACED_SPAWNABLE|%s|NOTHING SAVED; Don't-Save restart" % name)
    for item in plan["set_pieces"]:
        _set_piece(copy, item, rng, run)
        log.append({"set_piece": item["label"], "world": item["world"]})
    return log


def _glimmer(seq, plan, args, run):
    g = plan["glimmer"]
    b = seq.add_spawnable_from_class(unreal.NiagaraActor)
    if b is None or not b.is_valid():
        _stop(run, "GLIMMER_SPAWNABLE|NOTHING SAVED; Don't-Save restart")
    b.set_display_name(GLIMMER_NAME)
    nc = b.get_object_template().get_editor_property("niagara_component")
    ns = unreal.load_asset(g["system"])
    if nc is None or ns is None:
        _stop(run, "GLIMMER_TEMPLATE|NOTHING SAVED; Don't-Save restart")
    nc.set_asset(ns)
    end = plan["planned_end"]
    _spawn_track(b, [0, end], False, [(g["spawn"][0], True), (g["spawn"][1], False)])
    s = _const_transform(b, g["pose"], [0, end], run, GLIMMER_NAME)
    if g["scale_from"] != 1.0:
        cm = _chan_map(s)
        for i, n in enumerate(("Scale.X", "Scale.Y", "Scale.Z")):
            full = float(g["pose"]["scale"][i])
            for f, v in ((g["spawn"][0], full * g["scale_from"]), (plan["section"][0], full)):
                if cm[n].add_key(unreal.FrameNumber(int(f)), v, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                 interpolation=unreal.MovieSceneKeyInterpolation.LINEAR) is None:
                    _stop(run, "GLIMMER_SCALE_KEY|NOTHING SAVED; Don't-Save restart")
    return b


def run_apply(args, run, world):
    row = args["scene"]
    facts, seq = _facts(args)
    plan = plan_void(facts, args)
    if plan["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(plan["refusals"]))
    rise_mark = row.get("rise_mark", "HangarRise")
    rpath = os.path.join(_here(), RECORD_NAME)
    backup = _backup(run, [_file(row["scene_sequence"], ".uasset")])
    rec = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY", "backup": backup, "applied": False,
           "decided_by": args.get("decided_by"), "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "row": row, "rise_mark": rise_mark, "playback_before": facts["scene"]["playback"], "plan": plan,
           "copy": None, "before": _live_state(seq, row, rise_mark)}
    if rec["before"]["ours"]:
        _stop(run, "OUR_BINDINGS_ALREADY_PRESENT|%s" % rec["before"]["ours"][:4])
    write_record_exclusive(rpath, rec)
    # 1. the copy
    copy = unreal.EditorAssetLibrary.duplicate_asset(row["her_sequence"], row["copy_path"])   # prec klara_hookin.py:1076
    if copy is None:
        _stop(run, "DUPLICATE_FAILED|%s" % row["copy_path"])
    rec["copy"] = row["copy_path"]
    update_record(rpath, rec)
    rec["rebuild_log"] = _rebuild_copy(copy, args, plan, run)
    # 2. the scene
    sec = _shots_section(seq, row)
    sec.set_sequence(copy)
    sec.set_range(int(plan["section"][0]), int(plan["section"][1]))
    p = sec.get_editor_property("parameters")
    p.set_editor_property("start_frame_offset", unreal.FrameNumber(0))
    sec.set_editor_property("parameters", p)
    for tr in seq.get_tracks():
        if isinstance(tr, unreal.MovieSceneAudioTrack):
            for s in tr.get_sections():
                if _path(s.get_sound()) in row["mute_sounds"]:
                    s.set_is_active(False)                       # deactivate, never delete
        elif isinstance(tr, unreal.MovieSceneSubTrack) and tr.get_class().get_name() != CHOREO_TRACK_CLASS \
                and args["hangar"].get("mute_rise", True):
            for s in tr.get_sections():
                if s.get_sequence() is not None and rise_mark in _path(s.get_sequence()):
                    s.set_is_active(False)                       # the rise + strikes, deactivated, never deleted
    tl = plan["timeline"]
    hidden, zeroed = [], []
    if tl.get("hangar_off"):
        for a in _hangar_actors(args["hangar"]["tag"]):
            vb = _add_vis(seq, a, PFX_HANGAR, tl["hangar_off"])
            hidden.append(str(a.get_actor_label()))
            if tl.get("hangar_lights_zero") and _zero_light(seq, a, vb, tl["hangar_lights_zero"], run) is not None:
                zeroed.append(str(a.get_actor_label()))
    ours = []
    if tl.get("ours_off"):
        for a in _ours(_rig()):
            _add_vis(seq, a, PFX_OURS, tl["ours_off"])
            ours.append(str(a.get_actor_label()))
    if plan.get("glimmer"):
        _glimmer(seq, plan, args, run)
    # 3. read back, census, save
    after = _live_state(seq, row, rise_mark)
    bad = []
    if after["shot"] != {"sequence": row["copy_path"], "start": plan["section"][0], "end": plan["section"][1],
                         "active": True, "start_offset": 0}:
        bad.append("shot %s" % after["shot"])
    if not after["score"] or any(m[4] for m in after["score"]):
        bad.append("score still active %s" % after["score"])
    if args["hangar"].get("mute_rise", True) and (len(after["rise"]) != 1 or after["rise"][0][3]):
        bad.append("rise %s" % after["rise"])
    want_n = len(hidden) + len(zeroed) + len(ours) + (1 if plan.get("glimmer") else 0)
    if len(after["ours"]) != want_n:
        bad.append("our bindings %d want %d" % (len(after["ours"]), want_n))
    if bad:
        _stop(run, "APPLY_READBACK|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (bad, backup))
    gate = census_gate(_census(), [row["scene_sequence"], row["copy_path"]], [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    for pth in (row["copy_path"], row["scene_sequence"]):
        if not unreal.EditorAssetLibrary.save_asset(pth, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % pth)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    if _live_state(unreal.load_asset(row["scene_sequence"]), row, rise_mark) != after:
        _stop(run, "POST_SAVE_READBACK")
    c2 = unreal.load_asset(row["copy_path"])
    if [b for b in c2.get_possessables() if b.is_valid() and not (b.get_parent() is not None and b.get_parent().is_valid())]:
        _stop(run, "POST_SAVE_COPY_HAS_TOP_POSSESSABLES")
    rec.update(applied=True, after=after, hangar_hidden=hidden, hangar_zeroed=zeroed, ours_hidden=ours)
    update_record(rpath, rec)
    unreal.log("%s_EXTEND_NEXT|run=%s|extend_scene_playback_mode=%s"
               % (MARK, run, json.dumps(plan["extend_mode"], ensure_ascii=False)))
    unreal.log("%s_APPLY_OK|run=%s|copy=%s|section=%s|end=%d|hidden=%d|zeroed=%d|ours=%d|glimmer=%s|backup=%s|record=%s"
               % (MARK, run, row["copy_path"], plan["section"], plan["planned_end"], len(hidden), len(zeroed), len(ours),
                  (plan.get("glimmer") or {}).get("spawn"), backup, rpath))


def run_revert(args, run, world):
    rpath = os.path.join(_here(), RECORD_NAME)
    rec = load_record(rpath)
    row, rise_mark = rec["row"], rec["rise_mark"]
    seq = unreal.load_asset(row["scene_sequence"])
    live = _live_state(seq, row, rise_mark)
    if live != rec["after"]:
        _stop(run, "STATE_DRIFTED|live %s|nothing changed" % json.dumps(live, default=str)[:600])
    b = rec["before"]
    sec = _shots_section(seq, row)
    sec.set_sequence(unreal.load_asset(b["shot"]["sequence"]))
    sec.set_range(b["shot"]["start"], b["shot"]["end"])
    p = sec.get_editor_property("parameters")
    p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(b["shot"]["start_offset"])))
    sec.set_editor_property("parameters", p)
    was = {tuple(m[:4]): m[4] for m in b["score"]}
    was_r = {tuple(m[:3]): m[3] for m in b["rise"]}
    for tr in seq.get_tracks():
        if isinstance(tr, unreal.MovieSceneAudioTrack):
            for s in tr.get_sections():
                key = (str(tr.get_display_name()), int(s.get_start_frame()), int(s.get_end_frame()), _path(s.get_sound()))
                if key in was:
                    s.set_is_active(bool(was[key]))
        elif isinstance(tr, unreal.MovieSceneSubTrack) and tr.get_class().get_name() != CHOREO_TRACK_CLASS:
            for s in tr.get_sections():
                key = (str(tr.get_display_name()), int(s.get_start_frame()), int(s.get_end_frame()))
                if key in was_r:
                    s.set_is_active(bool(was_r[key]))
    mine = [x for x in seq.get_bindings() if is_ours(x.get_display_name())]
    kids = [x for x in mine if x.get_parent() is not None and x.get_parent().is_valid()]
    for bnd in kids + [x for x in mine if x not in kids]:                       # children first, then their actors
        if bnd.is_valid():
            bnd.remove()                                                         # prec klara_hookin.py:1282
    if _live_state(seq, row, rise_mark) != b:
        _stop(run, "REVERT_READBACK|NOTHING SAVED; Don't-Save restart")
    gate = census_gate(_census(), [row["scene_sequence"]], [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    if not unreal.EditorAssetLibrary.save_asset(row["scene_sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s" % row["scene_sequence"])
    deleted = []
    c = rec.get("copy")
    if c and unreal.EditorAssetLibrary.does_asset_exist(c):
        refs = [str(x) for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(c, False)]
        if refs:
            unreal.log_warning("%s_COPY_KEPT|run=%s|%s|referenced by %s" % (MARK, run, c, refs))
        elif unreal.EditorAssetLibrary.delete_asset(c) and not unreal.EditorAssetLibrary.does_asset_exist(c):
            deleted.append(c)
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("%s_EXTEND_NEXT|run=%s|restore: extend_scene_playback new_end_frame=%d"
               % (MARK, run, rec["playback_before"][1]))
    unreal.log("%s_REVERT_OK|run=%s|copies_deleted=%s" % (MARK, run, deleted))


def main():
    args = globals().get("KLARAVOIDS6_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAVOIDS6-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = editor.get_game_world() is not None
    world = None if pie else editor.get_editor_world()
    wname = str(world.get_outermost().get_name()) if world is not None else None
    rpath = os.path.join(_here(), RECORD_NAME)
    row = args["scene"]
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie,
             "wrong_world": None if wname == EXPECTED_WORLD else str(wname),
             "sequencer_open": None if pie else _sequencer_open(), "census": _census(),
             "decided_by": args.get("decided_by"), "record_exists": rpath if os.path.exists(rpath) else None,
             "record_applied": os.path.exists(rpath) and bool(load_record(rpath).get("applied")),
             "copy_exists": row["copy_path"] if unreal.EditorAssetLibrary.does_asset_exist(row["copy_path"]) else None}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None:
    main()
