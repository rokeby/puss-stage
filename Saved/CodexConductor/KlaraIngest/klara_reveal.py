"""KLARA REVEAL (7 Oct): intro | her cinematic slot (video later) | outro, around her diorama in our hangar.
Offline-written, NEVER RUN IN UNREAL. Plan and evidence: REVEAL_PLAN.md (same folder). Harness:
test_klara_reveal_offline.py (system Python, pure maths only).

Gary 7 Oct (via the conductor; his words condensed):
  - do not rescale her elements; reposition/resize the HANGAR around her diorama, the diorama right in front of the
    camera as it leaves the passage; floor in total darkness; ceiling-rig lights keep their glow, nothing on the floor;
  - her lights strike one by one (blink, "always there, only now struck"); CROSSFADE, no hard switch of lighting worlds;
  - Plan A: her cinematic plays as a VIDEO in a Sequencer Media track (videos not rendered yet; renders identical to
    her LS, so for now her in-engine cinematic - the hookin's re-keyed copy - fills the slot 1:1);
  - intro ends on her FIRST cinematic frame (pose + lens), outro starts on her LAST cinematic frame;
  - S1 and S4 (S2 untouched).

Tiers per claim: [decl] header/source we read (file:line), [prec] in-repo precedent call (cited), [meas] a record or
bytes read, [inf] inferred (why stated). Every [inf] API is probed by DRY into report["api_table"].

SCENE TIMELINE (Scene display frames; L = hangar land, C = the hookin's cut, E = C + her length)
  [0, L)        hangar rises; non-ceiling hangar lights BLACK (LightColor track) from frame 0; ceiling glows untouched
  [L, D0)       dark hold (her level visible since L via the hookin's Level Visibility track; her lights at 0)
  [D0, C)       her local lights strike one by one (Intensity, constant-interpolation flicker, seeded per light)
  [G0, C)       glide camera: Entry Handoff pose -> her first camera pose + lens (cubic Hermite, velocity-matched)
                her sun / sky light / fog / PPV weight ramp 0 -> her value-at-her-start (crossfade); roof hidden from G0;
                OUR celestial hidden from G0 (hookin "Ours Off" start moved C -> G0); hookin "Hers Dark" end C -> G0
  [C, E)        her cinematic SLOT: the hookin's nested copy now, a Media track section later (same range)
  [E, X)        outro: glide camera ON her last cinematic pose; her lights blink out in reverse order; env fades to 0;
                roof shown again when her env is out; then glide to the Exit Handoff pose
  [X, end)      the existing Exit Handoff cut (end = E + outro; relength FIRST with extend_scene_playback.py)
Every section is in LS_DevScene_0N, RESTORE_STATE; nothing in the rise sequence, the Show or the Master is edited.

PLACEMENT: her streamed level is moved by a translation DELTA so her first camera sits `lead_cm` ahead of the Entry
  Handoff camera on the dock axis; the re-keyed copy is shifted by the same delta (translation-only, exact). The level
  move is remove + re-add with the new LevelTransform (EditorLevelUtils.h:260-261, 276-277 [decl]; the engine's
  FLevelUtils::SetEditorTransform, LevelUtils.h:181, is C++-only [decl]). The hangar box is NOT rebuilt here: DRY
  emits snug HANGAR_PARAMS for Structure's hangar_build.py and checks the set against the LIVE box.

v3 (Gary 7 Oct: "Strike to her lit look; skip her dark opening"; REVEAL_PLAN.md section 9): her LS keys every local
  light at 0 on its first frame and fades them up later, so v2's strikes went to 0. v3 finds her LIT FRAME Lh in her
  copy (find_lit_frame: earliest frame by which >= 80% of her ever-lit lights hold >= 90% of their sustained plateau,
  snapped up to a frame that lands on our grid), strikes each light to its value AT Lh, crossfades the env to its
  values at Lh, glides to HER CAMERA AT Lh, and starts the slot INTO her copy at Lh (sub-section start_frame_offset),
  so her dark opening [her start, Lh) never plays and the Scene shortens by that much. Outro unchanged.
  Also fixed: add_possessable on an actor the hookin already binds returns THAT binding [meas: both live records
  lack the four env "Hers Dark" names in hookin_after]; v1/v2 renamed it, so APPLY missed those Hers Dark windows and
  REVERT deleted them (REVERT_READBACK). _possess never renames a shared binding; REVERT renames legacy ones back.

Modes (klara_reveal_run.py <- klara_reveal_args.json; confirm "<MODE> KLARAREVEAL"; one Scene per run):
  DRY    read-only -> klara_reveal_dry_S<n>.json; KLARAREVEAL_DRY_OK|run=..|scene=..|apply_ready=..
  APPLY  gates -> backups -> exclusive record -> level move + copy shift -> glide camera -> Scene tracks -> cut split
         -> census -> save map + LS_DevScene_0N + copy -> read back -> KLARAREVEAL_APPLY_OK
  REVERT drift check -> undo in reverse -> save -> KLARAREVEAL_REVERT_OK. Run BEFORE klara_hookin REVERT_SEQ.
Never: Save All, reload a level, open/scrub Sequencer, edit Show/Master, end PIE; no unreal objects in module globals.
Importing without `unreal` runs nothing.
"""
import datetime
import hashlib
import json
import math
import os
import random
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "klara_reveal"
CONFIRM_WORD = "KLARAREVEAL"
HER_LEVELS = ("/Game/KK_S1_Animals/L_Animals", "/Game/L_KK_children", "/Game/Japanese_Alley/Maps/Japanese_Alley")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                   # extend_scene_playback.py:44
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ARGS_NAME = "klara_reveal_args.json"
MODES = ("DRY", "APPLY", "REVERT")
PREFIX = "Klara Reveal - "                      # every binding/track this tool adds carries it
HOOK_OURS = "Klara Hookin - Ours Off: "         # klara_hookin.py:73
HOOK_HERS = "Klara Hookin - Hers Dark: "        # klara_hookin.py:74
HOOK_VIS = "Klara Levels (hookin)"             # klara_hookin.py:72
LOCAL_LIGHT_CLASSES = ("PointLight", "SpotLight", "RectLight")
ENV_INTENSITY = {"DirectionalLight": "Intensity", "SkyLight": "Intensity", "ExponentialHeightFog": "FogDensity"}
CEILING_PREFIX = "S%s Lattice Glow "            # hangar_build.py:140 (glows ride the bulbs on the Lattice Fly)
HANGAR_TAG = "RigAtmos.Scene%sHangar"           # hangar_build.py:179, 365
ROOF_LABELS = ("S%s Hangar Roof",)              # hangar_build.py:118
BULB_PREFIX = "S%s Lattice Bulb "               # hangar_build.py:137-138 (emissive work bulbs on the Lattice Fly)
LATTICE_PREFIX = "S%s Hangar Lattice "          # hangar_build.py:120-129 (Fly, Beams, Rails)
LATTICE_FLY = "S%s Hangar Lattice Fly"          # hangar_build.py:120; lowered by LS_S<n>_HangarRise Location.Z (:501)
RISE_MARK = "HangarRise"                        # klara_hookin.py:674 [prec]
LATTICE_MODES = ("cancel", "hide", "allow")
WALL_LABELS = {"left_wall": "S%s Hangar Left Wall", "right_wall": "S%s Hangar Right Wall",
               "far_wall": "S%s Hangar Far Wall"}   # hangar_build.py:110, 113
EPS = 1.0e-9
# v3 lit-frame detection (REVEAL_PLAN.md section 9). All proposed numbers, not Gary's; args "lit" overrides any field.
# frame: an explicit her display frame (overrides detection); enabled False = v2 behaviour (her first frame).
LIT_DEFAULTS = {"enabled": True, "light_fraction": 0.8, "value_fraction": 0.9, "hold_s": 1.0, "search_s": 60.0,
                "min_value": 1.0e-3, "sum_fraction": 0.75, "disagree_warn_s": 2.0, "frame": None}


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: small maths
# =====================================================================================================================

def wrap(deg):
    """-> (-180, 180]."""
    d = math.fmod(float(deg), 360.0)
    if d <= -180.0:
        d += 360.0
    elif d > 180.0:
        d -= 360.0
    return d


def rot2(x, y, yaw_deg):
    a = math.radians(yaw_deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def to_local(dock, p):
    x, y = rot2(p[0] - dock["loc"][0], p[1] - dock["loc"][1], -dock["yaw"])
    return [x, y, p[2] - dock["loc"][2]]


def from_local(dock, p):
    x, y = rot2(p[0], p[1], dock["yaw"])
    return [x + dock["loc"][0], y + dock["loc"][1], p[2] + dock["loc"][2]]


def smoothstep(s):
    s = min(1.0, max(0.0, s))
    return s * s * (3.0 - 2.0 * s)


def hermite(p0, p1, v0, v1, dur, s):
    """Cubic Hermite position at s in [0, 1]; v0/v1 in units per SECOND, dur in seconds. s=0 -> p0, s=1 -> p1 exactly."""
    s2, s3 = s * s, s * s * s
    h00, h10, h01, h11 = 2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2
    return h00 * p0 + h10 * dur * v0 + h01 * p1 + h11 * dur * v1


def hermite_vel(p0, p1, v0, v1, dur, s):
    s2 = s * s
    d00, d10, d01, d11 = 6 * s2 - 6 * s, 3 * s2 - 4 * s + 1, -6 * s2 + 6 * s, 3 * s2 - 2 * s
    return (d00 * p0 + d10 * dur * v0 + d01 * p1 + d11 * dur * v1) / dur


def equiv_focal(focal_mm, sensor_from_mm, sensor_to_mm):
    """Focal on a sensor of width `sensor_to` giving the same HORIZONTAL FOV as `focal` on `sensor_from`."""
    return float(focal_mm) * float(sensor_to_mm) / float(sensor_from_mm)


def hfov_deg(focal_mm, sensor_w_mm):
    return math.degrees(2.0 * math.atan(float(sensor_w_mm) / (2.0 * float(focal_mm))))


# =====================================================================================================================
# Pure: camera glide
# =====================================================================================================================

def plan_glide(start, end, f0, f1, fps, v0=None, v1=None, w0=None, w1=None, lens_v1=None):
    """Per-frame keys from frame f0 (pose `start`) to frame f1 (pose `end`), both inclusive.
    pose = {"loc": [x,y,z] cm, "rot": [roll,pitch,yaw] deg, "focal": mm, "focus": cm}; v = cm/s, w = deg/s (per axis).
    Rotation is unwrapped to the shortest arc per axis. Lens eases (zero end velocities unless lens_v1 given).
    Returns {"keys": [[frame, x,y,z, roll,pitch,yaw, focal, focus]...], "report": {...}}."""
    if f1 <= f0:
        raise PlanError("GLIDE_EMPTY: [%r, %r]" % (f0, f1))
    dur = (f1 - f0) / float(fps)
    v0 = v0 or [0.0, 0.0, 0.0]
    v1 = v1 or [0.0, 0.0, 0.0]
    w0 = w0 or [0.0, 0.0, 0.0]
    w1 = w1 or [0.0, 0.0, 0.0]
    lens_v1 = lens_v1 or [0.0, 0.0]
    r0 = [float(a) for a in start["rot"]]
    r1 = [r0[i] + wrap(float(end["rot"][i]) - r0[i]) for i in range(3)]
    keys, speeds = [], []
    for fr in range(int(f0), int(f1) + 1):
        s = (fr - f0) / float(f1 - f0)
        loc = [hermite(start["loc"][i], end["loc"][i], v0[i], v1[i], dur, s) for i in range(3)]
        rot = [hermite(r0[i], r1[i], w0[i], w1[i], dur, s) for i in range(3)]
        focal = hermite(start["focal"], end["focal"], 0.0, lens_v1[0], dur, s)
        focus = hermite(start["focus"], end["focus"], 0.0, lens_v1[1], dur, s)
        keys.append([fr] + loc + rot + [focal, focus])
        speeds.append(math.sqrt(sum(hermite_vel(start["loc"][i], end["loc"][i], v0[i], v1[i], dur, s) ** 2
                                    for i in range(3))))
    # the end key carries the END pose bit-for-bit (her rotation as authored, not the unwrapped value)
    keys[-1] = [int(f1)] + [float(v) for v in end["loc"]] + [float(v) for v in end["rot"]] + \
        [float(end["focal"]), float(end["focus"])]
    keys[0] = [int(f0)] + [float(v) for v in start["loc"]] + [float(v) for v in start["rot"]] + \
        [float(start["focal"]), float(start["focus"])]
    over = []
    for i, axis in enumerate(("x", "y", "z")):
        lo, hi = min(start["loc"][i], end["loc"][i]), max(start["loc"][i], end["loc"][i])
        worst = max(max(0.0, lo - k[1 + i], k[1 + i] - hi) for k in keys)
        if worst > 1.0:
            over.append({"axis": axis, "overshoot_cm": worst})
    dist = math.sqrt(sum((end["loc"][i] - start["loc"][i]) ** 2 for i in range(3)))
    rep = {"frames": [int(f0), int(f1)], "seconds": dur, "distance_cm": dist, "peak_speed_cm_s": max(speeds),
           "start_speed_cm_s": speeds[0], "end_speed_cm_s": speeds[-1],
           "want_start_speed_cm_s": math.sqrt(sum(x * x for x in v0)),
           "want_end_speed_cm_s": math.sqrt(sum(x * x for x in v1)),
           "turn_deg": [r1[i] - r0[i] for i in range(3)], "overshoot": over}
    return {"keys": keys, "report": rep}


def hold_keys(pose, frames):
    return [[int(f)] + [float(v) for v in pose["loc"]] + [float(v) for v in pose["rot"]] +
            [float(pose["focal"]), float(pose["focus"])] for f in frames]


# =====================================================================================================================
# Pure: placement and hangar fit
# =====================================================================================================================

def solve_placement(her_cam, fp_world, top_cm, dock, box, lead_cm, x_min_local, side_margin_cm, top_clear_cm=100.0,
                    lead_max_cm=None):
    """Translate her level so her FIRST camera sits `lead` cm ahead of the dock camera on the dock axis (lateral 0
    unless her set would cross a side wall). Her floor stays on our floor (delta z = 0: the hookin set it [meas
    klara_hookin_stream_record.json level z 0]).
    her_cam: world [x,y,z] NOW; fp_world: [xmin,xmax,ymin,ymax] NOW (world, her set without env actors);
    box: {"apron","depth","half_w","height","lattice_z"} = the LIVE interior in dock-local coords.
    Returns delta (world), the lead actually used, the set in dock-local coords after, and checks."""
    if abs(wrap(dock["yaw"])) > 1e-6:
        corners = [[fp_world[a], fp_world[b], 0.0] for a in (0, 1) for b in (2, 3)]
    else:
        corners = [[fp_world[0], fp_world[2], 0.0], [fp_world[1], fp_world[3], 0.0]]
    cam_l = to_local(dock, her_cam)
    loc = [to_local(dock, c) for c in corners]
    rel_x = [p[0] - cam_l[0] for p in loc]
    rel_y = [p[1] - cam_l[1] for p in loc]
    need = float(x_min_local) - min(rel_x)            # lead that puts her near edge on x_min_local
    lead = max(float(lead_cm), need)
    lead_over = lead_max_cm is not None and lead > float(lead_max_cm) + EPS
    iy = float(box["half_w"]) - float(side_margin_cm)
    lateral = 0.0
    if max(rel_y) > iy or min(rel_y) < -iy:
        lateral = -(max(rel_y) + min(rel_y)) / 2.0    # centre the set between the walls (camera off-axis)
    target = from_local(dock, [lead, lateral, cam_l[2]])
    delta = [target[0] - her_cam[0], target[1] - her_cam[1], 0.0]
    xs = [lead + r for r in rel_x]
    ys = [lateral + r for r in rel_y]
    far_limit = float(box["apron"]) + float(box["depth"]) - float(side_margin_cm)
    checks = {"near_ok": min(xs) >= float(x_min_local) - 1e-6, "far_ok": max(xs) <= far_limit,
              "side_ok": max(ys) <= iy + 1e-6 and min(ys) >= -iy - 1e-6,
              "under_lattice": float(top_cm) + top_clear_cm <= float(box["lattice_z"]),
              "under_roof": float(top_cm) <= float(box["height"]), "lead_in_range": not lead_over}
    return {"delta": delta, "lead_cm": lead, "lead_wanted_cm": float(lead_cm), "lead_needed_cm": need,
            "lateral_cm": lateral, "her_cam_local_after": [lead, lateral, cam_l[2]],
            "set_local_after": [min(xs), max(xs), min(ys), max(ys)], "checks": checks,
            "fits": all(checks[k] for k in ("near_ok", "far_ok", "side_ok", "under_roof"))}


FOOTPRINT_COMPONENTS = ("StaticMeshComponent", "InstancedStaticMeshComponent", "HierarchicalInstancedStaticMeshComponent",
                        "SkeletalMeshComponent", "GeometryCacheComponent", "NiagaraComponent")
FOOTPRINT_EXCLUDE = re.compile(r"Sky|Atmosphere|Landscape|Fog|PostProcess|Light|Volume|Cloud|Camera|Reflection|Decal|"
                               r"Audio|Sound|Note|Player|WorldSettings|Brush")


def footprint_from_rows(rows, max_size_cm=4000.0):
    """The DIORAMA footprint (coordinator 7 Oct: the live DRY's actor-bounds union came out ~80 x 80 m from environment
    actors). rows = [{"label", "class", "components": [class names], "bounds": [ox, oy, oz, ex, ey, ez]}].
    Kept: an actor whose class is not environment-like (FOOTPRINT_EXCLUDE) AND that owns a renderable mesh / cache /
    Niagara component AND whose full size is <= max_size_cm on every axis. -> {"box": [x0,x1,y0,y1,z0,z1] | None,
    "kept": [...], "excluded": [{"label", "class", "why"}]}."""
    kept, excluded = [], []
    for r in rows:
        cls = str(r["class"])
        e = r["bounds"][3:6]
        if FOOTPRINT_EXCLUDE.search(cls):
            excluded.append({"label": r["label"], "class": cls, "why": "environment/light/volume class"})
        elif not any(c in FOOTPRINT_COMPONENTS for c in r.get("components") or []):
            excluded.append({"label": r["label"], "class": cls, "why": "no mesh/cache/Niagara component"})
        elif max(e) * 2.0 > float(max_size_cm):
            excluded.append({"label": r["label"], "class": cls, "why": "size %.0f m > %.0f m" % (max(e) * 2.0 / 100.0,
                                                                                               max_size_cm / 100.0)})
        elif max(e) <= 0.5:
            excluded.append({"label": r["label"], "class": cls, "why": "zero bounds"})
        else:
            kept.append(r)
    if not kept:
        return {"box": None, "kept": [], "excluded": excluded}
    o = lambda r, i: r["bounds"][i]
    box = [min(o(r, 0) - o(r, 3) for r in kept), max(o(r, 0) + o(r, 3) for r in kept),
           min(o(r, 1) - o(r, 4) for r in kept), max(o(r, 1) + o(r, 4) for r in kept),
           min(o(r, 2) - o(r, 5) for r in kept), max(o(r, 2) + o(r, 5) for r in kept)]
    return {"box": box, "kept": [{"label": r["label"], "class": r["class"]} for r in kept], "excluded": excluded}


def glide_seconds(start, end, fps, v1, max_speed_cm_s, min_s, step_s=0.5, max_s=40.0):
    """Shortest glide (multiple of step_s, >= min_s) whose peak speed is <= max_speed (Gary/coordinator: <= ~3 m/s).
    Uses plan_glide itself, so the bound holds for the keys actually written. -> (seconds, peak) or (None, peak)."""
    t = float(min_s)
    peak = None
    while t <= max_s + EPS:
        f1 = int(round(t * fps))
        g = plan_glide(start, end, 0, f1, fps, v1=v1)
        peak = g["report"]["peak_speed_cm_s"]
        if peak <= max_speed_cm_s:
            return t, peak
        t += step_s
    return None, peak


def propose_hangar(set_local, top_cm, current, comfort_cm=300.0, depth_step=2000.0, width_step=500.0):
    """Snug HANGAR_PARAMS for Structure's hangar_build.py (hangar_build.py:61-67 names). Floor tiles are ~20 m squares
    (hangar_build.py:96-98), so depth steps by 2000. K = sqrt(max(depth, 2 x height)/6000) (hangar_build.py:178):
    keeping height keeps K, hence the rise timing, when depth <= 2 x height."""
    apron = float(current["apron"])
    depth = max(depth_step, math.ceil((set_local[1] + comfort_cm - apron) / depth_step) * depth_step)
    half_w = max(1000.0, math.ceil((max(abs(set_local[2]), abs(set_local[3])) + comfort_cm) / width_step) * width_step)
    lattice_z = max(float(current["lattice_z"]), math.ceil((float(top_cm) + comfort_cm) / 100.0) * 100.0)
    height = max(float(current["height"]), lattice_z + 1000.0)
    k_now = math.sqrt(max(float(current["depth"]), 2.0 * float(current["height"])) / 6000.0)
    k_new = math.sqrt(max(depth, 2.0 * height) / 6000.0)
    return {"params": {"depth": depth, "half_w": half_w, "height": height, "lattice_z": lattice_z, "apron": apron},
            "k_now": k_now, "k_new": k_new, "timing_changes": abs(k_new - k_now) > 1e-9,
            "encloses": set_local[0] >= apron and set_local[1] <= apron + depth - comfort_cm / 2.0}


def glow_reach(glow_z, radius, floor_z, her_box=None):
    """Can a ceiling glow (point light) reach the floor plane or her set's AABB [x0,x1,y0,y1,z0,z1] at `glow_z`'s xy?
    her_box distances use the glow position dict {"x","y","z"}."""
    out = {"floor_gap_cm": float(glow_z["z"]) - float(floor_z), "radius_cm": float(radius)}
    out["reaches_floor"] = out["floor_gap_cm"] < float(radius)
    if her_box:
        dx = max(her_box[0] - glow_z["x"], 0.0, glow_z["x"] - her_box[1])
        dy = max(her_box[2] - glow_z["y"], 0.0, glow_z["y"] - her_box[3])
        dz = max(her_box[4] - glow_z["z"], 0.0, glow_z["z"] - her_box[5])
        out["set_gap_cm"] = math.sqrt(dx * dx + dy * dy + dz * dz)
        out["reaches_set"] = out["set_gap_cm"] < float(radius)
    else:
        out["reaches_set"] = False
    gaps = [out["floor_gap_cm"]] + ([out["set_gap_cm"]] if her_box else [])
    out["clamp_cm"] = max(10.0, min(gaps) - 10.0) if (out["reaches_floor"] or out["reaches_set"]) else None
    return out


def surfaces_seen(cam_local, rot, hfov, aspect, box, set_box_local, nx=9, ny=5, far_cm=20000.0):
    """Which hangar surfaces her camera sees (ray grid; [inf] approximation: her set is its AABB, roll ignored).
    cam_local [x,y,z] dock-local; rot [roll,pitch,yaw] dock-local deg; box interior; set_box_local [x0,x1,y0,y1,z0,z1].
    -> {"left_wall": n, "right_wall": n, "far_wall": n, "roof": n, "floor": n, "set": n, "open": n}."""
    cp, sp = math.cos(math.radians(rot[1])), math.sin(math.radians(rot[1]))
    cy, sy = math.cos(math.radians(rot[2])), math.sin(math.radians(rot[2]))
    fwd = (cp * cy, cp * sy, sp)
    right = (-sy, cy, 0.0)
    up = (-sp * cy, -sp * sy, cp)
    th = math.tan(math.radians(hfov) / 2.0)
    tv = th / float(aspect)
    hw, x_far, h = float(box["half_w"]), float(box["apron"]) + float(box["depth"]), float(box["height"])
    out = {k: 0 for k in ("left_wall", "right_wall", "far_wall", "roof", "floor", "set", "open")}
    for i in range(nx):
        for j in range(ny):
            u = -1.0 + 2.0 * i / (nx - 1)
            v = -1.0 + 2.0 * j / (ny - 1)
            d = [fwd[k] + u * th * right[k] + v * tv * up[k] for k in range(3)]
            hits = []
            for name, axis, value in (("left_wall", 1, -hw), ("right_wall", 1, hw), ("far_wall", 0, x_far),
                                      ("roof", 2, h), ("floor", 2, 0.0)):
                if abs(d[axis]) < EPS:
                    continue
                t = (value - cam_local[axis]) / d[axis]
                if t > 0:
                    hits.append((t, name))
            tn, tf = 0.0, far_cm
            ok = True
            for k, (a, b) in enumerate(((set_box_local[0], set_box_local[1]), (set_box_local[2], set_box_local[3]),
                                        (set_box_local[4], set_box_local[5]))):
                if abs(d[k]) < EPS:
                    if not (a <= cam_local[k] <= b):
                        ok = False
                    continue
                t1, t2 = (a - cam_local[k]) / d[k], (b - cam_local[k]) / d[k]
                tn, tf = max(tn, min(t1, t2)), min(tf, max(t1, t2))
            if ok and tn <= tf:
                hits.append((tn, "set"))
            hits = [x for x in hits if x[0] < far_cm]
            out[min(hits)[1] if hits else "open"] += 1
    return out


# =====================================================================================================================
# Pure: lights (strike, blink-out, ramps)
# =====================================================================================================================

def order_lights(lights, cam, mode="near_to_far"):
    """lights = [{"label", "loc"}]; deterministic (ties broken by label)."""
    key = lambda r: (math.sqrt(sum((r["loc"][i] - cam[i]) ** 2 for i in range(3))), r["label"])
    rows = sorted(lights, key=key)
    if mode == "far_to_near":
        rows = list(reversed(rows))
    elif mode != "near_to_far":
        raise PlanError("ORDER_MODE_INVALID: %r" % mode)
    return rows


def schedule(n, first_frame, last_frame, fps, seed, gap_s=(0.6, 1.2), min_gap_s=0.25):
    """n strike frames from first_frame, gaps drawn from ONE generator (one draw per statement), compressed to end
    at or before last_frame. -> {"frames", "gaps_s", "scale", "refusals", "warnings"}."""
    out = {"frames": [], "gaps_s": [], "scale": 1.0, "refusals": [], "warnings": []}
    if n <= 0:
        return out
    rng = random.Random("%s|gaps" % seed)
    gaps = []
    for _ in range(n - 1):
        g = rng.uniform(float(gap_s[0]), float(gap_s[1]))
        gaps.append(g)
    avail = (last_frame - first_frame) / float(fps)
    total = sum(gaps)
    if total > avail + EPS:
        out["scale"] = avail / total if total > 0 else 1.0
        gaps = [g * out["scale"] for g in gaps]
        out["warnings"].append("GAPS_COMPRESSED: %d strikes need %.2f s, window %.2f s (x%.2f)" % (n, total, avail,
                                                                                                  out["scale"]))
        if gaps and min(gaps) < float(min_gap_s) - EPS:
            out["refusals"].append("STRIKES_DO_NOT_FIT: min gap %.3f s < %.3f s (window %.2f s for %d lights)"
                                   % (min(gaps), min_gap_s, avail, n))
    frames, t = [int(first_frame)], 0.0
    for g in gaps:
        t += g
        f = int(first_frame) + int(round(t * fps))
        frames.append(max(f, frames[-1] + 1))
    if frames[-1] > last_frame:
        out["refusals"].append("SCHEDULE_PAST_WINDOW: last %d > %d" % (frames[-1], last_frame))
    out["frames"], out["gaps_s"] = frames, gaps
    return out


def flicker_count(seed, label, pulses=(2, 4), max_pulses=None):
    rng = random.Random("%s|%s" % (seed, label))
    n = rng.randint(int(pulses[0]), int(pulses[1]))
    if max_pulses is not None:
        n = min(n, int(max_pulses))
    return n, rng


def strike_keys(target, f_strike, seed, label, fps, window_s=0.32, pulses=(2, 4), on_frac=(0.35, 1.0)):
    """Ignition flicker then settle at `target`. Frame-aligned (constant-interpolation keys): pulse k is ON at
    f+2k, OFF at f+2k+1; settle at f+2n. n <= floor(window_s*fps/2) (25 fps, 0.32 s -> 4). One RNG per light."""
    max_n = max(1, int(math.floor(window_s * fps / 2.0 + EPS)))
    n, rng = flicker_count(seed, label, pulses, max_n)
    keys = [[int(f_strike) - 1, 0.0]]
    for k in range(n):
        u = rng.uniform(float(on_frac[0]), float(on_frac[1]))
        keys.append([int(f_strike) + 2 * k, float(target) * u])
        keys.append([int(f_strike) + 2 * k + 1, 0.0])
    keys.append([int(f_strike) + 2 * n, float(target)])
    return keys


def blink_out_keys(start_value, f_out, seed, label, fps, window_s=0.32, pulses=(2, 4), on_frac=(0.2, 0.8)):
    """Reverse strike: held at start_value, then OFF/ON stutter, then 0 at f+2n (own RNG stream, ':out')."""
    max_n = max(1, int(math.floor(window_s * fps / 2.0 + EPS)))
    n, rng = flicker_count(seed, label + ":out", pulses, max_n)
    keys = [[int(f_out) - 1, float(start_value)]]
    for k in range(n):
        u = rng.uniform(float(on_frac[0]), float(on_frac[1]))
        keys.append([int(f_out) + 2 * k, 0.0])
        keys.append([int(f_out) + 2 * k + 1, float(start_value) * u])
    keys.append([int(f_out) + 2 * n, 0.0])
    return keys


def dedupe_keys(keys):
    """Sorted by frame; a later entry for the same frame wins (so composed key lists never double-key a frame)."""
    out = {}
    for k in keys:
        out[int(k[0])] = list(k)
    return [out[f] for f in sorted(out)]


def ramp_keys(v0, v1, f0, f1):
    """Per-frame smoothstep keys (LINEAR between frames => exact at every frame)."""
    if f1 <= f0:
        raise PlanError("RAMP_EMPTY: [%r, %r]" % (f0, f1))
    return [[f, float(v0) + (float(v1) - float(v0)) * smoothstep((f - f0) / float(f1 - f0))] for f in range(f0, f1 + 1)]


# =====================================================================================================================
# Pure: the ceiling rig must not lower (Gary 7 Oct: "no need for the ceiling rig now to lower")
# =====================================================================================================================

def cancel_keys(rise_keys, offset_ticks, hold_value=None):
    """ADDITIVE keys for OUR Scene that cancel the rise's lattice Location.Z motion exactly.
    rise_keys = [{"tick", "value", "interp" ('cubic'|'linear'|'constant'), "arrive", "leave", ("arrive_w", "leave_w",
    "weighted")}] in the RISE's tick space; offset_ticks maps rise tick -> Scene tick (same tick resolution, rate 1).
    Each additive key = hold - value with NEGATED tangents and the same interpolation, so rise(t) + add(t) = hold for
    every t: a Hermite/Bezier segment is linear in its end values and tangents [inf: standard curve algebra; weighted
    tangents keep their weights, the negated slope flips the handle]. Constant extrapolation on both sides cancels
    too (rise holds its first/last value, the additive holds hold - first/last). hold defaults to the FIRST key value
    (the rig flown up, hangar_build.py:501)."""
    if not rise_keys:
        raise PlanError("LATTICE_NO_KEYS")
    rows = sorted(rise_keys, key=lambda k: int(k["tick"]))
    hold = float(rows[0]["value"]) if hold_value is None else float(hold_value)
    out = []
    for k in rows:
        if k.get("interp") not in ("cubic", "linear", "constant"):
            raise PlanError("LATTICE_INTERP_UNKNOWN: %r" % k.get("interp"))
        out.append({"tick": int(k["tick"]) + int(offset_ticks), "value": hold - float(k["value"]), "interp": k["interp"],
                    "arrive": -float(k.get("arrive") or 0.0), "leave": -float(k.get("leave") or 0.0),
                    "arrive_w": k.get("arrive_w"), "leave_w": k.get("leave_w"), "weighted": k.get("weighted")})
    return {"hold": hold, "keys": out, "lowers_cm": hold - min(float(k["value"]) for k in rows),
            "span_ticks": [out[0]["tick"], out[-1]["tick"]]}


def curve_eval(keys, tick):
    """Unweighted Hermite evaluation of a key list (ticks; tangents in value/tick) - the harness's reference curve."""
    ks = sorted(keys, key=lambda k: k["tick"])
    if tick <= ks[0]["tick"]:
        return float(ks[0]["value"])
    if tick >= ks[-1]["tick"]:
        return float(ks[-1]["value"])
    for a, b in zip(ks, ks[1:]):
        if a["tick"] <= tick <= b["tick"]:
            if a["interp"] == "constant":
                return float(a["value"]) if tick < b["tick"] else float(b["value"])
            dt = float(b["tick"] - a["tick"])
            s_ = (tick - a["tick"]) / dt
            if a["interp"] == "linear":
                return float(a["value"]) + (float(b["value"]) - float(a["value"])) * s_
            return hermite(float(a["value"]), float(b["value"]), float(a["leave"]), float(b["arrive"]), dt, s_)
    raise PlanError("CURVE_EVAL")


def rise_offset_ticks(section_start_frame, scene_fps, scene_tick, rise_lower_tick, start_offset_tick, rise_tick,
                      play_rate=1.0):
    """Rise tick -> Scene tick for a rate-1 sub-section (klara_hookin.py:122-128 [prec]); refuses other cases."""
    if abs(float(scene_tick) - float(rise_tick)) > 1e-9:
        raise PlanError("RISE_TICK_RESOLUTION_DIFFERS: scene %r rise %r" % (scene_tick, rise_tick))
    if abs(float(play_rate) - 1.0) > 1e-9:
        raise PlanError("RISE_PLAY_RATE_NOT_1: %r" % play_rate)
    tpf = float(scene_tick) / float(scene_fps)
    if abs(tpf - round(tpf)) > 1e-9:
        raise PlanError("SCENE_TICKS_PER_FRAME_NOT_WHOLE: %r" % tpf)
    return int(section_start_frame) * int(round(tpf)) - int(rise_lower_tick) - int(start_offset_tick)


# =====================================================================================================================
# Pure: v3 her lit frame, the slot start offset, audio report
# =====================================================================================================================

def lit_cfg(args):
    c = dict(LIT_DEFAULTS)
    c.update(args.get("lit") or {})
    return c


def curve_at(curve, frame):
    """curve = {"tpf": ticks per display frame, "keys": [{"tick","value","interp","arrive","leave"}], "default"}.
    Value at a (display) frame: curve_eval in tick space (exact at keys, linear/constant exact, cubic = unweighted
    Hermite from the read tangents [inf: UE stores computed auto tangents on the key]); no keys -> default."""
    keys = curve.get("keys") or []
    if not keys:
        return curve.get("default")
    return curve_eval(keys, float(frame) * float(curve["tpf"]))


def _sustained(vals, hold):
    """m[i] = min(vals[i .. i+hold]) (truncated at the end): the level a curve HOLDS from frame i for `hold` frames."""
    n = len(vals)
    return [min(vals[i:min(n, i + hold + 1)]) for i in range(n)]


def snap_her_frame(frame, her_lo, her_fps, scene_fps):
    """Round a her-frame UP to the next frame that lands exactly on our Scene grid (S1: 30 -> 25 fps = every 6 of
    hers), so the skipped opening and her remaining length are whole Scene frames. -> (frame, step) or PlanError."""
    hf, sf = float(her_fps), float(scene_fps)
    if abs(hf - round(hf)) > 1e-9 or abs(sf - round(sf)) > 1e-9:
        raise PlanError("FPS_NOT_INTEGER: her %r scene %r" % (her_fps, scene_fps))
    step = int(round(hf)) // math.gcd(int(round(hf)), int(round(sf)))
    k = int(math.ceil((int(frame) - int(her_lo)) / float(step) - 1e-9))
    return int(her_lo) + max(0, k) * step, step


def find_lit_frame(curves, her_lo, her_hi, her_fps, cfg):
    """Her LIT frame from her lights' Intensity curves {label: curve} (her display frames, [her_lo, her_hi)).
    Per light, over the search window [her_lo, her_lo + search_s]: plateau = the highest level it HOLDS for hold_s
    (max of _sustained); lit_at = the first frame from which it holds >= value_fraction x plateau. A light whose
    plateau <= min_value is never lit in the window (no strike). frame_raw = the earliest frame by which
    light_fraction of the ever-lit lights are lit (the ceil(f x n)-th lit_at). Cross-check: the normalised sum
    (each light / its plateau) first holding >= sum_fraction of its own plateau; disagreement > disagree_warn_s
    warns. cfg["frame"] overrides (an explicit her frame). Unkeyed lights do not vote (they are lit throughout)."""
    out = {"refusals": [], "warnings": [], "per_light": {}, "method": "detected"}
    fps = float(her_fps)
    w1 = min(int(her_hi) - 1, int(her_lo) + int(math.ceil(float(cfg["search_s"]) * fps - 1e-9)))
    frames = list(range(int(her_lo), w1 + 1))
    out["window"] = [int(her_lo), w1]
    hold = max(0, int(round(float(cfg["hold_s"]) * fps)))
    vf, mv = float(cfg["value_fraction"]), float(cfg["min_value"])
    norm = [0.0] * len(frames)
    ever = []
    for label in sorted(curves):
        c = curves[label]
        if not c or not c.get("keys"):
            out["per_light"][label] = {"keyed": False}
            continue
        vals = [float(curve_at(c, f)) for f in frames]
        sus = _sustained(vals, hold)
        ref = max(sus)
        tpf = float(c["tpf"])
        row = {"keyed": True, "plateau": ref, "first_value": vals[0], "n_keys": len(c["keys"]),
               "keys": [[round(k["tick"] / tpf, 3), float(k["value"])] for k in sorted(c["keys"], key=lambda k: k["tick"])
                        if frames[0] * tpf <= k["tick"] <= frames[-1] * tpf][:60]}
        if ref <= mv:
            row["ever_lit"] = False
        else:
            i = next(j for j, s_ in enumerate(sus) if s_ >= vf * ref * (1.0 - 1e-6))
            row.update(ever_lit=True, lit_at=frames[i], lit_at_s_into_her=i / fps)
            ever.append(frames[i])
            for j, v in enumerate(vals):
                norm[j] += v / ref
        out["per_light"][label] = row
    out["n_ever_lit"] = len(ever)
    if ever:
        need = max(1, int(math.ceil(float(cfg["light_fraction"]) * len(ever) - 1e-9)))
        out["n_needed"] = need
        out["frame_votes"] = sorted(ever)[need - 1]
        ssus = _sustained(norm, hold)
        splat = max(ssus)
        out["sum_frame"] = frames[next(j for j, s_ in enumerate(ssus) if s_ >= float(cfg["sum_fraction"]) * splat *
                                       (1.0 - 1e-6))]
        if abs(out["sum_frame"] - out["frame_votes"]) / fps > float(cfg["disagree_warn_s"]):
            out["warnings"].append("LIT_METRICS_DISAGREE: votes %d vs normalised sum %d (%.2f s apart) - check "
                                   "per_light" % (out["frame_votes"], out["sum_frame"],
                                                  abs(out["sum_frame"] - out["frame_votes"]) / fps))
    if cfg.get("frame") is not None:
        out["method"] = "args lit.frame"
        out["frame_raw"] = int(cfg["frame"])
    elif ever:
        out["frame_raw"] = out["frame_votes"]
    else:
        out["frame_raw"] = None
        out["refusals"].append("LIT_NONE: no keyed light of hers holds > %g within %.0f s of her start (set "
                               "lit.frame or lit.enabled false)" % (mv, float(cfg["search_s"])))
    return out


def slot_skip(her_lo, her_hi, her_frame, her_fps, scene_fps, her_tpf, slot_len_scene):
    """The slot starts INTO her copy at her_frame: start_frame_offset (her TICKS [inf: StartFrameOffset is stored in
    the inner tick resolution, as klara_hookin.inner_to_scene_s and scene_audio_import.py:235-241 treat it; the header
    comment says display rate, MovieSceneSectionParameters.h:74-76 - APPLY's parent-frame read-back decides]) and the
    Scene frames skipped / remaining. Refuses off-grid values and a slot whose length is not her full length."""
    r = {"refusals": [], "her_frame": int(her_frame)}
    ratio = float(scene_fps) / float(her_fps)
    total = (int(her_hi) - int(her_lo)) * ratio
    skip = (int(her_frame) - int(her_lo)) * ratio
    rem = (int(her_hi) - int(her_frame)) * ratio
    if not (int(her_lo) <= int(her_frame) < int(her_hi)):
        r["refusals"].append("LIT_FRAME_OUTSIDE_HER_RANGE: %d not in [%d, %d)" % (her_frame, her_lo, her_hi))
    for nm, v in (("skip", skip), ("remaining", rem)):
        if abs(v - round(v)) > 1e-6:
            r["refusals"].append("SLOT_%s_OFF_GRID: %.6f Scene frames" % (nm.upper(), v))
    if abs(total - float(slot_len_scene)) > 1e-6:
        r["refusals"].append("SLOT_LENGTH_MISMATCH: her %.3f Scene frames vs slot %d" % (total, slot_len_scene))
    tpf = float(her_tpf)
    if abs(tpf - round(tpf)) > 1e-9:
        r["refusals"].append("HER_TICKS_PER_FRAME_NOT_WHOLE: %r" % her_tpf)
    r.update(skip_frames=int(round(skip)), remaining_frames=int(round(rem)), skip_s=skip / float(scene_fps),
             remaining_s=rem / float(scene_fps), offset_ticks=(int(her_frame) - int(her_lo)) * int(round(tpf)))
    return r


def scene_frame_of_her(her_frame, cut, lit_frame, her_fps, scene_fps):
    """Which Scene frame plays her frame `her_frame` once the slot starts at `cut` with her `lit_frame`."""
    return float(cut) + (float(her_frame) - float(lit_frame)) * float(scene_fps) / float(her_fps)


def audio_report(her_audio, scene_audio, scene_markers, lit_frame, her_fps, cut, scene_fps, planned_end):
    """What moves. Her copy's audio plays INSIDE the slot, so the skip shifts it; Scene-level audio and markers are
    absolute (nothing here moves them): report what now falls past the new end."""
    her = []
    for a in her_audio or []:
        s0, s1 = int(a["start_frame"]), int(a["end_frame"])
        row = dict(a)
        if s1 <= lit_frame:
            row["after_skip"] = "never plays (ends before her lit frame)"
        elif s0 < lit_frame:
            row["after_skip"] = "joins mid-sound at the cut: its first %.2f s are skipped" % ((lit_frame - s0) / her_fps)
            row["scene_start_frame"] = int(cut)
        else:
            row["after_skip"] = "starts inside the slot"
            row["scene_start_frame"] = scene_frame_of_her(s0, cut, lit_frame, her_fps, scene_fps)
        row["scene_end_frame"] = scene_frame_of_her(s1, cut, lit_frame, her_fps, scene_fps)
        her.append(row)
    past = [dict(s, why="ends past the new end %d" % planned_end) for s in scene_audio or []
            if int(s["range"][1]) > planned_end]
    marks = [dict(m, why="past the new end %d" % planned_end) for m in scene_markers or [] if int(m["frame"]) >= planned_end]
    return {"her_audio": her, "scene_audio_past_end": past, "scene_markers_past_end": marks,
            "scene_audio_all": list(scene_audio or []), "scene_markers_all": list(scene_markers or [])}


# =====================================================================================================================
# Pure: the timeline
# =====================================================================================================================

def plan_timeline(L, C, E, fps, n_lights, cfg, exit_len, glide_in_s=None, glide_out_s=None, skip=0):
    """v2 (Gary 7 Oct): "while we're in the dark, we should already have moved into the final position for S1's wide
    intro and then it lights up, and then we start it without any external lighting interference".
      [L, d0)        dark hold (rig glows still on: "the grid of faint lights showing the rig come up is good")
      [d0, g1]       glide ENTIRELY in the dark: Entry pose -> her first pose (speed-bounded length)
      [g1, S0)       hold on her first frame, still dark; roof hidden from g1; ceiling glows fade OUT over [gf0, S0]
      [S0, ...)      her lights strike one by one; her env crossfades 0 -> hers over [S0, C - settle]
      [C, E)         her cinematic (slot); the cut moves later when the intro needs it (slot keeps its length)
      outro          hold; her lights blink out; env out; roof back; rig glows back with the glide out; Exit cut.
    -> dict (+ refusals). glide_in_s / glide_out_s from glide_seconds.
    v3: `skip` = Scene frames of her opening that never play (slot_skip); the slot is her REMAINING length, so
    everything after the slot (outro, exit, end) comes `skip` frames earlier. n_lights = lights that STRIKE."""
    intro, outro = cfg["intro"], cfg["outro"]
    f = lambda s_: int(math.ceil(float(s_) * fps - 1e-6))
    r = {"refusals": [], "warnings": [], "land": L, "cut_before": C, "slot_before": [C, E], "version": 3,
         "slot_skip": int(skip)}
    if L is None or not (0 <= L < C < E):
        r["refusals"].append("TIMELINE_ORDER: land %r cut %r slot end %r" % (L, C, E))
        return r
    if not (0 <= int(skip) < E - C):
        r["refusals"].append("SKIP_INVALID: %r of a %d-frame slot" % (skip, E - C))
        return r
    E = E - int(skip)
    d0 = L + f(intro["dark_hold_s"])
    g1 = d0 + f(glide_in_s if glide_in_s is not None else intro["glide_s"])
    S0 = g1 + f(intro.get("pre_strike_hold_s", 0.5))
    gf0 = max(d0, S0 - f(intro.get("glow_fade_s", 1.5)))
    settle = f(intro["env_settle_s"])
    flick = f(intro["flicker_window_s"])
    gaps = intro["gap_s"]
    span = f((float(gaps[0]) + float(gaps[1])) / 2.0 * max(0, n_lights - 1))
    need = max(S0 + span + flick + 1 + settle, S0 + f(intro.get("env_min_s", 3.0)) + settle)
    shift = max(0, need - C)
    C, E = C + shift, E + shift
    r.update(cut=C, slot=[C, E], slot_shift=shift, slot_shift_s=shift / float(fps))
    if shift:
        r["warnings"].append("CUT_MOVED_LATER: +%d frames (%.2f s): glide in the dark, then strikes; slot -> [%d, %d)"
                             % (shift, shift / float(fps), C, E))
    strike_last = C - settle - flick - 1
    xf = [S0, C - settle]
    o0 = E + f(outro["hold_s"])
    blink_span = f(outro["blink_gap_s"][1]) * max(0, n_lights - 1) + flick + 1
    env_out = [o0, o0 + f(outro["env_fade_s"])]
    lights_out = o0 + blink_span
    go0 = max(env_out[1], lights_out) + f(outro["dark_before_glide_s"])
    go1 = go0 + f(glide_out_s if glide_out_s is not None else outro["glide_s"])
    end = go1 + int(exit_len)
    back = [go0, go0 + f(outro.get("rig_back_s", 1.5))] if outro.get("rig_glow_back", True) else None
    r.update(dark=[L, d0], glide_in=[d0, g1], first_hold=[g1, S0], glow_fade=[gf0, S0],
             rig_dark=[S0, back[0] if back else end], rig_back=back, strike_window=[S0, strike_last], crossfade=xf,
             roof_hidden=[g1, env_out[1]], ours_hidden_from=g1, hers_dark=[L, S0], outro_hold=[E, o0],
             blink_window=[o0, lights_out], env_out=env_out, glide_out=[go0, go1], exit_cut=[go1, end],
             planned_end=end, planned_end_s=end / float(fps), outro_s=(end - E) / float(fps),
             intro_s=(C - L) / float(fps))
    if strike_last <= S0:
        r["refusals"].append("STRIKE_WINDOW_EMPTY: [%d, %d]" % (S0, strike_last))
    if xf[1] <= xf[0]:
        r["refusals"].append("CROSSFADE_EMPTY: %s" % xf)
    if not (d0 <= g1 <= gf0 or gf0 < S0) or g1 > S0:
        r["refusals"].append("GLIDE_NOT_IN_DARK: glide end %d, first strike %d" % (g1, S0))
    if back and back[0] < max(env_out[1], lights_out):
        r["refusals"].append("RIG_BACK_BEFORE_HER_LIGHTS_OUT: %s" % back)
    return r


# =====================================================================================================================
# Pure: channels, re-key, args, gates
# =====================================================================================================================

def channel_base(name):
    """'Location.X_183' -> 'Location.X' (memory ue58-sequencer-read-traps: channel names are suffixed)."""
    return re.sub(r"_\d+$", "", str(name))


def eval_keys(keys, default, frame):
    """Value of a channel at `frame` WITHOUT interpolation maths: exact key, before-first / after-last (constant
    extrapolation), or the default when unkeyed. Between keys -> None (the live side then uses channel.evaluate)."""
    if not keys:
        return default
    keys = sorted(keys)
    for t, v in keys:
        if t == frame:
            return v
    if frame < keys[0][0]:
        return keys[0][1]
    if frame > keys[-1][0]:
        return keys[-1][1]
    return None


def shift_channels(chans, delta):
    """chans {"x": {"keys": [[t, v]...], "default": v|None}, ...} + translation delta -> shifted (exact for cubic keys:
    a constant offset leaves tangents unchanged)."""
    out = {}
    for i, ax in enumerate("xyz"):
        ch = chans.get(ax) or {"keys": [], "default": None}
        d = float(delta[i])
        out[ax] = {"keys": [[t, float(v) + d] for t, v in ch["keys"]],
                   "default": None if ch.get("default") is None else float(ch["default"]) + d}
    return out


def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in MODES:
        r.append("MODE_INVALID: %r" % args.get("mode"))
    key = str(args.get("scene") or "")
    scenes = args.get("scenes") or {}
    if key not in scenes:
        r.append("SCENE_NOT_IN_ARGS: %r" % key)
    for k, row in scenes.items():
        for fld in ("scene_sequence", "level", "copy", "entry_camera", "exit_camera", "glide_camera_label"):
            if fld not in row:
                r.append("S%s_MISSING_%s" % (k, fld.upper()))
        if "Master" in str(row.get("scene_sequence", "")):
            r.append("S%s_TARGET_IS_THE_MASTER" % k)
    i, o = args.get("intro") or {}, args.get("outro") or {}
    for blk, name, fields in ((i, "intro", ("dark_hold_s", "glide_s", "env_settle_s", "flicker_window_s", "gap_s",
                                              "min_gap_s", "order", "seed")),
                              (o, "outro", ("hold_s", "blink_gap_s", "env_fade_s", "flicker_window_s",
                                             "dark_before_glide_s", "glide_s"))):
        for fld in fields:
            if fld not in blk:
                r.append("%s_MISSING_%s" % (name.upper(), fld.upper()))
    if i.get("gap_s") and not (0 < i["gap_s"][0] <= i["gap_s"][1]):
        r.append("INTRO_GAP_RANGE_INVALID")
    if (args.get("placement") or {}).get("lead_cm", 0) < 0:
        r.append("LEAD_NEGATIVE")
    if args.get("roof") not in ("hide_roof", "hide_roof_and_seen_walls", "keep"):
        r.append("ROOF_OPTION_INVALID: %r" % args.get("roof"))
    if args.get("lattice", "cancel") not in LATTICE_MODES:
        r.append("LATTICE_MODE_INVALID: %r" % args.get("lattice"))
    if args.get("slot") not in ("nested_cinematic", "media_track"):
        r.append("SLOT_INVALID: %r" % args.get("slot"))
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
    c = state.get("census") or {}
    if c.get("content") or c.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(c, sort_keys=True))
    if mode == "APPLY" and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode == "APPLY" and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    if not state.get("hookin_applied"):
        r.append("HOOKIN_NOT_APPLIED: klara_hookin stream + seq records must be applied")
    return r


def census_gate(census, want_content, want_maps):
    out = []
    if sorted(census.get("content") or []) != sorted(want_content):
        out.append("CONTENT_CENSUS: got %s want %s" % (sorted(census.get("content") or []), sorted(want_content)))
    if sorted(census.get("maps") or []) != sorted(want_maps):
        out.append("MAP_CENSUS: got %s want %s" % (sorted(census.get("maps") or []), sorted(want_maps)))
    return out


def revert_actions(bindings, before_names, shared_guids):
    """Pure REVERT plan over binding rows [{"guid", "name", "parent", "tracks": [{"name", "cls"}]}].
    - shared (record shared_bindings): keep, strip OUR tracks (display name PREFIX...);
    - legacy (v1/v2 records have no shared list): a 'Klara Reveal - X' binding whose 'Klara Hookin - Hers Dark: X'
      (or Ours Off) is in the record's before-names but missing now, AND that still carries a Visibility track not
      named by us (the hookin's own track), is the hookin binding we renamed: rename back + strip;
    - every other 'Klara Reveal -' binding: remove (children before parents).
    unrecoverable = hookin names in before that are neither present nor recoverable (then restore from backup)."""
    shared = set(shared_guids or [])
    current = {b["name"] for b in bindings}
    rename, strip, remove = [], set(shared), []
    for b in bindings:
        if b["guid"] in shared or not b["name"].startswith(PREFIX):
            continue
        tail = b["name"][len(PREFIX):]
        hook = [hp + tail for hp in (HOOK_HERS, HOOK_OURS) if hp + tail in before_names and hp + tail not in current]
        foreign_vis = [t for t in b.get("tracks") or [] if not t["name"].startswith(PREFIX)
                       and t["cls"] == "MovieSceneVisibilityTrack"]
        if hook and foreign_vis:
            rename.append([b["guid"], hook[0]])
            strip.add(b["guid"])
        else:
            remove.append(b)
    remove.sort(key=lambda b: (b.get("parent") is None, b["name"]))
    renamed = {r[1] for r in rename}
    lost = sorted(n for n in before_names if n.startswith((HOOK_HERS, HOOK_OURS)) and n not in current
                  and n not in renamed)
    return {"rename": rename, "strip": sorted(strip), "remove": [b["guid"] for b in remove], "unrecoverable": lost}


def write_record_exclusive(path, data):          # klara_hookin.py:526-531 [prec]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(data, h, indent=1, sort_keys=True, default=str)
        h.flush()
        os.fsync(h.fileno())


def update_record(path, data):                    # klara_hookin.py:534-540 [prec]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(data, h, indent=1, sort_keys=True, default=str)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


def load_json(path):
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


# =====================================================================================================================
# Live (Unreal). Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraIngest")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _file(path, ext):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ext


def _stop(run, reason):
    unreal.log_error("KLARAREVEAL_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _by_label(label):
    return [a for a in _actors() if str(a.get_actor_label()) == label]


def _one(label, run):
    hits = _by_label(label)
    if len(hits) != 1:
        _stop(run, "ACTOR_COUNT|%s|%d" % (label, len(hits)))
    return hits[0]


def _v(v):
    return [float(v.x), float(v.y), float(v.z)]


def _level_actors(world, pkg):          # klara_hookin.py:816-820 [prec]
    for lv in unreal.EditorLevelUtils.get_levels(world):
        if lv.get_outer() is not None and _path(lv.get_outer()) == pkg:
            return [a for a in _actors() if a.get_level() == lv]
    return []


def _sequencer_open():
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    return _path(cur) if cur is not None else None


def _api_table():
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001 - a probe failure is a finding
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("MovieSceneScriptingFloatChannel.evaluate", "inf; live 7 Oct: False -> exact-key fallback eval_keys "
          "(a first/last frame BETWEEN keys refuses HER_CAMERA_EVAL)",
          lambda: hasattr(u.MovieSceneScriptingFloatChannel, "evaluate"))
    probe("MovieSceneScriptingDoubleChannel.evaluate", "inf", lambda: hasattr(u.MovieSceneScriptingDoubleChannel, "evaluate"))
    probe("GameplayStatics.get_streaming_level", "inf", lambda: hasattr(u.GameplayStatics, "get_streaming_level"))
    probe("EditorLevelUtils add_level_to_world_with_transform / remove_level_from_world",
          "decl EditorLevelUtils.h:276-277 (+ remove inf as used by klara_hookin.py:1019)",
          lambda: [hasattr(u.EditorLevelUtils, n) for n in ("add_level_to_world_with_transform", "remove_level_from_world")])
    probe("MovieSceneColorTrack (LightColor)", "inf; property LightColor via set_property_name_and_path",
          lambda: hasattr(u, "MovieSceneColorTrack"))
    probe("MovieSceneKeyInterpolation.CONSTANT", "inf", lambda: repr(u.MovieSceneKeyInterpolation.CONSTANT))
    probe("MovieSceneMediaTrack (MediaCompositing; the video slot)", "inf; plugin listed in "
          "pussstage_effective_plugins.json [meas]", lambda: hasattr(u, "MovieSceneMediaTrack"))
    probe("CineCameraComponent filmback", "prec curtain_sleight.py:1614",
          lambda: repr(u.CineCameraComponent.get_default_object().get_editor_property("filmback")))
    probe("MovieSceneSection.set_blend_type + MovieSceneBlendType.ADDITIVE (lattice cancel)", "inf",
          lambda: [hasattr(u.MovieSceneSection, "set_blend_type"), repr(u.MovieSceneBlendType.ADDITIVE)])
    probe("MovieSceneScriptingDoubleKey tangent get/set + RichCurveTangentMode.RCTM_USER", "inf",
          lambda: [hasattr(u.MovieSceneScriptingDoubleKey, n) for n in
                   ("get_arrive_tangent", "set_arrive_tangent", "get_leave_tangent", "set_leave_tangent",
                    "get_interpolation_mode", "set_tangent_mode", "get_tangent_weight_mode")] +
          [repr(u.RichCurveTangentMode.RCTM_USER)])
    probe("MovieSceneScriptingFloatKey get_time/get_interpolation_mode/tangents (v3 her light curves)", "inf",
          lambda: [hasattr(u.MovieSceneScriptingFloatKey, n) for n in
                   ("get_time", "get_interpolation_mode", "get_arrive_tangent", "get_leave_tangent")])
    probe("MovieSceneBindingProxy.remove_track (v3 REVERT strips OUR tracks off shared bindings)", "inf; memory: "
          "returns None, read back", lambda: hasattr(u.MovieSceneBindingProxy, "remove_track"))
    probe("MovieSceneSectionParameters.start_frame_offset (v3 slot offset)", "decl MovieSceneSectionParameters.h:76; "
          "units inf (ticks), decided by APPLY's parent-frame read-back",
          lambda: repr(u.MovieSceneSectionParameters().get_editor_property("start_frame_offset")))
    probe("MovieSceneCompletionMode.RESTORE_STATE", "prec klara_hookin.py:1156",
          lambda: repr(u.MovieSceneCompletionMode.RESTORE_STATE))
    probe("InfinityStageCelestialRig foreign_lighting_exempt_levels", "commit e0e04ed (built)",
          lambda: [a for a in _actors() if a.get_class().get_name() == "InfinityStageCelestialRig"][0]
          .get_editor_property("foreign_lighting_exempt_levels"))
    return rows


def _chan_map(section):
    return {channel_base(c.channel_name if hasattr(c, "channel_name") else c.get_name()): c
            for c in section.get_all_channels()}


def _ch_keys(ch):
    return [[int(k.get_time().frame_number.value), float(k.get_value())] for k in ch.get_keys()]


def _ch_curve(ch, tpf):
    """Keys with TICK times, interpolation and tangents (MovieSceneScriptingFloat/DoubleKey getters [inf, probed in
    api_table; the Double getters are live-proven by _lattice_facts]) -> a curve for curve_at."""
    keys = []
    for k in ch.get_keys():
        row = {"tick": int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
               "value": float(k.get_value())}
        try:
            row["interp"] = _INTERP.get(_enum_name(k.get_interpolation_mode()), "cubic")
        except Exception:  # noqa: BLE001 - recorded; cubic with zero tangents is the conservative read
            row["interp"], row["interp_unread"] = "cubic", True
        try:
            row["arrive"], row["leave"] = float(k.get_arrive_tangent()), float(k.get_leave_tangent())
        except Exception:  # noqa: BLE001
            row["arrive"], row["leave"], row["tangent_unread"] = 0.0, 0.0, True
        keys.append(row)
    return {"tpf": float(tpf), "keys": keys, "default": float(ch.get_default()) if ch.has_default() else None}


def _ch_eval(ch, frame, tpf=None):
    """Channel value at a DISPLAY frame: channel.evaluate when the build exposes it [inf, probed; live 7 Oct: absent],
    else an exact key / constant extrapolation (eval_keys), else (v3, tpf given) the key curve (curve_at)."""
    try:
        if hasattr(ch, "evaluate"):
            return float(ch.evaluate(unreal.FrameTime(unreal.FrameNumber(int(frame)))))
    except Exception:  # noqa: BLE001 - fall back to exact keys
        pass
    v = eval_keys(_ch_keys(ch), float(ch.get_default()) if ch.has_default() else None, int(frame))
    if v is None and tpf:
        v = curve_at(_ch_curve(ch, tpf), int(frame))
    return v


def _bindings_by_name(seq):
    out = {}
    for b in seq.get_bindings():
        out.setdefault(str(b.get_display_name()), []).append(b)
    return out


def _binding_tracks(b):
    """Tracks on a binding and its child possessables: {(child name or '', property or class): track}."""
    rows = []
    for t in b.get_tracks():
        rows.append(("", t))
    for c in b.get_child_possessables():
        for t in c.get_tracks():
            rows.append((str(c.get_display_name()), t))
    return rows


def _prop(t):
    try:
        return str(t.get_property_name())
    except Exception:  # noqa: BLE001 - not a property track
        return t.get_class().get_name()


def _her_camera(copy, which, at_frame=None, tpf=None):
    """Her FIRST ('first'), LAST ('last') or LIT ('lit', at_frame) cut camera pose + lens, from the re-keyed COPY
    (world positions now). Last = playback_end - 1 (memory ue58-sequencer-read-traps: the end frame is the restored
    REST pose). 'lit' evaluates between keys through the key curve (tpf) and reports which cut covers the frame."""
    lo, hi = int(copy.get_playback_start()), int(copy.get_playback_end())
    frame = int(at_frame) if which == "lit" else (lo if which == "first" else hi - 1)
    cuts = [s for t in copy.get_tracks() if isinstance(t, unreal.MovieSceneCameraCutTrack) for s in t.get_sections()]
    hit = [s for s in cuts if s.get_start_frame() <= frame < s.get_end_frame()]
    if len(hit) != 1:
        raise PlanError("HER_CUT_AT_%s: %d sections cover frame %d" % (which.upper(), len(hit), frame))
    guid = hit[0].get_camera_binding_id().get_editor_property("guid")
    gs = unreal.GuidLibrary.conv_guid_to_string      # memory: str(Guid) carries a memory address
    b = [x for x in copy.get_bindings() if gs(x.get_id()) == gs(guid)]
    if len(b) != 1:
        raise PlanError("HER_CAMERA_BINDING_%s: %d" % (which.upper(), len(b)))
    b = b[0]
    pose = {"binding": str(b.get_display_name()), "frame": frame, "fps": _rate(copy.get_display_rate()),
            "cut": [int(hit[0].get_start_frame()), int(hit[0].get_end_frame())]}
    tr = [s for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack) for s in t.get_sections()]
    if len(tr) != 1:
        raise PlanError("HER_CAMERA_TRANSFORM_SECTIONS: %d" % len(tr))
    cm = _chan_map(tr[0])
    vals = {}
    for n in ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z"):
        if n not in cm:
            raise PlanError("HER_CAMERA_CHANNEL_MISSING: %s" % n)
        v = _ch_eval(cm[n], frame, tpf)
        v2 = _ch_eval(cm[n], frame + (-1 if which == "last" else 1), tpf)
        if v is None or v2 is None:
            raise PlanError("HER_CAMERA_EVAL: %s between keys and no evaluate()" % n)
        vals[n] = (v, v2)
    sign = -1.0 if which == "last" else 1.0
    pose["loc"] = [vals["Location." + a][0] for a in "XYZ"]
    pose["rot"] = [vals["Rotation." + a][0] for a in "XYZ"]          # roll, pitch, yaw (memory: roll-pitch-yaw)
    pose["vel_cm_s"] = [sign * (vals["Location." + a][1] - vals["Location." + a][0]) * pose["fps"] for a in "XYZ"]
    pose["ang_deg_s"] = [sign * wrap(vals["Rotation." + a][1] - vals["Rotation." + a][0]) * pose["fps"] for a in "XYZ"]
    lens = {}
    for child in b.get_child_possessables():
        for t in child.get_tracks():
            p = _prop(t)
            for s in t.get_sections():
                chans = list(s.get_all_channels())
                if len(chans) == 1:
                    lens[p] = _ch_eval(chans[0], frame, tpf)
    # the camera actor itself (filmback, unkeyed lens) - lives in her streamed level
    pose["lens_tracks"] = lens
    pose["binding_guid"] = unreal.GuidLibrary.conv_guid_to_string(guid)
    return pose


def _camera_actor_facts(actor):
    comp = actor.get_cine_camera_component()
    fb = comp.get_editor_property("filmback")
    fs = comp.get_editor_property("focus_settings")
    return {"label": str(actor.get_actor_label()), "loc": _v(actor.get_actor_location()),
            "rot": [actor.get_actor_rotation().roll, actor.get_actor_rotation().pitch, actor.get_actor_rotation().yaw],
            "focal": float(comp.get_editor_property("current_focal_length")),
            "focus": float(fs.get_editor_property("manual_focus_distance")),
            "aperture": float(comp.get_editor_property("current_aperture")),
            "sensor": [float(fb.get_editor_property("sensor_width")), float(fb.get_editor_property("sensor_height"))]}


def _light_rows(actors, seq_bindings, her_lo, her_hi_last, tpf=None):
    """Her LOCAL lights with their authored (level) values and her LS's own values at her first / last frame
    for any property her copy keys (Intensity / LightColor) - the intro settles to the FIRST, the outro starts at
    the LAST, so the cut into and out of her section is value-continuous."""
    rows = []
    for a in actors:
        cls = a.get_class().get_name()
        if cls not in LOCAL_LIGHT_CLASSES:
            continue
        comp = a.get_component_by_class(unreal.LightComponent)
        lc = comp.get_editor_property("light_color")
        row = {"label": str(a.get_actor_label()), "name": str(a.get_name()), "class": cls, "loc": _v(a.get_actor_location()),
               "intensity": float(comp.get_editor_property("intensity")),
               "color": [lc.r / 255.0, lc.g / 255.0, lc.b / 255.0, lc.a / 255.0],
               "visible": bool(comp.get_editor_property("visible")), "hidden_in_game": bool(a.get_editor_property("hidden")),
               "keyed": {}, "first": {}, "last": {}, "curves": {}}
        for nm in {row["label"], row["name"]}:
            for b in seq_bindings.get(nm, []):
                for child, t in _binding_tracks(b):
                    p = _prop(t)
                    row["keyed"][p] = child or "(actor)"
                    for s in t.get_sections():
                        chans = list(s.get_all_channels())
                        if p == "Intensity" and len(chans) == 1:
                            row["first"]["Intensity"] = _ch_eval(chans[0], her_lo)
                            row["last"]["Intensity"] = _ch_eval(chans[0], her_hi_last)
                            if tpf:
                                row["curves"]["Intensity"] = _ch_curve(chans[0], tpf)
                        elif p == "LightColor" and len(chans) >= 3:
                            row["first"]["LightColor"] = [_ch_eval(c, her_lo) for c in chans]
                            row["last"]["LightColor"] = [_ch_eval(c, her_hi_last) for c in chans]
                            if tpf:
                                row["curves"]["LightColor"] = [_ch_curve(c, tpf) for c in chans]
        row["target_first"] = row["first"].get("Intensity", row["intensity"])
        row["target_last"] = row["last"].get("Intensity", row["intensity"])
        rows.append(row)
    return rows


def _her_prop_curve(seq_bindings, actor, prop, tpf):
    """(her copy keys `prop` on this actor or its components?, its key curve when exactly one channel) [v3]."""
    keyed, curve = False, None
    for nm in {str(actor.get_actor_label()), str(actor.get_name())}:
        for b in seq_bindings.get(nm, []):
            for _c, t in _binding_tracks(b):
                if _prop(t) == prop:
                    keyed = True
                    ch = [c for sct in t.get_sections() for c in sct.get_all_channels()]
                    if len(ch) == 1 and tpf:
                        curve = _ch_curve(ch[0], tpf)
    return keyed, curve


def _env_rows(actors, seq_bindings, her_lo, her_hi_last, tpf=None):
    """Her environment actors. v3: when her copy keys the ramped property, its key curve is kept (value at Lh)."""
    rows = []
    for a in actors:
        cls = a.get_class().get_name()
        if cls in ENV_INTENSITY:
            comp = a.get_component_by_class(unreal.ExponentialHeightFogComponent if cls == "ExponentialHeightFog"
                                            else unreal.LightComponentBase)
            prop = ENV_INTENSITY[cls]
            val = float(comp.get_editor_property("fog_density" if prop == "FogDensity" else "intensity"))
            row = {"label": str(a.get_actor_label()), "class": cls, "property": prop, "value": val}
            row["her_keyed"], row["curve"] = _her_prop_curve(seq_bindings, a, prop, tpf)
            rows.append(row)
        elif cls == "PostProcessVolume":
            st = a.get_editor_property("settings")
            exp = {n: bool(st.get_editor_property("override_" + n)) for n in
                   ("auto_exposure_method", "auto_exposure_bias", "auto_exposure_min_brightness",
                    "auto_exposure_max_brightness")}
            rows.append({"label": str(a.get_actor_label()), "class": cls, "property": "BlendWeight",
                         "value": float(a.get_editor_property("blend_weight")),
                         "unbound": bool(a.get_editor_property("unbound")),
                         "priority": float(a.get_editor_property("priority")), "exposure_overrides": exp,
                         "enabled": bool(a.get_editor_property("enabled"))})
            rows[-1]["her_keyed"], rows[-1]["curve"] = _her_prop_curve(seq_bindings, a, "BlendWeight", tpf)
        elif cls in ("SkyAtmosphere", "VolumetricCloud"):
            rows.append({"label": str(a.get_actor_label()), "class": cls, "property": None,
                         "note": "no intensity: lit by her sun, which ramps from 0 [inf]"})
    return rows


def _radius(comp):
    try:
        return float(comp.get_editor_property("attenuation_radius"))
    except Exception:  # noqa: BLE001 - directional / sky lights have none
        return None


def _hangar_lights(key, live_box, her_box_world):
    """Our hangar's lights: tag RigAtmos.Scene<N>Hangar or label 'S<N> ' with a LightComponent. Ceiling glows kept
    (radius-clamped if they reach the floor or her set); every other light is BLACKED (LightColor) for the Scene."""
    tag = HANGAR_TAG % key
    rows = []
    for a in _actors():
        lab = str(a.get_actor_label())
        if not (lab.startswith("S%s " % key) or tag in [str(t) for t in a.get_editor_property("tags")]):
            continue
        comp = a.get_component_by_class(unreal.LightComponent)
        if comp is None:
            continue
        lc = comp.get_editor_property("light_color")
        row = {"label": lab, "class": a.get_class().get_name(), "loc": _v(a.get_actor_location()),
               "radius": _radius(comp),
               "color": [lc.r / 255.0, lc.g / 255.0, lc.b / 255.0, lc.a / 255.0]}
        if lab.startswith(CEILING_PREFIX % key):
            row["role"] = "ceiling"
            # worst case: the lattice LANDED low (hangar_build.py:121, 501: fly_z - lattice_fly; glow at +11 cm)
            z_low = float(live_box["dock_z"]) + float(live_box["lattice_z"]) + 11.0
            row["reach"] = glow_reach({"x": row["loc"][0], "y": row["loc"][1], "z": z_low}, row["radius"] or 0.0,
                                      float(live_box["dock_z"]), her_box_world)
        else:
            row["role"] = "black"
        rows.append(row)
    return rows


def _live_box(key, args):
    """The LIVE interior from the walls (dock-local), not the 30 Sep record (memory: compose against the live root)."""
    h = (args.get("hookin_hangars") or {}).get(key) or {}
    root = _by_label("S%s Hangar Root" % key)
    entry = _by_label(args["scenes"][key]["entry_camera"])
    if len(root) != 1 or len(entry) != 1:
        raise PlanError("BOX_ANCHORS: root %d entry %d" % (len(root), len(entry)))
    ec = _camera_actor_facts(entry[0])
    dock = {"loc": [ec["loc"][0], ec["loc"][1], 0.0], "yaw": ec["rot"][2]}
    out = {"dock": dock, "dock_z": 0.0, "lattice_z": float(h.get("lattice_z", 1200.0))}
    rl = to_local(dock, _v(root[0].get_actor_location()))
    out["apron"] = rl[0]
    walls = {}
    for k2, lab in WALL_LABELS.items():
        w = _by_label(lab % key)
        if len(w) == 1:
            o, e = w[0].get_actor_bounds(False)
            walls[k2] = [to_local(dock, [o.x - e.x, o.y - e.y, o.z - e.z]), to_local(dock, [o.x + e.x, o.y + e.y, o.z + e.z])]
    if "far_wall" not in walls:
        # 7 Oct live: hangar_exit_doors.py split the far wall into Left/Right of Exit + Above Exit (+ Exit Door Leaf)
        parts = []
        for lab in ("S%s Hangar Far Wall Left of Exit", "S%s Hangar Far Wall Right of Exit",
                    "S%s Hangar Far Wall Above Exit", "S%s Hangar Exit Door Leaf"):
            for w in _by_label(lab % key):
                o, e = w.get_actor_bounds(False)
                parts.append([to_local(dock, [o.x - e.x, o.y - e.y, o.z - e.z]),
                              to_local(dock, [o.x + e.x, o.y + e.y, o.z + e.z])])
        if parts:
            walls["far_wall"] = [[min(p[0][i] for p in parts) for i in range(3)],
                                 [max(p[1][i] for p in parts) for i in range(3)]]
    if set(walls) != set(WALL_LABELS):
        raise PlanError("BOX_WALLS: found %s" % sorted(walls))
    # dock yaw is 0 for S1/S4 [meas klara_hookin_args.json]; bounds are axis-aligned, so only yaw 0 is exact here
    if abs(wrap(dock["yaw"])) > 0.01:
        raise PlanError("BOX_DOCK_YAW_NONZERO: %r (live box read assumes yaw 0)" % dock["yaw"])
    out["half_w"] = min(abs(max(walls["left_wall"][0][1], walls["left_wall"][1][1])),
                        abs(min(walls["right_wall"][0][1], walls["right_wall"][1][1])))
    out["depth"] = min(walls["far_wall"][0][0], walls["far_wall"][1][0]) - out["apron"]
    out["height"] = max(walls["left_wall"][0][2], walls["left_wall"][1][2])
    out["walls_local"] = walls
    return out, ec


def _streaming_level(world, pkg):
    ls = unreal.GameplayStatics.get_streaming_level(world, unreal.Name(pkg))       # [inf] probed
    if ls is None:
        raise PlanError("STREAMING_LEVEL_NOT_FOUND: %s" % pkg)
    return ls


def _footprint_rows(world, pkg):
    rows = []
    for a in _level_actors(world, pkg):
        o, e = a.get_actor_bounds(False)
        comps = sorted({c.get_class().get_name() for c in a.get_components_by_class(unreal.PrimitiveComponent)})
        rows.append({"label": str(a.get_actor_label()), "class": a.get_class().get_name(), "components": comps,
                     "bounds": [o.x, o.y, o.z, e.x, e.y, e.z]})
    return rows


def _hookin_bindings(seq):
    rows = []
    for b in seq.get_bindings():
        n = str(b.get_display_name())
        if n.startswith(HOOK_OURS) or n.startswith(HOOK_HERS):
            for t in b.get_tracks():
                for s in t.get_sections():
                    rows.append({"name": n, "range": [int(s.get_start_frame()), int(s.get_end_frame())]})
    for t in seq.get_tracks():
        if str(t.get_display_name()) == HOOK_VIS:
            for s in t.get_sections():
                rows.append({"name": HOOK_VIS, "range": [int(s.get_start_frame()), int(s.get_end_frame())]})
    return sorted(rows, key=lambda r: r["name"])


def _cuts(seq):
    tracks = [t for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneCameraCutTrack)]
    if len(tracks) != 1:
        raise PlanError("ROOT_CUT_TRACKS: %d" % len(tracks))
    rows = []
    for s in tracks[0].get_sections():
        guid = unreal.GuidLibrary.conv_guid_to_string(s.get_camera_binding_id().get_editor_property("guid"))
        name = [str(b.get_display_name()) for b in seq.get_bindings() if unreal.GuidLibrary.conv_guid_to_string(b.get_id()) == guid]
        rows.append({"guid": guid, "camera": name[0] if name else None, "range": [int(s.get_start_frame()),
                                                                                    int(s.get_end_frame())],
                     "active": bool(s.is_active())})
    return sorted(rows, key=lambda r: r["range"][0]), tracks[0]


def _land(seq, key):
    """Live land frame: reuse the hookin's record values only as a cross-check; read the Arrival's timing."""
    arr = _by_label("S%s Arrival" % key)
    if len(arr) != 1:
        raise PlanError("ARRIVAL_COUNT: %d" % len(arr))
    t = arr[0].get_editor_property("hangar_timing")
    drives = [str(d.get_editor_property("target")) for d in arr[0].get_editor_property("pre_scene_float_drives")]
    return {"land_s_transient": float(t.get_editor_property("land_seconds")),
            "strike_after_land_s": float(t.get_editor_property("strike_after_land_seconds")),
            "pre_scene_float_drives": drives}


_INTERP = {"RCIM_CUBIC": "cubic", "RCIM_LINEAR": "linear", "RCIM_CONSTANT": "constant"}


def _enum_name(v):
    return str(getattr(v, "name", v)).split(".")[-1]


def _lattice_facts(seq, key, fps):
    """The rise sub-section in the Scene + the rise's S<n> Hangar Lattice Fly Location.Z keys WITH tangents
    (MovieSceneScriptingDoubleKey get_* [inf, probed]). Read only."""
    hits = [sct for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) for sct in t.get_sections()
            if sct.get_sequence() is not None and RISE_MARK in _path(sct.get_sequence())]
    if len(hits) != 1:
        raise PlanError("RISE_SUBSECTION_COUNT: %d" % len(hits))
    sec = hits[0]
    rise = sec.get_sequence()
    prm = sec.get_editor_property("parameters")
    off = int(prm.get_editor_property("start_frame_offset").value)
    rate = 1.0
    try:
        ts = prm.get_editor_property("time_scale")
        rate = float(ts) if isinstance(ts, (int, float)) else float(ts.get_editor_property("play_rate"))
    except Exception:  # noqa: BLE001 - 5.8 time-warp struct: reported, rate assumed 1 [inf]
        rate = 1.0
    rres, rfps = _rate(rise.get_tick_resolution()), _rate(rise.get_display_rate())
    lower = int(round(rise.get_playback_start() * rres / rfps))
    b = [x for x in rise.get_bindings() if str(x.get_display_name()) == LATTICE_FLY % key]
    if len(b) != 1:
        raise PlanError("LATTICE_BINDING_COUNT: %d" % len(b))
    secs = [x for t in b[0].get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack) for x in t.get_sections()]
    if len(secs) != 1:
        raise PlanError("LATTICE_SECTIONS: %d" % len(secs))
    z = _chan_map(secs[0]).get("Location.Z")
    if z is None:
        raise PlanError("LATTICE_NO_LOCATION_Z")
    keys = []
    for k in z.get_keys():
        row = {"tick": int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
               "value": float(k.get_value()), "interp": _INTERP.get(_enum_name(k.get_interpolation_mode()))}
        row["tangent_mode"] = _enum_name(k.get_tangent_mode())
        row["arrive"], row["leave"] = float(k.get_arrive_tangent()), float(k.get_leave_tangent())
        try:
            row["weighted"] = _enum_name(k.get_tangent_weight_mode()) != "RCTWM_WEIGHTED_NONE"
            row["arrive_w"], row["leave_w"] = float(k.get_arrive_tangent_weight()), float(k.get_leave_tangent_weight())
        except Exception:  # noqa: BLE001
            row["weighted"] = None
        keys.append(row)
    return {"rise": _path(rise), "section": [int(sec.get_start_frame()), int(sec.get_end_frame())],
            "start_offset_tick": off, "play_rate": rate, "rise_tick": rres, "rise_lower_tick": lower,
            "offset_ticks": rise_offset_ticks(sec.get_start_frame(), fps, _rate(seq.get_tick_resolution()), lower, off,
                                              rres, rate),
            "keys": keys, "section_active": bool(sec.is_active())}


def gather(args, world, run):
    key = str(args["scene"])
    row = args["scenes"][key]
    seq = unreal.load_asset(row["scene_sequence"])
    copy = unreal.load_asset(row["copy"])
    if seq is None or copy is None:
        raise PlanError("ASSETS: scene %s copy %s" % (seq is not None, copy is not None))
    fps = _rate(seq.get_display_rate())
    seqrec = load_json(os.path.join(_here(), "klara_hookin_seq_record.json"))["scenes"][key]
    tl_h = seqrec["plan"]["timeline"]
    L, C, E = int(tl_h["level_visible"][0]), int(tl_h["cinematic"][0]), int(tl_h["cinematic"][1])
    facts = {"scene": key, "fps": fps, "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
             "L": L, "C": C, "E": E, "hookin_record_timeline": tl_h}
    sub = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) for s in t.get_sections()
           if s.get_sequence() is not None and _path(s.get_sequence()) == row["copy"]]
    if len(sub) != 1:
        raise PlanError("SLOT_SECTION_COUNT: %d" % len(sub))
    facts["slot_live"] = [int(sub[0].get_start_frame()), int(sub[0].get_end_frame()), bool(sub[0].is_active())]
    facts["slot_offset_tick_live"] = int(sub[0].get_editor_property("parameters")
                                         .get_editor_property("start_frame_offset").value)
    if facts["slot_live"][:2] != [C, E] or facts["slot_offset_tick_live"] != 0:
        raise PlanError("SLOT_DRIFT: live %s offset %d vs hookin record [%d, %d] offset 0 (a reveal still applied? "
                        "REVERT it first)" % (facts["slot_live"], facts["slot_offset_tick_live"], C, E))
    facts["arrival"] = _land(seq, key)
    box, entry = _live_box(key, args)
    facts["box"], facts["entry_camera"] = box, entry
    facts["exit_camera"] = _camera_actor_facts(_one(row["exit_camera"], run))
    facts["her_first"] = _her_camera(copy, "first")
    facts["her_last"] = _her_camera(copy, "last")
    her_actors = _level_actors(world, row["level"])
    cam_pool = list(her_actors)
    for pkg in row.get("other_levels") or []:          # S4: LS_Children also binds into L_Animals [meas census_report.md:39]
        cam_pool += _level_actors(world, pkg)
    for which in ("her_first", "her_last"):
        cams = [a for a in cam_pool if str(a.get_actor_label()) == facts[which]["binding"]
                or str(a.get_name()) == facts[which]["binding"]]
        facts[which]["actor"] = _camera_actor_facts(cams[0]) if len(cams) == 1 else None
        if len(cams) != 1:
            facts.setdefault("refusals", []).append("HER_CAMERA_ACTOR_%s: %d match %r" % (which.upper(), len(cams),
                                                                                        facts[which]["binding"]))
    fp = footprint_from_rows(_footprint_rows(world, row["level"]), float(args.get("footprint_max_size_cm", 4000.0)))
    facts["footprint"] = {"box": fp["box"], "kept_count": len(fp["kept"]), "kept": fp["kept"], "excluded": fp["excluded"]}
    facts["set_world"] = fp["box"]
    ls = _streaming_level(world, row["level"])
    lt = ls.get_editor_property("level_transform")
    facts["level_transform"] = {"loc": _v(lt.translation), "yaw": float(lt.rotation.rotator().yaw)}
    sb = _bindings_by_name(copy)
    her_lo, her_last = int(copy.get_playback_start()), int(copy.get_playback_end()) - 1
    facts["her_range"] = [her_lo, her_last + 1]
    her_fps = _rate(copy.get_display_rate())
    tpf = _rate(copy.get_tick_resolution()) / her_fps
    facts["her_fps"], facts["her_tpf"] = her_fps, tpf
    facts["her_lights"] = _light_rows(her_actors, sb, her_lo, her_last, tpf)
    facts["her_env"] = _env_rows(her_actors, sb, her_lo, her_last, tpf)
    _gather_lit(facts, copy, cam_pool, args, fps)
    facts["her_audio"] = [{"sound": _path(a.get_sound()), "active": bool(a.is_active()),
                           "start_frame": int(a.get_start_frame()), "end_frame": int(a.get_end_frame())}
                          for t in copy.get_tracks() if isinstance(t, unreal.MovieSceneAudioTrack)
                          for a in t.get_sections()]                                  # klara_hookin.py:718-720 [prec]
    facts["scene_audio"] = [{"track": str(t.get_display_name()), "sound": _path(a.get_sound()),
                             "active": bool(a.is_active()), "range": [int(a.get_start_frame()), int(a.get_end_frame())]}
                            for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneAudioTrack)
                            for a in t.get_sections()]
    try:                                                                              # curtain_sleight.py:1297-1299 [prec]
        facts["scene_markers"] = [{"label": str(m.get_editor_property("label")),
                                   "frame": int(m.get_editor_property("frame_number").value)}
                                  for m in seq.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)]
    except Exception as exc:  # noqa: BLE001 - reported, not a refusal
        facts["scene_markers"] = []
        facts["scene_markers_error"] = "%s: %s" % (type(exc).__name__, exc)
    facts["hangar_lights"] = _hangar_lights(key, box, None)
    facts["rig_bulbs"] = sorted(str(a.get_actor_label()) for a in _actors()
                                if str(a.get_actor_label()).startswith(BULB_PREFIX % key))
    facts["lattice_pieces"] = sorted(str(a.get_actor_label()) for a in _actors()
                                     if str(a.get_actor_label()).startswith(LATTICE_PREFIX % key)
                                     or str(a.get_actor_label()).startswith(CEILING_PREFIX % key))
    facts["tick"] = _rate(seq.get_tick_resolution())
    try:
        facts["lattice"] = _lattice_facts(seq, key, fps)
    except Exception as exc:  # noqa: BLE001 - a missing API / shape is a finding, the plan refuses on it
        facts["lattice"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    facts["hookin_bindings"] = _hookin_bindings(seq)
    facts["cuts"], _t = _cuts(seq)
    facts["copy_bindings_unresolved"] = []
    names = set()
    for pkg in [row["level"]] + list(row.get("other_levels") or []):
        for a in _level_actors(world, pkg):
            names.add(str(a.get_actor_label()))
            names.add(str(a.get_name()))
    for b in copy.get_bindings():
        parent = b.get_parent()
        if parent is not None and hasattr(parent, "is_valid") and parent.is_valid():
            continue
        if str(b.get_display_name()) not in names:
            facts["copy_bindings_unresolved"].append(str(b.get_display_name()))
    rig = [a for a in _actors() if a.get_class().get_name() == "InfinityStageCelestialRig"]
    facts["rig_exempt"] = [str(x) for x in rig[0].get_editor_property("foreign_lighting_exempt_levels")] if rig else None
    return facts, seq, copy


def _gather_lit(facts, copy, cam_pool, args, scene_fps):
    """v3: her lit frame (pure find_lit_frame + snap) and every value the plan needs AT it: camera pose + lens (the cut
    covering it), each light's Intensity / LightColor, each env property. Detection problems become refusals."""
    lit = detect_lit(facts, args, scene_fps)
    facts["lit"] = lit
    Lh = lit["frame"]
    if Lh is None or not lit.get("v3", True):
        return
    try:
        facts["her_lit"] = _her_camera(copy, "lit", Lh, facts["her_tpf"])
    except PlanError as exc:
        lit["refusals"].append(str(exc))
        return
    cams = [a for a in cam_pool if str(a.get_actor_label()) == facts["her_lit"]["binding"]
            or str(a.get_name()) == facts["her_lit"]["binding"]]
    facts["her_lit"]["actor"] = _camera_actor_facts(cams[0]) if len(cams) == 1 else None
    if len(cams) != 1:
        lit["refusals"].append("HER_CAMERA_ACTOR_LIT: %d match %r" % (len(cams), facts["her_lit"]["binding"]))
    apply_lit_values(facts, Lh)


def detect_lit(facts, args, scene_fps):
    """Pure: her lit frame from facts["her_lights"][*]["curves"]["Intensity"], snapped onto our grid."""
    cfg = lit_cfg(args)
    lo, hi = facts["her_range"]
    if not cfg.get("enabled", True):
        return {"method": "disabled (v2: her first frame)", "frame": lo, "frame_raw": lo, "refusals": [],
                "warnings": [], "v3": False}
    curves = {r["label"]: (r.get("curves") or {}).get("Intensity") for r in facts["her_lights"]}
    lit = find_lit_frame(curves, lo, hi, facts["her_fps"], cfg)
    lit["frame"] = None
    if lit["frame_raw"] is not None:
        try:
            lit["frame"], lit["snap_step"] = snap_her_frame(lit["frame_raw"], lo, facts["her_fps"], scene_fps)
        except PlanError as exc:
            lit["refusals"].append(str(exc))
    if lit["frame"] is not None:
        lit["s_into_her"] = (lit["frame"] - lo) / float(facts["her_fps"])
        lit["her_time_s"] = lit["frame"] / float(facts["her_fps"])
    return lit


def apply_lit_values(facts, Lh):
    """Pure: every light's / env row's value at her lit frame Lh from its kept curve (unkeyed -> level value)."""
    for r in facts["her_lights"]:
        c = (r.get("curves") or {}).get("Intensity")
        r["target_lit"] = float(curve_at(c, Lh)) if c and c.get("keys") else float(r["intensity"])
        cc = (r.get("curves") or {}).get("LightColor")
        r["color_lit"] = [float(curve_at(x, Lh)) for x in cc] if cc else None
    for e in facts["her_env"]:
        c = e.get("curve")
        if e.get("property") is not None:
            e["value_lit"] = float(curve_at(c, Lh)) if c and c.get("keys") else float(e["value"])


def build_plan(facts, args):
    """facts (plain data) -> the full plan. Pure: the harness drives it with recorded/synthetic facts."""
    key, fps = facts["scene"], float(facts["fps"])
    refusals, warnings = list(facts.get("refusals") or []), []
    box, entry = facts["box"], facts["entry_camera"]
    dock = box["dock"]
    first, last = facts["her_first"], facts["her_last"]
    pl = args["placement"]
    if not facts.get("set_world"):
        refusals.append("DIORAMA_FOOTPRINT_EMPTY (see footprint.excluded)")
        return {"scene": key, "refusals": refusals, "warnings": warnings, "apply_ready": False}
    # v3: everything the intro settles to is HER LIT FRAME Lh (Gary 7 Oct "Strike to her lit look; skip her dark
    # opening"); lit.enabled false = v2 (her first frame, no skip)
    cfg_lit = lit_cfg(args)
    v3 = bool(cfg_lit.get("enabled", True))
    lit = dict(facts.get("lit") or {})
    her_lo, her_hi = (facts.get("her_range") or [None, None])[:2]
    refusals += list(lit.get("refusals") or [])
    warnings += list(lit.get("warnings") or [])
    if v3:
        anchor = facts.get("her_lit")
        if lit.get("frame") is None or not anchor:
            refusals.append("LIT_FRAME_UNKNOWN: frame %r, camera at it %s" % (lit.get("frame"), bool(anchor)))
            return {"scene": key, "refusals": refusals, "warnings": warnings, "apply_ready": False, "lit": lit}
        if int(anchor.get("frame")) != int(lit["frame"]):
            refusals.append("LIT_CAMERA_FRAME_MISMATCH: camera read at %r, lit frame %r" % (anchor.get("frame"),
                                                                                         lit["frame"]))
        missing = [r["label"] for r in facts["her_lights"] if "target_lit" not in r]
        if missing:
            refusals.append("LIT_VALUES_MISSING: %s (apply_lit_values not run)" % missing)
        Lh = int(lit["frame"])
    else:
        anchor = first
        Lh = her_lo
    place = solve_placement(anchor["loc"], facts["set_world"][:4], facts["set_world"][5] - dock["loc"][2], dock, box,
                            pl["lead_cm"], pl.get("x_min_local", box["apron"]), pl["side_margin_cm"],
                            lead_max_cm=pl.get("lead_max_cm"))
    if not place["checks"]["lead_in_range"]:
        warnings.append("LEAD_ABOVE_RANGE: her first camera must sit %.0f cm in (> lead_max %.0f) to keep her set past "
                        "the hinge x %.0f" % (place["lead_cm"], pl.get("lead_max_cm"), pl.get("x_min_local", box["apron"])))
    d = place["delta"]
    sh = lambda p: [p[0] + d[0], p[1] + d[1], p[2] + d[2]]
    new_lt = {"loc": sh(facts["level_transform"]["loc"]), "yaw": facts["level_transform"]["yaw"]}
    if abs(wrap(new_lt["yaw"])) > 1e-6:
        refusals.append("LEVEL_YAW_NONZERO: %r (translation-only copy shift)" % new_lt["yaw"])
    set_after = [facts["set_world"][0] + d[0], facts["set_world"][1] + d[0], facts["set_world"][2] + d[1],
                 facts["set_world"][3] + d[1], facts["set_world"][4], facts["set_world"][5]]
    proposal = propose_hangar(place["set_local_after"], facts["set_world"][5] - dock["loc"][2],
                              {"apron": box["apron"], "depth": box["depth"], "half_w": box["half_w"],
                               "height": box["height"], "lattice_z": box["lattice_z"]}, args.get("comfort_cm", 300.0))
    # Gary 7 Oct: the hangar is arbitrary. Plan footprint must fit the LIVE box (else STOP with the proposal); a set
    # reaching the lattice proceeds only under allow_lattice_overlap.
    ck = place["checks"]
    if not (ck["near_ok"] and ck["far_ok"] and ck["side_ok"] and ck["under_roof"]):
        refusals.append("SET_DOES_NOT_FIT_LIVE_BOX: %s -> Structure resize with hangar_proposal.params %s"
                        % ({k: v for k, v in ck.items() if not v}, proposal["params"]))
    if not ck["under_lattice"]:
        msg = "SET_REACHES_LATTICE: top %.0f cm vs lattice %.0f cm" % (facts["set_world"][5] - dock["loc"][2],
                                                                     box["lattice_z"])
        if args.get("allow_lattice_overlap"):
            warnings.append(msg + " (allow_lattice_overlap)")
        else:
            refusals.append(msg + " -> set allow_lattice_overlap or resize (hangar_proposal.params %s)" % proposal["params"])
    # lenses: the glide camera takes HER filmback, so its end frame is hers; its start focal matches the Entry HFOV
    her_cam_actor = first.get("actor") or {}
    sensor = her_cam_actor.get("sensor") or entry["sensor"]
    if abs(sensor[0] / sensor[1] - entry["sensor"][0] / entry["sensor"][1]) > 0.01:
        warnings.append("SENSOR_ASPECT_DIFFERS: entry %s vs hers %s (vertical framing changes across the glide)"
                        % (entry["sensor"], sensor))

    def lens_of(cam):
        lt = cam.get("lens_tracks") or {}
        a = cam.get("actor") or {}
        return (lt.get("CurrentFocalLength", a.get("focal")),
                lt.get("ManualFocusDistance", lt.get("FocusSettings.ManualFocusDistance", a.get("focus"))))

    f1, fo1 = lens_of(anchor)
    fL, foL = lens_of(last)
    if f1 is None or fL is None:
        refusals.append("HER_LENS_UNKNOWN: first %r last %r" % (f1, fL))
        f1, fL = f1 or 35.0, fL or 35.0
    start_pose = {"loc": entry["loc"], "rot": entry["rot"], "focal": equiv_focal(entry["focal"], entry["sensor"][0], sensor[0]),
                  "focus": entry["focus"]}
    first_pose = {"loc": sh(anchor["loc"]), "rot": anchor["rot"], "focal": f1, "focus": fo1 or entry["focus"]}
    # (v3: first_pose IS her pose at Lh - the glide's end and the held frame until the cut)
    last_pose = {"loc": sh(last["loc"]), "rot": last["rot"], "focal": fL, "focus": foL or entry["focus"]}
    ex = facts["exit_camera"]
    exit_pose = {"loc": ex["loc"], "rot": ex["rot"], "focal": equiv_focal(ex["focal"], ex["sensor"][0], sensor[0]),
                 "focus": ex["focus"]}
    lights = order_lights([{"label": r["label"], "loc": sh(r["loc"]), "row": r} for r in facts["her_lights"]],
                          first_pose["loc"], args["intro"]["order"])
    exit_len = int(args["outro"].get("exit_cut_frames", 25))
    vmax = float(args["intro"].get("max_glide_speed_cm_s", 300.0))
    # v2: the glide ends in the DARK and holds on her first pose before anything lights, so it ends at rest
    gin_s, gin_peak = glide_seconds(start_pose, first_pose, fps, [0.0, 0.0, 0.0], vmax, args["intro"]["glide_s"])
    her_v = math.sqrt(sum(v * v for v in anchor["vel_cm_s"]))
    if her_v > 5.0:
        warnings.append("HER_%s_FRAME_MOVES: %.1f cm/s - the held camera steps into her motion at the cut"
                        % ("LIT" if v3 else "FIRST", her_v))
    # the slot starts INTO her copy at Lh (v3); her opening never plays and everything after the slot comes earlier
    if v3:
        sk = slot_skip(her_lo, her_hi, Lh, facts["her_fps"], fps, facts["her_tpf"], facts["E"] - facts["C"])
        refusals += sk["refusals"]
    else:
        sk = {"skip_frames": 0, "offset_ticks": 0, "her_frame": her_lo, "refusals": []}
    tgt = (lambda r: r.get("target_lit", r["target_first"])) if v3 else (lambda r: r["target_first"])
    min_v = float(cfg_lit["min_value"])
    gout_s, gout_peak = glide_seconds(last_pose, exit_pose, fps, [0.0, 0.0, 0.0], vmax, args["outro"]["glide_s"])
    if gin_s is None or gout_s is None:
        refusals.append("GLIDE_TOO_FAST: no glide <= 40 s keeps peak <= %.0f cm/s (in %r, out %r)" % (vmax, gin_peak,
                                                                                                        gout_peak))
        gin_s, gout_s = gin_s or args["intro"]["glide_s"], gout_s or args["outro"]["glide_s"]
    n_strike = sum(1 for x in lights if tgt(x["row"]) > min_v)
    tl = plan_timeline(facts["L"], facts["C"], facts["E"], fps, n_strike, args, exit_len, gin_s, gout_s,
                       skip=sk["skip_frames"] if not sk["refusals"] else 0)
    tl["glide_in_s"], tl["glide_out_s"] = gin_s, gout_s
    refusals += tl["refusals"]
    warnings += tl["warnings"]
    plan = {"scene": key, "fps": fps, "placement": place, "level_transform_before": facts["level_transform"],
            "level_transform_after": new_lt, "set_world_after": set_after, "hangar_proposal": proposal,
            "timeline": tl, "refusals": refusals, "warnings": warnings, "sensor_mm": sensor,
            "poses": {"entry": start_pose, "her_lit": first_pose, "her_first": first_pose if not v3 else
                      {"loc": sh(first["loc"]), "rot": first["rot"], "focal": lens_of(first)[0],
                       "focus": lens_of(first)[1]}, "her_last": last_pose, "exit": exit_pose},
            "lit": dict(lit, v3=v3, camera={k: anchor.get(k) for k in ("binding", "frame", "cut", "loc", "rot",
                                                                         "lens_tracks", "vel_cm_s", "ang_deg_s")},
                        camera_after_move=first_pose, slot=sk)}
    if tl["refusals"]:
        return plan
    seed = "%s|S%s" % (args["intro"]["seed"], key)
    sch = schedule(n_strike, tl["strike_window"][0], tl["strike_window"][1], fps, seed, args["intro"]["gap_s"],
                   args["intro"]["min_gap_s"])
    refusals += sch["refusals"]
    warnings += sch["warnings"]
    rows = []
    i_strike = 0
    for lt_row in lights:
        r = lt_row["row"]
        target = float(tgt(r))
        strikes = target > min_v
        f_in = None
        if strikes:
            f_in = sch["frames"][i_strike] if i_strike < len(sch["frames"]) else None
            i_strike += 1
        # v3: a light that is dark at Lh is held at 0 over [land, cut) (no strike; her copy takes it from the cut)
        if not strikes:
            intro = [[tl["land"], 0.0]]
        elif f_in is None:
            intro = None
        else:
            intro = dedupe_keys([[tl["land"], 0.0]] + strike_keys(target, f_in, seed, r["label"], fps,
                                                                  args["intro"]["flicker_window_s"]))
        color_lit = r.get("color_lit") if v3 else None
        rows.append({"label": r["label"], "class": r["class"], "dist_cm": math.dist(lt_row["loc"], first_pose["loc"]),
                     "strike_frame": f_in, "strike_s": None if f_in is None else f_in / fps,
                     "strikes": strikes, "target_intro": target, "target_first": r["target_first"],
                     "target_lit": r.get("target_lit"), "target_last": r["target_last"],
                     "her_keys": sorted(r["keyed"]), "color_first": r["first"].get("LightColor"),
                     "color_last": r["last"].get("LightColor"), "color_lit": color_lit,
                     "intro_color": None if color_lit is None else {"range": [tl["land"], tl["cut"]], "rgba": color_lit},
                     "intro_keys": intro, "warn_hidden": r["hidden_in_game"] or not r["visible"]})
    if v3 and n_strike == 0:
        refusals.append("NO_LIGHT_LIT_AT_LIT_FRAME: %d (detection must be wrong; see lit.per_light)" % Lh)
    out_sch = schedule(len(rows), tl["blink_window"][0],
                       tl["blink_window"][1] - int(math.ceil(args["outro"]["flicker_window_s"] * fps)) - 1, fps,
                       seed + "|out", args["outro"]["blink_gap_s"], 1.0 / fps)
    refusals += out_sch["refusals"]
    for j, r in enumerate(reversed(rows)):
        f_out = out_sch["frames"][j] if j < len(out_sch["frames"]) else None
        r["blink_frame"] = f_out
        r["outro_keys"] = None if f_out is None else dedupe_keys(
            [[tl["slot"][1], r["target_last"]]] + blink_out_keys(r["target_last"], f_out, seed, r["label"], fps,
                                                              args["outro"]["flicker_window_s"]))
    plan["her_lights"] = rows
    plan["strike_schedule"] = sch
    # environment crossfade (0 -> her value at her FIRST frame) and fade-out (value at her LAST frame -> 0)
    env = []
    for e in facts["her_env"]:
        if e.get("property") is None:
            env.append(dict(e, action="visible_from_G0 (no intensity)"))
            continue
        v = e["value"]
        v_in = float(e.get("value_lit", v)) if v3 else v
        env.append(dict(e, action="ramp", target_intro=v_in,
                        intro=ramp_keys(0.0, v_in, tl["crossfade"][0], tl["crossfade"][1]),
                        outro=ramp_keys(v, 0.0, tl["env_out"][0], tl["env_out"][1])))
        if e.get("her_keyed"):
            warnings.append("ENV_KEYED_BY_HER: %s %s (crossfade targets %s; the outro still fades from the LEVEL value)"
                            % (e["label"], e["property"], "her value at Lh %.4g" % v_in if (v3 and e.get("curve"))
                               else "the LEVEL value - her curve was not readable"))
        if e["class"] == "PostProcessVolume":
            ours = [h for h in facts.get("our_ppv") or []]
            if not any(e["exposure_overrides"].values()):
                warnings.append("HER_PPV_NO_EXPOSURE_OVERRIDE: %s - our pinned EV100 (hangar_build.py:451-454) stays "
                                "in force inside the hangar volume" % e["label"])
            if not e["unbound"]:
                warnings.append("HER_PPV_BOUNDED: %s - only applies inside its own box" % e["label"])
            for o in ours:
                if e["priority"] <= o["priority"]:
                    warnings.append("PPV_PRIORITY: hers %.1f <= ours %.1f (%s) - Look decision" % (e["priority"],
                                                                                                 o["priority"], o["label"]))
    plan["her_env"] = env
    # our hangar lights: non-ceiling black all Scene; ceiling glows fade OUT before her first strike, stay out through
    # the slot, and (outro) come back only after her lights and env are out (Gary 7 Oct)
    hl = []
    for h in facts["hangar_lights"]:
        if h["role"] == "ceiling":
            c = list(h.get("color") or [1.0, 1.0, 1.0, 1.0])
            keys = [[tl["glow_fade"][0], c], [tl["glow_fade"][1], [0.0, 0.0, 0.0, c[3]]]]
            if tl["rig_back"]:
                keys += [[tl["rig_back"][0], [0.0, 0.0, 0.0, c[3]]], [tl["rig_back"][1], c]]
            rng = [tl["glow_fade"][0], (tl["rig_back"][1] + 1) if tl["rig_back"] else tl["planned_end"]]
            hl.append(dict(h, action="fade_color", range=rng, color_keys=keys))
        else:
            hl.append(dict(h, action="black_color", range=[0, tl["planned_end"]]))
    plan["hangar_lights"] = hl
    bulbs = list(facts.get("rig_bulbs") or [])
    plan["rig_bulbs_hidden"] = {"labels": bulbs, "range": tl["rig_dark"]}
    if bulbs:
        warnings.append("BULB_EMISSIVE_POPS: %d bulb meshes hide at frame %d (glows already at 0; emissive cannot fade "
                        "without a material track)" % (len(bulbs), tl["rig_dark"][0]))
    # the ceiling rig must not lower (Gary 7 Oct)
    lat = facts.get("lattice") or {}
    mode = args.get("lattice", "cancel")
    plan["lattice"] = {"mode": mode, "facts": {k: v for k, v in lat.items() if k != "keys"}}
    if mode == "cancel":
        if lat.get("error"):
            refusals.append("LATTICE_CANCEL_UNAVAILABLE: %s (set lattice 'hide' or decide)" % lat["error"])
        elif lat.get("keys"):
            try:
                ck = cancel_keys(lat["keys"], lat["offset_ticks"])
                plan["lattice"].update(cancel=ck, range=[0, tl["planned_end"]])
                tpf = float(facts.get("tick", 24000.0)) / fps
                plan["lattice"]["lowers_scene_frames"] = [ck["span_ticks"][0] / tpf, ck["span_ticks"][1] / tpf]
            except PlanError as exc:
                refusals.append(str(exc))
        else:
            refusals.append("LATTICE_FACTS_MISSING")
    elif mode == "hide":
        plan["lattice"]["hide"] = {"labels": list(facts.get("lattice_pieces") or []) + bulbs,
                                   "range": [tl["rig_dark"][0], tl["planned_end"]]}
        warnings.append("LATTICE_HIDE: the rig still lowers, unseen; no rig glow in the outro")
    # glide camera keys
    gi = plan_glide(start_pose, first_pose, tl["glide_in"][0], tl["glide_in"][1], fps,
                    v0=[0.0, 0.0, 0.0], v1=[0.0, 0.0, 0.0])
    go = plan_glide(last_pose, exit_pose, tl["glide_out"][0], tl["glide_out"][1], fps,
                    v0=[0.0, 0.0, 0.0], v1=[0.0, 0.0, 0.0])
    keys = dedupe_keys(gi["keys"] + hold_keys(first_pose, [tl["cut"], tl["slot"][1] - 1]) +
                       hold_keys(last_pose, [tl["slot"][1], tl["glide_out"][0] - 1]) + go["keys"])
    plan["glide"] = {"in": gi["report"], "out": go["report"], "keys": keys,
                     "camera_label": args["scenes"][key]["glide_camera_label"]}
    for g, nm in ((gi["report"], "in"), (go["report"], "out")):
        if g["overshoot"]:
            warnings.append("GLIDE_%s_OVERSHOOT: %s" % (nm.upper(), g["overshoot"]))
    # roof / walls
    cam_l = to_local(dock, first_pose["loc"])
    rot_l = [first_pose["rot"][0], first_pose["rot"][1], wrap(first_pose["rot"][2] - dock["yaw"])]
    sl = place["set_local_after"]
    seen = surfaces_seen(cam_l, rot_l, hfov_deg(first_pose["focal"], sensor[0]), sensor[0] / sensor[1], box,
                         [sl[0], sl[1], sl[2], sl[3], 0.0, facts["set_world"][5] - dock["loc"][2]])
    plan["first_frame_sees"] = seen
    hide = []
    if args["roof"] in ("hide_roof", "hide_roof_and_seen_walls"):
        hide += [x % key for x in ROOF_LABELS]
    if args["roof"] == "hide_roof_and_seen_walls":
        hide += [WALL_LABELS[w] % key for w in ("left_wall", "right_wall", "far_wall") if seen.get(w)]
    elif any(seen.get(w) for w in ("left_wall", "right_wall", "far_wall")):
        warnings.append("FIRST_FRAME_SEES_WALLS: %s (roof option %r keeps them)" % (seen, args["roof"]))
    plan["hide"] = {"labels": hide, "range": tl["roof_hidden"]}
    # cuts: Entry [0, d0) | Glide [d0, X) | Exit [X, end) (X = glide_out end; relength FIRST)
    plan["cuts_after"] = [["entry", [0, tl["glide_in"][0]]], ["glide", [tl["glide_in"][0], tl["exit_cut"][0]]],
                          ["exit", tl["exit_cut"]]]
    plan["hookin_edits"] = {"hers_dark_range": tl["hers_dark"], "ours_off_range": [tl["ours_hidden_from"], tl["planned_end"]],
                            "level_visible_range": [tl["land"], tl["planned_end"]]}
    plan["extend_mode"] = {"scene_label": facts.get("label"), "new_end_s": round(tl["planned_end"] / fps, 6),
                           "dry_run": True}
    if facts["playback"][1] != tl["planned_end"]:
        plan["relength_first"] = True
    plan["slot"] = {"mode": args["slot"], "range": tl["slot"], "range_before": tl["slot_before"],
                    "shift": tl["slot_shift"], "skip_frames": tl["slot_skip"], "her_frame_at_cut": Lh,
                    "start_offset_ticks": sk["offset_ticks"], "her_range": [her_lo, her_hi],
                    "media_track_note": "later: a MovieSceneMediaTrack section over the same range replaces the "
                                        "nested copy 1:1 (videos = renders of her LS, Gary 7 Oct)"}
    plan["audio"] = audio_report(facts.get("her_audio"), facts.get("scene_audio"), facts.get("scene_markers"), Lh,
                                 float(facts.get("her_fps") or fps), tl["cut"], fps, tl["planned_end"])
    plan["footprint"] = facts.get("footprint")
    plan["apply_ready"] = not refusals
    return plan


# ----- live writers (APPLY) ------------------------------------------------------------------------------------------

def _add_float(binding, prop, path, sections, interp, run, label):          # prec curtain_sleight.py:1801-1816
    """ONE float track, one RESTORE_STATE section per (range, keys) in `sections` (intro and outro share a track)."""
    t = binding.add_track(unreal.MovieSceneFloatTrack)
    t.set_property_name_and_path(unreal.Name(prop), path)
    t.set_display_name(PREFIX + prop)
    for rng, keys in sections:
        s = t.add_section()
        s.set_range(int(rng[0]), int(rng[1]))
        s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        ch = list(s.get_all_channels())
        if len(ch) != 1:
            _stop(run, "FLOAT_CHANNELS|%s|%d|NOTHING SAVED; Don't-Save restart" % (label, len(ch)))
        for f, v in keys:
            ch[0].add_key(unreal.FrameNumber(int(f)), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                          interpolation=interp)
        got = sorted(_ch_keys(ch[0]))
        want = sorted([[int(f), float(v)] for f, v in keys])
        # float channels store float32 (7 Oct live: ManualFocusDistance ~600 cm failed a 4-decimal compare)
        if len(got) != len(want) or any(g[0] != w[0] or abs(float(g[1]) - w[1]) > max(1e-3, 1e-6 * abs(w[1]))
                                        for g, w in zip(got, want)):
            _stop(run, "KEY_READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, prop))
    return t


def _possess(seq, obj, name, shared):
    """add_possessable, but NEVER rename a binding someone else owns. 7 Oct [meas]: both live records' hookin_after
    lack the four env 'Hers Dark' names that their 'before' has, and no APPLY step removes a binding, so
    add_possessable on an actor the hookin already binds returned THAT binding and set_display_name renamed it
    [inf: the only explanation the records allow; MovieSceneSequenceExtensions.h:403-411 says 'new binding'].
    A reused binding is listed in `shared` (guid + its own name) and keeps its name; REVERT removes only OUR tracks
    (display name PREFIX...) and OUR child bindings from it."""
    gs = unreal.GuidLibrary.conv_guid_to_string
    before = {gs(b.get_id()) for b in seq.get_bindings()}
    b = seq.add_possessable(obj)
    g = gs(b.get_id())
    if g in before:
        shared.append({"guid": g, "name": str(b.get_display_name()), "wanted": name})
        return b
    b.set_display_name(name)
    return b


def _bind_component(seq, actor, comp, label, shared):          # prec curtain_sleight.py:1918-1928
    b = _possess(seq, actor, PREFIX + label, shared)
    kb = _possess(seq, comp, PREFIX + label + "/Component", shared)
    if not any(x["guid"] == unreal.GuidLibrary.conv_guid_to_string(kb.get_id()) for x in shared):
        kb.set_parent(b)
    return b, kb


def _add_color_black(seq, actor, label, rng, run, shared):
    comp = actor.get_component_by_class(unreal.LightComponent)
    _b, kb = _bind_component(seq, actor, comp, label, shared)
    t = kb.add_track(unreal.MovieSceneColorTrack)
    t.set_property_name_and_path(unreal.Name("LightColor"), "LightColor")
    t.set_display_name(PREFIX + "LightColor")
    s = t.add_section()
    s.set_range(int(rng[0]), int(rng[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    chans = list(s.get_all_channels())
    if len(chans) != 4:
        _stop(run, "COLOR_CHANNELS|%s|%d" % (label, len(chans)))
    for c, v in zip(chans, (0.0, 0.0, 0.0, 1.0)):
        c.set_default(v)
    return s


def _add_color_const(kb, label, rng, rgba, run):
    """v3: her LightColor at Lh held over [land, cut) on OUR component binding (her copy keys LightColor from the cut,
    so the colour is continuous across it [inf: same property, same value at Lh])."""
    t = kb.add_track(unreal.MovieSceneColorTrack)
    t.set_property_name_and_path(unreal.Name("LightColor"), "LightColor")
    t.set_display_name(PREFIX + "LightColor")
    s = t.add_section()
    s.set_range(int(rng[0]), int(rng[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    chans = list(s.get_all_channels())
    if len(chans) != len(rgba) or len(chans) != 4:
        _stop(run, "COLOR_CHANNELS|%s|%d vs %d|NOTHING SAVED; Don't-Save restart" % (label, len(chans), len(rgba)))
    for c, v in zip(chans, rgba):
        c.set_default(float(v))
    got = [float(c.get_default()) for c in chans]
    if any(abs(g - float(w)) > max(1e-3, 1e-6 * abs(float(w))) for g, w in zip(got, rgba)):
        _stop(run, "COLOR_READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, got))
    return s


def _add_color_keys(seq, actor, label, rng, keys, run, shared):
    """LightColor keyed (LINEAR) - fades a ceiling glow out/in on top of the rise's Intensity keys (multiplicative,
    so nothing fights the Arrival/rise owner, InfinityStageArrival.cpp:282-289)."""
    comp = actor.get_component_by_class(unreal.LightComponent)
    _b, kb = _bind_component(seq, actor, comp, label, shared)
    t = kb.add_track(unreal.MovieSceneColorTrack)
    t.set_property_name_and_path(unreal.Name("LightColor"), "LightColor")
    t.set_display_name(PREFIX + "LightColor")
    sc = t.add_section()
    sc.set_range(int(rng[0]), int(rng[1]))
    sc.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    chans = list(sc.get_all_channels())
    if len(chans) != 4:
        _stop(run, "COLOR_CHANNELS|%s|%d" % (label, len(chans)))
    lin = unreal.MovieSceneKeyInterpolation.LINEAR
    for f, rgba in keys:
        for c, v in zip(chans, rgba):
            c.add_key(unreal.FrameNumber(int(f)), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                      interpolation=lin)
    got = [len(_ch_keys(c)) for c in chans]
    if got != [len(keys)] * 4:
        _stop(run, "COLOR_KEY_READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, got))
    return sc


def _add_lattice_cancel(seq, actor, plan_lat, run, shared):
    """ADDITIVE transform section on the Lattice Fly in OUR Scene: Location.Z = cancel_keys, all else 0 [inf: the
    Scene's additive adds onto the rise's absolute; PIE stills over the old lowering window must confirm]."""
    b = _possess(seq, actor, PREFIX + "Lattice Hold: " + str(actor.get_actor_label()), shared)
    t = b.add_track(unreal.MovieScene3DTransformTrack)
    t.set_display_name(PREFIX + "Lattice Hold")
    sc = t.add_section()
    sc.set_blend_type(unreal.MovieSceneBlendType.ADDITIVE)                     # [inf] probed
    sc.set_range(int(plan_lat["range"][0]), int(plan_lat["range"][1]))
    sc.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    cm = _chan_map(sc)
    for n, c in cm.items():
        c.set_default(0.0)
    z = cm["Location.Z"]
    interp = {"cubic": unreal.MovieSceneKeyInterpolation.USER, "linear": unreal.MovieSceneKeyInterpolation.LINEAR,
              "constant": unreal.MovieSceneKeyInterpolation.CONSTANT}
    for k in plan_lat["cancel"]["keys"]:
        key = z.add_key(unreal.FrameNumber(int(k["tick"])), float(k["value"]), 0.0,
                        time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION, interpolation=interp[k["interp"]])
        if k["interp"] == "cubic":
            key.set_tangent_mode(unreal.RichCurveTangentMode.RCTM_USER)
            key.set_arrive_tangent(float(k["arrive"]))
            key.set_leave_tangent(float(k["leave"]))
            if k.get("weighted") and k.get("arrive_w") is not None:
                key.set_tangent_weight_mode(unreal.RichCurveTangentWeightMode.RCTWM_WEIGHTED_BOTH)
                key.set_arrive_tangent_weight(float(k["arrive_w"]))
                key.set_leave_tangent_weight(float(k["leave_w"]))
    got = [{"tick": int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
            "value": float(k.get_value()), "arrive": float(k.get_arrive_tangent()), "leave": float(k.get_leave_tangent())}
           for k in z.get_keys()]
    want = plan_lat["cancel"]["keys"]
    if len(got) != len(want) or any(g["tick"] != w["tick"] or abs(g["value"] - w["value"]) > 1e-3 or
                                    (w["interp"] == "cubic" and (abs(g["arrive"] - w["arrive"]) > 1e-6 or
                                                                 abs(g["leave"] - w["leave"]) > 1e-6))
                                    for g, w in zip(got, want)):
        _stop(run, "LATTICE_CANCEL_READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    _bt = sc.get_blend_type()          # 7 Oct live: an OptionalMovieSceneBlendType struct {blend_type, is_valid}
    _bt = _bt.get_editor_property("blend_type") if hasattr(_bt, "get_editor_property") else _bt
    if _enum_name(_bt).upper() not in ("ADDITIVE",):
        _stop(run, "LATTICE_BLEND_TYPE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % sc.get_blend_type())
    return got


def _add_visibility(seq, actor, label, rng, hidden, shared):  # prec klara_hookin.py:1143-1159
    b = _possess(seq, actor, PREFIX + "Hide: " + label, shared)
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    if str(t.get_property_name()) in ("None", ""):
        t.set_property_name_and_path("bHiddenInGame", "bHiddenInGame")
    if str(t.get_property_name()) != "bHiddenInGame":
        raise PlanError("VISIBILITY_TRACK_PROPERTY: %r" % str(t.get_property_name()))
    t.set_display_name(PREFIX + "Visibility")          # v3: REVERT finds OUR tracks on a shared binding by name
    s = t.add_section()
    s.set_range(int(rng[0]), int(rng[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    list(s.get_all_channels())[0].set_default(bool(hidden))
    return b


def _shift_copy(copy, world, level_pkg, delta, run, sign=1.0):
    """Shift every top-level unattached transform binding of the COPY by delta (klara_hookin.py:1087-1139 rules)."""
    names = {}
    for a in _level_actors(world, level_pkg):
        names.setdefault(str(a.get_actor_label()), []).append(a)
        if str(a.get_name()) != str(a.get_actor_label()):
            names.setdefault(str(a.get_name()), []).append(a)
    log = []
    d = [sign * x for x in delta]
    for b in copy.get_bindings():
        parent = b.get_parent()
        if parent is not None and hasattr(parent, "is_valid") and parent.is_valid():
            continue
        tracks = [t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)]
        if not tracks:
            continue
        nm = str(b.get_display_name())
        acts = names.get(nm, [])
        if len(acts) > 1:
            _stop(run, "SHIFT_AMBIGUOUS|%s|NOTHING SAVED; Don't-Save restart" % nm)
        if acts and acts[0].get_attach_parent_actor() is not None:
            log.append({"binding": nm, "skipped": "attached"})
            continue
        for t in tracks:
            for s in t.get_sections():
                cm = _chan_map(s)
                if not all("Location." + a in cm for a in "XYZ"):
                    continue
                chans = {ax: cm["Location." + ax.upper()] for ax in "xyz"}
                before = {ax: {"keys": _ch_keys(c), "default": float(c.get_default()) if c.has_default() else None}
                          for ax, c in chans.items()}
                want = shift_channels(before, d)
                for ax, c in chans.items():
                    for k, (_t, v) in zip(c.get_keys(), want[ax]["keys"]):
                        k.set_value(v)
                    if want[ax]["default"] is not None:
                        c.set_default(want[ax]["default"])
                got = {ax: [[t2, round(v2, 4)] for t2, v2 in _ch_keys(c)] for ax, c in chans.items()}
                if any(len(got[ax]) != len(want[ax]["keys"]) or any(g[0] != w[0] or abs(g[1] - w[1]) > 1e-2
                       for g, w in zip(got[ax], want[ax]["keys"])) for ax in "xyz"):   # float32-tolerant (7 Oct)
                    _stop(run, "SHIFT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % nm)
                log.append({"binding": nm, "keys": {ax: len(before[ax]["keys"]) for ax in "xyz"}})
    return log


def _move_level(world, pkg, new_lt, run):
    """Remove + re-add with the new LevelTransform (decl EditorLevelUtils.h:276-277; remove as klara_hookin.py:1019).
    Read back: the streaming transform AND one unkeyed actor's world delta."""
    probe = [a for a in _level_actors(world, pkg) if a.get_class().get_name() == "StaticMeshActor"]
    before = {str(a.get_path_name()): _v(a.get_actor_location()) for a in probe[:5]}
    lvls = [lv for lv in unreal.EditorLevelUtils.get_levels(world) if lv.get_outer() is not None
            and _path(lv.get_outer()) == pkg]
    if len(lvls) != 1:
        _stop(run, "MOVE_LEVEL_COUNT|%d" % len(lvls))
    if not unreal.EditorLevelUtils.remove_level_from_world(lvls[0], True, False):
        _stop(run, "REMOVE_LEVEL_FAILED|NOTHING SAVED; Don't-Save restart")
    tr = unreal.Transform(unreal.Vector(*new_lt["loc"]), unreal.Rotator(0.0, 0.0, float(new_lt["yaw"])),
                          unreal.Vector(1, 1, 1))
    ls = unreal.EditorLevelUtils.add_level_to_world_with_transform(world, pkg, unreal.LevelStreamingDynamic, tr)
    if ls is None:
        _stop(run, "ADD_LEVEL_NONE|NOTHING SAVED; Don't-Save restart")
    ls.set_editor_property("initially_loaded", True)
    ls.set_editor_property("initially_visible", False)
    lt = ls.get_editor_property("level_transform")
    if max(abs(a - b) for a, b in zip(_v(lt.translation), new_lt["loc"])) > 0.5:
        _stop(run, "LEVEL_TRANSFORM_READBACK|NOTHING SAVED; Don't-Save restart")
    after = {str(a.get_path_name()): _v(a.get_actor_location()) for a in _level_actors(world, pkg)
             if str(a.get_path_name()) in before}
    return {"probe_before": before, "probe_after": after}


def _label(args, key):
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues") if c.get_editor_property("type") == unreal.InfinityCueType.SCENE
            and _path(c.get_editor_property("scene").get_editor_property("sequence")) == args["scenes"][key]["scene_sequence"]]
    return str(cues[0].get_editor_property("label")) if len(cues) == 1 else None


def run_dry(args, run, world):
    key = str(args["scene"])
    facts, _seq, _copy = gather(args, world, run)
    facts["label"] = _label(args, key)
    ppv = _by_label("S%s Hangar Pinned Exposure" % key)
    facts["our_ppv"] = [{"label": str(p.get_actor_label()), "priority": float(p.get_editor_property("priority"))}
                        for p in ppv]
    plan = build_plan(facts, args)
    report = {"tool": TOOL, "run": run, "args": args, "api_table": _api_table(), "facts": facts, "plan": plan,
              "census": _census()}
    out = os.path.join(_here(), "klara_reveal_dry_S%s.json" % key)
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, sort_keys=True, default=str)
    for r in report["api_table"]:
        unreal.log("KLARAREVEAL_API|run=%s|ok=%d|%s|%s|%s" % (run, int(r["ok"]), r["api"], r["tier"], r["result"]))
    p = plan
    unreal.log("KLARAREVEAL_PLACE|run=%s|S%s|delta=%s|lead=%.0f|lateral=%.0f|fits=%s|set_local=%s|proposal=%s"
               % (run, key, [round(x, 1) for x in p["placement"]["delta"]], p["placement"]["lead_cm"],
                  p["placement"]["lateral_cm"], p["placement"]["fits"], [round(x) for x in p["placement"]["set_local_after"]],
                  p["hangar_proposal"]["params"]))
    unreal.log("KLARAREVEAL_TIMELINE|run=%s|S%s|%s" % (run, key, json.dumps({k: v for k, v in p["timeline"].items()
                                                                            if k not in ("refusals", "warnings")})))
    if p.get("glide"):
        unreal.log("KLARAREVEAL_GLIDE|run=%s|S%s|in=%s|out=%s" % (run, key, json.dumps(p["glide"]["in"]),
                                                                  json.dumps(p["glide"]["out"])))
    lit = p.get("lit") or {}
    unreal.log("KLARAREVEAL_LIT|run=%s|S%s|v3=%s|method=%s|frame=%s|raw=%s|s_into_her=%s|her_time_s=%s|ever_lit=%s|needed=%s|"
               "sum_frame=%s|window=%s" % (run, key, lit.get("v3"), lit.get("method"), lit.get("frame"), lit.get("frame_raw"),
                                           lit.get("s_into_her"), lit.get("her_time_s"), lit.get("n_ever_lit"),
                                           lit.get("n_needed"), lit.get("sum_frame"), lit.get("window")))
    for lab, row in sorted((lit.get("per_light") or {}).items()):
        unreal.log("KLARAREVEAL_LIT_LIGHT|run=%s|S%s|%s|%s" % (run, key, lab, json.dumps(row)[:1500]))
    unreal.log("KLARAREVEAL_LIT_CAMERA|run=%s|S%s|%s" % (run, key, json.dumps(lit.get("camera"), default=str)))
    unreal.log("KLARAREVEAL_SLOT|run=%s|S%s|%s" % (run, key, json.dumps(p.get("slot"), default=str)))
    unreal.log("KLARAREVEAL_AUDIO|run=%s|S%s|%s" % (run, key, json.dumps(
        {k: v for k, v in (p.get("audio") or {}).items() if k != "scene_audio_all"}, default=str)[:3000]))
    for r in p.get("her_lights") or []:
        unreal.log("KLARAREVEAL_LIGHT|run=%s|S%s|%s|%s|strikes=%s|strike_s=%s|target=%s|first=%s|blink=%s|her_keys=%s|"
                   "colour=%s" % (run, key, r["label"], r["class"], r.get("strikes"), r["strike_s"], r.get("target_intro"),
                                  r["target_first"], r["blink_frame"], r["her_keys"], r.get("color_lit")))
    for h in p.get("hangar_lights") or []:
        unreal.log("KLARAREVEAL_HANGAR_LIGHT|run=%s|S%s|%s|%s|%s" % (run, key, h["label"], h["action"], h.get("reach")))
    for e in p.get("her_env") or []:
        unreal.log("KLARAREVEAL_ENV|run=%s|S%s|%s|%s|%s|level=%s|at_lit=%s|her_keyed=%s"
                   % (run, key, e["label"], e["class"], e.get("property"), e.get("value"), e.get("target_intro"),
                      e.get("her_keyed")))
    lat = p.get("lattice") or {}
    unreal.log("KLARAREVEAL_LATTICE|run=%s|S%s|mode=%s|facts=%s|lowers_cm=%s|lowers_scene_frames=%s"
               % (run, key, lat.get("mode"), json.dumps(lat.get("facts"), default=str)[:1500],
                  (lat.get("cancel") or {}).get("lowers_cm"), lat.get("lowers_scene_frames")))
    fpr = facts.get("footprint") or {}
    unreal.log("KLARAREVEAL_FOOTPRINT|run=%s|S%s|box=%s|kept=%d|excluded=%s" % (run, key, fpr.get("box"),
               fpr.get("kept_count", 0), json.dumps(fpr.get("excluded"))[:3000]))
    unreal.log("KLARAREVEAL_SEES|run=%s|S%s|%s|hide=%s" % (run, key, p.get("first_frame_sees"), p.get("hide")))
    unreal.log("KLARAREVEAL_UNRESOLVED|run=%s|S%s|%s" % (run, key, facts["copy_bindings_unresolved"]))
    unreal.log("KLARAREVEAL_EXTEND_FIRST|run=%s|S%s|extend_scene_playback_mode=%s"
               % (run, key, json.dumps(p.get("extend_mode"), ensure_ascii=False)))
    for t in p["refusals"]:
        unreal.log_warning("KLARAREVEAL_REFUSAL|run=%s|%s" % (run, t))
    for t in p["warnings"]:
        unreal.log("KLARAREVEAL_WARNING|run=%s|%s" % (run, t))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("KLARAREVEAL_DRY_OK|run=%s|scene=S%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|relength_first=%d|report=%s"
               % (run, key, int(p["apply_ready"]), len(p["refusals"]), len(p["warnings"]), int(bool(p.get("relength_first"))),
                  out))


def run_apply(args, run, world):
    key = str(args["scene"])
    row = args["scenes"][key]
    facts, seq, copy = gather(args, world, run)
    facts["label"] = _label(args, key)
    facts["our_ppv"] = [{"label": str(p.get_actor_label()), "priority": float(p.get_editor_property("priority"))}
                        for p in _by_label("S%s Hangar Pinned Exposure" % key)]
    plan = build_plan(facts, args)
    if plan["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(plan["refusals"]))
    if plan.get("relength_first"):
        _stop(run, "RELENGTH_FIRST|playback end %d != planned %d: run extend_scene_playback.py with %s"
              % (facts["playback"][1], plan["timeline"]["planned_end"], json.dumps(plan["extend_mode"])))
    tl = plan["timeline"]
    rpath = os.path.join(_here(), "klara_reveal_record_S%s.json" % key)
    files = [_file(EXPECTED_WORLD, ".umap"), _file(row["scene_sequence"], ".uasset"), _file(row["copy"], ".uasset")]
    folder = os.path.join(_project(), "Backups", "PreKlaraReveal-S%s-%s" % (key, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for src in files:
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        hs = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if hs[0] != hs[1]:
            _stop(run, "BACKUP_HASH|" + src)
        manifest.append({"source": src, "sha256": hs[1]})
    rec = {"schema": 1, "tool": TOOL, "run": run, "scene": key, "applied": False, "backup": folder, "manifest": manifest,
           "decided_by": args.get("decided_by"), "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "before": {"level_transform": facts["level_transform"], "cuts": facts["cuts"], "playback": facts["playback"],
                      "hookin_bindings": facts["hookin_bindings"],
                      "slot": {"range": facts["slot_live"][:2], "offset_tick": facts["slot_offset_tick_live"]}},
           "shared_bindings": [],
           "plan": {k: v for k, v in plan.items() if k != "glide"}, "glide_report": plan["glide"]["in"]}
    write_record_exclusive(rpath, rec)
    # 1. level + copy (same delta)
    rec["level_move"] = _move_level(world, row["level"], plan["level_transform_after"], run)
    rec["copy_shift"] = _shift_copy(copy, world, row["level"], plan["placement"]["delta"], run)
    update_record(rpath, rec)
    # 2. glide camera (a level actor, unattached, world keys) [prec curtain_sleight.py:1837-1852]
    shared = rec["shared_bindings"]                     # filled by _possess; saved with the record below
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    k0 = plan["glide"]["keys"][0]
    cam = sub.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(*k0[1:4]),
                                     unreal.Rotator(roll=k0[4], pitch=k0[5], yaw=k0[6]), False)
    cam.set_actor_label(plan["glide"]["camera_label"])
    cam.tags = [unreal.Name("KlaraReveal.S%s" % key)]
    comp = cam.get_cine_camera_component()
    fb = comp.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", float(plan["sensor_mm"][0]))
    fb.set_editor_property("sensor_height", float(plan["sensor_mm"][1]))
    comp.set_editor_property("filmback", fb)
    fs = comp.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    comp.set_editor_property("focus_settings", fs)
    cb = _possess(seq, cam, PREFIX + plan["glide"]["camera_label"], shared)
    kb = _possess(seq, comp, PREFIX + plan["glide"]["camera_label"] + "/CameraComponent", shared)
    if shared:
        _stop(run, "GLIDE_CAMERA_ALREADY_BOUND|%s|NOTHING SAVED; Don't-Save restart" % shared)
    kb.set_parent(cb)
    tr = cb.add_track(unreal.MovieScene3DTransformTrack)
    tr.set_display_name(PREFIX + "Glide")
    ts = tr.add_section()
    ts.set_range(0, tl["planned_end"])
    ts.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    cm = _chan_map(ts)
    for n in ("Scale.X", "Scale.Y", "Scale.Z"):
        cm[n].set_default(1.0)                                       # scene_exit_block.py:775 [prec]
    lin = unreal.MovieSceneKeyInterpolation.LINEAR
    names = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")
    for k in plan["glide"]["keys"]:
        for i, n in enumerate(names):
            cm[n].add_key(unreal.FrameNumber(int(k[0])), float(k[1 + i]), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                          interpolation=lin)
    _add_float(kb, "CurrentFocalLength", "CurrentFocalLength",
               [([0, tl["planned_end"]], [[k[0], k[7]] for k in plan["glide"]["keys"]])], lin, run, "glide")
    _add_float(kb, "ManualFocusDistance", "FocusSettings.ManualFocusDistance",
               [([0, tl["planned_end"]], [[k[0], k[8]] for k in plan["glide"]["keys"]])], lin, run, "glide")
    # 3. her lights: intro strike [L, C), outro blink [E, end)
    const = unreal.MovieSceneKeyInterpolation.CONSTANT
    her = {str(a.get_actor_label()): a for a in _level_actors(world, row["level"])}
    for r in plan["her_lights"]:
        a = her.get(r["label"])
        if a is None:
            _stop(run, "HER_LIGHT_GONE|%s|NOTHING SAVED; Don't-Save restart" % r["label"])
        _b, lkb = _bind_component(seq, a, a.get_component_by_class(unreal.LightComponent), r["label"], shared)
        _add_float(lkb, "Intensity", "Intensity", [([tl["land"], tl["cut"]], r["intro_keys"]),
                                                   ([tl["slot"][1], tl["planned_end"]], r["outro_keys"])],
                   const, run, r["label"])
        if r.get("intro_color"):                       # v3: her LightColor at Lh over [land, cut)
            _add_color_const(lkb, r["label"], r["intro_color"]["range"], r["intro_color"]["rgba"], run)
    # 4. her environment: crossfade in [G0, C), fade out [E, end)
    for e in plan["her_env"]:
        if e.get("action") != "ramp":
            continue
        a = her.get(e["label"])
        if e["class"] == "PostProcessVolume":
            tgt = _possess(seq, a, PREFIX + e["label"], shared)
        else:
            comp_e = a.get_component_by_class(unreal.ExponentialHeightFogComponent if e["class"] == "ExponentialHeightFog"
                                              else unreal.LightComponentBase)
            _b, tgt = _bind_component(seq, a, comp_e, e["label"], shared)
        _add_float(tgt, e["property"], e["property"],
                   [([tl["crossfade"][0], tl["cut"]], e["intro"]),
                    ([tl["env_out"][0], tl["planned_end"]], dedupe_keys(e["outro"] + [[tl["planned_end"] - 1, 0.0]]))],
                   lin, run, e["label"])
    # 5. our hangar lights (non-ceiling black; ceiling glows fade out before her lights, back in the outro)
    for h in plan["hangar_lights"]:
        a = _one(h["label"], run)
        if h["action"] == "black_color":
            _add_color_black(seq, a, h["label"], h["range"], run, shared)
        elif h["action"] == "fade_color":
            _add_color_keys(seq, a, h["label"], h["range"], h["color_keys"], run, shared)
        elif h["action"] == "clamp_radius":
            _b, hk = _bind_component(seq, a, a.get_component_by_class(unreal.LightComponent), h["label"], shared)
            _add_float(hk, "AttenuationRadius", "AttenuationRadius", [([0, tl["planned_end"]], [[0, h["clamp_cm"]]])],
                       const, run, h["label"])
    # 6. roof (+ seen walls) hidden; rig bulbs hidden while the rig is dark
    for lab in plan["hide"]["labels"]:
        _add_visibility(seq, _one(lab, run), lab, plan["hide"]["range"], True, shared)
    for lab in plan["rig_bulbs_hidden"]["labels"]:
        _add_visibility(seq, _one(lab, run), lab, plan["rig_bulbs_hidden"]["range"], True, shared)
    # 6b. the ceiling rig does not lower
    lat = plan["lattice"]
    if lat["mode"] == "cancel":
        rec["lattice_cancel"] = _add_lattice_cancel(seq, _one(LATTICE_FLY % key, run), lat, run, shared)
    elif lat["mode"] == "hide":
        for lab in lat["hide"]["labels"]:
            if lab not in plan["rig_bulbs_hidden"]["labels"]:
                _add_visibility(seq, _one(lab, run), lab, lat["hide"]["range"], True, shared)
    # 7. hookin windows: Hers Dark [L, C) -> [L, G0); Ours Off [C, E) -> [G0, end); her level visible [L, E) -> [L, end)
    he = plan["hookin_edits"]
    for b in seq.get_bindings():
        n = str(b.get_display_name())
        for t in b.get_tracks():
            for s in t.get_sections():
                if n.startswith(HOOK_HERS):
                    s.set_range(int(he["hers_dark_range"][0]), int(he["hers_dark_range"][1]))
                elif n.startswith(HOOK_OURS):
                    s.set_range(int(he["ours_off_range"][0]), int(he["ours_off_range"][1]))
    vis = [s for t in seq.get_tracks() if str(t.get_display_name()) == HOOK_VIS for s in t.get_sections()]
    if len(vis) != 1:
        _stop(run, "HOOKIN_VIS_SECTIONS|%d|NOTHING SAVED; Don't-Save restart" % len(vis))
    vis[0].set_range(int(he["level_visible_range"][0]), int(he["level_visible_range"][1]))
    # v3 read-back: EVERY hookin window the record had is still there under its own name, at the planned range
    got_h = {r["name"]: r["range"] for r in _hookin_bindings(seq)}
    for r in facts["hookin_bindings"]:
        n = r["name"]
        want = he["hers_dark_range"] if n.startswith(HOOK_HERS) else he["ours_off_range"] if n.startswith(HOOK_OURS) \
            else he["level_visible_range"]
        if got_h.get(n) != [int(want[0]), int(want[1])]:
            _stop(run, "HOOKIN_WINDOW_READBACK|%s|%s vs %s|NOTHING SAVED; Don't-Save restart" % (n, got_h.get(n), want))
    # 7b. slot: moves with the cut and (v3) starts INTO her copy at Lh: start_frame_offset = (Lh - her start) in her
    # ticks [prec klara_hookin.py:1058-1068 set_editor_property("parameters"); units inf, decided by the read-back:
    # the cut frame must play her Lh and the section end her playback end]
    if plan["slot"]["shift"] or plan["slot"]["start_offset_ticks"]:
        subs = [x for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) for x in t.get_sections()
                if x.get_sequence() is not None and _path(x.get_sequence()) == row["copy"]]
        if len(subs) != 1:
            _stop(run, "SLOT_SECTION_COUNT|%d|NOTHING SAVED; Don't-Save restart" % len(subs))
        subs[0].set_range(int(plan["slot"]["range"][0]), int(plan["slot"]["range"][1]))
        prm = subs[0].get_editor_property("parameters")
        prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(plan["slot"]["start_offset_ticks"])))
        subs[0].set_editor_property("parameters", prm)
        off = int(subs[0].get_editor_property("parameters").get_editor_property("start_frame_offset").value)
        child = subs[0].get_sequence()
        pf = lambda f: int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(subs[0], int(f), seq))
        mapped = [pf(plan["slot"]["her_frame_at_cut"]), pf(child.get_playback_end())]
        got_rng = [int(subs[0].get_start_frame()), int(subs[0].get_end_frame())]
        if off != int(plan["slot"]["start_offset_ticks"]) or mapped != list(plan["slot"]["range"]) or \
                got_rng != list(plan["slot"]["range"]):
            _stop(run, "SLOT_MAPPING_READBACK|offset %d want %d|her %d->%s, end->%s; range %s vs %s|NOTHING SAVED; "
                       "Don't-Save restart" % (off, plan["slot"]["start_offset_ticks"], plan["slot"]["her_frame_at_cut"],
                                               mapped[0], mapped[1], got_rng, plan["slot"]["range"]))
        rec["slot_moved"] = {"before": plan["slot"]["range_before"], "after": mapped,
                             "offset_before": facts["slot_offset_tick_live"], "offset_after": off}
    # 8. cuts: Entry | Glide | Exit
    cuts, ct = _cuts(seq)
    entry_guid = [c["guid"] for c in cuts if c["camera"] and "Entry Handoff" in c["camera"]]
    exit_guid = [c["guid"] for c in cuts if c["camera"] and "Exit Handoff" in c["camera"]]
    if len(set(entry_guid)) != 1 or len(set(exit_guid)) != 1:
        _stop(run, "CUT_CAMERAS|entry %s exit %s|NOTHING SAVED; Don't-Save restart" % (entry_guid, exit_guid))
    by_guid = {unreal.GuidLibrary.conv_guid_to_string(b.get_id()): b for b in seq.get_bindings()}
    for s in list(ct.get_sections()):
        ct.remove_section(s)
    for which, rng in plan["cuts_after"]:
        s = ct.add_section()
        b = cb if which == "glide" else by_guid[entry_guid[0] if which == "entry" else exit_guid[0]]
        s.set_camera_binding_id(seq.get_binding_id(b))                 # prec curtain_sleight.py:2118
        s.set_range(int(rng[0]), int(rng[1]))
    after_cuts, _t = _cuts(seq)
    if [c["range"] for c in after_cuts] != [r for _w, r in plan["cuts_after"]]:
        _stop(run, "CUT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % after_cuts)
    # 7 Oct live: re-adding her streamed level / binding her lights also dirties HER map package; allow exactly her
    # streamed levels (KK hookin levels), back the .umap up first, and save it with the rest.
    her_maps = sorted(m for m in _census()["maps"] if m != EXPECTED_WORLD and m in set(HER_LEVELS))
    gate = census_gate(_census(), [row["scene_sequence"], row["copy"]], [EXPECTED_WORLD] + her_maps)
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, folder))
    for m in her_maps:
        src = os.path.join("E:/PussStage/Content", m[len("/Game/"):] + ".umap")
        if os.path.exists(src):
            shutil.copy2(src, folder)
    for p in [row["scene_sequence"], row["copy"]] + her_maps:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % p)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        _stop(run, "SAVE_MAP_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    rec.update(applied=True, cuts_after=after_cuts, hookin_after=_hookin_bindings(seq), glide_camera=plan["glide"]["camera_label"],
               version=3)
    update_record(rpath, rec)
    unreal.log("KLARAREVEAL_APPLY_OK|run=%s|scene=S%s|backup=%s|record=%s|next=rebuild_managed_master + "
               "SavedMasterMatchesShow + SceneCutBindingsResolve + live check_scene_cut_bindings" % (run, key, folder, rpath))


def _binding_rows(seq):
    gs = unreal.GuidLibrary.conv_guid_to_string
    rows = []
    for b in seq.get_bindings():
        par = b.get_parent()
        pg = gs(par.get_id()) if (par is not None and hasattr(par, "is_valid") and par.is_valid()) else None
        rows.append({"guid": gs(b.get_id()), "name": str(b.get_display_name()), "parent": pg,
                     "tracks": [{"name": str(t.get_display_name()), "cls": t.get_class().get_name()}
                                for t in b.get_tracks()]})
    return rows


def _slot_now(seq, copy_path):
    subs = [x for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) for x in t.get_sections()
            if x.get_sequence() is not None and _path(x.get_sequence()) == copy_path]
    if len(subs) != 1:
        raise PlanError("SLOT_SECTION_COUNT: %d" % len(subs))
    return subs[0], {"range": [int(subs[0].get_start_frame()), int(subs[0].get_end_frame())],
                     "offset_tick": int(subs[0].get_editor_property("parameters")
                                        .get_editor_property("start_frame_offset").value)}


def run_revert(args, run, world):
    """v3 REVERT. Fixes the 7 Oct REVERT_READBACK: v1/v2 APPLY renamed the hookin's four env 'Hers Dark' bindings
    (add_possessable reuse, see _possess), so removing every 'Klara Reveal -' binding deleted them. revert_actions
    renames such legacy bindings back and strips only OUR tracks from shared ones. Read-back covers hookin windows,
    leftovers, cuts (range AND camera) and the slot (range AND start offset). Restore-from-backup stays the fallback
    (REVEAL_PLAN.md section 9.6)."""
    key = str(args["scene"])
    row = args["scenes"][key]
    rpath = os.path.join(_here(), "klara_reveal_record_S%s.json" % key)
    rec = load_json(rpath)
    seq = unreal.load_asset(row["scene_sequence"])
    copy = unreal.load_asset(row["copy"])
    if _hookin_bindings(seq) != rec["hookin_after"]:
        _stop(run, "STATE_DRIFTED|hookin bindings|nothing changed")
    before_names = {r["name"] for r in rec["before"]["hookin_bindings"]}
    act = revert_actions(_binding_rows(seq), before_names, [x["guid"] for x in rec.get("shared_bindings") or []])
    unreal.log("KLARAREVEAL_REVERT_PLAN|run=%s|%s" % (run, json.dumps(act)))
    if act["unrecoverable"]:
        _stop(run, "REVERT_UNRECOVERABLE|%s|nothing changed: restore from %s" % (act["unrecoverable"], rec.get("backup")))
    gs = unreal.GuidLibrary.conv_guid_to_string
    by = lambda: {gs(b.get_id()): b for b in seq.get_bindings()}
    for g, name in act["rename"]:
        by()[g].set_display_name(name)
    for g in act["strip"]:
        b = by().get(g)
        if b is None:
            _stop(run, "SHARED_BINDING_GONE|%s|NOTHING SAVED; Don't-Save restart" % g)
        for t in list(b.get_tracks()):
            if str(t.get_display_name()).startswith(PREFIX):
                b.remove_track(t)                     # returns None [memory puss-python-api-gotchas]: read back below
    for g in act["remove"]:
        b = by().get(g)
        if b is not None:
            b.remove()                                                    # prec klara_hookin.py:1282
    before = {r["name"]: r["range"] for r in rec["before"]["hookin_bindings"]}
    for b in seq.get_bindings():
        n = str(b.get_display_name())
        if n in before:
            for t in b.get_tracks():
                for sct in t.get_sections():
                    sct.set_range(int(before[n][0]), int(before[n][1]))
    for t in seq.get_tracks():
        if str(t.get_display_name()) == HOOK_VIS:
            for sct in t.get_sections():
                sct.set_range(int(before[HOOK_VIS][0]), int(before[HOOK_VIS][1]))
    cuts, ct = _cuts(seq)
    bg = by()
    for sct in list(ct.get_sections()):
        ct.remove_section(sct)
    for c in rec["before"]["cuts"]:
        if c["guid"] not in bg:
            _stop(run, "CUT_CAMERA_GONE|%s|NOTHING SAVED; Don't-Save restart" % c)
        sct = ct.add_section()
        sct.set_camera_binding_id(seq.get_binding_id(bg[c["guid"]]))
        sct.set_range(int(c["range"][0]), int(c["range"][1]))
    seqrec = load_json(os.path.join(_here(), "klara_hookin_seq_record.json"))["scenes"][key]["plan"]["timeline"]
    slot_before = (rec["before"].get("slot") or
                   {"range": [int(seqrec["cinematic"][0]), int(seqrec["cinematic"][1])], "offset_tick": 0})
    sub, _now = _slot_now(seq, row["copy"])
    sub.set_range(int(slot_before["range"][0]), int(slot_before["range"][1]))
    prm = sub.get_editor_property("parameters")
    prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(slot_before["offset_tick"])))
    sub.set_editor_property("parameters", prm)
    _shift_copy(copy, world, row["level"], rec["plan"]["placement"]["delta"], run, sign=-1.0)
    _move_level(world, row["level"], rec["before"]["level_transform"], run)
    for a in _by_label(rec["glide_camera"]):
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a)
    # read-back: every check names itself (7 Oct: one combined REVERT_READBACK could not say which part failed)
    bad = []
    hb = _hookin_bindings(seq)
    if hb != rec["before"]["hookin_bindings"]:
        bad.append("hookin %s vs %s" % (hb, rec["before"]["hookin_bindings"]))
    left = [r["name"] for r in _binding_rows(seq) if r["name"].startswith(PREFIX)] + \
        ["%s/%s" % (r["name"], t["name"]) for r in _binding_rows(seq) for t in r["tracks"] if t["name"].startswith(PREFIX)]
    if left:
        bad.append("leftovers %s" % left)
    got_cuts = [[c["guid"], c["range"]] for c in _cuts(seq)[0]]
    want_cuts = [[c["guid"], c["range"]] for c in rec["before"]["cuts"]]
    if got_cuts != want_cuts:
        bad.append("cuts %s vs %s" % (got_cuts, want_cuts))
    _sub, slot_got = _slot_now(seq, row["copy"])
    if slot_got != {"range": list(slot_before["range"]), "offset_tick": int(slot_before["offset_tick"])}:
        bad.append("slot %s vs %s" % (slot_got, slot_before))
    if _by_label(rec["glide_camera"]):
        bad.append("glide camera still in the level")
    if bad:
        _stop(run, "REVERT_READBACK|%s|NOTHING SAVED; Don't-Save restart (or restore from %s)"
              % (" || ".join(bad), rec.get("backup")))
    her_maps = sorted(m for m in _census()["maps"] if m != EXPECTED_WORLD and m in set(HER_LEVELS))
    gate = census_gate(_census(), [row["scene_sequence"], row["copy"]], [EXPECTED_WORLD] + her_maps)
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    folder = os.path.join(_project(), "Backups", "PreKlaraRevealRevert-S%s-%s" % (key, run))
    os.makedirs(folder, exist_ok=False)
    for src in [_file(EXPECTED_WORLD, ".umap"), _file(row["scene_sequence"], ".uasset"), _file(row["copy"], ".uasset")] + \
            [_file(m, ".umap") for m in her_maps]:
        if os.path.exists(src):
            shutil.copy2(src, folder)
    for pth in [row["scene_sequence"], row["copy"]] + her_maps:
        if not unreal.EditorAssetLibrary.save_asset(pth, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % pth)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        _stop(run, "SAVE_MAP_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAREVEAL_REVERT_OK|run=%s|scene=S%s|renamed_back=%d|stripped=%d|removed=%d|next=extend_scene_playback "
               "to the next APPLY's planned end (or back to %s), rebuild, tests"
               % (run, key, len(act["rename"]), len(act["strip"]), len(act["remove"]), rec["before"].get("playback")))


def main():
    args = globals().get("KLARAREVEAL_ARGS")
    if args is None:
        args = load_json(os.path.join(_here(), ARGS_NAME))
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAREVEAL-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = ed.get_game_world() is not None
    world = None if pie else ed.get_editor_world()
    wname = str(world.get_outermost().get_name()) if world is not None else None
    key = str(args["scene"])
    rpath = os.path.join(_here(), "klara_reveal_record_S%s.json" % key)
    here = _here()
    hook = [os.path.join(here, n) for n in ("klara_hookin_stream_record.json", "klara_hookin_seq_record.json")]
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie,
             "wrong_world": None if wname == EXPECTED_WORLD else str(wname),
             "sequencer_open": None if pie else _sequencer_open(), "census": _census(),
             "decided_by": args.get("decided_by"), "record_exists": rpath if os.path.exists(rpath) else None,
             "record_applied": os.path.exists(rpath) and bool(load_json(rpath).get("applied")),
             "hookin_applied": all(os.path.exists(p) and load_json(p).get("applied") for p in hook)}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None:
    main()
